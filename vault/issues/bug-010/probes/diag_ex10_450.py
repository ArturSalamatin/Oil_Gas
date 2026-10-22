"""Что происходит при dt = 450 с у примера 10?

Ошибка на три порядка выше соседей (600 и 360 с). Смотрим первый шаг
истории: сколько ньютоновских подшагов, срабатывал ли A-retry,
и где в пространстве сидит расхождение.
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

retries = []
_orig = PrototypeHydroAdapter.solve


def patched(self, state, dt, bc):
    res = _orig(self, state, dt, bc)
    # сколько удвоений понадобилось - косвенно по факту вызова
    return res


def run(dt):
    cfg = load_config(ROOT / "examples" / "10_deep_degassing" / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return hist, sim


ref, sim = run(100.0)
r = sim._grid.r_centers
T_ref1 = np.array(ref.states[1].T, float)
p_ref1 = np.array(ref.states[1].p, float)
Sg_ref1 = np.array(ref.states[1].Sg, float)

print(f"{'dt':>6s} {'max|dT| 1-я':>13s} {'яч.':>5s} {'r,м':>8s} "
      f"{'max|dp|,Па':>12s} {'max|dSg|':>11s}")
for dt in (600.0, 450.0, 360.0):
    h, _ = run(dt)
    T1 = np.array(h.states[1].T, float)
    p1 = np.array(h.states[1].p, float)
    Sg1 = np.array(h.states[1].Sg, float)
    d = np.abs(T1 - T_ref1)
    j = int(np.argmax(d))
    print(f"{dt:6.0f} {d.max():13.4e} {j:5d} {r[j]:8.4f} "
          f"{np.max(np.abs(p1-p_ref1)):12.4e} {np.max(np.abs(Sg1-Sg_ref1)):11.4e}")

# профиль расхождения при 450 против 360
h450, _ = run(450.0)
h360, _ = run(360.0)
d450 = np.abs(np.array(h450.states[1].T, float) - T_ref1)
d360 = np.abs(np.array(h360.states[1].T, float) - T_ref1)
print("\nпрофиль |dT| на 1-й записи, ячейки 15..25:")
print("  j:    " + " ".join(f"{j:8d}" for j in range(15, 26)))
print("  450:  " + " ".join(f"{d450[j]:8.2e}" for j in range(15, 26)))
print("  360:  " + " ".join(f"{d360[j]:8.2e}" for j in range(15, 26)))
