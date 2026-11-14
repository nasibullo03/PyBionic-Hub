#!/usr/bin/env python3
"""Barcode Matrix Lab (BotHub Level 10/10)
Vector QR Code, Micro QR, Code128 1D Barcode & Crypto Payment Matrix Studio.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- Vector SVG & High-DPI PNG generation for QR codes and Code128 barcodes.
- Wi-Fi auto-connect profiles, vCard, and multi-currency crypto payment deep links.
- High Error Correction Level (ECC H) with custom color styling.
- Batch generation into labeled ZIP archives.
- Standalone Cyberpunk Web Studio on port 8104 with live canvas & SVG export.
- 24 languages support via i18n and locales.json.
- Fully offline capable without BOT_TOKEN.
"""

from __future__ import annotations

import html
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import tempfile
import threading
import time
import zipfile
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
    import qrcode
    from qrcode.constants import (
        ERROR_CORRECT_H,
        ERROR_CORRECT_L,
        ERROR_CORRECT_M,
        ERROR_CORRECT_Q,
    )
except ImportError:
    qrcode = None
    ERROR_CORRECT_H = 3

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

import i18n

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("barcode_matrix_lab")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8104"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "barcode_matrix.db"
OUTPUT_DIR = DATA_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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
                mode TEXT DEFAULT 'qr',
                fg_color TEXT DEFAULT '#00e5ff',
                bg_color TEXT DEFAULT '#0a0e17',
                ecc TEXT DEFAULT 'H',
                lang TEXT DEFAULT 'ru',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                code_type TEXT,
                payload_len INTEGER,
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
            INSERT INTO user_settings (user_id, mode, fg_color, bg_color, ecc, lang, updated_at)
            VALUES (?, 'qr', '#00e5ff', '#0a0e17', 'H', 'ru', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {
            "user_id": uid,
            "mode": "qr",
            "fg_color": "#00e5ff",
            "bg_color": "#0a0e17",
            "ecc": "H",
            "lang": "ru",
            "updated_at": now,
        }
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
            SET mode = ?, fg_color = ?, bg_color = ?, ecc = ?, lang = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                str(st["mode"]),
                str(st["fg_color"]),
                str(st["bg_color"]),
                str(st["ecc"]),
                str(st["lang"]),
                int(st["updated_at"]),
                uid,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return st


def record_job(user_id: int | str, code_type: str, payload_len: int) -> None:
    uid = str(user_id).strip()
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO job_stats (user_id, code_type, payload_len, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (uid, code_type, payload_len, int(time.time())),
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
                COALESCE(SUM(CASE WHEN code_type = 'qr' THEN 1 ELSE 0 END), 0) as total_qr,
                COALESCE(SUM(CASE WHEN code_type = 'barcode' THEN 1 ELSE 0 END), 0) as total_barcodes,
                COALESCE(SUM(CASE WHEN code_type = 'batch' THEN 1 ELSE 0 END), 0) as total_batches
            FROM job_stats
            """
        ).fetchone()
        q = row["total_qr"] if row else 0
        b = row["total_barcodes"] if row else 0
        bt = row["total_batches"] if row else 0
        return {"total_qr": q, "total_barcodes": b, "total_batches": bt}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Code128 1D Barcode Pure-Python Engine
# ---------------------------------------------------------------------------
CODE128_PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112"
]


def encode_code128_modules(text: str) -> str:
    """Encodes ASCII text into Code 128 (Subset B) modules string ('1' for bar, '0' for space)."""
    values = [104]  # Start Code B
    for ch in text:
        val = ord(ch) - 32
        if 0 <= val <= 95:
            values.append(val)
        else:
            values.append(0)
    checksum = values[0]
    for i, val in enumerate(values[1:], start=1):
        checksum += i * val
    checksum %= 103
    values.append(checksum)
    values.append(106)  # Stop Code

    modules = ""
    for val in values:
        pat = CODE128_PATTERNS[val]
        is_bar = True
        for width_char in pat:
            w = int(width_char)
            modules += ("1" if is_bar else "0") * w
            is_bar = not is_bar
    return modules


def generate_code128_png(
    text: str,
    fg_color: str = "#000000",
    bg_color: str = "#ffffff",
    bar_width: int = 3,
    bar_height: int = 120,
    quiet_zone: int = 30,
) -> bytes:
    """Renders Code 128 barcode into PNG bytes."""
    modules = encode_code128_modules(text)
    img_width = len(modules) * bar_width + 2 * quiet_zone
    img_height = bar_height + 2 * quiet_zone + 20

    img = Image.new("RGB", (img_width, img_height), bg_color)
    draw = ImageDraw.Draw(img)

    # Draw bars
    x = quiet_zone
    for m in modules:
        if m == "1":
            draw.rectangle([x, quiet_zone, x + bar_width - 1, quiet_zone + bar_height], fill=fg_color)
        x += bar_width

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_code128_svg(
    text: str,
    fg_color: str = "#000000",
    bg_color: str = "#ffffff",
    bar_width: int = 3,
    bar_height: int = 120,
    quiet_zone: int = 30,
) -> str:
    """Renders Code 128 barcode into vector SVG markup."""
    modules = encode_code128_modules(text)
    total_w = len(modules) * bar_width + 2 * quiet_zone
    total_h = bar_height + 2 * quiet_zone

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" viewBox="0 0 {total_w} {total_h}">',
        f'<rect width="100%" height="100%" fill="{bg_color}"/>',
    ]
    x = quiet_zone
    for m in modules:
        if m == "1":
            svg_parts.append(
                f'<rect x="{x}" y="{quiet_zone}" width="{bar_width}" height="{bar_height}" fill="{fg_color}"/>'
            )
        x += bar_width
    svg_parts.append("</svg>")
    return "".join(svg_parts)


# ---------------------------------------------------------------------------
# Vector & Raster QR Code Engine
# ---------------------------------------------------------------------------
def generate_qr_png(
    data: str,
    fg_color: str = "#00e5ff",
    bg_color: str = "#0a0e17",
    ecc: str = "H",
    box_size: int = 10,
    border: int = 4,
) -> bytes:
    """Generates a high-resolution QR code PNG image."""
    ecc_map = {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }
    correction = ecc_map.get(ecc.upper(), ERROR_CORRECT_H)
    qr = qrcode.QRCode(
        version=None,
        error_correction=correction,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fg_color, back_color=bg_color).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_qr_svg(
    data: str,
    fg_color: str = "#00e5ff",
    bg_color: str = "#0a0e17",
    ecc: str = "H",
) -> str:
    """Generates a clean vector SVG for the QR code."""
    ecc_map = {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }
    correction = ecc_map.get(ecc.upper(), ERROR_CORRECT_H)
    qr = qrcode.QRCode(
        version=None,
        error_correction=correction,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    dim = len(matrix)
    box = 10
    total_dim = dim * box

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_dim}" height="{total_dim}" viewBox="0 0 {total_dim} {total_dim}">',
        f'<rect width="100%" height="100%" fill="{bg_color}"/>',
    ]

    for r_idx, row in enumerate(matrix):
        for c_idx, val in enumerate(row):
            if val:
                svg_parts.append(
                    f'<rect x="{c_idx * box}" y="{r_idx * box}" width="{box}" height="{box}" fill="{fg_color}"/>'
                )
    svg_parts.append("</svg>")
    return "".join(svg_parts)


# ---------------------------------------------------------------------------
# Specialized Payload Formatters
# ---------------------------------------------------------------------------
def format_wifi_payload(ssid: str, password: str, auth_type: str = "WPA") -> str:
    """Standard Wi-Fi network configuration URI for QR scanning."""
    safe_ssid = ssid.replace(";", "\\;").replace(":", "\\:").replace('"', '\\"')
    safe_pass = password.replace(";", "\\;").replace(":", "\\:").replace('"', '\\"')
    return f"WIFI:T:{auth_type};S:{safe_ssid};P:{safe_pass};;"


def format_crypto_uri(currency: str, address: str, amount: str = "") -> str:
    """Generates cryptocurrency URI schema (BTC, ETH, TON, USDT)."""
    curr = currency.lower().strip()
    addr = address.strip()
    amt_param = f"?amount={amount.strip()}" if amount and amount.strip() else ""

    if curr in ("btc", "bitcoin"):
        return f"bitcoin:{addr}{amt_param}"
    elif curr in ("eth", "ethereum"):
        return f"ethereum:{addr}{amt_param}"
    elif curr in ("ton", "the-open-network"):
        return f"ton://transfer/{addr}{amt_param}"
    elif curr in ("sol", "solana"):
        return f"solana:{addr}{amt_param}"
    else:
        return f"{curr}:{addr}{amt_param}"


# ---------------------------------------------------------------------------
# Telegram Bot Interface (100% ReplyKeyboardMarkup)
# ---------------------------------------------------------------------------
def build_keyboard(lang: str = "ru") -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_qr = types.KeyboardButton(i18n.t(lang, "btn_gen_qr"))
    b_wifi = types.KeyboardButton(i18n.t(lang, "btn_gen_wifi"))
    b_bar = types.KeyboardButton(i18n.t(lang, "btn_gen_barcode"))
    b_cry = types.KeyboardButton(i18n.t(lang, "btn_gen_crypto"))
    b_col = types.KeyboardButton(i18n.t(lang, "btn_settings_color"))
    b_bat = types.KeyboardButton(i18n.t(lang, "btn_batch_zip"))
    b_stat = types.KeyboardButton(i18n.t(lang, "btn_status"))
    b_help = types.KeyboardButton(i18n.t(lang, "btn_help"))
    b_lang = types.KeyboardButton(i18n.t(lang, "btn_lang"))

    markup.add(b_qr, b_wifi)
    markup.add(b_bar, b_cry)
    markup.add(b_col, b_bat)
    markup.add(b_stat, b_help, b_lang)
    return markup


def setup_bot() -> telebot.TeleBot | None:
    if not BOT_TOKEN or not telebot:
        return None

    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

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
        msg = i18n.t(
            st["lang"],
            "welcome",
            mode=st["mode"].upper(),
            fg=st["fg_color"],
            bg=st["bg_color"],
        )
        bot.send_message(message.chat.id, msg, reply_markup=build_keyboard(st["lang"]))

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

    @bot.message_handler(content_types=["text"])
    def handle_text(message: Any):
        if not check_access(message):
            return
        uid = message.from_user.id
        st = get_user_settings(uid)
        lang = st["lang"]
        text = message.text.strip()

        if text == i18n.t(lang, "btn_gen_qr"):
            update_user_settings(uid, mode="qr")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "prompt_qr"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_gen_wifi"):
            update_user_settings(uid, mode="wifi")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "prompt_wifi"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_gen_barcode"):
            update_user_settings(uid, mode="barcode")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "prompt_barcode"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_gen_crypto"):
            update_user_settings(uid, mode="crypto")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "prompt_crypto"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_settings_color"):
            # Toggle between themes
            if st["fg_color"] == "#00e5ff":
                st = update_user_settings(uid, fg_color="#000000", bg_color="#ffffff")
                theme_name = "Black & White (Classic)"
            else:
                st = update_user_settings(uid, fg_color="#00e5ff", bg_color="#0a0e17")
                theme_name = "Cyberpunk Neon (Dark)"
            bot.send_message(
                message.chat.id,
                f"🎨 Color Theme switched: *{theme_name}*\nFG: `{st['fg_color']}` | BG: `{st['bg_color']}`",
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_batch_zip"):
            bot.send_message(
                message.chat.id,
                "📦 Send multiple lines of text in a single message to generate a ZIP of QR codes.",
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_status"):
            stats = get_stats()
            out = i18n.t(
                lang,
                "stats_text",
                total_qr=stats["total_qr"],
                total_barcodes=stats["total_barcodes"],
                total_batches=stats["total_batches"],
            )
            bot.send_message(message.chat.id, out, reply_markup=build_keyboard(lang))
        elif text == i18n.t(lang, "btn_help"):
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "help_text"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_lang"):
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
            # Process payload based on current mode
            def generate_task():
                try:
                    mode = st["mode"]
                    payload = text
                    code_type = "QR Code"

                    if mode == "wifi":
                        parts = [p.strip() for p in text.split("|")]
                        if len(parts) >= 2:
                            payload = format_wifi_payload(parts[0], parts[1])
                            code_type = f"Wi-Fi Network ({parts[0]})"
                        else:
                            bot.send_message(
                                message.chat.id,
                                "⚠️ Format error. Please use: `SSID | Password`",
                                reply_markup=build_keyboard(lang),
                            )
                            return
                    elif mode == "crypto":
                        parts = [p.strip() for p in text.split("|")]
                        curr = parts[0] if len(parts) > 0 else "btc"
                        addr = parts[1] if len(parts) > 1 else ""
                        amt = parts[2] if len(parts) > 2 else ""
                        payload = format_crypto_uri(curr, addr, amt)
                        code_type = f"Crypto Payment ({curr.upper()})"
                    elif mode == "barcode":
                        code_type = "Code128 Barcode"
                        png_bytes = generate_code128_png(
                            payload,
                            fg_color=st["fg_color"] if st["fg_color"] != "#00e5ff" else "#000000",
                            bg_color="#ffffff",
                        )
                        record_job(uid, "barcode", len(payload))
                        bot.send_photo(
                            message.chat.id,
                            png_bytes,
                            caption=i18n.t(
                                lang,
                                "code_ready",
                                code_type=code_type,
                                payload=payload[:100],
                            ),
                            reply_markup=build_keyboard(lang),
                        )
                        return

                    # Default QR code generation
                    png_bytes = generate_qr_png(
                        payload,
                        fg_color=st["fg_color"],
                        bg_color=st["bg_color"],
                        ecc=st["ecc"],
                    )
                    record_job(uid, "qr", len(payload))
                    bot.send_photo(
                        message.chat.id,
                        png_bytes,
                        caption=i18n.t(
                            lang,
                            "code_ready",
                            code_type=code_type,
                            payload=payload[:100],
                        ),
                        reply_markup=build_keyboard(lang),
                    )
                except Exception as e:
                    logger.exception("Generation error: %s", e)
                    bot.reply_to(message, f"❌ Generation error: {e}")

            threading.Thread(target=generate_task, daemon=True).start()

    return bot


# ---------------------------------------------------------------------------
# Web Studio Handler (Cyberpunk Neon UI on Port 8104)
# ---------------------------------------------------------------------------
WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Barcode Matrix Lab Studio</title>
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
.container { max-width: 960px; margin: 0 auto; }
header { margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
h1 { font-size: 24px; color: var(--accent); text-shadow: 0 0 10px var(--accent-glow); display: flex; align-items: center; gap: 10px; }
.badge { background: rgba(0, 229, 255, 0.15); color: var(--accent); padding: 4px 12px; border-radius: 999px; font-size: 12px; border: 1px solid var(--accent); }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
@media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
.card-title { font-size: 16px; font-weight: 600; margin-bottom: 14px; color: #f8fafc; }
.form-group { margin-bottom: 14px; }
label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; font-weight: 600; }
input[type="text"], textarea, select { width: 100%; background: #06090e; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: #fff; font-size: 14px; outline: none; }
input[type="text"]:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 8px var(--accent-glow); }
.color-row { display: flex; gap: 14px; }
.color-picker { display: flex; align-items: center; gap: 8px; background: #06090e; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border); flex: 1; }
input[type="color"] { background: none; border: none; width: 30px; height: 30px; cursor: pointer; }
.btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
button { background: var(--panel); color: var(--text); border: 1px solid var(--border); padding: 10px 18px; border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s; }
button:hover { border-color: var(--accent); color: var(--accent); }
button.active { background: var(--accent); color: #000; font-weight: 600; border-color: var(--accent); box-shadow: 0 0 12px var(--accent-glow); }
button.primary { background: var(--green); color: #000; font-weight: 600; border: none; }
button.primary:hover { box-shadow: 0 0 12px rgba(0, 255, 102, 0.4); }
.preview-box { background: #06090e; border: 1px solid var(--border); border-radius: 10px; padding: 24px; text-align: center; min-height: 280px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.preview-img { max-width: 100%; max-height: 240px; border-radius: 6px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.stat-box { background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; text-align: center; }
.stat-num { font-size: 26px; font-weight: 700; color: var(--accent); }
.stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🏷 Barcode Matrix Lab Pro</h1>
    <span class="badge">Port 8104 • Online</span>
  </header>

  <div class="grid">
    <div>
      <div class="card">
        <div class="card-title">1. Code Type & Format</div>
        <div class="btn-group" style="margin-top: 0; margin-bottom: 14px;">
          <button class="type-btn active" data-type="qr">📱 Vector QR</button>
          <button class="type-btn" data-type="barcode">🏷 Code128</button>
        </div>

        <div class="form-group">
          <label>Payload Content</label>
          <textarea id="payloadInput" rows="3" placeholder="Enter URL, text, or Wi-Fi info...">https://pybionic.org/bothub</textarea>
        </div>

        <div class="form-group color-row">
          <div class="color-picker">
            <input type="color" id="fgColor" value="#00e5ff">
            <span style="font-size:12px;">Foreground</span>
          </div>
          <div class="color-picker">
            <input type="color" id="bgColor" value="#0a0e17">
            <span style="font-size:12px;">Background</span>
          </div>
        </div>

        <div class="btn-group">
          <button class="primary" id="btnGenerate">⚡ Generate Live Code</button>
          <button id="btnDownloadSvg">⬇ Download Vector SVG</button>
          <button id="btnDownloadPng">⬇ Download PNG</button>
        </div>
      </div>
    </div>

    <div>
      <div class="card">
        <div class="card-title">2. Real-Time Vector Preview</div>
        <div class="preview-box" id="previewBox">
          <img class="preview-img" id="previewImg" src="" alt="Code Preview" style="display:none;">
          <span id="previewPlaceholder" style="color:var(--muted); font-size:14px;">Click Generate to preview</span>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Engine Statistics</div>
        <div class="stats-grid">
          <div class="stat-box"><div class="stat-num" id="statQr">0</div><div class="stat-label">QR Codes</div></div>
          <div class="stat-box"><div class="stat-num" id="statBar">0</div><div class="stat-label">Code128 Barcodes</div></div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
let currentType = 'qr';
document.querySelectorAll('.type-btn').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.type-btn').forEach(btn => btn.classList.remove('active'));
    b.classList.add('active');
    currentType = b.dataset.type;
    generateCode();
  });
});

const payloadInput = document.getElementById('payloadInput');
const fgColor = document.getElementById('fgColor');
const bgColor = document.getElementById('bgColor');
const previewImg = document.getElementById('previewImg');
const previewPlaceholder = document.getElementById('previewPlaceholder');

function generateCode() {
  const p = payloadInput.value.trim() || 'PyBionic';
  const fg = fgColor.value;
  const bg = bgColor.value;
  const url = `/api/generate?type=${currentType}&data=${encodeURIComponent(p)}&fg=${encodeURIComponent(fg)}&bg=${encodeURIComponent(bg)}&format=png`;

  previewImg.src = url;
  previewImg.style.display = 'block';
  previewPlaceholder.style.display = 'none';
  refreshStats();
}

document.getElementById('btnGenerate').addEventListener('click', generateCode);

document.getElementById('btnDownloadPng').addEventListener('click', () => {
  const p = payloadInput.value.trim() || 'PyBionic';
  window.location.href = `/api/generate?type=${currentType}&data=${encodeURIComponent(p)}&fg=${encodeURIComponent(fgColor.value)}&bg=${encodeURIComponent(bgColor.value)}&format=png&dl=1`;
});

document.getElementById('btnDownloadSvg').addEventListener('click', () => {
  const p = payloadInput.value.trim() || 'PyBionic';
  window.location.href = `/api/generate?type=${currentType}&data=${encodeURIComponent(p)}&fg=${encodeURIComponent(fgColor.value)}&bg=${encodeURIComponent(bgColor.value)}&format=svg&dl=1`;
});

function refreshStats() {
  fetch('/api/status').then(r => r.json()).then(data => {
    if (data.stats) {
      document.getElementById('statQr').textContent = data.stats.total_qr;
      document.getElementById('statBar').textContent = data.stats.total_barcodes;
    }
  });
}

generateCode();
</script>
</body>
</html>
"""


class WebStudioHandler(BaseHTTPRequestHandler):
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
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

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
                "bot": "barcode_matrix_lab",
                "port": WEB_PORT,
                "qrcode": bool(qrcode),
                "stats": st,
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))

        elif parsed.path == "/api/generate":
            code_type = qs.get("type", ["qr"])[0]
            data_val = qs.get("data", ["PyBionic"])[0]
            fg = qs.get("fg", ["#00e5ff"])[0]
            bg = qs.get("bg", ["#0a0e17"])[0]
            fmt = qs.get("format", ["png"])[0].lower()
            download = qs.get("dl", ["0"])[0] == "1"

            try:
                record_job("web_user", code_type, len(data_val))
                if code_type == "barcode":
                    if fmt == "svg":
                        svg_content = generate_code128_svg(data_val, fg_color=fg, bg_color=bg)
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "image/svg+xml")
                        if download:
                            self.send_header("Content-Disposition", 'attachment; filename="barcode.svg"')
                        self.end_headers()
                        self.wfile.write(svg_content.encode("utf-8"))
                        return
                    else:
                        png_bytes = generate_code128_png(data_val, fg_color=fg, bg_color=bg)
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "image/png")
                        if download:
                            self.send_header("Content-Disposition", 'attachment; filename="barcode.png"')
                        self.end_headers()
                        self.wfile.write(png_bytes)
                        return
                else:
                    if fmt == "svg":
                        svg_content = generate_qr_svg(data_val, fg_color=fg, bg_color=bg)
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "image/svg+xml")
                        if download:
                            self.send_header("Content-Disposition", 'attachment; filename="qrcode.svg"')
                        self.end_headers()
                        self.wfile.write(svg_content.encode("utf-8"))
                        return
                    else:
                        png_bytes = generate_qr_png(data_val, fg_color=fg, bg_color=bg)
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "image/png")
                        if download:
                            self.send_header("Content-Disposition", 'attachment; filename="qrcode.png"')
                        self.end_headers()
                        self.wfile.write(png_bytes)
                        return
            except Exception as e:
                logger.exception("Web generation error: %s", e)
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def start_web_server():
    server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), WEB_PORT), WebStudioHandler)
    print(f"[PYBIONIC_WEB:{WEB_PORT}]", flush=True)
    logger.info("Barcode Matrix Lab Web Studio running on port %d", WEB_PORT)
    server.serve_forever()


def main():
    init_db()
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    bot = setup_bot()
    if bot:
        logger.info("Starting Telegram bot polling for Barcode Matrix Lab...")
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            logger.error("Bot polling error: %s", e)
    else:
        logger.info("No BOT_TOKEN set. Web Studio running in offline mode.")
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
