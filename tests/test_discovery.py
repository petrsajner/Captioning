import asyncio
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from captioning.api import make_app
from captioning.discovery import discover
from captioning.models import MANAGED_URL, Settings
from captioning.provider import generate
from captioning.service import Studio


def mocked_client(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))


def test_discovery_validates_protocol_and_never_follows_redirects(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.host == "127.0.0.1"
        assert request.method == "GET" and request.url.path == "/v1/models"
        if request.url.port == 1234:
            return httpx.Response(200, json={"data": [{"id":"vision-model"}, {"id":"text-model"}]})
        if request.url.port == 8888:
            return httpx.Response(401)
        if request.url.port == 8080:
            return httpx.Response(302, headers={"location":"https://external.example/models"})
        if request.url.port == 8000:
            return httpx.Response(200, json={"data":"not a model list"})
        raise httpx.ConnectError("offline", request=request)
    mocked_client(monkeypatch, handler)
    result = asyncio.run(discover())
    assert result["checked"] == len(seen) == 6
    assert len(result["servers"]) == 2
    assert result["servers"][0]["models"] == ["text-model", "vision-model"]
    assert result["servers"][1]["status"] == "requires_key"


def test_discovery_keeps_credentials_on_their_exact_endpoint(monkeypatch):
    custom = "http://127.0.0.1:9911/custom/v1"
    def handler(request):
        is_custom = request.url.port == 9911
        assert request.headers.get("authorization") == ("Bearer local-test-secret" if is_custom else None)
        if is_custom:
            assert request.url.path == "/custom/v1/models"
            return httpx.Response(200, json={"data":[{"id":"custom-vision"}]})
        return httpx.Response(404)
    mocked_client(monkeypatch, handler)
    result = asyncio.run(discover(custom, {custom:"local-test-secret"}))
    assert result["checked"] == 7
    assert result["servers"][0]["url"] == custom
    assert "local-test-secret" not in json.dumps(result)
    with pytest.raises(ValueError):
        asyncio.run(discover("https://external.example/v1"))


def test_settings_migrate_existing_external_connection_and_keep_managed_route():
    external = Settings(local_url="http://127.0.0.1:1234/v1", local_model="existing")
    assert external.local_source == "external" and external.local_model_id == "existing"
    managed = external.model_copy(update={"local_source":"managed"})
    assert managed.local_endpoint == MANAGED_URL and managed.local_model_id == "caption-qwen"
    assert managed.local_url == external.local_url  # saved external preference is retained


def test_external_generation_uses_selected_model_and_standard_payload(tmp_path, monkeypatch):
    path = tmp_path / "image.png"
    Image.new("RGB", (32, 32), "blue").save(path)
    def handler(request):
        assert request.url.port == 1234
        assert request.headers["authorization"] == "Bearer local-test-secret"
        body = json.loads(request.content)
        assert body["model"] == "other-vision"
        assert "chat_template_kwargs" not in body
        assert body["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        return httpx.Response(200, json={"choices":[{"finish_reason":"stop", "message":{"content":"A blue square."}}]})
    mocked_client(monkeypatch, handler)
    settings = Settings(local_source="external", local_url="http://127.0.0.1:1234/v1", local_model="other-vision")
    assert asyncio.run(generate(path, settings, "local-test-secret")) == "A blue square."


def test_local_keys_preserve_cloud_configuration_and_are_not_exposed(tmp_path):
    studio = Studio(tmp_path)
    cloud = Settings(mode="cloud", cloud_model="user-tested-model", cloud_url="https://openrouter.ai/api/v1")
    studio.save_settings(cloud, api_key="cloud-test-secret")
    local = cloud.model_copy(update={"mode":"local", "local_source":"external", "local_url":"http://127.0.0.1:8888/v1"})
    studio.save_settings(local, local_api_key="local-test-secret")
    assert studio.keys.get(cloud.cloud_url) == "cloud-test-secret"
    assert studio.local_key(local) == "local-test-secret"
    assert studio.local_key(local.model_copy(update={"local_url":"http://127.0.0.1:1234/v1"})) == ""
    assert studio.settings.cloud_model == "user-tested-model"
    assert "test-secret" not in json.dumps(studio.snapshot())
    assert "test-secret" not in (tmp_path / "settings.json").read_text()
    studio.save_settings(local, clear_local_key=True)
    assert studio.local_key(local) == ""
    assert studio.keys.get(cloud.cloud_url) == "cloud-test-secret"


def test_discovery_api_requires_session_and_does_not_change_settings(tmp_path, monkeypatch):
    studio = Studio(tmp_path)
    before = studio.settings.model_dump()
    mocked_client(monkeypatch, lambda request: httpx.Response(200, json={"data":[]}))
    app = make_app(studio, "test-token", 8887, Path(__file__).parents[1] / "ui")
    with TestClient(app, base_url="http://127.0.0.1:8887") as client:
        headers = {"x-caption-client":"1"}
        assert client.post("/api/local-servers", json={}, headers=headers).status_code == 403
        client.get("/?token=test-token")
        response = client.post("/api/local-servers", json={}, headers=headers)
        assert response.status_code == 200 and response.json()["checked"] == 6
        assert studio.settings.model_dump() == before
        assert not (tmp_path / "settings.json").exists()
        assert client.post("/api/local-servers", json={"url":"http://192.168.1.2/v1"}, headers=headers).status_code == 400
