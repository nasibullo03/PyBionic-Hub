#!/usr/bin/env python3
"""Ghost Lens Sanitizer (BotHub Level 10/10)
Deep EXIF & metadata scrubber, GPS wiper, thumbnail purger, and stego canary checker.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- Deep EXIF, XMP, IPTC, ICC profile, and camera serial purging.
- Geolocation GPS coordinates extraction & complete wiping.
- Hidden thumbnail cache stripper (prevents uncropped shot leaks).
- Lossless video container atom sanitizer (MP4/MOV udta, meta, location).
- Steganographic canary analyzer (Shannon entropy of LSB bitplane).
- Standalone Cyberpunk Web Studio on port 8100 with interactive EXIF table & stego gauge.
- 24 languages support via i18n and locales.json.
"""

from __future__ import annotations

import html
import io
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import tempfile
import threading
import time
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class ThreadedStudioServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from PIL import Image, ExifTags
    HAVE_PILLOW = True
except ImportError:
    HAVE_PILLOW = False
    Image = None
    ExifTags = None

try:
    import telebot
    from telebot import types
except ImportError:
    telebot = None
    types = None

import i18n

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ghost_lens_sanitizer")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8100"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ghost_lens.db"
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
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                mode TEXT DEFAULT 'strip_all',
                format_out TEXT DEFAULT 'original',
                stego_check INTEGER DEFAULT 1,
                state TEXT DEFAULT 'idle',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sanitize_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                file_name TEXT,
                file_type TEXT,
                orig_bytes INTEGER,
                clean_bytes INTEGER,
                tags_scrubbed INTEGER,
                gps_scrubbed INTEGER,
                stego_entropy REAL,
                created_at INTEGER
            )
            """
        )
        conn.commit()


def get_user_settings(user_id: int | str) -> dict[str, Any]:
    uid = str(user_id).strip()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (uid,)).fetchone()
        if row:
            return dict(row)
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO user_settings (user_id, mode, format_out, stego_check, state, updated_at)
            VALUES (?, 'strip_all', 'original', 1, 'idle', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {
            "user_id": uid,
            "mode": "strip_all",
            "format_out": "original",
            "stego_check": 1,
            "state": "idle",
            "updated_at": now,
        }


def update_user_settings(user_id: int | str, **kwargs: Any) -> dict[str, Any]:
    uid = str(user_id).strip()
    st = get_user_settings(uid)
    st.update(kwargs)
    st["updated_at"] = int(time.time())
    with get_db() as conn:
        conn.execute(
            """
            UPDATE user_settings
            SET mode = ?, format_out = ?, stego_check = ?, state = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                str(st["mode"]),
                str(st["format_out"]),
                int(st["stego_check"]),
                str(st["state"]),
                int(st["updated_at"]),
                uid,
            ),
        )
        conn.commit()
    return st


def record_job(
    user_id: int | str,
    file_name: str,
    file_type: str,
    orig_bytes: int,
    clean_bytes: int,
    tags_scrubbed: int,
    gps_scrubbed: int,
    stego_entropy: float,
) -> None:
    uid = str(user_id).strip()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO sanitize_jobs (
                user_id, file_name, file_type, orig_bytes, clean_bytes,
                tags_scrubbed, gps_scrubbed, stego_entropy, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                file_name,
                file_type,
                orig_bytes,
                clean_bytes,
                tags_scrubbed,
                gps_scrubbed,
                stego_entropy,
                int(time.time()),
            ),
        )
        conn.commit()


