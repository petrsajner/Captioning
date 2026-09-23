"""Caption Studio desktop entry point. Frozen distribution includes private Python."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path


def interface_language(root: Path) -> str:
    """Best-effort language for native dialogs; never modifies saved files."""
    try:
        language = json.loads((root / "settings.json").read_text(encoding="utf-8")).get("ui_language")
    except (OSError, ValueError, AttributeError):
        return "en"
    return language if language in ("en", "cs") else "en"


def show_message(text: str, language: str, detail: str = "", error=False):
    import ctypes

    from captioning.i18n import translate

    message = translate(text, language) + ("\n\n" + detail if detail else "")
    ctypes.windll.user32.MessageBoxW(0, message, "Caption Studio", 0x10 if error else 0)


def pick(result, language="en"):
    from captioning.i18n import translate

    def t(text):
        return translate(text, language)

    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        paths = list(
            filedialog.askopenfilenames(
                parent=root,
                title=t("Select images"),
                filetypes=[(t("Images"), "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), (t("All files"), "*.*")],
            )
        )
        Path(result).write_text(json.dumps(paths, ensure_ascii=False), encoding="utf-8")
    finally:
        root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--pick", choices=["files"])
    parser.add_argument("--result")
    parser.add_argument("--ui-language", choices=["en", "cs"])
    args = parser.parse_args()
    if args.pick:
        pick(args.result, args.ui_language or "en")
        return

    import uvicorn

    from captioning import __version__
    from captioning.api import make_app
    from captioning.paths import prepare_data_directory
    from captioning.service import Studio

    # Next to the program; older per-user data is moved here once.
    root, notices = prepare_data_directory()
    # A session's dataset and model are owned by one instance.
    lock_file = (root / "instance.lock").open("a+b")
    if os.name == "nt":
        import msvcrt

        try:
            lock_file.seek(0)
            if lock_file.read(1) == b"":
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            show_message("Caption Studio is already running. Open the existing window.", interface_language(root))
            return
    if sys.stdout is None:
        sys.stdout = (root / "app.log").open("a", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = sys.stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    listener = None
    try:
        studio = Studio(root, notices)
        if args.ui_language:
            studio.save_settings(studio.settings.model_copy(update={"ui_language": args.ui_language}))
        listener = socket.socket()
        listener.bind(("127.0.0.1", args.port))
        port = listener.getsockname()[1]
        token = secrets.token_urlsafe(32)
        assets = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "ui"
        api = make_app(studio, token, port, assets)
        server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning", access_log=False))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError("The local application could not start.")
            time.sleep(0.05)
    except Exception:
        # A windowed build has no console; never fail without telling the user.
        traceback.print_exc()
        if listener is not None:
            listener.close()
        lock_file.close()
        if not (args.browser or args.no_open):
            show_message(
                "Caption Studio could not start. Details were written to app.log in the data folder.",
                interface_language(root),
                str(root),
                error=True,
            )
        raise SystemExit(1) from None
    url = f"http://127.0.0.1:{port}/?token={token}"
    # Test/browser launch details stay local and are replaced on each launch.
    (root / "launch.json").write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
    try:
        if args.browser or args.no_open:
            if not args.no_open:
                webbrowser.open(url)
            print(f"Caption Studio is running on port {port}. Press Ctrl+C to exit.", flush=True)
            while thread.is_alive():
                time.sleep(0.5)
        else:
            try:
                import webview

                webview.create_window(
                    f"Caption Studio {__version__}",
                    url,
                    width=1480,
                    height=940,
                    min_size=(1080, 700),
                    background_color="#101412",
                )
                webview.start(gui="edgechromium", private_mode=True, icon=str(assets / "caption-studio.ico"))
            except Exception as exc:
                print("The desktop window is unavailable; opening the browser.", type(exc).__name__, flush=True)
                webbrowser.open(url)
                while thread.is_alive():
                    time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        studio.runtime.cancel.set()
        server.should_exit = True
        thread.join(timeout=8)
        studio.runtime.stop()
        (root / "launch.json").unlink(missing_ok=True)
        lock_file.close()


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
