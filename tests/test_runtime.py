"""Managed runtime lifecycle with a stand-in process and stand-in downloads; never starts llama-server."""

import asyncio
import hashlib
import io
import socket
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from captioning import runtime as runtime_module
from captioning.api import make_app
from captioning.errors import UserError
from captioning.runtime import Runtime
from captioning.service import Studio

MODEL, PROJECTOR = b"tiny model weights", b"tiny projector"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive(names):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name in names:
            z.writestr(name, "stand-in")
    return buffer.getvalue()


@pytest.fixture
def tiny(monkeypatch):
    """Replace the multi-gigabyte pinned files with small ones and keep port checks off 8091."""
    server = archive(["bin/llama-server.exe", "bin/ggml.dll"])
    monkeypatch.setattr(
        runtime_module,
        "FILES",
        {"q4": ("model.gguf", len(MODEL), digest(MODEL)), "vision": ("mmproj.gguf", len(PROJECTOR), digest(PROJECTOR))},
    )
    monkeypatch.setattr(runtime_module, "ARCHIVES", {"cpu": [("llama-cpu.zip", len(server), digest(server))]})
    monkeypatch.setattr(runtime_module, "MANAGED_PORT", 0)
    return {"llama-cpu.zip": server, "model.gguf": MODEL, "mmproj.gguf": PROJECTOR}


def serve_downloads(monkeypatch, files, status=200):
    requests = []
    real = httpx.Client

    def handler(request):
        requests.append(request.url.path)
        name = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(status, content=files.get(name, b"") if status == 200 else b"")

    monkeypatch.setattr(runtime_module.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return requests


def installed(tmp_path, monkeypatch, tiny):
    runtime = Runtime(tmp_path)
    serve_downloads(monkeypatch, tiny)
    runtime._install("q4", "cpu")
    assert runtime.state["status"] == "done", runtime.state
    return runtime


class FakeProcess:
    """Stands in for llama-server: alive until terminated, or exits with a given code."""

    instances: list = []

    def __init__(self, args, exit_code=None, **kwargs):
        self.args, self.exit_code, self.terminated = args, exit_code, False
        FakeProcess.instances.append(self)

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.terminated, self.exit_code = True, 1

    def wait(self, timeout=None):
        return self.exit_code

    def kill(self):
        self.terminate()


def launch(monkeypatch, health=200, exit_code=None):
    FakeProcess.instances = []
    monkeypatch.setattr(
        runtime_module.subprocess, "Popen", lambda args, **kw: FakeProcess(args, exit_code=exit_code, **kw)
    )
    real = httpx.AsyncClient
    monkeypatch.setattr(
        runtime_module.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(lambda request: httpx.Response(health)), **kw),
    )


def test_install_downloads_verifies_extracts_and_is_ready(tmp_path, monkeypatch, tiny):
    runtime = Runtime(tmp_path)
    assert not runtime.ready("q4", "cpu")
    requests = serve_downloads(monkeypatch, tiny)
    runtime._install("q4", "cpu")
    assert runtime.state["status"] == "done" and runtime.ready("q4", "cpu")
    assert [path.rsplit("/", 1)[-1] for path in requests] == ["llama-cpu.zip", "model.gguf", "mmproj.gguf"]
    assert (runtime.runtime_dir("cpu") / "bin" / "llama-server.exe").is_file()
    assert not (runtime.root / "staging-cpu").exists()
    # Verified files are not downloaded or hashed again.
    requests.clear()
    runtime._install("q4", "cpu")
    assert runtime.state["status"] == "done" and requests == []
    assert Runtime(tmp_path).ready("q4", "cpu")


def test_install_puts_the_bundled_vc_runtime_next_to_llama_server(tmp_path, monkeypatch, tiny):
    # A clean Windows has no Visual C++ runtime; llama-server finds the bundled copy in its own folder.
    bundled = tmp_path / "bundle" / "vcredist"
    bundled.mkdir(parents=True)
    for name in runtime_module.VC_RUNTIME:
        (bundled / name).write_bytes(name.encode())
    monkeypatch.setattr(runtime_module, "bundled_vc_runtime", lambda: bundled)
    runtime = installed(tmp_path, monkeypatch, tiny)
    server_dir = runtime.runtime_dir("cpu") / "bin"
    assert all((server_dir / name).read_bytes() == name.encode() for name in runtime_module.VC_RUNTIME)


