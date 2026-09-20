"""Профиль T при аномальном и чистом dt: локальный выброс или сдвиг?

Интегральные члены баланса гладкие, а max|dT| скачет в 18 раз -
значит дело в РАСПРЕДЕЛЕНИИ. Печатаем профиль T(r) и dT(r).
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

EX = "07_degassing_adiabatic_only"


def run_first(dt):
    cfg = load_config(ROOT / "examples" / EX / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    cfg.time.history = cfg.time.history[:1]
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return np.array(hist.states[-1].T, float), np.array(hist.states[-1].Sg, float), sim


T_ref, Sg_ref, sim = run_first(50.0)
r = sim._grid.r_centers
T400, Sg400, _ = run_first(400.0)
T360, Sg360, _ = run_first(360.0)

print(f"{'j':>3s} {'r,м':>8s} {'Sg':>11s} | {'T эталон':>11s} "
      f"{'T@400':>11s} {'dT@400':>9s} | {'T@360':>11s} {'dT@360':>9s}")
for j in range(0, 32):
    print(f"{j:3d} {r[j]:8.4f} {Sg_ref[j]:11.4e} | {T_ref[j]:11.5f} "
          f"{T400[j]:11.5f} {T400[j]-T_ref[j]:+9.4f} | "
          f"{T360[j]:11.5f} {T360[j]-T_ref[j]:+9.4f}")
