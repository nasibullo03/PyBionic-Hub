"""AI Assistant — Telegram-бот с ИИ (Google Gemini или любой OpenAI-совместимый API).

Возможности:
- обычный чат с памятью последних сообщений (/new — начать заново);
- голосовые сообщения: расшифровка и ответ (Gemini);
- фото: описание, распознавание текста, ответ на вопрос из подписи (Gemini);
- быстрые режимы: перевод, краткий пересказ, исправление текста;
- дневной лимит запросов на пользователя, доступ по ALLOWED_USER_IDS.

Переменные (.env / секреты PyBionic):
    BOT_TOKEN          — токен Telegram-бота
    AI_API_KEY         — ключ Gemini (aistudio.google.com) или OpenAI-совместимого сервиса
    AI_PROVIDER        — gemini (по умолчанию) | openai
    AI_MODEL           — gemini-2.5-flash по умолчанию
    AI_BASE_URL        — для openai-совместимых (Groq, OpenRouter...), напр. https://api.groq.com/openai/v1
    SYSTEM_PROMPT      — характер бота
    DAILY_LIMIT        — запросов в день на человека (0 = без лимита), по умолчанию 100
    HISTORY_SIZE       — сколько последних сообщений помнить, по умолчанию 12
    ALLOWED_USER_IDS   — кому можно пользоваться (пусто = всем)
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import date
from typing import Any

import pybionic_core as core
from i18n import build_reply_language_keyboard, log, parse_lang_choice, set_user_lang, t

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
AI_API_KEY = os.environ.get("AI_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
AI_PROVIDER = (os.environ.get("AI_PROVIDER", "gemini").strip() or "gemini").lower()
AI_MODEL = os.environ.get("AI_MODEL", "").strip() or ("gemini-2.5-flash" if AI_PROVIDER == "gemini" else "llama-3.3-70b-versatile")
AI_BASE_URL = (os.environ.get("AI_BASE_URL", "").strip() or "https://api.groq.com/openai/v1").rstrip("/")
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "").strip() or (
    "You are a helpful, friendly assistant in Telegram. Answer in the user's language, "
    "briefly and clearly. Use plain text without Markdown tables."
)
DAILY_LIMIT = core.env_int("DAILY_LIMIT", 100, 0, 100000)
HISTORY_SIZE = core.env_int("HISTORY_SIZE", 12, 0, 60)
TG_MAX = 4000

DB_PATH = core.get_data_dir() / "ai_assistant.db"
_db_lock = threading.Lock()

MODES = {
    "btn_mode_chat": "chat",
    "btn_mode_translate": "translate",
    "btn_mode_summary": "summary",
    "btn_mode_fix": "fix",
}
MODE_PROMPTS = {
    "translate": "Translate the user's text. If it is in Russian, translate to English; otherwise translate to Russian. "
                 "If the user names a target language at the start (e.g. 'to Tajik:'), use it. Output only the translation.",
    "summary": "Summarize the user's text in 3-7 short bullet points in the same language as the text.",
    "fix": "Fix spelling, grammar and punctuation of the user's text, keep its language and meaning. Output only the fixed text.",
}


# ---------------------------------------------------------------------------
# База
# ---------------------------------------------------------------------------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS history (user_id INTEGER, role TEXT, text TEXT, ts INTEGER)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hist_user ON history(user_id, ts)")
    conn.execute("CREATE TABLE IF NOT EXISTS usage (user_id INTEGER, day TEXT, count INTEGER, PRIMARY KEY(user_id, day))")
    conn.execute("CREATE TABLE IF NOT EXISTS modes (user_id INTEGER PRIMARY KEY, mode TEXT)")
    return conn


def get_history(uid: int) -> list[tuple[str, str]]:
    if HISTORY_SIZE <= 0:
        return []
    with _db_lock, db() as c:
        rows = c.execute(
            "SELECT role, text FROM history WHERE user_id=? ORDER BY ts DESC, rowid DESC LIMIT ?", (uid, HISTORY_SIZE)
        ).fetchall()
    return list(reversed(rows))


def add_history(uid: int, role: str, text: str) -> None:
    with _db_lock, db() as c:
        c.execute("INSERT INTO history VALUES (?,?,?,?)", (uid, role, text[:8000], int(time.time() * 1000)))
        # храним не больше 200 сообщений на человека
        c.execute(
            "DELETE FROM history WHERE user_id=? AND rowid NOT IN "
            "(SELECT rowid FROM history WHERE user_id=? ORDER BY ts DESC LIMIT 200)", (uid, uid)
        )


def clear_history(uid: int) -> None:
    with _db_lock, db() as c:
        c.execute("DELETE FROM history WHERE user_id=?", (uid,))


def take_quota(uid: int) -> bool:
    """Списывает один запрос. False — лимит на сегодня исчерпан."""
    if DAILY_LIMIT <= 0:
        return True
    day = date.today().isoformat()
    with _db_lock, db() as c:
        row = c.execute("SELECT count FROM usage WHERE user_id=? AND day=?", (uid, day)).fetchone()
        used = row[0] if row else 0
        if used >= DAILY_LIMIT:
            return False
        c.execute("INSERT OR REPLACE INTO usage VALUES (?,?,?)", (uid, day, used + 1))
        c.execute("DELETE FROM usage WHERE day < ?", (day,))
    return True


def get_mode(uid: int) -> str:
    with _db_lock, db() as c:
        row = c.execute("SELECT mode FROM modes WHERE user_id=?", (uid,)).fetchone()
    return row[0] if row else "chat"


def set_mode(uid: int, mode: str) -> None:
    with _db_lock, db() as c:
        c.execute("INSERT OR REPLACE INTO modes VALUES (?,?)", (uid, mode))


# ---------------------------------------------------------------------------
# ИИ
# ---------------------------------------------------------------------------
class AIError(Exception):
    pass


def _post_json(url: str, payload: dict, headers: dict[str, str], timeout: int = 90) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        if e.code == 429:
            raise AIError("429: слишком много запросов к ИИ, подождите минуту / rate limit") from e
        if e.code in (401, 403):
            raise AIError(f"{e.code}: неверный AI_API_KEY / invalid key") from e
        raise AIError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise AIError(f"Нет связи с ИИ / network error: {e.reason}") from e


def ask_ai(history: list[tuple[str, str]], text: str, system: str,
           media: tuple[str, bytes] | None = None) -> str:
    """history: [(role, text)], role = user|model. media = (mime, bytes) — только Gemini."""
    if not AI_API_KEY:
        raise AIError("AI_API_KEY не задан / AI_API_KEY is empty")
    if AI_PROVIDER == "gemini":
        contents = [{"role": r, "parts": [{"text": x}]} for r, x in history]
        parts: list[dict[str, Any]] = []
        if media:
            parts.append({"inline_data": {"mime_type": media[0], "data": base64.b64encode(media[1]).decode()}})
        parts.append({"text": text})
        contents.append({"role": "user", "parts": parts})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{AI_MODEL}:generateContent"
        data = _post_json(url, {"contents": contents, "systemInstruction": {"parts": [{"text": system}]}},
                          {"x-goog-api-key": AI_API_KEY})
        try:
            cand = data["candidates"][0]
            out = "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()
        except (KeyError, IndexError):
            reason = (data.get("promptFeedback") or {}).get("blockReason") or json.dumps(data)[:200]
            raise AIError(f"Пустой ответ ИИ / empty answer: {reason}") from None
        return out or "…"
    # OpenAI-совместимый (Groq, OpenRouter, LM Studio ...)
    if media:
        raise AIError("Голос и фото работают только с AI_PROVIDER=gemini")
    msgs = [{"role": "system", "content": system}]
    msgs += [{"role": "assistant" if r == "model" else "user", "content": x} for r, x in history]
    msgs.append({"role": "user", "content": text})
    data = _post_json(f"{AI_BASE_URL}/chat/completions", {"model": AI_MODEL, "messages": msgs},
                      {"Authorization": f"Bearer {AI_API_KEY}"})
    try:
        return (data["choices"][0]["message"]["content"] or "").strip() or "…"
    except (KeyError, IndexError):
        raise AIError(f"Пустой ответ ИИ / empty answer: {json.dumps(data)[:200]}") from None


def split_text(text: str, limit: int = TG_MAX) -> list[str]:
    out = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        out.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        out.append(text)
    return out


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def main() -> None:
    if not BOT_TOKEN:
        log("err_missing_token")
        return
    import telebot
    from telebot import types

    bot = telebot.TeleBot(BOT_TOKEN)
    core.guard_bot(bot)
    me = core.call_with_retry(bot.get_me)

    def addressed(msg: Any) -> bool:
        """В личке — всегда. В группе — только @упоминание или ответ на сообщение бота."""
        if msg.chat.type == "private":
            return True
        text = (msg.text or msg.caption or "").lower()
        rep = msg.reply_to_message
        return f"@{me.username}".lower() in text or bool(rep and rep.from_user and rep.from_user.id == me.id)

    def main_kb(uid: int) -> Any:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(types.KeyboardButton(core.btn("btn_mode_chat", uid)), types.KeyboardButton(core.btn("btn_mode_translate", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_mode_summary", uid)), types.KeyboardButton(core.btn("btn_mode_fix", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_new_chat", uid)), types.KeyboardButton(core.btn("btn_lang", uid)),
               types.KeyboardButton(core.btn("btn_help", uid)))
        return kb

    def send_long(chat_id: int, text: str, reply_to: int | None = None, uid: int | None = None) -> None:
        chunks = split_text(text)
        for i, chunk in enumerate(chunks):
            bot.send_message(chat_id, chunk, reply_to_message_id=reply_to if i == 0 else None,
                             reply_markup=main_kb(uid) if (uid and i == len(chunks) - 1) else None)

    def handle(msg: Any, text: str, media: tuple[str, bytes] | None = None) -> None:
        uid = msg.from_user.id
        if not take_quota(uid):
            bot.reply_to(msg, t("ai_limit", user_id=uid, n=DAILY_LIMIT))
            return
        mode = get_mode(uid)
        system = SYSTEM_PROMPT if mode == "chat" else MODE_PROMPTS[mode]
        history = get_history(uid) if mode == "chat" else []
        bot.send_chat_action(msg.chat.id, "typing")

        def work() -> None:
            try:
                answer = ask_ai(history, text, system, media)
            except AIError as e:
                bot.reply_to(msg, t("ai_error", user_id=uid, err=str(e)))
                return
            except Exception as e:  # noqa: BLE001
                log("log_error", err=repr(e))
                bot.reply_to(msg, t("ai_error", user_id=uid, err=type(e).__name__))
                return
            if mode == "chat":
                add_history(uid, "user", text if not media else f"[{media[0]}] {text}")
                add_history(uid, "model", answer)
            send_long(msg.chat.id, answer, msg.message_id, uid if msg.chat.type == "private" else None)

        threading.Thread(target=work, daemon=True).start()

    @bot.message_handler(commands=["start"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        key_state = "ai_key_ok" if AI_API_KEY else "ai_key_missing"
        bot.reply_to(msg, t("ai_welcome", user_id=uid) + "\n\n" + t(key_state, user_id=uid), reply_markup=main_kb(uid))

    @bot.message_handler(commands=["help"])
    def on_help(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("ai_help", user_id=uid, n=DAILY_LIMIT or "∞", model=AI_MODEL), reply_markup=main_kb(uid))

    @bot.message_handler(commands=["new", "reset"])
    def on_new(msg: Any) -> None:
        clear_history(msg.from_user.id)
        set_mode(msg.from_user.id, "chat")
        bot.reply_to(msg, t("ai_new_chat", user_id=msg.from_user.id), reply_markup=main_kb(msg.from_user.id))

    @bot.message_handler(commands=["lang", "language"])
    def on_lang(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_lang_title", user_id=uid),
                     reply_markup=build_reply_language_keyboard(user_id=uid, back_text=core.btn("btn_menu", uid)))

    @bot.message_handler(func=lambda m: bool(m.text and parse_lang_choice(m.text)))
    def on_lang_chosen(msg: Any) -> None:
        uid = msg.from_user.id
        set_user_lang(uid, parse_lang_choice(msg.text) or "en")
        bot.reply_to(msg, t("tg_lang_changed", user_id=uid), reply_markup=main_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_lang"))
    def on_lang_btn(msg: Any) -> None:
        on_lang(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_help"))
    def on_help_btn(msg: Any) -> None:
        on_help(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_menu", "btn_back", "btn_cancel"))
    def on_menu(msg: Any) -> None:
        bot.reply_to(msg, t("ai_menu", user_id=msg.from_user.id), reply_markup=main_kb(msg.from_user.id))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_new_chat"))
    def on_new_btn(msg: Any) -> None:
        on_new(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, *MODES))
    def on_mode(msg: Any) -> None:
        uid = msg.from_user.id
        mode = next(v for k, v in MODES.items() if core.is_btn(msg.text, k))
        set_mode(uid, mode)
        bot.reply_to(msg, t(f"ai_mode_{mode}", user_id=uid), reply_markup=main_kb(uid))

    @bot.message_handler(content_types=["voice", "audio"])
    def on_voice(msg: Any) -> None:
        uid = msg.from_user.id
        if not addressed(msg):
            return
        if AI_PROVIDER != "gemini":
            bot.reply_to(msg, t("ai_media_gemini_only", user_id=uid))
            return
        obj = msg.voice or msg.audio
        try:
            data = core.download_tg_file(bot, obj.file_id, obj.file_size)
        except core.FileTooBig as e:
            bot.reply_to(msg, str(e))
            return
        mime = getattr(obj, "mime_type", None) or "audio/ogg"
        handle(msg, msg.caption or t("ai_voice_prompt", user_id=uid), (mime, data))

    @bot.message_handler(content_types=["photo"])
    def on_photo(msg: Any) -> None:
        uid = msg.from_user.id
        if not addressed(msg):
            return
        if AI_PROVIDER != "gemini":
            bot.reply_to(msg, t("ai_media_gemini_only", user_id=uid))
            return
        ph = msg.photo[-1]
        try:
            data = core.download_tg_file(bot, ph.file_id, ph.file_size)
        except core.FileTooBig as e:
            bot.reply_to(msg, str(e))
            return
        handle(msg, msg.caption or t("ai_photo_prompt", user_id=uid), ("image/jpeg", data))

    @bot.message_handler(content_types=["text"])
    def on_text(msg: Any) -> None:
        if not addressed(msg):
            return
        msg.text = msg.text.replace(f"@{me.username}", "").strip() or msg.text
        if msg.text.startswith("/"):
            bot.reply_to(msg, t("ai_unknown_cmd", user_id=msg.from_user.id))
            return
        handle(msg, msg.text)

    log("log_started_tg", model=AI_MODEL, provider=AI_PROVIDER)
    core.start_polling(bot, skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
