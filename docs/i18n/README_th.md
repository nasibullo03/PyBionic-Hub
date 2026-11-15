# 🇹🇭 ⚡ PyBionic Runner — สภาพแวดล้อมการรัน Python 3.14 บน Android ต่อเนื่องตลอด 24/7

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | **🇹🇭 ไทย**

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_ดาวน์โหลด_PYBIONIC_APK-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 เกี่ยวกับโครงการ

**PyBionic Runner** คือสภาพแวดล้อมการทำงานประสิทธิภาพสูงสำหรับ Android ที่รัน **Python 3.14 (aarch64 Bionic libc)** แบบเนทีฟบนสมาร์ทโฟนของคุณโดยตรง เปลี่ยนโทรศัพท์เครื่องเก่าหรือเครื่องสำรองให้กลายเป็นไมโครเซิร์ฟเวอร์ที่เงียบ ประหยัดพลังงาน และทำงานตลอด 24 ชั่วโมงสำหรับบอท Telegram, เว็บแอปพลิเคชัน FastAPI/Flask, บอท Discord และสคริปต์อัตโนมัติในเบื้องหลัง

แตกต่างจากอีมูเลเตอร์ Linux ขนาดใหญ่ (Termux, PRoot, UserLAnd) PyBionic ถูกคอมไพล์เข้ากับไลบรารีระบบของ Android อย่าง **Bionic libc** โดยตรง เริ่มทำงานได้ทันที ใช้หน่วยความจำน้อยกว่า **45 MB RAM** ป้องกันการปิดตัวในเบื้องหลังด้วย **WakeLock และข้อยกเว้นโหมดประหยัดพลังงาน Doze Mode** พร้อมควบคุมได้จากคอมพิวเตอร์ผ่าน **Web Dashboard** บน Wi-Fi.

---

## 🌟 คุณสมบัติเด่น

- 🐍 **Python 3.14.10 เนทีฟ:** คอมไพล์สำหรับ ARM64 Bionic libc พร้อมรองรับ `asyncio`, `multiprocessing`, `ssl` และ SQLite3 อย่างสมบูรณ์
- 🔋 **โฮสติ้งต่อเนื่อง 24/7:** บริการเบื้องหน้า (Foreground Service) พร้อม CPU WakeLock การตรวจวัดอุณหภูมิแบตเตอรี่ และการป้องกันระบบหลับ
- 🛡️ **ระบบ Watchdog อัจฉริยะ:** กู้คืนและรีสตาร์ทบอทอัตโนมัติเมื่อเกิดข้อผิดพลาดหรือเมื่อโทรศัพท์เปิดเครื่องใหม่
- 🌐 **Web Dashboard (ควบคุมจาก PC):** จัดการบอท ดูบันทึกการทำงานแบบเรียลไทม์ และแก้ไขโค้ดผ่านเบราว์เซอร์บนคอมพิวเตอร์ผ่าน Wi-Fi ด้วยรหัส PIN
- 📦 **คลัง BotHub:** เทมเพลตบอทสำเร็จรูปกว่า 26 แบบ (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, ตัวดึงข้อมูล และบอท AI)
- 🗄️ **ตัวดู SQLite ในตัว:** ตรวจสอบฐานข้อมูลได้โดยตรงในแอปพลิเคชันโดยไม่เสี่ยงต่อปัญหาหน่วยความจำไม่เพียงพอ (OOM)
- 🔍 **การวัดและส่งข้อมูลทางไกล:** กราฟความเร็วเครือข่ายมือถือและ Wi-Fi สถิติการใช้ข้อมูลของแต่ละบอท ปริมาณการใช้ RAM และ CPU
- 🌍 **รองรับ 24 ภาษา:** อินเทอร์เฟซได้รับการแปลเป็นภาษาท้องถิ่นอย่างสมบูรณ์รวมถึงภาษาที่เขียนจากขวาไปซ้าย (RTL)
- 🔒 **ความปลอดภัยและการแยกข้อมูล:** ตู้นิรภัยสำหรับตัวแปร `.env` การซ่อนโทเค็นในบันทึก และการล็อกด้วยลายนิ้วมือไบโอเมตริกซ์

---

## 🚀 เริ่มต้นใช้งานด่วน

1. **ดาวน์โหลด APK:** ดาวน์โหลดเวอร์ชันล่าสุดได้จาก [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
2. **ติดตั้ง:** ติดตั้งไฟล์ `PyBionic-Runner-v2.1.1-arm64.apk` บนอุปกรณ์ Android 8.0+ (ARM64)
3. **การอนุญาต:** อนุญาตการแจ้งเตือนและปิดการเพิ่มประสิทธิภาพแบตเตอรี่เพื่อให้ระบบทำงานได้ตลอด 24/7
4. **เริ่มบอทแรก:** ไปที่แท็บ **BotHub** เลือกเทมเพลต ใส่โทเค็นของคุณ แล้วกด **▶ เริ่มทำงาน**
5. **ควบคุมจาก PC:** ไปที่ **การตั้งค่า** ➔ **Web Dashboard** เปิดที่อยู่ IP ในเบราว์เซอร์ของคอมพิวเตอร์แล้วใส่รหัส PIN

---

## 🤖 ข้อมูลจำเพาะสำหรับ AI (LLM Reference)

PyBionic ได้รับการออกแบบให้เหมาะสมกับการเขียนโค้ดและปรับใช้บอทโดยอัตโนมัติจากผู้ช่วย AI อ่านคู่มือฉบับเต็มได้ที่ [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 สิทธิ์การใช้งานและผู้พัฒนา

- เผยแพร่ภายใต้ใบอนุญาต **GNU Affero General Public License v3.0 (AAGPL-3.0)** พัฒนาโดย **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03))
