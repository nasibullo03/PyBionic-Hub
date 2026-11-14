#!/usr/bin/env python3
"""Audiobook Chapterizer (BotHub Level 10/10)
Smart audiobook & podcast chapterizer by silence detection, M4B metadata injection, and track splitter.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- Silence pause detector with microsecond precision.
- Interactive M4B chapter injection (Apple Books, Audible, VLC, Telegram).
- Track splitter into numbered MP3 files packed as ZIP.
- Pitch-preserving atempo narration speedup (1.25x, 1.5x).
- Standalone Cyberpunk Web Studio on port 8099 with interactive Chapter Editor table.
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

import i18n

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("audiobook_chapterizer")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8099"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "chapterizer.db"
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
                mode TEXT DEFAULT 'm4b',
                noise_db INTEGER DEFAULT -30,
                min_pause REAL DEFAULT 1.5,
                state TEXT DEFAULT 'idle',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chapter_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                mode TEXT,
                chapters_count INTEGER,
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
            INSERT INTO user_settings (user_id, mode, noise_db, min_pause, state, updated_at)
            VALUES (?, 'm4b', -30, 1.5, 'idle', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {
            "user_id": uid,
            "mode": "m4b",
            "noise_db": -30,
            "min_pause": 1.5,
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
            SET mode = ?, noise_db = ?, min_pause = ?, state = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                str(st["mode"]),
                int(st["noise_db"]),
                float(st["min_pause"]),
                str(st["state"]),
                int(st["updated_at"]),
                uid,
            ),
        )
        conn.commit()
    return st


def record_chapter_job(
    user_id: int | str,
    mode: str,
    chapters_count: int,
    duration_sec: float,
    file_bytes: int,
) -> None:
    uid = str(user_id).strip()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chapter_jobs (user_id, mode, chapters_count, duration_sec, file_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                mode,
                chapters_count,
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
                COALESCE(SUM(duration_sec), 0.0) as total_dur,
                COALESCE(SUM(chapters_count), 0) as total_ch
            FROM chapter_jobs
            """
        ).fetchone()
        total_jobs = row["total_jobs"] if row else 0
        total_dur = row["total_dur"] if row else 0.0
        total_ch = row["total_ch"] if row else 0
        m = int(total_dur // 60)
        s = int(total_dur % 60)
        return {
            "total_jobs": total_jobs,
            "total_duration": f"{m}m {s}s",
            "total_chapters": total_ch,
        }


# ---------------------------------------------------------------------------
# FFmpeg Silence & Chapter Engine
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


def detect_silence_chapters(
    file_path: str | Path,
    noise_db: int = -30,
    min_pause: float = 1.5,
) -> list[dict[str, Any]]:
    total_dur = get_audio_duration(file_path)
    if total_dur <= 0.0:
        total_dur = 60.0

    cmd = [
        "ffmpeg",
        "-i",
        str(file_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_pause}",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out_text = res.stderr

    # Parse silence intervals
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", out_text)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", out_text)]

    min_gap = min(10.0, max(2.0, total_dur * 0.1))
    end_margin = min(5.0, max(1.0, total_dur * 0.05))

    split_points = [0.0]
    for s, e in zip(starts, ends):
        mid = (s + e) / 2.0
        if mid > split_points[-1] + min_gap and mid < total_dur - end_margin:
            split_points.append(mid)
    split_points.append(total_dur)

    chapters = []
    for idx in range(len(split_points) - 1):
        c_start = split_points[idx]
        c_end = split_points[idx + 1]
        chapters.append({
            "index": idx + 1,
            "title": f"Chapter {idx + 1}",
            "start_sec": c_start,
            "end_sec": c_end,
            "start_ms": int(c_start * 1000),
            "end_ms": int(c_end * 1000),
        })

    return chapters


def build_ffmetadata_text(chapters: list[dict[str, Any]], title: str = "Audiobook", artist: str = "Narrator") -> str:
    lines = [
        ";FFMETADATA1",
        f"title={title}",
        f"artist={artist}",
        "",
    ]
    for ch in chapters:
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={ch['start_ms']}")
        lines.append(f"END={ch['end_ms']}")
        lines.append(f"title={ch['title']}")
        lines.append("")
    return "\n".join(lines)


