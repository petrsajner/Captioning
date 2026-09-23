import asyncio
import json

import httpx
import pytest
from PIL import Image

from captioning.errors import ProviderUnavailableError
from captioning.models import Settings
from captioning.provider import generate
from captioning.quality import CaptionResult, word_count
from captioning.service import Studio


def caption(n):
    return " ".join(["detail"] * (n - 1) + ["visible."])


def responses(monkeypatch, texts, finishes=None):
    requests = []
    real = httpx.AsyncClient

    def handler(request):
        payload = json.loads(request.content)
        assert not {"max_tokens", "max_completion_tokens", "n_predict", "stop"} & payload.keys()
        requests.append(payload)
        index = min(len(requests) - 1, len(texts) - 1)
        text = texts[index]
        if isinstance(text, Exception):
            raise text
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": (finishes or ["stop"] * len(texts))[index], "message": {"content": text}}
                ],
                "usage": {"completion_tokens": 100, "completion_tokens_details": {"reasoning_tokens": 50}},
            },
        )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    return requests


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (32, 32), "blue").save(path)
    return path


@pytest.mark.parametrize("n", [20, 40, 48])
def test_at_or_below_120_percent_is_accepted_without_rewrite(image, monkeypatch, n):
    calls = responses(monkeypatch, [caption(n)])
    result = asyncio.run(generate(image, Settings(words=40, max_tokens=1)))
    assert result == caption(n) and not result.needs_review and len(calls) == 1
    assert "max_tokens" not in Settings(max_tokens=700).model_dump()


def test_over_120_percent_shortens_same_caption_without_image_resend(image, monkeypatch):
    calls = responses(monkeypatch, [caption(49), caption(40)])
    result = asyncio.run(generate(image, Settings(words=40)))
    assert word_count(result) == 40 and len(calls) == 2
    assert caption(49) in calls[1]["messages"][0]["content"]
    assert "data:image" not in json.dumps(calls[1])
    assert result.history[0]["text"] == caption(49)


def test_trigger_is_included_in_word_tolerance_and_not_duplicated(image, monkeypatch):
    calls = responses(monkeypatch, [caption(48), "my subject, " + caption(38)])
    result = asyncio.run(generate(image, Settings(words=40, trigger="my subject")))
    assert len(calls) == 2 and word_count(result) == 40 and result.count("my subject") == 1


def test_failed_or_unhelpful_shortening_preserves_original_complete_text(image, monkeypatch):
    calls = responses(monkeypatch, [caption(60), caption(70), httpx.ReadTimeout("test")])
    result = asyncio.run(generate(image, Settings(words=40)))
    assert result == caption(60) and not result.needs_review and result.notice and len(calls) == 3


def test_full_caption_with_length_finish_is_not_a_false_failure(image, monkeypatch):
    calls = responses(monkeypatch, [caption(35)], ["length"])
    result = asyncio.run(generate(image, Settings(words=40)))
    assert result == caption(35) and not result.needs_review and len(calls) == 1


def test_stop_flag_does_not_hide_a_cut_sentence(image, monkeypatch):
    original = "A person is standing in a room with a"
    calls = responses(monkeypatch, [original, "A person is standing in a room."])
    result = asyncio.run(generate(image, Settings(words=40)))
    assert str(result).endswith("room.") and not result.needs_review and len(calls) == 2
    assert result.history[0]["text"] == original


def test_unrepairable_fragment_is_kept_for_review_not_saved_as_done(image, monkeypatch):
    original = "A person is standing in a room with a"
    calls = responses(monkeypatch, [original])
    result = asyncio.run(generate(image, Settings(words=40)))
    assert result == original and result.needs_review and len(calls) == 3


def test_outage_while_completing_an_unfinished_caption_pauses_instead_of_review(image, monkeypatch):
    calls = responses(monkeypatch, ["A person is standing in a room with a", httpx.ConnectError("offline")])
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(generate(image, Settings(words=40)))
    assert len(calls) == 2


def test_outage_while_repairing_json_pauses_instead_of_review(image, monkeypatch):
    calls = responses(monkeypatch, ['{"short_description":"A blue', httpx.ConnectError("offline")])
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(generate(image, Settings(output_format="bria_json")))
    assert len(calls) == 2


def test_tags_do_not_require_sentence_punctuation(image, monkeypatch):
    calls = responses(monkeypatch, ["blue shirt, long hair, soft light"])
    result = asyncio.run(generate(image, Settings(words=40, format="tags")))
    assert not result.needs_review and len(calls) == 1


def test_nonstandard_finish_and_content_blocks_are_supported(image, monkeypatch):
    calls = responses(monkeypatch, [[{"type": "text", "text": "A blue square."}]], ["end_turn"])
    assert asyncio.run(generate(image, Settings())) == "A blue square." and len(calls) == 1


