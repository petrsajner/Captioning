"""The switch offer per model, reasoning per stage and provider (measured 2026-09-30 and 2026-10-01)."""

import asyncio
import json
import re

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
    "model",
    ["", "some/unknown-vision", "moonshotai/kimi-k3"],  # no model chosen yet, never measured
)
def test_a_model_we_have_not_measured_gets_every_switch(model):
    # Petr, 2026-10-01: we recommend, we do not forbid; never "not measured, so not allowed".
    s = cloud(model, preset="character", omitted_attributes=["hair_color", "accessories"])
    assert capabilities.offer(s) == {}
    assert capabilities.effective(s).omitted_attributes == ["hair_color", "accessories"]


@pytest.mark.parametrize(
    "lora_type,detail,followed,level",
    [
        # A character's switches are critical: green above 85 %, orange from 50 %, greyed below.
        ("character", "accessories", 9, None),
        ("character", "accessories", 8, "orange"),
        ("character", "accessories", 5, "orange"),
        ("character", "accessories", 4, "grey"),
        # A style is judged more loosely: green above 70 %, orange from 30 %.
        ("style", "background", 8, None),
        ("style", "background", 7, "orange"),
        ("style", "background", 3, "orange"),
        ("style", "background", 2, "grey"),
    ],
)
def test_the_offer_follows_the_measured_share_per_lora_type(monkeypatch, lora_type, detail, followed, level):
    monkeypatch.setattr(capabilities, "MEASURED", [(re.compile("test-model"), {(lora_type, detail): (followed, 10)})])
    s = cloud("x/test-model", preset=lora_type)
    got = capabilities.offer(s).get(lora_type, {}).get(detail)
    assert (got and got["level"]) == level
    if got:
        assert got == {"level": level, "state": "off", "followed": followed, "captions": 10}


def test_a_greyed_switch_stays_at_the_default_and_an_orange_one_as_chosen(monkeypatch):
    shares = {("character", "hair_color"): (2, 10), ("character", "accessories"): (6, 10)}
    monkeypatch.setattr(capabilities, "MEASURED", [(re.compile("test-model"), shares)])
    s = cloud("x/test-model", preset="character", omitted_attributes=["identity", "accessories"])
    offer = capabilities.offer(s)["character"]
    assert offer["hair_color"]["level"] == "grey" and offer["hair_color"]["state"] == "on"
    assert offer["accessories"]["level"] == "orange" and offer["accessories"]["state"] == "off"
    # Hair color switched on is greyed: left out like the type's default. Accessories stay off as chosen.
    assert capabilities.effective(s).omitted_attributes == ["identity", "accessories", "hair_color"]
    # The recipe keeps the choice for a model that can follow it.
    assert s.omitted_attributes == ["identity", "accessories"]
    other = cloud("x/other", preset="character", omitted_attributes=["identity", "accessories"])
    assert capabilities.effective(other).omitted_attributes == ["identity", "accessories"]


def test_local_qwen_has_its_own_measurement(monkeypatch):
    monkeypatch.setattr(capabilities, "LOCAL_MEASURED", {("style", "identity"): (1, 10)})
    assert capabilities.offer(Settings())["style"]["identity"]["level"] == "grey"
    assert capabilities.offer(cloud("x/y")) == {}


def test_recommended_length_follows_the_model_and_the_switched_on_details():
    character = dict(preset="character", omitted_attributes=["identity", "hair_color"])  # 9 photo details on
    assert capabilities.recommended_words(cloud("openai/gpt-6.1-sol", **character)) == 40
    assert capabilities.recommended_words(cloud("anthropic/claude-opus-5.5", **character)) == 40
    # Gemini described a close-up's pose in 7 of 10 captions at 40 words, in 9 at 60.
    assert capabilities.recommended_words(cloud("google/gemini-3.8-flash", **character)) == 60
    assert capabilities.recommended_words(Settings(**character)) == 60
    assert capabilities.recommended_words(cloud("x/y", **character)) == 60
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


def test_state_and_prompt_preview_show_what_the_model_gets(tmp_path, monkeypatch):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from captioning.service import Studio

    app = make_app(Studio(tmp_path), "test-token", 8888, Path(__file__).parents[1] / "ui")
    with TestClient(app, base_url="http://127.0.0.1:8888") as client:
        client.get("/?token=test-token")
        headers = {"X-Caption-Client": "1"}
        state = client.get("/api/state", headers=headers).json()
        assert state["capabilities"]["offer"] == capabilities.offer(Settings())
        assert "background" in {a["id"] for a in state["training_details"]["style"]}
        body = cloud("z-ai/glm-5.3-flashx", preset="style", omitted_attributes=["identity", "style"]).model_dump()
        # An orange switch stays as chosen; a greyed one is at the type's default in the preview.
        orange = client.post("/api/prompt", json=body, headers=headers).json()["prompt"]
        monkeypatch.setattr(capabilities, "MEASURED", [(re.compile("flashx"), {("style", "identity"): (1, 10)})])
        grey = client.post("/api/prompt", json=body, headers=headers).json()["prompt"]
    assert "- What is depicted: nothing about the people" in orange
    assert "- What is depicted: the people, animals and things" in grey


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
    glm = "it looks like the caption you want edited wasn't included. Please paste the caption, and I'll rewrite it."
    assert not_a_caption(glm) == NOT_A_CAPTION
    assert not_a_caption("Snow falls on a street; your eye goes to the lantern.") == ""
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


def test_the_model_table_shows_the_offer_of_every_model_it_lists():
    from pathlib import Path

    table = (Path(__file__).parents[1] / "ui" / "models.js").read_text(encoding="utf-8")
    listed = re.findall(r"'https://openrouter\.ai/api/v1': '([^']+)'", table)
    assert set(listed) == set(capabilities.TABLE_MODELS)
    summary = capabilities.summary(cloud("x/y"))
    assert set(summary["table"]) == {*capabilities.TABLE_MODELS, "local"}
    assert summary["table"]["local"] == capabilities.offer(Settings())


def test_the_measured_offer_of_the_table_models():
    # Measured 2026-09-30 and 2026-10-01, blind, the prompt of every test caption verified.
    def offer(model):
        o = capabilities.offer(cloud(model))
        return {(t, d): (v["level"], v["followed"], v["captions"]) for t, ds in o.items() for d, v in ds.items()}

    for model in ("openai/gpt-6.1-sol", "anthropic/claude-opus-5.5", "google/gemini-3.8-flash", "moonshotai/kimi-k3"):
        assert offer(model) == {}
    assert offer("meta/muse-spark-1.3") == {("character", "hair_color"): ("orange", 8, 10)}
    assert offer("z-ai/glm-5v-turbo")[("style", "identity")] == ("grey", 1, 5)
    assert offer("xiaomi/mimo-v2.6-flash")[("style", "identity")] == ("grey", 1, 5)
    assert offer("deepseek/deepseek-v4.1-flash") == {("character", "identity"): ("orange", 4, 5)}