def get_stats() -> dict[str, Any]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 
                COUNT(*) as total_jobs,
                COALESCE(SUM(tags_scrubbed), 0) as total_tags,
                COALESCE(SUM(gps_scrubbed), 0) as total_gps,
                COALESCE(SUM(CASE WHEN stego_entropy > 0.0 THEN 1 ELSE 0 END), 0) as total_stego
            FROM sanitize_jobs
            """
        ).fetchone()
        total_jobs = row["total_jobs"] if row else 0
        total_tags = row["total_tags"] if row else 0
        total_gps = row["total_gps"] if row else 0
        total_stego = row["total_stego"] if row else 0
        return {
            "total_jobs": total_jobs,
            "total_tags": total_tags,
            "total_gps": total_gps,
            "total_stego": total_stego,
        }


# ---------------------------------------------------------------------------
# EXIF & Stego Engine
# ---------------------------------------------------------------------------
def check_ffmpeg() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def _convert_gps_to_degrees(value: Any) -> float | None:
    """Helper to convert EXIF GPS tuple coordinates to decimal degrees."""
    try:
        if isinstance(value, (tuple, list)) and len(value) == 3:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        pass
    return None


def extract_metadata_report(file_path: str | Path) -> dict[str, Any]:
    """Inspects file EXIF, GPS, and container metadata without modifying."""
    p = Path(file_path)
    suffix = p.suffix.lower()
    report: dict[str, Any] = {
        "file_name": p.name,
        "suffix": suffix,
        "is_video": suffix in [".mp4", ".mov", ".mkv", ".webm", ".avi"],
        "has_gps": False,
        "gps_coords": None,
        "camera_make": None,
        "camera_model": None,
        "software": None,
        "date_time": None,
        "serial_number": None,
        "raw_tags": {},
        "tags_count": 0,
    }

    if not report["is_video"] and HAVE_PILLOW:
        try:
            with Image.open(p) as img:
                exif_data = img.getexif()
                if exif_data:
                    for tag_id, val in exif_data.items():
                        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                        # Skip large raw byte arrays for display
                        if isinstance(val, bytes) and len(val) > 100:
                            report["raw_tags"][tag_name] = f"<{len(val)} bytes>"
                        else:
                            report["raw_tags"][tag_name] = str(val)

                        if tag_name == "Make":
                            report["camera_make"] = str(val)
                        elif tag_name == "Model":
                            report["camera_model"] = str(val)
                        elif tag_name == "Software":
                            report["software"] = str(val)
                        elif tag_name in ("DateTime", "DateTimeOriginal"):
                            report["date_time"] = str(val)
                        elif "Serial" in tag_name:
                            report["serial_number"] = str(val)

                    # Inspect GPS IFD if present
                    gps_ifd = exif_data.get_ifd(ExifTags.IFD.GPSInfo) if hasattr(ExifTags, "IFD") else None
                    if gps_ifd:
                        lat_ref = gps_ifd.get(1, "N")
                        lat_val = _convert_gps_to_degrees(gps_ifd.get(2))
                        lon_ref = gps_ifd.get(3, "E")
                        lon_val = _convert_gps_to_degrees(gps_ifd.get(4))

                        if lat_val is not None and lon_val is not None:
                            if lat_ref == "S":
                                lat_val = -lat_val
                            if lon_ref == "W":
                                lon_val = -lon_val
                            report["has_gps"] = True
                            report["gps_coords"] = f"{lat_val:.6f}, {lon_val:.6f}"
                            report["raw_tags"]["GPSCoordinates"] = report["gps_coords"]

                    report["tags_count"] = len(report["raw_tags"])
        except Exception as e:
            logger.warning("Pillow exif inspection error: %s", e)

    elif report["is_video"]:
        # Use ffprobe to inspect video tags
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(p),
        ]
        try:
            out = subprocess.check_output(cmd)
            data = json.loads(out)
            tags = data.get("format", {}).get("tags", {})
            for k, v in tags.items():
                report["raw_tags"][k] = str(v)
                if "location" in k.lower():
                    report["has_gps"] = True
                    report["gps_coords"] = str(v)
            report["tags_count"] = len(tags)
        except Exception as e:
            logger.warning("ffprobe inspection error: %s", e)

    return report


def _get_pixel_data(img: Any) -> list[Any]:
    if hasattr(img, "get_flattened_data"):
        try:
            return list(img.get_flattened_data())
        except Exception:
            pass
    return list(img.getdata())


def calculate_lsb_entropy(image_path: str | Path) -> dict[str, Any]:
    """Calculates Shannon entropy of the Least Significant Bit (LSB) plane.
    Normal images: 0.40 - 0.75.
    Encrypted stego payload: 0.95 - 1.00 (uniform random distribution).
    """
    if not HAVE_PILLOW:
        return {"entropy": 0.0, "risk": "unknown", "label": "Pillow missing"}

    try:
        with Image.open(image_path) as img:
            rgb_img = img.convert("RGB")
            # Sample up to 500,000 pixels for fast execution
            pixels = _get_pixel_data(rgb_img)
            if len(pixels) > 500000:
                step = len(pixels) // 500000
                pixels = pixels[::step]

            # Extract LSB of each color channel
            bits = []
            for r, g, b in pixels:
                bits.append(r & 1)
                bits.append(g & 1)
                bits.append(b & 1)

            counts = Counter(bits)
            total = len(bits)
            if total == 0:
                return {"entropy": 0.0, "risk": "low", "label": "Normal"}

            # Shannon entropy H = - sum(p * log2(p))
            entropy = 0.0
            for count in counts.values():
                p = count / total
                if p > 0:
                    entropy -= p * math.log2(p)

            # Max entropy for 1 bit is 1.0
            entropy = min(1.0, max(0.0, entropy))

            if entropy >= 0.98:
                risk = "high"
                label = "⚠️ Stego Payload Suspicion (High Entropy)"
            elif entropy >= 0.88:
                risk = "medium"
                label = "⚡ Elevated Noise (Possible Stego / High ISO)"
            else:
                risk = "low"
                label = "✅ Clean Sensor Noise"

            return {
                "entropy": round(entropy, 4),
                "risk": risk,
                "label": label,
            }
    except Exception as e:
        logger.warning("Stego entropy check failed: %s", e)
        return {"entropy": 0.0, "risk": "error", "label": "Analysis Error"}


def sanitize_image(
    input_path: str | Path,
    output_path: str | Path,
    format_out: str = "original",
    keep_date: bool = False,
) -> None:
    """Deep scrubs all metadata, GPS, ICC profiles, thumbnails, MakerNotes from image."""
    in_p = Path(input_path)
    out_p = Path(output_path)

    # If Pillow is available, create pure clean pixel copy
    if HAVE_PILLOW:
        with Image.open(in_p) as img:
            # Preserve date if requested
            date_to_keep = None
            if keep_date:
                exif = img.getexif()
                if exif:
                    date_to_keep = exif.get(306) or exif.get(36867)

            # Re-create image from pure pixel data, abandoning all headers/icc/exif
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(_get_pixel_data(img))

            # Decide save format
            ext = in_p.suffix.lower()
            if format_out == "png":
                ext = ".png"
            elif format_out == "webp":
                ext = ".webp"

            if ext in (".jpg", ".jpeg"):
                if clean_img.mode in ("RGBA", "P"):
                    clean_img = clean_img.convert("RGB")
                if date_to_keep:
                    # Write only minimal date EXIF
                    minimal_exif = Image.Exif()
                    minimal_exif[306] = str(date_to_keep)
                    clean_img.save(str(out_p), "JPEG", quality=95, exif=minimal_exif)
                else:
                    clean_img.save(str(out_p), "JPEG", quality=95)
            elif ext == ".png":
                clean_img.save(str(out_p), "PNG", optimize=True)
            elif ext == ".webp":
                clean_img.save(str(out_p), "WEBP", quality=95, method=6)
            else:
                clean_img.save(str(out_p))
    else:
        # Fallback to FFmpeg metadata stripping
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(in_p),
            "-map_metadata", "-1",
            str(out_p),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sanitize_video(input_path: str | Path, output_path: str | Path) -> None:
    """Stream-copy video stripping all udta, meta, GPS, encoder tags without re-encoding."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-map_metadata", "-1",
        "-map_chapters", "-1",
        "-fflags", "+bitexact",
        "-flags:v", "+bitexact",
        "-flags:a", "+bitexact",
        "-c", "copy",
        str(output_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg video sanitize failed: {res.stderr[-300:]}")


def format_bytes(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


# ---------------------------------------------------------------------------
# Telegram Bot Keyboards (100% ReplyKeyboardMarkup, 0% Inline)
# ---------------------------------------------------------------------------
def build_main_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_all = types.KeyboardButton(i18n.t("btn_mode_strip_all", user_id=user_id))
    b_dat = types.KeyboardButton(i18n.t("btn_mode_keep_date", user_id=user_id))
    b_stg = types.KeyboardButton(i18n.t("btn_mode_stego_check", user_id=user_id))
    b_set = types.KeyboardButton(i18n.t("btn_settings", user_id=user_id))
    b_sta = types.KeyboardButton(i18n.t("btn_stats", user_id=user_id))
    b_hlp = types.KeyboardButton(i18n.t("btn_help", user_id=user_id))

    kb.add(b_all, b_dat)
    kb.add(b_stg)
    kb.add(b_set, b_sta, b_hlp)
    return kb


def build_settings_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_org = types.KeyboardButton(i18n.t("btn_format_original", user_id=user_id))
    b_png = types.KeyboardButton(i18n.t("btn_format_png", user_id=user_id))
    b_wbp = types.KeyboardButton(i18n.t("btn_format_webp", user_id=user_id))
    b_lng = types.KeyboardButton(i18n.t("btn_choose_lang", user_id=user_id))
    b_bck = types.KeyboardButton(i18n.t("btn_back_main", user_id=user_id))

    kb.add(b_org, b_png)
    kb.add(b_wbp, b_lng)
    kb.add(b_bck)
    return kb


# ---------------------------------------------------------------------------
# Telegram Bot Service
# ---------------------------------------------------------------------------
bot: Any = None
if telebot and BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


def setup_telegram_handlers() -> None:
    if not bot:
        return

    @bot.message_handler(commands=["start"])
    def handle_start(message: Any) -> None:
        uid = message.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            return
        welcome = i18n.t("tg_welcome", user_id=uid)
        bot.send_message(message.chat.id, welcome, reply_markup=build_main_keyboard(uid))

    @bot.message_handler(commands=["help"])
    def handle_help(message: Any) -> None:
        uid = message.from_user.id
        help_txt = i18n.t("tg_help_text", user_id=uid)
        bot.send_message(message.chat.id, help_txt, reply_markup=build_main_keyboard(uid))

    @bot.message_handler(content_types=["text"])
    def handle_text(message: Any) -> None:
        uid = message.from_user.id
        text = message.text.strip()

        # Check language button or choice
        if text == i18n.t("btn_choose_lang", user_id=uid):
            bot.send_message(
                message.chat.id,
                i18n.t("tg_lang_title", user_id=uid),
                reply_markup=i18n.build_reply_language_keyboard(uid),
            )
            return

        lang_code = i18n.parse_lang_choice(text)
        if lang_code:
            i18n.set_user_lang(uid, lang_code)
            bot.send_message(
                message.chat.id,
                i18n.t("tg_lang_changed", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_back_main", user_id=uid):
            bot.send_message(
                message.chat.id,
                i18n.t("tg_welcome", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_stats", user_id=uid):
            stats = get_stats()
            txt = i18n.t(
                "tg_stats_text",
                user_id=uid,
                total_jobs=stats["total_jobs"],
                total_tags=stats["total_tags"],
                total_gps=stats["total_gps"],
                total_stego=stats["total_stego"],
            )
            bot.send_message(message.chat.id, txt, reply_markup=build_main_keyboard(uid))
            return

        if text == i18n.t("btn_settings", user_id=uid):
            st = get_user_settings(uid)
            st_txt = i18n.t(
                "tg_settings_text",
                user_id=uid,
                mode=st["mode"],
                format_out=st["format_out"],
                stego_enabled="✅ ON" if st["stego_check"] else "❌ OFF",
            )
            bot.send_message(message.chat.id, st_txt, reply_markup=build_settings_keyboard(uid))
            return

        if text == i18n.t("btn_help", user_id=uid):
            bot.send_message(
                message.chat.id,
                i18n.t("tg_help_text", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_mode_strip_all", user_id=uid):
            update_user_settings(uid, mode="strip_all")
            bot.send_message(
                message.chat.id,
                "✅ <b>Режим установлен:</b> Стереть ВСЕ метаданные и GPS.",
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_mode_keep_date", user_id=uid):
            update_user_settings(uid, mode="keep_date")
            bot.send_message(
                message.chat.id,
                "✅ <b>Режим установлен:</b> Оставить дату съемки (GPS и серийники стираются).",
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_mode_stego_check", user_id=uid):
            st = get_user_settings(uid)
            new_val = 0 if st["stego_check"] else 1
            update_user_settings(uid, stego_check=new_val)
            status_str = "ВКЛЮЧЕН ✅" if new_val else "ВЫКЛЮЧЕН ❌"
            bot.send_message(
                message.chat.id,
                f"🔍 <b>Стеганографический анализ:</b> {status_str}",
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_format_original", user_id=uid):
            update_user_settings(uid, format_out="original")
            bot.send_message(
                message.chat.id,
                "📁 <b>Формат:</b> Исходный формат сохранен.",
                reply_markup=build_settings_keyboard(uid),
            )
            return

        if text == i18n.t("btn_format_png", user_id=uid):
            update_user_settings(uid, format_out="png")
            bot.send_message(
                message.chat.id,
                "🖼 <b>Формат:</b> Конвертировать в чистый PNG.",
                reply_markup=build_settings_keyboard(uid),
            )
            return

        if text == i18n.t("btn_format_webp", user_id=uid):
            update_user_settings(uid, format_out="webp")
            bot.send_message(
                message.chat.id,
                "⚡ <b>Формат:</b> Конвертировать в чистый WebP.",
                reply_markup=build_settings_keyboard(uid),
            )
            return

    def process_media_file(
        chat_id: int,
        uid: int,
        file_id: str,
        original_name: str,
        is_video: bool = False,
    ) -> None:
        try:
            status_msg = bot.send_message(chat_id, i18n.t("tg_analyzing", user_id=uid))
            file_info = bot.get_file(file_id)
            downloaded = bot.download_file(file_info.file_path)

            suffix = Path(original_name).suffix.lower() or (".mp4" if is_video else ".jpg")
            with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as tf_in:
                tf_in.write(downloaded)
                in_path = tf_in.name

            try:
                st = get_user_settings(uid)
                meta_report = extract_metadata_report(in_path)
                stego_info = {"entropy": 0.0, "risk": "off", "label": "Disabled"}
                if not is_video and st["stego_check"]:
                    stego_info = calculate_lsb_entropy(in_path)

                # Determine clean output path
                fmt = st["format_out"]
                out_suffix = suffix
                if not is_video:
                    if fmt == "png":
                        out_suffix = ".png"
                    elif fmt == "webp":
                        out_suffix = ".webp"

                clean_name = f"clean_{Path(original_name).stem}{out_suffix}"
                out_path = os.path.join(tempfile.gettempdir(), clean_name)

                keep_date = (st["mode"] == "keep_date")
                if is_video:
                    sanitize_video(in_path, out_path)
                else:
                    sanitize_image(in_path, out_path, format_out=fmt, keep_date=keep_date)

                orig_bytes = os.path.getsize(in_path)
                clean_bytes = os.path.getsize(out_path)

                # Record stats
                gps_scrubbed = 1 if meta_report["has_gps"] else 0
                record_job(
                    user_id=uid,
                    file_name=original_name,
                    file_type="video" if is_video else "photo",
                    orig_bytes=orig_bytes,
                    clean_bytes=clean_bytes,
                    tags_scrubbed=meta_report["tags_count"],
                    gps_scrubbed=gps_scrubbed,
                    stego_entropy=stego_info["entropy"],
                )

                gps_status = f"🔴 {meta_report['gps_coords']} (Удалены)" if meta_report["has_gps"] else "✅ Не обнаружены"
                done_txt = i18n.t(
                    "tg_clean_done",
                    user_id=uid,
                    tags_count=meta_report["tags_count"],
                    gps_status=gps_status,
                    orig_size=format_bytes(orig_bytes),
                    clean_size=format_bytes(clean_bytes),
                    entropy_val=stego_info["entropy"],
                    entropy_desc=stego_info["label"],
                )

                bot.delete_message(chat_id, status_msg.message_id)
                with open(out_path, "rb") as clean_file:
                    if is_video:
                        bot.send_video(
                            chat_id,
                            clean_file,
                            caption=done_txt,
                            reply_markup=build_main_keyboard(uid),
                        )
                    else:
                        bot.send_document(
                            chat_id,
                            clean_file,
                            caption=done_txt,
                            reply_markup=build_main_keyboard(uid),
                        )

            finally:
                if os.path.exists(in_path):
                    try:
                        os.unlink(in_path)
                    except Exception:
                        pass
                if os.path.exists(out_path):
                    try:
                        os.unlink(out_path)
                    except Exception:
                        pass

        except Exception as e:
            logger.error("Error processing media: %s", e)
            bot.send_message(chat_id, f"❌ <b>Ошибка:</b> {html.escape(str(e))}")

    @bot.message_handler(content_types=["photo"])
    def handle_photo(message: Any) -> None:
        uid = message.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            return
        photo = message.photo[-1]
        t = threading.Thread(
            target=process_media_file,
            args=(message.chat.id, uid, photo.file_id, "photo.jpg", False),
            daemon=True,
        )
        t.start()

    @bot.message_handler(content_types=["video"])
    def handle_video(message: Any) -> None:
        uid = message.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            return
        vid = message.video
        t = threading.Thread(
            target=process_media_file,
            args=(message.chat.id, uid, vid.file_id, vid.file_name or "video.mp4", True),
            daemon=True,
        )
        t.start()

    @bot.message_handler(content_types=["document"])
    def handle_document(message: Any) -> None:
        uid = message.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            return
        doc = message.document
        name = doc.file_name or "file.bin"
        suffix = Path(name).suffix.lower()
        is_video = suffix in [".mp4", ".mov", ".mkv", ".webm"]
        t = threading.Thread(
            target=process_media_file,
            args=(message.chat.id, uid, doc.file_id, name, is_video),
            daemon=True,
        )
        t.start()


# ---------------------------------------------------------------------------
# Standalone Cyberpunk Web Studio (Port 8100)
# ---------------------------------------------------------------------------
WEB_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ghost Lens Sanitizer Studio</title>
<style>
:root {
  --bg-dark: #0a0e14;
  --bg-card: #121824;
  --neon-cyan: #00f0ff;
  --neon-red: #ff0055;
  --neon-green: #00ff66;
  --neon-gold: #ffb700;
  --text-main: #f0f6fc;
  --text-muted: #8b949e;
  --border: #21262d;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--bg-dark);
  color: var(--text-main);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
  padding: 20px;
  line-height: 1.5;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
  padding-bottom: 16px;
  margin-bottom: 24px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand h1 {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--neon-cyan);
  text-shadow: 0 0 10px rgba(0,240,255,0.3);
}
.badge {
  background: rgba(0, 255, 102, 0.15);
  color: var(--neon-green);
  border: 1px solid var(--neon-green);
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
}
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
}
.card h2 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 8px;
}
.drop-zone {
  border: 2px dashed var(--border);
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: rgba(255,255,255,0.01);
}
.drop-zone:hover, .drop-zone.dragover {
  border-color: var(--neon-cyan);
  background: rgba(0,240,255,0.05);
}
.btn {
  background: var(--neon-cyan);
  color: #000;
  border: none;
  border-radius: 4px;
  padding: 10px 20px;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
}
.btn:hover {
  filter: brightness(1.2);
  box-shadow: 0 0 15px rgba(0,240,255,0.5);
}
.btn-red {
  background: var(--neon-red);
  color: #fff;
}
.btn-red:hover {
  box-shadow: 0 0 15px rgba(255,0,85,0.5);
}
.meta-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-top: 12px;
}
.meta-table th, .meta-table td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
.meta-table th {
  color: var(--text-muted);
  font-weight: 600;
}
.tag-pill {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.pill-danger {
  background: rgba(255,0,85,0.15);
  color: var(--neon-red);
  border: 1px solid var(--neon-red);
}
.pill-clean {
  background: rgba(0,255,102,0.15);
  color: var(--neon-green);
  border: 1px solid var(--neon-green);
}
.gauge-container {
  margin: 16px 0;
}
.gauge-bar {
  height: 12px;
  background: #1c2430;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}
.gauge-fill {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, var(--neon-green) 0%, var(--neon-gold) 60%, var(--neon-red) 100%);
  transition: width 0.5s ease;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.stat-label { color: var(--text-muted); }
.stat-value { font-weight: 600; color: var(--neon-cyan); }
</style>
</head>
<body>
<div class="header">
  <div class="brand">
    <h1>👻 GHOST LENS SANITIZER</h1>
    <span class="badge" id="botStatus">ONLINE • PORT 8100</span>
  </div>
  <div>
    <button class="btn btn-red" onclick="sanitizeCurrentFile()" id="sanitizeBtn" disabled>
      🛡 SANITIZE & PURGE ALL
    </button>
  </div>
</div>

<div class="grid">
  <!-- Left Column: Upload & Live Stego Canary -->
  <div class="card">
    <h2>📁 Media Ingestion & Scanner</h2>
    <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
      <div style="font-size: 32px; margin-bottom: 8px;">📷</div>
      <div style="font-weight: 600;">Click or Drop Image / Video Here</div>
      <div style="color: var(--text-muted); font-size: 12px; margin-top: 4px;">JPEG, PNG, WebP, TIFF, MP4, MOV</div>
      <input type="file" id="fileInput" style="display: none;" onchange="handleFileSelect(this.files[0])">
    </div>

    <div style="margin-top: 24px;">
      <h2>🔍 Stego Canary Entropy Analyzer</h2>
      <div class="gauge-container">
        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
          <span id="entropyScore">LSB Entropy: 0.0000</span>
          <span id="entropyVerdict" class="tag-pill pill-clean">Waiting for Media</span>
        </div>
        <div class="gauge-bar">
          <div class="gauge-fill" id="gaugeFill"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-muted); margin-top: 4px;">
          <span>0.0 (Clean/Simple)</span>
          <span>0.75 (Normal Sensor Noise)</span>
          <span>1.0 (Uniform Random / Stego Alert)</span>
        </div>
      </div>
    </div>

    <div style="margin-top: 24px;">
      <h2>📊 Global Sanitizer Metrics</h2>
      <div class="stat-row">
        <span class="stat-label">Total Files Cleaned:</span>
        <span class="stat-value" id="statFiles">0</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">GPS Geotags Scrubbed:</span>
        <span class="stat-value" id="statGps">0</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Metadata Tags Purged:</span>
        <span class="stat-value" id="statTags">0</span>
      </div>
    </div>
  </div>

  <!-- Right Column: EXIF Metadata Inspector Table -->
  <div class="card">
    <h2>🏷 Metadata Inspector & Geotag Diff</h2>
    <div style="overflow-x: auto; max-height: 480px;">
      <table class="meta-table" id="metaTable">
        <thead>
          <tr>
            <th>Tag Name</th>
            <th>Original Value</th>
            <th>Sanitized State</th>
          </tr>
        </thead>
        <tbody id="metaBody">
          <tr>
            <td colspan="3" style="text-align: center; color: var(--text-muted); padding: 30px;">
              No file loaded. Drop an image or video above to inspect EXIF and GPS tags.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
let activeFile = null;

async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.status === 'online') {
      document.getElementById('botStatus').innerText = `ONLINE • PORT ${data.port}`;
    }
  } catch (e) {
    document.getElementById('botStatus').innerText = 'OFFLINE';
    document.getElementById('botStatus').style.color = '#ff0055';
    document.getElementById('botStatus').style.borderColor = '#ff0055';
  }
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('statFiles').innerText = data.total_jobs;
    document.getElementById('statGps').innerText = data.total_gps;
    document.getElementById('statTags').innerText = data.total_tags;
  } catch (e) {}
}

const dropZone = document.getElementById('dropZone');
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) {
    handleFileSelect(e.dataTransfer.files[0]);
  }
});

async function handleFileSelect(file) {
  if (!file) return;
  activeFile = file;
  document.getElementById('sanitizeBtn').disabled = false;

  const formData = new FormData();
  formData.append('file', file);

  const tbody = document.getElementById('metaBody');
  tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 20px;">🔍 Inspecting EXIF tags & LSB entropy...</td></tr>';

  try {
    const res = await fetch('/api/inspect', { method: 'POST', body: formData });
    const data = await res.json();
    
    // Render Stego Gauge
    if (data.stego) {
      const ent = data.stego.entropy || 0.0;
      document.getElementById('entropyScore').innerText = `LSB Entropy: ${ent.toFixed(4)}`;
      document.getElementById('gaugeFill').style.width = `${Math.min(100, ent * 100)}%`;
      const verd = document.getElementById('entropyVerdict');
      verd.innerText = data.stego.label;
      if (data.stego.risk === 'high') {
        verd.className = 'tag-pill pill-danger';
      } else {
        verd.className = 'tag-pill pill-clean';
      }
    }

    // Render Table
    tbody.innerHTML = '';
    const tags = data.report.raw_tags || {};
    const keys = Object.keys(tags);
    if (keys.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color: var(--neon-green); padding: 20px;">✅ Clean file: No EXIF tags or GPS metadata detected!</td></tr>';
      return;
    }

    for (const k of keys) {
      const tr = document.createElement('tr');
      const isDangerous = k.includes('GPS') || k.includes('Make') || k.includes('Model') || k.includes('Serial') || k.includes('Software');
      tr.innerHTML = `
        <td style="font-weight: 600;">${k}</td>
        <td style="color: ${isDangerous ? 'var(--neon-red)' : 'var(--text-main)'};">${tags[k]}</td>
        <td><span class="tag-pill pill-danger">PURGED ✂️</span></td>
      `;
      tbody.appendChild(tr);
    }

  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="3" style="color:var(--neon-red); text-align:center;">Inspection error: ${e.message}</td></tr>`;
  }
}

async function sanitizeCurrentFile() {
  if (!activeFile) return;
  const btn = document.getElementById('sanitizeBtn');
  btn.disabled = true;
  btn.innerText = '🛡 PURGING METADATA...';

  const formData = new FormData();
  formData.append('file', activeFile);

  try {
    const res = await fetch('/api/sanitize', { method: 'POST', body: formData });
    if (!res.ok) throw new Error('Sanitize failed');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `clean_${activeFile.name}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    loadStats();
  } catch (e) {
    alert('Sanitize failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerText = '🛡 SANITIZE & PURGE ALL';
  }
}

checkStatus();
loadStats();
setInterval(checkStatus, 10000);
</script>
</body>
</html>
"""


class WebStudioHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("%s - " + format, self.address_string(), *args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(WEB_HTML.encode("utf-8"))
            return

        if parsed.path == "/api/status":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            body = {
                "status": "online",
                "bot": "ghost_lens_sanitizer",
                "port": WEB_PORT,
                "ffmpeg": check_ffmpeg(),
                "pillow": HAVE_PILLOW,
                "uptime": time.time(),
            }
            self.wfile.write(json.dumps(body).encode("utf-8"))
            return

        if parsed.path == "/api/stats":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_stats()).encode("utf-8"))
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/api/inspect", "/api/sanitize"):
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("multipart/form-data"):
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                return

            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)

            boundary = content_type.split("boundary=")[-1].strip().encode()
            parts = raw_body.split(b"--" + boundary)

            file_bytes = b""
            filename = "upload.jpg"
            for part in parts:
                if b'filename="' in part:
                    header_part, file_data = part.split(b"\r\n\r\n", 1)
                    file_data = file_data.rstrip(b"\r\n")
                    file_bytes = file_data
                    m = re.search(rb'filename="([^"]+)"', header_part)
                    if m:
                        filename = m.group(1).decode(errors="ignore")
                    break

            if not file_bytes:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                return

            suffix = Path(filename).suffix.lower() or ".jpg"
            with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as tf:
                tf.write(file_bytes)
                tmp_in = tf.name

            try:
                is_video = suffix in [".mp4", ".mov", ".mkv", ".webm"]
                report = extract_metadata_report(tmp_in)
                stego = calculate_lsb_entropy(tmp_in) if not is_video else {"entropy": 0.0, "risk": "low", "label": "Video (N/A)"}

                if parsed.path == "/api/inspect":
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"report": report, "stego": stego}).encode("utf-8"))
                    return

                if parsed.path == "/api/sanitize":
                    clean_out = os.path.join(tempfile.gettempdir(), f"clean_{filename}")
                    if is_video:
                        sanitize_video(tmp_in, clean_out)
                    else:
                        sanitize_image(tmp_in, clean_out, format_out="original", keep_date=False)

                    with open(clean_out, "rb") as cf:
                        clean_data = cf.read()

                    # Record job
                    gps_scrubbed = 1 if report["has_gps"] else 0
                    record_job(
                        user_id="web_studio",
                        file_name=filename,
                        file_type="video" if is_video else "photo",
                        orig_bytes=len(file_bytes),
                        clean_bytes=len(clean_data),
                        tags_scrubbed=report["tags_count"],
                        gps_scrubbed=gps_scrubbed,
                        stego_entropy=stego["entropy"],
                    )

                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'attachment; filename="clean_{filename}"')
                    self.end_headers()
                    self.wfile.write(clean_data)

                    if os.path.exists(clean_out):
                        try:
                            os.unlink(clean_out)
                        except Exception:
                            pass
                    return

            finally:
                if os.path.exists(tmp_in):
                    try:
                        os.unlink(tmp_in)
                    except Exception:
                        pass

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()


def run_web_server() -> None:
    server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), WEB_PORT), WebStudioHandler)
    print(f"[PYBIONIC_WEB:{WEB_PORT}]", flush=True)
    logger.info("Ghost Lens Sanitizer Studio running on port %d", WEB_PORT)
    server.serve_forever()


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    init_db()
    logger.info("Starting Ghost Lens Sanitizer...")

    # Start Web Studio thread
    web_t = threading.Thread(target=run_web_server, daemon=True)
    web_t.start()

    # Start Telegram bot if token is provided
    if bot:
        setup_telegram_handlers()
        logger.info("Starting Telegram bot polling...")
        bot.infinity_polling(skip_pending=True)
    else:
        logger.info("BOT_TOKEN not provided, running in Web Studio mode on port %d", WEB_PORT)
        web_t.join()


if __name__ == "__main__":
    main()
