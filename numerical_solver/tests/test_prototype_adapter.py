"""Тесты для PrototypeHydroAdapter (фаза 4a).

Тесты используют реальный прототип (RadialBlackOilModel), не mock.

PrototypeHydroAdapter выполняет 8 шагов:
  1. set_bhp_control(p_wf / BAR_TO_PA)
  2. SimulationState (Па) → BlackOilState (бар)
  3. model.advance(proto_state, dt)
  4. BlackOilState (бар) → SimulationState (Па)
  5. face_component_fluxes_sm3s → dict
  6. Инверсия знака ТОЛЬКО well-потоков
  7. Q, u, m из G через upstream PVT
  8. Gm_o, Gm_g, сборка HydroResult

Эталон для потоков — прямой вызов прототипа (face_component_fluxes_sm3s),
с ручной инверсией знаков. Это тестирует шаги 5–8.
"""

from pathlib import Path
import numpy as np
import pytest

from radial_blackoil.grid import RadialGrid
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.pvt import BlackOilPVT
from radial_blackoil.relperm import TabulatedRelPerm
from radial_blackoil.blackoil import RadialBlackOilModel
from radial_blackoil.state import BlackOilState

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypePVTAdapter
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions
from gpn_multiphase_solver.bc import PressureControl, RateControl, WellControl
from gpn_multiphase_solver.hydro.base import HydroSolver
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.units import BAR_TO_PA, M2_TO_MD


# ── Параметры ────────────────────────────────────────────────

R_WELL = 0.1
R_EXT = 50.0
H = 10.0
N = 20
K_PERM = 1e-13
K_MD = K_PERM * M2_TO_MD
PHI = 0.2

P0_PA = 200e5       # 200 бар
P_WF_PA = 150e5     # 150 бар
P0_BAR = P0_PA / BAR_TO_PA
P_WF_BAR = P_WF_PA / BAR_TO_PA

T0 = 350.0
RS0 = 30.0
RHO_O_STD = 850.0
RHO_G_STD = 0.85
DT = 3600.0

# Минимальные PVT-таблицы
OIL_ROWS = [
    (0.0,   50.0,  1.05, 3.0),
    (0.0,  300.0,  1.04, 3.2),
    (30.0, 150.0,  1.20, 1.5),
    (30.0, 300.0,  1.18, 1.6),
]
GAS_ROWS = [
    (50.0,  0.020, 0.012),
    (150.0, 0.008, 0.014),
    (300.0, 0.004, 0.018),
]
SG_TAB = [0.0, 0.1, 0.2, 0.4, 0.6, 0.8]
KRO_TAB = [1.0, 0.8, 0.6, 0.3, 0.1, 0.0]
KRG_TAB = [0.0, 0.01, 0.05, 0.2, 0.5, 0.8]


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def proto_pvt():
    return BlackOilPVT(OIL_ROWS, GAS_ROWS)

@pytest.fixture
def proto_rp():
    return TabulatedRelPerm(SG_TAB, KRO_TAB, KRG_TAB)

@pytest.fixture
def proto_grid():
    return RadialGrid(R_WELL, R_EXT, H, N, K_MD)

@pytest.fixture
def proto_rock():
    return CompressibleRock(phi_ref=PHI, p_ref_bar=P0_BAR, cr_per_bar=0.0)

@pytest.fixture
def model(proto_grid, proto_rock, proto_pvt, proto_rp):
    return RadialBlackOilModel(
        grid=proto_grid, rock=proto_rock, pvt=proto_pvt, relperm=proto_rp,
        p_bhp_bar=P_WF_BAR, p_outer_bar=P0_BAR,
        outer_rs_sm3_sm3=RS0, skin=0.0)

@pytest.fixture
def our_grid():
    return LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=N, k=K_PERM)

@pytest.fixture
def our_pvt(proto_pvt):
    """Наш HydroPVT — обёртка над тем же BlackOilPVT прототипа."""
    return PrototypePVTAdapter(proto_pvt, rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD)

