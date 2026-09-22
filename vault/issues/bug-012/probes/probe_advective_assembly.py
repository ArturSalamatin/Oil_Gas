"""Прогон плана в коде: адвективная сборка на существующих сценариях (аудит BUG-012).

Проверяет, что целевые формулы плана (шаг 1 и шаг 2 этапа I) дают:
  1. диагональное преобладание b > |a| + |c| в тех же сценариях, что
     существующие тесты TestAssembleTridiag (tests/test_energy.py:940, :980);
  2. запас преобладания РОВНО cap_j — усиленное утверждение плана;
  3. b_дивергентная − b_адвективная == D_j на внутренних ячейках;
  4. корректность при N = 1 (одна ячейка, обе грани граничные) — случай,
     для которого план требует отдельного разбора (в коде три ветки `if N > 1`);
  5. a[0] = 0 и c[N-1] = 0 сохраняются.

Рабочий код НЕ правится: адвективные коэффициенты собираются локально по
формулам плана из Φ⁺/Φ⁻, полученных методом решателя.

Параметры и конструкторы взяты из tests/test_energy.py, чтобы сценарии
совпадали с существующими тестами.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python ..\\vault\\issues\\bug-012\\probes\\probe_advective_assembly.py
"""

import sys
from pathlib import Path

import numpy as np

_SOLVER = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(_SOLVER))

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import (SimulationState, BoundaryConditions)
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.fluxes import compute_fluxes
from gpn_multiphase_solver.io.config import RockConfig
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver

# Параметры — как в tests/test_energy.py
R_WELL, R_EXT, H, K_PERM, PHI = 0.1, 50.0, 10.0, 1e-13, 0.2
P0, P_WF, T0, T_EXT, RS0 = 20e6, 10e6, 350.0, 350.0, 50.0
RHO_O_STD, RHO_G_STD, DT = 850.0, 0.85, 3600.0
CP_OIL, CP_GAS = 2000.0, 1000.0


def _make_pvt():
    return StandingFullPVT(
        rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD, T0=T0, Rs0=RS0,
        co_undersaturated=0.0, c_p_oil=CP_OIL, c_p_gas=CP_GAS,
        mu_JT_oil_val=0.0, mu_JT_gas_val=0.0, L_degas_val=0.0)


def _rock():
    return RockConfig(porosity=PHI, permeability=K_PERM, rho_cp_solid=1.25e6,
                      lambda_solid=1.5, lambda_oil=0.14, lambda_gas=0.04)


def _bc():
    return BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                              T_ext=T_EXT, Rs_ext=RS0)


def _log_pressure(grid):
    lr = np.log(grid.r_centers / R_WELL)
    return P_WF + (P0 - P_WF) * lr / np.log(R_EXT / R_WELL)


def advective_assemble(solver, N, dt, T_old, T_ext, rho_cp_eff,
                       Q_T_internal, Q_T_ext, Phi_plus, Phi_minus,
                       J_jt, Q_ad, Q_deg):
    """Адвективная сборка по формулам плана (этап I, шаги 1–2).

    a_j = -Q_T_{j-1/2} - Φ⁺_{j-1/2}                       (не изменилось)
    c_j = -Q_T_{j+1/2} + Φ⁻_{j+1/2}                       (не изменилось)
    b_j = cap + Q_T_L + Q_T_R + Φ⁺_{j-1/2} - Φ⁻_{j+1/2}   ← правка
    Забой:  забойная грань (f=0) вклада в b НЕ даёт (ГУ Неймана).
    Контур: b_{N-1} += Q_T_ext + Φ⁺_{N-1} - Φ⁻_N;  d += -Φ⁻_N·T_ext.
    """
    V = solver._grid.volumes
    a = np.zeros(N); b = np.zeros(N); c = np.zeros(N); d = np.zeros(N)
    cap = V * rho_cp_eff / dt

    for j in range(1, N - 1):
        Q_T_L = Q_T_internal[j - 1]
        Q_T_R = Q_T_internal[j]
        a[j] = -Q_T_L - Phi_plus[j]
        c[j] = -Q_T_R + Phi_minus[j + 1]
        b[j] = cap[j] + Q_T_L + Q_T_R + Phi_plus[j] - Phi_minus[j + 1]
        d[j] = cap[j] * T_old[j] + J_jt[j] + V[j] * (Q_ad[j] + Q_deg[j])

    # ── Забой j=0 ──
    Q_T_R0 = Q_T_internal[0] if N > 1 else 0.0
    a[0] = 0.0
    c[0] = (-Q_T_R0 + Phi_minus[1]) if N > 1 else 0.0
    b[0] = cap[0] + Q_T_R0
    if N > 1:
        # Правая грань ячейки 0 — внутренняя грань 1.
        b[0] += -Phi_minus[1]
    d[0] = cap[0] * T_old[0] + J_jt[0] + V[0] * (Q_ad[0] + Q_deg[0])

    # ── Контур j=N-1 ──
    Q_T_LN = Q_T_internal[-1] if N > 1 else 0.0
    if N > 1:
        a[N - 1] = -Q_T_LN - Phi_plus[N - 1]
        b[N - 1] = (cap[N - 1] + Q_T_LN + Q_T_ext
                    + Phi_plus[N - 1] - Phi_minus[N])
        d[N - 1] = (cap[N - 1] * T_old[N - 1] + Q_T_ext * T_ext
                    + (-Phi_minus[N]) * T_ext + J_jt[N - 1]
                    + V[N - 1] * (Q_ad[N - 1] + Q_deg[N - 1]))
    else:
        # N = 1: обе грани граничные. Забой вклада не даёт, контур — даёт
        # один раз. Φ⁺_{-1/2} отсутствует, остаётся -Φ⁻_N.
        b[0] += Q_T_ext - Phi_minus[N]
        d[0] += Q_T_ext * T_ext + (-Phi_minus[N]) * T_ext
    c[N - 1] = 0.0
    return a, b, c, d


