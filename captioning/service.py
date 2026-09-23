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

from . import __version__, provider
from .bria import CaptionValidationError, normalize_json
from .errors import ProviderUnavailableError, UserError
from .models import Settings
from .runtime import Runtime
from .storage import KeyStore, archive_sidecar, fingerprint, preserve_damaged, read_json, save_json, write_caption
from .training import ATTRIBUTES

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


class Row(TypedDict, total=False):
    """One dataset image as stored in session.json and shown in the UI."""

    id: Required[str]
    path: Required[str]
    name: Required[str]
    caption: Required[str]
    status: Required[str]
    caption_format: str
    # SHA-256 of each sidecar as last seen by the app; None when it did not exist.
    fingerprints: dict[str, str | None]
    error: str
    notice: str
    width: int
    height: int
    exists: bool
    seconds: float | None
    phase: str
    generation_history: list[dict]


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
    resume_regenerate: bool


STATUSES = frozenset(Status)
ROW_DEFAULTS = {
    "error": "",
    "notice": "",
    "width": 0,
    "height": 0,
    "exists": False,
    "seconds": None,
    "caption_format": "normal",
}
STAGE_LABELS = {
    "caption": "Captioning",
    "shorten": "Shortening caption",
    "complete": "Completing caption",
    "repair_json": "Repairing JSON",
    "retry_caption": "Requesting a response",
}


