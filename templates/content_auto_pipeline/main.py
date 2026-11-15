import pybionic_core as core
import pybionic_web as web
import sqlite3
from typing import Any
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import json
import time
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n
import pipeline_engine

PORT = int(os.environ.get("WEB_PORT") or os.environ.get("STUDIO_PORT") or 8110)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

pipeline_engine.init_db()

# Preload sample feed for offline studio
try:
    f = pipeline_engine.add_feed("PyBionic Architecture Digest", "https://pybionic.dev/rss.xml", interval=10)
    pipeline_engine.sync_feed_posts(f["id"], pipeline_engine.MOCK_FEED_XML)
except Exception:
    pass

class StudioHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            if "?" not in self.path and body:
                if "application/json" in self.headers.get("Content-Type", ""):
                    try:
                        j = json.loads(body)
                        q = urllib.parse.urlencode({k: str(v) for k, v in j.items()})
                        self.path = f"{self.path}?{q}"
                    except Exception:
                        pass
                else:
                    self.path = f"{self.path}?{body}"
        self.do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            stats = pipeline_engine.get_pipeline_stats()
            data = {
                "status": "online",
                "bot": "content_auto_pipeline",
                "port": PORT,
                "stats": stats,
                "deduplication_active": True
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path == "/api/feeds":
            feeds = pipeline_engine.get_all_feeds()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(feeds).encode("utf-8"))
            return

        elif path == "/api/sync":
            feeds = pipeline_engine.get_all_feeds()
            total_new = 0
            for feed in feeds:
                res = pipeline_engine.sync_feed_posts(feed["id"], pipeline_engine.MOCK_FEED_XML)
                total_new += res["new"]
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "new_posts": total_new}).encode("utf-8"))
            return

        elif path == "/api/add_feed":
            title = query.get("title", ["New Feed"])[0]
            url = query.get("url", ["https://example.com/feed"])[0]
            f = pipeline_engine.add_feed(title, url)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(f).encode("utf-8"))
            return

        render_studio(self)


def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    stats = pipeline_engine.get_pipeline_stats()
    feeds = pipeline_engine.get_all_feeds()
    conn = sqlite3.connect(pipeline_engine.DB_PATH)
    try:
        posts = conn.execute("SELECT p.title, p.link, p.summary, p.published_at, f.title FROM syndicated_posts p LEFT JOIN feeds f ON f.id = p.feed_id "
                             "ORDER BY p.id DESC LIMIT 8").fetchall()
    finally:
        conn.close()
    css = ("<style>.cp-feed{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:var(--surface2);margin-bottom:8px}"
           ".cp-feed .ico{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;flex:none;background:color-mix(in srgb,var(--brand) 16%,transparent);color:var(--brand)}"
           ".cp-feed div{flex:1;min-width:0}.cp-feed b{display:block;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
           ".cp-feed small{display:block;color:var(--muted);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
           ".cp-int{font-size:12px;color:var(--muted);white-space:nowrap}"
           ".cp-post{padding:12px 0;border-bottom:1px solid var(--line)}.cp-post:last-child{border:0}.cp-post a{color:var(--text);font-weight:600;text-decoration:none}"
           ".cp-post a:hover{color:var(--brand)}.cp-post p{margin:4px 0 0;color:var(--muted);font-size:13.5px;line-height:1.5}.cp-post small{color:var(--muted);font-size:12px}"
           ".cp-pipe{display:flex;align-items:center;gap:6px;flex-wrap:wrap;font-size:13px}.cp-pipe span{padding:7px 11px;border-radius:10px;background:var(--surface2);border:1px solid var(--line)}"
           ".cp-pipe i{color:var(--brand);font-style:normal}</style>")
    feed_html = "".join(
        f'<div class="cp-feed"><span class="ico">{web.icon("wave", 18)}</span><div><b>{web.esc(f["title"])}</b><small>{web.esc(f["url"])}</small></div>'
        f'<span class="cp-int">{web.esc(T("w_every", n=f["interval"]))}</span></div>' for f in feeds) or web.empty_state(T("w_no_feeds"), "wave")
    post_html = ""
    for p in posts:
        link = p[1] if str(p[1] or "").startswith(("http://", "https://")) else "#"
        when = time.strftime("%d.%m %H:%M", time.localtime(p[3] or 0))
        post_html += (f'<div class="cp-post"><a href="{web.esc(link)}" target="_blank" rel="noopener">{web.esc(p[0])}</a>'
                      f'<p>{web.esc((p[2] or "")[:180])}</p><small>{web.esc(p[4] or "")} · {when}</small></div>')
    post_html = post_html or web.empty_state(T("w_no_posts"), "list")
    steps = [T("w_p1"), T("w_p2"), T("w_p3"), T("w_p4")]
    pipe = '<div class="cp-pipe">' + "<i>→</i>".join(f"<span>{web.esc(s)}</span>" for s in steps) + "</div>"
    add = web.card(T("w_card_add"),
        '<form id="f">' + web.field(T("w_feed_title"), web.input_("title", "Hacker News", icon_name="list", autocomplete="off"))
        + web.field(T("w_feed_url"), web.input_("url", "https://news.ycombinator.com/rss", icon_name="link", type="url", autocomplete="off"))
        + '<div class="pb-row">' + web.button(T("add"), "addbtn", type="submit", icon_name="plus")
        + web.button(T("w_sync"), "sync", kind="ghost", icon_name="refresh") + "</div></form>", icon_name="plus")
    how = web.card(T("w_card_how"), pipe + web.note(T("w_demo_note"), "warn"), icon_name="zap")
    st = web.stats([(T("w_st_feeds"), str(stats.get("total_feeds", 0)), None, "wave"), (T("w_st_posts"), str(stats.get("total_posts", 0)), None, "list")])
    hero = web.hero(T("w_title"), T("w_hero"), "🚀", chips=["RSS", "Atom", "SHA-256", T("w_chip_dedup")])
    body = (css + st + web.grid(add, how, min_width=330)
            + web.grid(web.card(T("w_card_feeds"), feed_html, icon_name="wave"), web.card(T("w_card_posts"), post_html, icon_name="list"), min_width=330))
    web.send_page(handler, lang, title=T("w_title"), emoji="🚀", brand="#f43f5e", port=PORT, hero_html=hero, body=body, script=PIPELINE_JS)


