"""Вычисление потоков через грани: G, Q, u, m, Gm + upstream.

Eq. 8, 9, 24 problem_statement.tex. Конвенция: >0 = от скважины (рост r).

phase_fluxes_from_components — шаг «Q, u, m, Gm из G», общий для обоих
гидро-путей: compute_fluxes (путь тестов и двойников, G по Дарси) и
PrototypeHydroAdapter (рабочий расчёт, G от прототипа). Одна копия правила
выбора ячейки выше по потоку и формул (DEBT-028).
"""

import numpy as np

from .state import SimulationState, HydroResult, BoundaryConditions
from .bc import PressureControl
from .grid.base import Grid
from .pvt.base import HydroPVT, RelPermModel


def phase_fluxes_from_components(G_o: np.ndarray, G_g: np.ndarray,
                                 G_free_gas: np.ndarray,
                                 state: SimulationState, grid: Grid,
                                 pvt: HydroPVT, bc: BoundaryConditions,
                                 p_wf: float,
                                 n_substeps: int = 1) -> HydroResult:
    """Q, u, m, Gm из потоков компонентов G — общий шаг обоих гидро-путей. Ур. (eq:phase_flux)."""
    N = grid.N
    p = state.p
    Rs = state.Rs

    # PVT в центрах ячеек
    Bo = pvt.Bo(p, Rs)
    Bg = pvt.Bg(p)
    rho_o = pvt.rho_o(p, Rs)
    rho_g = pvt.rho_g(p)

    face_area = 2.0 * np.pi * grid.h * grid.r_faces

    Q_o = np.empty(N + 1)
    Q_g = np.empty(N + 1)
    u_o = np.empty(N + 1)
    u_g = np.empty(N + 1)
    m_o = np.empty(N + 1)
    m_g = np.empty(N + 1)

    # ── Внутренние грани (f = 1..N-1) ────────────────────────
    # Q_α = G·B_α ячейки выше по потоку: G^o = T·k_ro/(μ_o·B_o)·Δp, поэтому
    # G^o·B_o = T·(k_ro/μ_o)·Δp — это eq:phase_flux; для газа так же с G^св.газ.
    # Ячейка выше по потоку — по перепаду давления, как в прототипе
    # (blackoil.py, face_component_fluxes_sm3s: left = dp >= 0):
    #   dp = p[f-1] - p[f] >= 0 → ячейка f-1 (поток от скважины, нетипично)
    #   dp < 0                 → ячейка f   (поток к скважине, типично)
    # Не по знаку G^o: при k_ro = 0 в ячейке выше по потоку G^o = 0, и знак
    # не различает направление (DEBT-028).
    for f in range(1, N):
        up = f - 1 if p[f - 1] - p[f] >= 0 else f
        Q_o[f] = G_o[f] * Bo[up]
        Q_g[f] = G_free_gas[f] * Bg[up]
        u_o[f] = Q_o[f] / face_area[f]
        u_g[f] = Q_g[f] / face_area[f]
        m_o[f] = rho_o[up] * Q_o[f]
        m_g[f] = rho_g[up] * Q_g[f]

    # ── Забой (f = 0) ────────────────────────────────────────
    # Выше по потоку — ячейка 0: втекания через забой нет (eq:bc_pwf_shutin),
    # при закрытой скважине G = 0 и Q = 0. Знаки: добыча → G < 0 → Q < 0.
    Q_o[0] = G_o[0] * Bo[0]
    Q_g[0] = G_free_gas[0] * Bg[0]
    u_o[0] = Q_o[0] / face_area[0]
    u_g[0] = Q_g[0] / face_area[0]
    m_o[0] = rho_o[0] * Q_o[0]
    m_g[0] = rho_g[0] * Q_g[0]

    # ── Контур (f = N) ── eq:bc_flux_ext ─────────────────────
    if p[N - 1] - bc.p_ext < 0:
        # Приток с контура (типично): выше по потоку контур, свойства при
        # p_ext, Rs_ext. ρ_g — тоже при p_ext, а не ноль: свободного газа на
        # контуре нет и G^св.газ[N] = 0, но ветвь остаётся верной при
        # S_g,ext > 0 (DEBT-021, решение Р-1 DEBT-017).
        p_ext_a = np.array([bc.p_ext])
        Rs_ext_a = np.array([bc.Rs_ext])
        Bo_up_N = pvt.Bo(p_ext_a, Rs_ext_a)[0]
        Bg_up_N = pvt.Bg(p_ext_a)[0]
        rho_o_up_N = pvt.rho_o(p_ext_a, Rs_ext_a)[0]
        rho_g_up_N = pvt.rho_g(p_ext_a)[0]
    else:
        # Отток через контур (нетипично): выше по потоку ячейка N-1
        Bo_up_N = Bo[N - 1]
        Bg_up_N = Bg[N - 1]
        rho_o_up_N = rho_o[N - 1]
        rho_g_up_N = rho_g[N - 1]

    Q_o[N] = G_o[N] * Bo_up_N
    Q_g[N] = G_free_gas[N] * Bg_up_N
    u_o[N] = Q_o[N] / face_area[N]
    u_g[N] = Q_g[N] / face_area[N]
    m_o[N] = rho_o_up_N * Q_o[N]
    m_g[N] = rho_g_up_N * Q_g[N]

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
        p_wf=p_wf,
        n_substeps=n_substeps,
    )