def valid_row(row) -> bool:
    return (
        isinstance(row, dict)
        and row.get("status") in STATUSES
        and all(isinstance(row.get(key), str) for key in ("id", "path", "name", "caption"))
    )


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
        for row in saved if isinstance(saved, list) else []:
            if not valid_row(row):
                continue
            for key, value in ROW_DEFAULTS.items():
                row.setdefault(key, value)
            # Sessions from before 0.1.5 kept a single .txt hash.
            legacy_txt = row.pop("fingerprint", None)
            if not isinstance(row.get("fingerprints"), dict):
                try:
                    json_hash = fingerprint(Path(row["path"]).with_suffix(".json"))
                except (UserError, OSError):
                    json_hash = None
                row["fingerprints"] = {".txt": legacy_txt, ".json": json_hash}
            if row["status"] in (Status.PROCESSING, Status.QUEUED):
                row.update({"status": Status.PENDING, "error": "The previous run was interrupted. You can continue."})
            rows.append(row)
        if path.exists() and (not isinstance(saved, list) or len(rows) != len(saved)):
            self.recovered.append(preserve_damaged(path).name)
            save_json(path, rows)
        return rows

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
        return {
            "version": __version__,
            "settings": self.settings.model_dump(),
            "training_attributes": ATTRIBUTES,
            "has_key": self.keys.has(self.settings.cloud_url),
            "has_local_key": self.keys.has("local:" + self.settings.local_url),
            "rows": self.rows,
            "job": self.job,
            "importing": self.importing,
            "runtime": self.runtime.snapshot(self.settings.model_profile, self.settings.backend),
            "data_dir": str(self.root),
            "recovered": self.recovered,
            "notices": self.notices,
        }

    def local_key(self, settings: Settings):
        if settings.local_source == "managed":
            return self.runtime.api_key if self.runtime.process else ""
        return self.keys.get("local:" + settings.local_url)

    def row(self, image_id: str):
        row = next((r for r in self.rows if r["id"] == image_id), None)
        if not row:
            raise UserError("The image is not in the open dataset.")
        return row

    @staticmethod
    def collision(image: Path):
        matches = [
            p.name
            for p in image.parent.iterdir()
            if p.is_file() and p.suffix.lower() in provider.EXTENSIONS and p.stem.casefold() == image.stem.casefold()
        ]
        if len(matches) > 1:
            raise UserError("Duplicate filename stem: " + ", ".join(matches) + ". Rename the files first.")

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
            raise UserError("The selection contains no supported images.")
        if len(unique) > MAX_IMAGES:
            raise UserError(f"Open no more than {MAX_IMAGES} images in one dataset.")
        rows = list(self.rows) if append else []
        known = {r["path"].casefold() for r in rows}
        # Index each directory once; thousands of images must not trigger an O(n²) scan.
        stem_counts: dict[Path, Counter[str]] = {}
        for parent in {p.parent for p in unique.values()}:
            stem_counts[parent] = Counter(
                p.stem.casefold() for p in parent.iterdir() if p.is_file() and p.suffix.lower() in provider.EXTENSIONS
            )
        for path in sorted(unique.values(), key=lambda p: str(p).casefold()):
            if str(path).casefold() in known:
                continue
            row: Row = {
                "id": uuid.uuid4().hex,
                "path": str(path),
                "name": path.name,
                "caption": "",
                "status": Status.PENDING,
                "error": "",
                "width": 0,
                "height": 0,
                "exists": False,
                "seconds": None,
            }
            try:
                if stem_counts[path.parent][path.stem.casefold()] > 1:
                    raise UserError("Duplicate filename stem: " + path.stem + ". Rename the files first.")
                with Image.open(path) as im:
                    row.update({"width": im.width, "height": im.height})
                    if getattr(im, "n_frames", 1) > 1:
                        raise UserError("Multi-frame images are not supported. Select a single frame.")
                    im.verify()
                row["fingerprints"] = {suffix: fingerprint(path.with_suffix(suffix)) for suffix in (".txt", ".json")}
                preferred = ".json" if self.settings.output_format == "bria_json" else ".txt"
                other = ".txt" if preferred == ".json" else ".json"
                suffix = (
                    preferred
                    if path.with_suffix(preferred).exists()
                    else other
                    if path.with_suffix(other).exists()
                    else preferred
                )
                target = path.with_suffix(suffix)
                row["caption_format"] = "bria_json" if suffix == ".json" else "normal"
                if target.exists():
                    try:
                        existing = target.read_text(encoding="utf-8-sig").strip()
                    except UnicodeDecodeError:
                        # Older tools often saved captions in a legacy code page; never guess and overwrite.
                        raise UserError(
                            "The existing caption is not UTF-8 text. Save it as UTF-8 or remove it, then load the dataset again."
                        ) from None
                    row.update({"caption": existing, "exists": True, "status": Status.EXISTING})
                    if suffix == ".json":
                        try:
                            row["caption"] = normalize_json(row["caption"])
                        except CaptionValidationError as exc:
                            row.update({"status": Status.ERROR, "error": str(exc)})
                if all(row["fingerprints"].values()):
                    row["notice"] = (
                        "Both .txt and .json exist. LoRA Studio currently prefers .txt. Saving or regenerating keeps the selected format and backs up the other one."
                    )
            except Exception as e:
                row.update({"status": Status.INVALID, "error": str(e)})
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

    def save_row(self, image_id: str, text: str):
        self.idle()
        row = self.row(image_id)
        if row["status"] == Status.INVALID:
            raise UserError(row["error"])
        image = Path(row["path"])
        if not image.is_file():
            raise UserError("The original image no longer exists.")
        self.collision(image)
        if row.get("caption_format") == "bria_json":
            text = normalize_json(text)
        self._write_row(row, text, row.get("caption_format", "normal"), overwrite=True)
        self.persist()

    @staticmethod
    def _check_sidecars(row):
        image = Path(row["path"])
        hashes = row["fingerprints"]
        for suffix in (".txt", ".json"):
            if fingerprint(image.with_suffix(suffix)) != hashes.get(suffix):
                raise UserError("The caption was changed outside the app. Reload the dataset.")

    def _write_row(self, row, text, output_format, overwrite):
        if output_format == "bria_json":
            text = normalize_json(text)
        self._check_sidecars(row)
        suffix = ".json" if output_format == "bria_json" else ".txt"
        other = ".txt" if suffix == ".json" else ".json"
        image = Path(row["path"])
        hashes = row["fingerprints"]
        if hashes.get(other) is not None and not overwrite:
            raise FileExistsError("The caption already exists in another format.")
        digest = write_caption(image, text, hashes.get(suffix), overwrite=overwrite, suffix=suffix)
        hashes[suffix] = digest
        if hashes.get(other) is not None:
            archive_sidecar(image.with_suffix(other), hashes[other])
            hashes[other] = None
        row.update(
            {
                "caption": text.strip(),
                "caption_format": output_format,
                "exists": True,
                "status": Status.SAVED,
                "error": "",
                "notice": "",
            }
        )

    async def start_job(self, ids: list[str], regenerate=False):
        self.idle()
        selected = [self.row(i) for i in dict.fromkeys(ids)]
        if not selected:
            raise UserError("Select at least one image.")
        settings = self.settings.model_copy(deep=True)
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
            "total": len(selected),
            "completed": 0,
            "saved": 0,
            "errors": 0,
            "review": 0,
            "skipped": 0,
            "message": "Starting batch…",
            "id": uuid.uuid4().hex,
            "output_format": settings.output_format,
        }
        for row in selected:
            if row["status"] != Status.INVALID:
                row["status"] = Status.QUEUED
        self.persist()
        self.task = asyncio.create_task(self._run(selected, settings, key, regenerate))

    def _progress(self, row, settings, event):
        stage = event.get("stage", "caption")
        row["phase"] = stage
        self.job["message"] = STAGE_LABELS.get(stage, "Processing") + " · " + row["name"]
        if event.get("kind") == "response":
            row["generation_history"].append({k: v for k, v in event.items() if k != "kind"})
            self.persist()
        if event.get("kind") in ("response", "request_error"):
            self._log_generation(row, settings, event)

    def _log_generation(self, row, settings, event):
        """Operational evidence without images, captions, prompts or credentials."""
        diagnostic = {
            "time": datetime.now(UTC).isoformat(),
            "job": self.job.get("id"),
            "image": row["id"],
            "mode": settings.mode,
            "model": settings.cloud_model if settings.mode == "cloud" else settings.local_model_id,
            "target_words": settings.words,
            **{k: v for k, v in event.items() if k not in ("kind", "text")},
        }
        log = self.root / "logs" / "generation.jsonl"
        try:
            log.parent.mkdir(exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(diagnostic, ensure_ascii=False) + "\n")
        except OSError:
            pass  # Diagnostic logging must not turn a valid caption into a failure.

    async def _run(self, selected, settings, key, regenerate):
        try:
            for row in selected:
                if row["status"] == Status.INVALID:
                    self.job["errors"] += 1
                    self.job["completed"] += 1
                    continue
                image = Path(row["path"])
                if (
                    settings.skip_existing
                    and not regenerate
                    and any(image.with_suffix(s).exists() for s in (".txt", ".json"))
                ):
                    row.update({"status": Status.SKIPPED, "error": ""})
                    if row.get("caption_format", "normal") != settings.output_format:
                        row["notice"] = (
                            "The existing caption uses another format. Use Regenerate or turn off Skip existing captions to convert it."
                        )
                    self.job["skipped"] += 1
                    self.job["completed"] += 1
                    continue
                row.update({"status": Status.PROCESSING, "error": "", "phase": "caption", "generation_history": []})
                self.job["message"] = row["name"]
                started = time.monotonic()
                try:
                    self.collision(image)
                    # Check for external edits before spending time or cloud credits.
                    self._check_sidecars(row)
                    progress = functools.partial(self._progress, row, settings)
                    result = await provider.generate(image, settings, key, on_progress=progress)
                    row.update(
                        {
                            "caption": result.text,
                            "caption_format": settings.output_format,
                            "status": Status.DRAFT,
                            "notice": "",
                            "seconds": round(time.monotonic() - started, 1),
                        }
                    )
                    if result.needs_review:
                        row["status"] = Status.REVIEW
                        self.job["review"] += 1
                    elif settings.auto_save:
                        self.collision(image)
                        self._write_row(
                            row, result.text, settings.output_format, overwrite=regenerate or not settings.skip_existing
                        )
                        self.job["saved"] += 1
                    row["notice"] = result.notice
                    row["phase"] = ""
                except asyncio.CancelledError:
                    received = [h for h in row.get("generation_history", []) if h.get("text")]
                    if received:
                        best = next((h for h in reversed(received) if h.get("complete")), received[0])
                        row.update(
                            {
                                "caption": best["text"],
                                "caption_format": settings.output_format,
                                "status": Status.DRAFT if best.get("complete") else Status.REVIEW,
                                "error": "",
                                "notice": "Batch stopped. The received response has been kept as a draft.",
                                "phase": "",
                            }
                        )
                    else:
                        row.update({"status": Status.PENDING, "error": "Processing was stopped.", "phase": ""})
                    raise
                except ProviderUnavailableError as e:
                    row.update(
                        {
                            "status": Status.PENDING,
                            "error": "",
                            "phase": "",
                            "notice": "Waiting for the model connection to be restored.",
                        }
                    )
                    self.job.update(
                        {
                            "paused": True,
                            "message": "Batch paused: " + str(e),
                            "remaining_ids": [
                                r["id"] for r in selected if r["status"] in (Status.QUEUED, Status.PENDING)
                            ],
                            "resume_regenerate": regenerate,
                        }
                    )
                    return
                except Exception as e:
                    row.update({"status": Status.ERROR, "error": str(e)})
                    if isinstance(e, CaptionValidationError):
                        row.update({"caption": e.draft, "caption_format": "bria_json"})
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
            for row in selected:
                if row["status"] in (Status.QUEUED, Status.PROCESSING):
                    row["status"] = Status.PENDING
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
                if row["status"] in (Status.QUEUED, Status.PROCESSING):
                    row["status"] = Status.PENDING
            self.job.update({"running": False, "message": "Batch stopped; saved captions have been preserved"})
            self.persist()

    async def close(self):
        await self.cancel_job()
        self.runtime.cancel.set()
        if self.runtime.install_task:
            await self.runtime.install_task
        await asyncio.to_thread(self.runtime.stop)
