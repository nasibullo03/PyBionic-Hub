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
import crm_engine

PORT = int(os.environ.get("WEB_PORT") or os.environ.get("STUDIO_PORT") or 8109)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

crm_engine.init_db()

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
            stats = crm_engine.get_crm_stats()
            data = {
                "status": "online",
                "bot": "forum_crm_dispatcher",
                "port": PORT,
                "stats": stats,
                "forum_topics_enabled": True
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path == "/api/tickets":
            uid = int(query.get("user_id", [1234567])[0])
            tickets = crm_engine.get_user_tickets(uid)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(tickets).encode("utf-8"))
            return

        elif path == "/api/create_ticket":
            cat = query.get("cat", ["General"])[0]
            subj = query.get("subj", ["Web inquiry"])[0]
            t = crm_engine.create_ticket(999888, "web_user", cat, subj)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(t).encode("utf-8"))
            return

        # Render HTML UI
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = self._render_html()
        self.wfile.write(html.encode("utf-8"))

    def _render_html(self):
        stats = crm_engine.get_crm_stats()
        tickets = crm_engine.get_user_tickets(1234567) or [
            {"id": 1, "category": "Billing", "subject": "Payment query", "topic_id": 5567, "status": "PENDING", "created_at": time.time()}
        ]

        ticket_rows = "".join([
            f"""<tr>
                <td>#{t['id']}</td>
                <td><span class="badge">{t['category']}</span></td>
                <td>{t['subject']}</td>
                <td><code>#{t['topic_id']}</code></td>
                <td><span class="status-{t['status'].lower()}">{t['status']}</span></td>
            </tr>"""
            for t in tickets
        ])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forum CRM Dispatcher Studio</title>
