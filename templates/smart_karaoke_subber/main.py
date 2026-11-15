"""Smart Karaoke & Subber Studio — Word-by-word highlighted animated karaoke video & subtitle generator.
Features:
- True Advanced SubStation Alpha (.ass) word-by-word karaoke timing (\\k tags)
- Custom animated karaoke styles: Cyberpunk Neon, Classic Gold, TikTok Bounce, Minimal Clean
- Real-time reactive audio waveform / spectrum video synthesis for MP3/voice notes
- Direct video subtitle burning for existing video clips
- LRC timestamped lyrics & plain text auto-timing engine
- 100% ReplyKeyboardMarkup in Telegram (zero inline callback timeouts)
- 24 languages support
- Standalone Cyberpunk Web Studio on port 8095
"""

from __future__ import annotations

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
    d = get_data_dir() / "karaoke_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return get_data_dir() / "karaoke_jobs.db"


def init_db() -> None:
    with sqlite3.connect(db_path()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                style TEXT DEFAULT 'neon',
                background TEXT DEFAULT 'spectrum',
                resolution TEXT DEFAULT '720p',
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_karaoke (
                user_id INTEGER PRIMARY KEY,
                file_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                duration REAL NOT NULL,
                lyrics TEXT DEFAULT '',
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
        "style": "neon",
        "background": "spectrum",
        "resolution": "720p",
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
                INSERT OR REPLACE INTO user_settings (user_id, style, background, resolution, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    str(curr.get("style", "neon")),
                    str(curr.get("background", "spectrum")),
                    str(curr.get("resolution", "720p")),
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
    lyrics: str = "",
) -> None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pending_karaoke (user_id, file_id, source_path, media_type, duration, lyrics, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, file_id, source_path, media_type, float(duration), lyrics, time.time()),
            )
    except Exception:
        pass


def update_pending_lyrics(user_id: int, lyrics: str) -> None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.execute("UPDATE pending_karaoke SET lyrics = ?, updated_at = ? WHERE user_id = ?", (lyrics, time.time(), user_id))
    except Exception:
        pass


def get_pending_media(user_id: int) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM pending_karaoke WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)
    except Exception:
        pass
    return None


def clear_pending_media(user_id: int) -> None:
    try:
        with sqlite3.connect(db_path()) as conn:
            conn.execute("DELETE FROM pending_karaoke WHERE user_id = ?", (user_id,))
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


def probe_audio_duration(path: Path) -> float:
    ff = ffmpeg_path()
    if not ff or not os.path.isfile(ff):
        return 30.0
    try:
        res = subprocess.run([ff, "-i", str(path)], capture_output=True, text=True, check=False, timeout=10)
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):([\d\.]+)", res.stderr or "")
        if dur_match:
            h = float(dur_match.group(1))
            m = float(dur_match.group(2))
            s = float(dur_match.group(3))
            return h * 3600 + m * 60 + s
    except Exception:
        pass
    return 30.0


# ---------------------------------------------------------------------------
# Karaoke ASS Script Generator Engine
# ---------------------------------------------------------------------------

def parse_lrc_lines(lrc_text: str) -> list[tuple[float, str]]:
    """Parses LRC timestamped lyrics: [mm:ss.xx] Lyrics text"""
    results = []
    line_re = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\](.*)")
    for line in lrc_text.splitlines():
        line = line.strip()
        m = line_re.match(line)
        if m:
            mins = int(m.group(1))
            secs = int(m.group(2))
            ms_str = m.group(3) or "0"
            ms = int(ms_str.ljust(3, "0")[:3])
            t_sec = mins * 60.0 + secs + ms / 1000.0
            txt = m.group(4).strip()
            if txt:
                results.append((t_sec, txt))
    return sorted(results, key=lambda x: x[0])


