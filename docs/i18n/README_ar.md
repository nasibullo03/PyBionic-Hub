# 🇸🇦 ⚡ PyBionic Runner — بيئة تشغيل بايثون 3.14 على أندرويد على مدار الساعة 24/7

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | **🇸🇦 العربية** | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_تحميل_تطبيق_PYBIONIC_APK-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 نبذة عن المشروع

يُعد **PyBionic Runner** بيئة تشغيل ذاتية عالية الأداء لنظام أندرويد، حيث يُشغّل لغة **Python 3.14 (aarch64 Bionic libc)** الأصلية مباشرة على هاتفك الذكي. يُحوّل التطبيق أي هاتف قديم أو حديث إلى خادم صغير هادئ وموفر للطاقة يعمل 24/7 دون توقف لاستضافة بوتات تيليجرام وتطبيقات FastAPI/Flask وبوتات ديسكورد والمهام الخلفية.

على عكس برامج محاكاة لينكس الثقيلة (Termux, PRoot, UserLAnd)، تم تجميع PyBionic مباشرة باستخدام مكتبة أندرويد الأصلية **Bionic libc**. يبدأ التشغيل فوراً ويستهلك أقل من **45 ميجابايت من الذاكرة العشوائية (RAM)**، ومحمي من الإغلاق في الخلفية عبر **WakeLock واستثناء وضع السكون Doze Mode**، ويمكن التحكم به بالكامل من الكمبيوتر عبر **Web Dashboard** عبر شبكة Wi-Fi.

---

## 🌟 الميزات الأساسية

- 🐍 **بايثون 3.14.10 أصلي:** تم تجميعه لمعالجات ARM64 مع مكتبة Bionic ودعم كامل لمكتبات `asyncio` و `multiprocessing` و `ssl` و SQLite3.
- 🔋 **استضافة متواصلة 24/7:** خدمة خلفية مع حجز WakeLock ومراقبة حرارة البطارية وتجاوز قيود توفير الطاقة.
- 🛡️ **حارس ذكي (Watchdog):** إعادة تشغيل البوتات تلقائياً عند حدوث أخطاء أو إعادة تشغيل الهاتف مع سياسات مرنة.
- 🌐 **لوحة تحكم عبر الويب (التحكم من الحاسوب):** إدارة البوتات وتحرير الأكواد وقراءة السجلات مباشرة من متصفح الكمبيوتر مع حماية برمز PIN.
- 📦 **كتالوج BotHub:** أكثر من 26 قالباً جاهزاً للبوتات (Aiogram 3, Telebot, FastAPI, Flask, بوتات الذكاء الاصطناعي وكاشطات الويب).
- 🗄️ **متصفح SQLite مدمج:** تصفح قواعد البيانات مباشرة داخل التطبيق مع حماية فائقة من نفاد الذاكرة (OOM).
- 🔍 **بيانات تشغيل حية:** رسوم بيانية لسرعة الشبكة والواي فاي واستهلاك البيانات لكل بوت ونسبة استخدام المعالج والذاكرة.
- 🌍 **دعم 24 لغة:** تعريب كامل لواجهة المستخدم مع دعم كامل للغات التي تكتب من اليمين إلى اليسار (RTL).
- 🔒 **الأمان والعزل:** خزينة آمنة لمتغيرات البيئة `.env` وإخفاء الرموز السرية في السجلات وقفل بيومتري بالبصمة.

---

## 🚀 البدء السريع

1. **تحميل التطبيق:** حمّل أحدث إصدار من صفحة [إصدارات GitHub](https://github.com/nasibullo03/PyBionic-Hub/releases/latest).
2. **التثبيت:** ثبّت ملف `PyBionic-Runner-v2.1.1-arm64.apk` على هاتف يعمل بنظام Android 8.0 فما فوق.
3. **الأذونات:** امنح إذن الإشعارات ووافق على **تعطيل تحسينات البطارية** لضمان التشغيل الدائم 24/7.
4. **تشغيل أول بوت:** افتح تبويب **BotHub**، اختر القالب المناسب، أدخل التوكن واضغط على **▶ تشغيل**.
5. **التحكم من الحاسوب:** ادخل إلى **الإعدادات** ➔ **Web Dashboard**، وافتح العنوان في متصفح حاسوبك وأدخل رمز PIN.

---

## 🤖 دليل المطورين والذكاء الاصطناعي (LLM Reference)

تم تصميم PyBionic بالكامل ليتوافق مع المساعدين الأذكياء لإنشاء الأكواد ونشر البوتات تلقائياً. راجع الدليل الكامل: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 الترخيص والمؤلف

- مرخص تحت رخصة **GNU Affero General Public License v3.0 (AAGPL-3.0)** الحرة. المطور: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
