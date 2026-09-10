"""Local persistence, safe sidecars and Windows-protected provider credentials."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".caption-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def save_json(path: Path, data) -> None:
    atomic_bytes(path, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # Preserve the damaged file for recovery; never silently overwrite it.
        path.rename(path.with_name(path.name + ".damaged-" + uuid.uuid4().hex[:8]))
        return default


def fingerprint(path: Path) -> str | None:
    if path.is_symlink():
        raise ValueError("Popisek je symbolický odkaz. Zápis je zablokovaný.")
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def write_caption(image: Path, text: str, expected: str | None, overwrite: bool, suffix=".txt") -> str:
    """UTF-8 sidecar; preserve existing bytes and detect external modifications."""
    if suffix not in (".txt", ".json"):
        raise ValueError("Neplatná přípona popisku.")
    text = text.strip()
    if not text:
        raise ValueError("Prázdný popisek nelze uložit.")
    path = image.with_suffix(suffix)
    current = fingerprint(path)
    if current != expected:
        raise ValueError("Popisek byl mezitím změněn mimo aplikaci. Načtěte sadu znovu.")
    if current is not None and not overwrite:
        raise FileExistsError("Popisek už existuje.")
    data = (text + "\n").encode("utf-8")
    if current is None:
        # Windows rename is no-clobber and also works on exFAT/network volumes.
        # POSIX rename overwrites, so use a no-clobber link there instead.
        fd, temp = tempfile.mkstemp(prefix=".caption-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            if os.name == "nt":
                os.rename(temp, path)
            else:
                os.link(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)
    else:
        old = path.read_bytes()
        if hashlib.sha256(old).hexdigest() != expected:
            raise ValueError("Popisek byl mezitím změněn mimo aplikaci.")
        if old != data:
            backup = path.parent / ".caption-backups" / (path.name + "." + uuid.uuid4().hex + ".bak")
            atomic_bytes(backup, old)
            if fingerprint(path) != expected:
                raise ValueError("Popisek byl mezitím změněn mimo aplikaci.")
            atomic_bytes(path, data)
    return hashlib.sha256(data).hexdigest()


def archive_sidecar(path: Path, expected: str):
    """Retire the other caption format after a successful format conversion."""
    if fingerprint(path) != expected:
        raise ValueError("Původní popisek se změnil mimo aplikaci. Starý formát nebyl přesunut; načtěte sadu znovu.")
    backup_dir = path.parent / ".caption-backups"
    backup_dir.mkdir(exist_ok=True)
    target = backup_dir / (path.name + "." + uuid.uuid4().hex + ".bak")
    path.rename(target)


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def protect(data: bytes, decrypt=False) -> bytes:
    if os.name != "nt":
        raise ValueError("Trvalé uložení API klíče vyžaduje Windows.")
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(source), "Caption Studio", None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise ValueError("Windows nemohl zpřístupnit uložený klíč. Zadejte jej znovu.")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel.LocalFree(target.pbData)


class KeyStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = read_json(path, {})

    def has(self, endpoint: str) -> bool:
        return endpoint in self.data

    def set(self, endpoint: str, value: str):
        if value:
            self.data[endpoint] = base64.b64encode(protect(value.encode())).decode()
        else:
            self.data.pop(endpoint, None)
        save_json(self.path, self.data)

    def get(self, endpoint: str) -> str:
        value = self.data.get(endpoint)
        return protect(base64.b64decode(value), decrypt=True).decode() if value else ""
