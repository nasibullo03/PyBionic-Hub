"""PyBionic Core — общие помощники для всех ботов BotHub.

Исходник лежит в templates/pybionic_core.py. Копии в папках ботов делает
tools/sync_shared.py — правьте только корневой файл и запускайте скрипт.

Что внутри:
- allowed_ids() / guard_bot()  — единая проверка ALLOWED_USER_IDS для сообщений,
  кнопок и inline-запросов (первый обработчик бота);
- download_tg_file()           — скачивание с проверкой лимита Bot API (20 МБ);
- run_media() / media_slot()   — очередь тяжёлых задач ffmpeg/sox (по умолчанию 1 за раз);
- cleanup_old_files() / start_janitor() — удаление старых временных файлов;
- get_data_dir(), format_bytes(), format_duration(), env_int().
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

CORE_VERSION = "1.0.0"

# Лимит скачивания файлов через облачный Bot API
TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024


# ---------------------------------------------------------------------------
# Общее
# ---------------------------------------------------------------------------
def env_int(name: str, default: int, lo: int | None = None, hi: int | None = None) -> int:
    try:
        v = int(str(os.environ.get(name, "")).strip())
    except ValueError:
        v = default
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def get_data_dir() -> Path:
    d = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    d.mkdir(parents=True, exist_ok=True)
    return d


def format_bytes(n: float | int | None) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def format_duration(sec: float | int | None) -> str:
    s = int(sec or 0)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Доступ
# ---------------------------------------------------------------------------
def allowed_ids(raw: str | None = None) -> set[int]:
    raw = os.environ.get("ALLOWED_USER_IDS", "") if raw is None else raw
    out: set[int] = set()
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.add(int(part))
    return out


def is_allowed(user_id: int | None, closed_if_empty: bool = False) -> bool:
    ids = allowed_ids()
    if not ids:
        return not closed_if_empty
    return user_id is not None and int(user_id) in ids


DENY_TEXT = "⛔ Access denied / Доступ закрыт"


def guard_bot(bot: Any, closed_if_empty: bool = False, deny_text: str = DENY_TEXT) -> None:
    """Регистрирует запрет ПЕРВЫМИ обработчиками (вызывать сразу после TeleBot(...)).

    closed_if_empty=False: пустой ALLOWED_USER_IDS = бот открыт всем.
    closed_if_empty=True : пустой список = закрыт для всех (для опасных ботов).
    """

    def _blocked(user: Any) -> bool:
        return not is_allowed(getattr(user, "id", None), closed_if_empty)

    @bot.message_handler(func=lambda m: _blocked(m.from_user), content_types=[
        "text", "audio", "document", "photo", "sticker", "video", "video_note",
        "voice", "location", "contact", "animation", "poll", "dice",
    ])
    def _core_deny_message(m: Any) -> None:
        # в группах молчим, чтобы не спамить
        if getattr(m.chat, "type", "private") == "private":
            try:
                bot.reply_to(m, deny_text)
            except Exception:
                pass

    @bot.callback_query_handler(func=lambda c: _blocked(c.from_user))
    def _core_deny_callback(c: Any) -> None:
        try:
            bot.answer_callback_query(c.id, deny_text, show_alert=True)
        except Exception:
            pass

    @bot.inline_handler(func=lambda q: _blocked(q.from_user))
    def _core_deny_inline(q: Any) -> None:
        try:
            bot.answer_inline_query(q.id, [], cache_time=1)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Скачивание файлов из Telegram
# ---------------------------------------------------------------------------
class FileTooBig(Exception):
    def __init__(self, size: int):
        self.size = size
        what = f"Файл {format_bytes(size)}" if size > TG_DOWNLOAD_LIMIT else "Файл"
        super().__init__(
            f"{what} больше лимита Telegram-ботов {format_bytes(TG_DOWNLOAD_LIMIT)} / "
            f"File is larger than the {format_bytes(TG_DOWNLOAD_LIMIT)} Telegram bot limit"
        )


def file_size_of(message: Any) -> int:
    """Размер вложения сообщения в байтах (0, если неизвестен)."""
    for attr in ("document", "video", "audio", "voice", "video_note", "animation", "sticker"):
        obj = getattr(message, attr, None)
        if obj is not None:
            return int(getattr(obj, "file_size", 0) or 0)
    photos = getattr(message, "photo", None)
    if photos:
        return int(getattr(photos[-1], "file_size", 0) or 0)
    return 0


def check_size(size: int | None) -> None:
    if size and int(size) > TG_DOWNLOAD_LIMIT:
        raise FileTooBig(int(size))


def download_tg_file(bot: Any, file_id: str, size: int | None = None) -> bytes:
    """bot.get_file + download_file с понятной ошибкой вместо «Bad Request: file is too big»."""
    check_size(size)
    try:
        info = bot.get_file(file_id)
    except Exception as e:  # telebot.apihelper.ApiTelegramException
        if "too big" in str(e).lower():
            raise FileTooBig(int(size or 0)) from e
        raise
    check_size(getattr(info, "file_size", 0))
    return bot.download_file(info.file_path)


# ---------------------------------------------------------------------------
# Очередь тяжёлых задач (ffmpeg, sox ...)
# ---------------------------------------------------------------------------
_MEDIA_JOBS = env_int("MEDIA_MAX_JOBS", 1, 1, 8)
_media_sem = threading.BoundedSemaphore(_MEDIA_JOBS)
_waiting_lock = threading.Lock()
_waiting = 0


def media_queue_len() -> int:
    """Сколько задач сейчас ждёт своей очереди."""
    return _waiting


@contextmanager
def media_slot() -> Iterator[None]:
    global _waiting
    with _waiting_lock:
        _waiting += 1
    try:
        _media_sem.acquire()
    finally:
        with _waiting_lock:
            _waiting -= 1
    try:
        yield
    finally:
        _media_sem.release()


def run_media(cmd: list[str], timeout: float | None = None, **kwargs: Any) -> subprocess.CompletedProcess:
    """subprocess.run в общей очереди. Таймаут по умолчанию — MEDIA_TIMEOUT_SEC (900 с)."""
    if timeout is None:
        timeout = env_int("MEDIA_TIMEOUT_SEC", 900, 30, 7200)
    with media_slot():
        return subprocess.run(cmd, timeout=timeout, **kwargs)


# ---------------------------------------------------------------------------
# Уборка временных файлов
# ---------------------------------------------------------------------------
def cleanup_old_files(dirs: Iterable[str | Path], max_age_hours: float | None = None) -> int:
    if max_age_hours is None:
        max_age_hours = env_int("CLEANUP_HOURS", 48, 1, 24 * 365)
    edge = time.time() - max_age_hours * 3600
    removed = 0
    for d in dirs:
        p = Path(d)
        if not p.is_dir():
            continue
        for f in p.rglob("*"):
            try:
                if f.is_file() and not f.is_symlink() and f.stat().st_mtime < edge and f.suffix.lower() not in (".db", ".sqlite", ".sqlite3", ".json", ".env"):
                    f.unlink()
                    removed += 1
            except OSError:
                pass
    return removed


def start_janitor(dirs: Iterable[str | Path], max_age_hours: float | None = None, every_min: float = 60) -> threading.Thread:
    """Фоновая уборка папок кэша/вывода: сразу и затем раз в every_min минут.

    Срок хранения — CLEANUP_HOURS (по умолчанию 48 ч). CLEANUP_HOURS=0 в .env выключает уборку.
    """
    if str(os.environ.get("CLEANUP_HOURS", "")).strip() == "0":
        return threading.Thread(target=lambda: None)
    dirs = [Path(d) for d in dirs]

    def loop() -> None:
        while True:
            try:
                cleanup_old_files(dirs, max_age_hours)
            except Exception:
                pass
            time.sleep(every_min * 60)

    th = threading.Thread(target=loop, name="pybionic-janitor", daemon=True)
    th.start()
    return th


# ---------------------------------------------------------------------------
# Кнопки на всех языках
# ---------------------------------------------------------------------------
# Общие кнопки. Особые кнопки бота лежат в его locales.json (ключи btn_*).
BUTTONS: dict[str, dict[str, str]] = {
    "btn_lang": {
        "ru": "🌐 Выбрать язык",
        "en": "🌐 Language",
        "tg": "🌐 Интихоби забон",
        "uz": "🌐 Tilni tanlash",
        "tr": "🌐 Dil seç",
        "es": "🌐 Idioma",
        "de": "🌐 Sprache",
        "fr": "🌐 Langue",
        "it": "🌐 Lingua",
        "pt": "🌐 Idioma",
        "pl": "🌐 Język",
        "uk": "🌐 Мова",
        "kk": "🌐 Тілді таңдау",
        "ky": "🌐 Тил тандоо",
        "az": "🌐 Dili seç",
        "ar": "🌐 اللغة",
        "fa": "🌐 زبان",
        "hi": "🌐 भाषा",
        "zh-cn": "🌐 语言",
        "ja": "🌐 言語",
        "ko": "🌐 언어",
        "id": "🌐 Bahasa",
        "vi": "🌐 Ngôn ngữ",
        "th": "🌐 ภาษา"
    },
    "btn_help": {
        "ru": "ℹ️ Инструкция",
        "en": "ℹ️ Help",
        "tg": "ℹ️ Дастур",
        "uz": "ℹ️ Yoʻriqnoma",
        "tr": "ℹ️ Yardım",
        "es": "ℹ️ Ayuda",
        "de": "ℹ️ Hilfe",
        "fr": "ℹ️ Aide",
        "it": "ℹ️ Aiuto",
        "pt": "ℹ️ Ajuda",
        "pl": "ℹ️ Pomoc",
        "uk": "ℹ️ Інструкція",
        "kk": "ℹ️ Нұсқаулық",
        "ky": "ℹ️ Нускама",
        "az": "ℹ️ Təlimat",
        "ar": "ℹ️ مساعدة",
        "fa": "ℹ️ راهنما",
        "hi": "ℹ️ सहायता",
        "zh-cn": "ℹ️ 帮助",
        "ja": "ℹ️ ヘルプ",
        "ko": "ℹ️ 도움말",
        "id": "ℹ️ Bantuan",
        "vi": "ℹ️ Hướng dẫn",
        "th": "ℹ️ วิธีใช้"
    },
    "btn_menu": {
        "ru": "◀ Главное меню",
        "en": "◀ Main menu",
        "tg": "◀ Менюи асосӣ",
        "uz": "◀ Bosh menyu",
        "tr": "◀ Ana menü",
        "es": "◀ Menú principal",
        "de": "◀ Hauptmenü",
        "fr": "◀ Menu principal",
        "it": "◀ Menu principale",
        "pt": "◀ Menu principal",
        "pl": "◀ Menu główne",
        "uk": "◀ Головне меню",
        "kk": "◀ Басты мәзір",
        "ky": "◀ Башкы меню",
        "az": "◀ Əsas menyu",
        "ar": "◀ القائمة الرئيسية",
        "fa": "◀ منوی اصلی",
        "hi": "◀ मुख्य मेनू",
        "zh-cn": "◀ 主菜单",
        "ja": "◀ メインメニュー",
        "ko": "◀ 메인 메뉴",
        "id": "◀ Menu utama",
        "vi": "◀ Menu chính",
        "th": "◀ เมนูหลัก"
    },
    "btn_cancel": {
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
        "tg": "❌ Бекор кардан",
        "uz": "❌ Bekor qilish",
        "tr": "❌ İptal",
        "es": "❌ Cancelar",
        "de": "❌ Abbrechen",
        "fr": "❌ Annuler",
        "it": "❌ Annulla",
        "pt": "❌ Cancelar",
        "pl": "❌ Anuluj",
        "uk": "❌ Скасувати",
        "kk": "❌ Болдырмау",
        "ky": "❌ Жокко чыгаруу",
        "az": "❌ Ləğv et",
        "ar": "❌ إلغاء",
        "fa": "❌ لغو",
        "hi": "❌ रद्द करें",
        "zh-cn": "❌ 取消",
        "ja": "❌ キャンセル",
        "ko": "❌ 취소",
        "id": "❌ Batal",
        "vi": "❌ Hủy",
        "th": "❌ ยกเลิก"
    },
    "btn_back": {
        "ru": "🔙 Назад",
        "en": "🔙 Back",
        "tg": "🔙 Бозгашт",
        "uz": "🔙 Orqaga",
        "tr": "🔙 Geri",
        "es": "🔙 Atrás",
        "de": "🔙 Zurück",
        "fr": "🔙 Retour",
        "it": "🔙 Indietro",
        "pt": "🔙 Voltar",
        "pl": "🔙 Wstecz",
        "uk": "🔙 Назад",
        "kk": "🔙 Артқа",
        "ky": "🔙 Артка",
        "az": "🔙 Geri",
        "ar": "🔙 رجوع",
        "fa": "🔙 بازگشت",
        "hi": "🔙 वापस",
        "zh-cn": "🔙 返回",
        "ja": "🔙 戻る",
        "ko": "🔙 뒤로",
        "id": "🔙 Kembali",
        "vi": "🔙 Quay lại",
        "th": "🔙 ย้อนกลับ"
    }
}

# Старые надписи, которые уже висят на клавиатурах у пользователей
BUTTON_ALIASES: dict[str, list[str]] = {
    "btn_lang": [
        "🌐 Язык"
    ],
    "btn_help": [
        "ℹ️ Помощь"
    ],
    "btn_menu": [
        "◀ Назад"
    ],
    "btn_back": [
        "🔙 Назад / Back",
        "◀ Назад"
    ],
    "btn_cancel": [
        "❌ Отмена / Cancel"
    ]
}


def _user_lang(user_id: int | str | None) -> str:
    try:
        from i18n import get_user_lang

        return get_user_lang(user_id)
    except Exception:
        return "ru"


def btn(key: str, user_id: int | str | None = None) -> str:
    """Надпись кнопки на языке пользователя."""
    table = BUTTONS.get(key)
    if table is None:
        from i18n import t

        return t(key, user_id=user_id)
    lang = _user_lang(user_id)
    return table.get(lang) or table.get(lang.split("-")[0]) or table["en"]


_variants_cache: dict[str, frozenset[str]] = {}


def btn_variants(key: str) -> frozenset[str]:
    """Все надписи кнопки на всех языках (+ старые) — для сравнения текста."""
    if key not in _variants_cache:
        vals: set[str] = set(BUTTON_ALIASES.get(key, []))
        if key in BUTTONS:
            vals |= set(BUTTONS[key].values())
        else:
            try:
                from i18n import get_locales_dict

                entry = get_locales_dict().get("strings", {}).get(key)
                if isinstance(entry, dict):
                    vals |= {str(v) for v in entry.values()}
            except Exception:
                pass
        _variants_cache[key] = frozenset(vals)
    return _variants_cache[key]


def is_btn(text: str | None, *keys: str) -> bool:
    return bool(text) and any(text in btn_variants(k) for k in keys)


# ---------------------------------------------------------------------------
# Связь с Telegram: прокси и устойчивый запуск
# ---------------------------------------------------------------------------
TG_NO_NETWORK_HINT = (
    "Нет связи с api.telegram.org. Если Telegram заблокирован у провайдера — включите VPN на телефоне "
    "или задайте TELEGRAM_PROXY (например socks5h://IP:1080 или http://IP:8080). Повтор через {sec} с. / "
    "No connection to api.telegram.org — enable a VPN or set TELEGRAM_PROXY. Retrying in {sec}s."
)


def setup_telegram_proxy() -> str:
    """TELEGRAM_PROXY из .env → прокси для всех запросов telebot. Возвращает адрес или ''."""
    proxy = str(os.environ.get("TELEGRAM_PROXY", "")).strip()
    if not proxy:
        return ""
    try:
        from telebot import apihelper

        apihelper.proxy = {"https": proxy, "http": proxy}
    except Exception:
        return ""
    return proxy


def _is_network_error(e: BaseException) -> bool:
    name = type(e).__name__
    text = str(e).lower()
    return name in ("ConnectionError", "ConnectTimeout", "ReadTimeout", "ProxyError", "SSLError", "Timeout") or any(
        s in text for s in ("network is unreachable", "timed out", "max retries", "connection refused", "name or service not known")
    )


def call_with_retry(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Повторяет вызов Bot API, пока нет сети (для get_me() и т.п. при старте)."""
    delay = 5
    while True:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if not _is_network_error(e):
                raise
            print(TG_NO_NETWORK_HINT.format(sec=delay), flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 300)


def start_polling(bot: Any, **kwargs: Any) -> None:
    """bot.infinity_polling, который не падает без интернета/при блокировке, а ждёт и повторяет."""
    setup_telegram_proxy()
    delay = 5
    while True:
        try:
            bot.infinity_polling(**kwargs)
            return
        except KeyboardInterrupt:
            return
        except Exception as e:
            if not _is_network_error(e):
                raise
            print(TG_NO_NETWORK_HINT.format(sec=delay), flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 300)


setup_telegram_proxy()