def _setup(N, with_flow):
    grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
    pvt = _make_pvt()
    solver = TridiagEnergySolver(grid, pvt, _rock())
    p = _log_pressure(grid) if with_flow else np.full(N, P0)
    Sg = np.zeros(N); Rs = np.full(N, RS0); So = 1.0 - Sg
    T_old = np.full(N, T0)
    bc = _bc()
    if with_flow:
        st = SimulationState(p=p, Sg=Sg, Rs=Rs, T=T_old,
                             regime=np.full(N, 2, dtype=int), t=0.0)
        hyd = compute_fluxes(st, grid, pvt, CoreyRP(0.2, 0.05, 2.0, 2.0), bc)
        Q_o, Q_g = hyd.Q_o, hyd.Q_g
    else:
        Q_o = np.zeros(N + 1); Q_g = np.zeros(N + 1)
    props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)
    ext = solver._ext_properties(bc)
    Pp, Pm, _, _ = solver.compute_convective_coefficients(
        Q_o, Q_g, props['rho_o'], props['rho_g'],
        props['c_p_o'], props['c_p_g'], N, ext)
    QTi, QTe = solver.compute_conductive_transmissibility(props['lambda_eff'], N)
    return solver, props, Pp, Pm, QTi, QTe, T_old


def check(label, N, with_flow):
    solver, props, Pp, Pm, QTi, QTe, T_old = _setup(N, with_flow)
    z = np.zeros(N)
    args = (N, DT, T_old, T_EXT, props['rho_cp_eff'], QTi, QTe, Pp, Pm, z, z, z)
    a_d, b_d, c_d, d_d = solver.assemble_tridiag(*args)
    a_a, b_a, c_a, d_a = advective_assemble(solver, *args)

    slack_d = b_d - np.abs(a_d) - np.abs(c_d)
    slack_a = b_a - np.abs(a_a) - np.abs(c_a)
    cap = solver._grid.volumes * props['rho_cp_eff'] / DT
    Phi = Pp + Pm
    D = Phi[1:] - Phi[:-1]

    print(f"\n--- {label}   N={N}, поток={'да' if with_flow else 'нет'} ---")
    print(f"  Φ⁺ > 0 на гранях: {int(np.sum(Pp > 0))} из {N + 1}; "
          f"Φ⁻ < 0 на {int(np.sum(Pm < 0))}")
    print(f"  запас: дивергентная min = {slack_d.min():.6e}")
    print(f"         адвективная  min = {slack_a.min():.6e}")
    print(f"         min cap          = {cap.min():.6e}")
    print(f"  запас_адв == cap ?       {np.allclose(slack_a, cap, rtol=1e-11)}")
    print(f"  преобладание (адв.) ?    {bool(np.all(slack_a > 0))}")
    print(f"  a[0]==0 и c[N-1]==0 ?    {a_a[0] == 0.0 and c_a[N - 1] == 0.0}")
    if N > 2:
        inner = slice(1, N - 1)
        ok = np.allclose((b_d - b_a)[inner], D[inner], rtol=1e-10, atol=0)
        print(f"  (b_див − b_адв) == D_j (внутр.) ? {ok}")
        if not ok:
            print(f"     b_див-b_адв[1:3] = {(b_d - b_a)[1:3]}")
            print(f"     D_j[1:3]         = {D[1:3]}")
    print(f"  max|d_адв − d_див| = {np.max(np.abs(d_a - d_d)):.6e}")


if __name__ == "__main__":
    check("без потоков", 10, False)
    check("поток к скважине", 10, True)
    check("две ячейки", 2, True)
    check("одна ячейка", 1, False)
