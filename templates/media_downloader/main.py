"""Media Downloader Studio — High-speed video & audio downloader (yt-dlp + ffmpeg).
100% ReplyKeyboardMarkup (keyboard buttons only, no inline text buttons), 24 languages, and local Cyberpunk Web Studio.
"""

from __future__ import annotations

import html
import http.server
import json
import os
import re
import shutil
import socketserver
import sqlite3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

from i18n import (
    SUPPORTED_LANGUAGES,
    build_reply_language_keyboard,
    current_lang,
    get_user_lang,
    is_rtl,
    log,
    parse_lang_choice,
    set_user_lang,
    t,
)

URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def get_data_dir() -> Path:
    d = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_downloads_dir() -> Path:
    d = get_data_dir() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def init_db() -> None:
    db = get_data_dir() / "downloader.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_users (
                user_id INTEGER PRIMARY KEY,
                url TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS downloaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                filesize INTEGER NOT NULL,
                fmt TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )


def set_user_pending_url(user_id: int, url: str) -> None:
    db = get_data_dir() / "downloader.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pending_users (user_id, url, updated_at) VALUES (?, ?, ?)",
            (user_id, url, time.time()),
        )


def get_user_pending_url(user_id: int) -> str | None:
    db = get_data_dir() / "downloader.db"
    try:
        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT url FROM pending_users WHERE user_id = ?", (user_id,)).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return None


def clear_user_pending_url(user_id: int) -> None:
    db = get_data_dir() / "downloader.db"
    try:
        with sqlite3.connect(db) as conn:
            conn.execute("DELETE FROM pending_users WHERE user_id = ?", (user_id,))
    except Exception:
        pass


def record_downloaded_file(filename: str, title: str, filesize: int, fmt: str) -> None:
    db = get_data_dir() / "downloader.db"
    try:
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO downloaded_files (filename, title, filesize, fmt, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (filename, title, filesize, fmt, time.time()),
            )
    except Exception:
        pass


def is_user_allowed(user_id: int | str) -> bool:
    raw = os.environ.get("ALLOWED_USER_IDS", "").strip()
    if not raw:
        return True
    allowed = {x.strip() for x in raw.split(",") if x.strip()}
    return str(user_id).strip() in allowed