def create_m4b_audiobook(
    input_path: str | Path,
    output_path: str | Path,
    chapters: list[dict[str, Any]],
    title: str = "Audiobook",
    artist: str = "Narrator",
) -> None:
    meta_txt = build_ffmetadata_text(chapters, title=title, artist=artist)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf_meta:
        tf_meta.write(meta_txt)
        meta_file = tf_meta.name

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-i",
            meta_file,
            "-map_metadata",
            "1",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg M4B muxing failed: {res.stderr[-300:]}")
    finally:
        if os.path.exists(meta_file):
            try:
                os.unlink(meta_file)
            except Exception:
                pass


def split_into_zip_tracks(
    input_path: str | Path,
    output_zip_path: str | Path,
    chapters: list[dict[str, Any]],
) -> None:
    temp_dir = tempfile.mkdtemp(prefix="book_split_")
    in_p = str(input_path)
    generated_tracks = []

    try:
        for ch in chapters:
            c_idx = ch["index"]
            c_title = re.sub(r'[\\/*?:"<>|]', "", ch["title"]).replace(" ", "_")
            fname = f"{c_idx:02d}_{c_title}.mp3"
            fpath = os.path.join(temp_dir, fname)

            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{ch['start_sec']:.3f}",
                "-to",
                f"{ch['end_sec']:.3f}",
                "-i",
                in_p,
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                "-metadata",
                f"title={ch['title']}",
                "-metadata",
                f"track={c_idx}/{len(chapters)}",
                fpath,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            generated_tracks.append((fpath, fname))

        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath, fname in generated_tracks:
                zf.write(fpath, arcname=fname)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def speedup_audio(
    input_path: str | Path,
    output_path: str | Path,
    speed: float = 1.25,
) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-af",
        f"atempo={speed}",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(output_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg speedup failed: {res.stderr[-300:]}")


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
    b_m4b = types.KeyboardButton(i18n.t("btn_mode_m4b", user_id=user_id))
    b_spl = types.KeyboardButton(i18n.t("btn_mode_split", user_id=user_id))
    b_s12 = types.KeyboardButton(i18n.t("btn_speed_125", user_id=user_id))
    b_s15 = types.KeyboardButton(i18n.t("btn_speed_150", user_id=user_id))
    b_set = types.KeyboardButton(i18n.t("btn_settings", user_id=user_id))
    b_sta = types.KeyboardButton(i18n.t("btn_stats", user_id=user_id))
    b_hlp = types.KeyboardButton(i18n.t("btn_help", user_id=user_id))

    kb.add(b_m4b, b_spl)
    kb.add(b_s12, b_s15)
    kb.add(b_set, b_sta, b_hlp)
    return kb


def build_settings_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_n30 = types.KeyboardButton(i18n.t("btn_noise_30", user_id=user_id))
    b_n25 = types.KeyboardButton(i18n.t("btn_noise_25", user_id=user_id))
    b_p10 = types.KeyboardButton(i18n.t("btn_pause_10", user_id=user_id))
    b_p15 = types.KeyboardButton(i18n.t("btn_pause_15", user_id=user_id))
    b_p20 = types.KeyboardButton(i18n.t("btn_pause_20", user_id=user_id))
    b_lng = types.KeyboardButton(i18n.t("btn_choose_lang", user_id=user_id))
    b_bck = types.KeyboardButton(i18n.t("btn_back_main", user_id=user_id))

    kb.add(b_n30, b_n25)
    kb.add(b_p10, b_p15, b_p20)
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
        welcome = i18n.t(
            "tg_welcome",
            user_id=uid,
            mode=st["mode"],
            noise=st["noise_db"],
            pause=st["min_pause"],
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
            total_chapters=s["total_chapters"],
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

    @bot.message_handler(content_types=["audio", "document", "voice"])
    def on_audio_received(msg: Any) -> None:
        uid = msg.from_user.id
        if ALLOWED_USERS and uid not in ALLOWED_USERS:
            bot.reply_to(msg, "Access denied.")
            return

        file_obj = msg.audio or msg.document or msg.voice
        if not file_obj:
            bot.reply_to(msg, i18n.t("msg_send_audio", user_id=uid))
            return

        def worker() -> None:
            st = get_user_settings(uid)
            mode = st["mode"]
            noise_db = int(st["noise_db"])
            min_pause = float(st["min_pause"])

            status_msg = bot.send_message(
                msg.chat.id,
                i18n.t("msg_processing", user_id=uid),
                parse_mode="HTML",
            )

            tmp_in = None
            tmp_out = None
            try:
                finfo = bot.get_file(file_obj.file_id)
                data = bot.download_file(finfo.file_path)

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                    tf.write(data)
                    tmp_in = tf.name

                dur = get_audio_duration(tmp_in)

                if mode == "speed125" or mode == "speed150":
                    speed_factor = 1.25 if mode == "speed125" else 1.50
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf_out:
                        tmp_out = tf_out.name
                    speedup_audio(tmp_in, tmp_out, speed=speed_factor)
                    new_dur = get_audio_duration(tmp_out)
                    out_sz = os.path.getsize(tmp_out)
                    caption = i18n.t(
                        "msg_success_speed",
                        user_id=uid,
                        speed=speed_factor,
                        duration=format_duration(new_dur),
                        size=format_bytes(out_sz),
                    )
                    with open(tmp_out, "rb") as out_f:
                        bot.send_audio(msg.chat.id, out_f, caption=caption, parse_mode="HTML", reply_markup=build_main_keyboard(uid))
                    record_chapter_job(uid, mode, 0, new_dur, out_sz)

                elif mode == "split":
                    chapters = detect_silence_chapters(tmp_in, noise_db=noise_db, min_pause=min_pause)
                    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf_out:
                        tmp_out = tf_out.name
                    split_into_zip_tracks(tmp_in, tmp_out, chapters)
                    out_sz = os.path.getsize(tmp_out)
                    caption = i18n.t(
                        "msg_success_split",
                        user_id=uid,
                        chapters_count=len(chapters),
                    )
                    with open(tmp_out, "rb") as out_f:
                        bot.send_document(msg.chat.id, out_f, caption=caption, parse_mode="HTML", reply_markup=build_main_keyboard(uid))
                    record_chapter_job(uid, mode, len(chapters), dur, out_sz)

                else:
                    # Default M4B Chapters
                    chapters = detect_silence_chapters(tmp_in, noise_db=noise_db, min_pause=min_pause)
                    with tempfile.NamedTemporaryFile(suffix=".m4b", delete=False) as tf_out:
                        tmp_out = tf_out.name
                    create_m4b_audiobook(tmp_in, tmp_out, chapters, title="Audiobook")
                    out_sz = os.path.getsize(tmp_out)
                    caption = i18n.t(
                        "msg_success_m4b",
                        user_id=uid,
                        chapters_count=len(chapters),
                        duration=format_duration(dur),
                        size=format_bytes(out_sz),
                    )
                    with open(tmp_out, "rb") as out_f:
                        bot.send_document(msg.chat.id, out_f, caption=caption, parse_mode="HTML", reply_markup=build_main_keyboard(uid))
                    record_chapter_job(uid, mode, len(chapters), dur, out_sz)

            except Exception as e:
                logger.exception("Audiobook worker failed")
                bot.send_message(
                    msg.chat.id,
                    f"❌ Ошибка обработки книги: {e}",
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

        # Main menu modes
        if "M4B" in text:
            update_user_settings(uid, mode="m4b")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_mode_selected", user_id=uid, mode="Авто-главы (M4B Audiobook)"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "ZIP" in text or "Разрезать" in text:
            update_user_settings(uid, mode="split")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_mode_selected", user_id=uid, mode="Нарезка на треки (ZIP)"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "1.25x" in text:
            update_user_settings(uid, mode="speed125")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_mode_selected", user_id=uid, mode="Ускорение (1.25x)"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "1.5x" in text:
            update_user_settings(uid, mode="speed150")
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_mode_selected", user_id=uid, mode="Ускорение (1.5x)"),
                reply_markup=build_main_keyboard(uid),
            )
        elif "-30 dB" in text:
            update_user_settings(uid, noise_db=-30)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_noise_selected", user_id=uid, noise=-30),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "-25 dB" in text:
            update_user_settings(uid, noise_db=-25)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_noise_selected", user_id=uid, noise=-25),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "1.0с" in text:
            update_user_settings(uid, min_pause=1.0)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_pause_selected", user_id=uid, pause=1.0),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "1.5с" in text:
            update_user_settings(uid, min_pause=1.5)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_pause_selected", user_id=uid, pause=1.5),
                reply_markup=build_settings_keyboard(uid),
            )
        elif "2.0с" in text:
            update_user_settings(uid, min_pause=2.0)
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_pause_selected", user_id=uid, pause=2.0),
                reply_markup=build_settings_keyboard(uid),
            )
        elif text == i18n.t("btn_settings", user_id=uid) or "Настройки" in text or "Settings" in text:
            bot.send_message(
                msg.chat.id,
                "⚙️ **Настройки Audiobook Chapterizer** / Settings:",
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
                    total_chapters=s["total_chapters"],
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
                "📑 Главное меню Audiobook Chapterizer:",
                reply_markup=build_main_keyboard(uid),
            )
        else:
            bot.send_message(
                msg.chat.id,
                i18n.t("msg_send_audio", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )


# ---------------------------------------------------------------------------
# Cyberpunk Web Studio HTTP Handler (Interactive Chapter Editor Table)
# ---------------------------------------------------------------------------
WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Audiobook Chapterizer Studio</title>
<style>
  :root {
    --bg-dark: #0a0f1d;
    --card-bg: #111a2e;
    --accent-emerald: #10b981;
    --accent-teal: #14b8a6;
    --text-primary: #f1f5f9;
    --text-muted: #94a3b8;
    --border-color: #1e293b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: radial-gradient(circle at top right, #132e27 0%, var(--bg-dark) 100%);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh;
    padding: 24px 16px;
  }
  .container { max-width: 950px; margin: 0 auto; }
  header {
    text-align: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-color);
  }
  h1 {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent-emerald) 0%, var(--accent-teal) 100%);
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
    background: rgba(16, 185, 129, 0.15);
    color: var(--accent-emerald);
    border: 1px solid rgba(16, 185, 129, 0.3);
    margin-bottom: 8px;
    text-transform: uppercase;
  }
  p.subtitle { color: var(--text-muted); font-size: 0.95rem; }

  .card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    margin-bottom: 24px;
  }
  .card h2 {
    font-size: 1.15rem;
    margin-bottom: 16px;
    color: var(--accent-emerald);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .dropzone {
    border: 2px dashed rgba(16, 185, 129, 0.3);
    border-radius: 12px;
    padding: 24px 16px;
    text-align: center;
    cursor: pointer;
    background: rgba(0, 0, 0, 0.2);
    transition: all 0.2s;
  }
  .dropzone:hover { border-color: var(--accent-emerald); }

  .chapter-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 16px;
    font-size: 0.85rem;
  }
  .chapter-table th, .chapter-table td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid #1e293b;
  }
  .chapter-table th { color: var(--text-muted); font-weight: 600; }
  .chapter-table input {
    background: #0d1527;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 6px 10px;
    color: var(--text-primary);
    width: 100%;
    outline: none;
  }
  .chapter-table input:focus { border-color: var(--accent-emerald); }

  .btn-row {
    display: flex;
    gap: 12px;
    margin-top: 16px;
  }
  .action-btn {
    flex: 1;
    padding: 14px;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, var(--accent-emerald) 0%, var(--accent-teal) 100%);
    color: #051410;
    font-weight: 700;
    font-size: 0.95rem;
    cursor: pointer;
    transition: transform 0.1s ease;
  }
  .action-btn:hover { transform: translateY(-1px); }
  .action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="badge">Audiobook Studio • Port 8099</div>
    <h1>Audiobook Chapterizer Studio</h1>
    <p class="subtitle">Автодетектор глав по тишине, экспорт в M4B и нарезка треков в ZIP</p>
  </header>

  <div class="card">
    <h2>📁 1. Выберите файл книги или подкаста</h2>
    <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
      <strong id="filePrompt">Нажмите или перетащите аудиофайл книги</strong>
      <p style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">MP3, M4A, FLAC, WAV (до 2 ГБ)</p>
    </div>
    <input type="file" id="fileInput" accept="audio/*" onchange="onFileSelected(this)" style="display:none">
  </div>

  <div class="card" id="chaptersCard" style="display:none;">
    <h2>📑 2. Интерактивная таблица глав</h2>
    <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:12px;">
      Вы можете отредактировать названия глав перед созданием книги M4B или ZIP архива:
    </p>

    <table class="chapter-table">
      <thead>
        <tr>
          <th style="width:10%;">#</th>
          <th style="width:25%;">Начало (сек)</th>
          <th style="width:25%;">Конец (сек)</th>
          <th style="width:40%;">Название главы</th>
        </tr>
      </thead>
      <tbody id="chapterTableBody"></tbody>
    </table>

    <div class="btn-row">
      <button id="btnBuildM4b" class="action-btn" onclick="buildOutput('m4b')">📥 Скачать M4B с главами</button>
      <button id="btnBuildZip" class="action-btn" style="background:#1e293b; color:var(--text-primary);" onclick="buildOutput('split')">✂️ Скачать ZIP с треками</button>
    </div>
  </div>
