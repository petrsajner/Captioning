"""Which detail switches a model follows reliably, measured live (2026-09-30, output/switch-test/PROPOSAL.md).

A switch the model cannot follow is not offered (Petr: "it would lie"): its detail stays at the LoRA type's
default and the UI shows it greyed out with the reason. The recipe keeps the user's own choice, so it returns
with a model that can follow it.
"""

from __future__ import annotations

import math
import re

from .training import TYPE_DEFAULTS, details_for

# Style LoRAs: no measured model keeps the depicted content or the background out of a print (even Opus named
# the turtle or the lantern of a one-subject print, and the boats and small figures of a landscape).
NO_MODEL = "No measured model leaves this out reliably in style images, so it stays described."
# Measured on a few known models only; an unknown model gets the defaults where the weakest measured model failed.
UNMEASURED = "Not measured for this model; this detail stays at the LoRA type's default."
LOCKS: dict[str, dict[tuple[str, str], str]] = {
    "full": {},
    "muse": {
        ("character", "hair_color"): "This model often misses the hair tone in black-and-white photos, so hair color "
        "stays left out.",
    },
    "strict": {
        ("character", "identity"): UNMEASURED,
        ("character", "accessories"): UNMEASURED,
        ("object", "background"): UNMEASURED,
        ("style", "palette"): UNMEASURED,
    },
}
ALWAYS = {("style", "identity"): NO_MODEL, ("style", "background"): NO_MODEL}
# Words per switched-on photo detail for the shortest reliable caption: 40 words for a character's 9 details on
# GPT, Claude, Qwen Max and Grok, 60 on Gemini, Muse, GLM FlashX and local Qwen with reasoning (at 40 words Gemini
# described the pose of a close-up in 7 of 10 captions, at 60 in 9, at 80 in 10), 80 on Qwen without reasoning.
WORDS_PER_DETAIL = {"cloud": 4.4, "longer": 6.5, "local": 6.5, "strict": 8.8}
LONGER_MODELS = re.compile(r"gemini|muse-spark|glm-", re.I)
# Cloud models by name, newer versions of the same line included.
FULL_MODELS = re.compile(r"claude|anthropic|(^|/)gpt-|openai/|gemini|qwen[^/]*max|grok|glm-[\d.]+-flashx", re.I)
MUSE_MODELS = re.compile(r"muse-spark", re.I)


def profile(s, reasoning: bool = True) -> str:
    """The measured group of the configured model: "full", "muse" or "strict".

    Local models run with reasoning (Qwen through Marvin or the managed runtime); a local server that cannot
    reason (`reasoning` False, known only once it answers) and every unknown cloud model get "strict".
    """
    if s.mode == "local":
        return "full" if reasoning else "strict"
    if MUSE_MODELS.search(s.cloud_model):
        return "muse"
    return "full" if FULL_MODELS.search(s.cloud_model) else "strict"


def locked(s, reasoning: bool = True) -> dict[str, dict[str, str]]:
    """Per LoRA type, the details that stay at the type's default for this model, with the reason."""
    locks = {**ALWAYS, **LOCKS[profile(s, reasoning)]}
    out: dict[str, dict[str, str]] = {}
    for (lora_type, detail), reason in locks.items():
        out.setdefault(lora_type, {})[detail] = reason
    return out


def effective(s, reasoning: bool = True):
    """The settings a caption uses: every locked detail at its LoRA type's default, the rest as chosen."""
    locks = locked(s, reasoning).get(s.preset, {})
    if not locks:
        return s
    defaults = set(TYPE_DEFAULTS[s.preset])
    omitted = [a for a in s.omitted_attributes if a not in locks] + [a for a in locks if a in defaults]
    return s.model_copy(update={"omitted_attributes": omitted})


def words_per_detail(s, reasoning: bool = True) -> float:
    if profile(s, reasoning) == "strict":
        return WORDS_PER_DETAIL["strict"]
    if s.mode == "local":
        return WORDS_PER_DETAIL["local"]
    return WORDS_PER_DETAIL["longer" if LONGER_MODELS.search(s.cloud_model) else "cloud"]


def recommended_words(s, reasoning: bool = True) -> int:
    """The shortest reliable caption length for this model and the switched-on photo details."""
    on = [
        a
        for a in details_for(s.preset)
        if a.get("media", "image") == "image" and a["id"] not in effective(s, reasoning).omitted_attributes
    ]
    return max(20, math.ceil(len(on) * words_per_detail(s, reasoning) / 10) * 10)


def summary(s) -> dict:
    """What the UI needs: the locked details with their reasons and the words per switched-on detail."""
    return {"profile": profile(s), "locked": locked(s), "words_per_detail": words_per_detail(s)}
