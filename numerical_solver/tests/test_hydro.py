"""Тесты для ABC HydroSolver и тестового двойника LogProfileHydroStub.

Предмет теста двойной:
  1. Контракт ABC HydroSolver — нельзя инстанцировать, реализация проходит
     isinstance (класс A).
  2. Сам двойник LogProfileHydroStub (tests/_doubles.py) — он используется
     как опора в test_simulator.py, test_output.py и test_val001.py, поэтому
     его собственная корректность должна быть проверена, иначе те тесты
     опираются на непроверенный фундамент.

Двойник выполняет 4 действия, и на каждое есть блок тестов:
  1. Берёт p_wf из bc.well.p_wf (PressureControl)       → класс B
  2. Строит логарифмический профиль p(r)                → класс B
  3. Создаёт новый SimulationState (Sg=0, Rs=Rs_ext,
     T скопирована, t+=dt)                              → класс C
  4. Вызывает compute_fluxes() → HydroResult            → класс D

Классы E и F (сквозной дебит, повторные шаги) проверяют композицию
этих действий.

Свойства потоков (знаки, стационарность, баланс масс) покрыты в
test_fluxes.py и здесь не дублируются — test_all_fields_match_compute_fluxes
доказывает, что двойник делегирует fluxes.py, а не дублирует его логику.

До DEBT-005 двойник жил в gpn_multiphase_solver/hydro/analytical.py под
именем AnalyticalHydroSolver.
"""

import numpy as np
import pytest

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.hydro.base import HydroSolver
from ._doubles import LogProfileHydroStub
from gpn_multiphase_solver.fluxes import compute_fluxes


# ── Параметры ────────────────────────────────────────────────

R_WELL = 0.1
R_EXT = 50.0
H = 10.0
N = 20
K_PERM = 1e-13

P_EXT = 20e6
P_WF = 10e6
T0 = 350.0
RS0 = 50.0

RHO_O_STD = 850.0
RHO_G_STD = 0.85


# ── Fixtures ─────────────────────────────────────────────────

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
def solver(grid, pvt, relperm):
    return LogProfileHydroStub(grid, pvt, relperm)


@pytest.fixture
def initial_state():
    """Начальное состояние: p=p_ext, Sg=0, Rs=Rs0, T=T0."""
    return SimulationState(
        p=np.full(N, P_EXT),
        Sg=np.zeros(N),
        Rs=np.full(N, RS0),
        T=np.full(N, T0),
        regime=np.full(N, 2, dtype=int),
        t=0.0,
    )


@pytest.fixture
def bc():
    return BoundaryConditions(
        well=PressureControl(P_WF), p_ext=P_EXT,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)


@pytest.fixture
def result(solver, initial_state, bc):
    return solver.solve(initial_state, dt=3600.0, bc=bc)


# ═════════════════════════════════════════════════════════════
# A. ABC HydroSolver
# ═════════════════════════════════════════════════════════════

class TestABC:
    def test_cannot_instantiate(self):
        """HydroSolver — абстрактный, нельзя создать экземпляр."""
        with pytest.raises(TypeError):
            HydroSolver()

    def test_stub_is_hydro_solver(self, solver):
        assert isinstance(solver, HydroSolver)


# ═════════════════════════════════════════════════════════════
# B. Действие 1–2: профиль давления p(r)
# ═════════════════════════════════════════════════════════════

