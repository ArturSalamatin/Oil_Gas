"""Тесты для Simulator + Factory + TimeSchedule (фаза 6).

Интеграционные тесты: полный цикл hydro → energy → state update.
Используют LogProfileHydroStub + TridiagEnergySolver (реальный энергетический
солвер, гидродинамика — тестовый двойник с детерминированным p(r)).

A. TimeSchedule: substeps, total_time
B. Simulator.run(): цикл по времени, сохранение, смена BC
C. Factory: from_config(baseline.json) → run()
D. Физика: T сходится к T_ext, JT-охлаждение, стационарность p(r)
E. Состав истории: записи на концах интервалов time.history (DEBT-013)
F. Синхронное дробление шага энергии: подшаги гидро и энергии (BUG-010, DEBT-015)
G. Отказ при нефизичной температуре: T ≤ 0 или не конечна (DEBT-047)
"""

from pathlib import Path
import numpy as np
import pytest

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions
from gpn_multiphase_solver.bc import PressureControl
from ._doubles import LogProfileHydroStub, FailingHydroStub
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

    def test_well_data_pwf_from_hydro_result(self):
        """p_wf в записи скважины — из HydroResult, а не из граничного условия.

        Единый источник гидродинамических величин (FEAT-020): при управлении
        по дебиту p_wf известно только после гидро-шага, поэтому Simulator
        обязан брать его из результата шага. Запись 0 — начальное состояние:
        и WellData, и нулевой HydroResult несут p[0] (simulator.py, _zero_*).
        Ловит: второй источник p_wf в выводе.
        """
        grid, pvt, hydro, energy, _ = _make_simulator()
        schedule = _single_interval_schedule(dt_hist=7200.0, dt_int=3600.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)
        history = sim.run(_initial_state())

        assert history.well_data[0].p_wf == history.states[0].p[0]
        assert history.hydro_results[0].p_wf == history.states[0].p[0]
        for n in range(1, history.n_saved):
            assert history.well_data[n].p_wf == history.hydro_results[n].p_wf


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


# ── F. Синхронное дробление шага энергии (BUG-010) ───────────

class _CountingEnergySolver:
    """Обёртка над энергетическим решателем: считает вызовы и их dt.

    Не подменяет физику — делегирует настоящему TridiagEnergySolver.
    Нужна, чтобы проверить, СКОЛЬКО шагов энергии сделал Simulator и
    какой длины, не полагаясь на разбор логов.
    """

    def __init__(self, inner):
        self._inner = inner
        self.dt_calls: list[float] = []

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        self.dt_calls.append(dt)
        return self._inner.solve(hydro_result, state_prev, dt, bc, collect)


def _retry_run(fails, max_retries=None):
    """Simulator на двойнике с отказами: один интервал 3600 с = один шаг интегрирования."""
    grid, pvt, inner_hydro, inner_energy, _ = _make_simulator()
    hydro = FailingHydroStub(inner_hydro, fails)
    energy = _CountingEnergySolver(inner_energy)
    schedule = _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0)
    # max_retries = None — умолчание Simulator (9): единица дробления 3600/512 с
    kw = {} if max_retries is None else {"max_retries": max_retries}
    sim = Simulator(grid, hydro, energy, pvt, schedule, **kw)
    return sim, hydro, energy


