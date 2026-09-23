"""Read-only folder navigation with image previews before dataset import."""

import os
import secrets
from collections import OrderedDict
from pathlib import Path

from .provider import EXTENSIONS

PAGE_SIZE = 80


class FolderBrowser:
    def __init__(self):
        self.previews = OrderedDict()

    @staticmethod
    def describe(directory: Path):
        return {"name": directory.name or directory.anchor, "path": str(directory)}

    def children(self, path: str):
        """One tree level only; never scan descendants or decode images."""
        directory = Path(path).expanduser().resolve(strict=True)
        if not directory.is_dir():
            raise ValueError("This path is not a folder.")
        folders = []
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if entry.is_dir():
                        folders.append(self.describe(directory / entry.name))
                except OSError:
                    continue
        folders.sort(key=lambda item: item["name"].casefold())
        return {"path": str(directory), "folders": folders}

    def listing(self, path: str, page: int = 0):
        directory = Path(path).expanduser().resolve(strict=True)
        if not directory.is_dir():
            raise ValueError("This path is not a folder.")
        folders, images = [], []
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if entry.is_dir():
                        folders.append({"name": entry.name, "path": str(directory / entry.name)})
                    elif entry.is_file() and Path(entry.name).suffix.lower() in EXTENSIONS:
                        images.append(entry.name)
                except OSError:
                    continue
        folders.sort(key=lambda item: item["name"].casefold())
        images.sort(key=str.casefold)
        pages = max(1, (len(images) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, pages - 1)
        previews = []
        for name in images[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]:
            identifier = secrets.token_hex(16)
            self.previews[identifier] = directory / name
            previews.append({"id": identifier, "name": name})
        while len(self.previews) > 4096:
            self.previews.popitem(last=False)
        roots = [{"name": "Home folder", "path": str(Path.home())}]
        if os.name == "nt":
            import ctypes

            mask = ctypes.windll.kernel32.GetLogicalDrives()
            roots.extend({"name": chr(65 + i) + ":", "path": chr(65 + i) + ":\\"} for i in range(26) if mask & (1 << i))
        else:
            roots.append({"name": "/", "path": "/"})
        return {
            "path": str(directory),
            "parent": str(directory.parent),
            "folders": folders,
            "images": previews,
            "image_count": len(images),
            "page": page,
            "pages": pages,
            "roots": roots,
            "breadcrumbs": [self.describe(p) for p in [*reversed(directory.parents), directory]],
        }

    def image(self, identifier: str):
        if identifier not in self.previews:
            raise ValueError("The preview is no longer available. Open the folder again.")
        return self.previews[identifier]
