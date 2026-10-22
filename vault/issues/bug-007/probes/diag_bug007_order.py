"""BUG-007: что станет с порядком сходимости невязки по dt после фикса.

FEAT-016 трактовал невязку как ошибку расщепления O(dt) и опирался на
порядок 0.980 у примера 10. Если после фикса невязка падает до машинной
точности, то никакого O(dt) там нет — проверяем.
"""
import sys
from pathlib import Path

ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
for p in (str(ROOT), str(ROOT / "examples"),
          str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if p not in sys.path:
        sys.path.insert(0, p)

import copy
import numpy as np
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
import energy_balance as eb

_orig_substep = EnergyBalanceAccumulator.add_substep
_orig_accum = EnergyBalanceAccumulator.add_accumulation


def _patched_substep(self, hydro_result, state_prev, dt, props,
                     Phi_o, Phi_g, Q_T_ext, J_jt, Q_ad, Q_deg, T_ext):
    self._pending = (np.maximum(Phi_o, 0.0) + np.maximum(Phi_g, 0.0),
                     np.minimum(Phi_o, 0.0) + np.minimum(Phi_g, 0.0), dt, T_ext)
    conv_before = self.cum_conv
    _orig_substep(self, hydro_result, state_prev, dt, props, Phi_o, Phi_g,
                  Q_T_ext, J_jt, Q_ad, Q_deg, T_ext)
    self.cum_conv = conv_before


def _patched_accum(self, T_new, T_prev, rho_cp_eff, dt):
    _orig_accum(self, T_new, T_prev, rho_cp_eff, dt)
    Phi_plus, Phi_minus, dt_s, T_ext = self._pending
    N = self._grid.N
    T_left = np.concatenate(([T_new[0]], T_new))
    T_right = np.concatenate((T_new, [T_ext]))
    flux = Phi_plus * T_left + Phi_minus * T_right
    self.cum_conv += -(flux[N] - flux[0]) * dt_s


def run(example, dt_int, fixed):
    """dt_int — шаг ИНТЕГРИРОВАНИЯ; структура истории не меняется."""
    if fixed:
        EnergyBalanceAccumulator.add_substep = _patched_substep
        EnergyBalanceAccumulator.add_accumulation = _patched_accum
    try:
        cfg = load_config(ROOT / "examples" / example / "config.json")
        cfg.output.log_level = "WARNING"
        cfg.time.dt_integration = dt_int
        sim, init = SimulatorFactory.from_config(cfg)
        hist = sim.run(init)
        bal = eb.compute_balance(hist, sim._grid, cfg)
        return abs(float(bal["rel_residual"][-1]))
    finally:
        EnergyBalanceAccumulator.add_substep = _orig_substep
        EnergyBalanceAccumulator.add_accumulation = _orig_accum


EXAMPLE = sys.argv[1] if len(sys.argv) > 1 else "10_deep_degassing"
DTS = [3600.0, 900.0, 360.0]

print(f"=== {EXAMPLE}: невязка против dt_integration ===")
print(f"{'dt':>8s} {'штатно':>13s} {'фикс':>13s}")
rows = []
for dt in DTS:
    a = run(EXAMPLE, dt, False)
    b = run(EXAMPLE, dt, True)
    rows.append((dt, a, b))
    print(f"{dt:8.0f} {a:13.4e} {b:13.4e}")

for label, idx in (("штатно", 1), ("фикс", 2)):
    lg_dt = np.log([r[0] for r in rows])
    lg_e = np.log([r[idx] for r in rows])
    order = np.polyfit(lg_dt, lg_e, 1)[0]
    print(f"порядок {label}: {order:+.3f}")
