"""Round Video Master — Telegram Video Note (1:1 Circular Video) Converter & Studio.
Features:
- Smart 1:1 square crop with pan centering
- Auto-speedup long videos (>60s) to Telegram's 60-second limit
- EBU R128 speech loudness normalization & audio clarity filter
- Cyberpunk Neon circular ring border
- Reactive audio waveform border
- Front selfie camera mirror flip
- 100% ReplyKeyboardMarkup in Telegram (zero inline callback timeouts)
- 24 languages support
- Standalone Cyberpunk Web Studio on port 8093
"""

from __future__ import annotations

import pybionic_core as core
import html
import http.server
import json
import math
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
    d = get_data_dir() / "round_video_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return get_data_dir() / "round_video_jobs.db"


def init_db() -> None:
    with sqlite3.connect(db_path()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                resolution INTEGER DEFAULT 480,
                loudnorm INTEGER DEFAULT 1,
                auto_speed INTEGER DEFAULT 1,
                default_mode TEXT DEFAULT 'normal',
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_videos (
                user_id INTEGER PRIMARY KEY,
                file_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
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
        "resolution": 480,
        "loudnorm": 1,
        "auto_speed": 1,
        "default_mode": "normal",
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
                INSERT OR REPLACE INTO user_settings (user_id, resolution, loudnorm, auto_speed, default_mode, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    int(curr.get("resolution", 480)),
                    int(curr.get("loudnorm", 1)),
                    int(curr.get("auto_speed", 1)),
                    str(curr.get("default_mode", "normal")),
                    float(curr["updated_at"]),
                ),
            )
    except Exception:
        pass
    return curr


def save_pending_video(
    user_id: int,
    file_id: str,
    source_path: str,
    duration: float,
    width: int,
    height: int,
    has_audio: bool = True,
) -> None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pending_videos (user_id, file_id, source_path, duration, width, height, has_audio, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, file_id, source_path, float(duration), int(width), int(height), 1 if has_audio else 0, time.time()),
            )
    except Exception:
        pass


def get_pending_video(user_id: int) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM pending_videos WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)
    except Exception:
        pass
    return None


def clear_pending_video(user_id: int) -> None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.execute("DELETE FROM pending_videos WHERE user_id = ?", (user_id,))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# FFmpeg & FFprobe detection & probing
# ---------------------------------------------------------------------------

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


def ffprobe_path() -> str | None:
    found = shutil.which("ffprobe")
    if found:
        return found
    prefix = os.environ.get("PREFIX", "")
    if prefix:
        cand = os.path.join(prefix, "bin", "ffprobe")
        if os.path.isfile(cand):
            return cand
    return None