</div>

<script>
let currentFile = null;
let detectedChapters = [];

function onFileSelected(input) {
  if (input.files && input.files[0]) {
    currentFile = input.files[0];
    document.getElementById('filePrompt').innerText = 'Анализ пауз тишины: ' + currentFile.name + '…';
    scanSilence();
  }
}

async function scanSilence() {
  const formData = new FormData();
  formData.append('file', currentFile);
  try {
    const resp = await fetch('/api/detect', { method: 'POST', body: formData });
    if (!resp.ok) throw new Error(await resp.text());
    detectedChapters = await resp.json();

    const tbody = document.getElementById('chapterTableBody');
    tbody.innerHTML = '';
    detectedChapters.forEach((ch, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = 
        '<td>' + (idx + 1) + '</td>' +
        '<td>' + ch.start_sec.toFixed(1) + 's</td>' +
        '<td>' + ch.end_sec.toFixed(1) + 's</td>' +
        '<td><input type="text" value="' + ch.title + '" onchange="detectedChapters[' + idx + '].title = this.value"></td>';
      tbody.appendChild(tr);
    });

    document.getElementById('filePrompt').innerText = 'Файл: ' + currentFile.name + ' (найдено глав: ' + detectedChapters.length + ')';
    document.getElementById('chaptersCard').style.display = 'block';
  } catch (err) {
    alert('Ошибка анализа: ' + err.message);
  }
}

