"""Проверка гипотезы BUG-007: конвективный член баланса берёт T^n, а схема — T^{n+1}.

Схема неявная: Phi_plus/Phi_minus стоят в МАТРИЦЕ (tridiag.py:324-326, 341-344),
то есть умножаются на неизвестные T^{n+1}. Аккумулятор (balance.py:150-152)
умножает те же Phi на T_prev = T^n.

Здесь монкипатчим add_substep так, чтобы конвекция считалась по T^{n+1},
и сравниваем невязку баланса с текущей.
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

EXAMPLE = sys.argv[1] if len(sys.argv) > 1 else "03_standing_corey"


def run(deferred: bool):
    """deferred=True — конвекция по T^{n+1} (как в схеме), иначе штатно по T^n."""
    orig_add_substep = EnergyBalanceAccumulator.add_substep
    orig_add_accum = EnergyBalanceAccumulator.add_accumulation

    if deferred:
        def add_substep(self, hydro_result, state_prev, dt, props,
                        Phi_o, Phi_g, Q_T_ext, J_jt, Q_ad, Q_deg, T_ext):
            # сохраняем то, что нужно для отложенного конвективного члена
            self._pending = (np.maximum(Phi_o, 0.0) + np.maximum(Phi_g, 0.0),
                             np.minimum(Phi_o, 0.0) + np.minimum(Phi_g, 0.0),
                             dt, T_ext)
            conv_before = self.cum_conv
            orig_add_substep(self, hydro_result, state_prev, dt, props,
                             Phi_o, Phi_g, Q_T_ext, J_jt, Q_ad, Q_deg, T_ext)
            self.cum_conv = conv_before  # откатываем штатный вклад по T^n

        def add_accumulation(self, T_new, T_prev, rho_cp_eff, dt):
            orig_add_accum(self, T_new, T_prev, rho_cp_eff, dt)
            Phi_plus, Phi_minus, dt_s, T_ext = self._pending
            N = self._grid.N
            # тот же шаблон, но на НОВОМ слое — как в матрице СЛАУ
            T_left = np.concatenate(([T_new[0]], T_new))
            T_right = np.concatenate((T_new, [T_ext]))
            flux = Phi_plus * T_left + Phi_minus * T_right
            self.cum_conv += -(flux[N] - flux[0]) * dt_s

        EnergyBalanceAccumulator.add_substep = add_substep
        EnergyBalanceAccumulator.add_accumulation = add_accumulation

    try:
        cfg = load_config(ROOT / "examples" / EXAMPLE / "config.json")
        sim, intervals = SimulatorFactory.from_config(cfg)
        hist = sim.run(intervals)
        bal = eb.compute_balance(hist, sim._grid, cfg)
        return bal
    finally:
        EnergyBalanceAccumulator.add_substep = orig_add_substep
        EnergyBalanceAccumulator.add_accumulation = orig_add_accum


print(f"=== {EXAMPLE} ===")
a = run(deferred=False)
b = run(deferred=True)

print(f"{'':<14}{'штатно (T^n)':>18}{'по T^(n+1)':>18}")
for k in ("cum_conv", "delta_E", "residual", "rel_residual"):
    print(f"{k:<14}{a[k][-1]:>18.6e}{b[k][-1]:>18.6e}")
print(f"\nулучшение невязки: {abs(a['rel_residual'][-1]) / abs(b['rel_residual'][-1]):.1f}x")
