# 🇵🇹 ⚡ PyBionic Runner — Execução autônoma de Python 3.14 no Android 24/7

[![Release](https://img.shields.io/badge/Release-v1.0.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | **🇵🇹 Português** | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_BAIXAR_PYBIONIC_APK-v1.0.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Sobre o Projeto

**PyBionic Runner** é um ambiente de execução autônomo e de alta performance para Android que executa **Python 3.14 nativo (aarch64 Bionic libc)** diretamente no seu smartphone. Ele transforma qualquer celular em um microservidor silencioso, eficiente e ativo 24/7 para bots do Telegram, APIs web com FastAPI/Flask, bots do Discord e automações em segundo plano.

Ao contrário de emuladores Linux pesados (Termux, PRoot, UserLAnd), o PyBionic é compilado diretamente com a biblioteca de sistema do Android — **Bionic libc**. Ele inicializa instantaneamente, usa menos de **45 MB de RAM**, é protegido contra encerramentos com **WakeLock e isenção do Doze Mode**, e pode ser gerenciado pelo computador via **Web Dashboard** local por Wi-Fi.

---

## 🌟 Principais Recursos

- 🐍 **Python 3.14.10 Nativo:** Compilado para ARM64 Bionic libc com suporte a `asyncio`, `multiprocessing`, `ssl` e SQLite3.
- 🔋 **Hospedagem 24/7 Contínua:** Serviço em primeiro plano com CPU WakeLock, monitoramento de temperatura e prevenção de suspensão.
- 🛡️ **Watchdog Inteligente:** Reinicialização automática de bots após falhas ou reinício do sistema.
- 🌐 **Web Dashboard (Controle via PC):** Interface de navegador protegida por PIN para gerenciar bots e editar código por Wi-Fi.
- 📦 **Catálogo BotHub:** Mais de 26 modelos prontos para uso (Aiogram 3, Telebot, FastAPI, Flask, Scrapers e bots de IA).
- 🗄️ **Visualizador SQLite Integrado:** Inspeção de bancos de dados diretamente no aplicativo sem risco de estouro de memória (OOM).
- 🔍 **Telemetria em Tempo Real:** Gráficos de velocidade de rede e Wi-Fi, tráfego individual por bot, consumo de RAM e CPU.
- 🌍 **24 Idiomas Suportados:** Interface totalmente traduzida, incluindo suporte a idiomas RTL.
- 🔒 **Segurança e Isolamento:** Cofre de chaves `.env`, ocultação de tokens em logs e bloqueio biométrico.

---

## 🚀 Início Rápido

1. **Baixe o APK:** Obtenha a versão mais recente em [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest).
2. **Instale:** Instale o `PyBionic-Runner-v1.0.0-arm64.apk` em seu dispositivo Android 8.0+ (ARM64).
3. **Permissões:** Conceda permissão de notificações e desative a otimização de bateria para operação ininterrupta.
4. **Inicie um Bot:** Vá até a aba **BotHub**, escolha um modelo, insira seu token e toque em **▶ Iniciar**.
5. **Controle pelo PC:** Acesse **Configurações** ➔ **Web Dashboard**, abra o IP no navegador do computador e digite o PIN.

---

## 🤖 Informações para Agentes de IA (LLM Reference)

O PyBionic foi planejado para desenvolvimento e operação autônoma por assistentes de IA. Veja a especificação técnica em [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Licença e Autor

- Distribuído sob a licença livre **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Desenvolvido por **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
