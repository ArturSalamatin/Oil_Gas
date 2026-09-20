"""Гипотеза: выброс при dt = 514.3 и 450 с вызван A-retry.

Адаптер при несходимости Ньютона дробит шаг вдвое и повторяет. Тепловой
шаг при этом, возможно, считается НЕ на тех подшагах - отсюда всплеск
ошибки T при нормальной гидродинамике.

Логируем каждый вызов hydro.solve: какой dt запрошен, какой фактически
использован (по числу вызовов внутри одного advance).
"""
import sys
from pathlib import Path

ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
for p in (str(ROOT), str(ROOT / "examples"),
          str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter

log = []
_orig = PrototypeHydroAdapter.solve


def patched(self, state, dt, bc):
    n_before = len(log)
    res = _orig(self, state, dt, bc)
    log.append(dt)
    return res


def run_first(dt):
    log.clear()
    cfg = load_config(ROOT / "examples" / "10_deep_degassing" / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    cfg.time.history = cfg.time.history[:1]
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return np.array(hist.states[-1].T, float), list(log)


PrototypeHydroAdapter.solve = patched
try:
    T_ref, _ = run_first(50.0)
    for dt in (600.0, 514.28, 450.0, 400.0):
        T, calls = run_first(dt)
        e = float(np.max(np.abs(T - T_ref)))
        print(f"dt = {dt:7.2f}:  вызовов hydro.solve = {len(calls):3d}, "
              f"max|dT| = {e:.4e}")
        print(f"            запрошенные dt: {sorted(set(calls))}")
finally:
    PrototypeHydroAdapter.solve = _orig