def test_the_vc_runtime_is_bundled_only_in_a_built_app(tmp_path, monkeypatch):
    assert runtime_module.bundled_vc_runtime() is None  # a source checkout uses the system's copy
    (tmp_path / "vcredist").mkdir()
    monkeypatch.setattr(runtime_module.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert runtime_module.bundled_vc_runtime() == tmp_path / "vcredist"


def test_install_removes_runtimes_of_earlier_releases(tmp_path, monkeypatch, tiny):
    runtime = Runtime(tmp_path)
    old = runtime.root / "llama-b10821-cpu" / "bin"
    old.mkdir(parents=True)
    (old / "llama-server.exe").write_text("old", encoding="utf-8")
    other_backend = runtime.root / "llama-b10821-cuda"
    other_backend.mkdir()
    downloads = runtime.root / "downloads"
    downloads.mkdir()
    stale = downloads / "llama-b10821-bin-win-cpu-x64.zip"
    stale.write_bytes(b"old")
    cudart = downloads / "cudart-llama-bin-win-cuda-13.3-x64.zip"
    cudart.write_bytes(b"shared")
    serve_downloads(monkeypatch, tiny)
    runtime._install("q4", "cpu")
    assert runtime.state["status"] == "done" and runtime.ready("q4", "cpu")
    assert not old.parent.exists() and not stale.exists()
    assert other_backend.exists() and cudart.exists()  # other backends are left alone


def test_start_uses_the_measured_placement_of_each_profile(tmp_path, monkeypatch, tiny):
    files = runtime_module.FILES
    monkeypatch.setattr(runtime_module, "FILES", {**files, "q2": files["q4"], "q3": files["q4"]})
    monkeypatch.setattr(runtime_module, "ARCHIVES", {"cuda": runtime_module.ARCHIVES["cpu"]})
    runtime = Runtime(tmp_path)
    serve_downloads(monkeypatch, tiny)
    runtime._install("q4", "cuda")
    launch(monkeypatch)
    for profile, cpu_projector in (("q2", False), ("q3", True), ("q4", False)):
        asyncio.run(runtime.start(profile, "cuda"))
        args = FakeProcess.instances[-1].args
        assert args[args.index("-c") + 1] == "65536" and args[args.index("--fit") + 1] == "off"
        assert ("--no-mmproj-offload" in args) == cpu_projector, profile
        runtime.stop()


def test_install_cancel_keeps_progress_for_the_next_attempt(tmp_path, monkeypatch, tiny):
    runtime = Runtime(tmp_path)
    serve_downloads(monkeypatch, tiny)
    runtime.cancel.set()
    runtime._install("q4", "cpu")
    assert runtime.state["status"] == "cancelled" and not runtime.ready("q4", "cpu")
    runtime.cancel.clear()
    runtime._install("q4", "cpu")
    assert runtime.state["status"] == "done"


@pytest.mark.parametrize(
    "problem, message",
    [
        ("disk", "Insufficient disk space"),
        ("http", "Download failed"),
        ("archive", "does not contain llama-server.exe"),
        ("checksum", "Checksum mismatch"),
    ],
)
def test_install_failures_are_reported_without_a_ready_runtime(tmp_path, monkeypatch, tiny, problem, message):
    runtime = Runtime(tmp_path)
    files = dict(tiny)
    if problem == "disk":
        monkeypatch.setattr(runtime_module.shutil, "disk_usage", lambda path: type("Usage", (), {"free": 0})())
    if problem == "archive":
        files["llama-cpu.zip"] = archive(["bin/readme.txt"])
        monkeypatch.setattr(
            runtime_module,
            "ARCHIVES",
            {"cpu": [("llama-cpu.zip", len(files["llama-cpu.zip"]), digest(files["llama-cpu.zip"]))]},
        )
    if problem == "checksum":
        files["model.gguf"] = b"x" * len(MODEL)
    serve_downloads(monkeypatch, files, status=500 if problem == "http" else 200)
    runtime._install("q4", "cpu")
    assert runtime.state["status"] == "error" and message in runtime.state["message"]
    assert not runtime.ready("q4", "cpu")


def test_start_launches_owned_server_once_and_stop_releases_it(tmp_path, monkeypatch, tiny):
    runtime = installed(tmp_path, monkeypatch, tiny)
    launch(monkeypatch)

    async def run():
        await runtime.start("q4", "cpu")
        await runtime.start("q4", "cpu")  # already running with this profile
        with pytest.raises(UserError, match="Another profile"):
            await runtime.start("q5", "cpu")

    asyncio.run(run())
    assert len(FakeProcess.instances) == 1
    args = FakeProcess.instances[0].args
    assert args[args.index("--alias") + 1] == "caption-qwen" and args[args.index("--api-key") + 1] == runtime.api_key
    assert args[args.index("-n") + 1] == "-1" and "--no-mmproj-offload" in args  # no output cap; CPU projector
    assert args[args.index("-c") + 1] == "65536" and args[args.index("--fit") + 1] == "off"
    assert runtime.state["status"] == "running" and runtime.snapshot("q4", "cpu")["running"]
    with pytest.raises(UserError, match="Stop the local model"):
        runtime.install("q4", "cpu")
    runtime.stop()
    assert FakeProcess.instances[0].terminated and runtime.process is None
    assert runtime.state["status"] == "idle" and not runtime.snapshot("q4", "cpu")["running"]


@pytest.mark.parametrize("failure", ["exits", "never_healthy"])
def test_start_failure_stops_the_process_and_reports_an_error(tmp_path, monkeypatch, tiny, failure):
    runtime = installed(tmp_path, monkeypatch, tiny)
    launch(monkeypatch, health=503, exit_code=3 if failure == "exits" else None)

    async def no_wait(seconds):
        pass

    monkeypatch.setattr(runtime_module.asyncio, "sleep", no_wait)
    expected = "did not start" if failure == "exits" else "timed out"
    with pytest.raises(UserError, match=expected):
        asyncio.run(runtime.start("q4", "cpu"))
    assert runtime.process is None and runtime.state["status"] == "error"
    assert failure == "exits" or FakeProcess.instances[0].terminated


def test_start_requires_a_ready_runtime_and_a_free_port(tmp_path, monkeypatch, tiny):
    launch(monkeypatch)
    with pytest.raises(UserError, match="Download the selected local model"):
        asyncio.run(Runtime(tmp_path / "empty").start("q4", "cpu"))
    runtime = installed(tmp_path, monkeypatch, tiny)
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        monkeypatch.setattr(runtime_module, "MANAGED_PORT", busy.getsockname()[1])
        with pytest.raises(UserError, match="is in use"):
            asyncio.run(runtime.start("q4", "cpu"))
    assert FakeProcess.instances == [] and runtime.process is None


def test_runtime_endpoints_respect_running_batches_and_readiness(tmp_path):
    studio = Studio(tmp_path)
    api = make_app(studio, "test-token", 8888, Path(__file__).parents[1] / "ui")
    headers = {"X-Caption-Client": "1"}
    with TestClient(api, base_url="http://127.0.0.1:8888") as client:
        client.get("/?token=test-token")
        started = client.post("/api/runtime/start", json={}, headers=headers)
        assert started.status_code == 400 and started.json()["detail"].startswith("Download the selected local model")
        studio.job["running"] = True
        for action in ("install", "start", "stop"):
            busy = client.post("/api/runtime/" + action, json={}, headers=headers)
            assert busy.status_code == 400 and busy.json()["detail"].startswith("Wait for the operation")
        studio.job["running"] = False
    assert studio.runtime.process is None and not studio.runtime.installing


def test_the_nvidia_driver_is_recognised_by_its_cuda_library(tmp_path, monkeypatch):
    # Without an NVIDIA card the setup preselects the cloud; nothing is blocked either way.
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    assert runtime_module.nvidia_driver_installed() is False
    (tmp_path / "System32").mkdir()
    (tmp_path / "System32" / "nvcuda.dll").write_bytes(b"")
    assert runtime_module.nvidia_driver_installed() is True
    studio = Studio(tmp_path / "app")
    assert studio.snapshot()["nvidia_gpu"] is True
