# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import urllib.error
import urllib.request


def http_json(method: str, url: str, headers: dict | None = None, body: dict | None = None, timeout: int = 25):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("content-type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"_raw": raw[:400]}
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"_raw": raw[:400]}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}


def http_bytes(method: str, url: str, headers: dict | None = None, timeout: int = 60):
    req = urllib.request.Request(url, headers=dict(headers or {}), method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read(), resp.headers.get("content-type") or "application/octet-stream"
