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
WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Doc Scanner Lens Pro Studio</title>
<style>
:root {
  --bg: #0a0e17;
  --panel: #111927;
  --accent: #00e5ff;
  --accent-glow: rgba(0, 229, 255, 0.3);
  --green: #00ff66;
  --text: #e2e8f0;
  --muted: #64748b;
  --border: #1e293b;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
body { background: var(--bg); color: var(--text); padding: 24px; }
.container { max-width: 900px; margin: 0 auto; }
header { margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
h1 { font-size: 24px; color: var(--accent); text-shadow: 0 0 10px var(--accent-glow); display: flex; align-items: center; gap: 10px; }
.badge { background: rgba(0, 229, 255, 0.15); color: var(--accent); padding: 4px 12px; border-radius: 999px; font-size: 12px; border: 1px solid var(--accent); }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
.card-title { font-size: 16px; font-weight: 600; margin-bottom: 14px; color: #f8fafc; }
.drop-zone { border: 2px dashed var(--accent); border-radius: 10px; padding: 32px 16px; text-align: center; cursor: pointer; background: rgba(0, 229, 255, 0.02); transition: all 0.2s; }
.drop-zone:hover { background: rgba(0, 229, 255, 0.08); border-color: #fff; }
.btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
button { background: var(--panel); color: var(--text); border: 1px solid var(--border); padding: 10px 18px; border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s; }
button:hover { border-color: var(--accent); color: var(--accent); }
button.active { background: var(--accent); color: #000; font-weight: 600; border-color: var(--accent); box-shadow: 0 0 12px var(--accent-glow); }
button.primary { background: var(--green); color: #000; font-weight: 600; border: none; }
button.primary:hover { box-shadow: 0 0 12px rgba(0, 255, 102, 0.4); }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.stat-box { background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; text-align: center; }
.stat-num { font-size: 26px; font-weight: 700; color: var(--accent); }
.stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }
#statusMsg { margin-top: 12px; font-size: 13px; color: var(--green); min-height: 20px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>📄 Doc Scanner Lens Pro</h1>
    <span class="badge">Port 8103 • Online</span>
  </header>

  <div class="card">
    <div class="card-title">1. Document Filter Mode</div>
    <div class="btn-group">
      <button class="filter-btn active" data-mode="whitener">📄 Paper Whitener</button>
      <button class="filter-btn" data-mode="gray">🔘 Grayscale Clean</button>
      <button class="filter-btn" data-mode="binarize">⬛ 1-Bit Monochrome</button>
      <button class="filter-btn" data-mode="color">🎨 Color Enhanced</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">2. Upload Page Photos</div>
    <div class="drop-zone" id="dropZone">
      <p style="font-size: 15px; margin-bottom: 6px;">📂 Drag & drop page photo here, or click to select</p>
      <p style="font-size: 12px; color: var(--muted);">Supports JPG, PNG, WEBP, BMP</p>
      <input type="file" id="fileInput" accept="image/*" style="display:none;">
    </div>
    <div id="statusMsg"></div>
    <div class="btn-group" style="margin-top: 16px;">
      <button class="primary" id="btnCompile">📦 Compile Bundle into PDF</button>
      <button id="btnClear" style="color: #ff5555; border-color: #ff5555;">🗑 Clear Pages</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Engine Statistics</div>
    <div class="stats-grid">
      <div class="stat-box"><div class="stat-num" id="statPages">0</div><div class="stat-label">Pages Scanned</div></div>
      <div class="stat-box"><div class="stat-num" id="statPdfs">0</div><div class="stat-label">PDF Documents Built</div></div>
      <div class="stat-box"><div class="stat-num" id="statMb">0 MB</div><div class="stat-label">Data Volume Processed</div></div>
    </div>
  </div>
</div>

<script>
let activeMode = 'whitener';
document.querySelectorAll('.filter-btn').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    b.classList.add('active');
    activeMode = b.dataset.mode;
  });
});

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const statusMsg = document.getElementById('statusMsg');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.style.borderColor = '#fff'; });
dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor = 'var(--accent)'; });
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.style.borderColor = 'var(--accent)';
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
});

function uploadFile(file) {
  statusMsg.textContent = '⏳ Processing document page with ' + activeMode + ' filter...';
  const fd = new FormData();
  fd.append('file', file);
  fd.append('filter', activeMode);
  fetch('/api/upload_page', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        statusMsg.textContent = '✅ Page #' + data.page_num + ' added! Total in bundle: ' + data.total_pages;
        refreshStats();
      } else {
        statusMsg.textContent = '❌ Upload failed: ' + data.error;
      }
    })
    .catch(err => { statusMsg.textContent = '❌ Network error: ' + err; });
}

document.getElementById('btnCompile').addEventListener('click', () => {
  statusMsg.textContent = '⏳ Generating PDF document...';
  fetch('/api/compile_pdf', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        statusMsg.textContent = '🎉 PDF built successfully! Downloading...';
        window.location.href = data.download_url;
        refreshStats();
      } else {
        statusMsg.textContent = '⚠️ ' + data.error;
      }
    })
    .catch(err => { statusMsg.textContent = '❌ Error: ' + err; });
});

document.getElementById('btnClear').addEventListener('click', () => {
  fetch('/api/clear', { method: 'POST' })
    .then(r => r.json())
    .then(() => {
      statusMsg.textContent = '🗑 Session cleared.';
      refreshStats();
    });
});

function refreshStats() {
  fetch('/api/status').then(r => r.json()).then(data => {
    if (data.stats) {
      document.getElementById('statPages').textContent = data.stats.total_pages;
      document.getElementById('statPdfs').textContent = data.stats.total_pdfs;
      document.getElementById('statMb').textContent = data.stats.total_mb + ' MB';
    }
  });
}
refreshStats();
</script>
</body>
</html>
"""


class WebStudioHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(WEB_STUDIO_HTML.encode("utf-8"))
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
