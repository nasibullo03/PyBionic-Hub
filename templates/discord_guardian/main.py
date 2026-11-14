"""Discord Guardian Pro — Anti-Spam, Word Filter, Moderation, Tickets & XP Leaderboard (SQLite).
Features Rich Cyberpunk Embeds, guild language preferences, full 24-language support, and Cyberpunk Web Studio.
"""

from __future__ import annotations

import os
import sys
import json
import sqlite3
import time
import threading
import urllib.parse
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# Unbuffered output for real-time mobile logs
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

from i18n import current_lang, log, normalize_lang_tag, t

WEB_PORT = int(os.environ.get("WEB_PORT") or os.environ.get("STUDIO_PORT") or 8113)


def db_path() -> Path:
    base = Path(os.environ.get("PROJECT_DATA_DIR") or Path(__file__).resolve().parent / "data")
    base.mkdir(parents=True, exist_ok=True)
    return base / "guardian.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS user_xp (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                xp INTEGER DEFAULT 0,
                warns INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS bad_words (
                guild_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                PRIMARY KEY (guild_id, word)
            );
            CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                lang TEXT NOT NULL DEFAULT 'en'
            );
            """
        )
        # Seed default filter words if table is empty
        cnt = conn.execute("SELECT COUNT(*) FROM bad_words").fetchone()[0]
        if cnt == 0:
            defaults = ["scam", "phishing", "free-nitro", "hack", "discord-gift", "token-stealer"]
            for w in defaults:
                conn.execute("INSERT OR IGNORE INTO bad_words (guild_id, word) VALUES (0, ?)", (w,))


def get_guardian_stats() -> dict[str, Any]:
    try:
        with get_conn() as conn:
            logs_count = conn.execute("SELECT COUNT(*) FROM mod_logs").fetchone()[0]
            words_count = conn.execute("SELECT COUNT(*) FROM bad_words").fetchone()[0]
            users_count = conn.execute("SELECT COUNT(*) FROM user_xp").fetchone()[0]
            warns_sum = conn.execute("SELECT COALESCE(SUM(warns), 0) FROM user_xp").fetchone()[0]
            return {
                "mod_logs": logs_count,
                "bad_words": words_count,
                "ranked_users": users_count,
                "total_warns": warns_sum,
            }
    except Exception:
        return {"mod_logs": 0, "bad_words": 0, "ranked_users": 0, "total_warns": 0}


def get_bad_words(guild_id: int = 0) -> list[str]:
    try:
        with get_conn() as conn:
            rows = conn.execute("SELECT word FROM bad_words WHERE guild_id = ? OR guild_id = 0 ORDER BY word ASC", (guild_id,)).fetchall()
            return [r["word"] for r in rows]
    except Exception:
        return []


def add_bad_word(guild_id: int, word: str) -> bool:
    w = word.strip().lower()
    if not w:
        return False
    try:
        with get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO bad_words (guild_id, word) VALUES (?, ?)", (guild_id, w))
            return True
    except Exception:
        return False


def delete_bad_word(guild_id: int, word: str) -> bool:
    w = word.strip().lower()
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM bad_words WHERE (guild_id = ? OR guild_id = 0) AND word = ?", (guild_id, w))
            return True
    except Exception:
        return False


def get_mod_logs(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with get_conn() as conn:
            rows = conn.execute("SELECT id, guild_id, user_id, action, reason, created_at FROM mod_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def get_leaderboard(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with get_conn() as conn:
            rows = conn.execute("SELECT guild_id, user_id, xp, warns FROM user_xp ORDER BY xp DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def get_guild_lang(guild_id: int) -> str:
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT lang FROM guild_settings WHERE guild_id = ?", (guild_id,)).fetchone()
            if row and row[0]:
                return normalize_lang_tag(row[0])
    except Exception:
        pass
    return current_lang()


def set_guild_lang(guild_id: int, lang_code: str) -> str:
    norm = normalize_lang_tag(lang_code)
    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO guild_settings (guild_id, lang)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET lang = excluded.lang
                """,
                (guild_id, norm),
            )
    except Exception:
        pass
    return norm