def download_media(url: str, fmt: str, out_dir: Path, progress_cb: Any = None) -> tuple[Path, str]:
    import yt_dlp

    ydl_opts: dict[str, Any] = {
        "outtmpl": str(out_dir / "%(title).100B-%(id)s.%(ext)s"),
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    if fmt == "mp3":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title") or "download"
        if fmt == "mp3":
            base = ydl.prepare_filename(info)
            expected = Path(os.path.splitext(base)[0] + ".mp3")
            if not expected.is_file():
                for p in out_dir.glob("*.mp3"):
                    if p.is_file():
                        expected = p
                        break
            return expected, title
        else:
            final_p = Path(ydl.prepare_filename(info))
            if not final_p.is_file():
                for ext in (".mp4", ".mkv", ".webm"):
                    cand = final_p.with_suffix(ext)
                    if cand.is_file():
                        final_p = cand
                        break
            return final_p, title


def start_web_studio(port: int) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            u = urllib.parse.urlparse(self.path)
            lang = urllib.parse.parse_qs(u.query).get("lang", [current_lang()])[0]
            rtl_attr = ' dir="rtl"' if is_rtl(lang) else ""

            lang_options = "\n".join(
                f'<option value="{code}"{" selected" if code == lang else ""}>{html.escape(label)}</option>'
                for code, label in SUPPORTED_LANGUAGES
            )

            with sqlite3.connect(get_data_dir() / "downloader.db") as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM downloaded_files ORDER BY id DESC LIMIT 20").fetchall()

            files_html = ""
            for r in rows:
                mb = round(r["filesize"] / (1024 * 1024), 1)
                is_video = r["fmt"].lower() == "mp4"
                play_ctrl = f'<video src="/files/{html.escape(r["filename"])}" controls style="width:100%;max-height:240px;margin-top:8px;border-radius:8px"></video>' if is_video else f'<audio src="/files/{html.escape(r["filename"])}" controls style="width:100%;margin-top:8px"></audio>'
                files_html += f"""
                <div class="file-card">
                  <div style="font-weight:700;font-size:15px">{html.escape(r['title'])}</div>
                  <div style="font-size:12px;color:var(--text-dim);margin-top:4px">
                    <span class="badge">{html.escape(r['fmt'].upper())}</span> • {mb} MB • <a href="/files/{html.escape(r['filename'])}" download style="color:var(--accent-cyan);text-decoration:none;font-weight:600">⬇ Скачать</a>
                  </div>
                  {play_ctrl}
                </div>
                """

            html_page = f"""<!doctype html>
<html lang="{lang}"{rtl_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(t('web_title', lang_override=lang))}</title>
<style>
:root {{
  --bg-deep: #0A0F1A;
  --bg-card: #121A2B;
  --bg-input: #0D1322;
  --accent-cyan: #00D8FF;
  --accent-emerald: #00E676;
  --accent-gold: #FFC107;
  --text-main: #E6F1FF;
  --text-dim: #8BA0C6;
  --border: #1F2D4A;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg-deep);
  color: var(--text-main);
  font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  padding: 16px;
  max-width: 680px;
  margin: 0 auto;
}}
header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
}}
.brand {{ font-size: 20px; font-weight: 800; color: var(--accent-cyan); }}
.lang-sel {{
  background: var(--bg-input);
  color: var(--text-main);
  border: 1px solid var(--border);
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 13px;
}}
.card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}}
input, select, button {{
  width: 100%;
  padding: 12px;
  margin-top: 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text-main);
  font-size: 15px;
}}
button.primary {{
  background: linear-gradient(135deg, #00D8FF, #0088cc);
  color: #001B2E;
  font-weight: 700;
  border: none;
  cursor: pointer;
}}
button.primary:hover {{ opacity: 0.95; }}
.file-card {{
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
  margin-top: 12px;
}}
.badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
  background: rgba(0, 216, 255, 0.15);
  color: var(--accent-cyan);
}}
</style>
</head>
<body>
<header>
  <div class="brand">⚡ Media Downloader Pro</div>
  <select class="lang-sel" onchange="location.href='/?lang='+this.value">
    {lang_options}
  </select>
</header>

<div class="card">
  <h2>{html.escape(t('web_title', lang_override=lang))}</h2>
  <p style="color:var(--text-dim);margin-top:6px;font-size:14px">{html.escape(t('web_subtitle', lang_override=lang))}</p>
  <form id="dl-form">
    <input type="text" id="dl-url" placeholder="Вставьте ссылку YouTube, TikTok, VK, Rutube..." required>
    <select id="dl-fmt">
      <option value="mp4">🎬 Видео MP4 (Высокое качество)</option>
      <option value="mp3">🎵 Аудио MP3 (192 kbps)</option>
    </select>
    <button type="submit" class="primary">⬇ Скачать через Web Studio</button>
  </form>
  <div id="dl-status" style="margin-top:12px;text-align:center;font-size:14px;color:var(--accent-gold)"></div>
</div>

<div class="card">
  <h3>📁 Скачанные медиафайлы</h3>
  <div id="files-list">
    {files_html or '<div style="color:var(--text-dim);margin-top:10px">Файлов пока нет. Скачайте первое видео выше!</div>'}
  </div>
</div>

<script>
document.getElementById('dl-form').onsubmit = async (e) => {{
  e.preventDefault();
  const url = document.getElementById('dl-url').value;
  const fmt = document.getElementById('dl-fmt').value;
  const status = document.getElementById('dl-status');
  status.textContent = '⏳ Идет загрузка и конвертация медиа... Пожалуйста, подождите.';

  try {{
    const res = await fetch('/api/download', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: new URLSearchParams({{ url, fmt }})
    }});
    const data = await res.json();
    if (data.ok) {{
      status.textContent = '✅ Загрузка завершена!';
      setTimeout(() => location.reload(), 800);
    }} else {{
      status.textContent = '❌ Ошибка: ' + (data.error || 'неизвестная ошибка');
    }}
  }} catch (err) {{
    status.textContent = '❌ Ошибка соединения: ' + err;
  }}
}};
</script>
</body>
</html>
"""
            raw = html_page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            if self.path == "/api/download":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(min(length, 1024 * 1024)).decode("utf-8", errors="replace")
                params = urllib.parse.parse_qs(raw)
                url = (params.get("url") or [""])[0].strip()
                fmt = (params.get("fmt") or ["mp4"])[0].strip()
                try:
                    out_file, title = download_media(url, fmt, get_downloads_dir())
                    record_downloaded_file(out_file.name, title, out_file.stat().st_size, fmt)
                    payload = json.dumps({"ok": True, "filename": out_file.name, "title": title}).encode("utf-8")
                except Exception as exc:
                    payload = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_error(404)

    orig_get = Handler.do_GET

    def wrapped_get(self: Handler) -> None:
        if self.path.startswith("/files/"):
            fname = os.path.basename(urllib.parse.urlparse(self.path).path)
            fpath = (get_downloads_dir() / fname).resolve()
            if fpath.is_file() and fpath.is_relative_to(get_downloads_dir().resolve()):
                self.send_response(200)
                if fname.endswith(".mp4"):
                    self.send_header("Content-Type", "video/mp4")
                elif fname.endswith(".mp3"):
                    self.send_header("Content-Type", "audio/mpeg")
                else:
                    self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(fpath.stat().st_size))
                self.end_headers()
                with fpath.open("rb") as fh:
                    shutil.copyfileobj(fh, self.wfile)
                return
            self.send_error(404)
            return
        orig_get(self)

    Handler.do_GET = wrapped_get  # type: ignore[method-assign]

    class Reusable(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    def serve() -> None:
        try:
            with Reusable((os.environ.get("BIND_HOST", "127.0.0.1"), port), Handler) as srv:
                print(f"[PYBIONIC_WEB:{port}]", flush=True)
                log("log_web_started", port=port)
                srv.serve_forever()
        except Exception as exc:
            log("log_error", err=f"Web server failed on port {port}: {exc}")

    threading.Thread(target=serve, daemon=True).start()


def run_telegram_bot(token: str) -> None:
    import telebot
    from telebot import types

    init_db()
    bot = telebot.TeleBot(token, parse_mode="HTML")

    def build_main_reply_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton("🎬 MP4 (Видео)"),
            types.KeyboardButton("🎵 MP3 (Аудио)"),
        )
        kb.row(
            types.KeyboardButton("🌐 Выбрать язык"),
            types.KeyboardButton("ℹ️ Инструкция"),
        )
        return kb

    def build_format_picker_kb() -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton("🎬 MP4 (Видео)"),
            types.KeyboardButton("🎵 MP3 (Аудио)"),
        )
        kb.row(
            types.KeyboardButton("❌ Отмена"),
        )
        return kb

    @bot.message_handler(commands=["start"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_welcome", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(commands=["help"])
    def on_help(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            "⚡ <b>Media Downloader Pro</b>\n\n"
            "1. Отправьте ссылку на видео (YouTube, TikTok, VK, Rutube, Instagram...)\n"
            "2. Выберите формат <b>MP4</b> или <b>MP3</b> на панели клавиатуры внизу экрана!\n"
            "3. Бот мгновенно скачает и пришлет файл.\n\n"
            "Кнопка 🌐 Выбрать язык на клавиатуре меняет язык интерфейса.",
            reply_markup=build_main_reply_kb(uid),
        )

    @bot.message_handler(commands=["lang", "language"])
    def on_lang_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            t("tg_lang_title", user_id=uid),
            reply_markup=build_reply_language_keyboard(user_id=uid, back_text="◀ Главное меню"),
        )

    @bot.message_handler(func=lambda m: bool(m.text and parse_lang_choice(m.text)))
    def on_lang_chosen(msg: Any) -> None:
        uid = msg.from_user.id
        code = parse_lang_choice(msg.text)
        if code:
            set_user_lang(uid, code)
            bot.reply_to(
                msg,
                t("tg_lang_changed", user_id=uid),
                reply_markup=build_main_reply_kb(uid),
            )

    @bot.message_handler(func=lambda m: m.text in ("◀ Главное меню", "❌ Отмена", "◀ Назад"))
    def on_cancel_or_back(msg: Any) -> None:
        uid = msg.from_user.id
        clear_user_pending_url(uid)
        bot.reply_to(msg, "Главное меню:", reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: m.text in ("🌐 Выбрать язык", "🌐 Язык"))
    def on_lang_button(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            t("tg_lang_title", user_id=uid),
            reply_markup=build_reply_language_keyboard(user_id=uid, back_text="◀ Главное меню"),
        )

    @bot.message_handler(func=lambda m: m.text in ("ℹ️ Инструкция", "ℹ️ Помощь"))
    def on_help_button(msg: Any) -> None:
        on_help(msg)

    # Handling format buttons from bottom keyboard
    @bot.message_handler(func=lambda m: m.text in ("🎬 MP4 (Видео)", "🎵 MP3 (Аудио)", "🎬 Скачать MP4", "🎵 Скачать MP3"))
    def on_format_button(msg: Any) -> None:
        uid = msg.from_user.id
        pending_url = get_user_pending_url(uid)
        if not pending_url:
            bot.reply_to(
                msg,
                "Сначала отправьте ссылку на видео или трек (YouTube, TikTok, VK, Rutube...)!",
                reply_markup=build_main_reply_kb(uid),
            )
            return

        fmt = "mp3" if "MP3" in (msg.text or "") else "mp4"
        start_download_task(msg, pending_url, fmt)

    def start_download_task(msg: Any, url: str, fmt: str) -> None:
        uid = msg.from_user.id
        clear_user_pending_url(uid)
        status = bot.reply_to(msg, t("tg_working", user_id=uid), reply_markup=build_main_reply_kb(uid))

        def run_task():
            try:
                bot.edit_message_text("⏳ Скачивание и обработка медиа...", msg.chat.id, status.message_id)
                out_p, title = download_media(url, fmt, get_downloads_dir())
                sz = out_p.stat().st_size
                record_downloaded_file(out_p.name, title, sz, fmt)

                # Telegram 50MB bot upload limit check
                if sz > 49 * 1024 * 1024:
                    port = os.environ.get("WEB_PORT", "8088")
                    bot.edit_message_text(
                        f"⚠️ Файл слишком большой для Telegram ({round(sz / (1024 * 1024), 1)} MB > 50 MB)!\n\n"
                        f"⬇ Скачайте его через локальную веб-панель: http://localhost:{port}/files/{out_p.name}",
                        msg.chat.id,
                        status.message_id,
                    )
                    return

                bot.edit_message_text("📤 Отправка файла в Telegram...", msg.chat.id, status.message_id)
                with out_p.open("rb") as fh:
                    if fmt == "mp3":
                        bot.send_audio(msg.chat.id, fh, caption=f"🎵 {title[:100]}")
                    else:
                        bot.send_video(msg.chat.id, fh, caption=f"🎬 {title[:100]}")

                try:
                    bot.delete_message(msg.chat.id, status.message_id)
                except Exception:
                    pass
                log("log_download_done", fmt=fmt.upper(), title=title[:40])
            except Exception as exc:
                log("log_error", err=str(exc))
                try:
                    bot.edit_message_text(f"❌ Ошибка загрузки: {str(exc)[:200]}", msg.chat.id, status.message_id)
                except Exception:
                    bot.reply_to(msg, f"❌ Ошибка загрузки: {str(exc)[:200]}")

        threading.Thread(target=run_task, daemon=True).start()

    # URL message receiver
    @bot.message_handler(func=lambda m: bool(m.text and URL_RE.search(m.text)))
    def on_url(msg: Any) -> None:
        uid = msg.from_user.id
        if not is_user_allowed(uid):
            bot.reply_to(msg, t("err_access_denied", user_id=uid))
            return

        match = URL_RE.search(msg.text or "")
        if not match:
            return
        url = match.group(0)
        set_user_pending_url(uid, url)

        bot.reply_to(
            msg,
            f"🔗 <b>Ссылка получена!</b>\n\nВыберите формат на клавиатуре внизу:",
            reply_markup=build_format_picker_kb(),
        )

    log("log_started")
    bot.infinity_polling(timeout=30, long_polling_timeout=25)


def main() -> int:
    init_db()
    port_raw = os.environ.get("WEB_PORT", "8088").strip()
    if port_raw.isdigit() and int(port_raw) > 0:
        start_web_studio(int(port_raw))

    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        run_telegram_bot(token)
    elif port_raw.isdigit() and int(port_raw) > 0:
        log("log_web_only", port=port_raw)
        while True:
            time.sleep(3600)
    else:
        log("err_missing_token")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
