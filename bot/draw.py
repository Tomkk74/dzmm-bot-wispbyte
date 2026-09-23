# -*- coding: utf-8 -*-
"""MoeNode 生图 · 本地 SQLite 队列 · 成品存本地 data/img · 本机 /img 公开。"""
from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path

from bot import config
from bot import store
from bot.dzmm import send_photo, send_text
from bot.http_util import http_bytes, http_json


def _key_for_chat(chatroom_id: str) -> str:
    s = store.get_settings(chatroom_id)
    return (s.get("moenode_api_key") or config.MOENODE_API_KEY or "").strip()

DATA = Path(__file__).resolve().parents[1] / "data"
IMG_DIR = DATA / "img"
_lock = threading.Lock()
MOE_BASES = ["https://moenode.app", "https://www.moenode.app"]


def _db() -> sqlite3.Connection:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    return store.connect()


def parse_draw_prompt(text: str):
    raw = str(text or "").strip()
    import re

    m = re.match(r"^[／/]画[\s　]+([\s\S]+)$", raw)
    if not m:
        if re.match(r"^[／/]画[\s　]*$", raw):
            return ""
        return None
    prompt = m.group(1).strip()
    return prompt[:4000] if prompt else ""


def enqueue_draw(chatroom_id: str, user_id: str, prompt: str, api_key: str = "") -> dict:
    key = (api_key or config.MOENODE_API_KEY or "").strip()
    if not key:
        return {"ok": False, "error": "跑图密钥还没配（后台填写 MoeNode Key）"}
    text = str(prompt or "").strip()[:4000]
    if not text:
        return {"ok": False, "error": "提示词是空的"}
    now = int(time.time())
    job_id = str(uuid.uuid4())
    # 先看队列，再在锁外调 Moe（避免长请求占库）
    with _lock:
        conn = _db()
        try:
            active = conn.execute(
                "SELECT COUNT(*) AS n FROM draw_jobs WHERE status IN ('queued','running') AND moe_job_id IS NOT NULL"
            ).fetchone()["n"]
            can_submit = int(active or 0) == 0
        finally:
            conn.close()

    moe_job_id = None
    status = "pending"
    if can_submit:
        enq = moe_fetch(
            "/api/v1/generate",
            "POST",
            {"prompt": text, "modelId": "anima-turbo", "imageSize": "anima_832_1216"},
            key=key,
        )
        if enq.get("status") == 402:
            return {"ok": False, "error": "积分不够了"}
        data = enq.get("data") or {}
        if enq.get("ok") and data.get("jobId"):
            moe_job_id = str(data["jobId"])
            status = "queued"

    with _lock:
        conn = _db()
        try:
            conn.execute(
                """INSERT INTO draw_jobs(id, chatroom_id, user_id, prompt, moe_job_id, status, image_url, error, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,NULL,NULL,?,?)""",
                (job_id, chatroom_id, user_id or None, text, moe_job_id, status, now, now),
            )
            conn.commit()
        finally:
            conn.close()
    return {"ok": True, "id": job_id, "queuedAtMoe": bool(moe_job_id)}


def moe_fetch(path: str, method: str = "GET", body: dict | None = None, key: str = ""):
    api_key = (key or config.MOENODE_API_KEY or "").strip()
    last = {}
    for base in MOE_BASES:
        status, data = http_json(
            method,
            base + path,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            body=body,
            timeout=60,
        )
        last = {"status": status, "data": data, "ok": status == 200}
        if status and status < 500:
            return last
    return last


def serve_image(name: str):
    safe = Path(name).name
    path = IMG_DIR / safe
    if not path.is_file():
        return None, ""
    data = path.read_bytes()
    ct = "image/png"
    if safe.endswith(".webp"):
        ct = "image/webp"
    elif safe.endswith(".jpg") or safe.endswith(".jpeg"):
        ct = "image/jpeg"
    return data, ct


