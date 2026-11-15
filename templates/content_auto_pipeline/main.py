import pybionic_core as core
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

        # Render HTML UI
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = self._render_html()
        self.wfile.write(html.encode("utf-8"))

    def _render_html(self):
        stats = pipeline_engine.get_pipeline_stats()
        feeds = pipeline_engine.get_all_feeds()

        feed_rows = "".join([
            f"""<tr>
                <td>#{f['id']}</td>
                <td><b>{f['title']}</b></td>
                <td><code>{f['url']}</code></td>
                <td>{f['interval']} min</td>
                <td><span style="color:var(--success)">Active 🟢</span></td>
            </tr>"""
            for f in feeds
        ])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Content Auto Pipeline Studio</title>
<style>
  :root {{
    --bg: #090e17;
    --card: #121a29;
    --card-border: #1e2b42;
    --primary: #00f0ff;
    --accent: #7000ff;
    --success: #00e676;
    --warning: #ffb300;
    --text: #e0e6ed;
    --muted: #8492a6;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    padding: 20px;
  }}
  .container {{ max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }}
  .header {{
    text-align: center;
    border-bottom: 1px solid var(--card-border);
    padding-bottom: 16px;
  }}
  .header h1 {{ color: var(--primary); font-size: 26px; }}
  .header p {{ color: var(--muted); font-size: 14px; margin-top: 4px; }}
  .card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  }}
  .card-title {{
    color: var(--primary);
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 14px;
    display: flex;
    justify-content: space-between;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
  }}
  .stat-block {{
    background: #0b111c;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }}
  .stat-label {{ color: var(--muted); font-size: 12px; margin-bottom: 6px; }}
  .stat-val {{ font-size: 22px; font-weight: bold; color: #fff; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 14px;
  }}
  th, td {{
    padding: 12px 14px;
    text-align: left;
    border-bottom: 1px solid var(--card-border);
  }}
  th {{ color: var(--muted); font-weight: 600; }}
  .action-box {{
    display: flex;
    gap: 10px;
  }}
  input[type="text"] {{
    flex: 1;
    background: #0b111c;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 12px;
    color: #fff;
    outline: none;
  }}
  button {{
    background: var(--primary);
    color: #000;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 12px 20px;
    cursor: pointer;
    transition: 0.2s;
  }}
  button:hover {{ filter: brightness(1.2); }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🚀 CONTENT AUTO PIPELINE</h1>
    <p>RSS/Atom Syndication, SHA-256 Deduplication & Broadcast Hub (Offline Web Studio)</p>
  </div>

  <div class="card">
    <div class="card-title"><span>📊 SYNDICATION TELEMETRY</span><span style="color:var(--success)">{stats['status']}</span></div>
    <div class="grid">
      <div class="stat-block">
        <div class="stat-label">MONITORED FEEDS</div>
        <div class="stat-val">{stats['total_feeds']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">TOTAL POSTS</div>
        <div class="stat-val" style="color:var(--primary)">{stats['total_posts']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">DUPLICATES BLOCKED</div>
        <div class="stat-val" style="color:var(--accent)">{stats['duplicates_blocked']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">WEB STUDIO PORT</div>
        <div class="stat-val">{PORT}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span>➕ CONNECT NEW RSS STREAM</span></div>
    <div class="action-box">
      <input type="text" id="feedTitle" placeholder="Feed Title (e.g. Hacker News)..." style="max-width:200px">
      <input type="text" id="feedUrl" placeholder="Feed XML/Atom URL...">
      <button onclick="addFeed()">ADD FEED</button>
      <button onclick="syncNow()" style="background:var(--accent);color:#fff">⚡ SYNC NOW</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span>📡 CONFIGURED CHANNELS & PIPELINES</span></div>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>TITLE</th>
          <th>FEED URL</th>
          <th>INTERVAL</th>
          <th>STATUS</th>
        </tr>
      </thead>
      <tbody>
        {feed_rows}
      </tbody>
    </table>
  </div>
</div>

<script>
function addFeed() {{
  const title = document.getElementById('feedTitle').value.trim();
  const url = document.getElementById('feedUrl').value.trim();
  if(!title || !url) return alert('Enter both title and URL');
  window.location.href = '/api/add_feed?title=' + encodeURIComponent(title) + '&url=' + encodeURIComponent(url);
}}
function syncNow() {{
  fetch('/api/sync')
    .then(r => r.json())
    .then(d => {{
      alert('Synced! New posts: ' + d.new_posts);
      location.reload();
    }});
}}
</script>
</body>
</html>"""

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
