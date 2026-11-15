"""Media Downloader Studio — High-speed video & audio downloader (yt-dlp + ffmpeg).
100% ReplyKeyboardMarkup (keyboard buttons only, no inline text buttons), 24 languages, and local Cyberpunk Web Studio.
"""

from __future__ import annotations

import pybionic_core as core
import pybionic_web as web
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

    if progress_cb:
        ydl_opts["progress_hooks"] = [progress_cb]

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


def friendly_error(exc: Exception) -> str:
    """Понятный ключ ошибки для веб-страницы вместо сырого текста yt-dlp."""
    s = str(exc).lower()
    if ("unsupported url" in s or "is not a valid url" in s or "no video formats" in s or "404" in s
            or "not found" in s or "unable to download webpage" in s or "unable to extract" in s):
        return "w_err_unsupported"
    if "private" in s or "unavailable" in s or "removed" in s or "sign in" in s or "login" in s:
        return "w_err_private"
    if "ffmpeg" in s or "ffprobe" in s:
        return "w_err_ffmpeg"
    if "timed out" in s or "network" in s or "resolve" in s or "connection" in s or "urlopen" in s:
        return "w_err_network"
    return "error"


_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _run_job(job_id: str, url: str, fmt: str) -> None:
    job = _JOBS[job_id]

    def hook(d: dict[str, Any]) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            job.update(state="downloading", pct=round(done * 100 / total) if total else None,
                       speed=d.get("speed") or 0, done=done, total=total)
        elif d.get("status") == "finished":
            job.update(state="processing", pct=100)

    try:
        out_file, title = download_media(url, fmt, get_downloads_dir(), progress_cb=hook)
        record_downloaded_file(out_file.name, title, out_file.stat().st_size, fmt)
        job.update(state="done", title=title, filename=out_file.name)
    except Exception as exc:  # noqa: BLE001
        job.update(state="error", error_key=friendly_error(exc), error=str(exc)[:300])


def list_files() -> list[dict[str, Any]]:
    """Только файлы, которые реально лежат на диске (старые могла убрать автоочистка)."""
    out = []
    with sqlite3.connect(get_data_dir() / "downloader.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM downloaded_files ORDER BY id DESC LIMIT 50").fetchall()
    base = get_downloads_dir()
    for r in rows:
        p = base / r["filename"]
        if p.is_file():
            out.append({"filename": r["filename"], "title": r["title"], "size": p.stat().st_size,
                        "fmt": r["fmt"], "created": r["created_at"]})
    return out


def render_web_page(handler: Any, port: int) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    hours = os.environ.get("CLEANUP_HOURS", "48").strip() or "48"
    form = (
        web.field(T("w_url_label"), '<div class="pb-row">' + web.input_("dl-url", T("w_url_ph"), type="url", inputmode="url",
                                                                         autocomplete="off", icon_name="link")
                  + web.button(T("w_paste"), "dl-paste", kind="ghost", icon_name="clipboard") + "</div>", for_="dl-url")
        + web.field(T("format"), web.segmented("dl-fmt", [("mp4", T("w_fmt_video")), ("mp3", T("w_fmt_audio"))], "mp4",
                                                sub={"mp4": T("w_fmt_video_sub"), "mp3": T("w_fmt_audio_sub")},
                                                icons={"mp4": "film", "mp3": "music"}))
        + web.button(T("w_download_btn"), "dl-go", icon_name="download")
        + web.progress("dl-prog")
    )
    files_card = web.card(T("w_card_files"), '<div class="pb-list" id="files"><div class="pb-skel"></div></div>'
                          + web.empty_state(T("w_files_empty"), "film", id="files-empty")
                          + web.note(T("w_cleanup_note", hours=hours), icon_name="clock"), icon_name="folder",
                          aside=web.button(T("refresh"), "files-refresh", kind="ghost", icon_name="refresh", cls="pb-btn-sm"))
    hero = web.hero(T("web_title"), T("w_hero"), "⚡", chips=["YouTube", "TikTok", "Instagram", "VK", "SoundCloud"])
    body = web.grid(web.card(T("w_card_new"), form, icon_name="link"), files_card, min_width=340)
    web.send_page(handler, lang, title=T("web_title"), emoji="⚡", brand="#0a84ff", port=port,
                  hero_html=hero, body=body, script=MD_JS)


