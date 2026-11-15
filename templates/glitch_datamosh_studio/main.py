"""Glitch & Datamosh Studio — Procedural Datamoshing, RGB Split, VHS tape & Glitch Art.
Features:
- Real MPEG-4 byte-level I-Frame removal / P-frame pixel melting (Datamosh)
- 3-channel optical Chromatic Aberration (RGB Split)
- Analog VHS 90s cassette scanlines, tracking jitter & chroma noise
- Digital compression macroblocking & corrupt slice displacement
- Looping animated glitch GIF/MP4 from static photos
- Audio Bitcrusher & analog tape decay filter
- 100% ReplyKeyboardMarkup in Telegram (zero inline callback timeouts)
- 24 languages support
- Standalone Cyberpunk Web Studio on port 8094
"""

from __future__ import annotations

import html
import http.server
import json
import math
import os
import random
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


def get_data_dir() -> Path:
    d = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_cache_dir() -> Path:
    d = get_data_dir() / "glitch_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return get_data_dir() / "glitch_jobs.db"


def init_db() -> None:
    with sqlite3.connect(db_path()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                intensity INTEGER DEFAULT 3,
                format TEXT DEFAULT 'mp4',
                audio_glitch INTEGER DEFAULT 1,
                default_mode TEXT DEFAULT 'datamosh',
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_media (
                user_id INTEGER PRIMARY KEY,
                file_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                duration REAL NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                has_audio INTEGER DEFAULT 1,
                updated_at REAL NOT NULL
            )
            """
        )


def get_user_settings(user_id: int) -> dict[str, Any]:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)
    except Exception:
        pass
    return {
        "user_id": user_id,
        "intensity": 3,
        "format": "mp4",
        "audio_glitch": 1,
        "default_mode": "datamosh",
        "updated_at": time.time(),
    }


def update_user_settings(user_id: int, **kwargs: Any) -> dict[str, Any]:
    curr = get_user_settings(user_id)
    curr.update(kwargs)
    curr["updated_at"] = time.time()
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_settings (user_id, intensity, format, audio_glitch, default_mode, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    max(1, min(5, int(curr.get("intensity", 3)))),
                    str(curr.get("format", "mp4")),
                    int(curr.get("audio_glitch", 1)),
                    str(curr.get("default_mode", "datamosh")),
                    float(curr["updated_at"]),
                ),
            )
    except Exception:
        pass
    return curr


def save_pending_media(
    user_id: int,
    file_id: str,
    source_path: str,
    media_type: str,
    duration: float,
    width: int,
    height: int,
    has_audio: bool = True,
) -> None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pending_media (user_id, file_id, source_path, media_type, duration, width, height, has_audio, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, file_id, source_path, media_type, float(duration), int(width), int(height), 1 if has_audio else 0, time.time()),
            )
    except Exception:
        pass


def get_pending_media(user_id: int) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM pending_media WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)
    except Exception:
        pass
    return None


def clear_pending_media(user_id: int) -> None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.execute("DELETE FROM pending_media WHERE user_id = ?", (user_id,))
    except Exception:
        pass


def ffmpeg_path() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    prefix = os.environ.get("PREFIX", "")
    if prefix:
        cand = os.path.join(prefix, "bin", "ffmpeg")
        if os.path.isfile(cand):
            return cand
    return None


def probe_media(path: Path) -> dict[str, Any]:
    ff = ffmpeg_path()
    if not ff or not os.path.isfile(ff):
        return {"media_type": "video", "duration": 0.0, "width": 640, "height": 640, "has_audio": False}

    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        try:
            from PIL import Image
            with Image.open(path) as im:
                w, h = im.size
                return {"media_type": "photo", "duration": 0.0, "width": w, "height": h, "has_audio": False}
        except Exception:
            return {"media_type": "photo", "duration": 0.0, "width": 800, "height": 800, "has_audio": False}

    try:
        res = subprocess.run([ff, "-i", str(path)], capture_output=True, text=True, check=False, timeout=10)
        stderr = res.stderr or ""
        duration = 0.0
        width = 640
        height = 640
        has_audio = "Audio:" in stderr
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):([\d\.]+)", stderr)
        if dur_match:
            hours = float(dur_match.group(1))
            minutes = float(dur_match.group(2))
            secs = float(dur_match.group(3))
            duration = hours * 3600 + minutes * 60 + secs
        dim_match = re.search(r"Stream.*Video:.*,\s*(\d{2,5})x(\d{2,5})", stderr)
        if dim_match:
            width = int(dim_match.group(1))
            height = int(dim_match.group(2))
        return {
            "media_type": "video",
            "duration": duration,
            "width": width,
            "height": height,
            "has_audio": has_audio,
        }
    except Exception:
        pass

    return {"media_type": "video", "duration": 0.0, "width": 640, "height": 640, "has_audio": True}


# ---------------------------------------------------------------------------
# Core Datamoshing & Glitch Art Engine
# ---------------------------------------------------------------------------

def mpeg4_datamosh_bytes(avi_bytes: bytes, drop_ratio: float = 0.75) -> bytes:
    """True binary MPEG-4 I-Frame removal.
    Locates 0x000001B6 start codes in MPEG-4 bitstream and replaces I-frame headers (00)
    with P-frame headers (01) or drops them, producing real motion smear melting!
    """
    pattern = b"\x00\x00\x01\xb6"
    chunks = avi_bytes.split(pattern)
    if len(chunks) <= 2:
        return avi_bytes

    out_chunks = [chunks[0]]
    # Keep first frame as I-frame so video initializes
    out_chunks.append(chunks[1])

    for i in range(2, len(chunks)):
        chunk = chunks[i]
        if not chunk:
            out_chunks.append(b"")
            continue
        first_byte = chunk[0]
        # Frame type is determined by the two highest bits of the byte following 0x000001B6:
        # 00 = I-frame, 01 = P-frame, 10 = B-frame
        vop_type = (first_byte >> 6) & 0x03
        if vop_type == 0:  # I-frame
            if random.random() < drop_ratio:
                # Morph I-frame into P-frame: clear bit 7, set bit 6
                modified_first_byte = (first_byte & 0x3F) | 0x40
                out_chunks.append(bytes([modified_first_byte]) + chunk[1:])
            else:
                out_chunks.append(chunk)
        else:
            out_chunks.append(chunk)

    return pattern.join(out_chunks)

FFMPEG_SLOTS = threading.BoundedSemaphore(1)

def apply_glitch(
    src_path: Path,
    out_path: Path,
    mode: str = "datamosh",
    intensity: int = 3,
    export_gif: bool = False,
    audio_glitch: bool = True,
) -> bool:
    """Applies chosen glitch algorithm to input video or photo."""
    ff = ffmpeg_path()
    if not ff or not os.path.isfile(ff):
        log("log_error", err="FFmpeg binary not found.")
        return False

    info = probe_media(src_path)
    is_photo = info.get("media_type") == "photo"
    has_audio = info.get("has_audio", False)
    intensity = max(1, min(5, intensity))
    cache_dir = get_cache_dir()

    # If photo, convert into 3-second animated video clip first
    working_src = src_path
    if is_photo:
        tmp_clip = cache_dir / f"photo_clip_{int(time.time()*1000)}.mp4"
        cmd_photo = [
            ff, "-y",
            "-loop", "1", "-i", str(src_path),
            "-t", "3.0",
            "-vf", "scale='min(720,iw)':-2:flags=lanczos,fps=24,format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast",
            str(tmp_clip),
        ]
        res = subprocess.run(cmd_photo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if res.returncode == 0 and tmp_clip.is_file():
            working_src = tmp_clip

    # 1. Mode: True MPEG-4 Datamoshing (Melting)
    if mode == "datamosh" and not is_photo:
        token = hex(int(time.time() * 1000))[2:]
        avi_stage = cache_dir / f"stage_{token}.avi"
        avi_moshed = cache_dir / f"moshed_{token}.avi"

        # Transcode to MPEG-4 AVI with controlled GOP structure
        cmd_avi = [
            ff, "-y",
            "-i", str(working_src),
            "-c:v", "mpeg4", "-q:v", "2",
            "-g", "90", "-bf", "0",
            "-an",
            str(avi_stage),
        ]
        subprocess.run(cmd_avi, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        if avi_stage.is_file() and avi_stage.stat().st_size > 1024:
            raw_bytes = avi_stage.read_bytes()
            drop_ratio = 0.4 + (intensity * 0.12)  # 0.52 to 1.0
            moshed_bytes = mpeg4_datamosh_bytes(raw_bytes, drop_ratio=drop_ratio)
            avi_moshed.write_bytes(moshed_bytes)

            # Transcode back to target format
            if export_gif:
                cmd_out = [
                    ff, "-y",
                    "-i", str(avi_moshed),
                    "-vf", "fps=15,scale='min(480,iw)':-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                    "-loop", "0",
                    str(out_path),
                ]
            else:
                cmd_out = [
                    ff, "-y",
                    "-i", str(avi_moshed),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-preset", "veryfast", "-crf", "22",
                    "-movflags", "+faststart",
                    str(out_path),
                ]

            res_final = subprocess.run(cmd_out, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            try:
                avi_stage.unlink(missing_ok=True)
                avi_moshed.unlink(missing_ok=True)
            except Exception:
                pass

            if res_final.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
                return True

    # 2. Procedural Filter Graph Glitch Modes (RGB Split, VHS, Macroblocks, or Photo Datamosh)
    vf_list = []

    if mode == "rgb":
        # Chromatic Aberration with channel horizontal and vertical offset
        shift = intensity * 4
        vf_list.append(
            f"split=3[r][g][b];"
            f"[r]lutrgb=g=0:b=0[r1];"
            f"[g]lutrgb=r=0:b=0[g1];"
            f"[b]lutrgb=r=0:g=0[b1];"
            f"[r1]pad=iw+{shift*2}:ih+{shift}:0:0:color=black[r2];"
            f"[g1]pad=iw+{shift*2}:ih+{shift}:{shift}:0:color=black[g2];"
            f"[b1]pad=iw+{shift*2}:ih+{shift}:{shift*2}:{shift}:color=black[b2];"
            f"[r2][g2]blend=all_mode=addition[rg];"
            f"[rg][b2]blend=all_mode=addition,"
            f"crop=iw-{shift*2}:ih-{shift}:{shift}:0"
        )
    elif mode == "vhs":
        # Analog VHS tape tracking, interlacing, chroma blur, and analog noise
        noise_level = intensity * 8
        vf_list.append(
            f"noise=alls={noise_level}:allf=t+u,"
            f"eq=saturation=1.3:contrast=1.15,"
            f"tinterlace=mode=interleave_top,"
            f"drawgrid=width=10000:height=4:thickness=1:color=black@0.25"
        )
    elif mode == "blocks":
        # Extreme digital compression and pixel macroblock displacement
        factor = max(2, intensity * 2)
        vf_list.append(
            f"scale='trunc(iw/{factor}/2)*2':'trunc(ih/{factor}/2)*2':flags=neighbor,"
            f"scale='trunc(iw/2)*2':'trunc(ih/2)*2':flags=neighbor,"
            f"noise=c0s={intensity*10}:c0f=u"
        )
    else:
        # Fallback datamosh procedural motion blend
        vf_list.append(f"tblend=all_mode=difference128,eq=contrast={1.0 + intensity*0.15}:saturation={1.0 + intensity*0.2}")

    vf_str = ";".join(vf_list) if mode == "rgb" else ",".join(vf_list)

    # Audio Glitch / Bitcrusher filter
    af_str = ""
    if has_audio and not is_photo:
        if audio_glitch:
            rate = 24000 - (intensity * 2500)
            af_str = f"asetrate={rate},aresample=24000,lowpass=f=3200,volume=1.2"
        else:
            af_str = "anull"

    cmd = [ff, "-y", "-i", str(working_src)]
    
    if mode == "rgb":
        cmd += ["-filter_complex", vf_str]
    else:
        cmd += ["-vf", vf_str]

    if export_gif:
        cmd += ["-c:v", "gif", str(out_path)]
    else:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "22", "-movflags", "+faststart"]
        if has_audio and af_str:
            cmd += ["-af", af_str, "-c:a", "aac", "-b:a", "64k"]
        else:
            cmd += ["-an"]
        cmd += [str(out_path)]

    log("log_processing", filename=src_path.name, mode=mode, intensity=intensity)
    try:
        with FFMPEG_SLOTS:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=120)
        if res.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
            size_kb = out_path.stat().st_size / 1024.0
            log("log_done", out_path=out_path.name, size_kb=size_kb)
            return True
        else:
            err_msg = res.stderr.decode("utf-8", errors="replace")[-400:] if res.stderr else "Unknown error"
            log("log_error", err=f"FFmpeg error: {err_msg}")
    except Exception as exc:
        log("log_error", err=f"Glitch execution failed: {exc}")

    return False


# ---------------------------------------------------------------------------
# Offline Web Studio (Port 8094)
# ---------------------------------------------------------------------------

def start_web_studio(port: int = 8094) -> None:
    cache_dir = get_cache_dir()

    class StudioHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            u = urllib.parse.urlparse(self.path)
            path = u.path

            if path == "/api/status":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                status = {
                    "status": "online",
                    "bot": "glitch_datamosh_studio",
                    "port": port,
                    "ffmpeg": bool(ffmpeg_path()),
                    "uptime": time.time(),
                }
                self.wfile.write(json.dumps(status).encode("utf-8"))
                return

            if path.startswith("/download/"):
                filename = os.path.basename(path)
                fpath = cache_dir / filename
                if fpath.is_file():
                    self.send_response(200)
                    ctype = "image/gif" if filename.endswith(".gif") else "video/mp4"
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(fpath.stat().st_size))
                    self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                    self.end_headers()
                    with fpath.open("rb") as fh:
                        shutil.copyfileobj(fh, self.wfile)
                    return
                self.send_error(404)
                return

            lang = urllib.parse.parse_qs(u.query).get("lang", [current_lang()])[0]
            rtl_attr = ' dir="rtl"' if is_rtl(lang) else ""

            lang_options = "\n".join(
                f'<option value="{code}"{" selected" if code == lang else ""}>{html.escape(label)}</option>'
                for code, label in SUPPORTED_LANGUAGES
            )

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
  --accent-magenta: #FF0055;
  --accent-emerald: #00E676;
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
.brand {{ font-size: 20px; font-weight: 800; color: var(--accent-magenta); text-shadow: 2px 0 var(--accent-cyan); }}
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
  box-shadow: 0 4px 20px rgba(255,0,85,0.15);
}}
.drop-zone {{
  border: 2px dashed var(--accent-magenta);
  border-radius: 14px;
  padding: 30px 16px;
  text-align: center;
  background: var(--bg-input);
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 18px;
}}
.drop-zone:hover {{
  border-color: var(--accent-cyan);
  background: rgba(0, 216, 255, 0.05);
}}
.preview-box {{
  width: 100%;
  max-height: 320px;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 18px;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}}
.preview-box video, .preview-box img {{
  max-width: 100%;
  max-height: 320px;
}}
.control-group {{
  margin-bottom: 14px;
}}
.control-group label {{
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-dim);
  margin-bottom: 6px;
}}
.range-slider {{
  width: 100%;
  accent-color: var(--accent-magenta);
}}
.options-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 18px;
}}
.mode-btn {{
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text-main);
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  font-weight: bold;
  text-align: center;
  transition: all 0.2s;
}}
.mode-btn.active {{
  border-color: var(--accent-magenta);
  background: rgba(255,0,85,0.15);
  color: var(--accent-cyan);
}}
.btn-action {{
  width: 100%;
  background: linear-gradient(135deg, var(--accent-magenta), #9900FF);
  color: #FFF;
  font-weight: 800;
  padding: 14px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  cursor: pointer;
  transition: transform 0.1s;
}}
.btn-action:hover {{ opacity: 0.95; transform: translateY(-1px); }}
.btn-action:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.result-box {{
  display: none;
  margin-top: 20px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(0, 230, 118, 0.1);
  border: 1px solid var(--accent-emerald);
  text-align: center;
}}
.btn-download {{
  display: inline-block;
  margin-top: 10px;
  background: var(--accent-emerald);
  color: #003314;
  font-weight: bold;
  padding: 10px 20px;
  border-radius: 8px;
  text-decoration: none;
}}
.spinner {{
  display: none;
  margin: 15px auto;
  width: 36px;
  height: 36px;
  border: 4px solid var(--border);
  border-top-color: var(--accent-magenta);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<header>
  <div class="brand">⚡ Glitch & Datamosh Studio</div>
  <select class="lang-sel" onchange="location.href='?lang='+this.value">
    {lang_options}
  </select>
</header>

<div class="card">
  <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
    <div style="font-size: 32px; margin-bottom: 8px;">🎞</div>
    <div style="font-weight: 600;">{html.escape(t('web_drop_prompt', lang_override=lang))}</div>
    <div style="font-size: 12px; color: var(--text-dim); margin-top: 4px;">MP4, MOV, MKV, WebM, JPG, PNG (≤ 200 MB)</div>
    <input type="file" id="fileInput" accept="video/*,image/*" style="display:none" onchange="handleFileSelect(this.files[0])">
  </div>

  <div class="preview-box" id="previewBox" style="display:none;">
    <video id="previewVideo" autoplay loop muted playsinline style="display:none;"></video>
    <img id="previewImage" style="display:none;">
  </div>

  <div class="control-group">
    <label>{html.escape(t('web_intensity_label', lang_override=lang))}: <span id="intVal">3 / 5</span></label>
    <input type="range" class="range-slider" id="intensity" min="1" max="5" value="3" oninput="document.getElementById('intVal').innerText = this.value + ' / 5'">
  </div>

  <div class="options-grid">
    <div class="mode-btn active" id="btnModeDatamosh" onclick="selectMode('datamosh')">🌊 Datamosh</div>
    <div class="mode-btn" id="btnModeRgb" onclick="selectMode('rgb')">⚡ RGB Split</div>
    <div class="mode-btn" id="btnModeVhs" onclick="selectMode('vhs')">📺 VHS Tape</div>
    <div class="mode-btn" id="btnModeBlocks" onclick="selectMode('blocks')">🔲 Macroblocks</div>
  </div>

  <div style="display:flex; gap:10px; margin-bottom:18px;">
    <label style="flex:1; background:var(--bg-input); padding:10px; border-radius:8px; border:1px solid var(--border); font-size:13px; display:flex; align-items:center; gap:8px;">
      <input type="checkbox" id="chkAudio" checked>
      <span>🎵 Audio Bitcrush</span>
    </label>
    <label style="flex:1; background:var(--bg-input); padding:10px; border-radius:8px; border:1px solid var(--border); font-size:13px; display:flex; align-items:center; gap:8px;">
      <input type="checkbox" id="chkGif">
      <span>🎞 Export as GIF</span>
    </label>
  </div>

  <button class="btn-action" id="btnSubmit" onclick="startRender()" disabled>
    {html.escape(t('web_btn_render', lang_override=lang))}
  </button>

  <div class="spinner" id="spinner"></div>

  <div class="result-box" id="resultBox">
    <div style="font-weight: bold; color: var(--accent-emerald);">✅ Glitch render complete!</div>
    <a href="#" class="btn-download" id="downloadLink">{html.escape(t('web_download', lang_override=lang))}</a>
  </div>
</div>

<script>
let selectedFile = null;
let currentMode = 'datamosh';

function selectMode(m) {{
  currentMode = m;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  if (m === 'datamosh') document.getElementById('btnModeDatamosh').classList.add('active');
  if (m === 'rgb') document.getElementById('btnModeRgb').classList.add('active');
  if (m === 'vhs') document.getElementById('btnModeVhs').classList.add('active');
  if (m === 'blocks') document.getElementById('btnModeBlocks').classList.add('active');
}}

function handleFileSelect(file) {{
  if (!file) return;
  selectedFile = file;
  const pBox = document.getElementById('previewBox');
  const vid = document.getElementById('previewVideo');
  const img = document.getElementById('previewImage');
  pBox.style.display = 'flex';

  if (file.type.startsWith('video/')) {{
    vid.style.display = 'block';
    img.style.display = 'none';
    vid.src = URL.createObjectURL(file);
  }} else {{
    vid.style.display = 'none';
    img.style.display = 'block';
    img.src = URL.createObjectURL(file);
  }}
  document.getElementById('btnSubmit').disabled = false;
}}

const dz = document.getElementById('dropZone');
dz.addEventListener('dragover', (e) => {{ e.preventDefault(); dz.style.borderColor = 'var(--accent-cyan)'; }});
dz.addEventListener('dragleave', (e) => {{ e.preventDefault(); dz.style.borderColor = 'var(--accent-magenta)'; }});
dz.addEventListener('drop', (e) => {{
  e.preventDefault();
  dz.style.borderColor = 'var(--accent-magenta)';
  if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files[0]);
}});

async function startRender() {{
  if (!selectedFile) return;
  const btn = document.getElementById('btnSubmit');
  const sp = document.getElementById('spinner');
  const resBox = document.getElementById('resultBox');
  btn.disabled = true;
  sp.style.display = 'block';
  resBox.style.display = 'none';

  const fd = new FormData();
  fd.append('media', selectedFile);
  fd.append('mode', currentMode);
  fd.append('intensity', document.getElementById('intensity').value);
  fd.append('audio_glitch', document.getElementById('chkAudio').checked ? '1' : '0');
  fd.append('gif', document.getElementById('chkGif').checked ? '1' : '0');

  try {{
    const resp = await fetch('/api/render', {{ method: 'POST', body: fd }});
    const data = await resp.json();
    sp.style.display = 'none';
    btn.disabled = false;
    if (data.ok) {{
      resBox.style.display = 'block';
      const dl = document.getElementById('downloadLink');
      dl.href = data.download_url;
      dl.innerText = '⬇️ Download ' + data.filename + ' (' + data.size_kb + ' KB)';
    }} else {{
      alert('Error: ' + (data.error || 'Glitch render failed'));
    }}
  }} catch (err) {{
    sp.style.display = 'none';
    btn.disabled = false;
    alert('Server error: ' + err);
  }}
}}
</script>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_page.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(html_page.encode("utf-8"))

        def do_POST(self) -> None:
            if self.path == "/api/render":
                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    self.send_error(400, "Expected multipart/form-data")
                    return

                try:
                    content_len = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(min(content_len, 200 * 1024 * 1024))
                    boundary = ctype.split("boundary=")[1].split(";")[0].strip().encode()
                    parts = raw_body.split(b"--" + boundary)

                    mode = "datamosh"
                    intensity = 3
                    audio_glitch = True
                    export_gif = False
                    file_bytes = b""
                    fname = "input.mp4"

                    for part in parts:
                        if b'name="mode"' in part:
                            mode = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip()
                        elif b'name="intensity"' in part:
                            val = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip()
                            intensity = int(val) if val.isdigit() else 3
                        elif b'name="audio_glitch"' in part:
                            audio_glitch = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip() == "1"
                        elif b'name="gif"' in part:
                            export_gif = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip() == "1"
                        elif b'name="media"' in part and b'filename="' in part:
                            header, data = part.split(b"\r\n\r\n", 1)
                            file_bytes = data.rsplit(b"\r\n", 1)[0]
                            m = re.search(rb'filename="([^"]+)"', header)
                            if m:
                                fname = m.group(1).decode("utf-8", errors="replace")

                    if not file_bytes:
                        self.send_error(400, "No media file uploaded")
                        return

                    ext = os.path.splitext(fname)[1].lower() or ".mp4"
                    token_rand = hex(int(time.time() * 1000))[2:]
                    src_tmp = cache_dir / f"upload_{token_rand}{ext}"
                    out_ext = ".gif" if export_gif else ".mp4"
                    out_tmp = cache_dir / f"glitch_{token_rand}{out_ext}"

                    src_tmp.write_bytes(file_bytes)

                    ok = apply_glitch(
                        src_path=src_tmp,
                        out_path=out_tmp,
                        mode=mode,
                        intensity=intensity,
                        export_gif=export_gif,
                        audio_glitch=audio_glitch,
                    )

                    try:
                        src_tmp.unlink(missing_ok=True)
                    except Exception:
                        pass

                    if ok and out_tmp.is_file():
                        resp_data = {
                            "ok": True,
                            "filename": out_tmp.name,
                            "download_url": f"/download/{out_tmp.name}",
                            "size_kb": round(out_tmp.stat().st_size / 1024.0, 1),
                        }
                    else:
                        resp_data = {"ok": False, "error": "Glitch rendering failed"}

                    body = json.dumps(resp_data).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                except Exception as exc:
                    err_body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err_body)))
                    self.end_headers()
                    self.wfile.write(err_body)
                    return

            self.send_error(404)

    class Reusable(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    def serve() -> None:
        try:
            with Reusable((os.environ.get("BIND_HOST", "127.0.0.1"), port), StudioHandler) as srv:
                print(f"[PYBIONIC_WEB:{port}]", flush=True)
                log("log_web_started", port=port)
                srv.serve_forever()
        except Exception as exc:
            log("log_error", err=f"Web server failed on port {port}: {exc}")

    threading.Thread(target=serve, daemon=True).start()


# ---------------------------------------------------------------------------
# Telegram Bot Runner (100% ReplyKeyboardMarkup)
# ---------------------------------------------------------------------------

def run_bot(token: str) -> None:
    import telebot
    from telebot import types

    init_db()
    bot = telebot.TeleBot(token, parse_mode="HTML")
    cache_dir = get_cache_dir()

    ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()}

    def is_allowed(user_id: int) -> bool:
        return not ALLOWED or user_id in ALLOWED

    @bot.message_handler(func=lambda m: not is_allowed(m.from_user.id))
    def access_denied(m):
        bot.reply_to(m, f"⛔ Доступ ограничен владельцем бота (ваш ID: {m.from_user.id}).")

    def build_main_reply_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(t("btn_send_media", user_id=uid)),
            types.KeyboardButton(t("btn_help", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_settings", user_id=uid)),
            types.KeyboardButton(t("btn_choose_lang", user_id=uid)),
        )
        return kb

    def build_glitch_actions_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(t("btn_mode_datamosh", user_id=uid)),
            types.KeyboardButton(t("btn_mode_rgb", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_mode_vhs", user_id=uid)),
            types.KeyboardButton(t("btn_mode_blocks", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_export_mp4", user_id=uid)),
            types.KeyboardButton(t("btn_export_gif", user_id=uid)),
        )
        kb.row(types.KeyboardButton(t("btn_back_main", user_id=uid)))
        return kb

    def build_settings_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        st = get_user_settings(uid)
        kb.row(
            types.KeyboardButton(t("btn_intensity_up", user_id=uid)),
            types.KeyboardButton(t("btn_intensity_down", user_id=uid)),
        )
        fmt_label = "🎞 Формат: GIF ✓" if st["format"] == "gif" else "🎥 Формат: MP4 ✓"
        audio_label = "🎵 Звук: Глитч ✓" if st["audio_glitch"] else "🎵 Звук: Исходный"
        kb.row(types.KeyboardButton(fmt_label), types.KeyboardButton(audio_label))
        kb.row(types.KeyboardButton(t("btn_back_main", user_id=uid)))
        return kb

    @bot.message_handler(commands=["start"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_welcome", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(commands=["help"])
    def on_help(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_help_text", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(commands=["settings"])
    def on_settings_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        st = get_user_settings(uid)
        fmt_str = "GIF" if st["format"] == "gif" else "MP4"
        aud_str = "Биткрашер ВКЛ" if st["audio_glitch"] else "ВЫКЛ"
        bot.reply_to(
            msg,
            t("msg_settings_info", user_id=uid, intensity=st["intensity"], format=fmt_str, audio_glitch=aud_str),
            reply_markup=build_settings_kb(uid),
        )

    @bot.message_handler(commands=["lang", "language"])
    def on_lang_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            t("tg_lang_title", user_id=uid),
            reply_markup=build_reply_language_keyboard(user_id=uid, back_text=t("btn_back_main", user_id=uid)),
        )

    @bot.message_handler(func=lambda m: bool(m.text and parse_lang_choice(m.text)))
    def on_lang_chosen(msg: Any) -> None:
        uid = msg.from_user.id
        code = parse_lang_choice(msg.text)
        if code:
            set_user_lang(uid, code)
            bot.reply_to(
                msg,
                f"{t('tg_lang_changed', user_id=uid)}\n\n{t('tg_welcome', user_id=uid)}",
                reply_markup=build_main_reply_kb(uid),
            )

    @bot.message_handler(func=lambda m: bool(m.text and ("Главное меню" in m.text or "Main Menu" in m.text or "◀" in m.text)))
    def on_back_menu(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_welcome", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: bool(m.text and ("Выбрать язык" in m.text or "Choose Language" in m.text or "🌐" in m.text)))
    def on_click_lang(msg: Any) -> None:
        on_lang_cmd(msg)

    @bot.message_handler(func=lambda m: bool(m.text and ("Инструкция" in m.text or "Instructions" in m.text or "ℹ️" in m.text)))
    def on_click_help(msg: Any) -> None:
        on_help(msg)

    @bot.message_handler(func=lambda m: bool(m.text and ("Отправить медиа" in m.text or "Send Media" in m.text or "🎬" in m.text)))
    def on_click_send_media(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            "📤 <b>Отправьте любое видео или фото прямо сейчас!</b>\n\n"
            "• Видео превратятся в датамош / VHS клипы\n"
            "• Фото превратятся в зацикленные неоновые глитч-арты!",
            reply_markup=build_main_reply_kb(uid),
        )

    @bot.message_handler(func=lambda m: bool(m.text and ("Настройки" in m.text or "Settings" in m.text or "⚙️" in m.text)))
    def on_click_settings(msg: Any) -> None:
        on_settings_cmd(msg)

    @bot.message_handler(func=lambda m: bool(m.text and "+1" in m.text))
    def on_intensity_up(msg: Any) -> None:
        uid = msg.from_user.id
        st = get_user_settings(uid)
        update_user_settings(uid, intensity=min(5, st["intensity"] + 1))
        on_settings_cmd(msg)

    @bot.message_handler(func=lambda m: bool(m.text and "-1" in m.text))
    def on_intensity_down(msg: Any) -> None:
        uid = msg.from_user.id
        st = get_user_settings(uid)
        update_user_settings(uid, intensity=max(1, st["intensity"] - 1))
        on_settings_cmd(msg)

    @bot.message_handler(func=lambda m: bool(m.text and "Формат:" in m.text))
    def on_toggle_fmt(msg: Any) -> None:
        uid = msg.from_user.id
        st = get_user_settings(uid)
        new_fmt = "mp4" if st["format"] == "gif" else "gif"
        update_user_settings(uid, format=new_fmt)
        on_settings_cmd(msg)

    @bot.message_handler(func=lambda m: bool(m.text and "Звук:" in m.text))
    def on_toggle_audio(msg: Any) -> None:
        uid = msg.from_user.id
        st = get_user_settings(uid)
        update_user_settings(uid, audio_glitch=0 if st["audio_glitch"] else 1)
        on_settings_cmd(msg)

    # -----------------------------------------------------------------------
    # Incoming Media Handlers (Video, Video Note, Photo, Document)
    # -----------------------------------------------------------------------
    def handle_incoming_file(msg: Any, file_id: str, is_photo: bool, dur_hint: float, w_hint: int, h_hint: int) -> None:
        uid = msg.from_user.id

        def worker() -> None:
            try:
                bot.send_chat_action(msg.chat.id, "upload_document")
                f_info = bot.get_file(file_id)
                if (getattr(f_info, "file_size", 0) or 0) > 20 * 1024 * 1024:
                    bot.reply_to(msg, "⚠️ Файл слишком большой (> 20 МБ). Telegram Bot API разрешает ботам загружать файлы размером не более 20 МБ.", reply_markup=build_main_reply_kb(uid))
                    return
                f_bytes = bot.download_file(f_info.file_path)

                ext = ".jpg" if is_photo else ".mp4"
                src_path = cache_dir / f"in_glitch_{uid}_{int(time.time())}{ext}"
                src_path.write_bytes(f_bytes)

                probe = probe_media(src_path)
                mtype = probe.get("media_type", "photo" if is_photo else "video")
                dur = probe.get("duration", dur_hint)
                w = probe.get("width", w_hint)
                h = probe.get("height", h_hint)
                has_audio = probe.get("has_audio", False)

                save_pending_media(
                    user_id=uid,
                    file_id=file_id,
                    source_path=str(src_path),
                    media_type=mtype,
                    duration=dur,
                    width=w,
                    height=h,
                    has_audio=has_audio,
                )

                st = get_user_settings(uid)
                reply_txt = t(
                    "msg_media_received",
                    user_id=uid,
                    media_type="Фотография" if mtype == "photo" else "Видео",
                    duration=dur,
                    width=w,
                    height=h,
                    intensity=st["intensity"],
                )
                bot.reply_to(msg, reply_txt, reply_markup=build_glitch_actions_kb(uid))
            except Exception as exc:
                log("log_error", err=f"Failed to handle media: {exc}")
                bot.reply_to(msg, t("msg_err_generic", user_id=uid), reply_markup=build_main_reply_kb(uid))

        threading.Thread(target=worker, daemon=True).start()

    @bot.message_handler(content_types=["video"])
    def on_video(msg: Any) -> None:
        v = msg.video
        handle_incoming_file(msg, v.file_id, False, float(getattr(v, "duration", 0)), int(getattr(v, "width", 640)), int(getattr(v, "height", 640)))

    @bot.message_handler(content_types=["video_note"])
    def on_video_note(msg: Any) -> None:
        vn = msg.video_note
        handle_incoming_file(msg, vn.file_id, False, float(getattr(vn, "duration", 0)), int(getattr(vn, "length", 480)), int(getattr(vn, "length", 480)))

    @bot.message_handler(content_types=["photo"])
    def on_photo(msg: Any) -> None:
        p = msg.photo[-1]
        handle_incoming_file(msg, p.file_id, True, 0.0, int(getattr(p, "width", 800)), int(getattr(p, "height", 800)))

    @bot.message_handler(content_types=["document"])
    def on_document(msg: Any) -> None:
        doc = msg.document
        mime = getattr(doc, "mime_type", "") or ""
        fname = (getattr(doc, "file_name", "") or "").lower()
        if "video" in mime or fname.endswith((".mp4", ".mov", ".mkv", ".avi", ".webm")):
            handle_incoming_file(msg, doc.file_id, False, 0.0, 640, 640)
        elif "image" in mime or fname.endswith((".jpg", ".jpeg", ".png", ".webp")):
            handle_incoming_file(msg, doc.file_id, True, 0.0, 800, 800)
        else:
            bot.reply_to(msg, t("msg_no_media", user_id=msg.from_user.id), reply_markup=build_main_reply_kb(msg.from_user.id))

    # -----------------------------------------------------------------------
    # Glitch Processing Pipeline Trigger
    # -----------------------------------------------------------------------
    def process_glitch(msg: Any, mode: str, force_gif: bool = False) -> None:
        uid = msg.from_user.id
        pending = get_pending_media(uid)
        if not pending:
            bot.reply_to(msg, t("msg_no_media", user_id=uid), reply_markup=build_main_reply_kb(uid))
            return

        src_path = Path(pending["source_path"])
        if not src_path.is_file():
            bot.reply_to(msg, t("msg_no_media", user_id=uid), reply_markup=build_main_reply_kb(uid))
            clear_pending_media(uid)
            return

        st = get_user_settings(uid)
        intensity = st.get("intensity", 3)
        export_gif = force_gif or (st.get("format") == "gif")
        audio_glitch = bool(st.get("audio_glitch", 1))

        status_msg = bot.reply_to(msg, t("msg_processing", user_id=uid))

        def worker() -> None:
            out_ext = ".gif" if export_gif else ".mp4"
            out_file = cache_dir / f"glitch_{uid}_{int(time.time())}{out_ext}"
            try:
                bot.send_chat_action(msg.chat.id, "record_video" if not export_gif else "upload_photo")
                ok = apply_glitch(
                    src_path=src_path,
                    out_path=out_file,
                    mode=mode,
                    intensity=intensity,
                    export_gif=export_gif,
                    audio_glitch=audio_glitch,
                )

                if ok and out_file.is_file():
                    size_kb = out_file.stat().st_size / 1024.0
                    caption = t("msg_success", user_id=uid, mode=mode.upper(), size_kb=size_kb)

                    if export_gif:
                        with out_file.open("rb") as fh:
                            bot.send_animation(msg.chat.id, fh, caption=caption, reply_markup=build_main_reply_kb(uid))
                    else:
                        with out_file.open("rb") as fh:
                            bot.send_video(msg.chat.id, fh, caption=caption, reply_markup=build_main_reply_kb(uid))

                    try:
                        bot.delete_message(msg.chat.id, status_msg.message_id)
                    except Exception:
                        pass
                else:
                    bot.reply_to(msg, t("msg_err_ffmpeg", user_id=uid), reply_markup=build_glitch_actions_kb(uid))
            except Exception as exc:
                log("log_error", err=f"Glitch worker exception: {exc}")
                bot.reply_to(msg, t("msg_err_generic", user_id=uid), reply_markup=build_glitch_actions_kb(uid))
            finally:
                try:
                    if out_file.is_file():
                        out_file.unlink(missing_ok=True)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    # Reply keyboard action buttons
    @bot.message_handler(func=lambda m: bool(m.text and ("Датамош" in m.text or "Datamosh" in m.text or "🌊" in m.text)))
    def on_act_datamosh(msg: Any) -> None:
        process_glitch(msg, mode="datamosh")

    @bot.message_handler(func=lambda m: bool(m.text and ("RGB Split" in m.text or "Хроматика" in m.text or "⚡" in m.text)))
    def on_act_rgb(msg: Any) -> None:
        process_glitch(msg, mode="rgb")

    @bot.message_handler(func=lambda m: bool(m.text and ("VHS" in m.text or "Кассета" in m.text or "📺" in m.text)))
    def on_act_vhs(msg: Any) -> None:
        process_glitch(msg, mode="vhs")

    @bot.message_handler(func=lambda m: bool(m.text and ("Блокчейн" in m.text or "Macroblocks" in m.text or "🔲" in m.text)))
    def on_act_blocks(msg: Any) -> None:
        process_glitch(msg, mode="blocks")

    @bot.message_handler(func=lambda m: bool(m.text and ("Экспорт в GIF" in m.text or "Export as GIF" in m.text or "🎞" in m.text)))
    def on_act_gif(msg: Any) -> None:
        process_glitch(msg, mode="datamosh", force_gif=True)

    @bot.message_handler(func=lambda m: bool(m.text and ("Экспорт в MP4" in m.text or "Export as MP4" in m.text or "🎥" in m.text)))
    def on_act_mp4(msg: Any) -> None:
        process_glitch(msg, mode="datamosh", force_gif=False)

    log("log_started", port=8094)
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except Exception as exc:
        log("log_error", err=f"Glitch bot polling exception: {exc}")


def main() -> None:
    init_db()
    port = int(os.environ.get("WEB_PORT") or 8094)
    start_web_studio(port)

    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        run_bot(token)
    else:
        log("log_started", port=port)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
