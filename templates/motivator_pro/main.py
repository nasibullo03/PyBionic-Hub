"""Motivator & Habit Tracker Pro — Visual PNG Progress Cards, Streaks (SQLite), and Daily Scheduler.
100% ReplyKeyboardMarkup (all buttons next to keyboard, zero inline text buttons), 24 languages, and offline Web Dashboard.
"""

from __future__ import annotations

import pybionic_core as core
import pybionic_web as web
import datetime
import html
import http.server
import io
import json
import os
import random
import re
import socketserver
import sqlite3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import textwrap
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

from i18n import (
    SUPPORTED_LANGUAGES,
    build_reply_language_keyboard,
    current_lang,
    get_user_lang,
    is_rtl,
    log,
    parse_lang_choice,
    set_user_lang,
    t,
    t_list,
)

FONT_CANDIDATES = [
    "/system/fonts/Roboto-Bold.ttf",
    "/system/fonts/NotoSans-Bold.ttf",
    "/system/fonts/NotoSans-Regular.ttf",
    "/system/fonts/NotoNaskhArabic-Bold.ttf",
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/DroidSans-Bold.ttf",
]


def db_path() -> Path:
    base = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    base.mkdir(parents=True, exist_ok=True)
    return base / "habits.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_done_date TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS checkins (
                user_id INTEGER NOT NULL,
                habit_id INTEGER NOT NULL,
                done_date TEXT NOT NULL,
                PRIMARY KEY (user_id, habit_id, done_date)
            );
            CREATE TABLE IF NOT EXISTS reminders (
                user_id INTEGER PRIMARY KEY,
                hhmm TEXT NOT NULL,
                last_sent_date TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )


def set_user_state(user_id: int, state: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_states (user_id, state, updated_at) VALUES (?, ?, ?)",
            (user_id, state, time.time()),
        )


def get_user_state(user_id: int) -> str:
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT state FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return ""


def clear_user_state(user_id: int) -> None:
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
    except Exception:
        pass


def load_font(size: int, text: str = ""):
    from PIL import ImageFont

    has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in text)
    ordered = (
        ["/system/fonts/NotoNaskhArabic-Bold.ttf", "/system/fonts/NotoNaskhArabic-Regular.ttf"]
        if has_arabic
        else []
    ) + FONT_CANDIDATES
    for c in ordered:
        if os.path.isfile(c):
            try:
                return ImageFont.truetype(c, size=size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def pick_quote(user_id: int | str | None = None) -> str:
    quotes = t_list("quotes", user_id=user_id)
    return random.choice(quotes) if quotes else "Keep moving forward."


def render_progress_card(user_id: int, quote: str | None = None) -> bytes:
    from PIL import Image, ImageDraw

    if not quote:
        quote = pick_quote(user_id)

    today = datetime.date.today()
    week_days = [(today - datetime.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    with get_conn() as conn:
        habits = conn.execute(
            "SELECT * FROM habits WHERE user_id = ? ORDER BY streak DESC, id ASC", (user_id,)
        ).fetchall()
        done_week = {
            row["done_date"]
            for row in conn.execute(
                "SELECT DISTINCT done_date FROM checkins WHERE user_id = ? AND done_date >= ?",
                (user_id, week_days[0]),
            ).fetchall()
        }

    top_streak = max((h["streak"] for h in habits), default=0)
    best_streak = max((h["best_streak"] for h in habits), default=0)
    height = max(560, 390 + min(len(habits), 6) * 46)

    im = Image.new("RGB", (900, height), (10, 15, 26))
    draw = ImageDraw.Draw(im)

    draw.rounded_rectangle([24, 24, 876, height - 24], radius=24, fill=(18, 26, 43), outline=(0, 216, 255), width=2)

    f_title = load_font(34, quote)
    f_sub = load_font(22, quote)
    f_body = load_font(24, quote)
    f_small = load_font(18, quote)

    draw.text((52, 48), t("card_title", user_id=user_id), font=f_title, fill=(0, 216, 255))
    draw.text((52, 94), today.strftime("%Y-%m-%d"), font=f_small, fill=(139, 160, 198))

    draw.rounded_rectangle([610, 44, 846, 114], radius=16, fill=(12, 54, 48), outline=(0, 230, 118), width=2)
    draw.text((728, 79), f"STREAK: {top_streak}d (MAX {best_streak})", font=f_small, fill=(0, 230, 118), anchor="mm")

    wrapped_q = "\n".join(textwrap.wrap(f'"{quote}"', width=44)[:3])
    draw.rounded_rectangle([48, 134, 852, 248], radius=14, fill=(13, 19, 34), outline=(42, 59, 94), width=1)
    draw.multiline_text((450, 191), wrapped_q, font=f_sub, fill=(230, 241, 255), anchor="mm", align="center")

    draw.text((52, 272), t("card_week_title", user_id=user_id), font=f_small, fill=(139, 160, 198))
    for i, day_iso in enumerate(week_days):
        cx = 92 + i * 114
        active = day_iso in done_week
        fill_c = (0, 230, 118) if active else (28, 38, 60)
        draw.ellipse([cx - 18, 304, cx + 18, 340], fill=fill_c, outline=(0, 216, 255) if active else (55, 72, 108))
        draw.text((cx, 354), day_iso[-2:], font=f_small, fill=(230, 241, 255) if active else (120, 140, 170), anchor="ma")

    y = 398
    today_iso = today.isoformat()
    for h in habits[:6]:
        is_today = h["last_done_date"] == today_iso
        badge_col = (0, 230, 118) if is_today else (255, 193, 7)
        status = "DONE" if is_today else "TODO"
        draw.rounded_rectangle([48, y, 852, y + 38], radius=10, fill=(13, 19, 34))
        draw.text((66, y + 19), f"• {h['title'][:36]}", font=f_body, fill=(230, 241, 255), anchor="lm")
        draw.text((834, y + 19), f"[{status}] {h['streak']}d", font=f_small, fill=badge_col, anchor="rm")
        y += 46

    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def complete_habit(user_id: int, habit_id: int) -> tuple[bool, int]:
    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=1)).isoformat()
    today_iso = today.isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, user_id)).fetchone()
        if not row:
            return False, 0
        if row["last_done_date"] == today_iso:
            return False, row["streak"]
        new_streak = row["streak"] + 1 if row["last_done_date"] == yesterday else 1
        best = max(row["best_streak"], new_streak)
        conn.execute(
            "UPDATE habits SET streak = ?, best_streak = ?, last_done_date = ? WHERE id = ?",
            (new_streak, best, today_iso, habit_id),
        )
        conn.execute(
            "INSERT OR IGNORE INTO checkins(user_id, habit_id, done_date) VALUES(?, ?, ?)",
            (user_id, habit_id, today_iso),
        )
        return True, new_streak


