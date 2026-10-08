"""Тесты для fluxes.py (фаза 3).

Три сценария:
A. Однофазный стационарный поток (Sg=0, co=0).
   mob_o = kro/(mu_o*Bo) = const → G_o = const на всех гранях.
   Точная аналитическая формула: G_o = 2πhk*mob_o*(p_wf-p_ext)/ln(R/rw).

B. Двухфазный профиль (Sg неоднороден).
   Воспроизведение формулы на каждой грани, конкретные числа.

C. Краевые случаи: немонотонное давление (upstream flip),
   однородное давление (все потоки = 0), отток на контуре,
   предельные насыщенности.
"""

import numpy as np
import pytest

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import (
    SimulationState, HydroResult, BoundaryConditions,
    WellData, SimulationHistory,
)
from gpn_multiphase_solver.bc import WellControl, PressureControl, RateControl
from gpn_multiphase_solver.fluxes import compute_fluxes, phase_fluxes_from_components


# ═════════════════════════════════════════════════════════════
# Параметры
# ═════════════════════════════════════════════════════════════

R_WELL = 0.1
R_EXT = 50.0
H = 10.0
K_PERM = 1e-13

P_EXT = 20e6
P_WF = 10e6
# Забойное давление двухфазной фикстуры: ниже p[0] = 8 МПа — добыча.
# При P_WF = 10 МПа > p[0] скважина закрыта (eq:bc_pwf_shutin), и тесты
# грани 0 проверяли бы нули вместо формулы притока (DEBT-028).
P_WF_2PH = 6e6
T0 = 350.0

RHO_O_STD = 850.0
RHO_G_STD = 0.85
RS0 = 50.0

S_OR = 0.2
S_GC = 0.05


# ═════════════════════════════════════════════════════════════
# Эталонный расчёт на одной грани (воспроизведение логики ядра)
# ═════════════════════════════════════════════════════════════

def _compute_reference_face(pvt, rp, grid, state, bc, f):
    """Эталонный расчёт всех 11 полей на грани f."""
    p = state.p
    Sg = state.Sg
    Rs = state.Rs
    N = grid.N

    Bo = pvt.Bo(p, Rs)
    Bg = pvt.Bg(p)
    mu_o = pvt.mu_o(p, Rs)
    mu_g = pvt.mu_g(p)
    rho_o = pvt.rho_o(p, Rs)
    rho_g = pvt.rho_g(p)
    kro = rp.kro(Sg)
    krg = rp.krg(Sg)

    if f == 0:
        p_wf = bc.well.p_wf    # эталон: только PressureControl
        # Закрытая скважина (eq:bc_pwf_shutin): при p[0] <= p_wf потоков нет
        dp = min(p_wf - p[0], 0.0)
        T_f = grid.trans_well
        up = 0
        mob_o_up = kro[up] / (mu_o[up] * Bo[up])
        mob_g_up = krg[up] / (mu_g[up] * Bg[up])
        lam_o_up = kro[up] / mu_o[up]
        lam_g_up = krg[up] / mu_g[up]
        Rs_up = Rs[up]
        rho_o_up = rho_o[up]
        rho_g_up = rho_g[up]
    elif f == N:
        dp = p[N - 1] - bc.p_ext
        T_f = grid.trans_ext
        if dp >= 0:
            up = N - 1
            mob_o_up = kro[up] / (mu_o[up] * Bo[up])
            mob_g_up = krg[up] / (mu_g[up] * Bg[up])
            lam_o_up = kro[up] / mu_o[up]
            lam_g_up = krg[up] / mu_g[up]
            Rs_up = Rs[up]
            rho_o_up = rho_o[up]
            rho_g_up = rho_g[up]
        else:
            p_ext_a = np.array([bc.p_ext])
            Rs_ext_a = np.array([bc.Rs_ext])
            Bo_ext = pvt.Bo(p_ext_a, Rs_ext_a)[0]
            mu_o_ext = pvt.mu_o(p_ext_a, Rs_ext_a)[0]
            kro_ext = rp.kro(np.array([bc.Sg_ext]))[0]
            mob_o_up = kro_ext / (mu_o_ext * Bo_ext)
            mob_g_up = 0.0
            lam_o_up = kro_ext / mu_o_ext
            lam_g_up = 0.0
            Rs_up = bc.Rs_ext
            rho_o_up = pvt.rho_o(p_ext_a, Rs_ext_a)[0]
            rho_g_up = pvt.rho_g(p_ext_a)[0]   # при p_ext, как ρ_o (DEBT-021)
    else:
        dp = p[f - 1] - p[f]
        T_f = grid.trans_internal[f - 1]
        up = f - 1 if dp >= 0 else f
        mob_o_up = kro[up] / (mu_o[up] * Bo[up])
        mob_g_up = krg[up] / (mu_g[up] * Bg[up])
        lam_o_up = kro[up] / mu_o[up]
        lam_g_up = krg[up] / mu_g[up]
        Rs_up = Rs[up]
        rho_o_up = rho_o[up]
        rho_g_up = rho_g[up]

    G_o = T_f * mob_o_up * dp
    G_fg = T_f * mob_g_up * dp
    G_g = T_f * (Rs_up * mob_o_up + mob_g_up) * dp
    Q_o = T_f * lam_o_up * dp
    Q_g = T_f * lam_g_up * dp
    area = 2.0 * np.pi * grid.h * grid.r_faces[f]
    u_o = Q_o / area
    u_g = Q_g / area
    m_o = rho_o_up * Q_o
    m_g = rho_g_up * Q_g
    Gm_o = pvt.rho_o_std * G_o
    Gm_g = pvt.rho_g_std * G_g

    return dict(G_o=G_o, G_g=G_g, G_free_gas=G_fg,
                Q_o=Q_o, Q_g=Q_g, u_o=u_o, u_g=u_g,
                m_o=m_o, m_g=m_g, Gm_o=Gm_o, Gm_g=Gm_g)