@pytest.fixture
def adapter(model, our_grid, our_pvt):
    return PrototypeHydroAdapter(model, our_grid, our_pvt)

@pytest.fixture
def initial_state():
    return SimulationState(
        p=np.full(N, P0_PA), Sg=np.zeros(N), Rs=np.full(N, RS0),
        T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)

@pytest.fixture
def bc():
    return BoundaryConditions(
        well=PressureControl(P_WF_PA), p_ext=P0_PA,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)

@pytest.fixture
def result(adapter, initial_state, bc):
    return adapter.solve(initial_state, dt=DT, bc=bc)


# ═══════════════════════════════════════════════════════════
# A. Шаг 1: set_bhp_control
# ═══════════════════════════════════════════════════════════

class TestSetControl:
    def test_model_bhp_updated(self, model, adapter, initial_state, bc):
        """После solve() модель хранит p_bhp_bar = p_wf / BAR_TO_PA."""
        adapter.solve(initial_state, dt=DT, bc=bc)
        assert model.p_bhp_bar == pytest.approx(P_WF_PA / BAR_TO_PA, rel=1e-14)

    def test_unsupported_control_raises(self, adapter, initial_state):
        """Неизвестное адаптеру управление → NotImplementedError."""
        class FakeControl(WellControl):
            pass
        bc_fake = BoundaryConditions(
            well=FakeControl(), p_ext=P0_PA, T_ext=T0, Rs_ext=RS0)
        with pytest.raises(NotImplementedError):
            adapter.solve(initial_state, dt=DT, bc=bc_fake)


class TestAdapterWellPressure:
    """HydroResult.p_wf — фактическое давление на забойной грани после шага.

    Энергия и вывод берут p_wf только отсюда (FEAT-020): при управлении по
    дебиту оно известно лишь после шага, при закрытой скважине равно p[0].
    """

    def test_pwf_equals_setpoint_when_producing(self, result):
        """Добыча при заданном давлении: p_wf = уставка.

        Условия: p0 = 200 бар, уставка 150 бар — поток к скважине (G_o[0] < 0).
        Ожидание: p_wf = 150 бар с точностью до округления Па → бар → Па.
        Ловит: поле не заполнено или взято не из прототипа.
        """
        assert result.G_o[0] < 0.0
        assert result.p_wf == pytest.approx(P_WF_PA, rel=1e-14)

    def test_pwf_floats_to_p0_when_shut(self, adapter, initial_state):
        """Уставка выше давления у забоя: скважина закрыта, p_wf = p[0].

        Условия: p0 = 200 бар, уставка 250 бар. Прототип закрывает скважину
        вместо нагнетания (blackoil.py, ветка BHP): q = 0, bhp = p[0].
        Ожидание: G_o[0] = 0 (прототип отдаёт -0.0, в Python == 0.0 истинно)
        и p_wf = p[0] нового слоя (замер аудита FEAT-020: побитово).
        Ловит: запись уставки вместо фактического давления.
        """
        bc_shut = BoundaryConditions(
            well=PressureControl(250e5), p_ext=P0_PA, T_ext=T0, Rs_ext=RS0)
        r = adapter.solve(initial_state, dt=DT, bc=bc_shut)
        assert r.G_o[0] == 0.0
        assert r.p_wf == pytest.approx(r.state.p[0], rel=1e-14)


def _bc_rate(q_oil_sm3_day, min_bhp_pa):
    """Граничные условия с управлением по дебиту нефти (дебит в м³ст/сут → СИ)."""
    return BoundaryConditions(
        well=RateControl(q_oil_sm3_day / 86400.0, min_bhp_pa),
        p_ext=P0_PA, T_ext=T0, Rs_ext=RS0)


