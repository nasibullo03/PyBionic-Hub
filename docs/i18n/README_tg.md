# 🇹🇯 ⚡ PyBionic Runner — Иҷрои мустақили Python 3.14 дар Android 24/7

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | **🇹🇯 Тоҷикӣ** | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_ФАРОБАРДОРИИ_PYBIONIC_APK-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Дар бораи лоиҳа

**PyBionic Runner** муҳити иҷроиши худмухтор ва баландсуръат барои Android мебошад, ки насли нави **Python 3.14 (aarch64 Bionic libc)**-ро мустақиман дар смартфони шумо иҷро мекунад. Барнома ҳар гуна телефони муқаррарӣ ё кӯҳнаро ба микросервери доимии шабонарӯзӣ (24/7), бесадо ва сарфакори барқ барои ботҳои Telegram, веб-барномаҳои FastAPI/Flask, ботҳои Discord ва коркардҳои пасзамина табдил медиҳад.

Бар хилофи эмуляторҳои вазнини Linux (Termux, PRoot, UserLAnd), PyBionic мустақиман бо китобхонаи системавии Android — **Bionic libc** сохта шудааст. Он фавран оғоз меёбад, камтар аз **45 МБ хотираи фаврӣ (RAM)** истифода мебарад, бо **WakeLock ва истисно аз Doze Mode** ҳифз шудааст ва ҳам аз телефон ва ҳам аз компютер тавассути **Web Dashboard** идора мешавад.

---

## 🌟 Имкониятҳои калидӣ

- 🐍 **Python 3.14.10-и маҳаллӣ:** Сохташуда барои ARM64 Bionic libc бо дастгирии `asyncio`, `multiprocessing`, `ssl` ва SQLite3.
- 🔋 **Ҳостинги доимии 24/7:** Хадамоти пасзамина (Foreground Service) бо нигоҳдории WakeLock, назорати ҳарорати батарея ва муҳофизат аз хоби Android.
- 🛡️ **Таймери назоратӣ (Watchdog):** Бозоғозии худкори ботҳо дар сурати хатогӣ ё хомӯш шудани телефон бо танзими қоидаҳои бозоғозӣ.
- 🌐 **Web Dashboard (Идора аз компютер):** Идораи ботҳо, дидани сабти амалҳо (логҳо) ва таҳрири код дар браузери компютер бо Wi-Fi ва рамзи PIN.
- 📦 **Каталоги BotHub:** Зиёда аз 26 қолаби омодаи ботҳо (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Парсерҳо ва ёварони зеҳни сунъӣ).
- 🗄️ **Мурургари дохилии SQLite:** Дидани ҷадвалҳо ва пойгоҳи додаҳо мустақиман дар барнома бо муҳофизат аз камбуди хотира (OOM).
- 🔍 **Телеметрияи зинда:** Графикҳои суръати шабака ва Wi-Fi, ҳисоби трафики ҳар як бот, аптайм, RAM ва CPU.
- 🌍 **24 забони дастгиришаванда:** Локализатсияи комил бо дастгирии хати ростро ба чап (RTL).
- 🔒 **Амният ва ҷудокунӣ:** Анбори махфии калидҳои `.env`, ниқобкунии токенҳо дар логҳо ва қулф бо изи ангушт.

---

## 🚀 Оғози сареъ

1. **APK-ро боргирӣ кунед:** Версияи навро аз бахши [Релизҳои GitHub](https://github.com/nasibullo03/PyBionic-Hub/releases/latest) дастрас намоед.
2. **Насб кунед:** Файли `PyBionic-Runner-v2.1.1-arm64.apk`-ро дар дастгоҳи Android 8.0+ (ARM64) насб кунед.
3. **Иҷозатҳо:** Иҷозати огоҳиномаҳоро диҳед ва хомӯш кардани маҳдудияти батареяро (Doze Mode) барои кори устувори 24/7 тасдиқ кунед.
4. **Оғози боти аввал:** Ба бахши **BotHub** гузаред, қолабро интихоб кунед (масалан, `Telebot` ё `FastAPI`), токени худро ворид кунед ва тугмаи **▶ Оғоз**-ро пахш намоед.
5. **Идора аз компютер:** Ба **Танзимот** ➔ **Web Dashboard** равед, суроғаи IP-ро дар компютер кушоед ва PIN-кодро ворид созед.

---

## 🤖 Маълумот барои Зеҳни Сунъӣ (LLM Reference)

PyBionic барои кори худмухтор ва тавлиди код тавассути ёварони ИИ комилан мутобиқ карда шудааст. Барои ҳуҷҷатҳои пурра ба [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md) муроҷиат намоед.

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Литсензия ва муаллиф

- Таҳти литсензияи кушодаи **GNU Affero General Public License v3.0 (AAGPL-3.0)** нашр шудааст. Муаллиф ва таҳиягар: **Насибулло Халилов** ([@nasibullo03](https://github.com/nasibullo03)).
