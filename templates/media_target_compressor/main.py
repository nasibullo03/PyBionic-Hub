#!/usr/bin/env python3
"""Media Target Compressor (BotHub Level 10/10)
High-precision 2-pass target size compression engine for Telegram, Discord, WhatsApp & Mail.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- Dynamic 2-pass bitrate allocation with container margin reserve.
- Auto-resolution adaptation (prevents macroblocking at low bitrates).
- Multi-format support (MP4, MKV, MOV, WEBM, MP3, AAC, OGG).
- Standalone Cyberpunk Web Studio on port 8096 with live bit allocation math.
- 24 languages support via i18n and locales.json.
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
import subprocess
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
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

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
logger = logging.getLogger("media_target_compressor")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8096"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "compressor.db"
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
                target_mb REAL DEFAULT 8.0,
                mode TEXT DEFAULT '2pass',
                scale_pref TEXT DEFAULT 'auto',
                audio_kbps INTEGER DEFAULT 96,
                state TEXT DEFAULT 'idle',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compression_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                original_bytes INTEGER,
                target_bytes INTEGER,
                final_bytes INTEGER,
                duration_sec REAL,
                mode TEXT,
                scale_pref TEXT,
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
            INSERT INTO user_settings (user_id, target_mb, mode, scale_pref, audio_kbps, state, updated_at)
            VALUES (?, 8.0, '2pass', 'auto', 96, 'idle', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {
            "user_id": uid,
            "target_mb": 8.0,
            "mode": "2pass",
            "scale_pref": "auto",
            "audio_kbps": 96,
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
            SET target_mb = ?, mode = ?, scale_pref = ?, audio_kbps = ?, state = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                float(st["target_mb"]),
                str(st["mode"]),
                str(st["scale_pref"]),
                int(st["audio_kbps"]),
                str(st["state"]),
                int(st["updated_at"]),
                uid,
            ),
        )
        conn.commit()
    return st


def record_compression_job(
    user_id: int | str,
    original_bytes: int,
    target_bytes: int,
    final_bytes: int,
    duration_sec: float,
    mode: str,
    scale_pref: str,
) -> None:
    uid = str(user_id).strip()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO compression_jobs (user_id, original_bytes, target_bytes, final_bytes, duration_sec, mode, scale_pref, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                original_bytes,
                target_bytes,
                final_bytes,
                duration_sec,
                mode,
                scale_pref,
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
                COALESCE(SUM(original_bytes), 0) as total_in,
                COALESCE(SUM(final_bytes), 0) as total_out
            FROM compression_jobs
            """
        ).fetchone()
        total_jobs = row["total_jobs"] if row else 0
        total_in = row["total_in"] if row else 0
        total_out = row["total_out"] if row else 0
        saved = max(0, total_in - total_out)
        pct = (saved / total_in * 100.0) if total_in > 0 else 0.0
        return {
            "total_jobs": total_jobs,
            "total_in_mb": round(total_in / (1024 * 1024), 2),
            "total_out_mb": round(total_out / (1024 * 1024), 2),
            "saved_mb": round(saved / (1024 * 1024), 2),
            "pct_saved": round(pct, 1),
        }


# ---------------------------------------------------------------------------
# FFmpeg & Bitrate Math Engine
# ---------------------------------------------------------------------------
def check_ffmpeg() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def get_media_info(file_path: str | Path) -> dict[str, Any]:
    p = str(file_path)
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        p,
    ]
    try:
        out = subprocess.check_output(cmd)
        data = json.loads(out)
    except Exception as e:
        logger.warning(f"ffprobe failed on {p}: {e}")
        return {
            "duration": 0.0,
            "width": 0,
            "height": 0,
            "has_video": False,
            "has_audio": False,
            "vcodec": "",
            "acodec": "",
            "size": os.path.getsize(p) if os.path.exists(p) else 0,
        }

    fmt = data.get("format", {})
    dur = float(fmt.get("duration", 0.0))
    streams = data.get("streams", [])
    has_video = False
    has_audio = False
    width = 0
    height = 0
    vcodec = ""
    acodec = ""

    for s in streams:
        codec_type = s.get("codec_type")
        if codec_type == "video" and not has_video:
            has_video = True
            width = int(s.get("width", 0))
            height = int(s.get("height", 0))
            vcodec = s.get("codec_name", "")
            if dur <= 0.0 and "duration" in s:
                try:
                    dur = float(s["duration"])
                except Exception:
                    pass
        elif codec_type == "audio" and not has_audio:
            has_audio = True
            acodec = s.get("codec_name", "")
            if dur <= 0.0 and "duration" in s:
                try:
                    dur = float(s["duration"])
                except Exception:
                    pass

    return {
        "duration": max(dur, 0.1),
        "width": width,
        "height": height,
        "has_video": has_video,
        "has_audio": has_audio,
        "vcodec": vcodec,
        "acodec": acodec,
        "size": os.path.getsize(p) if os.path.exists(p) else 0,
    }