class TestAdapterRateControl:
    """Ветка RateControl адаптера: СИ → set_oil_rate_control(м³ст/сут, бар).

    Прототип выражает p_bhp из уравнения притока нефти внутри Ньютона
    (eq:bc_rate_pwf) с нижней границей min_bhp. Фикстуры model и adapter
    функциональные: внутри теста это одна модель, model.well_rates смотрит
    на то же управление, что выставил адаптер. p0 = 200 бар, N = 20, R = 50 м.
    """

    def test_rate_honoured(self, model, adapter, initial_state):
        """Дебит 2 м³ст/сут, граница 100 бар: дебит выдержан, p_wf из прототипа.

        Ожидание: −G_o[0] = q_oil (замер аудита: точно), 100 бар < p_wf < p[0];
        p_wf совпадает с bhp прототипа на том же состоянии. Сценарий
        test_rate_control_one_implicit_step прототипа, но через адаптер и в СИ.
        Ловит: ошибку единиц м³ст/с ↔ м³ст/сут, p_wf не из прототипа.
        """
        r = adapter.solve(initial_state, dt=DT, bc=_bc_rate(2.0, 100e5))
        assert -r.G_o[0] == pytest.approx(2.0 / 86400.0, rel=1e-12)
        assert 100e5 < r.p_wf < r.state.p[0]
        proto = BlackOilState(r.state.p / BAR_TO_PA, r.state.Rs, r.state.Sg,
                              r.state.regime == 1)
        assert r.p_wf == pytest.approx(
            model.well_rates(proto)['bhp_bar'] * BAR_TO_PA, rel=1e-12)

    def test_unreachable_rate_clamped_to_min_bhp(self, adapter, initial_state):
        """Дебит 1000 м³ст/сут недостижим: p_wf = min_bhp, дебит срезан.

        Замер аудита: за час дебит 477 м³ст/сут при p_bhp = 100 бар.
        Аналог test_rate_floor_switches_to_bhp прототипа.
        Ловит: расхождение решателя вместо перехода на ограничение.
        """
        r = adapter.solve(initial_state, dt=DT, bc=_bc_rate(1000.0, 100e5))
        assert r.p_wf == pytest.approx(100e5, rel=1e-12)
        assert 0.0 < -r.G_o[0] < 1000.0 / 86400.0

    def test_well_shut_when_p0_below_min_bhp(self, adapter, initial_state):
        """Граница 250 бар выше p0 = 200 бар: скважина закрыта, реверса нет.

        Ожидание: G_o[0] = 0 и p_wf = p[0] (замер аудита: bhp = p0 = 200 бар).
        Ловит: нагнетание вместо закрытия.
        """
        r = adapter.solve(initial_state, dt=DT, bc=_bc_rate(2.0, 250e5))
        assert r.G_o[0] == 0.0
        assert r.p_wf == pytest.approx(r.state.p[0], rel=1e-14)

    def test_zero_rate(self, adapter, initial_state):
        """Нулевой дебит: потока через забой нет."""
        r = adapter.solve(initial_state, dt=DT, bc=_bc_rate(0.0, 100e5))
        assert r.G_o[0] == 0.0

    def test_control_switch_between_calls(self, adapter, initial_state, bc):
        """Шаг по дебиту, затем по давлению: режим модели не залипает.

        set_bhp_control сбрасывает режим, min_bhp и последнее p_bhp прототипа.
        Ожидание: второй шаг — p_wf = уставка 150 бар.
        """
        r1 = adapter.solve(initial_state, dt=DT, bc=_bc_rate(2.0, 100e5))
        r2 = adapter.solve(r1.state, dt=DT, bc=bc)
        assert r2.p_wf == pytest.approx(P_WF_PA, rel=1e-14)


# ═══════════════════════════════════════════════════════════
# B. Шаги 2+4: конвертация State ↔ proto
# ═══════════════════════════════════════════════════════════

