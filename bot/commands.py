# -*- coding: utf-8 -*-
from __future__ import annotations

import random
import re

from bot.draw import enqueue_draw, parse_draw_prompt
from bot.dzmm import send_text
from bot.llm import chat_completion
from bot import store


LOTS = ["⚔️ 先手", "🛡️ 后手", "😴 休息一下", "🔥 再来一局", "✨ 好运", "🌊 观望"]


def _wake_match(text: str, wake: str):
    raw = str(text or "").strip()
    for w in [x.strip() for x in str(wake or "").split(",") if x.strip()]:
        if raw.startswith(w):
            rest = raw[len(w) :].lstrip(" ，,：:")
            return rest or None
        if re.match(r"^[@＠]\S+[\s　]+", raw):
            # ignore @bot prefix somehow - skip
            pass
    return False  # False = not wake; None = wake but empty


def handle_message(update: dict) -> dict:
    message = (update or {}).get("message") or (update or {}).get("edited_message") or {}
    chat = message.get("chat") or {}
    chatroom_id = str(chat.get("id") or "")
    text = str(message.get("text") or "").strip()
    frm = message.get("from") or {}
    title = str(chat.get("title") or chat.get("username") or "")
    if not chatroom_id or not text or frm.get("is_bot"):
        return {"ok": True, "skipped": True}

    store.touch_group(chatroom_id, title)
    cfg = store.get_settings(chatroom_id)
    user_id = str(frm.get("id") or "")

    draw = parse_draw_prompt(text)
    if draw is not None:
        if not int(cfg.get("draw_enabled") or 0):
            send_text(chatroom_id, "🛑 本群已关闭生图（后台可开）")
            return {"ok": True, "draw": False, "disabled": True}
        if draw == "":
            send_text(chatroom_id, "🎨 用法：/画 雨中的红发少女\n✨ 必须是 /画 + 空格 + 描述")
            return {"ok": True, "command": "draw_usage"}
        enq = enqueue_draw(chatroom_id, user_id, draw, api_key=cfg.get("moenode_api_key") or "")
        if not enq.get("ok"):
            send_text(chatroom_id, f"💦 没排上队：{enq.get('error')}")
            return {"ok": True, "draw": False, "enq": enq}
        send_text(
            chatroom_id,
            "\n".join(
                [
                    "🎨✨ 已提交画图，排队出图中～" if enq.get("queuedAtMoe") else "🎨✨ 已记下，稍等出图～",
                    f"📝 {draw[:120]}{'…' if len(draw) > 120 else ''}",
                    "⏳ 大约 20～90 秒，画好会自动发图",
                ]
            ),
        )
        return {"ok": True, "draw": True, "enq": enq}

    raw = text.lstrip("/／")
    if re.match(r"^(帮助|菜单|help)$", raw, re.I):
        return {
            "ok": True,
            "command": "help",
            "sent": send_text(chatroom_id, cfg.get("help_text") or store.DEFAULT_HELP),
        }
    if re.match(r"^(你好|欢迎)$", raw):
        return {
            "ok": True,
            "command": "welcome",
            "sent": send_text(chatroom_id, cfg.get("welcome_text") or store.DEFAULT_WELCOME),
        }
    if re.match(r"^骰子$", raw):
        if not int(cfg.get("game_dice") or 0):
            send_text(chatroom_id, "🛑 本群已关闭骰子")
            return {"ok": True, "disabled": True}
        faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        n = random.randint(1, 6)
        return {
            "ok": True,
            "command": "dice",
            "sent": send_text(chatroom_id, f"{faces[n - 1]} 骰子：{n}"),
        }
    if re.match(r"^抽签$", raw):
        if not int(cfg.get("game_lot") or 0):
            send_text(chatroom_id, "🛑 本群已关闭抽签")
            return {"ok": True, "disabled": True}
        return {
            "ok": True,
            "command": "lot",
            "sent": send_text(chatroom_id, "🎋 " + random.choice(LOTS)),
        }
    if re.match(r"^ping$", raw, re.I):
        return {"ok": True, "command": "ping", "sent": send_text(chatroom_id, "pong ✅")}

    if re.match(r"^管理码$", raw):
        code = cfg.get("group_admin_code") or ""
        send_text(
            chatroom_id,
            "🔐 本群管理码（勿公开刷屏）\n"
            f"群 ID：{chatroom_id}\n"
            f"管理码：{code}\n"
            "后台地址：/admin/ （用「群管理码」登录）",
        )
        return {"ok": True, "command": "admin_code"}

    # 大模型
    if int(cfg.get("llm_enabled") or 0):
        woke = _wake_match(text, cfg.get("llm_wake") or "")
        if woke is not False:
            if not woke:
                send_text(chatroom_id, "💬 唤醒词后面写点内容～")
                return {"ok": True, "llm": "empty"}
            r = chat_completion(
                cfg.get("llm_base_url") or "",
                cfg.get("llm_api_key") or "",
                cfg.get("llm_model") or "",
                cfg.get("llm_system") or "",
                woke,
            )
            if not r.get("ok"):
                send_text(chatroom_id, f"💦 模型失败：{r.get('error')}")
            else:
                send_text(chatroom_id, r["text"][:4000])
            return {"ok": True, "llm": True, "result": r}

    return {"ok": True, "skipped": True, "reason": "no command"}
