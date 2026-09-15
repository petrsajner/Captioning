"""Soft caption length and conservative completion checks, never text slicing."""
import re


def word_count(text: str) -> int:
    return len(text.split())


def word_ceiling(target: int) -> int:
    return target * 6 // 5


def unfinished(text: str, caption_format="description", finish_reason="") -> bool:
    text = text.strip()
    if not text:
        return True
    if caption_format == "tags":
        return finish_reason.lower() in {"length", "max_tokens"} and text.endswith((",", ";", ":", "-"))
    tail = text.rstrip('"”’»)]}')
    if tail.endswith((".", "!", "?", "。", "！", "？")) and not tail.endswith("..."):
        return False
    last = re.sub(r"[^\wá-ž]", "", tail.split()[-1].lower())
    dangling = {"a", "an", "the", "and", "or", "with", "in", "on", "of", "to", "for", "is", "are", "wearing",
                "her", "his", "its", "while", "which", "that", "s", "se", "v", "ve", "na", "do", "je", "jsou", "má", "její", "jeho", "která", "který"}
    return finish_reason.lower() in {"length", "max_tokens"} or last in dangling or word_count(text) >= 8


class CaptionResult(str):
    def __new__(cls, text, *, notice="", needs_review=False, history=None):
        obj = super().__new__(cls, text)
        obj.notice = notice
        obj.needs_review = needs_review
        obj.history = history or []
        return obj


class ProviderUnavailableError(ValueError):
    """A connection/account/server problem, not a bad image in the dataset."""