class TestStateConversion:
    def test_pressure_in_pascal(self, result):
        """p в результате — Па (порядок 1e7, не 1e2)."""
        assert np.all(result.state.p > 1e6)

    def test_pressure_between_pwf_and_pext(self, result):
        """p_wf ≤ p ≤ p_ext (с малым допуском на нестационарность)."""
        assert np.all(result.state.p >= P_WF_PA - 1e3)
        assert np.all(result.state.p <= P0_PA + 1e3)

    def test_time_updated(self, result):
        assert result.state.t == pytest.approx(DT)

    def test_Sg_non_negative(self, result):
        assert np.all(result.state.Sg >= 0)

    def test_regime_valid_values(self, result):
        """regime ∈ {1, 2}."""
        assert set(np.unique(result.state.regime)).issubset({1, 2})

    def test_T_unchanged(self, result, initial_state):
        """Splitting: гидро не трогает T."""
        np.testing.assert_allclose(result.state.T, initial_state.T, rtol=1e-14)

    def test_T_is_independent_copy(self, result, initial_state):
        """Мутация входного T не портит результат."""
        T_before = result.state.T.copy()
        initial_state.T[0] = 999.0
        np.testing.assert_allclose(result.state.T, T_before, rtol=1e-14)

    def test_nonuniform_T_preserved(self, adapter, bc):
        """Неоднородный T копируется поэлементно, не заменяется на T0."""
        T_input = np.linspace(340.0, 360.0, N)
        state = SimulationState(
            p=np.full(N, P0_PA), Sg=np.zeros(N), Rs=np.full(N, RS0),
            T=T_input.copy(), regime=np.full(N, 2, dtype=int), t=0.0)
        result = adapter.solve(state, dt=DT, bc=bc)
        np.testing.assert_allclose(result.state.T, T_input, rtol=1e-14)


# ═══════════════════════════════════════════════════════════
# C. Шаги 5–6: потоки — независимые эталоны
# ═══════════════════════════════════════════════════════════

