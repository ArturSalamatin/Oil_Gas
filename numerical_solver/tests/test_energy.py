"""Тесты для EnergySolver (фаза 5).

Систематическая проверка 5 слагаемых уравнения энергии:
  накопление, конвекция, теплопроводность, JT (адиабатический), дегазация.

Каждый тест изолирует одно слагаемое, остальные = 0. Затем — комбинации.

Аналитические эталоны:
  A. Чистый адиабатический: T_new = T_old + Q_ad*dt/rho_cp_eff (точная формула)
  B. Чистая конвекция (lambda=0, mu_JT=0): T -> T_ext за достаточное число шагов
  C. Чистая теплопроводность (Q=0): T -> T_ext
  D. Равновесие: T=T_ext, Q=0 -> T не меняется
  E. Комбинации: конвекция + теплопроводность, JT + конвекция
"""

import warnings
import numpy as np
import pytest

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import (
    SimulationState, HydroResult, BoundaryConditions,
)
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.fluxes import compute_fluxes
from gpn_multiphase_solver.io.config import RockConfig
from gpn_multiphase_solver.energy.base import EnergySolver
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver


# ── Параметры ────────────────────────────────────────────────

R_WELL = 0.1
R_EXT = 50.0
H = 10.0
N = 20
K_PERM = 1e-13
PHI = 0.2

P0 = 20e6
P_WF = 10e6
T0 = 350.0
T_EXT = 350.0
RS0 = 50.0
RHO_O_STD = 850.0
RHO_G_STD = 0.85
DT = 3600.0

CP_OIL = 2000.0
CP_GAS = 1000.0


# ── Helpers ──────────────────────────────────────────────────

def _zero_hydro(state, N_cells):
    """HydroResult с нулевыми потоками."""
    Z = np.zeros(N_cells + 1)
    return HydroResult(
        state=state, G_o=Z, G_g=Z, G_free_gas=Z,
        Q_o=Z, Q_g=Z, u_o=Z, u_g=Z, m_o=Z, m_g=Z, Gm_o=Z, Gm_g=Z)


def _make_pvt(mu_JT_oil=0.0, mu_JT_gas=0.0, L_degas=0.0):
    return StandingFullPVT(
        rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD,
        T0=T0, Rs0=RS0, co_undersaturated=0.0,
        c_p_oil=CP_OIL, c_p_gas=CP_GAS,
        mu_JT_oil_val=mu_JT_oil, mu_JT_gas_val=mu_JT_gas,
        L_degas_val=L_degas)


def _rock(lambda_solid=1.5, lambda_oil=0.14, lambda_gas=0.04):
    return RockConfig(
        porosity=PHI, permeability=K_PERM,
        rho_cp_solid=1.25e6, lambda_solid=lambda_solid,
        lambda_oil=lambda_oil, lambda_gas=lambda_gas)


def _bc(T_ext, Rs_ext=RS0):
    """Граничные условия для энергетического решателя (DEBT-009).

    Rs_ext по умолчанию = RS0: во всех этих тестах контур насыщен,
    поэтому состав притока совпадает с начальным (eq. bc_Sg_ext).
    p_ext энергетическим решателем не используется — он работает на
    замороженных полях из hydro_result, — но поле обязательное.
    """
    return BoundaryConditions(
        well=PressureControl(P_WF), p_ext=P0,
        T_ext=T_ext, Rs_ext=Rs_ext, Sg_ext=0.0)


def _log_pressure_profile(grid, p_wf, p_ext):
    """Стационарный логарифмический профиль p(r)."""
    r = grid.r_centers
    return p_wf + (p_ext - p_wf) * np.log(r / grid.r_well) / np.log(grid.R_ext / grid.r_well)


# ═══════════════════════════════════════════════════════════
# A. ABC
# ═══════════════════════════════════════════════════════════

class TestABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            EnergySolver()

    def test_isinstance(self):
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
        assert isinstance(solver, EnergySolver)

    def test_returns_ndarray(self):
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
        state = SimulationState(p=np.full(N, P0), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, T0),
            regime=np.full(N, 2, dtype=int), t=0.0)
        T_new = solver.solve(_zero_hydro(state, N), state, DT, _bc(T_EXT))
        assert isinstance(T_new, np.ndarray)
        assert T_new.shape == (N,)


# ═══════════════════════════════════════════════════════════
# B. Чисто адиабатический эффект (Q=0, lambda=0, mu_JT != 0)
# ═══════════════════════════════════════════════════════════