def test_review_draft_preserves_existing_file_and_is_not_counted_as_failure(tmp_path, monkeypatch):
    async def run():
        path = tmp_path / "a.png"
        Image.new("RGB", (32, 32)).save(path)
        target = path.with_suffix(".txt")
        target.write_text("original", encoding="utf-8")
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(path)], "", False, False)

        async def fake(*args, **kwargs):
            return CaptionResult("Partial answer with a", needs_review=True, notice="Review retained")

        monkeypatch.setattr("captioning.provider.generate", fake)
        await studio.start_job([studio.rows[0]["id"]], regenerate=True)
        await studio.task
        assert studio.rows[0]["status"] == "review" and studio.rows[0]["caption"] == "Partial answer with a"
        assert studio.job["errors"] == 0 and studio.job["review"] == 1 and studio.job["saved"] == 0
        assert target.read_text() == "original"

    asyncio.run(run())


def test_cancel_during_rewrite_retains_received_caption(tmp_path, monkeypatch):
    async def run():
        path = tmp_path / "a.png"
        Image.new("RGB", (32, 32)).save(path)
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(path)], "", False, False)
        waiting = asyncio.Event()

        async def fake(*args, on_progress=None):
            on_progress(
                {
                    "kind": "response",
                    "stage": "caption",
                    "text": caption(60),
                    "complete": True,
                    "word_count": 60,
                    "finish_reason": "stop",
                }
            )
            waiting.set()
            await asyncio.sleep(60)

        monkeypatch.setattr("captioning.provider.generate", fake)
        await studio.start_job([studio.rows[0]["id"]])
        await waiting.wait()
        await studio.cancel_job()
        assert studio.rows[0]["status"] == "draft" and studio.rows[0]["caption"] == caption(60)
        assert not path.with_suffix(".txt").exists()
        log = (studio.root / "logs/generation.jsonl").read_text(encoding="utf-8")
        assert "finish_reason" in log and caption(60) not in log

    asyncio.run(run())


def test_invalid_bria_is_repaired_automatically_without_token_cap(image, monkeypatch):
    valid = {
        "short_description": "A blue square.",
        "objects": [],
        "background_setting": "",
        "lighting": {"conditions": "", "direction": ""},
        "aesthetics": {"composition": "", "color_scheme": "blue", "mood_atmosphere": ""},
        "context": "",
    }
    calls = responses(monkeypatch, ['{"short_description":"A blue', json.dumps(valid)], ["length", "stop"])
    result = asyncio.run(generate(image, Settings(output_format="bria_json")))
    assert json.loads(result)["short_description"] == "A blue square." and not result.needs_review and len(calls) == 2


def test_invalid_bria_that_cannot_be_repaired_is_preserved(image, monkeypatch):
    calls = responses(monkeypatch, ['{"short_description":"A blue'])
    result = asyncio.run(generate(image, Settings(output_format="bria_json")))
    assert result.needs_review and "A blue" in result and len(calls) == 3


def test_recognized_external_llama_uses_non_thinking_without_output_limit(image, monkeypatch):
    real = httpx.AsyncClient

    def handler(request):
        if request.url.path == "/props":
            return httpx.Response(
                200, json={"default_generation_settings": {}, "chat_template": "uses enable_thinking"}
            )
        payload = json.loads(request.content)
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        assert "max_tokens" not in payload
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "A blue square."}}],
                "usage": "optional malformed metadata",
            },
        )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    s = Settings(local_source="external", local_url="http://127.0.0.1:8080/v1", local_model="q5")
    assert asyncio.run(generate(image, s)) == "A blue square."


def test_server_disappearance_pauses_batch_instead_of_failing_all_images(tmp_path, monkeypatch):
    async def run():
        folder = tmp_path / "images"
        folder.mkdir()
        for i in range(3):
            Image.new("RGB", (32, 32)).save(folder / f"{i}.png")
        studio = Studio(tmp_path / "app")
        await studio.import_images([], str(folder), False, False)
        calls = []

        async def fake(path, *args, **kwargs):
            calls.append(path.name)
            if path.name == "0.png":
                return CaptionResult("A complete caption.")
            raise ProviderUnavailableError("Server stopped")

        monkeypatch.setattr("captioning.provider.generate", fake)
        await studio.start_job([r["id"] for r in studio.rows])
        await studio.task
        assert calls == ["0.png", "1.png"]
        assert [r["status"] for r in studio.rows] == ["saved", "pending", "pending"]
        assert studio.job["paused"] and studio.job["errors"] == 0 and studio.job["saved"] == 1
        assert (folder / "0.txt").read_text() == "A complete caption.\n"
        pending = studio.job["remaining_ids"]
        assert pending == [r["id"] for r in studio.rows[1:]]

        async def restored(path, *args, **kwargs):
            calls.append(path.name)
            return CaptionResult("A recovered caption.")

        monkeypatch.setattr("captioning.provider.generate", restored)
        studio.settings.skip_existing = False
        await studio.start_job(pending)
        await studio.task
        assert calls == ["0.png", "1.png", "1.png", "2.png"]
        assert (folder / "0.txt").read_text() == "A complete caption.\n"

    asyncio.run(run())
