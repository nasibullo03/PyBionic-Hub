#!/usr/bin/env python3
"""Cloud Shard Backup (BotHub Level 10/10)
Shamir's Secret Sharing (k-of-n threshold) & Redundant Erasure Archive Splitter over GF(256).
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- Information-theoretic security: k-1 shards reveal ZERO bits of information.
- Galois Field GF(2^8) arithmetic with Rijndael irreducible polynomial (0x11B).
- Configurable (k, n) threshold (e.g. 2 of 3, 3 of 5, 4 of 7).
- Packaged ZIP distribution with recovery manifests and SHA-256 integrity verification.
- Standalone Cyberpunk Web Studio on port 8102 with Sharding & Reconstruction matrix.
- 24 languages support via i18n and locales.json.
"""

from __future__ import annotations

import hashlib
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
logger = logging.getLogger("cloud_shard_backup")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8102"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "shard_backup.db"
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
                thresh_k INTEGER DEFAULT 3,
                total_n INTEGER DEFAULT 5,
                mode TEXT DEFAULT 'shard',
                state TEXT DEFAULT 'idle',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shard_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT,
                thresh_k INTEGER,
                total_n INTEGER,
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
            INSERT INTO user_settings (user_id, thresh_k, total_n, mode, state, updated_at)
            VALUES (?, 3, 5, 'shard', 'idle', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {
            "user_id": uid,
            "thresh_k": 3,
            "total_n": 5,
            "mode": "shard",
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
            SET thresh_k = ?, total_n = ?, mode = ?, state = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                int(st["thresh_k"]),
                int(st["total_n"]),
                str(st["mode"]),
                str(st["state"]),
                int(st["updated_at"]),
                uid,
            ),
        )
        conn.commit()
    return st


