"""Запуск всех plot_*.py скриптов в этой папке последовательно.

Запуск:
    cd method_of_moments
    .venv/Scripts/python scripts/plot_all.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def main():
    self = Path(__file__).resolve()
    scripts = sorted(s for s in SCRIPTS_DIR.glob("plot_*.py") if s.resolve() != self)
    python = sys.executable

    failed = []
    for script in scripts:
        print(f"\n{'═' * 60}")
        print(f"  {script.name}")
        print(f"{'═' * 60}")
        result = subprocess.run([python, str(script)], cwd=str(SCRIPTS_DIR.parent))
        if result.returncode != 0:
            failed.append(script.name)

    print(f"\n{'═' * 60}")
    if failed:
        print(f"Ошибки в: {', '.join(failed)}")
    else:
        print(f"Все {len(scripts)} скриптов выполнены успешно.")


if __name__ == "__main__":
    main()
