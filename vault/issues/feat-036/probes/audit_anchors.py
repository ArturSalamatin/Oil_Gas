"""Аудит 1 FEAT-036: каждое «было» edits.py — ровно одно вхождение в файле HEAD основного каталога.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-036/probes/audit_anchors.py
"""

import runpy
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
edits = runpy.run_path(str(HERE / "plan_code" / "edits.py"))["EDITS"]
head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                      text=True, check=True).stdout.strip()
bad = 0
for rel, pairs in edits.items():
    # Файл из git HEAD, а не с диска: рабочий каталог может нести чужие незакоммиченные правки
    text = subprocess.run(["git", "show", f"HEAD:numerical_solver/{rel}"], cwd=ROOT,
                          capture_output=True, check=True).stdout.decode("utf-8")
    for i, (old, new) in enumerate(pairs, 1):
        n = text.count(old)
        if n != 1:
            bad += 1
            print(f"{rel} пара {i}: вхождений {n}: {old[:80]!r}")
        text = text.replace(old, new)
print(f"HEAD {head}: файлов {len(edits)}, пар {sum(len(p) for p in edits.values())}, "
      f"с ошибкой {bad}")
