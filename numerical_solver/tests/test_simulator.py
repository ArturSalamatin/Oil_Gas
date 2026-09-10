"""Тесты для Simulator + Factory + TimeSchedule (фаза 6).

Интеграционные тесты: полный цикл hydro → energy → state update.
Используют LogProfileHydroStub + TridiagEnergySolver (реальный энергетический
солвер, гидродинамика — тестовый двойник с детерминированным p(r)).

A. TimeSchedule: substeps, total_time
B. Simulator.run(): цикл по времени, сохранение, смена BC
C. Factory: from_config(baseline.json) → run()
D. Физика: T сходится к T_ext, JT-охлаждение, стационарность p(r)
E. Состав истории: записи на концах интервалов time.history (DEBT-013)
"""

from pathlib import Path
import numpy as np
import pytest

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions
from gpn_multiphase_solver.bc import PressureControl
from ._doubles import LogProfileHydroStub
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.io.config import load_config, RockConfig
from gpn_multiphase_solver.simulator import (
    Simulator, TimeSchedule, ScheduleInterval,
)
from gpn_multiphase_solver.factory import SimulatorFactory


# ── Параметры ────────────────────────────────────────────────

N = 10
R_WELL = 0.1
R_EXT = 50.0
H = 10.0
K_PERM = 1e-13
PHI = 0.2

P0 = 20e6
P_WF = 10e6
T0 = 350.0
RS0 = 50.0
DT_INT = 3600.0

BASELINE = Path(__file__).parent.parent / "configs" / "baseline.json"


# ── Helpers ──────────────────────────────────────────────────

def _make_simulator(n_cells=N, mu_JT_oil=0.0):
    """Создать Simulator с LogProfileHydroStub (без Factory)."""
    grid = LogRadialGrid(R_WELL, R_EXT, H, n_cells, K_PERM)
    pvt = StandingFullPVT(
        rho_o_std=850.0, rho_g_std=0.85, T0=T0, Rs0=RS0,
        co_undersaturated=0.0, c_p_oil=2000.0, c_p_gas=1000.0,
        mu_JT_oil_val=mu_JT_oil, mu_JT_gas_val=0.0, L_degas_val=0.0)
    rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
    hydro = LogProfileHydroStub(grid, pvt, rp)
    rock = RockConfig(porosity=PHI, permeability=K_PERM)
    energy = TridiagEnergySolver(grid, pvt, rock)
    # Пятый элемент — рудимент от save_every (удалён в DEBT-013). Оставлен
    # None, чтобы не править распаковку в двух десятках тестов; все они
    # принимают его как `_`.
    return grid, pvt, hydro, energy, None


def _initial_state(n_cells=N):
    return SimulationState(
        p=np.full(n_cells, P0), Sg=np.zeros(n_cells),
        Rs=np.full(n_cells, RS0), T=np.full(n_cells, T0),
        regime=np.full(n_cells, 2, dtype=int), t=0.0)


def _single_interval_schedule(dt_hist=86400.0, dt_int=DT_INT, p_wf=P_WF):
    """TimeSchedule с одним интервалом."""
    bc = BoundaryConditions(
        well=PressureControl(p_wf), p_ext=P0,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)
    return TimeSchedule(dt_int, [ScheduleInterval(dt=dt_hist, bc=bc)])


# ═══════════════════════════════════════════════════════════
# A. TimeSchedule
# ═══════════════════════════════════════════════════════════