def _finalize(row: sqlite3.Row) -> bool:
    moe_id = row["moe_job_id"]
    if not moe_id:
        return False
    key = _key_for_chat(row["chatroom_id"])
    poll = moe_fetch(f"/api/v1/jobs/{moe_id}", "GET", key=key)
    data = poll.get("data") or {}
    st = data.get("status")
    if st in ("queued", "running"):
        return False
    if st == "error" or poll.get("status") == 402:
        with _lock:
            conn = _db()
            conn.execute(
                "UPDATE draw_jobs SET status='error', error=?, updated_at=? WHERE id=?",
                [str(data.get("error") or "failed"), int(time.time()), row["id"]],
            )
            conn.commit()
            conn.close()
        send_text(row["chatroom_id"], f"💦 画失败了：{data.get('error') or '未知错误'}")
        return True
    if st != "ok":
        return False
    image_id = data.get("id") or ""
    image_url = data.get("imageUrl") or (f"https://moenode.app/api/images/{image_id}.png" if image_id else "")
    if not image_url:
        return False
    try:
        _status, raw, ct = http_bytes(
            "GET",
            image_url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=90,
        )
    except Exception as e:
        print("download fail", e, flush=True)
        return False
    ext = "png"
    if "webp" in (ct or ""):
        ext = "webp"
    elif "jpeg" in (ct or "") or "jpg" in (ct or ""):
        ext = "jpg"
    fname = f"draw-{row['id']}.{ext}"
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    (IMG_DIR / fname).write_bytes(raw)
    public = config.public_base().rstrip("/") + "/img/" + fname
    with _lock:
        conn = _db()
        conn.execute(
            "UPDATE draw_jobs SET status='done', image_url=?, updated_at=? WHERE id=?",
            [public, int(time.time()), row["id"]],
        )
        conn.commit()
        conn.close()
    cap = f"🎨 {str(row['prompt'])[:80]}"
    sent = send_photo(row["chatroom_id"], public, cap)
    if not sent.get("ok"):
        send_text(row["chatroom_id"], f"图好了但贴图失败，点开看：{public}")
    return True


def tick_once() -> dict:
    pending = None
    rows = []
    with _lock:
        conn = _db()
        try:
            pending = conn.execute(
                "SELECT id, prompt, chatroom_id FROM draw_jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            active = conn.execute(
                "SELECT COUNT(*) AS n FROM draw_jobs WHERE status IN ('queued','running') AND moe_job_id IS NOT NULL"
            ).fetchone()["n"]
            can_submit = pending is not None and int(active or 0) == 0
            if pending and can_submit:
                pending = dict(pending)
            else:
                pending = None
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM draw_jobs WHERE status IN ('queued','running') AND moe_job_id IS NOT NULL ORDER BY created_at ASC LIMIT 5"
                ).fetchall()
            ]
        finally:
            conn.close()

    if pending:
        key = _key_for_chat(pending["chatroom_id"])
        if key:
            enq = moe_fetch(
                "/api/v1/generate",
                "POST",
                {
                    "prompt": pending["prompt"],
                    "modelId": "anima-turbo",
                    "imageSize": "anima_832_1216",
                },
                key=key,
            )
            data = enq.get("data") or {}
            if enq.get("ok") and data.get("jobId"):
                with _lock:
                    conn = _db()
                    try:
                        conn.execute(
                            "UPDATE draw_jobs SET status='queued', moe_job_id=?, updated_at=? WHERE id=? AND status='pending'",
                            [str(data["jobId"]), int(time.time()), pending["id"]],
                        )
                        conn.commit()
                    finally:
                        conn.close()

    done = 0
    for row in rows:
        # sqlite3.Row 兼容：_finalize 用下标访问
        class _R:
            def __getitem__(self, k):
                return row[k]

        if _finalize(_R()):
            done += 1
    return {"ok": True, "done": done}


def draw_worker_loop():
    while True:
        try:
            tick_once()
        except Exception as e:
            print("draw tick", e, flush=True)
        time.sleep(2)
