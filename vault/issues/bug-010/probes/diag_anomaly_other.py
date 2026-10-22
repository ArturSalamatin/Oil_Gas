"""Аномалия dt=450 — только у примера 10 или есть у других?

Пример 10 единственный с lambda != 0. Проверяем тот же скан на 03
(Standing, lambda=0) и 09 (разгазирование + скрытая теплота, lambda=0).
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


def run_first(example, dt):
    cfg = load_config(ROOT / "examples" / example / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    cfg.time.history = cfg.time.history[:1]
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return np.array(hist.states[-1].T, float)


DTS = [1800, 1200, 900, 720, 600, 450, 400, 360, 300, 225, 180, 150]

for ex in (sys.argv[1:] or ["03_standing_corey", "09_degassing_latent_heat",
                            "10_deep_degassing"]):
    print(f"\n=== {ex} ===")
    T_ref = run_first(ex, 50.0)
    base = None
    print(f"{'dt':>7s} {'n_sub':>6s} {'max|dT|,K':>13s} {'к тренду':>10s}")
    for dt in DTS:
        T = run_first(ex, float(dt))
        e = float(np.max(np.abs(T - T_ref)))
        if base is None:
            base, base_dt = e, dt
        ratio = e / (base * dt / base_dt)
        flag = "  <<<" if ratio > 3 else ""
        print(f"{dt:7d} {3600/dt:6.2f} {e:13.4e} {ratio:10.2f}{flag}")
