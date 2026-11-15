import pybionic_core as core
import pybionic_web as web
import sqlite3
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

        render_studio(self)


def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    stats = crm_engine.get_crm_stats()
    conn = sqlite3.connect(crm_engine.DB_PATH)
    try:
        rows = conn.execute("SELECT id, username, category, subject, topic_id, status, created_at FROM tickets ORDER BY id DESC LIMIT 30").fetchall()
    finally:
        conn.close()
    css = ("<style>.cr-st{font-size:11.5px;font-weight:700;padding:4px 9px;border-radius:99px;white-space:nowrap}"
           ".cr-open{background:#3b82f622;color:#3b82f6}.cr-pending{background:#f59e0b22;color:#f59e0b}.cr-resolved{background:#22c55e22;color:#22c55e}"
           ".cr-cat{font-size:12px;padding:3px 9px;border-radius:8px;background:var(--surface2);border:1px solid var(--line);white-space:nowrap}"
           ".cr-subj{max-width:420px;word-break:break-word}.cr-meta{color:var(--muted);font-size:12.5px;white-space:nowrap}"
           ".cr-flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.cr-flow div{padding:14px;border-radius:14px;border:1px solid var(--line);background:var(--surface2);font-size:13.5px}"
           ".cr-flow b{display:block;font-size:15px;margin-bottom:4px}</style>")
    st_names = {"OPEN": T("w_s_open"), "PENDING": T("w_s_pending"), "RESOLVED": T("w_s_resolved")}
    trs = []
    for r in rows:
        status = str(r[5] or "OPEN").upper()
        when = time.strftime("%d.%m %H:%M", time.localtime(r[6] or 0))
        trs.append([f"#{int(r[0])}", f'<span class="cr-cat">{web.esc(r[2])}</span>', f'<div class="cr-subj">{web.esc(r[3])}</div><span class="cr-meta">{web.esc(r[1] or "")}</span>',
                    f'<code>#{int(r[4] or 0)}</code>', f'<span class="cr-st cr-{status.lower()}">{web.esc(st_names.get(status, status))}</span>', f'<span class="cr-meta">{when}</span>'])
    table = web.table(["ID", T("w_cat"), T("w_subject"), T("w_topic"), T("status"), T("time")], trs, T("w_no_tickets"), raw=True)
    cats = [("Technical", T("w_c_tech")), ("Billing", T("w_c_billing")), ("Partnership", T("w_c_partner")), ("Other", T("w_c_other"))]
    create = web.card(T("w_card_new"),
        '<form id="f">' + web.field(T("w_cat"), web.segmented("cat", cats, "Technical", icons={"Technical": "settings", "Billing": "chart", "Partnership": "users", "Other": "sparkles"}))
        + web.field(T("w_subject"), web.textarea("subj", T("w_subject_ph"), rows=3, maxlength="300"))
        + web.button(T("w_create"), "go", type="submit", icon_name="plus") + "</form>", icon_name="plus")
    flow = web.card(T("w_card_flow"), '<div class="cr-flow">' + "".join(
        f"<div><b>{i}. {web.esc(T('w_f' + str(i) + '_t'))}</b>{web.esc(T('w_f' + str(i)))}</div>" for i in (1, 2, 3)) + "</div>"
        + web.note(T("w_flow_note"), "info"), icon_name="list")
    st = web.stats([(T("w_st_total"), str(stats.get("total", 0)), None, "list"), (T("w_s_open"), str(stats.get("open", 0)), None, "send"),
                    (T("w_s_pending"), str(stats.get("pending", 0)), None, "clock"), (T("w_s_resolved"), str(stats.get("resolved", 0)), None, "check")])
    tickets = web.card(T("w_card_tickets"), table, icon_name="folder", aside=web.button(T("refresh"), "rf", kind="ghost", cls="pb-btn-sm", icon_name="refresh"))
    hero = web.hero(T("w_title"), T("w_hero"), "🗂", chips=[T("w_chip_tickets"), T("w_chip_topics"), T("w_chip_statuses")])
    web.send_page(handler, lang, title=T("w_title"), emoji="🗂", brand="#6366f1", port=PORT, hero_html=hero,
                  body=css + st + web.grid(create, flow, min_width=330) + tickets, script=CRM_JS)


CRM_JS = r"""
const $=s=>document.querySelector(s);
$('#rf').onclick=()=>location.reload();
$('#f').addEventListener('submit',async e=>{e.preventDefault();const v=$('#subj').value.trim();if(!v)return pb.toast(pb.t('w_need_subject'),true);
  const b=$('#go');pb.busy(b,true);
  try{const d=await pb.json('/api/create_ticket?cat='+encodeURIComponent($('#cat').dataset.value)+'&subj='+encodeURIComponent(v));
    pb.toast(pb.t('w_created',{id:d.ticket_id||d.id||''}));setTimeout(()=>location.reload(),700)}
  catch(err){pb.busy(b,false);pb.toast(pb.t('error')+': '+err.message,true)}});
"""


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
    core.start_polling(bot)

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