class TestFluxesAgainstPrototype:
    """Сравнение потоков Adapter с НЕЗАВИСИМЫМИ методами прототипа.

    well_rates() — независимый метод прототипа, не используемый в Adapter.
    step_global_balance() — внутренняя проверка баланса масс прототипа.
    Эти методы используют свою логику вычисления потоков и баланса,
    не зависящую от кода Adapter.
    """

    def test_well_oil_rate_matches(self, model, adapter, initial_state, bc):
        """Дебит нефти: наш -G_o[0] = well_rates()['oil_sm3_s'].

        well_rates() вызывает face_component_fluxes_sm3s внутри,
        но возвращает результат в конвенции прототипа (outflow+).
        Наш G_o[0] = -fluxes['oil_well']. Значит -G_o[0] = oil_sm3_s.
        Эта проверка верифицирует правильность инверсии знака на забое.
        """
        result = adapter.solve(initial_state, dt=DT, bc=bc)

        # Восстановить proto_state для вызова well_rates
        proto_state = BlackOilState(
            pressure_bar=result.state.p / BAR_TO_PA,
            rs_sm3_sm3=result.state.Rs.copy(),
            sg=result.state.Sg.copy(),
            gas_active=(result.state.regime == 1))
        rates = model.well_rates(proto_state)

        # -G_o[0] = oil_sm3_s (дебит прототипа, outflow+)
        assert -result.G_o[0] == pytest.approx(rates['oil_sm3_s'], rel=1e-12)

    def test_well_gas_rate_matches(self, model, adapter, initial_state, bc):
        """Дебит газа: наш -G_g[0] = well_rates()['total_gas_sm3_s']."""
        result = adapter.solve(initial_state, dt=DT, bc=bc)

        proto_state = BlackOilState(
            pressure_bar=result.state.p / BAR_TO_PA,
            rs_sm3_sm3=result.state.Rs.copy(),
            sg=result.state.Sg.copy(),
            gas_active=(result.state.regime == 1))
        rates = model.well_rates(proto_state)

        assert -result.G_g[0] == pytest.approx(rates['total_gas_sm3_s'], rel=1e-12)

    def test_well_free_gas_rate_matches(self, model, adapter,
                                         initial_state, bc):
        """Дебит свободного газа: -G_free_gas[0] = well_rates()['free_gas_sm3_s']."""
        result = adapter.solve(initial_state, dt=DT, bc=bc)

        proto_state = BlackOilState(
            pressure_bar=result.state.p / BAR_TO_PA,
            rs_sm3_sm3=result.state.Rs.copy(),
            sg=result.state.Sg.copy(),
            gas_active=(result.state.regime == 1))
        rates = model.well_rates(proto_state)

        assert -result.G_free_gas[0] == pytest.approx(
            rates['free_gas_sm3_s'], rel=1e-12, abs=1e-30)

    def test_bhp_matches(self, model, adapter, initial_state, bc):
        """Забойное давление: well_rates()['bhp_bar'] * BAR_TO_PA ≈ p_wf."""
        result = adapter.solve(initial_state, dt=DT, bc=bc)

        proto_state = BlackOilState(
            pressure_bar=result.state.p / BAR_TO_PA,
            rs_sm3_sm3=result.state.Rs.copy(),
            sg=result.state.Sg.copy(),
            gas_active=(result.state.regime == 1))
        rates = model.well_rates(proto_state)

        # В режиме BHP bhp_bar = p_wf_bar
        assert rates['bhp_bar'] * BAR_TO_PA == pytest.approx(P_WF_PA, rel=1e-10)

    def test_prototype_global_balance(self, model, adapter,
                                       initial_state, bc):
        """Внутренний баланс масс прототипа ≈ 0.

        step_global_balance() — независимый метод, вычисляет невязку
        через inventories и потоки прототипа. Если Adapter правильно
        передал state в advance(), невязка ≈ 0.
        """
        proto_old = BlackOilState(
            pressure_bar=initial_state.p / BAR_TO_PA,
            rs_sm3_sm3=initial_state.Rs.copy(),
            sg=initial_state.Sg.copy(),
            gas_active=(initial_state.regime == 1))

        result = adapter.solve(initial_state, dt=DT, bc=bc)

        proto_new = BlackOilState(
            pressure_bar=result.state.p / BAR_TO_PA,
            rs_sm3_sm3=result.state.Rs.copy(),
            sg=result.state.Sg.copy(),
            gas_active=(result.state.regime == 1))

        oil_bal, gas_bal = model.step_global_balance(proto_old, proto_new, DT)

        # Невязки нормированы на дебит · dt
        rates = model.well_rates(proto_new)
        q_o = abs(rates['oil_sm3_s'])
        q_g = abs(rates['total_gas_sm3_s'])
        if q_o > 1e-15:
            assert abs(oil_bal) / (q_o * DT) < 1e-8, \
                f"Oil balance: {oil_bal:.2e}, q_o·dt={q_o*DT:.2e}"
        if q_g > 1e-15:
            assert abs(gas_bal) / (q_g * DT) < 1e-8, \
                f"Gas balance: {gas_bal:.2e}, q_g·dt={q_g*DT:.2e}"

    def test_all_G_o_negative(self, result):
        """При p_ext > p_wf: все G_o < 0 (поток к скважине)."""
        assert np.all(result.G_o < 0)


# ═══════════════════════════════════════════════════════════
# D. Шаг 7: Q, u, m — формулы через upstream PVT
# ═══════════════════════════════════════════════════════════

