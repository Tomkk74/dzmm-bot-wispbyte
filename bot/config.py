# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DZMM_BOT_TOKEN = ""
DZMM_BOT_SECRET = ""
MOENODE_API_KEY = ""
ADMIN_PASSWORD = ""
PUBLIC_BASE = ""
PORT = 3000

API_BASES = [
    "https://www.aifukk.com",
    "https://www.fuckaibot.com",
    "https://www.thottai.com",
    "https://www.dzmm.ai",
    "https://www.dzmm.io",
]


def _load_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if not k:
            continue
        cur = os.environ.get(k, "")
        if not str(cur).strip():
            os.environ[k] = v


def load() -> None:
    global DZMM_BOT_TOKEN, DZMM_BOT_SECRET, MOENODE_API_KEY, ADMIN_PASSWORD, PUBLIC_BASE, PORT
    for name in ("env.txt", ".env"):
        _load_file(ROOT / name)
    DZMM_BOT_TOKEN = os.environ.get("DZMM_BOT_TOKEN", "").strip()
    DZMM_BOT_SECRET = os.environ.get("DZMM_BOT_SECRET", "").strip()
    MOENODE_API_KEY = os.environ.get("MOENODE_API_KEY", "").strip()
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
    PUBLIC_BASE = os.environ.get("PUBLIC_BASE", "").strip().rstrip("/")
    try:
        PORT = int(os.environ.get("PORT") or os.environ.get("SERVER_PORT") or "3000")
    except ValueError:
        PORT = 3000


def public_base() -> str:
    if PUBLIC_BASE:
        return PUBLIC_BASE
    return f"http://127.0.0.1:{PORT}"
