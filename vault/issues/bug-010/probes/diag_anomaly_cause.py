"""Аномалия ~0.48 K на табличном PVT: где она в пространстве и что там?

Аномальные dt: 1200, 720, 450, 400 (n_sub = 3, 5, 8, 9).
Чистые:        1800, 900, 600, 360, 300 (n_sub = 2, 4, 6, 10, 12).

Величина ~0.48 K одинакова у всех примеров и всех аномальных dt - значит
это не накопление, а попадание в какое-то ФИКСИРОВАННОЕ состояние.

Смотрим: в какой ячейке, что там с p относительно узлов таблицы PVT.
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
    s = hist.states[-1]
    return (np.array(s.T, float), np.array(s.p, float),
            np.array(s.Sg, float), np.array(s.Rs, float), sim)


T_ref, p_ref, Sg_ref, Rs_ref, sim = run_first(50.0)
r = sim._grid.r_centers

for dt in (600.0, 450.0, 400.0, 360.0):
    T, p, Sg, Rs, _ = run_first(dt)
    d = np.abs(T - T_ref)
    j = int(np.argmax(d))
    print(f"dt={dt:6.0f}  max|dT|={d.max():.4e} K  ячейка j={j} r={r[j]:.4f} м")
    print(f"          T={T[j]:.5f} эталон {T_ref[j]:.5f}   "
          f"p={p[j]/1e6:.5f} МПа эталон {p_ref[j]/1e6:.5f}")
    print(f"          Sg={Sg[j]:.6e} эталон {Sg_ref[j]:.6e}   "
          f"Rs={Rs[j]:.5f} эталон {Rs_ref[j]:.5f}")
    print(f"          max|dp|={np.max(np.abs(p-p_ref)):.3e} Па  "
          f"max|dSg|={np.max(np.abs(Sg-Sg_ref)):.3e}  "
          f"max|dRs|={np.max(np.abs(Rs-Rs_ref)):.3e}")
    print(f"          ячеек с газом: {int(np.count_nonzero(Sg>1e-12))} "
          f"(эталон {int(np.count_nonzero(Sg_ref>1e-12))})")