# ═════════════════════════════════════════════════════════════
# Общие fixtures
# ═════════════════════════════════════════════════════════════

@pytest.fixture
def pvt():
    return StandingFullPVT(rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD,
                           T0=T0, Rs0=RS0, co_undersaturated=0.0)


@pytest.fixture
def relperm():
    return CoreyRP(S_or=S_OR, S_gc=S_GC, n_o=2.0, n_g=2.0,
                   kro_max=1.0, krg_max=0.8)


# ═════════════════════════════════════════════════════════════
# A. Однофазный стационарный поток (N=20)
# ═════════════════════════════════════════════════════════════

N_1PH = 20


@pytest.fixture
def grid_1ph():
    return LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=N_1PH, k=K_PERM)


@pytest.fixture
def state_1ph(grid_1ph):
    """Стационарный логарифмический профиль давления, однофазный (Sg=0).

    p(r) = p_wf + (p_ext - p_wf) * ln(r/rw) / ln(R/rw).
    Это точное решение стационарного уравнения фильтрации.
    """
    r = grid_1ph.r_centers
    log_ratio = np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
    p = P_WF + (P_EXT - P_WF) * log_ratio
    return SimulationState(
        p=p, Sg=np.zeros(N_1PH), Rs=np.full(N_1PH, RS0),
        T=np.full(N_1PH, T0), regime=np.full(N_1PH, 2, dtype=int), t=0.0)


@pytest.fixture
def bc_1ph():
    return BoundaryConditions(
        well=PressureControl(P_WF), p_ext=P_EXT,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)


@pytest.fixture
def result_1ph(state_1ph, grid_1ph, pvt, relperm, bc_1ph):
    return compute_fluxes(state_1ph, grid_1ph, pvt, relperm, bc_1ph)


@pytest.fixture
def mob_o_const(pvt):
    """mob_o = kro/(mu_o*Bo) = const при Sg=0, co=0."""
    p_ref = np.array([15e6])
    Rs_ref = np.array([RS0])
    Bo = pvt.Bo(p_ref, Rs_ref)[0]
    mu_o = pvt.mu_o(p_ref, Rs_ref)[0]
    return 1.0 / (mu_o * Bo)


class TestOnePhaseAnalyticalRate:
    """Точная формула: G_o = 2πhk * mob_o * (p_wf - p_ext) / ln(R/rw).

    При co=0, Sg=0: Bo, mu_o = const → mob_o = const → формула точная.
    """

    def test_G_o_exact_value(self, result_1ph, mob_o_const):
        G_o_exact = (2 * np.pi * H * K_PERM * mob_o_const
                     * (P_WF - P_EXT) / np.log(R_EXT / R_WELL))
        assert result_1ph.G_o[0] == pytest.approx(G_o_exact, rel=1e-12)

    def test_G_o_concrete_number(self, result_1ph):
        """G_o ≈ -0.009138144903103 м³ст/с."""
        assert result_1ph.G_o[0] == pytest.approx(-0.009138144903103, rel=1e-10)

    def test_q_o_std_concrete_number(self, result_1ph):
        """q_o_std = -G_o[0] ≈ 0.009138 м³ст/с ≈ 789 м³ст/сут."""
        q = -result_1ph.G_o[0]
        assert q == pytest.approx(0.009138144903103, rel=1e-10)
        assert q * 86400 == pytest.approx(789.4, rel=0.01)


