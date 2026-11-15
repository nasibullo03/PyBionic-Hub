"""Проверка каталога и ботов для CI (и для себя перед коммитом).

    python tools/check_bots.py            # каталог + импорт каждого бота без запуска
    python tools/check_bots.py --no-import  # только каталог (если зависимости не установлены)

Проверяет:
- catalog.json: уникальные id, есть папка и entryFile, поля fields корректны, title/description словари,
  zipUrl https + sha256 (64 hex) + version;
- locales.json каждого бота читается, у ключей есть ru и en;
- main.py каждого бота импортируется без BOT_TOKEN (ловит опечатки, забытые импорты, синтаксис).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "templates"
KNOWN_CATEGORIES = {"DOWNLOADERS", "MEDIA_STICKERS", "PRODUCTIVITY", "DISCORD_MULTI",
                    "DEVELOPER_TOOLS", "MODERATION", "UTILITIES", "AI_ASSISTANTS", "BUSINESS"}


def check_catalog() -> list[str]:
    err: list[str] = []
    cat = json.loads((T / "catalog.json").read_text(encoding="utf-8"))
    seen: set[str] = set()
    for b in cat.get("bots", []):
        bid = b.get("id", "")
        where = f"catalog[{bid or '?'}]"
        if not re.fullmatch(r"[a-z0-9_]+", bid):
            err.append(f"{where}: плохой id")
        if bid in seen:
            err.append(f"{where}: id повторяется")
        seen.add(bid)
        if b.get("category") not in KNOWN_CATEGORIES:
            err.append(f"{where}: неизвестная категория {b.get('category')!r} (добавьте в KNOWN_CATEGORIES и во вкладки приложения)")
        if not (T / bid / b.get("entryFile", "main.py")).is_file():
            err.append(f"{where}: нет файла templates/{bid}/{b.get('entryFile', 'main.py')}")
        keys = [f.get("key") for f in b.get("fields", [])]
        if len(keys) != len(set(keys)):
            err.append(f"{where}: повторяются ключи в fields")
        for f in b.get("fields", []):
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", f.get("key", "")):
                err.append(f"{where}: плохой ключ поля {f.get('key')!r}")
        for k in ("title", "description"):
            if k in b and not (isinstance(b[k], dict) and "en" in b[k]):
                err.append(f"{where}: {k} должен быть словарём языков с 'en'")
        if not str(b.get("zipUrl", "")).startswith("https://"):
            err.append(f"{where}: нет zipUrl — приложение не увидит бота из GitHub (tools/build_catalog.py)")
        if not re.fullmatch(r"[0-9a-f]{64}", str(b.get("sha256", ""))):
            err.append(f"{where}: нет sha256")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(b.get("version", ""))):
            err.append(f"{where}: version должен быть вида 1.2.3")
        # переменные, которые бот читает, должны быть в fields (иначе их негде задать в приложении)
        main = T / bid / b.get("entryFile", "main.py")
        if main.is_file():
            src = main.read_text(encoding="utf-8")
            if "ALLOWED_USER_IDS" in keys and "guard_bot" not in src and "ALLOWED" not in src.replace("ALLOWED_USER_IDS", ""):
                err.append(f"{where}: в fields есть ALLOWED_USER_IDS, но бот его не проверяет")
    for d in sorted(p for p in T.iterdir() if p.is_dir() and (p / "main.py").exists()):
        if d.name not in seen:
            err.append(f"templates/{d.name}: бот есть в папке, но нет в catalog.json")
    return err


def check_locales() -> list[str]:
    err = []
    for lp in sorted(T.glob("*/locales.json")):
        try:
            data = json.loads(lp.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            err.append(f"{lp.parent.name}/locales.json: не читается: {e}")
            continue
        for key, val in data.get("strings", {}).items():
            if isinstance(val, dict) and not ({"ru", "en"} <= set(val)):
                err.append(f"{lp.parent.name}/locales.json: у '{key}' нет ru или en")
    return err


def check_imports() -> list[str]:
    err = []
    tmp = tempfile.mkdtemp(prefix="pybionic_check_")
    os.environ.update({"BOT_TOKEN": "", "PROJECT_DATA_DIR": tmp, "WEB_PORT": "0"})
    threading.Thread.daemon = True
    for d in sorted(p for p in T.iterdir() if p.is_dir() and (p / "main.py").exists()):
        sys.path.insert(0, str(d))
        for name in ("i18n", "pybionic_core"):
            sys.modules.pop(name, None)
        try:
            spec = importlib.util.spec_from_file_location(f"bot_{d.name}", d / "main.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not callable(getattr(mod, "main", None)):
                err.append(f"{d.name}: нет функции main()")
        except ModuleNotFoundError as e:
            if e.name in ("i18n", "pybionic_core"):
                err.append(f"{d.name}: нет {e.name}.py в папке бота (tools/sync_shared.py)")
            else:
                print(f"  пропуск {d.name}: не установлен {e.name}")
        except Exception as e:  # noqa: BLE001
            err.append(f"{d.name}: импорт упал: {type(e).__name__}: {e}")
        finally:
            sys.path.remove(str(d))
    return err


def main() -> int:
    errors = check_catalog() + check_locales()
    if "--no-import" not in sys.argv:
        errors += check_imports()
    for e in errors:
        print("ОШИБКА:", e)
    if not errors:
        print("OK: каталог, переводы и импорт ботов в порядке")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