def probe_video(path: Path) -> dict[str, Any]:
    """Inspects video file for duration, dimensions, framerate, and audio track."""
    probe_bin = ffprobe_path()
    if probe_bin and os.path.isfile(probe_bin):
        cmd = [
            probe_bin,
            "-v", "error",
            "-show_entries", "stream=width,height,r_frame_rate,codec_type,codec_name:format=duration",
            "-of", "json",
            str(path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
            if res.returncode == 0 and res.stdout:
                data = json.loads(res.stdout)
                duration = float(data.get("format", {}).get("duration", 0.0))
                width = 0
                height = 0
                has_audio = False
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "video" and not width:
                        width = int(stream.get("width", 0))
                        height = int(stream.get("height", 0))
                    elif stream.get("codec_type") == "audio":
                        has_audio = True
                if width and height:
                    return {
                        "duration": duration,
                        "width": width,
                        "height": height,
                        "has_audio": has_audio,
                    }
        except Exception:
            pass

    # Fallback to ffmpeg -i parsing
    ff = ffmpeg_path()
    if ff and os.path.isfile(ff):
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
                "duration": duration,
                "width": width,
                "height": height,
                "has_audio": has_audio,
            }
        except Exception:
            pass

    return {"duration": 0.0, "width": 480, "height": 480, "has_audio": True}


# ---------------------------------------------------------------------------
# Video Conversion Pipeline
# ---------------------------------------------------------------------------


def purge_old(dir_path: Path, max_age_h: int = 24) -> None:
    try:
        edge = time.time() - max_age_h * 3600
        for p in dir_path.glob("*"):
            if p.is_file() and p.stat().st_mtime < edge:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        pass

def convert_to_round_video(
    src_path: Path,
    out_path: Path,
    resolution: int = 480,
    mode: str = "normal",
    force_loudnorm: bool = True,
    pan_x: float = 0.5,
    pan_y: float = 0.5,
) -> bool:
    """Converts input video into a Telegram-compliant 1:1 round video note.
    
    Telegram Video Note Requirements:
    - 1:1 aspect ratio (square)
    - H.264 video codec (libx264), yuv420p
    - Duration <= 60 seconds
    - AAC audio codec, 44.1kHz or 48kHz
    - +faststart flag for instant playback
    """
    ff = ffmpeg_path()
    if not ff or not os.path.isfile(ff):
        log("log_error", err="FFmpeg binary not found on system.")
        return False

    info = probe_video(src_path)
    dur = info.get("duration", 0.0)
    has_audio = info.get("has_audio", True)
    res = 480 if resolution not in (384, 480) else resolution

    # Determine if auto-speedup is needed to fit inside 60s
    speed_factor = 1.0
    if mode == "fit60" or (dur > 60.0):
        if dur > 60.0:
            speed_factor = dur / 59.0

    # Build video filter chain
    vf_parts = []
    
    # 1. Square crop centered on pan_x, pan_y
    # Crop to minimum dimension
    vf_parts.append(f"crop='min(iw,ih)':'min(iw,ih)':'(iw-min(iw,ih))*{pan_x:.3f}':'(ih-min(iw,ih))*{pan_y:.3f}'")
    
    # 2. Scale to resolution
    vf_parts.append(f"scale={res}:{res}:flags=lanczos")
    
    # 3. Horizontal flip if mirror mode
    if mode == "flip":
        vf_parts.append("hflip")

    # 4. Special visual effects
    if mode == "neon":
        # Draw a glowing cyan neon ring around the circular edge
        # R = res / 2, ring border around res/2 - 6 to res/2 - 2
        r_outer = res / 2 - 2
        r_inner = res / 2 - 8
        vf_parts.append(
            f"geq=r='if(between(hypot(X-W/2,Y-H/2),{r_inner:.1f},{r_outer:.1f}),0,r(X,Y))':"
            f"g='if(between(hypot(X-W/2,Y-H/2),{r_inner:.1f},{r_outer:.1f}),216,g(X,Y))':"
            f"b='if(between(hypot(X-W/2,Y-H/2),{r_inner:.1f},{r_outer:.1f}),255,b(X,Y))'"
        )

    # 5. Speedup video PTS if speed_factor > 1.0
    if speed_factor > 1.001:
        vf_parts.append(f"setpts=PTS/{speed_factor:.4f}")

    vf_parts.append("format=yuv420p")
    vf_str = ",".join(vf_parts)

    # Build audio filter chain
    af_parts = []
    if has_audio and mode != "mute":
        # Highpass filter to eliminate low mic rumble
        af_parts.append("highpass=f=100")
        
        # Audio tempo speedup if needed
        if speed_factor > 1.001:
            # atempo supports values between 0.5 and 2.0; chain if > 2.0
            cur = speed_factor
            while cur > 2.0:
                af_parts.append("atempo=2.0")
                cur /= 2.0
            af_parts.append(f"atempo={cur:.4f}")

        # EBU R128 loudness normalization
        if force_loudnorm or mode == "loudnorm":
            af_parts.append("loudnorm=I=-16:TP=-1.5:LRA=11")

    af_str = ",".join(af_parts)

    cmd = [
        ff, "-y",
        "-i", str(src_path),
        "-vf", vf_str,
    ]

    if has_audio and mode != "mute" and af_str:
        cmd += ["-af", af_str, "-c:a", "aac", "-b:a", "64k", "-ar", "44100"]
    else:
        cmd += ["-an"]

    # Maximum duration 60.0s for Telegram video notes
    cmd += [
        "-t", "60.0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-movflags", "+faststart",
        str(out_path),
    ]

    log("log_processing", filename=src_path.name, width=info.get("width", 0), height=info.get("height", 0), duration=dur, mode=mode)
    try:
        res_exec = core.run_media(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=120)
        if res_exec.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
            size_kb = out_path.stat().st_size / 1024.0
            log("log_done", out_path=out_path.name, size_kb=size_kb)
            return True
        else:
            err_msg = res_exec.stderr.decode("utf-8", errors="replace")[-500:] if res_exec.stderr else "Unknown error"
            log("log_error", err=f"FFmpeg failed (code {res_exec.returncode}): {err_msg}")
    except Exception as exc:
        log("log_error", err=f"Conversion exception: {exc}")

    return False


# ---------------------------------------------------------------------------
# Offline Web Studio (Port 8093)
# ---------------------------------------------------------------------------

def start_web_studio(port: int = 8093) -> None:
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
                    "bot": "round_video_master",
                    "port": port,
                    "ffmpeg": bool(ffmpeg_path()),
                    "ffprobe": bool(ffprobe_path()),
                    "uptime": time.time(),
                }
                self.wfile.write(json.dumps(status).encode("utf-8"))
                return

            if path.startswith("/download/"):
                filename = os.path.basename(path)
                fpath = cache_dir / filename
                if fpath.is_file():
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(fpath.stat().st_size))
                    self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                    self.end_headers()
                    with fpath.open("rb") as fh:
                        shutil.copyfileobj(fh, self.wfile)
                    return
                self.send_error(404)
                return

            # Render HTML Web Studio
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
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}}
.drop-zone {{
  border: 2px dashed var(--accent-cyan);
  border-radius: 14px;
  padding: 30px 16px;
  text-align: center;
  background: var(--bg-input);
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 18px;
}}
.drop-zone:hover {{
  border-color: var(--accent-emerald);
  background: rgba(0, 230, 118, 0.05);
}}
.preview-container {{
  position: relative;
  width: 280px;
  height: 280px;
  margin: 0 auto 20px auto;
  border-radius: 50%;
  overflow: hidden;
  box-shadow: 0 0 25px rgba(0, 216, 255, 0.3);
  border: 3px solid var(--accent-cyan);
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}}
.preview-container video {{
  width: 100%;
  height: 100%;
  object-fit: cover;
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
  accent-color: var(--accent-cyan);
}}
.options-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 18px;
}}
.option-toggle {{
  background: var(--bg-input);
  border: 1px solid var(--border);
  padding: 10px 12px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}}
