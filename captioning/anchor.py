"""How a caption names what the LoRA learns, per LoRA type ("What are you training?").

The same rules hold for every caption output (Normal, BRIA JSON and the video models):
- character and object LoRAs: the vision model writes a token (<character>, <object>) where the
  subject is first named, and the application replaces it with "{trigger}, {class}," so the
  trigger appears exactly once: "Velmira, a woman, sits ...", "Zorbo, a backpack, hangs ...";
- style LoRAs: the caption describes only the content, and the application starts it with
  "{trigger} style, ";
- general datasets: the trigger, if any, starts the caption.
"""

from __future__ import annotations

import re

TOKENS = {"character": "<character>", "object": "<object>"}
# The class phrase used when the recipe leaves it empty.
DEFAULT_CLASS = {"character": "a person", "object": "an object"}
# How instructions refer to the named subject: noun, object pronoun, "X is", possessive.
_WORDS = {"character": ("character", "them", "they are", "their"), "object": ("object", "it", "it is", "its")}
# Petr, 2026-09-29: the model does not need to know what a LoRA learns; it needs exact rules (training.py).
PURPOSE = (
    "Follow the caption rules at the end exactly: describe everything they list under MUST DESCRIBE and nothing "
    "they list under NEVER DESCRIBE."
)
KIND = {"general": "", "character": "character ", "object": "object ", "style": "visual-style "}
# Notices finishing can add to a caption; each is a UI message with a translation.
MISSING_H3 = "Put the name into [Shot 1] manually."
ADDED_AT_START = "The name was added at the start."
NAMED_TWICE = "The subject was named more than once; later mentions now use its type."
PLACED_AT_CLASS = "The name was placed at the first mention of its type."
TRIGGER_REPEATED = "The trigger appears more than once in this caption."
TRIGGER_INSIDE_WORD = "The trigger is part of another word here; trainers may miss it. Choose a more distinct name."
TRIGGER_SPACE = "The trigger contains a space; a single invented word works best."
FINISH_NOTICES = (
    MISSING_H3,
    ADDED_AT_START,
    NAMED_TWICE,
    PLACED_AT_CLASS,
    TRIGGER_REPEATED,
    TRIGGER_INSIDE_WORD,
    TRIGGER_SPACE,
)


def clean_trigger(trigger: str) -> str:
    return trigger.strip().strip(",").strip()


def token(s) -> str | None:
    """The placeholder the vision model writes for a character or object; style and general have none."""
    return TOKENS.get(s.preset)


def subject_class(s) -> str:
    return s.subject_class or DEFAULT_CLASS.get(s.preset, "")


def style_phrase(trigger: str) -> str:
    """ "Zorvak" -> "Zorvak style"; a trigger that already ends in "style" is kept."""
    trigger = clean_trigger(trigger)
    if not trigger or re.search(r"\bstyle$", trigger, re.I):
        return trigger
    return trigger + " style"


def lead_phrase(s) -> str:
    """What starts every style or general caption; character and object LoRAs use the opening instead."""
    return style_phrase(s.trigger) if s.preset == "style" else clean_trigger(s.trigger)


def opening(trigger: str, cls: str) -> str:
    """The subject's first mention: "Velmira, a woman," or only the class phrase without a trigger."""
    trigger = clean_trigger(trigger)
    return f"{trigger}, {cls}," if trigger else cls


def definite(cls: str) -> str:
    """A later mention of the subject: "a woman" -> "the woman"."""
    words = cls.split()
    if len(words) > 1 and words[0].lower() in ("a", "an", "the"):
        words = words[1:]
    return "the " + " ".join(words)


def _lower_first(text: str) -> str:
    """ "A woman sits" -> "a woman sits" after a prefix; "I", acronyms and names in capitals stay."""
    first = text.split(" ", 1)[0]
    if first[:1].isupper() and first[1:] == first[1:].lower() and first != "I":
        return text[0].lower() + text[1:]
    return text


def prefix(text: str, phrase: str) -> str:
    """Start the caption with the phrase ("Zorvak style, a woman sits ...") unless it already does."""
    if not phrase or re.match(re.escape(phrase) + r"(?:\s|[,.:;]|$)", text, re.I):
        return text
    return f"{phrase}, {_lower_first(text)}"