async function buildOutput(mode) {
  if (!currentFile || !detectedChapters.length) return;
  const btn = mode === 'm4b' ? document.getElementById('btnBuildM4b') : document.getElementById('btnBuildZip');
  btn.disabled = true;
  btn.innerText = 'Сборка ' + mode.toUpperCase() + '…';

  const formData = new FormData();
  formData.append('file', currentFile);
  formData.append('mode', mode);
  formData.append('chapters', JSON.stringify(detectedChapters));

  try {
    const resp = await fetch('/api/build', { method: 'POST', body: formData });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    const a = document.createElement('a');
    a.href = '/download/' + data.filename;
    a.download = data.filename;
    a.click();
  } catch (err) {
    alert('Ошибка сборки: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerText = mode === 'm4b' ? '📥 Скачать M4B с главами' : '✂️ Скачать ZIP с треками';
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
                "bot": "audiobook_chapterizer",
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

        if path in ("/api/detect", "/api/build"):
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
            mode = "m4b"
            chapters_json = None

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
                elif 'name="mode"' in headers_text:
                    mode = body_part.decode("utf-8").strip()
                elif 'name="chapters"' in headers_text:
                    chapters_json = body_part.decode("utf-8").strip()

            if not file_bytes:
                self.send_error(HTTPStatus.BAD_REQUEST, "No file provided")
                return

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf_in:
                tf_in.write(file_bytes)
                tmp_in = tf_in.name

            try:
                if path == "/api/detect":
                    chapters = detect_silence_chapters(tmp_in, noise_db=-30, min_pause=1.5)
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(chapters).encode("utf-8"))
                    return

                # Build output
                if chapters_json:
                    try:
                        chapters = json.loads(chapters_json)
                    except Exception:
                        chapters = detect_silence_chapters(tmp_in)
                else:
                    chapters = detect_silence_chapters(tmp_in)

                if mode == "split":
                    out_fname = f"chapters_{int(time.time())}.zip"
                    out_path = OUTPUT_DIR / out_fname
                    split_into_zip_tracks(tmp_in, out_path, chapters)
                else:
                    out_fname = f"audiobook_{int(time.time())}.m4b"
                    out_path = OUTPUT_DIR / out_fname
                    create_m4b_audiobook(tmp_in, out_path, chapters)

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                data = {
                    "filename": out_fname,
                    "chapters_count": len(chapters),
                }
                self.wfile.write(json.dumps(data).encode("utf-8"))

            except Exception as e:
                logger.exception("Web chapterizer failed")
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
    logger.info(f"Cyberpunk Audiobook Studio active at http://127.0.0.1:{WEB_PORT}")
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
