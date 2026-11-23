# 🇮🇳 ⚡ PyBionic Runner — एंड्रॉइड पर 24/7 निरंतर Python 3.14 रनटाइम

[![Release](https://img.shields.io/badge/Release-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | **🇮🇳 हिन्दी** | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APK_डाउनलोड_करें-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 परियोजना के बारे में

**PyBionic Runner** एंड्रॉइड के लिए एक स्वतंत्र और उच्च-प्रदर्शन रनटाइम वातावरण है, जो आपके स्मार्टफोन पर सीधे **नेटिव Python 3.14 (aarch64 Bionic libc)** चलाता है। यह किसी भी एंड्रॉइड फोन को टेलीग्राम बॉट्स, FastAPI/Flask वेब एप्लिकेशन, डिस्कॉर्ड बॉट्स और बैकग्राउंड ऑटोमेशन के लिए एक शांत, ऊर्जा-कुशल और 24/7 चलने वाले माइक्रो-सर्वर में बदल देता है।

भारी लिनक्स एमुलेटर (Termux, PRoot, UserLAnd) के विपरीत, PyBionic को सीधे एंड्रॉइड की सिस्टम लाइब्रेरी **Bionic libc** के साथ संकलित किया गया है। यह तुरंत शुरू होता है, **45 MB RAM से कम** खपत करता है, **WakeLock और Doze Mode छूट** के साथ बैकग्राउंड में बंद होने से सुरक्षित रहता है, और वाई-फाई पर **Web Dashboard** के जरिए कंप्यूटर से नियंत्रित किया जा सकता है।

---

## 🌟 मुख्य विशेषताएं

- 🐍 **नेटिव Python 3.14.10:** ARM64 Bionic libc के लिए पूर्व-संकलित, `asyncio`, `multiprocessing`, `ssl` और SQLite3 का पूर्ण समर्थन।
- 🔋 **24/7 निर्बाध होस्टिंग:** CPU WakeLock बनाए रखने वाली फ़ोरग्राउंड सेवा, बैटरी तापमान की निगरानी और स्लीप मोड से सुरक्षा।
- 🛡️ **बुद्धिमान Watchdog:** क्रैश होने या फोन रीस्टार्ट होने पर बॉट्स का स्वचालित पुनः आरंभ।
- 🌐 **वेब डैशबोर्ड (PC नियंत्रण):** वाई-फाई पर कंप्यूटर ब्राउज़र से बॉट्स का प्रबंधन, लाइव लॉग और कोड संपादन (पिन सुरक्षा के साथ)।
- 📦 **BotHub कैटलॉग:** 26 से अधिक तैयार बॉट टेम्प्लेट (Aiogram 3, Telebot, FastAPI, Flask, स्क्रैपर्स और AI बॉट)।
- 🗄️ **एकीकृत SQLite ब्राउज़र:** मेमोरी ओवरफ्लो (OOM) के बिना सीधे ऐप में बॉट डेटाबेस का निरीक्षण।
- 🔍 **रीयल-टाइम टेलीमेट्री:** सेलुलर और वाई-फाई स्पीड ग्राफ़, प्रति-बॉट डेटा खपत, RAM और CPU उपयोग।
- 🌍 **24 भाषाओं का समर्थन:** RTL सहित पूर्ण बहुभाषी इंटरफ़ेस स्थानीयकरण।
- 🔒 **सुरक्षा और अलगाव:** `.env` क्रेडेंशियल वॉल्ट, लॉग में टोकन छिपाना और बायोमेट्रिक फिंगरप्रिंट लॉक।

---

## 🚀 त्वरित शुरुआत

1. **APK डाउनलोड करें:** [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest) से नवीनतम संस्करण प्राप्त करें।
2. **इंस्टॉल करें:** अपने Android 8.0+ (ARM64) डिवाइस पर `PyBionic-Runner-v2.2.0-arm64.apk` इंस्टॉल करें।
3. **अनुमतियां दें:** 24/7 संचालन के लिए सूचनाओं की अनुमति दें और बैटरी अनुकूलन को अक्षम करें।
4. **पहला बॉट चलाएं:** **BotHub** टैब पर जाएं, एक टेम्प्लेट चुनें, टोकन दर्ज करें और **▶ रन** दबाएं।
5. **कंप्यूटर से नियंत्रण:** **सेटिंग्स** ➔ **Web Dashboard** पर जाएं, ब्राउज़र में IP खोलें और पिन दर्ज करें।

---

## 🤖 एआई एजेंटों के लिए विनिर्देश (LLM Reference)

PyBionic को एआई सहायकों द्वारा कोड लिखने और स्वायत्त तैनाती के लिए अनुकूलित किया गया है। संपूर्ण तकनीकी गाइड: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)।

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 लाइसेंस और लेखक

- **GNU Affero General Public License v3.0 (AAGPL-3.0)** के तहत लाइसेंस प्राप्त। डेवलपर: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03))।