PIPELINE_JS = r"""
const $=s=>document.querySelector(s);
$('#f').addEventListener('submit',async e=>{e.preventDefault();const t=$('#title').value.trim(),u=$('#url').value.trim();
  if(!t||!/^https?:\/\//i.test(u))return pb.toast(pb.t('w_need_feed'),true);const b=$('#addbtn');pb.busy(b,true);
  try{await pb.json('/api/add_feed?title='+encodeURIComponent(t)+'&url='+encodeURIComponent(u));pb.toast(pb.t('w_added'));setTimeout(()=>location.reload(),600)}
  catch(err){pb.busy(b,false);pb.toast(pb.t('error')+': '+err.message,true)}});
$('#sync').onclick=async()=>{const b=$('#sync');pb.busy(b,true);
  try{const d=await pb.json('/api/sync');pb.toast(pb.t('w_synced',{n:d.new_posts||0}));setTimeout(()=>location.reload(),900)}
  catch(err){pb.busy(b,false);pb.toast(pb.t('error')+': '+err.message,true)}};
"""


class ThreadedStudioServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def start_web_studio():
    try:
        server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), PORT), StudioHandler)
        print(f"[PYBIONIC_WEB:{PORT}]", flush=True)
        print(f"[Content Auto Pipeline] Web Studio active at http://127.0.0.1:{PORT}", flush=True)
        server.serve_forever()
    except Exception as exc:
        print(f"[Content Auto Pipeline] Web Studio server error on port {PORT}: {exc}", flush=True)