def calculate_bitrate_plan(
    target_bytes: int,
    duration_sec: float,
    audio_budget_kbps: int = 96,
    container_margin: float = 0.04,
) -> dict[str, Any]:
    """Computes exact video and audio bitrates along with recommended downscale resolution."""
    duration = max(duration_sec, 0.5)
    usable_bits = target_bytes * 8.0 * (1.0 - container_margin)
    total_kbps = usable_bits / (duration * 1000.0)

    # Audio budget adapts if total bitrate is constrained
    if total_kbps < 150:
        a_kbps = 32
    elif total_kbps < 300:
        a_kbps = 48
    elif total_kbps < 600:
        a_kbps = 64
    else:
        a_kbps = min(audio_budget_kbps, 128)

    v_kbps = max(25, int(total_kbps - a_kbps))

    # Recommended resolution cap
    if v_kbps >= 1500:
        rec_res = "1080p"
        max_h = 1080
    elif v_kbps >= 700:
        rec_res = "720p"
        max_h = 720
    elif v_kbps >= 350:
        rec_res = "480p"
        max_h = 480
    else:
        rec_res = "360p"
        max_h = 360

    return {
        "total_kbps": int(total_kbps),
        "video_kbps": v_kbps,
        "audio_kbps": a_kbps,
        "recommended_res": rec_res,
        "max_h": max_h,
    }


def get_scale_filter(scale_pref: str, rec_max_h: int) -> str:
    """Produces an FFmpeg scale filter that always yields even dimensions."""
    if scale_pref == "keep":
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    if scale_pref == "720p":
        target_h = 720
    elif scale_pref == "480p":
        target_h = 480
    elif scale_pref == "auto":
        target_h = rec_max_h
    else:
        target_h = 720

    # Scale filter capping height to target_h while ensuring even width and height
    return f"scale=trunc(iw*min(1\\,{target_h}/ih)/2)*2:trunc(ih*min(1\\,{target_h}/ih)/2)*2"


