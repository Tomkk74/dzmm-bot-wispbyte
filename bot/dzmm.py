# -*- coding: utf-8 -*-
"""DZMM Bot 发消息（Vultr 本机出网）。"""
from __future__ import annotations

import threading
import time
import urllib.parse

from bot import config
from bot.http_util import http_json

_lock = threading.Lock()
_preferred: str = ""

# Cloudflare 对自定义 UA 常回 1010；用浏览器头即可
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def _bases() -> list[str]:
    preferred = ""
    with _lock:
        preferred = _preferred
    env_base = ""
    try:
        import os

        env_base = (os.environ.get("DZMM_API_BASE") or "").strip().rstrip("/")
    except Exception:
        env_base = ""
    ordered: list[str] = []
    for b in (env_base, preferred, *config.API_BASES):
        if not b:
            continue
        b = b.rstrip("/")
        if b not in ordered:
            ordered.append(b)
    return ordered


def _remember(base: str) -> None:
    global _preferred
    with _lock:
        _preferred = base.rstrip("/")


def _headers(base: str, token: str | None = None) -> dict:
    h = {
        "content-type": "application/json",
        "user-agent": _UA,
        "accept": "application/json,text/plain,*/*",
        "origin": base,
        "referer": base.rstrip("/") + "/",
    }
    if token:
        h["X-Bot-Token"] = token
    return h


def send_text(chatroom_id: str, content: str) -> dict:
    token = config.DZMM_BOT_TOKEN
    text = str(content or "")[:10000]
    if not token or not chatroom_id:
        return {"ok": False, "error": "missing token/chat"}
    last_err = ""
    t0 = time.time()
    for base in _bases():
        status, data = http_json(
            "POST",
            base + "/api/bot/send-message",
            headers=_headers(base, token),
            body={"chatroom_id": chatroom_id, "content": text},
            timeout=8,
        )
        if status == 200 and data.get("ok") is True:
            mid = (data.get("result") or {}).get("message_id")
            _remember(base)
            ms = int((time.time() - t0) * 1000)
            print(f"send_text ok via={base} {ms}ms", flush=True)
            return {"ok": True, "messageId": mid, "via": base, "ms": ms}
        last_err = f"{base}:{status}:{str(data)[:80]}"
        # 1010/403 换下一个镜像；真鉴权失败也别死磕太久
        if status in (401, 404):
            break
    return {"ok": False, "error": last_err or "all bases failed", "ms": int((time.time() - t0) * 1000)}


def send_photo(chatroom_id: str, photo_url: str, caption: str = "") -> dict:
    token = config.DZMM_BOT_TOKEN
    if not token or not chatroom_id or not photo_url:
        return {"ok": False, "error": "missing"}
    body = {"chat_id": chatroom_id, "photo": photo_url}
    if caption:
        body["caption"] = caption[:1000]
    last_err = ""
    t0 = time.time()
    for base in _bases():
        status, data = http_json(
            "POST",
            base + "/api/bot/bot" + urllib.parse.quote(token, safe="") + "/sendPhoto",
            headers=_headers(base),
            body=body,
            timeout=12,
        )
        if status == 200 and (
            data.get("ok") is True
            or (isinstance(data.get("result"), dict) and data["result"].get("message_id"))
        ):
            _remember(base)
            ms = int((time.time() - t0) * 1000)
            print(f"send_photo ok via={base} {ms}ms", flush=True)
            return {"ok": True, "via": base, "ms": ms}
        last_err = f"{base}:{status}"
        if status in (401, 404):
            break
    return {"ok": False, "error": last_err or "sendPhoto failed", "ms": int((time.time() - t0) * 1000)}
