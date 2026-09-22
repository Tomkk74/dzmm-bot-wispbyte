# -*- coding: utf-8 -*-
"""后台 API：登录、群列表、读写配置。"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from bot import config
from bot import store


def _json_body(handler) -> dict:
    try:
        n = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        n = 0
    if n <= 0:
        return {}
    raw = handler.rfile.read(n)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _bearer(handler) -> str:
    h = handler.headers.get("Authorization") or ""
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return handler.headers.get("X-Admin-Token") or ""


def _query(path: str) -> dict:
    return {k: (v[0] if v else "") for k, v in parse_qs(urlparse(path).query).items()}


def handle_admin(handler, method: str, path: str):
    """返回 (status, dict|None, static_path|None)。static_path 表示改走静态文件。"""
    pure = urlparse(path).path.rstrip("/") or "/"

    # 静态页
    if method == "GET" and pure in ("/admin", "/admin/"):
        return 200, None, "admin/index.html"
    if method == "GET" and pure.startswith("/admin/static/"):
        return 200, None, pure[len("/admin/") :]  # static/...

    if not pure.startswith("/admin/api"):
        return 404, {"ok": False, "error": "not found"}, None

    # POST /admin/api/login
    if method == "POST" and pure == "/admin/api/login":
        body = _json_body(handler)
        mode = str(body.get("mode") or "master")
        if mode == "master":
            pw = str(body.get("password") or "")
            if not config.ADMIN_PASSWORD:
                return 500, {"ok": False, "error": "未配置 ADMIN_PASSWORD"}, None
            if pw != config.ADMIN_PASSWORD:
                return 401, {"ok": False, "error": "密码错误"}, None
            token = store.create_session("master")
            return 200, {"ok": True, "token": token, "scope": "master"}, None
        # 群管理码
        chatroom_id = str(body.get("chatroom_id") or "").strip()
        code = str(body.get("code") or "").strip()
        if not chatroom_id or not code:
            return 400, {"ok": False, "error": "需要群 ID 与管理码"}, None
        s = store.get_settings(chatroom_id)
        if not s.get("group_admin_code") or s["group_admin_code"] != code:
            return 401, {"ok": False, "error": "管理码错误"}, None
        token = store.create_session("group", chatroom_id)
        return 200, {"ok": True, "token": token, "scope": "group", "chatroom_id": chatroom_id}, None

    if method == "POST" and pure == "/admin/api/logout":
        store.delete_session(_bearer(handler))
        return 200, {"ok": True}, None

    sess = store.get_session(_bearer(handler))
    if not sess:
        return 401, {"ok": False, "error": "未登录"}, None

    if method == "GET" and pure == "/admin/api/me":
        return 200, {"ok": True, "scope": sess["scope"], "chatroom_id": sess.get("chatroom_id")}, None

    if method == "GET" and pure == "/admin/api/groups":
        if sess["scope"] != "master":
            cid = sess.get("chatroom_id")
            g = [x for x in store.list_groups() if x["chatroom_id"] == cid]
            return 200, {"ok": True, "groups": g}, None
        return 200, {"ok": True, "groups": store.list_groups()}, None

    if method == "GET" and pure == "/admin/api/settings":
        q = _query(path)
        cid = q.get("chatroom_id") or sess.get("chatroom_id") or ""
        if not cid:
            return 400, {"ok": False, "error": "缺少 chatroom_id"}, None
        if sess["scope"] == "group" and sess.get("chatroom_id") != cid:
            return 403, {"ok": False, "error": "无权查看其它群"}, None
        return 200, {"ok": True, "settings": store.public_settings(cid)}, None

    if method == "POST" and pure == "/admin/api/settings":
        body = _json_body(handler)
        cid = str(body.get("chatroom_id") or sess.get("chatroom_id") or "").strip()
        if not cid:
            return 400, {"ok": False, "error": "缺少 chatroom_id"}, None
        if sess["scope"] == "group" and sess.get("chatroom_id") != cid:
            return 403, {"ok": False, "error": "无权修改其它群"}, None
        patch = dict(body.get("settings") or {})
        # 密钥字段由前端传 __KEEP__ / __CLEAR__ / 新值；save_settings 内处理
        if sess["scope"] != "master":
            patch.pop("group_admin_code", None)
        store.save_settings(cid, patch)
        return 200, {"ok": True, "settings": store.public_settings(cid)}, None

    if method == "POST" and pure == "/admin/api/rotate-code":
        if sess["scope"] != "master":
            return 403, {"ok": False, "error": "仅总管理可重置管理码"}, None
        body = _json_body(handler)
        cid = str(body.get("chatroom_id") or "").strip()
        if not cid:
            return 400, {"ok": False, "error": "缺少 chatroom_id"}, None
        code = store.rotate_group_code(cid)
        return 200, {"ok": True, "group_admin_code": code}, None

    return 404, {"ok": False, "error": "unknown api"}, None
