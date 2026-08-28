"""Тесты для fluxes.py (фаза 3).

Стационарный логарифмический профиль давления:
  p(r) = p_wf + (p_ext - p_wf) * ln(r/r_w) / ln(R_ext/r_w)

Однофазный поток нефти (Sg=0, krg=0, kro=1):
  G_o = const на всех гранях (стационар)
  Q_o = G_o * Bo — зависит от Bo(p) на грани
  u_o = Q_o / (2πhr)

Все потоки < 0 (к скважине).
"""

import numpy as np
import pytest

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.fluxes import compute_fluxes


# ── Параметры задачи ─────────────────────────────────────────

R_WELL = 0.1
R_EXT = 50.0
H = 10.0
N = 20
K_PERM = 1e-13  # м²

P_EXT = 20e6    # Па
P_WF = 10e6     # Па
T0 = 350.0      # К

RHO_O_STD = 850.0
RHO_G_STD = 0.85
RS0 = 50.0


@pytest.fixture
def grid():
    return LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=N, k=K_PERM)


@pytest.fixture
def pvt():
    return StandingFullPVT(rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD,
                           T0=T0, Rs0=RS0, co_undersaturated=0.0)


@pytest.fixture
def relperm():
    return CoreyRP(S_or=0.2, S_gc=0.05, n_o=2.0, n_g=2.0,
                   kro_max=1.0, krg_max=0.8)


@pytest.fixture
def log_pressure_state(grid, pvt):
    """Стационарный логарифмический профиль, Sg=0."""
    r = grid.r_centers
    log_ratio = np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
    p = P_WF + (P_EXT - P_WF) * log_ratio

    Sg = np.zeros(N)
    Rs = np.full(N, RS0)
    T = np.full(N, T0)
    regime = np.full(N, 2, dtype=int)

    return SimulationState(p=p, Sg=Sg, Rs=Rs, T=T, regime=regime, t=0.0)


@pytest.fixture
def bc():
    return BoundaryConditions(
        well=PressureControl(P_WF),
        p_ext=P_EXT,
        T_ext=T0,
        Rs_ext=RS0,
        Sg_ext=0.0,
    )


@pytest.fixture
def result(log_pressure_state, grid, pvt, relperm, bc):
    return compute_fluxes(log_pressure_state, grid, pvt, relperm, bc)


# ── Тесты формы массивов ─────────────────────────────────────

class TestShape:
    def test_G_o_shape(self, result):
        assert result.G_o.shape == (N + 1,)

    def test_G_g_shape(self, result):
        assert result.G_g.shape == (N + 1,)

    def test_G_free_gas_shape(self, result):
        assert result.G_free_gas.shape == (N + 1,)

    def test_Q_o_shape(self, result):
        assert result.Q_o.shape == (N + 1,)

    def test_Q_g_shape(self, result):
        assert result.Q_g.shape == (N + 1,)

    def test_u_o_shape(self, result):
        assert result.u_o.shape == (N + 1,)

    def test_u_g_shape(self, result):
        assert result.u_g.shape == (N + 1,)

    def test_m_o_shape(self, result):
        assert result.m_o.shape == (N + 1,)

    def test_m_g_shape(self, result):
        assert result.m_g.shape == (N + 1,)

    def test_Gm_o_shape(self, result):
        assert result.Gm_o.shape == (N + 1,)

    def test_Gm_g_shape(self, result):
        assert result.Gm_g.shape == (N + 1,)


# ── Знаки (типичный поток к скважине) ────────────────────────

class TestSigns:
    """При p_ext > p_wf все потоки к скважине (< 0)."""

    def test_G_o_negative(self, result):
        assert np.all(result.G_o < 0)

    def test_G_g_negative(self, result):
        assert np.all(result.G_g <= 0)

    def test_Q_o_negative(self, result):
        assert np.all(result.Q_o < 0)

    def test_u_o_negative(self, result):
        assert np.all(result.u_o < 0)

    def test_m_o_negative(self, result):
        assert np.all(result.m_o < 0)

    def test_Gm_o_negative(self, result):
        assert np.all(result.Gm_o < 0)


# ── Стационар: G_o = const на всех гранях ────────────────────

class TestStationaryFlux:
    """При логарифмическом профиле давления и однофазном потоке
    (kro=1, krg=0, Bo=const т.к. co=0):
    G_o[f] = T_f * (kro/(mu_o*Bo))_up * dp_f — одинаковый на всех гранях.
    """

    def test_G_o_constant(self, result):
        """G_o одинаков на всех гранях (стационарный поток)."""
        G_ref = result.G_o[0]
        np.testing.assert_allclose(result.G_o, G_ref, rtol=1e-6)

    def test_G_g_equals_Rs_times_G_o(self, result):
        """При Sg=0 (однофазный): G_g = Rs*G_o, G_free_gas = 0."""
        np.testing.assert_allclose(result.G_g, RS0 * result.G_o, rtol=1e-10)

    def test_G_free_gas_zero(self, result):
        """При Sg=0: krg=0 → G_free_gas = 0."""
        np.testing.assert_allclose(result.G_free_gas, 0.0, atol=1e-20)

    def test_Q_g_zero(self, result):
        """При Sg=0: krg=0 → Q_g = 0."""
        np.testing.assert_allclose(result.Q_g, 0.0, atol=1e-20)

    def test_u_g_zero(self, result):
        np.testing.assert_allclose(result.u_g, 0.0, atol=1e-20)


