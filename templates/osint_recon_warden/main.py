import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import html
import json
import time
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n
import recon_engine

PORT = int(os.environ.get("WEB_PORT") or os.environ.get("STUDIO_PORT") or 8107)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# Memory state
STATE = {
    "scanned_count": 0,
    "last_target": "github.com",
    "last_result": None,
    "history": []
}

# Perform initial mock or warmup scan
try:
    init_res = recon_engine.full_recon("github.com")
    STATE["last_result"] = init_res
    STATE["history"].append(init_res)
    STATE["scanned_count"] += 1
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
            data = {
                "status": "online",
                "bot": "osint_recon_warden",
                "port": PORT,
                "scanned_count": STATE["scanned_count"],
                "last_target": STATE["last_target"],
                "tls_support": True
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path == "/api/scan":
            target = query.get("target", ["github.com"])[0]
            try:
                res = recon_engine.full_recon(target)
                STATE["last_target"] = res["target"]
                STATE["last_result"] = res
                STATE["scanned_count"] += 1
                STATE["history"].insert(0, res)
                STATE["history"] = STATE["history"][:20]
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        elif path == "/api/last":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(STATE["last_result"] or {}).encode("utf-8"))
            return

        # Render HTML UI
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = self._render_html()
        self.wfile.write(html.encode("utf-8"))

    def _render_html(self):
        last = STATE["last_result"] or {}
        dns = last.get("dns", {})
        ssl_info = last.get("ssl", {})
        hdrs = last.get("headers", {})
        target = html.escape(str(last.get("target", "None")))
        score = last.get("security_score", 0)
        badge = html.escape(str(last.get("score_badge", "N/A"))) + f" ({score}/100)"

        ips_str = html.escape(", ".join(dns.get("ipv4", [])) or "None")
        issuer = html.escape(str(ssl_info.get("issuer", "N/A")))
        expires = html.escape(str(ssl_info.get("expires", "N/A")))
        cipher = html.escape(str(ssl_info.get("cipher", "N/A")))

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OSINT Recon Warden Studio</title>
<style>
  :root {{
    --bg: #090d16;
    --card: #131a29;
    --card-border: #1f2a40;
    --primary: #00e5ff;
    --success: #00e676;
    --warning: #ffb300;
    --danger: #ff1744;
    --text: #e0e6ed;
    --muted: #78909c;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    padding: 20px;
  }}
  .header {{
    text-align: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--card-border);
  }}
  .header h1 {{
    color: var(--primary);
    font-size: 26px;
    letter-spacing: 1px;
    margin-bottom: 6px;
  }}
  .header p {{ color: var(--muted); font-size: 14px; }}
  .container {{ max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }}
  .card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  }}
  .card-title {{
    color: var(--primary);
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .search-box {{
    display: flex;
    gap: 10px;
  }}
  input[type="text"] {{
    flex: 1;
    background: #0b101c;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 12px 16px;
    color: #fff;
    font-size: 15px;
    outline: none;
  }}
  input[type="text"]:focus {{ border-color: var(--primary); }}
  button {{
    background: var(--primary);
    color: #000;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    cursor: pointer;
    transition: 0.2s;
  }}
  button:hover {{ filter: brightness(1.2); }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 16px;
  }}
  .stat-block {{
    background: #0b101c;
    border-radius: 8px;
    padding: 14px;
    border: 1px solid var(--card-border);
  }}
  .stat-label {{ color: var(--muted); font-size: 12px; margin-bottom: 4px; }}
  .stat-val {{ font-size: 14px; word-break: break-all; color: #fff; }}
  .score-badge {{
    font-size: 18px;
    font-weight: bold;
    color: var(--success);
  }}
  .check-item {{
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px dashed #1a2336;
    font-size: 13px;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🛰 OSINT RECON WARDEN</h1>
    <p>Domain Security Infrastructure & Certificate Deep Analyzer (Offline Web Studio)</p>
  </div>

  <div class="card">
    <div class="card-title"><span>🎯 TARGET RECONNAISSANCE</span></div>
    <div class="search-box">
      <input type="text" id="targetInput" value="{target}" placeholder="e.g. cloudflare.com, google.com">
      <button onclick="runScan()">SCAN TARGET</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">
      <span>📊 AUDIT SUMMARY: <code style="color:#fff">{target}</code></span>
      <span class="score-badge">{badge}</span>
    </div>
    <div class="grid">
      <div class="stat-block">
        <div class="stat-label">IPv4 RESOLUTION</div>
        <div class="stat-val">{ips_str}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">SSL ISSUER</div>
        <div class="stat-val">{issuer}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">CERTIFICATE VALIDITY</div>
        <div class="stat-val">{expires}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">CIPHER SUITE</div>
        <div class="stat-val">{cipher}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span>🛡 HTTP SECURITY HEADERS AUDIT</span></div>
    <div class="check-item">
      <span>Strict-Transport-Security (HSTS)</span>
      <span>{'🟢 YES' if hdrs.get('hsts') else '❌ NO'}</span>
    </div>
    <div class="check-item">
      <span>Content-Security-Policy (CSP)</span>
      <span>{'🟢 YES' if hdrs.get('csp') else '❌ NO'}</span>
    </div>
    <div class="check-item">
      <span>X-Frame-Options (Clickjacking Protection)</span>
      <span>{'🟢 YES' if hdrs.get('x_frame_options') else '❌ NO'}</span>
    </div>
    <div class="check-item">
      <span>X-Content-Type-Options (MIME Sniffing)</span>
      <span>{'🟢 YES' if hdrs.get('x_content_type') else '❌ NO'}</span>
    </div>
    <div class="check-item">
      <span>Referrer-Policy</span>
      <span>{'🟢 YES' if hdrs.get('referrer_policy') else '❌ NO'}</span>
    </div>
  </div>
</div>

<script>
function runScan() {{
  const target = document.getElementById('targetInput').value.trim();
  if(!target) return alert('Enter target domain');
  window.location.href = '/api/scan?target=' + encodeURIComponent(target);
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
        print(f"[OSINT Recon Warden] Web Studio active at http://127.0.0.1:{PORT}", flush=True)
        server.serve_forever()
    except Exception as exc:
        print(f"[OSINT Recon Warden] Web Studio server error on port {PORT}: {exc}", flush=True)

# --- Telegram Bot Handler (Pure ReplyKeyboardMarkup) ---
def start_bot():
    if not BOT_TOKEN:
        print("[OSINT Recon Warden] No BOT_TOKEN set, running in offline Web Studio mode.")
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
            types.KeyboardButton(i18n.t("btn_quick_scan", lang)),
            types.KeyboardButton(i18n.t("btn_audit_domain", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_dns_records", lang)),
            types.KeyboardButton(i18n.t("btn_ssl_cert", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_security_headers", lang)),
            types.KeyboardButton(i18n.t("btn_status", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_help", lang)),
            types.KeyboardButton(i18n.t("btn_lang", lang))
        )
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

        # Check language switch
        lang_map = {
            "🇷🇺 Русский": "ru", "🇬🇧 English": "en", "🇺🇿 O'zbek": "uz", "🇩🇪 Deutsch": "de",
            "🇪🇸 Español": "es", "🇫🇷 Français": "fr", "🇨🇳 简体中文": "zh", "🇹🇷 Türkçe": "tr"
        }
        if text in lang_map:
            new_lang = lang_map[text]
            if cid not in user_state:
                user_state[cid] = {}
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
            st = i18n.t("status_text", lang).format(
                count=STATE["scanned_count"],
                port=PORT
            )
            bot.send_message(cid, st, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_quick_scan", lang):
            text = "google.com"

        if text == i18n.t("btn_audit_domain", lang):
            user_state[cid] = user_state.get(cid, {})
            user_state[cid]["waiting_domain"] = True
            bot.send_message(cid, i18n.t("prompt_domain", lang), parse_mode="HTML")
            return

        # Handle specific info buttons for last target
        if text == i18n.t("btn_dns_records", lang):
            last = STATE["last_result"] or recon_engine.full_recon("google.com")
            dns = last.get("dns", {})
            v4 = "\n".join([f"• <code>{ip}</code>" for ip in dns.get("ipv4", [])]) or "Нет"
            v6 = "\n".join([f"• <code>{ip}</code>" for ip in dns.get("ipv6", [])]) or "Нет"
            info = f"<b>IPv4:</b>\n{v4}\n\n<b>IPv6:</b>\n{v6}"
            bot.send_message(cid, i18n.t("dns_title", lang).format(target=last.get("target"), dns_info=info), parse_mode="HTML")
            return

        if text == i18n.t("btn_ssl_cert", lang):
            last = STATE["last_result"] or recon_engine.full_recon("google.com")
            ssl_info = last.get("ssl", {})
            sans = ", ".join(ssl_info.get("sans", [])) or "None"
            info = (
                f"• Статус: {'🟢 Валиден' if ssl_info.get('valid') else '❌ Ошибка'}\n"
                f"• Издатель: <code>{ssl_info.get('issuer')}</code>\n"
                f"• Действителен до: <code>{ssl_info.get('expires')}</code>\n"
                f"• Шифр: <code>{ssl_info.get('cipher')}</code>\n"
                f"• SANs: <code>{sans}</code>"
            )
            bot.send_message(cid, i18n.t("ssl_title", lang).format(target=last.get("target"), ssl_info=info), parse_mode="HTML")
            return

        if text == i18n.t("btn_security_headers", lang):
            last = STATE["last_result"] or recon_engine.full_recon("google.com")
            hdrs = last.get("headers", {})
            info = (
                f"• HSTS: {'🟢 Есть' if hdrs.get('hsts') else '❌ Нет'}\n"
                f"• CSP: {'🟢 Есть' if hdrs.get('csp') else '❌ Нет'}\n"
                f"• X-Frame-Options: {'🟢 Есть' if hdrs.get('x_frame_options') else '❌ Нет'}\n"
                f"• X-Content-Type: {'🟢 Есть' if hdrs.get('x_content_type') else '❌ Нет'}\n"
                f"• Referrer-Policy: {'🟢 Есть' if hdrs.get('referrer_policy') else '❌ Нет'}"
            )
            bot.send_message(cid, i18n.t("headers_title", lang).format(target=last.get("target"), headers_info=info), parse_mode="HTML")
            return

        # Treat as domain scan
        target = recon_engine.clean_target(text)
        if "." in target and len(target) >= 4:
            bot.send_message(cid, i18n.t("scanning", lang).format(target=target), parse_mode="HTML")
            
            def do_scan_async():
                try:
                    res = recon_engine.full_recon(target)
                    STATE["last_target"] = res["target"]
                    STATE["last_result"] = res
                    STATE["scanned_count"] += 1
                    
                    dns = res.get("dns", {})
                    ssl_info = res.get("ssl", {})
                    hdrs = res.get("headers", {})
                    
                    ips = ", ".join(dns.get("ipv4", [])) or "N/A"
                    hdrs_sum = (
                        f"• HSTS: {'🟢' if hdrs.get('hsts') else '❌'} | "
                        f"CSP: {'🟢' if hdrs.get('csp') else '❌'} | "
                        f"XFO: {'🟢' if hdrs.get('x_frame_options') else '❌'}"
                    )
                    
                    msg_txt = i18n.t("scan_result", lang).format(
                        target=res["target"],
                        ips=ips,
                        issuer=ssl_info.get("issuer", "N/A"),
                        subject=ssl_info.get("subject", "N/A"),
                        expires=ssl_info.get("expires", "N/A"),
                        days_left=ssl_info.get("days_left", 0),
                        cipher=ssl_info.get("cipher", "N/A"),
                        headers_summary=hdrs_sum,
                        score_badge=res.get("score_badge", "N/A")
                    )
                    bot.send_message(cid, msg_txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
                except Exception as ex:
                    bot.send_message(cid, f"❌ Ошибка аудита: {ex}", reply_markup=make_main_keyboard(lang))
            
            threading.Thread(target=do_scan_async, daemon=True).start()
        else:
            bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")

    print("[OSINT Recon Warden] Telegram bot polling started.")
    bot.infinity_polling()

def main():
    print(f"[OSINT Recon Warden] Starting on port {PORT}...")
    web_thread = threading.Thread(target=start_web_studio, daemon=True)
    web_thread.start()

    if BOT_TOKEN:
        start_bot()
    else:
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