<style>
  :root {{
    --bg: #0c101c;
    --card: #151d30;
    --card-border: #222f4d;
    --primary: #00d2ff;
    --accent: #3a7bd5;
    --success: #00e676;
    --warning: #ffb300;
    --text: #e0e6ed;
    --muted: #8899a6;
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
    background: #0f1524;
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
  .badge {{
    background: #1f2b48;
    color: var(--primary);
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
  }}
  .status-open {{ color: var(--primary); font-weight: bold; }}
  .status-pending {{ color: var(--warning); font-weight: bold; }}
  .status-resolved {{ color: var(--success); font-weight: bold; }}
  .action-box {{
    display: flex;
    gap: 10px;
  }}
  input[type="text"] {{
    flex: 1;
    background: #0f1524;
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
    <h1>🗂 FORUM CRM DISPATCHER</h1>
    <p>Client Inquiries & Telegram Forum Topics Routing Hub (Offline Web Studio)</p>
  </div>

  <div class="card">
    <div class="card-title"><span>📊 CRM PIPELINE OVERVIEW</span><span style="color:var(--primary)">PORT {PORT}</span></div>
    <div class="grid">
      <div class="stat-block">
        <div class="stat-label">TOTAL TICKETS</div>
        <div class="stat-val">{stats['total']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">OPEN INQUIRIES</div>
        <div class="stat-val" style="color:var(--primary)">{stats['open']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">PENDING REPLIES</div>
        <div class="stat-val" style="color:var(--warning)">{stats['pending']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">RESOLVED TICKETS</div>
        <div class="stat-val" style="color:var(--success)">{stats['resolved']}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span>✍️ SIMULATE CLIENT TICKET CREATION</span></div>
    <div class="action-box">
      <input type="text" id="subjInput" placeholder="Describe client issue (e.g. API webhook 500 error)...">
      <button onclick="createTicket()">CREATE TICKET</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span>📋 DISPATCHED FORUM TOPICS & THREADS</span></div>
    <table>
      <thead>
        <tr>
          <th>TICKET ID</th>
          <th>CATEGORY</th>
          <th>SUBJECT</th>
          <th>FORUM TOPIC</th>
          <th>STATUS</th>
        </tr>
      </thead>
      <tbody>
        {ticket_rows}
      </tbody>
    </table>
  </div>
</div>

<script>
function createTicket() {{
  const val = document.getElementById('subjInput').value.trim();
  if(!val) return alert('Enter subject');
  window.location.href = '/api/create_ticket?cat=Technical&subj=' + encodeURIComponent(val);
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
        print(f"[Forum CRM Dispatcher] Web Studio active at http://127.0.0.1:{PORT}", flush=True)
        server.serve_forever()
    except Exception as exc:
        print(f"[Forum CRM Dispatcher] Web Studio server error on port {PORT}: {exc}", flush=True)

# --- Telegram Bot Handler (Pure ReplyKeyboardMarkup) ---
def start_bot():
    if not BOT_TOKEN:
        print("[Forum CRM Dispatcher] No BOT_TOKEN provided, running in offline Web Studio mode.")
        return

    import telebot
    from telebot import types

    bot = telebot.TeleBot(BOT_TOKEN)
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
            types.KeyboardButton(i18n.t("btn_new_ticket", lang)),
            types.KeyboardButton(i18n.t("btn_my_tickets", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_faq", lang)),
            types.KeyboardButton(i18n.t("btn_crm_stats", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_status", lang)),
            types.KeyboardButton(i18n.t("btn_help", lang))
        )
        markup.add(types.KeyboardButton(i18n.t("btn_lang", lang)))
        return markup

    def make_category_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        cats = ["⚙️ Техподдержка", "💳 Оплата / Биллинг", "🤝 Партнерство", "💡 Другой вопрос"]
        markup.add(*[types.KeyboardButton(c) for c in cats])
        markup.add(types.KeyboardButton("🔙 Назад / Back"))
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
        uid = msg.from_user.id
        uname = msg.from_user.username or msg.from_user.first_name
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
            user_state[cid]["waiting_ticket_text"] = False
            user_state[cid]["category"] = None
            bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_help", lang):
            bot.send_message(cid, i18n.t("help_text", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_faq", lang):
            bot.send_message(cid, i18n.t("faq_text", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_crm_stats", lang):
            st = crm_engine.get_crm_stats()
            txt = i18n.t("stats_text", lang).format(
                total=st["total"],
                open=st["open"],
                pending=st["pending"],
                resolved=st["resolved"],
                agents=st["agents"],
                port=PORT
            )
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_status", lang):
            txt = i18n.t("status_text", lang).format(port=PORT)
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_new_ticket", lang):
            user_state[cid] = user_state.get(cid, {})
            user_state[cid]["category_selection"] = True
            bot.send_message(cid, i18n.t("prompt_category", lang), reply_markup=make_category_keyboard())
            return

        # Check category chosen
        if user_state.get(cid, {}).get("category_selection"):
            user_state[cid]["category_selection"] = False
            user_state[cid]["category"] = text
            user_state[cid]["waiting_ticket_text"] = True
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("🔙 Назад / Back"))
            bot.send_message(cid, i18n.t("prompt_topic", lang), reply_markup=markup, parse_mode="HTML")
            return

        if user_state.get(cid, {}).get("waiting_ticket_text"):
            cat = user_state.get(cid, {}).get("category", "General")
            user_state[cid]["waiting_ticket_text"] = False
            t = crm_engine.create_ticket(uid, uname, cat, text)
            txt = i18n.t("ticket_created", lang).format(
                tid=t["id"],
                cat=t["category"],
                topic_id=t["topic_id"]
            )
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_my_tickets", lang):
            tickets = crm_engine.get_user_tickets(uid)
            if not tickets:
                bot.send_message(cid, i18n.t("no_tickets", lang), reply_markup=make_main_keyboard(lang))
            else:
                lines = []
                for t in tickets:
                    st_icon = "🟢" if t["status"] == "RESOLVED" else ("🟡" if t["status"] == "PENDING" else "🔵")
                    lines.append(f"• <b>#{t['id']}</b> [{t['category']}]: {t['subject'][:30]}... ({st_icon} {t['status']})")
                out_txt = i18n.t("my_tickets_title", lang).format(list="\n".join(lines))
                bot.send_message(cid, out_txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")

    print("[Forum CRM Dispatcher] Telegram bot polling started.")
    bot.infinity_polling()

def main():
    print(f"[Forum CRM Dispatcher] Starting on port {PORT}...")
    web_thread = threading.Thread(target=start_web_studio, daemon=True)
    web_thread.start()

    if BOT_TOKEN:
        start_bot()
    else:
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