class TestDerivedFluxes:
    """Q_o = G_o · Bo_up, Q_g = G_free_gas · Bg_up.
    u = Q / (2πhr). m = ρ_up · Q.

    Воспроизводим upstream-логику и PVT-вычисления вручную.
    """

    def test_Q_o_from_G_o_Bo(self, result, our_pvt):
        """Q_o[f] = G_o[f] · Bo[up] на каждой внутренней грани."""
        p = result.state.p
        Rs = result.state.Rs
        Bo = our_pvt.Bo(p, Rs)

        for f in range(1, N):
            # Upstream по знаку G_o
            up = f if result.G_o[f] < 0 else f - 1
            Q_o_expected = result.G_o[f] * Bo[up]
            assert result.Q_o[f] == pytest.approx(Q_o_expected, rel=1e-12), \
                f"Q_o mismatch at face {f}"

    def test_Q_g_from_G_free_gas_Bg(self, result, our_pvt):
        """Q_g[f] = G_free_gas[f] · Bg[up] на каждой внутренней грани."""
        p = result.state.p
        Bg = our_pvt.Bg(p)

        for f in range(1, N):
            up = f if result.G_o[f] < 0 else f - 1
            Q_g_expected = result.G_free_gas[f] * Bg[up]
            assert result.Q_g[f] == pytest.approx(
                Q_g_expected, rel=1e-12, abs=1e-30), \
                f"Q_g mismatch at face {f}"

    def test_Q_o_well(self, result, our_pvt):
        """Q_o[0] = G_o[0] · Bo[0] (upstream = ячейка 0 на забое)."""
        Bo_0 = our_pvt.Bo(
            np.array([result.state.p[0]]),
            np.array([result.state.Rs[0]]))[0]
        assert result.Q_o[0] == pytest.approx(result.G_o[0] * Bo_0, rel=1e-12)

    def test_Q_o_ext(self, result, our_pvt, bc):
        """Q_o[N]: upstream = контур при G_o[N] < 0 (типичный приток)."""
        if result.G_o[N] < 0:
            # upstream = контур
            Bo_ext = our_pvt.Bo(
                np.array([bc.p_ext]), np.array([bc.Rs_ext]))[0]
            assert result.Q_o[N] == pytest.approx(
                result.G_o[N] * Bo_ext, rel=1e-12)

    def test_m_o_from_rho_Q(self, result, our_pvt):
        """m_o[f] = ρ_o[up] · Q_o[f] на каждой внутренней грани."""
        p = result.state.p
        Rs = result.state.Rs
        rho_o = our_pvt.rho_o(p, Rs)

        for f in range(1, N):
            up = f if result.G_o[f] < 0 else f - 1
            m_o_expected = rho_o[up] * result.Q_o[f]
            assert result.m_o[f] == pytest.approx(m_o_expected, rel=1e-12), \
                f"m_o mismatch at face {f}"

    def test_u_o_from_Q_o(self, result, our_grid):
        """u_o = Q_o / (2πhr) на каждой грани."""
        area = 2.0 * np.pi * our_grid.h * our_grid.r_faces
        np.testing.assert_allclose(result.u_o, result.Q_o / area, rtol=1e-12)

    def test_u_g_from_Q_g(self, result, our_grid):
        area = 2.0 * np.pi * our_grid.h * our_grid.r_faces
        np.testing.assert_allclose(result.u_g, result.Q_g / area, rtol=1e-12)


# ═══════════════════════════════════════════════════════════
# E. Шаг 8: покомпонентные массовые расходы
# ═══════════════════════════════════════════════════════════

class TestComponentMassFluxes:
    def test_Gm_o(self, result, our_pvt):
        np.testing.assert_allclose(result.Gm_o,
                                   our_pvt.rho_o_std * result.G_o, rtol=1e-14)

    def test_Gm_g(self, result, our_pvt):
        np.testing.assert_allclose(result.Gm_g,
                                   our_pvt.rho_g_std * result.G_g, rtol=1e-14)


# ═══════════════════════════════════════════════════════════
# F. G_g decomposition
# ═══════════════════════════════════════════════════════════

class TestGgDecomposition:
    """G_g = Rs_up · G_o + G_free_gas на каждой внутренней грани."""

    def test_decomposition_internal(self, result):
        Rs = result.state.Rs
        for f in range(1, N):
            up = f if result.G_o[f] < 0 else f - 1
            expected = Rs[up] * result.G_o[f] + result.G_free_gas[f]
            assert result.G_g[f] == pytest.approx(expected, rel=1e-10), \
                f"G_g decomposition mismatch at face {f}"


# ═══════════════════════════════════════════════════════════
# G. Баланс масс
# ═══════════════════════════════════════════════════════════