MD_JS = r"""
const $=s=>document.querySelector(s);
const fmtEl=$('#dl-fmt'), go=$('#dl-go');
$('#dl-paste').onclick=async()=>{try{const t=await navigator.clipboard.readText();if(t)$('#dl-url').value=t.trim()}catch(e){$('#dl-url').focus()}};
async function loadFiles(){
  const d=await pb.json('/api/files').catch(()=>({files:[]}));const list=$('#files');const fs=d.files||[];
  $('#files-empty').hidden=fs.length>0;
  list.innerHTML=fs.map(f=>{const u='/files/'+encodeURIComponent(f.filename);const v=f.fmt==='mp4';
   return `<div class="pb-item"><div class="pb-item-top"><span class="pb-item-ico">${v?'🎬':'🎵'}</span><div><b>${pb.esc(f.title)}</b>
   <div class="pb-meta"><span class="pb-tag">${pb.esc(f.fmt.toUpperCase())}</span><span>${pb.bytes(f.size)}</span><span>${new Date(f.created*1000).toLocaleString(PB_LANG)}</span></div></div></div>
   ${v?`<video src="${u}" controls preload="none"></video>`:`<audio src="${u}" controls preload="none"></audio>`}
   <div class="pb-row"><a class="pb-btn pb-btn-ghost pb-btn-sm" href="${u}" download>⬇ ${pb.t('download')}</a>
   <button class="pb-btn pb-btn-danger pb-btn-sm" data-del="${pb.esc(f.filename)}" data-title="${pb.esc(f.title)}">${pb.t('delete')}</button></div></div>`}).join('');
}
$('#files').addEventListener('click',async e=>{const b=e.target.closest('[data-del]');if(!b)return;
  if(!confirm(pb.t('w_delete_q',{name:b.dataset.title})))return;
  const d=await pb.post('/api/delete',{filename:b.dataset.del});if(d.ok){pb.toast(pb.t('deleted'));loadFiles()}else pb.toast(pb.t('error')+': '+(d.error||''),true)});
$('#files-refresh').onclick=loadFiles;
go.onclick=async()=>{
  const url=$('#dl-url').value.trim();if(!url){pb.toast(pb.t('w_need_url'),true);$('#dl-url').focus();return}
  pb.busy(go,true);pb.progress('dl-prog',null,pb.t('processing'));
  try{
    const d=await pb.post('/api/download',{url,fmt:fmtEl.dataset.value});
    if(!d.ok){throw new Error(d.error_key?pb.t(d.error_key):(d.error||pb.t('error')))}
    while(true){
      await new Promise(r=>setTimeout(r,800));
      const j=await pb.json('/api/job?id='+encodeURIComponent(d.job));
      if(j.state==='downloading'){pb.progress('dl-prog',j.pct,pb.t('w_dl_progress',{pct:j.pct==null?'…':j.pct,speed:j.speed?pb.bytes(j.speed)+'/s':''}))}
      else if(j.state==='processing'){pb.progress('dl-prog',null,pb.t('w_dl_converting'))}
      else if(j.state==='done'){pb.progress('dl-prog',100,pb.t('w_dl_done',{title:j.title}));pb.toast(pb.t('done'));$('#dl-url').value='';loadFiles();break}
      else if(j.state==='error'){throw new Error(pb.t(j.error_key||'error')+(j.error_key==='error'&&j.error?': '+j.error:''))}
    }
  }catch(err){pb.progress('dl-prog',0,'');pb.hide('dl-prog');pb.toast(err.message,true)}
  finally{pb.busy(go,false)}
};
$('#dl-url').addEventListener('keydown',e=>{if(e.key==='Enter')go.click()});
loadFiles();
"""


