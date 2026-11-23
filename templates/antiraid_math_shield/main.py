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

        render_studio(self)


def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    css = ("<style>.ar-eq{font-family:'Unbounded','Onest',system-ui,sans-serif;font-weight:700;font-size:clamp(34px,6vw,52px);text-align:center;padding:26px 10px;"
           "border-radius:20px;background:linear-gradient(135deg,color-mix(in srgb,var(--brand) 16%,transparent),color-mix(in srgb,var(--brand2) 10%,transparent));border:1px solid var(--line);letter-spacing:.02em}"
           ".ar-opts{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:14px}"
           ".ar-opt{font:inherit;font-size:22px;font-weight:800;padding:18px;border-radius:16px;border:1px solid var(--line);background:var(--surface2);color:var(--text);cursor:pointer;transition:transform .15s,border-color .2s,background .2s}"
           ".ar-opt:hover{transform:translateY(-2px);border-color:var(--brand)}.ar-opt:disabled{cursor:default;transform:none}"
           ".ar-opt.ok{background:#22c55e22;border-color:#22c55e;color:#22c55e}.ar-opt.bad{background:#ef444422;border-color:#ef4444;color:#ef4444;animation:arShake .4s}"
           "@keyframes arShake{25%{transform:translateX(-6px)}75%{transform:translateX(6px)}}"
           ".ar-timer{height:6px;border-radius:99px;background:var(--surface2);overflow:hidden;margin-top:14px}.ar-timer i{display:block;height:100%;width:100%;background:linear-gradient(90deg,var(--brand),var(--brand2));transition:width 1s linear}"
           ".ar-res{min-height:26px;margin-top:12px;text-align:center;font-weight:600}"
           ".ar-steps{counter-reset:s;display:grid;gap:10px;margin:0;padding:0;list-style:none}.ar-steps li{counter-increment:s;display:flex;gap:12px;align-items:flex-start;font-size:14px}"
           ".ar-steps li:before{content:counter(s);flex:none;width:26px;height:26px;border-radius:8px;display:grid;place-items:center;font-weight:700;font-size:13px;color:#fff;background:linear-gradient(135deg,var(--brand),var(--brand2))}</style>")
    test = web.card(T("w_card_test"),
        '<p class="pb-hint" style="margin-top:0">' + web.esc(T("w_test_hint")) + "</p>"
        + '<div class="ar-eq" id="eq">…</div><div class="ar-opts" id="opts"></div>'
        + '<div class="ar-timer"><i id="timer"></i></div><div class="ar-res" id="res"></div>'
        + '<div class="pb-row" style="justify-content:center">' + web.button(T("w_new"), "new", kind="ghost", icon_name="refresh") + "</div>",
        icon_name="zap")
    steps = "".join(f"<li>{web.esc(T(k))}</li>" for k in ("w_step1", "w_step2", "w_step3", "w_step4"))
    how = web.card(T("w_card_how"), f'<ol class="ar-steps">{steps}</ol>' + web.note(T("w_how_note"), "info", "shield"), icon_name="shield")
    st = web.stats([(T("w_st_checks"), "0", "s0", "list"), (T("w_st_verified"), "0", "s1", "check"),
                    (T("w_st_blocked"), "0", "s2", "x"), (T("w_st_avg"), "0", "s3", "clock")])
    hero = web.hero(T("w_title"), T("w_hero"), "🛡", chips=[T("w_chip_captcha"), T("w_chip_raid"), T("w_chip_nolinks")])
    web.send_page(handler, lang, title=T("w_title"), emoji="🛡", brand="#8b5cf6", port=PORT,
                  hero_html=hero, body=css + st + web.grid(test, how, min_width=330), script=ANTIRAID_JS)


ANTIRAID_JS = r"""
const $=s=>document.querySelector(s);let tick=null,left=0,total=60;
async function stats(){const d=await pb.json('/api/status').catch(()=>null);if(d&&d.stats){const s=d.stats;pb.count($('#s0'),s.total_checks||0);pb.count($('#s1'),s.verified||0);pb.count($('#s2'),s.blocked||0);
  $('#s3').textContent=(+s.avg_time||0).toFixed(1)+' '+pb.t('w_sec')}}
function timer(){clearInterval(tick);left=total;$('#timer').style.width='100%';tick=setInterval(()=>{left--;$('#timer').style.width=Math.max(0,left*100/total)+'%';if(left<=0){clearInterval(tick);lock();res(false,'timeout')}},1000)}
function lock(){document.querySelectorAll('.ar-opt').forEach(b=>b.disabled=true)}
function res(ok,reason){const r=$('#res');r.style.color=ok?'#22c55e':'#ef4444';r.textContent=ok?'✅ '+pb.t('w_ok'):'❌ '+pb.t('w_fail_'+(['timeout','wrong_answer','no_challenge'].includes(reason)?reason:'wrong_answer'))}
async function load(){$('#res').textContent='';const c=await pb.json('/api/challenge').catch(()=>null);if(!c){pb.toast(pb.t('error_conn'),true);return}
  total=+c.timeout||60;$('#eq').textContent=c.equation+' = ?';
  $('#opts').innerHTML=c.options.map(o=>`<button class="ar-opt" type="button" data-v="${+o}">${+o}</button>`).join('');
  document.querySelectorAll('.ar-opt').forEach(b=>b.onclick=async()=>{lock();clearInterval(tick);
    const d=await pb.json('/api/verify?answer='+b.dataset.v).catch(()=>({success:false,reason:'error'}));
    b.classList.add(d.success?'ok':'bad');res(d.success,d.reason);stats();setTimeout(load,2200)});timer()}
$('#new').onclick=load;load();stats();
"""


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
