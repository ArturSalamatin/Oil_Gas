"""Пример 10: ошибка финальной T против dt на плотном ряду шагов.

Подозрение: немонотонность вызвана тем, что 225 с (эталон) и 450/900/1800
делят первый интервал истории (3600 с) НАЦЕЛО, а какие-то другие - нет.
Плюс сам эталон при dt=225 может быть не лучшим.
Берём длинный ряд и смотрим последовательность как есть.
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


def run(dt):
    cfg = load_config(ROOT / "examples" / "10_deep_degassing" / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return (np.array(hist.states[-1].T, float),
            np.array(hist.states[1].T, float))   # первая запись после старта


DTS = [3600.0, 1800.0, 1200.0, 900.0, 720.0, 600.0, 450.0, 360.0, 300.0]
REF = 100.0

T_ref_fin, T_ref_1 = run(REF)
print(f"эталон dt = {REF} с;  n_sub на интервал 3600 с = {3600/REF:.1f}")
print(f"{'dt':>8s} {'3600/dt':>9s} {'max|dT| фин':>14s} {'max|dT| 1-я зап.':>18s}")
for dt in DTS:
    Tf, T1 = run(dt)
    print(f"{dt:8.0f} {3600/dt:9.2f} {np.max(np.abs(Tf-T_ref_fin)):14.4e} "
          f"{np.max(np.abs(T1-T_ref_1)):18.4e}")
