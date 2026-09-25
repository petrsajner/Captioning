import asyncio
import json

import httpx
import pytest
from PIL import Image

from captioning.bria import CaptionValidationError, normalize_json, validate_json
from captioning.errors import UserError
from captioning.models import Settings, make_prompt
from captioning.provider import CaptionResult, generate
from captioning.service import Studio
from captioning.training import ATTRIBUTES


def example():
    return {
        "short_description": "A person outdoors.",
        "objects": [
            {
                "description": "person",
                "location": "center",
                "relationship": "standing outdoors",
                "shape_and_color": "distinctive face",
                "clothing": "red coat",
                "pose": "standing",
                "expression": "smiling",
                "appearance_details": "short hair and glasses",
            }
        ],
        "background_setting": "a garden",
        "lighting": {"conditions": "daylight", "direction": "side-lit"},
        "aesthetics": {"composition": "centered", "color_scheme": "green and red", "mood_atmosphere": ""},
        "style_medium": "photograph",
        "context": "",
    }


def test_migrate_old_checkbox_and_explicit_new_policy_wins():
    old = Settings(omit_identity=True, lighting=False, composition=False)
    assert set(old.omitted_attributes) == {"identity", "lighting", "composition"}
    assert not {"omit_identity", "lighting", "composition"} & old.model_dump().keys()
    explicit = Settings(omit_identity=True, omitted_attributes=["clothing"])
    assert explicit.omitted_attributes == ["clothing"]
    renamed = Settings(learn_attributes=["clothing", "hair"])  # saved by 0.1.9 and earlier
    assert renamed.omitted_attributes == ["clothing", "hair_color", "hairstyle"]
    assert "learn_attributes" not in renamed.model_dump()
    # Up to 0.2.0 one "hair" detail covered color and style; omitting it omits both.
    split = Settings(omitted_attributes=["identity", "hair", "hairstyle"])
    assert split.omitted_attributes == ["identity", "hairstyle", "hair_color"]
    assert Settings.recover({"omitted_attributes": ["hair"]}) == (
        Settings(omitted_attributes=["hair_color", "hairstyle"]),
        False,
    )
    recovered, damaged = Settings.recover({"learn_attributes": ["unknown"], "trigger": "kept"})
    assert damaged and recovered.trigger == "kept" and recovered.omitted_attributes == []


def test_policy_covers_each_attribute_without_preset_conflicts():
    s = Settings(preset="character", omitted_attributes=["identity", "clothing"], instructions="Describe all clothes.")
    prompt = make_prompt(s)
    assert prompt.count("LEARN_WITH_LORA — DO NOT DESCRIBE:") == 2
    assert prompt.count("CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE:") == len(ATTRIBUTES) - 2
    assert prompt.index("MANDATORY CAPTION POLICY") > prompt.index("Describe all clothes.")
    assert "CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE: clothing" not in prompt
    # Hair color can belong to the LoRA while the hairstyle stays free for prompts.
    hair = make_prompt(Settings(preset="character", omitted_attributes=["identity", "hair_color"]))
    assert "LEARN_WITH_LORA — DO NOT DESCRIBE: hair color" in hair
    assert "CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE: hairstyle of the main person" in hair


def test_bria_keeps_appearance_details_until_hair_and_accessories_are_all_omitted():
    kept = json.loads(normalize_json(json.dumps(example()), Settings(omitted_attributes=["hair_color", "accessories"])))
    assert kept["objects"][0]["appearance_details"] == "short hair and glasses"
    omitted = Settings(omitted_attributes=["hair_color", "hairstyle", "accessories"])
    assert "appearance_details" not in json.loads(normalize_json(json.dumps(example()), omitted))["objects"][0]


