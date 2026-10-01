"""How reliably each model follows each detail switch, measured live and judged blind (output/switch-test).

A switch is offered in three ways (Petr, 2026-10-01): green when the model followed it in more than 85 % of the
test captions, orange from 50 % (it works, check the captions), greyed below 50 %. A style may be judged more
loosely (green above 70 %, orange from 30 %); for a character the switches are critical. A greyed switch stays at the
LoRA type's default for that model; the recipe keeps the user's own choice, so it returns with a model that can
follow it. Measured is the state the user switches to (a detail left out by default switched on, any other
switched off). A model we have not measured gets every switch: the app recommends, it does not forbid.
"""

from __future__ import annotations

import math
import re

from .training import TYPE_DEFAULTS, details_for

# Per LoRA type: (green above, orange from) as shares of the test captions that followed the switch.
THRESHOLDS = {"general": (0.85, 0.5), "character": (0.85, 0.5), "object": (0.85, 0.5), "style": (0.7, 0.3)}
# Per model, by name (newer versions of the same line included): (followed, test captions) for each switch it
# did not follow often enough to be green, 40 words, judged blind; the prompt of every test caption was checked to
# carry the switch as measured. A style on two print sets (the second with a single subject such as a turtle, a
# carp or a lantern), people and objects with the rule fixes of 0.3.0. Every other switch is green (a share needs
# at least 5 test captions; GPT's logo switched on was visible in only 2 and is green).
MEASURED: list[tuple[re.Pattern, dict[tuple[str, str], tuple[int, int]]]] = [
    (re.compile(r"qwen[^/]*max", re.I), {("style", "background"): (8, 15)}),
    (re.compile(r"grok", re.I), {("style", "identity"): (9, 15), ("style", "background"): (9, 15)}),
    (re.compile(r"muse-spark", re.I), {("character", "hair_color"): (8, 10)}),
    (re.compile(r"glm[^/]*flashx", re.I), {("style", "identity"): (7, 19), ("style", "background"): (9, 20)}),
    # The models we advise against, half switch test (the 5 hardest photos per LoRA type).
    (
        re.compile(r"glm-5v", re.I),
        {("character", "identity"): (4, 5), ("style", "identity"): (1, 5), ("style", "background"): (2, 5)},
    ),
    (
        re.compile(r"mimo[^/]*flash", re.I),
        {("character", "identity"): (3, 5), ("style", "identity"): (1, 5), ("style", "background"): (3, 5)},
    ),
    (re.compile(r"mimo[^/]*pro", re.I), {("character", "identity"): (4, 5)}),
    (re.compile(r"deepseek", re.I), {("character", "identity"): (4, 5)}),
]
# The models in the settings' table (their OpenRouter IDs, ui/models.js): the table shows each one's offer.
TABLE_MODELS = (
    "openai/gpt-6.1-sol",
    "anthropic/claude-opus-5.5",
    "google/gemini-3.8-flash",
    "qwen/qwen3.8-max-0902",
    "x-ai/grok-4.7",
    "meta/muse-spark-1.3",
    "z-ai/glm-5.3-flashx",
    "z-ai/glm-5v-turbo",
    "xiaomi/mimo-v2.6-flash",
    "deepseek/deepseek-v4.1-flash",
    "xiaomi/mimo-v2.6-pro",
    "moonshotai/kimi-k3",
)
# Local Qwen (Marvin, the managed runtime or an external llama-server running it), reasoning while it captions.
LOCAL_MEASURED: dict[tuple[str, str], tuple[int, int]] = {
    ("style", "identity"): (3, 10),
    ("style", "background"): (6, 10),
}
# Words per switched-on photo detail for the shortest reliable caption: 40 words for a character's 9 details on
# GPT, Claude, Qwen Max and Grok, 60 on Gemini, Muse, GLM, local Qwen with reasoning and any other model (at 40
# words Gemini described the pose of a close-up in 7 of 10 captions, at 60 in 9, at 80 in 10).
WORDS_PER_DETAIL = {"cloud": 4.4, "longer": 6.5}
SHORT_MODELS = re.compile(r"claude|anthropic|(^|/)gpt-|openai/|qwen[^/]*max|grok", re.I)


def measured(s) -> dict[tuple[str, str], tuple[int, int]]:
    if s.mode != "cloud":
        return LOCAL_MEASURED
    found: dict[tuple[str, str], tuple[int, int]] = {}
    for pattern, shares in MEASURED:
        if pattern.search(s.cloud_model):
            found |= shares
    return found


def offer(s) -> dict[str, dict[str, dict]]:
    """Per LoRA type, the switches this model does not follow reliably enough to be green: orange or grey, the
    state the user switches to and how many test captions followed it."""
    out: dict[str, dict[str, dict]] = {}
    for (lora_type, detail), (followed, captions) in measured(s).items():
        green_above, orange_from = THRESHOLDS[lora_type]
        share = followed / captions
        if share > green_above:
            continue
        out.setdefault(lora_type, {})[detail] = {
            "level": "orange" if share >= orange_from else "grey",
            "state": "on" if detail in TYPE_DEFAULTS[lora_type] else "off",
            "followed": followed,
            "captions": captions,
        }
    return out


def greyed(s) -> set[str]:
    return {d for d, o in offer(s).get(s.preset, {}).items() if o["level"] == "grey"}


def effective(s):
    """The settings a caption uses: every greyed detail at its LoRA type's default, the rest as chosen."""
    grey = greyed(s)
    if not grey:
        return s
    defaults = set(TYPE_DEFAULTS[s.preset])
    omitted = [a for a in s.omitted_attributes if a not in grey] + [a for a in grey if a in defaults]
    return s.model_copy(update={"omitted_attributes": omitted})


def words_per_detail(s) -> float:
    short = s.mode == "cloud" and SHORT_MODELS.search(s.cloud_model)
    return WORDS_PER_DETAIL["cloud" if short else "longer"]


def recommended_words(s) -> int:
    """The shortest reliable caption length for this model and the switched-on photo details."""
    omitted = effective(s).omitted_attributes
    on = [a for a in details_for(s.preset) if a.get("media", "image") == "image" and a["id"] not in omitted]
    return max(20, math.ceil(len(on) * words_per_detail(s) / 10) * 10)


def summary(s) -> dict:
    """What the UI needs: the orange and greyed switches of the configured model, the words per switched-on detail
    and, for the model table, the offer of every measured model and of local Qwen."""
    table = {m: offer(s.model_copy(update={"mode": "cloud", "cloud_model": m})) for m in TABLE_MODELS}
    table["local"] = offer(s.model_copy(update={"mode": "local"}))
    return {"offer": offer(s), "words_per_detail": words_per_detail(s), "table": table}
