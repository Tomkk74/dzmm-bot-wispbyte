#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZMM 新机器人 · WispByte 测试版（Python）
后台：/admin/
"""
from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from bot import config
from bot import store
from bot.admin_api import handle_admin
from bot.commands import handle_message
from bot.draw import draw_worker_loop, serve_image

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)

    def _read_json(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _json(self, code: int, obj: dict):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _bytes(self, code: int, data: bytes, content_type: str):
        self.send_response(code)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(data)))
        self.send_header("cache-control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, rel: str):
        path = (STATIC / rel).resolve()
        if not str(path).startswith(str(STATIC.resolve())) or not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        ct = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if path.suffix == ".html":
            ct = "text/html; charset=utf-8"
        elif path.suffix == ".css":
            ct = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            ct = "application/javascript; charset=utf-8"
        self._bytes(200, data, ct)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/admin"):
            code, payload, static_rel = handle_admin(self, "GET", self.path)
            if static_rel:
                self._file(static_rel)
                return
            if payload is not None:
                self._json(code, payload)
                return
            self.send_error(code)
            return

        if path in ("/", "/health"):
            self._json(
                200,
                {
                    "ok": True,
                    "bot": "dzmm-wispbyte-test",
                    "hint": "POST /webhook · GET /admin/",
                    "token": bool(config.DZMM_BOT_TOKEN),
                    "secret": bool(config.DZMM_BOT_SECRET),
                    "admin": bool(config.ADMIN_PASSWORD),
                    "publicBase": config.public_base(),
                },
            )
            return
        if path == "/webhook":
            self._json(200, {"ok": True, "hint": "POST webhook"})
            return
        if path.startswith("/img/"):
            name = unquote(path[len("/img/") :])
            data, ct = serve_image(name)
            if not data:
                self.send_error(404)
                return
            self._bytes(200, data, ct)
            return
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/admin"):
            code, payload, _static = handle_admin(self, "POST", self.path)
            self._json(code, payload or {"ok": False})
            return

        if path not in ("/webhook", "/"):
            self.send_error(404)
            return
        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token") or ""
        if config.DZMM_BOT_SECRET and secret != config.DZMM_BOT_SECRET:
            self.send_error(401, "unauthorized")
            return
        update = self._read_json()
        try:
            result = handle_message(update)
        except Exception as e:
            print("handle error", e, flush=True)
            result = {"ok": False, "error": str(e)}
        self._json(200, result if isinstance(result, dict) else {"ok": True})


def main():
    config.load()
    store.init_db()
    print(
        "dzmm-wispbyte-test listening",
        config.PORT,
        {
            "token": bool(config.DZMM_BOT_TOKEN),
            "secret": bool(config.DZMM_BOT_SECRET),
            "admin": bool(config.ADMIN_PASSWORD),
            "publicBase": config.public_base(),
            "adminUrl": config.public_base().rstrip("/") + "/admin/",
        },
        flush=True,
    )
    threading.Thread(target=draw_worker_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", config.PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
