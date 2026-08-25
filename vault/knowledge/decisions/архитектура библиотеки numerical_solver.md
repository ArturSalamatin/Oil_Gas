---
name: architecture-numerical-solver
description: Архитектура Python-библиотеки numerical_solver — модули, абстракции, паттерны, связь с InjectorGPN
metadata:
  type: project
---

# Архитектура библиотеки numerical_solver

## Контекст

Библиотека реализует постановку из `numerical_solver/doc/problem_statement.tex`: двухфазная фильтрация Black Oil с уравнением энергии в ПЗП. Язык: Python 3.10+, numpy/scipy.

Архитектурные решения выработаны с учётом опыта InjectorGPN (C++20, FVM, фабрики, шаблонные специализации). Ключевые заимствования: фабрика для сборки из JSON, splitting гидро→тепло, абстракции для подключаемых модулей.

## Паттерны проектирования

| Паттерн | Роль в библиотеке | Аналог в InjectorGPN |
|---|---|---|
| **Abstract Factory** | `SimulatorFactory` — создаёт конкретные модули из JSON и передаёт в оркестратор | `*Factory::create(json)` |
| **Strategy** | PVT-модель, ОФП-модель, гидро-модуль — подключаемые стратегии | `PointGas` / `FieldGas`, шаблонные специализации |
| **Mediator** | `Simulator` (оркестратор) — координирует гидродинамику, теплоперенос, PVT, ввод/вывод | `SolverManager` |
| **Adapter** | Обёртка вокруг внешнего гидродинамического модуля коллеги | `Wrapper` / `GasWrapper` |
| **Template Method** | Базовый цикл по времени в `Simulator.run()` | `advance(tau)` |

## Полиморфизм в Python

```python
from abc import ABC, abstractmethod

class PVTModel(ABC):
    @abstractmethod
    def Bo(self, p: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def dBo_dp(self, p: np.ndarray) -> np.ndarray: ...
```

- `ABC` + `@abstractmethod` — аналог чисто виртуальных методов C++.
- Конкретный класс обязан реализовать все `@abstractmethod`.
- `isinstance(obj, PVTModel)` — runtime-проверка типа.
- Аннотации типов (`p: np.ndarray`) — документация, не enforcement.
- Альтернатива: Protocol (structural subtyping, PEP 544) — duck typing с проверкой mypy. Для данного проекта ABC предпочтительнее: явный контракт, понятнее начинающему.

## Модульная структура

```
numerical_solver/
├── src/
│   ├── __init__.py
│   ├── pvt/                    # 1. PVT-модуль
│   │   ├── __init__.py
│   │   ├── base.py             # ABC: PVTModel, RPModel (ОФП)
│   │   ├── standing.py         # Конкретная реализация: Standing + Beggs-Robinson
│   │   ├── relperm.py          # Corey, таблица
│   │   └── thermal.py          # mu_JT, L, c_p — тепловые PVT-свойства
│   │
│   ├── grid/                   # 7. Сетка и дискретизация
│   │   ├── __init__.py
│   │   ├── base.py             # ABC: Grid
│   │   └── log_radial.py       # Конкретная: логарифмическая радиальная сетка
│   │
│   ├── hydro/                  # 5. Гидродинамический модуль
│   │   ├── __init__.py
│   │   ├── base.py             # ABC: HydroSolver, HydroResult
│   │   ├── analytical.py       # Аналитическая заглушка (стационарные поля)
│   │   └── adapter.py          # Adapter для внешнего модуля коллеги
│   │
│   ├── energy/                 # Тепловой модуль
│   │   ├── __init__.py
│   │   ├── base.py             # ABC: EnergySolver, EnergyResult
│   │   └── tridiag.py          # Конкретная: прогонка Томаса
│   │
│   ├── fluxes.py               # Вычисление потоков: G, Q, u, m + upstream
│   ├── bc.py                   # Граничные условия: ABC WellControl, PressureControl
│   ├── simulator.py            # 6. Оркестратор (Mediator)
│   ├── factory.py              # 7.1. Фабрика: JSON → Simulator
│   ├── log.py                  # Логирование: user + dev уровни
│   │
│   ├── io/                     # 2, 3. Ввод/вывод
│   │   ├── __init__.py
│   │   ├── config.py           # Чтение JSON, валидация, dataclasses
│   │   └── output.py           # Сохранение результатов, визуализация
│   │
│   └── state.py                # SimulationState, WellData, BoundaryConditions, SimulationHistory
│
├── configs/
│   └── baseline.json           # Эталонный конфиг
│
├── tests/
│   ├── test_pvt.py
│   ├── test_grid.py
│   ├── test_hydro.py
│   ├── test_energy.py
│   └── test_simulator.py
│
├── results/                    # Выходные данные
├── doc/
│   └── problem_statement.tex
└── pyproject.toml
```

