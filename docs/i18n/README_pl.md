# 🇵🇱 ⚡ PyBionic Runner — Autonomiczne środowisko uruchomieniowe Python 3.14 na Androida 24/7

[![Release](https://img.shields.io/badge/Release-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

**🇵🇱 Polski** | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_POBIERZ_PYBIONIC_APK-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 O projekcie

**PyBionic Runner** to autonomiczne, wysoce wydajne środowisko uruchomieniowe dla systemu Android, które uruchamia natywny **Python 3.14 (aarch64 Bionic libc)** bezpośrednio na Twoim smartfonie. Przekształca każdy telefon w cichy, energooszczędny i działający 24/7 mikroserwer dla botów Telegram, aplikacji webowych FastAPI/Flask, botów Discord i zadań w tle.

W przeciwieństwie do ciężkich emulatorów Linuksa (Termux, PRoot, UserLAnd), PyBionic jest skompilowany bezpośrednio z biblioteką systemową Androida — **Bionic libc**. Uruchamia się błyskawicznie, zużywa poniżej **45 MB RAM**, jest chroniony przed uśpieniem przez **WakeLock i wyjątki z Doze Mode**, a także może być w pełni kontrolowany z komputera przez lokalny **Web Dashboard** po Wi-Fi.

---

## 🌟 Kluczowe funkcje

- 🐍 **Natywny Python 3.14.10:** Skompilowany dla ARM64 Bionic libc z pełnym wsparciem dla `asyncio`, `multiprocessing`, `ssl` i SQLite3.
- 🔋 **Ciągły hosting 24/7:** Usługa pierwszoplanowa (Foreground Service) z blokadą procesora WakeLock, monitoringiem temperatury i ochroną przed uśpieniem.
- 🛡️ **Inteligentny Watchdog:** Automatyczne wznawianie botów po awarii lub ponownym uruchomieniu telefonu.
- 🌐 **Web Dashboard (Sterowanie z PC):** Zarządzanie botami, podgląd logów na żywo i edycja kodu w przeglądarce komputera przez Wi-Fi z autoryzacją PIN.
- 📦 **Katalog BotHub:** Ponad 26 gotowych szablonów botów (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Scrapery i boty AI).
- 🗄️ **Wbudowana przeglądarka SQLite:** Bezpieczny podgląd baz danych wewnątrz aplikacji z ochroną przed brakiem pamięci (OOM).
- 🔍 **Telemetria w czasie rzeczywistym:** Wykresy prędkości sieci i Wi-Fi, pomiar transferu dla każdego bota, statystyki RAM i procesora.
- 🌍 **Obsługa 24 języków:** Pełna lokalizacja interfejsu wraz ze wsparciem dla języków pisanych od prawej do lewej (RTL).
- 🔒 **Bezpieczeństwo i izolacja:** Bezpieczny magazyn kluczy `.env`, maskowanie wrażliwych tokenów w logach i blokada biometryczna.

---

## 🚀 Szybki start

1. **Pobierz APK:** Pobierz najnowszą wersję z [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest).
2. **Zainstaluj:** Zainstaluj `PyBionic-Runner-v2.2.0-arm64.apk` na urządzeniu z Androidem 8.0+ (ARM64).
3. **Uprawnienia:** Zezwól na powiadomienia i wyłącz optymalizację baterii dla stabilnej pracy 24/7.
4. **Uruchom pierwszego bota:** Otwórz zakładkę **BotHub**, wybierz szablon, wpisz token i kliknij **▶ Uruchom**.
5. **Sterowanie z PC:** Przejdź do **Ustawienia** ➔ **Web Dashboard**, otwórz adres IP w przeglądarce komputera i wpisz kod PIN.

---

## 🤖 Wskazówki dla modeli sztucznej inteligencji (LLM Reference)

PyBionic został zoptymalizowany pod kątem autonomicznego tworzenia kodu przez asystentów AI. Pełna dokumentacja: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Licencja i Autor

- Oprogramowanie objęte licencją **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Autor: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
