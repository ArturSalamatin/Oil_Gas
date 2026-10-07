"""DEBT-028: насколько Q = G·B_up отличается от Q = T·(k_r/μ)_up·Δp в фикстурах test_fluxes.

После переноса шага «Q, u, m из G» в общую функцию compute_fluxes считает Q через G·B
(как адаптер), а эталон теста _compute_reference_face — через T·λ·Δp. Математически
это одно и то же; проба меряет округление против допусков тестов (rel=1e-14 в
TestOnePhasePerFace, 1e-12 в TestTwoPhaseAllFields).

Двухфазная фикстура — с p_wf = 6 МПа (шаг 1 плана), иначе забой — втекание.

Запуск из каталога numerical_solver:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-028\\probes\\q_from_g_roundoff.py
"""
import sys
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "tests"))
sys.path.insert(0, str(SOLVER_ROOT))

import test_fluxes as tf                                                     # noqa: E402
from gpn_multiphase_solver.bc import PressureControl                         # noqa: E402
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions  # noqa: E402


def setup(case):
    pvt = tf.StandingFullPVT(rho_o_std=tf.RHO_O_STD, rho_g_std=tf.RHO_G_STD,
                             T0=tf.T0, Rs0=tf.RS0, co_undersaturated=0.0)
    rp = tf.CoreyRP(S_or=tf.S_OR, S_gc=tf.S_GC, n_o=2.0, n_g=2.0,
                    kro_max=1.0, krg_max=0.8)
    if case == "1ph":
        grid = tf.LogRadialGrid(r_well=tf.R_WELL, R_ext=tf.R_EXT, h=tf.H,
                                N=tf.N_1PH, k=tf.K_PERM)
        log_ratio = np.log(grid.r_centers / tf.R_WELL) / np.log(tf.R_EXT / tf.R_WELL)
        p = tf.P_WF + (tf.P_EXT - tf.P_WF) * log_ratio
        n = tf.N_1PH
        state = SimulationState(p=p, Sg=np.zeros(n), Rs=np.full(n, tf.RS0),
                                T=np.full(n, tf.T0), regime=np.full(n, 2, dtype=int), t=0.0)
        bc = BoundaryConditions(well=PressureControl(tf.P_WF), p_ext=tf.P_EXT,
                                T_ext=tf.T0, Rs_ext=tf.RS0)
    else:
        grid = tf.LogRadialGrid(r_well=tf.R_WELL, R_ext=tf.R_EXT, h=tf.H,
                                N=tf.N_2PH, k=tf.K_PERM)
        p = np.array([8e6, 10e6, 13e6, 16e6, 19e6])
        Rs = pvt.Rs_eq(p)
        Rs[4] = tf.RS0
        state = SimulationState(p=p, Sg=np.array([0.3, 0.2, 0.1, 0.05, 0.0]), Rs=Rs,
                                T=np.full(5, tf.T0), regime=np.array([1, 1, 1, 1, 2]), t=0.0)
        bc = BoundaryConditions(well=PressureControl(6e6), p_ext=tf.P_EXT,
                                T_ext=tf.T0, Rs_ext=tf.RS0, Sg_ext=0.0)
    return pvt, rp, grid, state, bc


def bo_bg_up(pvt, state, bc, f, N):
    """B_o, B_g, ρ_o, ρ_g ячейки выше по потоку — правило общей функции (по Δp)."""
    p, Rs = state.p, state.Rs
    if f == 0:
        i = 0
    elif f == N:
        if p[N - 1] - bc.p_ext < 0:
            pa, ra = np.array([bc.p_ext]), np.array([bc.Rs_ext])
            return (pvt.Bo(pa, ra)[0], pvt.Bg(pa)[0], pvt.rho_o(pa, ra)[0], pvt.rho_g(pa)[0])
        i = N - 1
    else:
        i = f - 1 if p[f - 1] - p[f] >= 0 else f
    pa, ra = np.array([p[i]]), np.array([Rs[i]])
    return pvt.Bo(pa, ra)[0], pvt.Bg(pa)[0], pvt.rho_o(pa, ra)[0], pvt.rho_g(pa)[0]


for case in ("1ph", "2ph"):
    pvt, rp, grid, state, bc = setup(case)
    N = grid.N
    worst = {"Q_o": 0.0, "Q_g": 0.0, "u_o": 0.0, "u_g": 0.0, "m_o": 0.0, "m_g": 0.0}
    area = 2.0 * np.pi * grid.h * grid.r_faces
    for f in range(N + 1):
        ref = tf._compute_reference_face(pvt, rp, grid, state, bc, f)
        Bo, Bg, rho_o, rho_g = bo_bg_up(pvt, state, bc, f, N)
        Q_o = ref["G_o"] * Bo
        Q_g = ref["G_free_gas"] * Bg
        new = {"Q_o": Q_o, "Q_g": Q_g, "u_o": Q_o / area[f], "u_g": Q_g / area[f],
               "m_o": rho_o * Q_o, "m_g": rho_g * Q_g}
        for k, v in new.items():
            r = ref[k]
            if r != 0.0:
                worst[k] = max(worst[k], abs(v - r) / abs(r))
            elif v != 0.0:
                worst[k] = max(worst[k], float("inf"))
    print(case, {k: f"{v:.2e}" for k, v in worst.items()})
