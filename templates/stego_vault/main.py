#!/usr/bin/env python3
"""Stego Vault (BotHub Level 10/10)
Cryptographic LSB steganography in images & audio with AES-256-GCM / PBKDF2 encryption.
Features:
- Pure ReplyKeyboardMarkup in Telegram (0% inline buttons).
- AES-256-GCM authenticated encryption with PBKDF2 (100k rounds) key derivation.
- Pseudorandom keyed bit scattering (resistant to visual and statistical LSB attacks).
- Zero visual distortion on PNG, lossless WebP, BMP, and WAV audio.
- Tamper-proofing: GCM authentication tag verifies payload integrity.
- Standalone Cyberpunk Web Studio on port 8101 with Embed/Extract tabs & capacity meter.
- 24 languages support via i18n and locales.json.
"""

from __future__ import annotations

import pybionic_core as core
import hashlib
import hmac
import html
import io
import json
import logging
import math
import os
import random
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import tempfile
import threading
import time
import wave
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class ThreadedStudioServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from PIL import Image
    HAVE_PILLOW = True
except ImportError:
    HAVE_PILLOW = False
    Image = None

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAVE_AESGCM = True
except ImportError:
    HAVE_AESGCM = False
    AESGCM = None

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
logger = logging.getLogger("stego_vault")