class TestPureAdiabatic:
    """Нулевые потоки, нулевая теплопроводность, dp != 0.

    Аналитический эталон (точная формула):
      rho_cp_eff * (T_new - T_old) / dt = Q_ad
      Q_ad = phi * So * (1 + rho_o*cp_o*mu_JT_o) * dp/dt
      T_new = T_old + Q_ad * dt / rho_cp_eff
    """

    @pytest.fixture
    def setup(self):
        N_cells = 5
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        mu_JT_o = -3e-7  # К/Па
        pvt = _make_pvt(mu_JT_oil=mu_JT_o)
        rock = _rock(lambda_solid=0.0, lambda_oil=0.0, lambda_gas=0.0)
        solver = TridiagEnergySolver(grid, pvt, rock)

        P_OLD, P_NEW = 20e6, 15e6
        T_init = 350.0

        state_prev = SimulationState(
            p=np.full(N_cells, P_OLD), Sg=np.zeros(N_cells),
            Rs=np.full(N_cells, RS0), T=np.full(N_cells, T_init),
            regime=np.full(N_cells, 2, dtype=int), t=0.0)
        state_new = SimulationState(
            p=np.full(N_cells, P_NEW), Sg=np.zeros(N_cells),
            Rs=np.full(N_cells, RS0), T=np.full(N_cells, T_init),
            regime=np.full(N_cells, 2, dtype=int), t=DT)
        hydro = _zero_hydro(state_new, N_cells)

        # Аналитический эталон
        rho_o = pvt.rho_o(np.array([P_NEW]), np.array([RS0]))[0]
        factor = 1.0 + rho_o * CP_OIL * mu_JT_o
        Q_ad = PHI * 1.0 * factor * (P_NEW - P_OLD) / DT  # Вт/м3
        rho_cp_eff = (1 - PHI) * 1.25e6 + PHI * rho_o * CP_OIL
        dT = Q_ad * DT / rho_cp_eff
        T_expected = T_init + dT

        return solver, hydro, state_prev, T_expected, N_cells

    def test_T_matches_formula(self, setup):
        """T_new совпадает с аналитической формулой до 6 знаков."""
        solver, hydro, state_prev, T_expected, N_cells = setup
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            T_new = solver.solve(hydro, state_prev, DT, _bc(T0))
        np.testing.assert_allclose(T_new, T_expected, rtol=1e-6)

    def test_T_uniform(self, setup):
        """Без пространственных потоков: T одинакова во всех ячейках."""
        solver, hydro, state_prev, _, N_cells = setup
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            T_new = solver.solve(hydro, state_prev, DT, _bc(T0))
        np.testing.assert_allclose(T_new, T_new[0], rtol=1e-12)

    def test_cooling_when_dp_negative(self, setup):
        """dp < 0, mu_JT_o < 0 => factor ~ 0.54 > 0 => Q_ad < 0 => охлаждение."""
        solver, hydro, state_prev, T_expected, _ = setup
        assert T_expected < 350.0

    def test_concrete_dT(self, setup):
        """dT ~ -0.41 К при dp = -5 МПа, dt = 1 ч."""
        _, _, _, T_expected, _ = setup
        dT = T_expected - 350.0
        assert dT == pytest.approx(-0.414, abs=0.01)


# ═══════════════════════════════════════════════════════════
# C. Чистая конвекция (lambda=0, mu_JT=0, dp/dt=0)
# ═══════════════════════════════════════════════════════════

class TestPureConvection:
    """Нулевая теплопроводность, нулевой JT. Поток к скважине.
    Upstream несёт T_ext с контура. T -> T_ext за достаточное число шагов.
    """

    def test_converges_to_T_ext(self):
        """Маленькая сетка (R=5 м, N=5): T -> T_ext за 500 шагов."""
        N_cells = 5
        grid = LogRadialGrid(R_WELL, 5.0, H, N_cells, K_PERM)
        pvt = _make_pvt()
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        rock = _rock(lambda_solid=0.0, lambda_oil=0.0, lambda_gas=0.0)
        solver = TridiagEnergySolver(grid, pvt, rock)

        p = _log_pressure_profile(grid, P_WF, P0)
        bc = BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                                T_ext=350.0, Rs_ext=RS0)

        state = SimulationState(p=p, Sg=np.zeros(N_cells), Rs=np.full(N_cells, RS0),
            T=np.full(N_cells, 340.0), regime=np.full(N_cells, 2, dtype=int), t=0.0)
        hydro = compute_fluxes(state, grid, pvt, rp, bc)

        # dp/dt = 0 (p_old = p_new)
        T = np.full(N_cells, 340.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for step in range(500):
                state_prev = SimulationState(p=p, Sg=np.zeros(N_cells),
                    Rs=np.full(N_cells, RS0), T=T,
                    regime=np.full(N_cells, 2, dtype=int), t=step * DT)
                T = solver.solve(hydro, state_prev, DT, _bc(350.0))

        # Конвекция вымывает T_init = 340 → T_ext = 350
        np.testing.assert_allclose(T, 350.0, atol=0.01)

    def test_first_step_warms_last_cell(self):
        """Первый шаг: последняя ячейка (у контура) нагревается."""
        N_cells = 5
        grid = LogRadialGrid(R_WELL, 5.0, H, N_cells, K_PERM)
        pvt = _make_pvt()
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        rock = _rock(lambda_solid=0.0, lambda_oil=0.0, lambda_gas=0.0)
        solver = TridiagEnergySolver(grid, pvt, rock)

        p = _log_pressure_profile(grid, P_WF, P0)
        bc = BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                                T_ext=350.0, Rs_ext=RS0)
        state = SimulationState(p=p, Sg=np.zeros(N_cells), Rs=np.full(N_cells, RS0),
            T=np.full(N_cells, 340.0), regime=np.full(N_cells, 2, dtype=int), t=0.0)
        hydro = compute_fluxes(state, grid, pvt, rp, bc)
        state_prev = SimulationState(p=p, Sg=np.zeros(N_cells),
            Rs=np.full(N_cells, RS0), T=np.full(N_cells, 340.0),
            regime=np.full(N_cells, 2, dtype=int), t=0.0)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            T_new = solver.solve(hydro, state_prev, DT, _bc(350.0))
        assert T_new[-1] > 340.0


