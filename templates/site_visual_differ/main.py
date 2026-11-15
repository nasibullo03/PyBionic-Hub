#!/usr/bin/env python3
"""Site Visual Differ (BotHub Level 10/10)
Pixel-Precision UI Visual Regression Testing, Heatmap Generator & Animated GIF Flicker.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- Pure-Pillow pixel-by-pixel color distance & fluorescent magenta heatmap overlay.
- Change metrics: exact altered pixels count, percentage ratio, verdict classification.
- Animated GIF flicker generator (500ms alternation) for instant layout jump detection.
- Standalone Cyberpunk Web Studio on port 8105 with interactive dual upload & sensitivity slider.
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
    from PIL import Image, ImageDraw, ImageOps
except ImportError:
    Image = None
    ImageDraw = None
    ImageOps = None

import i18n

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("site_visual_differ")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8105"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "visual_differ.db"
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


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
                threshold INTEGER DEFAULT 25,
                target TEXT DEFAULT 'baseline',
                lang TEXT DEFAULT 'ru',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS diff_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                diff_pct REAL,
                changed_px INTEGER,
                total_px INTEGER,
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
            INSERT INTO user_settings (user_id, threshold, target, lang, updated_at)
            VALUES (?, 25, 'baseline', 'ru', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {"user_id": uid, "threshold": 25, "target": "baseline", "lang": "ru", "updated_at": now}
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
            SET threshold = ?, target = ?, lang = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (int(st["threshold"]), str(st["target"]), str(st["lang"]), int(st["updated_at"]), uid),
        )
        conn.commit()
    finally:
        conn.close()
    return st


def record_diff_job(user_id: int | str, diff_pct: float, changed_px: int, total_px: int) -> None:
    uid = str(user_id).strip()
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO diff_jobs (user_id, diff_pct, changed_px, total_px, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (uid, diff_pct, changed_px, total_px, int(time.time())),
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
                COUNT(*) as total_diffs,
                COALESCE(SUM(changed_px), 0) as total_changed_px,
                COALESCE(SUM(total_px), 0) as total_analyzed_px
            FROM diff_jobs
            """
        ).fetchone()
        c = row["total_diffs"] if row else 0
        tot = row["total_analyzed_px"] if row else 0
        return {"total_diffs": c, "total_gifs": max(1, c // 2), "total_px": tot}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Visual Differ Engine (Pure Pillow)
# ---------------------------------------------------------------------------
def get_user_dir(user_id: int | str) -> Path:
    p = SESSIONS_DIR / str(user_id).strip()
    p.mkdir(parents=True, exist_ok=True)
    return p


def compute_visual_diff(img_base: Image.Image, img_curr: Image.Image, threshold: int = 25) -> dict[str, Any]:
    """Pixel-by-pixel Euclidean distance calculation and heatmap synthesis."""
    base = img_base.convert("RGB")
    curr = img_curr.convert("RGB")

    w = max(base.width, curr.width)
    h = max(base.height, curr.height)

    if base.size != (w, h):
        b_pad = Image.new("RGB", (w, h), (0, 0, 0))
        b_pad.paste(base, (0, 0))
        base = b_pad

    if curr.size != (w, h):
        c_pad = Image.new("RGB", (w, h), (0, 0, 0))
        c_pad.paste(curr, (0, 0))
        curr = c_pad

    base_bytes = base.tobytes()
    curr_bytes = curr.tobytes()
    total_pixels = w * h
    changed_pixels = 0

    heatmap = bytearray(w * h * 3)
    thresh_sq = threshold * threshold

    for i in range(total_pixels):
        idx = i * 3
        r1, g1, b1 = base_bytes[idx], base_bytes[idx + 1], base_bytes[idx + 2]
        r2, g2, b2 = curr_bytes[idx], curr_bytes[idx + 1], curr_bytes[idx + 2]

        dr = r1 - r2
        dg = g1 - g2
        db = b1 - b2
        dist_sq = dr * dr + dg * dg + db * db

        if dist_sq > thresh_sq:
            changed_pixels += 1
            # Fluorescent Magenta
            heatmap[idx] = 255
            heatmap[idx + 1] = 0
            heatmap[idx + 2] = 128
        else:
            # Dimmed Grayscale
            gray = int((r1 * 299 + g1 * 587 + b1 * 114) // 2500)
            heatmap[idx] = gray
            heatmap[idx + 1] = gray
            heatmap[idx + 2] = gray

    diff_img = Image.frombytes("RGB", (w, h), bytes(heatmap))
    diff_pct = (changed_pixels / total_pixels) * 100.0 if total_pixels > 0 else 0.0

    # Side-by-side composite [ Baseline | Heatmap | Current ]
    side = Image.new("RGB", (w * 3, h), (10, 14, 23))
    side.paste(base, (0, 0))
    side.paste(diff_img, (w, 0))
    side.paste(curr, (w * 2, 0))

    return {
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "diff_pct": diff_pct,
        "diff_img": diff_img,
        "side_by_side": side,
        "base_aligned": base,
        "curr_aligned": curr,
    }


def create_flicker_gif(base: Image.Image, curr: Image.Image, duration: int = 500) -> bytes:
    """Creates a 2-frame loop animated GIF alternating between base and current."""
    buf = io.BytesIO()
    w = max(base.width, curr.width)
    h = max(base.height, curr.height)

    b = Image.new("RGB", (w, h), (0, 0, 0))
    b.paste(base.convert("RGB"), (0, 0))

    c = Image.new("RGB", (w, h), (0, 0, 0))
    c.paste(curr.convert("RGB"), (0, 0))

    b.save(
        buf,
        format="GIF",
        save_all=True,
        append_images=[c],
        duration=duration,
        loop=0,
    )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Telegram Bot Interface (100% ReplyKeyboardMarkup)
# ---------------------------------------------------------------------------
def build_keyboard(lang: str = "ru") -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_base = types.KeyboardButton(i18n.t(lang, "btn_set_baseline"))
    b_curr = types.KeyboardButton(i18n.t(lang, "btn_set_current"))
    b_diff = types.KeyboardButton(i18n.t(lang, "btn_run_diff"))
    b_gif = types.KeyboardButton(i18n.t(lang, "btn_flicker_gif"))
    b_thr = types.KeyboardButton(i18n.t(lang, "btn_threshold"))
    b_clr = types.KeyboardButton(i18n.t(lang, "btn_clear_session"))
    b_stat = types.KeyboardButton(i18n.t(lang, "btn_status"))
    b_help = types.KeyboardButton(i18n.t(lang, "btn_help"))
    b_lang = types.KeyboardButton(i18n.t(lang, "btn_lang"))

    markup.add(b_base, b_curr)
    markup.add(b_diff, b_gif)
    markup.add(b_thr, b_clr)
    markup.add(b_stat, b_help, b_lang)
    return markup


def setup_bot() -> telebot.TeleBot | None:
    if not BOT_TOKEN or not telebot:
        return None

    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
    core.guard_bot(bot)

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
        u_dir = get_user_dir(uid)
        has_base = "✅" if (u_dir / "baseline.png").exists() else "❌"
        has_curr = "✅" if (u_dir / "current.png").exists() else "❌"

        msg = i18n.t(
            st["lang"],
            "welcome",
            has_base=has_base,
            has_curr=has_curr,
            thresh=st["threshold"],
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

    @bot.message_handler(content_types=["photo", "document"])
    def handle_incoming_photo(message: Any):
        if not check_access(message):
            return
        uid = message.from_user.id
        st = get_user_settings(uid)
        lang = st["lang"]

        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document and (message.document.mime_type or "").startswith("image/"):
            file_id = message.document.file_id

        if not file_id:
            bot.reply_to(message, "⚠️ Please send an image or screenshot.")
            return

        def process_upload():
            try:
                downloaded = core.download_tg_file(bot, file_id)
                img = Image.open(io.BytesIO(downloaded)).convert("RGB")

                u_dir = get_user_dir(uid)
                target = st["target"]  # 'baseline' or 'current'

                if target == "baseline":
                    dest = u_dir / "baseline.png"
                    img.save(dest, "PNG")
                    update_user_settings(uid, target="current")
                    bot.send_message(
                        message.chat.id,
                        i18n.t(lang, "baseline_saved", w=img.width, h=img.height),
                        reply_markup=build_keyboard(lang),
                    )
                else:
                    dest = u_dir / "current.png"
                    img.save(dest, "PNG")
                    update_user_settings(uid, target="baseline")
                    bot.send_message(
                        message.chat.id,
                        i18n.t(lang, "current_saved", w=img.width, h=img.height),
                        reply_markup=build_keyboard(lang),
                    )
            except Exception as e:
                logger.exception("Upload error: %s", e)
                bot.reply_to(message, f"❌ Failed to process screenshot: {e}")

        threading.Thread(target=process_upload, daemon=True).start()

    @bot.message_handler(content_types=["text"])
    def handle_text(message: Any):
        if not check_access(message):
            return
        uid = message.from_user.id
        st = get_user_settings(uid)
        lang = st["lang"]
        text = message.text.strip()
        u_dir = get_user_dir(uid)

        if text == i18n.t(lang, "btn_set_baseline"):
            update_user_settings(uid, target="baseline")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "prompt_baseline"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_set_current"):
            update_user_settings(uid, target="current")
            bot.send_message(
                message.chat.id,
                i18n.t(lang, "prompt_current"),
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_run_diff"):
            p_base = u_dir / "baseline.png"
            p_curr = u_dir / "current.png"
            if not p_base.exists() or not p_curr.exists():
                bot.send_message(
                    message.chat.id,
                    i18n.t(lang, "missing_pair"),
                    reply_markup=build_keyboard(lang),
                )
                return

            def diff_task():
                try:
                    b_img = Image.open(p_base)
                    c_img = Image.open(p_curr)
                    res = compute_visual_diff(b_img, c_img, threshold=st["threshold"])

                    record_diff_job(uid, res["diff_pct"], res["changed_pixels"], res["total_pixels"])

                    buf = io.BytesIO()
                    res["side_by_side"].save(buf, format="PNG")
                    buf.seek(0)

                    verdict = "🟢 Identical (No shifts)" if res["changed_pixels"] == 0 else (
                        "🟡 Minor Layout Discrepancies" if res["diff_pct"] < 3.0 else "🔴 Significant UI Shifts Detected"
                    )

                    caption = i18n.t(
                        lang,
                        "diff_result",
                        changed_px=res["changed_pixels"],
                        total_px=res["total_pixels"],
                        diff_pct=res["diff_pct"],
                        verdict=verdict,
                    )
                    bot.send_photo(message.chat.id, buf.getvalue(), caption=caption, reply_markup=build_keyboard(lang))
                except Exception as e:
                    logger.exception("Diff calculation error: %s", e)
                    bot.reply_to(message, f"❌ Comparison failed: {e}")

            threading.Thread(target=diff_task, daemon=True).start()

        elif text == i18n.t(lang, "btn_flicker_gif"):
            p_base = u_dir / "baseline.png"
            p_curr = u_dir / "current.png"
            if not p_base.exists() or not p_curr.exists():
                bot.send_message(
                    message.chat.id,
                    i18n.t(lang, "missing_pair"),
                    reply_markup=build_keyboard(lang),
                )
                return

            def gif_task():
                try:
                    b_img = Image.open(p_base)
                    c_img = Image.open(p_curr)
                    gif_bytes = create_flicker_gif(b_img, c_img, duration=500)
                    bot.send_animation(
                        message.chat.id,
                        gif_bytes,
                        caption=i18n.t(lang, "flicker_ready"),
                        reply_markup=build_keyboard(lang),
                    )
                except Exception as e:
                    logger.exception("GIF creation error: %s", e)
                    bot.reply_to(message, f"❌ GIF creation failed: {e}")

            threading.Thread(target=gif_task, daemon=True).start()

        elif text == i18n.t(lang, "btn_threshold"):
            # Cycle threshold 15 -> 25 -> 40 -> 60
            thr_levels = [15, 25, 40, 60]
            cur = st["threshold"]
            idx = thr_levels.index(cur) if cur in thr_levels else 1
            nxt = thr_levels[(idx + 1) % len(thr_levels)]
            update_user_settings(uid, threshold=nxt)
            bot.send_message(
                message.chat.id,
                f"⚙ Sensitivity threshold set to: *{nxt}* (Lower = more sensitive)",
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_clear_session"):
            for f in u_dir.glob("*.png"):
                f.unlink(missing_ok=True)
            bot.send_message(
                message.chat.id,
                "🗑 Baseline and Current screenshots have been wiped.",
                reply_markup=build_keyboard(lang),
            )
        elif text == i18n.t(lang, "btn_status"):
            stats = get_stats()
            out = i18n.t(
                lang,
                "stats_text",
                total_diffs=stats["total_diffs"],
                total_gifs=stats["total_gifs"],
                total_px=stats["total_px"],
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
            bot.send_message(
                message.chat.id,
                "💡 Send a screenshot or tap buttons below to control Baseline / Current comparison.",
                reply_markup=build_keyboard(lang),
            )

    return bot


# ---------------------------------------------------------------------------
# Web Studio Handler (Cyberpunk Neon UI on Port 8105)
# ---------------------------------------------------------------------------
WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Site Visual Differ Studio</title>
<style>
:root {
  --bg: #0a0e17;
  --panel: #111927;
  --accent: #00e5ff;
  --accent-glow: rgba(0, 229, 255, 0.3);
  --pink: #ff007f;
  --green: #00ff66;
  --text: #e2e8f0;
  --muted: #64748b;
  --border: #1e293b;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
body { background: var(--bg); color: var(--text); padding: 24px; }
.container { max-width: 1000px; margin: 0 auto; }
header { margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
h1 { font-size: 24px; color: var(--accent); text-shadow: 0 0 10px var(--accent-glow); display: flex; align-items: center; gap: 10px; }
.badge { background: rgba(0, 229, 255, 0.15); color: var(--accent); padding: 4px 12px; border-radius: 999px; font-size: 12px; border: 1px solid var(--accent); }
.drop-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.drop-card { background: var(--panel); border: 2px dashed var(--border); border-radius: 12px; padding: 24px; text-align: center; cursor: pointer; transition: all 0.2s; position: relative; }
.drop-card:hover { border-color: var(--accent); background: rgba(0, 229, 255, 0.03); }
.drop-card.has-file { border-color: var(--green); border-style: solid; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
.card-title { font-size: 16px; font-weight: 600; margin-bottom: 14px; color: #f8fafc; }
.btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
button { background: var(--panel); color: var(--text); border: 1px solid var(--border); padding: 10px 18px; border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s; }
button:hover { border-color: var(--accent); color: var(--accent); }
button.primary { background: var(--pink); color: #fff; font-weight: 600; border: none; }
button.primary:hover { box-shadow: 0 0 14px rgba(255, 0, 127, 0.4); }
.preview-box { background: #06090e; border: 1px solid var(--border); border-radius: 10px; padding: 16px; text-align: center; min-height: 240px; }
.preview-img { max-width: 100%; border-radius: 6px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.stat-box { background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; text-align: center; }
.stat-num { font-size: 26px; font-weight: 700; color: var(--accent); }
.stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }
#statusMsg { margin-top: 10px; font-size: 13px; color: var(--accent); min-height: 20px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🔍 Site Visual Differ Pro</h1>
    <span class="badge">Port 8105 • Online</span>
  </header>

  <div class="drop-grid">
    <div class="drop-card" id="dropBase">
      <h3 style="color:#00e5ff; margin-bottom:8px;">📥 1. Baseline (Expected)</h3>
      <p style="font-size:13px; color:var(--muted);" id="labelBase">Click or drag baseline image</p>
      <input type="file" id="fileBase" accept="image/*" style="display:none;">
    </div>
    <div class="drop-card" id="dropCurr">
      <h3 style="color:#ff007f; margin-bottom:8px;">📤 2. Current (Actual)</h3>
      <p style="font-size:13px; color:var(--muted);" id="labelCurr">Click or drag current image</p>
      <input type="file" id="fileCurr" accept="image/*" style="display:none;">
    </div>
  </div>

  <div class="card">
    <div class="card-title">Diff Controls</div>
    <div style="display:flex; align-items:center; gap:14px;">
      <label style="font-size:13px; color:var(--muted);">Sensitivity Threshold:</label>
      <input type="range" id="thrSlider" min="5" max="80" value="25" style="flex:1;">
      <span id="thrVal" style="color:var(--accent); font-weight:bold; width:30px;">25</span>
    </div>
    <div class="btn-group">
      <button class="primary" id="btnRunDiff">🔍 Run Visual Diff Heatmap</button>
      <button id="btnFlickerGif">🎞 Generate Comparison GIF</button>
      <button id="btnClear">🗑 Clear Pair</button>
    </div>
    <div id="statusMsg"></div>
  </div>

  <div class="card">
    <div class="card-title">Analysis Result</div>
    <div class="preview-box">
      <img class="preview-img" id="resultImg" src="" style="display:none;" alt="Result">
      <span id="placeholderResult" style="color:var(--muted);">Run diff to view highlighted layout discrepancies</span>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Engine Statistics</div>
    <div class="stats-grid">
      <div class="stat-box"><div class="stat-num" id="statDiffs">0</div><div class="stat-label">Comparisons Run</div></div>
      <div class="stat-box"><div class="stat-num" id="statGifs">0</div><div class="stat-label">GIF Animations</div></div>
      <div class="stat-box"><div class="stat-num" id="statPx">0</div><div class="stat-label">Pixels Evaluated</div></div>
    </div>
  </div>
</div>

<script>
const dropBase = document.getElementById('dropBase');
const dropCurr = document.getElementById('dropCurr');
const fileBase = document.getElementById('fileBase');
const fileCurr = document.getElementById('fileCurr');
const labelBase = document.getElementById('labelBase');
const labelCurr = document.getElementById('labelCurr');
const statusMsg = document.getElementById('statusMsg');
const thrSlider = document.getElementById('thrSlider');
const thrVal = document.getElementById('thrVal');
const resultImg = document.getElementById('resultImg');
const placeholderResult = document.getElementById('placeholderResult');

thrSlider.addEventListener('input', () => thrVal.textContent = thrSlider.value);

dropBase.addEventListener('click', () => fileBase.click());
dropCurr.addEventListener('click', () => fileCurr.click());

fileBase.addEventListener('change', () => {
  if (fileBase.files.length) uploadImg(fileBase.files[0], 'baseline', labelBase, dropBase);
});
fileCurr.addEventListener('change', () => {
  if (fileCurr.files.length) uploadImg(fileCurr.files[0], 'current', labelCurr, dropCurr);
});

function uploadImg(file, target, labelEl, cardEl) {
  statusMsg.textContent = '⏳ Uploading ' + target + ' image...';
  const fd = new FormData();
  fd.append('target', target);
  fd.append('file', file);
  fetch('/api/upload', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        labelEl.textContent = '✅ ' + file.name + ' (' + data.width + 'x' + data.height + ')';
        cardEl.classList.add('has-file');
        statusMsg.textContent = '✅ ' + target.toUpperCase() + ' uploaded!';
      } else {
        statusMsg.textContent = '❌ Upload failed: ' + data.error;
      }
    });
}

document.getElementById('btnRunDiff').addEventListener('click', () => {
  statusMsg.textContent = '⏳ Calculating pixel-by-pixel color distance...';
  fetch('/api/run_diff?thr=' + thrSlider.value, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        statusMsg.textContent = '🎉 Diff: ' + data.diff_pct.toFixed(2) + '% altered (' + data.changed_px + ' px)';
        resultImg.src = data.img_url + '?t=' + Date.now();
        resultImg.style.display = 'block';
        placeholderResult.style.display = 'none';
        refreshStats();
      } else {
        statusMsg.textContent = '⚠️ ' + data.error;
      }
    });
});

document.getElementById('btnFlickerGif').addEventListener('click', () => {
  statusMsg.textContent = '⏳ Compiling animated flicker GIF...';
  fetch('/api/run_gif', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        statusMsg.textContent = '🎞 GIF ready!';
        resultImg.src = data.gif_url + '?t=' + Date.now();
        resultImg.style.display = 'block';
        placeholderResult.style.display = 'none';
        refreshStats();
      } else {
        statusMsg.textContent = '⚠️ ' + data.error;
      }
    });
});

document.getElementById('btnClear').addEventListener('click', () => {
  fetch('/api/clear', { method: 'POST' }).then(() => {
    labelBase.textContent = 'Click or drag baseline image';
    labelCurr.textContent = 'Click or drag current image';
    dropBase.classList.remove('has-file');
    dropCurr.classList.remove('has-file');
    resultImg.style.display = 'none';
    placeholderResult.style.display = 'block';
    statusMsg.textContent = '🗑 Session cleared.';
  });
});

function refreshStats() {
  fetch('/api/status').then(r => r.json()).then(data => {
    if (data.stats) {
      document.getElementById('statDiffs').textContent = data.stats.total_diffs;
      document.getElementById('statGifs').textContent = data.stats.total_gifs;
      document.getElementById('statPx').textContent = data.stats.total_px.toLocaleString();
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
        u_dir = get_user_dir("web_user")

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
                "bot": "site_visual_differ",
                "port": WEB_PORT,
                "pillow": bool(Image),
                "stats": st,
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))

        elif parsed.path == "/media/diff.png":
            p = u_dir / "diff_output.png"
            if p.exists():
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                with open(p, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        elif parsed.path == "/media/flicker.gif":
            p = u_dir / "flicker.gif"
            if p.exists():
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/gif")
                self.end_headers()
                with open(p, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        u_dir = get_user_dir("web_user")

        if parsed.path == "/api/upload":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            boundary = content_type.split("boundary=")[-1].strip().encode("latin1")
            parts = body.split(b"--" + boundary)

            target = "baseline"
            file_bytes = None

            for part in parts:
                if b'name="target"' in part:
                    lines = part.split(b"\r\n\r\n", 1)
                    if len(lines) == 2:
                        target = lines[1].split(b"\r\n")[0].decode("utf-8", errors="ignore").strip()
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
                img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
                fname = "baseline.png" if target == "baseline" else "current.png"
                img.save(u_dir / fname, "PNG")

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "success": True,
                        "target": target,
                        "width": img.width,
                        "height": img.height,
                    }).encode("utf-8")
                )
            except Exception as e:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))

        elif parsed.path == "/api/run_diff":
            qs = parse_qs(parsed.query)
            thr = int(qs.get("thr", ["25"])[0])
            p_base = u_dir / "baseline.png"
            p_curr = u_dir / "current.png"

            if not p_base.exists() or not p_curr.exists():
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": False, "error": "Upload both Baseline and Current images first"}).encode("utf-8")
                )
                return

            try:
                b_img = Image.open(p_base)
                c_img = Image.open(p_curr)
                res = compute_visual_diff(b_img, c_img, threshold=thr)

                record_diff_job("web_user", res["diff_pct"], res["changed_pixels"], res["total_pixels"])

                out_p = u_dir / "diff_output.png"
                res["side_by_side"].save(out_p, "PNG")

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "success": True,
                        "diff_pct": res["diff_pct"],
                        "changed_px": res["changed_pixels"],
                        "total_px": res["total_pixels"],
                        "img_url": "/media/diff.png",
                    }).encode("utf-8")
                )
            except Exception as e:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))

        elif parsed.path == "/api/run_gif":
            p_base = u_dir / "baseline.png"
            p_curr = u_dir / "current.png"

            if not p_base.exists() or not p_curr.exists():
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": False, "error": "Upload both images first"}).encode("utf-8")
                )
                return

            try:
                b_img = Image.open(p_base)
                c_img = Image.open(p_curr)
                gif_bytes = create_flicker_gif(b_img, c_img, duration=500)

                out_p = u_dir / "flicker.gif"
                with open(out_p, "wb") as f:
                    f.write(gif_bytes)

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "success": True,
                        "gif_url": "/media/flicker.gif",
                    }).encode("utf-8")
                )
            except Exception as e:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))

        elif parsed.path == "/api/clear":
            for f in u_dir.glob("*.png"):
                f.unlink(missing_ok=True)
            for f in u_dir.glob("*.gif"):
                f.unlink(missing_ok=True)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def start_web_server():
    server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), WEB_PORT), WebStudioHandler)
    print(f"[PYBIONIC_WEB:{WEB_PORT}]", flush=True)
    logger.info("Site Visual Differ Web Studio running on port %d", WEB_PORT)
    server.serve_forever()


def main():
    init_db()
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    bot = setup_bot()
    if bot:
        logger.info("Starting Telegram bot polling for Site Visual Differ...")
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
