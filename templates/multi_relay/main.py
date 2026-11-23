"""Multi-Service Notifier — Watch YouTube/GitHub/RSS & Broadcast to Telegram, Discord, Slack & Webhooks.
100% ReplyKeyboardMarkup (all buttons next to keyboard, zero inline text buttons), 24 languages, and Cyberpunk Web UI.
"""

from __future__ import annotations

import pybionic_core as core
import pybionic_web as web
import html
import http.server
import json
import os
import re
import socketserver
import sqlite3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
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
)


def db_path() -> Path:
    base = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    base.mkdir(parents=True, exist_ok=True)
    return base / "relay.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                target TEXT NOT NULL UNIQUE,
                label TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS seen_items (
                source_id INTEGER NOT NULL,
                item_uid TEXT NOT NULL,
                PRIMARY KEY (source_id, item_uid)
            );
            CREATE TABLE IF NOT EXISTS broadcast_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                targets TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )
        init_src = os.environ.get("INITIAL_FEED_URL", "").strip()
        if init_src:
            kind = "gh" if "github.com/" in init_src and "/releases" not in init_src and ".atom" not in init_src else "rss"
            conn.execute(
                "INSERT OR IGNORE INTO sources(kind, target, label) VALUES(?, ?, ?)",
                (kind, init_src, init_src[:48]),
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


def log_broadcast(source: str, title: str, url: str, targets: list[str]) -> None:
    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO broadcast_logs (source, title, url, created_at, targets)
                VALUES (?, ?, ?, ?, ?)
                """,
                (source, title, url, int(time.time()), ", ".join(targets)),
            )
            conn.execute("DELETE FROM broadcast_logs WHERE id NOT IN (SELECT id FROM broadcast_logs ORDER BY id DESC LIMIT 50)")
    except Exception:
        pass


def normalize_feed_url(kind: str, target: str) -> str:
    tgt = target.strip()
    if kind == "yt":
        if tgt.startswith("http") and "videos.xml" in tgt:
            return tgt
        cid = tgt.rstrip("/").split("/")[-1]
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    if kind == "gh":
        if tgt.startswith("http") and tgt.endswith(".atom"):
            return tgt
        repo = tgt.replace("https://github.com/", "").strip("/")
        return f"https://github.com/{repo}/releases.atom"
    return tgt


def fetch_feed_items(url: str) -> list[tuple[str, str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "PyBionic-MultiRelay/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        xml_bytes = resp.read()
    root = ET.fromstring(xml_bytes)
    items: list[tuple[str, str, str]] = []

    # RSS 2.0
    for item in root.findall(".//channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        uid = (item.findtext("guid") or link or title).strip()
        if uid:
            items.append((uid, title, link))

    # Atom (YouTube / GitHub Releases)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//a:entry", ns):
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        uid = (entry.findtext("a:id", default="", namespaces=ns) or title).strip()
        link_el = entry.find("a:link", ns)
        link = link_el.attrib.get("href", "") if link_el is not None else ""
        if uid:
            items.append((uid, title, link))

    return items[:10]


def post_json(url: str, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "PyBionic-MultiRelay/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15):
        pass


def broadcast(source_label: str, title: str, link: str) -> list[str]:
    text = t("msg_new_item", source=source_label, title=title, link=link)
    delivered: list[str] = []

    tg_token = os.environ.get("BOT_TOKEN", "").strip()
    tg_chat = os.environ.get("TG_CHAT_ID", "").strip()
    if tg_token and tg_chat:
        try:
            post_json(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                {"chat_id": tg_chat, "text": text, "disable_web_page_preview": False},
            )
            delivered.append("Telegram")
            log("log_sent_tg", title=title[:40])
        except Exception as exc:
            log("log_err_target", target="Telegram", err=str(exc))

    dc_hook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if dc_hook:
        try:
            post_json(dc_hook, {"content": text})
            delivered.append("Discord")
            log("log_sent_dc", title=title[:40])
        except Exception as exc:
            log("log_err_target", target="Discord", err=str(exc))

    webhook = os.environ.get("WEBHOOK_URL", "").strip()
    if webhook:
        try:
            post_json(webhook, {"source": source_label, "title": title, "url": link, "text": text})
            delivered.append("Webhook")
            log("log_sent_hook", title=title[:40])
        except Exception as exc:
            log("log_err_target", target="Webhook", err=str(exc))

    if delivered:
        log_broadcast(source_label, title, link, delivered)
    return delivered


def poll_once() -> int:
    new_count = 0
    with get_conn() as conn:
        sources = conn.execute("SELECT * FROM sources").fetchall()
        for src in sources:
            feed_url = normalize_feed_url(src["kind"], src["target"])
            try:
                items = fetch_feed_items(feed_url)
                already = conn.execute(
                    "SELECT COUNT(*) FROM seen_items WHERE source_id = ?", (src["id"],)
                ).fetchone()[0]
                is_initial_seed = already == 0
                for uid, title, link in reversed(items):
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO seen_items(source_id, item_uid) VALUES(?, ?)",
                        (src["id"], uid),
                    )
                    if cur.rowcount > 0 and not is_initial_seed:
                        broadcast(src["label"] or src["target"], title, link)
                        new_count += 1
                if is_initial_seed and items:
                    log("log_seeded", source=src["label"] or src["target"], n=len(items))
            except Exception as exc:
                log("log_err_feed", url=feed_url[:50], err=str(exc))
    return new_count


def render_studio(handler: Any, port: int) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    strip = lambda s: re.sub(r"^[^\w(]+", "", s)  # noqa: E731
    with get_conn() as conn:
        sources = conn.execute("SELECT * FROM sources ORDER BY id DESC").fetchall()
        logs = conn.execute("SELECT * FROM broadcast_logs ORDER BY id DESC LIMIT 10").fetchall()
        total_logs = conn.execute("SELECT COUNT(*) FROM broadcast_logs").fetchone()[0]
    kinds = {"rss": ("RSS", "#f59e0b", "wave"), "gh": ("GitHub", "#22c55e", "code"), "yt": ("YouTube", "#ef4444", "play")}
    css = ("<style>.mr-row{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:var(--surface2);margin-bottom:8px}"
           ".mr-ico{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;flex:none}.mr-main{flex:1;min-width:0}"
           ".mr-main b{display:block;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
           ".mr-main small{color:var(--muted);display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
           ".mr-tag{font-size:11px;font-weight:700;padding:3px 8px;border-radius:99px}"
           ".mr-ch{display:flex;flex-wrap:wrap;gap:8px}.mr-chip{display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:99px;font-size:13px;border:1px solid var(--line);background:var(--surface2)}"
           ".mr-chip.on{border-color:#22c55e66;color:#22c55e}.mr-chip.off{color:var(--muted)}"
           ".mr-log{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--line)}.mr-log:last-child{border:0}"
           ".mr-log time{font-size:12.5px;color:var(--muted);white-space:nowrap;padding-top:2px}.mr-log a{color:var(--text);font-weight:600;text-decoration:none}"
           ".mr-log a:hover{color:var(--brand)}.mr-log small{display:block;color:var(--muted);font-size:12.5px;margin-top:2px}</style>")
    src_rows = []
    for r in sources:
        name, color, ico = kinds.get(r["kind"], (r["kind"].upper(), "#64748b", "link"))
        src_rows.append(
            f'<div class="mr-row"><span class="mr-ico" style="background:{color}22;color:{color}">{web.icon(ico, 18)}</span>'
            f'<div class="mr-main"><b>{web.esc(r["label"] or r["target"])}</b><small>{web.esc(r["target"])}</small></div>'
            f'<span class="mr-tag" style="background:{color}22;color:{color}">{web.esc(name)}</span>'
            + web.button("", cls="pb-btn-sm mr-del", kind="ghost", icon_name="trash", title=T("delete"), **{"data-id": str(r["id"]), "aria-label": T("delete")}) + "</div>")
    sources_html = "".join(src_rows) or web.empty_state(T("w_no_sources"), "wave")
    log_rows = []
    for item in logs:
        dt = time.strftime("%d.%m %H:%M", time.localtime(item["created_at"]))
        url = item["url"] if str(item["url"]).startswith(("http://", "https://")) else "#"
        log_rows.append(f'<div class="mr-log"><time>{dt}</time><div><a href="{web.esc(url)}" target="_blank" rel="noopener">{web.esc(item["title"])}</a>'
                        f'<small>{web.esc(item["source"])} → {web.esc(item["targets"])}</small></div></div>')
    logs_html = "".join(log_rows) or web.empty_state(T("no_history"), "clock")
    channels = [("Telegram", bool(os.environ.get("BOT_TOKEN", "").strip() and os.environ.get("TG_CHAT_ID", "").strip())),
                ("Discord", bool(os.environ.get("DISCORD_WEBHOOK_URL", "").strip())), ("Webhook", bool(os.environ.get("WEBHOOK_URL", "").strip()))]
    ch_html = '<div class="mr-ch">' + "".join(
        f'<span class="mr-chip {"on" if on else "off"}">{web.icon("check" if on else "x", 14)}{name}</span>' for name, on in channels) + "</div>"
    actions = web.card(T("w_card_actions"),
        '<div class="pb-row">' + web.button(strip(T("btn_check_now")), "poll", icon_name="refresh")
        + web.button(strip(T("btn_test_broadcast")), "test", kind="ghost", icon_name="send") + "</div>"
        + f'<h4 style="margin:18px 0 10px">{web.esc(T("w_channels"))}</h4>' + ch_html
        + web.note(T("w_channels_note"), "info"), icon_name="zap")
    add = web.card(T("btn_add_source"),
        '<form id="add">' + web.field(T("w_kind"), web.segmented("kind", [("rss", "RSS / Atom"), ("gh", "GitHub"), ("yt", "YouTube")], "rss",
                                     sub={"rss": T("w_rss_sub"), "gh": T("w_gh_sub"), "yt": T("w_yt_sub")}, icons={"rss": "wave", "gh": "code", "yt": "play"}))
        + web.field(T("w_target"), web.input_("target", "https://example.com/feed.xml", icon_name="link", required=True, autocomplete="off"))
        + web.field(T("ph_label"), web.input_("label", T("ph_label"), icon_name="list", autocomplete="off"))
        + web.button(strip(T("btn_add_source")), "addbtn", type="submit", icon_name="plus") + "</form>", icon_name="plus")
    src_card = web.card(T("web_sources"), f'<div id="sources">{sources_html}</div>', icon_name="wave", aside=f'<span class="mr-tag" style="background:var(--surface2)">{len(sources)}</span>')
    hist = web.card(T("broadcast_history"), logs_html, icon_name="clock")
    st = web.stats([(T("w_st_sources"), str(len(sources)), None, "wave"), (T("w_st_sent"), str(total_logs), None, "send"),
                    (T("w_st_channels"), str(sum(1 for _, on in channels if on)), None, "zap")])
    hero = web.hero(T("w_title"), T("w_hero"), "📡", chips=["RSS", "GitHub Releases", "YouTube", "Telegram · Discord"])
    web.send_page(handler, lang, title=T("w_title"), emoji="📡", brand="#06b6d4", port=port, hero_html=hero,
                  body=css + st + web.grid(actions, add, min_width=330) + web.grid(src_card, hist, min_width=330), script=RELAY_JS)


RELAY_JS = r"""
const $=s=>document.querySelector(s);
const PH={rss:'https://example.com/feed.xml',gh:'owner/repo',yt:'UCxxxxxxxxxxxxxxxxxxxxxx'};
$('#kind').addEventListener('change',()=>{$('#target').placeholder=PH[$('#kind').dataset.value]||''});
const form=(o)=>Object.entries(o).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&');
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:body||'',redirect:'manual'});return r}
$('#poll').onclick=async()=>{const b=$('#poll');pb.busy(b,true);try{await post('/poll');pb.toast(pb.t('w_poll_started'));setTimeout(()=>location.reload(),4000)}catch(e){pb.busy(b,false);pb.toast(pb.t('error_conn'),true)}};
$('#test').onclick=async()=>{const b=$('#test');pb.busy(b,true);try{await post('/test_broadcast');pb.toast(pb.t('w_test_sent'));setTimeout(()=>location.reload(),2500)}catch(e){pb.busy(b,false);pb.toast(pb.t('error_conn'),true)}};
$('#add').addEventListener('submit',async e=>{e.preventDefault();const t=$('#target').value.trim();if(!t)return;const b=$('#addbtn');pb.busy(b,true);
  try{await post('/add',form({kind:$('#kind').dataset.value,target:t,label:$('#label').value.trim()}));location.reload()}catch(err){pb.busy(b,false);pb.toast(pb.t('error_conn'),true)}});
