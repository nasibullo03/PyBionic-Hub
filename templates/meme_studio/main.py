"""MemeGen & Demotivator Studio — Telegram Bot & 100% Offline Local Web Studio.
100% ReplyKeyboardMarkup (all buttons next to keyboard, zero inline text buttons), 24 languages, and live Cyberpunk canvas.
"""

from __future__ import annotations

import pybionic_core as core
import pybionic_web as web
import base64
import html
import http.server
import io
import json
import os
import re
import socketserver
import sqlite3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import textwrap
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

from i18n import (
    SUPPORTED_LANGUAGES,
    build_reply_language_keyboard,
    current_lang,
    get_user_lang,
    is_rtl,
    log,
    parse_lang_choice,
    set_user_lang,
    t,
)

FONT_CANDIDATES = [
    "/system/fonts/Roboto-Bold.ttf",
    "/system/fonts/NotoSans-Bold.ttf",
    "/system/fonts/NotoSans-Regular.ttf",
    "/system/fonts/DroidSans-Bold.ttf",
    "/system/fonts/NotoNaskhArabic-Bold.ttf",
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/Roboto-Regular.ttf",
]

STYLE_OPTIONS = [
    ("classic", "🎭 Классический мем"),
    ("demotivator", "⬛ Демотиватор"),
    ("quote", "💬 Цитата"),
    ("blur", "🌫 Размытие"),
]


def get_data_dir() -> Path:
    d = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    d.mkdir(parents=True, exist_ok=True)
    return d


def init_db() -> None:
    db = get_data_dir() / "meme_users.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_styles (
                user_id INTEGER PRIMARY KEY,
                style TEXT NOT NULL,
                updated_at REAL
            )
            """
        )


def get_user_style(user_id: int | str) -> str:
    db = get_data_dir() / "meme_users.db"
    try:
        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT style FROM user_styles WHERE user_id = ?", (int(user_id),)).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return "classic"


def set_user_style(user_id: int | str, style: str) -> None:
    db = get_data_dir() / "meme_users.db"
    try:
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_styles (user_id, style, updated_at)
                VALUES (?, ?, ?)
                """,
                (int(user_id), style, time.time()),
            )
    except Exception:
        pass