class TestMassBalance:
    """F_oil[j] = V·φ·Δ(So/Bo)/dt + G_o[j+1] - G_o[j] ≈ 0.

    Допуск ~2% из-за разных центров ячеек:
    наш Grid — центр масс кольца (eq. 12), прототип — √(r_i·r_{i+1}).
    Проводимости расходятся → потоки немного разные.
    """

    def test_oil_balance(self, result, initial_state, our_grid, our_pvt):
        p_new, Rs_new, Sg_new = result.state.p, result.state.Rs, result.state.Sg
        p_old, Rs_old, Sg_old = initial_state.p, initial_state.Rs, initial_state.Sg

        Bo_new = our_pvt.Bo(p_new, Rs_new)
        Bo_old = our_pvt.Bo(p_old, Rs_old)

        accum = our_grid.volumes * PHI * (
            (1 - Sg_new) / Bo_new - (1 - Sg_old) / Bo_old) / DT
        net_flux = result.G_o[1:] - result.G_o[:-1]
        residual = accum + net_flux

        scale = np.abs(result.G_o[0])
        np.testing.assert_allclose(residual / scale, 0.0, atol=0.02,
                                   err_msg="Баланс нефтяного компонента нарушен")


# ═══════════════════════════════════════════════════════════
# H. PVT согласованность: наш pvt = обёртка model.pvt
# ═══════════════════════════════════════════════════════════

class TestPVTConsistency:
    """self._pvt (PrototypePVTAdapter) обёртывает тот же BlackOilPVT,
    что и model.pvt. Результаты Bo, Bg должны совпадать."""

    def test_Bo_matches(self, our_pvt, proto_pvt):
        p_pa = np.array([100e5, 150e5, 200e5])
        Rs = np.array([20.0, 25.0, 30.0])
        # Наш pvt: Па → внутри конвертирует в бар
        Bo_ours = our_pvt.Bo(p_pa, Rs)
        # Прототип напрямую: бар
        Bo_proto = proto_pvt.bo(p_pa / BAR_TO_PA, Rs)
        np.testing.assert_allclose(Bo_ours, Bo_proto, rtol=1e-14)

    def test_Bg_matches(self, our_pvt, proto_pvt):
        p_pa = np.array([100e5, 150e5, 200e5])
        Bg_ours = our_pvt.Bg(p_pa)
        Bg_proto = proto_pvt.bg(p_pa / BAR_TO_PA)
        np.testing.assert_allclose(Bg_ours, Bg_proto, rtol=1e-14)

    def test_mu_o_matches(self, our_pvt, proto_pvt):
        p_pa = np.array([100e5, 150e5, 200e5])
        Rs = np.array([20.0, 25.0, 30.0])
        # Наш: Па·с, прототип: сП → конвертируем
        mu_ours = our_pvt.mu_o(p_pa, Rs)
        mu_proto = proto_pvt.mu_o(p_pa / BAR_TO_PA, Rs) * 1e-3  # сП → Па·с
        np.testing.assert_allclose(mu_ours, mu_proto, rtol=1e-14)


# ═══════════════════════════════════════════════════════════
# I. Несколько шагов → сходимость
# ═══════════════════════════════════════════════════════════

class TestMultipleSteps:
    def test_convergence_to_stationary(self, adapter, initial_state, bc):
        """После 10 шагов Δp/p₀ < 1%."""
        state = initial_state
        for _ in range(10):
            result = adapter.solve(state, dt=DT, bc=bc)
            state = result.state
        result2 = adapter.solve(state, dt=DT, bc=bc)
        dp_rel = np.max(np.abs(result2.state.p - state.p)) / P0_PA
        assert dp_rel < 0.01

    def test_time_accumulates(self, adapter, initial_state, bc):
        state = initial_state
        for i in range(5):
            result = adapter.solve(state, dt=DT, bc=bc)
            state = result.state
        assert state.t == pytest.approx(5 * DT)


# ═══════════════════════════════════════════════════════════
# J. Смена BC: дебит меняется
# ═══════════════════════════════════════════════════════════

