"""Аудит DEBT-019, раунд 2: что делает энергия при втекании через забой ПОСЛЕ BUG-012.

Исходная запись DEBT-019: в b[0] стоял член + Phi_plus[0] без парного
слагаемого в d[0], то есть при втекании энергия входила при T = 0 K.
BUG-012 перевёл сборку в адвективную форму, и забойная грань из b[0]
удалена (tridiag.py, assemble_tridiag, блок «ГУ забой»).

Проверка: однофазная добыча из test_energy.py (лог-профиль p, μ_JT = 0,
L = 0), поток на забойной грани подменён на ВТЕКАНИЕ (Q_o[0] = +|Q_o[0]|),
p_wf = p[0] (нет JT-перепада на грани). Однородное поле T = T0.
  - при старом дефекте T[0] уходила бы к 0 K: вклад Φ⁺_0·T_0 в b[0] без
    пары в d[0] — сток энергии порядка Φ⁺_0·T_0·dt / (V·ρc_p);
  - при адвективной форме с условием Неймана втекающий поток считается
    при T_0, и T не меняется (однородное поле, нет источников).
Сравнивается также сток, который дал бы старый член: Φ⁺_0·T0·dt/cap[0].

Запуск из каталога numerical_solver:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-019\\probes\\round2_energy_inflow.py
"""

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

_SOLVER_ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(_SOLVER_ROOT / "tests"))
sys.path.insert(0, str(_SOLVER_ROOT))

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

import test_energy as te                                         # noqa: E402
from gpn_multiphase_solver.fluxes import compute_fluxes          # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP            # noqa: E402
from gpn_multiphase_solver.state import SimulationState          # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402


def main():
    grid = te.LogRadialGrid(te.R_WELL, te.R_EXT, te.H, te.N, te.K_PERM)
    pvt = te._make_pvt(mu_JT_oil=0.0)
    p = te._log_pressure_profile(grid, te.P_WF, te.P0)
    state = SimulationState(p=p, Sg=np.zeros(te.N), Rs=np.full(te.N, te.RS0),
                            T=np.full(te.N, te.T0),
                            regime=np.full(te.N, 2, dtype=int), t=0.0)
    bc = te._bc(te.T_EXT)
    hydro = compute_fluxes(state, grid, pvt, CoreyRP(0.2, 0.05, 2.0, 2.0), bc)
    solver = TridiagEnergySolver(grid, pvt, te._rock())

    # Добыча: эталон
    T_prod = solver.solve(hydro, state, te.DT, bc)

    # Втекание: Q_o[0] > 0, p_wf = p[0] (без JT на забойной грани)
    Q_o = hydro.Q_o.copy()
    Q_o[0] = abs(Q_o[0])
    h_in = replace(hydro, Q_o=Q_o, p_wf=float(state.p[0]))
    T_in = solver.solve(h_in, state, te.DT, bc)

    # Что дал бы старый член + Phi_plus[0] в b[0] без пары в d[0]
    props = solver.compute_cell_properties(state.p, state.Sg, state.Rs,
                                           1.0 - state.Sg, state.T)
    rho_o, c_p_o = props['rho_o'], props['c_p_o']
    Phi0 = rho_o[0] * c_p_o[0] * Q_o[0]
    cap0 = grid.volumes[0] * props['rho_cp_eff'][0] / te.DT
    old_sink = Phi0 * te.T0 / (cap0 + Phi0)

    print(f"Q_o[0] при втекании:            {Q_o[0]:+.3e} м³/с")
    print(f"Φ⁺_0 / cap[0]:                  {Phi0 / cap0:.3e}")
    print(f"T[0] добыча − T0:               {T_prod[0] - te.T0:+.3e} К")
    print(f"T[0] втекание − T0:             {T_in[0] - te.T0:+.3e} К")
    print(f"max|T_in − T_prod|:             {np.max(np.abs(T_in - T_prod)):.3e} К")
    print(f"оценка старого дефекта ΔT[0]:   {-old_sink:+.3e} К (сток к 0 K)")


if __name__ == "__main__":
    main()
