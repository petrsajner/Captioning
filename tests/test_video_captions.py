"""WAN 2.2, LTX-2.5 and MiniMax H3 caption outputs, and the coexisting caption files per image."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from captioning.anchor import FINISH_NOTICES
from captioning.errors import ProviderUnavailableError, UserError
from captioning.i18n import catalog
from captioning.models import OUTPUT_SUFFIX, Settings, make_prompt
from captioning.provider import CaptionResult, generate, revision_instruction
from captioning.service import Studio
from captioning.video import H3_ERROR, finish_video_caption, h3_body, validate_h3

H3_PHOTO = (
    "integrated_multimodal_description: [Shot 1] Live-action, photographic, a medium close-up at eye level frames "
    "Velmira, a woman, seated at a café table. The camera holds a static shot.\n\n"
    "overall_soundscape: N/A\n\nnon_diegetic_music: N/A"
)


def finish(draft, output, trigger="Velmira", cls="a woman", media="image"):
    s = Settings(output_format=output, preset="character", trigger=trigger, subject_class=cls)
    return finish_video_caption(draft, s, media)


def picture(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "red").save(path)
    return path


@pytest.mark.parametrize("output", ["wan", "ltx", "h3"])
def test_video_prompts_are_english_descriptions_with_the_character_token(output):
    s = Settings(
        output_format=output,
        language="Czech",
        format="tags",
        preset="character",
        trigger="Velmira",
        subject_class="a woman",
        omitted_attributes=["identity"],
    )
    prompt = make_prompt(s)
    assert "Write in English" in prompt and "Czech" not in prompt
    assert "comma-separated" not in prompt and "Velmira" not in prompt
    assert "<character>" in prompt and "'a woman'" in prompt and "'the woman'" in prompt
    assert "not even in passing" in prompt and "hair" not in prompt.split("MANDATORY CAPTION POLICY")[0]
    assert "do not describe motion over time or camera movement" in prompt
    assert "LEARN_WITH_LORA — DO NOT DESCRIBE: stable visual identity" in prompt
    assert ("The camera holds a static shot." in prompt) == (output == "h3")
    assert ("Begin with the shot" in prompt) == (output == "ltx")
    assert ("Begin the caption with <character>" in prompt) == (output == "wan")
    assert {"wan": "WAN 2.2", "ltx": "LTX-2.5", "h3": "MiniMax H3"}[output] in prompt
    all_models = make_prompt(s.model_copy(update={"output_format": "video_all"}))
    assert all_models == make_prompt(s.model_copy(update={"output_format": "wan"}))


@pytest.mark.parametrize(
    "output, draft, expected",
    [
        (
            "wan",
            "<character> sits at a café table. She smiles.",
            "Velmira, a woman, sits at a café table. She smiles.",
        ),
        (
            "wan",
            "<character>, a woman, sits by the window.",
            "Velmira, a woman, sits by the window.",
        ),
        (
            "ltx",
            "A medium close-up at eye level. <character> sits at a café table.",
            "A medium close-up at eye level. Velmira, a woman, sits at a café table.",
        ),
        (
            "wan",
            "<character> waves. Later <character> smiles.",
            "Velmira, a woman, waves. Later the woman smiles.",
        ),
    ],
)
def test_the_character_token_becomes_the_trigger_and_class_once(output, draft, expected):
    text, notices, review = finish(draft, output)
    assert text == expected and not review
    assert text.count("Velmira") == 1


def test_later_mentions_and_a_missing_token_read_naturally():
    text, notices, _ = finish("<character> smiles. <character> wears a grey coat.", "wan")
    assert text == "Velmira, a woman, smiles. The woman wears a grey coat."
    # The model wrote the class instead of the token: the name goes to its first mention.
    draft = "Live-action, photographic, a medium close-up frames a woman seated by a window."
    text, notices, review = finish(draft, "h3", "Velmira")
    assert not review and notices == ["The name was placed at the first mention of its type."]
    assert h3_body(text).startswith("Live-action, photographic, a medium close-up frames Velmira, a woman, seated")
    text, _, _ = finish("A woman sits by a window.", "ltx", "Velmira")
    assert text == "Velmira, a woman, sits by a window."
    # Seen with Qwen3.8 27B: an article before the token, and the class said again after it.
    text, _, _ = finish("A close-up frames a <character>.", "ltx", "Velmira")
    assert text == "A close-up frames Velmira, a woman."
    text, _, _ = finish("<character> is a woman with long hair.", "wan", "Velmira")
    assert text == "Velmira, a woman, has long hair."
    text, _, _ = finish("A close-up frames <character> as a woman with a ponytail.", "ltx", "Velmira")
    assert text == "A close-up frames Velmira, a woman, with a ponytail."


def test_without_a_trigger_the_class_opens_the_caption():
    text, notices, _ = finish("<character> sits at a table.", "wan", "")
    assert text == "A woman sits at a table." and notices == []
    text, notices, _ = finish("She sits at a table.", "wan")
    assert text == "Velmira, a woman, she sits at a table." and notices == ["The name was added at the start."]
    # Without a trigger there is no name to add, and H3 needs no manual step.
    text, notices, review = finish("Live-action, someone sits.", "h3", "")
    assert h3_body(text).startswith("Live-action, someone sits.") and notices == [] and not review


def test_h3_body_is_wrapped_in_the_official_fields_with_a_static_shot():
    draft = "integrated_multimodal_description: [Shot 1] Live-action, photographic, a medium close-up at eye level frames <character> seated at a café table."
    text, notices, review = finish(draft, "h3")
    assert text == H3_PHOTO and notices == [] and not review
    validate_h3(text)
    assert h3_body(text).startswith("Live-action") and "overall_soundscape" not in h3_body(text)
    # The character must be inside [Shot 1]; H3 never gets a name glued in front of its field label.
    text, notices, review = finish("Live-action, someone sits.", "h3")
    assert review and notices == ["Put the name into [Shot 1] manually."]
    assert text.startswith("integrated_multimodal_description: [Shot 1] Live-action")


@pytest.mark.parametrize(
    "text",
    [
        "A woman sits.",
        "integrated_multimodal_description: A woman sits.\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A",
        "integrated_multimodal_description: [Shot 1] A woman sits.\n\noverall_soundscape: N/A",
    ],
)
def test_h3_validation_rejects_captions_without_the_three_fields(text):
    with pytest.raises(UserError, match="three fields"):
        validate_h3(text)


def test_trigger_warnings_follow_trainer_substring_matching():
    _, notices, _ = finish("<character> asks for tea.", "wan", "sks", "a man")
    assert "The trigger is part of another word here; trainers may miss it. Choose a more distinct name." in notices
    _, notices, _ = finish("<character> stands.", "wan", "ohwx person", "a man")
    assert "The trigger contains a space; a single invented word works best." in notices


def test_every_finishing_notice_has_a_czech_translation():
    messages = catalog("cs")["messages"]
    assert [notice for notice in (*FINISH_NOTICES, H3_ERROR) if notice not in messages] == []


def test_generation_finishes_video_captions_and_revises_the_model_text(tmp_path, monkeypatch):
    image = picture(tmp_path / "a.png")
    long_draft = "<character> sits at a café table. " + "She looks out of the window at the rain. " * 12
    replies = [long_draft, "<character> sits at a café table and looks out at the rain."]
    requests = []
    real = httpx.AsyncClient

    def handler(request):
        requests.append(json.loads(request.content))
        content = replies[len(requests) - 1]
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": content}}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    s = Settings(
        mode="cloud",
        cloud_model="m",
        output_format="wan",
        preset="character",
        trigger="Velmira",
        subject_class="a woman",
        words=20,
    )
    result = asyncio.run(generate(image, s, "not-a-real-key"))
    assert result.text == "Velmira, a woman, sits at a café table and looks out at the rain."
    revision = requests[1]["messages"][0]["content"]
    assert "Keep the token <character> exactly once" in revision and "Velmira" not in revision
    assert "Write in English." in revision
    assert result.history[0]["text"].startswith("Velmira, a woman, sits")


def test_revision_instructions_keep_the_token_and_never_see_the_trigger():
    # The draft has no trigger yet; the application adds it to the finished caption.
    s = Settings(trigger="ohwx", language="Czech")
    text = revision_instruction(s, "draft", too_long=True)
    assert "Write in Czech." in text and "ohwx" not in text and "<character>" not in text
    text = revision_instruction(s.model_copy(update={"preset": "character"}), "draft", too_long=True)
    assert "Keep the token <character> exactly once" in text and "ohwx" not in text


def test_all_video_models_write_their_own_files_and_leave_the_others(tmp_path, monkeypatch):
    async def run():
        image = picture(tmp_path / "images" / "a.png")
        image.with_suffix(".txt").write_text("keep", encoding="utf-8")
        image.with_suffix(".ltx.txt").write_text("existing LTX", encoding="utf-8")
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(image)], "", False, False)
        studio.settings.output_format = "video_all"
        seen = []

        async def fake(path, settings, key, **kwargs):
            seen.append(settings.output_format)
            if settings.output_format == "h3":
                return CaptionResult(H3_PHOTO)
            return CaptionResult(f"Velmira, a woman, stands. ({settings.output_format})")

        monkeypatch.setattr("captioning.provider.generate", fake)
        row = studio.rows[0]
        await studio.start_job([row["id"]])
        await studio.task
        assert seen == ["wan", "h3"]  # the existing LTX file is skipped
        assert studio.job["total"] == 3 and studio.job["skipped"] == 1 and studio.job["saved"] == 2
        assert image.with_suffix(".wan.txt").read_text(encoding="utf-8") == "Velmira, a woman, stands. (wan)\n"
        assert image.with_suffix(".h3.txt").read_text(encoding="utf-8") == H3_PHOTO + "\n"
        assert image.with_suffix(".ltx.txt").read_text(encoding="utf-8") == "existing LTX"
        assert image.with_suffix(".txt").read_text(encoding="utf-8") == "keep"
        assert not image.with_suffix(".json").exists()
        statuses = {output: slot["status"] for output, slot in row["outputs"].items()}
        assert statuses == {
            "normal": "existing",
            "bria_json": "pending",
            "wan": "saved",
            "ltx": "skipped",
            "h3": "saved",
        }

    asyncio.run(run())


def test_a_paused_batch_continues_only_the_missing_outputs(tmp_path, monkeypatch):
    async def run():
        folder = tmp_path / "images"
        for name in ("a.png", "b.png"):
            picture(folder / name)
        studio = Studio(tmp_path / "app")
        await studio.import_images([], str(folder), False, False)
        studio.settings.output_format = "video_all"
        studio.settings.auto_save = False
        calls = []

        async def flaky(path, settings, key, **kwargs):
            calls.append((path.name, settings.output_format))
            if (path.name, settings.output_format) == ("a.png", "ltx"):
                raise ProviderUnavailableError("Server stopped")
            return CaptionResult(H3_PHOTO if settings.output_format == "h3" else "Velmira, a woman, stands.")

        monkeypatch.setattr("captioning.provider.generate", flaky)
        await studio.start_job([r["id"] for r in studio.rows])
        await studio.task
        assert studio.job["paused"] and calls == [("a.png", "wan"), ("a.png", "ltx")]
        a, b = studio.rows
        assert studio.job["remaining_tasks"] == [
            [a["id"], "ltx"],
            [a["id"], "h3"],
            [b["id"], "wan"],
            [b["id"], "ltx"],
            [b["id"], "h3"],
        ]
        assert studio.job["remaining_ids"] == [a["id"], b["id"]]
        calls.clear()

        async def restored(path, settings, key, **kwargs):
            calls.append((path.name, settings.output_format))
            return CaptionResult(H3_PHOTO if settings.output_format == "h3" else "Velmira, a woman, stands.")

        monkeypatch.setattr("captioning.provider.generate", restored)
        await studio.start_job(studio.job["remaining_ids"], resume=True)
        await studio.task
        # The WAN draft of a.png from the first run is kept, not generated again.
        assert calls == [("a.png", "ltx"), ("a.png", "h3"), ("b.png", "wan"), ("b.png", "ltx"), ("b.png", "h3")]
        assert all(a["outputs"][o]["status"] == "draft" for o in ("wan", "ltx", "h3"))

    asyncio.run(run())


def test_an_external_edit_blocks_only_its_own_caption_file(tmp_path, monkeypatch):
    async def run():
        image = picture(tmp_path / "images" / "a.png")
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(image)], "", False, False)
        row = studio.rows[0]
        image.with_suffix(".wan.txt").write_text("edited elsewhere", encoding="utf-8")
        with pytest.raises(UserError, match="outside the app"):
            studio.save_row(row["id"], "Velmira, a woman, stands.", "wan")
        studio.save_row(row["id"], "A plain caption.")
        studio.save_row(row["id"], H3_PHOTO, "h3")
        assert image.with_suffix(".wan.txt").read_text(encoding="utf-8") == "edited elsewhere"
        assert image.with_suffix(".txt").read_text(encoding="utf-8") == "A plain caption.\n"
        with pytest.raises(UserError, match="three fields"):
            studio.save_row(row["id"], "Velmira, a woman, stands.", "h3")
        assert image.with_suffix(".h3.txt").read_text(encoding="utf-8") == H3_PHOTO + "\n"
        with pytest.raises(UserError, match="Unknown caption output"):
            studio.save_row(row["id"], "x", "wan-i2v")

    asyncio.run(run())


def test_images_that_would_share_a_caption_file_are_blocked(tmp_path):
    folder = tmp_path / "images"
    picture(folder / "a.jpg")
    picture(folder / "a.wan.png")  # its Normal caption would be a.wan.txt, the WAN caption of a.jpg
    picture(folder / "b.png")
    studio = Studio(tmp_path / "app")
    asyncio.run(studio.import_images([], str(folder), False, False))
    blocked = {r["name"]: {s["status"] for s in r["outputs"].values()} for r in studio.rows}
    assert blocked == {"a.jpg": {"invalid"}, "a.wan.png": {"invalid"}, "b.png": {"pending"}}
    error = studio.rows[0]["outputs"]["wan"]["error"]
    assert error == "Two files would share the caption file a.wan.txt. Rename one of them."


def test_invalid_existing_h3_file_is_reported_and_kept(tmp_path):
    image = picture(tmp_path / "images" / "a.png")
    image.with_suffix(".h3.txt").write_text("not the official format", encoding="utf-8")
    studio = Studio(tmp_path / "app")
    asyncio.run(studio.import_images([str(image)], "", False, False))
    slot = studio.rows[0]["outputs"]["h3"]
    assert slot["status"] == "error" and slot["error"] == H3_ERROR and slot["caption"] == "not the official format"


def test_sessions_from_0_1_13_move_their_caption_into_its_output(tmp_path):
    folder = tmp_path / "images"
    normal = picture(folder / "a.png")
    bria = picture(folder / "b.png")
    normal.with_suffix(".wan.txt").write_text("Velmira, a woman, stands.", encoding="utf-8")
    old = [
        {
            "id": "1",
            "path": str(normal),
            "name": "a.png",
            "caption": "An unsaved draft.",
            "status": "draft",
            "caption_format": "normal",
            "fingerprints": {".txt": None, ".json": None},
            "notice": "Both .txt and .json exist. LoRA Studio currently prefers .txt. Saving or regenerating keeps the selected format and backs up the other one.",
            "generation_history": [{"stage": "caption", "text": "An unsaved draft."}],
        },
        {
            "id": "2",
            "path": str(bria),
            "name": "b.png",
            "caption": '{"short_description": "draft"}',
            "status": "review",
            "caption_format": "bria_json",
            "fingerprints": {".txt": None, ".json": None},
        },
    ]
    app = tmp_path / "app"
    app.mkdir()
    (app / "session.json").write_text(json.dumps(old), encoding="utf-8")
    studio = Studio(app)
    first, second = studio.rows
    assert first["outputs"]["normal"]["status"] == "draft" and first["outputs"]["normal"]["notice"] == ""
    assert first["outputs"]["normal"]["generation_history"] == old[0]["generation_history"]
    assert (
        first["outputs"]["wan"]["status"] == "existing"
        and first["outputs"]["wan"]["caption"] == "Velmira, a woman, stands."
    )
    assert second["outputs"]["bria_json"]["status"] == "review" and second["outputs"]["normal"]["status"] == "pending"
    assert set(first["fingerprints"]) == set(OUTPUT_SUFFIX.values())
    assert studio.recovered == []
    saved = json.loads((app / "session.json").read_text(encoding="utf-8"))
    assert all("outputs" in row and "caption" not in row for row in saved)