def compute_fluxes(state: SimulationState, grid: Grid,
                   pvt: HydroPVT, relperm: RelPermModel,
                   bc: BoundaryConditions) -> HydroResult:
    """Потоки через все грани: G по Дарси + общий шаг Q, u, m, Gm.

    Ур. (eq:flux_oil), (eq:flux_gas), (eq:bc_pwf_shutin) problem_statement.tex.
    """
    # Путь тестов и тестовых двойников: рабочий расчёт получает G от
    # прототипа (PrototypeHydroAdapter). state не меняется, HydroResult.state = state.
    N = grid.N
    p = state.p
    Sg = state.Sg
    Rs = state.Rs

    # PVT в центрах ячеек
    Bo = pvt.Bo(p, Rs)
    Bg = pvt.Bg(p)
    mu_o = pvt.mu_o(p, Rs)
    mu_g = pvt.mu_g(p)

    kro = relperm.kro(Sg)
    krg = relperm.krg(Sg)

    # Подвижности потоков компонентов
    mob_o = kro / (mu_o * Bo)       # kro/(μo·Bo) — для G_o
    mob_g = krg / (mu_g * Bg)       # krg/(μg·Bg) — для G_free_gas

    # Забойное давление. compute_fluxes — гидродинамический путь тестов
    # и дублёров и сам читает управление (FEAT-020). Заданный дебит здесь
    # не поддержан: p_wf пришлось бы искать итерациями.
    if not isinstance(bc.well, PressureControl):
        raise NotImplementedError(
            f"compute_fluxes поддерживает только PressureControl, "
            f"получено {type(bc.well).__name__}")
    p_wf = bc.well.p_wf

    # PVT на контуре (однофазная зона: Sg=0)
    p_ext_arr = np.array([bc.p_ext])
    Rs_ext_arr = np.array([bc.Rs_ext])
    Bo_ext = pvt.Bo(p_ext_arr, Rs_ext_arr)[0]
    mu_o_ext = pvt.mu_o(p_ext_arr, Rs_ext_arr)[0]
    kro_ext = relperm.kro(np.array([bc.Sg_ext]))[0]

    mob_o_ext = kro_ext / (mu_o_ext * Bo_ext)

    # Потоки компонентов, м³ст/с
    G_o = np.empty(N + 1)
    G_g = np.empty(N + 1)
    G_free_gas = np.empty(N + 1)

    # ── Внутренние грани (f = 1..N-1) ────────────────────────
    # Грань f расположена между ячейками f-1 (левая) и f (правая).
    # dp = p[f-1] - p[f]:
    #   dp > 0 → поток от скважины (нетипично), upstream = f-1
    #   dp < 0 → поток к скважине (типично), upstream = f
    for f in range(1, N):
        dp = p[f - 1] - p[f]
        T_f = grid.trans_internal[f - 1]

        # Upstream = ячейка с бо́льшим давлением
        if dp >= 0:
            up = f - 1
        else:
            up = f

        # G_o = T * (kro/(μo·Bo))_up * dp — поток нефтяного компонента, м³ст/с (eq. 8)
        G_o[f] = T_f * mob_o[up] * dp
        # G_free_gas = T * (krg/(μg·Bg))_up * dp — свободный газ, м³ст/с
        G_free_gas[f] = T_f * mob_g[up] * dp
        # G_g = (Rs_up * mob_o_up + mob_g_up) * T * dp — полный газовый компонент (eq. 9)
        G_g[f] = T_f * (Rs[up] * mob_o[up] + mob_g[up]) * dp

    # ── Забой (f = 0) ────────────────────────────────────────
    # Скважина только добывающая (eq:bc_pwf_shutin): при p[0] <= p_wf она
    # закрыта — потоки через забой нулевые, фактическое давление на забое
    # равно p[0] (problem_statement.tex, «Закрытие скважины»). Так же
    # поступает прототип (blackoil.py, _well_fluxes, ветвь 'shut').
    # Закрытие выражено нулевым перепадом: формулы ниже дают G = 0.
    # При добыче p_wf < p[0] → dp_w < 0 → G < 0 (к скважине); выше по
    # потоку — ячейка 0.
    dp_w = p_wf - p[0]
    if dp_w >= 0:
        p_wf = float(p[0])
        dp_w = 0.0
    up_w = 0

    G_o[0] = grid.trans_well * mob_o[up_w] * dp_w
    G_free_gas[0] = grid.trans_well * mob_g[up_w] * dp_w
    G_g[0] = grid.trans_well * (Rs[up_w] * mob_o[up_w] + mob_g[up_w]) * dp_w

    # ── Контур (f = N) ───────────────────────────────────────
    dp_e = p[N - 1] - bc.p_ext

    if dp_e >= 0:
        # Поток от скважины (нетипично): upstream = ячейка N-1
        mob_o_up_e = mob_o[N - 1]
        mob_g_up_e = mob_g[N - 1]
        Rs_up_e = Rs[N - 1]
    else:
        # Приток из контура (типично): upstream = контур
        mob_o_up_e = mob_o_ext
        mob_g_up_e = 0.0       # krg=0 на контуре (Sg=0)
        Rs_up_e = bc.Rs_ext

    G_o[N] = grid.trans_ext * mob_o_up_e * dp_e
    G_free_gas[N] = grid.trans_ext * mob_g_up_e * dp_e
    G_g[N] = grid.trans_ext * (Rs_up_e * mob_o_up_e + mob_g_up_e) * dp_e

    # ── Q, u, m, Gm — общий шаг с рабочим путём (адаптер прототипа) ──
    return phase_fluxes_from_components(G_o, G_g, G_free_gas,
                                        state, grid, pvt, bc, p_wf)
