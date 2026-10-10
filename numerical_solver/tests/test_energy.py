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
        Q_o=Z, Q_g=Z, u_o=Z, u_g=Z, m_o=Z, m_g=Z, Gm_o=Z, Gm_g=Z,
        p_wf=state.p[0])   # потока нет: давление на забое = p[0]


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


def _bc(T_ext, Rs_ext=RS0, p_ext=P0):
    """Граничные условия для энергетического решателя (DEBT-009).

    Rs_ext по умолчанию = RS0: во всех этих тестах контур насыщен,
    поэтому состав притока совпадает с начальным (eq:bc_Sg_ext).

    p_ext, T_ext, Rs_ext используются энергетическим решателем при
    втекании через контурную грань: свойства фаз берутся при условиях
    контура (_ext_properties, eq:bc_props_ext, DEBT-017). Прежде здесь
    было сказано, что p_ext решателем не используется, — после DEBT-017
    это неверно. Параметр p_ext оставлен изменяемым: тесты контурной
    грани задают его отличным от давления в ячейке N-1, иначе ветви
    «контур» и «ячейка N-1» неразличимы.
    """
    return BoundaryConditions(
        well=PressureControl(P_WF), p_ext=p_ext,
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
# F1. СЛАУ в отклонениях от T_ext (DEBT-043)
# ═══════════════════════════════════════════════════════════

class TestDeviationForm:
    """СЛАУ в отклонениях θ = T − T_ext — та же система, что в абсолютной T (DEBT-043)."""

    def test_solution_matches_absolute_form(self):
        """θ + T_ext совпадает с решением той же СЛАУ, собранной в абсолютной T.

        Решатель подаёт assemble_tridiag отклонения T^n − T_ext и 0.
        Тест перехватывает эти аргументы и коэффициенты, собирает ту же
        систему заново по АБСОЛЮТНЫМ T^n и T_ext (исходным
        assemble_tridiag) и решает её. Независимая сборка ловит неверный
        сдвиг — например, несдвинутую T_ext в граничной строке (замер
        аудита: расхождение 0.45 K). Расхождение при верном сдвиге —
        округление абсолютной формы: допуск 1e-9 K (замер 1.7e-13 K).
        Условия: приток через контур (логарифмический p), JT и
        теплопроводность включены, T^n = 345 K ≠ T_ext = 350 K — чтобы
        отклонения и граничная строка были нагружены.
        """
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt(mu_JT_oil=-4e-7)
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = _log_pressure_profile(grid, P_WF, P0)
        state = SimulationState(p=p, Sg=np.zeros(N), Rs=np.full(N, RS0),
            T=np.full(N, 345.0), regime=np.full(N, 2, dtype=int), t=0.0)
        hydro = compute_fluxes(state, grid, pvt, rp, _bc(350.0))
        # p_old = p_new -> dp/dt = 0: адиабатика нулевая, остаются
        # конвекция, теплопроводность и JT
        state_prev = SimulationState(p=p.copy(), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, 345.0),
            regime=np.full(N, 2, dtype=int), t=0.0)

        # Перехват сборки на экземпляре (класс не трогается): аргументы,
        # с которыми решатель собрал систему, и коэффициенты.
        calls = []
        orig = solver.assemble_tridiag

        def spy(N_, dt_, T_old_, T_ext_, *coef):
            calls.append((T_old_.copy(), T_ext_, coef))
            return orig(N_, dt_, T_old_, T_ext_, *coef)

        solver.assemble_tridiag = spy
        T_new = solver.solve(hydro, state_prev, DT, _bc(350.0))

        # Сдвиг: решатель подал отклонения от T_ext, граничное значение — 0
        theta_old, theta_ext, coef = calls[0]
        assert theta_ext == 0.0
        np.testing.assert_array_equal(theta_old, state_prev.T - 350.0)

        # Та же система в абсолютной T — независимая сборка
        a, b, c, d_abs = orig(N, DT, state_prev.T, 350.0, *coef)
        T_abs = solver.solve_banded_system(a, b, c, d_abs, N)
        np.testing.assert_allclose(T_new, T_abs, rtol=0.0, atol=1e-9)

        # Отклонения действительно ненулевые: тест не вырожден
        assert np.max(np.abs(T_new - 350.0)) > 1.0


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
    """compute_cell_properties: rho_cp_eff (eq:main_rhocpeff), lambda_eff (eq:lambda_eff)."""

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


