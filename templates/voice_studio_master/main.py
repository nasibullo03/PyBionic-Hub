#!/usr/bin/env python3
"""Voice Studio Master (BotHub Level 10/10)
Studio-grade voice post-production & vocal FX engine.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- 8 high-fidelity studio filters: Podcast Clean (EBU R128), Radio, Vocoder, Deep Pitch, Chipmunk, Cathedral, Megaphone, Lo-Fi.
- Native Telegram Voice bubble output (OGG Opus) or MP3 audio track.
- Standalone Cyberpunk Web Studio on port 8097 with in-browser microphone recording.
- 24 languages support via i18n and locales.json.
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
logger = logging.getLogger("voice_studio_master")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8097"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "voice_studio.db"
OUTPUT_DIR = DATA_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Presets & Filter Definitions
# ---------------------------------------------------------------------------
FX_PRESETS: dict[str, dict[str, str]] = {
    "podcast_clean": {
        "name_ru": "🎙 Студийный Подкаст",
        "name_en": "🎙 Studio Podcast",
        "af": "highpass=f=80,equalizer=f=1000:t=q:w=1:g=2,compand=attacks=0.05:decays=0.2:points=-80/-80|-30/-15|0/-3:gain=3,loudnorm=I=-16:TP=-1.5:LRA=11",
    },
    "radio_broadcast": {
        "name_ru": "📻 Радио Эфир",
        "name_en": "📻 Radio Broadcast",
        "af": "highpass=f=300,lowpass=f=3400,asoftclip=type=atan:threshold=0.8",
    },
    "vocoder_robot": {
        "name_ru": "🤖 Робот / Вокодер",
        "name_en": "🤖 Robot / Vocoder",
        "af": "vibrato=f=20:d=0.5,chorus=0.7:0.9:55:0.4:0.25:2",
    },
    "deep_pitch": {
        "name_ru": "👹 Глубокий Бас",
        "name_en": "👹 Deep Pitch",
        "af": "asetrate=44100*0.75,atempo=1/0.75,aresample=44100",
    },
    "chipmunk": {
        "name_ru": "🐿 Бурундук / Аниме",
        "name_en": "🐿 Chipmunk / Anime",
        "af": "asetrate=44100*1.35,atempo=1/1.35,aresample=44100",
    },
    "cathedral_reverb": {
        "name_ru": "🏛 Соборное Эхо",
        "name_en": "🏛 Cathedral Reverb",
        "af": "aecho=0.8:0.9:500|1000:0.3|0.2",
    },
    "megaphone": {
        "name_ru": "📢 Мегафон / Рация",
        "name_en": "📢 Megaphone / Walkie",
        "af": "highpass=f=500,lowpass=f=4000,volume=3dB,asoftclip=type=hard",
    },
    "lofi_tape": {
        "name_ru": "📼 Lo-Fi Кассета",
        "name_en": "📼 Lo-Fi Cassette",
        "af": "highpass=f=120,lowpass=f=7000,vibrato=f=4:d=0.1,volume=1.5",
    },
}


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
                effect TEXT DEFAULT 'podcast_clean',
                format_out TEXT DEFAULT 'voice',
                gain_db INTEGER DEFAULT 0,
                state TEXT DEFAULT 'idle',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                effect TEXT,
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
            INSERT INTO user_settings (user_id, effect, format_out, gain_db, state, updated_at)
            VALUES (?, 'podcast_clean', 'voice', 0, 'idle', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {
            "user_id": uid,
            "effect": "podcast_clean",
            "format_out": "voice",
            "gain_db": 0,
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
            SET effect = ?, format_out = ?, gain_db = ?, state = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                str(st["effect"]),
                str(st["format_out"]),
                int(st["gain_db"]),
                str(st["state"]),
                int(st["updated_at"]),
                uid,
            ),
        )
        conn.commit()
    return st


def record_voice_job(
    user_id: int | str,
    effect: str,
    format_out: str,
    duration_sec: float,
    file_bytes: int,
) -> None:
    uid = str(user_id).strip()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO voice_jobs (user_id, effect, format_out, duration_sec, file_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                effect,
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
            FROM voice_jobs
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
# FFmpeg Audio Engine
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


def process_voice_audio(
    input_path: str | Path,
    output_path: str | Path,
    effect: str = "podcast_clean",
    format_out: str = "voice",
    gain_db: int = 0,
) -> dict[str, Any]:
    dur = get_audio_duration(input_path)
    in_p = str(input_path)
    out_p = str(output_path)

    preset = FX_PRESETS.get(effect, FX_PRESETS["podcast_clean"])
    filter_chain = preset["af"]

    if gain_db != 0:
        filter_chain = f"volume={gain_db}dB,{filter_chain}"

    cmd = ["ffmpeg", "-y", "-i", in_p, "-af", filter_chain]

    if format_out == "voice":
        # Native Telegram Voice Note (OGG Opus at 48kHz mono)
        cmd.extend(["-c:a", "libopus", "-b:a", "48k", "-vbr", "on", "-ac", "1", out_p])
    else:
        # Standard MP3 Audio
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k", out_p])

    res = core.run_media(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg audio filter failed: {res.stderr[-300:]}")

    final_sz = os.path.getsize(out_p) if os.path.exists(out_p) else 0
    return {
        "effect": effect,
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
    b_pod = types.KeyboardButton(i18n.t("btn_fx_podcast", user_id=user_id))
    b_rad = types.KeyboardButton(i18n.t("btn_fx_radio", user_id=user_id))
    b_rob = types.KeyboardButton(i18n.t("btn_fx_robot", user_id=user_id))
    b_dep = types.KeyboardButton(i18n.t("btn_fx_deep", user_id=user_id))
    b_chp = types.KeyboardButton(i18n.t("btn_fx_chipmunk", user_id=user_id))
    b_rev = types.KeyboardButton(i18n.t("btn_fx_reverb", user_id=user_id))
    b_meg = types.KeyboardButton(i18n.t("btn_fx_megaphone", user_id=user_id))
    b_lof = types.KeyboardButton(i18n.t("btn_fx_lofi", user_id=user_id))
    b_set = types.KeyboardButton(i18n.t("btn_settings", user_id=user_id))
    b_sta = types.KeyboardButton(i18n.t("btn_stats", user_id=user_id))
    b_hlp = types.KeyboardButton(i18n.t("btn_help", user_id=user_id))

    kb.add(b_pod, b_rad)
    kb.add(b_rob, b_dep)
    kb.add(b_chp, b_rev)
    kb.add(b_meg, b_lof)
    kb.add(b_set, b_sta, b_hlp)
    return kb


def build_settings_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_vce = types.KeyboardButton(i18n.t("btn_format_voice", user_id=user_id))
    b_aud = types.KeyboardButton(i18n.t("btn_format_audio", user_id=user_id))
    b_gnm = types.KeyboardButton(i18n.t("btn_gain_norm", user_id=user_id))
    b_gbst = types.KeyboardButton(i18n.t("btn_gain_boost", user_id=user_id))
    b_lng = types.KeyboardButton(i18n.t("btn_choose_lang", user_id=user_id))
    b_bck = types.KeyboardButton(i18n.t("btn_back_main", user_id=user_id))

    kb.add(b_vce, b_aud)
    kb.add(b_gnm, b_gbst)
    kb.add(b_lng, b_bck)
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
        fx_name = FX_PRESETS.get(st["effect"], {}).get("name_ru", st["effect"])
        welcome = i18n.t(
            "tg_welcome",
            user_id=uid,
            effect=fx_name,
            format=st["format_out"],
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

    @bot.message_handler(content_types=["voice", "audio", "video_note", "document"])
    def on_audio_received(msg: Any) -> None:
        uid = msg.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            bot.reply_to(msg, "Access denied.")
            return

        file_obj = None
        ext = ".ogg"
        if msg.voice:
            file_obj = msg.voice
            ext = ".ogg"
        elif msg.audio:
            file_obj = msg.audio
            ext = ".mp3"
        elif msg.video_note:
            file_obj = msg.video_note
            ext = ".mp4"
        elif msg.document:
            name = (msg.document.file_name or "").lower()
            if any(name.endswith(e) for e in [".ogg", ".mp3", ".wav", ".m4a", ".flac", ".aac"]):
                file_obj = msg.document
                ext = os.path.splitext(name)[1]

        if not file_obj:
            bot.reply_to(msg, i18n.t("msg_send_voice", user_id=uid))
            return

        def worker() -> None:
            st = get_user_settings(uid)
            fx = st["effect"]
            fmt_out = st["format_out"]
            gain_db = st["gain_db"]
            fx_display = FX_PRESETS.get(fx, {}).get("name_ru", fx)

            status_msg = bot.send_message(
                msg.chat.id,
                i18n.t("msg_processing", user_id=uid, effect=fx_display),
                parse_mode="HTML",
            )

            tmp_in = None
            tmp_out = None
            try:
                data = core.download_tg_file(bot, file_obj.file_id)

                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                    tf.write(data)
                    tmp_in = tf.name

                out_ext = ".ogg" if fmt_out == "voice" else ".mp3"
                with tempfile.NamedTemporaryFile(suffix=out_ext, delete=False) as tf_out:
                    tmp_out = tf_out.name

                res = process_voice_audio(
                    input_path=tmp_in,
                    output_path=tmp_out,
                    effect=fx,
                    format_out=fmt_out,
                    gain_db=gain_db,
                )

                record_voice_job(
                    user_id=uid,
                    effect=fx,
                    format_out=fmt_out,
                    duration_sec=res["duration"],
                    file_bytes=res["final_bytes"],
                )

                caption = i18n.t(
                    "msg_success",
                    user_id=uid,
                    effect=fx_display,
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
                logger.exception("Voice worker failed")
                bot.send_message(
                    msg.chat.id,
                    f"❌ Ошибка обработки звука: {e}",
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

        # Preset selection
        fx_map = {
            "Подкаст": "podcast_clean",
            "Podcast": "podcast_clean",
            "Радио": "radio_broadcast",
            "Radio": "radio_broadcast",
            "Робот": "vocoder_robot",
            "Robot": "vocoder_robot",
            "Бас": "deep_pitch",
            "Deep": "deep_pitch",
            "Бурундук": "chipmunk",
            "Chipmunk": "chipmunk",
            "Эхо": "cathedral_reverb",
            "Reverb": "cathedral_reverb",
            "Мегафон": "megaphone",
            "Megaphone": "megaphone",
            "Lo-Fi": "lofi_tape",
            "Кассета": "lofi_tape",
        }
        for kw, fx_key in fx_map.items():
            if kw in text:
                update_user_settings(uid, effect=fx_key)
                fx_name = FX_PRESETS[fx_key]["name_ru"]
                bot.send_message(
                    msg.chat.id,
                    i18n.t("msg_fx_selected", user_id=uid, effect=fx_name),
                    parse_mode="HTML",
                    reply_markup=build_main_keyboard(uid),
                )
                return

        # Settings buttons
        if "Voice (OGG)" in text or "Голосовое" in text:
            update_user_settings(uid, format_out="voice")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_format_selected", user_id=uid, format="Voice Note (OGG)"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "MP3 Audio" in text or "Аудио" in text:
            update_user_settings(uid, format_out="audio")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_format_selected", user_id=uid, format="MP3 Audio Track"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "Норма" in text or "Normal" in text:
            update_user_settings(uid, gain_db=0)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_gain_selected", user_id=uid, gain="0 dB (Норма)"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "+6 dB" in text or "Усиление" in text:
            update_user_settings(uid, gain_db=6)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_gain_selected", user_id=uid, gain="+6 dB (Усиление)"),
                reply_markup=build_settings_keyboard(uid),
            )
        elif text == i18n.t("btn_settings", user_id=uid) or "Настройки" in text or "Settings" in text:
            bot.send_message(
                msg.chat.id,
                "⚙️ **Настройки аудио студии** / Settings:",
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
                "🎙 Главное меню Voice Studio:",
                reply_markup=build_main_keyboard(uid),
            )
        else:
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_send_voice", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )


# ---------------------------------------------------------------------------
# Cyberpunk Web Studio HTTP Handler (Mic recording + Live Playback)
# ---------------------------------------------------------------------------
WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Voice Studio Master</title>
<style>
  :root {
    --bg-dark: #090d16;
    --card-bg: #121824;
    --accent-gold: #ffb703;
    --accent-orange: #fb8500;
    --accent-cyan: #00f5ff;
    --text-primary: #f3f4f6;
    --text-muted: #9ca3af;
    --border-color: #1f293d;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: radial-gradient(circle at top right, #1f1d36 0%, var(--bg-dark) 100%);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh;
    padding: 24px 16px;
  }
  .container { max-width: 900px; margin: 0 auto; }
  header {
    text-align: center;
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border-color);
  }
  h1 {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent-gold) 0%, var(--accent-orange) 100%);
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
    background: rgba(255, 183, 3, 0.15);
    color: var(--accent-gold);
    border: 1px solid rgba(255, 183, 3, 0.3);
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
    color: var(--accent-gold);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .mic-box {
    text-align: center;
    padding: 24px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 12px;
    border: 1px dashed rgba(255, 183, 3, 0.3);
    margin-bottom: 16px;
  }
  .mic-btn {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    border: none;
    background: linear-gradient(135deg, var(--accent-gold), var(--accent-orange));
    color: #090d16;
    font-size: 28px;
    cursor: pointer;
    box-shadow: 0 0 20px rgba(255, 183, 3, 0.4);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .mic-btn.recording {
    background: #ef4444;
    box-shadow: 0 0 25px rgba(239, 68, 68, 0.8);
    animation: pulse 1.2s infinite;
  }
  @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.08); } 100% { transform: scale(1); } }

  .fx-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 16px;
  }
  .fx-card {
    background: #172033;
    border: 1px solid #23304a;
    border-radius: 10px;
    padding: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .fx-card:hover, .fx-card.active {
    border-color: var(--accent-gold);
    background: rgba(255, 183, 3, 0.12);
  }
  .fx-title { font-weight: 700; font-size: 0.9rem; margin-bottom: 4px; }
  .fx-desc { font-size: 0.75rem; color: var(--text-muted); }

  .action-btn {
    width: 100%;
    padding: 14px;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, var(--accent-gold) 0%, var(--accent-orange) 100%);
    color: #090d16;
    font-weight: 700;
    font-size: 1rem;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(255, 183, 3, 0.3);
    transition: transform 0.1s ease;
  }
  .action-btn:hover { transform: translateY(-1px); }
  .action-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  audio { width: 100%; margin-top: 16px; border-radius: 8px; }
  .download-btn {
    display: block;
    text-align: center;
    background: var(--accent-gold);
    color: #090d16;
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
    <div class="badge">Studio Master • Port 8097</div>
    <h1>Voice Studio Master</h1>
    <p class="subtitle">Студийная постобработка голоса, компрессия EBU R128 и вокальные FX</p>
  </header>

  <div class="grid">
    <div class="card">
      <h2>🎙 1. Запись или загрузка</h2>
      <div class="mic-box">
        <button id="micBtn" class="mic-btn" onclick="toggleRecording()">🎤</button>
        <p id="micStatus" style="font-size:0.85rem; margin-top:10px; color:var(--text-muted);">Нажмите микрофон для записи</p>
      </div>

      <div style="text-align:center; margin-bottom:12px; color:var(--text-muted); font-size:0.8rem;">— ИЛИ ВЫБЕРИТЕ ФАЙЛ —</div>
      <input type="file" id="audioFileInput" accept="audio/*,video/*" onchange="onFileChosen(this)" style="display:none">
      <button class="action-btn" style="background:#1f293d; color:var(--text-primary); box-shadow:none;" onclick="document.getElementById('audioFileInput').click()">📁 Загрузить аудио/голосовое</button>
      <p id="fileChosenLabel" style="font-size:0.8rem; margin-top:8px; color:var(--accent-gold); text-align:center;"></p>
    </div>

    <div class="card">
      <h2>✨ 2. Выберите эффект</h2>
      <div class="fx-grid">
        <div class="fx-card active" onclick="selectFx('podcast_clean', this)">
          <div class="fx-title">🎙 Подкаст Clean</div>
          <div class="fx-desc">EBU R128, компрессор, срез инфрагула</div>
        </div>
        <div class="fx-card" onclick="selectFx('radio_broadcast', this)">
          <div class="fx-title">📻 Радио Эфир</div>
          <div class="fx-desc">300-3400 Гц + мягкий сатуратор</div>
        </div>
        <div class="fx-card" onclick="selectFx('deep_pitch', this)">
          <div class="fx-title">👹 Глубокий Бас</div>
          <div class="fx-desc">Снижение питча на 4 полутона</div>
        </div>
        <div class="fx-card" onclick="selectFx('chipmunk', this)">
          <div class="fx-title">🐿 Бурундук / Аниме</div>
          <div class="fx-desc">Повышение тональности на 5 полутонов</div>
        </div>
        <div class="fx-card" onclick="selectFx('vocoder_robot', this)">
          <div class="fx-title">🤖 Вокодер / Робот</div>
          <div class="fx-desc">Модуляция частоты и тремоло</div>
        </div>
        <div class="fx-card" onclick="selectFx('cathedral_reverb', this)">
          <div class="fx-title">🏛 Соборное Эхо</div>
          <div class="fx-desc">Глубокая пространственная реверберация</div>
        </div>
        <div class="fx-card" onclick="selectFx('megaphone', this)">
          <div class="fx-title">📢 Мегафон / Рация</div>
          <div class="fx-desc">Акустический перегруз рации</div>
        </div>
        <div class="fx-card" onclick="selectFx('lofi_tape', this)">
          <div class="fx-title">📼 Lo-Fi Кассета</div>
          <div class="fx-desc">Винтажная лента с флаттером</div>
        </div>
      </div>

      <button id="renderBtn" class="action-btn" onclick="applyEffect()" disabled>⚡ Применить студийный эффект</button>

      <div id="resultBlock" style="display:none; margin-top:16px;">
        <h3 style="color:var(--accent-gold); font-size:1rem; margin-bottom:8px;">🎧 Результат:</h3>
        <audio id="audioPlayer" controls></audio>
        <a id="downloadBtn" class="download-btn" href="#" download>📥 Скачать обработанный звук</a>
      </div>
    </div>
  </div>
</div>

<script>
let currentBlob = null;
let currentFx = 'podcast_clean';
let mediaRecorder = null;
let audioChunks = [];

function selectFx(fx, el) {
  currentFx = fx;
  document.querySelectorAll('.fx-card').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

function onFileChosen(input) {
  if (input.files && input.files[0]) {
    currentBlob = input.files[0];
    document.getElementById('fileChosenLabel').innerText = 'Выбран файл: ' + currentBlob.name;
    document.getElementById('renderBtn').disabled = false;
  }
}

async function toggleRecording() {
  const btn = document.getElementById('micBtn');
  const status = document.getElementById('micStatus');
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    btn.classList.remove('recording');
    btn.innerText = '🎤';
    status.innerText = 'Запись остановлена. Готово к обработке.';
  } else {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = () => {
        currentBlob = new Blob(audioChunks, { type: 'audio/ogg' });
        document.getElementById('fileChosenLabel').innerText = 'Запись с микрофона готова (' + (currentBlob.size / 1024).toFixed(1) + ' KB)';
        document.getElementById('renderBtn').disabled = false;
      };
      mediaRecorder.start();
      btn.classList.add('recording');
      btn.innerText = '⏹';
      status.innerText = 'Идет запись… Нажмите для остановки';
    } catch(err) {
      alert('Ошибка доступа к микрофону: ' + err.message);
    }
  }
}

async function applyEffect() {
  if (!currentBlob) return;
  const btn = document.getElementById('renderBtn');
  btn.disabled = true;
  btn.innerText = 'Обработка на сервере…';

  const formData = new FormData();
  formData.append('file', currentBlob, 'recording.ogg');
  formData.append('effect', currentFx);
  formData.append('format', 'mp3');

  try {
    const resp = await fetch('/api/process', { method: 'POST', body: formData });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    const player = document.getElementById('audioPlayer');
    player.src = '/download/' + data.filename;
    document.getElementById('downloadBtn').href = '/download/' + data.filename;
    document.getElementById('downloadBtn').download = data.filename;
    document.getElementById('resultBlock').style.display = 'block';
  } catch (err) {
    alert('Ошибка: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerText = '⚡ Применить студийный эффект';
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
                "bot": "voice_studio_master",
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

        if path == "/api/process":
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
            effect = "podcast_clean"
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
                elif 'name="effect"' in headers_text:
                    effect = body_part.decode("utf-8").strip()
                elif 'name="format"' in headers_text:
                    fmt_out = body_part.decode("utf-8").strip()

            if not file_bytes:
                self.send_error(HTTPStatus.BAD_REQUEST, "No file provided")
                return

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf_in:
                tf_in.write(file_bytes)
                tmp_in = tf_in.name

            out_fname = f"voice_fx_{effect}_{int(time.time())}.mp3"
            out_path = OUTPUT_DIR / out_fname

            try:
                res = process_voice_audio(
                    input_path=tmp_in,
                    output_path=out_path,
                    effect=effect,
                    format_out=fmt_out,
                )
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                data = {
                    "filename": out_fname,
                    "duration": res["duration"],
                    "final_bytes": res["final_bytes"],
                    "effect": effect,
                }
                self.wfile.write(json.dumps(data).encode("utf-8"))
            except Exception as e:
                logger.exception("Web voice process failed")
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
    logger.info(f"Cyberpunk Voice Studio active at http://127.0.0.1:{WEB_PORT}")
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
    core.guard_bot(bot)
    core.start_janitor([core.get_data_dir() / "outputs"])
    setup_bot(bot)
    logger.info("Telegram bot listener initiated.")

    try:
        core.start_polling(bot, timeout=20, long_polling_timeout=10)
    except Exception as e:
        logger.exception(f"Bot polling exception: {e}")
    finally:
        web_server.shutdown()


if __name__ == "__main__":
    main()
