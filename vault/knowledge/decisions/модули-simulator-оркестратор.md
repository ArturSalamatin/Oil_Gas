---
name: модули-simulator-оркестратор
description: Simulator (Mediator) — цикл по времени, расписание BC, адаптация dt, SimulationState, SimulationHistory
metadata:
  type: project
---

# Simulator — оркестратор (Mediator)

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
                 output_config: OutputConfig | None = None):
        ...

    def run(self, initial_state: SimulationState) -> SimulationHistory:
        """Основной цикл по времени."""
        ...
```

pvt нужен для WellData (rho_o_std, rho_g_std → массовые дебиты).
initial_state передаётся в run() — Factory создаёт его отдельно.

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

Двухуровневый цикл: внешний — по интервалам истории, внутренний — по подшагам интегрирования.

```python
def run(self, initial_state: SimulationState) -> SimulationHistory:
    history = SimulationHistory()
    state = initial_state
    history.append(t=0, state=state, hydro=zero_hydro, well=zero_well)
    global_step = 0

    for k, interval in enumerate(self._schedule.intervals):
        n_sub, dt = self._schedule.substeps(k)

        for step in range(n_sub):
            global_step += 1

            # 1. Гидродинамика (splitting: T заморожена)
            hydro_result = self._hydro.solve(state, dt, interval.bc)

            # 2. Температура (splitting: p, Sg, Rs заморожены)
            T_new = self._energy.solve(hydro_result, state, dt, interval.bc.T_ext)

            # 3. Обновить состояние
            state = SimulationState(
                p=hydro_result.state.p, Sg=hydro_result.state.Sg,
                Rs=hydro_result.state.Rs, T=T_new,
                regime=hydro_result.state.regime, t=hydro_result.state.t)

            # 4. Сохранить на конце интервала истории (DEBT-013)
            if step == n_sub - 1:
                history.append(t=state.t, state=state,
                               hydro=hydro_result, well=WellData(...),
                               balance=balance.snapshot())

    return history
```

Ключевые отличия от плана:
- `run(initial_state)` — initial_state передаётся извне (Factory создаёт)
- `interval.bc` — полный BoundaryConditions (WellControl + p_ext + T_ext + Rs_ext)
- `interval.bc.T_ext` — T_ext берётся из BC, не из config (может меняться)
- отбор записей — только конец интервала (DEBT-013); второго механизма
  (`save_every`) больше нет, частоту вывода задаёт расписание
- накопитель баланса энергии передаётся в `energy.solve(..., collect=)`
  на **каждом** подшаге и вызывается безусловно: баланс должен считаться
  всегда, при любой структуре истории. См. [[модули-energy-tridiag]]

Подробности: [[контейнер-simulation-history]].

## TimeSchedule — runtime-обёртка над TimeConfig

Аналог InjectorGPN: `t_minor_step` + `t_major_step`.

**Данные** хранятся в `TimeConfig` (io/config.py): `dt_integration`, `start_day`, `history: list[HistoryInterval]`.
`HistoryInterval` (config.py) содержит `dt`, `control`, `p_wf` — сырые данные из JSON.

**Runtime**: Factory (фаза 6) создаёт `TimeSchedule` из `TimeConfig`, преобразуя
каждый `HistoryInterval.control + p_wf` → `WellControl` (см. [[модули-bc-граничные-условия]]).

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

    def substeps(self, k: int) -> tuple[int, float]:
        """n_sub = ceil(dt/dt_int), dt_actual = dt/n_sub."""
        ...

    def total_time(self) -> float: ...
    def n_intervals(self) -> int: ...
```

Ключевое свойство: `n_sub · dt_actual = dt_hist` **точно**.

Factory создаёт TimeSchedule из TimeConfig, преобразуя `HistoryInterval` (данные: control, p_wf) → `ScheduleInterval` (runtime: BoundaryConditions с WellControl).

## SimulationHistory — контейнер результатов (реализовано: state.py)

```python
@dataclass
class SimulationHistory:
    times: list[float]
    states: list[SimulationState]
    hydro_results: list[HydroResult]
    well_data: list[WellData]

    def append(self, t, state, hydro, well): ...
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
        hydro = AnalyticalHydroSolver(grid, pvt, relperm)
        energy = TridiagEnergySolver(grid, pvt, config.rock)
        schedule = _create_schedule(config)
        simulator = Simulator(grid, hydro, energy, pvt, schedule, config.output)
        initial_state = SimulationState(p=p0, Sg=0, Rs=Rs0, T=T0, regime=2, t=0)
        return simulator, initial_state
```

Фабрика — единственное место, где создаются конкретные классы. Остальной код работает с абстракциями.

Помощники `_create_pvt`, `_create_relperm`, `_create_schedule`, `_create_well_control` — модульные функции в factory.py.

Сейчас поддерживаются: PVT = "standing", RelPerm = "corey", HydroSolver = AnalyticalHydroSolver. При интеграции прототипа — добавить `from_config_with_prototype()`.

## Связанные заметки

- [[architecture-numerical-solver]]
- [[модули-hydro-newton]] — HydroResult, HydroSolver
- [[модули-energy-tridiag]] — EnergySolver
- [[P8-формат-ввода-json]] — структура JSON, секция time
- [[модули-io-вывод]] — сохранение и визуализация SimulationHistory