class TestOnePhasePerFace:
    """Формула G_o[f] = T_f * mob_o * dp на каждой грани."""

    @pytest.mark.parametrize("f", [0, 1, 5, 10, 15, 19, 20])
    def test_G_o_formula(self, result_1ph, grid_1ph, state_1ph, pvt,
                          relperm, bc_1ph, f):
        ref = _compute_reference_face(pvt, relperm, grid_1ph,
                                       state_1ph, bc_1ph, f)
        assert result_1ph.G_o[f] == pytest.approx(ref['G_o'], rel=1e-14)

    @pytest.mark.parametrize("f", [0, 1, 10, 20])
    def test_Q_o_formula(self, result_1ph, grid_1ph, state_1ph, pvt,
                          relperm, bc_1ph, f):
        ref = _compute_reference_face(pvt, relperm, grid_1ph,
                                       state_1ph, bc_1ph, f)
        assert result_1ph.Q_o[f] == pytest.approx(ref['Q_o'], rel=1e-14)

    @pytest.mark.parametrize("f", [0, 1, 10, 20])
    def test_u_o_formula(self, result_1ph, grid_1ph, state_1ph, pvt,
                          relperm, bc_1ph, f):
        ref = _compute_reference_face(pvt, relperm, grid_1ph,
                                       state_1ph, bc_1ph, f)
        assert result_1ph.u_o[f] == pytest.approx(ref['u_o'], rel=1e-14)

    @pytest.mark.parametrize("f", [0, 10, 20])
    def test_m_o_formula(self, result_1ph, grid_1ph, state_1ph, pvt,
                          relperm, bc_1ph, f):
        ref = _compute_reference_face(pvt, relperm, grid_1ph,
                                       state_1ph, bc_1ph, f)
        assert result_1ph.m_o[f] == pytest.approx(ref['m_o'], rel=1e-14)


class TestOnePhaseStationarity:
    """G_o = const, G_g = const, баланс масс = 0."""

    def test_G_o_constant(self, result_1ph):
        np.testing.assert_allclose(result_1ph.G_o, result_1ph.G_o[0], rtol=1e-12)

    def test_G_g_constant(self, result_1ph):
        np.testing.assert_allclose(result_1ph.G_g, result_1ph.G_g[0], rtol=1e-12)

    def test_oil_residual_per_cell(self, result_1ph):
        """F_oil[j] = G_o[j+1] - G_o[j] ≈ 0 (до машинной точности)."""
        residual = result_1ph.G_o[1:] - result_1ph.G_o[:-1]
        scale = np.abs(result_1ph.G_o[0])
        np.testing.assert_allclose(residual / scale, 0.0, atol=1e-12)

    def test_gas_residual_per_cell(self, result_1ph):
        residual = result_1ph.G_g[1:] - result_1ph.G_g[:-1]
        scale = np.abs(result_1ph.G_g[0])
        np.testing.assert_allclose(residual / scale, 0.0, atol=1e-12)


class TestOnePhaseAlgebraicRelations:
    """Связи: Q_o = G_o*Bo, u = Q/(2πhr), Gm = ρ_ст*G, m = ρ_up*Q."""

    def test_Q_o_equals_G_o_times_Bo(self, result_1ph, pvt):
        Bo = pvt.Bo(np.array([15e6]), np.array([RS0]))[0]
        np.testing.assert_allclose(result_1ph.Q_o,
                                   result_1ph.G_o * Bo, rtol=1e-12)

    def test_u_times_r_constant(self, result_1ph, grid_1ph):
        """u_o * r = const (1/r-профиль стационарного потока)."""
        u_r = result_1ph.u_o * grid_1ph.r_faces
        np.testing.assert_allclose(u_r, u_r[0], rtol=1e-10)

    def test_Gm_o(self, result_1ph, pvt):
        np.testing.assert_allclose(result_1ph.Gm_o,
                                   pvt.rho_o_std * result_1ph.G_o, rtol=1e-14)

    def test_Gm_g(self, result_1ph, pvt):
        np.testing.assert_allclose(result_1ph.Gm_g,
                                   pvt.rho_g_std * result_1ph.G_g, rtol=1e-14)

    def test_G_g_equals_Rs_times_G_o(self, result_1ph):
        """При Sg=0: G_free_gas=0 → G_g = Rs*G_o."""
        np.testing.assert_allclose(result_1ph.G_g,
                                   RS0 * result_1ph.G_o, rtol=1e-12)

    def test_G_free_gas_zero(self, result_1ph):
        """Sg=0 → krg=0 → mob_g=0 → G_free_gas = 0 на всех гранях."""
        np.testing.assert_allclose(result_1ph.G_free_gas, 0.0, atol=1e-30)

    def test_Q_g_zero(self, result_1ph):
        """Sg=0 → krg=0 → lam_g=0 → Q_g = 0 (нет газовой фазы)."""
        np.testing.assert_allclose(result_1ph.Q_g, 0.0, atol=1e-30)


# ═════════════════════════════════════════════════════════════
# B. Двухфазный профиль (N=5)
# ═════════════════════════════════════════════════════════════

N_2PH = 5


@pytest.fixture
def grid_2ph():
    return LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=N_2PH, k=K_PERM)


@pytest.fixture
def state_2ph(grid_2ph, pvt):
    """Двухфазный профиль: газонасыщенность убывает от скважины к контуру.

    Sg: 0.3 → 0.2 → 0.1 → 0.05 → 0.0
    p:  8   → 10  → 13  → 16   → 19 МПа

    Ячейки 0–3: двухфазные (regime=1), Rs = Rs_eq(p).
    Ячейка 4: однофазная (regime=2), Rs = Rs0.
    Давление монотонно растёт → dp < 0 на всех внутренних гранях →
    upstream = правая ячейка (типичный поток к скважине).
    """
    p = np.array([8e6, 10e6, 13e6, 16e6, 19e6])
    Sg = np.array([0.3, 0.2, 0.1, 0.05, 0.0])
    Rs = pvt.Rs_eq(p)
    Rs[4] = RS0  # однофазная ячейка: Rs свободно, не из PVT
    T = np.full(N_2PH, T0)
    regime = np.array([1, 1, 1, 1, 2], dtype=int)
    return SimulationState(p=p, Sg=Sg, Rs=Rs, T=T, regime=regime, t=0.0)


