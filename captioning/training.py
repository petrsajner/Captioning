"""Caption conditioning intent; these controls do not mask image training loss.

Every LoRA type has its own set of details (Petr, 2026-09-26): a character's hair and clothing mean
nothing for a product, and a style LoRA learns its medium and palette. A detail lists the types
that show it and may be named and instructed differently for a type (`by_type`).
"""

from typing import Any, Literal

Attribute = Literal[
    "identity",
    "object_text",
    "state",
    "hair_color",
    "hairstyle",
    "clothing",
    "accessories",
    "pose",
    "interaction",
    "expression",
    "background",
    "lighting",
    "composition",
    "style",
    "palette",
    "motion",
    "camera_motion",
]
LoraType = Literal["general", "character", "object", "style"]
ALL_TYPES = ("general", "character", "object", "style")
PEOPLE = ("general", "character")
# Details left out by default ("Apply defaults for this LoRA type"); the LoRA learns them.
TYPE_DEFAULTS: dict[str, list[str]] = {
    "general": [],
    "character": ["identity", "hair_color"],
    "object": ["identity", "object_text"],
    "style": ["style", "palette"],
}
ATTRIBUTES: list[dict[str, Any]] = [
    {
        "id": "identity",
        "types": ALL_TYPES,
        "label": "Identity / subject appearance",
        "detail": "Facial and physical features; an object’s characteristic shape, material and colors.",
        "instruction": "stable visual identity of the MAIN subject: facial structure and distinctive physical features; for an animal its coat markings; for an object its characteristic shape, material and colors",
        "by_type": {
            "object": {
                "label": "Object appearance",
                "detail": "The object’s shape, material, fixed colors and markings.",
                "instruction": "the main object's own appearance: its shape, size, parts, material, surface, colors, "
                "pattern and markings",
            },
            "style": {
                "label": "What is depicted",
                "detail": "People, animals and things with their clothing and expression, always described generically.",
                "instruction": "what is depicted: people, animals and things with their visible appearance, clothing "
                "and expression, described generically and never as identifiable individuals",
            },
        },
    },
    {
        "id": "object_text",
        "types": ("object",),
        "label": "Logo and text on the object",
        "detail": "Brand marks, labels and printed text on the object itself.",
        "instruction": "logos, brand marks, labels and any printed or engraved text on the main object itself",
    },
    {
        "id": "state",
        "types": ("object",),
        "label": "Variant and state",
        "detail": "Open or closed, folded, switched on or off; a version or colorway when the dataset has several.",
        "instruction": "the main object's changeable state: open or closed, folded or unfolded, assembled, switched on "
        "or off, full or empty; and its version or colorway only when the additional dataset instructions say it "
        "comes in several",
    },
    # Separate since 0.2.0: a character's hair color usually belongs to the LoRA, its hairstyle to the prompt.
    {
        "id": "hair_color",
        "types": PEOPLE,
        "label": "Hair color",
        "detail": "The main person’s hair and facial hair color and tones.",
        "instruction": "hair color and hair tones of the main person, including the color of any beard or other facial hair and color words such as blonde, brunette, dark, gray, light-colored or red",
    },
    {
        "id": "hairstyle",
        "types": PEOPLE,
        "label": "Hairstyle",
        "detail": "Hair length, cut and how it is worn, such as a ponytail or bangs; beard or stubble.",
        "instruction": "hairstyle of the main person: hair length, cut, parting and how it is worn, such as loose, braided, a ponytail or bangs, and the shape of any beard, moustache or stubble",
    },
    {
        "id": "clothing",
        "types": PEOPLE,
        "label": "Clothing",
        "detail": "Garments, cut, colors and fabric.",
        "instruction": "clothing of the main subject, garment type, cut, colors and fabric",
    },
    {
        "id": "accessories",
        "types": PEOPLE,
        "label": "Accessories",
        "detail": "Jewelry, glasses, hats and other wearable accessories.",
        "instruction": "accessories worn by the main subject, jewelry, glasses, hats and wearable accessories",
    },
    {
        "id": "pose",
        "types": ALL_TYPES,
        "label": "Pose and action",
        "detail": "Posture, movement, body orientation and action.",
        "instruction": "pose, body orientation and action of the main subject",
        "by_type": {
            "object": {
                "label": "Placement and orientation",
                "detail": "Where the object is, what it rests on and which side faces the camera.",
                "instruction": "placement of the main object: where it is, what it rests on or hangs from, and its "
                "orientation, meaning which side faces the camera and how it is tilted",
            },
            "style": {
                "detail": "What the people and animals are doing and how they are posed.",
                "instruction": "poses and actions of the depicted people and animals",
            },
        },
    },
    {
        "id": "interaction",
        "types": ("object",),
        "label": "Use and interaction",
        "detail": "Who holds, wears or uses the object and how; hands and people described generically.",
        "instruction": "how the main object is held, worn or used and by whom, with the hands and people "
        "described generically",
    },
    {
        "id": "expression",
        "types": PEOPLE,
        "label": "Facial expression",
        "detail": "Visible expression and gaze, without guessing emotions.",
        "instruction": "visible facial expression and gaze of the main subject, without inferring mental states",
    },
    {
        "id": "background",
        "types": ALL_TYPES,
        "label": "Environment and background",
        "detail": "Location, scenery, props and secondary subjects.",
        "instruction": "environment, background, scene props and secondary subjects",
        "by_type": {
            "object": {
                "detail": "Location, surface, background and other objects around it.",
                "instruction": "environment around the main object: location, the surface it is on, background and "
                "other objects",
            }
        },
    },
    {
        "id": "lighting",
        "types": ALL_TYPES,
        "label": "Lighting",
        "detail": "Light direction and quality, shadows and light color.",
        "instruction": "lighting conditions, light direction, shadows and light color",
        "by_type": {
            "style": {
                "label": "Light situation",
                "detail": "Time of day, weather and visible light sources; how light is rendered belongs to the style.",
                "instruction": "the light situation: time of day, weather and visible light sources, not the way light "
                "and shadow are rendered",
            }
        },
    },
    {
        "id": "composition",
        "types": ALL_TYPES,
        "label": "Composition and camera",
        "detail": "Framing, camera angle, subject placement and depth of field.",
        "instruction": "framing, camera viewpoint, subject placement and relative size, depth of field and focus",
    },
    {
        "id": "style",
        "types": ALL_TYPES,
        "label": "Visual style",
        "detail": "Medium, drawing or photography, rendering technique and overall palette.",
        "instruction": "visual style, medium, rendering technique and overall artistic color palette",
        "by_type": {
            "object": {
                "label": "Medium",
                "detail": "Photograph, 3D render or illustration.",
                "instruction": "the medium of the image: photograph, 3D render, illustration or painting",
            },
            "style": {
                "label": "Medium and technique",
                "detail": "Medium, brushwork, line work, texture and how light and shadow are rendered.",
                "instruction": "medium and technique: painting, drawing, print, render or photograph, brushwork, line "
                "work, shading, texture, grain and the way light and shadow are rendered",
            },
        },
    },
    {
        "id": "palette",
        "types": ("style",),
        "label": "Color palette and grading",
        "detail": "The overall color scheme and grading; colors of single things stay described.",
        "instruction": "the overall color palette, color scheme and grading of the image, not the colors of "
        "individual things",
    },
    # Only for video clips ("media": "clip"); photos never get these instructions.
    {
        "id": "motion",
        "types": ALL_TYPES,
        "label": "Motion over time",
        "detail": "What the main subject does from the start to the end of the clip.",
        "instruction": "movement and actions of the main subject over the clip, in time order",
        "media": "clip",
        "by_type": {
            "object": {
                "detail": "How the object moves or is handled from the start to the end of the clip.",
                "instruction": "how the main object moves or is handled over the clip, in time order",
            }
        },
    },
    {
        "id": "camera_motion",
        "types": ALL_TYPES,
        "label": "Camera movement",
        "detail": "Pans, pushes, tracking and other camera moves.",
        "instruction": "camera movement over the clip with its type, amplitude and speed",
        "media": "clip",
    },
]


