"""Peak GPU memory and prompt size of the managed runtime for one clip request (plan D4).

Starts the managed llama-server from an existing Caption Studio data folder's `runtime` folder with the
profile's normal placement, sends one clip request and stops the server again. Only `runtime/model.log`
and `runtime/verified.json` can change; settings, keys and the session are never read or written.
Close Caption Studio and free the GPU (for example Marvin's model) first.

Usage: python -m scripts.measure_managed_clip "<data folder>" --profile q4 [--backend cuda] [--clip file]
"""

import argparse
import asyncio
import json
import subprocess
import threading
import time
from pathlib import Path

import httpx

from captioning.models import MANAGED_MODEL, MANAGED_URL, Settings
from captioning.provider import build_payload, clip_frames
from captioning.runtime import CONTEXT, CPU_PROJECTOR, Runtime


def gpu_used_mib() -> int:
    """Memory in use on the first GPU; Windows does not report it per process, so deltas are measured."""
    query = ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]
    return int(subprocess.run(query, capture_output=True, text=True).stdout.split()[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path, help="Caption Studio data folder that holds runtime/")
    parser.add_argument("--profile", default="q4", choices=["q2", "q3", "q4", "q5"])
    parser.add_argument("--backend", default="cuda", choices=["cuda", "vulkan", "cpu"])
    parser.add_argument("--clip", type=Path, default=Path("output/live-clips/talk-68s.mp4"))
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()
    runtime = Runtime(args.data)
    if not runtime.ready(args.profile, args.backend):
        raise SystemExit(f"Download the {args.profile} model and the {args.backend} runtime in Caption Studio first.")
    frames = clip_frames(args.clip, args.interval)
    settings = Settings(output_format="wan", trigger="Karvel", character_class="a man", omitted_attributes=["identity"])
    payload = build_payload(settings, MANAGED_MODEL, frames, "clip")
    payload.update(temperature=0.6, top_p=0.95, chat_template_kwargs={"enable_thinking": False})
    before = gpu_used_mib()
    asyncio.run(runtime.start(args.profile, args.backend))
    try:
        loaded = gpu_used_mib()
        peak, done = [loaded], threading.Event()

        def watch():
            while not done.is_set():
                peak.append(gpu_used_mib())
                time.sleep(0.25)

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        started = time.monotonic()
        response = httpx.post(
            MANAGED_URL + "/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer " + runtime.api_key},
            timeout=900,
            trust_env=False,
        )
        seconds = round(time.monotonic() - started, 1)
        done.set()
        watcher.join()
        usage = response.json().get("usage", {})
    finally:
        runtime.stop()
    report = {
        "profile": args.profile,
        "backend": args.backend,
        "context": CONTEXT,
        "projector_on_cpu": args.profile in CPU_PROJECTOR or args.backend == "cpu",
        "clip": args.clip.name,
        "frames": len(frames),
        "frame_megabytes": round(sum(len(data) for _, data in frames) / 1e6, 1),
        "status": response.status_code,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "seconds": seconds,
        "gpu_before_mib": before,
        "gpu_after_load_mib": loaded,
        "gpu_peak_mib": max(peak),
        # What the model allocated: the rise over the memory other programs used before it started.
        "model_after_load_gib": round((loaded - before) / 1024, 2),
        "model_peak_gib": round((max(peak) - before) / 1024, 2),
    }
    out = Path("output") / f"measure-managed-{args.profile}-{args.backend}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