class TestTimeSchedule:
    def test_substeps_exact_division(self):
        """86400 / 3600 = 24 подшагов, dt_actual = 3600."""
        schedule = _single_interval_schedule(dt_hist=86400.0, dt_int=3600.0)
        n_sub, dt_actual = schedule.substeps(0)
        assert n_sub == 24
        assert dt_actual == pytest.approx(3600.0)

    def test_substeps_non_exact(self):
        """10000 / 3600 → ceil = 3, dt_actual = 10000/3 ≈ 3333.3."""
        schedule = _single_interval_schedule(dt_hist=10000.0, dt_int=3600.0)
        n_sub, dt_actual = schedule.substeps(0)
        assert n_sub == 3
        assert dt_actual == pytest.approx(10000.0 / 3)

    def test_nsub_times_dt_equals_dt_hist(self):
        """n_sub · dt_actual = dt_hist точно (нет ошибки округления)."""
        schedule = _single_interval_schedule(dt_hist=100000.0, dt_int=7200.0)
        n_sub, dt_actual = schedule.substeps(0)
        assert n_sub * dt_actual == pytest.approx(100000.0, rel=1e-14)

    def test_dt_actual_le_dt_integration(self):
        """dt_actual ≤ dt_integration."""
        schedule = _single_interval_schedule(dt_hist=10000.0, dt_int=3600.0)
        _, dt_actual = schedule.substeps(0)
        assert dt_actual <= 3600.0

    def test_total_time(self):
        """total_time = сумма dt всех интервалов."""
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P0,
            T_ext=T0, Rs_ext=RS0)
        intervals = [
            ScheduleInterval(dt=86400.0, bc=bc),
            ScheduleInterval(dt=259200.0, bc=bc),
        ]
        schedule = TimeSchedule(3600.0, intervals)
        assert schedule.total_time() == pytest.approx(345600.0)

    def test_empty_intervals_raises(self):
        with pytest.raises(ValueError):
            TimeSchedule(3600.0, [])

    def test_negative_dt_integration_raises(self):
        with pytest.raises(ValueError):
            _single_interval_schedule(dt_hist=86400.0, dt_int=-1.0)


# ═══════════════════════════════════════════════════════════
# B. Simulator.run() — цикл по времени
# ═══════════════════════════════════════════════════════════

