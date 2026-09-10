"""Caption conditioning intent; these controls do not mask image training loss."""
from typing import Literal

Attribute = Literal["identity", "hair", "clothing", "accessories", "pose", "expression", "background", "lighting", "composition", "style"]
ATTRIBUTES = [
    {"id":"identity", "label":"Identita / vzhled subjektu", "detail":"Obličej, tělesné rysy; u objektu typický tvar, materiál a barvy.",
     "instruction":"stable visual identity of the MAIN subject: facial structure and distinctive physical features; for an animal its coat markings; for an object its characteristic shape, material and colors"},
    {"id":"hair", "label":"Vlasy a účes", "detail":"Účes, délka a barva vlasů hlavní osoby.", "instruction":"hairstyle, hair length and hair color of the main person"},
    {"id":"clothing", "label":"Oblečení", "detail":"Oděv, jeho střih, barvy a materiál.", "instruction":"clothing of the main subject, garment type, cut, colors and fabric"},
    {"id":"accessories", "label":"Doplňky", "detail":"Šperky, brýle, pokrývky hlavy a další nošené doplňky.", "instruction":"accessories worn by the main subject, jewelry, glasses, hats and wearable accessories"},
    {"id":"pose", "label":"Póza a činnost", "detail":"Postoj, pohyb, natočení těla a prováděná činnost.", "instruction":"pose, body orientation and action of the main subject"},
    {"id":"expression", "label":"Výraz obličeje", "detail":"Viditelný výraz a směr pohledu, bez domýšlení emocí.", "instruction":"visible facial expression and gaze of the main subject, without inferring mental states"},
    {"id":"background", "label":"Prostředí a pozadí", "detail":"Místo, kulisy, vedlejší objekty a další postavy.", "instruction":"environment, background, scene props and secondary subjects"},
    {"id":"lighting", "label":"Osvětlení", "detail":"Směr a charakter světla, stíny a barevnost světla.", "instruction":"lighting conditions, light direction, shadows and light color"},
    {"id":"composition", "label":"Kompozice a kamera", "detail":"Rámování, úhel kamery, umístění subjektu a hloubka ostrosti.", "instruction":"framing, camera viewpoint, subject placement and relative size, depth of field and focus"},
    {"id":"style", "label":"Vizuální styl", "detail":"Médium, kresba či fotografie, způsob zpracování a celková paleta.", "instruction":"visual style, medium, rendering technique and overall artistic color palette"},
]


def training_plan(settings):
    learned = set(settings.learn_attributes)
    return {"learn": [a["label"] for a in ATTRIBUTES if a["id"] in learned],
            "describe": [a["label"] for a in ATTRIBUTES if a["id"] not in learned]}


def policy_prompt(settings):
    learned = set(settings.learn_attributes)
    lines = ["MANDATORY CAPTION POLICY (higher priority than preset and optional hints):",
             "The user is deciding which attributes should be associated with their LoRA concept and which should be described for later prompt control.",
             "For LEARN_WITH_LORA: omit the attribute's visual details from the caption. Keep only a generic subject/category or its provided identifier.",
             "For CONTROL_WITH_PROMPT: explicitly describe the visible attribute so it can be conditioned separately. Do not invent absent or uncertain details."]
    for a in ATTRIBUTES:
        lines.append(("LEARN_WITH_LORA — DO NOT DESCRIBE: " if a["id"] in learned else "CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE: ") + a["instruction"] + ".")
    lines += ["Do not leak omitted attributes through synonyms, the opening sentence, summaries, background, relationships or other fields.",
              "These settings affect captions only. Do not write explanations about learning, the settings or LoRA into the caption."]
    return "\n".join(lines)
