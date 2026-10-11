---
name: модули-simulator-оркестратор
description: Simulator (Mediator) — цикл по времени, расписание BC, локальное дробление шага в _advance (DEBT-015), SimulationState, SimulationHistory
metadata:
  type: project
---

# Simulator — оркестратор (Mediator)

> **Обновлено 2026-10-10 ([[DEBT-050]]):** цикл шага, конструктор, фабрика и `SimulationHistory` — по коду после [[DEBT-015]] (локальное дробление в `Simulator._advance`, параметр `max_retries`) и [[DEBT-047]] (`_check_temperature`).

## Класс Simulator (реализовано: simulator.py)

```python
class Simulator:
    """Координирует гидродинамику и теплоперенос.

    Зависит только от абстракций: Grid, HydroSolver, EnergySolver, HydroPVT.
    Конкретные реализации передаются через конструктор (DI).
    """

    def __init__(self, grid: Grid, hydro: HydroSolver,
                 energy: EnergySolver, pvt: HydroPVT,
                 schedule: TimeSchedule,
                 max_retries: int = 9):
        ...

    def run(self, initial_state: SimulationState) -> SimulationHistory:
        """Основной цикл по времени."""
        ...
```

pvt нужен для WellData (rho_o_std, rho_g_std → массовые дебиты).
initial_state передаётся в run() — Factory создаёт его отдельно.
max_retries — глубина локального дробления шага (DEBT-015): наименьший
подшаг dt/2**max_retries. Фабрика передаёт `numerics.max_retries`
(целое в [0, 20], по умолчанию 9 — проверка в `_validate`).
Параметр output_config удалён в [[DEBT-053]]: Simulator его не читал;
уровень журнала задаёт фабрика (`setup_logging(config.output.log_level)`).

## SimulationState — состояние системы (реализовано: state.py)

```python
@dataclass
class SimulationState:
    p: np.ndarray        # [N] давление, Па
    Sg: np.ndarray       # [N] газонасыщенность
    Rs: np.ndarray       # [N] газосодержание, м³ст/м³ст
    T: np.ndarray        # [N] температура, К
    regime: np.ndarray   # [N] int: 1=двухфазная, 2=однофазная
    t: float             # текущее время, с
```

Начальное состояние создаётся в Factory (не в Simulator):
```python
initial_state = SimulationState(
    p=np.full(N, ic.p0), Sg=np.zeros(N), Rs=np.full(N, ic.Rs0),
    T=np.full(N, ic.T0), regime=np.full(N, 2, dtype=int), t=0.0)
```

## Цикл по времени

Три уровня: интервалы истории (смена граничных условий) → шаги $dt$
расписания (`TimeSchedule.substeps`) → подшаги $h$ локального дробления
внутри `_advance` (DEBT-015). Записи истории — только на концах
интервалов (DEBT-013).

```python
def run(self, initial_state: SimulationState) -> SimulationHistory:
    history = SimulationHistory()
    balance = EnergyBalanceAccumulator(self._grid)    # DEBT-013: всегда
    mass = (MassBalanceAccumulator()                   # DEBT-039
            if self._hydro.component_inventories(initial_state) is not None
            else None)                                 # None — двойник без запаса
    state = initial_state
    history.append(t=state.t, state=state,
                   hydro=self._zero_hydro(state),
                   well=self._zero_well_data(state),
                   mass_balance=self._mass_snapshot(mass, state))

    # ── Внешний цикл: по интервалам истории ──
    for k, interval in enumerate(self._schedule.intervals):
        n_sub, dt = self._schedule.substeps(k)

        # ── Внутренний цикл: шаги dt расписания ──
        for step in range(n_sub):
            # Шаг dt; не сошедшийся подшаг дробится внутри _advance
            state, hydro_result = self._advance(
                state, dt, interval.bc, balance, mass)

            # 4. Запись на конце интервала истории (DEBT-013)
            if step == n_sub - 1:
                history.append(t=state.t, state=state,
                               hydro=hydro_result, well=WellData(...),
                               balance=balance.snapshot(),
                               mass_balance=self._mass_snapshot(mass, state))

    return history
```

### Шаг `_advance` — локальное дробление (DEBT-015)