class TestSimulatorRun:
    def test_single_interval_n_saved(self):
        """1 интервал, 24 подшага → n_saved = 2 (начальное + конец).

        До DEBT-013 здесь было 25: save_every = 1 записывал каждый подшаг.
        Теперь состав истории определяет только расписание, а 24 подшага
        внутри интервала — вопрос точности, а не вывода.
        """
        grid, pvt, hydro, energy, _ = _make_simulator()
        schedule = _single_interval_schedule(dt_hist=86400.0, dt_int=3600.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())
        assert history.n_saved == 2

    def test_final_time(self):
        """t в конце = dt_hist."""
        grid, pvt, hydro, energy, _ = _make_simulator()
        schedule = _single_interval_schedule(dt_hist=86400.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())
        assert history.times[-1] == pytest.approx(86400.0)

    def test_two_intervals(self):
        """Два интервала с разными p_wf."""
        grid, pvt, hydro, energy, _ = _make_simulator()
        bc1 = BoundaryConditions(
            well=PressureControl(15e6), p_ext=P0, T_ext=T0, Rs_ext=RS0)
        bc2 = BoundaryConditions(
            well=PressureControl(10e6), p_ext=P0, T_ext=T0, Rs_ext=RS0)
        schedule = TimeSchedule(3600.0, [
            ScheduleInterval(dt=7200.0, bc=bc1),   # 2 подшага
            ScheduleInterval(dt=3600.0, bc=bc2),   # 1 подшаг
        ])
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())

        # 1 начальный + по одной записи на конце каждого интервала = 3.
        # Подшагов внутри (2 и 1) в истории больше не видно (DEBT-013).
        assert history.n_saved == 3
        np.testing.assert_allclose(history.times, [0.0, 7200.0, 10800.0])

    def test_initial_state_preserved(self):
        """Начальное состояние сохранено первым в history."""
        grid, pvt, hydro, energy, _ = _make_simulator()
        schedule = _single_interval_schedule(dt_hist=3600.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        initial = _initial_state()
        history = sim.run(initial)

        assert history.times[0] == 0.0
        np.testing.assert_allclose(history.states[0].p, P0)
        np.testing.assert_allclose(history.states[0].T, T0)

    def test_time_monotonic(self):
        """times строго возрастают."""
        grid, pvt, hydro, energy, _ = _make_simulator()
        schedule = _single_interval_schedule(dt_hist=36000.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())

        times = np.array(history.times)
        assert np.all(np.diff(times) > 0)


# ═══════════════════════════════════════════════════════════
# C. Factory: from_config → run
# ═══════════════════════════════════════════════════════════

class TestFactory:
    def test_from_baseline(self):
        """Factory создаёт Simulator из baseline.json, run() не падает."""
        config = load_config(BASELINE)
        simulator, initial_state = SimulatorFactory.from_config(config)
        history = simulator.run(initial_state)

        assert history.n_saved > 1
        assert history.times[-1] == pytest.approx(345600.0)

    def test_initial_state_from_config(self):
        """Начальное состояние: p=p0, T=T0, Rs=Rs0, Sg=0, regime=2."""
        config = load_config(BASELINE)
        _, initial_state = SimulatorFactory.from_config(config)

        np.testing.assert_allclose(initial_state.p, config.initial_conditions.p0)
        np.testing.assert_allclose(initial_state.T, config.initial_conditions.T0)
        np.testing.assert_allclose(initial_state.Rs, config.initial_conditions.Rs0)
        np.testing.assert_allclose(initial_state.Sg, 0.0)
        np.testing.assert_array_equal(initial_state.regime, 2)
        assert initial_state.t == 0.0

    def test_well_rate_positive(self):
        """Дебит нефти > 0 при добыче."""
        config = load_config(BASELINE)
        simulator, initial_state = SimulatorFactory.from_config(config)
        history = simulator.run(initial_state)

        # Последний сохранённый шаг
        assert history.well_data[-1].q_o_std > 0


# ═══════════════════════════════════════════════════════════
# D. Физика
# ═══════════════════════════════════════════════════════════

class TestPhysics:
    def test_T_converges_to_T_ext_without_JT(self):
        """Чистая конвекция + теплопроводность → T → T_ext.

        Выключенные эффекты:
          - JT: μ_JT_oil = μ_JT_gas = 0 (передаётся в StandingFullPVT)
          - Дегазация: L_degas = 0 (передаётся в StandingFullPVT)
          - Адиабатический: LogProfileHydroStub даёт стационарный p(r),
            после первого шага dp/dt = 0 → Q_ad = 0 на всех последующих
          - Двухфазность: Sg = 0, krg = 0 → Q_g = 0 (только нефтяная фаза)

        Активные эффекты:
          - Конвекция: стационарный поток нефти от контура к скважине
            переносит T_ext (upstream = контур при типичном притоке)
          - Теплопроводность: λ_eff > 0 (порода + нефть), Дирихле T_ext на контуре

        Оба механизма приводят T к T_ext. Маленькая сетка (R = 5 м) уменьшает
        конвективное время промывки τ ~ πR²hφ/(q) для быстрой сходимости.
        """
        n_cells = 5
        grid = LogRadialGrid(R_WELL, 5.0, H, n_cells, K_PERM)
        pvt = StandingFullPVT(850.0, 0.85, T0, RS0, 0.0, 2000.0, 1000.0)
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        hydro = LogProfileHydroStub(grid, pvt, rp)
        rock = RockConfig(porosity=PHI, permeability=K_PERM)
        energy = TridiagEnergySolver(grid, pvt, rock)

        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P0,
            T_ext=350.0, Rs_ext=RS0)
        # 500 часов — достаточно для промывки маленькой области
        schedule = TimeSchedule(3600.0, [ScheduleInterval(dt=1800000.0, bc=bc)])
        sim = Simulator(grid, hydro, energy, pvt, schedule)

        # Начальное T = 340 К ≠ T_ext = 350 К — конвекция должна «промыть»
        initial = SimulationState(
            p=np.full(n_cells, P0), Sg=np.zeros(n_cells),
            Rs=np.full(n_cells, RS0), T=np.full(n_cells, 340.0),
            regime=np.full(n_cells, 2, dtype=int), t=0.0)

        history = sim.run(initial)

        T_final = history.states[-1].T
        assert np.max(np.abs(T_final - 350.0)) < 1.0, \
            f"T не сошлась к T_ext: max|T-350| = {np.max(np.abs(T_final - 350.0)):.2f}"

    def test_T_not_equal_T0_with_JT(self):
        """Пространственный JT-эффект отклоняет T от T0.

        Активные эффекты:
          - Конвекция: стационарный поток к скважине
          - Теплопроводность: λ_eff > 0
          - JT (пространственный): μ_JT_oil = -3e-7 К/Па ≠ 0.
            На каждой грани: J_face = μ_JT · <Φ·p>. При стационарном потоке
            давление неоднородно (лог-профиль) → J_face ≠ 0 → J_jt ≠ 0.
          - Адиабатический: только на первом шаге (dp = p_stationary - p0 ≠ 0).
            На последующих шагах dp/dt = 0 (p не меняется).

        Выключенные эффекты:
          - Дегазация: L = 0
          - Двухфазность: Sg = 0

        Конвекция тянет T к T_ext = T0 = 350. JT одновременно создаёт
        пространственный перепад T. В стационаре T(r) ≠ T0 — баланс
        между конвекцией и JT. Знак отклонения зависит от соотношения
        конвективного и JT-вкладов (не обязательно охлаждение).
        """
        grid, pvt, hydro, energy, _ = _make_simulator(mu_JT_oil=-3e-7)
        # 100 часов — выход на квазистационар
        schedule = _single_interval_schedule(dt_hist=360000.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())

        T_final = history.states[-1].T
        # T отличается от T0 — JT-эффект создаёт температурный профиль
        assert np.max(np.abs(T_final - T0)) > 0.01, \
            f"T слишком близка к T0: max|T-T0| = {np.max(np.abs(T_final - T0)):.4f}"

    def test_pressure_is_analytical_log_profile(self):
        """Splitting: Simulator не искажает профиль давления.

        LogProfileHydroStub строит стационарный лог-профиль p(r) на каждом
        шаге, не зависящий от входного state. EnergySolver обновляет только T.
        Проверяем, что после полного цикла (hydro → energy → state update)
        давление в state совпадает с аналитической формулой:
          p(r) = p_wf + (p_ext - p_wf) · ln(r/rw) / ln(R/rw).

        Выключенные эффекты: все тепловые (проверяется только p, не T).
        Активные: гидродинамика (LogProfileHydroStub).
        """
        grid, pvt, hydro, energy, _ = _make_simulator()
        schedule = _single_interval_schedule(dt_hist=3600.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())

        p_final = history.states[-1].p
        log_ratio = np.log(grid.r_centers / R_WELL) / np.log(R_EXT / R_WELL)
        p_expected = P_WF + (P0 - P_WF) * log_ratio
        np.testing.assert_allclose(p_final, p_expected, rtol=1e-12)


