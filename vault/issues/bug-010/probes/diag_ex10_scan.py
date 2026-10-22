"""Скан по dt: выброс при 450 с - единичный или их несколько?

Считаем только ПЕРВУЮ запись истории (первый интервал 3600 с) -
этого достаточно, ошибка вносится там. Быстро.
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


def run_first(dt):
    cfg = load_config(ROOT / "examples" / "10_deep_degassing" / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    cfg.time.history = cfg.time.history[:1]      # только первый интервал
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return np.array(hist.states[-1].T, float)


T_ref = run_first(50.0)
print("эталон dt = 50 с; первый интервал истории 3600 с")
print(f"{'dt':>7s} {'n_sub':>7s} {'max|dT|,K':>13s} {'отношение к ~O(dt)':>20s}")
base = None
for dt in (1800, 1200, 900, 720, 600, 514.28, 450, 400, 360, 327.27, 300,
           257.14, 225, 200, 180, 150, 120, 100):
    T = run_first(float(dt))
    e = float(np.max(np.abs(T - T_ref)))
    if base is None:
        base, base_dt = e, dt
    expect = base * dt / base_dt          # что дала бы чистая O(dt)
    flag = "  <<< ВЫБРОС" if e > 3 * expect else ""
    print(f"{dt:7.1f} {3600/dt:7.2f} {e:13.4e} {e/expect:20.2f}{flag}")