@pytest.fixture
def bc_2ph():
    return BoundaryConditions(
        well=PressureControl(P_WF_2PH), p_ext=P_EXT,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)


@pytest.fixture
def result_2ph(state_2ph, grid_2ph, pvt, relperm, bc_2ph):
    return compute_fluxes(state_2ph, grid_2ph, pvt, relperm, bc_2ph)


class TestTwoPhaseAllFields:
    """Формула на каждой грани × каждое поле (66 проверок: 11 полей × 6 граней)."""

    FIELDS = ["G_o", "G_g", "G_free_gas", "Q_o", "Q_g",
              "u_o", "u_g", "m_o", "m_g", "Gm_o", "Gm_g"]

    @pytest.mark.parametrize("f", [0, 1, 2, 3, 4, 5])
    @pytest.mark.parametrize("field", FIELDS)
    def test_field_matches_formula(self, result_2ph, state_2ph, grid_2ph,
                                    pvt, relperm, bc_2ph, f, field):
        ref = _compute_reference_face(pvt, relperm, grid_2ph,
                                       state_2ph, bc_2ph, f)
        actual = getattr(result_2ph, field)[f]
        assert actual == pytest.approx(ref[field], rel=1e-12, abs=1e-30)


class TestTwoPhaseConcreteValues:
    """Вручную вычисленные значения для грани f=1.

    p[0]=8e6, p[1]=10e6 → dp=-2e6 → upstream = ячейка 1.
    Sg[1]=0.2, Rs[1]=Rs_eq(10e6).
    """

    def test_G_o_face_1(self, result_2ph):
        assert result_2ph.G_o[1] == pytest.approx(-0.006019771615013, rel=1e-8)

    def test_G_free_gas_face_1(self, result_2ph):
        assert result_2ph.G_free_gas[1] == pytest.approx(-1.795875886047, rel=1e-8)

    def test_G_g_face_1(self, result_2ph):
        assert result_2ph.G_g[1] == pytest.approx(-2.118667745913, rel=1e-8)

    def test_Q_o_face_1(self, result_2ph):
        assert result_2ph.Q_o[1] == pytest.approx(-0.007080917929952, rel=1e-8)

    def test_Q_g_face_1(self, result_2ph):
        assert result_2ph.Q_g[1] == pytest.approx(-0.022059676995532, rel=1e-8)

    def test_m_o_face_1(self, result_2ph):
        assert result_2ph.m_o[1] == pytest.approx(-5.391178953647, rel=1e-8)

    def test_m_g_face_1(self, result_2ph):
        assert result_2ph.m_g[1] == pytest.approx(-1.526494503140, rel=1e-8)


class TestTwoPhaseGDecomposition:
    """G_g = Rs_up * G_o + G_free_gas на каждой грани."""

    @pytest.mark.parametrize("f", [0, 1, 2, 3, 4, 5])
    def test_decomposition(self, result_2ph, state_2ph, bc_2ph, f):
        Rs_up = _get_Rs_up(state_2ph, bc_2ph, f, N_2PH)
        expected = Rs_up * result_2ph.G_o[f] + result_2ph.G_free_gas[f]
        assert result_2ph.G_g[f] == pytest.approx(expected, rel=1e-12)


class TestTwoPhaseExtBoundary:
    """Контур: Sg=0 → krg=0 → газовые фазовые потоки = 0."""

    def test_G_free_gas_ext_zero(self, result_2ph):
        assert result_2ph.G_free_gas[N_2PH] == pytest.approx(0.0, abs=1e-30)

    def test_Q_g_ext_zero(self, result_2ph):
        assert result_2ph.Q_g[N_2PH] == pytest.approx(0.0, abs=1e-30)

    def test_G_g_ext_equals_Rs_ext_times_G_o(self, result_2ph):
        """На контуре: G_g = Rs_ext*G_o (газовая фаза отсутствует)."""
        assert result_2ph.G_g[N_2PH] == pytest.approx(
            RS0 * result_2ph.G_o[N_2PH], rel=1e-12)


