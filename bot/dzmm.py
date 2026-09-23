# -*- coding: utf-8 -*-
"""DZMM Bot 发消息（WispByte 出口，直连，不经 Cloudflare Pages）。"""
from __future__ import annotations

import threading
import time
import urllib.parse

from bot import config
from bot.http_util import http_json

_lock = threading.Lock()
_preferred: str = ""


def _bases() -> list[str]:
    """优先用上次成功的镜像，再试其余；可用环境变量 DZMM_API_BASE 指定首选。"""
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
            headers={
                "content-type": "application/json",
                "X-Bot-Token": token,
                "user-agent": "dzmm-wispbyte-test/1.0",
            },
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
        # 明确失败（鉴权/参数）别盲试完所有镜像拖时间
        if status in (401, 403, 404):
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
            headers={"content-type": "application/json", "user-agent": "dzmm-wispbyte-test/1.0"},
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
        if status in (401, 403, 404):
            break
    return {"ok": False, "error": last_err or "sendPhoto failed", "ms": int((time.time() - t0) * 1000)}
