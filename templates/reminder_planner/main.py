"""Reminder Planner — напоминания, задачи и утренняя сводка в Telegram.

Пишите обычным текстом:
    через 10 мин позвонить маме      | in 10 min call mom      | баъди 10 дақиқа ...   | 10 daqiqadan keyin ...
    завтра в 9:00 врач               | tomorrow 9:00 doctor    | пагоҳ 9:00 ...        | ertaga 9:00 ...
    в 18:30 спорт / 18:30 спорт      | at 18:30 gym
    25.12 10:00 поздравить           | 25.12.2026 10:00 ...
    каждый день в 8:00 таблетки      | every day 8:00 pills    | ҳар рӯз 8:00 ...      | har kuni 8:00 ...
    10m / 2h / 1d текст              — коротко для всех языков

Переменные:
    BOT_TOKEN, ALLOWED_USER_IDS
    TZ_OFFSET    — часовой пояс в часах от UTC (Душанбе/Ташкент = 5, Москва = 3). По умолчанию 5
    DIGEST_TIME  — время утренней сводки, напр. 08:00 (пусто = выключено)
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pybionic_core as core
from i18n import build_reply_language_keyboard, log, parse_lang_choice, set_user_lang, t

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
try:
    TZ_OFFSET = float(os.environ.get("TZ_OFFSET", "5").strip() or "5")
except ValueError:
    TZ_OFFSET = 5.0
TZ = timezone(timedelta(hours=TZ_OFFSET))
DIGEST_TIME = os.environ.get("DIGEST_TIME", "08:00").strip()

DB_PATH = core.get_data_dir() / "reminders.db"
_db_lock = threading.Lock()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, text TEXT,
        fire_at INTEGER, repeat TEXT DEFAULT '', active INTEGER DEFAULT 1, created INTEGER)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_rem_due ON reminders(active, fire_at)")
    c.execute("""CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, text TEXT, done INTEGER DEFAULT 0, created INTEGER)""")
    c.execute("CREATE TABLE IF NOT EXISTS digest (chat_id INTEGER PRIMARY KEY, last_day TEXT, enabled INTEGER DEFAULT 1)")
    return c


def q(sql: str, args: tuple = (), one: bool = False) -> Any:
    with _db_lock, db() as c:
        cur = c.execute(sql, args)
        if sql.lstrip().upper().startswith("SELECT"):
            return cur.fetchone() if one else cur.fetchall()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Разбор времени
# ---------------------------------------------------------------------------
UNIT_WORDS = {
    "m": ("мин", "минут", "минуту", "минуты", "min", "mins", "minute", "minutes", "дақиқа", "daqiqa", "daqiqadan"),
    "h": ("ч", "час", "часа", "часов", "h", "hr", "hour", "hours", "соат", "soat", "soatdan"),
    "d": ("д", "дн", "день", "дня", "дней", "d", "day", "days", "рӯз", "kun", "kundan"),
}
UNIT_SEC = {"m": 60, "h": 3600, "d": 86400}
_unit_alt = "|".join(sorted({w for ws in UNIT_WORDS.values() for w in ws}, key=len, reverse=True))

RE_SHORT = re.compile(r"^\+?(\d{1,4})\s*([mhd])\b\s*(.*)$", re.I | re.S)
RE_IN = re.compile(rf"^(?:через|in|баъди|пас аз)\s+(\d{{1,4}})\s*({_unit_alt})\.?\s+(.*)$", re.I | re.S)
RE_IN_UZ = re.compile(rf"^(\d{{1,4}})\s*({_unit_alt})(?:dan)?\s+keyin\s+(.*)$", re.I | re.S)
RE_PLUS_MIN = re.compile(r"^\+(\d{1,4})\s+(.*)$", re.S)
RE_TIME = r"(\d{1,2})[:.](\d{2})"
RE_EVERY = re.compile(rf"^(?:каждый день|ежедневно|every day|daily|ҳар рӯз|har kuni)\s*(?:в|at|соати|soat)?\s*{RE_TIME}\s+(.*)$", re.I | re.S)
RE_TOMORROW = re.compile(rf"^(?:завтра|tomorrow|пагоҳ|фардо|ertaga)\s*(?:в|at|соати|soat)?\s*{RE_TIME}\s+(.*)$", re.I | re.S)
RE_DATE = re.compile(rf"^(\d{{1,2}})\.(\d{{1,2}})(?:\.(\d{{2,4}}))?\s+(?:в\s+|at\s+)?{RE_TIME}\s+(.*)$", re.I | re.S)
RE_AT = re.compile(rf"^(?:сегодня\s+)?(?:в|at|соати|soat)?\s*{RE_TIME}\s+(.*)$", re.I | re.S)


def _unit_of(word: str) -> str | None:
    w = word.lower().rstrip(".")
    for u, words in UNIT_WORDS.items():
        if w in words:
            return u
    return None


def parse_reminder(text: str, now: datetime | None = None) -> tuple[datetime, str, str] | None:
    """-> (время в TZ, текст, repeat '' | 'daily') или None."""
    now = now or datetime.now(TZ)
    s = text.strip()

    for rx in (RE_IN, RE_IN_UZ):
        m = rx.match(s)
        if m:
            u = _unit_of(m.group(2))
            if u and m.group(3).strip():
                return now + timedelta(seconds=int(m.group(1)) * UNIT_SEC[u]), m.group(3).strip(), ""
    m = RE_SHORT.match(s)
    if m and m.group(3).strip():
        return now + timedelta(seconds=int(m.group(1)) * UNIT_SEC[m.group(2).lower()]), m.group(3).strip(), ""
    m = RE_PLUS_MIN.match(s)
    if m and m.group(2).strip():
        return now + timedelta(minutes=int(m.group(1))), m.group(2).strip(), ""

    def at(day: datetime, hh: str, mm: str) -> datetime | None:
        h, mi = int(hh), int(mm)
        if h > 23 or mi > 59:
            return None
        return day.replace(hour=h, minute=mi, second=0, microsecond=0)

    m = RE_EVERY.match(s)
    if m:
        when = at(now, m.group(1), m.group(2))
        if when and m.group(3).strip():
            if when <= now:
                when += timedelta(days=1)
            return when, m.group(3).strip(), "daily"
    m = RE_TOMORROW.match(s)
    if m:
        when = at(now + timedelta(days=1), m.group(1), m.group(2))
        if when and m.group(3).strip():
            return when, m.group(3).strip(), ""
    m = RE_DATE.match(s)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else now.year
        if y < 100:
            y += 2000
        try:
            when = now.replace(year=y, month=mo, day=d)
        except ValueError:
            return None
        when = at(when, m.group(4), m.group(5))
        if when and m.group(6).strip():
            if when <= now and not m.group(3):
                when = when.replace(year=when.year + 1)
            return when, m.group(6).strip(), ""
    m = RE_AT.match(s)
    if m:
        when = at(now, m.group(1), m.group(2))
        if when and m.group(3).strip():
            if when <= now:
                when += timedelta(days=1)
            return when, m.group(3).strip(), ""
    return None


def fmt_dt(ts: int) -> str:
    d = datetime.fromtimestamp(ts, TZ)
    today = datetime.now(TZ).date()
    if d.date() == today:
        return d.strftime("%H:%M")
    if d.date() == today + timedelta(days=1):
        return d.strftime("%d.%m %H:%M") + " (+1)"
    return d.strftime("%d.%m.%Y %H:%M")


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def main() -> None:
    if not BOT_TOKEN:
        log("err_missing_token")
        return
    import telebot
    from telebot import types

    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
    core.guard_bot(bot)
    pending: dict[int, str] = {}  # chat_id -> "remind" | "todo"

    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def main_kb(uid: int) -> Any:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(types.KeyboardButton(core.btn("btn_new_reminder", uid)), types.KeyboardButton(core.btn("btn_my_reminders", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_add_todo", uid)), types.KeyboardButton(core.btn("btn_todos", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_lang", uid)), types.KeyboardButton(core.btn("btn_help", uid)))
        return kb

    def snooze_kb(rid: int, uid: int) -> Any:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("+10 min", callback_data=f"sn:{rid}:10"),
               types.InlineKeyboardButton("+1 h", callback_data=f"sn:{rid}:60"),
               types.InlineKeyboardButton("+1 d", callback_data=f"sn:{rid}:1440"))
        kb.row(types.InlineKeyboardButton(t("rem_done_btn", user_id=uid), callback_data=f"ok:{rid}"))
        return kb

    def add_reminder(msg: Any, parsed: tuple[datetime, str, str]) -> None:
        when, text, repeat = parsed
        uid = msg.from_user.id
        rid = q("INSERT INTO reminders (chat_id,user_id,text,fire_at,repeat,created) VALUES (?,?,?,?,?,?)",
                (msg.chat.id, uid, text[:1000], int(when.timestamp()), repeat, int(time.time())))
        key = "rem_saved_daily" if repeat else "rem_saved"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(t("rem_cancel_btn", user_id=uid), callback_data=f"del:{rid}"))
        bot.reply_to(msg, t(key, user_id=uid, when=fmt_dt(int(when.timestamp())), text=esc(text)), reply_markup=kb)

    def show_reminders(chat_id: int, uid: int) -> None:
        rows = q("SELECT id, text, fire_at, repeat FROM reminders WHERE chat_id=? AND active=1 ORDER BY fire_at LIMIT 30", (chat_id,))
        if not rows:
            bot.send_message(chat_id, t("rem_empty", user_id=uid), reply_markup=main_kb(uid))
            return
        lines, kb = [t("rem_list_title", user_id=uid)], types.InlineKeyboardMarkup()
        for i, (rid, text, fire_at, repeat) in enumerate(rows, 1):
            rep = " 🔁" if repeat else ""
            lines.append(f"{i}. <b>{fmt_dt(fire_at)}</b>{rep} — {esc(text)}")
            kb.add(types.InlineKeyboardButton(f"🗑 {i}. {text[:30]}", callback_data=f"del:{rid}"))
        bot.send_message(chat_id, "\n".join(lines), reply_markup=kb)

    def todo_view(chat_id: int, uid: int) -> tuple[str, Any]:
        rows = q("SELECT id, text, done FROM todos WHERE chat_id=? ORDER BY done, id LIMIT 40", (chat_id,))
        kb = types.InlineKeyboardMarkup()
        if not rows:
            return t("todo_empty", user_id=uid), None
        lines = [t("todo_title", user_id=uid)]
        for tid, text, done in rows:
            mark = "✅" if done else "⬜"
            lines.append(f"{mark} {esc(text)}")
            kb.row(types.InlineKeyboardButton(f"{mark} {text[:28]}", callback_data=f"tt:{tid}"),
                   types.InlineKeyboardButton("🗑", callback_data=f"td:{tid}"))
        if any(r[2] for r in rows):
            kb.add(types.InlineKeyboardButton(t("todo_clear_done", user_id=uid), callback_data="tc"))
        return "\n".join(lines), kb

    @bot.message_handler(commands=["start", "help"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        q("INSERT OR IGNORE INTO digest (chat_id, last_day) VALUES (?, '')", (msg.chat.id,))
        tz = f"UTC{'+' if TZ_OFFSET >= 0 else ''}{TZ_OFFSET:g}"
        bot.reply_to(msg, t("rem_welcome", user_id=uid, tz=tz, digest=DIGEST_TIME or "—"), reply_markup=main_kb(uid))

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

    @bot.message_handler(commands=["digest"])
    def on_digest_toggle(msg: Any) -> None:
        row = q("SELECT enabled FROM digest WHERE chat_id=?", (msg.chat.id,), one=True)
        new = 0 if (row and row[0]) else 1
        q("INSERT OR REPLACE INTO digest (chat_id, last_day, enabled) VALUES (?, COALESCE((SELECT last_day FROM digest WHERE chat_id=?), ''), ?)",
          (msg.chat.id, msg.chat.id, new))
        bot.reply_to(msg, t("digest_on" if new else "digest_off", user_id=msg.from_user.id, time=DIGEST_TIME or "—"))

    @bot.message_handler(commands=["todo"])
    def on_todo_cmd(msg: Any) -> None:
        text = msg.text.split(maxsplit=1)[1].strip() if len(msg.text.split(maxsplit=1)) > 1 else ""
        if text:
            q("INSERT INTO todos (chat_id, text, created) VALUES (?,?,?)", (msg.chat.id, text[:300], int(time.time())))
        body, kb = todo_view(msg.chat.id, msg.from_user.id)
        bot.reply_to(msg, body, reply_markup=kb)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_lang"))
    def on_lang_btn(msg: Any) -> None:
        on_lang(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_help"))
    def on_help_btn(msg: Any) -> None:
        on_start(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_menu", "btn_back", "btn_cancel"))
    def on_menu(msg: Any) -> None:
        pending.pop(msg.chat.id, None)
        bot.reply_to(msg, "👌", reply_markup=main_kb(msg.from_user.id))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_new_reminder"))
    def on_new_rem(msg: Any) -> None:
        pending[msg.chat.id] = "remind"
        bot.reply_to(msg, t("rem_ask", user_id=msg.from_user.id))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_my_reminders"))
    def on_list_rem(msg: Any) -> None:
        show_reminders(msg.chat.id, msg.from_user.id)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_add_todo"))
    def on_add_todo(msg: Any) -> None:
        pending[msg.chat.id] = "todo"
        bot.reply_to(msg, t("todo_ask", user_id=msg.from_user.id))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_todos"))
    def on_todos(msg: Any) -> None:
        body, kb = todo_view(msg.chat.id, msg.from_user.id)
        bot.reply_to(msg, body, reply_markup=kb)

    @bot.message_handler(content_types=["text"])
    def on_text(msg: Any) -> None:
        uid = msg.from_user.id
        state = pending.pop(msg.chat.id, None)
        if state == "todo":
            for line in msg.text.splitlines():
                if line.strip():
                    q("INSERT INTO todos (chat_id, text, created) VALUES (?,?,?)", (msg.chat.id, line.strip()[:300], int(time.time())))
            body, kb = todo_view(msg.chat.id, uid)
            bot.reply_to(msg, body, reply_markup=kb)
            return
        parsed = parse_reminder(msg.text)
        if parsed:
            add_reminder(msg, parsed)
            return
        # в группе молчим на обычные сообщения
        if msg.chat.type == "private" or state == "remind":
            if state == "remind":
                pending[msg.chat.id] = "remind"
            bot.reply_to(msg, t("rem_not_understood", user_id=uid))

    @bot.callback_query_handler(func=lambda c: True)
    def on_cb(c: Any) -> None:
        uid, chat_id = c.from_user.id, c.message.chat.id
        parts = (c.data or "").split(":")
        act = parts[0]
        try:
            if act == "sn":
                rid, mins = int(parts[1]), int(parts[2])
                fire = int(time.time()) + mins * 60
                row = q("SELECT repeat, text FROM reminders WHERE id=? AND chat_id=?", (rid, chat_id), one=True)
                if row and row[0]:
                    # у ежедневных откладываем копию, основное расписание не трогаем
                    q("INSERT INTO reminders (chat_id,user_id,text,fire_at,repeat,created) VALUES (?,?,?,?,?,?)",
                      (chat_id, uid, row[1], fire, "", int(time.time())))
                else:
                    q("UPDATE reminders SET fire_at=?, active=1 WHERE id=? AND chat_id=?", (fire, rid, chat_id))
                bot.answer_callback_query(c.id, t("rem_snoozed", user_id=uid, when=fmt_dt(fire)))
                bot.edit_message_reply_markup(chat_id, c.message.message_id, reply_markup=None)
            elif act == "ok":
                bot.answer_callback_query(c.id, "✅")
                bot.edit_message_reply_markup(chat_id, c.message.message_id, reply_markup=None)
            elif act == "del":
                q("UPDATE reminders SET active=0 WHERE id=? AND chat_id=?", (int(parts[1]), chat_id))
                bot.answer_callback_query(c.id, t("rem_deleted", user_id=uid))
                bot.edit_message_reply_markup(chat_id, c.message.message_id, reply_markup=None)
            elif act in ("tt", "td", "tc"):
                if act == "tt":
                    q("UPDATE todos SET done = 1 - done WHERE id=? AND chat_id=?", (int(parts[1]), chat_id))
                elif act == "td":
                    q("DELETE FROM todos WHERE id=? AND chat_id=?", (int(parts[1]), chat_id))
                else:
                    q("DELETE FROM todos WHERE chat_id=? AND done=1", (chat_id,))
                body, kb = todo_view(chat_id, uid)
                bot.edit_message_text(body, chat_id, c.message.message_id, reply_markup=kb)
                bot.answer_callback_query(c.id)
            else:
                bot.answer_callback_query(c.id)
        except Exception as e:  # noqa: BLE001
            log("log_error", err=repr(e))
            try:
                bot.answer_callback_query(c.id)
            except Exception:
                pass

    # -- планировщик --------------------------------------------------------
    def scheduler() -> None:
        while True:
            try:
                now = int(time.time())
                due = q("SELECT id, chat_id, user_id, text, fire_at, repeat FROM reminders WHERE active=1 AND fire_at<=? ORDER BY fire_at LIMIT 50", (now,))
                for rid, chat_id, uid, text, fire_at, repeat in due:
                    late = now - fire_at > 6 * 3600
                    try:
                        if not late or repeat:
                            bot.send_message(chat_id, t("rem_fire", user_id=uid, text=esc(text)), reply_markup=snooze_kb(rid, uid))
                    except Exception as e:  # noqa: BLE001 — чат удалён/бот заблокирован
                        log("log_error", err=repr(e))
                        if "blocked" in str(e).lower() or "chat not found" in str(e).lower():
                            q("UPDATE reminders SET active=0 WHERE id=?", (rid,))
                            continue
                    if repeat == "daily":
                        nxt = fire_at
                        while nxt <= now:
                            nxt += 86400
                        q("UPDATE reminders SET fire_at=? WHERE id=?", (nxt, rid))
                    else:
                        q("UPDATE reminders SET active=0 WHERE id=?", (rid,))
                send_digests()
            except Exception as e:  # noqa: BLE001
                log("log_error", err=repr(e))
            time.sleep(15)

    def send_digests() -> None:
        if not re.fullmatch(r"\d{1,2}:\d{2}", DIGEST_TIME):
            return
        now = datetime.now(TZ)
        hh, mm = map(int, DIGEST_TIME.split(":"))
        if (now.hour, now.minute) < (hh, mm):
            return
        today = now.date().isoformat()
        end = int((now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp())
        for chat_id, last_day in q("SELECT chat_id, last_day FROM digest WHERE enabled=1"):
            if last_day == today:
                continue
            q("UPDATE digest SET last_day=? WHERE chat_id=?", (today, chat_id))
            rems = q("SELECT text, fire_at FROM reminders WHERE chat_id=? AND active=1 AND fire_at<? ORDER BY fire_at", (chat_id, end))
            todos = q("SELECT text FROM todos WHERE chat_id=? AND done=0 ORDER BY id LIMIT 15", (chat_id,))
            if not rems and not todos:
                continue
            lines = [t("digest_title", user_id=chat_id)]
            for text, fire_at in rems:
                lines.append(f"⏰ {fmt_dt(fire_at)} — {esc(text)}")
            for (text,) in todos:
                lines.append(f"⬜ {esc(text)}")
            try:
                bot.send_message(chat_id, "\n".join(lines))
            except Exception as e:  # noqa: BLE001
                log("log_error", err=repr(e))

    threading.Thread(target=scheduler, name="reminders", daemon=True).start()
    log("log_started_tg", tz=TZ_OFFSET)
    core.start_polling(bot, skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