def test_bria_structure_policy_trigger_and_unicode():
    s = Settings(
        output_format="bria_json",
        trigger="\u65e5\u672c",
        omitted_attributes=["identity", "clothing", "lighting", "style"],
    )
    caption = normalize_json("```json\n" + json.dumps(example()) + "\n```", s)
    data = json.loads(caption)
    assert data["short_description"].startswith("\u65e5\u672c, ")
    assert "shape_and_color" not in data["objects"][0] and "clothing" not in data["objects"][0]
    assert data["objects"][0]["pose"] == "standing"
    assert data["background_setting"] == "a garden"
    assert data["lighting"] == {"conditions": "", "direction": ""}
    assert "style_medium" not in data and data["aesthetics"]["color_scheme"] == ""
    validate_json(caption)
    assert normalize_json(caption, s) == caption
    prompt = make_prompt(s)
    assert "Schema:" in prompt and '"short_description"' in prompt
    assert "Target about" not in prompt and "comma-separated visual tags" not in prompt


@pytest.mark.parametrize(
    "value",
    [
        '{"subject":"custom schema"}',
        "[]",
        '{"short_description":"a","short_description":"b"}',
        '{"number":NaN}',
        "plain text",
    ],
)
def test_invalid_bria_never_silently_becomes_text(value):
    with pytest.raises(CaptionValidationError):
        normalize_json(value)


def test_invalid_nested_field_rejected():
    data = example()
    data["objects"][0]["clothing"] = ["red coat"]
    with pytest.raises(CaptionValidationError, match="objects.0.clothing"):
        normalize_json(json.dumps(data))


def test_bria_finetuning_example_optional_scores_are_accepted():
    data = example()
    data["aesthetics"].update(preference_score="very high", aesthetic_score="very high")
    assert json.loads(normalize_json(json.dumps(data)))["aesthetics"]["preference_score"] == "very high"


def test_job_freezes_caption_policy_and_output_format(tmp_path, monkeypatch):
    async def run():
        image = tmp_path / "a.png"
        Image.new("RGB", (32, 32)).save(image)
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(image)], "", False, False)
        studio.settings.output_format = "bria_json"
        studio.settings.omitted_attributes = ["identity"]
        entered, release = asyncio.Event(), asyncio.Event()

        async def fake(path, settings, key, **kwargs):
            entered.set()
            await release.wait()
            assert settings.output_format == "bria_json" and settings.omitted_attributes == ["identity"]
            return CaptionResult(normalize_json(json.dumps(example()), settings))

        monkeypatch.setattr("captioning.provider.generate", fake)
        await studio.start_job([studio.rows[0]["id"]])
        await entered.wait()
        studio.settings.output_format = "normal"
        studio.settings.omitted_attributes.clear()
        release.set()
        await studio.task
        assert image.with_suffix(".json").exists() and not image.with_suffix(".txt").exists()
        assert "shape_and_color" not in json.loads(image.with_suffix(".json").read_text(encoding="utf-8"))["objects"][0]

    asyncio.run(run())


def test_text_and_json_captions_coexist_and_round_trip(tmp_path, monkeypatch):
    async def run():
        path = tmp_path / "dataset" / "image.png"
        path.parent.mkdir()
        Image.new("RGB", (32, 32), "red").save(path)
        original = b"original plain caption\r\n"
        path.with_suffix(".txt").write_bytes(original)
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(path)], "", False, False)
        row = studio.rows[0]
        assert row["outputs"]["normal"]["status"] == "existing" and row["outputs"]["bria_json"]["status"] == "pending"
        studio.settings.output_format = "bria_json"

        async def bria(*_, **kwargs):
            return CaptionResult(normalize_json(json.dumps(example())))

        monkeypatch.setattr("captioning.provider.generate", bria)
        # Skipping looks only at the selected output's file, so the existing .txt does not block BRIA.
        await studio.start_job([row["id"]])
        await studio.task
        assert row["outputs"]["bria_json"]["status"] == "saved"
        assert path.with_suffix(".txt").read_bytes() == original
        validate_json(path.with_suffix(".json").read_text(encoding="utf-8"))
        assert not (path.parent / ".caption-backups").exists()
        await studio.start_job([row["id"]])
        await studio.task
        assert row["outputs"]["bria_json"]["status"] == "skipped"
        previous = path.with_suffix(".json").read_bytes()
        with pytest.raises(CaptionValidationError):
            studio.save_row(row["id"], '{"not":"FIBO"}', "bria_json")
        assert path.with_suffix(".json").read_bytes() == previous
        studio.settings.output_format = "normal"

        async def normal(*_, **kwargs):
            return CaptionResult("New text caption")

        monkeypatch.setattr("captioning.provider.generate", normal)
        await studio.start_job([row["id"]], regenerate=True)
        await studio.task
        assert row["outputs"]["normal"]["status"] == "saved"
        assert path.with_suffix(".txt").read_text() == "New text caption\n"
        assert path.with_suffix(".json").read_bytes() == previous
        assert [p.read_bytes() for p in (path.parent / ".caption-backups").glob("*.bak")] == [original]

    asyncio.run(run())


