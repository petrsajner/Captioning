"""Video clips: probing, frames for the captioning model and thumbnails. Clips are only read, never changed."""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import TypedDict

import av
from PIL import Image

from .errors import UserError

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
# A frame every 0.5 s by default and at most 30 frames: H3's longest clip (15 s) at 0.5 s.
FRAME_CAP = 30
# About one megapixel: the vision encoder spends at least 1,024 tokens (32 x 32 px each) on a frame anyway.
FRAME_PIXELS = 1024 * 1024
UNREADABLE = "The video cannot be read."


class ClipInfo(TypedDict):
    width: int  # as displayed, after rotation
    height: int
    fps: float
    frames: int
    duration: float
    has_audio: bool
    rotation: int


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _open(path: Path):
    try:
        container = av.open(str(path))
    except (av.error.FFmpegError, OSError):
        raise UserError(UNREADABLE) from None
    if not container.streams.video:
        container.close()
        raise UserError(UNREADABLE)
    return container


def probe(path: Path) -> ClipInfo:
    with _open(path) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or stream.guessed_rate or 0)
        if stream.duration and stream.time_base:
            duration = float(stream.duration * stream.time_base)
        else:
            duration = container.duration / av.time_base if container.duration else 0.0
        try:
            first = next(container.decode(stream))
        except (StopIteration, av.error.FFmpegError):
            raise UserError(UNREADABLE) from None
        rotation = int(first.rotation or 0) % 360
        width, height = (first.height, first.width) if rotation in (90, 270) else (first.width, first.height)
        # A clip cut without re-encoding keeps the header's count, including frames before the cut.
        frames = (
            stream.frames if stream.frames and abs(stream.frames - duration * fps) <= fps else round(duration * fps)
        )
        return {
            "width": width,
            "height": height,
            "fps": round(fps, 3),
            "frames": int(frames),
            "duration": round(duration, 3),
            "has_audio": bool(container.streams.audio),
            "rotation": rotation,
        }


def frame_times(duration: float, interval: float, cap: int = FRAME_CAP) -> list[float]:
    """Times of the frames sent to the model: the middles of equal parts, about `interval` apart."""
    count = max(1, min(cap, math.ceil(duration / interval))) if duration > 0 else 1
    return [round((i + 0.5) * duration / count, 3) for i in range(count)]


def _upright(frame) -> Image.Image:
    image = frame.to_image()
    # The display matrix turns the stored picture counterclockwise, as players show it.
    return image.rotate(frame.rotation, expand=True) if frame.rotation else image


def frames_at(path: Path, times: list[float]) -> list[Image.Image]:
    """The first frame at or after each time, upright; seeking keeps long 4K clips fast."""
    images = []
    with _open(path) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        fps = float(stream.average_rate or 24)
        for t in times:
            if stream.time_base:
                container.seek(int(t / stream.time_base), stream=stream, backward=True)
            chosen = None
            try:
                for frame in container.decode(stream):
                    chosen = frame
                    if frame.time is not None and frame.time >= t - 0.5 / fps:
                        break
            except av.error.FFmpegError:
                pass
            if chosen is None:
                raise UserError(UNREADABLE)
            images.append(_upright(chosen))
    return images


def encode(image: Image.Image, pixels: int = FRAME_PIXELS, quality: int = 90) -> bytes:
    """Re-encoded pixels only: no metadata and no file names leave the computer."""
    scale = math.sqrt(pixels / (image.width * image.height))
    if scale < 1:
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS
        )
    out = io.BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=quality)
    return out.getvalue()


def sample_frames(path: Path, interval: float, quality: int = 90) -> list[tuple[float, bytes]]:
    times = frame_times(probe(path)["duration"], interval)
    return [(t, encode(image, quality=quality)) for t, image in zip(times, frames_at(path, times), strict=True)]


def thumbnail(path: Path, size: int, t: float | None = None, quality: int = 85) -> bytes:
    """A frame as a JPEG no larger than `size` on its long side; the middle frame by default."""
    time = probe(path)["duration"] / 2 if t is None else t
    image = frames_at(path, [time])[0]
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=quality)
    return out.getvalue()
