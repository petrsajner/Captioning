"""Opt-in live model check against the two public test images, using installed app."""
import json
import os
from pathlib import Path
import time
import httpx

workspace = Path(__file__).resolve().parents[1]
dataset = workspace / "output" / "test-dataset"
launch = json.loads((Path(os.environ["LOCALAPPDATA"]) / "CaptionStudio" / "launch.json").read_text())
base = launch["url"].split("/?")[0]
with httpx.Client(follow_redirects=True, trust_env=False, timeout=240) as client:
    client.get(launch["url"]).raise_for_status()
    headers = {"X-Caption-Client": "1"}
    state = client.get(base + "/api/state").json()
    assert state["settings"]["mode"] == "local"
    rows = [r for r in state["rows"] if Path(r["path"]).parent == dataset]
    assert len(rows) == 2 and {r["name"] for r in rows} == {"cats.png", "dog.jpg"}
    client.post(base + "/api/runtime/start", json={}, headers=headers).raise_for_status()
    client.post(base + "/api/jobs", json={"ids": [r["id"] for r in rows], "regenerate": True}, headers=headers).raise_for_status()
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        state = client.get(base + "/api/state").json()
        if not state["job"]["running"]:
            break
        time.sleep(1)
    assert state["job"]["saved"] == 2 and state["job"]["errors"] == 0, state["job"]
    report = {"version": state["version"], "runtime": state["runtime"]["root"], "rows": []}
    for row in state["rows"]:
        if Path(row["path"]).parent != dataset:
            continue
        data = Path(row["path"]).with_suffix(".txt").read_bytes()
        assert data.decode("utf-8").strip() == row["caption"]
        assert data.endswith(b"\n") and not data.startswith(b"\xef\xbb\xbf")
        report["rows"].append({k: row[k] for k in ("name", "status", "seconds", "caption")})
    (workspace / "output" / "live-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved": state["job"]["saved"], "errors": 0, "seconds": [r["seconds"] for r in report["rows"]]}))