class TestEnergySubstepsUnderRetry:
    """BUG-010, DEBT-015: Simulator дробит шаг локально, энергия идёт по принятым подшагам гидро."""

    def test_energy_steps_match_hydro_substeps(self):
        """Когда гидро не сходится на шаге, энергия проходит те же подшаги.

        Физика: расщепление «гидро -> энергия» имеет порядок O(dt) и
        применимо лишь на шаге, где обе половины устойчивы. Если гидро
        признало dt слишком крупным и раздробило его, решать энергию
        одним большим шагом нельзя: замерено -1.39 К ошибки на первом
        шаге при dt = 450 с против -0.06 К при дроблении энергии на 2
        (улучшение в 11.8 раза при ИДЕНТИЧНОМ гидро-состоянии) — BUG-010.
        """
        # Двойник отказывает на шагах длиннее 1800 с: 3600 ✗ → 1800 ✓ → 1800 ✓
        sim, hydro, energy = _retry_run(lambda s, dt: dt > 1800.0)
        sim.run(_initial_state())

        assert hydro.dt_calls == [3600.0, 1800.0, 1800.0]
        # Энергия должна пройти 2 шага по 1800 с, а не 1 шаг на 3600 с.
        assert energy.dt_calls == [1800.0, 1800.0]

        # Интервал пройден ровно один раз: сумма dt энергии = длине интервала.
        # Ловит ошибку «отказавший шаг не отброшен, интервал посчитан дважды».
        assert sum(energy.dt_calls) == pytest.approx(3600.0)

    def test_no_retry_path_unchanged(self):
        """Без отказов гидродинамики путь исполнения не меняется вовсе.

        Энергия обязана получить ровно один вызов с полным dt. Регрессия на
        штатный путь: все рабочие конфиги идут именно так, и их результаты
        меняться не должны.
        """
        sim, hydro, energy = _retry_run(lambda s, dt: False)
        sim.run(_initial_state())

        assert hydro.dt_calls == [3600.0]
        assert energy.dt_calls == [3600.0]

    def test_subdivision_does_not_duplicate_history(self):
        """Дробление не добавляет записей в историю.

        Состав истории задаёт расписание, а не число подшагов (DEBT-013).
        Подшаги — деталь Simulator._advance, снаружи они не должны быть видны.
        """
        sim, hydro, energy = _retry_run(lambda s, dt: dt > 1800.0)
        history = sim.run(_initial_state())

        assert history.n_saved == 2                        # начальное + конец
        assert history.times[-1] == pytest.approx(3600.0)  # время не удвоилось

    def test_only_failed_substep_refined(self):
        """Делится только не сошедшийся подшаг; принятые не пересчитываются (DEBT-015).

        Двойник: отказ на шагах > 1800 с и, начиная с t = 1800 с, на шагах > 900 с.
        Последовательность в единицах 3600/512 с: 3600 ✗ → 1800 ✓ (t = 0) →
        пройдено 256 из 512, рост запрещён (256 % 512 ≠ 0) → 1800 при t = 1800 ✗ →
        900 ✓ → пройдено 384, рост запрещён (384 % 256 ≠ 0) → 900 ✓.
        Равномерное дробление прежнего A-retry дало бы энергию 4 × 900 с.
        """
        sim, hydro, energy = _retry_run(
            lambda s, dt: dt > 1800.0 or (dt > 900.0 and s.t >= 1800.0))
        sim.run(_initial_state())

        assert hydro.dt_calls == [3600.0, 1800.0, 1800.0, 900.0, 900.0]
        assert energy.dt_calls == [1800.0, 900.0, 900.0]

    def test_substep_grows_after_success(self):
        """После удачи подшаг удваивается — только когда граница кратна удвоенному (DEBT-015).

        Двойник: до t = 900 с отказ на шагах > 900 с. 3600 ✗, 1800 ✗ → 900 ✓ →
        пройдено 128, рост запрещён (128 % 256 ≠ 0) → 900 ✓ → пройдено 256,
        рост: 256 % 256 = 0 → 1800 ✓. Без выравнивания (G1) энергия шла бы
        900, 1800, 900 — подшаг 1800 с поперёк границы 1800 с; без роста
        (G0) — 4 × 900 с.
        """
        sim, hydro, energy = _retry_run(lambda s, dt: s.t < 900.0 and dt > 900.0)
        sim.run(_initial_state())

        assert hydro.dt_calls == [3600.0, 1800.0, 900.0, 900.0, 1800.0]
        assert energy.dt_calls == [900.0, 900.0, 1800.0]

    def test_exhausted_subdivision_raises(self):
        """Не сошлось и на наименьшем подшаге dt/2**max_retries — RuntimeError с фактами.

        max_retries = 2: попытки 3600, 1800, 900 с — все отказ. Энергия не
        вызывается ни разу: в накопитель баланса не попадает ни один
        отказавший подшаг. Текст называет глубину и оба рычага.
        """
        sim, hydro, energy = _retry_run(lambda s, dt: True, max_retries=2)
        with pytest.raises(
                RuntimeError,
                match=r"^HydroSolver не сошёлся при дроблении шага до dt/4 = ") as exc:
            sim.run(_initial_state())

        msg = str(exc.value)
        assert "time.dt_integration" in msg
        assert "numerics.max_retries" in msg
        assert hydro.dt_calls == [3600.0, 1800.0, 900.0]
        assert energy.dt_calls == []

    def test_other_errors_not_subdivided(self):
        """Ошибка кода в гидро (не HydroConvergenceError) не маскируется дроблением.

        Simulator ловит только отказ сходимости; любой другой RuntimeError
        уходит наружу с первого вызова, без повторов.
        """

        class _Broken(FailingHydroStub):
            def solve(self, state, dt, bc):
                self.dt_calls.append(dt)
                raise RuntimeError("сбой двойника")

        grid, pvt, inner_hydro, inner_energy, _ = _make_simulator()
        hydro = _Broken(inner_hydro, lambda s, dt: False)
        sim = Simulator(grid, hydro, inner_energy, pvt,
                        _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
        with pytest.raises(RuntimeError, match="сбой двойника"):
            sim.run(_initial_state())
        assert hydro.dt_calls == [3600.0]


# ═══════════════════════════════════════════════════════════
# G. Отказ при нефизичной температуре (DEBT-047)
# ═══════════════════════════════════════════════════════════
#
# Гидродинамика от T не зависит (PVT при T0), поэтому до DEBT-047 нефизичная T
# доходила до истории без отказа и предупреждения: B_o < 0 в таблице до
# DEBT-044 дало T_min = −245.8 К (vault/issues/debt-044/probes/red_state.out.txt),
# c_p,o < 0 в конфиге — −7947 К (vault/issues/debt-047/probes/red_state.out.txt).
# Тесты портят T обёрткой решателя энергии: ввод допустим, отказ обязан дать
# сам Simulator, откуда бы ни взялась нефизичная T.


class _CorruptingEnergySolver:
    """Обёртка решателя энергии: на вызове on_call ставит T[cell] = value.

    Физику не подменяет — делегирует настоящему TridiagEnergySolver и портит
    только его результат.
    """

    def __init__(self, inner, value, cell=3, on_call=2):
        self._inner = inner
        self._value = value
        self._cell = cell
        self._on_call = on_call
        self.n_calls = 0

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        T = self._inner.solve(hydro_result, state_prev, dt, bc, collect)
        self.n_calls += 1
        if self.n_calls == self._on_call:
            T = T.copy()
            T[self._cell] = self._value
        return T


class TestNonphysicalTemperature:
    """Simulator останавливает расчёт, если после шага энергии T ≤ 0 или не конечна."""

    @pytest.mark.parametrize("value", [
        -245.8,     # порядок замера DEBT-044 (B_o < 0 в таблице)
        0.0,        # граница: абсолютный нуль недопустим
        np.nan,     # NaN — не число: ловит isfinite
        np.inf,
        -np.inf,
    ], ids=["negative", "zero", "nan", "inf", "minus_inf"])
    def test_nonphysical_T_raises(self, value):
        """Отказ называет шаг, время его конца, ячейку, её r и значение T.

        24 шага по 1 ч, T испорчена на втором вызове энергии: конец шага
        t = 7200 с = 0.0833 сут, ячейка 3 из 10.
        """
        grid, pvt, hydro, inner_energy, _ = _make_simulator()
        energy = _CorruptingEnergySolver(inner_energy, value, cell=3, on_call=2)
        sim = Simulator(grid, hydro, energy, pvt, _single_interval_schedule())

        with pytest.raises(RuntimeError, match="Нефизичная температура") as exc:
            sim.run(_initial_state())

        msg = str(exc.value)
        assert "dt = 3600 с" in msg
        assert "t = 0.0833 сут" in msg
        assert f"в ячейке 3 (r = {grid.r_centers[3]:.4g} м)" in msg
        assert f"T = {value:.6g} К" in msg
        assert "1 из 10" in msg
        # Расчёт остановлен на испорченном шаге, а не дошёл до конца
        assert energy.n_calls == 2

    def test_small_positive_T_passes(self):
        """T = 1 К нефизична для пласта, но положительна — расчёт идёт.

        Критерий — только T > 0 и конечность (решение DEBT-047), окна
        правдоподобия нет: тест ловит порог, добавленный без решения.
        Без JT и дегазации, при стационарном p схема энергии монотонна,
        и T дальше остаётся положительной.
        """
        grid, pvt, hydro, inner_energy, _ = _make_simulator()
        energy = _CorruptingEnergySolver(inner_energy, 1.0, cell=3, on_call=2)
        sim = Simulator(grid, hydro, energy, pvt, _single_interval_schedule())

        history = sim.run(_initial_state())

        assert energy.n_calls == 24
        assert history.times[-1] == pytest.approx(86400.0)
        assert np.all(history.states[-1].T > 0)

    def test_raises_under_subdivision(self):
        """Проверка работает и на подшагах локального дробления (DEBT-015).

        Гидро отказывает на шаге 3600 с: Simulator делит его пополам и
        проходит двумя подшагами по 1800 с. Отказавший шаг энергию не
        вызывает — первый вызов энергии и есть первый подшаг. T испорчена
        на нём: отказ называет его dt и не делит подшаг дальше (дробление
        ловит только HydroConvergenceError).
        """
        grid, pvt, inner_hydro, inner_energy, _ = _make_simulator()
        hydro = FailingHydroStub(inner_hydro, lambda s, dt: dt > 1800.0)
        energy = _CorruptingEnergySolver(inner_energy, -1.0, cell=0, on_call=1)
        schedule = _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)

        with pytest.raises(RuntimeError, match="Нефизичная температура") as exc:
            sim.run(_initial_state())

        msg = str(exc.value)
        assert "dt = 1800 с" in msg
        assert "в ячейке 0" in msg
        assert hydro.dt_calls == [3600.0, 1800.0]
        assert energy.n_calls == 1
