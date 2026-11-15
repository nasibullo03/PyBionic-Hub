# 🇪🇸 ⚡ PyBionic Runner — Entorno de ejecución de Python 3.14 en Android 24/7

[![Release](https://img.shields.io/badge/Release-v1.0.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | **🇪🇸 Español** | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_DESCARGAR_PYBIONIC_APK-v1.0.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Acerca del proyecto

**PyBionic Runner** es un entorno de ejecución autónomo y de alto rendimiento para Android que ejecuta **Python 3.14 nativo (aarch64 Bionic libc)** directamente en su teléfono inteligente. Convierte cualquier dispositivo Android en un microservidor silencioso, eficiente y activo 24/7 para bots de Telegram, aplicaciones web FastAPI/Flask, bots de Discord y tareas en segundo plano.

A diferencia de los emuladores pesados de Linux (Termux, PRoot, UserLAnd), PyBionic está compilado directamente contra **Bionic libc**, la biblioteca nativa de Android. Se inicia al instante, consume menos de **45 MB de RAM**, está protegido contra el cierre del sistema mediante **WakeLock y exención de Doze Mode**, y se puede controlar desde la PC a través de un **Web Dashboard** local por Wi-Fi.

---

## 🌟 Características principales

- 🐍 **Python 3.14.10 nativo:** Compilado para ARM64 Bionic libc con soporte completo para `asyncio`, `multiprocessing`, `ssl` y SQLite3.
- 🔋 **Alojamiento continuo 24/7:** Servicio en primer plano con CPU WakeLock, monitoreo térmico de batería y evasión del modo de reposo de Android.
- 🛡️ **Watchdog inteligente:** Reinicio automático de bots tras fallos o reinicio del dispositivo con políticas configurables.
- 🌐 **Web Dashboard (Control desde PC):** Gestión de bots, logs en tiempo real y edición de código desde el navegador mediante Wi-Fi con PIN.
- 📦 **Catálogo BotHub:** Más de 26 plantillas listas para usar (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Scrapers y bots de IA).
- 🗄️ **Visor SQLite integrado:** Inspección directa de bases de datos sin salir de la app y con protección contra falta de memoria (OOM).
- 🔍 **Telemetría en tiempo real:** Gráficos de velocidad de red y Wi-Fi, consumo de ancho de banda por bot, uso de RAM y CPU.
- 🌍 **24 idiomas disponibles:** Localización completa con soporte de derecha a izquierda (RTL).
- 🔒 **Seguridad y aislamiento:** Bóveda de credenciales `.env`, anonimización de tokens en registros y bloqueo biométrico.

---

## 🚀 Inicio rápido

1. **Descargue el APK:** Obtenga la última versión desde [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest).
2. **Instale:** Instale `PyBionic-Runner-v1.0.0-arm64.apk` en su dispositivo Android 8.0+ (ARM64).
3. **Permisos:** Conceda permiso de notificaciones y desactive la optimización de batería para operación 24/7.
4. **Ejecute un bot:** Vaya a **BotHub**, elija una plantilla, introduzca su token y pulse **▶ Ejecutar**.
5. **Control desde PC:** Vaya a **Ajustes** ➔ **Web Dashboard**, abra la IP en el navegador de su computadora e ingrese el PIN.

---

## 🤖 Guía técnica para Agentes de IA (LLM Reference)

PyBionic está preparado para el despliegue y desarrollo autónomo de código por asistentes de IA. Consulte la guía completa en [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Licencia y Autor

- Distribuido bajo licencia **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Desarrollado por **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
