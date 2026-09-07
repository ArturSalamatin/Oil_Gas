"""Последовательный запуск всех примеров.

Каждый пример запускается отдельным процессом (subprocess) — изоляция
состояния matplotlib, sys.path и глобальных настроек солвера.

Не останавливается на первой ошибке: это набор демонстраций, а не конвейер
сборки. Если пользователь правил конфиг и сломал один пример, он должен
видеть, что остальные живы. Код возврата ≠ 0, если хоть один упал.

Запуск:
    python examples/run_all.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent


def find_examples() -> list[Path]:
    """Подпапки примеров: NN_имя с main.py внутри, отсортированные по номеру."""
    return sorted(
        d for d in EXAMPLES_DIR.iterdir()
        if d.is_dir() and (d / "main.py").is_file() and d.name[0].isdigit()
    )


def main() -> int:
    examples = find_examples()
    if not examples:
        print(f"В {EXAMPLES_DIR} не найдено ни одного примера.")
        return 1

    total = len(examples)
    failed: list[tuple[str, str]] = []   # (имя примера, хвост stderr)
    t_all = time.perf_counter()

    for i, example in enumerate(examples, start=1):
        label = f"[{i}/{total}] {example.name}"
        print(f"{label} ".ljust(48, "."), end=" ", flush=True)

        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(example / "main.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        dt = time.perf_counter() - t0

        if proc.returncode == 0:
            print(f"OK   ({dt:.1f} с)")
        else:
            print(f"ОШИБКА ({dt:.1f} с)")
            # Последние строки stderr — обычно там сообщение исключения.
            tail = "\n".join(
                (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
            )
            failed.append((example.name, tail))

    elapsed = time.perf_counter() - t_all

    print()
    if failed:
        print(f"Итог: {total - len(failed)} из {total} успешно, "
              f"{len(failed)} отказ(ов): "
              + ", ".join(name for name, _ in failed))
        for name, tail in failed:
            print(f"\n--- {name} ---")
            print(tail)
    else:
        print(f"Итог: все {total} примеров успешно.")
    print(f"Суммарное время: {elapsed:.1f} с")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
