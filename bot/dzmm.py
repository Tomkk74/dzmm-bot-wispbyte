# -*- coding: utf-8 -*-
"""DZMM Bot 发消息（WispByte 出口，直连，不经 Cloudflare Pages）。"""
from __future__ import annotations

import urllib.parse

from bot import config
from bot.http_util import http_json


def send_text(chatroom_id: str, content: str) -> dict:
    token = config.DZMM_BOT_TOKEN
    text = str(content or "")[:10000]
    if not token or not chatroom_id:
        return {"ok": False, "error": "missing token/chat"}
    for base in config.API_BASES:
        status, data = http_json(
            "POST",
            base + "/api/bot/send-message",
            headers={
                "content-type": "application/json",
                "X-Bot-Token": token,
                "user-agent": "dzmm-wispbyte-test/1.0",
            },
            body={"chatroom_id": chatroom_id, "content": text},
            timeout=25,
        )
        if status == 200 and data.get("ok") is True:
            mid = (data.get("result") or {}).get("message_id")
            return {"ok": True, "messageId": mid, "via": base}
    return {"ok": False, "error": "all bases failed"}


def send_photo(chatroom_id: str, photo_url: str, caption: str = "") -> dict:
    token = config.DZMM_BOT_TOKEN
    if not token or not chatroom_id or not photo_url:
        return {"ok": False, "error": "missing"}
    body = {"chat_id": chatroom_id, "photo": photo_url}
    if caption:
        body["caption"] = caption[:1000]
    for base in config.API_BASES:
        status, data = http_json(
            "POST",
            base + "/api/bot/bot" + urllib.parse.quote(token, safe="") + "/sendPhoto",
            headers={"content-type": "application/json", "user-agent": "dzmm-wispbyte-test/1.0"},
            body=body,
            timeout=25,
        )
        if status == 200 and (
            data.get("ok") is True
            or (isinstance(data.get("result"), dict) and data["result"].get("message_id"))
        ):
            return {"ok": True, "via": base}
    return {"ok": False, "error": "sendPhoto failed"}
