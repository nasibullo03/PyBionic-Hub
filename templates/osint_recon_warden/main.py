import pybionic_core as core
import pybionic_web as web
from typing import Any
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import html
import json
from html import escape as html_escape
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

        render_studio(self)


def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    css = ("<style>.os-search{display:flex;gap:10px;flex-wrap:wrap}.os-search .pb-input-wrap{flex:1;min-width:220px}"
           ".os-score{display:flex;align-items:center;gap:22px;flex-wrap:wrap}.os-ring{--p:0;--c:var(--brand);width:128px;height:128px;border-radius:50%;flex:none;display:grid;place-items:center;"
           "background:conic-gradient(var(--c) calc(var(--p)*1%),var(--surface2) 0);transition:--p .8s}"
           ".os-ring b{width:100px;height:100px;border-radius:50%;background:var(--solid);display:grid;place-items:center;font-size:30px;font-weight:800;line-height:1}"
           ".os-ring b small{display:block;font-size:12px;font-weight:500;color:var(--muted)}"
           ".os-grade{font-size:20px;font-weight:800}.os-target{font-family:ui-monospace,Consolas,monospace;color:var(--muted);word-break:break-all}"
           ".os-kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}.os-kv div{padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:var(--surface2);min-width:0}"
           ".os-kv span{display:block;font-size:12px;color:var(--muted);margin-bottom:4px}.os-kv b{font-weight:600;word-break:break-word;font-size:14px}"
           ".os-chk{display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid var(--line)}.os-chk:last-child{border:0}"
           ".os-chk .ok,.os-chk .no{width:26px;height:26px;border-radius:8px;display:grid;place-items:center;flex:none}.os-chk .ok{background:#22c55e22;color:#22c55e}.os-chk .no{background:#ef444422;color:#ef4444}"
           ".os-chk div{flex:1;min-width:0}.os-chk b{display:block;font-weight:600;font-size:14px}.os-chk small{color:var(--muted);font-size:12.5px}"
           ".os-sans{display:flex;flex-wrap:wrap;gap:6px}.os-sans span{font-size:12px;padding:4px 9px;border-radius:99px;background:var(--surface2);border:1px solid var(--line);font-family:ui-monospace,Consolas,monospace}</style>")
    search = web.card(T("w_card_scan"),
        '<form class="os-search" id="f">' + web.input_("target", "example.com", icon_name="globe", autocomplete="off", spellcheck="false")
        + web.button(T("w_scan"), "go", type="submit", icon_name="search") + "</form>" + web.progress("prog")
        + web.note(T("w_scan_note"), "info", "shield"), icon_name="search")
    res = ('<div id="res" hidden>'
           + web.card(T("w_card_score"), '<div class="os-score"><div class="os-ring" id="ring"><b><span id="sc">0</span><small>/100</small></b></div>'
                      '<div><div class="os-grade" id="grade"></div><div class="os-target" id="tgt"></div><p class="pb-hint" id="when"></p></div></div>', icon_name="shield")
           + web.grid(
               web.card(T("w_card_net"), '<div class="os-kv" id="kv"></div><div class="os-sans" id="sans" style="margin-top:12px"></div>', icon_name="globe"),
               web.card(T("w_card_headers"), '<div id="hdrs"></div>', icon_name="lock"), min_width=330)
           + "</div>")
    empty = web.empty_state(T("w_empty"), "search", id="empty")
    st = web.card(T("statistics"), web.stats([(T("w_st_scans"), "0", "s1", "search"), (T("w_st_last"), "—", "s2", "globe")]), icon_name="chart")
    hero = web.hero(T("w_title"), T("w_hero"), "🛰", chips=["DNS", "TLS", "HSTS · CSP", "A–F"])
    web.send_page(handler, lang, title=T("w_title"), emoji="🛰", brand="#14b8a6", port=PORT,
                  hero_html=hero, body=css + search + empty + res + st, script=OSINT_JS)


OSINT_JS = r"""
const $=s=>document.querySelector(s);
const HDR=[['hsts','Strict-Transport-Security','w_h_hsts'],['csp','Content-Security-Policy','w_h_csp'],['x_frame_options','X-Frame-Options','w_h_xfo'],
  ['x_content_type','X-Content-Type-Options','w_h_xcto'],['referrer_policy','Referrer-Policy','w_h_ref']];
const ICO_OK='<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
const ICO_NO='<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';
function grade(s){return s>=90?['A','#22c55e']:s>=75?['B','#84cc16']:s>=55?['C','#f59e0b']:s>=35?['D','#f97316']:['F','#ef4444']}
function show(r){if(!r||!r.target)return;$('#empty').hidden=true;$('#res').hidden=false;
  const s=+r.security_score||0,[g,c]=grade(s);const ring=$('#ring');ring.style.setProperty('--c',c);ring.style.setProperty('--p',s);pb.count($('#sc'),s);
  $('#grade').textContent=pb.t('w_grade',{g});$('#grade').style.color=c;$('#tgt').textContent=r.target;
  try{$('#when').textContent=new Date(r.timestamp).toLocaleString(PB_LANG)}catch(e){}
  const d=r.dns||{},t=r.ssl||{},na=v=>(v&&v!=='N/A')?v:'—';
  const days=t.valid&&t.days_left!==undefined?pb.t('w_days_left',{n:t.days_left}):'';
  const kv=[[pb.t('w_ipv4'),(d.ipv4||[]).join(', ')||'—'],[pb.t('w_ipv6'),(d.ipv6||[]).slice(0,3).join(', ')||'—'],[pb.t('w_issuer'),na(t.issuer)],
    [pb.t('w_expires'),na(t.expires)+(days?' · '+days:'')],[pb.t('w_cipher'),na(t.cipher)],[pb.t('w_http'),r.headers&&r.headers.status?String(r.headers.status):'—']];
  $('#kv').innerHTML=kv.map(([k,v])=>`<div><span>${pb.esc(k)}</span><b>${pb.esc(v)}</b></div>`).join('');
  $('#sans').innerHTML=(t.sans||[]).map(x=>`<span>${pb.esc(x)}</span>`).join('');
  const h=r.headers||{};$('#hdrs').innerHTML=HDR.map(([k,name,desc])=>`<div class="os-chk"><span class="${h[k]?'ok':'no'}">${h[k]?ICO_OK:ICO_NO}</span>
    <div><b>${name}</b><small>${pb.esc(pb.t(desc))}</small></div></div>`).join('');
  $('#s2').textContent=r.target}
async function status(){const d=await pb.json('/api/status').catch(()=>null);if(d){pb.count($('#s1'),d.scanned_count||0);if(d.last_target)$('#s2').textContent=d.last_target}}
$('#f').addEventListener('submit',async e=>{e.preventDefault();const v=$('#target').value.trim().replace(/^https?:\/\//,'').replace(/\/.*$/,'');
  if(!v)return pb.toast(pb.t('w_need_target'),true);const b=$('#go');pb.busy(b,true);pb.progress('prog',null,pb.t('w_scanning',{t:v}));
  try{const r=await fetch('/api/scan?target='+encodeURIComponent(v));const d=await r.json();if(!r.ok||d.error)throw new Error(d.error||('HTTP '+r.status));
    pb.hide('prog');show(d);status();$('#res').scrollIntoView({behavior:'smooth',block:'start'})}
  catch(err){pb.hide('prog');pb.toast(pb.t('error')+': '+err.message,true)}finally{pb.busy(b,false)}});
pb.json('/api/last').then(r=>{show(r);if(r&&r.target)$('#target').value=r.target}).catch(()=>{});status();
"""


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
    core.start_polling(bot)

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