class TestWellShutIn:
    """Закрытие скважины при p_wf >= p[0] (eq:bc_pwf_shutin, DEBT-028).

    Скважина только добывающая: если заданное p_wf не ниже давления в
    ячейке 0, закачки нет — потоки через забой нулевые, а фактическое
    давление на забое равно p[0] (problem_statement.tex, «Закрытие
    скважины»). Так же поступает прототип (blackoil.py, _well_fluxes,
    ветвь 'shut'). Профиль — state_2ph, p[0] = 8 МПа; уставка 10 МПа > p[0].
    """

    @pytest.fixture
    def shut(self, state_2ph, grid_2ph, pvt, relperm):
        bc_shut = BoundaryConditions(
            well=PressureControl(10e6), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)
        return compute_fluxes(state_2ph, grid_2ph, pvt, relperm, bc_shut)

    @pytest.mark.parametrize("field", TestTwoPhaseAllFields.FIELDS)
    def test_well_face_zero(self, shut, field):
        """Все 11 полей на грани 0 — нули.

        Ловит: закачку через забой (до DEBT-028 G_o[0] > 0 при p_wf > p[0]).
        """
        assert getattr(shut, field)[0] == 0.0

    def test_pwf_equals_p0(self, shut, state_2ph):
        """Фактическое p_wf = p[0] = 8 МПа, а не уставка 10 МПа.

        Ловит: возврат уставки — энергия берёт давление на забойной грани
        из HydroResult.p_wf (energy/tridiag.py), а не из управления.
        """
        assert shut.p_wf == state_2ph.p[0]

    def test_other_faces_unchanged(self, shut, result_2ph):
        """Грани 1..N побитово те же, что при добыче (p_wf = 6 МПа).

        Условие на забое входит только в поток грани 0. Ловит: закрытие,
        задевающее другие грани.
        """
        for field in TestTwoPhaseAllFields.FIELDS:
            np.testing.assert_array_equal(getattr(shut, field)[1:],
                                          getattr(result_2ph, field)[1:])

    def test_producing_pwf_is_setpoint(self, result_2ph):
        """При добыче (p_wf = 6 МПа < p[0]) фактическое p_wf = уставке."""
        assert result_2ph.p_wf == P_WF_2PH


class TestPhaseFluxesFromComponents:
    """Общий шаг «Q, u, m, Gm из G» (phase_fluxes_from_components, DEBT-028).

    Функцию вызывают оба гидро-пути: compute_fluxes (тесты, двойники) и
    PrototypeHydroAdapter (рабочий расчёт). G задаются вручную — так
    получаются ситуации, которых compute_fluxes на штатных профилях не даёт.
    Профиль state_2ph: p растёт от скважины (8 → 19 МПа), Δp < 0 на всех
    внутренних гранях, на контуре p[N-1] = 19 < p_ext = 20 МПа — приток.
    """

    @staticmethod
    def _zeros(n):
        return np.zeros(n + 1), np.zeros(n + 1), np.zeros(n + 1)

    def test_upstream_by_pressure_when_G_o_zero(self, state_2ph, grid_2ph,
                                                pvt, bc_2ph):
        """G_o = 0, свободный газ течёт к скважине: выше по потоку — ячейка f.

        Так бывает при k_ro = 0 (S_g >= 1 - S_or) в ячейке выше по потоку.
        Ячейка выбирается по перепаду давления (как в прототипе), а не по
        знаку G_o: на грани 1 Δp = 8 - 10 МПа < 0 → ячейка 1.
        Ожидание: Q_g[1] = G_free_gas[1] · B_g[1]. Ловит: правило «по знаку
        G_o», которое при G_o = 0 брало ячейку 0 (ниже по потоку).
        """
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        G_free_gas[1] = -1.0          # к скважине: знак «−» по конвенции
        G_g[1] = -1.0
        Bg = pvt.Bg(state_2ph.p)
        rho_g = pvt.rho_g(state_2ph.p)
        # Контроль невырожденности: при равных B_g тест не различит ячейки
        assert not np.isclose(Bg[0], Bg[1], rtol=1e-6)
        r = phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                         grid_2ph, pvt, bc_2ph, P_WF_2PH)
        area = 2.0 * np.pi * grid_2ph.h * grid_2ph.r_faces[1]
        assert r.Q_g[1] == pytest.approx(-Bg[1], rel=1e-14)
        assert r.u_g[1] == pytest.approx(-Bg[1] / area, rel=1e-14)
        assert r.m_g[1] == pytest.approx(rho_g[1] * r.Q_g[1], rel=1e-14)

    def test_outer_inflow_gas_density_from_ext(self, state_2ph, grid_2ph,
                                               pvt, bc_2ph):
        """Приток через контур: B_g и ρ_g — при p_ext (DEBT-021).

        Свободного газа на контуре нет (S_g,ext = 0), и в расчёте
        G_free_gas[N] = 0 — здесь он задан вручную, как при S_g,ext > 0.
        Ожидание: Q_g[N] = G_free_gas[N]·B_g(p_ext), m_g[N] = ρ_g(p_ext)·Q_g[N] ≠ 0.
        Ловит: ρ_g = 0 на контуре (прежний compute_fluxes) — расхождение
        двух гидро-путей, скрытое умножением на ноль.
        """
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        G_free_gas[N] = -1.0          # приток: к скважине, знак «−»
        G_g[N] = -1.0
        p_ext_a = np.array([bc_2ph.p_ext])
        Bg_ext = pvt.Bg(p_ext_a)[0]
        rho_g_ext = pvt.rho_g(p_ext_a)[0]
        assert state_2ph.p[N - 1] < bc_2ph.p_ext          # действительно приток
        # Контроль невырожденности: ρ_g контура ≠ ρ_g ячейки N-1
        assert not np.isclose(rho_g_ext, pvt.rho_g(state_2ph.p)[N - 1], rtol=1e-6)
        r = phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                         grid_2ph, pvt, bc_2ph, P_WF_2PH)
        assert r.Q_g[N] == pytest.approx(-Bg_ext, rel=1e-14)
        assert r.m_g[N] == pytest.approx(rho_g_ext * r.Q_g[N], rel=1e-14)
        assert r.m_g[N] != 0.0

    def test_pwf_and_state_passed_through(self, state_2ph, grid_2ph,
                                          pvt, bc_2ph):
        """p_wf и state уходят в HydroResult без изменений.

        Адаптер передаёт фактическое p_wf прототипа (FEAT-020). Ловит: потерю
        или подмену этих полей.
        """
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        r = phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                         grid_2ph, pvt, bc_2ph, 7.5e6)
        assert r.p_wf == 7.5e6
        assert r.state is state_2ph


