import pybionic_core as core
import pybionic_web as web
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

        render_studio(self)


SANDBOX_SAMPLES = {
    "fib": "# Fibonacci\ndef fib(n):\n    a, b = 0, 1\n    out = []\n    for _ in range(n):\n        out.append(a)\n        a, b = b, a + b\n    return out\n\nprint(\"fib(12):\", fib(12))\n",
    "math": "import math\n\nprint(\"pi =\", math.pi)\nprint(\"8! =\", math.factorial(8))\nprint(\"sin(pi/2) =\", math.sin(math.pi / 2))\n",
    "text": "words = \"the quick brown fox jumps over the lazy dog the end\".split()\ncounts = {}\nfor w in words:\n    counts[w] = counts.get(w, 0) + 1\nfor w, c in sorted(counts.items(), key=lambda x: -x[1])[:5]:\n    print(f\"{w:>6} {'#' * c} {c}\")\n",
    "blocked": "import os\nprint(os.listdir('.'))\n",
}


def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    css = ("<style>#code{font-family:ui-monospace,'Cascadia Code',Consolas,monospace;font-size:14px;line-height:1.6;min-height:280px;tab-size:4;white-space:pre;resize:vertical}"
           ".sb-out{font-family:ui-monospace,'Cascadia Code',Consolas,monospace;font-size:13.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word;margin:0;min-height:160px;"
           "padding:14px 16px;border-radius:14px;background:#0b1020;color:#d1e7ff;border:1px solid var(--line);max-height:460px;overflow:auto}"
           ".sb-out.err{color:#fca5a5}.sb-badge{font-size:12px;font-weight:700;padding:4px 10px;border-radius:99px;background:var(--surface2);border:1px solid var(--line)}"
           ".sb-badge.ok{color:#22c55e;border-color:#22c55e55}.sb-badge.bad{color:#ef4444;border-color:#ef444455}.sb-badge.warn{color:#f59e0b;border-color:#f59e0b55}"
           ".sb-samples{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}</style>")
    samples = ('<div class="sb-samples">' + "".join(
        web.button(T(f"w_s_{k}"), cls="pb-btn-sm sb-sample", kind="ghost", icon_name="alert" if k == "blocked" else "code", **{"data-k": k}) for k in SANDBOX_SAMPLES) + "</div>")
    editor = web.card(T("w_card_editor"), samples + web.textarea("code", "", rows=12, value=SANDBOX_SAMPLES["fib"], spellcheck="false")
                      + '<div class="pb-row">' + web.button(T("run"), "run", icon_name="play") + '<span class="pb-hint">Ctrl + Enter</span></div>', icon_name="code")
    out = web.card(T("w_card_output"), '<pre class="sb-out" id="out"></pre>', icon_name="list", aside='<span class="sb-badge" id="badge">—</span>')
    rules = web.card(T("w_card_rules"), "".join(web.note(T(k), "warn" if k == "w_r_block" else "info", ic) for k, ic in
                                                (("w_r_iso", "shield"), ("w_r_block", "lock"), ("w_r_time", "clock"))), icon_name="shield")
    st = web.stats([(T("w_st_runs"), "0", "s1", "play"), (T("w_st_ok"), "0", "s2", "check"), (T("w_st_blocked"), "0", "s3", "lock"), (T("w_st_avg"), "0", "s4", "clock")])
    hero = web.hero(T("w_title"), T("w_hero"), "🐍", chips=["Python 3", "AST", T("w_chip_timeout")])
    web.send_page(handler, lang, title=T("w_title"), emoji="🐍", brand="#ca8a04", port=PORT, hero_html=hero,
                  body=css + st + web.grid(editor, out, min_width=360) + rules,
                  script="window.SB_SAMPLES=" + json.dumps(SANDBOX_SAMPLES) + ";" + SANDBOX_JS)


SANDBOX_JS = r"""
const $=s=>document.querySelector(s);
$('#out').textContent=pb.t('w_out_empty');
document.querySelectorAll('.sb-sample').forEach(b=>b.onclick=()=>{$('#code').value=SB_SAMPLES[b.dataset.k]||'';$('#code').focus()});
$('#code').addEventListener('keydown',e=>{if(e.key==='Tab'){e.preventDefault();const t=e.target,s=t.selectionStart;t.setRangeText('    ',s,t.selectionEnd,'end')}
  if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();run()}});
async function stats(){const d=await pb.json('/api/status').catch(()=>null);if(d&&d.stats){const s=d.stats;pb.count($('#s1'),s.total_runs||0);pb.count($('#s2'),s.success_runs||0);pb.count($('#s3'),s.blocked_ast||0);
  $('#s4').textContent=(+s.avg_time||0).toFixed(2)+' '+pb.t('w_sec')}}
async function run(){const code=$('#code').value;if(!code.trim())return;const b=$('#run');pb.busy(b,true);const o=$('#out'),g=$('#badge');
  o.className='sb-out';o.textContent=pb.t('w_running');g.className='sb-badge';g.textContent='…';
  try{const d=await pb.postJSON('/api/run',{code});const t=(+d.exec_time||0).toFixed(3)+' '+pb.t('w_sec');
    if(d.success){g.className='sb-badge ok';g.textContent='✓ '+pb.t('w_ok')+' · '+t;o.textContent=d.stdout||pb.t('w_no_output')}
    else{const blocked=d.status==='AST_BLOCKED',to=d.status==='TIMEOUT';g.className='sb-badge '+(blocked||to?'warn':'bad');
      g.textContent=(blocked?pb.t('w_blocked'):to?pb.t('w_timeout'):pb.t('w_failed'))+' · '+t;o.className='sb-out err';o.textContent=(d.stdout?d.stdout+'\n':'')+(d.error||d.violation||'')}
    stats()}
  catch(err){g.className='sb-badge bad';g.textContent=pb.t('error');o.className='sb-out err';o.textContent=err.message}finally{pb.busy(b,false)}}
$('#run').onclick=run;stats();
"""


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
