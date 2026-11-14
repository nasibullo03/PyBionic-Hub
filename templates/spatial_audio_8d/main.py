#!/usr/bin/env python3
"""8D Spatial Audio Studio (BotHub Level 10/10)
360° binaural spatial audio generator with rotating sound, acoustic hall modeling, and visual radar.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- Multiple orbit speeds: Slow (10s), Standard 8D (6s), Fast (3s), Storm (1.5s).
- Multiple trajectories: 360° Circular Orbit, Infinity (8) Lissajous.
- Acoustic halls: Club with bass boost, Cathedral, Open Space.
- Standalone Cyberpunk Web Studio on port 8098 with live rotating 2D Radar Canvas.
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
from typing import Any
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
logger = logging.getLogger("spatial_audio_8d")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8098"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "spatial_audio.db"
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
                speed_hz REAL DEFAULT 0.166,
                speed_name TEXT DEFAULT 'norm',
                trajectory TEXT DEFAULT 'circle',
                hall TEXT DEFAULT 'club',
                format_out TEXT DEFAULT 'audio',
                state TEXT DEFAULT 'idle',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spatial_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                speed_hz REAL,
                trajectory TEXT,
                hall TEXT,
                format_out TEXT,
                duration_sec REAL,
                file_bytes INTEGER,
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
            INSERT INTO user_settings (user_id, speed_hz, speed_name, trajectory, hall, format_out, state, updated_at)
            VALUES (?, 0.166, 'norm', 'circle', 'club', 'audio', 'idle', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {
            "user_id": uid,
            "speed_hz": 0.166,
            "speed_name": "norm",
            "trajectory": "circle",
            "hall": "club",
            "format_out": "audio",
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
            SET speed_hz = ?, speed_name = ?, trajectory = ?, hall = ?, format_out = ?, state = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                float(st["speed_hz"]),
                str(st["speed_name"]),
                str(st["trajectory"]),
                str(st["hall"]),
                str(st["format_out"]),
                str(st["state"]),
                int(st["updated_at"]),
                uid,
            ),
        )
        conn.commit()
    return st


def record_spatial_job(
    user_id: int | str,
    speed_hz: float,
    trajectory: str,
    hall: str,
    format_out: str,
    duration_sec: float,
    file_bytes: int,
) -> None:
    uid = str(user_id).strip()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO spatial_jobs (user_id, speed_hz, trajectory, hall, format_out, duration_sec, file_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                speed_hz,
                trajectory,
                hall,
                format_out,
                duration_sec,
                file_bytes,
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
                COALESCE(SUM(duration_sec), 0.0) as total_dur
            FROM spatial_jobs
            """
        ).fetchone()
        total_jobs = row["total_jobs"] if row else 0
        total_dur = row["total_dur"] if row else 0.0
        m = int(total_dur // 60)
        s = int(total_dur % 60)
        return {
            "total_jobs": total_jobs,
            "total_duration": f"{m}m {s}s",
        }


# ---------------------------------------------------------------------------
# FFmpeg 8D Spatial Audio Engine
# ---------------------------------------------------------------------------
def check_ffmpeg() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def get_audio_duration(file_path: str | Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        str(file_path),
    ]
    try:
        out = subprocess.check_output(cmd)
        data = json.loads(out)
        return float(data.get("format", {}).get("duration", 0.0))
    except Exception:
        return 0.0


def process_8d_audio(
    input_path: str | Path,
    output_path: str | Path,
    speed_hz: float = 0.166,
    trajectory: str = "circle",
    hall: str = "club",
    format_out: str = "audio",
) -> dict[str, Any]:
    dur = get_audio_duration(input_path)
    in_p = str(input_path)
    out_p = str(output_path)

    hz = max(0.02, min(speed_hz, 2.0))

    if trajectory == "infinity":
        l_expr = f"0.15+0.85*(0.5+0.5*sin(2*PI*{hz}*t))"
        r_expr = f"0.15+0.85*(0.5+0.5*sin(4*PI*{hz}*t))"
    else:
        l_expr = f"0.15+0.85*(0.5+0.5*sin(2*PI*{hz}*t))"
        r_expr = f"0.15+0.85*(0.5+0.5*cos(2*PI*{hz}*t))"

    if hall == "cathedral":
        hall_filter = "aecho=0.8:0.9:800|1200:0.35|0.3"
    elif hall == "open":
        hall_filter = "aecho=0.8:0.8:30|50:0.15|0.1"
    else:
        hall_filter = "aecho=0.8:0.88:40|60:0.25|0.2,equalizer=f=60:t=q:w=1:g=3"

    af_complex = (
        f"[0:a]asplit=2[l_in][r_in];"
        f"[l_in]volume=eval=frame:volume='{l_expr}'[l_mod];"
        f"[r_in]volume=eval=frame:volume='{r_expr}'[r_mod];"
        f"[l_mod][r_mod]amerge=inputs=2,extrastereo=m=1.8,{hall_filter}"
    )

    cmd = ["ffmpeg", "-y", "-i", in_p, "-filter_complex", af_complex]

    if format_out == "voice":
        cmd.extend(["-c:a", "libopus", "-b:a", "48k", "-vbr", "on", out_p])
    else:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k", out_p])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg 8D filter failed: {res.stderr[-300:]}")

    final_sz = os.path.getsize(out_p) if os.path.exists(out_p) else 0
    return {
        "speed_hz": hz,
        "trajectory": trajectory,
        "hall": hall,
        "format_out": format_out,
        "duration": dur,
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
    b_slw = types.KeyboardButton(i18n.t("btn_speed_slow", user_id=user_id))
    b_nrm = types.KeyboardButton(i18n.t("btn_speed_norm", user_id=user_id))
    b_fst = types.KeyboardButton(i18n.t("btn_speed_fast", user_id=user_id))
    b_hyp = types.KeyboardButton(i18n.t("btn_speed_hyper", user_id=user_id))
    b_crc = types.KeyboardButton(i18n.t("btn_traj_circle", user_id=user_id))
    b_inf = types.KeyboardButton(i18n.t("btn_traj_infinity", user_id=user_id))
    b_set = types.KeyboardButton(i18n.t("btn_settings", user_id=user_id))
    b_sta = types.KeyboardButton(i18n.t("btn_stats", user_id=user_id))
    b_hlp = types.KeyboardButton(i18n.t("btn_help", user_id=user_id))

    kb.add(b_slw, b_nrm)
    kb.add(b_fst, b_hyp)
    kb.add(b_crc, b_inf)
    kb.add(b_set, b_sta, b_hlp)
    return kb


def build_settings_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_opn = types.KeyboardButton(i18n.t("btn_hall_open", user_id=user_id))
    b_clb = types.KeyboardButton(i18n.t("btn_hall_club", user_id=user_id))
    b_cat = types.KeyboardButton(i18n.t("btn_hall_cathedral", user_id=user_id))
    b_aud = types.KeyboardButton(i18n.t("btn_format_audio", user_id=user_id))
    b_vce = types.KeyboardButton(i18n.t("btn_format_voice", user_id=user_id))
    b_lng = types.KeyboardButton(i18n.t("btn_choose_lang", user_id=user_id))
    b_bck = types.KeyboardButton(i18n.t("btn_back_main", user_id=user_id))

    kb.add(b_opn, b_clb)
    kb.add(b_cat, b_aud)
    kb.add(b_vce, b_lng)
    kb.add(b_bck)
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
            speed=st["speed_name"],
            traj=st["trajectory"],
            hall=st["hall"],
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
            total_duration=s["total_duration"],
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

    @bot.message_handler(content_types=["audio", "voice", "document"])
    def on_audio_received(msg: Any) -> None:
        uid = msg.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            bot.reply_to(msg, "Access denied.")
            return

        file_obj = None
        ext = ".mp3"
        if msg.audio:
            file_obj = msg.audio
            ext = ".mp3"
        elif msg.voice:
            file_obj = msg.voice
            ext = ".ogg"
        elif msg.document:
            name = (msg.document.file_name or "").lower()
            if any(name.endswith(e) for e in [".mp3", ".ogg", ".wav", ".m4a", ".flac", ".aac"]):
                file_obj = msg.document
                ext = os.path.splitext(name)[1]

        if not file_obj:
            bot.reply_to(msg, i18n.t("msg_send_audio", user_id=uid))
            return

        def worker() -> None:
            st = get_user_settings(uid)
            sp_hz = float(st["speed_hz"])
            sp_name = st["speed_name"]
            traj = st["trajectory"]
            hall = st["hall"]
            fmt_out = st["format_out"]

            status_msg = bot.send_message(
                msg.chat.id,
                i18n.t("msg_processing", user_id=uid, speed=sp_name, hall=hall),
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

                out_ext = ".ogg" if fmt_out == "voice" else ".mp3"
                with tempfile.NamedTemporaryFile(suffix=out_ext, delete=False) as tf_out:
                    tmp_out = tf_out.name

                res = process_8d_audio(
                    input_path=tmp_in,
                    output_path=tmp_out,
                    speed_hz=sp_hz,
                    trajectory=traj,
                    hall=hall,
                    format_out=fmt_out,
                )

                record_spatial_job(
                    user_id=uid,
                    speed_hz=sp_hz,
                    trajectory=traj,
                    hall=hall,
                    format_out=fmt_out,
                    duration_sec=res["duration"],
                    file_bytes=res["final_bytes"],
                )

                caption = i18n.t(
                    "msg_success",
                    user_id=uid,
                    speed=sp_name,
                    traj=traj,
                    hall=hall,
                    duration=format_duration(res["duration"]),
                    size=format_bytes(res["final_bytes"]),
                )

                with open(tmp_out, "rb") as out_f:
                    if fmt_out == "voice":
                        bot.send_voice(
                            msg.chat.id,
                            out_f,
                            caption=caption,
                            parse_mode="HTML",
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
                logger.exception("8D spatial worker failed")
                bot.send_message(
                    msg.chat.id,
                    f"❌ Ошибка 8D-обработки: {e}",
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

        # Language selection
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

        # Speed presets
        if "10с" in text or "Slow" in text or "Медленно" in text:
            update_user_settings(uid, speed_hz=0.1, speed_name="10s (0.1 Hz)")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_speed_selected", user_id=uid, speed="10с / 0.1 Гц"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "6с" in text or "Стандарт" in text or "Standard" in text:
            update_user_settings(uid, speed_hz=0.166, speed_name="6s (0.166 Hz)")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_speed_selected", user_id=uid, speed="6с / 0.166 Гц"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "3с" in text or "Быстро" in text or "Fast" in text:
            update_user_settings(uid, speed_hz=0.333, speed_name="3s (0.333 Hz)")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_speed_selected", user_id=uid, speed="3с / 0.333 Гц"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "1.5с" in text or "Шторм" in text or "Storm" in text:
            update_user_settings(uid, speed_hz=0.666, speed_name="1.5s (0.666 Hz)")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_speed_selected", user_id=uid, speed="1.5с / 0.666 Гц"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "Круговая" in text or "Circle" in text:
            update_user_settings(uid, trajectory="circle")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_traj_selected", user_id=uid, traj="Круговая 360°"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "Восьмёрка" in text or "Infinity" in text:
            update_user_settings(uid, trajectory="infinity")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_traj_selected", user_id=uid, traj="Восьмёрка (Лиссажу)"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "Открытое" in text or "Open" in text:
            update_user_settings(uid, hall="open")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_hall_selected", user_id=uid, hall="Открытое поле"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "Клуб" in text or "Club" in text:
            update_user_settings(uid, hall="club")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_hall_selected", user_id=uid, hall="Ночной Клуб (+Bass)"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "Собор" in text or "Cathedral" in text:
            update_user_settings(uid, hall="cathedral")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_hall_selected", user_id=uid, hall="Соборный зал"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "MP3 (320k)" in text:
            update_user_settings(uid, format_out="audio")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_format_selected", user_id=uid, format="MP3 Audio Track (320 kbps)"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "Voice Note (OGG)" in text:
            update_user_settings(uid, format_out="voice")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_format_selected", user_id=uid, format="Telegram Voice Note (OGG)"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif text == i18n.t("btn_settings", user_id=uid) or "Настройки" in text or "Settings" in text:
            bot.send_message(
                msg.chat.id,
                "⚙️ **Настройки 8D Spatial Audio** / Settings:",
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
                    total_duration=s["total_duration"],
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
                "🎧 Главное меню 8D Spatial Audio:",
                reply_markup=build_main_keyboard(uid),
            )
        else:
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_send_audio", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )


# ---------------------------------------------------------------------------
# Cyberpunk Web Studio HTTP Handler (Interactive 2D/3D Radar Canvas)
# ---------------------------------------------------------------------------
WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>8D Spatial Audio Studio</title>
<style>
  :root {
    --bg-dark: #070a13;
    --card-bg: #0f172a;
    --accent-cyan: #00f5ff;
    --accent-violet: #8b5cf6;
    --text-primary: #f8fafc;
    --text-muted: #94a3b8;
    --border-color: #1e293b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: radial-gradient(circle at top right, #1e1b4b 0%, var(--bg-dark) 100%);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh;
    padding: 24px 16px;
  }
  .container { max-width: 900px; margin: 0 auto; }
  header {
    text-align: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-color);
  }
  h1 {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-violet) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
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

  .radar-wrap {
    text-align: center;
    position: relative;
    padding: 12px;
  }
  canvas#radarCanvas {
    background: #090e1a;
    border-radius: 50%;
    border: 2px solid rgba(0, 245, 255, 0.3);
    box-shadow: 0 0 30px rgba(0, 245, 255, 0.15);
  }

  .form-group { margin-bottom: 16px; }
  label { display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 6px; font-weight: 600; }
  select {
    width: 100%;
    padding: 10px 12px;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 0.9rem;
    outline: none;
  }

  .dropzone {
    border: 2px dashed rgba(0, 245, 255, 0.3);
    border-radius: 12px;
    padding: 24px 16px;
    text-align: center;
    cursor: pointer;
    background: rgba(0, 0, 0, 0.2);
    transition: all 0.2s;
    margin-bottom: 16px;
  }
  .dropzone:hover { border-color: var(--accent-cyan); }

  .action-btn {
    width: 100%;
    padding: 14px;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-violet) 100%);
    color: #070a13;
    font-weight: 700;
    font-size: 1rem;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(0, 245, 255, 0.3);
    transition: transform 0.1s ease;
  }
  .action-btn:hover { transform: translateY(-1px); }
  .action-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  audio { width: 100%; margin-top: 16px; border-radius: 8px; }
  .download-btn {
    display: block;
    text-align: center;
    background: var(--accent-cyan);
    color: #070a13;
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
    <div class="badge">Spatial Studio • Port 8098</div>
    <h1>8D Spatial Audio Studio</h1>
    <p class="subtitle">360° бинауральное панорамирование, орбитальный радар и акустика зала</p>
  </header>

  <div class="grid">
    <div class="card">
      <h2>🛰 Интерактивный 8D Радар</h2>
      <div class="radar-wrap">
        <canvas id="radarCanvas" width="260" height="260"></canvas>
      </div>
      <p style="text-align:center; font-size:0.8rem; color:var(--text-muted); margin-top:8px;">
        Голова слушателя по центру • Зеленый маркер: орбитальная траектория звука
      </p>
    </div>

    <div class="card">
      <h2>🎛 Настройка 8D параметров</h2>
      <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
        <strong id="filePrompt">Нажмите или перетащите аудиофайл</strong>
        <p style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">MP3, WAV, FLAC, OGG, AAC</p>
      </div>
      <input type="file" id="fileInput" accept="audio/*,video/*" onchange="onFileSelected(this)" style="display:none">

      <div class="form-group">
        <label>Скорость вращения орбиты:</label>
        <select id="speedSelect" onchange="updateRadarSpeed(this.value)">
          <option value="0.1">🌊 Медленная (10 сек на оборот / 0.1 Гц)</option>
          <option value="0.166" selected>🎧 Стандарт 8D (6 сек на оборот / 0.166 Гц)</option>
          <option value="0.333">⚡ Быстрая (3 сек на оборот / 0.333 Гц)</option>
          <option value="0.666">🌪 Шторм (1.5 сек на оборот / 0.666 Гц)</option>
        </select>
      </div>

      <div class="form-group">
        <label>Траектория движения звука:</label>
        <select id="trajSelect" onchange="updateRadarTraj(this.value)">
          <option value="circle" selected>🔄 Круговая 360° орбита</option>
          <option value="infinity">♾ Восьмёрка (Лиссажу перед-зад-лево-право)</option>
        </select>
      </div>

      <div class="form-group">
        <label>Акустическое пространство:</label>
        <select id="hallSelect">
          <option value="club" selected>🏢 Ночной клуб (+Bass Boost)</option>
          <option value="cathedral">🏛 Кафедральный собор (Глубокое эхо)</option>
          <option value="open">🌌 Открытое поле (Мягкое окружение)</option>
        </select>
      </div>

      <button id="renderBtn" class="action-btn" onclick="render8DAudio()" disabled>🎧 Сгенерировать 8D Аудио</button>

      <div id="resultBox" style="display:none; margin-top:16px;">
        <h3 style="color:var(--accent-cyan); font-size:1rem; margin-bottom:8px;">✅ 8D Аудио готово:</h3>
        <audio id="audioPlayer" controls></audio>
        <a id="downloadLink" class="download-btn" href="#" download>📥 Скачать 8D Аудио (MP3 320k)</a>
      </div>
    </div>
  </div>
</div>

<script>
let currentSpeedHz = 0.166;
let currentTraj = 'circle';
let chosenFile = null;

function updateRadarSpeed(val) { currentSpeedHz = parseFloat(val); }
function updateRadarTraj(val) { currentTraj = val; }

function onFileSelected(input) {
  if (input.files && input.files[0]) {
    chosenFile = input.files[0];
    document.getElementById('filePrompt').innerText = 'Выбран: ' + chosenFile.name;
    document.getElementById('renderBtn').disabled = false;
  }
}

// Interactive Canvas Radar
const canvas = document.getElementById('radarCanvas');
const ctx = canvas.getContext('2d');
let animTime = 0;

function drawRadar() {
  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const r = 95;

  ctx.clearRect(0, 0, w, h);

  // Radar grid rings
  ctx.strokeStyle = 'rgba(0, 245, 255, 0.2)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(cx, cy, r * 0.33, 0, Math.PI * 2); ctx.stroke();
  ctx.beginPath(); ctx.arc(cx, cy, r * 0.66, 0, Math.PI * 2); ctx.stroke();
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();

  // Crosshairs
  ctx.beginPath();
  ctx.moveTo(cx, cy - r); ctx.lineTo(cx, cy + r);
  ctx.moveTo(cx - r, cy); ctx.lineTo(cx + r, cy);
  ctx.stroke();

  // Listener Head Center (Headphones Icon)
  ctx.fillStyle = '#f8fafc';
  ctx.beginPath(); ctx.arc(cx, cy, 14, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#00f5ff';
  ctx.beginPath(); ctx.arc(cx - 15, cy, 5, 0, Math.PI * 2); ctx.fill(); // Left Ear
  ctx.beginPath(); ctx.arc(cx + 15, cy, 5, 0, Math.PI * 2); ctx.fill(); // Right Ear

  // Sound source orbital position
  animTime += 0.016;
  let sx, sy;
  if (currentTraj === 'infinity') {
    const angle = 2 * Math.PI * currentSpeedHz * animTime;
    sx = cx + r * Math.sin(angle);
    sy = cy + r * 0.65 * Math.sin(2 * angle);
  } else {
    const angle = 2 * Math.PI * currentSpeedHz * animTime;
    sx = cx + r * Math.cos(angle);
    sy = cy + r * Math.sin(angle);
  }

  // Sound orb glow
  const grad = ctx.createRadialGradient(sx, sy, 2, sx, sy, 18);
  grad.addColorStop(0, '#00ff9d');
  grad.addColorStop(0.5, 'rgba(0, 245, 255, 0.6)');
  grad.addColorStop(1, 'rgba(0, 245, 255, 0)');
  ctx.fillStyle = grad;
  ctx.beginPath(); ctx.arc(sx, sy, 18, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = '#ffffff';
  ctx.beginPath(); ctx.arc(sx, sy, 4, 0, Math.PI * 2); ctx.fill();

  requestAnimationFrame(drawRadar);
}
requestAnimationFrame(drawRadar);

async function render8DAudio() {
  if (!chosenFile) return;
  const btn = document.getElementById('renderBtn');
  btn.disabled = true;
  btn.innerText = 'Рендеринг 8D-аудио…';

  const formData = new FormData();
  formData.append('file', chosenFile);
  formData.append('speed_hz', currentSpeedHz);
  formData.append('trajectory', currentTraj);
  formData.append('hall', document.getElementById('hallSelect').value);
  formData.append('format', 'audio');

  try {
    const resp = await fetch('/api/render', { method: 'POST', body: formData });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    const player = document.getElementById('audioPlayer');
    player.src = '/download/' + data.filename;
    document.getElementById('downloadLink').href = '/download/' + data.filename;
    document.getElementById('downloadLink').download = data.filename;
    document.getElementById('resultBox').style.display = 'block';
  } catch (err) {
    alert('Ошибка: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerText = '🎧 Сгенерировать 8D Аудио';
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
                "bot": "spatial_audio_8d",
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
                self.send_header("Content-Type", "audio/mpeg")
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

        if path == "/api/render":
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
            speed_hz = 0.166
            trajectory = "circle"
            hall = "club"
            fmt_out = "audio"

            for part in parts:
                if not part or part == b"--\r\n" or part == b"--":
                    continue
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                headers_text = part[:header_end].decode("utf-8", errors="replace")
                body_part = part[header_end + 4 :].rstrip(b"\r\n")

                if 'name="file"' in headers_text:
                    file_bytes = body_part
                elif 'name="speed_hz"' in headers_text:
                    try:
                        speed_hz = float(body_part.decode("utf-8").strip())
                    except Exception:
                        pass
                elif 'name="trajectory"' in headers_text:
                    trajectory = body_part.decode("utf-8").strip()
                elif 'name="hall"' in headers_text:
                    hall = body_part.decode("utf-8").strip()
                elif 'name="format"' in headers_text:
                    fmt_out = body_part.decode("utf-8").strip()

            if not file_bytes:
                self.send_error(HTTPStatus.BAD_REQUEST, "No file provided")
                return

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf_in:
                tf_in.write(file_bytes)
                tmp_in = tf_in.name

            out_fname = f"8d_audio_{trajectory}_{int(time.time())}.mp3"
            out_path = OUTPUT_DIR / out_fname

            try:
                res = process_8d_audio(
                    input_path=tmp_in,
                    output_path=out_path,
                    speed_hz=speed_hz,
                    trajectory=trajectory,
                    hall=hall,
                    format_out=fmt_out,
                )
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                data = {
                    "filename": out_fname,
                    "duration": res["duration"],
                    "final_bytes": res["final_bytes"],
                    "speed_hz": speed_hz,
                    "trajectory": trajectory,
                }
                self.wfile.write(json.dumps(data).encode("utf-8"))
            except Exception as e:
                logger.exception("Web 8D render failed")
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
    logger.info(f"Cyberpunk 8D Spatial Studio active at http://127.0.0.1:{WEB_PORT}")
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
