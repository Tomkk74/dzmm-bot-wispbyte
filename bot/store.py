# -*- coding: utf-8 -*-
"""SQLite：群配置 / 会话 / 出现过的群。"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA / "bot.sqlite"

DEFAULT_WELCOME = "\n".join(
    [
        "🎊 欢迎～",
        "🤖 我是群里的智能机器人",
        "",
        "发「帮助」看指令",
        "生图：/画 + 空格 + 描述",
    ]
)

DEFAULT_HELP = "\n".join(
    [
        "🤖 群机器人",
        "",
        "帮助 —— 本说明",
        "骰子 / 抽签 —— 小游戏（可在后台关闭）",
        "/画 + 空格 + 描述 —— 生图（需配置跑图密钥）",
        "唤醒词 + 内容 —— 大模型对话（需配置）",
        "",
        "后台由群主在网页配置欢迎词、开关与密钥",
    ]
)

DEFAULTS = {
    "welcome_text": DEFAULT_WELCOME,
    "help_text": DEFAULT_HELP,
    "game_dice": 1,
    "game_lot": 1,
    "draw_enabled": 1,
    "moenode_api_key": "",
    "llm_enabled": 0,
    "llm_base_url": "https://api.openai.com/v1",
    "llm_api_key": "",
    "llm_model": "gpt-4o-mini",
    "llm_system": "你是群聊助手，口语、简短、有用。",
    "llm_wake": "小哈,助手",
    "title": "",
    "group_admin_code": "",
}


def connect() -> sqlite3.Connection:
    """多线程安全：WAL + busy_timeout，避免 draw tick / webhook 互锁。"""
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS groups (
              chatroom_id TEXT PRIMARY KEY,
              title TEXT,
              first_seen INTEGER NOT NULL,
              last_seen INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS group_settings (
              chatroom_id TEXT PRIMARY KEY,
              data_json TEXT NOT NULL,
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admin_sessions (
              token TEXT PRIMARY KEY,
              scope TEXT NOT NULL,
              chatroom_id TEXT,
              created_at INTEGER NOT NULL,
              expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS draw_jobs (
              id TEXT PRIMARY KEY,
              chatroom_id TEXT NOT NULL,
              user_id TEXT,
              prompt TEXT NOT NULL,
              moe_job_id TEXT,
              status TEXT NOT NULL,
              image_url TEXT,
              error TEXT,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def touch_group(chatroom_id: str, title: str = "") -> None:
    if not chatroom_id:
        return
    now = int(time.time())
    conn = connect()
    row = conn.execute("SELECT chatroom_id FROM groups WHERE chatroom_id=?", [chatroom_id]).fetchone()
    if row:
        conn.execute(
            "UPDATE groups SET last_seen=?, title=COALESCE(NULLIF(?,''), title) WHERE chatroom_id=?",
            [now, title or "", chatroom_id],
        )
    else:
        conn.execute(
            "INSERT INTO groups(chatroom_id, title, first_seen, last_seen) VALUES(?,?,?,?)",
            [chatroom_id, title or "", now, now],
        )
        # 新群自动生成管理码
        settings = dict(DEFAULTS)
        settings["group_admin_code"] = secrets.token_hex(4)
        if title:
            settings["title"] = title
        conn.execute(
            "INSERT OR IGNORE INTO group_settings(chatroom_id, data_json, updated_at) VALUES(?,?,?)",
            [chatroom_id, json.dumps(settings, ensure_ascii=False), now],
        )
    conn.commit()
    conn.close()


def list_groups() -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT chatroom_id, title, first_seen, last_seen FROM groups ORDER BY last_seen DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_settings(chatroom_id: str) -> dict:
    conn = connect()
    row = conn.execute(
        "SELECT data_json FROM group_settings WHERE chatroom_id=?", [chatroom_id]
    ).fetchone()
    conn.close()
    data = dict(DEFAULTS)
    if row and row["data_json"]:
        try:
            data.update(json.loads(row["data_json"]))
        except json.JSONDecodeError:
            pass
    data["chatroom_id"] = chatroom_id
    return data


def save_settings(chatroom_id: str, patch: dict) -> dict:
    cur = get_settings(chatroom_id)
    allowed = set(DEFAULTS.keys()) | {"title"}
    for k, v in (patch or {}).items():
        if k not in allowed:
            continue
        if k in ("moenode_api_key", "llm_api_key"):
            if v == "__KEEP__":
                continue
            if v == "__CLEAR__":
                cur[k] = ""
                continue
            cur[k] = str(v)
            continue
        if k in ("game_dice", "game_lot", "draw_enabled", "llm_enabled"):
            cur[k] = 1 if v in (1, True, "1", "true", "on", "yes") else 0
        else:
            cur[k] = "" if v is None else str(v)
    now = int(time.time())
    conn = connect()
    conn.execute(
        """INSERT INTO group_settings(chatroom_id, data_json, updated_at) VALUES(?,?,?)
           ON CONFLICT(chatroom_id) DO UPDATE SET data_json=excluded.data_json, updated_at=excluded.updated_at""",
        [chatroom_id, json.dumps(cur, ensure_ascii=False), now],
    )
    if cur.get("title"):
        conn.execute("UPDATE groups SET title=? WHERE chatroom_id=?", [cur["title"], chatroom_id])
    conn.commit()
    conn.close()
    return cur


def public_settings(chatroom_id: str) -> dict:
    """给后台展示：密钥只回是否已配置。"""
    s = get_settings(chatroom_id)
    out = dict(s)
    out["moenode_api_key_set"] = bool(str(s.get("moenode_api_key") or "").strip())
    out["llm_api_key_set"] = bool(str(s.get("llm_api_key") or "").strip())
    out["moenode_api_key"] = ""
    out["llm_api_key"] = ""
    return out


def hash_password(pw: str) -> str:
    return hashlib.sha256(("dzmm-admin:" + str(pw)).encode("utf-8")).hexdigest()


def create_session(scope: str, chatroom_id: str | None = None, ttl: int = 86400 * 7) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn = connect()
    conn.execute(
        "INSERT INTO admin_sessions(token, scope, chatroom_id, created_at, expires_at) VALUES(?,?,?,?,?)",
        [token, scope, chatroom_id, now, now + ttl],
    )
    conn.commit()
    conn.close()
    return token


def get_session(token: str) -> dict | None:
    if not token:
        return None
    now = int(time.time())
    conn = connect()
    row = conn.execute(
        "SELECT token, scope, chatroom_id, expires_at FROM admin_sessions WHERE token=?",
        [token],
    ).fetchone()
    if not row or int(row["expires_at"]) < now:
        if row:
            conn.execute("DELETE FROM admin_sessions WHERE token=?", [token])
            conn.commit()
        conn.close()
        return None
    conn.close()
    return dict(row)


def delete_session(token: str) -> None:
    conn = connect()
    conn.execute("DELETE FROM admin_sessions WHERE token=?", [token])
    conn.commit()
    conn.close()


def rotate_group_code(chatroom_id: str) -> str:
    code = secrets.token_hex(4)
    save_settings(chatroom_id, {"group_admin_code": code})
    return code