class TestBCChange:
    def test_lower_pwf_higher_rate(self, adapter, initial_state):
        bc_high = BoundaryConditions(
            well=PressureControl(180e5), p_ext=P0_PA,
            T_ext=T0, Rs_ext=RS0)
        bc_low = BoundaryConditions(
            well=PressureControl(100e5), p_ext=P0_PA,
            T_ext=T0, Rs_ext=RS0)
        r_high = adapter.solve(initial_state, dt=DT, bc=bc_high)
        r_low = adapter.solve(initial_state, dt=DT, bc=bc_low)
        # Больший перепад → больший дебит (по модулю)
        assert -r_low.G_o[0] > -r_high.G_o[0]


# ═══════════════════════════════════════════════════════════
# K. Тесты на падение
# ═══════════════════════════════════════════════════════════

class TestErrorHandling:
    def test_isinstance(self, adapter):
        assert isinstance(adapter, HydroSolver)

    def test_all_result_shapes(self, result):
        """Все 11 массивов имеют размер [N+1]."""
        for field in ['G_o', 'G_g', 'G_free_gas', 'Q_o', 'Q_g',
                      'u_o', 'u_g', 'm_o', 'm_g', 'Gm_o', 'Gm_g']:
            assert getattr(result, field).shape == (N + 1,), \
                f"{field} shape mismatch"


# ═══════════════════════════════════════════════════════════
# L. BUG-014: скачок p_wf вверх выше p[0]
# ═══════════════════════════════════════════════════════════

def _bc(p_wf):
    """ГУ как фикстура bc, но с заданным p_wf, Па."""
    return BoundaryConditions(
        well=PressureControl(p_wf), p_ext=P0_PA,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)


class TestAdapterPwfUpStep:
    """После отбора p_wf поднимают выше p[0]; адаптер не должен дробить шаг.

    Подготовка: 6 ч отбора при p_wf = 80 бар → p[0] = 84.12 бар, у забоя
    11 двухфазных ячеек. До правки прототипа (BUG-014) шаг 1 ч не сходился
    при любом дроблении (RuntimeError), шаг 60 с дробился на 64 подшага.
    """

    @pytest.fixture
    def drawn_down(self, adapter, initial_state):
        state = initial_state
        for _ in range(6):
            state = adapter.solve(state, dt=3600.0, bc=_bc(80e5)).state
        return state

    def test_long_upstep_single_substep(self, adapter, drawn_down):
        # p_wf 80 → 114 бар при p[0] = 84.1 бар, шаг 1 ч. За час давление у забоя
        # восстанавливается выше 114 бар — согласованный ответ: скважина снова
        # добывает. Прототип решает шаг запасным путём без дробления.
        r = adapter.solve(drawn_down, dt=3600.0, bc=_bc(114e5))
        assert r.n_substeps == 1
        # Добыча: поток к скважине, по конвенции знаков G < 0. Замер −4.47e-3.
        assert r.G_o[0] < 0.0
        assert r.state.p[0] >= 114e5            # замер 116.57 бар
        # Запасной путь прототипа пропускает S_g < 0 только на итерациях Ньютона;
        # в принятом состоянии 0 <= S_g < 1.
        assert r.state.Sg.min() >= 0.0
        assert r.state.Sg.max() < 1.0

    def test_short_upstep_well_shut(self, adapter, drawn_down):
        # p_wf 80 → 190 бар, шаг 60 с: за минуту p[0] до 190 бар не дорастает —
        # скважина закрыта, потоки через забой нулевые (закачки нет).
        # −0.0 (инверсия знака well-потоков в адаптере) проходит сравнение с 0.0.
        r = adapter.solve(drawn_down, dt=60.0, bc=_bc(190e5))
        assert r.n_substeps == 1
        assert r.G_o[0] == 0.0
        assert r.G_g[0] == 0.0
        assert r.G_free_gas[0] == 0.0
        assert r.state.p[0] < 190e5             # замер 157.09 бар
        assert r.state.Sg.min() >= 0.0          # см. test_long_upstep_single_substep
        assert r.state.Sg.max() < 1.0
