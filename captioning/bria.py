"""FIBO structured captions matching BRIA's published ImageAnalysis field layout.

Reference: Bria-AI/FIBO/src/fibo_inference/vlm/gemini_api.py and the fine-tuning
example. Empty required strings represent deliberately omitted conditioning.
The upstream parse_caption normalizer removes empty fields. No invented schema.
"""
import json
import re
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ObjectDescription(StrictModel):
    description: str = Field(min_length=1)
    location: str
    relationship: str
    relative_size: str | None = None
    shape_and_color: str | None = None
    texture: str | None = None
    appearance_details: str | None = None
    number_of_objects: int | None = Field(None, ge=1)
    pose: str | None = None
    expression: str | None = None
    clothing: str | None = None
    action: str | None = None
    gender: str | None = None
    skin_tone_and_texture: str | None = None
    orientation: str | None = None


class Lighting(StrictModel):
    conditions: str
    direction: str
    shadows: str | None = None


class Aesthetics(StrictModel):
    composition: str
    color_scheme: str
    mood_atmosphere: str
    # Also present in BRIA's published fine-tuning example / normalized captions.
    preference_score: str | None = None
    aesthetic_score: str | None = None


class Photography(StrictModel):
    depth_of_field: str
    focus: str
    camera_angle: str
    lens_focal_length: str


class TextRender(StrictModel):
    text: str
    location: str
    size: str
    color: str
    font: str
    appearance_details: str | None = None


class FiboCaption(StrictModel):
    short_description: str = Field(min_length=1)
    objects: list[ObjectDescription]
    background_setting: str
    lighting: Lighting
    aesthetics: Aesthetics
    photographic_characteristics: Photography | None = None
    style_medium: str | None = None
    text_render: list[TextRender] | None = None
    context: str
    artistic_style: str | None = None


class CaptionValidationError(ValueError):
    def __init__(self, message, draft):
        super().__init__(message)
        self.draft = draft


def schema_prompt():
    return "\n".join([
        "Return ONLY one valid BRIA FIBO JSON object, without markdown. Use the exact English field names below.",
        "Put the main subject FIRST in objects. Its description is a brief generic category/name, not a catalogue of details.",
        "Put its identity details in shape_and_color, texture, skin_tone_and_texture; hair and wearable accessories in appearance_details; garments in clothing.",
        "Respect the caption policy in EVERY field, including short_description and context. Do not repeat omitted details in free text.",
        "Use an empty string for required descriptive fields deliberately omitted by the policy or not observable; use null for optional fields. Do not invent content to fill the schema.",
        "If background is omitted, list only the main subject in objects. Do not create separate objects for omitted clothing or accessories.",
        "Do not guess gender, camera settings, exact focal length, intended use or aesthetic scores. context may be empty. No total word-count constraint applies to JSON.",
        "Schema: " + json.dumps(FiboCaption.model_json_schema(), ensure_ascii=False),
    ])


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key " + key)
        result[key] = value
    return result


def validate_json(text: str) -> dict:
    try:
        def invalid_constant(value):
            raise ValueError("Invalid JSON constant " + value)
        parsed = json.loads(text.strip().lstrip("\ufeff"), object_pairs_hook=_unique_pairs, parse_constant=invalid_constant)
        return FiboCaption.model_validate(parsed).model_dump(exclude_none=True)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, ValidationError):
            detail = "; ".join(".".join(map(str, e["loc"])) + ": " + e["msg"] for e in exc.errors(include_input=False)[:4])
        else:
            detail = str(exc)
        raise CaptionValidationError("Invalid BRIA/FIBO JSON: " + detail, text) from None


def normalize_json(text: str, settings=None) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    match = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", cleaned, flags=re.I)
    if match:
        cleaned = match.group(1).strip()
    data = validate_json(cleaned)
    if settings is not None:
        learned = set(settings.learn_attributes)
        if "background" in learned:
            data["background_setting"] = ""
            data["context"] = ""
            data["objects"] = data["objects"][:1]
        if "lighting" in learned:
            data["lighting"] = {"conditions":"", "direction":""}
        if "composition" in learned:
            data.pop("photographic_characteristics", None)
            data["aesthetics"]["composition"] = ""
            for obj in data["objects"]:
                obj["location"] = ""
                obj["relationship"] = ""
                obj.pop("relative_size", None)
        if "style" in learned:
            data.pop("style_medium", None)
            data.pop("artistic_style", None)
            data["aesthetics"].update(color_scheme="", mood_atmosphere="")
        if data["objects"]:
            main = data["objects"][0]
            groups = {"identity":["shape_and_color", "texture", "gender", "skin_tone_and_texture"],
                      "clothing":["clothing"], "pose":["pose", "action", "orientation"], "expression":["expression"]}
            for group, fields in groups.items():
                if group in learned:
                    for field in fields: main.pop(field, None)
            if {"hair", "accessories"} <= learned:
                main.pop("appearance_details", None)
        if not settings.text_in_image:
            data["text_render"] = []
        trigger = settings.trigger.strip().strip(",")
        if trigger and not re.match(re.escape(trigger) + r"(?:\s|[,.:;]|$)", data["short_description"], re.I):
            data["short_description"] = trigger + ", " + data["short_description"]
    ordered = FiboCaption.model_validate(data).model_dump(exclude_none=True)
    return json.dumps(ordered, ensure_ascii=False, indent=2, allow_nan=False)