def render_studio(handler: Any, port: int) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    today = datetime.date.today()
    today_iso = today.isoformat()
    week_days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    with get_conn() as conn:
        habits = conn.execute("SELECT * FROM habits WHERE user_id = 0 ORDER BY streak DESC, id ASC").fetchall()
        done_week = {
            row["done_date"]
            for row in conn.execute(
                "SELECT DISTINCT done_date FROM checkins WHERE user_id = 0 AND done_date >= ?",
                (week_days[0].isoformat(),),
            ).fetchall()
        }
    quotes = t_list("quotes", lang_override=lang)
    quote = random.choice(quotes) if quotes else pick_quote()
    css = ("<style>.mv-quote{font-family:'Unbounded','Onest',system-ui,sans-serif;font-weight:500;font-size:clamp(18px,2.4vw,24px);line-height:1.45;padding:22px 24px;border-radius:18px;"
           "background:linear-gradient(135deg,color-mix(in srgb,var(--brand) 16%,transparent),color-mix(in srgb,var(--brand2) 10%,transparent));border:1px solid var(--line);position:relative}"
           ".mv-quote:before{content:'“';position:absolute;top:-18px;left:14px;font-size:72px;color:var(--brand);opacity:.35}"
           ".mv-week{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-top:16px}.mv-day{text-align:center;font-size:12px;color:var(--muted)}"
           ".mv-day i{display:grid;place-items:center;aspect-ratio:1;border-radius:14px;margin-bottom:6px;font-style:normal;font-weight:700;font-size:15px;"
           "background:var(--surface2);border:1px solid var(--line);color:var(--muted);transition:transform .2s}"
           ".mv-day.on i{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;border-color:transparent;box-shadow:0 6px 18px -8px var(--brand)}"
           ".mv-day.today i{outline:2px solid var(--brand);outline-offset:2px}"
           ".mv-habit{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:var(--surface2);margin-bottom:8px;transition:transform .2s}"
           ".mv-habit:hover{transform:translateY(-1px)}.mv-habit b{flex:1;font-weight:600;word-break:break-word}"
           ".mv-streak{font-size:13px;color:var(--muted);white-space:nowrap}.mv-habit.done .mv-streak{color:#22c55e;font-weight:600}"
           ".mv-add{display:flex;gap:8px;margin-top:12px}.mv-add .pb-input-wrap,.mv-add>input{flex:1}</style>")
    days_unit = T("days_unit")
    rows = []
    for h in habits:
        done = h["last_done_date"] == today_iso
        btn = (web.button(T("w_done"), cls="pb-btn-sm", kind="ghost", icon_name="check", disabled=True) if done
               else web.button(T("w_mark"), cls="pb-btn-sm mv-check", icon_name="check", **{"data-id": str(h["id"])}))
        rows.append(f'<div class="mv-habit{" done" if done else ""}"><b>{web.esc(h["title"])}</b>'
                    f'<span class="mv-streak">🔥 {int(h["streak"] or 0)} {web.esc(days_unit)}</span>{btn}</div>')
    habits_html = "".join(rows) or web.empty_state(T("w_no_habits"), "list")
    week_html = "".join(
        f'<div class="mv-day{" on" if d.isoformat() in done_week else ""}{" today" if d == today else ""}"><i>{d.day}</i>{web.esc(T("w_wd" + str(d.isoweekday())))}</div>'
        for d in week_days)
    done_today = sum(1 for h in habits if h["last_done_date"] == today_iso)
    best = max((int(h["streak"] or 0) for h in habits), default=0)
    left = web.card(T("w_card_today"),
        f'<div class="mv-quote">{web.esc(quote)}</div>'
        + f'<h4 style="margin:18px 0 0">{web.esc(T("w_week"))}</h4><div class="mv-week">{week_html}</div>'
        + '<div class="pb-row" style="margin-top:16px">' + web.link_button(T("w_card_btn"), "/api/card", kind="ghost", icon_name="image", target="_blank") + "</div>",
        icon_name="sparkles")
    right = web.card(T("w_card_habits"),
        f'<div id="habits">{habits_html}</div>'
        + '<form class="mv-add" id="add">' + web.input_("title", T("ph_habit_name"), icon_name="plus", maxlength="64", required=True, autocomplete="off")
        + web.button(re.sub(r"^[^\w(]+", "", T("btn_add_habit")), "addbtn", type="submit", icon_name="plus") + "</form>", icon_name="list")
    st = web.stats([(T("w_st_habits"), str(len(habits)), None, "list"), (T("w_st_today"), f"{done_today}", None, "check"),
                    (T("w_st_best"), str(best), None, "zap"), (T("w_st_week"), str(len(done_week)), None, "clock")])
    hero = web.hero(T("w_title"), T("w_hero"), "🔥", chips=[T("w_chip_streaks"), T("w_chip_quotes"), "PNG"])
    web.send_page(handler, lang, title=T("w_title"), emoji="🔥", brand="#f97316", port=port, hero_html=hero,
                  body=css + st + web.grid(left, right, min_width=330), script=MOTIVATOR_JS)


