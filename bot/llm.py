# -*- coding: utf-8 -*-
"""OpenAI 兼容对话。"""
from __future__ import annotations

from bot.http_util import http_json


def chat_completion(base_url: str, api_key: str, model: str, system: str, user_text: str) -> dict:
    base = (base_url or "").rstrip("/")
    if not base or not api_key or not model:
        return {"ok": False, "error": "大模型未配置完整"}
    url = base + "/chat/completions"
    status, data = http_json(
        "POST",
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        body={
            "model": model,
            "messages": [
                {"role": "system", "content": system or "你是助手。"},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.8,
        },
        timeout=90,
    )
    if status != 200:
        err = (data or {}).get("error")
        if isinstance(err, dict):
            err = err.get("message") or err
        return {"ok": False, "error": str(err or data or status)}
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        return {"ok": False, "error": "模型返回异常"}
    return {"ok": True, "text": str(text).strip()}
