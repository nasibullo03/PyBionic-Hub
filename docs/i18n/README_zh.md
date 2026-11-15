# 🇨🇳 ⚡ PyBionic Runner — 安卓端 24/7 原生 Python 3.14 高性能运行环境

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | **🇨🇳 简体中文** | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_下载_PYBIONIC_APK-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 项目概述

**PyBionic Runner** 是一款专为 Android 打造的高性能自主执行环境，可直接在智能手机上原生运行 **Python 3.14 (aarch64 Bionic libc)**。它能将任何闲置或备用手机转变为安静、低功耗且 7×24 小时不间断运行的微型服务器，完美支持 Telegram 机器人、FastAPI/Flask Web 接口、Discord 机器人及各类后台自动化任务。

与笨重的 Linux 模拟器（Termux、PRoot、UserLAnd）不同，PyBionic 直接基于 Android 原生系统库 **Bionic libc** 编译。它毫秒级瞬间启动，内存占用低于 **45 MB RAM**，通过原生 **WakeLock 和电池深度睡眠白名单 (Doze Mode)** 彻底杜绝系统杀后台，并提供局域网 **Web Dashboard** 支持在电脑浏览器中进行远程控制。

---

## 🌟 核心特性

- 🐍 **原生 Python 3.14.10 引擎：** 专为 ARM64 Bionic libc 编译，完整支持 `asyncio`、`multiprocessing`、`ssl` 与 SQLite3。
- 🔋 **7×24 小时全天候托管：** 前台保活服务、CPU 唤醒锁持有、电池温度看门狗以及 Android 睡眠模式豁免。
- 🛡️ **智能 Watchdog 容灾机制：** 崩溃或手机重启后自动拉起，支持重试策略配置及进程树彻底清理。
- 🌐 **远程 Web 控制台 (PC 端控制)：** 通过局域网 Wi-Fi 在电脑浏览器中管理机器人、实时查看日志并在线编辑代码（PIN 码安全验证）。
- 📦 **BotHub 机器人商城：** 内置 26+ 款开箱即用的机器人模板（Aiogram 3、Telebot、FastAPI + Uvicorn、Flask、爬虫及 AI 助手）。
- 🗄️ **内置 SQLite 数据查看器：** 原生同步数据库表格查看器，具备内存防溢出 (Anti-OOM) 保护。
- 🔍 **实时运行遥测：** 蜂窝数据与 Wi-Fi 实时速率曲线、单个机器人流量统计、内存及 CPU 占用监控。
- 🌍 **支持 24 种语言：** 全球主流语言全量本地化界面，支持阿拉伯语及波斯语从右至左 (RTL) 显示。
- 🔒 **安全与隔离：** `.env` 环境变量安全保险箱、日志敏感令牌自动脱敏与硬件生物指纹锁。

---

## 🚀 快速上手

1. **下载安装包：** 前往 [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest) 下载最新版 APK。
2. **安装应用：** 在 Android 8.0+ (ARM64) 设备上安装 `PyBionic-Runner-v2.1.1-arm64.apk`。
3. **系统授权：** 允许发送通知并在弹窗中同意**关闭电池优化**以确保 7×24 小时稳定运行。
4. **启动首个机器人：** 点击底部的 **BotHub** 标签，选择机器人模板，填入 Token 或配置，点击 **▶ 运行**。
5. **电脑端管理：** 打开 **设置** ➔ **Web Dashboard**，在电脑浏览器中输入显示的 IP 并输入一次性 PIN 码。

---

## 🤖 人工智能与大模型参考规范 (LLM Reference)

PyBionic 针对 AI 助手编写和自主运行代码进行了深度优化。完整技术参考指南请阅读 [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)。

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 开源许可与作者

- 基于 **GNU 通用公共许可证第三版 (AGPL-3.0)** 开源。作者与开发者：**Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03))。