class TestPressureProfile:
    def test_pressure_formula_each_cell(self, result, grid):
        """p(r_j) = p_wf + (p_ext - p_wf) · ln(r_j/rw) / ln(R/rw)
        — проверка в каждой ячейке."""
        log_ratio = np.log(grid.r_centers / R_WELL) / np.log(R_EXT / R_WELL)
        p_expected = P_WF + (P_EXT - P_WF) * log_ratio
        np.testing.assert_allclose(result.state.p, p_expected, rtol=1e-14)

    def test_pressure_independent_of_input(self, solver, bc, grid):
        """Аналитический профиль определяется только p_wf и p_ext,
        а не входным state.p — это отличие от Newton-солвера."""
        state_random = SimulationState(
            p=np.random.uniform(5e6, 25e6, N),
            Sg=np.zeros(N), Rs=np.full(N, RS0),
            T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
        result = solver.solve(state_random, dt=100.0, bc=bc)

        log_ratio = np.log(grid.r_centers / R_WELL) / np.log(R_EXT / R_WELL)
        p_expected = P_WF + (P_EXT - P_WF) * log_ratio
        np.testing.assert_allclose(result.state.p, p_expected, rtol=1e-14)


# ═════════════════════════════════════════════════════════════
# C. Действие 3: конструирование нового state
# ═════════════════════════════════════════════════════════════

class TestStateConstruction:
    def test_time_updated(self, result):
        """t = 0 + 3600 = 3600."""
        assert result.state.t == pytest.approx(3600.0)

    def test_Sg_zero(self, result):
        """Однофазный: Sg = 0."""
        np.testing.assert_allclose(result.state.Sg, 0.0, atol=1e-30)

    def test_Rs_equals_Rs_ext(self, result):
        """Rs = Rs_ext = Rs0."""
        np.testing.assert_allclose(result.state.Rs, RS0, rtol=1e-14)

    def test_regime_all_two(self, result):
        """regime = 2 (однофазное)."""
        np.testing.assert_array_equal(result.state.regime, 2)

    def test_T_copied_not_overwritten(self, solver, bc):
        """T из входного state копируется как есть, не перезаписывается на T0.

        Входное T — неоднородный профиль. Проверяем, что _doubles.py
        копирует его, а не подставляет T0.
        """
        # Неоднородный температурный профиль: 345..350 К
        T_input = np.linspace(345.0, 350.0, N)
        state = SimulationState(
            p=np.full(N, P_EXT), Sg=np.zeros(N), Rs=np.full(N, RS0),
            T=T_input.copy(), regime=np.full(N, 2, dtype=int), t=0.0)

        result = solver.solve(state, dt=3600.0, bc=bc)

        # T в результате = T во входном state (поэлементно)
        np.testing.assert_allclose(result.state.T, T_input, rtol=1e-14)

    def test_T_is_independent_copy(self, solver, initial_state, bc):
        """T — независимая копия: мутация входного массива
        не влияет на результат."""
        result = solver.solve(initial_state, dt=3600.0, bc=bc)
        T_before = result.state.T.copy()

        # Мутируем входной state.T
        initial_state.T[0] = 999.0

        # Результат не изменился
        np.testing.assert_allclose(result.state.T, T_before, rtol=1e-14)


# ═════════════════════════════════════════════════════════════
# D. Действие 4: делегирование compute_fluxes
# ═════════════════════════════════════════════════════════════

class TestDelegationToFluxes:
    def test_all_fields_match_compute_fluxes(self, result, grid, pvt,
                                              relperm, bc):
        """Все 11 массивов HydroResult совпадают с compute_fluxes(new_state).

        Это ключевой тест: доказывает, что _doubles.py не дублирует
        логику потоков, а делегирует fluxes.py.
        """
        ref = compute_fluxes(result.state, grid, pvt, relperm, bc)
        for field in ['G_o', 'G_g', 'G_free_gas', 'Q_o', 'Q_g',
                      'u_o', 'u_g', 'm_o', 'm_g', 'Gm_o', 'Gm_g']:
            np.testing.assert_allclose(
                getattr(result, field), getattr(ref, field),
                rtol=1e-14, atol=1e-30,
                err_msg=f"Mismatch in {field}")


# ═════════════════════════════════════════════════════════════
# E. Сквозная проверка: p(r) + fluxes → дебит
# ═════════════════════════════════════════════════════════════

class TestEndToEndRate:
    def test_G_o_analytical_value(self, result, pvt):
        """G_o = 2πhk · mob_o · (p_wf - p_ext) / ln(R/rw).

        Сквозная проверка: формула p(r) → compute_fluxes → G_o.
        Совпадение с аналитикой доказывает корректность всей цепочки.
        """
        p_ref = np.array([15e6])
        Rs_ref = np.array([RS0])
        Bo = pvt.Bo(p_ref, Rs_ref)[0]
        mu_o = pvt.mu_o(p_ref, Rs_ref)[0]
        mob_o = 1.0 / (mu_o * Bo)

        G_o_exact = (2 * np.pi * H * K_PERM * mob_o
                     * (P_WF - P_EXT) / np.log(R_EXT / R_WELL))
        assert result.G_o[0] == pytest.approx(G_o_exact, rel=1e-12)

    def test_G_o_concrete_number(self, result):
        """G_o ≈ -0.009138 м³ст/с — конкретное число для регрессии."""
        assert result.G_o[0] == pytest.approx(-0.009138144903103, rel=1e-10)


# ═════════════════════════════════════════════════════════════
# F. Повторные шаги и смена BC
# ═════════════════════════════════════════════════════════════

class TestMultipleSteps:
    def test_repeated_solve_same_fluxes(self, solver, initial_state, bc):
        """Стационар: solve() на результате предыдущего шага
        даёт те же потоки (p(r) не зависит от входного state)."""
        r1 = solver.solve(initial_state, dt=3600.0, bc=bc)
        r2 = solver.solve(r1.state, dt=3600.0, bc=bc)
        np.testing.assert_allclose(r2.G_o, r1.G_o, rtol=1e-14)
        np.testing.assert_allclose(r2.state.p, r1.state.p, rtol=1e-14)

    def test_time_accumulates(self, solver, initial_state, bc):
        """t: 0 → 3600 → 7200."""
        r1 = solver.solve(initial_state, dt=3600.0, bc=bc)
        r2 = solver.solve(r1.state, dt=3600.0, bc=bc)
        assert r1.state.t == pytest.approx(3600.0)
        assert r2.state.t == pytest.approx(7200.0)

    def test_rate_proportional_to_dp(self, solver, initial_state):
        """Дебит пропорционален перепаду (p_ext - p_wf):
        q ~ Δp при mob_o = const (co=0, Sg=0)."""
        bc_10 = BoundaryConditions(
            well=PressureControl(10e6), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0)
        bc_15 = BoundaryConditions(
            well=PressureControl(15e6), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0)

        r_10 = solver.solve(initial_state, dt=3600.0, bc=bc_10)
        r_15 = solver.solve(initial_state, dt=3600.0, bc=bc_15)

        q_10 = -r_10.G_o[0]  # Δp = 10e6
        q_15 = -r_15.G_o[0]  # Δp = 5e6

        # q_10 / q_15 = 10e6 / 5e6 = 2.0
        assert (q_10 / q_15) == pytest.approx(2.0, rel=1e-10)