# ═══════════════════════════════════════════════════════════
# D. Чистая теплопроводность (Q=0, mu_JT=0, L=0)
# ═══════════════════════════════════════════════════════════

class TestPureConduction:
    """Нулевые потоки, mu_JT=0, L=0. Только кондуктивная диффузия.
    Стационар с Нейман на забое и Дирихле на контуре: T = T_ext = const.
    Маленькая сетка для быстрой сходимости (tau ~ R^2 * rho_cp / lambda).
    """

    def test_converges_to_T_ext(self):
        N_cells = 3
        grid = LogRadialGrid(R_WELL, 1.0, H, N_cells, K_PERM)
        pvt = _make_pvt()
        rock = _rock()
        solver = TridiagEnergySolver(grid, pvt, rock)

        T = np.full(N_cells, 340.0)
        for step in range(500):
            state = SimulationState(p=np.full(N_cells, P0), Sg=np.zeros(N_cells),
                Rs=np.full(N_cells, RS0), T=T,
                regime=np.full(N_cells, 2, dtype=int), t=step * 86400.0)
            hydro = _zero_hydro(state, N_cells)
            T = solver.solve(hydro, state, 86400.0, _bc(350.0))

        np.testing.assert_allclose(T, 350.0, atol=0.5)


# ═══════════════════════════════════════════════════════════
# E. Равновесие: T = T_ext, Q = 0 -> T не меняется
# ═══════════════════════════════════════════════════════════

class TestEquilibrium:
    def test_T_unchanged_at_equilibrium(self):
        """T = T_ext = 350, dp = 0, Q = 0 -> dT = 0."""
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        solver = TridiagEnergySolver(grid, _make_pvt(), _rock())

        state = SimulationState(p=np.full(N, P0), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, T_EXT),
            regime=np.full(N, 2, dtype=int), t=0.0)
        T_new = solver.solve(_zero_hydro(state, N), state, DT, _bc(T_EXT))
        np.testing.assert_allclose(T_new, T_EXT, atol=1e-10)

    def test_T_unchanged_with_flow_at_T_ext(self):
        """T = T_ext = 350, потоки к скважине, dp/dt = 0, mu_JT = 0, L = 0.
        Конвекция переносит T_ext -> T_ext. dT = 0."""
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt()
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = _log_pressure_profile(grid, P_WF, P0)
        state = SimulationState(p=p, Sg=np.zeros(N), Rs=np.full(N, RS0),
            T=np.full(N, T_EXT), regime=np.full(N, 2, dtype=int), t=0.0)
        bc = BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                                T_ext=T_EXT, Rs_ext=RS0)
        hydro = compute_fluxes(state, grid, pvt, rp, bc)
        # p_old = p_new -> dp/dt = 0
        state_prev = SimulationState(p=p.copy(), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, T_EXT),
            regime=np.full(N, 2, dtype=int), t=0.0)

        T_new = solver.solve(hydro, state_prev, DT, _bc(T_EXT))
        np.testing.assert_allclose(T_new, T_EXT, atol=1e-8)


# ═══════════════════════════════════════════════════════════
# F. Диагональное преобладание: T > 0 при T_old > 0, T_ext > 0
# ═══════════════════════════════════════════════════════════

