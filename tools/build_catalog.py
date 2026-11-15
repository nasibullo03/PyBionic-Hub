"""Собирает ZIP каждого бота в dist/ и прописывает zipUrl / sha256 в templates/catalog.json.

Зачем: приложение PyBionic показывает бота из GitHub-каталога и предлагает обновление,
только если у записи есть zipUrl (https) и sha256. Без них правки в репо до людей не доходят.

    python tools/build_catalog.py           # собрать архивы и обновить каталог
    python tools/build_catalog.py --check   # проверка для CI: архивы и суммы совпадают с кодом

Правило: изменили бота — поднимите его "version" в catalog.json (1.1.0 → 1.1.1) и запустите скрипт.
Старые архивы не удаляются: у пользователей могут быть ссылки на них.
Проверка сравнивает содержимое архива по файлам (байты сжатия на разных ОС могут отличаться),
а sha256 в каталоге — с самим файлом в dist/.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
DIST = ROOT / "dist"
RAW_BASE = os.environ.get("HUB_RAW_BASE", "https://raw.githubusercontent.com/nasibullo03/PyBionic-Hub/main").rstrip("/")

SKIP_DIRS = {"data", "__pycache__", ".git", "storage", "downloads", "logs", ".secrets"}
SKIP_SUFFIX = {".pyc", ".db", ".sqlite", ".sqlite3", ".log"}
SKIP_NAMES = {".env", "config.json", ".DS_Store"}
TEXT_SUFFIX = {".py", ".json", ".txt", ".md", ".html", ".css", ".js"}
CRLF, LF = bytes([13, 10]), bytes([10])


def bot_files(bot_dir: Path) -> list[Path]:
    out = []
    for p in sorted(bot_dir.rglob("*")):
        rel = p.relative_to(bot_dir)
        if not p.is_file() or any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if p.suffix.lower() in SKIP_SUFFIX or p.name in SKIP_NAMES:
            continue
        out.append(p)
    return out


def expected_files(bot_id: str) -> dict[str, bytes]:
    """Что должно лежать в архиве: {bot_id/путь: байты}. Переводы строк приводим к LF."""
    bot_dir = TEMPLATES / bot_id
    out = {}
    for p in bot_files(bot_dir):
        data = p.read_bytes()
        if p.suffix.lower() in TEXT_SUFFIX:
            data = data.replace(CRLF, LF)
        out[f"{bot_id}/{p.relative_to(bot_dir).as_posix()}"] = data
    return out


def zip_files(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def build_zip(bot_id: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in expected_files(bot_id).items():
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return buf.getvalue()


def main() -> int:
    check = "--check" in sys.argv
    cat_path = TEMPLATES / "catalog.json"
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    changed = False
    if not check:
        DIST.mkdir(exist_ok=True)

    for entry in cat["bots"]:
        bid = entry["id"]
        if not (TEMPLATES / bid / entry.get("entryFile", "main.py")).exists():
            errors.append(f"{bid}: нет папки templates/{bid} или {entry.get('entryFile', 'main.py')}")
            continue
        version = entry.get("version") or "1.0.0"
        name = f"{bid}-{version}.zip"
        url = f"{RAW_BASE}/dist/{name}"
        zpath = DIST / name
        want = expected_files(bid)

        if zpath.exists():
            existing = zpath.read_bytes()
            if zip_files(existing) != want:
                errors.append(f"{bid}: код изменился, а dist/{name} старый — поднимите version в catalog.json "
                              f"и запустите tools/build_catalog.py")
                continue
            sha = hashlib.sha256(existing).hexdigest()
        elif check:
            errors.append(f"{bid}: нет dist/{name} — запустите tools/build_catalog.py")
            continue
        else:
            data = build_zip(bid)
            zpath.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            print(f"собран dist/{name} ({len(data) // 1024} КБ)")

        if entry.get("sha256") != sha or entry.get("zipUrl") != url or entry.get("version") != version:
            if check:
                errors.append(f"{bid}: zipUrl/sha256 в catalog.json не совпадают с dist/{name} — запустите tools/build_catalog.py")
                continue
            entry.update(zipUrl=url, sha256=sha, version=version)
            changed = True

    if changed:
        cat_path.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("catalog.json обновлён")
    for e in errors:
        print("ОШИБКА:", e)
    if errors:
        return 1
    if check:
        print(f"OK: {len(cat['bots'])} ботов, архивы и sha256 совпадают с кодом")
    return 0


if __name__ == "__main__":
    sys.exit(main())