## Ключевые абстракции (ABC)

### 1. PVTModel — свойства фаз

Контракт из problem_statement.tex §2.1 (таблица требований к PVT-модели):

| Метод | Аргументы | Возврат | Производные |
|---|---|---|---|
| `Rs_eq(p)` | p | м³ст/м³ст | `dRs_eq_dp(p)` |
| `Bo(p, Rs)` | p, Rs | м³пл/м³ст | `dBo_dp(p, Rs)`, `dBo_dRs(p, Rs)` |
| `Bg(p)` | p | м³пл/м³ст | `dBg_dp(p)` |
| `rho_o(p, Rs)` | p, Rs | кг/м³ | через Bo, Rs |
| `rho_g(p)` | p | кг/м³ | `drho_g_dp(p)` |
| `mu_o(p)` | p | Па·с | `dmu_o_dp(p)` |
| `mu_g(p)` | p | Па·с | `dmu_g_dp(p)` |
| `pb()` | — | Па | — |

Допущение splitting: в гидродинамике PVT зависят только от p (T=T_пл=const).

Тепловые свойства (отдельный контракт `ThermalPVT`):
- `c_p_o(p, T)`, `c_p_g(p, T)` — теплоёмкости
- `mu_JT_o`, `mu_JT_g` — коэффициенты Джоуля-Томсона (скаляры)
- `L_degas` — теплота дегазации (скаляр)

### 2. RPModel — относительные фазовые проницаемости

| Метод | Аргументы | Возврат |
|---|---|---|
| `kro(Sg)` | Sg | безразм. |
| `krg(Sg)` | Sg | безразм. |
| `dkro_dSg(Sg)` | Sg | безразм. |
| `dkrg_dSg(Sg)` | Sg | безразм. |

### 3. Grid — пространственная дискретизация

| Свойство/метод | Описание |
|---|---|
| `N` | число ячеек |
| `r_faces` | массив граней r_{j+1/2}, длина N+1 |
| `r_centers` | массив центров r_j, длина N |
| `volumes` | массив объёмов V_j, длина N |
| `transmissibilities` | массив проводимостей T_{j+1/2}, длина N-1 |
| `trans_left` | проводимость левой граничной грани |
| `trans_right` | проводимость правой граничной грани |

### 4. HydroSolver — гидродинамика

| Метод | Описание |
|---|---|
| `solve(state, dt, bc) → state` | Один шаг: p^n, Sg^n, Rs^n → p^{n+1}, Sg^{n+1}, Rs^{n+1} |
| `velocities(state) → (u_o, u_g)` | Скорости Дарси на гранях |

Контракт минимален — чтобы внешний модуль коллеги мог быть обёрнут через Adapter с минимальными усилиями.

### 5. EnergySolver — теплоперенос

| Метод | Описание |
|---|---|
| `solve(state, dt, bc) → T` | T^n → T^{n+1} на известных p, Sg, Rs, u_o, u_g |

### 6. Simulator — оркестратор

```python
class Simulator:
    def __init__(self, grid, pvt, relperm, hydro, energy, config):
        ...

    def run(self) -> SimulationResult:
        for each time step:
            1. определить p_wf(t) из расписания
            2. hydro.solve(state, dt, bc) → state (p, Sg, Rs)
            3. вычислить u_o, u_g
            4. energy.solve(state, dt, bc) → T
            5. сохранить состояние в историю
```

### 7. SimulatorFactory — фабрика

