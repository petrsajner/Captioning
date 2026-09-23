"""Package the rendered UI logo as a multiresolution Windows icon.

brand-icon.png is a transparent 12x browser render of the existing .brand-icon
CSS/HTML (Segoe UI, C with a middle dot), not a crop of a user screenshot.
The app header retains its original CSS logo. This script only packages the
committed logo render for Windows; end users do not need any build tools.
"""

from pathlib import Path

from PIL import Image

root = Path(__file__).resolve().parents[1]
sizes = [(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
with Image.open(root / "ui" / "brand-icon.png") as image:
    image.save(root / "ui" / "caption-studio.ico", sizes=sizes)
