"""Collect licenses of the distributions bundled into the Windows release."""

import importlib.metadata
import re
import shutil
import sys
from pathlib import Path

workspace = Path(__file__).resolve().parents[1]


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# Only runtime pins are bundled; test, lint and packaging tools are not.
bundled = {
    normalized(line.split("==")[0])
    for line in (workspace / "requirements-lock.txt").read_text(encoding="utf-8").splitlines()
    if "==" in line and not line.startswith("#")
}
root = workspace / "output" / "licenses"
shutil.rmtree(root, ignore_errors=True)
root.mkdir(parents=True)
for dist in importlib.metadata.distributions():
    if normalized(dist.metadata["Name"]) not in bundled:
        continue
    target = root / f"{dist.metadata['Name']}-{dist.version}"
    target.mkdir(exist_ok=True)
    (target / "METADATA.txt").write_text(
        dist.read_text("METADATA") or dist.read_text("PKG-INFO") or dist.metadata["Name"], encoding="utf-8"
    )
    for file in dist.files or []:
        if any(word in file.name.lower() for word in ("license", "copying", "notice")):
            source = Path(dist.locate_file(file))
            if source.is_file():
                shutil.copy2(source, target / file.name)
missing = bundled - {normalized(d.metadata["Name"]) for d in importlib.metadata.distributions()}
if missing:
    raise SystemExit("Runtime pins are not installed: " + ", ".join(sorted(missing)))
for name in ("LICENSE.txt", "LICENSE"):
    path = Path(sys.base_prefix) / name
    if path.exists():
        shutil.copy2(path, root / ("Python-" + name))
