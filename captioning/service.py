from __future__ import annotations

import asyncio
import functools
import json
import os
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Required, TypedDict

from PIL import Image

from . import __version__, capabilities, provider
from .bria import CaptionValidationError, normalize_json
from .errors import ProviderUnavailableError, UserError
from .media import is_video, probe
from .models import MEDIA_OUTPUTS, OUTPUT_NAMES, OUTPUT_SUFFIX, VIDEO_OUTPUTS, Settings, outputs_for
from .runtime import Runtime, nvidia_driver_installed
from .storage import KeyStore, fingerprint, preserve_damaged, read_json, save_json, write_caption
from .training import ALL_TYPES, TYPE_DEFAULTS, details_for
from .video import I2V_WORDS, validate_h3

MAX_IMAGES = 20000
MAX_KEY_LENGTH = 8192


class Status(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    SAVED = "saved"
    EXISTING = "existing"
    SKIPPED = "skipped"
    DRAFT = "draft"
    REVIEW = "review"
    ERROR = "error"
    INVALID = "invalid"


class Slot(TypedDict, total=False):
    """The caption of one output (Normal, BRIA JSON, WAN 2.2, ...) for one image."""

    caption: Required[str]
    status: Required[str]
    error: str
    notice: str
    exists: bool
    seconds: float | None
    phase: str
    generation_history: list[dict]


class Row(TypedDict, total=False):
    """One dataset image as stored in session.json and shown in the UI."""

    id: Required[str]
    path: Required[str]
    name: Required[str]
    # "image" or "clip"; a clip also has its probed ClipInfo.
    kind: str
    clip: dict
    # One slot per output that applies to the media; every output has its own caption file next to it.
    outputs: Required[dict[str, Slot]]
    # SHA-256 of each sidecar as last seen by the app; None when it did not exist.
    fingerprints: dict[str, str | None]
    width: int
    height: int


class Job(TypedDict, total=False):
    running: Required[bool]
    total: Required[int]
    completed: Required[int]
    saved: Required[int]
    errors: Required[int]
    review: Required[int]
    skipped: Required[int]
    message: Required[str]
    id: str
    output_format: str
    paused: bool
    remaining_ids: list[str]
    # [image id, output] pairs a paused batch still has to create.
    remaining_tasks: list[list[str]]
    resume_regenerate: bool


STATUSES = frozenset(Status)
SLOT_KEYS = ("caption", "status", "error", "notice", "exists", "seconds", "phase", "generation_history")
SLOT_DEFAULTS = {"error": "", "notice": "", "exists": False, "seconds": None}
LEGACY_ENCODING = "The existing caption is not UTF-8 text. Save it as UTF-8 or remove it, then load the dataset again."
# Notices from the time .txt and .json excluded each other (before 0.2.0).
RETIRED_NOTICES = {
    "Both .txt and .json exist. LoRA Studio currently prefers .txt. Saving or regenerating keeps the selected format and backs up the other one.",
    "The existing caption uses another format. Use Regenerate or turn off Skip existing captions to convert it.",
}
STAGE_LABELS = {
    "caption": "Captioning",
    "shorten": "Shortening caption",
    "complete": "Completing caption",
    "repair_json": "Repairing JSON",
    "retry_caption": "Requesting a response",
}


def valid_slot(slot) -> bool:
    return isinstance(slot, dict) and slot.get("status") in STATUSES and isinstance(slot.get("caption"), str)


def valid_row(row) -> bool:
    if not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in ("id", "path", "name")):
        return False
    if "outputs" in row:
        outputs = row["outputs"]
        return isinstance(outputs, dict) and all(k in OUTPUT_SUFFIX and valid_slot(v) for k, v in outputs.items())
    return valid_slot(row)  # Sessions before 0.2.0 kept one caption on the row itself.


def new_slot(**values) -> Slot:
    slot: Slot = {"caption": "", "status": Status.PENDING, "error": "", "notice": "", "exists": False, "seconds": None}
    slot.update(values)  # type: ignore[typeddict-item]
    return slot


def sidecar_names(image: Path) -> set[str]:
    """Every caption file name an image can have, for detecting two images that would share one."""
    return {(image.stem + suffix).casefold() for suffix in OUTPUT_SUFFIX.values()}


