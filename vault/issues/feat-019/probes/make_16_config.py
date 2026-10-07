"""FEAT-019: конфиг примера 16 — 15 сут добычи при 6 МПа, затем 15 сут останова.

Заготовка — конфиг примера 12 (меняется только time.history). Останов —
управление по дебиту q_oil = 0 (решение пользователя 2026-10-03), min_bhp
обязателен по конфигу, при q = 0 не действует. Записи: добыча — раз в сутки,
первые сутки останова — раз в час (восстановление давления), дальше — раз
в сутки. Краткая форма истории {duration, dt_out} (FEAT-018).

Запуск: python make_16_config.py [корень numerical_solver] [папка назначения]
"""

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[3] / "numerical_solver"
DST = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "cfg_16"
SRC = SOLVER / "examples" / "12_large_drainage_radius"

DAY, HOUR = 86400.0, 3600.0
SHUT = {"control": "rate", "q_oil": 0.0, "min_bhp": 101325.0}

raw = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
raw["time"]["history"] = [
    {"duration": 15 * DAY, "dt_out": DAY, "control": "pressure", "p_wf": 6.0e6},
    {"duration": DAY, "dt_out": HOUR, **SHUT},
    {"duration": 14 * DAY, "dt_out": DAY, **SHUT},
]
DST.mkdir(parents=True, exist_ok=True)
(DST / "config.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
for name in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
    shutil.copyfile(SRC / name, DST / name)
print(f"записан {DST / 'config.json'}")
