# 🇰🇿 ⚡ PyBionic Runner — Android жүйесінде тәулік бойы (24/7) жұмыс істейтін Python 3.14 ортасы

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | **🇰🇿 Қазақша**

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APK_ЖҮКТЕП_АЛУ-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Жоба туралы

**PyBionic Runner** — бұл Android жүйесіне арналған автономды және жоғары өнімді орындау ортасы, ол **нативті Python 3.14 (aarch64 Bionic libc)** нұсқасын тікелей смартфонда іске қосады. Қосымша кез келген телефонды Telegram-боттар, FastAPI/Flask веб-қосымшалары, Discord-боттар және фондық процестер үшін үнсіз, қуат үнемдейтін 24/7 жеке микросерверге айналдырады.

Ауыр Linux эмуляторларынан (Termux, PRoot, UserLAnd) айырмашылығы, PyBionic тікелей Android жүйелік кітапханасымен — **Bionic libc**-пен құрастырылған. Ол лезде ашылады, **45 МБ-тан аз жедел жад (RAM)** пайдаланады, **WakeLock және Doze Mode шектеулерінен босату** арқылы фондық өшуден қорғалған, сондай-ақ жергілікті Wi-Fi арқылы компьютер браузерінен **Web Dashboard** арқылы басқарылады.

---

## 🌟 Негізгі мүмкіндіктер

- 🐍 **Нативті Python 3.14.10:** ARM64 Bionic libc үшін құрастырылған, `asyncio`, `multiprocessing`, `ssl` және SQLite3 толық қолдауы.
- 🔋 **24/7 Үздіксіз хостинг:** CPU WakeLock ұстап тұратын Foreground Service, батарея температурасын бақылау және ұйқы режимінен қорғау.
- 🛡️ **Интеллектуалды Watchdog:** Қателіктер туындағанда немесе телефон өшіп-қосылғанда боттарды автоматты түрде қайта қосу.
- 🌐 **Web Dashboard (Компьютерден басқару):** Wi-Fi арқылы компьютер браузерінде боттарды басқару, логтарды қарау және кодты өңдеу (PIN-код қорғауымен).
- 📦 **BotHub каталогы:** 26-дан астам дайын бот үлгілері (Aiogram 3, Telebot, FastAPI, Flask, Скраперлер және ЖИ боттары).
- 🗄️ **Кіріктірілген SQLite шолғышы:** Қосымша ішінде жад тапшылығынсыз дерекқорларды тікелей қарау.
- 🔍 **Тікелей телеметрия:** Мобильді желі мен Wi-Fi жылдамдық графиктері, боттар трафигінің есебі, RAM және CPU көрсеткіштері.
- 🌍 **24 тілді қолдау:** Оңнан солға жазылатын (RTL) тілдерді қоса алғанда толық жергіліктендіру.
- 🔒 **Қауіпсіздік және оқшаулау:** Құпия `.env` кілттер қоймасы, логтарда токендерді жасыру және саусақ ізімен бұғаттау.

---

## 🚀 Жылдам бастау

1. **APK файлын жүктеп алыңыз:** Соңғы нұсқаны [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest) бетінен алыңыз.
2. **Орнатыңыз:** `PyBionic-Runner-v2.1.1-arm64.apk` файлын Android 8.0+ (ARM64) құрылғыңызға орнатыңыз.
3. **Рұқсаттар беріңіз:** Хабарландыруларға рұқсат беріп, 24/7 жұмыс істеуі үшін батареяны оңтайландыруды өшіріңіз.
4. **Алғашқы ботты іске қосыңыз:** **BotHub** қойындысына өтіп, үлгіні таңдаңыз, токеніңізді енгізіп, **▶ Іске қосу** батырмасын басыңыз.
5. **Компьютерден басқарыңыз:** **Параметрлер** ➔ **Web Dashboard** бөліміне өтіп, көрсетілген IP-ді компьютерде ашыңыз және PIN енгізіңіз.

---

## 🤖 Жасанды интеллект үшін мәліметтер (LLM Reference)

PyBionic жасанды интеллект көмекшілерінің өздігінен код жазуы және боттарды орнатуы үшін оңтайландырылған. Толық құжаттама: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Лицензия және автор

- **GNU Affero General Public License v3.0 (AAGPL-3.0)** еркін лицензиясымен таратылады. Әзірлеуші: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