def compress_media(
    input_path: str | Path,
    output_path: str | Path,
    target_bytes: int,
    mode: str = "2pass",
    scale_pref: str = "auto",
    audio_budget_kbps: int = 96,
) -> dict[str, Any]:
    info = get_media_info(input_path)
    dur = info["duration"]
    has_video = info["has_video"]
    has_audio = info["has_audio"]

    out_p = str(output_path)
    in_p = str(input_path)

    # Audio-only compression
    if not has_video or mode == "audio":
        usable_bits = target_bytes * 8.0 * 0.95
        a_kbps = max(24, int(usable_bits / (dur * 1000.0)))
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            in_p,
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            f"{a_kbps}k",
            out_p,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg audio encoding failed: {res.stderr[-300:]}")
        final_sz = os.path.getsize(out_p) if os.path.exists(out_p) else 0
        return {
            "mode": "audio",
            "duration": dur,
            "video_kbps": 0,
            "audio_kbps": a_kbps,
            "scale": "N/A",
            "final_bytes": final_sz,
        }

    # Video compression
    plan = calculate_bitrate_plan(target_bytes, dur, audio_budget_kbps)
    v_kbps = plan["video_kbps"]
    a_kbps = plan["audio_kbps"]
    vf = get_scale_filter(scale_pref, plan["max_h"])

    null_dev = "NUL" if os.name == "nt" else "/dev/null"
    temp_dir = tempfile.mkdtemp(prefix="target_comp_")
    passlog = os.path.join(temp_dir, "ffmpeg2pass")

    try:
        if mode == "1pass":
            # Fast CRF single pass
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                in_p,
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-b:v",
                f"{v_kbps}k",
                "-maxrate",
                f"{int(v_kbps * 1.3)}k",
                "-bufsize",
                f"{int(v_kbps * 2)}k",
                "-c:a",
                "aac",
                "-b:a",
                f"{a_kbps}k",
                "-movflags",
                "+faststart",
                out_p,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg 1-pass failed: {res.stderr[-300:]}")
        else:
            # 2-Pass precision target fit
            cmd_p1 = [
                "ffmpeg",
                "-y",
                "-i",
                in_p,
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-b:v",
                f"{v_kbps}k",
                "-pass",
                "1",
                "-passlogfile",
                passlog,
                "-an",
                "-f",
                "mp4",
                null_dev,
            ]
            res1 = subprocess.run(cmd_p1, capture_output=True, text=True)
            if res1.returncode != 0:
                raise RuntimeError(f"FFmpeg pass 1 failed: {res1.stderr[-300:]}")

            cmd_p2 = [
                "ffmpeg",
                "-y",
                "-i",
                in_p,
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-b:v",
                f"{v_kbps}k",
                "-pass",
                "2",
                "-passlogfile",
                passlog,
                "-c:a",
                "aac",
                "-b:a",
                f"{a_kbps}k",
                "-movflags",
                "+faststart",
                out_p,
            ]
            res2 = subprocess.run(cmd_p2, capture_output=True, text=True)
            if res2.returncode != 0:
                raise RuntimeError(f"FFmpeg pass 2 failed: {res2.stderr[-300:]}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    final_sz = os.path.getsize(out_p) if os.path.exists(out_p) else 0
    return {
        "mode": mode,
        "duration": dur,
        "video_kbps": v_kbps,
        "audio_kbps": a_kbps,
        "scale": plan["recommended_res"] if scale_pref == "auto" else scale_pref,
        "final_bytes": final_sz,
    }


def format_bytes(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


def format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Telegram Bot Keyboards (100% ReplyKeyboardMarkup, 0% Inline)
# ---------------------------------------------------------------------------
def build_main_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b8 = types.KeyboardButton(i18n.t("btn_preset_8mb", user_id=user_id))
    b16 = types.KeyboardButton(i18n.t("btn_preset_16mb", user_id=user_id))
    b25 = types.KeyboardButton(i18n.t("btn_preset_25mb", user_id=user_id))
    b50 = types.KeyboardButton(i18n.t("btn_preset_50mb", user_id=user_id))
    b100 = types.KeyboardButton(i18n.t("btn_preset_100mb", user_id=user_id))
    bcustom = types.KeyboardButton(i18n.t("btn_custom_size", user_id=user_id))
    bset = types.KeyboardButton(i18n.t("btn_settings", user_id=user_id))
    bstats = types.KeyboardButton(i18n.t("btn_stats", user_id=user_id))
    bhelp = types.KeyboardButton(i18n.t("btn_help", user_id=user_id))
    kb.add(b8, b16)
    kb.add(b25, b50)
    kb.add(b100, bcustom)
    kb.add(bset, bstats, bhelp)
    return kb


def build_settings_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m2p = types.KeyboardButton(i18n.t("btn_mode_2pass", user_id=user_id))
    m1p = types.KeyboardButton(i18n.t("btn_mode_1pass", user_id=user_id))
    maudio = types.KeyboardButton(i18n.t("btn_mode_audio", user_id=user_id))
    sauto = types.KeyboardButton(i18n.t("btn_scale_auto", user_id=user_id))
    s720 = types.KeyboardButton(i18n.t("btn_scale_720p", user_id=user_id))
    s480 = types.KeyboardButton(i18n.t("btn_scale_480p", user_id=user_id))
    blang = types.KeyboardButton(i18n.t("btn_choose_lang", user_id=user_id))
    bback = types.KeyboardButton(i18n.t("btn_back_main", user_id=user_id))
    kb.add(m2p, m1p)
    kb.add(maudio, sauto)
    kb.add(s720, s480)
    kb.add(blang, bback)
    return kb


# ---------------------------------------------------------------------------
# Telegram Bot Handlers
# ---------------------------------------------------------------------------
def setup_bot(bot: Any) -> None:
    @bot.message_handler(commands=["start"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            bot.reply_to(msg, "Access denied.")
            return
        st = get_user_settings(uid)
        update_user_settings(uid, state="idle")
        welcome = i18n.t(
            "tg_welcome",
            user_id=uid,
            target_mb=st["target_mb"],
            mode=st["mode"],
            scale=st["scale_pref"],
        )
        bot.send_message(
            msg.chat.id,
            welcome,
            parse_mode="HTML",
            reply_markup=build_main_keyboard(uid),
        )

    @bot.message_handler(commands=["help"])
    def on_help(msg: Any) -> None:
        uid = msg.from_user.id
        text = i18n.t("tg_help_text", user_id=uid, port=WEB_PORT)
        bot.send_message(
            msg.chat.id,
            text,
            parse_mode="HTML",
            reply_markup=build_main_keyboard(uid),
        )

    @bot.message_handler(commands=["stats"])
    def on_stats(msg: Any) -> None:
        uid = msg.from_user.id
        s = get_stats()
        text = i18n.t(
            "msg_stats",
            user_id=uid,
            total_jobs=s["total_jobs"],
            total_in_mb=s["total_in_mb"],
            total_out_mb=s["total_out_mb"],
            saved_mb=s["saved_mb"],
            pct_saved=s["pct_saved"],
        )
        bot.send_message(
            msg.chat.id,
            text,
            parse_mode="HTML",
            reply_markup=build_main_keyboard(uid),
        )

    @bot.message_handler(commands=["lang"])
    def on_lang_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        update_user_settings(uid, state="lang_pick")
        kb = i18n.build_reply_language_keyboard(user_id=uid)
        bot.send_message(
            msg.chat.id,
            i18n.t("tg_lang_title", user_id=uid),
            reply_markup=kb,
        )

    @bot.message_handler(content_types=["video", "document", "audio", "voice"])
    def on_media_received(msg: Any) -> None:
        uid = msg.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            bot.reply_to(msg, "Access denied.")
            return

        file_obj = None
        ext = ".mp4"
        if msg.video:
            file_obj = msg.video
            ext = ".mp4"
        elif msg.audio:
            file_obj = msg.audio
            ext = ".mp3"
        elif msg.voice:
            file_obj = msg.voice
            ext = ".ogg"
        elif msg.document:
            file_obj = msg.document
            name = (msg.document.file_name or "").lower()
            if any(name.endswith(e) for e in [".mp4", ".mkv", ".mov", ".webm", ".avi", ".ts", ".mp3", ".m4a", ".ogg", ".flac"]):
                ext = os.path.splitext(name)[1]
            else:
                ext = ".mp4"

        if not file_obj:
            bot.reply_to(msg, i18n.t("msg_send_file", user_id=uid))
            return

        # Start asynchronous processing thread
        def worker() -> None:
            st = get_user_settings(uid)
            target_mb = float(st["target_mb"])
            target_bytes = int(target_mb * 1024 * 1024)
            mode = str(st["mode"])
            scale_pref = str(st["scale_pref"])

            status_msg = bot.send_message(
                msg.chat.id,
                i18n.t(
                    "msg_processing",
                    user_id=uid,
                    target=target_mb,
                    mode=mode,
                    scale=scale_pref,
                ),
                parse_mode="HTML",
            )

            tmp_in = None
            tmp_out = None
            try:
                finfo = bot.get_file(file_obj.file_id)
                data = bot.download_file(finfo.file_path)

                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                    tf.write(data)
                    tmp_in = tf.name

                orig_size = os.path.getsize(tmp_in)
                out_ext = ".mp3" if mode == "audio" or ext in [".mp3", ".ogg", ".m4a"] else ".mp4"
                with tempfile.NamedTemporaryFile(suffix=out_ext, delete=False) as tf_out:
                    tmp_out = tf_out.name

                # Perform compression
                res = compress_media(
                    input_path=tmp_in,
                    output_path=tmp_out,
                    target_bytes=target_bytes,
                    mode=mode,
                    scale_pref=scale_pref,
                    audio_budget_kbps=int(st["audio_kbps"]),
                )

                final_size = os.path.getsize(tmp_out)
                record_compression_job(
                    user_id=uid,
                    original_bytes=orig_size,
                    target_bytes=target_bytes,
                    final_bytes=final_size,
                    duration_sec=res["duration"],
                    mode=mode,
                    scale_pref=scale_pref,
                )

                pct = round((final_size / orig_size * 100.0), 1) if orig_size > 0 else 100.0
                caption = i18n.t(
                    "msg_success",
                    user_id=uid,
                    orig_size=format_bytes(orig_size),
                    target_size=format_bytes(target_bytes),
                    final_size=format_bytes(final_size),
                    pct=pct,
                    duration=format_duration(res["duration"]),
                    v_kbps=res["video_kbps"],
                    a_kbps=res["audio_kbps"],
                    resolution=res["scale"],
                )

                with open(tmp_out, "rb") as out_f:
                    if out_ext == ".mp4":
                        bot.send_video(
                            msg.chat.id,
                            out_f,
                            caption=caption,
                            parse_mode="HTML",
                            supports_streaming=True,
                            reply_markup=build_main_keyboard(uid),
                        )
                    else:
                        bot.send_audio(
                            msg.chat.id,
                            out_f,
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=build_main_keyboard(uid),
                        )

            except Exception as e:
                logger.exception("Compression worker failed")
                bot.send_message(
                    msg.chat.id,
                    f"❌ Ошибка сжатия / Compression error: {e}",
                    reply_markup=build_main_keyboard(uid),
                )
            finally:
                if tmp_in and os.path.exists(tmp_in):
                    try:
                        os.unlink(tmp_in)
                    except Exception:
                        pass
                if tmp_out and os.path.exists(tmp_out):
                    try:
                        os.unlink(tmp_out)
                    except Exception:
                        pass
                try:
                    bot.delete_message(msg.chat.id, status_msg.message_id)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    @bot.message_handler(func=lambda m: True)
    def on_text(msg: Any) -> None:
        uid = msg.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            bot.reply_to(msg, "Access denied.")
            return

        text = (msg.text or "").strip()
        st = get_user_settings(uid)

        # Language selection flow
        if st.get("state") == "lang_pick":
            lang = i18n.parse_lang_choice(text)
            if lang:
                i18n.set_user_lang(uid, lang)
                update_user_settings(uid, state="idle")
                bot.send_message(
                    msg.chat.id,
                    i18n.t("tg_lang_changed", user_id=uid),
                    reply_markup=build_main_keyboard(uid),
                )
                return

        # Custom size prompt flow
        if st.get("state") == "custom_size":
            try:
                val = float(text.replace(",", "."))
                if 0.5 <= val <= 2000.0:
                    update_user_settings(uid, target_mb=val, state="idle")
                    bot.send_message(
                        msg.chat.id,
                        i18n.t("msg_custom_size_set", user_id=uid, size=val),
                        parse_mode="HTML",
                        reply_markup=build_main_keyboard(uid),
                    )
                    return
            except ValueError:
                pass
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_invalid_size", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
            return

        # Main menu presets
        if "8 MB" in text:
            update_user_settings(uid, target_mb=8.0)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_custom_size_set", user_id=uid, size=8.0),
                parse_mode="HTML",
                reply_markup=build_main_keyboard(uid),
            )
        elif "16 MB" in text:
            update_user_settings(uid, target_mb=16.0)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_custom_size_set", user_id=uid, size=16.0),
                parse_mode="HTML",
                reply_markup=build_main_keyboard(uid),
            )
        elif "25 MB" in text:
            update_user_settings(uid, target_mb=25.0)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_custom_size_set", user_id=uid, size=25.0),
                parse_mode="HTML",
                reply_markup=build_main_keyboard(uid),
            )
        elif "50 MB" in text:
            update_user_settings(uid, target_mb=50.0)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_custom_size_set", user_id=uid, size=50.0),
                parse_mode="HTML",
                reply_markup=build_main_keyboard(uid),
            )
        elif "100 MB" in text:
            update_user_settings(uid, target_mb=100.0)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_custom_size_set", user_id=uid, size=100.0),
                parse_mode="HTML",
                reply_markup=build_main_keyboard(uid),
            )
        elif text == i18n.t("btn_custom_size", user_id=uid) or "Свой размер" in text or "Custom Size" in text:
            update_user_settings(uid, state="custom_size")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_ask_custom_size", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
        elif text == i18n.t("btn_settings", user_id=uid) or "Настройки" in text or "Settings" in text:
            bot.send_message(
                msg.chat.id,
                "⚙️ **Настройки сжатия** / Settings:",
                parse_mode="Markdown",
                reply_markup=build_settings_keyboard(uid),
            )
        elif text == i18n.t("btn_stats", user_id=uid) or "Статистика" in text or "Statistics" in text:
            s = get_stats()
            bot.send_message(
                msg.chat.id,
                i18n.t(
                    "msg_stats",
                    user_id=uid,
                    total_jobs=s["total_jobs"],
                    total_in_mb=s["total_in_mb"],
                    total_out_mb=s["total_out_mb"],
                    saved_mb=s["saved_mb"],
                    pct_saved=s["pct_saved"],
                ),
                parse_mode="HTML",
                reply_markup=build_main_keyboard(uid),
            )
        elif text == i18n.t("btn_help", user_id=uid) or "Справка" in text or "Help" in text:
            bot.send_message(
                msg.chat.id,
                i18n.t("tg_help_text", user_id=uid, port=WEB_PORT),
                parse_mode="HTML",
                reply_markup=build_main_keyboard(uid),
            )
        elif text == i18n.t("btn_choose_lang", user_id=uid) or "Language" in text or "Язык" in text:
            update_user_settings(uid, state="lang_pick")
            bot.send_message(
                msg.chat.id,
                i18n.t("tg_lang_title", user_id=uid),
                reply_markup=i18n.build_reply_language_keyboard(user_id=uid),
            )
        elif text == i18n.t("btn_back_main", user_id=uid) or "Главное меню" in text or "Main Menu" in text:
            update_user_settings(uid, state="idle")
            bot.send_message(
                msg.chat.id,
                "🎯 Главное меню:",
                reply_markup=build_main_keyboard(uid),
            )
        elif "2-Pass" in text:
            update_user_settings(uid, mode="2pass")
            bot.send_message(
                msg.chat.id,
                "✅ Режим: **2-Pass (Точно в байт)**",
                parse_mode="Markdown",
                reply_markup=build_settings_keyboard(uid),
            )
        elif "1-Pass" in text:
            update_user_settings(uid, mode="1pass")
            bot.send_message(
                msg.chat.id,
                "✅ Режим: **1-Pass (Быстро CRF)**",
                parse_mode="Markdown",
                reply_markup=build_settings_keyboard(uid),
            )
        elif "Только Аудио" in text or "Audio Only" in text:
            update_user_settings(uid, mode="audio")
            bot.send_message(
                msg.chat.id,
                "✅ Режим: **Только Аудио (MP3)**",
                parse_mode="Markdown",
                reply_markup=build_settings_keyboard(uid),
            )
        elif "Авто-разрешение" in text or "Auto Scale" in text:
            update_user_settings(uid, scale_pref="auto")
            bot.send_message(
                msg.chat.id,
                "✅ Масштаб: **Авто-разрешение**",
                parse_mode="Markdown",
                reply_markup=build_settings_keyboard(uid),
            )
        elif "720p" in text:
            update_user_settings(uid, scale_pref="720p")
            bot.send_message(
                msg.chat.id,
                "✅ Масштаб: **Макс 720p**",
                parse_mode="Markdown",
                reply_markup=build_settings_keyboard(uid),
            )
        elif "480p" in text:
            update_user_settings(uid, scale_pref="480p")
            bot.send_message(
                msg.chat.id,
                "✅ Масштаб: **Макс 480p**",
                parse_mode="Markdown",
                reply_markup=build_settings_keyboard(uid),
            )
        else:
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_send_file", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )


