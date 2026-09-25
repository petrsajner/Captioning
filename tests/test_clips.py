"""Video clips: probing, frames for the model, import, batches, payloads and the clip endpoints."""

import asyncio
import json
from pathlib import Path

import av
import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from captioning import provider
from captioning.api import make_app
from captioning.media import frame_times, frames_at, probe, thumbnail
from captioning.models import Settings, make_prompt
from captioning.provider import CaptionResult, generate
from captioning.service import Studio

FIXTURES = Path(__file__).parent / "fixtures"


def clip(path: Path, seconds: float = 2, fps: int = 10, size=(64, 48)) -> Path:
    """A clip whose frame n is filled with gray level 10 * n, so tests can see which frame was taken."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = size[0], size[1], "yuv420p"
        for n in range(round(seconds * fps)):
            frame = av.VideoFrame.from_image(Image.new("RGB", size, (10 * n,) * 3))
            container.mux(stream.encode(frame))
        container.mux(stream.encode(None))
    return path


def picture(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "red").save(path)
    return path


def test_probe_reads_size_rate_length_and_rotation(tmp_path):
    info = probe(clip(tmp_path / "a.mp4", seconds=2, fps=10))
    assert (info["width"], info["height"], info["fps"], info["frames"]) == (64, 48, 10.0, 20)
    assert info["duration"] == pytest.approx(2.0, abs=0.15) and not info["has_audio"] and info["rotation"] == 0
    # A phone clip stored landscape with a 90 degree display matrix is portrait, as players show it.
    rotated = probe(FIXTURES / "rotated-90.mp4")
    assert (rotated["width"], rotated["height"], rotated["rotation"]) == (48, 64, 90)
    assert frames_at(FIXTURES / "rotated-90.mp4", [0.5])[0].size == (48, 64)


def test_frame_times_follow_the_interval_up_to_thirty_frames():
    assert frame_times(10, 0.5) == [round(0.25 + 0.5 * i, 3) for i in range(20)]
    assert len(frame_times(68.352, 0.5)) == 30 and frame_times(68.352, 0.5)[0] == pytest.approx(1.139, abs=0.001)
    assert frame_times(1.0, 0.25) == [0.125, 0.375, 0.625, 0.875]
    assert frame_times(0, 0.5) == [0.0]


def test_frames_are_taken_at_their_times(tmp_path):
    video = clip(tmp_path / "a.mp4", seconds=2, fps=10)
    images = frames_at(video, [0.12, 1.14, 1.95])  # the nearest frame to each time
    levels = [image.convert("L").getpixel((32, 24)) for image in images]
    assert [round(level / 10) for level in levels] == [1, 11, 19]
    assert thumbnail(video, 32)[:2] == b"\xff\xd8"


def test_clips_import_with_their_own_outputs_and_unreadable_files_are_marked(tmp_path):
    folder = tmp_path / "media"
    clip(folder / "walk.mp4")
    picture(folder / "photo.png")
    (folder / "broken.mov").write_bytes(b"not a video")
    picture(folder / "same.png")
    clip(folder / "same.mp4")  # both would need same.wan.txt
    studio = Studio(tmp_path / "app")
    asyncio.run(studio.import_images([], str(folder), False, False))
    rows = {r["name"]: r for r in studio.rows}
    walk = rows["walk.mp4"]
    assert walk["kind"] == "clip" and set(walk["outputs"]) == {"wan", "wan_i2v", "ltx", "h3"}
    assert walk["clip"]["fps"] == 10.0 and (walk["width"], walk["height"]) == (64, 48)
    assert rows["photo.png"]["kind"] == "image" and "wan_i2v" not in rows["photo.png"]["outputs"]
    broken = rows["broken.mov"]["outputs"]
    assert {s["status"] for s in broken.values()} == {"invalid"} and broken["wan"][
        "error"
    ] == "The video cannot be read."
    assert rows["same.mp4"]["outputs"]["wan"]["error"].startswith("Two files would share the caption file same.")


def test_all_video_models_create_four_files_for_a_clip_and_three_for_a_photo(tmp_path, monkeypatch):
    async def run():
        folder = tmp_path / "media"
        video = clip(folder / "walk.mp4")
        photo = picture(folder / "photo.png")
        studio = Studio(tmp_path / "app")
        await studio.import_images([], str(folder), False, False)
        studio.settings.output_format = "video_all"
        studio.settings.words = 150
        seen = []

        async def fake(path, settings, key, **kwargs):
            seen.append((path.name, settings.output_format, settings.words))
            h3 = "integrated_multimodal_description: [Shot 1] Live-action, a medium shot frames Velmira, a woman, walking. The camera pans right.\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A"
            return CaptionResult(h3 if settings.output_format == "h3" else "Velmira, a woman, walks forward.")

        monkeypatch.setattr("captioning.provider.generate", fake)
        await studio.start_job([r["id"] for r in studio.rows])
        await studio.task
        assert studio.job["total"] == 7 and studio.job["saved"] == 7
        assert ("walk.mp4", "wan_i2v", 100) in seen  # WAN I2V captions stay short
        assert [o for name, o, _ in seen if name == "photo.png"] == ["wan", "ltx", "h3"]
        for suffix in (".wan.txt", ".wan-i2v.txt", ".ltx.txt", ".h3.txt"):
            assert video.with_suffix(suffix).exists()
        assert not photo.with_suffix(".wan-i2v.txt").exists()
        # Normal applies to photos only; a clip is left out of such a batch.
        studio.settings.output_format = "normal"
        seen.clear()
        await studio.start_job([r["id"] for r in studio.rows])
        await studio.task
        assert [name for name, _, _ in seen] == ["photo.png"]

    asyncio.run(run())


def capture(monkeypatch, content="<character> turns toward the camera."):
    requests = []
    real = httpx.AsyncClient

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": content}}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    return requests


def test_clip_requests_send_labeled_frames_and_the_clip_instructions(tmp_path, monkeypatch):
    video = clip(tmp_path / "walk.mp4", seconds=2, fps=10)
    requests = capture(monkeypatch)
    s = Settings(mode="cloud", cloud_model="m", output_format="wan_i2v", trigger="Velmira", character_class="a woman")
    result = asyncio.run(generate(video, s, "not-a-real-key"))
    assert result.text == "Velmira, a woman, turns toward the camera."
    content = requests[0]["messages"][0]["content"]
    labels = [part["text"] for part in content[:-1] if part["type"] == "text"]
    images = [part for part in content if part["type"] == "image_url"]
    assert labels == [f"Frame {i + 1} at {0.25 + 0.5 * i:.2f} s:" for i in range(4)] and len(images) == 4
    prompt = content[-1]["text"]
    assert "frames of one continuous video clip" in prompt and "first frame" in prompt
    assert "Target about 100 words" in prompt and "do not describe motion" not in prompt
    assert "camera movement over the clip" in prompt and "hair color" not in prompt


def test_h3_clip_captions_keep_their_own_camera_movement(tmp_path, monkeypatch):
    video = clip(tmp_path / "walk.mp4")
    capture(monkeypatch, "Live-action, a medium shot frames <character> walking. The camera pans right slowly.")
    s = Settings(mode="cloud", cloud_model="m", output_format="h3", trigger="Velmira", character_class="a woman")
    text = asyncio.run(generate(video, s, "not-a-real-key")).text
    assert "The camera pans right slowly." in text and "static" not in text
    photo_prompt = make_prompt(s)
    clip_prompt = make_prompt(s, "clip")
    assert "single still image" in photo_prompt and "single still image" not in clip_prompt
    assert "Motion over time" not in photo_prompt and "movement and actions of the main subject" in clip_prompt


def test_large_clip_requests_are_compressed_below_the_provider_limit(tmp_path, monkeypatch):
    video = clip(tmp_path / "noise.mp4", seconds=2, size=(640, 480))
    full = sum(len(data) for _, data in provider.clip_frames(video, 0.5))
    monkeypatch.setattr(provider, "MAX_IMAGE_BYTES", full // 2)
    smaller = sum(len(data) for _, data in provider.clip_frames(video, 0.5))
    assert len(provider.clip_frames(video, 0.5)) == 4 and smaller < full


def test_clip_endpoints_serve_the_file_its_frames_and_thumbnails(tmp_path):
    folder = tmp_path / "media"
    clip(folder / "walk.mp4")
    picture(folder / "photo.png")
    studio = Studio(tmp_path / "app")
    asyncio.run(studio.import_images([], str(folder), False, False))
    ids = {r["name"]: r["id"] for r in studio.rows}
    api = make_app(studio, "test-token", 8888, Path(__file__).parents[1] / "ui")
    with TestClient(api, base_url="http://127.0.0.1:8888") as client:
        client.get("/?token=test-token")
        media = client.get("/api/media/" + ids["walk.mp4"], headers={"Range": "bytes=0-99"})
        assert media.status_code == 206 and len(media.content) == 100
        assert media.headers["content-type"] == "video/mp4"
        assert client.get("/api/image/" + ids["walk.mp4"]).headers["content-type"] == "image/jpeg"
        assert client.get("/api/clip-frames/" + ids["walk.mp4"]).json() == {"times": [0.25, 0.75, 1.25, 1.75]}
        frame = client.get("/api/frame/" + ids["walk.mp4"], params={"t": 0.75})
        assert frame.status_code == 200 and frame.content[:2] == b"\xff\xd8"
        assert client.get("/api/media/" + ids["photo.png"]).status_code == 400
        prompt = client.post(
            "/api/prompt", params={"media": "clip"}, json={"output_format": "ltx"}, headers={"X-Caption-Client": "1"}
        )
        assert "frames of one continuous video clip" in prompt.json()["prompt"]
