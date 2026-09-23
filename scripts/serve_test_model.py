"""Opt-in local integration fixture: existing Qwen weights, separate authenticated server.

This test helper never downloads weights and is not shipped or started by the app.
The fixed key is test-only and the server is bound to loopback. Ctrl+C shuts it down.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx

from captioning.runtime import FILES, RELEASE

workspace = Path(__file__).resolve().parents[1]
runtime = Path(os.environ["LOCALAPPDATA"]) / "CaptionStudio" / "runtime"
exe = next((runtime / f"llama-{RELEASE}-cuda").rglob("llama-server.exe"))
logs = workspace / "output" / "external-server-test"
logs.mkdir(parents=True, exist_ok=True)
args = [
    str(exe),
    "-m",
    str(runtime / "models" / FILES["q4"][0]),
    "--mmproj",
    str(runtime / "models" / FILES["vision"][0]),
    "--host",
    "127.0.0.1",
    "--port",
    "8080",
    "--alias",
    "qa-qwen-vision",
    "--api-key",
    "caption-local-test-only",
    "-c",
    "8192",
    "-np",
    "1",
    "-ngl",
    "999",
    "--jinja",
    "-fa",
    "on",
    "-ctk",
    "q8_0",
    "-ctv",
    "q8_0",
    "--image-min-tokens",
    "1024",
    "--chat-template-kwargs",
    json.dumps({"enable_thinking": False}),
]
with (logs / "model.log").open("ab") as log:
    process = subprocess.Popen(
        args, cwd=exe.parent, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW
    )
try:
    with httpx.Client(timeout=2, trust_env=False) as client:
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError("Test model failed to start; inspect output/external-server-test/model.log")
            try:
                if client.get("http://127.0.0.1:8080/health").status_code == 200:
                    print("External test Qwen ready on loopback port 8080", flush=True)
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Test model startup timeout")
    process.wait()
except KeyboardInterrupt:
    pass
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=10)
