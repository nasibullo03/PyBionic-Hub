# 🇺🇿 ⚡ PyBionic Runner — Android tizimida 24/7 uzluksiz Python 3.14 muhiti

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | **🇺🇿 Oʻzbekcha** | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APK-NI_YUKLAB_OLISH-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Loyiha haqida

**PyBionic Runner** — bu Android uchun yuqori unumdor mustaqil ijro muhiti bo‘lib, to‘liq mahalliy **Python 3.14 (aarch64 Bionic libc)**-ni to‘g‘ridan-to‘g‘ri smartfoningizda ishga tushiradi. Ilova har qanday telefonni Telegram-botlar, FastAPI/Flask veb-ilovalari, Discord-botlar va fon jarayonlari uchun shovqinsiz, tejamkor va 24/7 ishlaydigan shaxsiy mikroserverga aylantiradi.

Og‘ir Linux emulyatorlaridan (Termux, PRoot, UserLAnd) farqli o‘laroq, PyBionic to‘g‘ridan-to‘g‘ri Android-ning tizimli **Bionic libc** kutubxonasi bilan kompilyatsiya qilingan. U bir zumda ochiladi, **45 MB-dan kam operativ xotira (RAM)** iste'mol qiladi, **WakeLock va Doze Mode cheklovlaridan ozod qilish** orqali fonda to‘xtab qolishdan himoyalangan, shuningdek telefon va kompyuter orqali **Web Dashboard** vositasida boshqariladi.

---

## 🌟 Asosiy imkoniyatlar

- 🐍 **Mahalliy Python 3.14.10:** ARM64 Bionic libc uchun yig‘ilgan, `asyncio`, `multiprocessing`, `ssl` va SQLite3 to‘liq qo‘llab-quvvatlanadi.
- 🔋 **24/7 uzluksiz xosting:** Protsessor WakeLock-ni ushlab turuvchi `Foreground Service`, batareya harorati nazorati va Android uyqu rejimidan himoya.
- 🛡️ **Intellektual Watchdog:** Bot ishdan chiqqanda yoki telefon qayta yoqilganda avtomatik qayta ishga tushirish siyosati.
- 🌐 **Web Dashboard (Kompyuterdan boshqarish):** Wi-Fi orqali kompyuter brauzerida botlarni boshqarish, kodni tahrirlash va jonli loglarni ko‘rish (PIN-kod himoyasi bilan).
- 📦 **BotHub katalogi:** 26+ dan ortiq tayyor bot andozalari (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Skraperlar va AI-botlar).
- 🗄️ **O‘rnatilgan SQLite ko‘ruvchi:** Botlar ma'lumotlar bazasini xotira xatolarisiz to‘g‘ridan-to‘g‘ri ilova ichida ko‘rish.
- 🔍 **Jonli telemetriya:** Mobil aloqa va Wi-Fi tezlik grafiklari, har bir botning trafik hisobi, RAM va CPU yuklamasi.
- 🌍 **24 ta til qo‘llab-quvvatlanadi:** To‘liq tarjima va RTL interfeysi.
- 🔒 **Xavfsizlik va izolyatsiya:** `.env` maxfiy kalitlar ombori, loglarda tokenlarni yashirish va biometrik barmoq izi himoyasi.

---

## 🚀 Tezkor boshlash

1. **APK-ni yuklab oling:** Yangi versiyani [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest) sahifasidan yuklab oling.
2. **O‘rnating:** `PyBionic-Runner-v2.1.1-arm64.apk` faylini Android 8.0+ (ARM64) qurilmangizga o‘rnating.
3. **Ruxsatlar:** Bildirishnomalarga ruxsat bering va 24/7 uzluksiz ishlashi uchun batareya cheklovlarini (Doze Mode) o‘chiring.
4. **Birinchi botni ishga tushirish:** **BotHub** bo‘limiga o‘ting, shablonni tanlang (masalan, `Telebot` yoki `FastAPI`), tokenni kiriting va **▶ Ishga tushirish** tugmasini bosing.
5. **Kompyuterdan boshqarish:** **Sozlamalar** ➔ **Web Dashboard** menyusiga kiring, ko‘rsatilgan IP-ni kompyuter brauzerida oching va PIN-kodni kiriting.

---

## 🤖 Sun'iy intellekt uchun ma'lumot (LLM Reference)

PyBionic sun'iy intellekt yordamchilari tomonidan avtonom kod yozish va botlarni boshqarish uchun to‘liq moslashtirilgan. To‘liq qo‘llanma: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Litsenziya va muallif

- **GNU Affero General Public License v3.0 (AAGPL-3.0)** ochiq litsenziyasi ostida tarqatiladi. Muallif va dasturchi: **Nasibullo Xalilov** ([@nasibullo03](https://github.com/nasibullo03)).
