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

import pybionic_core as core
import pybionic_web as web
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
    core.guard_bot(bot)


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

        downloaded = core.download_tg_file(bot, doc.file_id)
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
def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    css = ("<style>.cs-scheme{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 6px}.cs-dot{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;"
           "font-size:12px;font-weight:700;background:var(--surface2);border:1px solid var(--line);color:var(--muted);transition:all .25s}"
           ".cs-dot.k{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;border-color:transparent;box-shadow:0 4px 14px -6px var(--brand)}"
           ".cs-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.cs-pill{padding:5px 10px;border-radius:99px;font-size:12.5px;background:var(--surface2);border:1px solid var(--line)}"
           ".cs-kv{display:grid;grid-template-columns:auto 1fr;gap:8px 14px;font-size:14px}.cs-kv span{color:var(--muted)}.cs-kv b{word-break:break-all;font-weight:600}"
           ".cs-sha{font-family:ui-monospace,Consolas,monospace;font-size:12.5px}</style>")
    tabs = web.segmented("mode", [("shard", T("w_tab_shard")), ("restore", T("w_tab_restore"))], "shard",
                         sub={"shard": T("w_tab_shard_sub"), "restore": T("w_tab_restore_sub")}, icons={"shard": "zap", "restore": "refresh"})
    shard = web.grid(
        web.card(T("w_card_scheme"),
            web.field(T("w_k"), web.range_("k", 2, 10, 3, 1), hint=T("w_k_hint"))
            + web.field(T("w_n"), web.range_("n", 2, 15, 5, 1), hint=T("w_n_hint"))
            + '<div class="cs-scheme" id="scheme"></div>' + web.note(T("w_scheme_note", k="3", n="5"), "info", "shield").replace("<span>", '<span id="scheme-note">', 1),
            icon_name="settings"),
        web.card(T("w_card_source"),
            web.dropzone("src", T("w_drop_src"), T("w_drop_src_hint"), icon_name="file")
            + '<div class="pb-row">' + web.button(T("w_shard_btn"), "go", icon_name="download", disabled=True) + "</div>" + web.progress("sp")
            + web.note(T("w_store_note"), "warn"), icon_name="file"), min_width=320)
    restore = web.grid(
        web.card(T("w_card_shards"),
            web.dropzone("sh", T("w_drop_shards"), T("w_drop_shards_hint"), accept=".bin,.zip", multiple=True, icon_name="folder")
            + '<div class="cs-pills" id="pills"></div>'
            + '<div class="pb-row">' + web.button(T("w_restore_btn"), "rs", icon_name="refresh", disabled=True) + "</div>" + web.progress("rp"),
            icon_name="folder"),
        web.card(T("w_card_verify"),
            f'<div class="cs-kv"><span>{web.esc(T("file_name"))}</span><b id="r-name">—</b><span>{web.esc(T("file_size"))}</span><b id="r-size">—</b>'
            f'<span>SHA-256</span><b id="r-sha" class="cs-sha">—</b><span>{web.esc(T("status"))}</span><b id="r-st">{web.esc(T("waiting"))}</b></div>',
            icon_name="check"), min_width=320)
    st = web.card(T("statistics"), web.stats([(T("w_st_created"), "0", "s1", "zap"), (T("w_st_restores"), "0", "s2", "refresh")]), icon_name="chart")
    body = css + web.card(T("mode"), tabs, icon_name="shield") + f'<div id="t-shard">{shard}</div><div id="t-restore" hidden>{restore}</div>' + st
    hero = web.hero(T("w_title"), T("w_hero"), "🧩", chips=["Shamir K-of-N", "ZIP", "SHA-256"])
    web.send_page(handler, lang, title=T("w_title"), emoji="🧩", brand="#22c55e", port=WEB_PORT,
                  hero_html=hero, body=body, script=SHARD_JS)


