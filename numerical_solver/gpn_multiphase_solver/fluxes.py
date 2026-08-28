"""Вычисление потоков через грани: G, Q, u, m, Gm + upstream.

Eq. 8, 9, 24 problem_statement.tex. Конвенция: >0 = от скважины (рост r).
"""

import numpy as np

from .state import SimulationState, HydroResult, BoundaryConditions
from .grid.base import Grid
from .pvt.base import HydroPVT, RelPermModel


def compute_fluxes(state: SimulationState, grid: Grid,
                   pvt: HydroPVT, relperm: RelPermModel,
                   bc: BoundaryConditions) -> HydroResult:
    """Потоки через все грани при заданном состоянии.

    Не обновляет state — только вычисляет потоки.
    Возвращает HydroResult со state=state (без изменений).
    """
    N = grid.N
    p = state.p
    Sg = state.Sg
    Rs = state.Rs

    # PVT в центрах ячеек
    Bo = pvt.Bo(p, Rs)
    Bg = pvt.Bg(p)
    mu_o = pvt.mu_o(p, Rs)
    mu_g = pvt.mu_g(p)
    rho_o = pvt.rho_o(p, Rs)
    rho_g = pvt.rho_g(p)

    kro = relperm.kro(Sg)
    krg = relperm.krg(Sg)

    # Подвижности
    mob_o = kro / (mu_o * Bo)       # kro/(μo·Bo) — для G_o
    lam_o = kro / mu_o              # kro/μo — для Q_o
    mob_g = krg / (mu_g * Bg)       # krg/(μg·Bg) — для G_free_gas
    lam_g = krg / mu_g              # krg/μg — для Q_g

    # Забойное давление
    p_wf = bc.well.boundary_pressure(state, grid, pvt, relperm)

    # PVT на контуре (однофазная зона: Sg=0)
    p_ext_arr = np.array([bc.p_ext])
    Rs_ext_arr = np.array([bc.Rs_ext])
    Bo_ext = pvt.Bo(p_ext_arr, Rs_ext_arr)[0]
    mu_o_ext = pvt.mu_o(p_ext_arr, Rs_ext_arr)[0]
    rho_o_ext = pvt.rho_o(p_ext_arr, Rs_ext_arr)[0]
    kro_ext = relperm.kro(np.array([bc.Sg_ext]))[0]

    mob_o_ext = kro_ext / (mu_o_ext * Bo_ext)
    lam_o_ext = kro_ext / mu_o_ext

    # Массивы результатов
    G_o = np.empty(N + 1)
    G_g = np.empty(N + 1)
    G_free_gas = np.empty(N + 1)
    Q_o = np.empty(N + 1)
    Q_g = np.empty(N + 1)
    u_o = np.empty(N + 1)
    u_g = np.empty(N + 1)
    m_o = np.empty(N + 1)
    m_g = np.empty(N + 1)

    face_area = 2.0 * np.pi * grid.h * grid.r_faces

    # ── Внутренние грани (f = 1..N-1) ────────────────────────
    for f in range(1, N):
        dp = p[f - 1] - p[f]
        T_f = grid.trans_internal[f - 1]

        if dp >= 0:
            up = f - 1
        else:
            up = f

        G_o[f] = T_f * mob_o[up] * dp
        G_free_gas[f] = T_f * mob_g[up] * dp
        G_g[f] = T_f * (Rs[up] * mob_o[up] + mob_g[up]) * dp

        Q_o[f] = T_f * lam_o[up] * dp
        Q_g[f] = T_f * lam_g[up] * dp

        u_o[f] = Q_o[f] / face_area[f]
        u_g[f] = Q_g[f] / face_area[f]

        m_o[f] = rho_o[up] * Q_o[f]
        m_g[f] = rho_g[up] * Q_g[f]

    # ── Забой (f = 0) ────────────────────────────────────────
    dp_w = p_wf - p[0]
    up_w = 0

    G_o[0] = grid.trans_well * mob_o[up_w] * dp_w
    G_free_gas[0] = grid.trans_well * mob_g[up_w] * dp_w
    G_g[0] = grid.trans_well * (Rs[up_w] * mob_o[up_w] + mob_g[up_w]) * dp_w

    Q_o[0] = grid.trans_well * lam_o[up_w] * dp_w
    Q_g[0] = grid.trans_well * lam_g[up_w] * dp_w

    u_o[0] = Q_o[0] / face_area[0]
    u_g[0] = Q_g[0] / face_area[0]

    m_o[0] = rho_o[up_w] * Q_o[0]
    m_g[0] = rho_g[up_w] * Q_g[0]

    # ── Контур (f = N) ───────────────────────────────────────
    dp_e = p[N - 1] - bc.p_ext

    if dp_e >= 0:
        # Поток от скважины (нетипично): upstream = ячейка N-1
        mob_o_up_e = mob_o[N - 1]
        lam_o_up_e = lam_o[N - 1]
        mob_g_up_e = mob_g[N - 1]
        lam_g_up_e = lam_g[N - 1]
        Rs_up_e = Rs[N - 1]
        rho_o_up_e = rho_o[N - 1]
        rho_g_up_e = rho_g[N - 1]
    else:
        # Приток из контура (типично): upstream = контур
        mob_o_up_e = mob_o_ext
        lam_o_up_e = lam_o_ext
        mob_g_up_e = 0.0       # krg=0 на контуре (Sg=0)
        lam_g_up_e = 0.0
        Rs_up_e = bc.Rs_ext
        rho_o_up_e = rho_o_ext
        rho_g_up_e = 0.0       # нет газовой фазы на контуре

    G_o[N] = grid.trans_ext * mob_o_up_e * dp_e
    G_free_gas[N] = grid.trans_ext * mob_g_up_e * dp_e
    G_g[N] = grid.trans_ext * (Rs_up_e * mob_o_up_e + mob_g_up_e) * dp_e

    Q_o[N] = grid.trans_ext * lam_o_up_e * dp_e
    Q_g[N] = grid.trans_ext * lam_g_up_e * dp_e

    u_o[N] = Q_o[N] / face_area[N]
    u_g[N] = Q_g[N] / face_area[N]

    m_o[N] = rho_o_up_e * Q_o[N]
    m_g[N] = rho_g_up_e * Q_g[N]

    # ── Покомпонентные массовые расходы ──────────────────────
    Gm_o = pvt.rho_o_std * G_o
    Gm_g = pvt.rho_g_std * G_g

    return HydroResult(
        state=state,
        G_o=G_o, G_g=G_g, G_free_gas=G_free_gas,
        Q_o=Q_o, Q_g=Q_g,
        u_o=u_o, u_g=u_g,
        m_o=m_o, m_g=m_g,
        Gm_o=Gm_o, Gm_g=Gm_g,
    )
