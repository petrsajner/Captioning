"""Caption Studio desktop entry point. Frozen distribution includes private Python."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
import webbrowser


def pick(kind, result):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        paths = list(filedialog.askopenfilenames(parent=root, title="Vyberte obrázky", filetypes=[
            ("Obrázky", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("Všechny soubory", "*.*")]))
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
    args = parser.parse_args()
    if args.pick:
        pick(args.pick, args.result)
        return

    from captioning.service import Studio, data_directory
    from captioning.api import make_app
    import uvicorn

    root = data_directory()
    root.mkdir(parents=True, exist_ok=True)
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
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Caption Studio už běží. Otevřete existující okno.", "Caption Studio", 0)
            return
    if sys.stdout is None:
        sys.stdout = (root / "app.log").open("a", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = sys.stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    listener = socket.socket()
    listener.bind(("127.0.0.1", args.port))
    port = listener.getsockname()[1]
    token = secrets.token_urlsafe(32)
    studio = Studio(root)
    assets = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "ui"
    api = make_app(studio, token, port, assets)
    server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning", access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        if not thread.is_alive():
            raise RuntimeError("Lokální aplikaci se nepodařilo spustit.")
        time.sleep(0.05)
    url = f"http://127.0.0.1:{port}/?token={token}"
    # Test/browser launch details stay local and are replaced on each launch.
    (root / "launch.json").write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
    try:
        if args.browser or args.no_open:
            if not args.no_open:
                webbrowser.open(url)
            print(f"Caption Studio běží na portu {port}. Ukončení: Ctrl+C.", flush=True)
            while thread.is_alive():
                time.sleep(0.5)
        else:
            try:
                import webview
                webview.create_window("Caption Studio", url, width=1480, height=940, min_size=(1080, 700), background_color="#101412")
                webview.start(gui="edgechromium", private_mode=True)
            except Exception as exc:
                print("Desktopové okno není dostupné; otevírám prohlížeč.", type(exc).__name__, flush=True)
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