def details_for(lora_type: str) -> list[dict[str, Any]]:
    """The details of a LoRA type, with its own names and instructions."""
    return [
        {**{k: v for k, v in a.items() if k not in ("types", "by_type")}, **a.get("by_type", {}).get(lora_type, {})}
        for a in ATTRIBUTES
        if lora_type in a["types"]
    ]


def type_ids(lora_type: str) -> set[str]:
    return {a["id"] for a in ATTRIBUTES if lora_type in a["types"]}


def _policy_details(settings, media: str, only: tuple[str, ...] | None) -> list[dict[str, Any]]:
    """The details a policy covers: clip-only details for clips, and `only` limits it to some details."""
    return [
        a for a in details_for(settings.preset) if a.get("media", media) == media and (only is None or a["id"] in only)
    ]


def described_details(settings, media: str = "image", only: tuple[str, ...] | None = None) -> list[str]:
    """Instructions of the details the caption describes (CONTROL_WITH_PROMPT), for keeping them when shortening."""
    omitted = set(settings.omitted_attributes)
    return [a["instruction"] for a in _policy_details(settings, media, only) if a["id"] not in omitted]


def policy_prompt(settings, media: str = "image", only: tuple[str, ...] | None = None):
    """The detail policy; clip-only details appear for clips, and `only` limits it to some details."""
    # The model-facing labels are unchanged: omitted details are the ones the LoRA should learn.
    omitted = set(settings.omitted_attributes)
    lines = [
        "MANDATORY CAPTION POLICY (higher priority than preset and optional hints):",
        "The user is deciding which attributes should be associated with their LoRA concept and which should be described for later prompt control.",
        "For LEARN_WITH_LORA: omit the attribute's visual details from the caption. Keep only a generic subject/category or its provided identifier.",
        "For CONTROL_WITH_PROMPT: explicitly describe the visible attribute so it can be conditioned separately. Do not invent absent or uncertain details.",
        # Reported 2026-09-28: a character's clothing was missing. The length target must not drop a detail.
        "Give every visible CONTROL_WITH_PROMPT attribute at least a few words, also in a short caption: shorten other "
        "wording rather than leave one out.",
    ]
    for a in _policy_details(settings, media, only):
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