MOTIVATOR_JS = r"""
document.querySelectorAll('.mv-check').forEach(b=>b.onclick=async()=>{pb.busy(b,true);
  try{const r=await fetch('/api/checkin?id='+b.dataset.id,{method:'POST'});if(!r.ok)throw new Error('HTTP '+r.status);pb.toast(pb.t('w_marked'));setTimeout(()=>location.reload(),500)}
  catch(e){pb.busy(b,false);pb.toast(pb.t('error_conn'),true)}});
document.getElementById('add').addEventListener('submit',async e=>{e.preventDefault();const v=document.getElementById('title').value.trim();if(!v)return;
  const b=document.getElementById('addbtn');pb.busy(b,true);
  try{await fetch('/api/add_habit',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'title='+encodeURIComponent(v),redirect:'manual'});location.reload()}
  catch(err){pb.busy(b,false);pb.toast(pb.t('error_conn'),true)}});
"""


def start_web_dashboard(port: int) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            u = urllib.parse.urlparse(self.path)
            if u.path == "/api/card":
                png = render_progress_card(0, pick_quote())
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return

            render_studio(self, port)

        def do_POST(self) -> None:
            u = urllib.parse.urlparse(self.path)
            if u.path == "/api/checkin":
                qs = urllib.parse.parse_qs(u.query)
                hid = (qs.get("id") or [""])[0]
                if hid.isdigit():
                    complete_habit(0, int(hid))
                self.send_response(200)
                self.end_headers()
            elif u.path == "/api/add_habit":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(min(length, 4096)).decode("utf-8", errors="replace")
                params = urllib.parse.parse_qs(raw)
                title = (params.get("title") or [""])[0].strip()
                if title:
                    with get_conn() as conn:
                        conn.execute("INSERT INTO habits (user_id, title) VALUES (0, ?)", (title[:64],))
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
            else:
                self.send_error(404)

    class Reusable(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    def serve() -> None:
        try:
            with Reusable((os.environ.get("BIND_HOST", "127.0.0.1"), port), Handler) as srv:
                print(f"[PYBIONIC_WEB:{port}]", flush=True)
                log("log_web_started", port=port)
                srv.serve_forever()
        except Exception as exc:
            log("log_error", err=f"Web server failed on port {port}: {exc}")

    threading.Thread(target=serve, daemon=True).start()


def run_bot(token: str) -> None:
    import telebot
    from telebot import types

    init_db()
    bot = telebot.TeleBot(token, parse_mode="HTML")

    def build_main_reply_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(core.btn("kb_habits", uid)),
            types.KeyboardButton(core.btn("kb_card", uid)),
        )
        kb.row(
            types.KeyboardButton(core.btn("kb_quote", uid)),
            types.KeyboardButton(core.btn("kb_add_habit", uid)),
        )
        kb.row(
            types.KeyboardButton(core.btn("btn_lang", uid)),
            types.KeyboardButton(core.btn("btn_help", uid)),
        )
        return kb

    def build_habits_checkin_kb(uid: int) -> types.ReplyKeyboardMarkup:
        today_iso = datetime.date.today().isoformat()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM habits WHERE user_id = ? ORDER BY id ASC", (uid,)).fetchall()
        for r in rows:
            mark = "✅" if r["last_done_date"] == today_iso else "⬜"
            btn_txt = f"{mark} {r['title']} ({r['streak']}d)"
            kb.row(types.KeyboardButton(btn_txt))
        kb.row(types.KeyboardButton(core.btn("btn_menu", uid)))
        return kb

    @bot.message_handler(commands=["start"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        clear_user_state(uid)
        bot.reply_to(msg, t("tg_welcome", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(commands=["help"])
    def on_help(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_help_text", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(commands=["lang", "language"])
    def on_lang_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            t("tg_lang_title", user_id=uid),
            reply_markup=build_reply_language_keyboard(user_id=uid, back_text=core.btn("btn_menu", uid)),
        )

    @bot.message_handler(func=lambda m: bool(m.text and parse_lang_choice(m.text)))
    def on_lang_chosen(msg: Any) -> None:
        uid = msg.from_user.id
        code = parse_lang_choice(msg.text)
        if code:
            set_user_lang(uid, code)
            bot.reply_to(msg, t("tg_lang_changed", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_menu", "btn_cancel"))
    def on_back(msg: Any) -> None:
        uid = msg.from_user.id
        clear_user_state(uid)
        bot.reply_to(msg, "Главное меню:", reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_lang"))
    def on_lang_btn(msg: Any) -> None:
        on_lang_cmd(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_help"))
    def on_help_btn(msg: Any) -> None:
        on_help(msg)

    @bot.message_handler(commands=["quote"])
    def on_quote(msg: Any) -> None:
        uid = msg.from_user.id
        q = pick_quote(uid)
        bot.reply_to(msg, f"✨ <i>{q}</i>", reply_markup=build_main_reply_kb(uid))
        log("log_quote_sent", user=uid)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_quote"))
    def on_quote_btn(msg: Any) -> None:
        on_quote(msg)

    @bot.message_handler(commands=["card"])
    def on_card(msg: Any) -> None:
        uid = msg.from_user.id

        def send_card():
            png = render_progress_card(uid)
            bot.send_photo(
                msg.chat.id,
                io.BytesIO(png),
                caption=t("card_caption", user_id=uid),
                reply_markup=build_main_reply_kb(uid),
            )
            log("log_card_sent", user=uid)

        threading.Thread(target=send_card, daemon=True).start()

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_card"))
    def on_card_btn(msg: Any) -> None:
        on_card(msg)

    @bot.message_handler(commands=["done"])
    def on_done(msg: Any) -> None:
        uid = msg.from_user.id
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM habits WHERE user_id = ?", (uid,)).fetchall()
        if not rows:
            bot.reply_to(
                msg,
                "У вас пока нет привычек! Нажмите <b>➕ Добавить привычку</b> на клавиатуре ниже.",
                reply_markup=build_main_reply_kb(uid),
            )
            return
        bot.reply_to(
            msg,
            t("tg_pick_done", user_id=uid),
            reply_markup=build_habits_checkin_kb(uid),
        )

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_habits"))
    def on_done_btn(msg: Any) -> None:
        on_done(msg)

    @bot.message_handler(commands=["add"])
    def on_add(msg: Any) -> None:
        uid = msg.from_user.id
        arg = (msg.text or "").split(maxsplit=1)[1].strip() if " " in (msg.text or "") else ""
        if arg:
            with get_conn() as conn:
                conn.execute("INSERT INTO habits (user_id, title) VALUES (?, ?)", (uid, arg[:64]))
            bot.reply_to(msg, t("tg_habit_added", user_id=uid, title=arg), reply_markup=build_habits_checkin_kb(uid))
            log("log_habit_added", title=arg)
        else:
            set_user_state(uid, "WAITING_HABIT_NAME")
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
            kb.row(types.KeyboardButton(core.btn("btn_menu", uid)))
            bot.reply_to(
                msg,
                "✏️ <b>Введите название привычки:</b>\n\n(Например: <i>Чтение 20 мин</i> или <i>Утренняя пробежка</i>)",
                reply_markup=kb,
            )

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_add_habit"))
    def on_add_btn(msg: Any) -> None:
        # текст кнопки не должен стать названием привычки — спрашиваем название
        msg.text = "/add"
        on_add(msg)

    # Habit checkin button handler (detects '[✅/⬜] Title (Xd)')
    @bot.message_handler(func=lambda m: bool(m.text and (m.text.startswith("✅ ") or m.text.startswith("⬜ "))))
    def on_habit_checkin_tap(msg: Any) -> None:
        uid = msg.from_user.id
        txt = msg.text or ""
        # Match habit title
        m = re.match(r"^[✅⬜]\s*(.+?)\s*\(\d+d\)$", txt)
        if not m:
            return
        title = m.group(1).strip()
        with get_conn() as conn:
            row = conn.execute("SELECT id FROM habits WHERE user_id = ? AND title = ?", (uid, title)).fetchone()
            if not row:
                row = conn.execute("SELECT id FROM habits WHERE user_id = ? AND title LIKE ?", (uid, f"{title}%")).fetchone()

        if row:
            hid = row["id"]
            changed, streak = complete_habit(uid, hid)
            msg_txt = t("tg_streak_up", user_id=uid, streak=streak) if changed else t("tg_already_done", user_id=uid)
            bot.reply_to(msg, f"🔥 {msg_txt}", reply_markup=build_habits_checkin_kb(uid))
        else:
            bot.reply_to(msg, "Привычка не найдена.", reply_markup=build_main_reply_kb(uid))

    # General text message handler (handles WAITING_HABIT_NAME state)
    @bot.message_handler(content_types=["text"])
    def on_general_text(msg: Any) -> None:
        uid = msg.from_user.id
        state = get_user_state(uid)
        if state == "WAITING_HABIT_NAME":
            clear_user_state(uid)
            title = (msg.text or "").strip()
            if title:
                with get_conn() as conn:
                    conn.execute("INSERT INTO habits (user_id, title) VALUES (?, ?)", (uid, title[:64]))
                bot.reply_to(
                    msg,
                    t("tg_habit_added", user_id=uid, title=title),
                    reply_markup=build_habits_checkin_kb(uid),
                )
                log("log_habit_added", title=title)
                return
        bot.reply_to(msg, "Главное меню:", reply_markup=build_main_reply_kb(uid))

    def reminder_loop() -> None:
        while True:
            try:
                now = datetime.datetime.now()
                hhmm = now.strftime("%H:%M")
                today_iso = now.date().isoformat()
                with get_conn() as conn:
                    due = conn.execute(
                        "SELECT user_id FROM reminders WHERE hhmm = ? AND last_sent_date != ?",
                        (hhmm, today_iso),
                    ).fetchall()
                    for row in due:
                        uid = row["user_id"]
                        png = render_progress_card(uid)
                        bot.send_photo(
                            uid,
                            io.BytesIO(png),
                            caption=t("tg_daily_ping", user_id=uid),
                            reply_markup=build_main_reply_kb(uid),
                        )
                        conn.execute("UPDATE reminders SET last_sent_date = ? WHERE user_id = ?", (today_iso, uid))
                        log("log_daily_sent", user=uid)
            except Exception as exc:
                log("log_error", err=str(exc))
            time.sleep(30)

    threading.Thread(target=reminder_loop, daemon=True).start()
    log("log_started")
    core.start_polling(bot, timeout=30, long_polling_timeout=25)


def main() -> int:
    init_db()
    port_raw = os.environ.get("WEB_PORT", "8092").strip()
    if port_raw.isdigit() and int(port_raw) > 0:
        start_web_dashboard(int(port_raw))

    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        run_bot(token)
    elif port_raw.isdigit() and int(port_raw) > 0:
        log("log_web_only", port=port_raw)
        while True:
            time.sleep(3600)
    else:
        log("err_missing_token")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