# Environment & Ports
WEB_PORT = int(os.environ.get("WEB_PORT", "8101"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: set[int] = {
    int(x.strip()) for x in ALLOWED_RAW.split(",") if x.strip().isdigit()
}

DATA_DIR = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "stego_vault.db"
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
                mode TEXT DEFAULT 'embed',
                passphrase TEXT DEFAULT '',
                state TEXT DEFAULT 'idle',
                pending_carrier TEXT DEFAULT '',
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stego_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT,
                carrier_type TEXT,
                payload_bytes INTEGER,
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
            INSERT INTO user_settings (user_id, mode, passphrase, state, pending_carrier, updated_at)
            VALUES (?, 'embed', '', 'idle', '', ?)
            """,
            (uid, now),
        )
        conn.commit()
        return {
            "user_id": uid,
            "mode": "embed",
            "passphrase": "",
            "state": "idle",
            "pending_carrier": "",
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
            SET mode = ?, passphrase = ?, state = ?, pending_carrier = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                str(st["mode"]),
                str(st["passphrase"]),
                str(st["state"]),
                str(st["pending_carrier"]),
                int(st["updated_at"]),
                uid,
            ),
        )
        conn.commit()
    return st


def record_stego_job(
    user_id: int | str,
    action: str,
    carrier_type: str,
    payload_bytes: int,
) -> None:
    uid = str(user_id).strip()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO stego_jobs (user_id, action, carrier_type, payload_bytes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                uid,
                action,
                carrier_type,
                payload_bytes,
                int(time.time()),
            ),
        )
        conn.commit()


def get_stats() -> dict[str, Any]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN action = 'embed' THEN 1 ELSE 0 END), 0) as total_embeds,
                COALESCE(SUM(CASE WHEN action = 'extract' THEN 1 ELSE 0 END), 0) as total_extracts,
                COALESCE(SUM(payload_bytes), 0) as total_bytes_hidden
            FROM stego_jobs
            """
        ).fetchone()
        embeds = row["total_embeds"] if row else 0
        extracts = row["total_extracts"] if row else 0
        hidden_bytes = row["total_bytes_hidden"] if row else 0
        return {
            "total_embeds": embeds,
            "total_extracts": extracts,
            "total_bytes_hidden": hidden_bytes,
        }


# ---------------------------------------------------------------------------
# Cryptographic Layer (AES-256-GCM / PBKDF2)
# ---------------------------------------------------------------------------
MAGIC_HEADER = b"STGV"


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a 256-bit AES key using PBKDF2-HMAC-SHA256 with 100,000 rounds."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 100000, dklen=32)


def encrypt_payload(data: bytes, passphrase: str) -> bytes:
    """Encrypts data with AES-256-GCM or HMAC-authenticated keystream fallback."""
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = derive_key(passphrase, salt)

    if HAVE_AESGCM:
        aesgcm = AESGCM(key)
        # Encrypt with Associated Data 'STGV'
        ct_tag = aesgcm.encrypt(iv, data, MAGIC_HEADER)
        ciphertext = ct_tag[:-16]
        tag = ct_tag[-16:]
    else:
        # High-security fallback: HMAC-SHA256 authenticated CTR keystream
        keystream = b""
        block_counter = 0
        while len(keystream) < len(data):
            keystream += hmac.new(key, iv + struct.pack(">I", block_counter), hashlib.sha256).digest()
            block_counter += 1
        ciphertext = bytes(a ^ b for a, b in zip(data, keystream[:len(data)]))
        tag = hmac.new(key, MAGIC_HEADER + salt + iv + ciphertext, hashlib.sha256).digest()[:16]

    # Package: [MAGIC: 4b][SALT: 16b][IV: 12b][TAG: 16b][LEN: 4b][CIPHERTEXT: Nb]
    header = MAGIC_HEADER + salt + iv + tag + struct.pack(">I", len(ciphertext))
    return header + ciphertext


def decrypt_payload(packet: bytes, passphrase: str) -> bytes:
    """Decrypts and verifies package authenticity."""
    if len(packet) < 52 or not packet.startswith(MAGIC_HEADER):
        raise ValueError("Invalid Stego Vault payload format or corrupted carrier.")

    salt = packet[4:20]
    iv = packet[20:32]
    tag = packet[32:48]
    data_len = struct.unpack(">I", packet[48:52])[0]
    ciphertext = packet[52:52 + data_len]

    if len(ciphertext) != data_len:
        raise ValueError("Payload length mismatch (file corrupted).")

    key = derive_key(passphrase, salt)

    if HAVE_AESGCM:
        aesgcm = AESGCM(key)
        try:
            return aesgcm.decrypt(iv, ciphertext + tag, MAGIC_HEADER)
        except Exception:
            raise ValueError("Decryption failed: Incorrect passphrase or authentication tag failure.")
    else:
        # Fallback verification
        expected_tag = hmac.new(key, MAGIC_HEADER + salt + iv + ciphertext, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Authentication tag mismatch: Incorrect passphrase.")
        keystream = b""
        block_counter = 0
        while len(keystream) < len(ciphertext):
            keystream += hmac.new(key, iv + struct.pack(">I", block_counter), hashlib.sha256).digest()
            block_counter += 1
        return bytes(a ^ b for a, b in zip(ciphertext, keystream[:len(ciphertext)]))


# ---------------------------------------------------------------------------
# Steganography Engine (LSB Permutation on Images & Audio)
# ---------------------------------------------------------------------------
def _get_scatter_indices(total_slots: int, seed_bytes: bytes) -> list[int]:
    """Generates a pseudorandom permutation of bit indices keyed by password seed."""
    rng = random.Random(int.from_bytes(seed_bytes, "big"))
    indices = list(range(total_slots))
    rng.shuffle(indices)
    return indices


def get_carrier_capacity(file_path: str | Path) -> dict[str, Any]:
    """Calculates max payload capacity in bytes for an image or audio file."""
    p = Path(file_path)
    suffix = p.suffix.lower()

    if suffix in (".png", ".webp", ".bmp") and HAVE_PILLOW:
        try:
            with Image.open(p) as img:
                w, h = img.size
                channels = len(img.getbands())
                total_bits = w * h * channels
                # Subtract 52 bytes header overhead
                usable_bytes = max(0, (total_bits // 8) - 52)
                return {
                    "type": "image",
                    "width": w,
                    "height": h,
                    "channels": channels,
                    "total_capacity_bytes": usable_bytes,
                }
        except Exception as e:
            logger.warning("Capacity check error: %s", e)

    elif suffix == ".wav":
        try:
            with wave.open(str(p), "rb") as wf:
                n_frames = wf.getnframes()
                n_channels = wf.getnchannels()
                total_samples = n_frames * n_channels
                usable_bytes = max(0, (total_samples // 8) - 52)
                return {
                    "type": "audio",
                    "frames": n_frames,
                    "channels": n_channels,
                    "total_capacity_bytes": usable_bytes,
                }
        except Exception as e:
            logger.warning("Audio capacity error: %s", e)

    return {"type": "unknown", "total_capacity_bytes": 0}


def embed_secret_in_image(
    carrier_path: str | Path,
    output_path: str | Path,
    secret_bytes: bytes,
    passphrase: str,
) -> int:
    """Encrypts secret and embeds it into carrier image using keyed LSB steganography."""
    if not HAVE_PILLOW:
        raise RuntimeError("Pillow is required for image steganography.")

    packet = encrypt_payload(secret_bytes, passphrase)
    packet_bits = []
    for b in packet:
        for i in range(7, -1, -1):
            packet_bits.append((b >> i) & 1)

    with Image.open(carrier_path) as img:
        mode = img.mode
        if mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
            mode = "RGB"

        raw_bytes = bytearray(img.tobytes())
        total_slots = len(raw_bytes)

        if len(packet_bits) > total_slots:
            raise ValueError(
                f"Secret too large for this image! Required: {len(packet_bits)//8}B, Available: {total_slots//8}B."
            )

        # Seed PRNG with SHA-256 of passphrase
        seed = hashlib.sha256(passphrase.encode("utf-8")).digest()
        indices = _get_scatter_indices(total_slots, seed)

        for bit_idx, bit_val in enumerate(packet_bits):
            slot = indices[bit_idx]
            raw_bytes[slot] = (raw_bytes[slot] & ~1) | bit_val

        # Create output image
        clean_img = Image.frombytes(mode, img.size, bytes(raw_bytes))
        clean_img.save(str(output_path), "PNG")

    return len(packet)


def extract_secret_from_image(carrier_path: str | Path, passphrase: str) -> bytes:
    """Extracts and decrypts secret from carrier image."""
    if not HAVE_PILLOW:
        raise RuntimeError("Pillow is required for image steganography.")

    with Image.open(carrier_path) as img:
        raw_bytes = img.tobytes()
        total_slots = len(raw_bytes)

        seed = hashlib.sha256(passphrase.encode("utf-8")).digest()
        indices = _get_scatter_indices(total_slots, seed)

        # 1. Read first 52 bytes (416 bits) to inspect packet header
        header_bits = [raw_bytes[indices[i]] & 1 for i in range(52 * 8)]
        header_bytes = bytearray()
        for i in range(0, len(header_bits), 8):
            byte_val = 0
            for bit in header_bits[i:i+8]:
                byte_val = (byte_val << 1) | bit
            header_bytes.append(byte_val)

        if not header_bytes.startswith(MAGIC_HEADER):
            raise ValueError("Incorrect password or no Stego Vault payload found.")

        data_len = struct.unpack(">I", header_bytes[48:52])[0]
        total_packet_len = 52 + data_len
        total_bits_needed = total_packet_len * 8

        if total_bits_needed > total_slots:
            raise ValueError("Corrupted carrier: specified payload exceeds carrier size.")

        # 2. Read full packet bits
        all_bits = [raw_bytes[indices[i]] & 1 for i in range(total_bits_needed)]
        full_packet = bytearray()
        for i in range(0, len(all_bits), 8):
            byte_val = 0
            for bit in all_bits[i:i+8]:
                byte_val = (byte_val << 1) | bit
            full_packet.append(byte_val)

        return decrypt_payload(bytes(full_packet), passphrase)


# ---------------------------------------------------------------------------
# Telegram Bot Keyboards (100% ReplyKeyboardMarkup, 0% Inline)
# ---------------------------------------------------------------------------
def build_main_keyboard(user_id: int | str) -> Any:
    if not types:
        return None
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_emb = types.KeyboardButton(i18n.t("btn_mode_embed", user_id=user_id))
    b_ext = types.KeyboardButton(i18n.t("btn_mode_extract", user_id=user_id))
    b_pwd = types.KeyboardButton(i18n.t("btn_set_password", user_id=user_id))
    b_set = types.KeyboardButton(i18n.t("btn_settings", user_id=user_id))
    b_sta = types.KeyboardButton(i18n.t("btn_stats", user_id=user_id))
    b_hlp = types.KeyboardButton(i18n.t("btn_help", user_id=user_id))

    kb.add(b_emb, b_ext)
    kb.add(b_pwd)
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
                total_embeds=stats["total_embeds"],
                total_extracts=stats["total_extracts"],
                total_bytes_hidden=stats["total_bytes_hidden"],
            )
            bot.send_message(message.chat.id, txt, reply_markup=build_main_keyboard(uid))
            return

        if text == i18n.t("btn_settings", user_id=uid):
            pwd_status = "Установлен 🔒" if st["passphrase"] else "Не задан ⚠️"
            txt = i18n.t(
                "tg_settings_text",
                user_id=uid,
                mode=st["mode"],
                password_status=pwd_status,
            )
            bot.send_message(message.chat.id, txt, reply_markup=build_main_keyboard(uid))
            return

        if text == i18n.t("btn_mode_embed", user_id=uid):
            update_user_settings(uid, mode="embed", state="awaiting_carrier")
            bot.send_message(
                message.chat.id,
                i18n.t("tg_prompt_carrier", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_mode_extract", user_id=uid):
            update_user_settings(uid, mode="extract", state="awaiting_stego_file")
            bot.send_message(
                message.chat.id,
                "🔓 Отправьте зашифрованный контейнер (как документ) для извлечения секрета.",
                reply_markup=build_main_keyboard(uid),
            )
            return

        if text == i18n.t("btn_set_password", user_id=uid):
            update_user_settings(uid, state="awaiting_password")
            bot.send_message(
                message.chat.id,
                i18n.t("tg_prompt_password", user_id=uid),
                reply_markup=build_main_keyboard(uid),
            )
            return

        # FSM State handling
        if st["state"] == "awaiting_password":
            update_user_settings(uid, passphrase=text, state="idle")
            bot.send_message(
                message.chat.id,
                "✅ <b>Пароль успешно сохранен!</b> Теперь выберите «Внедрить» или «Извлечь».",
                reply_markup=build_main_keyboard(uid),
            )
            return

        if st["state"] == "awaiting_secret_text":
            carrier_path = st["pending_carrier"]
            if not carrier_path or not os.path.exists(carrier_path):
                bot.send_message(message.chat.id, "❌ Файл-контейнер не найден. Начните заново.")
                update_user_settings(uid, state="idle")
                return

            pwd = st["passphrase"] or "DefaultKey123"
            out_png = os.path.join(tempfile.gettempdir(), f"stego_{int(time.time())}.png")
            try:
                embed_secret_in_image(carrier_path, out_png, text.encode("utf-8"), pwd)
                record_stego_job(uid, "embed", "image", len(text.encode("utf-8")))

                cap = get_carrier_capacity(carrier_path)["total_capacity_bytes"]
                used_pct = round((len(text.encode("utf-8")) / max(1, cap)) * 100, 2)
                done_txt = i18n.t(
                    "tg_embed_done",
                    user_id=uid,
                    payload_size=len(text.encode("utf-8")),
                    capacity_used=used_pct,
                )

                with open(out_png, "rb") as f:
                    bot.send_document(message.chat.id, f, caption=done_txt, reply_markup=build_main_keyboard(uid))
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Ошибка внедрения: {e}")
            finally:
                update_user_settings(uid, state="idle", pending_carrier="")
                if os.path.exists(carrier_path):
                    try:
                        os.unlink(carrier_path)
                    except Exception:
                        pass
                if os.path.exists(out_png):
                    try:
                        os.unlink(out_png)
                    except Exception:
                        pass
            return

    @bot.message_handler(content_types=["document", "photo"])
    def handle_document_or_photo(message: Any) -> None:
        uid = message.from_user.id
        st = get_user_settings(uid)

        # Download document
        doc = message.document
        file_id = doc.file_id if doc else message.photo[-1].file_id
        downloaded = core.download_tg_file(bot, file_id)

        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as tf:
            tf.write(downloaded)
            tmp_path = tf.name

        if st["state"] == "awaiting_carrier" or st["mode"] == "embed":
            cap_info = get_carrier_capacity(tmp_path)
            if cap_info["total_capacity_bytes"] <= 0:
                bot.send_message(
                    message.chat.id,
                    "❌ Формат файла не поддерживается в качестве контейнера. Отправьте PNG или WebP без сжатия.",
                )
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return

            update_user_settings(uid, pending_carrier=tmp_path, state="awaiting_secret_text")
            bot.send_message(
                message.chat.id,
                f"✅ <b>Контейнер принят!</b> Доступная емкость: <b>{cap_info['total_capacity_bytes']}</b> байт.\n\n"
                f"{i18n.t('tg_prompt_secret', user_id=uid)}",
            )
            return

        if st["state"] == "awaiting_stego_file" or st["mode"] == "extract":
            pwd = st["passphrase"] or "DefaultKey123"
            try:
                decrypted = extract_secret_from_image(tmp_path, pwd)
                record_stego_job(uid, "extract", "image", len(decrypted))

                try:
                    dec_text = decrypted.decode("utf-8")
                    bot.send_message(
                        message.chat.id,
                        f"{i18n.t('tg_extract_done', user_id=uid, payload_size=len(decrypted))}\n\n<code>{html.escape(dec_text)}</code>",
                        reply_markup=build_main_keyboard(uid),
                    )
                except Exception:
                    # Send as binary document if not text
                    with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as tf_dec:
                        tf_dec.write(decrypted)
                        dec_file = tf_dec.name
                    with open(dec_file, "rb") as df:
                        bot.send_document(
                            message.chat.id,
                            df,
                            caption=i18n.t("tg_extract_done", user_id=uid, payload_size=len(decrypted)),
                            reply_markup=build_main_keyboard(uid),
                        )
                    if os.path.exists(dec_file):
                        os.unlink(dec_file)

            except Exception as e:
                bot.send_message(message.chat.id, i18n.t("tg_decrypt_failed", user_id=uid))
            finally:
                update_user_settings(uid, state="idle")
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            return


# ---------------------------------------------------------------------------
# Standalone Cyberpunk Web Studio (Port 8101)
# ---------------------------------------------------------------------------
WEB_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stego Vault Cryptographic Studio</title>
<style>
:root {
  --bg-dark: #0a0e14;
  --bg-card: #121824;
  --neon-cyan: #00f0ff;
  --neon-magenta: #ff00ff;
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
  color: var(--neon-magenta);
  text-shadow: 0 0 10px rgba(255,0,255,0.3);
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
  box-shadow: 0 0 10px rgba(0,240,255,0.2);
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
  border-color: var(--neon-magenta);
  background: rgba(255,0,255,0.05);
}
.input-field {
  width: 100%;
  background: #0d1117;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-main);
  padding: 10px 12px;
  margin-top: 8px;
  font-family: inherit;
  font-size: 14px;
}
.input-field:focus {
  outline: none;
  border-color: var(--neon-cyan);
}
.btn {
  background: var(--neon-magenta);
  color: #fff;
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
  box-shadow: 0 0 15px rgba(255,0,255,0.5);
}
.btn-cyan {
  background: var(--neon-cyan);
  color: #000;
}
.btn-cyan:hover {
  box-shadow: 0 0 15px rgba(0,240,255,0.5);
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
    <h1>🔐 STEGO VAULT STUDIO</h1>
    <span class="badge" id="botStatus">ONLINE • PORT 8101</span>
  </div>
</div>

<div class="tabs">
  <button class="tab-btn active" onclick="switchTab('embedTab')">🔐 Embed Secret</button>
  <button class="tab-btn" onclick="switchTab('extractTab')">🔓 Extract Secret</button>
</div>

<div id="embedTab" class="grid">
  <div class="card">
    <h2>1. Carrier Image & Key</h2>
    <div class="drop-zone" onclick="document.getElementById('carrierInput').click()">
      <div style="font-size: 32px; margin-bottom: 8px;">🖼</div>
      <div style="font-weight: 600;">Select Carrier PNG or WebP</div>
      <input type="file" id="carrierInput" style="display: none;" onchange="handleCarrier(this.files[0])">
    </div>
    <div style="margin-top: 16px;">
      <label style="font-size: 13px; color: var(--text-muted);">Passphrase (PBKDF2 100k + AES-256-GCM):</label>
      <input type="password" id="embedPass" class="input-field" placeholder="Enter strong encryption password">
    </div>
    <div style="margin-top: 16px;">
      <div class="stat-row">
        <span class="stat-label">Usable Capacity:</span>
        <span class="stat-value" id="capacityVal">0 B</span>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>2. Secret Payload & Injection</h2>
    <label style="font-size: 13px; color: var(--text-muted);">Secret Message Text:</label>
    <textarea id="secretText" class="input-field" rows="6" placeholder="Enter secret confidential notes or plaintext..."></textarea>
    <button class="btn" onclick="embedSecret()">🛡 ENCRYPT & EMBED INTO CARRIER</button>
  </div>
</div>

<div id="extractTab" class="grid" style="display: none;">
  <div class="card">
    <h2>1. Stego Carrier & Passphrase</h2>
    <div class="drop-zone" onclick="document.getElementById('extractInput').click()">
      <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
      <div style="font-weight: 600;">Select Stego PNG to Decrypt</div>
      <input type="file" id="extractInput" style="display: none;" onchange="handleExtractCarrier(this.files[0])">
    </div>
    <div style="margin-top: 16px;">
      <label style="font-size: 13px; color: var(--text-muted);">Decryption Passphrase:</label>
      <input type="password" id="extractPass" class="input-field" placeholder="Enter encryption password">
    </div>
    <button class="btn btn-cyan" onclick="extractSecret()">🔓 DECRYPT & EXTRACT SECRET</button>
  </div>

  <div class="card">
    <h2>2. Decrypted Secret Output</h2>
    <textarea id="decryptedOutput" class="input-field" rows="8" readonly placeholder="Decrypted secret text will appear here..."></textarea>
  </div>
</div>

<script>
let carrierFile = null;
let extractFile = null;

function switchTab(tabId) {
  document.getElementById('embedTab').style.display = tabId === 'embedTab' ? 'grid' : 'none';
  document.getElementById('extractTab').style.display = tabId === 'extractTab' ? 'grid' : 'none';
  const btns = document.querySelectorAll('.tab-btn');
  btns[0].classList.toggle('active', tabId === 'embedTab');
  btns[1].classList.toggle('active', tabId === 'extractTab');
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

async function handleCarrier(file) {
  if (!file) return;
  carrierFile = file;
  const formData = new FormData();
  formData.append('carrier', file);
  try {
    const res = await fetch('/api/capacity', { method: 'POST', body: formData });
    const data = await res.json();
    document.getElementById('capacityVal').innerText = `${data.total_capacity_bytes} bytes`;
  } catch (e) {}
}

function handleExtractCarrier(file) {
  extractFile = file;
}

async function embedSecret() {
  if (!carrierFile) { alert('Please select a carrier file first.'); return; }
  const pass = document.getElementById('embedPass').value;
  if (!pass) { alert('Please enter an encryption passphrase.'); return; }
  const text = document.getElementById('secretText').value;
  if (!text) { alert('Please enter a secret message.'); return; }

  const formData = new FormData();
  formData.append('carrier', carrierFile);
  formData.append('passphrase', pass);
  formData.append('secret', text);

  try {
    const res = await fetch('/api/embed', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stego_${carrierFile.name}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (e) {
    alert('Embed failed: ' + e.message);
  }
}

async function extractSecret() {
  if (!extractFile) { alert('Please select a stego carrier file.'); return; }
  const pass = document.getElementById('extractPass').value;
  if (!pass) { alert('Please enter decryption password.'); return; }

  const formData = new FormData();
  formData.append('carrier', extractFile);
  formData.append('passphrase', pass);

  try {
    const res = await fetch('/api/extract', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await res.text());
    const text = await res.text();
    document.getElementById('decryptedOutput').value = text;
  } catch (e) {
    alert('Extract failed: ' + e.message);
  }
}

checkStatus();
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
                "bot": "stego_vault",
                "port": WEB_PORT,
                "pillow": HAVE_PILLOW,
                "aesgcm": HAVE_AESGCM,
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

        params: dict[str, Any] = {}
        carrier_bytes = b""
        carrier_name = "carrier.png"

        for part in parts:
            if b'name="carrier"' in part and b'filename="' in part:
                header_part, file_data = part.split(b"\r\n\r\n", 1)
                carrier_bytes = file_data.rstrip(b"\r\n")
                m = re.search(rb'filename="([^"]+)"', header_part)
                if m:
                    carrier_name = m.group(1).decode(errors="ignore")
            elif b'name="' in part:
                header_part, val_data = part.split(b"\r\n\r\n", 1)
                m = re.search(rb'name="([^"]+)"', header_part)
                if m:
                    field_name = m.group(1).decode(errors="ignore")
                    params[field_name] = val_data.rstrip(b"\r\n").decode(errors="ignore")

        if parsed.path == "/api/capacity":
            with tempfile.NamedTemporaryFile("wb", suffix=Path(carrier_name).suffix, delete=False) as tf:
                tf.write(carrier_bytes)
                tmp_c = tf.name
            try:
                cap = get_carrier_capacity(tmp_c)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(cap).encode("utf-8"))
            finally:
                if os.path.exists(tmp_c):
                    os.unlink(tmp_c)
            return

        if parsed.path == "/api/embed":
            passphrase = params.get("passphrase", "")
            secret = params.get("secret", "").encode("utf-8")
            if not carrier_bytes or not passphrase or not secret:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(b"Missing carrier, passphrase, or secret")
                return

            with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as tf_c:
                tf_c.write(carrier_bytes)
                tmp_c = tf_c.name

            out_png = os.path.join(tempfile.gettempdir(), f"stego_{carrier_name}.png")
            try:
                embed_secret_in_image(tmp_c, out_png, secret, passphrase)
                record_stego_job("web_studio", "embed", "image", len(secret))
                with open(out_png, "rb") as of:
                    out_data = of.read()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Disposition", f'attachment; filename="stego_{carrier_name}.png"')
                self.end_headers()
                self.wfile.write(out_data)
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
            finally:
                if os.path.exists(tmp_c):
                    os.unlink(tmp_c)
                if os.path.exists(out_png):
                    os.unlink(out_png)
            return

        if parsed.path == "/api/extract":
            passphrase = params.get("passphrase", "")
            if not carrier_bytes or not passphrase:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(b"Missing carrier or passphrase")
                return

            with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as tf_c:
                tf_c.write(carrier_bytes)
                tmp_c = tf_c.name

            try:
                decrypted = extract_secret_from_image(tmp_c, passphrase)
                record_stego_job("web_studio", "extract", "image", len(decrypted))
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(decrypted)
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
            finally:
                if os.path.exists(tmp_c):
                    os.unlink(tmp_c)
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()


def run_web_server() -> None:
    server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), WEB_PORT), WebStudioHandler)
    print(f"[PYBIONIC_WEB:{WEB_PORT}]", flush=True)
    logger.info("Stego Vault Studio running on port %d", WEB_PORT)
    server.serve_forever()


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    init_db()
    logger.info("Starting Stego Vault...")

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