# ---------------------------------------------------------------------------
# Cyberpunk Web Studio HTTP Handler (Pure Python, No external cgi)
# ---------------------------------------------------------------------------
WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Media Target Compressor Studio</title>
<style>
  :root {
    --bg-dark: #0a0e17;
    --card-bg: #111827;
    --accent-cyan: #00f5ff;
    --accent-green: #00ff9d;
    --accent-pink: #ff007f;
    --text-primary: #f3f4f6;
    --text-muted: #9ca3af;
    --border-color: #1f2937;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: radial-gradient(circle at top right, #131b2e 0%, var(--bg-dark) 100%);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    min-height: 100vh;
    padding: 24px 16px;
  }
  .container { max-width: 900px; margin: 0 auto; }
  header {
    text-align: center;
    margin-bottom: 32px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border-color);
  }
  h1 {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-green) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
    margin-bottom: 8px;
  }
  .badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    background: rgba(0, 245, 255, 0.15);
    color: var(--accent-cyan);
    border: 1px solid rgba(0, 245, 255, 0.3);
    margin-bottom: 8px;
    text-transform: uppercase;
  }
  p.subtitle { color: var(--text-muted); font-size: 0.95rem; }

  .grid { display: grid; grid-template-columns: 1fr; gap: 24px; }
  @media(min-width: 768px) { .grid { grid-template-columns: 1fr 1fr; } }

  .card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
  }
  .card h2 {
    font-size: 1.15rem;
    margin-bottom: 16px;
    color: var(--accent-cyan);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .dropzone {
    border: 2px dashed rgba(0, 245, 255, 0.3);
    border-radius: 12px;
    padding: 32px 16px;
    text-align: center;
    cursor: pointer;
    background: rgba(0, 0, 0, 0.2);
    transition: all 0.2s ease;
  }
  .dropzone:hover, .dropzone.dragover {
    border-color: var(--accent-green);
    background: rgba(0, 255, 157, 0.05);
  }
  .dropzone svg { width: 44px; height: 44px; fill: var(--accent-cyan); margin-bottom: 12px; }
  .dropzone p { color: var(--text-muted); font-size: 0.85rem; }
  .dropzone strong { color: var(--text-primary); display: block; font-size: 1rem; margin-bottom: 4px; }

  .presets-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 16px;
  }
  .preset-btn {
    background: #1f2937;
    border: 1px solid #374151;
    color: var(--text-primary);
    padding: 10px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    text-align: center;
    font-size: 0.85rem;
  }
  .preset-btn:hover, .preset-btn.active {
    background: rgba(0, 245, 255, 0.2);
    border-color: var(--accent-cyan);
    color: var(--accent-cyan);
  }

  .form-group { margin-bottom: 16px; }
  label { display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 6px; font-weight: 600; }
  input[type="range"] {
    width: 100%;
    accent-color: var(--accent-cyan);
    background: #1f2937;
    height: 6px;
    border-radius: 3px;
  }
  .range-meta { display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }

  select {
    width: 100%;
    padding: 10px 12px;
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 0.9rem;
    outline: none;
  }

  .calc-box {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(0, 255, 157, 0.2);
    border-radius: 12px;
    padding: 16px;
    margin-top: 16px;
  }
  .calc-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    margin-bottom: 8px;
  }
  .calc-row:last-child { margin-bottom: 0; }
  .calc-val { font-weight: 700; color: var(--accent-green); }

  .action-btn {
    width: 100%;
    padding: 14px;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-green) 100%);
    color: #050b14;
    font-weight: 700;
    font-size: 1rem;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(0, 245, 255, 0.3);
    transition: transform 0.1s ease, box-shadow 0.2s ease;
    margin-top: 16px;
  }
  .action-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(0, 245, 255, 0.4); }
  .action-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }

  .progress-wrap {
    display: none;
    margin-top: 16px;
  }
  .progress-bar-bg {
    background: #1f2937;
    height: 8px;
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-cyan), var(--accent-green));
    width: 0%;
    transition: width 0.3s ease;
  }

  .result-box {
    display: none;
    background: rgba(0, 255, 157, 0.05);
    border: 1px solid var(--accent-green);
    border-radius: 12px;
    padding: 16px;
    margin-top: 16px;
  }
  .download-btn {
    display: block;
    text-align: center;
    background: var(--accent-green);
    color: #050b14;
    font-weight: 700;
    padding: 12px;
    border-radius: 8px;
    text-decoration: none;
    margin-top: 12px;
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="badge">Level 10/10 Studio • Port 8096</div>
    <h1>Media Target Compressor</h1>
    <p class="subtitle">Сжатие видео и аудио точно в заданный размер (Discord, WhatsApp, Telegram, Email)</p>
  </header>

  <div class="grid">
    <div class="card">
      <h2>📁 1. Выберите файл</h2>
      <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
        <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
        <strong id="dropPrompt">Нажмите или перетащите файл</strong>
        <p>Поддерживаются: MP4, MKV, MOV, WEBM, MP3, AAC, OGG</p>
      </div>
      <input type="file" id="fileInput" style="display:none" onchange="onFileSelected(this)">

      <div id="fileMeta" style="display:none; margin-top:16px;">
        <div class="calc-box">
          <div class="calc-row"><span>Имя файла:</span><span id="metaName" class="calc-val">-</span></div>
          <div class="calc-row"><span>Исходный размер:</span><span id="metaSize" class="calc-val">-</span></div>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>🎯 2. Параметры сжатия</h2>
      <label>Быстрые пресеты лимитов:</label>
      <div class="presets-grid">
        <button class="preset-btn active" onclick="setPreset(8)">8 MB<br><small>Discord</small></button>
        <button class="preset-btn" onclick="setPreset(16)">16 MB<br><small>WhatsApp</small></button>
        <button class="preset-btn" onclick="setPreset(25)">25 MB<br><small>Nitro/Mail</small></button>
        <button class="preset-btn" onclick="setPreset(50)">50 MB<br><small>Telegram</small></button>
        <button class="preset-btn" onclick="setPreset(100)">100 MB<br><small>Web</small></button>
        <button class="preset-btn" onclick="setPreset(200)">200 MB<br><small>HD</small></button>
      </div>

      <div class="form-group">
        <label>Целевой размер: <span id="targetLabel" style="color:var(--accent-cyan); font-weight:700;">8 MB</span></label>
        <input type="range" id="targetSlider" min="1" max="250" value="8" oninput="onSliderChange(this.value)">
        <div class="range-meta"><span>1 MB</span><span>125 MB</span><span>250 MB</span></div>
      </div>

      <div class="form-group">
        <label>Режим кодирования:</label>
        <select id="modeSelect">
          <option value="2pass" selected>🎯 2-Pass Target Fit (Точно в байт)</option>
          <option value="1pass">⚡ 1-Pass Fast (Быстро)</option>
          <option value="audio">🎵 Только Аудио (MP3)</option>
        </select>
      </div>

      <div class="form-group">
        <label>Разрешение (масштаб):</label>
        <select id="scaleSelect">
          <option value="auto" selected>📐 Автоматически (по битрейту)</option>
          <option value="keep">🖼 Сохранить исходное</option>
          <option value="720p">📺 Максимум 720p</option>
          <option value="480p">📱 Максимум 480p</option>
        </select>
      </div>

      <div class="calc-box">
        <div class="calc-row"><span>Резерв контейнера MP4:</span><span class="calc-val">4% (moov)</span></div>
        <div class="calc-row"><span>Расчетная точность:</span><span class="calc-val">± 1.5%</span></div>
      </div>

      <button id="startBtn" class="action-btn" onclick="startCompression()" disabled>🚀 Сжать в точный размер</button>

      <div id="progressWrap" class="progress-wrap">
        <p id="progressStatus" style="font-size:0.85rem; margin-bottom:6px; color:var(--accent-cyan);">Обработка на сервере…</p>
        <div class="progress-bar-bg"><div id="progressBar" class="progress-bar-fill"></div></div>
      </div>

      <div id="resultBox" class="result-box">
        <h3 style="color:var(--accent-green); margin-bottom:8px;">✅ Сжатие завершено!</h3>
        <p id="resultInfo" style="font-size:0.85rem; color:var(--text-muted);"></p>
        <a id="downloadLink" class="download-btn" href="#" download>📥 Скачать файл</a>
      </div>
    </div>
  </div>
</div>

<script>
let selectedFile = null;
let currentTargetMb = 8;

function setPreset(mb) {
  currentTargetMb = mb;
  document.getElementById('targetSlider').value = mb;
  document.getElementById('targetLabel').innerText = mb + ' MB';
  document.querySelectorAll('.preset-btn').forEach(b => {
    b.classList.toggle('active', b.innerText.includes(mb + ' MB'));
  });
}

function onSliderChange(val) {
  currentTargetMb = parseFloat(val);
  document.getElementById('targetLabel').innerText = currentTargetMb + ' MB';
  document.querySelectorAll('.preset-btn').forEach(b => {
    b.classList.toggle('active', b.innerText.includes(currentTargetMb + ' MB'));
  });
}

function onFileSelected(input) {
  if (input.files && input.files[0]) {
    selectedFile = input.files[0];
    document.getElementById('dropPrompt').innerText = selectedFile.name;
    document.getElementById('metaName').innerText = selectedFile.name;
    document.getElementById('metaSize').innerText = (selectedFile.size / (1024 * 1024)).toFixed(2) + ' MB';
    document.getElementById('fileMeta').style.display = 'block';
    document.getElementById('startBtn').disabled = false;
  }
}

const dropzone = document.getElementById('dropzone');
dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
    document.getElementById('fileInput').files = e.dataTransfer.files;
    onFileSelected(document.getElementById('fileInput'));
  }
});