# ===========================================================================
# Cyberpunk Web Studio Handler & HTML
# ===========================================================================

WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Discord Guardian Pro — Web Studio</title>
<style>
:root {
  --bg: #090d16;
  --surface: #101726;
  --card: #151f33;
  --border: #1e2c47;
  --accent: #5865f2;
  --accent-glow: rgba(88, 101, 242, 0.35);
  --cyan: #00d8ff;
  --emerald: #00e676;
  --gold: #ffc107;
  --danger: #ff4757;
  --text: #f1f5f9;
  --text-muted: #94a3b8;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
body { background: var(--bg); color: var(--text); padding: 16px; min-height: 100vh; }
.container { max-width: 960px; margin: 0 auto; }
header {
  background: linear-gradient(135deg, rgba(88, 101, 242, 0.15), rgba(0, 216, 255, 0.05));
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.brand { display: flex; align-items: center; gap: 14px; }
.logo-icon {
  width: 48px; height: 48px; border-radius: 12px;
  background: var(--accent);
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; box-shadow: 0 0 16px var(--accent-glow);
}
.brand h1 { font-size: 1.4rem; font-weight: 700; color: #fff; }
.brand p { font-size: 0.85rem; color: var(--text-muted); margin-top: 2px; }
.badges { display: flex; gap: 8px; flex-wrap: wrap; }
.badge {
  padding: 6px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
  display: inline-flex; align-items: center; gap: 6px;
}
.badge-online { background: rgba(0, 230, 118, 0.15); color: var(--emerald); border: 1px solid rgba(0, 230, 118, 0.3); }
.badge-port { background: rgba(88, 101, 242, 0.15); color: var(--cyan); border: 1px solid rgba(88, 101, 242, 0.3); }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px; }
.stat-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 16px;
  display: flex; flex-direction: column; gap: 6px; transition: transform 0.2s, border-color 0.2s;
}
.stat-card:hover { transform: translateY(-2px); border-color: var(--accent); }
.stat-card .label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.stat-card .value { font-size: 1.7rem; font-weight: 800; color: #fff; }
.section-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  padding: 20px; margin-bottom: 20px;
}
.section-title { font-size: 1.1rem; font-weight: 700; color: #fff; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.filter-input-row { display: flex; gap: 10px; margin-bottom: 16px; }
input[type="text"] {
  flex: 1; background: var(--card); border: 1px solid var(--border);
  color: #fff; padding: 10px 14px; border-radius: 10px; font-size: 0.95rem; outline: none;
}
input[type="text"]:focus { border-color: var(--cyan); box-shadow: 0 0 10px rgba(0, 216, 255, 0.2); }
button.btn {
  background: var(--accent); color: #fff; border: none; padding: 10px 18px;
  border-radius: 10px; font-weight: 600; font-size: 0.9rem; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px; transition: background 0.2s;
}
button.btn:hover { background: #4752c4; }
.chips-container { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  background: var(--card); border: 1px solid var(--border); padding: 6px 12px;
  border-radius: 8px; font-size: 0.85rem; color: var(--text);
  display: inline-flex; align-items: center; gap: 8px;
}
.chip .del-btn {
  color: var(--danger); cursor: pointer; font-weight: bold; font-size: 1rem; line-height: 1;
}
.chip .del-btn:hover { color: #ff6b81; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
th { color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }
tr:hover { background: rgba(255, 255, 255, 0.02); }
.badge-action {
  padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;
}
.action-warn { background: rgba(255, 193, 7, 0.2); color: var(--gold); }
.action-filter { background: rgba(255, 71, 87, 0.2); color: var(--danger); }
.action-mod { background: rgba(0, 216, 255, 0.2); color: var(--cyan); }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="brand">
      <div class="logo-icon">🛡️</div>
      <div>
        <h1>Discord Guardian Pro</h1>
        <p>Anti-Spam • Word Filter • Moderation • XP Leaderboard</p>
      </div>
    </div>
    <div class="badges">
      <span class="badge badge-online">🟢 Web Studio Online</span>
      <span class="badge badge-port" id="portBadge">PORT: ...</span>
    </div>
  </header>

  <div class="stats-grid">
    <div class="stat-card">
      <span class="label">🚫 Filter Words</span>
      <span class="value" id="statWords">0</span>
    </div>
    <div class="stat-card">
      <span class="label">⚖️ Mod Audit Logs</span>
      <span class="value" id="statLogs">0</span>
    </div>
    <div class="stat-card">
      <span class="label">👥 Tracked Users</span>
      <span class="value" id="statUsers">0</span>
    </div>
    <div class="stat-card">
      <span class="label">⚠️ Total Warnings</span>
      <span class="value" id="statWarns">0</span>
    </div>
  </div>

  <div class="section-card">
    <h2 class="section-title">🚫 Word Filter Blacklist</h2>
    <div class="filter-input-row">
      <input type="text" id="wordInput" placeholder="Enter word or pattern to filter (e.g. scam-link)...">
      <button class="btn" onclick="addWord()">+ Add Word</button>
    </div>
    <div class="chips-container" id="wordsContainer">
      <span style="color:var(--text-muted);">Loading bad words...</span>
    </div>
  </div>

  <div class="section-card">
    <h2 class="section-title">🏆 Top XP Members</h2>
    <table>
      <thead>
        <tr><th>Rank</th><th>Guild ID</th><th>User ID</th><th>XP Points</th><th>Warnings</th></tr>
      </thead>
      <tbody id="leaderboardBody">
        <tr><td colspan="5" style="text-align:center; color:var(--text-muted);">Loading leaderboard...</td></tr>
      </tbody>
    </table>
  </div>

  <div class="section-card">
    <h2 class="section-title">📜 Recent Moderation Logs</h2>
    <table>
      <thead>
        <tr><th>Time</th><th>User ID</th><th>Action</th><th>Reason / Details</th></tr>
      </thead>
      <tbody id="logsBody">
        <tr><td colspan="4" style="text-align:center; color:var(--text-muted);">Loading logs...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
async function refreshData() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('portBadge').textContent = 'PORT: ' + data.port;
    document.getElementById('statWords').textContent = data.stats.bad_words;
    document.getElementById('statLogs').textContent = data.stats.mod_logs;
    document.getElementById('statUsers').textContent = data.stats.ranked_users;
    document.getElementById('statWarns').textContent = data.stats.total_warns;
  } catch(e) {}

  try {
    const res = await fetch('/api/words');
    const words = await res.json();
    const cont = document.getElementById('wordsContainer');
    if (!words || words.length === 0) {
      cont.innerHTML = '<span style="color:var(--text-muted)">No active filter words.</span>';
    } else {
      cont.innerHTML = words.map(w =>
        `<span class="chip">${escapeHtml(w)} <span class="del-btn" onclick="deleteWord('${escapeHtml(w)}')">&times;</span></span>`
      ).join('');
    }
  } catch(e) {}

  try {
    const res = await fetch('/api/leaderboard');
    const top = await res.json();
    const tbody = document.getElementById('leaderboardBody');
    if (!top || top.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted)">No members ranked yet.</td></tr>';
    } else {
      tbody.innerHTML = top.map((r, i) =>
        `<tr>
          <td><strong>#${i+1}</strong></td>
          <td><code>${r.guild_id}</code></td>
          <td><code>${r.user_id}</code></td>
          <td><span style="color:var(--gold); font-weight:700;">${r.xp} XP</span></td>
          <td>${r.warns > 0 ? '<span style="color:var(--danger)">⚠️ ' + r.warns + '</span>' : '0'}</td>
        </tr>`
      ).join('');
    }
  } catch(e) {}

  try {
    const res = await fetch('/api/logs');
    const logs = await res.json();
    const tbody = document.getElementById('logsBody');
    if (!logs || logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted)">No moderation actions logged yet.</td></tr>';
    } else {
      tbody.innerHTML = logs.map(l => {
        let cls = 'action-mod';
        if (l.action === 'WARN') cls = 'action-warn';
        if (l.action === 'WORD_FILTER') cls = 'action-filter';
        const d = new Date(l.created_at * 1000).toLocaleTimeString();
        return `<tr>
          <td>${d}</td>
          <td><code>${l.user_id}</code></td>
          <td><span class="badge-action ${cls}">${escapeHtml(l.action)}</span></td>
          <td>${escapeHtml(l.reason || '-')}</td>
        </tr>`;
      }).join('');
    }
  } catch(e) {}
}