class TestPositivity:
    """b > |a| + |c| => T_new > 0 если d > 0 (T_old > 0, T_ext > 0, источники малы)."""

    def test_no_flow(self):
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
        state = SimulationState(p=np.full(N, P0), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, 300.0),
            regime=np.full(N, 2, dtype=int), t=0.0)
        T_new = solver.solve(_zero_hydro(state, N), state, DT, _bc(350.0))
        assert np.all(T_new > 0)

    def test_with_flow(self):
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt()
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = _log_pressure_profile(grid, P_WF, P0)
        state = SimulationState(p=p, Sg=np.zeros(N), Rs=np.full(N, RS0),
            T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
        bc = BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                                T_ext=T_EXT, Rs_ext=RS0)
        hydro = compute_fluxes(state, grid, pvt, rp, bc)
        state_prev = SimulationState(p=p.copy(), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, T0),
            regime=np.full(N, 2, dtype=int), t=0.0)
        T_new = solver.solve(hydro, state_prev, DT, _bc(T_EXT))
        assert np.all(T_new > 0)


# ═══════════════════════════════════════════════════════════
# G. JT-охлаждение при снижении давления
# ═══════════════════════════════════════════════════════════

class TestJTCooling:
    """dp < 0, mu_JT_o < 0 => factor > 0 => Q_ad < 0 => T_new < T_old."""

    def test_cooling(self):
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt(mu_JT_oil=-3e-7, mu_JT_gas=4e-6)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        state_prev = SimulationState(p=np.full(N, P0), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, T0),
            regime=np.full(N, 2, dtype=int), t=0.0)
        # Давление снизилось на 5 МПа
        state_new = SimulationState(p=np.full(N, P0 - 5e6), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, T0),
            regime=np.full(N, 2, dtype=int), t=DT)
        hydro = _zero_hydro(state_new, N)

        T_new = solver.solve(hydro, state_prev, DT, _bc(T0))
        assert np.all(T_new < T0)


# ═══════════════════════════════════════════════════════════
# H. Комбинация: конвекция + теплопроводность (mu_JT=0, L=0, dp/dt=0)
# ═══════════════════════════════════════════════════════════

class TestConvectionPlusConduction:
    """Оба механизма переноса тепла к T_ext. Быстрее, чем каждый отдельно."""

    def test_faster_than_conduction_alone(self):
        N_cells = 5
        grid = LogRadialGrid(R_WELL, 5.0, H, N_cells, K_PERM)
        pvt = _make_pvt()
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)

        p = _log_pressure_profile(grid, P_WF, P0)
        bc = BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                                T_ext=350.0, Rs_ext=RS0)
        state_flow = SimulationState(p=p, Sg=np.zeros(N_cells),
            Rs=np.full(N_cells, RS0), T=np.full(N_cells, 340.0),
            regime=np.full(N_cells, 2, dtype=int), t=0.0)
        hydro = compute_fluxes(state_flow, grid, pvt, rp, bc)

        # С конвекцией + теплопроводностью
        solver_both = TridiagEnergySolver(grid, pvt, _rock())
        T_both = np.full(N_cells, 340.0)
        for step in range(50):
            sp = SimulationState(p=p, Sg=np.zeros(N_cells), Rs=np.full(N_cells, RS0),
                T=T_both, regime=np.full(N_cells, 2, dtype=int), t=step * DT)
            T_both = solver_both.solve(hydro, sp, DT, _bc(350.0))

        # Только теплопроводность (Q=0)
        solver_cond = TridiagEnergySolver(grid, pvt, _rock())
        T_cond = np.full(N_cells, 340.0)
        for step in range(50):
            sp = SimulationState(p=np.full(N_cells, P0), Sg=np.zeros(N_cells),
                Rs=np.full(N_cells, RS0), T=T_cond,
                regime=np.full(N_cells, 2, dtype=int), t=step * DT)
            T_cond = solver_cond.solve(_zero_hydro(sp, N_cells), sp, DT,
                                       _bc(350.0))

        # Конвекция + теплопроводность ближе к T_ext, чем теплопроводность одна
        err_both = np.max(np.abs(T_both - 350.0))
        err_cond = np.max(np.abs(T_cond - 350.0))
        assert err_both < err_cond


# ═══════════════════════════════════════════════════════════
# I. Устойчивость: 20 шагов с полным набором эффектов
# ═══════════════════════════════════════════════════════════

