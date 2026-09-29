"""FEAT-022: конфиг примера 13a из конфига 12 — меняется только time.history.

30 интервалов по 43200 с (запись каждые 0.5 сут). Сутки k = 1..15 —
интервалы 2k-1 и 2k, p_wf = 15 - 0.6·k МПа (от p_b = 15 МПа, решение
пользователя 2026-09-28). Остальное — копия конфига 12.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-022\\probes\\make_13a_config.py
"""

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parents[3] / "numerical_solver" / "examples"
SRC = EX / "12_large_drainage_radius"
DST = EX / "13a_pwf_ramp_down"

DST.mkdir(exist_ok=True)
for f in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
    shutil.copyfile(SRC / f, DST / f)

cfg = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
# Целочисленная арифметика в Па: 15e6 - 0.6e6·k без ошибок округления
cfg["time"]["history"] = [
    {"dt": 43200.0, "control": "pressure", "p_wf": float(15_000_000 - 600_000 * k)}
    for k in range(1, 16) for _ in range(2)
]
(DST / "config.json").write_text(
    json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("записан", DST / "config.json")