class TestComputeConvectiveCoefficients:
    """compute_convective_coefficients: выбор ячейки выше по потоку.

    Прямых тестов у метода не было до DEBT-017 (в отличие от четырёх
    соседних методов) — он покрывался только косвенно, через сборку
    матрицы и эталон DEBT-016. Эти три теста закрывают контурную грань:
    ветвь притока, ветвь оттока и неизменность остальных граней.

    Как обеспечена различимость ветвей. ρ_o = (ρ_o,ст + Rs·ρ_g,ст)/Bo(p, Rs)
    (base.py:70), поэтому различие даёт либо Rs, либо p — но p только при
    включённой сжимаемости недонасыщенной нефти: при co_undersaturated = 0
    (значение по умолчанию в _make_pvt) Bo от p выше p_b не зависит вовсе,
    и ветви по давлению неразличимы. Здесь используются оба пути:
    Rs_ext ≠ Rs[N-1] — физическая ситуация DEBT-009 (разгазирование
    у контура), и p_ext ≠ p[N-1] при co > 0.

    Через c_p или μ_JT проверять нельзя — в _make_pvt они константы
    (CP_OIL, mu_JT_oil_val), ветви по ним неразличимы в принципе.
    """

    def _setup(self, N_cells=3, p_cells=None, Rs_cells=None,
               p_ext=P0, Rs_ext=RS0, co=0.0):
        """Решатель, свойства ячеек и ГУ для проверки грани N.

        co — сжимаемость недонасыщенной нефти: при co > 0 величина Bo,
        а значит и ρ_o, начинает зависеть от давления.
        """
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        pvt = StandingFullPVT(
            rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD, T0=T0, Rs0=RS0,
            co_undersaturated=co, c_p_oil=CP_OIL, c_p_gas=CP_GAS,
            mu_JT_oil_val=4e-7, mu_JT_gas_val=2e-6, L_degas_val=0.0)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = np.full(N_cells, P0) if p_cells is None else p_cells
        Rs = np.full(N_cells, RS0) if Rs_cells is None else Rs_cells
        Sg = np.zeros(N_cells)
        T_old = np.full(N_cells, T0)
        props = solver.compute_cell_properties(p, Sg, Rs, 1.0 - Sg, T_old)
        bc = _bc(T_EXT, Rs_ext=Rs_ext, p_ext=p_ext)
        return solver, props, bc, N_cells

    def test_inflow_uses_boundary_properties(self):
        """Приток (Q_o < 0): ρ и c_p на грани N — из ГУ, не из ячейки N-1.

        Физика: при втекании выше по потоку находится контур
        (eq:bc_props_ext, problem_statement.tex). В ячейке N-1 задано
        разгазирование — Rs снижен до 0.6·Rs^0, как при падении давления
        ниже p_b у контура (ситуация DEBT-009). Тогда ρ_o(Rs^0) ≠
        ρ_o(Rs[N-1]) и ветви различимы. DEBT-017.
        """
        N_cells = 3
        # Приконтурная ячейка обеднена растворённым газом
        Rs_cells = np.full(N_cells, RS0)
        Rs_cells[-1] = 0.6 * RS0
        solver, props, bc, N_cells = self._setup(
            N_cells=N_cells, Rs_cells=Rs_cells, Rs_ext=RS0)
        ext = solver._ext_properties(bc)

        # Приток через все грани: поток направлен к скважине (Q < 0)
        Q_o = np.full(N_cells + 1, -0.01)
        Q_g = np.zeros(N_cells + 1)

        _, _, Phi_o, _ = solver.compute_convective_coefficients(
            Q_o, Q_g, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N_cells, ext)

        expected = ext['rho_o'] * ext['c_p_o'] * Q_o[N_cells]
        buggy = (props['rho_o'][-1] * props['c_p_o'][-1] * Q_o[N_cells])

        # Контроль невырожденности: если ветви дают одно значение,
        # тест ничего не проверяет (приём из DEBT-009)
        assert not np.isclose(expected, buggy), \
            "тест вырожден: ветви дают одно значение, увеличить перепад p"
        np.testing.assert_allclose(Phi_o[N_cells], expected, rtol=1e-13)

    def test_outflow_uses_inner_cell(self):
        """Отток (Q_o > 0): свойства из ячейки N-1, ГУ не участвует.

        Страхует от правдоподобной ошибки реализации — применить ГУ
        в обеих ветвях, «упростив» ветвление. Два вызова с разными
        p_ext обязаны дать один и тот же Φ_o[N].

        Сжимаемость включена (co = 1e-9): иначе ρ_o не зависит от p_ext
        и тест прошёл бы даже на ошибочной реализации.
        """
        N_cells = 3
        Q_o = np.full(N_cells + 1, +0.01)   # отток наружу
        Q_g = np.zeros(N_cells + 1)

        phis = []
        for p_ext in (P0, 0.7 * P0):
            solver, props, bc, _ = self._setup(
                N_cells=N_cells, p_ext=p_ext, co=1e-9)
            ext = solver._ext_properties(bc)
            _, _, Phi_o, _ = solver.compute_convective_coefficients(
                Q_o, Q_g, props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], N_cells, ext)
            phis.append(Phi_o[N_cells])

        # ГУ различаются вдвое по давлению — если бы они участвовали,
        # значения разошлись бы
        assert phis[0] == phis[1], \
            f"при оттоке Φ_o[N] зависит от p_ext: {phis[0]} != {phis[1]}"

    def test_internal_and_well_faces_unchanged_by_bc(self):
        """Внутренние грани и забой не зависят от ГУ контура.

        Правка DEBT-017 касается только грани N. Забой (f=0) — зона
        DEBT-019, он не должен измениться; внутренние грани тем более.
        Два вызова с разными p_ext дают одинаковые Φ[0] и Φ[1:N],
        а Φ[N] обязан различаться — иначе правка не работает.

        Сжимаемость включена (co = 1e-9), чтобы ρ_o зависела от p_ext.
        """
        N_cells = 4
        Q_o = np.full(N_cells + 1, -0.01)
        Q_g = np.full(N_cells + 1, -0.001)

        results = []
        for p_ext in (P0, 0.7 * P0):
            solver, props, bc, _ = self._setup(
                N_cells=N_cells, p_ext=p_ext, co=1e-9)
            ext = solver._ext_properties(bc)
            _, _, Phi_o, Phi_g = solver.compute_convective_coefficients(
                Q_o, Q_g, props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], N_cells, ext)
            results.append((Phi_o.copy(), Phi_g.copy()))

        (Phi_o_a, Phi_g_a), (Phi_o_b, Phi_g_b) = results
        # Забой: f=0
        assert Phi_o_a[0] == Phi_o_b[0], "забой изменился от p_ext"
        assert Phi_g_a[0] == Phi_g_b[0], "забой (газ) изменился от p_ext"
        # Внутренние грани: f = 1..N-1
        np.testing.assert_array_equal(Phi_o_a[1:N_cells], Phi_o_b[1:N_cells])
        np.testing.assert_array_equal(Phi_g_a[1:N_cells], Phi_g_b[1:N_cells])
        # Контроль: грань N при этом ОБЯЗАНА различаться (приток)
        assert Phi_o_a[N_cells] != Phi_o_b[N_cells], \
            "грань N не реагирует на p_ext — правка DEBT-017 не работает"


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
        (eq:bc_Sg_ext, problem_statement.tex). Если в ячейке
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
        # ext — свойства контура (DEBT-017). При Q = 0 ветвь «отток»
        # (Q >= 0) берёт ячейку N-1, и ext на результат не влияет,
        # но параметр обязательный.
        ext = solver._ext_properties(_bc(T_EXT))
        Phi_plus, Phi_minus, _, _ = solver.compute_convective_coefficients(
            Q_o, Q_g, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N_cells, ext)
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
        # ext — свойства контура из того же bc, что у compute_fluxes:
        # согласованность гидро и энергии на контурной грани (DEBT-017)
        ext = solver._ext_properties(bc)
        Phi_plus, Phi_minus, _, _ = solver.compute_convective_coefficients(
            hydro.Q_o, hydro.Q_g, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N_cells, ext)
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


