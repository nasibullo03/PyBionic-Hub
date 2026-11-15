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
import runner_engine

PORT = int(os.environ.get("WEB_PORT") or os.environ.get("STUDIO_PORT") or 8111)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

runner_engine.init_db()

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
            stats = runner_engine.get_runner_stats()
            data = {
                "status": "online",
                "bot": "python_sandbox_runner",
                "port": PORT,
                "stats": stats,
                "ast_audit_enabled": True
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path == "/api/run":
            code = query.get("code", ["print('Hello from PyBionic Sandbox!')"])[0]
            res = runner_engine.execute_sandboxed(code)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # Render HTML UI
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = self._render_html()
        self.wfile.write(html.encode("utf-8"))

    def _render_html(self):
        stats = runner_engine.get_runner_stats()

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Python Sandbox Runner Studio</title>
<style>
  :root {{
    --bg: #0b0f19;
    --card: #141c2e;
    --card-border: #202d4a;
    --primary: #00f0ff;
    --accent: #ff0055;
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
    background: #0d1322;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }}
  .stat-label {{ color: var(--muted); font-size: 12px; margin-bottom: 6px; }}
  .stat-val {{ font-size: 22px; font-weight: bold; color: #fff; }}
  textarea {{
    width: 100%;
    height: 180px;
    background: #0d1322;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 14px;
    color: #00ffcc;
    font-family: 'Courier New', Courier, monospace;
    font-size: 14px;
    resize: vertical;
    outline: none;
  }}
  .btn-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 12px;
  }}
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
  pre {{
    background: #080c14;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 14px;
    color: #fff;
    font-size: 13px;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 240px;
    overflow-y: auto;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🐍 PYTHON SANDBOX RUNNER</h1>
    <p>Isolated AST-Audited Python Execution Environment (Offline Web Studio)</p>
  </div>

  <div class="card">
    <div class="card-title"><span>📊 EXECUTION TELEMETRY</span><span style="color:var(--primary)">PORT {PORT}</span></div>
    <div class="grid">
      <div class="stat-block">
        <div class="stat-label">TOTAL RUNS</div>
        <div class="stat-val">{stats['total_runs']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">SUCCESSFUL</div>
        <div class="stat-val" style="color:var(--success)">{stats['success_runs']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">AST BLOCKED</div>
        <div class="stat-val" style="color:var(--accent)">{stats['blocked_ast']}</div>
      </div>
      <div class="stat-block">
        <div class="stat-label">AVG TIME</div>
        <div class="stat-val">{stats['avg_time']:.3f}s</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span>💻 PYTHON CODE EDITOR</span></div>
    <textarea id="codeEditor"># Compute Fibonacci sequence
def fib(n):
    a, b = 0, 1
    res = []
    for _ in range(n):
        res.append(a)
        a, b = b, a + b
    return res

print("Fibonacci(12):", fib(12))</textarea>
    <div class="btn-bar">
      <div>
        <button onclick="setSample('math')" style="background:#1f2b48;color:#fff;margin-right:8px">Math Sample</button>
        <button onclick="setSample('forbidden')" style="background:#1f2b48;color:var(--accent)">Test AST Block</button>
      </div>
      <button onclick="runCode()">EXECUTE CODE ⚡</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span>📤 CONSOLE STDOUT / STDERR</span><span id="runBadge"></span></div>
    <pre id="outputBox">Press "EXECUTE CODE" to view sandboxed output...</pre>
  </div>
</div>

<script>
function setSample(t) {{
  if(t === 'math') {{
    document.getElementById('codeEditor').value = "import math\nprint('Pi:', math.pi)\nprint('Factorial(8):', math.factorial(8))\nprint('Sine(math.pi/2):', math.sin(math.pi/2))";
  }} else {{
    document.getElementById('codeEditor').value = "import os\nprint(os.listdir('.'))";
  }}
}}

function runCode() {{
  const code = document.getElementById('codeEditor').value;
  const outBox = document.getElementById('outputBox');
  const badge = document.getElementById('runBadge');
  outBox.innerText = 'Executing in isolated namespace...';
  
  fetch('/api/run?code=' + encodeURIComponent(code))
    .then(r => r.json())
    .then(d => {{
      if(d.success) {{
        badge.innerHTML = '<span style="color:var(--success)">SUCCESS (' + d.exec_time.toFixed(3) + 's)</span>';
        outBox.innerText = d.stdout;
      }} else {{
        badge.innerHTML = '<span style="color:var(--accent)">' + d.status + ' (' + d.exec_time.toFixed(3) + 's)</span>';
        outBox.innerText = d.error || d.violation;
      }}
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
        print(f"[Python Sandbox Runner] Web Studio active at http://127.0.0.1:{PORT}", flush=True)
        server.serve_forever()
    except Exception as exc:
        print(f"[Python Sandbox Runner] Web Studio server error on port {PORT}: {exc}", flush=True)

# --- Telegram Bot Handler (Pure ReplyKeyboardMarkup) ---
def start_bot():
    if not BOT_TOKEN:
        print("[Python Sandbox Runner] No BOT_TOKEN provided, running in offline Web Studio mode.")
        return

    import telebot
    from telebot import types

    bot = telebot.TeleBot(BOT_TOKEN)
    core.guard_bot(bot, closed_if_empty=True)

    user_state = {}

    def get_user_lang(chat_id):
        return user_state.get(chat_id, {}).get("lang", "ru")

    def make_main_keyboard(lang):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton(i18n.t("btn_run_code", lang)),
            types.KeyboardButton(i18n.t("btn_sample_math", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_sample_bench", lang)),
            types.KeyboardButton(i18n.t("btn_ast_rules", lang))
        )
        markup.add(
            types.KeyboardButton(i18n.t("btn_runner_stats", lang)),
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
        uid = msg.from_user.id
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
            user_state[cid]["waiting_code"] = False
            bot.send_message(cid, i18n.t("welcome", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_help", lang):
            bot.send_message(cid, i18n.t("help_text", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_ast_rules", lang):
            bot.send_message(cid, i18n.t("ast_rules_text", lang), reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_runner_stats", lang):
            st = runner_engine.get_runner_stats()
            txt = i18n.t("stats_text", lang).format(
                total_runs=st["total_runs"],
                success_runs=st["success_runs"],
                failed_runs=st["failed_runs"],
                blocked_ast=st["blocked_ast"],
                avg_time=st["avg_time"],
                port=PORT
            )
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_status", lang):
            txt = i18n.t("status_text", lang).format(port=PORT)
            bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            return

        if text == i18n.t("btn_run_code", lang):
            user_state[cid] = user_state.get(cid, {})
            user_state[cid]["waiting_code"] = True
            bot.send_message(cid, i18n.t("prompt_code", lang), parse_mode="HTML")
            return

        # Predefined samples
        if text == i18n.t("btn_sample_math", lang):
            text = "import math\nvals = [math.sin(i * 0.5) for i in range(5)]\nprint('Trig samples:', [round(x, 4) for x in vals])\nprint('Factorial 7! =', math.factorial(7))"

        if text == i18n.t("btn_sample_bench", lang):
            text = "import time\nt0 = time.time()\ntotal = sum(i**2 for i in range(100_000))\nelapsed = time.time() - t0\nprint(f'Computed sum of 100k squares in {elapsed*1000:.2f} ms')\nprint('Sum ends with:', str(total)[-6:])"

        # Execute code snippet
        bot.send_message(cid, i18n.t("executing", lang), parse_mode="HTML")
        
        def run_async():
            res = runner_engine.execute_sandboxed(text, user_id=uid)
            if res["status"] == "AST_BLOCKED":
                txt = i18n.t("ast_violation", lang).format(violation=res["violation"])
                bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            elif res["success"]:
                txt = i18n.t("exec_result", lang).format(
                    exec_time=res["exec_time"],
                    ast_status=res["ast_status"],
                    stdout=res["stdout"]
                )
                bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")
            else:
                txt = i18n.t("exec_error", lang).format(
                    exec_time=res["exec_time"],
                    error_type=res.get("error_type", "Error"),
                    error=res.get("error", "Unknown error")
                )
                bot.send_message(cid, txt, reply_markup=make_main_keyboard(lang), parse_mode="HTML")

        threading.Thread(target=run_async, daemon=True).start()

    print("[Python Sandbox Runner] Telegram bot polling started.")
    core.start_polling(bot)

def main():
    print(f"[Python Sandbox Runner] Starting on port {PORT}...")
    web_thread = threading.Thread(target=start_web_studio, daemon=True)
    web_thread.start()

    if BOT_TOKEN:
        start_bot()
    else:
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
