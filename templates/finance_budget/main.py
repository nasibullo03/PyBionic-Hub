"""Finance Budget — курсы валют, конвертер, уведомления о курсе и семейный бюджет.

Пишите обычным текстом:
    100 usd rub        → перевод по текущему курсу (также «100 usd в rub», «100$»)
    -120 такси         → расход (минус можно не писать: «120 такси»)
    +5000 зарплата     → доход
    /alert USD RUB > 95 → сообщу, когда курс перейдёт черту
Добавьте бота в семейную группу — бюджет будет общим для всех в чате.

Переменные:
    BOT_TOKEN, ALLOWED_USER_IDS
    HOME_CURRENCY     — валюта бюджета, по умолчанию TJS
    WATCH_CURRENCIES  — курсы в «💱 Курсы», по умолчанию USD,EUR,RUB,CNY
Курсы: open.er-api.com (бесплатно, без ключа, обновление раз в сутки).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.request
from datetime import datetime
from typing import Any

import pybionic_core as core
from i18n import build_reply_language_keyboard, log, parse_lang_choice, set_user_lang, t

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
HOME = (os.environ.get("HOME_CURRENCY", "TJS").strip() or "TJS").upper()
WATCH = [c.strip().upper() for c in (os.environ.get("WATCH_CURRENCIES", "") or "USD,EUR,RUB,CNY").split(",") if c.strip()]
RATES_URL = "https://open.er-api.com/v6/latest/USD"

ALIASES = {
    "$": "USD", "доллар": "USD", "долл": "USD", "dollar": "USD", "доллара": "USD", "долларов": "USD",
    "€": "EUR", "евро": "EUR", "euro": "EUR",
    "₽": "RUB", "руб": "RUB", "рубль": "RUB", "рубля": "RUB", "рублей": "RUB", "rubl": "RUB",
    "сомони": "TJS", "сомон": "TJS", "сом": "TJS", "somoni": "TJS",
    "сум": "UZS", "so'm": "UZS", "soʻm": "UZS", "som": "UZS",
    "тенге": "KZT", "юань": "CNY", "юаней": "CNY", "yuan": "CNY", "лира": "TRY",
}

DB_PATH = core.get_data_dir() / "finance.db"
_db_lock = threading.Lock()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("""CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER,
        user_name TEXT, amount REAL, category TEXT, note TEXT, ts INTEGER)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_entries ON entries(chat_id, ts)")
    c.execute("""CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER,
        base TEXT, quote TEXT, op TEXT, value REAL, active INTEGER DEFAULT 1)""")
    c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
    return c


def q(sql: str, args: tuple = (), one: bool = False) -> Any:
    with _db_lock, db() as c:
        cur = c.execute(sql, args)
        if sql.lstrip().upper().startswith("SELECT"):
            return cur.fetchone() if one else cur.fetchall()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Курсы
# ---------------------------------------------------------------------------
_rates: dict[str, Any] = {"ts": 0, "rates": {}, "updated": ""}


