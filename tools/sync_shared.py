"""Копирует общие модули (i18n.py, pybionic_core.py) из templates/ в папку каждого бота.

Приложение PyBionic ставит бота как отдельную папку (из APK или ZIP), поэтому
общие файлы должны лежать внутри каждой папки. Правьте только templates/<файл>.

    python tools/sync_shared.py          # разложить копии
    python tools/sync_shared.py --check  # только проверить (для CI), код 1 при расхождении
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "templates"
SHARED = ["i18n.py", "pybionic_core.py", "pybionic_web.py"]


def bot_dirs() -> list[Path]:
    return sorted(p for p in ROOT.iterdir() if p.is_dir() and (p / "main.py").exists())


def main() -> int:
    check = "--check" in sys.argv
    bad = []
    for name in SHARED:
        src = (ROOT / name).read_bytes()
        for d in bot_dirs():
            dst = d / name
            if dst.exists() and dst.read_bytes() == src:
                continue
            # копию ядра кладём только тем ботам, что его импортируют
            # копии модулей кладём только тем ботам, что их импортируют
            if name != "i18n.py" and name[:-3] not in (d / "main.py").read_text(encoding="utf-8"):
                continue
            if check:
                bad.append(str(dst.relative_to(ROOT)))
            else:
                dst.write_bytes(src)
                print("обновлён", dst.relative_to(ROOT))
    if bad:
        print("Не совпадают с исходником (запустите tools/sync_shared.py):")
        for b in bad:
            print("  ", b)
        return 1
    if check:
        print("OK: общие файлы во всех ботах совпадают")
    return 0


if __name__ == "__main__":
    sys.exit(main())