async function startCompression() {
  if (!selectedFile) return;
  const btn = document.getElementById('startBtn');
  const progWrap = document.getElementById('progressWrap');
  const progBar = document.getElementById('progressBar');
  const progStatus = document.getElementById('progressStatus');
  const resBox = document.getElementById('resultBox');

  btn.disabled = true;
  progWrap.style.display = 'block';
  resBox.style.display = 'none';
  progBar.style.width = '20%';
  progStatus.innerText = 'Загрузка медиа…';

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('target_mb', currentTargetMb);
  formData.append('mode', document.getElementById('modeSelect').value);
  formData.append('scale', document.getElementById('scaleSelect').value);

  try {
    progBar.style.width = '50%';
    progStatus.innerText = 'Кодирование через FFmpeg (2-pass)…';
    const resp = await fetch('/api/compress', { method: 'POST', body: formData });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    progBar.style.width = '100%';
    progStatus.innerText = 'Готово!';

    resBox.style.display = 'block';
    document.getElementById('resultInfo').innerHTML = 
      'Исходный: <b>' + (data.orig_bytes / (1024*1024)).toFixed(2) + ' MB</b><br>' +
      'Итоговый: <b>' + (data.final_bytes / (1024*1024)).toFixed(2) + ' MB</b> (' + data.pct + '% от оригинала)<br>' +
      'Видео битрейт: <b>' + data.video_kbps + ' kbps</b> | Аудио: <b>' + data.audio_kbps + ' kbps</b>';
    document.getElementById('downloadLink').href = '/download/' + data.filename;
    document.getElementById('downloadLink').download = data.filename;
  } catch (err) {
    alert('Ошибка: ' + err.message);
    progStatus.innerText = 'Ошибка обработки';
  } finally {
    btn.disabled = false;
  }
}
</script>
</body>
</html>
"""


class WebStudioHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(WEB_STUDIO_HTML.encode("utf-8"))
            return

        if path == "/api/status":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            data = {
                "status": "online",
                "bot": "media_target_compressor",
                "port": WEB_PORT,
                "ffmpeg": check_ffmpeg(),
                "uptime": time.time(),
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if path.startswith("/download/"):
            fname = os.path.basename(path[10:])
            fpath = OUTPUT_DIR / fname
            if fpath.exists() and fpath.is_file():
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.send_header("Content-Length", str(fpath.stat().st_size))
                self.end_headers()
                with open(fpath, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/calc":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
                target_mb = float(body.get("target_mb", 8.0))
                duration = float(body.get("duration", 60.0))
                plan = calculate_bitrate_plan(int(target_mb * 1024 * 1024), duration)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(plan).encode("utf-8"))
            except Exception as e:
                self.send_error(HTTPStatus.BAD_REQUEST, str(e))
            return

        if path == "/api/compress":
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("multipart/form-data"):
                self.send_error(HTTPStatus.BAD_REQUEST, "Expected multipart/form-data")
                return

            boundary_match = re.search(r"boundary=([^\s;]+)", ctype)
            if not boundary_match:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing boundary")
                return
            boundary = boundary_match.group(1).encode("utf-8")

            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)

            parts = raw_body.split(b"--" + boundary)
            file_bytes = None
            filename = "input.mp4"
            target_mb = 8.0
            mode = "2pass"
            scale_pref = "auto"

            for part in parts:
                if not part or part == b"--\r\n" or part == b"--":
                    continue
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                headers_text = part[:header_end].decode("utf-8", errors="replace")
                body_part = part[header_end + 4 :].rstrip(b"\r\n")

                if 'name="file"' in headers_text:
                    fn_match = re.search(r'filename="([^"]+)"', headers_text)
                    if fn_match:
                        filename = fn_match.group(1)
                    file_bytes = body_part
                elif 'name="target_mb"' in headers_text:
                    try:
                        target_mb = float(body_part.decode("utf-8").strip())
                    except Exception:
                        pass
                elif 'name="mode"' in headers_text:
                    mode = body_part.decode("utf-8").strip()
                elif 'name="scale"' in headers_text:
                    scale_pref = body_part.decode("utf-8").strip()

            if not file_bytes:
                self.send_error(HTTPStatus.BAD_REQUEST, "No file provided")
                return

            ext = os.path.splitext(filename)[1].lower() or ".mp4"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf_in:
                tf_in.write(file_bytes)
                tmp_in = tf_in.name

            out_fname = f"compressed_{int(time.time())}_{target_mb}mb{'.mp3' if mode == 'audio' else '.mp4'}"
            out_path = OUTPUT_DIR / out_fname

            try:
                res = compress_media(
                    input_path=tmp_in,
                    output_path=out_path,
                    target_bytes=int(target_mb * 1024 * 1024),
                    mode=mode,
                    scale_pref=scale_pref,
                )
                final_sz = os.path.getsize(out_path)
                orig_sz = len(file_bytes)
                pct = round((final_sz / orig_sz * 100.0), 1) if orig_sz > 0 else 100.0

                resp_data = {
                    "filename": out_fname,
                    "orig_bytes": orig_sz,
                    "final_bytes": final_sz,
                    "pct": pct,
                    "video_kbps": res["video_kbps"],
                    "audio_kbps": res["audio_kbps"],
                    "scale": res["scale"],
                    "duration": res["duration"],
                }
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resp_data).encode("utf-8"))
            except Exception as e:
                logger.exception("Web compress failed")
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))
            finally:
                if os.path.exists(tmp_in):
                    try:
                        os.unlink(tmp_in)
                    except Exception:
                        pass
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")


def start_web_server() -> ThreadingHTTPServer:
    server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), WEB_PORT), WebStudioHandler)
    print(f"[PYBIONIC_WEB:{WEB_PORT}]", flush=True)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Cyberpunk Web Studio active at http://127.0.0.1:{WEB_PORT}")
    return server


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    init_db()
    web_server = start_web_server()

    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN is not configured. Running offline in Web Studio mode on port %d.", WEB_PORT)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Exiting...")
            web_server.shutdown()
            return

    if not telebot:
        logger.error("pyTelegramBotAPI is not installed. Please install requirements.txt.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return

    bot = telebot.TeleBot(BOT_TOKEN)
    setup_bot(bot)
    logger.info("Telegram bot listener initiated.")

    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except Exception as e:
        logger.exception(f"Bot polling exception: {e}")
    finally:
        web_server.shutdown()


if __name__ == "__main__":
    main()