```python
def _advance(self, state, dt, bc, balance, mass
             ) -> tuple[SimulationState, HydroResult]:
    n_units = 2 ** self._max_retries  # dt в единицах наименьшего подшага
    done = 0                          # пройдено единиц
    size = n_units                    # текущий подшаг, единиц; степень двойки
    while done < n_units:
        h = dt / (n_units // size)    # деление на степень двойки — точно

        # 1. Гидродинамика; отказ сходимости — подшаг пополам, из того же state
        try:
            hydro_result = self._hydro.solve(state, h, bc)
        except HydroConvergenceError as exc:
            if size == 1:             # исчерпан наименьший подшаг dt/2**max_retries
                raise RuntimeError(self._failure_message(state, dt, exc)) from exc
            size //= 2
            continue

        # Баланс массы — только принятый подшаг (DEBT-039)
        if mass is not None:
            mass.add_step(hydro_result)

        # 2. Энергия на замороженных p, Sg, Rs подшага; коэффициенты СЛАУ —
        #    в накопитель баланса энергии (DEBT-013)
        T_new = self._energy.solve(hydro_result, state, h, bc, collect=balance)

        # 2a. T ≤ 0 или не конечная → RuntimeError, не дробится (DEBT-047)
        self._check_temperature(T_new, h, hydro_result.state.t)

        # 3. Новое состояние: T из энергии, остальное из гидро
        state = SimulationState(p=hydro_result.state.p, Sg=hydro_result.state.Sg,
                                Rs=hydro_result.state.Rs, T=T_new,
                                regime=hydro_result.state.regime,
                                t=hydro_result.state.t)
        done += size

        # Рост ×2 — только если граница кратна удвоенному подшагу:
        # подшаги всегда dt/2**k и стыкуются без остатка
        if done < n_units and done % (2 * size) == 0:
            size *= 2

    # Были отказы — user_log.info: число подшагов, наименьший, число отказов
    return state, hydro_result
```

Алгоритм G1a, пример и параметры — [[P4-адаптивный-шаг]]; замеры и
почему локальное, а не равномерное — [[локальное дробление шага проходит останов при суточном dt_integration — равномерное падает на одном подшаге из 512]].

Ключевые отличия от плана:
- `run(initial_state)` — initial_state передаётся извне (Factory создаёт)
- `interval.bc` — полный BoundaryConditions (WellControl + p_ext + T_ext + Rs_ext + Sg_ext)
- `energy.solve` получает весь `bc`: $T_{ext}$ берётся из `bc.T_ext`, а не
  из config (может меняться по интервалам)
- отбор записей — только конец интервала (DEBT-013); второго механизма
  (`save_every`) больше нет, частоту вывода задаёт расписание
- дробление шага — в `Simulator`, а не в адаптере (DEBT-015): адаптер
  делает один шаг и при отказе Ньютона бросает `HydroConvergenceError`,
  `_advance` делит пополам только не сошедшийся подшаг. Энергия идёт
  ровно по подшагам гидродинамики (BUG-010). Ловится только
  `HydroConvergenceError` — иной `RuntimeError` из гидродинамики уходит
  наружу без повторов. Отказ на наименьшем подшаге — `RuntimeError` с
  текстом `_failure_message`: глубина дробления, $t$ подшага, число
  двухфазных ячеек, $\max S_g$ и оба рычага (`numerics.max_retries`,
  `time.dt_integration`); причину текст не называет. Начало текста
  цитируют README примеров 03, 05, 06, 07, 10 и тесты. В конце — текст
  отказа гидродинамики последнего подшага (DEBT-054): у прототипа он
  называет, какое условие сходимости не выполнено
- накопитель баланса энергии передаётся в `energy.solve(..., collect=)`
  на **каждом** принятом подшаге и вызывается безусловно: баланс должен
  считаться всегда, при любой структуре истории. См. [[модули-energy-tridiag]]
- накопитель баланса массы `MassBalanceAccumulator` (DEBT-039,
  `gpn_multiphase_solver/mass_balance.py`) создаётся, если решатель отдаёт
  запас начального состояния (`HydroSolver.component_inventories` не `None`);
  `_advance` добавляет в него `HydroResult.int_G_*` только принятого
  подшага. Откатывать нечего: отказ гидродинамики случается до обоих
  накопителей. На каждой записи `_mass_snapshot` берёт у решателя запас
  текущего состояния. У двойников без запаса снимки — `None`
- после каждого подшага энергии `_advance` проверяет температуру
  (`_check_temperature`, DEBT-047): $T \le 0$ или не конечная $T$ →
  `RuntimeError` с $\Delta t$ подшага, временем его конца, ячейкой, $r$ и
  значением. Гидродинамика от $T$ не зависит, поэтому без проверки
  нефизичная $T$ доходила до истории молча. Проверка одна на любой
  `EnergySolver`; отказ не дробится — дробление ловит только
  `HydroConvergenceError` (DEBT-015)

Подробности: [[контейнер-simulation-history]].

## TimeSchedule — runtime-обёртка над TimeConfig

Аналог InjectorGPN: `t_minor_step` + `t_major_step`.

