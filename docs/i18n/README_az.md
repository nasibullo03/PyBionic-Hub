# 🇦🇿 ⚡ PyBionic Runner — Android-də 24/7 fasiləsiz Python 3.14 mühiti

[![Release](https://img.shields.io/badge/Release-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | **🇦🇿 Azərbaycan** | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APK_YÜKLƏ-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Layihə haqqında

**PyBionic Runner** — Android üçün yüksək performanslı müstəqil icra mühitidir və yerli **Python 3.14 (aarch64 Bionic libc)**-ni birbaşa smartfonunuzda işə salır. Tətbiq istənilən telefonu Telegram botları, FastAPI/Flask veb tətbiqləri, Discord botları və arxa plan tapşırıqları üçün səssiz, enerjiyə qənaət edən və 24/7 fasiləsiz işləyən mikroserverə çevirir.

Ağır Linux emulyatorlarından (Termux, PRoot, UserLAnd) fərqli olaraq, PyBionic birbaşa Android-in sistem kitabxanası — **Bionic libc** ilə tərtib edilmişdir. Dərhal açılır, **45 MB-dan az operativ yaddaş (RAM)** istifadə edir, **WakeLock və Doze Mode istisnası** ilə arxa planda bağlanmaqdan qorunur və yerli Wi-Fi vasitəsilə **Web Dashboard** ilə kompüterdən idarə olunur.

---

## 🌟 Əsas xüsusiyyətlər

- 🐍 **Yerli Python 3.14.10:** ARM64 Bionic libc üçün yığılmış, `asyncio`, `multiprocessing`, `ssl` və SQLite3 dəstəyi.
- 🔋 **24/7 Fasiləsiz hostinq:** CPU WakeLock saxlayan Foreground Service, batareya temperaturu nəzarəti və yuxu rejimindən mühafizə.
- 🛡️ **Ağıllı Watchdog:** Xətalar baş verdikdə və ya telefon yenidən başladıqda botların avtomatik bərpası.
- 🌐 **Web Dashboard (Kompüterdən idarəetmə):** Wi-Fi vasitəsilə kompüter brauzerində botların idarəsi, loqların izlənməsi və kod redaktəsi (PIN kod ilə).
- 📦 **BotHub kataloqu:** 26-dan çox hazır bot şablonu (Aiogram 3, Telebot, FastAPI, Flask, Skraperlər və süni intellekt botları).
- 🗄️ **Daxili SQLite baxıcısı:** Botların verilənlər bazasını yaddaş daşması riski olmadan tətbiq daxilində nəzərdən keçirmək.
- 🔍 **Canlı telemetriya:** Şəbəkə və Wi-Fi sürət qrafikləri, hər botun trafik xərci, RAM və CPU istifadəsi.
- 🌍 **24 dil dəstəyi:** Sağdan sola (RTL) daxil olmaqla tam interfeys lokallaşdırılması.
- 🔒 **Təhlükəsizlik və izolyasiya:** Gizli `.env` açarlar kassası, loqlarda tokenlərin maskalanması və biometrik barmaq izi kilidi.

---

## 🚀 Tez başlama

1. **APK yükləyin:** Ən son buraxılışı [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest) səhifəsindən əldə edin.
2. **Quraşdırın:** `PyBionic-Runner-v2.2.0-arm64.apk` faylını Android 8.0+ (ARM64) cihazınıza quraşdırın.
3. **İcazələr verin:** Bildirişlərə icazə verin və 24/7 işləməsi üçün batareya optimallaşdırmasını söndürün.
4. **İlk botu işə salın:** **BotHub** bölməsinə keçin, şablon seçin, tokeninizi daxil edin və **▶ Başla** düyməsinə vurun.
5. **Kompüterdən idarə edin:** **Parametrlər** ➔ **Web Dashboard** menyusuna daxil olun, göstərilən IP-ni kompüterdə açın və PIN daxil edin.

---

## 🤖 Süni intellekt üçün məlumat (LLM Reference)

PyBionic süni intellekt köməkçiləri tərəfindən avtonom kod yazmaq və botları yerləşdirmək üçün optimallaşdırılmışdır. Tam təlimat: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Lisenziya və müəllif

- **GNU Affero General Public License v3.0 (AAGPL-3.0)** açıq lisenziyası ilə yayılır. Tərtibatçı: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
