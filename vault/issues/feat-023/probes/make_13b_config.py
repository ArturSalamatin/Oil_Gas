"""FEAT-023: конфиг примера 13b из конфига 12 — меняется только time.history.

60 интервалов по 43200 с (запись каждые 0.5 сут). Сутки d = 1..30 —
интервалы 2d-1 и 2d: нечётные сутки p_wf = 6 МПа, чётные 10.75 МПа =
(6 + 15.5)/2 (решение пользователя 2026-09-28). Остальное — копия конфига 12.

Необязательный аргумент — каталог numerical_solver, куда писать (реализация
шла в git worktree .worktrees/feat-023, а этот файл лежит в vault/issues
основного каталога, в .gitignore). Без аргумента — numerical_solver рядом с
vault/ этого файла.

Запуск (из numerical_solver нужного дерева):
    <venv>\\Scripts\\python <путь>\\make_13b_config.py .
"""

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1
          else HERE.parents[3] / "numerical_solver")
EX = SOLVER / "examples"
SRC = EX / "12_large_drainage_radius"
DST = EX / "13b_pwf_alternating"

DST.mkdir(exist_ok=True)
for f in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
    shutil.copyfile(SRC / f, DST / f)

cfg = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
# Целые Па: 6 000 000 и 10 750 000 — без ошибок округления в тестах
cfg["time"]["history"] = [
    {"dt": 43200.0, "control": "pressure",
     "p_wf": 6_000_000.0 if d % 2 == 1 else 10_750_000.0}
    for d in range(1, 31) for _ in range(2)
]
(DST / "config.json").write_text(
    json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("записан", DST / "config.json")