class TestStability:
    def test_T_bounded_after_many_steps(self):
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt(mu_JT_oil=-3e-7, mu_JT_gas=4e-6)
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = _log_pressure_profile(grid, P_WF, P0)
        bc = BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                                T_ext=T_EXT, Rs_ext=RS0)
        state = SimulationState(p=p, Sg=np.zeros(N), Rs=np.full(N, RS0),
            T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
        hydro = compute_fluxes(state, grid, pvt, rp, bc)

        T = np.full(N, T0)
        state_prev = SimulationState(p=np.full(N, P0), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=T, regime=np.full(N, 2, dtype=int), t=0.0)

        for step in range(20):
            T_new = solver.solve(hydro, state_prev, DT, _bc(T_EXT))
            state_prev = SimulationState(p=p, Sg=np.zeros(N),
                Rs=np.full(N, RS0), T=T_new,
                regime=np.full(N, 2, dtype=int), t=(step + 1) * DT)
            T = T_new

        assert np.all(T > 200), f"T too low: min={T.min()}"
        assert np.all(T < 500), f"T too high: max={T.max()}"


# ═══════════════════════════════════════════════════════════
# J. Нулевая теплопроводность фаз, ненулевая породы
# ═══════════════════════════════════════════════════════════

class TestZeroPhaseConduction:
    """lambda_oil = lambda_gas = 0, lambda_solid > 0.
    Эффективная lambda_eff = (1-phi)*lambda_solid > 0. Теплопроводность работает.
    """

    def test_still_conducts(self):
        N_cells = 3
        grid = LogRadialGrid(R_WELL, 1.0, H, N_cells, K_PERM)
        pvt = _make_pvt()
        # lambda фаз = 0, породы = 1.5
        rock = _rock(lambda_solid=1.5, lambda_oil=0.0, lambda_gas=0.0)
        solver = TridiagEnergySolver(grid, pvt, rock)

        T = np.full(N_cells, 340.0)
        for step in range(500):
            state = SimulationState(p=np.full(N_cells, P0), Sg=np.zeros(N_cells),
                Rs=np.full(N_cells, RS0), T=T,
                regime=np.full(N_cells, 2, dtype=int), t=step * 86400.0)
            T = solver.solve(_zero_hydro(state, N_cells), state, 86400.0,
                             _bc(350.0))

        # lambda_eff = (1-0.2)*1.5 = 1.2 > 0 -> T -> T_ext
        np.testing.assert_allclose(T, 350.0, atol=1.0)


# ═══════════════════════════════════════════════════════════
# K. Тесты отдельных методов TridiagEnergySolver
# ═══════════════════════════════════════════════════════════

class TestComputeCellProperties:
    """compute_cell_properties: rho_cp_eff (eq. 5), lambda_eff (eq. 7)."""

    def test_rho_cp_eff_formula(self):
        """rho_cp_eff = (1-phi)*rho_cp_s + phi*(So*rho_o*cp_o + Sg*rho_g*cp_g).
        При Sg=0: rho_cp_eff = (1-phi)*rho_cp_s + phi*rho_o*cp_o.
        """
        grid = LogRadialGrid(R_WELL, R_EXT, H, 3, K_PERM)
        pvt = _make_pvt()
        rock = _rock()
        solver = TridiagEnergySolver(grid, pvt, rock)

        p = np.array([15e6, 18e6, 20e6])
        Sg = np.zeros(3)
        Rs = np.full(3, RS0)
        So = 1.0 - Sg
        T_old = np.full(3, T0)

        props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)

        # Вычисляем эталон вручную
        rho_o = pvt.rho_o(p, Rs)
        expected = (1 - PHI) * 1.25e6 + PHI * rho_o * CP_OIL
        np.testing.assert_allclose(props['rho_cp_eff'], expected, rtol=1e-14)

    def test_lambda_eff_formula(self):
        """lambda_eff = (1-phi)*lambda_s + phi*(So*lambda_o + Sg*lambda_g).
        При Sg=0: lambda_eff = (1-phi)*lambda_s + phi*lambda_o.
        """
        grid = LogRadialGrid(R_WELL, R_EXT, H, 3, K_PERM)
        pvt = _make_pvt()
        rock = _rock()
        solver = TridiagEnergySolver(grid, pvt, rock)

        p = np.array([15e6, 18e6, 20e6])
        Sg = np.zeros(3)
        Rs = np.full(3, RS0)
        So = 1.0 - Sg
        T_old = np.full(3, T0)

        props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)

        expected = (1 - PHI) * 1.5 + PHI * 0.14  # lambda_solid=1.5, lambda_oil=0.14
        np.testing.assert_allclose(props['lambda_eff'], expected, rtol=1e-14)

    def test_lambda_eff_two_phase(self):
        """Двухфазная: lambda_eff = (1-phi)*lambda_s + phi*(So*lambda_o + Sg*lambda_g)."""
        grid = LogRadialGrid(R_WELL, R_EXT, H, 2, K_PERM)
        pvt = _make_pvt()
        rock = _rock()
        solver = TridiagEnergySolver(grid, pvt, rock)

        p = np.array([15e6, 18e6])
        Sg = np.array([0.3, 0.0])
        Rs = np.array([30.0, RS0])
        So = 1.0 - Sg
        T_old = np.full(2, T0)

        props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)

        # Ячейка 0: So=0.7, Sg=0.3
        lam_0 = (1 - PHI) * 1.5 + PHI * (0.7 * 0.14 + 0.3 * 0.04)
        # Ячейка 1: So=1.0, Sg=0.0
        lam_1 = (1 - PHI) * 1.5 + PHI * 0.14
        np.testing.assert_allclose(props['lambda_eff'], [lam_0, lam_1], rtol=1e-14)


