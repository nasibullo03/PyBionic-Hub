# 🇮🇷 ⚡ PyBionic Runner — اجرای ۲۴ ساعته پایتون ۳.۱۴ در اندروید به صورت مستقل

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | **🇮🇷 فارسی** | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_دانلود_فایل_نصبی_PYBIONIC_APK-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 درباره پروژه

برنامه **PyBionic Runner** یک محیط اجرای خودکار و با عملکرد بالا برای اندروید است که پایتون نسخه **Python 3.14 (aarch64 Bionic libc)** را به طور مستقیم روی تلفن همراه شما اجرا می‌کند. این برنامه هر گوشی اندرویدی را به یک مینی‌سرور ۲۴ ساعته، بی‌صدا و کم‌مصرف برای ربات‌های تلگرام، وب‌سرویس‌های FastAPI/Flask، ربات‌های دیسکورد و وظایف پس‌زمینه تبدیل می‌نماید.

برخلاف شبیه‌سازهای سنگین لینوکس (Termux، PRoot، UserLAnd)، این پلتفرم مستقیماً با کتابخانه سیستمی اندروید **Bionic libc** کامپایل شده است. بلافاصله اجرا می‌شود، کمتر از **۴۵ مگابایت رم** مصرف می‌کند، با استفاده از **WakeLock و لغو محدودیت Doze Mode** از توقف در پس‌زمینه در امان است و از طریق **Web Dashboard** تحت شبکه Wi-Fi از رایانه قابل کنترل است.

---

## 🌟 ویژگی‌های کلیدی

- 🐍 **پایتون ۳.۱۴.۱۰ بومی:** کامپایل شده برای معماری ARM64 Bionic با پشتیبانی از `asyncio`، `multiprocessing`، `ssl` و SQLite3.
- 🔋 **میزبانی ۲۴ ساعته مداوم:** سرویس پس‌زمینه همراه با نگهداری پردازنده WakeLock، پایش دمای باتری و جلوگیری از خواب رفتن سیستم.
- 🛡️ **نگهبان هوشمند (Watchdog):** راه‌اندازی مجدد خودکار ربات‌ها در صورت بروز خطا یا روشن شدن مجدد گوشی.
- 🌐 **داشبورد تحت وب (کنترل با کامپیوتر):** مدیریت ربات‌ها، مشاهده لاگ‌های زنده و ویرایش کد در مرورگر رایانه از طریق Wi-Fi با رمز PIN.
- 📦 **کاتالوگ BotHub:** بیش از ۲۶ قالب آماده ربات (Aiogram 3، Telebot، FastAPI + Uvicorn، Flask، اسکریپت‌های اسکرپ و هوش مصنوعی).
- 🗄️ **مرورگر داخلی دیتابیس SQLite:** مشاهده داده‌ها به صورت مستقیم درون برنامه با محافظت در برابر کمبود حافظه (OOM).
- 🔍 **تله‌متری زنده:** نمودار لحظه‌ای سرعت اینترنت همراه و وای‌فای، مصرف دیتای هر ربات، میزان اشغال رم و پردازنده.
- 🌍 **پشتیبانی از ۲۴ زبان:** بومی‌سازی کامل محیط کاربری به همراه چینش راست به چپ (RTL).
- 🔒 **امنیت و تفکیک داده‌ها:** مخزن امن متغیرهای محیطی `.env`، پوشاندن توکن‌های حساس در لاگ‌ها و قفل اثر انگشت.

---

## 🚀 راه‌اندازی سریع

1. **دانلود APK:** آخرین نسخه را از صفحه [انتشارهای GitHub](https://github.com/nasibullo03/PyBionic-Hub/releases/latest) دانلود کنید.
2. **نصب برنامه:** فایل `PyBionic-Runner-v2.1.1-arm64.apk` را روی دستگاه اندروید ۸.۰ یا بالاتر نصب نمایید.
3. **مجوزها:** دسترسی اعلان‌ها را تایید کرده و بهینه‌سازی باتری را غیرفعال کنید تا برنامه متوقف نشود.
4. **اجرای اولین ربات:** به زبانه **BotHub** بروید، قالبی را انتخاب کرده، توکن خود را وارد کنید و دکمه **▶ اجرا** را بزنید.
5. **مدیریت از رایانه:** به **تنظیمات** ➔ **Web Dashboard** بروید، آدرس IP را در مرورگر کامپیوتر باز کرده و پین کد را وارد نمایید.

---

## 🤖 راهنمای هوش مصنوعی و مدل‌های زبانی (LLM Reference)

این برنامه برای توسعه خودکار توسط هوش مصنوعی طراحی و بهینه‌سازی شده است. مستندات کامل فنی در [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md) موجود است.

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 مجوز و توسعه‌دهنده

- تحت مجوز آزاد **GNU Affero General Public License v3.0 (AAGPL-3.0)** منتشر شده است. توسعه‌دهنده: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
