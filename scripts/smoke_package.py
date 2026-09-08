"""Run an installed EXE with no source/runtime paths and a fresh data directory."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

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
    proc = subprocess.Popen([str(exe), "--no-open"], cwd=root, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        launch = root / "profile" / "launch.json"
        for _ in range(100):
            if launch.exists():
                break
            assert proc.poll() is None, "Packaged app exited before readiness"
            time.sleep(.1)
        url = json.loads(launch.read_text())["url"]
        with httpx.Client(follow_redirects=True, trust_env=False, timeout=20) as client:
            assert client.get(url).status_code == 200
            base = url.split("/?")[0]
            s = client.get(base + "/api/state").json()
            assert s["settings"]["local_source"] == "managed"
            assert client.get(base + "/assets/connections.css").status_code == 200
            assert 'id="app-version"' in client.get(base).text
            assert s["rows"] == [] and not s["has_key"] and not s["settings"]["setup_complete"]
            assert not s["runtime"]["ready"] and not s["runtime"]["running"]
            assert Path(s["runtime"]["root"]).is_relative_to(root)
            path = root / "dataset" / "test.png"
            path.parent.mkdir()
            Image.new("RGB", (60, 40), "green").save(path)
            headers = {"X-Caption-Client": "1"}
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
            response = client.put(base + "/api/caption/" + row["id"], json={"text": "Zeleny obrazek."}, headers=headers)
            assert response.status_code == 200, response.text
            assert path.with_suffix(".txt").read_bytes() == b"Zeleny obrazek.\n"
            report = {"exe": str(exe), "version": s["version"], "fresh_profile": True,
                      "isolated_PATH": True, "image_preview": True, "folder_preview_before_import": True,
                      "sidecar_write": True}
            (output / "package-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
    finally:
        proc.terminate()
        proc.wait(timeout=15)
