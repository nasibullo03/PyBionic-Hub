"""StickerPack Studio — Convert single Telegram stickers or whole packs (PNG, WebP, GIF, MP4, TGS JSON + ZIP).
100% ReplyKeyboardMarkup (all buttons next to keyboard, zero inline text buttons), 24 languages, and offline Web Studio.
"""

from __future__ import annotations

import pybionic_core as core
import pybionic_web as web
import base64
import gzip
import html
import http.server
import io
import json
import os
import re
import shutil
import socketserver
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
import urllib.parse
import zipfile
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

PACK_RE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/addstickers/([A-Za-z0-9_]+)", re.IGNORECASE)


def get_data_dir() -> Path:
    d = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    d.mkdir(parents=True, exist_ok=True)
    return d


def init_db() -> None:
    db = get_data_dir() / "sticker_jobs.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_users (
                user_id INTEGER PRIMARY KEY,
                job_type TEXT NOT NULL,
                file_id TEXT DEFAULT '',
                kind TEXT DEFAULT '',
                set_name TEXT DEFAULT '',
                updated_at REAL NOT NULL
            )
            """
        )


def set_user_pending_job(user_id: int, job_type: str, file_id: str = "", kind: str = "", set_name: str = "") -> None:
    db = get_data_dir() / "sticker_jobs.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO pending_users (user_id, job_type, file_id, kind, set_name, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, job_type, file_id, kind, set_name, time.time()),
        )


def get_user_pending_job(user_id: int) -> dict[str, Any] | None:
    db = get_data_dir() / "sticker_jobs.db"
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM pending_users WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)
    except Exception:
        pass
    return None


def clear_user_pending_job(user_id: int) -> None:
    db = get_data_dir() / "sticker_jobs.db"
    try:
        with sqlite3.connect(db) as conn:
            conn.execute("DELETE FROM pending_users WHERE user_id = ?", (user_id,))
    except Exception:
        pass


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg") or (
        os.path.join(os.environ.get("PREFIX", ""), "bin", "ffmpeg")
        if os.environ.get("PREFIX")
        else None
    )


def convert_single_bytes(raw_bytes: bytes, kind: str, target_fmt: str, stem: str, out_dir: Path) -> Path:
    target_fmt = target_fmt.lower().strip()
    if kind == "tgs":
        json_path = out_dir / f"{stem}.lottie.json"
        try:
            json_bytes = gzip.decompress(raw_bytes)
            json_path.write_bytes(json_bytes)
        except Exception:
            json_path.write_bytes(raw_bytes)
        if target_fmt in ("json", "lottie"):
            return json_path
        tgs_path = out_dir / f"{stem}.tgs"
        tgs_path.write_bytes(raw_bytes)
        return json_path

    src_path = out_dir / f"{stem}.{kind}"
    src_path.write_bytes(raw_bytes)

    if target_fmt == kind:
        return src_path

    if kind == "webp" and target_fmt in {"png", "webp"}:
        try:
            from PIL import Image

            out_path = out_dir / f"{stem}.{target_fmt}"
            with Image.open(src_path) as im:
                im.save(out_path, format=target_fmt.upper())
            return out_path
        except Exception:
            pass

    ff = ffmpeg_path()
    if ff and os.path.isfile(ff):
        out_path = out_dir / f"{stem}.{target_fmt}"
        if target_fmt == "gif":
            cmd = [
                ff, "-y", "-i", str(src_path),
                "-vf", "fps=20,scale=320:-1:flags=lanczos,split[s0][s1];[s0]palettegen=reserve_transparent=on[p];[s1][p]paletteuse",
                "-loop", "0", str(out_path),
            ]
        elif target_fmt == "mp4":
            cmd = [
                ff, "-y", "-i", str(src_path),
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2:color=black",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
                str(out_path),
            ]
        else:
            cmd = [ff, "-y", "-i", str(src_path), str(out_path)]
        try:
            res = core.run_media(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
                return out_path
        except Exception:
            pass

    if kind == "webp":
        try:
            from PIL import Image

            out_path = out_dir / f"{stem}.png"
            with Image.open(src_path) as im:
                im.save(out_path, format="PNG")
            return out_path
        except Exception:
            pass

    return src_path


def detect_sticker_kind(sticker: Any) -> str:
    if getattr(sticker, "is_video", False):
        return "webm"
    if getattr(sticker, "is_animated", False):
        return "tgs"
    return "webp"


def render_studio(handler: Any, port: int) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    fmts = [("png", "PNG"), ("gif", "GIF"), ("mp4", "MP4"), ("webp", "WebP"), ("json", "Lottie")]
    sub = {"png": T("w_fmt_png"), "gif": T("w_fmt_gif"), "mp4": T("w_fmt_mp4"), "webp": T("w_fmt_webp"), "json": ".tgs → JSON"}
    css = ("<style>.st-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px}"
           ".st-cell{display:grid;gap:6px;padding:8px;border-radius:12px;background:var(--surface2);border:1px solid var(--line);text-align:center;font-size:12px;animation:pbup .4s var(--ease) both}"
           ".st-cell img,.st-cell video{width:100%;aspect-ratio:1;object-fit:contain;border-radius:8px;background:repeating-conic-gradient(var(--surface2) 0 25%,transparent 0 50%) 0 0/16px 16px}"
           ".st-cell a{color:var(--brand);text-decoration:none;font-weight:600;overflow-wrap:anywhere}</style>")
    left = web.card(T("web_title"), web.dropzone("fi", T("drop_stickers_here"), "WebP · WebM · TGS", accept=".webp,.webm,.tgs", multiple=True, icon_name="image")
                    + web.field(T("w_target_fmt"), web.segmented("fmt", fmts, "png", sub=sub))
                    + web.button(T("btn_convert"), "go", icon_name="sparkles", disabled=True) + web.progress("prog"), icon_name="image")
    right = web.card(T("w_ready_files"), '<div class="st-grid" id="grid"></div>' + web.empty_state(T("w_files_empty"), "image", id="empty")
                     + '<a class="pb-btn pb-btn-primary" id="zip" hidden download>' + web.icon("download") + f'<span>{web.esc(T("btn_download_zip"))}</span></a>',
                     icon_name="folder")
    hero = web.hero(T("w_title"), T("web_subtitle"), "🎨", chips=["WebP", "WebM", "TGS", "PNG · GIF · MP4"])
    web.send_page(handler, lang, title=T("w_title"), emoji="🎨", brand="#f59e0b", port=port,
                  hero_html=hero, body=css + web.grid(left, right, min_width=330), script=STICKER_JS)


STICKER_JS = r"""
const $=s=>document.querySelector(s);let files=[];const go=$('#go');
$('#fi-zone').addEventListener('pb:files',e=>{files=e.detail;go.disabled=!files.length});
go.onclick=async()=>{if(!files.length){pb.toast(pb.t('w_need_stickers'),true);return}
  pb.busy(go,true);const fmt=$('#fmt').dataset.value;const fd=new FormData();fd.append('fmt',fmt);files.forEach(f=>fd.append('files',f));
  try{const d=await pb.upload('/api/convert',fd,p=>pb.progress('prog',p<100?p:null,p<100?pb.t('uploading',{pct:p}):pb.t('processing')));
    if(!d.files)throw new Error(d.error||pb.t('error'));pb.progress('prog',100,pb.t('w_processed',{n:d.files.length}));
    $('#empty').hidden=d.files.length>0;
    $('#grid').innerHTML=d.files.map(f=>{const u=pb.esc(f.url);const m=fmt==='mp4'?`<video src="${u}" autoplay loop muted playsinline></video>`:(fmt==='json'?`<span class="pb-tag">JSON</span>`:`<img src="${u}" alt="">`);
      return `<div class="st-cell">${m}<a href="${u}" download="${pb.esc(f.name)}">${pb.esc(f.name)}</a></div>`}).join('');
    const z=$('#zip');if(d.zipUrl){z.href=d.zipUrl;z.hidden=false}else z.hidden=true;pb.toast(pb.t('done'))}
  catch(err){pb.hide('prog');pb.toast(pb.t('error')+': '+err.message,true)}finally{pb.busy(go,false)}};
