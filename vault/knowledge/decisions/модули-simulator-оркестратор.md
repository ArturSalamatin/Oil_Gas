---
name: модули-simulator-оркестратор
description: Simulator (Mediator) — цикл по времени, расписание BC, адаптация dt, SimulationState, SimulationHistory
metadata:
  type: project
---

# Simulator — оркестратор (Mediator)

## Класс Simulator

```python
class Simulator:
    """Координирует гидродинамику и теплоперенос.

    Зависит только от абстракций: Grid, HydroSolver, EnergySolver.
    Конкретные реализации передаются через конструктор (Dependency Injection).
    """

    def __init__(self,
                 grid: Grid,
                 hydro: HydroSolver,
                 energy: EnergySolver,
                 schedule: WellSchedule,
                 config: NumericsConfig,
                 output_config: OutputConfig):
        self.grid = grid
        self.hydro = hydro
        self.energy = energy
        self.schedule = schedule
        self.config = config
        self.output_config = output_config

    def run(self) -> SimulationHistory:
        """Основной цикл по времени. Template Method."""
        ...
```

## SimulationState — состояние системы

```python
@dataclass
class SimulationState:
    p: np.ndarray        # давление, [N], Па
    Sg: np.ndarray       # газонасыщенность, [N]
    Rs: np.ndarray       # фактическое газосодержание, [N], м³ст/м³ст
    T: np.ndarray        # температура, [N], К
    regime: np.ndarray   # режим ячейки: 1 или 2, [N], int
    t: float             # текущее время, с

    def copy(self) -> 'SimulationState':
        """Глубокая копия (numpy-массивы копируются)."""
        return SimulationState(
            p=self.p.copy(), Sg=self.Sg.copy(), Rs=self.Rs.copy(),
            T=self.T.copy(), regime=self.regime.copy(), t=self.t)
```

Начальное состояние (eq. 3 problem_statement.tex):
```python
def initial_state(self) -> SimulationState:
    N = self.grid.N
    return SimulationState(
        p=np.full(N, self.config.p0),
        Sg=np.zeros(N),
        Rs=np.full(N, self.config.Rs0),
        T=np.full(N, self.config.T0),
        regime=np.full(N, 2, dtype=int),  # все ячейки однофазные
        t=0.0)
```

## Цикл по времени

Двухуровневый цикл: внешний — по интервалам истории, внутренний — по подшагам интегрирования.

```python
def run(self) -> SimulationHistory:
    state = self.initial_state()
    history = SimulationHistory()
    history.append(state, well_data=None)  # начальное состояние

    t = 0.0

    # Внешний цикл: по интервалам истории
    for k, interval in enumerate(self.schedule.history):
        p_wf = interval.p_wf
        n_sub, dt = self.schedule.substeps(k)

        # Внутренний цикл: подшаги интегрирования
        for step in range(n_sub):
            # 1. Гидродинамика → p, Sg, Rs + потоки G, Q
            hydro_result = self.hydro.solve(
                state, dt, p_wf, self.config.p0, self.config.Rs0)

            # 2. Температура (на известных p, Sg, Rs, Q, G)
            T_new = self.energy.solve(
                hydro_result, state, dt, self.config.T0)

            # 3. Обновить состояние
            t += dt
            state = SimulationState(
                p=hydro_result.state.p,
                Sg=hydro_result.state.Sg,
                Rs=hydro_result.state.Rs,
                T=T_new,
                regime=hydro_result.state.regime,
                t=t)

        # Сохранить результат на конце интервала истории
        well_data = WellData(
            q_o_std=-hydro_result.G_o[0],   # G_o[0] < 0 при добыче, дебит > 0
            q_g_std=-hydro_result.G_g[0])
        history.append(state, well_data)

    return history
```

Результаты сохраняются **только на концах интервалов истории** — это то, что пользователь хочет видеть. Промежуточные подшаги не сохраняются (экономия памяти).

Число записей в history = len(schedule.history) + 1 (начальное состояние).

## TimeSchedule — история + шаг интегрирования

Аналог InjectorGPN: `t_minor_step` + `t_major_step`.

