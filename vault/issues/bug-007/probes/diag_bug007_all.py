"""BUG-007: измерение эффекта фикса на ВСЕХ примерах.

Сравнивает отн. невязку баланса при штатном (T^n) и исправленном (T^{n+1})
конвективном члене. Нужно для плана: эталоны в check_energy_balance_all.py
после фикса меняются, и их надо знать заранее.
"""
import sys
from pathlib import Path

ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
for p in (str(ROOT), str(ROOT / "examples"),
          str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
import energy_balance as eb

EXAMPLES = [
    "01_single_phase_no_jt", "02_single_phase_jt", "03_standing_corey",
    "04_table_table", "04a_high_gas_saturation", "05_standing_table_rp",
    "06_table_corey_rp", "07_degassing_adiabatic_only", "08_degassing_jt",
    "09_degassing_latent_heat", "10_deep_degassing", "11_degassing_at_boundary",
]

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


def run(example, fixed):
    if fixed:
        EnergyBalanceAccumulator.add_substep = _patched_substep
        EnergyBalanceAccumulator.add_accumulation = _patched_accum
    try:
        cfg = load_config(ROOT / "examples" / example / "config.json")
        cfg.output.log_level = "WARNING"
        sim, init = SimulatorFactory.from_config(cfg)
        hist = sim.run(init)
        bal = eb.compute_balance(hist, sim._grid, cfg)
        return abs(float(bal["rel_residual"][-1])), float(bal["cum_conv"][-1])
    finally:
        EnergyBalanceAccumulator.add_substep = _orig_substep
        EnergyBalanceAccumulator.add_accumulation = _orig_accum


print(f"{'пример':30s} {'штатно':>12s} {'фикс':>12s} {'выигрыш':>10s}")
print("-" * 68)
for ex in EXAMPLES:
    try:
        a, ca = run(ex, False)
        b, cb = run(ex, True)
        print(f"{ex:30s} {a:12.4e} {b:12.4e} {a/b:9.0f}x")
    except Exception as exc:
        print(f"{ex:30s} ОШИБКА: {type(exc).__name__}: {exc}")
