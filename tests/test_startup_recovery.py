import asyncio
import json
import msvcrt
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app
from captioning.api import make_app
from captioning.errors import UserError
from captioning.models import Settings
from captioning.provider import INVALID_RESPONSE, generate, list_models
from captioning.quality import unfinished
from captioning.runtime import Runtime
from captioning.service import Studio


def damaged(root, name):
    return [p for p in root.iterdir() if p.name.startswith(name + ".damaged-")]


def test_invalid_saved_settings_keep_valid_values_and_the_original(tmp_path):
    saved = {
        "words": 5,
        "cloud_url": "http://insecure.example/v1",
        "trigger": "ohwx",
        "language": "Czech",
        "ui_language": "cs",
    }
    (tmp_path / "settings.json").write_text(json.dumps(saved), encoding="utf-8")
    studio = Studio(tmp_path)
    assert studio.settings.words == 100 and studio.settings.cloud_url == "https://openrouter.ai/api/v1"
    assert (studio.settings.trigger, studio.settings.language, studio.settings.ui_language) == ("ohwx", "Czech", "cs")
    kept = damaged(tmp_path, "settings.json")
    assert [p.name for p in kept] == studio.recovered and json.loads(kept[0].read_text(encoding="utf-8")) == saved
    assert Studio(tmp_path).settings == studio.settings and Studio(tmp_path).recovered == []


@pytest.mark.parametrize("content", ["[]", "{not json", '{"local_url": 5}'])
def test_unusable_settings_fall_back_to_defaults(tmp_path, content):
    (tmp_path / "settings.json").write_text(content, encoding="utf-8")
    studio = Studio(tmp_path)
    assert studio.settings.model_dump() == Settings().model_dump()
    assert len(damaged(tmp_path, "settings.json")) == 1 and len(studio.recovered) == 1


def test_session_rows_this_version_cannot_use_are_dropped_and_kept(tmp_path):
    image = tmp_path / "a.png"
    Image.new("RGB", (8, 8)).save(image)
    good = {
        "id": "1",
        "path": str(image),
        "name": "a.png",
        "caption": "A caption.",
        "status": "processing",
        "fingerprint": "abc",
    }
    rows = [
        good,
        {**good, "id": "2", "status": "archived"},
        {"id": "3", "name": "b.png", "caption": "", "status": "saved"},
        "row",
    ]
    (tmp_path / "session.json").write_text(json.dumps(rows), encoding="utf-8")
    studio = Studio(tmp_path)
    assert [r["id"] for r in studio.rows] == ["1"]
    row = studio.rows[0]
    assert "fingerprint" not in row  # the pre-0.1.5 single hash moved into fingerprints
    assert (
        row["status"] == "pending" and row["exists"] is False and row["fingerprints"] == {".txt": "abc", ".json": None}
    )
    assert json.loads(damaged(tmp_path, "session.json")[0].read_text(encoding="utf-8")) == rows
    assert [r["id"] for r in json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))] == ["1"]
    assert "recovered" in studio.snapshot() and len(studio.recovered) == 1


def test_startup_failure_is_reported_and_releases_the_instance_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPTION_STUDIO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["app.py"])

    def broken(root):
        raise RuntimeError("test failure")

    monkeypatch.setattr("captioning.service.Studio", broken)
    shown = []
    monkeypatch.setattr(
        app, "show_message", lambda text, language, detail="", error=False: shown.append((text, detail, error))
    )
    with pytest.raises(SystemExit) as result:
        app.main()
    assert result.value.code == 1
    assert shown == [
        ("Caption Studio could not start. Details were written to app.log in the data folder.", str(tmp_path), True)
    ]
    with (tmp_path / "instance.lock").open("r+b") as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


@pytest.mark.parametrize("text", ['"', ")", "”", '" '])
def test_only_closing_marks_is_unfinished_not_a_crash(text):
    assert unfinished(text)


class ExitedProcess:
    def poll(self):
        return 3


def test_owned_model_exit_is_reported(tmp_path):
    runtime = Runtime(tmp_path)
    runtime.process = ExitedProcess()
    runtime.state.update(status="running", message="The local model is running.")
    snapshot = runtime.snapshot("q4", "cuda")
    assert snapshot["status"] == "error" and not snapshot["running"]
    assert "exit code 3" in snapshot["message"] and "model.log" in snapshot["message"]


@pytest.mark.parametrize("body", [b"[]", b"not json", b'{"choices":[{"message":"text"}]}'])
def test_non_object_provider_responses_are_invalid_format(tmp_path, monkeypatch, body):
    image = tmp_path / "a.png"
    Image.new("RGB", (8, 8)).save(image)
    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)), **kwargs
        ),
    )
    with pytest.raises(UserError, match=INVALID_RESPONSE):
        asyncio.run(generate(image, Settings()))
    if body != b'{"choices":[{"message":"text"}]}':
        with pytest.raises(UserError, match=INVALID_RESPONSE):
            asyncio.run(list_models(Settings()))


def test_unexpected_api_error_is_json_for_the_ui(tmp_path, monkeypatch):
    studio = Studio(tmp_path)

    def broken():
        raise RuntimeError("test failure")

    monkeypatch.setattr(studio, "snapshot", broken)
    api = make_app(studio, "test-token", 8888, Path(__file__).parents[1] / "ui")
    with TestClient(api, base_url="http://127.0.0.1:8888", raise_server_exceptions=False) as client:
        client.get("/?token=test-token")
        response = client.get("/api/state")
    assert response.status_code == 500
    assert response.json() == {
        "detail": "An unexpected error occurred. If it repeats, check app.log in the data folder."
    }