class TestComputeAdiabatic:
    """compute_adiabatic: Q_ad = phi * Sigma_alpha S_alpha * (1 + rho*cp*mu_JT) * dp/dt."""

    def test_formula_single_phase(self):
        """Однофазный (Sg=0): Q_ad = phi * (1 + rho_o*cp_o*mu_JT_o) * dp/dt."""
        grid = LogRadialGrid(R_WELL, R_EXT, H, 3, K_PERM)
        mu_JT_o = -3e-7
        pvt = _make_pvt(mu_JT_oil=mu_JT_o)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = np.array([15e6, 18e6, 20e6])
        p_old = np.full(3, 20e6)
        Sg = np.zeros(3)
        So = np.ones(3)
        rho_o = pvt.rho_o(p, np.full(3, RS0))
        rho_g = pvt.rho_g(p)
        c_p_o = np.full(3, CP_OIL)
        c_p_g = np.full(3, CP_GAS)
        mu_JT_o_arr = np.full(3, mu_JT_o)
        mu_JT_g_arr = np.zeros(3)
        dt = 3600.0

        Q_ad = solver.compute_adiabatic(
            So, Sg, rho_o, rho_g, c_p_o, c_p_g,
            mu_JT_o_arr, mu_JT_g_arr, p, p_old, dt)

        # Эталон
        dp_dt = (p - p_old) / dt
        expected = PHI * (1.0 + rho_o * CP_OIL * mu_JT_o) * dp_dt
        np.testing.assert_allclose(Q_ad, expected, rtol=1e-14)

    def test_zero_dp_gives_zero(self):
        """dp = 0 -> Q_ad = 0."""
        grid = LogRadialGrid(R_WELL, R_EXT, H, 3, K_PERM)
        pvt = _make_pvt(mu_JT_oil=-3e-7)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = np.full(3, 20e6)
        So = np.ones(3)
        Sg = np.zeros(3)
        rho_o = pvt.rho_o(p, np.full(3, RS0))
        rho_g = pvt.rho_g(p)

        Q_ad = solver.compute_adiabatic(
            So, Sg, rho_o, rho_g,
            np.full(3, CP_OIL), np.full(3, CP_GAS),
            np.full(3, -3e-7), np.zeros(3),
            p, p, 3600.0)

        np.testing.assert_allclose(Q_ad, 0.0, atol=1e-30)


class TestComputeConductiveTransmissibility:
    """compute_conductive_transmissibility: Q_T = geom * lambda_face."""

    def test_uniform_lambda(self):
        """При однородном lambda_eff:
        lambda_face = lam / (w_L + w_R) (гармоническое среднее с ненормированными весами).
        Q_T = geom * lambda_face.
        """
        N_cells = 5
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt()
        solver = TridiagEnergySolver(grid, pvt, _rock())

        lam_val = 1.228
        lambda_eff = np.full(N_cells, lam_val)

        Q_T_int, _ = solver.compute_conductive_transmissibility(lambda_eff, N_cells)

        # Последовательные сопротивления: Q_T = 2πh / (w_L/λ + w_R/λ) = 2πhλ / (w_L + w_R)
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        expected = 2.0 * np.pi * grid.h * lam_val / (w_L + w_R)
        np.testing.assert_allclose(Q_T_int, expected, rtol=1e-12)

    def test_Q_T_ext(self):
        """Q_T_ext = (2*pi*h / ln(R_ext/r_c[-1])) * lambda_eff[-1]."""
        N_cells = 5
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt()
        solver = TridiagEnergySolver(grid, pvt, _rock())

        lam_val = 1.228
        lambda_eff = np.full(N_cells, lam_val)

        _, Q_T_ext = solver.compute_conductive_transmissibility(lambda_eff, N_cells)

        geom_ext = 2.0 * np.pi * grid.h / np.log(grid.R_ext / grid.r_centers[-1])
        expected = geom_ext * lam_val
        assert Q_T_ext == pytest.approx(expected, rel=1e-10)

    def test_zero_lambda_gives_zero_Q_T(self):
        """lambda_eff = 0 -> Q_T = 0 (нулевая теплопроводность)."""
        N_cells = 3
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt()
        rock = _rock(lambda_solid=0.0, lambda_oil=0.0, lambda_gas=0.0)
        solver = TridiagEnergySolver(grid, pvt, rock)

        lambda_eff = np.zeros(N_cells)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
                lambda_eff, N_cells)

        np.testing.assert_allclose(Q_T_int, 0.0, atol=1e-30)
        assert Q_T_ext == pytest.approx(0.0, abs=1e-30)


