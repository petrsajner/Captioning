"""Presentation-only localization; captions, prompts and stored diagnostics stay intact."""

import json
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache
def catalog(language: str) -> dict:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return json.loads((root / "ui" / "locales" / f"{language}.json").read_text(encoding="utf-8"))


def translate(text: str, language: str = "en") -> str:
    """Translate an exact UI message. Never call this on caption content."""
    return catalog(language)["messages"].get(text, text)


def dangling_words() -> frozenset[str]:
    return frozenset(word for language in ("en", "cs") for word in catalog(language)["grammar"]["dangling_words"])