document.querySelectorAll('.mr-del').forEach(b=>b.onclick=async()=>{if(!confirm(pb.t('w_del_confirm')))return;pb.busy(b,true);
  try{await fetch('/del?id='+b.dataset.id,{redirect:'manual'});b.closest('.mr-row').remove();pb.toast(pb.t('deleted'))}catch(e){pb.busy(b,false);pb.toast(pb.t('error_conn'),true)}});
"""


def start_web_ui(port: int) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            u = urllib.parse.urlparse(self.path)
            render_studio(self, port)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 8192)).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw)

            if self.path == "/add":
                kind = (params.get("kind") or ["rss"])[0]
                target = (params.get("target") or [""])[0].strip()
                label = (params.get("label") or [""])[0].strip()
                if target:
                    with get_conn() as conn:
                        conn.execute(
                            "INSERT OR IGNORE INTO sources(kind, target, label) VALUES(?, ?, ?)",
                            (kind, target, label or target[:48]),
                        )
                    log("log_source_added", target=target)
            elif self.path == "/poll":
                threading.Thread(target=poll_once, daemon=True).start()
            elif self.path == "/test_broadcast":
                threading.Thread(
                    target=lambda: broadcast("PyBionic Studio", "Test Notification: Relay link online! 🚀", "https://github.com/nasibullo03"),
                    daemon=True,
                ).start()

            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

    orig_get = Handler.do_GET

    def wrapped_get(self: Handler) -> None:
        if self.path.startswith("/del?"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            sid = (qs.get("id") or [""])[0]
            if sid.isdigit():
                with get_conn() as conn:
                    conn.execute("DELETE FROM sources WHERE id = ?", (int(sid),))
                    conn.execute("DELETE FROM seen_items WHERE source_id = ?", (int(sid),))
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        orig_get(self)

    Handler.do_GET = wrapped_get  # type: ignore[method-assign]

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


def run_telegram_bot(token: str) -> None:
    import telebot
    from telebot import types

    init_db()
    bot = telebot.TeleBot(token, parse_mode="HTML")

    def build_main_reply_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(core.btn("kb_check_updates", uid)),
            types.KeyboardButton(core.btn("kb_test_broadcast", uid)),
        )
        kb.row(
            types.KeyboardButton(core.btn("kb_my_sources", uid)),
            types.KeyboardButton(core.btn("kb_add_source", uid)),
        )
        kb.row(
            types.KeyboardButton(core.btn("btn_lang", uid)),
            types.KeyboardButton(core.btn("btn_help", uid)),
        )
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

    @bot.message_handler(commands=["sources"])
    def on_sources(msg: Any) -> None:
        uid = msg.from_user.id
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM sources ORDER BY id ASC").fetchall()
        if not rows:
            bot.reply_to(
                msg,
                "Список источников пуст. Нажмите <b>➕ Добавить источник</b> на клавиатуре ниже!",
                reply_markup=build_main_reply_kb(uid),
            )
            return
        lines = ["<b>📡 Активные источники:</b>\n"]
        for r in rows:
            lines.append(f"• <b>[{r['kind'].upper()}]</b> {html.escape(r['label'] or r['target'])}")
        bot.reply_to(msg, "\n".join(lines), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_my_sources"))
    def on_sources_btn(msg: Any) -> None:
        on_sources(msg)

    @bot.message_handler(commands=["poll"])
    def on_poll_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        status = bot.reply_to(msg, "⏳ Проверка источников на наличие обновлений...", reply_markup=build_main_reply_kb(uid))

        def do_poll():
            n = poll_once()
            bot.edit_message_text(f"✅ Проверка завершена! Новых записей отправлено: {n}", msg.chat.id, status.message_id)

        threading.Thread(target=do_poll, daemon=True).start()

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_check_updates"))
    def on_poll_btn(msg: Any) -> None:
        on_poll_cmd(msg)

    @bot.message_handler(commands=["test"])
    def on_test_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        status = bot.reply_to(msg, "⏳ Отправка тестовой рассылки...", reply_markup=build_main_reply_kb(uid))

        def do_test():
            res = broadcast("PyBionic Studio", "Test Notification: Relay link online! 🚀", "https://github.com/nasibullo03")
            out_txt = f"📢 Тестовая рассылка успешно доставлена в: <b>{', '.join(res)}</b>" if res else "⚠️ Не настроен ни один получатель (BOT_TOKEN + TG_CHAT_ID, DISCORD_WEBHOOK_URL или WEBHOOK_URL)!"
            bot.edit_message_text(out_txt, msg.chat.id, status.message_id)

        threading.Thread(target=do_test, daemon=True).start()

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_test_broadcast"))
    def on_test_btn(msg: Any) -> None:
        on_test_cmd(msg)

    @bot.message_handler(commands=["add"])
    def on_add(msg: Any) -> None:
        uid = msg.from_user.id
        arg = (msg.text or "").split(maxsplit=1)[1].strip() if " " in (msg.text or "") else ""
        if arg:
            kind = "gh" if "github.com/" in arg and "/releases" not in arg and ".atom" not in arg else ("yt" if arg.startswith("UC") else "rss")
            with get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO sources(kind, target, label) VALUES(?, ?, ?)",
                    (kind, arg, arg[:48]),
                )
            bot.reply_to(msg, f"✅ Источник <code>{arg}</code> добавлен!", reply_markup=build_main_reply_kb(uid))
        else:
            set_user_state(uid, "WAITING_FEED_URL")
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
            kb.row(types.KeyboardButton(core.btn("btn_menu", uid)))
            bot.reply_to(
                msg,
                "✏️ <b>Отправьте URL или репозиторий:</b>\n\n• RSS URL: <code>https://example.com/feed.xml</code>\n• GitHub: <code>owner/repo</code>\n• YouTube: <code>UC...</code>",
                reply_markup=kb,
            )

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_add_source"))
    def on_add_btn(msg: Any) -> None:
        on_add(msg)

    @bot.message_handler(content_types=["text"])
    def on_text(msg: Any) -> None:
        uid = msg.from_user.id
        state = get_user_state(uid)
        if state == "WAITING_FEED_URL":
            clear_user_state(uid)
            raw = (msg.text or "").strip()
            if raw:
                kind = "gh" if "github.com/" in raw and "/releases" not in raw and ".atom" not in raw else ("yt" if raw.startswith("UC") else "rss")
                with get_conn() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO sources(kind, target, label) VALUES(?, ?, ?)",
                        (kind, raw, raw[:48]),
                    )
                bot.reply_to(msg, f"✅ Источник <code>{raw}</code> успешно добавлен!", reply_markup=build_main_reply_kb(uid))
                return
        bot.reply_to(msg, "Главное меню:", reply_markup=build_main_reply_kb(uid))

    log("log_started")
    core.start_polling(bot, timeout=30, long_polling_timeout=25)


def main() -> int:
    init_db()
    log("log_boot")
    port_raw = os.environ.get("WEB_PORT", "8090").strip()
    if port_raw.isdigit() and int(port_raw) > 0:
        start_web_ui(int(port_raw))

    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        threading.Thread(target=lambda: run_telegram_bot(token), daemon=True).start()

    interval = max(30, int(os.environ.get("POLL_INTERVAL_SEC", "180") or "180"))
    log("log_polling_started", sec=interval)
    while True:
        poll_once()
        time.sleep(interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
