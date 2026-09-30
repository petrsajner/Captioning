"""Model profiles, locked detail switches, reasoning per stage and provider (0.3.0, measured 2026-09-30)."""

import asyncio
import json

import httpx
import pytest
from PIL import Image

from captioning import capabilities
from captioning.api import make_app
from captioning.models import Settings, make_prompt
from captioning.provider import (
    NOT_A_CAPTION,
    CaptionSession,
    clean_caption,
    generate,
    http_error,
    not_a_caption,
    provider_message,
    rewrite_reasoning,
)


def cloud(model, url="https://openrouter.ai/api/v1", **extra):
    return Settings(mode="cloud", cloud_url=url, cloud_model=model, **extra)


@pytest.mark.parametrize(
    "model,expected",
    [
        ("anthropic/claude-opus-5.5", "full"),
        ("openai/gpt-6.1-sol", "full"),
        ("gpt-6.1-sol", "full"),
        ("google/gemini-3.8-flash", "full"),
        ("gemini-3.8-flash", "full"),
        ("qwen/qwen3.8-max-0902", "full"),
        ("x-ai/grok-4.7", "full"),
        ("z-ai/glm-5.3-flashx", "full"),
        ("meta/muse-spark-1.3", "muse"),
        ("z-ai/glm-5v-turbo", "strict"),
        ("xiaomi/mimo-v2.6-pro", "strict"),
        ("deepseek/deepseek-v4.1-flash", "strict"),
        ("some/unknown-vision", "strict"),
    ],
)
def test_cloud_models_get_their_measured_profile(model, expected):
    assert capabilities.profile(cloud(model)) == expected


def test_local_models_reason_and_fall_back_to_strict_without_it():
    assert capabilities.profile(Settings()) == "full"
    assert capabilities.profile(Settings(), reasoning=False) == "strict"


def test_style_content_and_background_stay_described_for_every_model():
    for s in (cloud("anthropic/claude-opus-5.5"), Settings(), cloud("unknown/model")):
        style = cloud(s.cloud_model, preset="style") if s.mode == "cloud" else Settings(preset="style")
        chosen = style.model_copy(update={"omitted_attributes": ["style", "palette", "identity", "background"]})
        assert capabilities.effective(chosen).omitted_attributes == ["style", "palette"]
        # The recipe keeps the choice; only the caption uses the default.
        assert chosen.omitted_attributes == ["style", "palette", "identity", "background"]


def test_locked_detail_returns_to_the_type_default_in_both_directions():
    # Muse: character hair color switched on stays left out (the type default).
    muse = cloud("meta/muse-spark-1.3", preset="character", omitted_attributes=["identity"])
    assert "hair_color" in capabilities.effective(muse).omitted_attributes
    # Unknown model: the palette switched on stays left out, identity switched on too.
    strict = cloud("x/y", preset="character", omitted_attributes=["hair_color"])
    assert set(capabilities.effective(strict).omitted_attributes) == {"hair_color", "identity"}
    # Unknown model: an object's background switched off stays described.
    obj = cloud("x/y", preset="object", omitted_attributes=["identity", "object_text", "background"])
    assert capabilities.effective(obj).omitted_attributes == ["identity", "object_text"]
    # Opus follows every switch of a character.
    opus = cloud("anthropic/claude-opus-5.5", preset="character", omitted_attributes=["hair_color", "accessories"])
    assert capabilities.effective(opus).omitted_attributes == ["hair_color", "accessories"]


def test_recommended_length_follows_the_model_and_the_switched_on_details():
    character = dict(preset="character", omitted_attributes=["identity", "hair_color"])  # 9 photo details on
    assert capabilities.recommended_words(cloud("openai/gpt-6.1-sol", **character)) == 40
    assert capabilities.recommended_words(cloud("anthropic/claude-opus-5.5", **character)) == 40
    # Gemini described a close-up's pose in 7 of 10 captions at 40 words, in 9 at 60.
    assert capabilities.recommended_words(cloud("google/gemini-3.8-flash", **character)) == 60
    assert capabilities.recommended_words(Settings(**character)) == 60
    assert capabilities.recommended_words(cloud("x/y", **character)) == 80
    few = cloud(
        "openai/gpt-6.1-sol",
        preset="character",
        omitted_attributes=[
            "identity",
            "hair_color",
            "hairstyle",
            "clothing",
            "accessories",
            "pose",
            "expression",
            "background",
        ],
    )
    assert capabilities.recommended_words(few) == 20


