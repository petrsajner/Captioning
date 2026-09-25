from __future__ import annotations

import asyncio
import json
import mimetypes
import secrets
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from .discovery import CANDIDATES, discover
from .errors import UserError
from .folders import FolderBrowser
from .models import MANAGED_URL, Settings, make_prompt
from .provider import image_bytes, list_models
from .service import MAX_IMAGES, MAX_KEY_LENGTH, Studio

# Windows registry entries can map .js/.css to other types; the UI's module scripts need these.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


class ImportRequest(BaseModel):
    paths: list[str] = Field(default_factory=list, max_length=MAX_IMAGES)
    folder: str = ""
    recursive: bool = False
    append: bool = False


class SettingsRequest(BaseModel):
    settings: Settings
    api_key: str | None = Field(None, max_length=MAX_KEY_LENGTH)
    clear_key: bool = False
    local_api_key: str | None = Field(None, max_length=MAX_KEY_LENGTH)
    clear_local_key: bool = False


class LanguageRequest(BaseModel):
    language: Literal["en", "cs"]


class DiscoveryRequest(BaseModel):
    url: str = ""


class JobRequest(BaseModel):
    ids: list[str] = Field(max_length=MAX_IMAGES)
    regenerate: bool = False
    # Continue the image and output pairs a paused batch had left.
    resume: bool = False
    # Only this output (Regenerate in the inspector); otherwise the recipe's outputs.
    output: str | None = None


class CaptionRequest(BaseModel):
    text: str
    output: str = "normal"


class FolderRequest(BaseModel):
    path: str = ""
    page: int = Field(0, ge=0)


