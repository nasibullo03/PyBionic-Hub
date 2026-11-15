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
import shield_engine

PORT = int(os.environ.get("WEB_PORT") or os.environ.get("STUDIO_PORT") or 8108)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

shield_engine.init_db()

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
            stats = shield_engine.get_shield_statistics()
            data = {
                "status": "online",
                "bot": "antiraid_math_shield",
                "port": PORT,
                "stats": stats,
                "protection_active": True
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path == "/api/challenge":
            c = shield_engine.create_challenge_for_user(999999)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(c).encode("utf-8"))
            return

        elif path == "/api/verify":
            val = int(query.get("answer", [0])[0])
            res, reason = shield_engine.verify_user_answer(999999, val)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": res, "reason": reason}).encode("utf-8"))
            return

        # Render HTML UI
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = self._render_html()
        self.wfile.write(html.encode("utf-8"))

    def _render_html(self):
        stats = shield_engine.get_shield_statistics()
        c = shield_engine.create_challenge_for_user(1001)

        opts_html = "".join([f'<button class="opt-btn" onclick="checkAnswer({opt})">{opt}</button>' for opt in c["options"]])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Anti-Raid Math Shield Studio</title>
<style>
  :root {{
    --bg: #0b0f19;
    --card: #151c2e;
    --card-border: #222d4a;
    --primary: #00e5ff;
    --accent: #ff0055;
    --success: #00e676;
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
  .header h1 {{ color: var(--primary); font-size: 26px; letter-spacing: 1px; }}
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
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
  }}
  .stat-block {{
    background: #0d1322;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }}
  .stat-label {{ color: var(--muted); font-size: 12px; margin-bottom: 6px; }}
  .stat-val {{ font-size: 22px; font-weight: bold; color: #fff; }}
  .challenge-box {{
    background: #0d1322;
    border: 2px dashed var(--primary);
    border-radius: 12px;
    padding: 24px;
    text-align: center;
  }}
  .eq-text {{ font-size: 32px; font-weight: bold; color: var(--primary); margin: 16px 0; }}
  .options-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    max-width: 320px;
    margin: 0 auto;
  }}
  .opt-btn {{
    background: #1f2b48;
    color: #fff;
    border: 1px solid var(--primary);
    padding: 14px;
    font-size: 18px;
    font-weight: bold;
    border-radius: 8px;
    cursor: pointer;
    transition: 0.2s;
  }}
  .opt-btn:hover {{
    background: var(--primary);
    color: #000;
  }}
  #resultBox {{
    margin-top: 14px;
    font-weight: bold;
    font-size: 16px;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🛡 ANTI-RAID MATH SHIELD</h1>
    <p>Zero-Inline Telegram Keyboard Math CAPTCHA & Group Raid Guard (Offline Web Studio)</p>
  </div>

  <div class="card">
    <div class="card-title"><span>📊 PROTECTION TELEMETRY</span><span style="color:var(--success)">{stats['raid_mode']}</span></div>
    <div class="grid">
      <div class="stat-block">
        <div class="stat-label">TOTAL VERIFIED</div>
        <div class="stat-val" style="color:var(--success)">{stats['verified']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">BLOCKED RAIDS</div>
        <div class="stat-val" style="color:var(--accent)">{stats['blocked']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">AVG RESPONSE TIME</div>
        <div class="stat-val">{stats['avg_time']:.1f}s</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">ACTIVE STUDIO PORT</div>
        <div class="stat-val" style="color:var(--primary)">{PORT}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span>⚡ INTERACTIVE CHALLENGE TEST</span></div>
    <div class="challenge-box">
      <p style="color:var(--muted)">Simulate member challenge verification:</p>
      <div class="eq-text">{c['equation']} = ?</div>
      <div class="options-grid">
        {opts_html}
      </div>
      <div id="resultBox"></div>
    </div>
  </div>
</div>

<script>
function checkAnswer(val) {{
  fetch('/api/verify?answer=' + val)
    .then(r => r.json())
    .then(d => {{
      const rb = document.getElementById('resultBox');
      if(d.success) {{
        rb.innerHTML = '<span style="color:var(--success)">✅ VERIFICATION SUCCESSFUL! Human confirmed.</span>';
      }} else {{
        rb.innerHTML = '<span style="color:var(--accent)">❌ FAILED: ' + d.reason + '</span>';
      }}
      setTimeout(() => location.reload(), 1500);
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
        print(f"[Anti-Raid Math Shield] Web Studio active at http://127.0.0.1:{PORT}", flush=True)
        server.serve_forever()
    except Exception as exc:
        print(f"[Anti-Raid Math Shield] Web Studio server error on port {PORT}: {exc}", flush=True)

# --- Telegram Bot Handler (Pure ReplyKeyboardMarkup) ---
def start_bot():
    if not BOT_TOKEN:
        print("[Anti-Raid Math Shield] No BOT_TOKEN provided, running in offline Web Studio mode.")
        return

    import telebot
    from telebot import types

    bot = telebot.TeleBot(BOT_TOKEN)
    user_state = {}

    ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()}

    def is_allowed(user_id: int) -> bool:
        return not ALLOWED or user_id in ALLOWED

    @bot.message_handler(func=lambda m: m.chat.type == "private" and not is_allowed(m.from_user.id))
    def access_denied(m):
        bot.reply_to(m, f"⛔ Доступ ограничен владельцем бота (ваш ID: {m.from_user.id}).")

    def get_user_lang(chat_id):
        return user_state.get(chat_id, {}).get("lang", "ru")

    def make_main_keyboard(lang):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton(i18n.t("btn_test_challenge", lang)),
            types.KeyboardButton(i18n.t("btn_verify", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_rules", lang)),
            types.KeyboardButton(i18n.t("btn_stats", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_status", lang)),
            types.KeyboardButton(i18n.t("btn_help", lang))
        )
        markup.add(types.KeyboardButton(i18n.t("btn_lang", lang)))
        return markup

    def make_challenge_keyboard(options):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btns = [types.KeyboardButton(f"🔢 {opt}") for opt in options]
        markup.add(*btns)
        markup.add(types.KeyboardButton("❌ Отмена / Cancel"))
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

    # Monitor new chat members
    @bot.message_handler(content_types=["new_chat_members"])
    def on_new_members(msg):
        for user in msg.new_chat_members:
            if user.is_bot:
                continue
            lang = get_user_lang(msg.chat.id)
            c = shield_engine.create_challenge_for_user(user.id, timeout=60)
            txt = i18n.t("challenge_prompt", lang).format(
                user=user.first_name,
                equation=c["equation"],
                timeout=c["timeout"]
            )
            bot.send_message(
                msg.chat.id,
                txt,
                reply_markup=make_challenge_keyboard(c["options"]),
                parse_mode="HTML"
            )

    @bot.message_handler(func=lambda m: True)
    def handle_message(msg):
        cid = msg.chat.id
        uid = msg.from_user.id
        lang = get_user_lang(cid)
        text = (msg.text or "").strip()

        # Rate limit check
        if not shield_engine.check_rate_limit(uid, window=5.0, max_msgs=5):
            bot.send_message(cid, "⚠️ <b>Флуд-контроль!</b> Пожалуйста, не спамьте сообщениями.", parse_mode="HTML")
            return

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

        if text in ("🔙 Назад / Back", "Back", "❌ Отмена / Cancel"):
            bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_help", lang):
            bot.send_message(cid, i18n.t("help_text", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_rules", lang):
            bot.send_message(cid, i18n.t("rules_text", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_stats", lang):
            st = shield_engine.get_shield_statistics()
            txt = i18n.t("stats_text", lang).format(
                verified=st["verified"],
                blocked=st["blocked"],
                avg_time=st["avg_time"],
                raid_mode=st["raid_mode"],
                port=PORT
            )
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_status", lang):
            txt = i18n.t("status_text", lang).format(port=PORT)
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text in (i18n.t("btn_verify", lang), i18n.t("btn_test_challenge", lang)):
            c = shield_engine.create_challenge_for_user(uid, timeout=60)
            txt = i18n.t("challenge_prompt", lang).format(
                user=msg.from_user.first_name,
                equation=c["equation"],
                timeout=c["timeout"]
            )
            bot.send_message(cid, txt, reply_markup=make_challenge_keyboard(c["options"]), parse_mode="HTML")
            return

        # Check if text is a math answer (e.g. "🔢 42" or "42")
        val_str = text.replace("🔢", "").strip()
        if val_str.lstrip("-").isdigit():
            val = int(val_str)
            success, reason = shield_engine.verify_user_answer(uid, val)
            if success:
                bot.send_message(cid, i18n.t("verified_success", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            else:
                if reason == "timeout":
                    bot.send_message(cid, i18n.t("timeout_fail", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
                else:
                    bot.send_message(cid, i18n.t("verified_fail", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")

    print("[Anti-Raid Math Shield] Telegram bot polling started.")
    core.start_polling(bot)

def main():
    print(f"[Anti-Raid Math Shield] Starting on port {PORT}...")
    web_thread = threading.Thread(target=start_web_studio, daemon=True)
    web_thread.start()

    if BOT_TOKEN:
        start_bot()
    else:
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