def _get_Rs_up(state, bc, f, N):
    """Rs upstream для грани f. Правило то же, что в fluxes.py:
    upstream = ячейка с бо́льшим давлением (откуда течёт жидкость).
    На забое: всегда ячейка 0.
    На контуре: ячейка N-1 при оттоке, контур при притоке.
    """
    if f == 0:
        return state.Rs[0]
    elif f == N:
        if state.p[N - 1] >= bc.p_ext:
            return state.Rs[N - 1]   # отток → upstream = ячейка N-1
        else:
            return bc.Rs_ext          # приток → upstream = контур
    else:
        dp = state.p[f - 1] - state.p[f]
        return state.Rs[f - 1] if dp >= 0 else state.Rs[f]


# ═════════════════════════════════════════════════════════════
# C. Краевые случаи
# ═════════════════════════════════════════════════════════════

class TestUniformPressure:
    """p = const → dp = 0 на всех гранях → все потоки = 0."""

    def test_all_fluxes_zero(self, pvt, relperm):
        grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=5, k=K_PERM)
        P_UNIFORM = 15e6
        state = SimulationState(
            p=np.full(5, P_UNIFORM), Sg=np.zeros(5),
            Rs=np.full(5, RS0), T=np.full(5, T0),
            regime=np.full(5, 2, dtype=int), t=0.0)
        bc = BoundaryConditions(
            well=PressureControl(P_UNIFORM), p_ext=P_UNIFORM,
            T_ext=T0, Rs_ext=RS0)
        result = compute_fluxes(state, grid, pvt, relperm, bc)

        for field in ['G_o', 'G_g', 'G_free_gas', 'Q_o', 'Q_g',
                      'u_o', 'u_g', 'm_o', 'm_g', 'Gm_o', 'Gm_g']:
            np.testing.assert_allclose(
                getattr(result, field), 0.0, atol=1e-30,
                err_msg=f"{field} should be 0 at uniform pressure")


class TestNonMonotonicPressure:
    """Немонотонное давление: p[1] > p[0] и p[1] > p[2].

    На грани f=1: dp = p[0]-p[1] < 0 → upstream = ячейка 1.
    На грани f=2: dp = p[1]-p[2] > 0 → upstream = ячейка 1.
    Обе грани используют ячейку 1 как upstream, но G имеют разные знаки.
    """

    def test_upstream_flip(self, pvt, relperm):
        grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=4, k=K_PERM)
        p = np.array([12e6, 18e6, 11e6, 15e6])  # пик в ячейке 1
        state = SimulationState(
            p=p, Sg=np.zeros(4), Rs=np.full(4, RS0),
            T=np.full(4, T0), regime=np.full(4, 2, dtype=int), t=0.0)
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0)
        result = compute_fluxes(state, grid, pvt, relperm, bc)

        # Грань f=1: dp = p[0]-p[1] = 12-18 = -6e6 < 0 → upstream=1 → G<0
        ref_1 = _compute_reference_face(pvt, relperm, grid, state, bc, 1)
        assert result.G_o[1] == pytest.approx(ref_1['G_o'], rel=1e-14)
        assert result.G_o[1] < 0

        # Грань f=2: dp = p[1]-p[2] = 18-11 = 7e6 > 0 → upstream=1 → G>0
        ref_2 = _compute_reference_face(pvt, relperm, grid, state, bc, 2)
        assert result.G_o[2] == pytest.approx(ref_2['G_o'], rel=1e-14)
        assert result.G_o[2] > 0

    def test_all_fields_on_flipped_face(self, pvt, relperm):
        """Все 11 полей верны на грани с dp > 0."""
        grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=4, k=K_PERM)
        p = np.array([12e6, 18e6, 11e6, 15e6])
        state = SimulationState(
            p=p, Sg=np.array([0.1, 0.2, 0.0, 0.0]),
            Rs=pvt.Rs_eq(p),
            T=np.full(4, T0), regime=np.array([1, 1, 2, 2], dtype=int), t=0.0)
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0)
        result = compute_fluxes(state, grid, pvt, relperm, bc)

        for f in range(5):
            ref = _compute_reference_face(pvt, relperm, grid, state, bc, f)
            for field in ['G_o', 'G_g', 'G_free_gas', 'Q_o', 'Q_g',
                          'u_o', 'u_g', 'm_o', 'm_g', 'Gm_o', 'Gm_g']:
                assert getattr(result, field)[f] == pytest.approx(
                    ref[field], rel=1e-12, abs=1e-30), \
                    f"Mismatch: face={f}, field={field}"