async function addWord() {
  const inp = document.getElementById('wordInput');
  const w = inp.value.trim();
  if (!w) return;
  await fetch('/api/add_word?word=' + encodeURIComponent(w), { method: 'POST' });
  inp.value = '';
  refreshData();
}

async function deleteWord(w) {
  await fetch('/api/delete_word?word=' + encodeURIComponent(w), { method: 'POST' });
  refreshData();
}

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

document.getElementById('wordInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') addWord();
});

refreshData();
setInterval(refreshData, 5000);
</script>
</body>
</html>
"""


class WebStudioHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            if "?" not in self.path and body:
                if "application/json" in self.headers.get("Content-Type", ""):
                    try:
                        j = json.loads(body)
                        q = urllib.parse.urlencode({k: str(v) for k, v in j.items()})
                        self.path = f"{self.path}?{q}"
                    except Exception:
                        pass
                else:
                    self.path = f"{self.path}?{body}"
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(WEB_STUDIO_HTML.encode("utf-8"))
            return

        elif path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            stats = get_guardian_stats()
            data = {
                "status": "online",
                "bot": "discord_guardian",
                "port": WEB_PORT,
                "stats": stats,
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path == "/api/words":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            words = get_bad_words(0)
            self.wfile.write(json.dumps(words).encode("utf-8"))
            return

        elif path == "/api/add_word":
            w = query.get("word", [""])[0]
            ok = add_bad_word(0, w)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "words": get_bad_words(0)}).encode("utf-8"))
            return

        elif path == "/api/delete_word":
            w = query.get("word", [""])[0]
            ok = delete_bad_word(0, w)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "words": get_bad_words(0)}).encode("utf-8"))
            return

        elif path == "/api/logs":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            logs = get_mod_logs(50)
            self.wfile.write(json.dumps(logs).encode("utf-8"))
            return

        elif path == "/api/leaderboard":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            board = get_leaderboard(20)
            self.wfile.write(json.dumps(board).encode("utf-8"))
            return

        self.send_error(404, "Not Found")


class ThreadedStudioServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_web_studio() -> None:
    try:
        server = ThreadedStudioServer((os.environ.get("BIND_HOST", "127.0.0.1"), WEB_PORT), WebStudioHandler)
        print(f"[PYBIONIC_WEB:{WEB_PORT}]", flush=True)
        log("log_web_started", port=WEB_PORT)
        server.serve_forever()
    except Exception as exc:
        print(f"[Discord Guardian Pro] Web Studio server error on port {WEB_PORT}: {exc}", flush=True)


# ===========================================================================
# Discord Bot Core (discord.py)
# ===========================================================================

def run_discord_bot(token: str) -> None:
    try:
        import discord
        from discord.ext import commands
    except ImportError:
        print("[Discord Guardian Pro] discord.py is not installed. Running in Web Studio mode.", flush=True)
        return

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    prefix = os.environ.get("COMMAND_PREFIX", "!").strip() or "!"
    bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)
    msg_history: dict[tuple[int, int], deque[float]] = defaultdict(lambda: deque(maxlen=8))

    CYAN = 0x00D8FF
    EMERALD = 0x00E676
    GOLD = 0xFFC107
    RED = 0xFF5252

    @bot.event
    async def on_ready() -> None:
        log("log_ready", tag=str(bot.user), guilds=len(bot.guilds))

    @bot.event
    async def on_member_join(member: discord.Member) -> None:
        ch = member.guild.system_channel
        glang = get_guild_lang(member.guild.id)
        if ch and ch.permissions_for(member.guild.me).send_messages:
            embed = discord.Embed(
                title="👋 " + member.guild.name,
                description=t("dc_welcome", lang_override=glang, user=member.mention, server=member.guild.name),
                color=CYAN,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=t("dc_embed_footer", lang_override=glang))
            await ch.send(embed=embed)
        log("log_member_join", user=str(member), guild=member.guild.name)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        gid = message.guild.id
        uid = message.author.id
        glang = get_guild_lang(gid)
        now = time.time()

        # 1. Word filter check
        lower = (message.content or "").lower()
        with get_conn() as conn:
            words = [r["word"] for r in conn.execute("SELECT word FROM bad_words WHERE guild_id = ? OR guild_id = 0", (gid,)).fetchall()]
            if not message.content.startswith(prefix) and any(w in lower for w in words):
                try:
                    await message.delete()
                except Exception:
                    pass
                conn.execute(
                    "INSERT INTO mod_logs(guild_id, user_id, action, reason, created_at) VALUES(?, ?, 'WORD_FILTER', ?, ?)",
                    (gid, uid, message.content[:80], int(now)),
                )
                await message.channel.send(t("dc_filtered", lang_override=glang, user=message.author.mention), delete_after=5)
                log("log_filtered", user=str(message.author), guild=message.guild.name)
                return

        # 2. Flood / anti-spam detection (6 msgs in 4 sec)
        dq = msg_history[(gid, uid)]
        dq.append(now)
        if len(dq) >= 6 and (now - dq[0]) <= 4.0:
            dq.clear()
            await message.channel.send(t("dc_spam_warn", lang_override=glang, user=message.author.mention), delete_after=6)
            log("log_spam", user=str(message.author), guild=message.guild.name)

        # 3. Award XP
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_xp(guild_id, user_id, xp, warns) VALUES(?, ?, 10, 0)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + 10
                """,
                (gid, uid),
            )

        await bot.process_commands(message)

    @bot.command(name="help")
    async def cmd_help(ctx: commands.Context) -> None:
        glang = get_guild_lang(ctx.guild.id)
        embed = discord.Embed(
            title="🛡️ Discord Guardian Pro",
            description=t("dc_help", lang_override=glang, prefix=prefix),
            color=CYAN,
        )
        embed.add_field(name="🌐 Language", value=f"`{prefix}lang <code>` (e.g. ru, en, tg, uz)", inline=False)
        embed.set_footer(text=t("dc_embed_footer", lang_override=glang))
        await ctx.send(embed=embed)

    @bot.command(name="ping")
    async def cmd_ping(ctx: commands.Context) -> None:
        glang = get_guild_lang(ctx.guild.id)
        ms = round(bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=t("dc_pong", lang_override=glang, ms=ms),
            color=EMERALD if ms < 150 else GOLD,
        )
        embed.set_footer(text=t("dc_embed_footer", lang_override=glang))
        await ctx.send(embed=embed)

    @bot.command(name="lang", aliases=["language"])
    @commands.has_permissions(administrator=True)
    async def cmd_lang(ctx: commands.Context, code: str | None = None) -> None:
        if not code:
            glang = get_guild_lang(ctx.guild.id)
            await ctx.send(t("dc_lang_usage", lang_override=glang, prefix=prefix))
            return
        saved = set_guild_lang(ctx.guild.id, code)
        await ctx.send(t("dc_guild_lang_set", lang_override=saved, lang=saved.upper()))

    @bot.command(name="stats")
    async def cmd_stats(ctx: commands.Context, member: discord.Member | None = None) -> None:
        glang = get_guild_lang(ctx.guild.id)
        target = member or ctx.author
        with get_conn() as conn:
            row = conn.execute(
                "SELECT xp, warns FROM user_xp WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, target.id),
            ).fetchone()
        xp = row["xp"] if row else 0
        warns = row["warns"] if row else 0
        lvl = xp // 100 + 1

        embed = discord.Embed(
            title=f"📊 {target.display_name}",
            color=CYAN,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=str(lvl), inline=True)
        embed.add_field(name="XP", value=str(xp), inline=True)
        embed.add_field(name="Warns", value=str(warns), inline=True)
        embed.set_footer(text=t("dc_embed_footer", lang_override=glang))
        await ctx.send(embed=embed)

    @bot.command(name="top")
    async def cmd_top(ctx: commands.Context) -> None:
        glang = get_guild_lang(ctx.guild.id)
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT user_id, xp FROM user_xp WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
                (ctx.guild.id,),
            ).fetchall()

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for idx, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["user_id"])
            name = member.display_name if member else str(r["user_id"])
            prefix_badge = medals[idx - 1] if idx <= 3 else f"`#{idx:02d}`"
            lines.append(f"{prefix_badge} **{name}** — `{r['xp']} XP`")

        embed = discord.Embed(
            title="🏆 " + t("dc_top_title", lang_override=glang),
            description="\n".join(lines) if lines else "No ranked members yet.",
            color=GOLD,
        )
        embed.set_footer(text=t("dc_embed_footer", lang_override=glang))
        await ctx.send(embed=embed)

    @bot.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def cmd_warn(ctx: commands.Context, member: discord.Member, *, reason: str = "-") -> None:
        glang = get_guild_lang(ctx.guild.id)
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_xp(guild_id, user_id, xp, warns) VALUES(?, ?, 0, 1)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET warns = warns + 1
                """,
                (ctx.guild.id, member.id),
            )
            conn.execute(
                "INSERT INTO mod_logs(guild_id, user_id, action, reason, created_at) VALUES(?, ?, 'WARN', ?, ?)",
                (ctx.guild.id, member.id, reason[:120], int(time.time())),
            )
        embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=t("dc_warned", lang_override=glang, user=member.mention, reason=reason),
            color=RED,
        )
        embed.set_footer(text=t("dc_embed_footer", lang_override=glang))
        await ctx.send(embed=embed)
        log("log_warned", user=str(member), reason=reason)

    @bot.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def cmd_clear(ctx: commands.Context, count: int = 10) -> None:
        glang = get_guild_lang(ctx.guild.id)
        n = max(1, min(count, 100))
        deleted = await ctx.channel.purge(limit=n + 1)
        await ctx.send(t("dc_cleared", lang_override=glang, n=max(0, len(deleted) - 1)), delete_after=4)
        log("log_cleared", n=max(0, len(deleted) - 1), channel=ctx.channel.name)

    @bot.command(name="addword")
    @commands.has_permissions(manage_messages=True)
    async def cmd_addword(ctx: commands.Context, word: str) -> None:
        glang = get_guild_lang(ctx.guild.id)
        w = word.strip().lower()
        if w:
            add_bad_word(ctx.guild.id, w)
            await ctx.send(t("dc_word_added", lang_override=glang, word=w))

    @bot.command(name="ticket")
    async def cmd_ticket(ctx: commands.Context, *, subject: str = "Support") -> None:
        glang = get_guild_lang(ctx.guild.id)
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        ch = await ctx.guild.create_text_channel(f"ticket-{ctx.author.name[:16]}", overwrites=overwrites)
        embed = discord.Embed(
            title="🎫 Ticket Opened",
            description=t("dc_ticket_opened", lang_override=glang, user=ctx.author.mention, subject=subject),
            color=EMERALD,
        )
        embed.set_footer(text=t("dc_embed_footer", lang_override=glang))
        await ch.send(embed=embed)
        await ctx.send(t("dc_ticket_created", lang_override=glang, channel=ch.mention))
        log("log_ticket", user=str(ctx.author), subject=subject)

    log("log_boot")
    bot.run(token)


def main() -> int:
    init_db()
    web_thread = threading.Thread(target=start_web_studio, daemon=True)
    web_thread.start()

    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        log("err_missing_token")
        print(f"[Discord Guardian Pro] Token not configured. Running Web Studio on port {WEB_PORT} (http://127.0.0.1:{WEB_PORT})", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0
    else:
        run_discord_bot(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
