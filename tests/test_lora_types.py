"""The LoRA type ("What are you training?") decides how every caption output names what the LoRA learns."""

import json

import pytest

from captioning.anchor import NAMED_TWICE, STYLE_MEDIUM, STYLE_PALETTE, class_caption, finish_caption
from captioning.bria import normalize_json
from captioning.i18n import catalog
from captioning.models import Settings, make_prompt
from captioning.training import TYPE_DEFAULTS
from captioning.video import finish_video_caption, h3_body

TEXT_OUTPUTS = ["normal", "wan", "wan_i2v", "ltx", "h3"]
PROMPT_OUTPUTS = ["normal", "bria_json", "wan", "wan_i2v", "ltx", "h3"]


def settings(preset, output="normal", trigger="Zorvak", cls="", **extra):
    omitted = TYPE_DEFAULTS[preset]
    return Settings(
        preset=preset, output_format=output, trigger=trigger, subject_class=cls, omitted_attributes=omitted, **extra
    )


def finished(draft, s, media="image"):
    if s.output_format == "normal":
        return finish_caption(draft, s)
    return finish_video_caption(draft, s, media)


@pytest.mark.parametrize("output", PROMPT_OUTPUTS)
def test_object_prompts_name_the_object_with_its_own_token(output):
    prompt = make_prompt(settings("object", output, "Zorbo", "a backpack"), "clip" if output == "wan_i2v" else "image")
    assert "<object>" in prompt and "'a backpack'" in prompt and "<character>" not in prompt
    assert "Zorbo" not in prompt and "brand or product name" in prompt
    assert "people who hold, wear or use it" in prompt and "'the backpack'" in prompt
    # Live on Qwen3.8 27B the object's colors and stickers leaked until this was said outright.
    assert "Never describe what the object itself looks like" in prompt
    if output != "wan_i2v":  # the motion-only caption has no identity line
        assert "DO NOT DESCRIBE: the main object's own appearance" in prompt
    if output in ("wan", "ltx", "h3", "wan_i2v"):
        assert "object LoRA" in prompt and "main object's appearance" in prompt


def test_a_forgotten_object_token_takes_the_place_of_the_described_object():
    s = settings("object", "wan", "Zorbo", "a puzzle cube")
    text, notices, _ = finished("A 3x3 puzzle cube sits on a windowsill beside a cat.", s)
    assert text == "Zorbo, a puzzle cube, sits on a windowsill beside a cat."
    assert notices == ["The name was placed at the first mention of its type."]
    # Seen live in H3: the model said the type again after the token.
    text, _, _ = finished("A cat sits behind <object>, the puzzle cube, on a windowsill.", s)
    assert text == "A cat sits behind Zorbo, a puzzle cube, on a windowsill."


@pytest.mark.parametrize("output", PROMPT_OUTPUTS)
def test_style_prompts_describe_only_the_content(output):
    prompt = make_prompt(settings("style", output), "clip" if output == "wan_i2v" else "image")
    assert STYLE_MEDIUM in prompt and STYLE_PALETTE in prompt and "Describe people generically" in prompt
    assert "Do not write a style name" in prompt and "Zorvak" not in prompt
    assert "<character>" not in prompt and "<object>" not in prompt and "main character" not in prompt
    assert "Live-action, photographic" not in prompt  # H3 opens with the composition; the style is learned
    if output == "h3":
        assert "Begin with the initial composition" in prompt


def test_a_style_detail_left_on_is_not_forbidden():
    prompt = make_prompt(Settings(preset="style", output_format="wan", trigger="Zorvak"))
    assert STYLE_MEDIUM not in prompt and STYLE_PALETTE not in prompt
    assert "CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE: medium and technique" in prompt
    # The palette alone can be described while the medium stays learned.
    prompt = make_prompt(Settings(preset="style", omitted_attributes=["style"], omitted_by_type={}))
    assert STYLE_MEDIUM in prompt and STYLE_PALETTE not in prompt
    assert "CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE: the overall color palette" in prompt


POLICY = "MANDATORY CAPTION POLICY"


@pytest.mark.parametrize("output", PROMPT_OUTPUTS)
def test_each_type_gets_only_its_own_details(output):
    media = "clip" if output == "wan_i2v" else "image"
    obj = make_prompt(settings("object", output, "Zorbo", "a backpack"), media).split(POLICY)[1]
    assert "hairstyle" not in obj and "hair color" not in obj and "facial expression" not in obj
    style = make_prompt(settings("style", output), media).split(POLICY)[1]
    assert "hair color" not in style and "hairstyle" not in style and "logos" not in style
    if output != "wan_i2v":  # motion-only captions describe only motion and camera
        assert "how the main object is held, worn or used" in obj and "changeable state" in obj
        assert "placement of the main object" in obj and "the medium of the image" in obj
        assert "the light situation" in style and "what is depicted" in style


