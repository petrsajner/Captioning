"""Captions of any LoRA type and output for copies of photos and clips, through a local server or a cloud API.

The original folder is read-only and checked by hash afterwards. A local server (for example Marvin on
127.0.0.1:8080) is never started, stopped or reconfigured. For a cloud API, the encrypted key is read from
an existing keys.json into memory only. Captions stay in the ignored output/ folder.
"""

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
from pathlib import Path

from captioning.models import OUTPUT_SUFFIX, Settings, outputs_for
from captioning.quality import word_count
from captioning.service import Studio
from captioning.storage import KeyStore
from captioning.video import h3_body


def digests(folder: Path, names: list[str]) -> dict[str, str | None]:
    """Hashes of the originals and every caption file they may have."""
    result = {}
    for name in names:
        media = folder / name
        for path in [media, *(media.with_suffix(suffix) for suffix in OUTPUT_SUFFIX.values())]:
            result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--names", nargs="+", required=True, help="photo or clip file names to copy")
    parser.add_argument("--url", default="http://127.0.0.1:8080/v1", help="local server")
    parser.add_argument("--model", default="q5", help="local model ID")
    parser.add_argument("--cloud-url", help="use this cloud API instead of the local server")
    parser.add_argument("--cloud-model", help="cloud model ID")
    parser.add_argument("--keys", type=Path, help="keys.json holding the cloud API key (read into memory only)")
    parser.add_argument("--preset", default="character", choices=["general", "character", "object", "style"])
    parser.add_argument("--trigger", default="")
    parser.add_argument("--class", dest="subject_class", default="", help="character or object type, e.g. a woman")
    parser.add_argument("--outputs", nargs="+", default=["video_all"], help="caption outputs, run one after another")
    parser.add_argument("--omit", nargs="*", help="details left out of the captions (default: the type's defaults)")
    parser.add_argument("--words", type=int, default=80)
    parser.add_argument("--interval", type=float, default=0.5, help="seconds between clip frames")
    parser.add_argument("--out", default="video-captions-live", help="folder name under output/")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    output = workspace / "output" / args.out
    shutil.rmtree(output, ignore_errors=True)
    dataset = output / "dataset"
    dataset.mkdir(parents=True)
    before = digests(args.folder, args.names)
    for name in args.names:
        shutil.copy2(args.folder / name, dataset / name)
    studio = Studio(output / "profile")
    # The recipe's "Apply defaults for this LoRA type" choices, unless details are given.
    defaults = {"character": ["identity", "hair_color"], "object": ["identity"], "style": ["style"]}
    omitted = args.omit if args.omit is not None else defaults.get(args.preset, [])
    connection: dict = (
        {"mode": "cloud", "cloud_url": args.cloud_url, "cloud_model": args.cloud_model}
        if args.cloud_url
        else {"mode": "local", "local_source": "external", "local_url": args.url, "local_model": args.model}
    )
    studio.save_settings(
        Settings(
            **connection,
            preset=args.preset,
            output_format=args.outputs[0],
            trigger=args.trigger,
            subject_class=args.subject_class,
            omitted_attributes=omitted,
            words=args.words,
            clip_interval=args.interval,
            timeout=600,
            skip_existing=False,
            auto_save=True,
            setup_complete=True,
        )
    )
    if args.keys:
        studio.keys.data = KeyStore(args.keys).data.copy()  # encrypted values, in memory only
    await studio.import_images([], str(dataset), False, False)
    for output_format in args.outputs:
        studio.save_settings(studio.settings.model_copy(update={"output_format": output_format}))
        await studio.start_job([r["id"] for r in studio.rows])
        await studio.task
    wanted = {name for output_format in args.outputs for name in outputs_for(output_format)}
    report = []
    for row in studio.rows:
        for output_name, slot in row["outputs"].items():
            if output_name not in wanted:
                continue
            text = slot["caption"]
            history = slot.get("generation_history", [])
            report.append(
                {
                    "file": row["name"],
                    "kind": row.get("kind"),
                    "output": output_name,
                    "status": slot["status"],
                    "words": None if output_name == "bria_json" else word_count(h3_body(text)),
                    "trigger_count": text.count(args.trigger) if args.trigger else None,
                    "seconds": slot.get("seconds"),
                    "stages": [h.get("stage") for h in history],
                    "completion_tokens": [h.get("completion_tokens") for h in history],
                    "notice": slot.get("notice"),
                    "error": slot.get("error"),
                    "caption": text,
                }
            )
    assert digests(args.folder, args.names) == before, "An original file changed"
    assert not studio.keys.path.exists(), "The API key must not be written"
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"job": studio.job, "originals_unchanged": True, "results": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