def naming_line(s, where: str = "where {is} first mentioned", language: str = "English") -> str | None:
    """The token instruction for character and object LoRAs; `where` says where the token goes."""
    tok = token(s)
    if tok is None:
        return None
    noun, obj, is_, possessive = _WORDS[s.preset]
    cls = subject_class(s)
    later = (
        f"write {definite(cls)!r} or a matching pronoun"
        if language == "English"
        else f"refer to {obj} with a matching {language} pronoun or noun"
    )
    return (
        f"The main {noun} is {cls!r}. Name {obj} exactly once, as the literal token {tok}, "
        f"{where.format(**{'is': is_})}. The application replaces the token with {possessive} name and {cls!r}, "
        f"so do not say again what kind of {noun} {is_}. Afterwards {later}; never write {tok} again and never give "
        f"{obj} a name."
    )


def subject_lines(s, where: str = "at the start") -> list[str]:
    """What the LoRA type means for the content of any caption; `where` says where the trigger goes.

    What each detail may and may not say is in the caption rules (training.policy_prompt).
    """
    lines = []
    if s.preset == "general":
        lines.append("Identify the main subject and describe it.")
    elif s.preset == "character":
        if "background" not in s.omitted_attributes:
            lines.append("Keep the main character's description separate from other people in the image.")
    elif s.preset == "object":
        lines.append("The main subject is the object; people who hold, wear or use it are secondary subjects.")
        if "identity" in s.omitted_attributes:
            cls = subject_class(s)
            lines.append(f"Call it only {cls!r} or {definite(cls)!r}, without adjectives.")
    else:
        lines.append("Describe people generically, such as a woman or an old man; never say who they are.")
        if "palette" in s.omitted_attributes:
            lines.append(
                "Name the colors of single things, but never the overall color palette, color scheme or grading of "
                "the image."
            )
    if token(s) is None and lead_phrase(s):
        lines.append(
            f"Do not write a style name; the application adds it {where}."
            if s.preset == "style"
            else f"Do not add a training trigger token; the application adds it {where}."
        )
    return lines


def text_line(s) -> str:
    """Whether readable text is transcribed; an object's own logo and text follow its detail switch."""
    if s.text_in_image:
        return "Transcribe readable visible text when relevant."
    if s.preset == "object" and "object_text" not in s.omitted_attributes:
        return "Do not transcribe text or watermarks, except the logo and text on the main object."
    return "Do not transcribe text or watermarks."


def _tidy(text: str) -> str:
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r",\s*([.;:!?])", r"\1", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _capitalize_sentences(text: str, phrase: str) -> str:
    """Capitalize the inserted phrase where it starts a sentence ("a woman sits" -> "A woman sits")."""
    if not phrase or not phrase[0].islower():
        return text
    pattern = r"(^|[.!?]\s+)" + re.escape(phrase)
    return re.sub(pattern, lambda m: m.group(1) + phrase[0].upper() + phrase[1:], text)