def test_state_and_prompt_preview_show_what_the_model_gets(tmp_path):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from captioning.service import Studio

    app = make_app(Studio(tmp_path), "test-token", 8888, Path(__file__).parents[1] / "ui")
    with TestClient(app, base_url="http://127.0.0.1:8888") as client:
        client.get("/?token=test-token")
        headers = {"X-Caption-Client": "1"}
        state = client.get("/api/state", headers=headers).json()["capabilities"]
        assert state["profile"] == "full" and state["locked"]["style"].keys() == {"identity", "background"}
        body = Settings(preset="style", omitted_attributes=["style", "palette", "background"]).model_dump()
        prompt = client.post("/api/prompt", json=body, headers=headers).json()["prompt"]
    assert "- Environment and background: where the main subject is" in prompt


@pytest.mark.parametrize(
    "url,field,value",
    [
        ("https://openrouter.ai/api/v1", "reasoning", {"effort": "minimal"}),
        ("https://generativelanguage.googleapis.com/v1beta/openai", "reasoning_effort", "none"),
        ("https://api.openai.com/v1", "reasoning_effort", "low"),
    ],
)
def test_cloud_rewrites_reason_as_little_as_the_provider_accepts(url, field, value):
    session = CaptionSession(None, cloud("m", url=url), url, {}, {"model": "m"}, None)
    assert session.stage_options("caption") == {} and session.stage_options("retry_caption") == {}
    assert session.stage_options("shorten") == {field: value} == session.stage_options("complete")


def test_unknown_provider_gets_no_reasoning_parameter():
    assert rewrite_reasoning("https://example.com/v1") is None
    session = CaptionSession(None, cloud("m", url="https://example.com/v1"), "https://example.com/v1", {}, {}, None)
    assert session.stage_options("shorten") == {}


def test_cloud_shortening_request_carries_the_reasoning_setting(tmp_path, monkeypatch):
    image = tmp_path / "a.png"
    Image.new("RGB", (32, 32), "blue").save(image)
    real, bodies = httpx.AsyncClient, []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        text = " ".join(["blue"] * 150) + "." if len(bodies) == 1 else "A blue square."
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": text}}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    result = asyncio.run(generate(image, cloud("google/gemini-3.8-flash", words=40), "k"))
    assert result.text == "A blue square."
    assert "reasoning" not in bodies[0] and bodies[1]["reasoning"] == {"effort": "minimal"}


def test_reasoning_blocks_are_removed_from_a_caption():
    assert clean_caption("<thinking>check the hands</thinking>A woman stands.") == "A woman stands."
    assert clean_caption("<think>x</think> A cube.") == "A cube."
    assert clean_caption("draft</thinking>A cube.") == "A cube."


def test_text_that_is_not_a_caption_is_kept_for_review():
    assert not_a_caption("i'll condense your draft to about forty words") == NOT_A_CAPTION
    assert not_a_caption("Here is the caption: a cube.") == NOT_A_CAPTION
    assert "<characters>" in not_a_caption("A woman <characters> stands.")
    assert not_a_caption("A woman stands under an umbrella.") == ""
    # The name token of a character is markup only until the application replaces it.
    assert not_a_caption("<character>, a woman, stands.", "Velmira, a woman, stands.") == ""


def test_the_provider_message_is_shown_with_the_key_masked():
    response = httpx.Response(403, json={"error": {"message": "Confirm   your age (18+) for key sk-1"}})
    assert provider_message(response, "sk-1") == "Confirm your age (18+) for key ***"
    google = httpx.Response(400, json=[{"error": {"code": 400, "message": "Thinking level MINIMAL is not supported"}}])
    assert provider_message(google) == "Thinking level MINIMAL is not supported"
    assert str(http_error(402, "Out of credit.")) == "HTTP 402: Insufficient credit. Provider: Out of credit."
    assert provider_message(httpx.Response(500, text="<html>")) == ""


def test_palette_is_a_style_detail_again():
    prompt = make_prompt(Settings(preset="style", omitted_attributes=["style"], omitted_by_type={}))
    assert "- Color palette and grading: one phrase about the overall color palette" in prompt