```python
@dataclass
class HistoryInterval:
    """Один интервал истории."""
    dt: float        # длительность интервала (шаг истории), с
    p_wf: float      # забойное давление на интервале, Па

class TimeSchedule:
    """Расписание: разбивка по интервалам истории + шаг интегрирования.

    Аналог InjectorGPN: t_major_step + t_minor_step.
    """

    def __init__(self, dt_integration: float, history: list[HistoryInterval]):
        self.dt_integration = dt_integration
        self.history = history

    def substeps(self, interval_idx: int) -> tuple[int, float]:
        """Число подшагов и фактический шаг для интервала k.

        n_sub = ceil(dt_hist / dt_integration)
        dt_actual = dt_hist / n_sub

        Гарантии:
        - dt_actual ≤ dt_integration
        - n_sub · dt_actual = dt_hist ровно
        """
        dt_hist = self.history[interval_idx].dt
        n_sub = int(np.ceil(dt_hist / self.dt_integration))
        n_sub = max(n_sub, 1)
        dt_actual = dt_hist / n_sub
        return n_sub, dt_actual

    def total_time(self) -> float:
        return sum(iv.dt for iv in self.history)
```

Ключевое свойство: `n_sub · dt_actual = dt_hist` **точно**, без накопления ошибки округления. Каждый интервал истории покрывается целым числом одинаковых подшагов.

## SimulationHistory — накопление результатов

```python
class SimulationHistory:
    def __init__(self):
        self.times: list[float] = []
        self.states: list[SimulationState] = []

    def append(self, state: SimulationState):
        self.times.append(state.t)
        self.states.append(state.copy())  # глубокая копия!

    def to_arrays(self) -> dict:
        """Упаковка в numpy-массивы для сохранения/визуализации."""
        n_steps = len(self.times)
        N = self.states[0].p.shape[0]
        return {
            'times': np.array(self.times),             # [n_steps]
            'p': np.array([s.p for s in self.states]),  # [n_steps, N]
            'T': np.array([s.T for s in self.states]),
            'Sg': np.array([s.Sg for s in self.states]),
            'Rs': np.array([s.Rs for s in self.states]),
        }
```

Глубокая копия при append — обязательна! Иначе все записи будут ссылаться на последнее состояние (мутабельные numpy-массивы).

## SimulatorFactory — фабрика

```python
class SimulatorFactory:
    @staticmethod
    def from_json(path: str) -> Simulator:
        config = load_config(path)

        grid = LogRadialGrid(
            r_well=config.geometry.r_well,
            R_ext=config.geometry.R_ext,
            h=config.geometry.h,
            N=config.grid.N,
            k=config.rock.permeability)

        pvt = create_pvt(config.pvt, config.thermal)  # HydroPVT + ThermalPVT
        relperm = create_relperm(config.relperm)       # RelPermModel

        hydro = NewtonHydroSolver(grid, pvt, relperm, config.numerics)
        energy = TridiagEnergySolver(grid, pvt, config.rock, config.thermal)

        schedule = WellSchedule(config.boundary_conditions.schedule)

        return Simulator(grid, hydro, energy, schedule,
                         config.numerics, config.output)
```

Фабрика — единственное место, где создаются конкретные классы. Остальной код работает с абстракциями.

Функции `create_pvt`, `create_relperm` — внутри фабрики, выбирают конкретный класс по `config.pvt.model`:
```python
def create_pvt(pvt_config, thermal_config):
    if pvt_config.model == "standing":
        return StandingPVT(pvt_config, thermal_config)
    elif pvt_config.model == "table":
        return TablePVT(pvt_config, thermal_config)
    elif pvt_config.model == "custom":
        module = importlib.import_module(pvt_config.module_path)
        cls = getattr(module, pvt_config.class_name)
        return cls(pvt_config, thermal_config)
    else:
        raise ValueError(f"Unknown PVT model: {pvt_config.model}")
```

## Связанные заметки

- [[architecture-numerical-solver]]
- [[модули-hydro-newton]] — HydroResult, HydroSolver
- [[модули-energy-tridiag]] — EnergySolver
- [[json-config-schema]] — WellSchedule из boundary_conditions
- [[модули-io-вывод]] — сохранение и визуализация SimulationHistory
