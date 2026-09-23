"""Where Caption Studio keeps user data: a data folder next to the program, so every copy is self-contained.

CAPTION_STUDIO_DATA_DIR overrides the location (tests and isolated profiles). Releases before
0.1.13 used %LOCALAPPDATA%\\CaptionStudio; an installed or portable build moves that data once.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Small user files worth carrying over when the model folder cannot be moved cheaply.
PERSONAL_FILES = ("settings.json", "keys.json", "session.json", "logs")


def notice(template: str, **values) -> str:
    """A one-time startup message for the UI; the template is its translation key."""
    return template.format(**values)


def program_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # source checkout


def legacy_directory() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CaptionStudio"


def data_directory() -> Path:
    override = os.environ.get("CAPTION_STUDIO_DATA_DIR")
    return Path(override) if override else program_directory() / "data"


def _writable(folder: Path) -> bool:
    probe = folder / ".write-test"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def _in_use(folder: Path) -> bool:
    """True while an older Caption Studio still holds that folder's instance lock."""
    lock = folder / "instance.lock"
    if os.name != "nt" or not lock.exists():
        return False
    import msvcrt

    try:
        with lock.open("r+b") as handle:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return False
    except OSError:
        return True


def _copy_personal_files(legacy: Path, target: Path):
    """Copy everything first and delete the originals only when every copy succeeded."""
    copied = []
    try:
        for name in PERSONAL_FILES:
            source = legacy / name
            if source.is_dir():
                shutil.copytree(source, target / name)
            elif source.is_file():
                shutil.copy2(source, target / name)
            else:
                continue
            copied.append(target / name)
    except OSError:
        for path in copied:
            _remove(path)
        raise
    for name in PERSONAL_FILES:
        _remove(legacy / name)


def _remove(path: Path):
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _same_volume(a: Path, b: Path) -> bool:
    return os.stat(a).st_dev == os.stat(b).st_dev


def _move_legacy(legacy: Path, target: Path) -> list[str]:
    moved = notice("Caption Studio now keeps its data next to the program: {path}", path=target)
    if _same_volume(legacy, target):
        # Same volume: one rename moves everything, including multi-gigabyte models, instantly.
        target.rmdir()
        try:
            legacy.rename(target)
        except OSError:
            target.mkdir()
            raise
        return [moved]
    # Another drive: copying the model at startup would look like a hang, so move personal files only.
    _copy_personal_files(legacy, target)
    runtime = legacy / "runtime"
    if not runtime.is_dir():
        return [moved]
    return [
        notice(
            "Settings, keys and the session were moved to {target}. The downloaded model is still in {runtime}; "
            "close Caption Studio and move that folder into {target}, or download the model again in Setup.",
            target=target,
            runtime=runtime,
        )
    ]


def prepare_data_directory() -> tuple[Path, list[str]]:
    """Create the data folder, moving data from the old per-user location once. Returns notices for the UI."""
    target = data_directory()
    if os.environ.get("CAPTION_STUDIO_DATA_DIR"):
        target.mkdir(parents=True, exist_ok=True)
        return target, []
    legacy = legacy_directory()
    if not _writable(target):
        legacy.mkdir(parents=True, exist_ok=True)
        return legacy, [notice("The program folder cannot be written to, so data is kept in {path}.", path=legacy)]
    # Only a built program adopts old data; a source checkout must never take an installation's data.
    adopt = getattr(sys, "frozen", False) and legacy.is_dir() and any(legacy.iterdir()) and not any(target.iterdir())
    if adopt:
        if _in_use(legacy):
            return legacy, []  # An older version is running; its own lock check reports it.
        try:
            return target, _move_legacy(legacy, target)
        except OSError:
            # Try again on the next start; nothing was lost. If another instance just moved it, use that.
            return (legacy if legacy.exists() else target), []
    return target, []