def start_web_studio(port: int) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            if path.startswith("/files/"):
                return self._send_file(urllib.parse.unquote(path[len("/files/"):]))
            if path == "/api/files":
                return web.send_json(self, {"ok": True, "files": list_files()})
            if path == "/api/job":
                jid = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("id", [""])[0]
                job = _JOBS.get(jid)
                return web.send_json(self, job or {"state": "error", "error_key": "error"}, 200 if job else 404)
            if path in ("/", "/index.html"):
                return render_web_page(self, port)
            self.send_error(404)

        def _send_file(self, name: str) -> None:
            fname = os.path.basename(name)
            fpath = (get_downloads_dir() / fname).resolve()
            if not (fpath.is_file() and fpath.is_relative_to(get_downloads_dir().resolve())):
                return self.send_error(404)
            ctype = "video/mp4" if fname.endswith(".mp4") else "audio/mpeg" if fname.endswith(".mp3") else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(fpath.stat().st_size))
            self.send_header("Content-Disposition", "inline; filename*=UTF-8''" + urllib.parse.quote(fname))
            self.end_headers()
            with fpath.open("rb") as fh:
                shutil.copyfileobj(fh, self.wfile)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or 0)
            params = urllib.parse.parse_qs(self.rfile.read(min(length, 1024 * 1024)).decode("utf-8", errors="replace"))
            if self.path == "/api/download":
                url = (params.get("url") or [""])[0].strip()
                fmt = "mp3" if (params.get("fmt") or ["mp4"])[0].strip() == "mp3" else "mp4"
                if not URL_RE.match(url):
                    return web.send_json(self, {"ok": False, "error_key": "w_err_unsupported"})
                job_id = f"{int(time.time() * 1000)}"
                with _JOBS_LOCK:
                    _JOBS[job_id] = {"state": "queued", "pct": 0}
                    for old in sorted(_JOBS)[:-30]:
                        _JOBS.pop(old, None)
                threading.Thread(target=_run_job, args=(job_id, url, fmt), daemon=True).start()
                return web.send_json(self, {"ok": True, "job": job_id})
            if self.path == "/api/delete":
                fname = os.path.basename((params.get("filename") or [""])[0])
                fpath = (get_downloads_dir() / fname).resolve()
                if fname and fpath.is_file() and fpath.is_relative_to(get_downloads_dir().resolve()):
                    fpath.unlink()
                    with sqlite3.connect(get_data_dir() / "downloader.db") as conn:
                        conn.execute("DELETE FROM downloaded_files WHERE filename = ?", (fname,))
                    return web.send_json(self, {"ok": True})
                return web.send_json(self, {"ok": False, "error": "not found"}, 404)
            self.send_error(404)

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
    core.guard_bot(bot)
    core.start_janitor([core.get_data_dir() / "downloads"])

    def build_main_reply_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(core.btn("kb_mp4", uid)),
            types.KeyboardButton(core.btn("kb_mp3", uid)),
        )
        kb.row(
            types.KeyboardButton(core.btn("btn_lang", uid)),
            types.KeyboardButton(core.btn("btn_help", uid)),
        )
        return kb

    def build_format_picker_kb(uid: int | None = None) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(core.btn("kb_mp4", uid)),
            types.KeyboardButton(core.btn("kb_mp3", uid)),
        )
        kb.row(
            types.KeyboardButton(core.btn("btn_cancel", uid)),
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
            reply_markup=build_reply_language_keyboard(user_id=uid, back_text=core.btn("btn_menu", uid)),
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

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_menu", "btn_cancel"))
    def on_cancel_or_back(msg: Any) -> None:
        uid = msg.from_user.id
        clear_user_pending_url(uid)
        bot.reply_to(msg, "Главное меню:", reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_lang"))
    def on_lang_button(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            t("tg_lang_title", user_id=uid),
            reply_markup=build_reply_language_keyboard(user_id=uid, back_text=core.btn("btn_menu", uid)),
        )

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_help"))
    def on_help_button(msg: Any) -> None:
        on_help(msg)

    # Handling format buttons from bottom keyboard
    @bot.message_handler(func=lambda m: core.is_btn(m.text, "kb_mp4", "kb_mp3"))
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
            reply_markup=build_format_picker_kb(uid),
        )

    log("log_started")
    core.start_polling(bot, timeout=30, long_polling_timeout=25)


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