def test_a_described_logo_is_no_longer_forbidden():
    s = settings("object", "normal", "Zorbo", "a backpack").model_copy(update={"omitted_attributes": ["identity"]})
    prompt = make_prompt(s)
    assert "brand or product name" not in prompt and "logo, brand marks" not in prompt.split(POLICY)[0]
    assert "CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE: logos, brand marks" in prompt
    assert "its shape, size, parts, material" in prompt  # the object's own look is still learned


def test_each_type_remembers_its_own_choices():
    s = Settings(preset="object", omitted_attributes=["identity", "hair_color"])
    assert s.omitted_attributes == ["identity"]  # hair color is not a detail of an object
    assert s.omitted_by_type == {"object": ["identity"]}
    s = Settings(preset="style", omitted_attributes=["style"], omitted_by_type={"object": ["identity"]})
    assert s.omitted_by_type == {"object": ["identity"], "style": ["style"]}
    # Recipes up to 0.2.2: "Visual style" of a style LoRA also covered the palette.
    old = Settings(**{"preset": "style", "omitted_attributes": ["style"]})
    assert old.omitted_attributes == ["style", "palette"]
    assert Settings(**{"preset": "character", "omitted_attributes": ["style"]}).omitted_attributes == ["style"]


def test_bria_json_keeps_the_palette_apart_for_a_style_lora():
    data = {
        "short_description": "A woman sits.",
        "objects": [
            {"description": "a woman", "location": "center", "relationship": "main", "appearance_details": "a scarf"}
        ],
        "background_setting": "a café",
        "lighting": {"conditions": "daylight", "direction": "left"},
        "aesthetics": {"composition": "centered", "color_scheme": "muted blues", "mood_atmosphere": "calm"},
        "style_medium": "woodblock print",
        "context": "",
    }
    medium_only = Settings(preset="style", omitted_attributes=["style"], omitted_by_type={})
    result = json.loads(normalize_json(json.dumps(data), medium_only))
    assert "style_medium" not in result and result["aesthetics"]["color_scheme"] == "muted blues"
    both = json.loads(normalize_json(json.dumps(data), settings("style")))
    assert both["aesthetics"]["color_scheme"] == ""
    # Other types: "Visual style" still covers the palette.
    character = json.loads(normalize_json(json.dumps(data), Settings(preset="character", omitted_attributes=["style"])))
    assert character["aesthetics"]["color_scheme"] == ""
    obj = json.loads(normalize_json(json.dumps(data), settings("object", "bria_json", "Zorbo", "a backpack")))
    assert "appearance_details" not in obj["objects"][0]


def test_motion_only_captions_forbid_every_learned_detail():
    prompt = make_prompt(settings("character", "wan_i2v", "Velmira", "a woman"), "clip").split(POLICY)[1]
    assert "DO NOT DESCRIBE: hair color" in prompt and "DO NOT DESCRIBE: stable visual identity" in prompt
    assert "clothing of the main subject" not in prompt and "movement and actions" in prompt


@pytest.mark.parametrize("output", PROMPT_OUTPUTS)
def test_general_prompts_have_no_token_and_leave_the_trigger_to_the_app(output):
    prompt = make_prompt(settings("general", output, "ohwx"))
    assert "<character>" not in prompt and "<object>" not in prompt and "ohwx" not in prompt
    assert "the application adds it" in prompt


def test_character_prompts_for_normal_captions_use_the_token_at_the_start():
    s = settings("character", "normal", "Velmira", "a woman")
    prompt = make_prompt(s)
    assert "as the literal token <character>, at the very start of the caption" in prompt
    assert "'the woman'" in prompt and "Velmira" not in prompt
    tags = make_prompt(s.model_copy(update={"format": "tags"}))
    assert "<character>, as the first tag" in tags
    czech = make_prompt(s.model_copy(update={"language": "Czech"}))
    assert "matching Czech pronoun" in czech and "'the woman'" not in czech


