# 🇹🇷 ⚡ PyBionic Runner — Android'de 7/24 Kesintisiz Python 3.14 Çalıştırma

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | **🇹🇷 Türkçe** | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APK_İNDİR-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Proje Hakkında

**PyBionic Runner**, yerel **Python 3.14 (aarch64 Bionic libc)** sürümünü doğrudan akıllı telefonunuzda çalıştıran Android için bağımsız ve yüksek performanslı bir çalışma ortamıdır. Telefonunuzu Telegram botları, FastAPI/Flask web uygulamaları, Discord botları ve arka plan görevleri için sessiz, enerji tasarruflu ve 7/24 kesintisiz çalışan bir mikro sunucuya dönüştürür.

Ağır Linux emülatörlerinin (Termux, PRoot, UserLAnd) aksine PyBionic, doğrudan Android'in sistem kütüphanesi olan **Bionic libc** ile derlenmiştir. Anında başlar, **45 MB'tan az RAM** tüketir, **WakeLock ve Doze Mode muafiyeti** ile arka planda kapanmaya karşı korunur ve yerel Wi-Fi üzerinden **Web Dashboard** ile bilgisayardan kontrol edilebilir.

---

## 🌟 Öne Çıkan Özellikler

- 🐍 **Yerel Python 3.14.10:** ARM64 Bionic libc için derlenmiş, `asyncio`, `multiprocessing`, `ssl` ve SQLite3 desteği.
- 🔋 **7/24 Kesintisiz Barındırma:** CPU WakeLock tutan `Foreground Service`, pil sıcaklığı takibi ve Android uyku koruması.
- 🛡️ **Akıllı Watchdog:** Çökme veya yeniden başlatmada botları otomatik olarak yeniden başlatan akıllı mekanizma.
- 🌐 **Web Dashboard (PC Kontrolü):** Wi-Fi üzerinden bilgisayar tarayıcısından bot yönetimi, log takibi ve kod düzenleme (PIN korumalı).
- 📦 **BotHub Kataloğu:** 26'dan fazla hazır bot şablonu (Aiogram 3, Telebot, FastAPI, Flask, Kazıyıcılar ve Yapay Zeka botları).
- 🗄️ **Dahili SQLite Tarayıcı:** Bot veritabanlarını OOM bellek taşması riski olmadan doğrudan uygulama içinde inceleme.
- 🔍 **Canlı Telemetri:** Hücresel ağ ve Wi-Fi hız grafikleri, bot başına bant genişliği, RAM ve CPU kullanımı.
- 🌍 **24 Dil Desteği:** Sağdan sola (RTL) dahil olmak üzere eksiksiz arayüz yerelleştirmesi.
- 🔒 **Güvenlik ve İzolasyon:** `.env` gizli anahtar kasası, loglarda token maskeleme ve biyometrik parmak izi kilidi.

---

## 🚀 Hızlı Başlangıç

1. **APK İndirin:** En son sürümü [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest) sayfasından edinin.
2. **Kurun:** `PyBionic-Runner-v2.1.1-arm64.apk` dosyasını Android 8.0+ (ARM64) cihazınıza yükleyin.
3. **İzinler:** Bildirim iznini verin ve 7/24 çalışma için pil optimizasyonunu devre dışı bırakın.
4. **İlk Botu Çalıştırın:** **BotHub** sekmesine gidin, bir şablon seçin, tokeninizi girin ve **▶ Çalıştır**'a basın.
5. **Bilgisayardan Yönetin:** **Ayarlar** ➔ **Web Dashboard** yolunu izleyin, IP adresini bilgisayarınızda açın ve PIN kodunu girin.

---

## 🤖 Yapay Zeka İçin Bilgiler (LLM Reference)

PyBionic, yapay zeka asistanlarının otonom bot yazması ve yönetmesi için optimize edilmiştir. Tam teknik kılavuz için [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md) dosyasına bakın.

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Lisans ve Geliştirici

- **GNU Affero General Public License v3.0 (AAGPL-3.0)** altında lisanslanmıştır. Geliştirici: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
