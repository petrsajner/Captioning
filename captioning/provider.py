from __future__ import annotations

import asyncio
import base64
import io
import re
from pathlib import Path
import httpx
from PIL import Image, ImageOps
from .models import Settings, make_prompt

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def image_bytes(path: Path, size: int, quality=92) -> bytes:
    with Image.open(path) as source:
        source.seek(0)
        im = ImageOps.exif_transpose(source)
        im.thumbnail((size, size), Image.Resampling.LANCZOS)
        if im.mode in ("RGBA", "LA") or "transparency" in im.info:
            rgba = im.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            im = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            im = im.convert("RGB")
        out = io.BytesIO()
        # Re-encode pixels only: never transmit EXIF or original paths.
        im.save(out, format="JPEG", quality=quality)
        return out.getvalue()


def clean_caption(value: str, trigger: str) -> str:
    value = re.sub(r"<think>.*?</think>", "", value, flags=re.S).strip()
    if "<think>" in value or "</think>" in value:
        raise ValueError("Model vrátil nedokončené uvažování místo popisku.")
    value = re.sub(r"^```[^\n]*\n|\n```$", "", value).strip().strip('"')
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        raise ValueError("Model vrátil prázdný popisek.")
    trigger = trigger.strip().strip(",")
    if trigger and not re.match(re.escape(trigger) + r"(?:\s|[,.:;]|$)", value, re.I):
        value = trigger + ", " + value
    return value


async def list_models(s: Settings, key: str = "") -> list[str]:
    base = s.local_endpoint if s.mode == "local" else s.cloud_url
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        async with httpx.AsyncClient(timeout=12, trust_env=False) as client:
            r = await client.get(base + "/models", headers=headers)
            if r.is_error:
                raise ValueError(f"API vrátilo HTTP {r.status_code}. Zkontrolujte adresu a přístupový klíč.")
            data = r.json().get("data", [])
            return sorted(str(m["id"]) for m in data if isinstance(m, dict) and m.get("id"))
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, httpx.HTTPError):
            raise ValueError("API není dostupné. Spusťte lokální model nebo zkontrolujte připojení.") from None
        raise


async def generate(path: Path, s: Settings, key: str = "") -> str:
    base = s.local_endpoint if s.mode == "local" else s.cloud_url
    model = s.local_model_id if s.mode == "local" else s.cloud_model
    if not model.strip():
        raise ValueError("V nastavení vyberte nebo zadejte ID modelu s podporou obrázků.")
    if s.mode == "cloud" and not key:
        raise ValueError("V nastavení chybí API klíč pro tuto adresu poskytovatele.")
    encoded = base64.b64encode(await asyncio.to_thread(image_bytes, path, s.image_size)).decode()
    payload = {
        "model": model, "stream": False, "max_tokens": s.max_tokens,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}},
            {"type": "text", "text": make_prompt(s)},
        ]}],
    }
    if s.mode == "local":
        payload.update(temperature=0.6, top_p=0.95)
        if s.local_source == "managed":
            payload["chat_template_kwargs"] = {"enable_thinking": False}
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(s.timeout, connect=15), trust_env=False) as client:
            for attempt in range(3):
                r = await client.post(base + "/chat/completions", json=payload, headers=headers)
                if r.status_code in (429, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                if r.is_error:
                    hints = {401: "Neplatný API klíč.", 402: "Nedostatečný kredit.",
                             403: "Přístup byl zamítnut.", 404: "Model nebo API adresa neexistuje.",
                             400: "Model nepřijal obrazový požadavek nebo jeho parametry.",
                             429: "Byl překročen limit požadavků."}
                    raise ValueError(f"HTTP {r.status_code}: " + hints.get(r.status_code, "Chyba poskytovatele. Zkuste to znovu."))
                body = r.json()
                if body.get("error"):
                    raise ValueError("Poskytovatel vrátil chybu generování. Zkontrolujte model a kredit.")
                choice = body["choices"][0]
                if choice.get("finish_reason") not in ("stop", "eos"):
                    raise ValueError("Model nedokončil popisek (limit délky nebo filtr). Zvyšte limit tokenů nebo upravte nastavení.")
                msg = choice["message"]
                if msg.get("refusal"):
                    raise ValueError("Poskytovatel odmítl popsat tento obrázek.")
                content = msg.get("content")
                if not isinstance(content, str):
                    raise ValueError("Model nevrátil textový popisek.")
                return clean_caption(content, s.trigger)
    except httpx.TimeoutException:
        raise ValueError("Model překročil časový limit. Lze jej zvýšit v nastavení.") from None
    except httpx.HTTPError:
        raise ValueError("Spojení s modelem selhalo. Zkontrolujte, zda běží a je dostupný.") from None
    except (KeyError, IndexError, TypeError):
        raise ValueError("API vrátilo neplatný formát odpovědi.") from None
    raise ValueError("Generování selhalo.")
