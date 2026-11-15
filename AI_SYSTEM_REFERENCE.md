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
├── config.json         # Project metadata, restart policies & hardware limits
├── main.py             # Entrypoint script (configurable via entryFile)
├── requirements.txt    # Declared pip dependencies
└── [custom_files]      # Bot modules, sqlite databases, logs
```

> **Security Note:** Secrets and API tokens are **never** stored in plain-text `.env` files. They are encrypted in **Android Keystore** and securely injected into the child process environment (`os.environ`) at launch.

### `config.json` Specification:
```json
{
  "id": "my_telegram_bot",
  "name": "My Telegram Bot",
  "entryFile": "main.py",
  "restartPolicy": "ALWAYS",
  "maxMemoryMb": 256,
  "stopTimeoutSec": 3,
  "healthCheckPort": 8080,
  "dailyScheduleHHmm": "09:00",
  "autoRestart": true,
  "envKeys": ["BOT_TOKEN", "ALLOWED_USER_IDS"]
}
```

---

## 3. Web UI Port Protocol (`PYBIONIC_WEB`)

If your Python code runs a local web server (FastAPI, Flask, aiohttp, Tornado, Streamlit, etc.), your bot can automatically register its web panel in the Android UI by emitting a single stdout line:

```python
import os

PORT = int(os.environ.get("WEB_PORT") or os.environ.get("PORT") or 8080)

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
- **`ON_FAILURE`:** Restarts only if exit code != 0.
- **`NEVER`:** Does not restart once terminated.

### Process Termination:
PyBionic uses `ProcessTreeKiller` to ensure clean shutdowns:
1. Sends `SIGTERM` to the parent process and all child PIDs.
2. Waits for graceful shutdown (configurable: 1s, 3s, 5s, or 10s; default **3.0 seconds**).
3. Sends `SIGKILL` (`kill -9`) to guarantee no orphan worker processes remain in memory.

---

## 5. Python Libraries & Dependency Management

- **Core Bootstrap:** Provides native Python 3.14.10 linked against Android Bionic libc with `pip` pre-installed.
- **Dependencies via `requirements.txt`:** All third-party libraries (e.g. `aiogram`, `pyTelegramBotAPI`, `fastapi`, `requests`, `uvicorn`, `beautifulsoup4`) are declared in `requirements.txt` and installed into the bot's isolated environment or system site-packages.
- **Binary Extension Advisory:** Avoid packages requiring a full C/C++ compiler or glibc-specific headers (such as `lxml`); prefer pure-Python packages or standard library modules (`html.parser`, `xml.etree.ElementTree`).

---

## 6. How AI Should Generate Code for PyBionic

When an AI writes Python code for PyBionic Runner:
1. **Always read configuration from environment variables:**
   ```python
   import os
   TOKEN = os.getenv("BOT_TOKEN")
   PORT = int(os.getenv("WEB_PORT") or os.getenv("PORT", 8080))
   ```
2. **Bind servers to `0.0.0.0` or `127.0.0.1` based on config:**
   ```python
   import uvicorn
   # If LAN access is needed:
   uvicorn.run("main:app", host="0.0.0.0", port=PORT)
   ```
3. **Use SQLite for persistent data:**
   Store database files in `PROJECT_DATA_DIR` or the project root:
   ```python
   import os, sqlite3
   from pathlib import Path
   data_dir = Path(os.getenv("PROJECT_DATA_DIR", "."))
   conn = sqlite3.connect(data_dir / "bot_data.db")
   ```
