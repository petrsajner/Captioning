from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import os
from pathlib import Path
import time
import uuid

from PIL import Image
from . import __version__, provider
from .models import Settings, MANAGED_URL
from .runtime import Runtime
from .storage import KeyStore, fingerprint, read_json, save_json, write_caption


def data_directory() -> Path:
    return Path(os.environ.get("CAPTION_STUDIO_DATA_DIR") or
                str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CaptionStudio"))


class Studio:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(**read_json(root / "settings.json", {}))
        self.keys = KeyStore(root / "keys.json")
        self.runtime = Runtime(root)
        self.rows: list[dict] = read_json(root / "session.json", [])
        for row in self.rows:
            if row["status"] in ("processing", "queued"):
                row.update(status="pending", error="Předchozí běh byl přerušen. Můžete pokračovat.")
        self.job = {"running": False, "total": 0, "completed": 0, "saved": 0, "errors": 0, "skipped": 0, "message": "Připraveno"}
        self.task: asyncio.Task | None = None
        self.importing = False

    def idle(self):
        if self.job["running"] or self.importing:
            raise ValueError("Počkejte na dokončení operace nebo zastavte dávku.")

    def persist(self):
        save_json(self.root / "session.json", self.rows)

    def save_settings(self, settings: Settings, api_key: str | None = None, clear_key=False,
                      local_api_key: str | None = None, clear_local_key=False):
        self.idle()
        if self.runtime.installing or self.runtime.state["status"] == "loading":
            raise ValueError("Počkejte na dokončení přípravy modelu.")
        if (api_key and len(api_key) > 8192) or (local_api_key and len(local_api_key) > 8192):
            raise ValueError("API klíč je příliš dlouhý.")
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
        return {"version": __version__, "settings": self.settings.model_dump(),
                "has_key": self.keys.has(self.settings.cloud_url),
                "has_local_key": self.keys.has("local:" + self.settings.local_url),
                "rows": self.rows, "job": self.job, "importing": self.importing,
                "runtime": self.runtime.snapshot(self.settings.model_profile, self.settings.backend),
                "data_dir": str(self.root)}

    def local_key(self, settings: Settings):
        if settings.local_source == "managed":
            return self.runtime.api_key if self.runtime.process else ""
        return self.keys.get("local:" + settings.local_url)

    def row(self, image_id: str):
        row = next((r for r in self.rows if r["id"] == image_id), None)
        if not row:
            raise ValueError("Obrázek není v otevřené sadě.")
        return row

    @staticmethod
    def collision(image: Path):
        matches = [p.name for p in image.parent.iterdir()
                   if p.is_file() and p.suffix.lower() in provider.EXTENSIONS and p.stem.casefold() == image.stem.casefold()]
        if len(matches) > 1:
            raise ValueError("Stejný název bez přípony: " + ", ".join(matches) + ". Nejdříve soubory přejmenujte.")

    def _scan(self, paths: list[str], folder: str, recursive: bool, append: bool):
        files = []
        if folder:
            directory = Path(folder).expanduser().resolve(strict=True)
            if not directory.is_dir():
                raise ValueError("Zadaná cesta není složka.")
            # os.walk does not traverse directory symlinks. Avoid backup and dot folders.
            for current, dirs, names in os.walk(directory, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".")) if recursive else []
                files.extend(Path(current) / n for n in sorted(names) if Path(n).suffix.lower() in provider.EXTENSIONS)
        files.extend(Path(p).expanduser() for p in paths)
        unique = {str(p.resolve()).casefold(): p.resolve() for p in files
                  if p.suffix.lower() in provider.EXTENSIONS and p.is_file()}
        if not unique:
            raise ValueError("Výběr neobsahuje podporované obrázky.")
        if len(unique) > 20000:
            raise ValueError("Otevřete nejvýše 20 000 obrázků v jedné sadě.")
        rows = list(self.rows) if append else []
        known = {r["path"].casefold() for r in rows}
        # Index each directory once; thousands of images must not trigger an O(n²) scan.
        stem_counts = {}
        for parent in {p.parent for p in unique.values()}:
            stem_counts[parent] = Counter(p.stem.casefold() for p in parent.iterdir()
                                          if p.is_file() and p.suffix.lower() in provider.EXTENSIONS)
        for path in sorted(unique.values(), key=lambda p: str(p).casefold()):
            if str(path).casefold() in known:
                continue
            row = {"id": uuid.uuid4().hex, "path": str(path), "name": path.name,
                   "caption": "", "fingerprint": None, "status": "pending", "error": "",
                   "width": 0, "height": 0, "exists": False, "seconds": None}
            try:
                if stem_counts[path.parent][path.stem.casefold()] > 1:
                    raise ValueError("Stejný název bez přípony: " + path.stem + ". Nejdříve soubory přejmenujte.")
                with Image.open(path) as im:
                    row.update(width=im.width, height=im.height)
                    if getattr(im, "n_frames", 1) > 1:
                        raise ValueError("Vícesnímkové obrázky nejsou podporované. Vyberte jeden snímek.")
                    im.verify()
                target = path.with_suffix(".txt")
                row["fingerprint"] = fingerprint(target)
                if target.exists():
                    row.update(caption=target.read_text(encoding="utf-8-sig").strip(), exists=True, status="existing")
            except Exception as e:
                row.update(status="invalid", error=str(e))
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
        if row["status"] == "invalid":
            raise ValueError(row["error"])
        if len(text) > 50000:
            raise ValueError("Popisek je příliš dlouhý.")
        image = Path(row["path"])
        if not image.is_file():
            raise ValueError("Původní obrázek už neexistuje.")
        self.collision(image)
        digest = write_caption(image, text, row["fingerprint"], overwrite=True)
        row.update(caption=text.strip(), fingerprint=digest, exists=True, status="saved", error="")
        self.persist()

    async def start_job(self, ids: list[str], regenerate=False):
        self.idle()
        selected = [self.row(i) for i in dict.fromkeys(ids)]
        if not selected:
            raise ValueError("Vyberte alespoň jeden obrázek.")
        settings = self.settings.model_copy(deep=True)
        if settings.mode == "cloud":
            if not settings.cloud_model.strip():
                raise ValueError("V nastavení vyberte cloudový model s podporou obrázků.")
            key = self.keys.get(settings.cloud_url)
            if not key:
                raise ValueError("V nastavení zadejte API klíč pro tohoto poskytovatele.")
        else:
            key = self.local_key(settings)
        self.job = {"running": True, "total": len(selected), "completed": 0, "saved": 0,
                    "errors": 0, "skipped": 0, "message": "Spouštím dávku…"}
        for row in selected:
            if row["status"] != "invalid":
                row["status"] = "queued"
        self.persist()
        self.task = asyncio.create_task(self._run(selected, settings, key, regenerate))

    async def _run(self, selected, settings, key, regenerate):
        try:
            for row in selected:
                if row["status"] == "invalid":
                    self.job["errors"] += 1
                    self.job["completed"] += 1
                    continue
                image = Path(row["path"])
                if settings.skip_existing and not regenerate and image.with_suffix(".txt").exists():
                    row.update(status="skipped", error="")
                    self.job["skipped"] += 1
                    self.job["completed"] += 1
                    continue
                row.update(status="processing", error="")
                self.job["message"] = row["name"]
                started = time.monotonic()
                try:
                    self.collision(image)
                    # Check for external edits before spending time or cloud credits.
                    if fingerprint(image.with_suffix(".txt")) != row["fingerprint"]:
                        raise ValueError("Popisek byl změněn mimo aplikaci. Načtěte sadu znovu.")
                    caption = await provider.generate(image, settings, key)
                    row.update(caption=caption, status="draft", seconds=round(time.monotonic() - started, 1))
                    if settings.auto_save:
                        self.collision(image)
                        digest = write_caption(image, caption, row["fingerprint"], overwrite=regenerate or not settings.skip_existing)
                        row.update(fingerprint=digest, exists=True, status="saved")
                        self.job["saved"] += 1
                except asyncio.CancelledError:
                    row.update(status="pending", error="Zpracování bylo zastaveno.")
                    raise
                except Exception as e:
                    row.update(status="error", error=str(e))
                    self.job["errors"] += 1
                self.job["completed"] += 1
                self.persist()
            self.job["message"] = "Dávka dokončena" if not self.job["errors"] else "Dokončeno s chybami — zkontrolujte označené obrázky"
        except asyncio.CancelledError:
            self.job["message"] = "Dávka zastavena; uložené popisky zůstávají zachované"
        finally:
            for row in selected:
                if row["status"] in ("queued", "processing"):
                    row["status"] = "pending"
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
                if row["status"] in ("queued", "processing"):
                    row["status"] = "pending"
            self.job.update(running=False, message="Dávka zastavena; uložené popisky zůstávají zachované")
            self.persist()

    async def close(self):
        await self.cancel_job()
        self.runtime.cancel.set()
        if self.runtime.install_task:
            await self.runtime.install_task
        await asyncio.to_thread(self.runtime.stop)