"""


def start_web_studio(port: int) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            u = urllib.parse.urlparse(self.path)
            render_studio(self, port)

        def do_POST(self) -> None:
            if self.path == "/api/convert":
                self.handle_api_convert()
            else:
                self.send_error(404)

        def handle_api_convert(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self.send_error(400, "Expected multipart/form-data")
                return

            content_len = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(min(content_len, 50 * 1024 * 1024))
            boundary = content_type.split("boundary=")[1].split(";")[0].strip().encode()
            parts = raw_body.split(b"--" + boundary)

            target_fmt = "png"
            uploaded_files: list[tuple[str, bytes]] = []

            for part in parts:
                if b'name="fmt"' in part:
                    lines = part.split(b"\r\n\r\n", 1)
                    if len(lines) == 2:
                        target_fmt = lines[1].split(b"\r\n")[0].decode("utf-8").strip()
                elif b'name="files"' in part and b'filename="' in part:
                    header, data = part.split(b"\r\n\r\n", 1)
                    file_bytes = data.rsplit(b"\r\n", 1)[0]
                    m = re.search(rb'filename="([^"]+)"', header)
                    fname = m.group(1).decode("utf-8", errors="replace") if m else "sticker"
                    uploaded_files.append((fname, file_bytes))

            out_dir = get_data_dir() / "web_converted"
            out_dir.mkdir(parents=True, exist_ok=True)
            _edge = time.time() - 24 * 3600
            for _old in out_dir.glob("*"):
                if _old.is_file() and _old.stat().st_mtime < _edge:
                    _old.unlink(missing_ok=True)
            res_files = []
            converted_paths = []

            for idx, (orig_name, b) in enumerate(uploaded_files, 1):
                kind = "webp"
                if orig_name.lower().endswith(".webm"):
                    kind = "webm"
                elif orig_name.lower().endswith(".tgs"):
                    kind = "tgs"
                stem = f"sticker_{int(time.time())}_{idx}"
                out_p = convert_single_bytes(b, kind, target_fmt, stem, out_dir)
                converted_paths.append(out_p)
                res_files.append({"name": out_p.name, "url": f"/files/{out_p.name}"})

            zip_url = ""
            if len(converted_paths) > 1:
                zip_name = f"stickers_{target_fmt}_{int(time.time())}.zip"
                zip_path = out_dir / zip_name
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for cp in converted_paths:
                        zf.write(cp, arcname=cp.name)
                zip_url = f"/files/{zip_name}"

            resp_payload = json.dumps({"files": res_files, "zipUrl": zip_url}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_payload)))
            self.end_headers()
            self.wfile.write(resp_payload)

    orig_get = Handler.do_GET

    def wrapped_get(self: Handler) -> None:
        if self.path.startswith("/files/"):
            fname = os.path.basename(urllib.parse.urlparse(self.path).path)
            fpath = get_data_dir() / "web_converted" / fname
            if fpath.is_file():
                self.send_response(200)
                if fname.endswith(".png"):
                    self.send_header("Content-Type", "image/png")
                elif fname.endswith(".gif"):
                    self.send_header("Content-Type", "image/gif")
                elif fname.endswith(".mp4"):
                    self.send_header("Content-Type", "video/mp4")
                elif fname.endswith(".zip"):
                    self.send_header("Content-Type", "application/zip")
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


def run_bot(token: str) -> None:
    import telebot
    from telebot import types

    init_db()
    bot = telebot.TeleBot(token, parse_mode="HTML")

    web_dir = get_data_dir() / "web_converted"
    web_dir.mkdir(parents=True, exist_ok=True)

    def purge_old(dir_path: Path, max_age_h: int = 24) -> None:
        try:
            edge = time.time() - max_age_h * 3600
            for p in dir_path.glob("*"):
                if p.is_file() and p.stat().st_mtime < edge:
                    try: p.unlink(missing_ok=True)
                    except Exception: pass
        except Exception: pass

    purge_old(web_dir, max_age_h=24)

    def _cleanup_loop():
        while True:
            time.sleep(3600)
            purge_old(web_dir, max_age_h=24)
    threading.Thread(target=_cleanup_loop, daemon=True).start()

    def build_main_reply_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(core.btn("btn_lang", uid)),
            types.KeyboardButton(core.btn("btn_help", uid)),
        )
        return kb

    def build_single_sticker_kb(kind: str, has_pack: bool, uid: int | None = None) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        if kind == "webp":
            kb.row(types.KeyboardButton(core.btn("kb_to_png", uid)), types.KeyboardButton(core.btn("kb_to_webp", uid)))
        elif kind == "webm":
            kb.row(types.KeyboardButton(core.btn("kb_to_gif", uid)), types.KeyboardButton(core.btn("kb_to_mp4", uid)))
            kb.row(types.KeyboardButton(core.btn("kb_first_frame", uid)))
        else:
            kb.row(types.KeyboardButton(core.btn("kb_lottie", uid)), types.KeyboardButton(core.btn("kb_tgs", uid)))

        if has_pack:
            kb.row(types.KeyboardButton(core.btn("kb_pack_png", uid)))
            kb.row(types.KeyboardButton(core.btn("kb_pack_gif", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_menu", uid)))
        return kb

    def build_pack_kb(uid: int | None = None) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(types.KeyboardButton(core.btn("kb_zip_png", uid)), types.KeyboardButton(core.btn("kb_zip_gif", uid)))
        kb.row(types.KeyboardButton(core.btn("kb_zip_webp", uid)), types.KeyboardButton(core.btn("kb_zip_mp4", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_menu", uid)))
        return kb

    @bot.message_handler(commands=["start"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_welcome", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(commands=["help"])
    def on_help(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_help_text", user_id=uid), reply_markup=build_main_reply_kb(uid))

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
            bot.reply_to(msg, t("tg_lang_changed", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_menu", "btn_cancel"))
    def on_back(msg: Any) -> None:
        uid = msg.from_user.id
        clear_user_pending_job(uid)
        bot.reply_to(msg, "Главное меню:", reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_lang"))
    def on_lang_btn(msg: Any) -> None:
        on_lang_cmd(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_help"))
    def on_help_btn(msg: Any) -> None:
        on_help(msg)

    # Sticker message handler
    @bot.message_handler(content_types=["sticker"])
    def on_sticker(msg: Any) -> None:
        uid = msg.from_user.id
        st = msg.sticker
        kind = detect_sticker_kind(st)
        set_user_pending_job(uid, "single", file_id=st.file_id, kind=kind, set_name=st.set_name or "")
        bot.reply_to(
            msg,
            f"🎨 <b>Стикер получен ({kind.upper()})!</b>\n\nВыберите формат конвертации на клавиатуре внизу:",
            reply_markup=build_single_sticker_kb(kind, bool(st.set_name), uid),
        )

    # Pack link handler
    @bot.message_handler(func=lambda m: bool(m.text and PACK_RE.search(m.text)))
    def on_pack_link(msg: Any) -> None:
        uid = msg.from_user.id
        match = PACK_RE.search(msg.text or "")
        if not match:
            return
        pack_name = match.group(1)
        set_user_pending_job(uid, "pack", set_name=pack_name)
        bot.reply_to(
            msg,
            f"📦 <b>Стикерпак:</b> <code>{pack_name}</code>\n\nВыберите формат для архива на клавиатуре внизу:",
            reply_markup=build_pack_kb(uid),
        )

    # Format action buttons from bottom keyboard
    @bot.message_handler(func=lambda m: any(kw in (m.text or "") for kw in (
        "PNG", "WebP", "GIF", "MP4", "JSON", "TGS"
    )))
    def on_format_action(msg: Any) -> None:
        uid = msg.from_user.id
        txt = msg.text or ""
        job = get_user_pending_job(uid)
        if not job:
            bot.reply_to(msg, "Сначала отправьте стикер или ссылку на набор стикеров!", reply_markup=build_main_reply_kb(uid))
            return

        fmt = "png"
        if "GIF" in txt:
            fmt = "gif"
        elif "MP4" in txt:
            fmt = "mp4"
        elif "WebP" in txt:
            fmt = "webp"
        elif "JSON" in txt or "Lottie" in txt:
            fmt = "json"
        elif "TGS" in txt:
            fmt = "tgs"

        is_pack_action = core.is_btn(txt, "kb_pack_png", "kb_pack_gif") or job.get("job_type") == "pack"

        if is_pack_action:
            set_name = job.get("set_name")
            if not set_name:
                bot.reply_to(msg, t("err_no_pack", user_id=uid), reply_markup=build_main_reply_kb(uid))
                return

            status = bot.reply_to(
                msg,
                t("tg_pack_fetching", user_id=uid, name=set_name),
                reply_markup=build_main_reply_kb(uid),
            )

            def run_pack():
                try:
                    st_set = bot.get_sticker_set(set_name)
                    stickers = st_set.stickers
                    total = len(stickers)
                    log("log_pack_start", name=set_name, count=total, fmt=fmt.upper())
                    with tempfile.TemporaryDirectory() as tmp:
                        tmp_dir = Path(tmp)
                        out_files = []
                        for idx, st in enumerate(stickers, 1):
                            kind = detect_sticker_kind(st)
                            raw = core.download_tg_file(bot, st.file_id)
                            stem = f"{idx:03d}_{set_name}"
                            out_f = convert_single_bytes(raw, kind, fmt, stem, tmp_dir)
                            out_files.append(out_f)
                            if idx % 5 == 0 or idx == total:
                                try:
                                    bot.edit_message_text(
                                        t("tg_pack_progress", user_id=uid, done=idx, total=total, fmt=fmt.upper()),
                                        msg.chat.id,
                                        status.message_id,
                                    )
                                except Exception:
                                    pass

                        zip_path = tmp_dir / f"{set_name}_{fmt}.zip"
                        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                            for f in out_files:
                                zf.write(f, arcname=f.name)

                        with zip_path.open("rb") as zfh:
                            bot.send_document(
                                msg.chat.id,
                                zfh,
                                caption=t("tg_pack_done", user_id=uid, name=set_name, count=total, fmt=fmt.upper()),
                            )
                    try:
                        bot.delete_message(msg.chat.id, status.message_id)
                    except Exception:
                        pass
                except Exception as exc:
                    log("log_error", err=str(exc))
                    bot.reply_to(msg, t("err_failed", user_id=uid, err=str(exc)[:200]))

            threading.Thread(target=run_pack, daemon=True).start()

        else:
            file_id = job.get("file_id")
            kind = job.get("kind", "webp")
            status = bot.reply_to(msg, t("tg_working", user_id=uid), reply_markup=build_main_reply_kb(uid))

            def run_single():
                try:
                    try:
                        raw = core.download_tg_file(bot, file_id)
                    except core.FileTooBig:
                        bot.reply_to(msg, "⚠️ Файл слишком большой (> 20 МБ). Telegram Bot API не позволяет скачивать файлы более 20 МБ.")
                        return
                    with tempfile.TemporaryDirectory() as tmp:
                        out_file = convert_single_bytes(raw, kind, fmt, "sticker", Path(tmp))
                        with out_file.open("rb") as fh:
                            if fmt == "gif":
                                bot.send_animation(msg.chat.id, fh)
                            elif fmt == "mp4":
                                bot.send_video(msg.chat.id, fh)
                            else:
                                bot.send_document(msg.chat.id, fh)
                    try:
                        bot.delete_message(msg.chat.id, status.message_id)
                    except Exception:
                        pass
                except Exception as exc:
                    log("log_error", err=str(exc))
                    bot.reply_to(msg, t("err_failed", user_id=uid, err=str(exc)[:200]))

            threading.Thread(target=run_single, daemon=True).start()

    log("log_started")
    core.start_polling(bot, timeout=30, long_polling_timeout=25)


def main() -> int:
    init_db()
    port_raw = os.environ.get("WEB_PORT", "8091").strip()
    if port_raw.isdigit() and int(port_raw) > 0:
        start_web_studio(int(port_raw))

    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        run_bot(token)
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
