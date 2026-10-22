"""BUG-020, механизм М1: коэффициенты запаса забойной ячейки по S_g при разных давлениях.

Запас на единицу порового объёма двухфазной ячейки: нефть S_o/B_o, газ
S_o R_s/B_o + S_g/B_g (R_s = R_s^sat(p)). Производные по S_g при фиксированном p:
нефть -1/B_o, газ 1/B_g - R_s/B_o (м³ст на м³ пор). Чем меньше газовый
коэффициент, тем большее |dS_g| нужно линеаризации, чтобы «уложить» приток газа.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\cell0_storage.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

cfg = load_config(SOLVER / "examples" / "20_rs300_cooling" / "config.json")
cfg.output.log_level = "ERROR"
sim, _ = SimulatorFactory.from_config(cfg)
pvt = sim._hydro._model.pvt
print("p, бар | R_s^sat | B_o | B_g | 1/B_g | R_s/B_o | газ: 1/B_g - R_s/B_o | нефть: 1/B_o")
for p in (50.9, 100.0, 150.0, 200.0, 250.0, 300.0):
    pa = np.array([p])
    rs = pvt.rs_sat(pa)
    bo = pvt.bo(pa, rs)
    bg = pvt.bg(pa)
    print(f"{p:6.1f} | {rs[0]:7.2f} | {bo[0]:.4f} | {bg[0]:.5f} | {1/bg[0]:7.2f} | {rs[0]/bo[0]:7.2f} | "
          f"{1/bg[0] - rs[0]/bo[0]:8.2f} | {1/bo[0]:.4f}")
