"""Simulator (оркестратор) + TimeSchedule (runtime-расписание).

Simulator координирует гидродинамику и теплоперенос.
Зависит только от абстракций (Grid, HydroSolver, EnergySolver, HydroPVT).
Конкретные реализации передаются через конструктор (Dependency Injection).

Цикл по времени (Template Method):
  Внешний: по интервалам schedule.intervals (смена BC)
  Внутренний: n_sub подшагов × (hydro.solve → energy.solve → обновить state)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state import (
    SimulationState, HydroResult, WellData,
    BoundaryConditions, SimulationHistory,
)
from .grid.base import Grid
from .hydro.base import HydroSolver
from .energy.base import EnergySolver
from .energy.balance import EnergyBalanceAccumulator
from .pvt.base import HydroPVT
from .io.config import OutputConfig
from .log import user_log


# ── TimeSchedule: runtime-расписание ─────────────────────────

@dataclass
class ScheduleInterval:
    """Один интервал истории (runtime-уровень).

    dt — длительность интервала, с.
    bc — граничные условия (содержит WellControl, p_ext, T_ext, Rs_ext, Sg_ext).
    """
    dt: float
    bc: BoundaryConditions


class TimeSchedule:
    """Расписание: интервалы истории + шаг интегрирования.

    Аналог InjectorGPN: t_major_step (интервал) + t_minor_step (подшаг).
    Гарантия: n_sub · dt_actual = dt_hist точно (нет накопления ошибки округления).
    """

    def __init__(self, dt_integration: float,
                 intervals: list[ScheduleInterval]):
        if dt_integration <= 0:
            raise ValueError(f"dt_integration должен быть > 0, получено {dt_integration}")
        if len(intervals) == 0:
            raise ValueError("intervals не может быть пустым")
        self.dt_integration = dt_integration
        self.intervals = intervals

    def substeps(self, interval_idx: int) -> tuple[int, float]:
        """Число подшагов и фактический шаг для интервала k.

        n_sub = ceil(dt_hist / dt_integration)
        dt_actual = dt_hist / n_sub

        Гарантии:
          - dt_actual ≤ dt_integration
          - n_sub · dt_actual = dt_hist ровно
        """
        dt_hist = self.intervals[interval_idx].dt
        n_sub = int(np.ceil(dt_hist / self.dt_integration))
        n_sub = max(n_sub, 1)
        dt_actual = dt_hist / n_sub
        return n_sub, dt_actual

    def total_time(self) -> float:
        """Суммарное время всех интервалов, с."""
        return sum(iv.dt for iv in self.intervals)

    @property
    def n_intervals(self) -> int:
        return len(self.intervals)


# ── Simulator: оркестратор ───────────────────────────────────

class Simulator:
    """Координирует гидродинамику и теплоперенос.

    Зависит только от абстракций: Grid, HydroSolver, EnergySolver, HydroPVT.
    Конкретные реализации передаются через конструктор (DI).
    """

    def __init__(self, grid: Grid, hydro: HydroSolver,
                 energy: EnergySolver, pvt: HydroPVT,
                 schedule: TimeSchedule,
                 output_config: OutputConfig | None = None):
        """
        grid          — пространственная сетка (immutable, общая для всех модулей)
        hydro         — гидродинамический солвер (ABC: PrototypeHydroAdapter, ...)
        energy        — тепловой солвер (ABC: TridiagEnergySolver, ...)
        pvt           — PVT-модель (для rho_o_std, rho_g_std в WellData)
        schedule      — расписание: интервалы + шаг интегрирования
        output_config — параметры вывода (log_level, format), опционально
        """
        self._grid = grid
        self._hydro = hydro
        self._energy = energy
        self._pvt = pvt
        self._schedule = schedule
        # save_every удалён (DEBT-013): состав истории определяет только
        # структура time.history. output_config остаётся ради log_level
        # и format, поэтому из сигнатуры не убирается.

    def run(self, initial_state: SimulationState) -> SimulationHistory:
        """Основной цикл по времени.

        Аргументы:
            initial_state — начальное состояние (p0, Sg=0, Rs0, T0, regime=2, t=0)

        Возвращает:
            SimulationHistory — сохранённые шаги (times, states, hydro_results, well_data)
        """
        history = SimulationHistory()

        # Баланс энергии накапливается по ВСЕМ подшагам и считается всегда
        # (DEBT-013): восстановить его по записям истории нельзя, а
        # отключать по флагу нельзя по требованию к валидации схемы.
        balance = EnergyBalanceAccumulator(self._grid)

        state = initial_state

        # Сохранить начальное состояние (нулевые потоки)
        history.append(
            t=state.t,
            state=state,
            hydro=self._zero_hydro(state),
            well=self._zero_well_data(state),
        )

        user_log.info(
            f"Расчет: {self._schedule.n_intervals} интервалов, "
            f"T_total = {self._schedule.total_time():.0f} с")

        # ── Внешний цикл: по интервалам истории ──
        for k, interval in enumerate(self._schedule.intervals):
            n_sub, dt = self._schedule.substeps(k)

            user_log.info(
                f"  Интервал {k+1}/{self._schedule.n_intervals}: "
                f"dt_hist={interval.dt:.0f} с, {n_sub} подшагов, "
                f"dt_actual={dt:.1f} с")

            # ── Внутренний цикл: подшаги интегрирования ──
            for step in range(n_sub):
                state, hydro_result = self._advance(
                    state, dt, interval.bc, balance)

                # 4. Сохранить состояние на конце интервала истории.
                # Единственный механизм отбора: моменты записи задаёт
                # расписание, а не шаг интегрирования (DEBT-013).
                # Члены баланса накоплены по ВСЕМ подшагам интервала,
                # поэтому запись реже подшага их не портит.
                if step == n_sub - 1:
                    well = WellData(
                        q_o_std=-hydro_result.G_o[0],
                        q_g_std=-hydro_result.G_g[0],
                        m_o_well=self._pvt.rho_o_std * (-hydro_result.G_o[0]),
                        m_g_well=self._pvt.rho_g_std * (-hydro_result.G_g[0]),
                        # Фактическое давление шага из HydroResult (FEAT-020):
                        # при управлении по дебиту оно не задано, а вычислено.
                        p_wf=hydro_result.p_wf,
                        T_wf=state.T[0],
                    )
                    history.append(t=state.t, state=state,
                                   hydro=hydro_result, well=well,
                                   balance=balance.snapshot())

        user_log.info(
            f"Симуляция завершена: {history.n_saved} сохранённых шагов, "
            f"T_final = {state.t:.0f} с")

        return history

    def _advance(self, state: SimulationState, dt: float,
                 bc: BoundaryConditions,
                 balance: EnergyBalanceAccumulator,
                 allow_subdivision: bool = True
                 ) -> tuple[SimulationState, HydroResult]:
        """Один шаг dt: гидродинамика → энергия → новое состояние.

        Если гидро-решатель раздробил шаг на n_substeps подшагов (A-retry),
        шаг энергии дробится на столько же. Причина — BUG-010: расщепление
        «гидро → энергия» имеет порядок O(dt) и применимо лишь там, где
        устойчивы обе половины. Решать энергию одним шагом по интервалу,
        который гидродинамика признала слишком крупным, значит накопить
        ошибку порядка градуса (замерено −1.39 К против −0.06 К при
        дроблении, пример 07 при dt = 450 с).

        Порядок вызовов критичен. `EnergyBalanceAccumulator` — кумулятивный
        сумматор без отката: вклад, единожды добавленный в него, убрать
        нельзя. Поэтому энергия решается только ПОСЛЕ того, как выяснено
        окончательное число подшагов; результат «пробного» крупного шага
        отбрасывается до того, как он попадёт в баланс.

        allow_subdivision=False запрещает повторное дробление: так
        ограничивается один уровень вложенности. Подшаг, который сам
        потребовал retry, принимается как есть — иначе рекурсия не имеет
        дна. На примере 07 такого не происходит ни разу (подшаги 225 и
        200 с сходятся без дробления), это страховка для других конфигов.
        """
        # 1. Гидродинамика → p^{n+1}, Sg^{n+1}, Rs^{n+1} + потоки
        hydro_result = self._hydro.solve(state, dt, bc)

        n_sub = getattr(hydro_result, 'n_substeps', 1)

        if allow_subdivision and n_sub > 1:
            # Результат пробного шага отбрасываем целиком и проходим
            # интервал заново — гидро и энергию вместе, тем же дроблением.
            # Гидро-подшаги при этом считаются повторно: плата за то, что
            # A-retry живёт внутри адаптера (DEBT-015).
            dt_sub = dt / n_sub
            for _ in range(n_sub):
                state, hydro_result = self._advance(
                    state, dt_sub, bc, balance, allow_subdivision=False)
            return state, hydro_result

        if n_sub > 1:
            # Вложенное дробление: принимаем как есть, но не молчим —
            # часть ошибки расщепления здесь остаётся неисправленной.
            user_log.warning(
                f"Гидро раздробило подшаг dt={dt:.3g} с на {n_sub} частей; "
                f"шаг энергии не дробится (предел вложенности). "
                f"Точность T на этом шаге снижена — уменьшите dt_integration.")

        # 2. Температура на замороженных p, Sg, Rs.
        # Решатель попутно отдаёт накопителю коэффициенты, которые
        # уходят в СЛАУ, — баланс считается по тем же величинам,
        # что и схема (DEBT-013).
        T_new = self._energy.solve(
            hydro_result, state, dt, bc, collect=balance)

        # 3. Обновить состояние (splitting: T из energy, остальное из hydro)
        new_state = SimulationState(
            p=hydro_result.state.p,
            Sg=hydro_result.state.Sg,
            Rs=hydro_result.state.Rs,
            T=T_new,
            regime=hydro_result.state.regime,
            t=hydro_result.state.t,
        )
        return new_state, hydro_result

    def _zero_hydro(self, state: SimulationState) -> HydroResult:
        """HydroResult с нулевыми потоками (для начального состояния)."""
        N = self._grid.N
        Z = np.zeros(N + 1)
        # p_wf = p[0]: потока нет — то же значение, что в _zero_well_data
        return HydroResult(
            state=state, G_o=Z, G_g=Z, G_free_gas=Z,
            Q_o=Z, Q_g=Z, u_o=Z, u_g=Z,
            m_o=Z, m_g=Z, Gm_o=Z, Gm_g=Z,
            p_wf=state.p[0])

    def _zero_well_data(self, state: SimulationState) -> WellData:
        """WellData с нулевыми дебитами (для начального состояния)."""
        return WellData(
            q_o_std=0.0, q_g_std=0.0,
            m_o_well=0.0, m_g_well=0.0,
            p_wf=state.p[0], T_wf=state.T[0])
