"""DEBT-063, проба: итог баланса энергии всех примеров — центры exp<ln r> и √.

Сводная таблица examples/README.md («баланс энергии») и README примеров
приводят на конец расчёта ΔE, член теплопроводности и относительную
невязку (examples/energy_balance.compute_balance). Проба печатает их для
обеих формул центров (подмена функции центров в log_radial).

Запуск из numerical_solver/:  .venv\\Scripts\\python -u ..\\vault\\issues\\debt-063\\probes\\energy_all.py
"""

import logging
import sys
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "examples"))
sys.path.insert(0, str(SOLVER / "tests"))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import numpy as np

import gpn_multiphase_solver.grid.log_radial as lr
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from energy_balance import compute_balance
from test_examples import ALL_EXAMPLES, EXAMPLES_DIR

# После DEBT-063 функции нет (центры √ в конструкторе) — тогда один расчёт
# текущим кодом, он же печатается в оба столбца
ORIG = getattr(lr, "_cell_centers_mass", None)
VARIANTS = (False, True) if ORIG is not None else (False,)

print(f"{'пример':28s} {'ΔE: exp → √':>26s} {'теплопроводность: exp → √':>28s} "
      f"{'отн. невязка: exp → √':>24s}")
for name in ALL_EXAMPLES:
    out = []
    for sq in VARIANTS:
        if ORIG is not None:
            lr._cell_centers_mass = (lambda a, b: np.sqrt(a * b)) if sq else ORIG
        try:
            cfg = load_config(EXAMPLES_DIR / name / "config.json")
            sim, init = SimulatorFactory.from_config(cfg)
            logging.disable(logging.INFO)
            h = sim.run(init)
            logging.disable(logging.NOTSET)
        finally:
            if ORIG is not None:
                lr._cell_centers_mass = ORIG
        b = compute_balance(h, None, None)
        out.append((b["delta_E"][-1], b["cum_cond"][-1], b["rel_residual"][-1]))
    (e0, c0, r0), (e1, c1, r1) = out[0], out[-1]
    print(f"{name:28s} {e0:+.4e} → {e1:+.4e}   {c0:+.4e} → {c1:+.4e}   "
          f"{r0:.1e} → {r1:.1e}")
