"""Opt-in cloud regression using only the public dog fixture, never user datasets."""

import argparse
import asyncio
import json
from pathlib import Path

from captioning.models import Settings
from captioning.provider import generate
from captioning.quality import word_count
from captioning.service import data_directory
from captioning.storage import KeyStore


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    root = data_directory()
    previous = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    s = Settings(
        mode="cloud",
        cloud_url=previous["cloud_url"],
        cloud_model=previous["cloud_model"],
        words=40,
        subject="dog",
        trigger="testdog",
        omitted_attributes=["identity"],
    )
    result = await generate(workspace / "output/test-dataset/dog.jpg", s, KeyStore(root / "keys.json").get(s.cloud_url))
    output = workspace / "output/length-live-cloud"
    output.mkdir(parents=True, exist_ok=True)
    (output / "caption.txt").write_text(result.text + "\n", encoding="utf-8")
    report = {
        "words": word_count(result.text),
        "needs_review": result.needs_review,
        "notice": result.notice,
        "stages": [
            {
                k: h.get(k)
                for k in (
                    "stage",
                    "word_count",
                    "finish_reason",
                    "completion_tokens",
                    "reasoning_tokens",
                    "reasoning_present",
                    "app_token_limit",
                )
            }
            for h in result.history
        ],
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