def get_rates(force: bool = False) -> dict[str, float]:
    """Курсы к USD. Кэш 1 час в памяти + последний удачный ответ в базе (работает без сети)."""
    if not force and _rates["rates"] and time.time() - _rates["ts"] < 3600:
        return _rates["rates"]
    try:
        req = urllib.request.Request(RATES_URL, headers={"User-Agent": "PyBionic-FinanceBudget/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("result") == "success" and data.get("rates"):
            _rates.update(ts=time.time(), rates=data["rates"], updated=data.get("time_last_update_utc", ""))
            q("INSERT OR REPLACE INTO kv VALUES ('rates', ?)", (json.dumps({"rates": data["rates"], "updated": _rates["updated"]}),))
            return _rates["rates"]
    except Exception as e:  # noqa: BLE001
        log("log_error", err=f"rates: {e!r}")
    if not _rates["rates"]:
        row = q("SELECT v FROM kv WHERE k='rates'", one=True)
        if row:
            saved = json.loads(row[0])
            _rates.update(ts=time.time() - 3000, rates=saved["rates"], updated=saved.get("updated", "") + " (cache)")
    return _rates["rates"]


def convert(amount: float, frm: str, to: str) -> float | None:
    r = get_rates()
    if frm not in r or to not in r:
        return None
    return amount / r[frm] * r[to]


def norm_code(word: str) -> str | None:
    w = word.strip().lower().strip(".,")
    if w in ALIASES:
        return ALIASES[w]
    code = w.upper()
    if len(code) == 3 and code.isalpha() and code in get_rates():
        return code
    return None


def esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def op_html(op: str) -> str:
    return "&gt;" if op == ">" else "&lt;"


def fmt_num(v: float) -> str:
    if abs(v) >= 100:
        s = f"{v:,.2f}"
    elif abs(v) >= 1:
        s = f"{v:,.4f}"
    else:
        s = f"{v:,.6f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return s.replace(",", " ")


RE_CONV = re.compile(r"^(\d+(?:[.,]\d+)?)\s*([^\s\d]+)(?:\s+(?:в|to|in|ба|ga|=)?\s*([^\s\d]+))?$", re.I)
RE_ENTRY = re.compile(r"^([+-]?)\s*(\d+(?:[.,]\d+)?)\s+(.+)$", re.S)
RE_ALERT = re.compile(r"^/alert\s+([A-Za-z]{3})\s+([A-Za-z]{3})\s*([<>])\s*(\d+(?:[.,]\d+)?)", re.I)


def parse_conversion(text: str) -> tuple[float, str, str] | None:
    m = RE_CONV.match(text.strip())
    if not m:
        return None
    frm = norm_code(m.group(2))
    if not frm:
        return None
    to = norm_code(m.group(3)) if m.group(3) else (HOME if frm != HOME else "USD")
    if not to:
        return None
    return float(m.group(1).replace(",", ".")), frm, to


def parse_entry(text: str) -> tuple[float, str, str] | None:
    """-> (сумма со знаком, категория, заметка). Без знака — расход."""
    m = RE_ENTRY.match(text.strip())
    if not m:
        return None
    amount = float(m.group(2).replace(",", "."))
    if amount <= 0:
        return None
    note = m.group(3).strip()[:200]
    category = note.split()[0].lower().strip(".,:;!")[:30]
    return (amount if m.group(1) == "+" else -amount), category, note


# ---------------------------------------------------------------------------
# Отчёт
# ---------------------------------------------------------------------------
def month_bounds(ym: str) -> tuple[int, int]:
    y, m = map(int, ym.split("-"))
    start = datetime(y, m, 1)
    end = datetime(y + (m == 12), m % 12 + 1, 1)
    return int(start.timestamp()), int(end.timestamp())


def shift_month(ym: str, delta: int) -> str:
    y, m = map(int, ym.split("-"))
    m += delta
    while m < 1:
        m, y = m + 12, y - 1
    while m > 12:
        m, y = m - 12, y + 1
    return f"{y:04d}-{m:02d}"


def month_report(chat_id: int, ym: str, uid: int) -> str:
    a, b = month_bounds(ym)
    rows = q("SELECT amount, category FROM entries WHERE chat_id=? AND ts>=? AND ts<?", (chat_id, a, b))
    income = sum(x for x, _ in rows if x > 0)
    expense = -sum(x for x, _ in rows if x < 0)
    cats: dict[str, float] = {}
    for x, c in rows:
        if x < 0:
            cats[c] = cats.get(c, 0) - x
    lines = [t("fin_report_title", user_id=uid, month=ym),
             t("fin_report_sums", user_id=uid, inc=fmt_num(income), exp=fmt_num(expense), bal=fmt_num(income - expense), cur=HOME)]
    if cats:
        lines.append(t("fin_report_cats", user_id=uid))
        top = max(cats.values())
        for c, v in sorted(cats.items(), key=lambda kv: -kv[1])[:12]:
            bar = "▇" * max(1, round(v / top * 10))
            lines.append(f"<code>{bar:<10}</code> {esc(c)} — {fmt_num(v)} ({v / expense * 100:.0f}%)")
    elif not rows:
        lines.append(t("fin_report_empty", user_id=uid))
    return "\n".join(lines)


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

    def main_kb(uid: int) -> Any:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(types.KeyboardButton(core.btn("btn_rates", uid)), types.KeyboardButton(core.btn("btn_report", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_undo", uid)), types.KeyboardButton(core.btn("btn_alerts", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_lang", uid)), types.KeyboardButton(core.btn("btn_help", uid)))
        return kb

    def report_kb(ym: str) -> Any:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("◀", callback_data=f"rep:{shift_month(ym, -1)}"),
               types.InlineKeyboardButton("CSV", callback_data=f"csv:{ym}"),
               types.InlineKeyboardButton("▶", callback_data=f"rep:{shift_month(ym, 1)}"))
        return kb

    @bot.message_handler(commands=["start", "help"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("fin_welcome", user_id=uid, cur=HOME), reply_markup=main_kb(uid))

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
        on_start(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_menu", "btn_back", "btn_cancel"))
    def on_menu(msg: Any) -> None:
        bot.reply_to(msg, "👌", reply_markup=main_kb(msg.from_user.id))

    @bot.message_handler(commands=["rates"])
    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_rates"))
    def on_rates(msg: Any) -> None:
        uid = msg.from_user.id
        r = get_rates()
        if not r:
            bot.reply_to(msg, t("fin_no_rates", user_id=uid))
            return
        lines = [t("fin_rates_title", user_id=uid, cur=HOME)]
        for c in WATCH:
            if c != HOME and c in r and HOME in r:
                lines.append(f"1 {c} = <b>{fmt_num(r[HOME] / r[c])}</b> {HOME}")
        lines.append(f"\n<i>{_rates['updated']}</i>")
        bot.reply_to(msg, "\n".join(lines))

    @bot.message_handler(commands=["report"])
    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_report"))
    def on_report(msg: Any) -> None:
        ym = datetime.now().strftime("%Y-%m")
        bot.reply_to(msg, month_report(msg.chat.id, ym, msg.from_user.id), reply_markup=report_kb(ym))

    @bot.message_handler(commands=["undo"])
    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_undo"))
    def on_undo(msg: Any) -> None:
        uid = msg.from_user.id
        row = q("SELECT id, amount, note FROM entries WHERE chat_id=? AND user_id=? ORDER BY id DESC LIMIT 1", (msg.chat.id, uid), one=True)
        if not row:
            bot.reply_to(msg, t("fin_nothing_to_undo", user_id=uid))
            return
        q("DELETE FROM entries WHERE id=?", (row[0],))
        bot.reply_to(msg, t("fin_undone", user_id=uid, amount=fmt_num(row[1]), note=esc(row[2])))

    @bot.message_handler(commands=["alerts"])
    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_alerts"))
    def on_alerts(msg: Any) -> None:
        uid = msg.from_user.id
        rows = q("SELECT id, base, quote, op, value FROM alerts WHERE chat_id=? AND active=1", (msg.chat.id,))
        kb = types.InlineKeyboardMarkup()
        lines = [t("fin_alerts_title", user_id=uid)]
        for aid, base, quote, op, value in rows:
            lines.append(f"• {base}/{quote} {op_html(op)} {fmt_num(value)}")
            kb.add(types.InlineKeyboardButton(f"🗑 {base}/{quote} {op} {fmt_num(value)}", callback_data=f"adel:{aid}"))
        if not rows:
            lines.append(t("fin_alerts_empty", user_id=uid))
        bot.reply_to(msg, "\n".join(lines), reply_markup=kb if rows else None)

    @bot.message_handler(commands=["alert"])
    def on_alert(msg: Any) -> None:
        uid = msg.from_user.id
        m = RE_ALERT.match(msg.text or "")
        if not m:
            bot.reply_to(msg, t("fin_alert_usage", user_id=uid))
            return
        base, quote, op, value = m.group(1).upper(), m.group(2).upper(), m.group(3), float(m.group(4).replace(",", "."))
        now_v = convert(1, base, quote)
        if now_v is None:
            bot.reply_to(msg, t("fin_unknown_currency", user_id=uid))
            return
        q("INSERT INTO alerts (chat_id, user_id, base, quote, op, value) VALUES (?,?,?,?,?,?)", (msg.chat.id, uid, base, quote, op, value))
        bot.reply_to(msg, t("fin_alert_saved", user_id=uid, pair=f"{base}/{quote}", op=op_html(op), value=fmt_num(value), now=fmt_num(now_v)))

    @bot.message_handler(commands=["export"])
    def on_export(msg: Any) -> None:
        send_csv(msg.chat.id, None)

    def send_csv(chat_id: int, ym: str | None) -> None:
        if ym:
            a, b = month_bounds(ym)
            rows = q("SELECT ts, user_name, amount, category, note FROM entries WHERE chat_id=? AND ts>=? AND ts<? ORDER BY ts", (chat_id, a, b))
        else:
            rows = q("SELECT ts, user_name, amount, category, note FROM entries WHERE chat_id=? ORDER BY ts", (chat_id,))
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["date", "who", f"amount_{HOME}", "category", "note"])
        for ts, who, amount, cat, note in rows:
            w.writerow([datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"), who, f"{amount:.2f}", cat, note])
        data = io.BytesIO(("﻿" + buf.getvalue()).encode("utf-8"))
        data.name = f"budget_{ym or 'all'}.csv"
        bot.send_document(chat_id, data)

    @bot.message_handler(content_types=["text"])
    def on_text(msg: Any) -> None:
        uid = msg.from_user.id
        text = (msg.text or "").strip()
        if text.startswith("/"):
            return
        conv = parse_conversion(text)
        if conv:
            amount, frm, to = conv
            res = convert(amount, frm, to)
            if res is None:
                bot.reply_to(msg, t("fin_no_rates", user_id=uid))
            else:
                bot.reply_to(msg, f"💱 {fmt_num(amount)} {frm} = <b>{fmt_num(res)}</b> {to}")
            return
        entry = parse_entry(text)
        if entry:
            amount, cat, note = entry
            name = msg.from_user.first_name or msg.from_user.username or str(uid)
            eid = q("INSERT INTO entries (chat_id, user_id, user_name, amount, category, note, ts) VALUES (?,?,?,?,?,?,?)",
                    (msg.chat.id, uid, name[:40], amount, cat, note, int(time.time())))
            a, b = month_bounds(datetime.now().strftime("%Y-%m"))
            spent = -(q("SELECT COALESCE(SUM(amount),0) FROM entries WHERE chat_id=? AND amount<0 AND ts>=? AND ts<?", (msg.chat.id, a, b), one=True)[0])
            key = "fin_income_saved" if amount > 0 else "fin_expense_saved"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("↩️", callback_data=f"edel:{eid}"))
            bot.reply_to(msg, t(key, user_id=uid, amount=fmt_num(abs(amount)), cur=HOME, cat=esc(cat), month=fmt_num(spent)), reply_markup=kb)
            return
        if msg.chat.type == "private":
            bot.reply_to(msg, t("fin_not_understood", user_id=uid))

    @bot.callback_query_handler(func=lambda c: True)
    def on_cb(c: Any) -> None:
        uid, chat_id, mid = c.from_user.id, c.message.chat.id, c.message.message_id
        act, _, arg = (c.data or "").partition(":")
        try:
            if act == "rep":
                bot.edit_message_text(month_report(chat_id, arg, uid), chat_id, mid, reply_markup=report_kb(arg))
            elif act == "csv":
                send_csv(chat_id, arg)
            elif act == "edel":
                q("DELETE FROM entries WHERE id=? AND chat_id=? AND user_id=?", (int(arg), chat_id, uid))
                bot.edit_message_reply_markup(chat_id, mid, reply_markup=None)
                bot.answer_callback_query(c.id, t("fin_deleted", user_id=uid))
                return
            elif act == "adel":
                q("UPDATE alerts SET active=0 WHERE id=? AND chat_id=?", (int(arg), chat_id))
                bot.answer_callback_query(c.id, t("fin_deleted", user_id=uid))
                return
            bot.answer_callback_query(c.id)
        except Exception as e:  # noqa: BLE001
            log("log_error", err=repr(e))
            try:
                bot.answer_callback_query(c.id)
            except Exception:
                pass

    def alert_loop() -> None:
        while True:
            time.sleep(30 * 60)
            try:
                if not q("SELECT 1 FROM alerts WHERE active=1 LIMIT 1", one=True):
                    continue
                get_rates(force=True)
                for aid, chat_id, uid, base, quote, op, value in q("SELECT id, chat_id, user_id, base, quote, op, value FROM alerts WHERE active=1"):
                    v = convert(1, base, quote)
                    if v is None or not ((op == ">" and v > value) or (op == "<" and v < value)):
                        continue
                    q("UPDATE alerts SET active=0 WHERE id=?", (aid,))
                    bot.send_message(chat_id, t("fin_alert_fired", user_id=uid, pair=f"{base}/{quote}", op=op_html(op), value=fmt_num(value), now=fmt_num(v)))
            except Exception as e:  # noqa: BLE001
                log("log_error", err=repr(e))

    threading.Thread(target=alert_loop, name="alerts", daemon=True).start()
    threading.Thread(target=get_rates, daemon=True).start()
    log("log_started_tg", cur=HOME)
    core.start_polling(bot, skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