def shared_sidecar(names: set[str]) -> str:
    return f"Two files would share the caption file {min(names)}. Rename one of them."


def read_slot(image: Path, output: str) -> Slot:
    """The saved caption of one output, validated like a manual save."""
    target = image.with_suffix(OUTPUT_SUFFIX[output])
    if not target.exists():
        return new_slot()
    try:
        text = target.read_text(encoding="utf-8-sig").strip()
    except UnicodeDecodeError:
        # Older tools often saved captions in a legacy code page; never guess and overwrite.
        return new_slot(status=Status.INVALID, error=LEGACY_ENCODING)
    slot = new_slot(caption=text, exists=True, status=Status.EXISTING)
    try:
        if output == "bria_json":
            slot["caption"] = normalize_json(text)
        elif output == "h3":
            validate_h3(text)
    except (CaptionValidationError, UserError) as exc:
        slot.update({"status": Status.ERROR, "error": str(exc)})
    return slot


class Studio:
    def __init__(self, root: Path, notices: list[str] | None = None):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        # One-time startup messages, for example about moving the data folder.
        self.notices = notices or []
        # Unusable saved files are kept beside the originals under these names.
        self.recovered: list[str] = []
        self.settings = self._load_settings()
        self.keys = KeyStore(root / "keys.json", self.recovered)
        self.runtime = Runtime(root)
        # Without an NVIDIA card the setup starts on the cloud; the local model stays optional.
        self.nvidia_gpu = nvidia_driver_installed()
        self.rows: list[Row] = self._load_rows()
        self.job: Job = {
            "running": False,
            "total": 0,
            "completed": 0,
            "saved": 0,
            "errors": 0,
            "review": 0,
            "skipped": 0,
            "message": "Ready",
        }
        self.task: asyncio.Task | None = None
        self.importing = False

    def _load_settings(self) -> Settings:
        path = self.root / "settings.json"
        settings, damaged = Settings.recover(read_json(path, {}, self.recovered))
        if damaged:
            # Keep the original and continue with every value this version still accepts.
            self.recovered.append(preserve_damaged(path).name)
            save_json(path, settings.model_dump())
        return settings

    def _load_rows(self) -> list[Row]:
        path = self.root / "session.json"
        saved = read_json(path, [], self.recovered)
        rows: list[Row] = []
        migrated = False
        for row in saved if isinstance(saved, list) else []:
            if not valid_row(row):
                continue
            if "outputs" not in row:
                row, migrated = self._migrate_row(row), True
            for slot in row["outputs"].values():
                for key, value in SLOT_DEFAULTS.items():
                    slot.setdefault(key, value)  # type: ignore[misc]
                if slot["status"] in (Status.PROCESSING, Status.QUEUED):
                    slot.update(
                        {"status": Status.PENDING, "error": "The previous run was interrupted. You can continue."}
                    )
            row.setdefault("kind", "image")
            row.setdefault("width", 0)
            row.setdefault("height", 0)
            hashes = row.setdefault("fingerprints", {})
            for suffix in OUTPUT_SUFFIX.values():
                if suffix not in hashes:
                    try:
                        hashes[suffix] = fingerprint(Path(row["path"]).with_suffix(suffix))
                    except (UserError, OSError):
                        hashes[suffix] = None
            rows.append(row)
        if path.exists() and (not isinstance(saved, list) or len(rows) != len(saved)):
            self.recovered.append(preserve_damaged(path).name)
            save_json(path, rows)
        elif migrated:
            save_json(path, rows)
        return rows

    @staticmethod
    def _migrate_row(old: dict) -> Row:
        """A row from before 0.2.0: its one caption becomes the slot of its format, the rest come from disk."""
        image = Path(old["path"])
        slot = new_slot(**{key: old[key] for key in SLOT_KEYS if key in old})
        if slot["notice"] in RETIRED_NOTICES:
            slot["notice"] = ""
        if slot["status"] == Status.INVALID:
            outputs = {
                output: new_slot(status=Status.INVALID, error=slot["error"]) for output in MEDIA_OUTPUTS["image"]
            }
        else:
            outputs = {}
            for output in MEDIA_OUTPUTS["image"]:
                try:
                    outputs[output] = read_slot(image, output) if image.is_file() else new_slot()
                except OSError:
                    outputs[output] = new_slot()
            outputs["bria_json" if old.get("caption_format") == "bria_json" else "normal"] = slot
        hashes = old.get("fingerprints")
        if not isinstance(hashes, dict):
            # Sessions before 0.1.5 kept a single .txt hash.
            hashes = {".txt": old.get("fingerprint")}
        return {
            "id": old["id"],
            "path": old["path"],
            "name": old["name"],
            "kind": "image",
            "outputs": outputs,
            "fingerprints": hashes,
            "width": old.get("width", 0),
            "height": old.get("height", 0),
        }

    def idle(self):
        if self.job["running"] or self.importing:
            raise UserError("Wait for the operation to finish or stop the batch.")

    def persist(self):
        save_json(self.root / "session.json", self.rows)

    def save_settings(
        self,
        settings: Settings,
        api_key: str | None = None,
        clear_key=False,
        local_api_key: str | None = None,
        clear_local_key=False,
    ):
        self.idle()
        if self.runtime.installing or self.runtime.state["status"] == "loading":
            raise UserError("Wait for model setup to finish.")
        if len(api_key or "") > MAX_KEY_LENGTH or len(local_api_key or "") > MAX_KEY_LENGTH:
            raise UserError("The API key is too long.")
        if clear_key:
            self.keys.set(settings.cloud_url, "")
        elif api_key and api_key.strip():
            self.keys.set(settings.cloud_url, api_key.strip())
        if clear_local_key:
            self.keys.set("local:" + settings.local_url, "")
        elif local_api_key and local_api_key.strip():
            self.keys.set("local:" + settings.local_url, local_api_key.strip())
        save_json(self.root / "settings.json", settings.model_dump())
        self.settings = settings

    def snapshot(self):
        cloud_keys, local_keys = self.keys.endpoints()
        return {
            "version": __version__,
            "settings": self.settings.model_dump(),
            # Each LoRA type has its own details, names and defaults.
            "training_details": {t: details_for(t) for t in ALL_TYPES},
            "training_defaults": TYPE_DEFAULTS,
            # What the configured model follows reliably: greyed switches and the recommended length.
            "capabilities": capabilities.summary(self.settings),
            "caption_outputs": {o: {"suffix": OUTPUT_SUFFIX[o], "name": OUTPUT_NAMES[o]} for o in OUTPUT_SUFFIX},
            "video_outputs": VIDEO_OUTPUTS,
            "media_outputs": MEDIA_OUTPUTS,
            "has_key": self.keys.has(self.settings.cloud_url),
            "has_local_key": self.keys.has("local:" + self.settings.local_url),
            # Which API addresses have a saved key, so the setup can show it at a glance.
            "cloud_keys": cloud_keys,
            "local_keys": local_keys,
            "rows": self.rows,
            "job": self.job,
            "importing": self.importing,
            "runtime": self.runtime.snapshot(self.settings.model_profile, self.settings.backend),
            "nvidia_gpu": self.nvidia_gpu,
            "data_dir": str(self.root),
            "recovered": self.recovered,
            "notices": self.notices,
        }

    def local_key(self, settings: Settings):
        if settings.local_source == "managed":
            return self.runtime.api_key if self.runtime.process else ""
        return self.keys.get("local:" + settings.local_url)

    def row(self, image_id: str) -> Row:
        row = next((r for r in self.rows if r["id"] == image_id), None)
        if not row:
            raise UserError("The image is not in the open dataset.")
        return row

    @staticmethod
    def collision(image: Path):
        names = sidecar_names(image)
        for other in image.parent.iterdir():
            if other.name.casefold() != image.name.casefold() and other.suffix.lower() in provider.EXTENSIONS:
                shared = names & sidecar_names(other)
                if shared and other.is_file():
                    raise UserError(shared_sidecar(shared))

    def _scan(self, paths: list[str], folder: str, recursive: bool, append: bool) -> list[Row]:
        files: list[Path] = []
        if folder:
            directory = Path(folder).expanduser().resolve(strict=True)
            if not directory.is_dir():
                raise UserError("The selected path is not a folder.")
            # os.walk does not traverse directory symlinks. Avoid backup and dot folders.
            for current, dirs, names in os.walk(directory, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".")) if recursive else []
                files.extend(Path(current) / n for n in sorted(names) if Path(n).suffix.lower() in provider.EXTENSIONS)
        files.extend(Path(p).expanduser() for p in paths)
        unique = {
            str(p.resolve()).casefold(): p.resolve()
            for p in files
            if p.suffix.lower() in provider.EXTENSIONS and p.is_file()
        }
        if not unique:
            raise UserError("The selection contains no supported images or video clips.")
        if len(unique) > MAX_IMAGES:
            raise UserError(f"Open no more than {MAX_IMAGES} images in one dataset.")
        rows = list(self.rows) if append else []
        known = {r["path"].casefold() for r in rows}
        # Index each directory once; thousands of images must not trigger an O(n²) scan.
        claims: dict[Path, Counter[str]] = {}
        for parent in {p.parent for p in unique.values()}:
            claims[parent] = Counter(
                name
                for p in parent.iterdir()
                if p.is_file() and p.suffix.lower() in provider.EXTENSIONS
                for name in sidecar_names(p)
            )
        for path in sorted(unique.values(), key=lambda p: str(p).casefold()):
            if str(path).casefold() in known:
                continue
            kind = "clip" if is_video(path) else "image"
            row: Row = {
                "id": uuid.uuid4().hex,
                "path": str(path),
                "name": path.name,
                "kind": kind,
                "outputs": {},
                "width": 0,
                "height": 0,
            }
            try:
                shared = {name for name in sidecar_names(path) if claims[path.parent][name] > 1}
                if shared:
                    raise UserError(shared_sidecar(shared))
                if kind == "clip":
                    info = probe(path)
                    row.update({"width": info["width"], "height": info["height"], "clip": dict(info)})
                else:
                    with Image.open(path) as im:
                        row.update({"width": im.width, "height": im.height})
                        if getattr(im, "n_frames", 1) > 1:
                            raise UserError("Multi-frame images are not supported. Select a single frame.")
                        im.verify()
                row["fingerprints"] = {
                    suffix: fingerprint(path.with_suffix(suffix)) for suffix in OUTPUT_SUFFIX.values()
                }
                row["outputs"] = {output: read_slot(path, output) for output in MEDIA_OUTPUTS[kind]}
            except Exception as e:
                row["outputs"] = {
                    output: new_slot(status=Status.INVALID, error=str(e)) for output in MEDIA_OUTPUTS[kind]
                }
            rows.append(row)
        return rows

    async def import_images(self, paths: list[str], folder: str, recursive: bool, append: bool):
        self.idle()
        self.importing = True
        try:
            rows = await asyncio.to_thread(self._scan, paths, folder, recursive, append)
            self.rows = rows
            self.persist()
        finally:
            self.importing = False

    def save_row(self, image_id: str, text: str, output: str = "normal"):
        self.idle()
        if output not in OUTPUT_SUFFIX:
            raise UserError("Unknown caption output.")
        row = self.row(image_id)
        slot = row["outputs"][output]
        if slot["status"] == Status.INVALID:
            raise UserError(slot.get("error", ""))
        image = Path(row["path"])
        if not image.is_file():
            raise UserError("The original image no longer exists.")
        self.collision(image)
        self._write_row(row, output, text, overwrite=True)
        self.persist()

    @staticmethod
    def _check_sidecar(row: Row, suffix: str):
        if fingerprint(Path(row["path"]).with_suffix(suffix)) != row["fingerprints"].get(suffix):
            raise UserError("The caption was changed outside the app. Reload the dataset.")

    def _write_row(self, row: Row, output: str, text: str, overwrite: bool):
        """Write one output's caption file; the other caption files are never touched."""
        if output == "bria_json":
            text = normalize_json(text)
        elif output == "h3":
            validate_h3(text)
        suffix = OUTPUT_SUFFIX[output]
        self._check_sidecar(row, suffix)
        hashes = row["fingerprints"]
        hashes[suffix] = write_caption(Path(row["path"]), text, hashes.get(suffix), overwrite=overwrite, suffix=suffix)
        row["outputs"][output].update(
            {"caption": text.strip(), "exists": True, "status": Status.SAVED, "error": "", "notice": ""}
        )

    async def start_job(self, ids: list[str], regenerate=False, resume=False, output: str | None = None):
        """Create the recipe's outputs for the images, or only `output` (Regenerate in the inspector)."""
        self.idle()
        if output is not None and output not in OUTPUT_SUFFIX:
            raise UserError("Unknown caption output.")
        settings = self.settings.model_copy(deep=True)
        if resume and self.job.get("paused"):
            # Continue exactly the image and output pairs the paused batch had left.
            wanted, present = set(ids), {r["id"] for r in self.rows}
            pairs = [(i, o) for i, o in self.job.get("remaining_tasks", []) if i in wanted and i in present]
            tasks = [(self.row(i), o) for i, o in pairs]
        else:
            outputs = (output,) if output else outputs_for(settings.output_format)
            rows = [self.row(i) for i in dict.fromkeys(ids)]
            tasks = [(row, o) for row in rows for o in outputs if o in row["outputs"]]
        if not tasks:
            raise UserError("Select at least one image.")
        if settings.mode == "cloud":
            if not settings.cloud_model.strip():
                raise UserError("Select a cloud model with image support in Settings.")
            key = self.keys.get(settings.cloud_url)
            if not key:
                raise UserError("Enter this provider’s API key in Settings.")
        else:
            key = self.local_key(settings)
        self.job = {
            "running": True,
            "total": len(tasks),
            "completed": 0,
            "saved": 0,
            "errors": 0,
            "review": 0,
            "skipped": 0,
            "message": "Starting batch…",
            "id": uuid.uuid4().hex,
            "output_format": output or settings.output_format,
        }
        for row, task_output in tasks:
            if row["outputs"][task_output]["status"] != Status.INVALID:
                row["outputs"][task_output]["status"] = Status.QUEUED
        self.persist()
        self.task = asyncio.create_task(self._run(tasks, settings, key, regenerate))

    def _task_name(self, row: Row, output: str) -> str:
        """The image name, plus the model when one batch creates several outputs."""
        return row["name"] if self.job.get("output_format") == output else row["name"] + " · " + OUTPUT_NAMES[output]

    def _progress(self, row: Row, output: str, settings: Settings, event):
        slot = row["outputs"][output]
        stage = event.get("stage", "caption")
        slot["phase"] = stage
        self.job["message"] = STAGE_LABELS.get(stage, "Processing") + " · " + self._task_name(row, output)
        if event.get("kind") == "response":
            slot.setdefault("generation_history", []).append({k: v for k, v in event.items() if k != "kind"})
            self.persist()
        if event.get("kind") in ("response", "request_error"):
            self._log_generation(row, output, settings, event)

    def _log_generation(self, row: Row, output: str, settings: Settings, event):
        """Operational evidence without images, captions, prompts or credentials."""
        diagnostic = {
            "time": datetime.now(UTC).isoformat(),
            "job": self.job.get("id"),
            "image": row["id"],
            "output": output,
            "mode": settings.mode,
            "model": settings.cloud_model if settings.mode == "cloud" else settings.local_model_id,
            "target_words": settings.words,
            **{k: v for k, v in event.items() if k not in ("kind", "text", "draft")},
        }
        log = self.root / "logs" / "generation.jsonl"
        try:
            log.parent.mkdir(exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(diagnostic, ensure_ascii=False) + "\n")
        except OSError:
            pass  # Diagnostic logging must not turn a valid caption into a failure.

    async def _run(self, tasks: list[tuple[Row, str]], settings: Settings, key: str, regenerate: bool):
        try:
            for row, output in tasks:
                slot = row["outputs"][output]
                if slot["status"] == Status.INVALID:
                    self.job["errors"] += 1
                    self.job["completed"] += 1
                    continue
                image = Path(row["path"])
                suffix = OUTPUT_SUFFIX[output]
                if settings.skip_existing and not regenerate and image.with_suffix(suffix).exists():
                    slot.update({"status": Status.SKIPPED, "error": ""})
                    self.job["skipped"] += 1
                    self.job["completed"] += 1
                    continue
                slot.update({"status": Status.PROCESSING, "error": "", "phase": "caption", "generation_history": []})
                self.job["message"] = self._task_name(row, output)
                started = time.monotonic()
                task_settings = settings.model_copy(update={"output_format": output})
                if output == "wan_i2v":
                    # WAN's image-to-video prompts are short; the recipe's target only applies up to that length.
                    task_settings.words = min(settings.words, I2V_WORDS)
                try:
                    self.collision(image)
                    # Check for external edits before spending time or cloud credits.
                    self._check_sidecar(row, suffix)
                    progress = functools.partial(self._progress, row, output, task_settings)
                    result = await provider.generate(image, task_settings, key, on_progress=progress)
                    slot.update(
                        {
                            "caption": result.text,
                            "status": Status.DRAFT,
                            "notice": "",
                            "seconds": round(time.monotonic() - started, 1),
                        }
                    )
                    if result.needs_review:
                        slot["status"] = Status.REVIEW
                        self.job["review"] += 1
                    elif settings.auto_save:
                        self.collision(image)
                        self._write_row(row, output, result.text, overwrite=regenerate or not settings.skip_existing)
                        self.job["saved"] += 1
                    slot["notice"] = result.notice
                    slot["phase"] = ""
                except asyncio.CancelledError:
                    received = [h for h in slot.get("generation_history", []) if h.get("text")]
                    if received:
                        best = next((h for h in reversed(received) if h.get("complete")), received[0])
                        slot.update(
                            {
                                "caption": best["text"],
                                "status": Status.DRAFT if best.get("complete") else Status.REVIEW,
                                "error": "",
                                "notice": "Batch stopped. The received response has been kept as a draft.",
                                "phase": "",
                            }
                        )
                    else:
                        slot.update({"status": Status.PENDING, "error": "Processing was stopped.", "phase": ""})
                    raise
                except ProviderUnavailableError as e:
                    slot.update(
                        {
                            "status": Status.PENDING,
                            "error": "",
                            "phase": "",
                            "notice": "Waiting for the model connection to be restored.",
                        }
                    )
                    waiting = [(r, o) for r, o in tasks if r["outputs"][o]["status"] in (Status.QUEUED, Status.PENDING)]
                    self.job.update(
                        {
                            "paused": True,
                            "message": "Batch paused: " + str(e),
                            "remaining_ids": list(dict.fromkeys(r["id"] for r, _ in waiting)),
                            "remaining_tasks": [[r["id"], o] for r, o in waiting],
                            "resume_regenerate": regenerate,
                        }
                    )
                    return
                except Exception as e:
                    slot.update({"status": Status.ERROR, "error": str(e)})
                    if isinstance(e, CaptionValidationError):
                        slot["caption"] = e.draft
                    self.job["errors"] += 1
                self.job["completed"] += 1
                self.persist()
            self.job["message"] = (
                "Batch completed" if not self.job["errors"] else "Finished with errors — check the marked images"
            )
            if self.job["review"]:
                self.job["message"] += f" · {self.job['review']} drafts to review"
        except asyncio.CancelledError:
            self.job["message"] = "Batch stopped; saved captions have been preserved"
        finally:
            for row, output in tasks:
                if row["outputs"][output]["status"] in (Status.QUEUED, Status.PROCESSING):
                    row["outputs"][output]["status"] = Status.PENDING
            self.job["running"] = False
            self.persist()

    async def cancel_job(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            # Also handles cancellation before the task's coroutine first runs.
            for row in self.rows:
                for slot in row["outputs"].values():
                    if slot["status"] in (Status.QUEUED, Status.PROCESSING):
                        slot["status"] = Status.PENDING
            self.job.update({"running": False, "message": "Batch stopped; saved captions have been preserved"})
            self.persist()
        elif self.job.get("paused"):
            # A paused batch is not running; discarding it frees the images for a new selection.
            self.job.update(
                {
                    "paused": False,
                    "remaining_ids": [],
                    "remaining_tasks": [],
                    "message": "Batch discarded; saved captions have been preserved",
                }
            )
            self.persist()

    async def close(self):
        await self.cancel_job()
        self.runtime.cancel.set()
        if self.runtime.install_task:
            await self.runtime.install_task
        await asyncio.to_thread(self.runtime.stop)