# ═══════════════════════════════════════════════════════════
# Детекторы формы дискретизации (BUG-012)
# ═══════════════════════════════════════════════════════════

class TestAdvectiveFormDetectors:
    """Схема решает то уравнение, которое выведено в постановке.

    ЗАЧЕМ ЭТИ ТЕСТЫ. Три пространственных члена уравнения энергии имеют
    в постановке структуру «скорость · градиент скаляра»:

        конвекция  ρ·c_p·u·∂T/∂r     eq:main_energy_final
        JT         ρ·c_p·μ_JT·u·∂p/∂r  eq:main_QJT_muJT
        дегазация  (u_o/B_o)·∂Rs/∂r    eq:main_mdot

    До BUG-012 все три дискретизировались как РАЗНОСТЬ ПОТОКОВ через
    грани, то есть аппроксимировали div(u·ψ). Разность операторов —
    лишний член ψ_j·D_j, где D_j = Φ_{j+1/2} − Φ_{j−1/2}, и на сетке он
    в нуль не обращается.

    Дефект не ловился НИ ОДНИМ существующим тестом, и это было слепое
    пятно по построению, а не пробел покрытия:
      - баланс энергии суммировал те же дивергентные потоки, что матрица;
      - эталон матрицы (DEBT-016) сверял её с теми же формулами;
      - оба проверяли согласованность кода с кодом, а не схемы с
        уравнением.

    ИДЕЯ ДЕТЕКТОРА. Адвективный оператор на ОДНОРОДНОМ поле переносимой
    величины обязан давать машинный ноль: каждое слагаемое содержит
    разность соседних значений. Дивергентный даёт ψ·D_j ≠ 0. Это прямой
    различитель форм, не требующий эталонного решения.

    ⚠️ СЦЕНАРИИ ОБЯЗАНЫ БЫТЬ ДВУХФАЗНЫМИ. В однофазной зоне Φ почти
    постоянен (замерено: D_j ~ 1e-12 — машинный ноль), и обе формы дают
    один результат. Тест на Sg = 0 проходил бы при любой форме и создавал
    бы ложное чувство покрытия. Существующие TestAssembleTridiag — как раз
    такие: они правку BUG-012 не различают.
    """

    N_CELLS = 12
    SG = 0.3          # двухфазная зона: ρ_g·c_p_g на полтора порядка
                      # меньше ρ_o·c_p_o, поэтому Φ меняется вдоль r

    def _setup(self):
        """Двухфазное состояние с потоком к скважине.

        Sg = 0.3 постоянна, но Φ всё равно меняется по r: вклад газовой
        фазы зависит от k_rg и от расхода, а тот падает как 1/r.
        """
        grid = LogRadialGrid(R_WELL, R_EXT, H, self.N_CELLS, K_PERM)
        pvt = _make_pvt(mu_JT_oil=-3e-7, mu_JT_gas=4e-6, L_degas=1e5)
        solver = TridiagEnergySolver(grid, pvt, _rock())

        p = _log_pressure_profile(grid, P_WF, P0)
        Sg = np.full(self.N_CELLS, self.SG)
        Rs = np.full(self.N_CELLS, RS0)
        T_old = np.full(self.N_CELLS, T0)

        state = SimulationState(
            p=p, Sg=Sg, Rs=Rs, T=T_old,
            regime=np.full(self.N_CELLS, 1, dtype=int), t=0.0)
        bc = BoundaryConditions(well=PressureControl(P_WF), p_ext=P0,
                                T_ext=T_EXT, Rs_ext=RS0)
        hydro = compute_fluxes(state, grid, pvt, CoreyRP(0.2, 0.05, 2.0, 2.0),
                               bc)

        props = solver.compute_cell_properties(p, Sg, Rs, 1.0 - Sg, T_old)
        ext = solver._ext_properties(bc)
        Phi_plus, Phi_minus, Phi_o, Phi_g = \
            solver.compute_convective_coefficients(
                hydro.Q_o, hydro.Q_g, props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], self.N_CELLS, ext)

        return dict(solver=solver, grid=grid, hydro=hydro, bc=bc,
                    props=props, ext=ext, p=p, Sg=Sg, Rs=Rs, T_old=T_old,
                    Phi_plus=Phi_plus, Phi_minus=Phi_minus,
                    Phi_o=Phi_o, Phi_g=Phi_g)

    def test_scenario_is_two_phase(self):
        """Контроль самого теста: D_j существенно отличен от нуля.

        Без этой проверки остальные тесты класса могли бы «проходить»
        на вырожденном сценарии, где обе формы совпадают. Порог выбран
        по замеру: в однофазной зоне D_j ~ 1e-12, в двухфазной ~1e+2.
        """
        s = self._setup()
        Phi = s['Phi_o'] + s['Phi_g']
        D = Phi[1:] - Phi[:-1]
        assert np.max(np.abs(D)) > 1.0, (
            f"сценарий вырожден: max|D_j| = {np.max(np.abs(D)):.3e} Вт/К, "
            "обе формы дадут одно и то же и тест ничего не различит")

    def test_convection_vanishes_on_uniform_temperature(self):
        """Конвективный вклад строки матрицы на однородном T равен нулю.

        Условия: T ≡ T_ext во всех ячейках И на контуре (иначе вклад дала
        бы граничная разность, а не дефект формы). Собирается ТОЛЬКО
        конвективная часть коэффициентов — накопление и кондукция
        исключены, они на однородном поле зануляются сами и замаскировали
        бы результат.

        Ожидание: машинный ноль относительно масштаба задачи.
        На дивергентной схеме тест даёт 4.5e-06 при пороге 1e-9.

        ⚠️ Коэффициенты берутся ИЗ ЯДРА (assemble_tridiag), а не
        собираются здесь по формулам постановки. Собранные в тесте они
        проверяли бы арифметику самого теста — тавтология, из-за которой
        первая редакция этого теста проходила и на дефектном коде.
        Чтобы выделить конвективную часть, матрица собирается дважды: с
        потоками и без них, и вычитается. Всё, что не зависит от Φ
        (накопление, кондукция, источники), сокращается.
        """
        s = self._setup()
        N = self.N_CELLS
        solver = s['solver']

        Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
            s['props']['lambda_eff'], N)
        z = np.zeros(N)
        zf = np.zeros(N + 1)
        args = (N, DT, s['T_old'], T_EXT, s['props']['rho_cp_eff'],
                Q_T_int, Q_T_ext)

        a1, b1, c1, d1 = solver.assemble_tridiag(
            *args, s['Phi_plus'], s['Phi_minus'], z, z, z)
        a0, b0, c0, d0 = solver.assemble_tridiag(
            *args, zf, zf, z, z, z)

        a_conv, b_conv = a1 - a0, b1 - b0
        c_conv, d_conv = c1 - c0, d1 - d0

        # Однородное поле: T в ячейках и T_ext за контуром — одно число
        T_u = np.full(N, T_EXT)

        residual = b_conv * T_u - d_conv
        residual[1:] += a_conv[1:] * T_u[:-1]
        residual[:-1] += c_conv[:-1] * T_u[1:]

        cap = s['grid'].volumes * s['props']['rho_cp_eff'] / DT
        scale = float(np.max(cap * T_EXT))
        rel = float(np.max(np.abs(residual))) / scale

        assert rel < 1e-9, (
            f"конвективный оператор не зануляется на однородном T: "
            f"отн. невязка {rel:.3e}. Это признак дивергентной формы — "
            f"остаток равен T·D_j (BUG-012)")

    def test_jt_vanishes_on_uniform_pressure(self):
        """JT-вклад на однородном p равен нулю.

        Зеркало предыдущего теста для eq:QJT_disc. Давление однородно и
        в ячейках, и за обеими границами (p_wf и p_ext равны тому же
        значению), расходы при этом НЕнулевые — иначе тест тривиален:
        при Q = 0 обращается в нуль и дивергентная форма.
        """
        s = self._setup()
        N = self.N_CELLS
        solver = s['solver']

        p_u = np.full(N, P0)
        # Свойства пересчитываем на однородном p: μ_JT в _make_pvt
        # константа, но Φ зависит от ρ(p), и брать его от другого поля
        # нельзя — коэффициенты должны отвечать одному состоянию.
        props_u = solver.compute_cell_properties(
            p_u, s['Sg'], s['Rs'], 1.0 - s['Sg'], s['T_old'])
        bc_u = BoundaryConditions(well=PressureControl(P0), p_ext=P0,
                                  T_ext=T_EXT, Rs_ext=RS0)
        ext_u = solver._ext_properties(bc_u)

        # Расходы берём от НЕоднородного поля: они должны быть ненулевыми,
        # иначе обе формы дадут ноль и тест ничего не различит.
        Q_o, Q_g = s['hydro'].Q_o, s['hydro'].Q_g
        _, _, Phi_o_u, Phi_g_u = solver.compute_convective_coefficients(
            Q_o, Q_g, props_u['rho_o'], props_u['rho_g'],
            props_u['c_p_o'], props_u['c_p_g'], N, ext_u)

        assert np.max(np.abs(Phi_o_u)) > 0.0, "расходы нулевые — тест вырожден"

        J = solver.compute_jt(
            Q_o, Q_g, Phi_o_u, Phi_g_u,
            props_u['mu_JT_o'], props_u['mu_JT_g'], p_u, N, ext_u, P0)

        scale = float(np.max(np.abs(Phi_o_u + Phi_g_u))) * P0
        rel = float(np.max(np.abs(J))) / scale

        assert rel < 1e-12, (
            f"JT-член не зануляется на однородном p: отн. {rel:.3e}. "
            f"Признак дивергентной формы — остаток равен μ_JT·p·D_j")

    def test_degassing_vanishes_on_uniform_composition(self):
        """Пространственная часть mdot на однородном Rs равна нулю.

        Дискретный аналог утверждения постановки: в однофазной зоне
        (Rs = Rs0 = const) mdot = 0 автоматически. Временная часть здесь
        тоже нулевая (Rs_old = Rs), поэтому проверяется именно
        пространственная.

        Состав однороден и за контуром (Rs_ext = Rs0) — иначе вклад дала
        бы граничная разность.
        """
        s = self._setup()
        N = self.N_CELLS
        solver = s['solver']

        Rs_u = np.full(N, RS0)
        Q_deg = solver.compute_degassing(
            1.0 - s['Sg'], s['Sg'], Rs_u, Rs_u, s['props']['Bo'],
            s['hydro'].G_o, s['props']['L'], DT, N, RS0)

        assert np.max(np.abs(s['hydro'].G_o)) > 0.0, (
            "потоки нулевые — тест вырожден")
        assert np.max(np.abs(Q_deg)) == 0.0, (
            f"член дегазации не зануляется на однородном Rs: "
            f"max|Q_deg| = {np.max(np.abs(Q_deg)):.3e} Вт/м³. "
            f"Признак дивергентной формы — остаток равен Rs·div(G^o)")

    def test_outflow_branch_assembles_correctly(self):
        """Ветвь Φ⁺ > 0 (отток от скважины) собирается по постановке.

        Во ВСЕХ штатных конфигах поток направлен к скважине, и Φ⁺ ≡ 0 на
        всех гранях (замерено: 0 из 51). Слагаемые с Phi_plus в
        assemble_tridiag прогонами примеров не исполняются вовсе, и
        ошибка в них осталась бы незамеченной.

        Здесь знак потока инвертируется искусственно.
        """
        s = self._setup()
        N = self.N_CELLS
        solver = s['solver']

        # Инвертируем знак: Φ⁺ становится ненулевым, Φ⁻ зануляется
        Phi_plus = -s['Phi_minus'][::1].copy()
        Phi_minus = -s['Phi_plus'][::1].copy()
        assert np.max(Phi_plus) > 0.0, "ветвь оттока не активирована"

        Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
            s['props']['lambda_eff'], N)
        z = np.zeros(N)
        a, b, c, d = solver.assemble_tridiag(
            N, DT, s['T_old'], T_EXT, s['props']['rho_cp_eff'],
            Q_T_int, Q_T_ext, Phi_plus, Phi_minus, z, z, z)

        # Проверяем по eq:tridiag_a/b/c: Φ⁺ берётся с ЛЕВОЙ грани j
        for j in range(1, N - 1):
            assert a[j] == pytest.approx(-Q_T_int[j - 1] - Phi_plus[j]), (
                f"a[{j}]: Φ⁺ должен браться с левой грани {j}")
            assert b[j] == pytest.approx(
                s['grid'].volumes[j] * s['props']['rho_cp_eff'][j] / DT
                + Q_T_int[j - 1] + Q_T_int[j]
                + Phi_plus[j] - Phi_minus[j + 1]), (
                f"b[{j}]: в адвективной форме Φ⁺ с грани j, Φ⁻ с грани j+1")

    def test_single_cell_boundary_contribution_counted_once(self):
        """N = 1: вклад контурной грани учитывается ровно один раз.

        Вырожденный случай, в котором обе грани ячейки граничные. Прежний
        код писал в b[0] дважды — в блоке забоя и в блоке контура, — и
        вторая запись затирала первую, теряя вклад. Постановка разбирает
        случай явно (ГУ по температуре, N = 1).
        """
        grid = LogRadialGrid(R_WELL, R_EXT, H, 1, K_PERM)
        pvt = _make_pvt()
        solver = TridiagEnergySolver(grid, pvt, _rock())

        props = solver.compute_cell_properties(
            np.full(1, P0), np.zeros(1), np.full(1, RS0),
            np.ones(1), np.full(1, T0))
        Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
            props['lambda_eff'], 1)

        # Потоки на двух гранях РАЗЛИЧНЫ — иначе дефект не проявится:
        # прежний код брал забойную грань (индекс 0) там, где должна
        # стоять контурная (индекс 1), и при равных значениях подмена
        # давала бы тот же результат.
        Phi_plus = np.zeros(2)
        Phi_minus = np.array([-300.0, -500.0])
        z = np.zeros(1)

        a, b, c, d = solver.assemble_tridiag(
            1, DT, np.full(1, T0), T_EXT, props['rho_cp_eff'],
            Q_T_int, Q_T_ext, Phi_plus, Phi_minus, z, z, z)

        cap = grid.volumes[0] * props['rho_cp_eff'][0] / DT
        # Забойная грань вклада не даёт, контурная даёт РОВНО ОДИН раз
        assert b[0] == pytest.approx(cap + Q_T_ext - Phi_minus[1]), (
            "при N = 1 вклад контурной грани учтён неверно "
            "(дважды или потерян)")
        assert d[0] == pytest.approx(
            cap * T0 + Q_T_ext * T_EXT + (-Phi_minus[1]) * T_EXT), (
            "при N = 1 правая часть собрана неверно")
        assert a[0] == 0.0 and c[0] == 0.0, (
            "при N = 1 связей с соседями нет")


