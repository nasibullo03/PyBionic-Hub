# ⚡ PyBionic Runner — 24/7 Python 3.14 on Android

[![Release](https://img.shields.io/badge/Release-v2.1.54-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg?style=for-the-badge)](LICENSE)

---

### 🌐 Select Language / Выберите язык
**🇬🇧 English** | [🇷🇺 Русский](docs/i18n/README_ru.md) | [🇹🇯 Тоҷикӣ](docs/i18n/README_tg.md) | [🇺🇿 Oʻzbekcha](docs/i18n/README_uz.md) | [🇹🇷 Türkçe](docs/i18n/README_tr.md) | [🇮🇷 فارسی](docs/i18n/README_fa.md) | [🇸🇦 العربية](docs/i18n/README_ar.md) | [🇰🇿 Қазақша](docs/i18n/README_kk.md)

[🇰🇬 Кыргызча](docs/i18n/README_ky.md) | [🇺🇦 Українська](docs/i18n/README_uk.md) | [🇦🇿 Azərbaycan](docs/i18n/README_az.md) | [🇩🇪 Deutsch](docs/i18n/README_de.md) | [🇫🇷 Français](docs/i18n/README_fr.md) | [🇪🇸 Español](docs/i18n/README_es.md) | [🇵🇹 Português](docs/i18n/README_pt.md) | [🇮🇹 Italiano](docs/i18n/README_it.md)

[🇵🇱 Polski](docs/i18n/README_pl.md) | [🇮🇳 हिन्दी](docs/i18n/README_hi.md) | [🇨🇳 简体中文](docs/i18n/README_zh.md) | [🇯🇵 日本語](docs/i18n/README_ja.md) | [🇰🇷 한국어](docs/i18n/README_ko.md) | [🇮🇩 Bahasa Indonesia](docs/i18n/README_id.md) | [🇻🇳 Tiếng Việt](docs/i18n/README_vi.md) | [🇹🇭 ไทย](docs/i18n/README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_DOWNLOAD_PYBIONIC_APK-v2.1.43-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>


---

## 📖 Overview

**PyBionic Runner** is an autonomous high-performance execution runtime for Android that brings native **Python 3.14 (aarch64 Bionic libc)** to your smartphone. It turns any spare or daily Android device into a dedicated, silent, energy-efficient 24/7 server for Telegram bots, web APIs, Discord bots, AI assistants, and background automations.

Unlike heavy chroot or Linux emulators (Termux, PRoot, UserLAnd), PyBionic is compiled directly against Android's native **Bionic libc**. It launches instantly, consumes under **45 MB RAM**, prevents background task kills via native **WakeLock & Doze exemptions**, and offers both a modern **Jetpack Compose UI** and a browser-based **Web Dashboard** accessible over local Wi-Fi.

---

## 🌟 Key Features

- 🐍 **Native Python 3.14.10 Runtime:** Precompiled for ARM64 Bionic libc with full `asyncio`, `multiprocessing`, `ssl`, and SQLite support.
- 🔋 **24/7 Uninterrupted Hosting:** Industrial-grade foreground service with CPU WakeLock, battery temperature watchdog, and Doze Mode bypass.
- 🛡️ **Intelligent Watchdog & Crash Recovery:** Configurable restart backoff policies (`Always`, `On Crash`, `Never`), auto-restart limits, and process-tree cleanup.
- 🌐 **Remote Web Dashboard (PC Control):** Secure browser interface with PIN authentication to manage bots, view real-time logs, and edit code from your computer.
- 📦 **BotHub Ecosystem:** 26+ built-in ready-to-run bot templates (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Web Scrapers, AI assistants).
- 🗄️ **Integrated SQLite Browser:** Monolithic synchronous data viewer to inspect bot databases directly without exporting `.db` files.
- 🔍 **Real-Time Telemetry:** Live cellular/Wi-Fi speed graphs, per-bot bandwidth breakdown, RAM/CPU metrics, and battery thermals.
- 🌍 **24 Languages Supported:** Fully localized interface in 24 languages with RTL support.
- 🔒 **Security & Isolation:** Secret vault for `.env` credentials, memory-safe log sanitization, and hardware biometric app lock.

---

## 🚀 Quick Start

1. **Download APK:** Get the latest release from [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest).
2. **Install:** Install `PyBionic-Runner-v2.1.43-arm64.apk` on your Android device (Android 8.0+ / arm64-v8a).
3. **Launch & Permissions:** Allow Notification permission and accept the prompt to **Disable Battery Optimizations** for uninterrupted 24/7 background operation.
4. **Run a Bot:**
   - Tap **BotHub** at the bottom.
   - Choose a bot (e.g., `Simple Telebot` or `FastAPI Web Server`).
   - Tap **Install Bot** ➔ Enter your Bot Token or Settings ➔ Tap **▶ Run**.
5. **Control from PC:**
   - Go to **Settings** ➔ Tap **PC Web Dashboard**.
   - Open the displayed IP/URL in your computer browser and enter the one-time PIN.

---

## 🤖 Instructions for AI Agents & LLMs

PyBionic is fully optimized for programmatic inspection and autonomous bot deployment by AI assistants.

- **Full AI Reference Guide:** See [AI_SYSTEM_REFERENCE.md](AI_SYSTEM_REFERENCE.md) for environment variables, path structures, and API specs.
- **Bot Web Port Declaration:**
  Any Python bot running a local web server (FastAPI, Flask, aiohttp) can declare its web interface automatically by printing:
  ```python
  print("[PYBIONIC_WEB:8080]")
  ```
  PyBionic detects this signal in stdout and automatically enables the **🌐 Web UI** button on the bot card in the Android app.
- **Process Management:**
  PyBionic manages bot processes as process trees. Child processes spawned via `subprocess` or `multiprocessing` are tracked and cleanly terminated on stop.

---

## 📄 License & Credits

- Copyright (c) 2026 Nasibullo Khalilov. All Rights Reserved. Proprietary software.
- Developed by **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
