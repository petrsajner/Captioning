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
# Each detail tells the model exactly what the caption MUST contain when it is switched on and what it must
# NEVER contain when it is off, with concrete words (Petr, 2026-09-29: the model does not follow general wording
# such as "the LoRA learns this"; live, clothing, accessories, background and hairstyle leaked when switched off).
ATTRIBUTES: list[dict[str, Any]] = [
    {
        "id": "identity",
        "types": ALL_TYPES,
        "label": "Identity / subject appearance",
        "detail": "Facial and physical features; an object’s characteristic shape, material and colors.",
        "must": "Face and body: the main subject's visible facial features and physical traits, such as face shape, "
        "eye color, eyebrows, nose, lips, skin tone, freckles, scars, tattoos, build and apparent age; for an animal "
        "its coat, markings and colors. Example: 'a square jaw, gray eyes and a small scar above the left "
        "eyebrow'.",
        "never": "Face and body: nothing about the main subject's face or physical traits. No face shape, eye color, "
        "eyebrows, nose, lips, skin tone, freckles, scars, tattoos, build, body shape or apparent age (not young, "
        "old, elderly); for an animal no coat, markings or colors.",
        "by_type": {
            "object": {
                "label": "Object appearance",
                "detail": "The object’s shape, material, fixed colors and markings.",
                "must": "Object appearance: the main object's own shape, size, parts, material, surface, colors, "
                "pattern and markings. Example: 'a round ceramic mug with a matte blue glaze and a white rim'.",
                "never": "Object appearance: nothing about what the main object itself looks like. No shape, size, "
                "parts, material, surface, colors, pattern or markings of the object (not colorful, glossy, plastic, "
                "wooden, metal, striped), also not in summaries or in the colors of the image.",
            },
            "style": {
                "label": "What is depicted",
                "detail": "People, animals and things with their clothing and expression, always described generically.",
                "must": "What is depicted: the people, animals and things in the image, described generically with "
                "their visible clothing and expression, never as identifiable individuals. Example: 'a fisherman in a "
                "straw coat, a dog on a path'.",
                "never": "What is depicted: nothing about the people, animals and things in the image, their "
                "clothing or expressions.",
            },
        },
    },
    {
        "id": "object_text",
        "types": ("object",),
        "label": "Logo and text on the object",
        "detail": "Brand marks, labels and printed text on the object itself.",
        "must": "Logo and text: the logos, brand marks, labels and readable printed or engraved text on the main "
        "object itself. Example: 'a brand name printed on the front pocket'.",
        "never": "Logo and text: no logo, brand mark, label or text on the object and never a brand or product name.",
    },
    {
        "id": "state",
        "types": ("object",),
        "label": "Variant and state",
        "detail": "Open or closed, folded, switched on or off; a version or colorway when the dataset has several.",
        "must": "Variant and state: the main object's changeable state, such as open or closed, folded or unfolded, "
        "assembled, switched on or off, full or empty; its version or colorway only when the additional dataset "
        "instructions say it comes in several.",
        "never": "Variant and state: nothing about the main object's changeable state. Not open, closed, folded, "
        "unfolded, assembled, switched on or off, full or empty, and no version or colorway.",
    },
    # Separate since 0.2.0: a character's hair color usually belongs to the LoRA, its hairstyle to the prompt.
    {
        "id": "hair_color",
        "types": PEOPLE,
        "label": "Hair color",
        "detail": "The main person’s hair and facial hair color and tones.",
        "must": "Hair color: the color of the main person's hair and of any beard or moustache. Example: 'auburn "
        "hair', 'a gray beard'.",
        "never": "Hair color: no color of the main person's hair, beard or moustache. Never blonde, brunette, "
        "brown, dark, black, gray, white, silver, red, auburn, ginger, fair or light-colored hair or facial hair.",
    },
    {
        "id": "hairstyle",
        "types": PEOPLE,
        "label": "Hairstyle",
        "detail": "Hair length, cut and how it is worn, such as a ponytail or bangs; beard or stubble.",
        "must": "Hairstyle: how long the main person's hair is, its texture, cut and how it is worn, and the shape "
        "of any beard or moustache. Example: 'a shoulder-length braid', 'short spiky hair', 'a full beard'.",
        "never": "Hairstyle: nothing about the main person's hair length, texture, cut or how it is worn, and "
        "nothing about a beard, moustache, stubble or being clean-shaven. Never long, short, shoulder-length, wavy, "
        "curly, straight, loose, bun, ponytail, braid, bangs, bob, pixie cut or parted.",
    },
    {
        "id": "clothing",
        "types": PEOPLE,
        "label": "Clothing",
        "detail": "Garments, cut, colors and fabric.",
        "must": "Clothing: every garment the main person wears, each with its color and, when clear, its cut or "
        "fabric. Example: 'a green knitted cardigan over a striped shirt', 'blue denim overalls'.",
        "never": "Clothing: nothing the main person wears. No garment (dress, gown, shirt, t-shirt, blouse, top, "
        "sweater, jacket, coat, suit, tie, uniform, apron, trousers, jeans, skirt, shoes, boots), no color, "
        "fabric or cut of clothes, and no wears, wearing, dressed, outfit, attire or costume about clothes.",
    },
    {
        "id": "accessories",
        "types": PEOPLE,
        "label": "Accessories",
        "detail": "Jewelry, glasses, hats and other wearable accessories.",
        "must": "Accessories: every accessory the main person wears, such as earrings, necklaces, rings, glasses, "
        "hats, caps, helmets, tiaras, hair ornaments, gloves, belts, straps, worn bags, badges and lanyards. "
        "Example: 'round sunglasses and a straw hat', 'a leather watch and a silver necklace'.",
        "never": "Accessories: nothing the main person wears besides clothes. No jewelry, earrings, necklaces, "
        "rings, glasses, hats, caps, helmets, tiaras, hair ornaments or flowers in the hair, gloves, belts, "
        "straps, worn bags, badges or lanyards.",
    },
    {
        "id": "pose",
        "types": ALL_TYPES,
        "label": "Pose and action",
        "detail": "Posture, movement, body orientation and action.",
        "must": "Pose and action: the main subject's posture, body orientation and what they do, including what "
        "they hold. Example: 'kneels with one hand on the ground', 'leans against a railing, holding a cup'.",
        "never": "Pose and action: nothing about the main subject's posture, body orientation or action. Never "
        "stands, sits, walks, leans, poses, faces, turns, arms or hands in a position, holds, carries or a tilted "
        "head.",
        "by_type": {
            "object": {
                "label": "Placement and orientation",
                "detail": "Where the object is, what it rests on and which side faces the camera.",
                "must": "Placement and orientation: where the main object is, what it rests on or hangs from, and "
                "which side faces the camera and how it is tilted. Example: 'hangs from a hook, handle to the "
                "right'.",
                "never": "Placement and orientation: nothing about where the main object is, what it rests on or "
                "hangs from, or how it is turned or tilted.",
            },
            "style": {
                "detail": "What the people and animals are doing and how they are posed.",
                "must": "Pose and action: what the depicted people and animals do and how they are posed. Example: "
                "'a man rowing a boat', 'a horse grazing'.",
                "never": "Pose and action: nothing about what the depicted people and animals do or how they are "
                "posed. Never walking, standing, sitting, running, flying, holding or carrying.",
            },
        },
    },
    {
        "id": "interaction",
        "types": ("object",),
        "label": "Use and interaction",
        "detail": "Who holds, wears or uses the object and how; hands and people described generically.",
        "must": "Use and interaction: who holds, wears or uses the main object and how, with hands and people "
        "described generically. Example: 'a hand grips its handle'.",
        "never": "Use and interaction: no hands or people touching, holding, wearing or using the main object.",
    },
    {
        "id": "expression",
        "types": PEOPLE,
        "label": "Facial expression",
        "detail": "Visible expression and gaze, without guessing emotions.",
        "must": "Expression and gaze: the main person's visible facial expression and where they look, without "
        "guessing emotions. Example: 'laughs with eyes closed', 'frowns, looking down to the left'.",
        "never": "Expression and gaze: nothing about the main person's facial expression or gaze. Never smiles, "
        "smiling, laughs, frowns, a neutral or serious expression, an open mouth, closed eyes, looks, looking, "
        "gazes or glances.",
    },
    {
        "id": "background",
        "types": ALL_TYPES,
        "label": "Environment and background",
        "detail": "Location, scenery, props and secondary subjects.",
        "must": "Environment and background: where the main subject is and what is around it: the place, ground, "
        "surroundings, props and other people or animals. Example: 'a sandy beach with palm trees and other "
        "swimmers'.",
        "never": "Environment and background: nothing about where the main subject is or what is around it. No "
        "place, room, street, landscape, ground, floor, wall, sky, plants, buildings, furniture, props, other "
        "people or animals, and never outdoors, indoors, studio, scene, backdrop or background, not even a "
        "blurred background.",
        "by_type": {
            "object": {
                "detail": "Location, surface, background and other objects around it.",
                "must": "Environment: the surroundings of the main object: the surface it is on, the location, the "
                "background and other objects. Example: 'on a wooden shelf beside a stack of books'.",
                "never": "Environment: nothing around the main object. No surface, table, floor, location, "
                "background or backdrop color, other objects, people or animals, and never outdoors, indoors, "
                "studio, scene or background.",
            }
        },
    },
    {
        "id": "lighting",
        "types": ALL_TYPES,
        "label": "Lighting",
        "detail": "Light direction and quality, shadows and light color.",
        "must": "Lighting: the light as it is in this image: its source or time of day (such as daylight, "
        "overcast sky, sunset, night, lamp), direction (front, side, back), softness (soft, hard), color (warm, "
        "cool, neutral) and shadows.",
        "never": "Lighting: nothing about light or shadow. No daylight, sunlight, sunset, night, lamps, "
        "streetlights, glow, reflections of light, shadows, bright, dim, soft, warm or cold light, backlit, lit or "
        "illuminated.",
        "by_type": {
            "style": {
                "label": "Light situation",
                "detail": "Time of day, weather and visible light sources; how light is rendered belongs to the style.",
                "must": "Light situation: the time of day, the weather and visible light sources, not the way light "
                "and shadow are rendered. Example: 'at noon under a clear sky', 'early morning fog'.",
                "never": "Light situation: nothing about the time of day, weather or light sources. No day, night, "
                "dawn, dusk, sunset, sun, moon, rain, snow, fog, lanterns or fireworks.",
            }
        },
    },
    {
        "id": "composition",
        "types": ALL_TYPES,
        "label": "Composition and camera",
        "detail": "Framing, camera angle, subject placement and depth of field.",
        "must": "Composition and camera: the framing and camera as they are in this image: shot size (such as "
        "close-up, medium shot, full-body shot), camera angle (eye level, low angle, high angle), where the main "
        "subject is in the frame (centered, left, right) and focus (sharp throughout or shallow depth of "
        "field).",
        "never": "Composition and camera: nothing about framing, camera or focus. No close-up, medium shot, "
        "full-body shot, portrait framing, eye level, low or high angle, centered, in or out of focus, blurred, "
        "bokeh or depth of field.",
    },
    {
        "id": "style",
        "types": ALL_TYPES,
        "label": "Visual style",
        "detail": "Medium, drawing or photography, rendering technique and overall palette.",
        "must": "Visual style: the medium of the image (such as color photograph, black-and-white photograph, "
        "illustration, painting, 3D render) and its overall color palette.",
        "never": "Visual style: nothing about the medium or look of the image. Never photograph, photo, "
        "photographic, black-and-white, monochrome, illustration, painting, render, cinematic, vintage, film "
        "grain or the image's overall color palette.",
        "by_type": {
            "object": {
                "label": "Medium",
                "detail": "Photograph, 3D render or illustration.",
                "must": "Medium: whether the image is a photograph, 3D render, illustration or painting.",
                "never": "Medium: never whether the image is a photograph, render, illustration or painting. No "
                "photo, photographic, rendered, 3D, CGI, illustrated or painted.",
            },
            "style": {
                "label": "Medium and technique",
                "detail": "Medium, brushwork, line work, texture and how light and shadow are rendered.",
                "must": "Medium and technique: the medium and how the image is made: brushwork, line work, shading, "
                "texture, grain and the way light and shadow are rendered. Example: 'a watercolor painting with soft "
                "washes and visible paper texture'.",
                "never": "Medium and technique: never name or describe the medium or technique. No painting, "
                "painted, illustration, drawing, sketch, print, woodblock, engraving, render, 3D, CGI, anime, "
                "cartoon, photo, photograph, cinematic, film still, stylized, brushwork, line work, outlines, "
                "shading, texture, grain or gradation.",
            },
        },
    },
    {
        "id": "palette",
        "types": ("style",),
        "label": "Color palette and grading",
        "detail": "The overall color scheme and grading; colors of single things stay described.",
        "must": "Color palette and grading: the overall color scheme and grading of the image. Example: 'warm "
        "ochres and browns with green accents'.",
        "never": "Color palette and grading: nothing about the image's overall colors. No palette, color scheme, "
        "grading, tones, muted, vibrant, pastel, monochrome, warm or cool colors; the colors of single things may "
        "still be named.",
    },
    # Only for video clips ("media": "clip"); photos never get these instructions.
    {
        "id": "motion",
        "types": ALL_TYPES,
        "label": "Motion over time",
        "detail": "What the main subject does from the start to the end of the clip.",
        "must": "Motion: what the main subject does from the start to the end of the clip, in time order.",
        "never": "Motion: nothing about how the main subject moves or what it does over the clip.",
        "media": "clip",
        "by_type": {
            "object": {
                "detail": "How the object moves or is handled from the start to the end of the clip.",
                "must": "Motion: how the main object moves or is handled from the start to the end of the clip, in "
                "time order.",
                "never": "Motion: nothing about how the main object moves or is handled over the clip.",
            }
        },
    },
    {
        "id": "camera_motion",
        "types": ALL_TYPES,
        "label": "Camera movement",
        "detail": "Pans, pushes, tracking and other camera moves.",
        "must": "Camera movement: how the camera moves over the clip, with its type, amplitude and speed, or that "
        "it does not move. Example: 'the camera slowly pushes in'.",
        "never": "Camera movement: nothing about camera movement. No pan, tilt, push, pull, zoom, tracking, "
        "handheld or static camera.",
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


def _combinations(ids: set[str], omitted: set[str]) -> list[str]:
    """Rules for details that touch each other; live, these leaked most (2026-09-29)."""
    on, off = ids - omitted, ids & omitted
    lines = []
    if {"hair_color", "hairstyle"} <= off:
        lines.append("Do not mention the main person's hair, beard or moustache at all.")
    elif "hair_color" in on and "hairstyle" in off:
        lines.append(
            "Write the main person's hair only as its color, such as 'auburn hair', with no word about its length, "
            "texture or how it is worn."
        )
    elif "hairstyle" in on and "hair_color" in off:
        lines.append(
            "Describe the main person's hairstyle without any color word: 'a shoulder-length braid', never 'a dark "
            "braid' or 'long auburn hair'."
        )
    if "background" in off:
        if "lighting" in on:
            lines.append("Describe only the light as it falls on the main subject, not what it lights around it.")
        if "composition" in on:
            lines.append(
                "Describe only the framing and the camera angle; say nothing about the background, not even that it "
                "is blurred."
            )
    elif "background" in on:
        if "composition" in off:
            lines.append("Describe the surroundings as they are, without saying they are blurred or out of focus.")
        if "lighting" in off:
            lines.append("Describe the surroundings without their light: no lamps, streetlights, glow or reflections.")
    return lines


def policy_prompt(settings, media: str = "image", only: tuple[str, ...] | None = None):
    """The caption rules: what the caption must describe and what it must never describe.

    Clip-only details appear for clips, and `only` limits the rules to some details.
    """
    omitted = set(settings.omitted_attributes)
    details = _policy_details(settings, media, only)
    must = [a["must"] for a in details if a["id"] not in omitted]
    never = [a["never"] for a in details if a["id"] in omitted]
    lines = ["CAPTION RULES. They decide what the caption contains and override every other instruction."]
    if must:
        # Reported 2026-09-28: a character's clothing was missing. The length target must not drop a detail.
        lines.append(
            "MUST DESCRIBE, when visible, without inventing what is not visible. Give each at least a few words, "
            "also in a short caption; shorten other wording rather than leave one out:"
        )
        lines += ["- " + text for text in must]
    if never:
        lines.append("NEVER DESCRIBE, in no sentence, not in passing and not through synonyms:")
        lines += ["- " + text for text in never]
    lines += _combinations({a["id"] for a in details}, omitted)
    if never:
        lines.append(
            "Before answering, check every sentence against the NEVER DESCRIBE list and delete whatever it forbids."
        )
    lines += [
        "The listed words are English examples; the rules hold for any wording and language.",
        "Do not write about these rules, the settings or training into the caption.",
    ]
    return "\n".join(lines)
