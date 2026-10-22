"""Какой ЧЛЕН уравнения энергии теряется на аномальных dt?

При 400 с и 360 с состояние (p, Sg, Rs) почти одинаково, а T отличается
на 0.47 K. Значит расходится источник. Смотрим накопленные члены баланса.
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

EX = sys.argv[1] if len(sys.argv) > 1 else "07_degassing_adiabatic_only"


def run_first(dt):
    cfg = load_config(ROOT / "examples" / EX / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    cfg.time.history = cfg.time.history[:1]
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return hist.balance[-1], np.array(hist.states[-1].T, float)


print(f"=== {EX}: накопленные члены за первый интервал (3600 с) ===")
keys = ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")
ref, T_ref = run_first(50.0)
print(f"{'dt':>6s} " + " ".join(f"{k:>13s}" for k in keys) + f" {'max|dT|':>10s}")
print(f"{'эталон':>6s} " + " ".join(f"{ref[k]:13.5e}" for k in keys)
      + f" {'—':>10s}")
for dt in (600.0, 450.0, 400.0, 360.0):
    bal, T = run_first(dt)
    print(f"{dt:6.0f} " + " ".join(f"{bal[k]:13.5e}" for k in keys)
          + f" {np.max(np.abs(T-T_ref)):10.3e}")

print("\nОтклонение от эталона, %:")
for dt in (600.0, 450.0, 400.0, 360.0):
    bal, _ = run_first(dt)
    row = []
    for k in keys:
        if abs(ref[k]) > 1e-6:
            row.append(f"{100*(bal[k]-ref[k])/abs(ref[k]):13.3f}")
        else:
            row.append(f"{'—':>13s}")
    print(f"{dt:6.0f} " + " ".join(row))
