# 🇺🇦 ⚡ PyBionic Runner — Автономний запуск Python 3.14 на Android 24/7

[![Release](https://img.shields.io/badge/Release-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | **🇺🇦 Українська** | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_ЗАВАНТАЖИТИ_PYBIONIC_APK-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Про проект

**PyBionic Runner** — це високопродуктивне автономне середовище виконання для Android, яке запускає повноцінний нативний **Python 3.14 (aarch64 Bionic libc)** безпосередньо на вашому смартфоні. Додаток перетворює будь-який телефон на безшумний, енергоефективний цілодобовий мікросервер (24/7) для Telegram-ботів, веб-сервісів FastAPI/Flask, Discord-ботів та фонової автоматизації.

На відміну від важких емуляторів Linux (Termux, PRoot, UserLAnd), PyBionic скомпільований безпосередньо під системну бібліотеку Android — **Bionic libc**. Він запускається миттєво, споживає менше **45 МБ оперативної пам'яті**, захищений від зупинки системою завдяки **WakeLock та виключенню з Doze Mode**, а також керується як з телефону, так і з ПК через локальний **Web Dashboard**.

---

## 🌟 Ключові можливості

- 🐍 **Нативний Python 3.14.10:** Скомпільований під ARM64 Bionic libc з підтримкою `asyncio`, `multiprocessing`, `ssl` та SQLite3.
- 🔋 **Безперервний хостинг 24/7:** Фонова служба Foreground Service з утриманням процесорного WakeLock, контролем температури та захистом від сну.
- 🛡️ **Розумний Watchdog:** Автоматичний перезапуск ботів у разі збоїв або перезавантаження пристрою з гнучкими політиками.
- 🌐 **Web Dashboard (Керування з ПК):** Керування ботами, перегляд логів у реальному часі та редагування коду в браузері комп'ютера через Wi-Fi з PIN-кодом.
- 📦 **Каталог BotHub:** Понад 26 вбудованих готових шаблонів ботів (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Скрапери та ШІ-боти).
- 🗄️ **Вбудований SQLite браузер:** Перегляд баз даних безпосередньо у додатку з захистом від переповнення пам'яті (OOM).
- 🔍 **Жива телеметрія:** Графіки швидкості мережі та Wi-Fi, облік трафіку кожного бота, аптайм, використання RAM та CPU.
- 🌍 **Підтримка 24 мов:** Повна локалізація інтерфейсу з підтримкою мов RTL.
- 🔒 **Безпека та ізоляція:** Сховище секретів `.env`, маскування токенів у логах та біометричний захист відбитком пальця.

---

## 🚀 Швидкий старт

1. **Завантажте APK:** Завантажте свіжу версію з розділу [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest).
2. **Встановіть:** Встановіть `PyBionic-Runner-v2.2.0-arm64.apk` на Android 8.0+ (ARM64).
3. **Дозволи:** Дозвольте сповіщення та вимкніть оптимізацію батареї для безперервної роботи 24/7.
4. **Запуск першого бота:** Перейдіть у вкладку **BotHub**, виберіть шаблон, введіть токен і натисніть **▶ Запустити**.
5. **Керування з комп'ютера:** Відкрийте **Налаштування** ➔ **Web Dashboard**, перейдіть за вказаною IP у браузері ПК та введіть PIN.

---

## 🤖 Інформація для штучного інтелекту (LLM Reference)

PyBionic оптимізовано для автономного написання коду та розгортання ботів ШІ-асистентами. Технічна специфікація: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Ліцензія та авторство

- Поширюється за вільною ліцензією **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Розробник: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