# --- Telegram Bot Handler (Pure ReplyKeyboardMarkup) ---
def start_bot():
    if not BOT_TOKEN:
        print("[Content Auto Pipeline] No BOT_TOKEN provided, running in offline Web Studio mode.")
        return

    import telebot
    from telebot import types

    bot = telebot.TeleBot(BOT_TOKEN)
    core.guard_bot(bot)

    user_state = {}

    ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()}

    def is_allowed(user_id: int) -> bool:
        return not ALLOWED or user_id in ALLOWED

    @bot.message_handler(func=lambda m: not is_allowed(m.from_user.id))
    def access_denied(m):
        bot.reply_to(m, f"⛔ Доступ ограничен владельцем бота (ваш ID: {m.from_user.id}).")

    def get_user_lang(chat_id):
        return user_state.get(chat_id, {}).get("lang", "ru")

    def make_main_keyboard(lang):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton(i18n.t("btn_check_now", lang)),
            types.KeyboardButton(i18n.t("btn_list_feeds", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_add_feed", lang)),
            types.KeyboardButton(i18n.t("btn_pipeline_stats", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_status", lang)),
            types.KeyboardButton(i18n.t("btn_help", lang))
        )
        markup.add(types.KeyboardButton(i18n.t("btn_lang", lang)))
        return markup

    def make_lang_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=4)
        langs = [
            ("🇷🇺 Русский", "ru"), ("🇬🇧 English", "en"), ("🇺🇿 O'zbek", "uz"), ("🇩🇪 Deutsch", "de"),
            ("🇪🇸 Español", "es"), ("🇫🇷 Français", "fr"), ("🇨🇳 简体中文", "zh"), ("🇹🇷 Türkçe", "tr")
        ]
        buttons = [types.KeyboardButton(text) for text, _ in langs]
        markup.add(*buttons)
        markup.add(types.KeyboardButton("🔙 Назад / Back"))
        return markup

    @bot.message_handler(commands=["start"])
    def cmd_start(msg):
        lang = get_user_lang(msg.chat.id)
        bot.send_message(
            msg.chat.id,
            i18n.t("welcome", lang),
            reply_markup=make_main_keyboard(lang),
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: True)
    def handle_message(msg):
        cid = msg.chat.id
        lang = get_user_lang(cid)
        text = (msg.text or "").strip()

        if text in (i18n.t("btn_lang", lang), "🌐 Язык / Language", "🌐 Language / Язык"):
            bot.send_message(cid, i18n.t("choose_lang", lang), reply_markup=make_lang_keyboard())
            return

        lang_map = {
            "🇷🇺 Русский": "ru", "🇬🇧 English": "en", "🇺🇿 O'zbek": "uz", "🇩🇪 Deutsch": "de",
            "🇪🇸 Español": "es", "🇫🇷 Français": "fr", "🇨🇳 简体中文": "zh", "🇹🇷 Türkçe": "tr"
        }
        if text in lang_map:
            new_lang = lang_map[text]
            user_state[cid] = user_state.get(cid, {})
            user_state[cid]["lang"] = new_lang
            bot.send_message(
                cid,
                i18n.t("lang_changed", new_lang).format(lang=new_lang),
                reply_markup=make_main_keyboard(new_lang)
            )
            return

        if text in ("🔙 Назад / Back", "Back"):
            user_state[cid] = user_state.get(cid, {})
            user_state[cid]["waiting_feed_url"] = False
            bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_help", lang):
            bot.send_message(cid, i18n.t("help_text", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_pipeline_stats", lang):
            st = pipeline_engine.get_pipeline_stats()
            txt = i18n.t("stats_text", lang).format(
                total_feeds=st["total_feeds"],
                total_posts=st["total_posts"],
                syndicated_count=st["syndicated_count"],
                duplicates_blocked=st["duplicates_blocked"],
                port=PORT
            )
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_status", lang):
            txt = i18n.t("status_text", lang).format(port=PORT)
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_list_feeds", lang):
            feeds = pipeline_engine.get_all_feeds()
            if not feeds:
                bot.send_message(cid, i18n.t("no_feeds", lang), reply_markup=make_main_keyboard(lang))
            else:
                lines = [f"• <b>{f['title']}</b> ({f['interval']}m): <code>{f['url']}</code>" for f in feeds]
                out_txt = i18n.t("feeds_list_title", lang).format(list="\n".join(lines))
                bot.send_message(cid, out_txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_add_feed", lang):
            user_state[cid] = user_state.get(cid, {})
            user_state[cid]["waiting_feed_url"] = True
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("🔙 Назад / Back"))
            bot.send_message(cid, i18n.t("prompt_feed_url", lang), reply_markup=markup, parse_mode="HTML")
            return

        if user_state.get(cid, {}).get("waiting_feed_url"):
            user_state[cid]["waiting_feed_url"] = False
            title = text.split("/")[2] if "://" in text else "Custom Stream"
            f = pipeline_engine.add_feed(title, text, interval=15)
            txt = i18n.t("feed_added", lang).format(
                title=f["title"],
                url=f["url"],
                interval=f["interval"]
            )
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_check_now", lang):
            bot.send_message(cid, i18n.t("syncing", lang), parse_mode="HTML")
            feeds = pipeline_engine.get_all_feeds()
            total_new = 0
            for feed in feeds:
                res = pipeline_engine.sync_feed_posts(feed["id"], pipeline_engine.MOCK_FEED_XML)
                total_new += res["new"]
            res_txt = i18n.t("sync_result", lang).format(
                feeds_count=len(feeds),
                new_posts=total_new,
                syndicated=f"{total_new} published"
            )
            bot.send_message(cid, res_txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")

    print("[Content Auto Pipeline] Telegram bot polling started.")
    core.start_polling(bot)

def main():
    print(f"[Content Auto Pipeline] Starting on port {PORT}...")
    web_thread = threading.Thread(target=start_web_studio, daemon=True)
    web_thread.start()

    if BOT_TOKEN:
        start_bot()
    else:
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
