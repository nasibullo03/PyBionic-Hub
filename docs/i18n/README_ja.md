# 🇯🇵 ⚡ PyBionic Runner — Android上で24時間365日常駐するネイティブPython 3.14環境

[![Release](https://img.shields.io/badge/Release-v1.0.0-00E5FF.svg?style=for-the-badge&logo=android&logoColor=black)](https://github.com/nasibullo03/PyBionic-Hub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.14.10_Bionic-FFD700.svg?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![License](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Select Language / Тилди тандоо / Выберите язык
[🇬🇧 English](../../README.md) | [🇷🇺 Русский](README_ru.md) | [🇹🇯 Тоҷикӣ](README_tg.md) | [🇺🇿 Oʻzbekcha](README_uz.md) | [🇹🇷 Türkçe](README_tr.md) | [🇮🇷 فارسی](README_fa.md) | [🇸🇦 العربية](README_ar.md) | [🇰🇿 Қазақша](README_kk.md)

[🇰🇬 Кыргызча](README_ky.md) | [🇺🇦 Українська](README_uk.md) | [🇦🇿 Azərbaycan](README_az.md) | [🇩🇪 Deutsch](README_de.md) | [🇫🇷 Français](README_fr.md) | [🇪🇸 Español](README_es.md) | [🇵🇹 Português](README_pt.md) | [🇮🇹 Italiano](README_it.md)

[🇵🇱 Polski](README_pl.md) | [🇮🇳 हिन्दी](README_hi.md) | [🇨🇳 简体中文](README_zh.md) | **🇯🇵 日本語** | [🇰🇷 한국어](README_ko.md) | [🇮🇩 Bahasa Indonesia](README_id.md) | [🇻🇳 Tiếng Việt](README_vi.md) | [🇹🇭 ไทย](README_th.md)

---

<p align="center">
  <a href="https://github.com/nasibullo03/PyBionic-Hub/releases/latest">
    <img src="https://img.shields.io/badge/🚀_PYBIONIC_APKをダウンロード-v1.0.0-00E5FF?style=for-the-badge&logo=android&logoColor=black" alt="Download APK" height="50">
  </a>
</p>

---

## 📖 プロジェクト概要

**PyBionic Runner** は、スマートフォン上でネイティブの **Python 3.14 (aarch64 Bionic libc)** を直接実行する、Android向けの高性能で自律的な実行ランタイムです。お使いのスマートフォンを、Telegramボット、FastAPI/Flask Webサーバー、Discordボット、バックグラウンド自動化スクリプトのための静かで省電力な24時間稼働のマイクロサーバーに変身させます。

従来の重いLinuxエミュレータ（Termux、PRoot、UserLAnd）とは異なり、PyBionicはAndroidのシステムライブラリである **Bionic libc** に直接リンクしてコンパイルされています。瞬時に起動し、**45MB未満のRAM** しか消費せず、**WakeLockとDozeモード除外** によってバックグラウンドでの強制終了を完全に防ぎ、ローカルWi-Fiを介してPCブラウザの **Web Dashboard** から快適に操作できます。

---

## 🌟 主な機能

- 🐍 **ネイティブ Python 3.14.10：** ARM64 Bionic libc向けに事前コンパイルされ、`asyncio`、`multiprocessing`、`ssl`、SQLite3を完全サポート。
- 🔋 **24時間365日の連続ホスティング：** CPU WakeLockを保持するフォアグラウンドサービス、バッテリー温度監視、Androidの省電力スリープ防止。
- 🛡️ **インテリジェントWatchdog：** クラッシュ時や端末再起動時にボットを自動再起動する障害復旧機能。
- 🌐 **Web Dashboard（PCからの操作）：** Wi-Fi経由でPCブラウザからボットの管理、リアルタイムログの閲覧、コードの編集が可能（PIN認証保護）。
- 📦 **BotHubカタログ：** すぐに使える26種類以上のボットテンプレート（Aiogram 3、Telebot、FastAPI、Flask、スクレイピング、AIボット）。
- 🗄️ **内蔵SQLiteブラウザ：** メモリ不足（OOM）を起こさずにアプリ内でボットのデータベースを直接閲覧・管理。
- 🔍 **リアルタイムテレメトリ：** モバイル通信・Wi-Fiの速度グラフ、ボットごとの通信量測定、RAMおよびCPU使用率監視。
- 🌍 **24言語対応：** RTL（右から左書き）を含む完全な多言語ローカライズインターフェース。
- 🔒 **セキュリティと分離：** `.env` 秘密情報金庫、ログ内の機密トークン自動マスキング、指紋・生体認証ロック。

---

## 🚀 クイックスタート

1. **APKのダウンロード：** [GitHub Releases](https://github.com/nasibullo03/PyBionic-Hub/releases/latest) から最新版APKを入手します。
2. **インストール：** Android 8.0以上（ARM64）の端末に `PyBionic-Runner-v1.0.0-arm64.apk` をインストールします。
3. **権限の許可：** 通知の許可を与え、常時稼働のために**バッテリー最適化の無効化**を承認します。
4. **ボットの起動：** 下部の **BotHub** タブを開き、テンプレートを選択してトークンを入力し、**▶ 起動** をタップします。
5. **PCから操作：** **設定** ➔ **Web Dashboard** を開き、PCのブラウザで表示されたIPにアクセスしてPINを入力します。

---

## 🤖 AIエージェント向け技術仕様 (LLM Reference)

PyBionicはAIアシスタントによる自律的なコード生成と展開に最適化されています。詳細な仕様書は [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md) をご覧ください。

- **AI Technical Reference:** [AI_SYSTEM_REFERENCE.md](../../AI_SYSTEM_REFERENCE.md)
- **Web UI Declaration:**
  ```python
  print("[PYBIONIC_WEB:8080]", flush=True)
  ```

---

## 📄 ライセンスと開発者

- **GNU Affero General Public License v3.0 (AAGPL-3.0)** に基づいて公開されています。開発者：**Nasibullo Khalilov** ([@nasibullo03](https://github.com/nasibullo03))。