def generate_karaoke_ass(
    lyrics_text: str,
    total_duration: float,
    style_name: str = "neon",
    out_path: Path | None = None,
) -> Path:
    """Generates an Advanced SubStation Alpha (.ass) file with \\k karaoke tags."""
    if out_path is None:
        out_path = get_cache_dir() / f"karaoke_{int(time.time()*1000)}.ass"

    # Style definition mapping
    # Note: in ASS BGR format: &HAABBGGRR
    # Neon: Secondary color &H0000D8FF (Electric Cyan sweep)
    # Gold: Secondary color &H0000D7FF (Gold sweep)
    # TikTok: Secondary color &H0000FFFF (Bright Yellow sweep)
    # Minimal: Secondary color &H00E67600 (Emerald sweep)
    styles = {
        "neon": (
            "Style: Neon,Arial,48,&H00FFFFFF,&H00FF0055,&H0000D8FF,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,3,2,2,40,40,60,1"
        ),
        "gold": (
            "Style: Gold,Arial,48,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,3,2,2,40,40,60,1"
        ),
        "tiktok": (
            "Style: TikTok,Arial Black,54,&H00FFFFFF,&H0000FFFF,&H00000000,&HB0000000,"
            "-1,0,0,0,100,100,0,0,1,4,0,2,40,40,80,1"
        ),
        "minimal": (
            "Style: Minimal,Arial,40,&H00E0E0E0,&H0000D8FF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,0,0,1,2,1,2,30,30,50,1"
        ),
    }

    active_style_key = style_name if style_name in styles else "neon"
    style_def = styles[active_style_key]
    style_label = active_style_key.capitalize()

    # Parse lines: either LRC timestamped or plain text lines
    lrc_parsed = parse_lrc_lines(lyrics_text)
    timed_lines: list[tuple[float, float, str]] = []

    if lrc_parsed:
        for i in range(len(lrc_parsed)):
            st, txt = lrc_parsed[i]
            et = lrc_parsed[i + 1][0] if i + 1 < len(lrc_parsed) else min(total_duration, st + 4.5)
            timed_lines.append((st, et, txt))
    else:
        raw_lines = [l.strip() for l in lyrics_text.splitlines() if l.strip()]
        if not raw_lines:
            raw_lines = [
                "♪ Smart Karaoke Studio ♪",
                "Sing along with the music",
                "PyBionic BotHub Offline",
                "Music connects everything",
            ]
        # Distribute plain lines evenly across duration
        line_dur = max(2.0, total_duration / max(1, len(raw_lines)))
        cur = 0.5
        for line in raw_lines:
            timed_lines.append((cur, cur + line_dur - 0.4, line))
            cur += line_dur

    def fmt_ass_time(sec: float) -> str:
        sec = max(0.0, sec)
        hrs = int(sec // 3600)
        mins = int((sec % 3600) // 60)
        s = int(sec % 60)
        cs = int(round((sec - int(sec)) * 100)) % 100
        return f"{hrs}:{mins:02d}:{s:02d}.{cs:02d}"

    events = []
    for st, et, line in timed_lines:
        words = line.split()
        if not words:
            continue
        dur_cs = int((et - st) * 100)
        per_word_cs = max(10, dur_cs // len(words))

        # Build karaoke line with \k tags
        k_text = ""
        for w in words:
            k_text += f"{{\\k{per_word_cs}}}{w} "

        events.append(f"Dialogue: 0,{fmt_ass_time(st)},{fmt_ass_time(et)},{style_label},,0,0,0,,{k_text.strip()}")

    ass_content = f"""[Script Info]
Title: Smart Karaoke
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_def}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(events) + "\n"

    out_path.write_text(ass_content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Karaoke Video Rendering Pipeline
# ---------------------------------------------------------------------------

FFMPEG_SLOTS = threading.BoundedSemaphore(1)

def render_karaoke_video(
    media_path: Path,
    lyrics_text: str,
    out_video_path: Path,
    style: str = "neon",
    background: str = "spectrum",
) -> bool:
    """Renders a complete MP4 video with burned-in animated karaoke subtitles."""
    ff = ffmpeg_path()
    if not ff or not os.path.isfile(ff):
        log("log_error", err="FFmpeg binary not found.")
        return False

    dur = probe_audio_duration(media_path)
    ass_path = generate_karaoke_ass(lyrics_text, total_duration=dur, style_name=style)

    # Windows path escape for FFmpeg subtitles filter:
    # Need forward slashes and escaped colon: C\:/path/to/sub.ass
    ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

    is_video = media_path.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm", ".avi")

    if is_video:
        # Overlay on existing video
        cmd = [
            ff, "-y",
            "-i", str(media_path),
            "-vf", f"scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,subtitles='{ass_escaped}'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out_video_path),
        ]
    else:
        # Audio file: generate reactive visualizer background + subtitles
        if background == "gradient":
            # Gradient colored background
            bg_filter = "testsrc=size=1280x720:rate=25:duration={dur},hue=s=sin(t):h=t*10"
        else:
            # Pulsing audio waveform
            bg_filter = "showwaves=s=1280x720:mode=cline:colors=0x00D8FF@0.9:scale=sqrt"

        cmd = [
            ff, "-y",
            "-i", str(media_path),
            "-filter_complex",
            f"[0:a]{bg_filter}[bg];"
            f"[bg]subtitles='{ass_escaped}'[v]",
            "-map", "[v]",
            "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(out_video_path),
        ]

    log("log_processing", filename=media_path.name, style=style, bg=background)
    try:
        with FFMPEG_SLOTS:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=180)
        if res.returncode == 0 and out_video_path.is_file() and out_video_path.stat().st_size > 0:
            size_kb = out_video_path.stat().st_size / 1024.0
            log("log_done", out_path=out_video_path.name, size_kb=size_kb)
            return True
        else:
            err_msg = res.stderr.decode("utf-8", errors="replace")[-400:] if res.stderr else "Unknown error"
            log("log_error", err=f"FFmpeg error: {err_msg}")
    except Exception as exc:
        log("log_error", err=f"Karaoke rendering failed: {exc}")

    return False


# ---------------------------------------------------------------------------
# Offline Web Studio (Port 8095)
# ---------------------------------------------------------------------------

def start_web_studio(port: int = 8095) -> None:
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
                    "bot": "smart_karaoke_subber",
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
                    ctype = "text/plain" if filename.endswith((".ass", ".srt")) else "video/mp4"
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
  --accent-gold: #FFC107;
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
  max-width: 720px;
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
  box-shadow: 0 4px 20px rgba(0, 216, 255, 0.1);
}}
.drop-zone {{
  border: 2px dashed var(--accent-cyan);
  border-radius: 14px;
  padding: 26px 16px;
  text-align: center;
  background: var(--bg-input);
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 16px;
}}
.drop-zone:hover {{
  border-color: var(--accent-emerald);
  background: rgba(0, 230, 118, 0.05);
}}
.lyrics-box {{
  width: 100%;
  height: 120px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text-main);
  padding: 12px;
  font-family: monospace;
  font-size: 13px;
  resize: vertical;
  margin-bottom: 16px;
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
.options-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 16px;
}}
.style-btn {{
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text-main);
  padding: 10px 6px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: bold;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}}
.style-btn.active {{
  border-color: var(--accent-cyan);
  background: rgba(0, 216, 255, 0.15);
  color: var(--accent-cyan);
}}
.btn-action {{
  width: 100%;
  background: linear-gradient(135deg, var(--accent-cyan), #0066FF);
  color: #001529;
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
  margin: 6px 4px;
  background: var(--accent-emerald);
  color: #003314;
  font-weight: bold;
  padding: 10px 18px;
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
  <div class="brand">🎤 Smart Karaoke Studio</div>
  <select class="lang-sel" onchange="location.href='?lang='+this.value">
    {lang_options}
  </select>
</header>

<div class="card">
  <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
    <div style="font-size: 32px; margin-bottom: 6px;">🎵</div>
    <div style="font-weight: 600;">{html.escape(t('web_drop_prompt', lang_override=lang))}</div>
    <div style="font-size: 12px; color: var(--text-dim); margin-top: 4px;" id="fileInfoLabel">MP3, WAV, OGG, MP4, MOV, MKV</div>
    <input type="file" id="fileInput" accept="audio/*,video/*" style="display:none" onchange="handleFileSelect(this.files[0])">
  </div>

  <div class="control-group">
    <label>{html.escape(t('web_lyrics_prompt', lang_override=lang))}</label>
    <textarea class="lyrics-box" id="lyricsInput" placeholder="Line 1 of song\nLine 2 of song\nOr [00:12.30] Synced LRC format..."></textarea>
  </div>

  <div class="control-group">
    <label>{html.escape(t('web_style_label', lang_override=lang))}</label>
    <div class="options-grid">
      <div class="style-btn active" id="btnStyleNeon" onclick="selectStyle('neon')">✨ Neon</div>
      <div class="style-btn" id="btnStyleGold" onclick="selectStyle('gold')">🌟 Gold</div>
      <div class="style-btn" id="btnStyleTiktok" onclick="selectStyle('tiktok')">📱 TikTok</div>
      <div class="style-btn" id="btnStyleMinimal" onclick="selectStyle('minimal')">⚪ Minimal</div>
    </div>
  </div>

  <button class="btn-action" id="btnSubmit" onclick="startRender()" disabled>
    {html.escape(t('web_btn_render', lang_override=lang))}
  </button>

  <div class="spinner" id="spinner"></div>

  <div class="result-box" id="resultBox">
    <div style="font-weight: bold; color: var(--accent-emerald);">✅ Karaoke render complete!</div>
    <a href="#" class="btn-download" id="downloadVideo">{html.escape(t('web_download', lang_override=lang))}</a>
  </div>
</div>

<script>
let selectedFile = null;
let currentStyle = 'neon';

function selectStyle(s) {{
  currentStyle = s;
  document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
  if (s === 'neon') document.getElementById('btnStyleNeon').classList.add('active');
  if (s === 'gold') document.getElementById('btnStyleGold').classList.add('active');
  if (s === 'tiktok') document.getElementById('btnStyleTiktok').classList.add('active');
  if (s === 'minimal') document.getElementById('btnStyleMinimal').classList.add('active');
}}

function handleFileSelect(file) {{
  if (!file) return;
  selectedFile = file;
  document.getElementById('fileInfoLabel').innerText = file.name + ' (' + (file.size/1024/1024).toFixed(1) + ' MB)';
  document.getElementById('btnSubmit').disabled = false;
}}

const dz = document.getElementById('dropZone');
dz.addEventListener('dragover', (e) => {{ e.preventDefault(); dz.style.borderColor = 'var(--accent-emerald)'; }});
dz.addEventListener('dragleave', (e) => {{ e.preventDefault(); dz.style.borderColor = 'var(--accent-cyan)'; }});
dz.addEventListener('drop', (e) => {{
  e.preventDefault();
  dz.style.borderColor = 'var(--accent-cyan)';
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
  fd.append('lyrics', document.getElementById('lyricsInput').value);
  fd.append('style', currentStyle);

  try {{
    const resp = await fetch('/api/render', {{ method: 'POST', body: fd }});
    const data = await resp.json();
    sp.style.display = 'none';
    btn.disabled = false;
    if (data.ok) {{
      resBox.style.display = 'block';
      const dlVid = document.getElementById('downloadVideo');
      dlVid.href = data.download_url;
      dlVid.innerText = '⬇️ Download ' + data.filename + ' (' + data.size_kb + ' KB)';
    }} else {{
      alert('Error: ' + (data.error || 'Karaoke render failed'));
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

                    style = "neon"
                    lyrics = ""
                    file_bytes = b""
                    fname = "audio.mp3"

                    for part in parts:
                        if b'name="style"' in part:
                            style = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode().strip()
                        elif b'name="lyrics"' in part:
                            lyrics = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0].decode("utf-8", errors="replace").strip()
                        elif b'name="media"' in part and b'filename="' in part:
                            header, data = part.split(b"\r\n\r\n", 1)
                            file_bytes = data.rsplit(b"\r\n", 1)[0]
                            m = re.search(rb'filename="([^"]+)"', header)
                            if m:
                                fname = m.group(1).decode("utf-8", errors="replace")

                    if not file_bytes:
                        self.send_error(400, "No media file uploaded")
                        return

                    ext = os.path.splitext(fname)[1].lower() or ".mp3"
                    token_rand = hex(int(time.time() * 1000))[2:]
                    src_tmp = cache_dir / f"upload_{token_rand}{ext}"
                    out_tmp = cache_dir / f"karaoke_{token_rand}.mp4"

                    src_tmp.write_bytes(file_bytes)

                    ok = render_karaoke_video(
                        media_path=src_tmp,
                        lyrics_text=lyrics,
                        out_video_path=out_tmp,
                        style=style,
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
                        resp_data = {"ok": False, "error": "Karaoke rendering failed"}

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

    def build_karaoke_actions_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.row(types.KeyboardButton(t("btn_render_video", user_id=uid)))
        kb.row(
            types.KeyboardButton(t("btn_style_neon", user_id=uid)),
            types.KeyboardButton(t("btn_style_gold", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_style_tiktok", user_id=uid)),
            types.KeyboardButton(t("btn_style_minimal", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_export_ass", user_id=uid)),
            types.KeyboardButton(t("btn_back_main", user_id=uid)),
        )
        return kb

    def build_settings_kb(uid: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        st = get_user_settings(uid)
        kb.row(
            types.KeyboardButton(t("btn_style_neon", user_id=uid)),
            types.KeyboardButton(t("btn_style_gold", user_id=uid)),
        )
        kb.row(
            types.KeyboardButton(t("btn_bg_spectrum", user_id=uid)),
            types.KeyboardButton(t("btn_bg_gradient", user_id=uid)),
        )
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
        bot.reply_to(
            msg,
            t("msg_settings_info", user_id=uid, style=st["style"].upper(), bg=st["background"].upper(), resolution=st["resolution"]),
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

    @bot.message_handler(func=lambda m: bool(m.text and ("Отправить аудио" in m.text or "Send Audio" in m.text or "🎤" in m.text)))
    def on_click_send_media(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(
            msg,
            "📤 <b>Отправьте песню, голосовое сообщение или видеофайл:</b>\n\n"
            "• Бот считает длительность и подготовит аудио-спектр\n"
            "• Затем просто пришлите текст песни!",
            reply_markup=build_main_reply_kb(uid),
        )

    @bot.message_handler(func=lambda m: bool(m.text and ("Настройки" in m.text or "Settings" in m.text or "⚙️" in m.text)))
    def on_click_settings(msg: Any) -> None:
        on_settings_cmd(msg)

    # Style toggle buttons
    @bot.message_handler(func=lambda m: bool(m.text and ("Неон" in m.text or "Neon" in m.text)))
    def on_set_neon(msg: Any) -> None:
        update_user_settings(msg.from_user.id, style="neon")
        bot.reply_to(msg, "✨ Выбран стиль: <b>Неон Киберпанк</b>", reply_markup=build_karaoke_actions_kb(msg.from_user.id))

    @bot.message_handler(func=lambda m: bool(m.text and ("Золотой" in m.text or "Gold" in m.text)))
    def on_set_gold(msg: Any) -> None:
        update_user_settings(msg.from_user.id, style="gold")
        bot.reply_to(msg, "🌟 Выбран стиль: <b>Золотой глянец</b>", reply_markup=build_karaoke_actions_kb(msg.from_user.id))

    @bot.message_handler(func=lambda m: bool(m.text and "TikTok" in m.text))
    def on_set_tiktok(msg: Any) -> None:
        update_user_settings(msg.from_user.id, style="tiktok")
        bot.reply_to(msg, "📱 Выбран стиль: <b>TikTok Bounce</b>", reply_markup=build_karaoke_actions_kb(msg.from_user.id))

    @bot.message_handler(func=lambda m: bool(m.text and ("Минимализм" in m.text or "Minimal" in m.text)))
    def on_set_minimal(msg: Any) -> None:
        update_user_settings(msg.from_user.id, style="minimal")
        bot.reply_to(msg, "⚪ Выбран стиль: <b>Минимализм</b>", reply_markup=build_karaoke_actions_kb(msg.from_user.id))

    # -----------------------------------------------------------------------
    # Media Handlers (Audio, Voice, Video, Documents)
    # -----------------------------------------------------------------------
    def handle_incoming_audio(msg: Any, file_id: str, is_video: bool, dur_hint: float) -> None:
        uid = msg.from_user.id

        def worker() -> None:
            try:
                bot.send_chat_action(msg.chat.id, "upload_document")
                f_info = bot.get_file(file_id)
                if (getattr(f_info, "file_size", 0) or 0) > 20 * 1024 * 1024:
                    bot.reply_to(msg, "⚠️ Файл слишком большой (> 20 МБ). Telegram Bot API разрешает ботам загружать файлы размером не более 20 МБ.", reply_markup=build_main_reply_kb(uid))
                    return
                f_bytes = bot.download_file(f_info.file_path)

                ext = ".mp4" if is_video else ".mp3"
                src_path = cache_dir / f"in_karaoke_{uid}_{int(time.time())}{ext}"
                src_path.write_bytes(f_bytes)

                dur = probe_audio_duration(src_path) or dur_hint

                save_pending_media(
                    user_id=uid,
                    file_id=file_id,
                    source_path=str(src_path),
                    media_type="video" if is_video else "audio",
                    duration=dur,
                )

                reply_txt = t("msg_media_received", user_id=uid, duration=dur)
                bot.reply_to(msg, reply_txt, reply_markup=build_karaoke_actions_kb(uid))
            except Exception as exc:
                log("log_error", err=f"Failed to receive audio: {exc}")
                bot.reply_to(msg, t("msg_err_generic", user_id=uid), reply_markup=build_main_reply_kb(uid))

        threading.Thread(target=worker, daemon=True).start()

    @bot.message_handler(content_types=["audio"])
    def on_audio(msg: Any) -> None:
        a = msg.audio
        handle_incoming_audio(msg, a.file_id, False, float(getattr(a, "duration", 0)))

    @bot.message_handler(content_types=["voice"])
    def on_voice(msg: Any) -> None:
        v = msg.voice
        handle_incoming_audio(msg, v.file_id, False, float(getattr(v, "duration", 0)))

    @bot.message_handler(content_types=["video"])
    def on_video(msg: Any) -> None:
        v = msg.video
        handle_incoming_audio(msg, v.file_id, True, float(getattr(v, "duration", 0)))

    @bot.message_handler(content_types=["document"])
    def on_document(msg: Any) -> None:
        doc = msg.document
        fname = (getattr(doc, "file_name", "") or "").lower()
        if fname.endswith((".lrc", ".srt", ".txt")):
            # It's lyrics or subtitles!
            f_info = bot.get_file(doc.file_id)
            f_bytes = bot.download_file(f_info.file_path)
            lyrics = f_bytes.decode("utf-8", errors="replace")
            update_pending_lyrics(msg.from_user.id, lyrics)
            lines_cnt = len([l for l in lyrics.splitlines() if l.strip()])
            bot.reply_to(
                msg,
                t("msg_lyrics_received", user_id=msg.from_user.id, lines=lines_cnt),
                reply_markup=build_karaoke_actions_kb(msg.from_user.id),
            )
        elif fname.endswith((".mp3", ".wav", ".ogg", ".m4a", ".flac", ".mp4")):
            handle_incoming_audio(msg, doc.file_id, fname.endswith(".mp4"), 0.0)
        else:
            bot.reply_to(msg, t("msg_no_media", user_id=msg.from_user.id), reply_markup=build_main_reply_kb(msg.from_user.id))

    # Plain text handler for lyrics input
    @bot.message_handler(func=lambda m: bool(m.text and not m.text.startswith("/") and len(m.text.splitlines()) >= 2))
    def on_lyrics_text(msg: Any) -> None:
        uid = msg.from_user.id
        lyrics = msg.text.strip()
        update_pending_lyrics(uid, lyrics)
        lines_cnt = len(lyrics.splitlines())
        bot.reply_to(
            msg,
            t("msg_lyrics_received", user_id=uid, lines=lines_cnt),
            reply_markup=build_karaoke_actions_kb(uid),
        )

    # -----------------------------------------------------------------------
    # Render & Export Triggers
    # -----------------------------------------------------------------------
    @bot.message_handler(func=lambda m: bool(m.text and ("Создать караоке-видео" in m.text or "Render Karaoke" in m.text or "🎬" in m.text)))
    def on_act_render(msg: Any) -> None:
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

        lyrics = pending.get("lyrics", "")
        st = get_user_settings(uid)
        style = st.get("style", "neon")
        bg = st.get("background", "spectrum")

        status_msg = bot.reply_to(msg, t("msg_processing", user_id=uid))

        def worker() -> None:
            out_file = cache_dir / f"karaoke_{uid}_{int(time.time())}.mp4"
            try:
                bot.send_chat_action(msg.chat.id, "record_video")
                ok = render_karaoke_video(
                    media_path=src_path,
                    lyrics_text=lyrics,
                    out_video_path=out_file,
                    style=style,
                    background=bg,
                )

                if ok and out_file.is_file():
                    size_kb = out_file.stat().st_size / 1024.0
                    caption = t("msg_success", user_id=uid, style=style.upper(), size_kb=size_kb)
                    with out_file.open("rb") as fh:
                        bot.send_video(msg.chat.id, fh, caption=caption, reply_markup=build_main_reply_kb(uid))
                    try:
                        bot.delete_message(msg.chat.id, status_msg.message_id)
                    except Exception:
                        pass
                else:
                    bot.reply_to(msg, t("msg_err_ffmpeg", user_id=uid), reply_markup=build_karaoke_actions_kb(uid))
            except Exception as exc:
                log("log_error", err=f"Karaoke worker exception: {exc}")
                bot.reply_to(msg, t("msg_err_generic", user_id=uid), reply_markup=build_karaoke_actions_kb(uid))
            finally:
                try:
                    if out_file.is_file():
                        out_file.unlink(missing_ok=True)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    @bot.message_handler(func=lambda m: bool(m.text and (".ASS" in m.text or ".SRT" in m.text or "📄" in m.text)))
    def on_act_export_ass(msg: Any) -> None:
        uid = msg.from_user.id
        pending = get_pending_media(uid)
        lyrics = pending.get("lyrics", "") if pending else "No lyrics provided"
        dur = pending.get("duration", 30.0) if pending else 30.0
        st = get_user_settings(uid)

        ass_file = generate_karaoke_ass(lyrics, total_duration=dur, style_name=st.get("style", "neon"))
        if ass_file.is_file():
            with ass_file.open("rb") as fh:
                bot.send_document(msg.chat.id, fh, caption="📄 Валидный караоке-файл SubStation Alpha (.ASS)")

    log("log_started", port=8095)
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except Exception as exc:
        log("log_error", err=f"Karaoke bot polling exception: {exc}")


def main() -> None:
    init_db()
    port = int(os.environ.get("WEB_PORT") or 8095)
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
