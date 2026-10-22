"""Есть ли величина, у которой O(dt) остаётся настоящим порядком?

После BUG-007 невязка баланса - округления, её порядок отрицателен.
Но ошибка РАСЩЕПЛЕНИЯ (гидро замораживает T, тепло замораживает p, Sg)
никуда не делась и должна быть O(dt). Она проявляется не в невязке
баланса, а в САМОМ РЕШЕНИИ T.

Проверяем: сходится ли T(r) по dt с первым порядком, если за "точное"
взять решение на самом мелком шаге (метод Рунге без аналитики).
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


def run_T(example, dt):
    EnergyBalanceAccumulator.add_substep = _patched_substep
    EnergyBalanceAccumulator.add_accumulation = _patched_accum
    try:
        cfg = load_config(ROOT / "examples" / example / "config.json")
        cfg.output.log_level = "WARNING"
        cfg.time.dt_integration = dt
        sim, init = SimulatorFactory.from_config(cfg)
        hist = sim.run(init)
        return np.array(hist.states[-1].T, dtype=float)
    finally:
        EnergyBalanceAccumulator.add_substep = _orig_substep
        EnergyBalanceAccumulator.add_accumulation = _orig_accum


EXAMPLE = sys.argv[1] if len(sys.argv) > 1 else "03_standing_corey"
# Мельчайший шаг - опорное решение; остальные сравниваем с ним.
DTS = [3600.0, 1800.0, 900.0, 450.0]
REF_DT = 225.0

print(f"=== {EXAMPLE}: сходимость САМОГО РЕШЕНИЯ T по dt ===")
ref = run_T(EXAMPLE, REF_DT)
rows = []
for dt in DTS:
    T = run_T(EXAMPLE, dt)
    err = float(np.max(np.abs(T - ref)))
    rows.append((dt, err))
    print(f"  dt = {dt:7.1f} с   max|T - T_ref| = {err:.6e} K")

lg_dt = np.log([r[0] for r in rows])
lg_e = np.log([r[1] for r in rows])
order = np.polyfit(lg_dt, lg_e, 1)[0]
print(f"\nпорядок по всем {len(rows)} точкам: {order:+.3f}")

# Опорное решение само приближённое (REF_DT конечен), поэтому ближайшая
# к нему точка систематически ЗАНИЖАЕТ ошибку и завышает наклон.
# Исключаем её и смотрим, устойчив ли порядок.
order_trim = np.polyfit(lg_dt[:-1], lg_e[:-1], 1)[0]
print(f"порядок без ближайшей к эталону точки: {order_trim:+.3f}")

print("\nпопарные порядки:")
for i in range(len(rows) - 1):
    p = np.log(rows[i][1] / rows[i + 1][1]) / np.log(rows[i][0] / rows[i + 1][0])
    print(f"  {rows[i][0]:7.1f} -> {rows[i+1][0]:7.1f}: {p:+.3f}")
print("\n(ожидается ~ +1: расщепление гидро/тепло первого порядка)")
