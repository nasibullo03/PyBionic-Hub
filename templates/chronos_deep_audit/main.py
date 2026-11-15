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
import chronos_engine

PORT = int(os.environ.get("WEB_PORT") or os.environ.get("STUDIO_PORT") or 8112)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

chronos_engine.init_db()

# Pre-warm an audit
try:
    chronos_engine.run_global_audit()
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
            up = chronos_engine.get_uptime_report()
            data = {
                "status": "online",
                "bot": "chronos_deep_audit",
                "port": PORT,
                "uptime": up,
                "targets_count": len(chronos_engine.TARGETS),
                "sonar_active": True
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path == "/api/audit":
            res = chronos_engine.run_global_audit()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        elif path == "/api/histogram":
            hist = chronos_engine.generate_ascii_histogram()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(hist.encode("utf-8"))
            return

        # Render HTML UI
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = self._render_html()
        self.wfile.write(html.encode("utf-8"))

    def _render_html(self):
        up = chronos_engine.get_uptime_report()
        audit = chronos_engine.run_global_audit()
        hist = chronos_engine.generate_ascii_histogram()

        rows = "".join([
            f"""<tr>
                <td><b>{r['name']}</b></td>
                <td><code>{r['host']}:{r['port']}</code></td>
                <td><b>{r['latency_ms']:.1f} ms</b></td>
                <td><span style="color:var(--success)">{r['status']} 🟢</span></td>
            </tr>"""
            for r in audit["results"]
        ])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chronos Deep Audit Studio</title>
<style>
  :root {{
    --bg: #090e18;
    --card: #131b2e;
    --card-border: #1f2d4d;
    --primary: #00e5ff;
    --accent: #ff0077;
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
    background: #0b1120;
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
  pre {{
    background: #080c14;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 14px;
    color: #00ffcc;
    font-family: monospace;
    font-size: 14px;
    line-height: 1.5;
  }}
  button {{
    background: var(--primary);
    color: #000;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    cursor: pointer;
    transition: 0.2s;
  }}
  button:hover {{ filter: brightness(1.2); }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>⏳ CHRONOS DEEP AUDIT</h1>
    <p>Network Latency Sonar, Percentiles (P50/P99) & SLA Monitoring (Offline Web Studio)</p>
  </div>

  <div class="card">
    <div class="card-title"><span>📊 SLA & HEALTH TELEMETRY</span><span style="color:var(--success)">{up['status']}</span></div>
    <div class="grid">
      <div class="stat-block">
        <div class="stat-label">UPTIME SLA</div>
        <div class="stat-val" style="color:var(--success)">{up['uptime_pct']}%</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">MEDIAN LATENCY (P50)</div>
        <div class="stat-val" style="color:var(--primary)">{audit['p50']:.1f} ms</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">TAIL LATENCY (P99)</div>
        <div class="stat-val" style="color:var(--accent)">{audit['p99']:.1f} ms</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">NETWORK JITTER</div>
        <div class="stat-val">{audit['jitter']:.2f} ms</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">
      <span>⚡ LIVE GLOBAL LATENCY PROBES</span>
      <button onclick="location.reload()">PROBE NOW 📡</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>TARGET NODE</th>
          <th>ENDPOINT</th>
          <th>ROUNDTRIP</th>
          <th>STATUS</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title"><span>📈 RESPONSE TIME DISTRIBUTION HISTOGRAM</span></div>
    <pre>{hist}</pre>
  </div>
</div>
</body>
</html>"""

class ThreadedStudioServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def start_web_studio():
    try:
        server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), PORT), StudioHandler)
        print(f"[PYBIONIC_WEB:{PORT}]", flush=True)
        print(f"[Chronos Deep Audit] Web Studio active at http://127.0.0.1:{PORT}", flush=True)
        server.serve_forever()
    except Exception as exc:
        print(f"[Chronos Deep Audit] Web Studio server error on port {PORT}: {exc}", flush=True)

# --- Telegram Bot Handler (Pure ReplyKeyboardMarkup) ---
def start_bot():
    if not BOT_TOKEN:
        print("[Chronos Deep Audit] No BOT_TOKEN provided, running in offline Web Studio mode.")
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
            types.KeyboardButton(i18n.t("btn_ping_check", lang)),
            types.KeyboardButton(i18n.t("btn_histogram", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_uptime_report", lang)),
            types.KeyboardButton(i18n.t("btn_targets", lang))
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
            bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_help", lang):
            bot.send_message(cid, i18n.t("help_text", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_status", lang):
            txt = i18n.t("status_text", lang).format(port=PORT)
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_targets", lang):
            lines = [f"• <b>{t['name']}</b>: <code>{t['host']}:{t['port']}</code>" for t in chronos_engine.TARGETS]
            bot.send_message(cid, "🎯 <b>Целевые узлы мониторинга:</b>\n\n" + "\n".join(lines), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_uptime_report", lang):
            up = chronos_engine.get_uptime_report()
            txt = i18n.t("uptime_title", lang).format(
                uptime_pct=up["uptime_pct"],
                total_hours=up["total_hours"],
                incidents=up["incidents"]
            )
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_histogram", lang):
            hist = chronos_engine.generate_ascii_histogram()
            txt = i18n.t("histogram_title", lang).format(histogram=hist)
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_ping_check", lang):
            bot.send_message(cid, i18n.t("ping_running", lang), parse_mode="HTML")
            
            def do_ping_async():
                audit = chronos_engine.run_global_audit()
                lines = []
                for r in audit["results"]:
                    lines.append(f"• <b>{r['name']}</b>: <code>{r['latency_ms']:.1f} мс</code> (🟢 {r['status']})")
                txt = i18n.t("ping_result", lang).format(
                    results="\n".join(lines),
                    min_ms=audit["min_ms"],
                    max_ms=audit["max_ms"],
                    p50=audit["p50"],
                    p99=audit["p99"],
                    jitter=audit["jitter"]
                )
                bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")

            threading.Thread(target=do_ping_async, daemon=True).start()
            return

        bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")

    print("[Chronos Deep Audit] Telegram bot polling started.")
    bot.infinity_polling()

def main():
    print(f"[Chronos Deep Audit] Starting on port {PORT}...")
    web_thread = threading.Thread(target=start_web_studio, daemon=True)
    web_thread.start()

    if BOT_TOKEN:
        start_bot()
    else:
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
