# 🇰🇷 ⚡ PyBionic Runner — 안드로이드 기반 24/7 무중단 네이티브 Python 3.14 환경

[![Release](https://img.shields.io/badge/Release-v2.2.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | **🇰🇷 한국어** | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APK_다운로드-v2.2.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 프로젝트 소개

**PyBionic Runner**는 스마트폰에서 직접 네이티브 **Python 3.14 (aarch64 Bionic libc)**를 실행하는 Android 전용 고성능 자율 실행 런타임입니다. 사용하지 않는 공기계나 일상 스마트폰을 텔레그램 봇, FastAPI/Flask 웹 서버, 디스코드 봇, 백그라운드 자동화를 위한 조용하고 전력 효율적인 24/7 상시 가동 마이크로 서버로 변환합니다.

무거운 리눅스 에뮬레이터(Termux, PRoot, UserLAnd)와 달리, PyBionic은 안드로이드 시스템 라이브러리인 **Bionic libc**와 직접 링크되어 빌드되었습니다. 지연 없이 즉시 실행되며, **45MB 미만의 RAM**만 사용하고, **WakeLock 및 Doze 모드 예외 처리**로 백그라운드 강제 종료를 완벽히 방지하며, Wi-Fi 네트워크를 통해 PC 브라우저의 **Web Dashboard**에서 원격으로 제어할 수 있습니다.

---

## 🌟 핵심 기능

- 🐍 **네이티브 Python 3.14.10:** ARM64 Bionic libc 전용 빌드로 `asyncio`, `multiprocessing`, `ssl`, SQLite3 완벽 지원.
- 🔋 **24/7 무중단 호스팅:** CPU WakeLock을 유지하는 포그라운드 서비스, 배터리 온도 모니터링 및 절전 모드 차단.
- 🛡️ **지능형 Watchdog:** 비정상 종료 또는 기기 재부팅 시 봇 자동 재시작 및 프로세스 트리 안전 정리.
- 🌐 **Web Dashboard (PC 제어):** Wi-Fi를 통해 PC 브라우저에서 봇 관리, 실시간 로그 확인 및 코드 편집 가능 (PIN 보안 인증).
- 📦 **BotHub 카탈로그:** 바로 실행 가능한 26개 이상의 봇 템플릿 내장 (Aiogram 3, Telebot, FastAPI, Flask, 스크래퍼 및 AI 봇).
- 🗄️ **내장 SQLite 브라우저:** 메모리 부족(OOM) 오류 없이 앱 내부에서 봇 데이터베이스를 직접 탐색.
- 🔍 **실시간 원격 측정:** 모바일 데이터 및 Wi-Fi 속도 그래프, 봇별 트래픽 분석, RAM 및 CPU 사용률 모니터링.
- 🌍 **24개 언어 지원:** RTL(우측 정렬) 언어를 포함한 완벽한 다국어 인터페이스 지원.
- 🔒 **보안 및 격리:** `.env` 보안 키 금고, 로그 내 토큰 자동 마스킹 및 생체 지문 잠금.

---

## 🚀 빠른 시작

1. **APK 다운로드:** [GitHub Releases](https://github.com/nasibullo03/PyBionic/releases/latest)에서 최신 APK를 다운로드합니다.
2. **설치:** Android 8.0 이상(ARM64) 기기에 `PyBionic-Runner-v2.2.0-arm64.apk`를 설치합니다.
3. **권한 설정:** 알림 권한을 허용하고 24/7 상시 작동을 위해 배터리 최적화를 비활성화합니다.
4. **첫 봇 실행:** 하단 **BotHub** 탭에서 템플릿을 선택하고 토큰을 입력한 후 **▶ 실행**을 누릅니다.
5. **PC에서 제어:** **설정** ➔ **Web Dashboard**로 이동하여 PC 브라우저에 표시된 IP를 입력하고 PIN 코드를 입력합니다.

---

## 🤖 AI 에이전트 및 대규모 언어 모델 참고 사항 (LLM Reference)

PyBionic은 AI 도우미가 자율적으로 코드를 작성하고 배포할 수 있도록 최적화되었습니다. 자세한 사양은 [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)를 참조하세요.

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 라이선스 및 개발자

- **GNU Affero General Public License v3.0 (AAGPL-3.0)**에 따라 배포됩니다. 개발자: **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
