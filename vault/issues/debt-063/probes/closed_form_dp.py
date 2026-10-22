"""DEBT-063, проба: max|p_ана − p_чис| в README примеров — доля разницы центров.

README 03, 04, 04a, 12, 13a, 15 приводят max|p_ана − p_чис| — сверку
замкнутого решения (examples/closed_form.py::report_closed,
two_phase_analytics.py, раздел E) с расчётом на последней записи. Замкнутое
решение строится в точках grid.r_centers (exp<ln r>), а давление прототипа
посчитано в его центрах √(r_{j-1/2}·r_{j+1/2}). Гидродинамика от центров
LogRadialGrid не зависит (examples_shift.out.txt — побитово), поэтому один
расчёт и две точки построения аналитики: как сейчас и как после DEBT-063.

Запуск из numerical_solver/:  .venv\\Scripts\\python -u ..\\vault\\issues\\debt-063\\probes\\closed_form_dp.py
"""

import logging
import sys
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "examples"))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm
from closed_form import solve_closed

EXAMPLES = ["03_standing_corey", "04_table_table", "04a_high_gas_saturation",
            "12_large_drainage_radius", "13a_pwf_ramp_down", "15_oil_rate_ramp_up"]

print(f"{'пример':26s} {'N':>4s} {'d_p сейчас, кПа':>16s} {'d_p при √, кПа':>15s} "
      f"{'% депр. сейчас':>15s} {'% депр. при √':>14s}")
for name in EXAMPLES:
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    sim, init = SimulatorFactory.from_config(cfg)
    logging.disable(logging.INFO)          # журнал интервалов не нужен
    hist = sim.run(init)
    logging.disable(logging.NOTSET)
    g = sim._grid
    pvt, rp = sim._energy._pvt, _create_relperm(cfg)
    p_num = hist.states[-1].p
    out = []
    for r in (g.r_centers, np.sqrt(g.r_faces[:-1] * g.r_faces[1:])):
        cl = solve_closed(cfg, pvt, rp, r)
        dep = cfg.initial_conditions.p0 - cl["p_wf"]
        d_p = float(np.abs(cl["p"] - p_num).max())
        out.append((d_p, d_p / dep * 100))
    print(f"{name:26s} {g.N:4d} {out[0][0] / 1e3:16.2f} {out[1][0] / 1e3:15.2f} "
          f"{out[0][1]:15.3f} {out[1][1]:14.3f}")
