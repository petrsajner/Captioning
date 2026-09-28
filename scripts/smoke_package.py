"""Run an installed EXE with no source/runtime paths and a fresh data directory."""

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import av
import httpx
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument("exe", type=Path)
args = parser.parse_args()
exe = args.exe.resolve(strict=True)
output = Path(__file__).resolve().parents[1] / "output"
output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="clean-package-", dir=output) as temp:
    root = Path(temp)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PATH"] = os.path.join(os.environ["SystemRoot"], "System32")
    env["CAPTION_STUDIO_DATA_DIR"] = str(root / "profile")
    proc = subprocess.Popen(
        [str(exe), "--no-open"], cwd=root, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
    try:
        launch = root / "profile" / "launch.json"
        for _ in range(100):
            if launch.exists():
                break
            assert proc.poll() is None, "Packaged app exited before readiness"
            time.sleep(0.1)
        url = json.loads(launch.read_text())["url"]
        with httpx.Client(follow_redirects=True, trust_env=False, timeout=20) as client:
            assert client.get(url).status_code == 200
            base = url.split("/?")[0]
            s = client.get(base + "/api/state").json()
            assert s["settings"]["local_source"] == "managed"
            assert client.get(base + "/assets/style.css").headers["content-type"].startswith("text/css")
            assert 'id="app-version"' in client.get(base).text
            assert s["rows"] == [] and not s["has_key"] and not s["settings"]["setup_complete"]
            assert not s["runtime"]["ready"] and not s["runtime"]["running"]
            assert Path(s["runtime"]["root"]).is_relative_to(root)
            path = root / "dataset" / "test.png"
            path.parent.mkdir()
            Image.new("RGB", (60, 40), "green").save(path)
            headers = {"X-Caption-Client": "1"}
            assert s["settings"]["ui_language"] == "en"
            for language in ("en", "cs"):
                response = client.get(base + "/assets/locales/" + language + ".json")
                assert response.status_code == 200 and "messages" in response.json()
            assert client.get(base + "/assets/main.js").headers["content-type"].startswith("text/javascript")
            before_language = s["settings"]
            client.post(base + "/api/ui-language", json={"language": "cs"}, headers=headers).raise_for_status()
            assert client.get(base + "/api/state").json()["settings"] == {**before_language, "ui_language": "cs"}
            assert json.loads((root / "profile" / "settings.json").read_text())["ui_language"] == "cs"
            listing_response = client.post(base + "/api/folders", json={"path": str(path.parent)}, headers=headers)
            assert listing_response.status_code == 200, listing_response.text
            listing = listing_response.json()
            assert listing["image_count"] == 1 and listing["images"][0]["name"] == "test.png"
            assert listing["breadcrumbs"][-1]["path"] == str(path.parent)
            tree_response = client.post(base + "/api/folder-tree", json={"path": str(root)}, headers=headers)
            assert tree_response.status_code == 200
            assert "dataset" in [f["name"] for f in tree_response.json()["folders"]]
            preview = client.get(base + "/api/folder-image/" + listing["images"][0]["id"])
            assert preview.status_code == 200 and preview.headers["content-type"] == "image/jpeg"
            assert client.get(base + "/api/state").json()["rows"] == []
            response = client.post(base + "/api/import", json={"paths": [str(path)]}, headers=headers)
            assert response.status_code == 200, response.text
            s = client.get(base + "/api/state").json()
            row = s["rows"][0]
            assert client.get(base + "/api/image/" + row["id"]).headers["content-type"] == "image/jpeg"
            response = client.put(base + "/api/caption/" + row["id"], json={"text": "Green image."}, headers=headers)
            assert response.status_code == 200, response.text
            assert path.with_suffix(".txt").read_bytes() == b"Green image.\n"
            # The packaged JSON writer must validate structure; other caption files stay untouched.
            json_image = root / "dataset" / "bria.png"
            Image.new("RGB", (60, 40), "blue").save(json_image)
            fibo = {
                "short_description": "A blue image.",
                "objects": [],
                "background_setting": "",
                "lighting": {"conditions": "", "direction": ""},
                "aesthetics": {"composition": "", "color_scheme": "blue", "mood_atmosphere": ""},
                "context": "",
            }
            json_image.with_suffix(".json").write_text(json.dumps(fibo), encoding="utf-8")
            json_image.with_suffix(".txt").write_text("keep this caption", encoding="utf-8")
            config = s["settings"]
            config["output_format"] = "bria_json"
            client.post(base + "/api/settings", json={"settings": config}, headers=headers).raise_for_status()
            client.post(base + "/api/import", json={"paths": [str(json_image)]}, headers=headers).raise_for_status()
            json_row = client.get(base + "/api/state").json()["rows"][0]
            assert json_row["outputs"]["bria_json"]["status"] == "existing"
            assert json_row["outputs"]["normal"]["caption"] == "keep this caption"
            endpoint = base + "/api/caption/" + json_row["id"]
            bria = {"output": "bria_json"}
            assert client.put(endpoint, json={"text": "{}", **bria}, headers=headers).status_code == 400
            client.put(endpoint, json={"text": json.dumps(fibo), **bria}, headers=headers).raise_for_status()
            assert json_image.with_suffix(".txt").read_text(encoding="utf-8") == "keep this caption"
            assert json.loads(json_image.with_suffix(".json").read_text())["short_description"] == "A blue image."
            # Video-model captions are separate files; H3 keeps its three official fields.
            wan = "Velmira, a woman, stands in front of a blue wall."
            client.put(endpoint, json={"text": wan, "output": "wan"}, headers=headers).raise_for_status()
            assert json_image.with_suffix(".wan.txt").read_text(encoding="utf-8") == wan + "\n"
            assert client.put(endpoint, json={"text": wan, "output": "h3"}, headers=headers).status_code == 400
            assert not json_image.with_suffix(".h3.txt").exists()
            # The packaged PyAV decodes clips: import, thumbnail, frames and a WAN I2V caption file.
            clip_path = root / "dataset" / "walk.mp4"
            with av.open(str(clip_path), "w") as container:
                stream = container.add_stream("libx264", rate=24)
                stream.width, stream.height, stream.pix_fmt = 96, 64, "yuv420p"
                for n in range(48):
                    frame = av.VideoFrame.from_image(Image.new("RGB", (96, 64), (5 * n, 40, 90)))
                    container.mux(stream.encode(frame))
                container.mux(stream.encode(None))
            client.post(base + "/api/import", json={"paths": [str(clip_path)]}, headers=headers).raise_for_status()
            clip_row = client.get(base + "/api/state").json()["rows"][0]
            assert clip_row["kind"] == "clip" and clip_row["clip"]["frames"] == 48, clip_row
            assert client.get(base + "/api/image/" + clip_row["id"]).headers["content-type"] == "image/jpeg"
            assert client.get(base + "/api/clip-frames/" + clip_row["id"]).json()["times"] == [0.25, 0.75, 1.25, 1.75]
            i2v = "Velmira, a woman, turns toward the camera."
            client.put(
                base + "/api/caption/" + clip_row["id"], json={"text": i2v, "output": "wan_i2v"}, headers=headers
            ).raise_for_status()
            assert clip_path.with_suffix(".wan-i2v.txt").read_text(encoding="utf-8") == i2v + "\n"
            # A clean Windows lacks the Visual C++ runtime that llama.cpp needs; the app ships it.
            vc_runtime = exe.parent / "_internal" / "vcredist"
            for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
                assert (vc_runtime / name).is_file(), f"{name} is missing from the package"
            # The user manuals ship next to the application in both languages.
            for language in ("EN", "CS"):
                manual = exe.parent / "manuals" / f"Caption-Studio-Manual-{language}.pdf"
                assert manual.is_file() and manual.read_bytes()[:5] == b"%PDF-", f"{manual.name} is missing"
            report = {
                "exe": str(exe),
                "version": s["version"],
                "fresh_profile": True,
                "isolated_PATH": True,
                "image_preview": True,
                "folder_preview_before_import": True,
                "sidecar_write": True,
                "bria_validation_with_coexisting_captions": True,
                "video_model_caption_files": True,
                "clip_decoding_and_captions": True,
                "localization_assets_and_preference": True,
                "vc_runtime_for_llama_cpp": True,
                "user_manuals": True,
            }
            (output / "package-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
    finally:
        proc.terminate()
        proc.wait(timeout=15)
