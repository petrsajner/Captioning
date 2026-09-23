"""Opt-in three-call caption policy check with a public fixture and configured cloud provider.

Never reads user datasets or writes provider keys. Public fixture:
https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg
"""

import argparse
import asyncio
import json
import shutil
from pathlib import Path

from captioning.bria import validate_json
from captioning.models import Settings
from captioning.paths import data_directory
from captioning.service import Studio
from captioning.storage import KeyStore


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    original = data_directory()
    config = json.loads((original / "settings.json").read_text(encoding="utf-8"))
    source = workspace / "output" / "test-dataset" / "dog.jpg"
    output = workspace / "output" / "training-live"
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for name, output_format, omitted in [
        ("identity-learn", "normal", ["identity"]),
        ("identity-described", "normal", []),
        ("bria-identity-learn", "bria_json", ["identity", "lighting"]),
    ]:
        folder = output / name
        folder.mkdir(exist_ok=True)
        image = folder / "dog.jpg"
        shutil.copy2(source, image)
        studio = Studio(output / (name + "-profile"))
        studio.settings = Settings(
            mode="cloud",
            cloud_url=config["cloud_url"],
            cloud_model=config["cloud_model"],
            output_format=output_format,
            omitted_attributes=omitted,
            preset="general",
            words=70,
            trigger="testdog",
            subject="dog",
            skip_existing=False,
        )
        studio.keys.data = KeyStore(original / "keys.json").data.copy()  # encrypted values, in memory only
        await studio.import_images([str(image)], "", False, False)
        await studio.start_job([studio.rows[0]["id"]], regenerate=True)
        await studio.task
        row = studio.rows[0]
        assert row["status"] == "saved", row["error"]
        suffix = ".json" if output_format == "bria_json" else ".txt"
        caption = image.with_suffix(suffix).read_text(encoding="utf-8").strip()
        assert caption == row["caption"]
        if output_format == "bria_json":
            validate_json(caption)
        assert not studio.keys.path.exists()
        report.append(
            {"case": name, "caption": caption, "seconds": row["seconds"], "file": str(image.with_suffix(suffix))}
        )
        print(name + ": saved", flush=True)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
