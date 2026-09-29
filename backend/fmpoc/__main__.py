"""Launcher for local and server modes (docs/06 §7).

    fmpoc [--mode local|server] [--host HOST] [--port PORT] [--data-dir DIR] [--no-browser]

Local mode binds to 127.0.0.1, applies migrations, waits for /api/health and opens the default browser.
Server mode binds to the configured interface; plain-HTTP network exposure logs a prominent warning.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import urllib.request
import webbrowser

from .config import VERSION, is_loopback, load_settings


def _open_browser_when_ready(url: str) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1) as r:  # noqa: S310 - fixed loopback URL
                if r.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            time.sleep(0.25)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fmpoc", description="Financial Management POC")
    p.add_argument("--mode", choices=["local", "server"])
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--data-dir")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--version", action="store_true")
    a = p.parse_args(argv)
    if a.version:
        print(VERSION)
        return 0
    overrides = {"mode": a.mode, "host": a.host, "port": a.port, "data_dir": a.data_dir}
    if a.no_browser:
        overrides["open_browser"] = False
    settings = load_settings(overrides)
    if settings.mode == "local" and not is_loopback(settings.host):
        print("WARNING: local mode is intended for loopback only; binding to", settings.host, file=sys.stderr)
    if settings.mode == "server" and not is_loopback(settings.host) and settings.secure_cookies != "true":
        print("\n" + "!" * 78 + "\n SECURITY WARNING: serving on a network interface over plain HTTP.\n"
              " This is NOT secure for authenticated use. Place the application behind an HTTPS reverse\n"
              " proxy (Caddy/nginx/Apache) and set FM_SECURE_COOKIES=true.\n" + "!" * 78 + "\n", file=sys.stderr)

    import uvicorn

    from .app import create_app

    app = create_app(settings)
    url = f"http://{'127.0.0.1' if settings.host in ('0.0.0.0', '::') else settings.host}:{settings.port}"
    print(f"Financial Management POC {VERSION} - {settings.mode} mode - {url}")
    print(f"Application data: {settings.data_dir}")
    if settings.mode == "local" and settings.open_browser:
        threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()
    trusted = settings.trusted_proxies.strip()
    uvicorn.run(app, host=settings.host, port=settings.port, access_log=False, server_header=False,
                proxy_headers=bool(trusted), forwarded_allow_ips=trusted or None, log_config=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
