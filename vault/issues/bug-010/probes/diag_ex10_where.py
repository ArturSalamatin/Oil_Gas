"""Где именно расходится T у примера 10: какая ячейка, какой момент.

p, Sg, Rs сходятся до 1e-10 отн., а T скачет на 0.1 K немонотонно по dt.
Смотрим: в какой ячейке максимум расхождения, растёт ли оно во времени,
и что там с числом Куранта / теплопроводностью.
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


def run(example, dt):
    cfg = load_config(ROOT / "examples" / example / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return hist, sim


EXAMPLE = "10_deep_degassing"
h_ref, sim = run(EXAMPLE, 225.0)
r = sim._grid.r_centers
T_ref = np.array([np.array(s.T, float) for s in h_ref.states])

for dt in (3600.0, 450.0, 900.0):
    h, _ = run(EXAMPLE, dt)
    T = np.array([np.array(s.T, float) for s in h.states])
    d = np.abs(T - T_ref)
    k_step, k_cell = np.unravel_index(np.argmax(d), d.shape)
    print(f"--- dt = {dt} с ---")
    print(f"  max|dT| = {d.max():.4e} K  в ячейке j={k_cell} (r={r[k_cell]:.4f} м), "
          f"запись {k_step} из {d.shape[0]-1}")
    print(f"  |dT| по записям (каждая 12-я): "
          + " ".join(f"{d[i].max():.1e}" for i in range(0, d.shape[0], 12)))
    print(f"  |dT| в последней записи по ячейкам 0..5: "
          + " ".join(f"{d[-1, j]:.1e}" for j in range(6)))
    print(f"  T[0] финальная: расчёт {T[-1,0]:.6f}, эталон {T_ref[-1,0]:.6f}")
