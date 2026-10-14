"""Simulator (оркестратор) + TimeSchedule (runtime-расписание).

Simulator координирует гидродинамику и теплоперенос.
Зависит только от абстракций (Grid, HydroSolver, EnergySolver, HydroPVT).
Конкретные реализации передаются через конструктор (Dependency Injection).

Цикл по времени (Template Method):
  Внешний: по интервалам schedule.intervals (смена BC)
  Внутренний: шаги dt_integration; шаг, на котором гидродинамика не
  сошлась, дробится локально (DEBT-015): подшаг × (hydro.solve →
  energy.solve → обновить state). Первый шаг интервала со сменой
  управления начинается с подшага dt/2**m и растёт ×2 (FEAT-032)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state import (
    SimulationState, HydroResult, WellData,
    BoundaryConditions, SimulationHistory,
)
from .grid.base import Grid
from .hydro.base import HydroSolver, HydroConvergenceError
from .energy.base import EnergySolver
from .energy.balance import EnergyBalanceAccumulator
from .mass_balance import MassBalanceAccumulator
from .pvt.base import HydroPVT, RelPermModel
from .units import DAY_TO_S
from .log import user_log, dev_log


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
    Первый шаг интервала со сменой управления начинается с подшага dt/2**m (FEAT-032).
    """

    def __init__(self, dt_integration: float,
                 intervals: list[ScheduleInterval],
                 dt_after_control_change: float | None = None):
        if dt_integration <= 0:
            raise ValueError(f"dt_integration должен быть > 0, получено {dt_integration}")
        if len(intervals) == 0:
            raise ValueError("intervals не может быть пустым")
        # Первый подшаг после смены управления, с (FEAT-032); None — нарастания
        # нет. «not > 0» отсекает и NaN.
        if dt_after_control_change is not None and not dt_after_control_change > 0:
            raise ValueError(
                f"dt_after_control_change должен быть > 0 или None, "
                f"получено {dt_after_control_change}")
        self.dt_integration = dt_integration
        self.intervals = intervals
        self.dt_after_control_change = dt_after_control_change

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

    def first_substep_depth(self, interval_idx: int) -> int:
        """Глубина m первого подшага dt/2**m на первом шаге интервала со сменой управления (FEAT-032)."""
        # Смена — граничные условия интервала не равны предыдущим; управление
        # сравнивается по значению (bc.py). Первый интервал сменой не считается
        # (решение пользователя 2026-10-11, когда мелкий первый шаг добычи из
        # равновесия в примерах 19 и 21 не сходился — BUG-028, исправлен в
        # прототипе; снятие исключения меняет истории всех примеров и решается
        # отдельно). m — наименьшее, при котором
        # dt/2**m <= h0: подшаги вида dt/2**k стыкуются с дроблением отказов
        # (DEBT-015) без остатка, а h0 округляется вниз не более чем вдвое.
        h0 = self.dt_after_control_change
        if h0 is None or interval_idx == 0:
            return 0
        if self.intervals[interval_idx].bc == self.intervals[interval_idx - 1].bc:
            return 0
        _, dt = self.substeps(interval_idx)
        m = 0
        while dt / 2 ** m > h0:
            m += 1
        return m

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
                 max_retries: int = 9,
                 relperm: RelPermModel | None = None):
        """
        grid          — пространственная сетка (immutable, общая для всех модулей)
        hydro         — гидродинамический солвер (ABC: PrototypeHydroAdapter, ...)
        energy        — тепловой солвер (ABC: TridiagEnergySolver, ...)
        pvt           — PVT-модель (для rho_o_std, rho_g_std в WellData)
        schedule      — расписание: интервалы + шаг интегрирования
        max_retries   — глубина дробления шага: наименьший подшаг
                        dt/2**max_retries (numerics.max_retries, DEBT-015)
        relperm       — модель ОФП, отданная гидродинамике; Simulator её не
                        использует, а хранит для диагностики (DEBT-011).
                        None — не задана (тестовые двойники)
        """
        self._grid = grid
        self._hydro = hydro
        self._energy = energy
        self._pvt = pvt
        self._schedule = schedule
        self._max_retries = int(max_retries)
        self._relperm = relperm
        # save_every удалён (DEBT-013): состав истории определяет только
        # структура time.history. output_config удалён (DEBT-053): Simulator
        # его не читал — уровень журнала задаёт фабрика (setup_logging).

    # ── Объекты задачи для диагностики (DEBT-011) ────────────
    # Публичный доступ вместо sim._grid, sim._energy._pvt: диагностика
    # обязана видеть ровно те объекты, которыми считалась задача.

    @property
    def grid(self) -> Grid:
        """Сетка задачи."""
        return self._grid

    @property
    def pvt(self) -> HydroPVT:
        """PVT задачи — тот же объект, что у решателя энергии и гидродинамики."""
        return self._pvt

    @property
    def relperm(self) -> RelPermModel | None:
        """ОФП задачи по конфигу; Кори прототип получает её таблицей на 101 узле."""
        return self._relperm

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

        # Баланс массы компонентов (DEBT-039). Интегралы потоков через
        # забой и контур копятся по ВСЕМ принятым шагам — по записям
        # истории их не восстановить, как и члены баланса энергии. Запас —
        # функция состояния, на каждой записи его отдаёт решатель. None —
        # решатель массу не сохраняет (тестовые двойники): баланс не
        # считается, снимки истории — None.
        mass = (MassBalanceAccumulator()
                if self._hydro.component_inventories(initial_state) is not None
                else None)

        state = initial_state

        # Сохранить начальное состояние (нулевые потоки)
        history.append(
            t=state.t,
            state=state,
            hydro=self._zero_hydro(state),
            well=self._zero_well_data(state),
            mass_balance=self._mass_snapshot(mass, state),
        )

        user_log.info(
            f"Расчет: {self._schedule.n_intervals} интервалов, "
            f"T_total = {self._schedule.total_time():.0f} с")

        # ── Внешний цикл: по интервалам истории ──
        for k, interval in enumerate(self._schedule.intervals):
            n_sub, dt = self._schedule.substeps(k)
            # Первый шаг интервала со сменой управления начинается с подшага
            # dt/2**depth и растёт ×2 (FEAT-032): сразу после смены — самый
            # быстрый переходный процесс, а схема первого порядка по времени.
            # depth = 0 — полный шаг, как у остальных шагов интервала.
            depth = self._schedule.first_substep_depth(k)
            ramp = (f", первый шаг от {dt / 2 ** depth:.3g} с (смена управления)"
                    if depth else "")

            user_log.info(
                f"  Интервал {k+1}/{self._schedule.n_intervals}: "
                f"dt_hist={interval.dt:.0f} с, {n_sub} подшагов, "
                f"dt_actual={dt:.1f} с{ramp}")

            # ── Внутренний цикл: подшаги интегрирования ──
            for step in range(n_sub):
                state, hydro_result = self._advance(
                    state, dt, interval.bc, balance, mass,
                    depth if step == 0 else 0)

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
                                   balance=balance.snapshot(),
                                   mass_balance=self._mass_snapshot(mass, state))

        user_log.info(
            f"Симуляция завершена: {history.n_saved} сохранённых шагов, "
            f"T_final = {state.t:.0f} с")

        return history

    def _advance(self, state: SimulationState, dt: float,
                 bc: BoundaryConditions,
                 balance: EnergyBalanceAccumulator,
                 mass: MassBalanceAccumulator | None,
                 depth: int = 0
                 ) -> tuple[SimulationState, HydroResult]:
        """Шаг dt: подшаги гидро → энергия; не сошедшийся подшаг делится пополам (DEBT-015), первый — dt/2**depth (FEAT-032)."""
        # ── Локальное дробление (DEBT-015) ──
        # Подшаг, на котором гидродинамика не сошлась (HydroConvergenceError),
        # делится пополам и повторяется из того же состояния; принятый сразу
        # проходит балансы и энергию. После удачи подшаг удваивается, если
        # пройденная часть шага кратна удвоенному подшагу: подшаги остаются
        # вида dt/2**k и стыкуются без остатка. Наименьший подшаг —
        # dt/2**max_retries; не сошлось и на нём — RuntimeError.
        #
        # Энергия идёт ровно по подшагам гидро — BUG-010: расщепление
        # «гидро → энергия» имеет порядок O(dt) и применимо лишь там, где
        # устойчивы обе половины (замерено −1.39 К против −0.06 К при
        # дроблении, пример 07 при dt = 450 с).
        #
        # Накопители (EnergyBalanceAccumulator, MassBalanceAccumulator) —
        # кумулятивные сумматоры без отката. Откатывать нечего: отказ
        # гидродинамики случается до энергии, в накопители попадают только
        # принятые подшаги. Допущение «гидродинамика не зависит от T» не
        # нужно: каждый подшаг гидро видит T, обновлённое предыдущими.
        #
        # Равномерное дробление (A-retry адаптера до DEBT-015) требовало,
        # чтобы сходился каждый из 2**k равных подшагов: при немонотонной
        # сходимости по dt (BUG-019, BUG-020) один неудачный подшаг из 512
        # валил шаг, и останов из развитой газовой зоны при dt_integration =
        # 1 сут не проходил. Локальное дробление выбирает подшаг на каждом
        # участке отдельно.

        # Шаг dt в единицах наименьшего подшага dt/2**(max_retries + depth):
        # пройденная часть и текущий подшаг — целые, ошибка округления не
        # копится. Начальный подшаг — dt/2**depth (FEAT-032: первый шаг после
        # смены управления; depth = 0 — весь шаг, и код побитово прежний),
        # дробление отказа идёт на max_retries уровней ниже него. Рост ×2 с
        # выравниванием (ниже) доводит нарастание до dt/2: h, h, 2h, …, dt/2.
        n_units = 2 ** (self._max_retries + depth)
        done = 0              # пройдено единиц
        size = 2 ** self._max_retries   # текущий подшаг, единиц; всегда степень двойки
        n_ok = n_fail = 0
        h_min_ok = dt
        while done < n_units:
            # Деление на степень двойки точно: при глубине 1 подшаг побитово
            # равен dt/2 прежнего A-retry, и истории примеров не меняются.
            h = dt / (n_units // size)

            # 1. Гидродинамика → p, Sg, Rs + потоки на конце подшага
            try:
                hydro_result = self._hydro.solve(state, h, bc)
            except HydroConvergenceError as exc:
                # Ловим только отказ сходимости: ошибка кода в гидро
                # (иной RuntimeError) дроблением не маскируется.
                n_fail += 1
                dev_log.debug(f"  подшаг {h:.3e} с не сошёлся: {exc}")
                if size == 1:
                    raise RuntimeError(
                        self._failure_message(state, dt, exc, depth)) from exc
                size //= 2
                continue

            # Баланс массы (DEBT-039): только принятый подшаг.
            if mass is not None:
                mass.add_step(hydro_result)

            # 2. Температура на замороженных p, Sg, Rs подшага.
            # Решатель попутно отдаёт накопителю коэффициенты, которые
            # уходят в СЛАУ, — баланс считается по тем же величинам,
            # что и схема (DEBT-013).
            T_new = self._energy.solve(
                hydro_result, state, h, bc, collect=balance)

            # 2a. Нефизичная T — отказ (DEBT-047). Гидродинамика от T не зависит
            # (PVT при T0), поэтому без этой проверки T ≤ 0 доходит до истории
            # как обычный результат: B_o < 0 в таблице до DEBT-044 дало
            # T_min = −245.8 К (vault/issues/debt-044/probes/red_state.out.txt).
            # Проверка здесь, а не в решателе энергии: одна на любой
            # EnergySolver и на каждом подшаге — следующий подшаг с плохой T не
            # начинается. RuntimeError не HydroConvergenceError: подшаг не
            # делится, отказ уходит из run. Накопители баланса к этому моменту
            # уже получили вклад подшага — неважно: run их не возвращает.
            self._check_temperature(T_new, h, hydro_result.state.t)

            # 3. Обновить состояние (splitting: T из energy, остальное из hydro)
            state = SimulationState(
                p=hydro_result.state.p,
                Sg=hydro_result.state.Sg,
                Rs=hydro_result.state.Rs,
                T=T_new,
                regime=hydro_result.state.regime,
                t=hydro_result.state.t,
            )
            n_ok += 1
            h_min_ok = min(h_min_ok, h)
            done += size
            # Рост ×2 после удачи — только с выравниванием: граница кратна
            # удвоенному подшагу, поэтому n_units − done кратно 2·size и
            # удвоенный подшаг не выходит за конец шага. Без выравнивания
            # появляются подшаги не вида dt/2**k (замер при планировании:
            # 548 и 928 с при dt = 1 сут) и стык через остаток, а останов
            # 20B при 1 сут не проходит.
            if done < n_units and done % (2 * size) == 0:
                size *= 2

        if n_fail > 0:
            # Видимо сказывается на времени расчёта — сообщаем, как прежде
            # сообщал адаптер.
            user_log.info(
                f"Шаг {dt:.3g} с раздроблен: подшагов {n_ok}, наименьший "
                f"{h_min_ok:.3g} с, отказов гидродинамики {n_fail}")
        return state, hydro_result

    def _failure_message(self, state: SimulationState, dt: float,
                         exc: HydroConvergenceError, depth: int = 0) -> str:
        """Текст отказа: факты подшага, на котором исчерпано дробление, и его отказ гидродинамики (BUG-018, DEBT-015, DEBT-054, FEAT-032)."""
        # Факты, а не догадка о причине: отказ бывает из-за величины шага
        # (DEBT-007, BUG-003 — помогает дробление глубже) и не из-за неё
        # (BUG-017, BUG-018 до исправления, BUG-019 — шаг не сходится и при
        # мелких подшагах). Различить их здесь нельзя. Начало текста
        # цитируют README примеров 03, 05, 06, 07, 10 и тесты — менять
        # вместе с ними.
        # Конец текста — текст HydroConvergenceError этого подшага (DEBT-054): у
        # прототипа там допуск, мера условия по ячейке, причина выхода Ньютона и
        # какое условие сходимости не выполнено. Прежде он был виден только в
        # цепочке traceback и в отладочном журнале.
        n_units = 2 ** (self._max_retries + depth)
        n_two = int(np.count_nonzero(state.regime == 1))
        # Первый шаг после смены управления (FEAT-032) начат с dt/2**depth:
        # наименьший подшаг на depth уровней мельче, чем у остальных шагов.
        # Пол округления невязки на коротком подшаге снят допуском Ньютона
        # (BUG-025); причину отказа текст не угадывает, а называет поле и null.
        ramp = (f"Шаг — первый после смены управления: начат с подшага "
                f"dt/{2 ** depth} = {dt / 2 ** depth:.3g} с "
                f"(time.dt_after_control_change); если отказывает короткий "
                f"подшаг, увеличьте time.dt_after_control_change или задайте null. "
                if depth else "")
        return (
            f"HydroSolver не сошёлся при дроблении шага до dt/{n_units} = "
            f"{dt / n_units:.2e} с на подшаге с t = {state.t / DAY_TO_S:.4f} сут: "
            f"двухфазных ячеек {n_two} из {state.p.size}, "
            f"max S_g = {float(np.max(state.Sg)):.3f}. "
            f"Наименьший подшаг — time.dt_integration / 2**numerics.max_retries "
            f"(сейчас max_retries = {self._max_retries}, допустимо до 20). "
            f"Если отказ вызван величиной шага, поможет больший "
            f"numerics.max_retries или меньший time.dt_integration; если шаг "
            f"не сходится и при мелких подшагах, причина не в его величине. "
            f"{ramp}Последний отказ гидродинамики: {exc}")

    def _check_temperature(self, T: np.ndarray, dt: float, t: float) -> None:
        """Отказ, если после шага энергии T ≤ 0 или не конечна (DEBT-047)."""
        # NaN и ±inf отсекает isfinite, T ≤ 0 — сравнение
        bad = ~(np.isfinite(T) & (T > 0))
        if not bad.any():
            return
        # Сообщение — факты, а не догадка о причине, как у отказа
        # гидродинамики (_failure_message): первая от забоя плохая ячейка,
        # её r и T, число таких ячеек. t — время конца подшага; dt — его
        # длина (при локальном дроблении — подшаг, а не шаг расписания).
        j = int(np.argmax(bad))
        r = float(self._grid.r_centers[j])
        raise RuntimeError(
            f"Нефизичная температура после шага энергии dt = {dt:g} с к "
            f"t = {t / DAY_TO_S:.4f} сут: в ячейке {j} (r = {r:.4g} м) "
            f"T = {T[j]:.6g} К; ячеек с T ≤ 0 или не конечной T — "
            f"{int(np.count_nonzero(bad))} из {T.size}.")

    def _mass_snapshot(self, mass: MassBalanceAccumulator | None,
                       state: SimulationState) -> dict | None:
        """Снимок баланса массы на записи истории; None — решатель массу не сохраняет."""
        if mass is None:
            return None
        return mass.snapshot(self._hydro.component_inventories(state))

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
