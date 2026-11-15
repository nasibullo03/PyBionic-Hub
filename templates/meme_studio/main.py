"""MemeGen & Demotivator Studio — Telegram Bot & 100% Offline Local Web Studio.
100% ReplyKeyboardMarkup (all buttons next to keyboard, zero inline text buttons), 24 languages, and live Cyberpunk canvas.
"""

from __future__ import annotations

import pybionic_core as core
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


def start_web_studio(port: int) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            u = urllib.parse.urlparse(self.path)
            lang = urllib.parse.parse_qs(u.query).get("lang", [current_lang()])[0]
            rtl_attr = ' dir="rtl"' if is_rtl(lang) else ""

            lang_options = "\n".join(
                f'<option value="{code}"{" selected" if code == lang else ""}>{html.escape(label)}</option>'
                for code, label in SUPPORTED_LANGUAGES
            )

            html_page = f"""<!doctype html>
<html lang="{lang}"{rtl_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(t('web_title', lang_override=lang))}</title>
<style>
:root {{
  --bg-deep: #0A0F1A;
  --bg-card: #121A2B;
  --bg-input: #0D1322;
  --accent-cyan: #00D8FF;
  --accent-emerald: #00E676;
  --accent-gold: #FFC107;
  --text-main: #E6F1FF;
  --text-dim: #8BA0C6;
  --border: #1F2D4A;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg-deep);
  color: var(--text-main);
  font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  padding: 16px;
  max-width: 640px;
  margin: 0 auto;
}}
header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
}}
.brand {{ font-size: 20px; font-weight: 800; color: var(--accent-cyan); }}
.lang-sel {{
  background: var(--bg-input);
  color: var(--text-main);
  border: 1px solid var(--border);
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 13px;
}}
.card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}}
.style-tabs {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-top: 14px;
}}
.style-btn {{
  background: var(--bg-input);
  color: var(--text-dim);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;
}}
.style-btn.active {{
  background: rgba(0, 216, 255, 0.12);
  color: var(--accent-cyan);
  border-color: var(--accent-cyan);
}}
input[type="text"], input[type="file"], select, button {{
  width: 100%;
  padding: 12px;
  margin-top: 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text-main);
  font-size: 15px;
}}
button.primary {{
  background: linear-gradient(135deg, #00D8FF, #0088cc);
  color: #001B2E;
  font-weight: 700;
  border: none;
  cursor: pointer;
}}
button.primary:hover {{ opacity: 0.95; }}
.canvas-wrap {{
  margin-top: 16px;
  text-align: center;
}}
#preview-img {{
  max-width: 100%;
  border-radius: 12px;
  border: 1px solid var(--border);
  display: block;
  margin: 0 auto;
}}
.btn-group {{
  display: flex;
  gap: 10px;
  margin-top: 12px;
}}
.btn-group button {{ margin-top: 0; }}
</style>
</head>
<body>
<header>
  <div class="brand">🎭 Meme & Demotivator Studio</div>
  <select class="lang-sel" onchange="location.href='/?lang='+this.value">
    {lang_options}
  </select>
</header>

<div class="card">
  <h2>{html.escape(t('web_title', lang_override=lang))}</h2>
  <p style="color:var(--text-dim);margin-top:6px;font-size:14px">{html.escape(t('web_subtitle', lang_override=lang))}</p>

  <div class="style-tabs">
    <div class="style-btn active" data-style="classic" onclick="pickStyle('classic')">{html.escape(t('style_classic', lang_override=lang))}</div>
    <div class="style-btn" data-style="demotivator" onclick="pickStyle('demotivator')">{html.escape(t('style_demotivator', lang_override=lang))}</div>
    <div class="style-btn" data-style="quote" onclick="pickStyle('quote')">{html.escape(t('style_quote', lang_override=lang))}</div>
    <div class="style-btn" data-style="blur" onclick="pickStyle('blur')">{html.escape(t('style_blur', lang_override=lang))}</div>
  </div>

  <input type="file" id="fi" accept="image/*">
  <input type="text" id="top" placeholder="{html.escape(t('ph_top', lang_override=lang))}" oninput="scheduleRender()">
  <input type="text" id="bot" placeholder="{html.escape(t('ph_bottom', lang_override=lang))}" oninput="scheduleRender()">

  <div class="btn-group">
    <button class="primary" onclick="renderNow()">{html.escape(t('btn_generate', lang_override=lang))}</button>
    <button style="background:#1F2D4A;color:#00D8FF" onclick="useSampleImage()">Образец</button>
  </div>
</div>

<div class="card" id="preview-card" style="display:none">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <h3>{html.escape(t('web_live_preview', lang_override=lang))}</h3>
    <a id="dl-link" download="meme.jpg" href="#"><button class="primary" style="padding:6px 14px;font-size:13px;margin:0">{html.escape(t('btn_download', lang_override=lang))}</button></a>
  </div>
  <div class="canvas-wrap">
    <img id="preview-img" src="" alt="Meme Preview">
  </div>
</div>

<script>
let currentStyle = 'classic';
let currentB64 = '';
let renderTimer = null;

function pickStyle(st) {{
  currentStyle = st;
  document.querySelectorAll('.style-btn').forEach(b => {{
    b.classList.toggle('active', b.dataset.style === st);
  }});
  scheduleRender();
}}

document.getElementById('fi').onchange = (e) => {{
  const f = e.target.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {{
    currentB64 = reader.result.split(',')[1] || '';
    renderNow();
  }};
  reader.readAsDataURL(f);
}};

function useSampleImage() {{
  const cvs = document.createElement('canvas');
  cvs.width = 800; cvs.height = 600;
  const ctx = cvs.getContext('2d');
  const g = ctx.createLinearGradient(0, 0, 800, 600);
  g.addColorStop(0, '#0f2027');
  g.addColorStop(0.5, '#203a43');
  g.addColorStop(1, '#2c5364');
  ctx.fillStyle = g; ctx.fillRect(0, 0, 800, 600);
  currentB64 = cvs.toDataURL('image/jpeg', 0.9).split(',')[1];
  document.getElementById('top').value = 'КОГДА КОД ЗАПУСТИЛСЯ';
  document.getElementById('bot').value = 'С ПЕРВОЙ ПОПЫТКИ';
  renderNow();
}}

function scheduleRender() {{
  if (renderTimer) clearTimeout(renderTimer);
  renderTimer = setTimeout(renderNow, 400);
}}

async function renderNow() {{
  if (!currentB64) return;
  const top = document.getElementById('top').value;
  const bot = document.getElementById('bot').value;
  try {{
    const res = await fetch('/render', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: new URLSearchParams({{
        b64: currentB64,
        style: currentStyle,
        top: top,
        bot: bot
      }})
    }});
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    document.getElementById('preview-img').src = url;
    document.getElementById('dl-link').href = url;
    document.getElementById('preview-card').style.display = 'block';
  }} catch (err) {{
    console.error(err);
  }}
}}
</script>
</body>
</html>
"""
            raw = html_page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

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