def make_app(studio: Studio, token: str, port: int, assets: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        yield
        await studio.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    origin = f"http://127.0.0.1:{port}"
    folder_browser = FolderBrowser()

    @app.middleware("http")
    async def local_session(request: Request, call_next):
        if request.headers.get("host") != f"127.0.0.1:{port}":
            return Response(status_code=403)
        if request.url.path == "/" and secrets.compare_digest(request.query_params.get("token", ""), token):
            response = RedirectResponse("/", status_code=303)
            response.set_cookie("caption_session", token, httponly=True, samesite="strict")
        else:
            if not secrets.compare_digest(request.cookies.get("caption_session", ""), token):
                return Response("Open the application using its shortcut.", status_code=403)
            if request.method not in ("GET", "HEAD"):
                if request.headers.get("origin", origin) != origin or request.headers.get("x-caption-client") != "1":
                    return Response(status_code=403)
            response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
            }
        )
        return response

    @app.exception_handler(UserError)
    async def user_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(ValidationError)
    async def invalid_value(request, exc):
        # Settings built from request fields, e.g. a typed server address.
        messages = [error["msg"].removeprefix("Value error, ") for error in exc.errors(include_input=False)]
        return JSONResponse({"detail": "; ".join(messages)}, status_code=400)

    @app.exception_handler(OSError)
    async def io_error(request, exc):
        return JSONResponse(
            {"detail": "The file is unavailable or writing is not allowed: " + str(exc)}, status_code=400
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        # The server still logs the traceback; the UI must not report a stopped application.
        return JSONResponse(
            {"detail": "An unexpected error occurred. If it repeats, check app.log in the data folder."},
            status_code=500,
        )

    @app.get("/")
    async def index():
        return FileResponse(assets / "index.html")

    @app.get("/api/state")
    async def state():
        return studio.snapshot()

    @app.post("/api/settings")
    async def settings(body: SettingsRequest):
        studio.save_settings(body.settings, body.api_key, body.clear_key, body.local_api_key, body.clear_local_key)
        return {
            "ok": True,
            "has_key": studio.keys.has(studio.settings.cloud_url),
            "has_local_key": studio.keys.has("local:" + studio.settings.local_url),
        }

    @app.post("/api/ui-language")
    async def ui_language(body: LanguageRequest):
        studio.save_settings(studio.settings.model_copy(update={"ui_language": body.language}))
        return {"ok": True}

    @app.post("/api/prompt")
    async def prompt(body: Settings):
        return {"prompt": make_prompt(body), "output_format": body.output_format}

    @app.post("/api/models")
    async def models(body: Settings):
        key = studio.keys.get(body.cloud_url) if body.mode == "cloud" else studio.local_key(body)
        return {"models": await list_models(body, key)}

    @app.post("/api/local-servers")
    async def local_servers(body: DiscoveryRequest):
        configured = (
            Settings(local_source="external", local_url=body.url).local_url
            if body.url.strip()
            else studio.settings.local_url
        )
        endpoints = {url for url, _ in CANDIDATES} | {configured}
        keys = {}
        for endpoint in endpoints:
            try:
                keys[endpoint] = studio.keys.get("local:" + endpoint)
            except UserError:
                pass  # Unreadable credentials appear as an authentication request.
        owned = studio.runtime.process is not None and studio.runtime.process.poll() is None
        if owned:
            keys[MANAGED_URL] = studio.runtime.api_key
        return await discover(configured, keys, owned)

    @app.post("/api/import")
    async def import_images(body: ImportRequest):
        await studio.import_images(body.paths, body.folder, body.recursive, body.append)
        return {"count": len(studio.rows)}

    @app.post("/api/pick/{kind}")
    async def pick(kind: str):
        studio.idle()
        if kind != "files":
            raise UserError("Unknown selection type.")
        result = studio.root / ("picker-" + uuid.uuid4().hex + ".json")
        if getattr(sys, "frozen", False):
            args = [sys.executable]
        else:
            args = [sys.executable, str(Path(__file__).resolve().parent.parent / "app.py")]
        process = await asyncio.create_subprocess_exec(
            *args, "--pick", kind, "--result", str(result), "--ui-language", studio.settings.ui_language
        )
        try:
            await process.wait()
            return {"paths": json.loads(result.read_text(encoding="utf-8")) if result.exists() else []}
        finally:
            result.unlink(missing_ok=True)

    @app.post("/api/folders")
    async def folders(body: FolderRequest):
        path = body.path or (str(Path(studio.rows[0]["path"]).parent) if studio.rows else str(Path.home()))
        return await asyncio.to_thread(folder_browser.listing, path, body.page)

    @app.get("/api/folder-image/{image_id}")
    async def folder_image(image_id: str):
        path = folder_browser.image(image_id)
        data = await asyncio.to_thread(image_bytes, path, 240, 85)
        return Response(data, media_type="image/jpeg")

    @app.post("/api/folder-tree")
    async def folder_tree(body: FolderRequest):
        return await asyncio.to_thread(folder_browser.children, body.path or str(Path.home()))

    @app.get("/api/image/{image_id}")
    async def image(image_id: str, full: bool = False):
        row = studio.row(image_id)
        data = await asyncio.to_thread(image_bytes, Path(row["path"]), 2048 if full else 360, 88)
        return Response(data, media_type="image/jpeg")

    @app.put("/api/caption/{image_id}")
    async def caption(image_id: str, body: CaptionRequest):
        studio.save_row(image_id, body.text, body.output)
        return {"ok": True}

    @app.post("/api/jobs")
    async def jobs(body: JobRequest):
        await studio.start_job(body.ids, body.regenerate, body.resume, body.output)
        return {"ok": True}

    @app.post("/api/jobs/stop")
    async def stop_job():
        await studio.cancel_job()
        return {"ok": True}

    @app.post("/api/runtime/install")
    async def install():
        studio.idle()
        studio.runtime.install(studio.settings.model_profile, studio.settings.backend)
        return {"ok": True}

    @app.post("/api/runtime/cancel")
    async def cancel_install():
        studio.runtime.cancel.set()
        return {"ok": True}

    @app.post("/api/runtime/start")
    async def start_model():
        studio.idle()
        await studio.runtime.start(studio.settings.model_profile, studio.settings.backend)
        return {"ok": True}

    @app.post("/api/runtime/stop")
    async def stop_model():
        studio.idle()
        await asyncio.to_thread(studio.runtime.stop)
        return {"ok": True}

    app.mount("/assets", StaticFiles(directory=assets), name="assets")
    return app