class TestComputeDegassing:
    """compute_degassing: Q_deg = -L * mdot."""

    def test_zero_when_Rs_constant(self):
        """Rs = const (однофазная зона) -> ΔRs = 0, mdot = 0, Q_deg = 0."""
        N_cells = 3
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt(L_degas=168000.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        So = np.ones(N_cells)
        Sg = np.zeros(N_cells)
        Rs = np.full(N_cells, RS0)
        Rs_old = np.full(N_cells, RS0)  # Rs не изменилось
        Bo = pvt.Bo(np.full(N_cells, P0), Rs)
        G_o = np.full(N_cells + 1, -0.01)  # постоянный G_o -> R_conv = G_o*Rs = const
        L = np.full(N_cells, 168000.0)

        # Rs_ext = RS0: контур насыщен, состав притока совпадает с Rs в ячейках,
        # поэтому обе ветви контурной грани дают одно значение (DEBT-009)
        Q_deg = solver.compute_degassing(
            So, Sg, Rs, Rs_old, Bo, G_o, L, DT, N_cells, RS0)

        # Rs[j] = Rs_old[j] -> mdot_time = 0
        # G_o = const, Rs = const -> R_conv[j+1] - R_conv[j] = 0 -> mdot_conv = 0
        np.testing.assert_allclose(Q_deg, 0.0, atol=1e-20)

    def test_inflow_uses_boundary_composition(self):
        """Приток с контура (G_o < 0): upstream = ГУ, а не ячейка N-1.

        Физика: через контур поступает нефть с составом Rs^0
        (eq. bc_Sg_ext, problem_statement.tex:1469-1472). Если в ячейке
        N-1 началось разгазирование (Rs < Rs^0), схема обязана взять
        на контурной грани состав ПРИТОКА, а не обеднённый состав
        последней ячейки. DEBT-009.

        Rs_old = Rs намеренно: это обнуляет временную часть mdot_time
        и изолирует конвективный вклад — именно то, что чинит DEBT-009.
        """
        N_cells = 3
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt(L_degas=168000.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        So = np.ones(N_cells)
        Sg = np.zeros(N_cells)
        # Ячейка N-1 обеднена газом: разгазирование у контура
        Rs = np.full(N_cells, RS0)
        Rs[-1] = 0.8 * RS0
        Rs_old = Rs.copy()          # mdot_time = 0
        Bo = pvt.Bo(np.full(N_cells, P0), Rs)
        G_o = np.full(N_cells + 1, -0.01)   # втекание на всех гранях
        L = np.full(N_cells, 168000.0)

        Q_deg = solver.compute_degassing(
            So, Sg, Rs, Rs_old, Bo, G_o, L, DT, N_cells, RS0)

        # Восстанавливаем ожидаемый Q_deg последней ячейки из формулы схемы:
        #   mdot_time = 0  =>  Q_deg[-1] = -L * mdot_conv[-1]
        #   mdot_conv[-1] = -rho_g_std * (R_conv[N] - R_conv[N-1]) / V[-1]
        V = grid.volumes
        rho_g_std = pvt.rho_g_std
        # Внутренняя грань N-1 при G_o < 0: upstream — ячейка N-1
        R_conv_inner = G_o[N_cells - 1] * Rs[N_cells - 1]
        # Контурная грань при притоке: состав ГУ
        R_conv_ext_expected = G_o[N_cells] * RS0

        mdot_conv_expected = -rho_g_std * (
            R_conv_ext_expected - R_conv_inner) / V[-1]
        Q_deg_expected = -L[-1] * mdot_conv_expected

        np.testing.assert_allclose(Q_deg[-1], Q_deg_expected, rtol=1e-12)

        # Контроль невырожденности: со старым (дефектным) поведением на
        # контуре стоял бы Rs[N-1] = 0.8*RS0, и Q_deg[-1] был бы другим.
        # Без этой проверки тест мог бы проходить на обеих ветвях.
        R_conv_ext_buggy = G_o[N_cells] * Rs[-1]
        mdot_conv_buggy = -rho_g_std * (R_conv_ext_buggy - R_conv_inner) / V[-1]
        Q_deg_buggy = -L[-1] * mdot_conv_buggy
        assert not np.isclose(Q_deg_expected, Q_deg_buggy), \
            "тест вырожден: дефектная и корректная ветви дают одно значение"

    def test_outflow_ignores_boundary_composition(self):
        """Отток через контур (G_o > 0): upstream = ячейка N-1, Rs_ext не влияет.

        Симметричная проверка к test_inflow_uses_boundary_composition:
        правка DEBT-009 не должна затрагивать ветвь оттока. Если реализация
        «упростит» ветвление и подставит Rs_ext в обе ветви, этот тест упадёт.
        """
        N_cells = 3
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt(L_degas=168000.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        So = np.ones(N_cells)
        Sg = np.zeros(N_cells)
        Rs = np.full(N_cells, RS0)
        Rs[-1] = 0.8 * RS0
        Rs_old = Rs.copy()
        Bo = pvt.Bo(np.full(N_cells, P0), Rs)
        G_o = np.full(N_cells + 1, +0.01)   # отток наружу на всех гранях
        L = np.full(N_cells, 168000.0)

        # Два разных Rs_ext должны дать ОДИН результат: при оттоке
        # выше по потоку лежит ячейка N-1, состав контура не участвует
        Q_deg_a = solver.compute_degassing(
            So, Sg, Rs, Rs_old, Bo, G_o, L, DT, N_cells, RS0)
        Q_deg_b = solver.compute_degassing(
            So, Sg, Rs, Rs_old, Bo, G_o, L, DT, N_cells, 0.5 * RS0)

        np.testing.assert_allclose(Q_deg_a, Q_deg_b, rtol=1e-14)


class TestAssembleTridiag:
    """assemble_tridiag: проверка диагонального преобладания b > |a| + |c|."""

    def test_diagonal_dominance_no_flow(self):
        """Без потоков: b > |a| + |c| для каждой ячейки."""
        N_cells = 10
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt()
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = np.full(N_cells, P0)
        Sg = np.zeros(N_cells)
        Rs = np.full(N_cells, RS0)
        So = 1.0 - Sg
        T_old = np.full(N_cells, T0)

        props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)
        Q_o = np.zeros(N_cells + 1)
        Q_g = np.zeros(N_cells + 1)
        Phi_plus, Phi_minus, _, _ = solver.compute_convective_coefficients(
            Q_o, Q_g, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N_cells)
        Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
            props['lambda_eff'], N_cells)

        J_jt = np.zeros(N_cells)
        Q_ad = np.zeros(N_cells)
        Q_deg = np.zeros(N_cells)

        a, b, c, d = solver.assemble_tridiag(
            N_cells, DT, T_old, T_EXT,
            props['rho_cp_eff'], Q_T_int, Q_T_ext,
            Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)

        # b > |a| + |c| (строгое диагональное преобладание)
        for j in range(N_cells):
            assert b[j] > abs(a[j]) + abs(c[j]), \
                f"Diagonal dominance violated at j={j}: b={b[j]}, |a|+|c|={abs(a[j])+abs(c[j])}"

    def test_diagonal_dominance_with_flow(self):
        """С потоками к скважине: b > |a| + |c|."""
        N_cells = 10
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt()
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = _log_pressure_profile(grid, P_WF, P0)
        Sg = np.zeros(N_cells)
        Rs = np.full(N_cells, RS0)
        So = 1.0 - Sg
        T_old = np.full(N_cells, T0)

        state = SimulationState(p=p, Sg=Sg, Rs=Rs, T=T_old,
            regime=np.full(N_cells, 2, dtype=int), t=0.0)
        bc = BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                                T_ext=T_EXT, Rs_ext=RS0)
        hydro = compute_fluxes(state, grid, pvt, rp, bc)

        props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)
        Phi_plus, Phi_minus, _, _ = solver.compute_convective_coefficients(
            hydro.Q_o, hydro.Q_g, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N_cells)
        Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
            props['lambda_eff'], N_cells)

        J_jt = np.zeros(N_cells)
        Q_ad = np.zeros(N_cells)
        Q_deg = np.zeros(N_cells)

        a, b, c, d = solver.assemble_tridiag(
            N_cells, DT, T_old, T_EXT,
            props['rho_cp_eff'], Q_T_int, Q_T_ext,
            Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)

        for j in range(N_cells):
            assert b[j] > abs(a[j]) + abs(c[j]), \
                f"Diagonal dominance violated at j={j}"

    def test_boundary_conditions_a0_cN(self):
        """a[0] = 0 (Нейман на забое), c[N-1] = 0 (Дирихле на контуре)."""
        N_cells = 5
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = _make_pvt()
        solver = TridiagEnergySolver(grid, pvt, _rock())

        props = solver.compute_cell_properties(
            np.full(N_cells, P0), np.zeros(N_cells),
            np.full(N_cells, RS0), np.ones(N_cells), np.full(N_cells, T0))
        Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
            props['lambda_eff'], N_cells)
        Phi_plus = np.zeros(N_cells + 1)
        Phi_minus = np.zeros(N_cells + 1)

        a, b, c, d = solver.assemble_tridiag(
            N_cells, DT, np.full(N_cells, T0), T_EXT,
            props['rho_cp_eff'], Q_T_int, Q_T_ext,
            Phi_plus, Phi_minus,
            np.zeros(N_cells), np.zeros(N_cells), np.zeros(N_cells))

        assert a[0] == 0.0, "a[0] must be 0 (Neumann BC)"
        assert c[N_cells - 1] == 0.0, "c[N-1] must be 0 (Dirichlet BC)"
