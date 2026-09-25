"""Local-only regression on copies of explicitly selected user images.

The original directory is read-only. The existing external Q5 server is never
started/stopped by this script. Full captions stay in ignored output/, not logs.
"""

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
from pathlib import Path

from captioning.models import Settings
from captioning.paths import data_directory
from captioning.quality import word_ceiling, word_count
from captioning.service import Studio


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--model", default="q5")
    parser.add_argument("--url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--all", action="store_true", help="copy every image in the folder")
    parser.add_argument("--names", nargs="+", help="image file names to copy; default: the first five")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    output = workspace / "output" / ("length-live-local-all" if args.all else "length-live-local")
    dataset = output / "dataset"
    dataset.mkdir(parents=True, exist_ok=True)
    images = [p.name for p in sorted(args.folder.iterdir()) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    names = images if args.all else args.names or images[:5]
    originals = {}
    for name in names:
        image = args.folder / name
        originals[str(image)] = hashlib.sha256(image.read_bytes()).hexdigest()
        txt = image.with_suffix(".txt")
        originals[str(txt)] = hashlib.sha256(txt.read_bytes()).hexdigest() if txt.exists() else None
        shutil.copy2(image, dataset / name)
    studio = Studio(output / "profile")
    config = json.loads((data_directory() / "settings.json").read_text(encoding="utf-8"))
    config.update(
        mode="local",
        local_source="external",
        local_url=args.url,
        local_model=args.model,
        words=40,
        output_format="normal",
        format="description",
        skip_existing=False,
        auto_save=True,
    )
    studio.settings = Settings(**config)
    studio.save_settings(studio.settings)
    await studio.import_images([], str(dataset), False, False)
    await studio.start_job([r["id"] for r in studio.rows], regenerate=True)
    await studio.task
    report = []
    for row in studio.rows:
        slot = row["outputs"]["normal"]
        report.append(
            {
                "name": row["name"],
                "status": slot["status"],
                "words": word_count(slot["caption"]),
                "seconds": slot.get("seconds"),
                "target": 40,
                "ceiling": word_ceiling(40),
                "notice": slot.get("notice"),
                "error": slot.get("error"),
                "stages": [
                    {
                        k: h.get(k)
                        for k in ("stage", "word_count", "finish_reason", "completion_tokens", "reasoning_tokens")
                    }
                    for h in slot.get("generation_history", [])
                ],
            }
        )
    for path, digest in originals.items():
        p = Path(path)
        assert (hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None) == digest, "Original file changed"
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"originals_unchanged": True, "results": report}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