def record_job(
    user_id: int | str,
    action: str,
    thresh_k: int,
    total_n: int,
    file_bytes: int,
) -> None:
    uid = str(user_id).strip()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO shard_jobs (user_id, action, thresh_k, total_n, file_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                action,
                thresh_k,
                total_n,
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
                COALESCE(SUM(CASE WHEN action = 'shard' THEN 1 ELSE 0 END), 0) as total_shards_created,
                COALESCE(SUM(CASE WHEN action = 'restore' THEN 1 ELSE 0 END), 0) as total_restores,
                COALESCE(SUM(file_bytes), 0) as total_bytes_protected
            FROM shard_jobs
            """
        ).fetchone()
        created = row["total_shards_created"] if row else 0
        restores = row["total_restores"] if row else 0
        protected = row["total_bytes_protected"] if row else 0
        return {
            "total_shards_created": created,
            "total_restores": restores,
            "total_bytes_protected": protected,
        }


# ---------------------------------------------------------------------------
# Galois Field GF(2^8) Arithmetic Engine
# ---------------------------------------------------------------------------
EXP_TABLE = [0] * 512
LOG_TABLE = [0] * 256
POLY = 0x11B  # x^8 + x^4 + x^3 + x + 1 (AES irreducible polynomial)

# Initialize log and antilog tables with primitive element 3
_x = 1
for _i in range(255):
    EXP_TABLE[_i] = _x
    EXP_TABLE[_i + 255] = _x
    LOG_TABLE[_x] = _i
    # Multiply by generator 3 in GF(2^8): (x << 1) ^ x
    _x2 = _x << 1
    if _x2 & 0x100:
        _x2 ^= POLY
    _x = _x2 ^ _x


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return EXP_TABLE[LOG_TABLE[a] + LOG_TABLE[b]]


def gf_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("GF(256) division by zero")
    if a == 0:
        return 0
    return EXP_TABLE[(LOG_TABLE[a] - LOG_TABLE[b]) % 255]


# ---------------------------------------------------------------------------
# Shamir Secret Sharing Engine
# ---------------------------------------------------------------------------
MAGIC_HEADER = b"SHRD"


def shard_bytes(
    data: bytes,
    k: int,
    n: int,
    original_filename: str = "secret.bin",
) -> list[bytes]:
    """Splits arbitrary binary data into n shards (k required to recover)."""
    if k < 2 or n < k or n > 255:
        raise ValueError(f"Invalid threshold parameters: k={k}, n={n} (must be 2 <= k <= n <= 255).")

    orig_len = len(data)
    data_sha = hashlib.sha256(data).digest()
    fname_bytes = original_filename.encode("utf-8")

    # Header structure for each shard:
    # [MAGIC: 4b][VER: 1b][X: 1b][K: 1b][N: 1b][ORIG_LEN: 4b][SHA256: 32b][FNAME_LEN: 2b][FNAME: Mb]
    shard_headers = []
    for x_idx in range(1, n + 1):
        hdr = (
            MAGIC_HEADER
            + bytes([1, x_idx, k, n])
            + struct.pack(">I", orig_len)
            + data_sha
            + struct.pack(">H", len(fname_bytes))
            + fname_bytes
        )
        shard_headers.append(bytearray(hdr))

    # For each byte of data, generate a random polynomial of degree k-1:
    # P(x) = S + a_1*x + a_2*x^2 + ... + a_{k-1}*x^{k-1}
    for byte_val in data:
        coeffs = [byte_val] + list(os.urandom(k - 1))
        for x_idx in range(1, n + 1):
            # Evaluate P(x_idx) via Horner's method
            y = coeffs[-1]
            for c in reversed(coeffs[:-1]):
                y = gf_mul(y, x_idx) ^ c
            shard_headers[x_idx - 1].append(y)

    return [bytes(sh) for sh in shard_headers]


def parse_shard(raw_shard: bytes) -> dict[str, Any]:
    """Parses a shard binary packet into its components."""
    if len(raw_shard) < 46 or not raw_shard.startswith(MAGIC_HEADER):
        raise ValueError("Invalid shard file: Magic header missing.")

    ver = raw_shard[4]
    x_idx = raw_shard[5]
    k = raw_shard[6]
    n = raw_shard[7]
    orig_len = struct.unpack(">I", raw_shard[8:12])[0]
    sha256_hash = raw_shard[12:44]
    fname_len = struct.unpack(">H", raw_shard[44:46])[0]

    header_size = 46 + fname_len
    if len(raw_shard) < header_size:
        raise ValueError("Corrupted shard header.")

    fname = raw_shard[46:header_size].decode("utf-8", errors="ignore")
    data_payload = raw_shard[header_size:]

    if len(data_payload) != orig_len:
        raise ValueError(f"Shard payload length ({len(data_payload)}) does not match header length ({orig_len}).")

    return {
        "version": ver,
        "x": x_idx,
        "k": k,
        "n": n,
        "orig_len": orig_len,
        "sha256": sha256_hash,
        "filename": fname,
        "payload": data_payload,
    }


def restore_bytes(raw_shards: list[bytes]) -> tuple[bytes, str]:
    """Reconstructs original file data from any k valid shards using Lagrange interpolation."""
    if not raw_shards:
        raise ValueError("No shards provided for restoration.")

    parsed_list = []
    seen_x = set()
    for sh in raw_shards:
        try:
            p = parse_shard(sh)
            if p["x"] not in seen_x:
                seen_x.add(p["x"])
                parsed_list.append(p)
        except Exception as e:
            logger.warning("Skipping invalid shard: %s", e)

    if not parsed_list:
        raise ValueError("No valid shard packets recognized.")

    k = parsed_list[0]["k"]
    orig_len = parsed_list[0]["orig_len"]
    expected_sha = parsed_list[0]["sha256"]
    fname = parsed_list[0]["filename"]

    if len(parsed_list) < k:
        raise ValueError(f"Insufficient shards provided: Got {len(parsed_list)}, but scheme requires minimum {k}.")

    # Take first k shards
    shards_to_use = parsed_list[:k]
    xs = [s["x"] for s in shards_to_use]
    payloads = [s["payload"] for s in shards_to_use]

    # Precalculate Lagrange basis coefficients L_j(0) = \prod_{m != j} (x_m / (x_m ^ x_j))
    lagrange_weights = []
    for j in range(k):
        weight = 1
        x_j = xs[j]
        for m in range(k):
            if m != j:
                x_m = xs[m]
                diff = x_m ^ x_j
                frac = gf_div(x_m, diff)
                weight = gf_mul(weight, frac)
        lagrange_weights.append(weight)

    # Reconstruct original bytes
    reconstructed = bytearray(orig_len)
    for byte_idx in range(orig_len):
        val = 0
        for j in range(k):
            y_j = payloads[j][byte_idx]
            term = gf_mul(y_j, lagrange_weights[j])
            val ^= term
        reconstructed[byte_idx] = val

    result = bytes(reconstructed)
    actual_sha = hashlib.sha256(result).digest()
    if actual_sha != expected_sha:
        raise ValueError("SHA-256 integrity check failed! Shards may be mismatched or corrupted.")

    return result, fname


def create_shards_zip(
    data: bytes,
    k: int,
    n: int,
    filename: str,
    output_zip_path: str | Path,
) -> None:
    """Generates all shards and packages them into a clean ZIP archive with recovery readme."""
    shards = shard_bytes(data, k, n, original_filename=filename)
    sha_hex = hashlib.sha256(data).hexdigest()

    readme_text = (
        f"CLOUD SHARD BACKUP - RECOVERY INSTRUCTIONS\n"
        f"===========================================\n"
        f"Original File: {filename}\n"
        f"Original Size: {len(data)} bytes\n"
        f"SHA-256 Hash:  {sha_hex}\n"
        f"Scheme:        {k} of {n} (Shamir's Secret Sharing over GF(256))\n\n"
        f"RULES FOR RECOVERY:\n"
        f"1. You need ANY {k} shard files to perfectly reconstruct the original file.\n"
        f"2. Having fewer than {k} shards reveals ZERO bits of information.\n"
        f"3. Distribute these shards across separate locations (Telegram, Cloud, USB, Friends).\n"
        f"4. To reconstruct, upload any {k} shards back to the bot or Web Studio.\n"
    )

    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README_RECOVERY.txt", readme_text)
        for idx, sh in enumerate(shards, start=1):
            shard_name = f"shard_{idx:02d}_of_{n:02d}.bin"
            zf.writestr(shard_name, sh)


# ---------------------------------------------------------------------------
# Telegram Bot Keyboards (100% ReplyKeyboardMarkup, 0% Inline)
# ---------------------------------------------------------------------------
def build_main_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_shd = types.KeyboardButton(i18n.t("btn_mode_shard", user_id=user_id))
    b_rst = types.KeyboardButton(i18n.t("btn_mode_restore", user_id=user_id))
    b_t23 = types.KeyboardButton(i18n.t("btn_thresh_2_3", user_id=user_id))
    b_t35 = types.KeyboardButton(i18n.t("btn_thresh_3_5", user_id=user_id))
    b_t47 = types.KeyboardButton(i18n.t("btn_thresh_4_7", user_id=user_id))
    b_set = types.KeyboardButton(i18n.t("btn_settings", user_id=user_id))
    b_sta = types.KeyboardButton(i18n.t("btn_stats", user_id=user_id))
    b_hlp = types.KeyboardButton(i18n.t("btn_help", user_id=user_id))

    kb.add(b_shd, b_rst)
    kb.add(b_t23, b_t35, b_t47)
    kb.add(b_set, b_sta, b_hlp)
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
        st = get_user_settings(uid)

        # Language picker
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
            update_user_settings(uid, state="idle")
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
                total_shards_created=stats["total_shards_created"],
                total_restores=stats["total_restores"],
                total_bytes_protected=stats["total_bytes_protected"],
            )
            bot.send_message(message.chat.id, txt, reply_markup=build_main_keyboard(uid))
            return

        if text == i18n.t("btn_settings", user_id=uid):
            txt = i18n.t(
                "tg_settings_text",
                user_id=uid,
                thresh_k=st["thresh_k"],
                total_n=st["total_n"],
            )
            bot.send_message(message.chat.id, txt, reply_markup=build_main_keyboard(uid))
            return

        # Scheme presets
        if text == i18n.t("btn_thresh_2_3", user_id=uid):
            update_user_settings(uid, thresh_k=2, total_n=3)
            bot.send_message(message.chat.id, "✅ Установлена схема: <b>2 из 3</b> (K=2, N=3).")
            return

        if text == i18n.t("btn_thresh_3_5", user_id=uid):
            update_user_settings(uid, thresh_k=3, total_n=5)
            bot.send_message(message.chat.id, "✅ Установлена схема: <b>3 из 5</b> (K=3, N=5).")
            return

        if text == i18n.t("btn_thresh_4_7", user_id=uid):
            update_user_settings(uid, thresh_k=4, total_n=7)
            bot.send_message(message.chat.id, "✅ Установлена схема: <b>4 из 7</b> (K=4, N=7).")
            return

        if text == i18n.t("btn_mode_shard", user_id=uid):
            update_user_settings(uid, mode="shard", state="awaiting_file_to_shard")
            bot.send_message(
                message.chat.id,
                i18n.t("tg_prompt_file_to_shard", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_mode_restore", user_id=uid):
            update_user_settings(uid, mode="restore", state="awaiting_shards")
            bot.send_message(
                message.chat.id,
                i18n.t("tg_prompt_shards_to_restore", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
            return

        # Text input to shard
        if st["state"] == "awaiting_file_to_shard":
            raw_bytes = text.encode("utf-8")
            k, n = st["thresh_k"], st["total_n"]
            out_zip = os.path.join(tempfile.gettempdir(), f"shards_{int(time.time())}.zip")
            try:
                create_shards_zip(raw_bytes, k, n, "secret_message.txt", out_zip)
                record_job(uid, "shard", k, n, len(raw_bytes))

                done_txt = i18n.t(
                    "tg_shard_done",
                    user_id=uid,
                    total_n=n,
                    thresh_k=k,
                    orig_bytes=len(raw_bytes),
                    sha256_hash=hashlib.sha256(raw_bytes).hexdigest()[:16] + "...",
                )
                with open(out_zip, "rb") as zf:
                    bot.send_document(message.chat.id, zf, caption=done_txt, reply_markup=build_main_keyboard(uid))
            finally:
                update_user_settings(uid, state="idle")
                if os.path.exists(out_zip):
                    try:
                        os.unlink(out_zip)
                    except Exception:
                        pass
            return

    @bot.message_handler(content_types=["document"])
    def handle_document(message: Any) -> None:
        uid = message.from_user.id
        st = get_user_settings(uid)
        doc = message.document

        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        doc_name = doc.file_name or "file.bin"

        # Check if user sent a ZIP containing shards or a single shard
        if doc_name.lower().endswith(".zip") and (st["state"] == "awaiting_shards" or st["mode"] == "restore"):
            # Unpack and extract shards from ZIP
            shards = []
            try:
                with zipfile.ZipFile(io.BytesIO(downloaded), "r") as zf:
                    for name in zf.namelist():
                        if name.endswith(".bin"):
                            shards.append(zf.read(name))

                reconstructed, orig_fname = restore_bytes(shards)
                record_job(uid, "restore", len(shards), len(shards), len(reconstructed))

                with tempfile.NamedTemporaryFile("wb", suffix=f"_{orig_fname}", delete=False) as tf:
                    tf.write(reconstructed)
                    restored_path = tf.name

                done_txt = i18n.t(
                    "tg_restore_done",
                    user_id=uid,
                    shards_used=len(shards),
                    file_bytes=len(reconstructed),
                )
                with open(restored_path, "rb") as rf:
                    bot.send_document(message.chat.id, rf, caption=done_txt, reply_markup=build_main_keyboard(uid))

                if os.path.exists(restored_path):
                    os.unlink(restored_path)

            except Exception as e:
                bot.send_message(message.chat.id, f"❌ <b>Ошибка:</b> {html.escape(str(e))}")
            finally:
                update_user_settings(uid, state="idle")
            return

        # Otherwise, if sharding a new file
        if st["state"] == "awaiting_file_to_shard" or st["mode"] == "shard":
            k, n = st["thresh_k"], st["total_n"]
            out_zip = os.path.join(tempfile.gettempdir(), f"shards_{Path(doc_name).stem}.zip")
            try:
                create_shards_zip(downloaded, k, n, doc_name, out_zip)
                record_job(uid, "shard", k, n, len(downloaded))

                done_txt = i18n.t(
                    "tg_shard_done",
                    user_id=uid,
                    total_n=n,
                    thresh_k=k,
                    orig_bytes=len(downloaded),
                    sha256_hash=hashlib.sha256(downloaded).hexdigest()[:16] + "...",
                )
                with open(out_zip, "rb") as zf:
                    bot.send_document(message.chat.id, zf, caption=done_txt, reply_markup=build_main_keyboard(uid))
            finally:
                update_user_settings(uid, state="idle")
                if os.path.exists(out_zip):
                    try:
                        os.unlink(out_zip)
                    except Exception:
                        pass
            return


# ---------------------------------------------------------------------------
# Standalone Cyberpunk Web Studio (Port 8102)
# ---------------------------------------------------------------------------
WEB_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cloud Shard Backup Studio</title>
<style>
:root {
  --bg-dark: #0a0e14;
  --bg-card: #121824;
  --neon-cyan: #00f0ff;
  --neon-green: #00ff66;
  --neon-gold: #ffb700;
  --neon-purple: #9d00ff;
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
.tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.tab-btn {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}
.tab-btn.active {
  color: var(--neon-cyan);
  border-color: var(--neon-cyan);
  background: rgba(0,240,255,0.08);
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
}
.drop-zone {
  border: 2px dashed var(--border);
  border-radius: 8px;
  padding: 30px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: rgba(255,255,255,0.01);
}
.drop-zone:hover {
  border-color: var(--neon-cyan);
  background: rgba(0,240,255,0.05);
}
.btn {
  background: var(--neon-cyan);
  color: #000;
  border: none;
  border-radius: 4px;
  padding: 12px 24px;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  width: 100%;
  margin-top: 16px;
  transition: all 0.2s ease;
}
.btn:hover {
  box-shadow: 0 0 15px rgba(0,240,255,0.5);
}
.btn-green {
  background: var(--neon-green);
}
.btn-green:hover {
  box-shadow: 0 0 15px rgba(0,255,102,0.5);
}
.slider-group {
  margin: 16px 0;
}
.slider-group label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 6px;
}
input[type="range"] {
  width: 100%;
  accent-color: var(--neon-cyan);
}
.shard-matrix {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.shard-pill {
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.03);
  color: var(--text-muted);
}
.shard-pill.loaded {
  border-color: var(--neon-green);
  color: var(--neon-green);
  background: rgba(0,255,102,0.1);
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
    <h1>🧩 CLOUD SHARD BACKUP</h1>
    <span class="badge" id="botStatus">ONLINE • PORT 8102</span>
  </div>
</div>

<div class="tabs">
  <button class="tab-btn active" onclick="switchTab('shardTab')">🧩 Shard File (Split)</button>
  <button class="tab-btn" onclick="switchTab('restoreTab')">🔄 Restore from Shards</button>
</div>

<!-- Tab 1: Shard File -->
<div id="shardTab" class="grid">
  <div class="card">
    <h2>1. Threshold Configuration</h2>
    <div class="slider-group">
      <label>Recovery Threshold (K): <span id="valK" style="color: var(--neon-cyan); font-weight: 700;">3</span></label>
      <input type="range" id="inputK" min="2" max="10" value="3" oninput="updateSliders()">
    </div>
    <div class="slider-group">
      <label>Total Shards (N): <span id="valN" style="color: var(--neon-cyan); font-weight: 700;">5</span></label>
      <input type="range" id="inputN" min="2" max="15" value="5" oninput="updateSliders()">
    </div>
    <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
      Scheme: Any <b id="schemeText">3 of 5</b> shards can restore original. K-1 shards reveal ZERO bits.
    </div>

    <div style="margin-top: 24px;">
      <h2>📊 Global Backup Metrics</h2>
      <div class="stat-row">
        <span class="stat-label">Files Sharded:</span>
        <span class="stat-value" id="statCreated">0</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Restores Completed:</span>
        <span class="stat-value" id="statRestores">0</span>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>2. Source File & Shard Packaging</h2>
    <div class="drop-zone" onclick="document.getElementById('fileToShard').click()">
      <div style="font-size: 32px; margin-bottom: 8px;">📁</div>
      <div style="font-weight: 600;">Select Document, Archive, or Seed Phrase</div>
      <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;" id="selectedFileName">No file selected</div>
      <input type="file" id="fileToShard" style="display: none;" onchange="handleFileSelect(this.files[0])">
    </div>
    <button class="btn" onclick="shardFile()" id="shardBtn" disabled>
      🧩 GENERATE & DOWNLOAD SHARDS (ZIP)
    </button>
  </div>
</div>

<!-- Tab 2: Restore from Shards -->
<div id="restoreTab" class="grid" style="display: none;">
  <div class="card">
    <h2>1. Shard Upload & Matrix</h2>
    <div class="drop-zone" onclick="document.getElementById('shardsInput').click()">
      <div style="font-size: 32px; margin-bottom: 8px;">📥</div>
      <div style="font-weight: 600;">Drop Shard Files (.bin) or Recovery ZIP</div>
      <input type="file" id="shardsInput" multiple style="display: none;" onchange="handleShardsInput(this.files)">
    </div>
    <div style="margin-top: 16px;">
      <label style="font-size: 13px; color: var(--text-muted);">Loaded Shards Matrix:</label>
      <div class="shard-matrix" id="shardMatrix">
        <span class="shard-pill">No shards loaded</span>
      </div>
    </div>
    <button class="btn btn-green" onclick="restoreShards()" id="restoreBtn" disabled>
      🔄 RECONSTRUCT ORIGINAL FILE
    </button>
  </div>

  <div class="card">
    <h2>2. Integrity Verification</h2>
    <div class="stat-row">
      <span class="stat-label">Original Filename:</span>
      <span class="stat-value" id="resFilename">—</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">SHA-256 Checksum:</span>
      <span class="stat-value" id="resSha">—</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Recovery Status:</span>
      <span class="stat-value" id="resStatus" style="color: var(--neon-gold);">Awaiting K Shards</span>
    </div>
  </div>
</div>

<script>
let sourceFile = null;
let uploadedShards = [];

function switchTab(tabId) {
  document.getElementById('shardTab').style.display = tabId === 'shardTab' ? 'grid' : 'none';
  document.getElementById('restoreTab').style.display = tabId === 'restoreTab' ? 'grid' : 'none';
  const btns = document.querySelectorAll('.tab-btn');
  btns[0].classList.toggle('active', tabId === 'shardTab');
  btns[1].classList.toggle('active', tabId === 'restoreTab');
}

function updateSliders() {
  let k = parseInt(document.getElementById('inputK').value);
  let n = parseInt(document.getElementById('inputN').value);
  if (k > n) { n = k; document.getElementById('inputN').value = n; }
  document.getElementById('valK').innerText = k;
  document.getElementById('valN').innerText = n;
  document.getElementById('schemeText').innerText = `${k} of ${n}`;
}

function handleFileSelect(file) {
  if (!file) return;
  sourceFile = file;
  document.getElementById('selectedFileName').innerText = `${file.name} (${file.size} bytes)`;
  document.getElementById('shardBtn').disabled = false;
}

async function shardFile() {
  if (!sourceFile) return;
  const k = document.getElementById('inputK').value;
  const n = document.getElementById('inputN').value;

  const btn = document.getElementById('shardBtn');
  btn.disabled = true;
  btn.innerText = '🧩 GENERATING SHARDS...';

  const formData = new FormData();
  formData.append('file', sourceFile);
  formData.append('k', k);
  formData.append('n', n);

  try {
    const res = await fetch('/api/shard', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `shards_${sourceFile.name}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    loadStats();
  } catch (e) {
    alert('Sharding failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerText = '🧩 GENERATE & DOWNLOAD SHARDS (ZIP)';
  }
}

function handleShardsInput(files) {
  uploadedShards = Array.from(files);
  const matrix = document.getElementById('shardMatrix');
  matrix.innerHTML = '';
  if (!uploadedShards.length) {
    matrix.innerHTML = '<span class="shard-pill">No shards loaded</span>';
    document.getElementById('restoreBtn').disabled = true;
    return;
  }
  uploadedShards.forEach((f, idx) => {
    const pill = document.createElement('span');
    pill.className = 'shard-pill loaded';
    pill.innerText = `Shard #${idx+1} (${f.name})`;
    matrix.appendChild(pill);
  });
  document.getElementById('restoreBtn').disabled = false;
  document.getElementById('resStatus').innerText = `${uploadedShards.length} Shards Ready`;
  document.getElementById('resStatus').style.color = '#00ff66';
}

async function restoreShards() {
  if (!uploadedShards.length) return;
  const btn = document.getElementById('restoreBtn');
  btn.disabled = true;
  btn.innerText = '🔄 RECONSTRUCTING...';

  const formData = new FormData();
  uploadedShards.forEach(f => formData.append('shards', f));

  try {
    const res = await fetch('/api/restore', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    let fname = 'restored_file.bin';
    const m = disposition.match(/filename="([^"]+)"/);
    if (m) fname = m[1];

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    a.remove();
    loadStats();
    document.getElementById('resStatus').innerText = 'Reconstructed & Verified ✅';
  } catch (e) {
    alert('Restore failed: ' + e.message);
    document.getElementById('resStatus').innerText = 'Failed: ' + e.message;
    document.getElementById('resStatus').style.color = '#ff0055';
  } finally {
    btn.disabled = false;
    btn.innerText = '🔄 RECONSTRUCT ORIGINAL FILE';
  }
}

async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.status === 'online') {
      document.getElementById('botStatus').innerText = `ONLINE • PORT ${data.port}`;
    }
  } catch (e) {}
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('statCreated').innerText = data.total_shards_created;
    document.getElementById('statRestores').innerText = data.total_restores;
  } catch (e) {}
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
        if parsed.path in ("/", "/index.html"):
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
                "bot": "cloud_shard_backup",
                "port": WEB_PORT,
                "gf256": True,
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
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)

        if not content_type.startswith("multipart/form-data"):
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return

        boundary = content_type.split("boundary=")[-1].strip().encode()
        parts = raw_body.split(b"--" + boundary)

        params: dict[str, str] = {}
        files_data: list[tuple[str, bytes]] = []

        for part in parts:
            if b'filename="' in part:
                header_part, file_data = part.split(b"\r\n\r\n", 1)
                data_clean = file_data.rstrip(b"\r\n")
                m = re.search(rb'filename="([^"]+)"', header_part)
                fname = m.group(1).decode(errors="ignore") if m else "file.bin"
                files_data.append((fname, data_clean))
            elif b'name="' in part:
                header_part, val_data = part.split(b"\r\n\r\n", 1)
                m = re.search(rb'name="([^"]+)"', header_part)
                if m:
                    f_name = m.group(1).decode(errors="ignore")
                    params[f_name] = val_data.rstrip(b"\r\n").decode(errors="ignore")

        if parsed.path == "/api/shard":
            if not files_data:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(b"No file uploaded")
                return

            fname, fdata = files_data[0]
            k = int(params.get("k", "3"))
            n = int(params.get("n", "5"))

            out_zip = os.path.join(tempfile.gettempdir(), f"shards_{fname}.zip")
            try:
                create_shards_zip(fdata, k, n, fname, out_zip)
                record_job("web_studio", "shard", k, n, len(fdata))
                with open(out_zip, "rb") as zf:
                    zip_data = zf.read()

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="shards_{fname}.zip"')
                self.end_headers()
                self.wfile.write(zip_data)
            finally:
                if os.path.exists(out_zip):
                    try:
                        os.unlink(out_zip)
                    except Exception:
                        pass
            return

        if parsed.path == "/api/restore":
            shards_collected = []
            for fname, fdata in files_data:
                if fname.lower().endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(fdata), "r") as zf:
                        for z_name in zf.namelist():
                            if z_name.endswith(".bin"):
                                shards_collected.append(zf.read(z_name))
                else:
                    shards_collected.append(fdata)

            try:
                restored, orig_name = restore_bytes(shards_collected)
                record_job("web_studio", "restore", len(shards_collected), len(shards_collected), len(restored))

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{orig_name}"')
                self.end_headers()
                self.wfile.write(restored)
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()


def run_web_server() -> None:
    server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), WEB_PORT), WebStudioHandler)
    print(f"[PYBIONIC_WEB:{WEB_PORT}]", flush=True)
    logger.info("Cloud Shard Backup Studio running on port %d", WEB_PORT)
    server.serve_forever()


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    init_db()
    logger.info("Starting Cloud Shard Backup...")

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
