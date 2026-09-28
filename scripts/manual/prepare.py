"""Prepare the demo dataset and two isolated profiles for the user manual's screenshots.

The dataset is docs/manual/demo (public-domain prints with captions) plus a short clip made here;
the profiles are fresh data folders with a finished setup, one per interface language. Nothing
outside output/manual is written. Prints the paths as JSON for scripts/manual/capture.mjs.

Usage: python -m scripts.manual.prepare
"""

import json
import shutil
from pathlib import Path

import av
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "docs" / "manual" / "demo"
OUT = ROOT / "output" / "manual"
CLIP = "ryogoku-bridge-pan"
# Captions for the demo clip, as the video models would open them for the style Zorvak.
CLIP_CAPTIONS = {
    ".wan.txt": "Zorvak style, crowds cross a long wooden bridge over a wide river while sailboats and "
    "rowboats drift below. A covered market lines the near bank. Soft daylight under a pale sky. A high, "
    "wide view; the camera tilts slowly down from the far shore to the market.",
    ".wan-i2v.txt": "Zorvak style, the view tilts slowly down from the far shore across the bridge to the "
    "busy market on the near bank.",
    ".ltx.txt": "Zorvak style, a high-angle wide shot looks across a wide river spanned by a long wooden "
    "bridge full of people. Boats with white sails drift beneath it, and a covered market crowds the near "
    "bank. The camera tilts slowly down from the far shore to the market.",
    ".h3.txt": "integrated_multimodal_description: [Shot 1] Zorvak style, a high-angle wide shot frames a "
    "long wooden bridge crowded with people over a wide river, boats drifting below and a covered market on "
    "the near bank. The camera tilts down with small amplitude at slow speed toward the market.\n\n"
    "overall_soundscape: N/A\n\nnon_diegetic_music: N/A",
}


def make_clip(source: Path, target: Path, seconds: int = 4, fps: int = 24, size=(768, 432)):
    """A slow tilt down one print, enough to show the clip view and its frames."""
    with Image.open(source) as image:
        image = image.convert("RGB")
        tall = image.resize((size[0], round(image.height * size[0] / image.width)), Image.Resampling.LANCZOS)
    travel = max(0, tall.height - size[1])
    frames = seconds * fps
    with av.open(str(target), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = size[0], size[1], "yuv420p"
        for n in range(frames):
            top = round(travel * n / (frames - 1))
            frame = av.VideoFrame.from_image(tall.crop((0, top, size[0], top + size[1])))
            container.mux(stream.encode(frame))
        container.mux(stream.encode())


def profile(folder: Path, language: str):
    folder.mkdir(parents=True)
    settings = {
        "ui_language": language,
        "setup_complete": True,
        "mode": "cloud",
        "cloud_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "cloud_model": "gemini-3.8-flash",
        "preset": "style",
        "trigger": "Zorvak",
        "output_format": "normal",
        "omitted_attributes": ["style", "palette"],
        "omitted_by_type": {"style": ["style", "palette"], "character": ["identity", "hair_color"]},
        "words": 100,
    }
    (folder / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    dataset = OUT / "dataset"
    dataset.mkdir(parents=True)
    for path in DEMO.iterdir():
        if path.suffix.lower() in (".jpg", ".txt", ".json"):
            shutil.copy2(path, dataset / path.name)
    make_clip(DEMO / "ryogoku-bridge.jpg", dataset / f"{CLIP}.mp4")
    for suffix, text in CLIP_CAPTIONS.items():
        (dataset / f"{CLIP}{suffix}").write_text(text + "\n", encoding="utf-8", newline="\n")
    profiles = {language: OUT / f"profile-{language}" for language in ("en", "cs")}
    for language, folder in profiles.items():
        profile(folder, language)
    print(json.dumps({"dataset": str(dataset), "profiles": {k: str(v) for k, v in profiles.items()}}))


if __name__ == "__main__":
    main()
