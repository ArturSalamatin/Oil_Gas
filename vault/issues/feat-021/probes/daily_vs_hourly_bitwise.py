"""Аудит FEAT-021: суточная запись истории не меняет счёт.

Утверждение плана (§6.1): при dt_integration = 3600 с история 3 × 86400 с и
72 × 3600 с дают одну и ту же последовательность подшагов, значит состояние на
3 сут совпадает побитово. Проверяем p, S_g, R_s, T и дебиты.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-021\\probes\\daily_vs_hourly_bitwise.py
"""

import copy
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def run(n_int, dt):
    cfg = load_config(SOLVER / "examples" / "11_degassing_at_boundary" / "config.json")
    cfg.geometry.R_ext, cfg.initial_conditions.p0 = 200.0, 15.5e6
    cfg.output.log_level = "ERROR"
    iv = copy.deepcopy(cfg.time.history[0])
    iv.dt = dt
    cfg.time.history = [copy.deepcopy(iv) for _ in range(n_int)]
    sim, init = SimulatorFactory.from_config(cfg)
    h = sim.run(init)
    return h.states[-1], h.well_data[-1]


s_d, w_d = run(3, 86400.0)
s_h, w_h = run(72, 3600.0)
for name in ("p", "Sg", "Rs", "T"):
    a, b = getattr(s_d, name), getattr(s_h, name)
    print(f"{name:3s}: побитово {np.array_equal(a, b)}, max|Δ| = {np.max(np.abs(a - b)):.3e}")
print(f"q_o: {w_d.q_o_std == w_h.q_o_std}, q_g: {w_d.q_g_std == w_h.q_g_std}")
