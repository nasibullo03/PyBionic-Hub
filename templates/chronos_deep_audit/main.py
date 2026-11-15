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

        render_studio(self)


def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    up = chronos_engine.get_uptime_report()
    css = ("<style>.ch-row{display:grid;grid-template-columns:minmax(120px,1.2fr) 2fr auto;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line)}.ch-row:last-child{border:0}"
           ".ch-row b{display:block;font-weight:600}.ch-row small{color:var(--muted);font-family:ui-monospace,Consolas,monospace;font-size:12px}"
           ".ch-bar{height:10px;border-radius:99px;background:var(--surface2);overflow:hidden;border:1px solid var(--line)}"
           ".ch-bar i{display:block;height:100%;width:0;border-radius:99px;transition:width .8s cubic-bezier(.2,.8,.2,1)}"
           ".ch-ms{font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap;min-width:78px;text-align:end}"
           ".ch-hist{display:flex;align-items:flex-end;gap:10px;height:180px;padding-top:10px}.ch-col{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;height:100%;justify-content:flex-end}"
           ".ch-col i{width:100%;border-radius:10px 10px 4px 4px;background:linear-gradient(180deg,var(--brand),var(--brand2));min-height:4px;transition:height .8s cubic-bezier(.2,.8,.2,1)}"
           ".ch-col span{font-size:11.5px;color:var(--muted);white-space:nowrap}.ch-col b{font-size:13px}"
           ".ch-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin-top:10px}.ch-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-inline-end:6px;vertical-align:-1px}</style>")
    probes = web.card(T("w_card_probes"), '<div id="rows">' + "".join('<div class="pb-skel" style="height:46px;margin:8px 0"></div>' for _ in chronos_engine.TARGETS) + "</div>"
                      + '<div class="ch-legend"><span><i style="background:#22c55e"></i>&lt; 50 ms</span><span><i style="background:#f59e0b"></i>50–150 ms</span><span><i style="background:#ef4444"></i>&gt; 150 ms</span></div>'
                      + web.note(T("w_probe_note"), "info"), icon_name="wave",
                      aside=web.button(T("w_probe"), "probe", cls="pb-btn-sm", icon_name="refresh"))
    hist = web.card(T("w_card_hist"), '<div class="ch-hist" id="hist"></div><p class="pb-hint" id="hist-note"></p>', icon_name="chart")
    st = web.stats([(T("w_st_uptime"), f'{up.get("uptime_pct", 0)}%', "s0", "shield"), ("P50", "—", "s1", "clock"),
                    ("P99", "—", "s2", "zap"), (T("w_st_jitter"), "—", "s3", "wave"), (T("w_st_checks"), str(up.get("total_checks", 0)), "s4", "list")])
    hero = web.hero(T("w_title"), T("w_hero"), "⏳", chips=["P50 · P90 · P99", T("w_chip_jitter"), "TCP"])
    web.send_page(handler, lang, title=T("w_title"), emoji="⏳", brand="#0ea5e9", port=PORT,
                  hero_html=hero, body=css + st + web.grid(probes, hist, min_width=340), script=CHRONOS_JS)


CHRONOS_JS = r"""
const $=s=>document.querySelector(s);const ms=v=>(+v).toFixed(1)+' '+pb.t('w_ms');
const col=v=>v<50?'#22c55e':v<150?'#f59e0b':'#ef4444';
async function hist(){const t=await fetch('/api/histogram').then(r=>r.text()).catch(()=>'');const bins=[];
  t.split('\n').forEach(l=>{const m=l.match(/^\s*(\d+)\s*-\s*(\d+)ms.*\((\d+)\)\s*$/);if(m)bins.push({lo:+m[1],hi:+m[2],n:+m[3]})});
  const mx=Math.max(1,...bins.map(b=>b.n));
  $('#hist').innerHTML=bins.map(b=>`<div class="ch-col"><b>${b.n}</b><i style="height:0" data-h="${b.n*100/mx}"></i><span>${b.lo}–${b.hi}</span></div>`).join('');
  requestAnimationFrame(()=>document.querySelectorAll('.ch-col i').forEach(i=>i.style.height=Math.max(3,+i.dataset.h)+'%'));
  $('#hist-note').textContent=pb.t('w_hist_note',{n:bins.reduce((a,b)=>a+b.n,0)})}
async function status(){const d=await pb.json('/api/status').catch(()=>null);if(d&&d.uptime){$('#s0').textContent=d.uptime.uptime_pct+'%';pb.count($('#s4'),d.uptime.total_checks||0)}}
async function probe(){const b=$('#probe');pb.busy(b,true);
  try{const d=await pb.json('/api/audit');const mx=Math.max(100,...d.results.map(r=>+r.latency_ms));
    $('#rows').innerHTML=d.results.map(r=>`<div class="ch-row"><div><b>${pb.esc(r.name)}</b><small>${pb.esc(r.host)}:${+r.port}</small></div>
      <div class="ch-bar"><i style="background:${col(+r.latency_ms)}" data-w="${(+r.latency_ms)*100/mx}"></i></div><div class="ch-ms" style="color:${col(+r.latency_ms)}">${ms(r.latency_ms)}</div></div>`).join('');
    requestAnimationFrame(()=>document.querySelectorAll('.ch-bar i').forEach(i=>i.style.width=Math.max(2,+i.dataset.w)+'%'));
    $('#s1').textContent=ms(d.p50);$('#s2').textContent=ms(d.p99);$('#s3').textContent=ms(d.jitter);hist();status()}
  catch(e){pb.toast(pb.t('error_conn'),true)}finally{pb.busy(b,false)}}
$('#probe').onclick=probe;probe();
"""


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
    core.start_polling(bot)

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