# ═══════════════════════════════════════════════════════════
# E. Состав истории задаёт только расписание (DEBT-013)
# ═══════════════════════════════════════════════════════════

class TestHistoryComposition:
    """Единственный механизм отбора записей — структура time.history.

    Заменяет класс TestSaveEvery. Прежде частоту вывода задавали два
    независимых механизма, и счётчик подшагов перебивал расписание: при
    save_every = 1 запись шла на каждом подшаге независимо от того, какие
    интервалы задал пользователь. Это трижды ломало постобработку
    (BUG-004, BUG-005, FEAT-016).
    """

    def test_history_records_interval_ends(self):
        """Запись строго на концах интервалов, по одной на интервал.

        3 интервала по 36 000 с при dt_integration = 3600 — это 10
        подшагов внутри каждого. Записей должно быть 4: начальное
        состояние плюс три конца, а не 31.
        """
        grid, pvt, hydro, energy, _ = _make_simulator()
        bc = BoundaryConditions(
            well=PressureControl(P_WF), p_ext=P0, T_ext=T0, Rs_ext=RS0)
        schedule = TimeSchedule(3600.0, [
            ScheduleInterval(dt=36000.0, bc=bc) for _ in range(3)
        ])
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())

        assert history.n_saved == 4
        np.testing.assert_allclose(
            history.times, [0.0, 36000.0, 72000.0, 108000.0])

    def test_history_step_independent_of_dt_integration(self):
        """Моменты записи не зависят от шага интегрирования.

        Главный дефект DEBT-013: dt_integration отвечает за точность
        схемы, а не за частоту вывода. Одно расписание при вчетверо
        разном шаге обязано дать одни и те же моменты записи.
        """
        times = {}
        for dt_int in (3600.0, 900.0):
            grid, pvt, hydro, energy, _ = _make_simulator()
            bc = BoundaryConditions(
                well=PressureControl(P_WF), p_ext=P0, T_ext=T0, Rs_ext=RS0)
            schedule = TimeSchedule(dt_int, [
                ScheduleInterval(dt=7200.0, bc=bc) for _ in range(2)
            ])
            sim = Simulator(grid, hydro, energy, pvt, schedule)
            times[dt_int] = sim.run(_initial_state()).times

        assert len(times[3600.0]) == len(times[900.0]) == 3
        np.testing.assert_allclose(times[3600.0], times[900.0])

    def test_last_record_is_interval_end(self):
        """Последняя запись — точно конец последнего интервала.

        substeps() делит интервал так, что n_sub * dt_actual = dt_hist
        ровно, поэтому кратность dt_hist шагу интегрирования не требуется.
        Здесь 36 000 / 7000 = 5.14 подшага → 6 подшагов по 6000 с.
        """
        grid, pvt, hydro, energy, _ = _make_simulator()
        schedule = _single_interval_schedule(dt_hist=36000.0, dt_int=7000.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())

        assert history.n_saved == 2          # начальное + конец интервала
        assert history.times[-1] == pytest.approx(36000.0)