class TestOutflowAtExtBoundary:
    """p[N-1] > p_ext → отток на контуре (нетипично).

    Upstream = ячейка N-1 (не контур). G_o > 0 (от скважины).
    """

    def test_outflow_positive_G_o(self, pvt, relperm):
        grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=5, k=K_PERM)
        p = np.array([12e6, 15e6, 18e6, 22e6, 25e6])  # p[-1] > P_EXT
        state = SimulationState(
            p=p, Sg=np.zeros(5), Rs=np.full(5, RS0),
            T=np.full(5, T0), regime=np.full(5, 2, dtype=int), t=0.0)
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0)
        result = compute_fluxes(state, grid, pvt, relperm, bc)

        # G_o на контуре > 0 (отток)
        assert result.G_o[5] > 0

        # Формула верна
        ref = _compute_reference_face(pvt, relperm, grid, state, bc, 5)
        assert result.G_o[5] == pytest.approx(ref['G_o'], rel=1e-14)

    def test_upstream_is_last_cell(self, pvt, relperm):
        """При оттоке upstream = ячейка N-1, а не контур."""
        grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=5, k=K_PERM)
        p = np.array([12e6, 15e6, 18e6, 22e6, 25e6])
        Sg = np.array([0.0, 0.0, 0.0, 0.0, 0.15])
        state = SimulationState(
            p=p, Sg=Sg, Rs=pvt.Rs_eq(p),
            T=np.full(5, T0), regime=np.array([2, 2, 2, 2, 1], dtype=int), t=0.0)
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)
        result = compute_fluxes(state, grid, pvt, relperm, bc)

        # Sg[4]=0.15 → krg > 0 → Q_g ≠ 0 на контуре (upstream = ячейка 4)
        assert result.Q_g[5] != 0.0
        ref = _compute_reference_face(pvt, relperm, grid, state, bc, 5)
        assert result.Q_g[5] == pytest.approx(ref['Q_g'], rel=1e-12)
        assert result.G_free_gas[5] == pytest.approx(ref['G_free_gas'], rel=1e-12)


class TestMaxGasSaturation:
    """Sg = 1 - S_or = 0.8: kro = 0, krg = max.

    Нефтяные потоки = 0, газовые потоки ≠ 0.
    """

    def test_oil_fluxes_zero(self, pvt, relperm):
        grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=3, k=K_PERM)
        Sg_max = 1.0 - S_OR  # 0.8
        p = np.array([10e6, 15e6, 19e6])
        state = SimulationState(
            p=p, Sg=np.full(3, Sg_max),
            Rs=pvt.Rs_eq(p),
            T=np.full(3, T0), regime=np.full(3, 1, dtype=int), t=0.0)
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0)
        result = compute_fluxes(state, grid, pvt, relperm, bc)

        # kro(0.8) = 0 → G_o = 0, Q_o = 0 на внутренних гранях
        for f in range(1, 3):
            assert result.G_o[f] == pytest.approx(0.0, abs=1e-30)
            assert result.Q_o[f] == pytest.approx(0.0, abs=1e-30)

        # krg(0.8) = 0.8 → Q_g ≠ 0
        for f in range(1, 3):
            assert result.Q_g[f] != 0.0

    def test_gas_flux_formula(self, pvt, relperm):
        """G_free_gas вычислен корректно при kro=0."""
        grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=3, k=K_PERM)
        Sg_max = 1.0 - S_OR
        p = np.array([10e6, 15e6, 19e6])
        state = SimulationState(
            p=p, Sg=np.full(3, Sg_max),
            Rs=pvt.Rs_eq(p),
            T=np.full(3, T0), regime=np.full(3, 1, dtype=int), t=0.0)
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0)
        result = compute_fluxes(state, grid, pvt, relperm, bc)

        for f in range(4):
            ref = _compute_reference_face(pvt, relperm, grid, state, bc, f)
            assert result.G_free_gas[f] == pytest.approx(
                ref['G_free_gas'], rel=1e-12, abs=1e-30)