def load_font(size: int, text: str = ""):
    from PIL import ImageFont

    has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in text)
    ordered = (
        ["/system/fonts/NotoNaskhArabic-Bold.ttf", "/system/fonts/NotoNaskhArabic-Regular.ttf"]
        if has_arabic
        else []
    ) + FONT_CANDIDATES
    for candidate in ordered:
        if os.path.isfile(candidate):
            try:
                return ImageFont.truetype(candidate, size=size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def draw_outlined_multiline(draw, xy: tuple[int, int], text: str, font, fill="white", stroke_fill="black", stroke_width=3, align="center"):
    draw.multiline_text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor="ma",
        align=align,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def render_meme(img_bytes: bytes, top_text: str, bottom_text: str, style: str = "classic", custom_font_size: int = 0) -> bytes:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps

    with Image.open(io.BytesIO(img_bytes)) as src_im:
        im = ImageOps.exif_transpose(src_im).convert("RGB")

    max_w = 960
    if im.width > max_w or im.width < 480:
        ratio = max_w / float(im.width)
        im = im.resize((max_w, max(240, int(im.height * ratio))), Image.Resampling.LANCZOS)

    style = (style or "classic").strip().lower()

    if style == "blur":
        blurred = im.filter(ImageFilter.GaussianBlur(radius=14))
        buf = io.BytesIO()
        blurred.save(buf, format="JPEG", quality=92)
        return buf.getvalue()

    if style == "demotivator":
        pad_x = max(48, im.width // 14)
        pad_top = max(48, im.width // 14)
        base_size = custom_font_size if custom_font_size > 0 else max(30, im.width // 16)
        font_title = load_font(base_size, top_text)
        font_sub = load_font(max(20, int(base_size * 0.65)), bottom_text)
        title_lines = textwrap.wrap(top_text.strip(), width=26) if top_text.strip() else []
        sub_lines = textwrap.wrap(bottom_text.strip(), width=38) if bottom_text.strip() else []
        footer_h = 46 + len(title_lines) * (font_title.size + 8) + len(sub_lines) * (font_sub.size + 6)
        canvas = Image.new("RGB", (im.width + pad_x * 2, im.height + pad_top + footer_h), (8, 8, 10))
        canvas.paste(im, (pad_x, pad_top))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            [pad_x - 4, pad_top - 4, pad_x + im.width + 3, pad_top + im.height + 3],
            outline=(235, 235, 235),
            width=2,
        )
        y_cursor = pad_top + im.height + 18
        if title_lines:
            draw.multiline_text(
                (canvas.width // 2, y_cursor),
                "\n".join(title_lines),
                font=font_title,
                fill=(255, 255, 255),
                anchor="ma",
                align="center",
            )
            y_cursor += len(title_lines) * (font_title.size + 8) + 6
        if sub_lines:
            draw.multiline_text(
                (canvas.width // 2, y_cursor),
                "\n".join(sub_lines),
                font=font_sub,
                fill=(200, 210, 225),
                anchor="ma",
                align="center",
            )
        out = io.BytesIO()
        canvas.save(out, format="JPEG", quality=92)
        return out.getvalue()

    if style == "quote":
        bg = im.filter(ImageFilter.GaussianBlur(radius=16)).point(lambda p: int(p * 0.45))
        draw = ImageDraw.Draw(bg)
        quote = (top_text or bottom_text).strip() or "PyBionic Studio"
        author = bottom_text.strip() if (top_text.strip() and bottom_text.strip()) else ""
        base_size = custom_font_size if custom_font_size > 0 else max(26, bg.width // 18)
        font_q = load_font(base_size, quote)
        wrapped = "\n".join(textwrap.wrap(f'"{quote}"', width=24))
        draw.multiline_text(
            (bg.width // 2, int(bg.height * 0.36)),
            wrapped,
            font=font_q,
            fill=(242, 248, 255),
            anchor="ma",
            align="center",
            stroke_width=2,
            stroke_fill=(0, 0, 0),
        )
        if author:
            font_a = load_font(max(20, int(base_size * 0.7)), author)
            draw.text(
                (bg.width // 2, int(bg.height * 0.78)),
                f"— {author}",
                font=font_a,
                fill=(0, 216, 255),
                anchor="ma",
            )
        out = io.BytesIO()
        bg.save(out, format="JPEG", quality=92)
        return out.getvalue()

    # Classic top + bottom meme
    draw = ImageDraw.Draw(im)
    font_sz = custom_font_size if custom_font_size > 0 else max(30, im.width // 14)
    stroke_w = max(2, font_sz // 11)
    if top_text.strip():
        wrapped_top = "\n".join(textwrap.wrap(top_text.strip().upper(), width=20))
        font = load_font(font_sz, wrapped_top)
        draw_outlined_multiline(draw, (im.width // 2, 16), wrapped_top, font, stroke_width=stroke_w)
    if bottom_text.strip():
        lines = textwrap.wrap(bottom_text.strip().upper(), width=20)
        wrapped_bot = "\n".join(lines)
        font = load_font(font_sz, wrapped_bot)
        block_h = len(lines) * (font_sz + 6)
        draw_outlined_multiline(
            draw,
            (im.width // 2, max(16, im.height - block_h - 18)),
            wrapped_bot,
            font,
            stroke_width=stroke_w,
        )

    out = io.BytesIO()
    im.save(out, format="JPEG", quality=92)
    return out.getvalue()


def render_studio(handler: Any, port: int) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    styles = [("classic", T("style_classic")), ("demotivator", T("style_demotivator")), ("quote", T("style_quote")), ("blur", T("style_blur"))]
    left = web.card(T("w_card_make"),
        web.field(T("w_style"), web.segmented("style", styles, "classic"))
        + web.dropzone("fi", T("drop_or_click"), "JPG · PNG · WebP", accept="image/*", icon_name="image")
        + web.field(T("ph_top"), web.input_("top", T("ph_top")))
        + web.field(T("ph_bottom"), web.input_("bot", T("ph_bottom")))
        + '<div class="pb-row">' + web.button(T("btn_generate"), "go", icon_name="sparkles")
        + web.button(T("w_sample"), "sample", kind="ghost", icon_name="image") + "</div>", icon_name="sparkles")
    right = web.card(T("web_live_preview"),
        '<img id="pv" alt="" hidden style="width:100%;border-radius:14px;box-shadow:var(--sh2)">'
        + web.empty_state(T("w_preview_empty"), "image", id="pv-empty")
        + '<a class="pb-btn pb-btn-primary" id="dl" hidden download="meme.jpg">' + web.icon("download") + f'<span>{web.esc(T("btn_download"))}</span></a>',
        icon_name="image")
    hero = web.hero(T("w_title"), T("web_subtitle"), "🎭", chips=[T("style_classic"), T("style_demotivator"), T("style_quote"), "JPG"])
    web.send_page(handler, lang, title=T("w_title"), emoji="🎭", brand="#ef4444", port=port,
                  hero_html=hero, body=web.grid(left, right, min_width=330), script=MEME_JS)


MEME_JS = r"""
const $=s=>document.querySelector(s);let b64='',timer=null;
async function render(){if(!b64)return;
  try{const r=await fetch('/render',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:new URLSearchParams({b64,style:$('#style').dataset.value,top:$('#top').value,bot:$('#bot').value})});
    if(!r.ok)throw new Error('HTTP '+r.status);const u=URL.createObjectURL(await r.blob());
    $('#pv').src=u;$('#pv').hidden=false;$('#pv-empty').hidden=true;$('#dl').href=u;$('#dl').hidden=false}
  catch(err){pb.toast(pb.t('error')+': '+err.message,true)}}
const later=()=>{clearTimeout(timer);timer=setTimeout(render,400)};
$('#top').addEventListener('input',later);$('#bot').addEventListener('input',later);$('#style').addEventListener('change',later);
$('#fi-zone').addEventListener('pb:files',e=>{const f=e.detail[0];if(!f)return;const rd=new FileReader();rd.onload=()=>{b64=String(rd.result).split(',')[1]||'';render()};rd.readAsDataURL(f)});
$('#go').onclick=()=>{if(!b64){pb.toast(pb.t('need_file'),true);return}render()};
$('#sample').onclick=()=>{const c=document.createElement('canvas');c.width=800;c.height=600;const x=c.getContext('2d');
  const g=x.createLinearGradient(0,0,800,600);g.addColorStop(0,'#0f2027');g.addColorStop(.5,'#203a43');g.addColorStop(1,'#2c5364');x.fillStyle=g;x.fillRect(0,0,800,600);
  b64=c.toDataURL('image/jpeg',.9).split(',')[1];$('#top').value=pb.t('w_sample_top');$('#bot').value=pb.t('w_sample_bot');render()};
"""


def start_web_studio(port: int) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            u = urllib.parse.urlparse(self.path)
            render_studio(self, port)

        def do_POST(self) -> None:
            if self.path != "/render":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 16 * 1024 * 1024)).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw)
            b64 = (params.get("b64") or [""])[0]
            style = (params.get("style") or ["classic"])[0]
            top = (params.get("top") or [""])[0]
            bot_txt = (params.get("bot") or [""])[0]
            try:
                out = render_meme(base64.b64decode(b64), top, bot_txt, style)
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
                log("log_meme_web", style=style)
            except Exception as exc:
                err = str(exc).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)

    class Reusable(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    def serve() -> None:
        try:
            with Reusable((os.environ.get("BIND_HOST", "127.0.0.1"), port), Handler) as srv:
                print(f"[PYBIONIC_WEB:{port}]", flush=True)
                log("log_web_started", port=port)
                srv.serve_forever()
        except Exception as exc:
            log("log_error", err=f"Web server failed on port {port}: {exc}")

    threading.Thread(target=serve, daemon=True).start()


def run_telegram_bot(token: str) -> None:
    import telebot
    from telebot import types

    init_db()
    bot = telebot.TeleBot(token, parse_mode="HTML")

    def build_main_reply_kb(uid: int) -> types.ReplyKeyboardMarkup:
        active = get_user_style(uid)
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)

        def btn_txt(code: str, label: str) -> str:
            return f"{label} ✓" if code == active else label

        kb.row(
            types.KeyboardButton(btn_txt("classic", "🎭 Классический мем")),
            types.KeyboardButton(btn_txt("demotivator", "⬛ Демотиватор")),
        )
        kb.row(
            types.KeyboardButton(btn_txt("quote", "💬 Цитата")),
            types.KeyboardButton(btn_txt("blur", "🌫 Размытие")),
        )
        kb.row(
            types.KeyboardButton(core.btn("btn_lang", uid)),
            types.KeyboardButton(core.btn("btn_help", uid)),
        )
        return kb

    @bot.message_handler(commands=["start"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_welcome", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(commands=["help"])
    def on_help(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_help_text", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(commands=["lang", "language"])
    def on_lang_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            t("tg_lang_title", user_id=uid),
            reply_markup=build_reply_language_keyboard(user_id=uid, back_text=core.btn("btn_menu", uid)),
        )

    @bot.message_handler(func=lambda m: bool(m.text and parse_lang_choice(m.text)))
    def on_lang_chosen(msg: Any) -> None:
        uid = msg.from_user.id
        code = parse_lang_choice(msg.text)
        if code:
            set_user_lang(uid, code)
            bot.reply_to(msg, t("tg_lang_changed", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_menu", "btn_cancel"))
    def on_back(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, "Главное меню:", reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_lang"))
    def on_lang_btn(msg: Any) -> None:
        on_lang_cmd(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_help"))
    def on_help_btn(msg: Any) -> None:
        on_help(msg)

    # Style button handler from bottom keyboard
    @bot.message_handler(func=lambda m: any(kw in (m.text or "") for kw in (
        "Классический мем", "Демотиватор", "Цитата", "Размытие"
    )))
    def on_style_picked(msg: Any) -> None:
        uid = msg.from_user.id
        txt = msg.text or ""
        st = "classic"
        if "Демотиватор" in txt:
            st = "demotivator"
        elif "Цитата" in txt:
            st = "quote"
        elif "Размытие" in txt:
            st = "blur"

        set_user_style(uid, st)
        bot.reply_to(
            msg,
            f"✅ <b>Выбран стиль:</b> {txt.replace('✓', '').strip()}\n\nТеперь отправьте фото с текстом подписи!",
            reply_markup=build_main_reply_kb(uid),
        )

    # Photo message handler
    @bot.message_handler(content_types=["photo"])
    def on_photo(msg: Any) -> None:
        uid = msg.from_user.id
        caption = (msg.caption or "").strip()
        style = get_user_style(uid)

        if caption.startswith("!"):
            style = "demotivator"
            caption = caption[1:].strip()
        elif caption.startswith('"'):
            style = "quote"

        if "|" in caption:
            top, bottom = [x.strip() for x in caption.split("|", 1)]
        elif "\n" in caption:
            top, bottom = [x.strip() for x in caption.split("\n", 1)]
        else:
            top, bottom = caption, ""

        def run_render():
            try:
                img_bytes = core.download_tg_file(bot, msg.photo[-1].file_id)
                rendered = render_meme(img_bytes, top, bottom, style)
                bot.send_photo(
                    msg.chat.id,
                    io.BytesIO(rendered),
                    reply_to_message_id=msg.message_id,
                    reply_markup=build_main_reply_kb(uid),
                )
                log("log_meme_tg", style=style, user=uid)
            except Exception as exc:
                log("log_error", err=str(exc))
                bot.reply_to(msg, t("err_failed", user_id=uid, err=str(exc)[:180]), reply_markup=build_main_reply_kb(uid))

        threading.Thread(target=run_render, daemon=True).start()

    log("log_started_tg")
    core.start_polling(bot, timeout=30, long_polling_timeout=25)


def main() -> int:
    init_db()
    log("log_boot")
    port_raw = os.environ.get("WEB_PORT", "8089").strip()
    if port_raw.isdigit() and int(port_raw) > 0:
        start_web_studio(int(port_raw))
    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        run_telegram_bot(token)
    elif port_raw.isdigit() and int(port_raw) > 0:
        log("log_web_only", port=port_raw)
        while True:
            time.sleep(3600)
    else:
        log("err_missing_token")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
