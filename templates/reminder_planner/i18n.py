"""PyBionic BotHub localization engine driven by PYBIONIC_LANG, PYBIONIC_RTL & SQLite per-user prefs.
Supports persistent user languages, ReplyKeyboard menus, and seamless fallback.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_LANGUAGES: list[tuple[str, str]] = [
    ("ru", "🇷🇺 Русский"),
    ("en", "🇬🇧 English"),
    ("tg", "🇹🇯 Тоҷикӣ"),
    ("uz", "🇺🇿 Oʻzbekcha"),
    ("tr", "🇹🇷 Türkçe"),
    ("es", "🇪🇸 Español"),
    ("de", "🇩🇪 Deutsch"),
    ("fr", "🇫🇷 Français"),
    ("it", "🇮🇹 Italiano"),
    ("pt", "🇵🇹 Português"),
    ("pl", "🇵🇱 Polski"),
    ("uk", "🇺🇦 Українська"),
    ("kk", "Қазақша"),
    ("ky", "🇰🇬 Кыргызча"),
    ("az", "🇦🇿 Azərbaycan"),
    ("ar", "🇸🇦 العربية"),
    ("fa", "🇮🇷 فارسی"),
    ("hi", "🇮🇳 हिन्दी"),
    ("zh-cn", "🇨🇳 简体中文"),
    ("ja", "🇯🇵 日本語"),
    ("ko", "🇰🇷 한국어"),
    ("id", "🇮🇩 Bahasa Indonesia"),
    ("vi", "🇻🇳 Tiếng Việt"),
    ("th", "🇹🇭 ไทย"),
]


def normalize_lang_tag(raw: str | None) -> str:
    tag = (raw or "en").strip().replace("_", "-").lower()
    if tag in ("in", "id-id"):
        return "id"
    if tag in ("zh-cn", "zh-hans", "zh-hans-cn", "zh"):
        return "zh-cn"
    if tag.startswith("ru"):
        return "ru"
    if tag.startswith("tg"):
        return "tg"
    if tag.startswith("uz"):
        return "uz"
    if tag.startswith("en"):
        return "en"
    return tag.split("-")[0] if "-" in tag and tag not in ("zh-cn",) else (tag or "en")


def current_lang() -> str:
    return normalize_lang_tag(os.environ.get("PYBIONIC_LANG") or os.environ.get("LANG") or "en")


def is_rtl(lang: str | None = None) -> bool:
    if os.environ.get("PYBIONIC_RTL") == "1":
        return True
    target = lang or current_lang()
    base = normalize_lang_tag(target).split("-")[0]
    return base in {"ar", "fa", "ur", "he", "ps", "sd", "ug"}


def _db_path() -> Path:
    base = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    base.mkdir(parents=True, exist_ok=True)
    return base / "i18n_users.db"


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_lang (
            user_id TEXT PRIMARY KEY,
            lang_tag TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    return conn


def get_user_lang(user_id: int | str | None, default: str | None = None) -> str:
    if not user_id:
        return default or current_lang()
    uid = str(user_id).strip()
    try:
        with _get_db() as conn:
            row = conn.execute("SELECT lang_tag FROM user_lang WHERE user_id = ?", (uid,)).fetchone()
            if row and row[0]:
                return normalize_lang_tag(row[0])
    except Exception:
        pass
    return default or current_lang()


def set_user_lang(user_id: int | str, lang_tag: str) -> str:
    norm = normalize_lang_tag(lang_tag)
    uid = str(user_id).strip()
    try:
        with _get_db() as conn:
            conn.execute(
                """
                INSERT INTO user_lang (user_id, lang_tag, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET lang_tag = excluded.lang_tag, updated_at = excluded.updated_at
                """,
                (uid, norm, int(time.time())),
            )
    except Exception:
        pass
    return norm


def safe_answer_callback(bot: Any, call_id: str | int, text: str | None = None, show_alert: bool = False) -> bool:
    """Safely answers a Telegram callback query to avoid spinning buttons and catch timeout errors."""
    try:
        bot.answer_callback_query(call_id, text=text, show_alert=show_alert)
        return True
    except Exception:
        return False


def build_language_keyboard(user_id: int | str | None = None, prefix: str = "setlang"):
    """Legacy InlineKeyboardMarkup with supported languages (kept for backwards-compatibility)."""
    try:
        from telebot import types
    except ImportError:
        return None

    active = get_user_lang(user_id)
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for code, label in SUPPORTED_LANGUAGES:
        check = " ✓" if code == active else ""
        btn_text = f"{label}{check}"
        cb_data = f"{prefix}|{code}"
        buttons.append(types.InlineKeyboardButton(text=btn_text, callback_data=cb_data))
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            kb.row(buttons[i], buttons[i + 1])
        else:
            kb.row(buttons[i])
    return kb


def build_reply_language_keyboard(user_id: int | str | None = None, back_text: str = "◀ Назад"):
    """Builds a bottom ReplyKeyboardMarkup with all 24 languages next to the input keyboard."""
    try:
        from telebot import types
    except ImportError:
        return None

    active = get_user_lang(user_id)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    row = []
    for code, label in SUPPORTED_LANGUAGES:
        check = " ✓" if code == active else ""
        btn_text = f"{label}{check}"
        row.append(types.KeyboardButton(btn_text))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    kb.row(types.KeyboardButton(back_text))
    return kb


def parse_lang_choice(text: str | None) -> str | None:
    """Matches text clicked from a reply language keyboard and returns the lang_code."""
    if not text:
        return None
    raw = text.strip()
    # Strip trailing checkmark if present
    if raw.endswith("✓"):
        raw = raw[:-1].strip()
    for code, label in SUPPORTED_LANGUAGES:
        if raw == label or raw == f"{label} ✓" or raw in label or label in raw:
            return code
    return None


@lru_cache(maxsize=8)
def _load_locales(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _candidate_langs(tag: str) -> list[str]:
    norm = normalize_lang_tag(tag)
    base = norm.split("-")[0]
    candidates = [norm]
    if base and base not in candidates:
        candidates.append(base)
    if "en" not in candidates:
        candidates.append("en")
    if "ru" not in candidates:
        candidates.append("ru")
    return candidates


_LOCALES_CACHE: dict[str, Any] = {"mtime": None, "data": {}}


def get_locales_dict() -> dict[str, Any]:
    """locales.json с кэшем: файл перечитывается, только если изменился."""
    loc_file = Path(__file__).resolve().parent / "locales.json"
    try:
        mtime = loc_file.stat().st_mtime_ns
    except OSError:
        return {}
    if _LOCALES_CACHE["mtime"] != mtime:
        _LOCALES_CACHE["data"] = _load_locales(str(loc_file))
        _LOCALES_CACHE["mtime"] = mtime
    return _LOCALES_CACHE["data"]


def t(key: str, lang_override: str | None = None, user_id: int | str | None = None, **kwargs: Any) -> str:
    """Resolve localized string by key with automatic fallback chain."""
    data = get_locales_dict()
    strings = data.get("strings", {})
    entry = strings.get(key)
    if isinstance(entry, dict):
        effective_lang = lang_override or get_user_lang(user_id)
        val = None
        for code in _candidate_langs(effective_lang):
            if code in entry and entry[code]:
                val = str(entry[code])
                break
        if val is None and entry:
            val = str(next(iter(entry.values())))
    elif isinstance(entry, str):
        val = entry
    else:
        val = key

    if kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val


def t_list(key: str, lang_override: str | None = None, user_id: int | str | None = None) -> list[str]:
    """Resolve localized list (e.g., quotes list) by key."""
    data = get_locales_dict()
    lists = data.get("lists", {})
    entry = lists.get(key)
    if not isinstance(entry, dict):
        return []
    effective_lang = lang_override or get_user_lang(user_id)
    for code in _candidate_langs(effective_lang):
        val = entry.get(code)
        if isinstance(val, list) and val:
            return [str(x) for x in val]
    first = next(iter(entry.values()), [])
    return [str(x) for x in first] if isinstance(first, list) else []


def log(key: str, **kwargs: Any) -> None:
    """Print timestamped, localized status message to PyBionic console."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{current_lang()}] {t(key, **kwargs)}", flush=True)
