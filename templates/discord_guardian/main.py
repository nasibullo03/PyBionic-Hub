"""Discord Guardian Pro — Anti-Spam, Word Filter, Moderation, Tickets & XP Leaderboard (SQLite).
Features Rich Cyberpunk Embeds, guild language preferences, full 24-language support, and Cyberpunk Web Studio.
"""

from __future__ import annotations

import pybionic_web as web
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

def render_studio(handler: Any) -> None:
    lang = web.resolve_lang(handler)
    T = web.translator(lang)
    css = ("<style>.dg-add{display:flex;gap:8px;flex-wrap:wrap}.dg-add .pb-input-wrap{flex:1;min-width:200px}"
           ".dg-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;min-height:36px}"
           ".dg-chip{display:inline-flex;align-items:center;gap:6px;padding:6px 6px 6px 12px;border-radius:99px;background:#ef444418;border:1px solid #ef444444;font-size:13.5px;font-weight:600;animation:dgIn .3s both}"
           "@keyframes dgIn{from{opacity:0;transform:scale(.9)}to{opacity:1;transform:none}}"
           ".dg-chip button{width:22px;height:22px;border-radius:50%;border:0;background:transparent;color:var(--muted);cursor:pointer;display:grid;place-items:center;font-size:15px;line-height:1}"
           ".dg-chip button:hover{background:#ef444433;color:#ef4444}"
           ".dg-rank{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;font-weight:800;font-size:13px;background:var(--surface2)}"
           ".dg-r1{background:linear-gradient(135deg,#fbbf24,#f59e0b);color:#3b2600}.dg-r2{background:linear-gradient(135deg,#e5e7eb,#9ca3af);color:#1f2937}.dg-r3{background:linear-gradient(135deg,#fdba74,#c2410c);color:#fff}"
           ".dg-xp{font-weight:800;color:#f59e0b}.dg-act{font-size:11.5px;font-weight:700;padding:4px 9px;border-radius:99px;background:var(--surface2);white-space:nowrap}"
           ".dg-WARN{background:#f59e0b22;color:#f59e0b}.dg-WORD_FILTER{background:#ef444422;color:#ef4444}.dg-SPAM{background:#a855f722;color:#a855f7}"
           ".dg-id{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;color:var(--muted)}</style>")
    words = web.card(T("w_card_words"),
        '<form class="dg-add" id="f">' + web.input_("word", T("w_word_ph"), icon_name="shield", autocomplete="off", maxlength="64")
        + web.button(T("add"), "addbtn", type="submit", icon_name="plus") + "</form>"
        + '<div class="dg-chips" id="words"></div>' + web.note(T("w_words_note"), "info"), icon_name="shield")
    how = web.card(T("w_card_how"), "".join(web.note(T(k), "info", ic) for k, ic in (("w_h_spam", "zap"), ("w_h_filter", "shield"), ("w_h_xp", "chart"))), icon_name="list")
    board = web.card(T("w_card_board"), web.table(["#", T("w_user"), "XP", T("w_warns")], [], T("w_no_board"), id="board"), icon_name="chart")
    logs = web.card(T("w_card_logs"), web.table([T("time"), T("w_user"), T("action"), T("reason")], [], T("w_no_logs"), id="logs"), icon_name="clock",
                    aside=web.button(T("refresh"), "rf", kind="ghost", cls="pb-btn-sm", icon_name="refresh"))
    st = web.stats([(T("w_st_words"), "0", "s1", "shield"), (T("w_st_logs"), "0", "s2", "list"), (T("w_st_users"), "0", "s3", "users"), (T("w_st_warns"), "0", "s4", "alert")])
    hero = web.hero(T("w_title"), T("w_hero"), "🛡️", chips=[T("w_chip_spam"), T("w_chip_filter"), "XP", "Discord"])
    web.send_page(handler, lang, title=T("w_title"), emoji="🛡️", brand="#5865f2", port=WEB_PORT, hero_html=hero,
                  body=css + st + web.grid(words, how, min_width=330) + web.grid(board, logs, min_width=330), script=GUARDIAN_JS)


GUARDIAN_JS = r"""
const $=s=>document.querySelector(s);
const empty=(id,key,cols)=>{$(id+' tbody').innerHTML=`<tr class="pb-empty-row"><td colspan="${cols}">${pb.esc(pb.t(key))}</td></tr>`};
const ACT={WARN:'w_a_warn',WORD_FILTER:'w_a_filter',SPAM:'w_a_spam',MUTE:'w_a_mute',KICK:'w_a_kick',BAN:'w_a_ban'};
async function status(){const d=await pb.json('/api/status').catch(()=>null);if(d&&d.stats){const s=d.stats;pb.count($('#s1'),s.bad_words||0);pb.count($('#s2'),s.mod_logs||0);pb.count($('#s3'),s.ranked_users||0);pb.count($('#s4'),s.total_warns||0)}}
function renderWords(ws){const c=$('#words');if(!ws||!ws.length){c.innerHTML=`<span class="pb-hint">${pb.esc(pb.t('w_no_words'))}</span>`;return}
  c.innerHTML=ws.map(w=>`<span class="dg-chip">${pb.esc(w)}<button type="button" data-w="${pb.esc(w)}" aria-label="${pb.esc(pb.t('delete'))}">×</button></span>`).join('');
  c.querySelectorAll('button').forEach(b=>b.onclick=async()=>{const d=await pb.post('/api/delete_word?word='+encodeURIComponent(b.dataset.w),{}).catch(()=>null);
    if(d){renderWords(d.words);status();pb.toast(pb.t('deleted'))}else pb.toast(pb.t('error_conn'),true)})}
async function load(){
  pb.json('/api/words').then(renderWords).catch(()=>{});
  pb.json('/api/leaderboard').then(top=>{if(!top||!top.length)return empty('#board','w_no_board',4);
    $('#board tbody').innerHTML=top.map((r,i)=>`<tr><td><span class="dg-rank ${i<3?'dg-r'+(i+1):''}">${i+1}</span></td><td><span class="dg-id">${pb.esc(String(r.user_id))}</span></td>
      <td><span class="dg-xp">${(+r.xp).toLocaleString(PB_LANG)}</span></td><td>${+r.warns>0?'⚠️ '+(+r.warns):'0'}</td></tr>`).join('')}).catch(()=>{});
  pb.json('/api/logs').then(ls=>{if(!ls||!ls.length)return empty('#logs','w_no_logs',4);
    $('#logs tbody').innerHTML=ls.slice(0,30).map(l=>{const a=String(l.action||'');const when=new Date(l.created_at*1000).toLocaleString(PB_LANG,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
      return `<tr><td class="dg-id">${when}</td><td><span class="dg-id">${pb.esc(String(l.user_id))}</span></td><td><span class="dg-act dg-${pb.esc(a)}">${pb.esc(ACT[a]?pb.t(ACT[a]):a)}</span></td><td>${pb.esc(l.reason||'—')}</td></tr>`}).join('')}).catch(()=>{});
  status()}
$('#f').addEventListener('submit',async e=>{e.preventDefault();const w=$('#word').value.trim();if(!w)return;const b=$('#addbtn');pb.busy(b,true);
  try{const d=await pb.post('/api/add_word?word='+encodeURIComponent(w),{});renderWords(d.words);$('#word').value='';status();pb.toast(pb.t('w_word_added'))}
  catch(err){pb.toast(pb.t('error_conn'),true)}finally{pb.busy(b,false)}});
$('#rf').onclick=load;load();
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
            render_studio(self)
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
