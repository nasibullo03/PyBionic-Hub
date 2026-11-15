# 🇫🇷 ⚡ PyBionic Runner — Exécution autonome de Python 3.14 sur Android 24/7

[![Release](https://img.shields.io/badge/Release-v2.1.1-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | **🇫🇷 Français** | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | [🇯🇵 日本語](README_ja.md) | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_TÉLÉCHARGER_L'APK_PYBIONIC-v2.1.1-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 Présentation du projet

**PyBionic Runner** est un environnement d'exécution autonome et haute performance pour Android qui exécute nativement **Python 3.14 (aarch64 Bionic libc)** directement sur votre smartphone. Il transforme n'importe quel téléphone en un micro-serveur silencieux, économe en énergie et fonctionnant 24h/24 et 7j/7 pour les bots Telegram, les applications web FastAPI/Flask, les bots Discord et les automatisations en arrière-plan.

Contrairement aux émulateurs Linux lourds (Termux, PRoot, UserLAnd), PyBionic est directement compilé avec la bibliothèque système d'Android — **Bionic libc**. Il démarre instantanément, consomme moins de **45 Mo de RAM**, est protégé contre les arrêts du système grâce au **WakeLock et à l'exemption Doze Mode**, et se pilote depuis un PC via un **Web Dashboard** en Wi-Fi.

---

## 🌟 Fonctionnalités clés

- 🐍 **Python 3.14.10 natif :** Compilé pour ARM64 Bionic libc avec support complet de `asyncio`, `multiprocessing`, `ssl` et SQLite3.
- 🔋 **Hébergement continu 24/7 :** Service d'arrière-plan avec CPU WakeLock, surveillance de la température de batterie et contournement de la mise en veille.
- 🛡️ **Chien de garde intelligent (Watchdog) :** Redémarrage automatique des bots en cas de plantage ou de redémarrage du téléphone.
- 🌐 **Web Dashboard (Contrôle PC) :** Gestion des bots, consultation des logs en direct et édition de code depuis un navigateur via Wi-Fi avec code PIN.
- 📦 **Catalogue BotHub :** Plus de 26 modèles de bots prêts à l'emploi (Aiogram 3, Telebot, FastAPI + Uvicorn, Flask, Scrapers et bots IA).
- 🗄️ **Navigateur SQLite intégré :** Visualisation des bases de données directement dans l'application avec protection contre le manque de mémoire (OOM).
- 🔍 **Télémétrie en temps réel :** Graphiques de vitesse réseau et Wi-Fi, suivi de la bande passante par bot, statistiques RAM et processeur.
- 🌍 **24 langues supportées :** Interface entièrement traduite avec support des langues de droite à gauche (RTL).
- 🔒 **Sécurité et isolation :** Coffre-fort de clés secrètes `.env`, masquage des tokens dans les journaux et verrouillage biométrique.

---

## 🚀 Démarrage rapide

1. **Téléchargez l'APK :** Obtenez la dernière version sur [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest).
2. **Installez :** Installez `PyBionic-Runner-v2.1.1-arm64.apk` sur votre appareil Android 8.0+ (ARM64).
3. **Autorisations :** Autorisez les notifications et désactivez les optimisations de batterie pour un fonctionnement 24/7.
4. **Lancez un premier bot :** Allez dans l'onglet **BotHub**, choisissez un modèle, renseignez votre token et appuyez sur **▶ Démarrer**.
5. **Pilotez depuis votre PC :** Allez dans **Paramètres** ➔ **Web Dashboard**, ouvrez l'adresse IP dans votre navigateur et entrez le code PIN.

---

## 🤖 Informations pour les agents IA (LLM Reference)

PyBionic est entièrement optimisé pour la génération de code et le contrôle autonome par les assistants IA. Consultez le guide complet : [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md).

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 Licence et Auteur

- Distribué sous licence libre **GNU Affero General Public License v3.0 (AAGPL-3.0)**. Auteur et développeur : **Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03)).
