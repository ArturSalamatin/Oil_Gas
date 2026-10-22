"""DEBT-060, проба: в каких точках test_val001::test_pressure_log_profile сравнивает давление.

Прототип считает давление в своих центрах √(r_{j-1/2}·r_{j+1/2}), тест строит
эталон в центрах LogRadialGrid (eq:cell_center). Проба меряет ошибку p
относительно точного профиля в обоих наборах точек и разницу самих эталонов.

Запуск из numerical_solver/:  .venv\\Scripts\\python ..\\vault\\issues\\debt-060\\probes\\val001_centers.py
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

R_WELL, R_EXT, P_EXT, P_WF = 0.1, 50.0, 20e6, 15e6


def p_exact(r):
    """Стационарный профиль Дюпюи."""
    return P_WF + (P_EXT - P_WF) * np.log(r / R_WELL) / np.log(R_EXT / R_WELL)


config = load_config(SOLVER / "configs" / "val001.json")
sim, initial = SimulatorFactory.from_config(config)
history = sim.run(initial)
p = history.states[-1].p

faces = sim._grid.r_faces
r_ours = sim._grid.r_centers
r_geo = np.sqrt(faces[:-1] * faces[1:])           # центры прототипа

err_ours = np.max(np.abs(p / p_exact(r_ours) - 1.0))
err_geo = np.max(np.abs(p / p_exact(r_geo) - 1.0))
ref_gap = np.max(np.abs(p_exact(r_ours) / p_exact(r_geo) - 1.0))

print(f"N = {sim._grid.N}, t_end = {history.times[-1] / 86400:.3f} сут")
print(f"max |p/p_exact(r_ours) - 1| = {err_ours:.3e}   (как в тесте)")
print(f"max |p/p_exact(r_geo)  - 1| = {err_geo:.3e}   (центры прототипа)")
print(f"max |p_exact(r_ours)/p_exact(r_geo) - 1| = {ref_gap:.3e}   (разница эталонов)")