class TestUpstreamAtGasFront:
    """Sg > 0 в ячейке 0, Sg = 0 в ячейке 1.

    При типичном потоке к скважине: upstream = ячейка 1 (Sg=0, krg=0).
    G_free_gas на грани f=1 = 0, хотя ячейка 0 имеет газ.
    """

    def test_gas_flux_zero_at_front(self, pvt, relperm):
        grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=4, k=K_PERM)
        p = np.array([12e6, 16e6, 18e6, 19e6])
        Sg = np.array([0.2, 0.0, 0.0, 0.0])
        state = SimulationState(
            p=p, Sg=Sg, Rs=np.full(4, RS0),
            T=np.full(4, T0), regime=np.array([1, 2, 2, 2], dtype=int), t=0.0)
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0)
        result = compute_fluxes(state, grid, pvt, relperm, bc)

        # dp = p[0]-p[1] < 0 → upstream = ячейка 1 (Sg=0, krg=0)
        assert result.G_free_gas[1] == pytest.approx(0.0, abs=1e-30)
        assert result.Q_g[1] == pytest.approx(0.0, abs=1e-30)

        # Грань f=0 (забой): p_wf=10e6 < p[0]=12e6 → dp < 0
        # upstream = ячейка 0 (Sg=0.2, krg>0) → G_free_gas ≠ 0
        assert result.G_free_gas[0] != 0.0
        assert result.Q_g[0] != 0.0

        # Формула верна
        ref = _compute_reference_face(pvt, relperm, grid, state, bc, 0)
        assert result.G_free_gas[0] == pytest.approx(ref['G_free_gas'], rel=1e-12)
        ref_1 = _compute_reference_face(pvt, relperm, grid, state, bc, 1)
        assert result.G_free_gas[1] == pytest.approx(ref_1['G_free_gas'], abs=1e-30)


# ═════════════════════════════════════════════════════════════
# D. Контейнеры данных
# ═════════════════════════════════════════════════════════════

class TestSimulationHistory:
    def test_empty_history(self):
        h = SimulationHistory()
        assert h.n_saved == 0
        assert h.times == []
        assert h.states == []

    def test_append_preserves_references(self):
        h = SimulationHistory()
        s = SimulationState(
            p=np.array([1e7]), Sg=np.array([0.0]),
            Rs=np.array([50.0]), T=np.array([350.0]),
            regime=np.array([2]), t=100.0)
        hr = HydroResult(
            state=s,
            G_o=np.array([-0.01, -0.01]),
            G_g=np.array([-0.5, -0.5]),
            G_free_gas=np.zeros(2),
            Q_o=np.array([-0.012, -0.012]),
            Q_g=np.zeros(2),
            u_o=np.array([-0.001, -0.0002]),
            u_g=np.zeros(2),
            m_o=np.array([-9.0, -9.0]),
            m_g=np.zeros(2),
            Gm_o=np.array([-8.5, -8.5]),
            Gm_g=np.array([-0.425, -0.425]),
            p_wf=1e7)
        wd = WellData(q_o_std=0.01, q_g_std=0.5, m_o_well=8.5,
                      m_g_well=0.425, p_wf=1e7, T_wf=350.0)

        h.append(t=100.0, state=s, hydro=hr, well=wd)
        assert h.n_saved == 1
        assert h.states[0] is s
        assert h.hydro_results[0] is hr
        assert h.well_data[0] is wd
        assert h.times[0] == 100.0

    def test_n_saved_tracks_count(self):
        h = SimulationHistory()
        for i in range(10):
            s = SimulationState(
                p=np.array([1e7]), Sg=np.array([0.0]),
                Rs=np.array([50.0]), T=np.array([350.0]),
                regime=np.array([2]), t=float(i))
            hr = HydroResult(
                state=s, G_o=np.zeros(2), G_g=np.zeros(2),
                G_free_gas=np.zeros(2), Q_o=np.zeros(2), Q_g=np.zeros(2),
                u_o=np.zeros(2), u_g=np.zeros(2), m_o=np.zeros(2),
                m_g=np.zeros(2), Gm_o=np.zeros(2), Gm_g=np.zeros(2),
                p_wf=1e7)
            wd = WellData(q_o_std=0.0, q_g_std=0.0, m_o_well=0.0,
                          m_g_well=0.0, p_wf=1e7, T_wf=350.0)
            h.append(t=float(i), state=s, hydro=hr, well=wd)
        assert h.n_saved == 10


# ═════════════════════════════════════════════════════════════
# E. PressureControl
# ═════════════════════════════════════════════════════════════

class TestPressureControl:
    def test_negative_raises(self):
        with pytest.raises(ValueError):
            PressureControl(-1.0)

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            PressureControl(0.0)

    def test_returns_p_wf(self):
        pc = PressureControl(15e6)
        assert pc.p_wf == 15e6

    def test_isinstance_well_control(self):
        assert isinstance(PressureControl(1e7), WellControl)

    def test_rate_control_not_supported(self, state_1ph, grid_1ph, pvt, relperm):
        """compute_fluxes — путь тестов и дублёров, управление по дебиту не поддержано.

        При заданном дебите p_wf здесь пришлось бы искать итерациями; в
        рабочем расчёте его выражает прототип (FEAT-020). Ловит: молчаливый
        расчёт с неверным p_wf вместо явного отказа.
        """
        bc = BoundaryConditions(well=RateControl(1e-3, 101325.0), p_ext=P_EXT,
                                T_ext=350.0, Rs_ext=RS0)
        with pytest.raises(NotImplementedError):
            compute_fluxes(state_1ph, grid_1ph, pvt, relperm, bc)
