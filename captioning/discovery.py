"""Bounded, read-only discovery of loopback OpenAI-compatible model APIs."""
import asyncio
import json
import httpx
from .models import MANAGED_URL, Settings

CANDIDATES = [
    ("http://127.0.0.1:11434/v1", "Obvyklá adresa Ollamy"),
    ("http://127.0.0.1:1234/v1", "Obvyklá adresa LM Studia"),
    ("http://127.0.0.1:8080/v1", "Obvyklá adresa llama.cpp"),
    ("http://127.0.0.1:8000/v1", "Obvyklá adresa Unsloth / vLLM"),
    ("http://127.0.0.1:8888/v1", "Obvyklá adresa Unslothu"),
    (MANAGED_URL, "Adresa prostředí Caption Studio"),
]


async def probe(client, url, hint, key="", managed=False):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        async with client.stream("GET", url + "/models", headers=headers) as response:
            if response.status_code in (401, 403):
                return {"url": url, "hint": hint, "status": "requires_key", "models": [], "managed": managed}
            if response.status_code != 200:
                return None
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 2 * 1024 * 1024:
                    return None
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            return None
        models = sorted({m["id"] for m in data["data"] if isinstance(m, dict)
                         and isinstance(m.get("id"), str) and 0 < len(m["id"]) <= 300})[:1000]
        return {"url": url, "hint": hint, "status": "ready", "models": models, "managed": managed}
    except (httpx.HTTPError, ValueError, UnicodeError):
        return None


async def discover(configured_url="", keys=None, managed_running=False):
    candidates = list(CANDIDATES)
    if configured_url.strip():
        url = Settings(local_source="external", local_url=configured_url).local_url
        if url not in dict(candidates):
            candidates.append((url, "Vlastní adresa"))
    async with httpx.AsyncClient(timeout=httpx.Timeout(2.5, connect=1), follow_redirects=False, trust_env=False) as client:
        async def check(url, hint):
            try:
                return await asyncio.wait_for(probe(client, url, hint, (keys or {}).get(url, ""),
                                                    managed_running and url == MANAGED_URL), timeout=3.5)
            except asyncio.TimeoutError:
                return None
        results = await asyncio.gather(*(check(url, hint) for url, hint in candidates))
    return {"servers": [r for r in results if r is not None], "checked": len(candidates)}