# ═══════════════════════════════════════════════════════════
# Источник p_wf для энергии — только HydroResult (FEAT-020)
# ═══════════════════════════════════════════════════════════

class _NoAccessWell:
    """Управление-ловушка: любое обращение к атрибуту — ошибка теста."""

    def __getattr__(self, name):
        raise AssertionError(f"энергия обратилась к bc.well.{name}")


class TestWellPressureSource:
    """Энергия берёт давление на забойной грани из HydroResult, не из bc.well.

    JT-вклад забойной грани (eq:QJT_disc) для ячейки 0 равен
    μ_JT·Φ⁺_{1/2}·(p[0] − p_wf): схема против потока берёт левую грань с Φ⁺.
    При добыче Φ_{1/2} < 0, Φ⁺ = 0, и p_wf на T не влияет (BUG-015); при
    притоке через забой (Φ⁺ > 0) — влияет. Это единственный режим, где
    источник p_wf наблюдаем.
    """

    @staticmethod
    def _production():
        """Однофазная добыча: лог-профиль p(r), потоки к скважине (Q_o[0] < 0)."""
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt(mu_JT_oil=4e-7)
        p = _log_pressure_profile(grid, P_WF, P0)
        state = SimulationState(p=p, Sg=np.zeros(N), Rs=np.full(N, RS0),
                                T=np.full(N, T0), regime=np.full(N, 2, dtype=int),
                                t=0.0)
        hydro = compute_fluxes(state, grid, pvt, CoreyRP(0.2, 0.05, 2.0, 2.0),
                               _bc(T_EXT))
        solver = TridiagEnergySolver(grid, pvt, _rock())
        # Управление-ловушка: энергия не вправе читать bc.well
        bc_trap = BoundaryConditions(well=_NoAccessWell(), p_ext=P0,
                                     T_ext=T_EXT, Rs_ext=RS0)
        return solver, state, hydro, bc_trap

    def test_energy_does_not_read_well_control(self):
        """Шаг энергии проходит, не обращаясь к bc.well; T конечна.

        Ловит: обход HydroResult — чтение p_wf из граничного условия.
        """
        solver, state, hydro, bc_trap = self._production()
        T_new = solver.solve(hydro, state, DT, bc_trap)
        assert np.all(np.isfinite(T_new))

    def test_inflow_temperature_depends_on_hydro_pwf(self):
        """Приток через забой: T[0] зависит от hydro_result.p_wf.

        HydroResult строится подменой потока на забойной грани: compute_fluxes
        при p_wf > p[0] закрывает скважину (eq:bc_pwf_shutin, DEBT-028), и
        притока через забой гидродинамика не даёт. Энергия приток не
        запрещает, её путь с Φ⁺_{1/2} > 0 проверяем.
        Условия: Q_o[0] = +|Q_o[0]| (~1e-2 м³/с), μ_JT = 4e-7 К/Па,
        p_wf меняется на 1 МПа. Ожидание: |ΔT[0]| > 1e-3 К (замер аудита
        FEAT-020: 0.40 К).
        Ловит: энергия игнорирует hydro_result.p_wf.
        """
        from dataclasses import replace
        solver, state, hydro, bc_trap = self._production()
        Q_o = hydro.Q_o.copy()
        Q_o[0] = abs(Q_o[0])
        h_in = replace(hydro, Q_o=Q_o)
        assert h_in.Q_o[0] > 0.0

        T_a = solver.solve(h_in, state, DT, bc_trap)
        T_b = solver.solve(replace(h_in, p_wf=h_in.p_wf - 1e6), state, DT, bc_trap)
        assert np.all(np.isfinite(T_a)) and np.all(np.isfinite(T_b))
        assert abs(T_a[0] - T_b[0]) > 1e-3

    def test_production_temperature_independent_of_pwf(self):
        """Добыча: T побитово не зависит от p_wf (Φ⁺_{1/2} = 0).

        Фиксирует факт eq:QJT_disc при потоке к скважине (см. BUG-015).
        Ловит: случайное появление забойного вклада при добыче (двойной учёт).
        """
        from dataclasses import replace
        solver, state, hydro, bc_trap = self._production()
        T_a = solver.solve(hydro, state, DT, bc_trap)
        T_b = solver.solve(replace(hydro, p_wf=1e5), state, DT, bc_trap)
        assert np.array_equal(T_a, T_b)