```python
class SimulatorFactory:
    @staticmethod
    def from_json(path: str) -> Simulator:
        config = load_config(path)
        grid = LogRadialGrid(config.grid)
        pvt = StandingPVT(config.pvt)
        relperm = CoreyRP(config.relperm)
        hydro = NewtonHydroSolver(grid, pvt, relperm, config.numerics)
        energy = TridiagEnergySolver(grid, pvt, config.numerics)
        return Simulator(grid, pvt, relperm, hydro, energy, config)
```

## SimulationState — состояние системы

```python
@dataclass
class SimulationState:
    p: np.ndarray       # давление в центрах ячеек, [N]
    Sg: np.ndarray      # газонасыщенность, [N]
    Rs: np.ndarray      # фактическое газосодержание, [N]
    T: np.ndarray       # температура, [N]
    regime: np.ndarray  # режим ячейки: 1 (двухфазная) или 2 (однофазная), [N]
    t: float            # текущее время
```

## Структура JSON-конфига

Группировка по физическим блокам (аналог InjectorGPN):

```json
{
  "geometry": {
    "r_well": 0.1,
    "R_ext": 500.0,
    "h": 10.0
  },
  "grid": {
    "N": 100,
    "type": "log_radial"
  },
  "rock": {
    "porosity": 0.2,
    "permeability": 1e-13,
    "rho_cp_solid": 2.0e6,
    "lambda_solid": 2.0,
    "lambda_oil": 0.13,
    "lambda_gas": 0.03
  },
  "pvt": {
    "model": "standing",
    "rho_o_std": 850.0,
    "rho_g_std": 1.2,
    "Rs0": 50.0,
    "...": "параметры корреляций"
  },
  "relperm": {
    "model": "corey",
    "S_or": 0.2,
    "S_gc": 0.05,
    "n_o": 2.0,
    "n_g": 2.0,
    "kro_max": 1.0,
    "krg_max": 0.8
  },
  "thermal": {
    "mu_JT_oil": -4e-7,
    "mu_JT_gas": -3e-6,
    "L_degas": 150000.0,
    "c_p_oil": 2000.0,
    "c_p_gas": 1000.0
  },
  "initial_conditions": {
    "p0": 25e6,
    "T0": 353.0
  },
  "boundary_conditions": {
    "schedule": [
      {"t_end": 86400, "p_wf": 15e6},
      {"t_end": 864000, "p_wf": 10e6}
    ]
  },
  "numerics": {
    "dt_init": 100.0,
    "dt_max": 86400.0,
    "newton_tol_abs": 1e-8,
    "newton_tol_rel": 1e-6,
    "newton_max_iter": 20
  }
}
```

## Связь с внешним гидродинамическим модулем

Гидродинамический блок коллеги ещё не передан, его интерфейс неизвестен. Подход:

1. Определить минимальный ABC `HydroSolver` с одним методом `solve(state, dt, bc)`.
2. Реализовать собственный `NewtonHydroSolver` по problem_statement.tex.
3. Когда модуль коллеги поступит — написать `AdapterHydroSolver`, который:
   - принимает внешний объект
   - транслирует вызов `solve()` в API коллеги
   - конвертирует форматы данных (если нужно)

Паттерн Adapter позволяет не менять ни Simulator, ни код коллеги.

## Решения, отличные от InjectorGPN

| Аспект | InjectorGPN (C++) | numerical_solver (Python) |
|---|---|---|
| Полиморфизм | Шаблоны + специализации | ABC + наследование |
| Указатели | `cptr<const T>` (shared_ptr) | Обычные ссылки (GC) |
| Сборка объектов | Шаблонные фабрики | `SimulatorFactory.from_json()` |
| Размерность | 2D (Z×R) | 1D (R) — осесимметричная задача |
| СЛАУ | Eigen SparseLU | numpy/scipy (блочная прогонка вручную) |
| Конфиг | nlohmann::json | json (стандартная библиотека Python) |

## Связанные заметки

- problem_statement.tex — постановка и численная схема
- [[модули-pvt-контракт]] — детальный контракт PVT
- [[модули-hydro-newton]] — детали блочного Ньютона
- [[модули-energy-tridiag]] — детали тепловой прогонки
- [[json-config-schema]] — полная схема JSON
