"""Caption conditioning intent; these controls do not mask image training loss."""

from typing import Literal

Attribute = Literal[
    "identity",
    "hair_color",
    "hairstyle",
    "clothing",
    "accessories",
    "pose",
    "expression",
    "background",
    "lighting",
    "composition",
    "style",
]
ATTRIBUTES = [
    {
        "id": "identity",
        "label": "Identity / subject appearance",
        "detail": "Facial and physical features; an object’s characteristic shape, material and colors.",
        "instruction": "stable visual identity of the MAIN subject: facial structure and distinctive physical features; for an animal its coat markings; for an object its characteristic shape, material and colors",
    },
    # Separate since 0.2.0: a character's hair color usually belongs to the LoRA, its hairstyle to the prompt.
    {
        "id": "hair_color",
        "label": "Hair color",
        "detail": "The main person’s hair color and tones.",
        "instruction": "hair color and hair tones of the main person, including color words for the hair such as blonde, brunette, dark, light-colored or red",
    },
    {
        "id": "hairstyle",
        "label": "Hairstyle",
        "detail": "Hair length, cut and how it is worn, such as a ponytail or bangs.",
        "instruction": "hairstyle of the main person: hair length, cut, parting and how it is worn, such as loose, braided, a ponytail or bangs",
    },
    {
        "id": "clothing",
        "label": "Clothing",
        "detail": "Garments, cut, colors and fabric.",
        "instruction": "clothing of the main subject, garment type, cut, colors and fabric",
    },
    {
        "id": "accessories",
        "label": "Accessories",
        "detail": "Jewelry, glasses, hats and other wearable accessories.",
        "instruction": "accessories worn by the main subject, jewelry, glasses, hats and wearable accessories",
    },
    {
        "id": "pose",
        "label": "Pose and action",
        "detail": "Posture, movement, body orientation and action.",
        "instruction": "pose, body orientation and action of the main subject",
    },
    {
        "id": "expression",
        "label": "Facial expression",
        "detail": "Visible expression and gaze, without guessing emotions.",
        "instruction": "visible facial expression and gaze of the main subject, without inferring mental states",
    },
    {
        "id": "background",
        "label": "Environment and background",
        "detail": "Location, scenery, props and secondary subjects.",
        "instruction": "environment, background, scene props and secondary subjects",
    },
    {
        "id": "lighting",
        "label": "Lighting",
        "detail": "Light direction and quality, shadows and light color.",
        "instruction": "lighting conditions, light direction, shadows and light color",
    },
    {
        "id": "composition",
        "label": "Composition and camera",
        "detail": "Framing, camera angle, subject placement and depth of field.",
        "instruction": "framing, camera viewpoint, subject placement and relative size, depth of field and focus",
    },
    {
        "id": "style",
        "label": "Visual style",
        "detail": "Medium, drawing or photography, rendering technique and overall palette.",
        "instruction": "visual style, medium, rendering technique and overall artistic color palette",
    },
]


def policy_prompt(settings):
    # The model-facing labels are unchanged: omitted details are the ones the LoRA should learn.
    omitted = set(settings.omitted_attributes)
    lines = [
        "MANDATORY CAPTION POLICY (higher priority than preset and optional hints):",
        "The user is deciding which attributes should be associated with their LoRA concept and which should be described for later prompt control.",
        "For LEARN_WITH_LORA: omit the attribute's visual details from the caption. Keep only a generic subject/category or its provided identifier.",
        "For CONTROL_WITH_PROMPT: explicitly describe the visible attribute so it can be conditioned separately. Do not invent absent or uncertain details.",
    ]
    for a in ATTRIBUTES:
        lines.append(
            (
                "LEARN_WITH_LORA — DO NOT DESCRIBE: "
                if a["id"] in omitted
                else "CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE: "
            )
            + a["instruction"]
            + "."
        )
    lines += [
        "Do not leak omitted attributes through synonyms, the opening sentence, summaries, background, relationships or other fields.",
        "These settings affect captions only. Do not write explanations about learning, the settings or LoRA into the caption.",
    ]
    return "\n".join(lines)