def test_bria_draft_preserves_txt_until_manual_save_and_detects_external_edit(tmp_path, monkeypatch):
    async def run():
        path = tmp_path / "a.png"
        Image.new("RGB", (32, 32)).save(path)
        path.with_suffix(".txt").write_text("old", encoding="utf-8")
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(path)], "", False, False)
        studio.settings.output_format = "bria_json"
        studio.settings.auto_save = False

        async def fake(*_, **kwargs):
            return CaptionResult(json.dumps(example()))

        monkeypatch.setattr("captioning.provider.generate", fake)
        row = studio.rows[0]
        await studio.start_job([row["id"]], regenerate=True)
        await studio.task
        slot = row["outputs"]["bria_json"]
        assert slot["status"] == "draft" and row["outputs"]["normal"]["caption"] == "old"
        assert path.with_suffix(".txt").read_text() == "old" and not path.with_suffix(".json").exists()
        path.with_suffix(".json").write_text('{"made": "elsewhere"}', encoding="utf-8")
        with pytest.raises(UserError, match="outside the app"):
            studio.save_row(row["id"], slot["caption"], "bria_json")
        assert path.with_suffix(".json").read_text() == '{"made": "elsewhere"}'
        # An edit of the .txt does not block the BRIA file; the two files are independent.
        path.with_suffix(".json").unlink()
        path.with_suffix(".txt").write_text("user edit", encoding="utf-8")
        studio.save_row(row["id"], slot["caption"], "bria_json")
        assert path.with_suffix(".json").exists() and path.with_suffix(".txt").read_text() == "user edit"

    asyncio.run(run())


def test_bria_provider_has_sufficient_budget_and_keeps_cloud_protocol(tmp_path, monkeypatch):
    path = tmp_path / "a.png"
    Image.new("RGB", (32, 32)).save(path)
    real = httpx.AsyncClient

    def handler(request):
        payload = json.loads(request.content)
        assert "max_tokens" not in payload and "max_completion_tokens" not in payload
        assert "response_format" not in payload and "chat_template_kwargs" not in payload
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(example())}}]}
        )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    s = Settings(mode="cloud", cloud_model="test-model", output_format="bria_json", trigger="ohwx")
    caption = asyncio.run(generate(path, s, "not-a-real-key"))
    assert json.loads(caption.text)["short_description"].startswith("ohwx, ")


def test_bad_generated_json_keeps_original_and_exposes_repairable_draft(tmp_path, monkeypatch):
    async def run():
        path = tmp_path / "a.png"
        Image.new("RGB", (32, 32)).save(path)
        path.with_suffix(".txt").write_text("keep this", encoding="utf-8")
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(path)], "", False, False)
        studio.settings.output_format = "bria_json"

        async def bad(*_, **kwargs):
            return CaptionResult('{"subject":"wrong shape"}')

        monkeypatch.setattr("captioning.provider.generate", bad)
        row = studio.rows[0]
        await studio.start_job([row["id"]], regenerate=True)
        await studio.task
        slot = row["outputs"]["bria_json"]
        assert slot["status"] == "error" and "wrong shape" in slot["caption"]
        assert path.with_suffix(".txt").read_text() == "keep this" and not path.with_suffix(".json").exists()

    asyncio.run(run())
