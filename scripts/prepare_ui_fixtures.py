"""Create an isolated profile and public test images for the browser UI suite.

Usage: prepare_ui_fixtures.py <root> <model-server-url>
Prints the resolved fixture paths as JSON. Never touches user datasets or profiles.
"""

import json
import sys
from pathlib import Path

import av
from PIL import Image


def picture(path: Path, color: str, size=(96, 64)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def video(path: Path, seconds=2, fps=24, size=(96, 64)):
    """An H.264 clip, so the inspector's player can show it; the square moves left to right."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = size[0], size[1], "yuv420p"
        for n in range(seconds * fps):
            image = Image.new("RGB", size, "navy")
            image.paste(
                "yellow", (n * (size[0] - 16) // (seconds * fps), 24, n * (size[0] - 16) // (seconds * fps) + 16, 40)
            )
            container.mux(stream.encode(av.VideoFrame.from_image(image)))
        container.mux(stream.encode(None))


def main():
    root = Path(sys.argv[1]).resolve()
    model_url = sys.argv[2]
    dataset, navigation, bria, clips = root / "dataset", root / "navigation", root / "bria", root / "clips"
    picture(dataset / "Waiting.png", "gray")
    picture(dataset / "second.png", "teal")
    picture(dataset / "red.png", "red")
    (dataset / "red.txt").write_text("ohwx, A red square on a plain background.\n", encoding="utf-8")
    picture(dataset / "blue.png", "blue")
    picture(dataset / "sub" / "nested.png", "black")
    picture(navigation / "Collection A" / "Set One" / "one.png", "orange")
    picture(navigation / "Collection A" / "Set Two" / "dog.jpg", "brown")
    picture(navigation / "Collection B" / "Other Set" / "other.png", "purple")
    picture(bria / "dog.jpg", "brown")
    video(clips / "walk.mp4")
    picture(clips / "still.png", "olive")
    fibo = {
        "short_description": "testdog, A brown dog sitting on grass.",
        "objects": [{"description": "dog", "location": "center", "relationship": "sitting on grass"}],
        "background_setting": "a lawn",
        "lighting": {"conditions": "daylight", "direction": "front"},
        "aesthetics": {"composition": "centered", "color_scheme": "green and brown", "mood_atmosphere": "calm"},
        "context": "",
    }
    (bria / "dog.json").write_text(json.dumps(fibo, indent=2) + "\n", encoding="utf-8")
    settings = {
        "ui_language": "en",
        "setup_complete": True,
        "mode": "local",
        "local_source": "external",
        "local_url": model_url,
        "local_model": "fake-vision",
        "trigger": "ohwx",
        "words": 40,
    }
    (root / "profile").mkdir(parents=True, exist_ok=True)
    (root / "profile" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    print(
        json.dumps(
            {
                "root": str(root),
                "dataset": str(dataset),
                "navigation": str(navigation),
                "bria": str(bria),
                "clips": str(clips),
                "profile": str(root / "profile"),
                "settings": settings,
            }
        )
    )


if __name__ == "__main__":
    main()