**Данные** хранятся в `TimeConfig` (io/config.py): `dt_integration`, `history: list[HistoryInterval]` (`start_day` удалён, [[DEBT-008]]).
`HistoryInterval` (config.py) содержит `dt`, `control`, `p_wf`, `q_oil`, `min_bhp` (последние два — управление по дебиту нефти, FEAT-020) — сырые данные из JSON.

**Runtime**: Factory (фаза 6) создаёт `TimeSchedule` из `TimeConfig`, преобразуя
каждый `HistoryInterval` → `WellControl` (`_create_well_control`: `control = "pressure"` →
`PressureControl(p_wf)`, `"rate"` → `RateControl(q_oil, min_bhp)`; см. [[модули-bc-граничные-условия]]).

```python
@dataclass
class ScheduleInterval:
    """Один интервал (runtime-уровень)."""
    dt: float                  # длительность, с
    bc: BoundaryConditions     # WellControl + p_ext + T_ext + Rs_ext + Sg_ext

class TimeSchedule:
    def __init__(self, dt_integration: float,
                 intervals: list[ScheduleInterval]):
        ...

    def substeps(self, interval_idx: int) -> tuple[int, float]:
        """n_sub = ceil(dt/dt_int), dt_actual = dt/n_sub."""
        ...

    def total_time(self) -> float: ...

    @property
    def n_intervals(self) -> int: ...
```

Ключевое свойство: `n_sub · dt_actual = dt_hist` **точно**.

Factory создаёт TimeSchedule из TimeConfig, преобразуя `HistoryInterval` (данные: control, p_wf, q_oil, min_bhp) → `ScheduleInterval` (runtime: BoundaryConditions с WellControl).

## SimulationHistory — контейнер результатов (реализовано: state.py)

```python
@dataclass
class SimulationHistory:
    times: list[float]
    states: list[SimulationState]
    hydro_results: list[HydroResult]
    well_data: list[WellData]
    balance: list[dict]              # DEBT-013: члены баланса энергии
    mass_balance: list[dict | None]  # DEBT-039: None — решатель массу не сохраняет

    def append(self, t, state, hydro, well,
               balance=None, mass_balance=None): ...  # balance=None → нулевой снимок

    @property
    def n_saved(self) -> int: ...
```

Simulator создаёт новый SimulationState на каждом шаге (не мутирует старый), поэтому глубокая копия при append не нужна. Подробности: [[контейнер-simulation-history]].

## SimulatorFactory — фабрика (реализовано: factory.py)

```python
class SimulatorFactory:
    @staticmethod
    def from_config(config: SimulationConfig) -> tuple[Simulator, SimulationState]:
        grid = LogRadialGrid(...)
        pvt = _create_pvt(config)         # "standing" → StandingFullPVT
        relperm = _create_relperm(config)  # "corey" → CoreyRP
        hydro = _create_prototype_hydro(config, grid, pvt, relperm)  # PrototypeHydroAdapter; до FEAT-014 — AnalyticalHydroSolver
        energy = TridiagEnergySolver(grid, pvt, config.rock)
        schedule = _create_schedule(config)
        simulator = Simulator(grid, hydro, energy, pvt, schedule, config.output,
                              max_retries=config.numerics.max_retries)
        initial_state = SimulationState(p=p0, Sg=0, Rs=Rs0, T=T0, regime=2, t=0)
        return simulator, initial_state
```

Фабрика — единственное место, где создаются конкретные классы. Остальной код работает с абстракциями.

Помощники `_create_pvt`, `_create_relperm`, `_create_prototype_hydro`, `_create_schedule`, `_create_well_control` — модульные функции в factory.py.

Сейчас поддерживаются: PVT = "standing" / "table", RelPerm = "corey" / "table", HydroSolver = `PrototypeHydroAdapter` (с FEAT-014 — всегда он; заглушка `AnalyticalHydroSolver` удалена из пакета в DEBT-005 и живёт как тестовый двойник `LogProfileHydroStub` в `tests/_doubles.py`).

## Связанные заметки

- [[архитектура библиотеки numerical_solver]]
- [[модули-hydro-newton]] — HydroResult, HydroSolver
- [[модули-energy-tridiag]] — EnergySolver
- [[P4-адаптивный-шаг]] — локальное дробление шага в `_advance` (DEBT-015)
- [[локальное дробление шага проходит останов при суточном dt_integration — равномерное падает на одном подшаге из 512]] — замеры G1a
- [[нефизичная температура доходила до истории молча — проверка T ловит грубые ошибки, остальное проверка ввода]] — `_check_temperature` (DEBT-047)
- [[контейнер-simulation-history]] — поля и наполнение истории
- [[P8-формат-ввода-json]] — структура JSON, секция time
- [[модули-io-вывод]] — сохранение и визуализация SimulationHistory
