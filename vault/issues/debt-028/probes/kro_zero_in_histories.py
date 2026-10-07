"""DEBT-028: есть ли в историях примеров ячейки с k_ro = 0 (S_g >= 1 - S_or).

Правило адаптера (up = f if G_o[f] < 0 else f-1) расходится с прототипом
(up = f-1 if dp >= 0 else f) только при G_o[f] = 0 и dp < 0, то есть при
k_ro = 0 в ячейке f. k_ro — табличная функция прототипа (для Corey —
таблица, построенная фабрикой), именно она обнуляет G_o.

Истории — сохранённые записи DEBT-033 (history_base, все 20 примеров);
промежуточные шаги между записями не видны.

Запуск из каталога numerical_solver:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-028\\probes\\kro_zero_in_histories.py
"""
import sys
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))

from gpn_multiphase_solver.io.config import load_config                          # noqa: E402
from gpn_multiphase_solver.factory import _create_relperm, _get_or_create_proto_rp  # noqa: E402

BASE = Path(__file__).resolve().parents[2] / "debt-033" / "probes" / "history_base"

for f in sorted(BASE.glob("*.npz")):
    cfg = load_config(SOLVER_ROOT / "examples" / f.stem / "config.json")
    rp = _get_or_create_proto_rp(_create_relperm(cfg))
    Sg = np.load(f)["Sg"]
    kro = rp.kro(Sg.ravel()).reshape(Sg.shape)
    # Наименьшая S_g, при которой табличная k_ro обращается в ноль
    s = np.linspace(0.0, 1.0, 100001)
    zero = rp.kro(s) <= 0.0
    sg_zero = float(s[np.argmax(zero)]) if zero.any() else float("nan")
    print(f"{f.stem:28s} записей {Sg.shape[0]:4d}  max Sg {Sg.max():.4f}  "
          f"Sg(k_ro=0) {sg_zero:.4f}  min k_ro {kro.min():.3e}  "
          f"ячеек с k_ro=0: {int(np.sum(kro <= 0.0))}")