def name_subject(text: str, s, output: str, english: bool = True) -> tuple[str, list[str], bool]:
    """Put the trigger into the model's text for the recipe's LoRA type.

    Returns the text, notices for the user and whether it needs manual review. For H3 this is the
    [Shot 1] body; video.py adds the field labels.
    """
    tok = token(s)
    if tok is None:
        return prefix(text, lead_phrase(s)), [], False
    notices: list[str] = []
    review = False
    trigger, cls = clean_trigger(s.trigger), subject_class(s)
    body = re.sub(r"<\s*" + tok[1:-1] + r"\s*>", tok, text, flags=re.I)
    # The model sometimes adds an article or repeats the class around the token:
    # "frames a <character>", "<character>, a woman, sits", "<character> is a woman with ...".
    body = re.sub(r"\b(?:a|an|the)\s+" + re.escape(tok), tok, body, flags=re.I)
    said_again = "(?:" + re.escape(cls) + "|" + re.escape(definite(cls)) + ")"
    body = re.sub(re.escape(tok) + r"\s*,?\s*" + said_again + r"\b", tok, body, flags=re.I)
    for verb, replacement in (("is", " has"), ("as", " with")):
        body = re.sub(
            re.escape(tok) + rf"\s+{verb}\s+" + re.escape(cls) + r"\s+with\b", tok + replacement, body, flags=re.I
        )
    first, later = opening(trigger, cls), definite(cls) if english else cls
    count = body.count(tok)
    mention = re.search(r"\b" + re.escape(cls) + r"\b", body, flags=re.I)
    if not mention and len(cls.split()) > 1:
        # "A 3x3 puzzle cube sits" for "a puzzle cube": the name replaces the whole phrase.
        noun = re.escape(cls.split()[-1])
        mention = re.search(r"\b(?:a|an|the)\s+(?:[\w-]+\s+){0,3}?" + noun + r"\b", body, flags=re.I)
    if count == 0 and mention:
        # The model wrote the class instead of the token: "frames a woman seated ..."
        body = body[: mention.start()] + first + body[mention.end() :]
        notices.append(PLACED_AT_CLASS)
    elif count == 0 and not trigger:
        pass  # Without a trigger there is no name to add.
    elif count == 0 and output == "h3":
        review = True
        notices.append(MISSING_H3)
    elif count == 0:
        body = f"{first} {_lower_first(body)}"
        notices.append(ADDED_AT_START)
    else:
        head, _, tail = body.partition(tok)
        if count > 1:
            tail = tail.replace(tok, later)
            notices.append(NAMED_TWICE)
        body = head + first + tail
    # Only a class phrase is capitalized at a sentence start: trainers match the trigger exactly.
    body = _tidy(body) if trigger else _capitalize_sentences(_tidy(body), first)
    return _capitalize_sentences(body, later), notices, review


def class_caption(caption: str, s) -> str:
    """The caption without its trigger, as used for preservation (DOP); LORA Train uses the same rule.

    Character and object: "Velmira, a woman, sits" -> "A woman sits". Style and general: the leading
    "Zorvak style, " or "ohwx, " is removed. The result equals the caption written without a trigger.
    """
    trigger = clean_trigger(s.trigger)
    if not trigger:
        return caption
    if token(s) is None:
        replacements = [(lead_phrase(s) + ", ", "")]
    else:
        cls = subject_class(s)
        replacements = [(f"{trigger}, {cls},", cls), (f"{trigger}, {cls}", cls)]
    for old, new in replacements:
        start = caption.find(old)
        if start >= 0:
            rest = new + caption[start + len(old) :]
            # Capitalize where the remaining text starts a sentence or the [Shot 1] body.
            if re.search(r"(?:^|[.!?]\s+|\[Shot 1\]\s+)$", caption[:start]):
                rest = rest[:1].upper() + rest[1:]
            return caption[:start] + rest
    return caption


def trigger_warnings(text: str, s) -> list[str]:
    trigger = clean_trigger(s.trigger)
    if not trigger:
        return []
    warnings = []
    if text.count(trigger) > 1:
        warnings.append(TRIGGER_REPEATED)
    if re.search(r"\w" + re.escape(trigger) + r"|" + re.escape(trigger) + r"\w", text):
        warnings.append(TRIGGER_INSIDE_WORD)
    if " " in trigger and token(s) is not None:
        warnings.append(TRIGGER_SPACE)
    return warnings


def finish_caption(draft: str, s, output: str = "normal") -> tuple[str, list[str], bool]:
    """Normal captions: the model's text with the trigger put in place, plus notices."""
    text, notices, review = name_subject(draft, s, output, english=s.language == "English")
    return text, notices + trigger_warnings(text, s), review


def name_in_json(data: dict, s) -> None:
    """BRIA JSON: the trigger goes into short_description; other fields use the class phrase."""
    data["short_description"], _, _ = name_subject(
        data["short_description"], s, "bria_json", english=s.language == "English"
    )
    tok = token(s)
    if tok is None:
        return

    def replace(value):
        if isinstance(value, str):
            return re.sub(r"<\s*" + tok[1:-1] + r"\s*>", subject_class(s), value, flags=re.I)
        if isinstance(value, list):
            return [replace(v) for v in value]
        if isinstance(value, dict):
            return {k: replace(v) for k, v in value.items()}
        return value

    for key, value in data.items():
        if key != "short_description":
            data[key] = replace(value)
