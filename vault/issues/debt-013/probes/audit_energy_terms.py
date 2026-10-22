"""Аудит BUG-010: какой член энергии даёт 0.48 К?

Пример 07: mu_JT = 0, L_degas = 0, lambda = 0. Значит в энергии
работают ТОЛЬКО два механизма:
  - конвекция (Phi из потоков Q, мгновенных при n+1)
  - адиабатический член Q_ad ∝ (p - p_old)/dt

J_jt тождественно 0 (mu_JT = 0), Q_deg тождественно 0 (L = 0),
кондукция 0 (lambda = 0).

Проверим напрямую: посчитаем оба члена для аномального dt=450
и для чистого dt=360, и сравним с эталоном dt=50 (просуммированным
по подшагам). Тот член, который у аномального шага выбивается,
и есть причина.
"""

import copy
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
_PROTO = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
for _p in (str(_PROTO), str(_ROOT / "examples")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402

CFG = _ROOT / "examples" / "07_degassing_adiabatic_only" / "config.json"


def build(dt):
    cfg = copy.deepcopy(load_config(CFG))
    cfg.time.dt_integration = float(dt)
    cfg.time.history = cfg.time.history[:1]
    return SimulatorFactory.from_config(cfg)


def march(dt, total=3600.0):
    """Пройти интервал шагами dt, накапливая вклады членов энергии.

    Возвращает (T_final, сумма V*Q_ad*dt, сумма конвективного вклада).
    """
    sim, state = build(dt)
    bc = sim._schedule.intervals[0].bc
    hydro, energy = sim._hydro, sim._energy
    grid = sim._grid
    V = grid.volumes

    n = int(round(total / dt))
    cum_ad = 0.0
    cum_conv = 0.0

    for _ in range(n):
        hr = hydro.solve(state, dt, bc)
        props = energy.compute_cell_properties(
            hr.state.p, hr.state.Sg, hr.state.Rs, 1.0 - hr.state.Sg, state.T)
        Q_ad = energy.compute_adiabatic(
            1.0 - hr.state.Sg, hr.state.Sg, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], props['mu_JT_o'], props['mu_JT_g'],
            hr.state.p, state.p, dt)
        cum_ad += float(np.sum(V * Q_ad) * dt)

        Phi_p, Phi_m, Phi_o, Phi_g = energy.compute_convective_coefficients(
            hr.Q_o, hr.Q_g, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], grid.N)
        # Полный конвективный вынос на забое за шаг (Вт * с = Дж)
        cum_conv += float(Phi_o[0] + Phi_g[0]) * dt

        T_new = energy.solve(hr, state, dt, bc)
        state = SimulationState(p=hr.state.p, Sg=hr.state.Sg, Rs=hr.state.Rs,
                                T=T_new, regime=hr.state.regime, t=hr.state.t)

    return state.T, cum_ad, cum_conv


def main():
    T_ref, ad_ref, conv_ref = march(50.0)
    print(f"{'dt':>6} {'max|dT|, К':>12} {'cum_ad, Дж':>14} {'откл, %':>9} "
          f"{'cum_conv, Дж':>15} {'откл, %':>9}")
    print("-" * 70)
    print(f"{50:6.0f} {0.0:12.4e} {ad_ref:14.6e} {0.0:9.2f} "
          f"{conv_ref:15.6e} {0.0:9.2f}")

    for dt in (600.0, 450.0, 400.0, 360.0):
        T, ad, conv = march(dt)
        dT = float(np.max(np.abs(T - T_ref)))
        d_ad = 100.0 * (ad - ad_ref) / abs(ad_ref)
        d_cv = 100.0 * (conv - conv_ref) / abs(conv_ref)
        print(f"{dt:6.0f} {dT:12.4e} {ad:14.6e} {d_ad:9.2f} "
              f"{conv:15.6e} {d_cv:9.2f}")


if __name__ == "__main__":
    main()
