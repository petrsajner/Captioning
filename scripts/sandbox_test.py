"""Test the built installer on a clean Windows in Windows Sandbox (run before a release).

Windows Sandbox is a disposable Windows without Python, the Visual C++ runtime or anything else
installed; closing its window discards it. This script prepares output/sandbox/in (the installer
of the current version from dist/, test media and the llama.cpp CPU runtime address), maps it
read-only into the sandbox with a writable output/sandbox/results, starts the sandbox and waits
for scripts/sandbox/clean-install-test.ps1 to write results/summary.json. It then prints which
checks passed. Requires the Windows Sandbox feature and a build (scripts/build.ps1).

Usage: python -m scripts.sandbox_test [--timeout 900]
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from PIL import Image

from captioning import __version__
from captioning.runtime import ARCHIVES, RELEASE

ROOT = Path(__file__).resolve().parents[1]
# The sandbox side of the shared folders; kept off the desktop, like everything the test creates.
SANDBOX_WORK = r"C:\CaptionStudioTest"
# What a working clean install looks like; any other value is reported as a failure.
EXPECTED = {
    "installer_exit": lambda v: v == 0,
    "installed": lambda v: v is True,
    "app_started": lambda v: v is True,
    "app_process_running": lambda v: v is True,
    "webview2_processes": lambda v: isinstance(v, int) and v > 0,
    "version": lambda v: v == __version__,
    "imported": lambda v: v == 3,
    "photo_thumbnail": lambda v: v == "image/jpeg",
    "clip_frames": lambda v: isinstance(v, int) and v > 0,
    "caption_saved": lambda v: v is True,
    "prompt_for_wan": lambda v: v is True,
    "llama_with_bundled_vc_runtime_exit": lambda v: v == 0,
}


def prepare(sandbox: Path) -> Path:
    installer = ROOT / "dist" / f"Caption-Studio-Setup-{__version__}-Windows-x64.exe"
    if not installer.is_file():
        raise SystemExit(f"{installer.name} is missing; build it with scripts/build.ps1 first.")
    inbox, results = sandbox / "in", sandbox / "results"
    shutil.rmtree(sandbox, ignore_errors=True)
    (inbox / "media").mkdir(parents=True)
    results.mkdir()
    shutil.copy2(installer, inbox)
    shutil.copy2(ROOT / "scripts" / "sandbox" / "clean-install-test.ps1", inbox)
    for name, color in (("red.jpg", (190, 60, 50)), ("blue.jpg", (40, 90, 180))):
        Image.new("RGB", (320, 240), color).save(inbox / "media" / name, quality=90)
    shutil.copy2(ROOT / "tests" / "fixtures" / "rotated-90.mp4", inbox / "media")
    cpu_zip = ARCHIVES["cpu"][0][0]
    url = f"https://github.com/ggml-org/llama.cpp/releases/download/{RELEASE}/{cpu_zip}"
    (inbox / "config.json").write_text(json.dumps({"llama_cpu_url": url}), encoding="utf-8")
    config = sandbox / "clean-install-test.wsb"
    config.write_text(
        f"""<Configuration>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{inbox}</HostFolder>
      <SandboxFolder>{SANDBOX_WORK}\\in</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{results}</HostFolder>
      <SandboxFolder>{SANDBOX_WORK}\\results</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <MemoryInMB>8192</MemoryInMB>
  <LogonCommand>
    <Command>powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File {SANDBOX_WORK}\\in\\clean-install-test.ps1</Command>
  </LogonCommand>
</Configuration>
""",
        encoding="utf-8",
    )
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=900, help="seconds to wait for the sandbox")
    args = parser.parse_args()
    if not Path(os.environ["SystemRoot"], "System32", "WindowsSandbox.exe").is_file():
        raise SystemExit("Windows Sandbox is not enabled (Turn Windows features on or off > Windows Sandbox).")
    sandbox = ROOT / "output" / "sandbox"
    config = prepare(sandbox)
    os.startfile(config)  # opens the sandbox window with this configuration
    summary_file = sandbox / "results" / "summary.json"
    deadline = time.monotonic() + args.timeout
    while not summary_file.is_file():
        if time.monotonic() > deadline:
            raise SystemExit(f"No results after {args.timeout} s; see {sandbox / 'results' / 'log.txt'}.")
        time.sleep(5)
    time.sleep(1)  # the file is written in one go; give the share a moment
    summary = json.loads(summary_file.read_text(encoding="utf-8-sig"))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    failed = [key for key, check in EXPECTED.items() if not check(summary.get(key))]
    for key in failed:
        print(f"FAILED: {key} = {summary.get(key)!r}")
    print("All clean-install checks passed." if not failed else f"{len(failed)} check(s) failed.")
    print(f"Screenshots and logs: {sandbox / 'results'}. Close the sandbox window to discard it.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
