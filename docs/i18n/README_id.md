# 🇮🇩 ⚡ PyBionic Runner — Lingkungan Eksekusi Python 3.14 Mandiri di Android 24/7

[![Release](https://img.shields.io/badge/Release-v1.0.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | **🇮🇩 Bahasa Indonesia** | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_UNDUH_PYBIONIC_APK-v1.0.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Tentang Proyek

**PyBionic Runner** adalah runtime eksekusi mandiri berkinerja tinggi untuk Android yang menjalankan **Python 3.14 native (aarch64 Bionic libc)** langsung di smartphone Anda. Aplikasi ini mengubah ponsel apa pun menjadi server mikro 24/7 yang senyap, hemat daya, dan stabil untuk bot Telegram, aplikasi web FastAPI/Flask, bot Discord, dan otomatisasi latar belakang.

Tidak seperti emulator Linux yang berat (Termux, PRoot, UserLAnd), PyBionic dikompilasi langsung terhadap pustaka sistem Android — **Bionic libc**. Aplikasi ini terbuka instan, menggunakan kurang dari **45 MB RAM**, terlindung dari penghentian sistem berkat **WakeLock & pengecualian Doze Mode**, serta dapat dikontrol dari komputer melalui **Web Dashboard** lokal via Wi-Fi.

---

## 🌟 Fitur Utama

- 🐍 **Python 3.14.10 Native:** Dikompilasi untuk ARM64 Bionic libc dengan dukungan penuh `asyncio`, `multiprocessing`, `ssl`, dan SQLite3.
- 🔋 **Hosting Non-Stop 24/7:** Layanan latar depan (Foreground Service) dengan CPU WakeLock, pemantau suhu baterai, dan pencegah tidur Android.
- 🛡️ **Watchdog Pintar:** Pemulihan otomatis saat bot crash atau ponsel restart dengan kebijakan yang dapat disesuaikan.
- 🌐 **Web Dashboard (Kontrol PC):** Kelola bot, pantau log langsung, dan edit kode dari browser komputer melalui Wi-Fi dengan PIN aman.
- 📦 **Katalog BotHub:** Lebih dari 26 template bot siap pakai (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Scraper, dan bot AI).
- 🗄️ **Penjelajah SQLite Bawaan:** Pemeriksaan database langsung di dalam aplikasi dengan perlindungan kehabisan memori (Anti-OOM).
- 🔍 **Telemetri Real-Time:** Grafik kecepatan seluler dan Wi-Fi, statistik penggunaan data per bot, serta metrik RAM dan CPU.
- 🌍 **Mendukung 24 Bahasa:** Antarmuka multibahasa lengkap termasuk tata letak dari kanan ke kiri (RTL).
- 🔒 **Keamanan & Isolasi:** Brankas kredensial `.env`, penyamaran token sensitif pada log, dan kunci sidik jari biometrik.

---

## 🚀 Panduan Cepat

1. **Unduh APK:** Dapatkan versi terbaru dari [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest).
2. **Pasang:** Pasang `PyBionic-Runner-v1.0.0-arm64.apk` pada perangkat Android 8.0+ (ARM64) Anda.
3. **Izin:** Berikan izin notifikasi dan nonaktifkan pengoptimalan baterai agar bot berjalan 24/7 tanpa henti.
4. **Jalankan Bot Pertama:** Buka tab **BotHub**, pilih template, masukkan token Anda, lalu tekan **▶ Jalankan**.
5. **Kontrol dari Komputer:** Buka **Pengaturan** ➔ **Web Dashboard**, akses IP di browser komputer Anda, dan masukkan PIN.

---

## 🤖 Spesifikasi untuk Agen AI (LLM Reference)

PyBionic dioptimalkan untuk pembuatan dan eksekusi kode otomatis oleh asisten AI. Panduan teknis lengkap: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Lisensi & Pengembang

- Didistribusikan di bawah lisensi terbuka **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Pengembang: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