# ── Дебит скважины ───────────────────────────────────────────

class TestWellRate:
    def test_q_o_std_positive(self, result):
        """Дебит = -G_o[0] > 0."""
        q_o_std = -result.G_o[0]
        assert q_o_std > 0

    def test_q_o_std_nonzero(self, result):
        """Дебит конечен и ненулевой."""
        q_o_std = -result.G_o[0]
        assert q_o_std > 1e-10


# ── Формула G_o на внутренней грани ──────────────────────────

class TestFormulaReproduction:
    """Воспроизведение формулы G_o[f] = T_f * mob_o_up * dp на одной грани."""

    def test_G_o_face_1(self, result, grid, pvt, relperm, log_pressure_state):
        f = 1
        p = log_pressure_state.p
        Rs = log_pressure_state.Rs
        Sg = log_pressure_state.Sg

        dp = p[f - 1] - p[f]
        # dp < 0 (типично) → upstream = ячейка f
        if dp >= 0:
            up = f - 1
        else:
            up = f

        Bo_up = pvt.Bo(np.array([p[up]]), np.array([Rs[up]]))[0]
        mu_o_up = pvt.mu_o(np.array([p[up]]), np.array([Rs[up]]))[0]
        kro_up = relperm.kro(np.array([Sg[up]]))[0]

        mob = kro_up / (mu_o_up * Bo_up)
        G_o_expected = grid.trans_internal[f - 1] * mob * dp

        assert result.G_o[f] == pytest.approx(G_o_expected, rel=1e-12)


# ── Связи между величинами ───────────────────────────────────

class TestRelations:
    """Проверка связей Q_o = G_o * Bo_up, u_o = Q_o / (2πhr), etc."""

    def test_u_o_equals_Q_o_over_area(self, result, grid):
        area = 2.0 * np.pi * grid.h * grid.r_faces
        np.testing.assert_allclose(result.u_o, result.Q_o / area, rtol=1e-12)

    def test_Gm_o_equals_rho_std_times_G_o(self, result, pvt):
        np.testing.assert_allclose(result.Gm_o, pvt.rho_o_std * result.G_o,
                                   rtol=1e-14)

    def test_Gm_g_equals_rho_std_times_G_g(self, result, pvt):
        np.testing.assert_allclose(result.Gm_g, pvt.rho_g_std * result.G_g,
                                   rtol=1e-14)


# ── Баланс масс (стационар) ─────────────────────────────────

class TestMassBalance:
    """При стационаре: G_o[j+1] - G_o[j] = 0 для каждой ячейки."""

    def test_oil_balance_per_cell(self, result):
        residual = result.G_o[1:] - result.G_o[:-1]
        np.testing.assert_allclose(residual, 0.0, atol=1e-12)

    def test_gas_balance_per_cell(self, result):
        residual = result.G_g[1:] - result.G_g[:-1]
        np.testing.assert_allclose(residual, 0.0, atol=1e-12)

    def test_global_balance(self, result):
        """Поток на забое = поток на контуре (стационар)."""
        assert result.G_o[0] == pytest.approx(result.G_o[-1], rel=1e-6)


# ── Аналитическое значение G_o для однофазного потока ────────

class TestAnalyticalRate:
    """Аналитический дебит однофазного стационарного потока:
    G_o = (2πhk / (μ_o * Bo * ln(R/rw))) * (p_wf - p_ext) / Bo_ст
    Упрощённо: Q_o = 2πhk*(p_wf-p_ext)/(μ_o*ln(R/rw))
    G_o = Q_o / Bo
    """

    def test_G_o_analytical(self, result, pvt):
        # Однофазная, Sg=0, средние свойства (p ~ среднее)
        p_avg = (P_WF + P_EXT) / 2.0
        Rs_arr = np.array([RS0])
        p_arr = np.array([p_avg])

        Bo_avg = pvt.Bo(p_arr, Rs_arr)[0]
        mu_o_avg = pvt.mu_o(p_arr, Rs_arr)[0]

        Q_o_analytical = (2.0 * np.pi * H * K_PERM * (P_WF - P_EXT)
                          / (mu_o_avg * np.log(R_EXT / R_WELL)))
        G_o_analytical = Q_o_analytical / Bo_avg

        # co=0 → Bo не зависит от p → mob=const → точная формула
        # Но upstream берёт Bo в ячейке, а не среднее → приближённо
        # Допуск ~10% из-за дискретизации upstream
        assert result.G_o[0] == pytest.approx(G_o_analytical, rel=0.1)


# ── Валидация PressureControl ────────────────────────────────

class TestPressureControl:
    def test_negative_p_wf_raises(self):
        with pytest.raises(ValueError):
            PressureControl(-1.0)

    def test_zero_p_wf_raises(self):
        with pytest.raises(ValueError):
            PressureControl(0.0)

    def test_boundary_pressure_returns_p_wf(self, log_pressure_state,
                                             grid, pvt, relperm):
        pc = PressureControl(P_WF)
        assert pc.boundary_pressure(log_pressure_state, grid, pvt, relperm) == P_WF