@pytest.mark.parametrize(
    "preset, cls, output, draft, expected",
    [
        (
            "character",
            "a woman",
            "normal",
            "<character> sits at a café table.",
            "Velmira, a woman, sits at a café table.",
        ),
        ("character", "a woman", "normal", "<character>, café, sitting", "Velmira, a woman, café, sitting"),
        (
            "object",
            "a backpack",
            "wan",
            "<object> hangs from a hook. A man lifts <object>.",
            "Velmira, a backpack, hangs from a hook. A man lifts the backpack.",
        ),
        (
            "object",
            "",
            "ltx",
            "A close-up frames <object> on a desk.",
            "A close-up frames Velmira, an object, on a desk.",
        ),
        ("style", "", "normal", "A woman sits at a café table.", "Velmira style, a woman sits at a café table."),
        ("style", "", "ltx", "A medium shot frames a woman.", "Velmira style, a medium shot frames a woman."),
        ("general", "", "wan", "A woman sits at a café table.", "Velmira, a woman sits at a café table."),
    ],
)
def test_each_type_puts_the_trigger_in_its_place(preset, cls, output, draft, expected):
    s = settings(preset, output, "Velmira", cls)
    text, notices, review = finished(draft, s)
    assert text == expected and not review and set(notices) <= {NAMED_TWICE}
    assert text.count("Velmira") == 1


def test_style_h3_opens_the_shot_with_the_style_name():
    s = settings("style", "h3")
    text, notices, review = finished("A medium close-up frames a woman at a table.", s)
    assert h3_body(text) == "Zorvak style, a medium close-up frames a woman at a table. The camera holds a static shot."
    assert notices == [] and not review
    # A trigger that already ends in "style" is used as it is, and a space is fine for a style name.
    s = settings("style", "normal", "ink wash style")
    text, notices, _ = finished("A heron stands in a pond.", s)
    assert text == "ink wash style, a heron stands in a pond." and notices == []


@pytest.mark.parametrize("output", TEXT_OUTPUTS)
def test_a_lowercase_trigger_keeps_its_case_at_a_sentence_start(output):
    # Trainers match the trigger case-sensitively; up to 0.2.1 it became "Velmira" here.
    s = settings("character", output, "velmira", "a woman")
    text = finished("<character> sits. A cat sleeps.", s)[0]
    assert "velmira, a woman, sits" in text and "Velmira" not in text


def test_general_trigger_is_not_repeated_when_the_model_already_wrote_it():
    s = settings("general", "normal", "ohwx")
    assert finished("ohwx, a woman sits.", s)[0] == "ohwx, a woman sits."
    assert finished("I stand here.", s)[0] == "ohwx, I stand here."  # "I" and acronyms keep their capitals
    assert finished("LED lights glow.", s)[0] == "ohwx, LED lights glow."


@pytest.mark.parametrize("preset", ["character", "object", "style", "general"])
@pytest.mark.parametrize("output", TEXT_OUTPUTS)
def test_class_caption_equals_the_caption_written_without_a_trigger(preset, output):
    draft = {
        "character": "A medium shot frames <character> at a table. The woman smiles.",
        "object": "<object> rests on a table. A man opens <object>.",
    }.get(preset, "A medium shot frames a woman at a table.")
    cls = {"character": "a woman", "object": "a backpack"}.get(preset, "")
    named = settings(preset, output, "Velmira", cls)
    plain = settings(preset, output, "", cls)
    text = finished(draft, named)[0]
    assert class_caption(text, named) == finished(draft, plain)[0]


def test_bria_json_names_the_subject_in_short_description_only():
    data = {
        "short_description": "<character> sits at a café table.",
        "objects": [{"description": "<character>", "location": "center", "relationship": "main subject"}],
        "background_setting": "a café",
        "lighting": {"conditions": "daylight", "direction": "left"},
        "aesthetics": {"composition": "centered", "color_scheme": "warm", "mood_atmosphere": "calm"},
        "context": "<character> waits for someone.",
    }
    s = settings("character", "bria_json", "Velmira", "a woman")
    result = json.loads(normalize_json(json.dumps(data), s))
    assert result["short_description"] == "Velmira, a woman, sits at a café table."
    assert result["objects"][0]["description"] == "a woman" and result["context"] == "a woman waits for someone."
    style = json.loads(normalize_json(json.dumps({**data, "short_description": "A woman sits."}), settings("style")))
    assert style["short_description"] == "Zorvak style, a woman sits."


def test_old_recipes_move_to_the_class_field_and_drop_the_subject_name():
    s = Settings(**{"character_class": "a woman", "subject": "Velmira", "preset": "character"})
    assert s.subject_class == "a woman" and "subject" not in s.model_dump() and "character_class" not in s.model_dump()
    assert Settings(**{"character_class": "a person"}).subject_class == ""  # the old default
    assert Settings(subject_class="  a   tall  man ").subject_class == "a tall man"


def test_type_specific_detail_names_are_translated():
    from captioning.training import ALL_TYPES, details_for

    messages = catalog("cs")["messages"]
    names = {d[key] for t in ALL_TYPES for d in details_for(t) for key in ("label", "detail")}
    assert [name for name in names if name not in messages] == []