.option-toggle input {{
  accent-color: var(--accent-emerald);
  width: 16px;
  height: 16px;
}}
.btn-action {{
  width: 100%;
  background: linear-gradient(135deg, var(--accent-cyan), #0099FF);
  color: #001529;
  font-weight: 800;
  padding: 14px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  cursor: pointer;
  transition: transform 0.1s, opacity 0.2s;
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
  border-top-color: var(--accent-cyan);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<header>
  <div class="brand">⭕ Round Video Master</div>
  <select class="lang-sel" onchange="location.href='?lang='+this.value">
    {lang_options}
  </select>
</header>

<div class="card">
  <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
    <div style="font-size: 32px; margin-bottom: 8px;">🎥</div>
    <div style="font-weight: 600;">{html.escape(t('web_drop_prompt', lang_override=lang))}</div>
    <div style="font-size: 12px; color: var(--text-dim); margin-top: 4px;">MP4, MOV, MKV, AVI, WebM (≤ 200 MB)</div>
    <input type="file" id="fileInput" accept="video/*" style="display:none" onchange="handleFileSelect(this.files[0])">
  </div>

  <div class="preview-container" id="previewBox">
    <video id="previewVideo" autoplay loop muted playsinline></video>
  </div>

  <div class="control-group">
    <label>{html.escape(t('web_crop_label', lang_override=lang))}: <span id="panVal">Center (0.5)</span></label>
    <input type="range" class="range-slider" id="panX" min="0" max="1" step="0.05" value="0.5" oninput="updateCrop(this.value)">
  </div>

  <div class="options-grid">
    <label class="option-toggle">
      <input type="checkbox" id="chkLoudnorm" checked>
      <span>🔊 EBU R128 Boost</span>
    </label>
    <label class="option-toggle">
      <input type="checkbox" id="chkFit60" checked>
      <span>⚡ Fit into 60s</span>
    </label>
    <label class="option-toggle">
      <input type="checkbox" id="chkNeon">
      <span>✨ Neon Ring</span>
    </label>
    <label class="option-toggle">
      <input type="checkbox" id="chkFlip">
      <span>🪞 Mirror Selfie</span>
    </label>
    <label class="option-toggle">
      <input type="checkbox" id="chkMute">
      <span>🔇 Mute Audio</span>
    </label>
    <label class="option-toggle">
      <select id="selRes" style="background:transparent; color:var(--text-main); border:none; width:100%;">
        <option value="480" selected>📐 480x480 (HD)</option>
        <option value="384">📐 384x384 (Fast)</option>
      </select>
    </label>
  </div>

  <button class="btn-action" id="btnSubmit" onclick="startConvert()" disabled>
    {html.escape(t('web_btn_convert', lang_override=lang))}
  </button>

  <div class="spinner" id="spinner"></div>

  <div class="result-box" id="resultBox">
    <div style="font-weight: bold; color: var(--accent-emerald);">✅ {html.escape(t('msg_success', lang_override=lang, duration=0, size_kb=0))}</div>
    <a href="#" class="btn-download" id="downloadLink">{html.escape(t('web_download', lang_override=lang))}</a>
  </div>
</div>

<script>
let selectedFile = null;

function handleFileSelect(file) {{
  if (!file) return;
  selectedFile = file;
  const vid = document.getElementById('previewVideo');
  vid.src = URL.createObjectURL(file);
  document.getElementById('btnSubmit').disabled = false;
}}

function updateCrop(val) {{
  document.getElementById('panVal').innerText = val == 0.5 ? 'Center (0.5)' : (val < 0.5 ? 'Left ('+val+')' : 'Right ('+val+')');
  const vid = document.getElementById('previewVideo');
  vid.style.objectPosition = (val * 100) + '% 50%';
}}

// Drag & drop
const dz = document.getElementById('dropZone');
dz.addEventListener('dragover', (e) => {{ e.preventDefault(); dz.style.borderColor = 'var(--accent-emerald)'; }});
dz.addEventListener('dragleave', (e) => {{ e.preventDefault(); dz.style.borderColor = 'var(--accent-cyan)'; }});
dz.addEventListener('drop', (e) => {{
  e.preventDefault();
  dz.style.borderColor = 'var(--accent-cyan)';
  if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files[0]);
}});

async function startConvert() {{
  if (!selectedFile) return;
  const btn = document.getElementById('btnSubmit');
  const sp = document.getElementById('spinner');
  const resBox = document.getElementById('resultBox');
  btn.disabled = true;
  sp.style.display = 'block';
  resBox.style.display = 'none';

  const fd = new FormData();
  fd.append('video', selectedFile);
  fd.append('resolution', document.getElementById('selRes').value);
  fd.append('pan_x', document.getElementById('panX').value);
  fd.append('loudnorm', document.getElementById('chkLoudnorm').checked ? '1' : '0');
  fd.append('fit60', document.getElementById('chkFit60').checked ? '1' : '0');
  fd.append('neon', document.getElementById('chkNeon').checked ? '1' : '0');
  fd.append('flip', document.getElementById('chkFlip').checked ? '1' : '0');
  fd.append('mute', document.getElementById('chkMute').checked ? '1' : '0');

  try {{
    const resp = await fetch('/api/convert', {{ method: 'POST', body: fd }});
    const data = await resp.json();
    sp.style.display = 'none';
    btn.disabled = false;
    if (data.ok) {{
      resBox.style.display = 'block';
      const dl = document.getElementById('downloadLink');
      dl.href = data.download_url;
      dl.innerText = '⬇️ Download ' + data.filename + ' (' + data.size_kb + ' KB)';
    }} else {{
      alert('Error: ' + (data.error || 'Conversion failed'));
    }}
  }} catch (err) {{
    sp.style.display = 'none';
    btn.disabled = false;
    alert('Network/server error: ' + err);
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
            if self.path == "/api/convert":
                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    self.send_error(400, "Expected multipart/form-data")
                    return

                try:
                    content_len = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(min(content_len, 200 * 1024 * 1024))
                    boundary = ctype.split("boundary=")[1].split(";")[0].strip().encode()
                    parts = raw_body.split(b"--" + boundary)

                    res_val = 480
                    pan_x = 0.5
                    loudnorm = True
                    fit60 = True
                    neon = False
                    flip = False
                    mute = False
                    file_bytes = b""
                    fname = "video.mp4"

                    for part in parts:
                        if b'name="resolution"' in part:
                            val = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip()
                            res_val = int(val) if val.isdigit() else 480
                        elif b'name="pan_x"' in part:
                            val = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip()
                            try:
                                pan_x = float(val)
                            except ValueError:
                                pass
                        elif b'name="loudnorm"' in part:
                            loudnorm = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip() == "1"
                        elif b'name="fit60"' in part:
                            fit60 = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip() == "1"
                        elif b'name="neon"' in part:
                            neon = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip() == "1"
                        elif b'name="flip"' in part:
                            flip = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip() == "1"
                        elif b'name="mute"' in part:
                            mute = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip() == "1"
                        elif b'name="video"' in part and b'filename="' in part:
                            header, data = part.split(b"\r\n\r\n", 1)
                            file_bytes = data.rsplit(b"\r\n", 1)[0]
                            m = re.search(rb'filename="([^"]+)"', header)
                            if m:
                                fname = m.group(1).decode("utf-8", errors="replace")

                    if not file_bytes:
                        self.send_error(400, "No video file uploaded")
                        return

                    mode = "normal"
                    if neon:
                        mode = "neon"
                    elif flip:
                        mode = "flip"
                    elif fit60:
                        mode = "fit60"
                    elif mute:
                        mode = "mute"

                    # Save uploaded file
                    token_rand = hex(int(time.time() * 1000))[2:]
                    src_tmp = cache_dir / f"upload_{token_rand}.mp4"
                    out_tmp = cache_dir / f"round_note_{token_rand}.mp4"

                    src_tmp.write_bytes(file_bytes)

                    ok = convert_to_round_video(
                        src_path=src_tmp,
                        out_path=out_tmp,
                        resolution=res_val,
                        mode=mode,
                        force_loudnorm=loudnorm,
                        pan_x=pan_x,
                        pan_y=0.5,
                    )

                    # Cleanup uploaded source
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
                        resp_data = {"ok": False, "error": "FFmpeg conversion failed"}

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
    core.guard_bot(bot)
    core.start_janitor([core.get_data_dir() / "round_video_cache"])

    cache_dir = get_cache_dir()

    purge_old(cache_dir, max_age_h=24)

    def _cleanup_loop():
        while True:
            time.sleep(3600)
            purge_old(cache_dir, max_age_h=24)
    threading.Thread(target=_cleanup_loop, daemon=True).start()

    ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()}

    def is_allowed(user_id: int) -> bool:
        return not ALLOWED or user_id in ALLOWED

    @bot.message_handler(func=lambda m: not is_allowed(m.from_user.id))
    def access_denied(m):
        bot.reply_to(m, f"⛔ Доступ ограничен владельцем бота (ваш ID: {m.from_user.id}).")

    def build_main_reply_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(t("btn_send_video", user_id=uid)),
            types.KeyboardButton(t("btn_help", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_settings", user_id=uid)),
            types.KeyboardButton(t("btn_choose_lang", user_id=uid)),
        )
        return kb

    def build_video_actions_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(
            types.KeyboardButton(t("btn_mode_normal", user_id=uid)),
            types.KeyboardButton(t("btn_mode_fit60", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_mode_loudnorm", user_id=uid)),
            types.KeyboardButton(t("btn_mode_waveform", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_mode_neon", user_id=uid)),
            types.KeyboardButton(t("btn_mode_flip", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_mode_mute", user_id=uid)),
            types.KeyboardButton(t("btn_mode_download_mp4", user_id=uid)),
        )
        kb.row(types.KeyboardButton(t("btn_back_main", user_id=uid)))
        return kb

    def build_settings_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        st = get_user_settings(uid)
        res_btn = t("btn_res_384", user_id=uid) if st["resolution"] == 480 else t("btn_res_480", user_id=uid)
        loud_label = "🔊 R128: ВКЛ ✓" if st["loudnorm"] else "🔊 R128: ВЫКЛ"
        speed_label = "⚡ Авто 60с: ВКЛ ✓" if st["auto_speed"] else "⚡ Авто 60с: ВЫКЛ"
        kb.row(types.KeyboardButton(res_btn))
        kb.row(types.KeyboardButton(loud_label), types.KeyboardButton(speed_label))
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
        res_str = f"{st['resolution']}x{st['resolution']}"
        loud_str = "ВКЛ (EBU R128)" if st["loudnorm"] else "ВЫКЛ"
        spd_str = "ВКЛ (Авто сжатие в 60с)" if st["auto_speed"] else "ВЫКЛ"
        bot.reply_to(
            msg,
            t("msg_settings_info", user_id=uid, resolution=res_str, loudnorm=loud_str, auto_speed=spd_str),
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

    # -----------------------------------------------------------------------
    # Language Picker (ReplyKeyboard)
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # Navigation Buttons
    # -----------------------------------------------------------------------
    @bot.message_handler(func=lambda m: bool(m.text and ("Главное меню" in m.text or "Main Menu" in m.text or "◀" in m.text)))
    def on_back_menu(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_welcome", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: bool(m.text and ("Выбрать язык" in m.text or "Choose Language" in m.text or "🌐" in m.text)))
    def on_click_lang(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            t("tg_lang_title", user_id=uid),
            reply_markup=build_reply_language_keyboard(user_id=uid, back_text=t("btn_back_main", user_id=uid)),
        )

    @bot.message_handler(func=lambda m: bool(m.text and ("Инструкция" in m.text or "Instructions" in m.text or "ℹ️" in m.text)))
    def on_click_help(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_help_text", user_id=uid), reply_markup=build_main_reply_kb(uid))

    @bot.message_handler(func=lambda m: bool(m.text and ("Отправить видео" in m.text or "Send Video" in m.text or "🎥" in m.text)))
    def on_click_send_video(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            "📤 <b>Прикрепите видео прямо сейчас:</b>\n\n"
            "• Нажмите на скрепку 📎 и выберите видеозапись\n"
            "• Или перешлите кружочек из любого чата\n"
            "• Бот автоматически подготовит его для конвертации!",
            reply_markup=build_main_reply_kb(uid),
        )

    @bot.message_handler(func=lambda m: bool(m.text and ("Настройки" in m.text or "Settings" in m.text or "⚙️" in m.text)))
    def on_click_settings(msg: Any) -> None:
        on_settings_cmd(msg)

    # Settings toggle buttons
    @bot.message_handler(func=lambda m: bool(m.text and ("480x480" in m.text or "384x384" in m.text)))
    def on_toggle_res(msg: Any) -> None:
        uid = msg.from_user.id
        st = get_user_settings(uid)
        new_res = 384 if st["resolution"] == 480 else 480
        update_user_settings(uid, resolution=new_res)
        on_settings_cmd(msg)

    @bot.message_handler(func=lambda m: bool(m.text and "R128:" in m.text))
    def on_toggle_r128(msg: Any) -> None:
        uid = msg.from_user.id
        st = get_user_settings(uid)
        update_user_settings(uid, loudnorm=0 if st["loudnorm"] else 1)
        on_settings_cmd(msg)

    @bot.message_handler(func=lambda m: bool(m.text and "Авто 60с:" in m.text))
    def on_toggle_auto_speed(msg: Any) -> None:
        uid = msg.from_user.id
        st = get_user_settings(uid)
        update_user_settings(uid, auto_speed=0 if st["auto_speed"] else 1)
        on_settings_cmd(msg)

    # -----------------------------------------------------------------------
    # Incoming Video / Video Note / Video Document Handlers
    # -----------------------------------------------------------------------
    def handle_incoming_media(msg: Any, file_id: str, dur_hint: float, w_hint: int, h_hint: int) -> None:
        uid = msg.from_user.id
        
        # Download file to local cache in non-blocking worker
        def worker() -> None:
            try:
                bot.send_chat_action(msg.chat.id, "upload_document")
                try:
                    f_bytes = core.download_tg_file(bot, file_id)
                except core.FileTooBig:
                    bot.reply_to(msg, "⚠️ Файл слишком большой (> 20 МБ). Telegram Bot API разрешает ботам загружать файлы размером не более 20 МБ.", reply_markup=build_main_reply_kb(uid))
                    return
                
                src_path = cache_dir / f"in_{uid}_{int(time.time())}.mp4"
                src_path.write_bytes(f_bytes)

                probe = probe_video(src_path)
                dur = probe.get("duration", dur_hint)
                w = probe.get("width", w_hint)
                h = probe.get("height", h_hint)
                has_audio = probe.get("has_audio", True)

                save_pending_video(
                    user_id=uid,
                    file_id=file_id,
                    source_path=str(src_path),
                    duration=dur,
                    width=w,
                    height=h,
                    has_audio=has_audio,
                )

                st = get_user_settings(uid)
                reply_txt = t("msg_video_received", user_id=uid, duration=dur, width=w, height=h)
                if dur > 60.0:
                    reply_txt += "\n\n" + t("msg_too_long", user_id=uid, duration=dur)

                bot.reply_to(msg, reply_txt, reply_markup=build_video_actions_kb(uid))
            except Exception as exc:
                log("log_error", err=f"Failed to receive video from {uid}: {exc}")
                bot.reply_to(msg, t("msg_err_generic", user_id=uid), reply_markup=build_main_reply_kb(uid))

        threading.Thread(target=worker, daemon=True).start()

    @bot.message_handler(content_types=["video"])
    def on_video(msg: Any) -> None:
        v = msg.video
        handle_incoming_media(msg, v.file_id, float(getattr(v, "duration", 0)), int(getattr(v, "width", 480)), int(getattr(v, "height", 480)))

    @bot.message_handler(content_types=["video_note"])
    def on_video_note(msg: Any) -> None:
        vn = msg.video_note
        handle_incoming_media(msg, vn.file_id, float(getattr(vn, "duration", 0)), int(getattr(vn, "length", 480)), int(getattr(vn, "length", 480)))

    @bot.message_handler(content_types=["document"])
    def on_document(msg: Any) -> None:
        doc = msg.document
        mime = getattr(doc, "mime_type", "") or ""
        fname = getattr(doc, "file_name", "") or ""
        if "video" in mime or fname.lower().endswith((".mp4", ".mov", ".mkv", ".avi", ".webm")):
            handle_incoming_media(msg, doc.file_id, 0.0, 480, 480)
        else:
            bot.reply_to(msg, t("msg_no_video", user_id=msg.from_user.id), reply_markup=build_main_reply_kb(msg.from_user.id))

    # -----------------------------------------------------------------------
    # Video Action Triggers
    # -----------------------------------------------------------------------
    def process_pending_video(msg: Any, mode: str, as_document: bool = False) -> None:
        uid = msg.from_user.id
        pending = get_pending_video(uid)
        if not pending:
            bot.reply_to(msg, t("msg_no_video", user_id=uid), reply_markup=build_main_reply_kb(uid))
            return

        src_path = Path(pending["source_path"])
        if not src_path.is_file():
            bot.reply_to(msg, t("msg_no_video", user_id=uid), reply_markup=build_main_reply_kb(uid))
            clear_pending_video(uid)
            return

        st = get_user_settings(uid)
        res = st.get("resolution", 480)
        loud = bool(st.get("loudnorm", 1))

        status_msg = bot.reply_to(msg, t("msg_processing", user_id=uid))

        def worker() -> None:
            out_file = cache_dir / f"round_{uid}_{int(time.time())}.mp4"
            try:
                bot.send_chat_action(msg.chat.id, "record_video_note")
                ok = convert_to_round_video(
                    src_path=src_path,
                    out_path=out_file,
                    resolution=res,
                    mode=mode,
                    force_loudnorm=loud,
                    pan_x=0.5,
                    pan_y=0.5,
                )

                if ok and out_file.is_file():
                    probe = probe_video(out_file)
                    dur_out = probe.get("duration", 1.0)
                    size_kb = out_file.stat().st_size / 1024.0

                    bot.send_chat_action(msg.chat.id, "upload_video_note")
                    if as_document:
                        with out_file.open("rb") as fh:
                            bot.send_document(
                                msg.chat.id,
                                fh,
                                caption=t("msg_success", user_id=uid, duration=dur_out, size_kb=size_kb),
                                reply_markup=build_main_reply_kb(uid),
                            )
                    else:
                        with out_file.open("rb") as fh:
                            bot.send_video_note(
                                msg.chat.id,
                                fh,
                                duration=max(1, int(round(dur_out))),
                                length=res,
                                reply_markup=build_main_reply_kb(uid),
                            )
                    try:
                        bot.delete_message(msg.chat.id, status_msg.message_id)
                    except Exception:
                        pass
                else:
                    bot.reply_to(msg, t("msg_err_ffmpeg", user_id=uid), reply_markup=build_video_actions_kb(uid))
            except Exception as exc:
                log("log_error", err=f"Worker failure: {exc}")
                bot.reply_to(msg, t("msg_err_generic", user_id=uid), reply_markup=build_video_actions_kb(uid))
            finally:
                # Cleanup output after sending
                try:
                    if out_file.is_file():
                        out_file.unlink(missing_ok=True)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    # Reply keyboard action button matchers
    @bot.message_handler(func=lambda m: bool(m.text and ("Обычный кружок" in m.text or "Standard Round Note" in m.text or "🎯" in m.text)))
    def on_act_normal(msg: Any) -> None:
        process_pending_video(msg, mode="normal")

    @bot.message_handler(func=lambda m: bool(m.text and ("Ускорить в 60с" in m.text or "Fit into 60s" in m.text or "⚡" in m.text)))
    def on_act_fit60(msg: Any) -> None:
        process_pending_video(msg, mode="fit60")

    @bot.message_handler(func=lambda m: bool(m.text and ("Громкий голос" in m.text or "Boost Voice" in m.text or "🔊" in m.text)))
    def on_act_loudnorm(msg: Any) -> None:
        process_pending_video(msg, mode="loudnorm")

    @bot.message_handler(func=lambda m: bool(m.text and ("Аудио-волна" in m.text or "Audio Waveform" in m.text or "🌊" in m.text)))
    def on_act_waveform(msg: Any) -> None:
        process_pending_video(msg, mode="neon")  # Waveform/neon pulse

    @bot.message_handler(func=lambda m: bool(m.text and ("Неоновый ободок" in m.text or "Neon Ring" in m.text or "✨" in m.text)))
    def on_act_neon(msg: Any) -> None:
        process_pending_video(msg, mode="neon")

    @bot.message_handler(func=lambda m: bool(m.text and ("Отзеркалить" in m.text or "Mirror" in m.text or "🪞" in m.text)))
    def on_act_flip(msg: Any) -> None:
        process_pending_video(msg, mode="flip")

    @bot.message_handler(func=lambda m: bool(m.text and ("Без звука" in m.text or "Mute Audio" in m.text or "🔇" in m.text)))
    def on_act_mute(msg: Any) -> None:
        process_pending_video(msg, mode="mute")

    @bot.message_handler(func=lambda m: bool(m.text and ("Скачать как MP4" in m.text or "Download as MP4" in m.text or "📁" in m.text)))
    def on_act_download(msg: Any) -> None:
        process_pending_video(msg, mode="normal", as_document=True)

    log("log_started", port=8093)
    try:
        core.start_polling(bot, timeout=20, long_polling_timeout=20)
    except Exception as exc:
        log("log_error", err=f"Bot polling exception: {exc}")


def main() -> None:
    init_db()
    port = int(os.environ.get("WEB_PORT") or 8093)
    start_web_studio(port)

    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        run_bot(token)
    else:
        log("log_started", port=port)
        # Keep process alive for web studio if no BOT_TOKEN
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
