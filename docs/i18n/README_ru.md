# ⚡ PyBionic Runner — Автономный запуск Python 3.14 на Android 24/7

[![Релиз](https://img.shields.io/badge/Релиз-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Платформа](https://img.shields.io/badge/Платформа-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![Лицензия](https://img.shields.io/badge/Лицензия-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Выберите язык / Select Language
[🇬🇧 English](../../README.md) | **🇷🇺 Русский** | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_СКАЧАТЬ_PYBIONIC_APK-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Скачать APK" height="50">
  </a>
</p>

---

## 📖 О проекте

**PyBionic Runner** — это высокопроизводительная автономная среда исполнения для Android, запускающая полноценный нативный **Python 3.14 (aarch64 Bionic libc)** прямо на вашем смартфоне. Приложение превращает любой современный или старый телефон в бесшумный, энергоэффективный круглосуточный микросервер (24/7) для Telegram-ботов, веб-приложений FastAPI/Flask, Discord-ботов и фоновых автоматизаций.

В отличие от тяжелых эмуляторов Linux (Termux, PRoot, UserLAnd), PyBionic скомпилирован напрямую под стандартную системную библиотеку Android — **Bionic libc**. Он запускается мгновенно, потребляет менее **45 МБ оперативной памяти**, защищен от засыпания системы через **WakeLock и исключение из Doze Mode**, а также управляется как с телефона (Material 3), так и с любого ПК через локальный **Web Dashboard**.

---

## 🌟 Ключевые возможности

- 🐍 **Нативный Python 3.14.10:** Скомпилирован под ARM64 Bionic libc с поддержкой `asyncio`, `multiprocessing`, `ssl`, `ctypes` и SQLite3.
- 🔋 **Непрерывный хостинг 24/7:** Фоновая служба `Foreground Service` с удержанием процессорного WakeLock, мониторингом температуры аккумулятора и защитой от сна Android.
- 🛡️ **Сторожевой таймер (Watchdog):** Автоматический перезапуск ботов при падении или перезагрузке телефона с настраиваемыми политиками перезапуска.
- 🌐 **Web Dashboard (Управление с ПК):** Управление ботами, просмотр живых логов и редактирование кода в браузере компьютера по Wi-Fi с PIN-авторизацией.
- 📦 **Каталог BotHub:** Более 26 встроенных готовых ботов (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Парсеры, ИИ-боты).
- 🗄️ **Встроенный SQLite браузер:** Просмотр баз данных ботов прямо в приложении с монолитным синхронным скроллингом и защитой от переполнения памяти.
- 🔍 **Живая телеметрия:** Графики скорости сотовой сети и Wi-Fi, учет потребления трафика каждым ботом, аптайм, RAM и CPU.
- 🌍 **24 поддерживаемых языка:** Полная локализация интерфейса с поддержкой RTL.
- 🔒 **Изоляция и безопасность:** Хранилище секретов `.env`, маскирование токенов в логах и защита биометрией/отпечатком пальца.

---

## 🚀 Быстрый старт

1. **Скачайте APK:** Загрузите свежую версию из раздела [Релизы GitHub](https://github.com/nasibullo03/PyBionic/releases/latest).
2. **Установите:** Установите `PyBionic-Runner-v2.2.0-arm64.apk` на Android 8.0+ (ARM64).
3. **Разрешения:** Разрешите показ уведомлений и подтвердите отключение оптимизации батареи для стабильной работы 24/7.
4. **Запуск первого бота:**
   - Перейдите во вкладку **BotHub**.
   - Выберите шаблон (например, `Простой Telebot` или `FastAPI сервер`).
   - Нажмите **Установить бота** ➔ укажите токен ➔ нажмите **▶ Запустить**.
5. **Управление с компьютера:**
   - Перейдите в **Настройки** ➔ **Web Dashboard**.
   - Откройте указанный IP в браузере на ПК и введите PIN-код.

---

## 🤖 Информация для ИИ (LLM Reference)

PyBionic оптимизирован для автономной работы и генерации кода ИИ-ассистентами:
- **Техническая спецификация для ИИ:** Смотрите подробный документ [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).
- **Декларация веб-панелей в коде:**
  ```python
  print("[PYBIONIC_WEB:8080]")
  ```
  При выводе этой строки PyBionic автоматически отобразит кнопку **🌐 Веб-UI** на карточке бота в приложении.

---

## 📄 Лицензия и авторство

- Распространяется под свободной лицензией **GNU AGPLv3**.
- Автор и разработчик: **Насибулло Халилов** ([@nasibullo03](https://github.com/nasibullo03)).
