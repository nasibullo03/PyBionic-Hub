# 🇩🇪 ⚡ PyBionic Runner — 24/7 Python 3.14 Laufzeitumgebung auf Android

[![Release](https://img.shields.io/badge/Release-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | **🇩🇪 Deutsch** | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APK_HERUNTERLADEN-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Über das Projekt

**PyBionic Runner** ist eine autonome Hochleistungs-Ausführungsumgebung für Android, die natives **Python 3.14 (aarch64 Bionic libc)** direkt auf Ihrem Smartphone ausführt. Es verwandelt jedes Android-Gerät in einen leisen, energieeffizienten 24/7-Mikroserver für Telegram-Bots, FastAPI/Flask-Web-Apps, Discord-Bots und Hintergrundautomatisierungen.

Im Gegensatz zu schweren Linux-Emulatoren (Termux, PRoot, UserLAnd) ist PyBionic direkt gegen Androids systemeigene **Bionic libc** kompiliert. Es startet blitzschnell, verbraucht weniger als **45 MB RAM**, verhindert Systemabschaltungen durch **WakeLock & Doze-Mode-Ausnahme** und lässt sich über ein **Web Dashboard** bequem vom PC über WLAN steuern.

---

## 🌟 Hauptmerkmale

- 🐍 **Natives Python 3.14.10:** Für ARM64 Bionic libc kompiliert mit voller Unterstützung für `asyncio`, `multiprocessing`, `ssl` und SQLite3.
- 🔋 **24/7 Unterbrechungsfreies Hosting:** Foreground Service mit CPU-WakeLock, Akkutemperatur-Überwachung und Android-Doze-Bypass.
- 🛡️ **Intelligenter Watchdog:** Automatische Wiederherstellung bei Abstürzen oder Systemneustarts mit anpassbaren Richtlinien.
- 🌐 **Web Dashboard (PC-Steuerung):** Sichere Browser-Oberfläche mit PIN-Authentifizierung zur Verwaltung von Bots und Live-Logs über WLAN.
- 📦 **BotHub-Katalog:** Über 26 sofort einsatzbereite Bot-Vorlagen (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Scraper und KI-Bots).
- 🗄️ **Integrierter SQLite-Browser:** Direkte Datenbankinspektion in der App mit Schutz vor Arbeitsspeicherüberlastung (OOM).
- 🔍 **Echtzeit-Telemetrie:** Netzwerk- und WLAN-Geschwindigkeitsdiagramme, Bandbreite pro Bot, RAM- und CPU-Statistiken.
- 🌍 **24 Sprachen unterstützt:** Vollständige Lokalisierung inklusive Unterstützung für RTL-Sprachen.
- 🔒 **Sicherheit & Isolation:** Sicherer Tresor für `.env`-Schlüssel, Maskierung sensibler Daten in Logs und biometrische App-Sperre.

---

## 🚀 Schnellstart

1. **APK herunterladen:** Laden Sie die neueste Version aus den [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest) herunter.
2. **Installieren:** Installieren Sie `PyBionic-Runner-v2.2.0-arm64.apk` auf Ihrem Android 8.0+ (ARM64) Gerät.
3. **Berechtigungen erteilen:** Benachrichtigungen erlauben und die Akku-Optimierung deaktivieren.
4. **Ersten Bot starten:** Wechseln Sie zu **BotHub**, wählen Sie eine Vorlage, geben Sie den Token ein und tippen Sie auf **▶ Starten**.
5. **Vom PC steuern:** Öffnen Sie **Einstellungen** ➔ **Web Dashboard**, rufen Sie die IP im Browser auf und geben Sie die PIN ein.

---

## 🤖 Anweisungen für KI-Agenten (LLM Reference)

PyBionic ist für die autonome Codegenerierung durch KI-Assistenten optimiert. Die vollständige Spezifikation finden Sie in [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Lizenz & Autor

- Lizenziert unter der **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Entwickelt von **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
