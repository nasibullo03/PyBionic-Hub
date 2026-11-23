# 🇰🇬 ⚡ PyBionic Runner — Android түзмөгүндө 24/7 үзгүлтүксүз Python 3.14 чөйрөсү

[![Release](https://img.shields.io/badge/Release-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

**🇰🇬 Кыргызча** | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APK_ЖҮКТӨП_АЛУУ-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Долбоор жөнүндө

**PyBionic Runner** — бул Android үчүн жогорку ылдамдыктагы өз алдынча аткаруу чөйрөсү, ал түздөн-түз смартфонуңузда **нативдүү Python 3.14 (aarch64 Bionic libc)** иштетет. Тиркеме каалаган телефонду Telegram-боттор, FastAPI/Flask веб-кызматтары, Discord-боттор жана фондук тапшырмалар үчүн тынч, энергияны үнөмдөөчү 24/7 жеке микросерверге айлантат.

Оор Linux эмуляторлорунан (Termux, PRoot, UserLAnd) айырмаланып, PyBionic түздөн-түз Android'дин тутумдук китепканасы — **Bionic libc** менен куралган. Ал заматта ачылат, **45 МБдан аз оперативдүү эстутумду (RAM)** талап кылат, **WakeLock жана Doze Mode чектөөлөрүнөн бошотуу** аркылуу фондо токтоп калуудан корголгон, ошондой эле жергиликтүү Wi-Fi аркылуу компьютерден **Web Dashboard** менен башкарылат.

---

## 🌟 Негизги мүмкүнчүлүктөр

- 🐍 **Нативдүү Python 3.14.10:** ARM64 Bionic libc үчүн даярдалган, `asyncio`, `multiprocessing`, `ssl` жана SQLite3 толук колдоосу.
- 🔋 **24/7 Үзгүлтүксүз хостинг:** CPU WakeLock кармап туруучу Foreground Service, батареянын температурасын көзөмөлдөө жана уйку режиминен коргоо.
- 🛡️ **Акылдуу Watchdog:** Ката чыкканда же телефон өчүп-күйгөндө ботторду автоматтык түрдө кайра иштетүү.
- 🌐 **Web Dashboard (Компьютерден башкаруу):** Wi-Fi аркылуу компьютер браузеринде ботторду башкаруу, логдорду көрүү жана кодду түзөтүү (PIN-код менен корголгон).
- 📦 **BotHub каталогу:** 26дан ашык даяр бот калыптары (Aiogram 3, Telebot, FastAPI, Flask, Скраперлер жана ЖИ боттору).
- 🗄️ **Ички SQLite серепчиси:** Эстутум жетишсиздигине кабылбай, боттордун маалымат базаларын тиркеменин ичинен түздөн-түз көрүү.
- 🔍 **Түз телеметрия:** Мобилдик тармак жана Wi-Fi ылдамдык графиктери, ар бир боттун трафик көлөмү, RAM жана CPU көрсөткүчтөрү.
- 🌍 **24 тилди колдоо:** Оңдон солго жазылган (RTL) тилдерди кошкондо толук интерфейс котормосу.
- 🔒 **Коопсуздук жана изоляция:** Жашыруун `.env` ачкычтар кампасы, логдордо токендерди жашыруу жана манжа изи менен бөгөттөө.

---

## 🚀 Ыкчам баштоо

1. **APK файлын жүктөп алыңыз:** Акыркы нускасын [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest) баракчасынан алыңыз.
2. **Орнотуңуз:** `PyBionic-Runner-v2.2.0-arm64.apk` файлын Android 8.0+ (ARM64) түзмөгүңүзгө орнотуңуз.
3. **Уруксаттарды бериңиз:** Билдирмелерге уруксат берип, 24/7 үзгүлтүксүз иштөө үчүн батареяны оптималдаштырууну өчүрүңүз.
4. **Алгачкы ботту иштетиңиз:** **BotHub** өтмөгүнө өтүп, калыпты тандаңыз, токениңизди киргизип, **▶ Баштоо** баскычын басыңыз.
5. **Компьютерден башкарыңыз:** **Жөндөөлөр** ➔ **Web Dashboard** бөлүмүнө кирип, көрсөтүлгөн IP-ни компьютерде ачыңыз жана PIN киргизиңиз.

---

## 🤖 Жасалма интеллект үчүн маалымат (LLM Reference)

PyBionic жасалма интеллект жардамчыларынын өз алдынча код жазуусу жана ботторду орнотуусу үчүн толук ылайыкташтырылган. Толук маалымат: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Лицензия жана автор

- **GNU Affero General Public License v3.0 (AAGPL-3.0)** ачык лицензиясы боюнча таратылат. Иштеп чыгуучу: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