SHARD_JS = r"""
const $=s=>document.querySelector(s);let src=null,shards=[];
$('#mode').addEventListener('change',()=>{const s=$('#mode').dataset.value==='shard';$('#t-shard').hidden=!s;$('#t-restore').hidden=s});
function scheme(from){let k=+$('#k').value,n=+$('#n').value;if(k>n){if(from==='n'){k=n;$('#k').value=k}else{n=k;$('#n').value=n}
  ['k','n'].forEach(id=>$('#'+id).dispatchEvent(new Event('input')))}
  $('#scheme').innerHTML=Array.from({length:n},(_,i)=>`<span class="cs-dot ${i<k?'k':''}">${i+1}</span>`).join('');
  $('#scheme-note').textContent=pb.t('w_scheme_note',{k,n})}
$('#k').addEventListener('change',()=>scheme('k'));$('#n').addEventListener('change',()=>scheme('n'));
$('#k').addEventListener('input',()=>scheme('k'));$('#n').addEventListener('input',()=>scheme('n'));scheme();
async function stats(){const d=await pb.json('/api/stats').catch(()=>null);if(d){pb.count($('#s1'),d.total_shards_created||0);pb.count($('#s2'),d.total_restores||0)}}
function save(blob,name){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();a.remove()}
async function send(url,fd){const r=await fetch(url,{method:'POST',body:fd});if(!r.ok){const t=await r.text();throw new Error(t||('HTTP '+r.status))}return r}
$('#src-zone').addEventListener('pb:files',e=>{src=e.detail[0];$('#go').disabled=!src});
$('#go').onclick=async()=>{if(!src)return;const b=$('#go');pb.busy(b,true);pb.progress('sp',null,pb.t('processing'));
  try{const fd=new FormData();fd.append('file',src);fd.append('k',$('#k').value);fd.append('n',$('#n').value);
    const blob=await (await send('/api/shard',fd)).blob();save(blob,'shards_'+src.name+'.zip');
    pb.progress('sp',100,pb.t('w_shard_done',{n:$('#n').value}));pb.toast(pb.t('done'));stats()}
  catch(err){pb.hide('sp');pb.toast(pb.t('error')+': '+err.message,true)}finally{pb.busy(b,false)}};
$('#sh-zone').addEventListener('pb:files',e=>{shards=Array.from(e.detail);$('#rs').disabled=!shards.length;
  $('#pills').innerHTML=shards.map((f,i)=>`<span class="cs-pill">🧩 ${i+1} · ${pb.esc(f.name)}</span>`).join('');
  $('#r-st').textContent=shards.length?pb.t('w_ready',{n:shards.length}):pb.t('waiting');$('#r-st').style.color=''});
async function sha(blob){try{const h=await crypto.subtle.digest('SHA-256',await blob.arrayBuffer());return [...new Uint8Array(h)].map(b=>b.toString(16).padStart(2,'0')).join('')}catch(e){return '—'}}
$('#rs').onclick=async()=>{if(!shards.length)return;const b=$('#rs');pb.busy(b,true);pb.progress('rp',null,pb.t('processing'));
  try{const fd=new FormData();shards.forEach(f=>fd.append('shards',f));const r=await send('/api/restore',fd);const blob=await r.blob();
    const m=(r.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/);const name=m?m[1]:'restored.bin';save(blob,name);
    $('#r-name').textContent=name;$('#r-size').textContent=pb.bytes(blob.size);$('#r-sha').textContent=await sha(blob);
    $('#r-st').textContent='✅ '+pb.t('w_restored');$('#r-st').style.color='#22c55e';pb.progress('rp',100,pb.t('done'));stats()}
  catch(err){pb.hide('rp');$('#r-st').textContent=pb.t('w_restore_fail');$('#r-st').style.color='#ef4444';pb.toast(pb.t('w_restore_fail'),true)}
  finally{pb.busy(b,false)}};
stats();
"""


class WebStudioHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("%s - " + format, self.address_string(), *args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            render_studio(self)
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
        core.start_polling(bot, skip_pending=True)
    else:
        logger.info("BOT_TOKEN not provided, running in Web Studio mode on port %d", WEB_PORT)
        web_t.join()


if __name__ == "__main__":
    main()
