# 🇮🇹 ⚡ PyBionic Runner — Esecuzione autonoma di Python 3.14 su Android 24/7

[![Release](https://img.shields.io/badge/Release-v1.0.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | **🇮🇹 Italiano**

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_SCARICA_PYBIONIC_APK-v1.0.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Informazioni sul progetto

**PyBionic Runner** è un ambiente di esecuzione autonomo e ad alte prestazioni per Android che esegue **Python 3.14 nativo (aarch64 Bionic libc)** direttamente sul tuo smartphone. Trasforma qualsiasi dispositivo Android in un microserver silenzioso, a basso consumo energetico e attivo 24 ore su 24, 7 giorni su 7 per bot Telegram, API web FastAPI/Flask, bot Discord e automazioni in background.

A differenza dei pesanti emulatori Linux (Termux, PRoot, UserLAnd), PyBionic è compilato direttamente contro la libreria di sistema di Android — **Bionic libc**. Si avvia all'istante, consuma meno di **45 MB di RAM**, previene la sospensione tramite **WakeLock ed esenzione Doze Mode**, e può essere gestito comodamente dal computer tramite una **Web Dashboard** locale via Wi-Fi.

---

## 🌟 Caratteristiche principali

- 🐍 **Python 3.14.10 nativo:** Compilato per ARM64 Bionic libc con supporto completo per `asyncio`, `multiprocessing`, `ssl` e SQLite3.
- 🔋 **Hosting continuo 24/7:** Foreground Service con CPU WakeLock, monitoraggio termico della batteria e protezione da sospensione.
- 🛡️ **Watchdog intelligente:** Riavvio automatico dei bot in caso di arresto anomalo o riavvio del telefono.
- 🌐 **Web Dashboard (Controllo da PC):** Gestione dei bot, log in tempo reale e modifica del codice dal browser via Wi-Fi con PIN.
- 📦 **Catalogo BotHub:** Più di 26 modelli pronti all'uso (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Scraper e bot IA).
- 🗄️ **Visualizzatore SQLite integrato:** Consultazione diretta dei database all'interno dell'app con protezione da memoria insufficiente (OOM).
- 🔍 **Telemetria in tempo reale:** Grafici di velocità di rete e Wi-Fi, consumo di banda per bot, utilizzo di RAM e processore.
- 🌍 **24 lingue supportate:** Localizzazione completa dell'interfaccia con supporto per lingue RTL.
- 🔒 **Sicurezza e isolamento:** Cassaforte per chiavi segrete `.env`, mascheramento dei token nei log e blocco biometrico.

---

## 🚀 Guida rapida

1. **Scarica l'APK:** Scarica l'ultima versione dalla pagina [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest).
2. **Installa:** Installa `PyBionic-Runner-v1.0.0-arm64.apk` sul tuo dispositivo Android 8.0+ (ARM64).
3. **Permessi:** Consenti le notifiche e disattiva le ottimizzazioni della batteria per l'attività 24/7.
4. **Avvia un bot:** Vai alla scheda **BotHub**, scegli un modello, inserisci il tuo token e tocca **▶ Avvia**.
5. **Controllo da PC:** Vai su **Impostazioni** ➔ **Web Dashboard**, apri l'IP nel browser del computer e inserisci il PIN.

---

## 🤖 Istruzioni per agenti IA (LLM Reference)

PyBionic è ottimizzato per la generazione autonoma di codice da parte di assistenti IA. Consulta la guida tecnica: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Licenza e Autore

- Distribuito con licenza **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Sviluppato da **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
