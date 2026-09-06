"""Collect installed distribution licenses for the Windows release."""
import importlib.metadata
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1] / "output" / "licenses"
root.mkdir(parents=True, exist_ok=True)
for dist in importlib.metadata.distributions():
    target = root / f"{dist.metadata['Name']}-{dist.version}"
    target.mkdir(exist_ok=True)
    (target / "METADATA.txt").write_text(dist.read_text("METADATA") or dist.read_text("PKG-INFO") or dist.metadata["Name"], encoding="utf-8")
    for file in dist.files or []:
        if any(word in file.name.lower() for word in ("license", "copying", "notice")):
            source = Path(dist.locate_file(file))
            if source.is_file():
                shutil.copy2(source, target / file.name)
for name in ("LICENSE.txt", "LICENSE"):
    path = Path(sys.base_prefix) / name
    if path.exists():
        shutil.copy2(path, root / ("Python-" + name))
