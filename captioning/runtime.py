"""Self-contained model setup. Never imports or changes another application's runtime."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import zipfile

import httpx
from .storage import read_json, save_json

REPO = "unsloth/Qwen3.8-27B-GGUF"
REVISION = "4ca720788d1e01f1bff70c033e0d0028fd02e502"
RELEASE = "b10821"
FILES = {
    "q3": ("Qwen3.8-27B-UD-IQ3_S.gguf", 12040883104, "d847e2c1e4aa276e4b7b8e9ad7628050e61e165d49ab995407bc36677a6f3864"),
    "q4": ("Qwen3.8-27B-UD-Q4_K_M.gguf", 16464440224, "322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482"),
    "q5": ("Qwen3.8-27B-UD-Q5_K_M.gguf", 19771509664, "2de73110cb254cbf09b54b717578dadff12ef1194e7271527e68202f39ba4bfd"),
    "vision": ("mmproj-F16.gguf", 927607488, "cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e"),
}
ARCHIVES = {
    "cuda": [
        ("llama-b10821-bin-win-cuda-13.3-x64.zip", 149589734, "3058afb6b1f1ec232fd7b747ed684f440ad03831809af713ae8452bff0c49cda"),
        ("cudart-llama-bin-win-cuda-13.3-x64.zip", 390970417, "1462a050eb4c684921ba51dcc4cc488a036674c3e73e9945ee705b854808d03e"),
    ],
    "vulkan": [("llama-b10821-bin-win-vulkan-x64.zip", 35228149, "23dc394e279940c6b720dca0af53ebf678e48edda7a58ebcb5b52c41c3bd07cb")],
    "cpu": [("llama-b10821-bin-win-cpu-x64.zip", 18413173, "e33b673c5d056da7128a66710fafe615a9ce35aa72f32c52b683bee56826ca12")],
}


class SetupCancelled(Exception):
    pass


def safe_extract(archive: Path, destination: Path):
    root = destination.resolve()
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            path = (destination / info.filename).resolve()
            if not path.is_relative_to(root) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archiv obsahuje neplatnou cestu.")
        z.extractall(destination)


class Runtime:
    def __init__(self, data_dir: Path):
        self.root = data_dir / "runtime"
        self.root.mkdir(parents=True, exist_ok=True)
        self.cancel = threading.Event()
        self.install_task: asyncio.Task | None = None
        self.process: subprocess.Popen | None = None
        self.process_profile: str | None = None
        self.process_backend: str | None = None
        self.api_key = secrets.token_urlsafe(32)
        self.start_lock = asyncio.Lock()
        self.state = {"status": "idle", "message": "Lokální model zatím není připravený.", "done": 0, "total": 0}
        self.verified = read_json(self.root / "verified.json", {})

    @property
    def installing(self):
        return self.install_task is not None and not self.install_task.done()

    def checkpoint(self):
        if self.cancel.is_set():
            raise SetupCancelled()

    def valid_file(self, path: Path, sha: str, size: int):
        if not path.is_file() or path.stat().st_size != size:
            return False
        stat = path.stat()
        return self.verified.get(str(path)) == [sha, size, stat.st_mtime_ns]

    def verify(self, path: Path, sha: str, size: int):
        self.state.update(message="Ověřuji soubor: " + path.name, done=0, total=size)
        h = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(8 * 1024 * 1024):
                self.checkpoint()
                h.update(chunk)
                self.state["done"] += len(chunk)
        if path.stat().st_size != size or h.hexdigest() != sha:
            path.unlink(missing_ok=True)
            raise ValueError("Kontrolní součet nesouhlasí. Poškozený soubor byl odstraněn; spusťte stažení znovu.")

    def download(self, url: str, destination: Path, size: int, sha: str):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if self.valid_file(destination, sha, size):
            return
        partial = destination.with_name(destination.name + ".part")
        if destination.exists():
            self.verify(destination, sha, size)
        else:
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > size:
                partial.unlink()
                offset = 0
            self.state.update(message="Stahuji " + destination.name, done=offset, total=size)
            if offset < size:
                headers = {"Range": f"bytes={offset}-"} if offset else {}
                with httpx.Client(follow_redirects=True, timeout=60, trust_env=False) as client:
                    with client.stream("GET", url, headers=headers) as response:
                        response.raise_for_status()
                        if offset and response.status_code == 206:
                            if not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                                raise ValueError("Server vrátil nesprávný rozsah souboru.")
                        elif offset:
                            offset = 0
                            self.state["done"] = 0
                        with partial.open("ab" if offset else "wb") as f:
                            for chunk in response.iter_bytes(1024 * 1024):
                                self.checkpoint()
                                f.write(chunk)
                                self.state["done"] += len(chunk)
                                if self.state["done"] > size:
                                    raise ValueError("Stažený soubor překročil očekávanou velikost.")
            self.verify(partial, sha, size)
            os.replace(partial, destination)
        self.verified[str(destination)] = [sha, size, destination.stat().st_mtime_ns]
        save_json(self.root / "verified.json", self.verified)

    def runtime_dir(self, backend: str):
        return self.root / f"llama-{RELEASE}-{backend}"

    def ready(self, profile: str, backend: str):
        if not self.installing:
            self.verified = read_json(self.root / "verified.json", self.verified)
        runtime = self.runtime_dir(backend)
        return ((runtime / "ready.json").is_file()
                and any(runtime.rglob("llama-server.exe"))
                and all(self.valid_file(self.root / "models" / FILES[k][0], FILES[k][2], FILES[k][1])
                        for k in (profile, "vision")))

    def snapshot(self, profile: str, backend: str):
        return {**self.state, "installing": self.installing, "ready": self.ready(profile, backend),
                "running": self.process is not None and self.process.poll() is None,
                "root": str(self.root), "profile": self.process_profile}

    def _install(self, profile: str, backend: str):
        try:
            needed = 2 * 1024**3
            for key in (profile, "vision"):
                filename, size, _ = FILES[key]
                destination = self.root / "models" / filename
                partial = destination.with_name(filename + ".part")
                existing = destination if destination.exists() else partial
                needed += max(0, size - (existing.stat().st_size if existing.exists() else 0))
            if shutil.disk_usage(self.root).free < needed:
                raise ValueError(f"Nedostatek místa. Potřebuji ještě přibližně {needed / 1024**3:.1f} GB.")
            self.state.update(status="working")
            runtime = self.runtime_dir(backend)
            if not (runtime / "ready.json").exists():
                staging = self.root / f"staging-{backend}"
                staging.mkdir(exist_ok=True)
                for filename, size, sha in ARCHIVES[backend]:
                    self.checkpoint()
                    archive = self.root / "downloads" / filename
                    self.download(f"https://github.com/ggml-org/llama.cpp/releases/download/{RELEASE}/{filename}", archive, size, sha)
                    self.state.update(message="Rozbaluji lokální prostředí…", done=0, total=0)
                    safe_extract(archive, staging)
                if not any(staging.rglob("llama-server.exe")):
                    raise ValueError("Stažený balík neobsahuje llama-server.exe.")
                self.checkpoint()
                if runtime.exists():
                    # Fixed, application-owned staging target only.
                    shutil.rmtree(runtime)
                staging.rename(runtime)
                save_json(runtime / "ready.json", {"release": RELEASE, "backend": backend})
            for k in (profile, "vision"):
                self.checkpoint()
                filename, size, sha = FILES[k]
                self.download(f"https://huggingface.co/{REPO}/resolve/{REVISION}/{filename}", self.root / "models" / filename, size, sha)
            self.state.update(status="done", message="Prostředí i model jsou připravené.", done=1, total=1)
        except SetupCancelled:
            self.state.update(status="cancelled", message="Stahování pozastaveno. Další spuštění naváže na stažená data.")
        except httpx.HTTPError:
            self.state.update(status="error", message="Stahování selhalo. Zkontrolujte internet a zkuste znovu; stažená část zůstává zachovaná.")
        except Exception as e:
            self.state.update(status="error", message=str(e))

    def install(self, profile: str, backend: str):
        if self.installing:
            raise ValueError("Instalace už probíhá.")
        if self.process and self.process.poll() is None:
            raise ValueError("Před instalací zastavte lokální model.")
        self.cancel.clear()
        self.state.update(status="working", message="Připravuji stahování…", done=0, total=0)
        self.install_task = asyncio.create_task(asyncio.to_thread(self._install, profile, backend))

    async def start(self, profile: str, backend: str):
        async with self.start_lock:
            if self.process and self.process.poll() is None:
                if self.process_profile != profile or self.process_backend != backend:
                    raise ValueError("Běží jiný profil. Nejprve jej zastavte.")
                return
            if self.installing:
                raise ValueError("Počkejte na dokončení instalace.")
            if not self.ready(profile, backend):
                raise ValueError("Nejprve stáhněte vybraný lokální model v nastavení.")
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", 8091))
                except OSError:
                    raise ValueError("Port 8091 je obsazený. Cizí proces nebyl ukončen; zkontrolujte další běžící instance.") from None
            exe = next(self.runtime_dir(backend).rglob("llama-server.exe"))
            args = [str(exe), "-m", str(self.root / "models" / FILES[profile][0]),
                    "--mmproj", str(self.root / "models" / FILES["vision"][0]),
                    "--host", "127.0.0.1", "--port", "8091", "--alias", "caption-qwen",
                    "--api-key", self.api_key, "--image-min-tokens", "1024",
                    "-c", "8192", "-np", "1", "-ngl", "0" if backend == "cpu" else "999",
                    "--jinja", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0"]
            if backend == "cpu":
                args.append("--no-mmproj-offload")
            with (self.root / "model.log").open("ab") as log:
                self.process = subprocess.Popen(args, cwd=exe.parent, stdout=log, stderr=subprocess.STDOUT,
                                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.process_profile, self.process_backend = profile, backend
            self.state.update(status="loading", message="Načítám model do paměti…")
            try:
                async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                    for _ in range(180):
                        if not self.process or self.process.poll() is not None:
                            raise ValueError("Model se nespustil. Podrobnosti jsou v runtime/model.log; zkontrolujte ovladač GPU a volnou paměť.")
                        try:
                            r = await client.get("http://127.0.0.1:8091/health")
                            if r.status_code == 200:
                                self.state.update(status="running", message="Lokální model běží.")
                                return
                        except httpx.HTTPError:
                            pass
                        await asyncio.sleep(1)
                raise ValueError("Načítání modelu překročilo časový limit.")
            except BaseException:
                self.stop()
                self.state.update(status="error", message="Spuštění modelu selhalo. Zkontrolujte nastavení a model.log.")
                raise

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None
        self.state.update(status="idle", message="Lokální model je zastavený.")
