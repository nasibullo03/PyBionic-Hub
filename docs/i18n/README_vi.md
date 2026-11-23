# 🇻🇳 ⚡ PyBionic Runner — Môi trường chạy Python 3.14 tự động 24/7 trên Android

[![Release](https://img.shields.io/badge/Release-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | **🇻🇳 Tiếng Việt** | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_TẢI_VỀ_PYBIONIC_APK-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Giới thiệu dự án

**PyBionic Runner** là môi trường thực thi hiệu năng cao dành riêng cho Android, chạy trực tiếp **Python 3.14 nguyên bản (aarch64 Bionic libc)** trên điện thoại của bạn. Ứng dụng biến bất kỳ chiếc điện thoại nào thành máy chủ mini hoạt động 24/7 êm ái, tiết kiệm pin cho bot Telegram, ứng dụng web FastAPI/Flask, bot Discord và các tác vụ tự động hóa ngầm.

Khác với các trình giả lập Linux nặng nề (Termux, PRoot, UserLAnd), PyBionic được biên dịch trực tiếp với thư viện hệ thống của Android — **Bionic libc**. Ứng dụng khởi động tức thì, tiêu tốn dưới **45 MB RAM**, được bảo vệ chống tắt ngầm nhờ **WakeLock và miễn trừ chế độ ngủ Doze Mode**, đồng thời có thể quản lý tiện lợi từ máy tính qua **Web Dashboard** qua mạng Wi-Fi.

---

## 🌟 Tính năng nổi bật

- 🐍 **Python 3.14.10 nguyên bản:** Được biên dịch cho ARM64 Bionic libc với hỗ trợ đầy đủ `asyncio`, `multiprocessing`, `ssl` và SQLite3.
- 🔋 **Máy chủ chạy liên tục 24/7:** Dịch vụ tiền cảnh (Foreground Service) duy trì CPU WakeLock, theo dõi nhiệt độ pin và ngăn chặn chế độ ngủ của Android.
- 🛡️ **Watchdog thông minh:** Tự động khôi phục bot khi gặp sự cố hoặc khi điện thoại khởi động lại.
- 🌐 **Web Dashboard (Điều khiển từ PC):** Quản lý bot, xem log trực tiếp và chỉnh sửa mã nguồn trên trình duyệt máy tính qua Wi-Fi với mã PIN an toàn.
- 📦 **Kho mẫu BotHub:** Hơn 26 mẫu bot dựng sẵn (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Trình thu thập dữ liệu và bot AI).
- 🗄️ **Trình duyệt SQLite tích hợp:** Xem trực tiếp cơ sở dữ liệu bên trong ứng dụng mà không lo lỗi tràn bộ nhớ (OOM).
- 🔍 **Giám sát thời gian thực:** Biểu đồ tốc độ mạng di động và Wi-Fi, lưu lượng dữ liệu từng bot, mức tiêu thụ RAM và CPU.
- 🌍 **Hỗ trợ 24 ngôn ngữ:** Giao diện được bản địa hóa hoàn toàn bao gồm cả các ngôn ngữ viết từ phải sang trái (RTL).
- 🔒 **Bảo mật và cách ly:** Két lưu trữ biến môi trường `.env`, ẩn token nhạy cảm trong nhật ký và khóa sinh trắc học vân tay.

---

## 🚀 Bắt đầu nhanh

1. **Tải APK:** Tải phiên bản mới nhất từ mục [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest).
2. **Cài đặt:** Cài đặt file `PyBionic-Runner-v2.2.0-arm64.apk` trên thiết bị Android 8.0+ (ARM64).
3. **Cấp quyền:** Cho phép thông báo và tắt tối ưu hóa pin để đảm bảo ứng dụng chạy 24/7 không bị gián đoạn.
4. **Chạy bot đầu tiên:** Vào tab **BotHub**, chọn mẫu bot, nhập mã Token của bạn và nhấn **▶ Chạy**.
5. **Điều khiển từ máy tính:** Mở **Cài đặt** ➔ **Web Dashboard**, truy cập địa chỉ IP hiển thị trên trình duyệt PC và nhập mã PIN.

---

## 🤖 Hướng dẫn kỹ thuật cho Trí tuệ Nhân tạo (LLM Reference)

PyBionic được thiết kế tối ưu cho trợ lý AI lập trình và triển khai bot tự động. Tài liệu đầy đủ: [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Giấy phép & Tác giả

- Phát hành dưới giấy phép mã nguồn mở **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Tác giả: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
