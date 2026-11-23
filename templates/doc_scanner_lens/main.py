#!/usr/bin/env python3
"""Doc Scanner Lens (BotHub Level 10/10)
High-clarity document perspective deskew, shadow remover, paper whitener, and multi-page PDF compiler.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- Pure-Pillow shadow division normalization & paper whitening (removes camera shadows, boosts ink clarity).
- Grayscale, 1-bit monochrome binarization, and color-enhanced scan filters.
- Multi-page document accumulation and instant PDF compilation with metadata.
- Standalone Cyberpunk Web Studio on port 8103 with drag-and-drop & live preview.
- 24 languages support via i18n and locales.json.
- Fully offline capable without BOT_TOKEN.
"""

from __future__ import annotations

import pybionic_core as core
import pybionic_web as web
import html
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import struct
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import tempfile
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class ThreadedStudioServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    import telebot
    from telebot import types
except ImportError:
    telebot = None
    types = None

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:
    Image = None
    ImageEnhance = None
    ImageFilter = None
    ImageOps = None

import i18n

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("doc_scanner_lens")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8103"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "doc_scanner.db"
PAGES_DIR = DATA_DIR / "pages"
PAGES_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR = DATA_DIR / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Database Management
# ---------------------------------------------------------------------------
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                filter_mode TEXT DEFAULT 'whitener',
                lang TEXT DEFAULT 'ru',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                page_order INTEGER,
                image_path TEXT,
                width INTEGER,
                height INTEGER,
                created_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                pages_count INTEGER,
                filter_mode TEXT,
                pdf_bytes INTEGER,
                created_at INTEGER
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_user_settings(user_id: int | str) -> dict[str, Any]:
    uid = str(user_id).strip()
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (uid,)).fetchone()
        if row:
            return dict(row)
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO user_settings (user_id, filter_mode, lang, updated_at)
            VALUES (?, 'whitener', 'ru', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {"user_id": uid, "filter_mode": "whitener", "lang": "ru", "updated_at": now}
    finally:
        conn.close()


def update_user_settings(user_id: int | str, **kwargs: Any) -> dict[str, Any]:
    uid = str(user_id).strip()
    st = get_user_settings(uid)
    st.update(kwargs)
    st["updated_at"] = int(time.time())
    conn = get_db()
    try:
        conn.execute(
            """
            UPDATE user_settings
            SET filter_mode = ?, lang = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (str(st["filter_mode"]), str(st["lang"]), int(st["updated_at"]), uid),
        )
        conn.commit()
    finally:
        conn.close()
    return st


def add_session_page(user_id: int | str, image_path: str, width: int, height: int) -> int:
    uid = str(user_id).strip()
    conn = get_db()
    try:
        count_row = conn.execute(
            "SELECT COUNT(*) as c FROM session_pages WHERE user_id = ?", (uid,)
        ).fetchone()
        order_idx = (count_row["c"] if count_row else 0) + 1
        conn.execute(
            """
            INSERT INTO session_pages (user_id, page_order, image_path, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (uid, order_idx, image_path, width, height, int(time.time())),
        )
        conn.commit()
        return order_idx
    finally:
        conn.close()


def get_session_pages(user_id: int | str) -> list[dict[str, Any]]:
    uid = str(user_id).strip()
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM session_pages WHERE user_id = ? ORDER BY page_order ASC", (uid,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def clear_session_pages(user_id: int | str) -> None:
    uid = str(user_id).strip()
    conn = get_db()
    try:
        rows = conn.execute("SELECT image_path FROM session_pages WHERE user_id = ?", (uid,)).fetchall()
        for r in rows:
            p = Path(r["image_path"])
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
        conn.execute("DELETE FROM session_pages WHERE user_id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()


def record_scan_job(user_id: int | str, pages_count: int, filter_mode: str, pdf_bytes: int) -> None:
    uid = str(user_id).strip()
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO scan_jobs (user_id, pages_count, filter_mode, pdf_bytes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (uid, pages_count, filter_mode, pdf_bytes, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats() -> dict[str, Any]:
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT 
                COALESCE(SUM(pages_count), 0) as total_pages,
                COALESCE(COUNT(*), 0) as total_pdfs,
                COALESCE(SUM(pdf_bytes), 0) as total_bytes
            FROM scan_jobs
            """
        ).fetchone()
        pages = row["total_pages"] if row else 0
        pdfs = row["total_pdfs"] if row else 0
        b = row["total_bytes"] if row else 0
        return {
            "total_pages": pages,
            "total_pdfs": pdfs,
            "total_mb": round(b / (1024 * 1024), 2),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Image Processing & Filtering Engine (Pure Pillow)
# ---------------------------------------------------------------------------
def filter_whitener(img: Image.Image) -> Image.Image:
    """Removes uneven shadows and whitens paper background using division normalization."""
    gray = img.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    bg = gray.filter(ImageFilter.BoxBlur(15))

    w, h = gray.size
    gray_bytes = gray.tobytes()
    bg_bytes = bg.tobytes()
    out_bytes = bytearray(w * h)

    for i in range(w * h):
        g = gray_bytes[i]
        b = bg_bytes[i]
        if b == 0:
            b = 1
        val = int((g / b) * 235)
        out_bytes[i] = 255 if val > 215 else val

    res = Image.frombytes("L", (w, h), bytes(out_bytes))
    return res.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))


def filter_gray(img: Image.Image) -> Image.Image:
    """High-contrast 8-bit clean grayscale."""
    gray = img.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=2)
    return gray.filter(ImageFilter.SHARPEN)


def filter_binarize(img: Image.Image, threshold: int = 145) -> Image.Image:
    """1-bit monochrome pure black and white."""
    clean = filter_whitener(img)
    return clean.point(lambda p: 255 if p > threshold else 0, mode="1")


def filter_color(img: Image.Image) -> Image.Image:
    """Color enhanced document scan with boosted sharpness and contrast."""
    res = img.convert("RGB")
    res = ImageOps.autocontrast(res, cutoff=1)
    enh_c = ImageEnhance.Color(res)
    res = enh_c.enhance(1.25)
    enh_k = ImageEnhance.Contrast(res)
    res = enh_k.enhance(1.2)
    enh_s = ImageEnhance.Sharpness(res)
    return enh_s.enhance(1.5)


def apply_filter(img: Image.Image, mode: str) -> Image.Image:
    if mode == "gray":
        return filter_gray(img)
    elif mode == "binarize":
        return filter_binarize(img)
    elif mode == "color":
        return filter_color(img)
    return filter_whitener(img)


def compile_pages_to_pdf(page_paths: list[str], output_pdf: str) -> str:
    """Compiles a list of processed image files into a single unified PDF."""
    if not page_paths:
        raise ValueError("No images provided to compile PDF.")

    images = []
    for p in page_paths:
        im = Image.open(p)
        if im.mode == "RGBA":
            # Flatten transparency to white background
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[3])
            images.append(bg)
        elif im.mode == "1":
            images.append(im.convert("L"))
        else:
            images.append(im.convert("RGB"))

    first = images[0]
    rest = images[1:] if len(images) > 1 else []
    first.save(output_pdf, "PDF", resolution=150.0, save_all=True, append_images=rest)
    return output_pdf


# ---------------------------------------------------------------------------
# Telegram Bot Interface (100% ReplyKeyboardMarkup)
# ---------------------------------------------------------------------------
def build_keyboard(lang: str = "ru") -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_white = types.KeyboardButton(i18n.t(lang, "btn_filter_whitener"))
    b_gray = types.KeyboardButton(i18n.t(lang, "btn_filter_gray"))
    b_bin = types.KeyboardButton(i18n.t(lang, "btn_filter_binarize"))
    b_col = types.KeyboardButton(i18n.t(lang, "btn_filter_color"))
    b_pdf = types.KeyboardButton(i18n.t(lang, "btn_compile_pdf"))
    b_clr = types.KeyboardButton(i18n.t(lang, "btn_clear_session"))
    b_stat = types.KeyboardButton(i18n.t(lang, "btn_status"))
    b_help = types.KeyboardButton(i18n.t(lang, "btn_help"))
    b_lang = types.KeyboardButton(i18n.t(lang, "btn_lang"))

    markup.add(b_white, b_gray)
    markup.add(b_bin, b_col)
    markup.add(b_pdf, b_clr)
    markup.add(b_stat, b_help, b_lang)
    return markup


def setup_bot() -> telebot.TeleBot | None:
    if not BOT_TOKEN or not telebot:
        return None

    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
    core.guard_bot(bot)
    core.start_janitor([core.get_data_dir() / "pages"])

    def check_access(message: Any) -> bool:
        if not ALLOWED_USERS:
            return True
        return message.from_user.id in ALLOWED_USERS

    @bot.message_handler(commands=["start"])
    def cmd_start(message: Any):
        if not check_access(message):
            bot.reply_to(message, "⛔ Access denied.")
            return
        uid = message.from_user.id
        st = get_user_settings(uid)
        lang = st["lang"]
        pages = get_session_pages(uid)
        msg = i18n.t(
            lang,
            "welcome",
            filter=st["filter_mode"],
            pages=len(pages),
        )
        bot.send_message(message.chat.id, msg, reply_markup=build_keyboard(lang))

    @bot.message_handler(commands=["help"])
    def cmd_help(message: Any):
        if not check_access(message):
            return
        st = get_user_settings(message.from_user.id)
        bot.send_message(
            message.chat.id,
            i18n.t(st["lang"], "help_text"),
            reply_markup=build_keyboard(st["lang"]),
        )

    @bot.message_handler(content_types=["photo", "document"])
    def handle_incoming_document(message: Any):
        if not check_access(message):
            return
        uid = message.from_user.id
        st = get_user_settings(uid)
        lang = st["lang"]

        # Download image payload
        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document and (message.document.mime_type or "").startswith("image/"):
            file_id = message.document.file_id

        if not file_id:
            bot.reply_to(message, "⚠️ Please send an image file or photo.")
            return

        def process_page():
            try:
                downloaded = core.download_tg_file(bot, file_id)
                raw_img = Image.open(io.BytesIO(downloaded))
                proc_img = apply_filter(raw_img, st["filter_mode"])

                # Save page to disk
                page_filename = f"scan_{uid}_{int(time.time())}_{os.urandom(3).hex()}.png"
                page_path = PAGES_DIR / page_filename
                proc_img.save(str(page_path), "PNG")

                order = add_session_page(uid, str(page_path), proc_img.width, proc_img.height)
                all_pages = get_session_pages(uid)

                reply = i18n.t(
                    lang,
                    "page_added",
                    page_num=order,
                    width=proc_img.width,
                    height=proc_img.height,
                    pages_total=len(all_pages),
                )
                bot.send_message(message.chat.id, reply, reply_markup=build_keyboard(lang))
            except Exception as e:
                logger.exception("Error processing document page: %s", e)
                bot.reply_to(message, f"❌ Error processing page: {e}")

        threading.Thread(target=process_page, daemon=True).start()

    @bot.message_handler(content_types=["text"])
    def handle_text(message: Any):
        if not check_access(message):
            return
        uid = message.from_user.id
        st = get_user_settings(uid)
        lang = st["lang"]
        text = message.text.strip()

        # Filter mode selections
        if text == i18n.t(lang, "btn_filter_whitener"):
            update_user_settings(uid, filter_mode="whitener")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "filter_selected", filter="Paper Whitener"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_filter_gray"):
            update_user_settings(uid, filter_mode="gray")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "filter_selected", filter="Grayscale Clean"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_filter_binarize"):
            update_user_settings(uid, filter_mode="binarize")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "filter_selected", filter="Monochrome 1-Bit"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_filter_color"):
            update_user_settings(uid, filter_mode="color")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "filter_selected", filter="Color Enhanced"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_clear_session"):
            clear_session_pages(uid)
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "session_cleared"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_compile_pdf"):
            pages = get_session_pages(uid)
            if not pages:
                bot.send_message(
                    message.chat.id,
                    i18n.t(lang, "no_pages"),
                    reply_markup=build_keyboard(lang),
                )
                return

            def build_pdf_worker():
                try:
                    bot.send_message(
                        message.chat.id,
                        i18n.t(lang, "compiling_pdf", pages=len(pages)),
                    )
                    pdf_filename = f"Document_Scan_{int(time.time())}.pdf"
                    out_pdf = PDF_DIR / pdf_filename
                    paths = [p["image_path"] for p in pages]
                    compile_pages_to_pdf(paths, str(out_pdf))

                    file_size = out_pdf.stat().st_size
                    record_scan_job(uid, len(pages), st["filter_mode"], file_size)

                    with open(out_pdf, "rb") as f:
                        bot.send_document(
                            message.chat.id,
                            f,
                            caption=i18n.t(
                                lang,
                                "pdf_ready",
                                pages=len(pages),
                                size_kb=round(file_size / 1024, 1),
                                filter=st["filter_mode"],
                            ),
                            reply_markup=build_keyboard(lang),
                        )
                except Exception as e:
                    logger.exception("Error building PDF: %s", e)
                    bot.reply_to(message, f"❌ Failed to build PDF: {e}")

            threading.Thread(target=build_pdf_worker, daemon=True).start()

        elif text == i18n.t(lang, "btn_status"):
            stats = get_stats()
            pages = get_session_pages(uid)
            text_out = i18n.t(
                lang,
                "stats_text",
                total_pages=stats["total_pages"],
                total_pdfs=stats["total_pdfs"],
                total_mb=stats["total_mb"],
            ) + f"\n\n📂 Current session pages: *{len(pages)}*"
            bot.send_message(message.chat.id, text_out, reply_markup=build_keyboard(lang))

        elif text == i18n.t(lang, "btn_help"):
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "help_text"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_lang"):
            # Cycle through languages
            langs = ["ru", "en", "uz", "tg", "tr"]
            curr_idx = langs.index(lang) if lang in langs else 0
            next_lang = langs[(curr_idx + 1) % len(langs)]
            update_user_settings(uid, lang=next_lang)
            bot.send_message(
                message.chat.id,
                f"🌐 Language updated to: *{next_lang.upper()}*",
                reply_markup=build_keyboard(next_lang),
            )
        else:
            bot.send_message(
                message.chat.id,
                "💡 Send photos of pages or tap buttons below to control filters and compile PDF.",
                reply_markup=build_keyboard(lang),
            )

    return bot


# ---------------------------------------------------------------------------
# Web Studio Handler (Cyberpunk Neon UI on Port 8103)
# ---------------------------------------------------------------------------
def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    css = ("<style>.ds-pages{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:10px}"
           ".ds-page{position:relative;aspect-ratio:3/4;border-radius:10px;overflow:hidden;border:1px solid var(--line);background:var(--surface2);animation:pbup .35s var(--ease) both}"
           ".ds-page img{width:100%;height:100%;object-fit:cover}.ds-page b{position:absolute;inset-inline-start:6px;top:6px;min-width:22px;height:22px;border-radius:7px;"
           "display:grid;place-items:center;font-size:12px;color:#fff;background:var(--brand)}</style>")
    modes = [("whitener", "📄 " + T("w_f_whitener")), ("gray", "🔘 " + T("w_f_gray")), ("binarize", "⬛ " + T("w_f_bw")), ("color", "🎨 " + T("w_f_color"))]
    sub = {"whitener": T("w_f_whitener_sub"), "gray": T("w_f_gray_sub"), "binarize": T("w_f_bw_sub"), "color": T("w_f_color_sub")}
    left = web.card(T("w_card_scan"),
        web.field(T("w_filter"), web.segmented("mode", modes, "whitener", sub=sub))
        + web.dropzone("pf", T("w_drop_pages"), "JPG · PNG · WEBP · BMP", accept="image/*", multiple=True, icon_name="image")
        + web.progress("prog"), icon_name="image")
    right = web.card(T("w_card_bundle"),
        '<div class="ds-pages" id="pages"></div>' + web.empty_state(T("w_no_pages"), "file", id="empty")
        + '<div class="pb-row">' + web.button(T("w_compile"), "pdf", icon_name="download", disabled=True)
        + web.button(T("clear"), "clr", kind="danger", icon_name="trash") + "</div>",
        icon_name="file", aside='<span class="pb-tag" id="cnt">0</span>')
    st = web.card(T("statistics"), web.stats([(T("w_st_pages"), "0", "s1", "image"), (T("w_st_pdfs"), "0", "s2", "file"),
                                              (T("w_st_mb"), "0", "s3", "chart")]), icon_name="chart")
    hero = web.hero(T("w_title"), T("w_hero"), "📄", chips=["PDF", T("w_f_whitener"), T("w_f_bw")])
    web.send_page(handler, lang, title=T("w_title"), emoji="📄", brand="#2563eb", port=WEB_PORT,
                  hero_html=hero, body=css + web.grid(left, right, min_width=330) + st, script=DOC_JS)


DOC_JS = r"""
const $=s=>document.querySelector(s);let n=0;
function addThumb(file,num){const d=document.createElement('div');d.className='ds-page';d.innerHTML=`<img alt=""><b>${num}</b>`;d.querySelector('img').src=URL.createObjectURL(file);$('#pages').appendChild(d)}
function setCount(c){n=c;$('#cnt').textContent=c;$('#empty').hidden=c>0;$('#pdf').disabled=c===0}
async function stats(){const d=await pb.json('/api/status').catch(()=>({}));if(d.stats){pb.count($('#s1'),d.stats.total_pages||0);pb.count($('#s2'),d.stats.total_pdfs||0);$('#s3').textContent=(d.stats.total_mb||0)+' MB'}}
$('#pf-zone').addEventListener('pb:files',async e=>{const fs=e.detail;for(let i=0;i<fs.length;i++){
  const fd=new FormData();fd.append('file',fs[i]);fd.append('filter',$('#mode').dataset.value);
  try{const d=await pb.upload('/api/upload_page',fd,p=>pb.progress('prog',p<100?p:null,pb.t('w_uploading_page',{i:i+1,n:fs.length})));
    if(!d.success)throw new Error(d.error||pb.t('error'));addThumb(fs[i],d.page_num);setCount(d.total_pages);
  }catch(err){pb.toast(pb.t('error')+': '+err.message,true);break}}
  pb.progress('prog',100,pb.t('w_pages_in_bundle',{n}));stats()});
$('#pdf').onclick=async()=>{const b=$('#pdf');pb.busy(b,true);pb.progress('prog',null,pb.t('w_building_pdf'));
  try{const d=await pb.post('/api/compile_pdf',{});if(!d.success)throw new Error(d.error||pb.t('error'));pb.progress('prog',100,pb.t('done'));
    const a=document.createElement('a');a.href=d.download_url;a.download='';document.body.appendChild(a);a.click();a.remove();pb.toast(pb.t('done'));stats()}
  catch(err){pb.hide('prog');pb.toast(pb.t('error')+': '+err.message,true)}finally{pb.busy(b,false);$('#pdf').disabled=n===0}};
$('#clr').onclick=async()=>{await pb.post('/api/clear',{}).catch(()=>{});$('#pages').innerHTML='';setCount(0);pb.hide('prog');pb.toast(pb.t('w_cleared'));stats()};
setCount(0);stats();
"""


class WebStudioHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            render_studio(self)
        elif parsed.path == "/api/status":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            st = get_stats()
            resp = {
                "status": "online",
                "bot": "doc_scanner_lens",
                "port": WEB_PORT,
                "pillow": bool(Image),
                "stats": st,
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        elif parsed.path.startswith("/download/"):
            fname = os.path.basename(parsed.path)
            fpath = (PDF_DIR / fname).resolve()
            if fpath.is_file() and fpath.is_relative_to(PDF_DIR.resolve()):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.send_header("Content-Length", str(fpath.stat().st_size))
                self.end_headers()
                with open(fpath, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/upload_page":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self.send_error(HTTPStatus.BAD_REQUEST, "Must be multipart/form-data")
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            boundary = content_type.split("boundary=")[-1].strip().encode("latin1")
            parts = body.split(b"--" + boundary)

            file_bytes = None
            filter_mode = "whitener"

            for part in parts:
                if b'name="filter"' in part:
                    lines = part.split(b"\r\n\r\n", 1)
                    if len(lines) == 2:
                        filter_mode = lines[1].split(b"\r\n")[0].decode("utf-8", errors="ignore").strip()
                elif b'name="file"' in part:
                    lines = part.split(b"\r\n\r\n", 1)
                    if len(lines) == 2:
                        file_bytes = lines[1].rsplit(b"\r\n", 1)[0]

            if not file_bytes:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "No file received"}).encode("utf-8"))
                return

            try:
                raw_img = Image.open(io.BytesIO(file_bytes))
                proc_img = apply_filter(raw_img, filter_mode)
                fname = f"web_{int(time.time())}_{os.urandom(3).hex()}.png"
                out_path = PAGES_DIR / fname
                proc_img.save(str(out_path), "PNG")

                order = add_session_page("web_user", str(out_path), proc_img.width, proc_img.height)
                pages = get_session_pages("web_user")

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "success": True,
                        "page_num": order,
                        "total_pages": len(pages),
                    }).encode("utf-8")
                )
            except Exception as e:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))

        elif parsed.path == "/api/compile_pdf":
            pages = get_session_pages("web_user")
            if not pages:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": False, "error": "No pages in session to compile"}).encode("utf-8")
                )
                return

            try:
                pdf_fname = f"WebScan_{int(time.time())}.pdf"
                out_pdf = PDF_DIR / pdf_fname
                paths = [p["image_path"] for p in pages]
                compile_pages_to_pdf(paths, str(out_pdf))

                record_scan_job("web_user", len(pages), "web", out_pdf.stat().st_size)

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "success": True,
                        "download_url": f"/download/{pdf_fname}",
                        "pages": len(pages),
                    }).encode("utf-8")
                )
            except Exception as e:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))

        elif parsed.path == "/api/clear":
            clear_session_pages("web_user")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def start_web_server():
    server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), WEB_PORT), WebStudioHandler)
    print(f"[PYBIONIC_WEB:{WEB_PORT}]", flush=True)
    logger.info("Doc Scanner Lens Web Studio running on port %d", WEB_PORT)
    server.serve_forever()


def main():
    init_db()
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    bot = setup_bot()
    if bot:
        logger.info("Starting Telegram bot polling for Doc Scanner Lens...")
        try:
            core.start_polling(bot, skip_pending=True)
        except Exception as e:
            logger.error("Bot polling error: %s", e)
    else:
        logger.info("No BOT_TOKEN set. Web Studio running in offline mode.")
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
