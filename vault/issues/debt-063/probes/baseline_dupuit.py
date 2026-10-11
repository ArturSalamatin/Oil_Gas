"""DEBT-063, проба: test_factory_standing_hydro::…Дюпюи — доля центров в rtol=1e-2.

Тест сверяет давление прототипа на configs/baseline.json с профилем Дюпюи
p_wf + (p0 − p_wf)·ln(r/r_w)/ln(R/r_w) в центрах LogRadialGrid. Проба
печатает max отн. отклонение в центрах LogRadialGrid (как в тесте) и в
центрах прототипа √(r_{j-1/2}·r_{j+1/2}) — точках, где давление посчитано.

Запуск из numerical_solver/:  .venv\\Scripts\\python ..\\vault\\issues\\debt-063\\probes\\baseline_dupuit.py
"""

import sys
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory

cfg = load_config(SOLVER / "configs" / "baseline.json")
sim, init = SimulatorFactory.from_config(cfg)
hist = sim.run(init)
g = sim._grid
p0, p_wf = cfg.initial_conditions.p0, cfg.time.history[-1].p_wf
rw, R = cfg.geometry.r_well, cfg.geometry.R_ext


def dupuit(r):
    return p_wf + (p0 - p_wf) * np.log(r / rw) / np.log(R / rw)


p = hist.states[-1].p
r_geo = np.sqrt(g.r_faces[:-1] * g.r_faces[1:])
print(f"N = {g.N}, интервалов {len(cfg.time.history)}, t_end = {hist.times[-1] / 86400:.2f} сут")
print(f"max |p/p_Дюпюи(r_GPN) − 1|  = {np.max(np.abs(p / dupuit(g.r_centers) - 1)):.3e} (как в тесте)")
print(f"max |p/p_Дюпюи(r_прот) − 1| = {np.max(np.abs(p / dupuit(r_geo) - 1)):.3e} (центры прототипа)")
print(f"max |p_Дюпюи(r_GPN)/p_Дюпюи(r_прот) − 1| = "
      f"{np.max(np.abs(dupuit(g.r_centers) / dupuit(r_geo) - 1)):.3e} (разница точек)")
