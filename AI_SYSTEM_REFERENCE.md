# 🤖 PyBionic Runner: Architecture & Technical Reference for AI Agents

> **Audience:** Autonomous AI Agents, LLMs, and Developers building bots for PyBionic Runner.  
> **Platform:** Android 8.0+ (API 26–36), Architecture: `arm64-v8a` (aarch64).  
> **Python Engine:** Native Python 3.14.10 linked against Android Bionic libc.

---

## 1. System Architecture

```
+-------------------------------------------------------------------+
|                        PyBionic Runner (Android)                  |
|                                                                   |
|  +--------------------+  +------------------+  +---------------+  |
|  | Jetpack Compose UI |  | Foreground 24/7  |  | Web Dashboard |  |
|  | (Projects, BotHub) |  | Service Engine   |  | (PC Browser)  |  |
|  +--------------------+  +------------------+  +---------------+  |
|            |                      |                    |          |
|            +----------------------+--------------------+          |
|                                   |                               |
|                     [ ProcessTreeKiller & Watchdog ]              |
|                                   |                               |
|        +--------------------------+--------------------------+    |
|        |                          |                          |    |
|  [ Bot Project 1 ]         [ Bot Project 2 ]          [ Project N ]|
|  (Python 3.14 Process)     (Python 3.14 Process)      (Background)|
+-------------------------------------------------------------------+
```

### Key Differences from Linux / Termux:
1. **Bionic libc vs glibc/musl:**
   - Python is built directly against Android's C library (`/system/lib64/libc.so`).
   - No `chroot`, no `proot` translation overhead. System calls execute with zero virtualization latency.
2. **Filesystem Isolation:**
   - Application data resides in Android internal storage:
     `/data/user/0/dev.pybionic.runner/files/`
   - Native binaries and libraries:
     `/data/user/0/dev.pybionic.runner/files/usr/bin/python3`
     `/data/user/0/dev.pybionic.runner/files/usr/lib/python3.14/`
3. **Execution Permissions (W^X on Android 10+):**
   - Executable scripts and pip wheels must be placed in internal app storage (`context.filesDir`).
   - External SDCard or shared storage (`/sdcard`) does NOT have execution permissions (`noexec`).

---

## 2. Bot Project Structure

Every bot project is stored in its own isolated directory:
```
/data/user/0/dev.pybionic.runner/files/projects/<project_id>/
├── config.json         # Project metadata & run settings
├── main.py             # Entrypoint script
├── requirements.txt    # Declared dependencies
├── .env                # Project environment variables
└── [custom_files]      # Bot modules, sqlite databases, logs
```

### `config.json` Specification:
```json
{
  "id": "my_telegram_bot",
  "name": "My Telegram Bot",
  "entryPoint": "main.py",
  "watchdogPolicy": "ALWAYS",
  "webPort": 8080,
  "autoStartOnBoot": true,
  "envVars": {
    "BOT_TOKEN": "YOUR_TOKEN_HERE"
  }
}
```

---

## 3. Web UI Port Protocol (`PYBIONIC_WEB`)

If your Python code runs a local web server (FastAPI, Flask, aiohttp, Tornado, Streamlit, etc.), your bot can automatically register its web panel in the Android UI by emitting a single stdout line:

```python
import os

PORT = int(os.environ.get("PORT", 8080))

# Print signal for PyBionic Android Runner:
print(f"[PYBIONIC_WEB:{PORT}]", flush=True)
```

### Result in Android UI:
- PyBionic detects `[PYBIONIC_WEB:<PORT>]` in stdout.
- A **«🌐 Web UI»** button immediately appears on the bot's card.
- Tapping it opens the local web page in the phone's browser (`http://127.0.0.1:PORT` or LAN IP).

---

## 4. 24/7 Hosting & Watchdog Lifecycle

### Restart Policies:
- **`ALWAYS` (Default):** The bot is automatically restarted 24/7 if it exits, crashes, or after phone reboot. Uses exponential backoff (2s ➔ 4s ➔ 8s ➔ ... up to 60s).
- **`ON_CRASH`:** Restarts only if exit code != 0.
- **`NEVER`:** Does not restart once terminated.

### Process Termination:
PyBionic uses `ProcessTreeKiller` to ensure clean shutdowns:
1. Sends `SIGTERM` to the parent process and all child PIDs.
2. Waits 2.5 seconds for graceful shutdown.
3. Sends `SIGKILL` (`kill -9`) to guarantee no orphan worker processes remain in memory.

---

## 5. Pre-installed & Supported Python Libraries

- **Asyncio / Networking:** `aiogram==3.*`, `pyTelegramBotAPI (telebot)`, `aiohttp`, `httpx`, `requests`, `urllib3`.
- **Web Servers:** `fastapi`, `uvicorn`, `flask`.
- **Data & Parsing:** `sqlite3`, `beautifulsoup4`, `lxml`, `json`, `csv`.
- **System & Utils:** `psutil`, `schedule`, `dotenv`.

---

## 6. How AI Should Generate Code for PyBionic

When an AI writes Python code for PyBionic Runner:
1. **Always read configuration from environment variables:**
   ```python
   import os
   TOKEN = os.getenv("BOT_TOKEN")
   PORT = int(os.getenv("PORT", 8080))
   ```
2. **Bind servers to `0.0.0.0` or `127.0.0.1` based on config:**
   ```python
   import uvicorn
   # If LAN access is needed:
   uvicorn.run("main:app", host="0.0.0.0", port=PORT)
   ```
3. **Use SQLite for persistent data:**
   SQLite requires zero setup and runs at native speed under Bionic libc:
   ```python
   import sqlite3
   conn = sqlite3.connect("bot_data.db")
   ```
