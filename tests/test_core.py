import asyncio
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from captioning.api import make_app
from captioning.models import Settings, make_prompt
from captioning.provider import clean_caption, generate, image_bytes
from captioning.runtime import Runtime, SetupCancelled, safe_extract
from captioning.service import Studio
from captioning.storage import KeyStore, fingerprint, write_caption
from captioning.folders import FolderBrowser, PAGE_SIZE


def picture(path, color="red"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 60), color).save(path)
    return path


def test_unicode_sidecar_and_backup(tmp_path):
    image = picture(tmp_path / "\u65e5\u672c.01.png")
    digest = write_caption(image, "  Red \u753b image  ", None, False)
    target = image.with_suffix(".txt")
    assert target.read_bytes() == "Red \u753b image\n".encode()
    write_caption(image, "Updated caption", digest, True)
    backups = list((tmp_path / ".caption-backups").glob("*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == "Red \u753b image\n".encode()
    assert not list(tmp_path.glob("*.tmp"))


def test_no_clobber_external_edit_and_empty(tmp_path):
    image = picture(tmp_path / "a.png")
    image.with_suffix(".txt").write_text("Original", encoding="utf-8")
    old = fingerprint(image.with_suffix(".txt"))
    with pytest.raises(FileExistsError):
        write_caption(image, "new", old, False)
    image.with_suffix(".txt").write_text("External edit", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        write_caption(image, "new", old, True)
    with pytest.raises(ValueError, match="empty"):
        write_caption(image, " ", old, True)
    assert image.with_suffix(".txt").read_text() == "External edit"


def test_import_recursion_conflicts_append_corruption(tmp_path):
    data = tmp_path / "images"
    picture(data / "same.png")
    picture(data / "same.jpg")
    picture(data / "deep" / "valid.webp")
    (data / "broken.png").write_bytes(b"broken")
    studio = Studio(tmp_path / "app")
    asyncio.run(studio.import_images([], str(data), False, False))
    assert len(studio.rows) == 3
    assert all(r["status"] == "invalid" for r in studio.rows)
    asyncio.run(studio.import_images([], str(data), True, True))
    assert len(studio.rows) == 4
    assert next(r for r in studio.rows if r["name"] == "valid.webp")["status"] == "pending"
    asyncio.run(studio.import_images([str(data / "same.png")], "", False, False))
    assert studio.rows[0]["status"] == "invalid"  # collision even outside selection


def test_batch_failure_skip_draft_and_resume(tmp_path, monkeypatch):
    async def run():
        folder = tmp_path / "dataset"
        first = picture(folder / "a.png")
        picture(folder / "b.png")
        picture(folder / "c.png")
        first.with_suffix(".txt").write_text("keep", encoding="utf-8")
        studio = Studio(tmp_path / "app")
        await studio.import_images([], str(folder), False, False)
        calls = []
        async def fake(path, settings, key, **kwargs):
            calls.append(path.name)
            if path.name == "b.png":
                raise ValueError("Test model failure")
            return "A red image."
        monkeypatch.setattr("captioning.provider.generate", fake)
        await studio.start_job([r["id"] for r in studio.rows])
        await studio.task
        assert calls == ["b.png", "c.png"]
        assert studio.job["errors"] == 1 and studio.job["saved"] == 1 and studio.job["skipped"] == 1
        assert first.with_suffix(".txt").read_text() == "keep"
        reloaded = Studio(tmp_path / "app")
        assert reloaded.rows[2]["caption"] == "A red image."
        reloaded.settings.auto_save = False
        await reloaded.start_job([reloaded.rows[2]["id"]], regenerate=True)
        await reloaded.task
        assert reloaded.rows[2]["status"] == "draft"
    asyncio.run(run())


@pytest.mark.parametrize("before_first_tick", [True, False])
def test_cancel_does_not_save(tmp_path, monkeypatch, before_first_tick):
    async def run():
        image = picture(tmp_path / "images" / "a.png")
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(image)], "", False, False)
        started = asyncio.Event()
        async def slow(*_, **kwargs):
            started.set()
            await asyncio.sleep(60)
            return "Should not be written"
        monkeypatch.setattr("captioning.provider.generate", slow)
        await studio.start_job([studio.rows[0]["id"]])
        if not before_first_tick:
            await started.wait()
        await studio.cancel_job()
        assert not image.with_suffix(".txt").exists()
        assert not studio.job["running"]
        assert studio.rows[0]["status"] == "pending"
    asyncio.run(run())


def test_payload_and_image_preprocessing(tmp_path, monkeypatch):
    image = tmp_path / "sensitive-path.png"
    Image.new("RGBA", (1800, 900), (0, 0, 255, 128)).save(image)
    real_client = httpx.AsyncClient
    captured = []
    def handler(request):
        data = json.loads(request.content)
        captured.append(data)
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "<think>internal</think>A blue rectangle."}}]})
    monkeypatch.setattr("captioning.provider.httpx.AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    s = Settings(trigger="abc", image_size=1024)
    result = asyncio.run(generate(image, s))
    assert result == "abc, A blue rectangle."
    payload = captured[0]
    assert "sensitive-path" not in json.dumps(payload)
    encoded = payload["messages"][0]["content"][0]["image_url"]["url"].split(",", 1)[1]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as im:
        assert im.size == (1024, 512) and im.mode == "RGB"
    assert payload["chat_template_kwargs"]["enable_thinking"] is False


@pytest.mark.parametrize("finish,content", [("length", "unfinished"), ("content_filter", ""), ("stop", "<think>incomplete")])
def test_incomplete_response_rejected(tmp_path, monkeypatch, finish, content):
    image = picture(tmp_path / "a.png")
    real_client = httpx.AsyncClient
    def handler(_):
        return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": {"content": content}}]})
    monkeypatch.setattr("captioning.provider.httpx.AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    if finish == "length":
        result = asyncio.run(generate(image, Settings()))
        assert result == "unfinished" and result.needs_review
    else:
        with pytest.raises(ValueError):
            asyncio.run(generate(image, Settings()))


def test_prompt_trigger_and_network_boundaries():
    s = Settings(preset="character", subject="ohwx", trigger="ohwx", omit_identity=True, instructions="Describe clothing.")
    prompt = make_prompt(s)
    assert "ohwx" in prompt and "Describe clothing." in prompt and "LEARN_WITH_LORA — DO NOT DESCRIBE: stable visual identity" in prompt
    assert clean_caption("ohwx, woman", "ohwx") == "ohwx, woman"
    assert clean_caption("ohwxish object", "ohwx") == "ohwx, ohwxish object"
    with pytest.raises(ValueError):
        Settings(local_url="https://external.example/v1")
    with pytest.raises(ValueError):
        Settings(cloud_url="http://example.com/v1")
    with pytest.raises(ValueError):
        Settings(cloud_url="https://secret@example.com/v1")


def test_local_api_auth_and_path_registration(tmp_path):
    studio = Studio(tmp_path / "app")
    assets = Path(__file__).parents[1] / "ui"
    app = make_app(studio, "test-token", 8888, assets)
    with TestClient(app, base_url="http://127.0.0.1:8888") as client:
        assert client.get("/api/state").status_code == 403
        assert client.get("/?token=test-token").status_code == 200
        assert client.get("/api/state").status_code == 200
        assert client.get("/api/image/not-registered").status_code == 400
        assert client.post("/api/jobs/stop", json={}).status_code == 403
        assert client.post("/api/jobs/stop", json={}, headers={"x-caption-client": "1", "origin": "https://hostile.example"}).status_code == 403
        assert client.post("/api/jobs/stop", json={}, headers={"x-caption-client": "1"}).status_code == 200
        assert client.get("/api/state", headers={"host": "hostile.example"}).status_code == 403


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI")
def test_key_encrypted_and_bound_to_endpoint(tmp_path):
    keys = KeyStore(tmp_path / "keys.json")
    fake = "unit-test-only-not-a-real-key"
    keys.set("https://provider-a.example/v1", fake)
    assert fake not in keys.path.read_text()
    assert keys.get("https://provider-a.example/v1") == fake
    assert keys.get("https://provider-b.example/v1") == ""
    keys.set("https://provider-a.example/v1", "")
    assert not keys.has("https://provider-a.example/v1")


def test_download_resume_verify_and_cancel(tmp_path, monkeypatch):
    runtime = Runtime(tmp_path)
    destination = tmp_path / "test.bin"
    data = b"a" * (1024 * 1024) + b"b" * (1024 * 1024)
    sha = hashlib.sha256(data).hexdigest()
    destination.with_name("test.bin.part").write_bytes(data[:1024 * 1024])
    real_client = httpx.Client
    def handler(request):
        assert request.headers["range"] == "bytes=1048576-"
        return httpx.Response(206, headers={"Content-Range": "bytes 1048576-2097151/2097152"}, content=data[1024 * 1024:])
    monkeypatch.setattr("captioning.runtime.httpx.Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    runtime.download("https://example.com/test.bin", destination, len(data), sha)
    assert destination.read_bytes() == data
    assert runtime.valid_file(destination, sha, len(data))
    runtime.cancel.set()
    with pytest.raises(SetupCancelled):
        runtime.verify(destination, sha, len(data))


def test_download_bad_hash_and_zip_traversal(tmp_path, monkeypatch):
    runtime = Runtime(tmp_path)
    dest = tmp_path / "broken.bin"
    dest.write_bytes(b"bad")
    with pytest.raises(ValueError, match="Checksum"):
        runtime.verify(dest, "a" * 64, 3)
    assert not dest.exists()
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escaped.txt", "no")
    with pytest.raises(ValueError, match="invalid path"):
        safe_extract(archive, tmp_path / "target")
    assert not (tmp_path / "escaped.txt").exists()


def test_cloud_request_key_and_clean_failure(tmp_path, monkeypatch):
    image = picture(tmp_path / "private-photo.png")
    real_client = httpx.AsyncClient
    def handler(request):
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer fake-test-key"
        assert "chat_template_kwargs" not in payload
        assert payload["model"] == "test/vision"
        return httpx.Response(401, json={"error": "fake-test-key private-photo.png provider internals"})
    monkeypatch.setattr("captioning.provider.httpx.AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(ValueError) as result:
        asyncio.run(generate(image, Settings(mode="cloud", cloud_model="test/vision"), "fake-test-key"))
    assert "401" in str(result.value) and "fake-test-key" not in str(result.value)


def test_external_change_during_inference_keeps_user_caption(tmp_path, monkeypatch):
    async def run():
        image = picture(tmp_path / "images" / "a.png")
        studio = Studio(tmp_path / "app")
        await studio.import_images([str(image)], "", False, False)
        async def fake(*_, **kwargs):
            image.with_suffix(".txt").write_text("External caption", encoding="utf-8")
            return "New generated draft"
        monkeypatch.setattr("captioning.provider.generate", fake)
        await studio.start_job([studio.rows[0]["id"]])
        await studio.task
        assert image.with_suffix(".txt").read_text() == "External caption"
        assert studio.rows[0]["status"] == "error"
        assert studio.rows[0]["caption"] == "New generated draft"
    asyncio.run(run())


def test_folder_browser_shows_images_subfolders_and_pages(tmp_path):
    folder = tmp_path / "selection"
    (folder / "subfolder").mkdir(parents=True)
    for i in range(PAGE_SIZE + 1):
        picture(folder / f"foto-{i:03d}.PNG")
    (folder / "foto-000.txt").write_text("untouched")
    browser = FolderBrowser()
    first = browser.listing(str(folder))
    assert first["image_count"] == PAGE_SIZE + 1
    assert first["folders"] == [{"name": "subfolder", "path": str(folder / "subfolder")}]
    assert len(first["images"]) == PAGE_SIZE and first["pages"] == 2
    assert browser.image(first["images"][0]["id"]) == folder / "foto-000.PNG"
    second = browser.listing(str(folder), 1)
    assert [i["name"] for i in second["images"]] == [f"foto-{PAGE_SIZE:03d}.PNG"]
    empty = browser.listing(str(folder / "subfolder"))
    assert empty["image_count"] == 0 and empty["parent"] == str(folder)
    assert (folder / "foto-000.txt").read_text() == "untouched"
    with pytest.raises(ValueError):
        browser.image("not-registered")


def test_folder_preview_api_does_not_import_until_confirmed(tmp_path):
    image = picture(tmp_path / "dataset" / "red.png")
    studio = Studio(tmp_path / "profile")
    app = make_app(studio, "test-token", 8888, Path(__file__).parents[1] / "ui")
    headers = {"X-Caption-Client": "1"}
    with TestClient(app, base_url="http://127.0.0.1:8888") as client:
        assert client.post("/api/folders", json={"path": str(image.parent)}, headers=headers).status_code == 403
        client.get("/?token=test-token")
        listing = client.post("/api/folders", json={"path": str(image.parent)}, headers=headers).json()
        assert listing["image_count"] == 1 and studio.rows == []
        response = client.get("/api/folder-image/" + listing["images"][0]["id"])
        assert response.headers["content-type"] == "image/jpeg"
        assert Image.open(io.BytesIO(response.content)).size == (80, 60)
        assert client.get("/api/folder-image/unknown").status_code == 400
        assert client.post("/api/pick/folder", json={}, headers=headers).status_code == 400
        assert client.post("/api/import", json={"folder": listing["path"]}, headers=headers).status_code == 200
        assert len(studio.rows) == 1 and not image.with_suffix(".txt").exists()


def test_folder_tree_is_one_level_and_breadcrumbs_reach_root(tmp_path):
    root = tmp_path / "kolekce"
    first = root / "Dataset A" / "Selected"
    first.mkdir(parents=True)
    (root / "Dataset B").mkdir()
    (root / "ignored.png").write_bytes(b"not an image; tree must not decode it")
    browser = FolderBrowser()
    tree = browser.children(str(root))
    assert [f["name"] for f in tree["folders"]] == ["Dataset A", "Dataset B"]
    assert browser.previews == {}
    listing = browser.listing(str(first))
    crumbs = listing["breadcrumbs"]
    assert crumbs[-1]["path"] == str(first)
    assert crumbs[-2]["path"] == str(first.parent)
    assert crumbs[0]["path"] == str(Path(first.anchor))
    assert all(Path(child["path"]).parent == Path(parent["path"]) for parent, child in zip(crumbs, crumbs[1:]))
    assert browser.listing(first.anchor)["parent"] == first.anchor


def test_tree_api_auth_and_invalid_navigation_leave_dataset_intact(tmp_path):
    image = picture(tmp_path / "dataset" / "red.png")
    studio = Studio(tmp_path / "profile")
    asyncio.run(studio.import_images([str(image)], "", False, False))
    previous = json.dumps(studio.rows)
    app = make_app(studio, "test-token", 8888, Path(__file__).parents[1] / "ui")
    headers = {"X-Caption-Client": "1"}
    with TestClient(app, base_url="http://127.0.0.1:8888") as client:
        assert client.post("/api/folder-tree", json={"path": str(tmp_path)}, headers=headers).status_code == 403
        client.get("/?token=test-token")
        assert client.post("/api/folder-tree", json={"path": str(tmp_path)}, headers=headers).status_code == 200
        assert client.post("/api/folders", json={"path": str(tmp_path / 'missing')}, headers=headers).status_code == 400
        assert client.post("/api/folder-tree", json={"path": str(image)}, headers=headers).status_code == 400
    assert json.dumps(studio.rows) == previous
