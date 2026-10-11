---
name: P5-pvt-архитектура
description: Архитектура PVT — двухуровневый ABC (HydroPVT → FullPVT), адаптер табличного PVT прототипа, strategy pattern
metadata:
  type: project
---

# P5. Архитектура PVT-модуля

## Принципы

1. **Один PVT** для гидродинамики и температуры — никакой рассогласованности.
2. **Двухуровневый интерфейс**: узкий (только для гидро) и расширенный (+ тепловые свойства).
3. **Strategy pattern**: PVT заменяем без переписывания остального кода.
4. **Адаптер** для табличного PVT прототипа Сергея.

## Двухуровневый ABC

### Уровень 1: HydroPVT — интерфейс для гидродинамики

Минимальный набор, достаточный для гидро-модуля. Этот интерфейс реализует или оборачивает PVT прототипа.

```python
from abc import ABC, abstractmethod
import numpy as np

class HydroPVT(ABC):
    """Физические свойства фаз (без производных). Единицы: SI.

    Производные — в DifferentiableHydroPVT (отдельный ABC).
    """

    @property
    @abstractmethod
    def rho_o_std(self) -> float: ...
    @property
    @abstractmethod
    def rho_g_std(self) -> float: ...

    @abstractmethod
    def Rs_eq(self, p: np.ndarray) -> np.ndarray: ...
    @abstractmethod
    def Bo(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray: ...
    @abstractmethod
    def Bg(self, p: np.ndarray) -> np.ndarray: ...
    @abstractmethod
    def mu_o(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray: ...
    @abstractmethod
    def mu_g(self, p: np.ndarray) -> np.ndarray: ...
    @abstractmethod
    def pb(self, Rs: np.ndarray) -> np.ndarray: ...

    # --- Вычисляемые (не абстрактные) ---
    def rho_o(self, p, Rs):
        return (self.rho_o_std + Rs * self.rho_g_std) / self.Bo(p, Rs)

    def rho_g(self, p):
        return self.rho_g_std / self.Bg(p)
```

### Уровень 2: FullPVT — расширение для температурной задачи

Наследуется от HydroPVT. Добавляет тепловые свойства.

```python
class FullPVT(HydroPVT):
    """Полные PVT-свойства: гидро + тепловые.

    Тепловые методы принимают (p, T) для расширяемости.
    Скалярная реализация может игнорировать аргументы.
    """

    @abstractmethod
    def c_p_oil(self, p: np.ndarray, T: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def c_p_gas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def mu_JT_oil(self, p: np.ndarray, T: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def mu_JT_gas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def L_degas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray: ...
```

### Иерархия

Физика и метод решения **разделены**:

```
HydroPVT (ABC)                    ← физические свойства: Bo, Bg, mu, Rs_eq, pb, rho
    │
    ├── FullPVT (ABC)             ← + тепловые: c_p, mu_JT, L
    │       ├── StandingFullPVT   ← корреляции Standing + скалярные тепловые
    │       └── TableFullPVT      ← табличные гидро + скалярные тепловые
    │
    ├── PrototypePVTAdapter       ← обёртка BlackOilPVT (бар→Па), только физика
    │
    └── DifferentiableHydroPVT (ABC) ← + производные: dBo_dp, dBo_dRs, ...
                                       (для Newton-солвера, не реализован сейчас)

RelPermModel (ABC)                ← физика: kro, krg
    │
    ├── PrototypeRPAdapter        ← обёртка TabulatedRelPerm
    │
    └── DifferentiableRelPerm (ABC) ← + производные: dkro_dSg, dkrg_dSg
            └── CoreyRP           ← аналитические kro, krg + аналитические производные
```

- HydroPVT / FullPVT / RelPermModel — **что описывает вещество** (нужно всем модулям)
- DifferentiableHydroPVT / DifferentiableRelPerm — **как решается СЛАУ** (нужно только Newton-солверу)
- Модули EnergySolver, Adapter, fluxes зависят от HydroPVT/FullPVT — **без** производных

## Adapter для PVT прототипа

### Интерфейс прототипа (BlackOilPVT)

| Метод | Аргументы | Единицы |
|---|---|---|
| `pvt.bo(p, rs)` | p в **бар**, rs | Bo безразм. |
| `pvt.mu_o(p, rs)` | p в **бар**, rs | μ_o в **сП** |
| `pvt.bg(p)` | p в **бар** | Bg безразм. |
| `pvt.mu_g(p)` | p в **бар** | μ_g в **сП** |
| `pvt.rs_sat(p)` | p в **бар** | Rs м³ст/м³ст |
| `pvt.pb` | свойство | массив бар |
| `pvt.max_rs` | свойство | скаляр |

### PrototypePVTAdapter (обёртка → HydroPVT)

```python
from radial_blackoil.pvt import BlackOilPVT
from radial_blackoil.units import BAR_TO_PA, CP_TO_PA_S

class PrototypePVTAdapter(HydroPVT):
    """Адаптер табличного BlackOilPVT → наш HydroPVT.

    Конвертирует:
    - p: Па → бар на входе
    - μ: сП → Па·с на выходе
    - Bo, Bg, Rs: без конвертации (безразмерные / м³ст/м³ст)

    Производные: конечные разности (табличный PVT не предоставляет аналитических).
    """

    def __init__(self, proto_pvt: BlackOilPVT,
                 rho_o_std: float, rho_g_std: float):
        self._pvt = proto_pvt
        self._rho_o_std = float(rho_o_std)
        self._rho_g_std = float(rho_g_std)

    @property
    def rho_o_std(self): return self._rho_o_std

    @property
    def rho_g_std(self): return self._rho_g_std

    def _to_bar(self, p_pa):
        return np.asarray(p_pa, float) / BAR_TO_PA

    # --- Газосодержание ---
    def Rs_eq(self, p):
        return self._pvt.rs_sat(self._to_bar(p))

    # --- Bo ---
    def Bo(self, p, Rs):
        return self._pvt.bo(self._to_bar(p), Rs)

    # --- Bg ---
    def Bg(self, p):
        return self._pvt.bg(self._to_bar(p))

    # --- Вязкости (сП → Па·с) ---
    def mu_o(self, p, Rs):
        return self._pvt.mu_o(self._to_bar(p), Rs) * CP_TO_PA_S

    def mu_g(self, p):
        return self._pvt.mu_g(self._to_bar(p)) * CP_TO_PA_S

    # --- Давление насыщения ---
    def pb(self, Rs):
        return self._pvt.pb_of_rs(Rs) * BAR_TO_PA
```

Производные (dBo_dp, dBg_dp, dmu_o_dp, dmu_g_dp) — в будущем DifferentiablePrototypePVTAdapter (конечные разности с конвертацией единиц). Сейчас не реализованы.

## FullPVT: расширение для температуры

### Вариант 1: TableFullPVT (табличные гидро + скалярные тепловые)

```python
class TableFullPVT(FullPVT):
    """Табличные гидро-свойства (через PrototypePVTAdapter) + скалярные тепловые."""

    def __init__(self, proto_pvt_adapter: PrototypePVTAdapter,
                 c_p_oil: float, c_p_gas: float,
                 mu_JT_oil: float, mu_JT_gas: float,
                 L_degas: float):
        self._hydro = proto_pvt_adapter
        self._cp_o = c_p_oil
        self._cp_g = c_p_gas
        self._mu_JT_o = mu_JT_oil
        self._mu_JT_g = mu_JT_gas
        self._L = L_degas

    # --- Делегирование гидро-методов ---
    @property
    def rho_o_std(self): return self._hydro.rho_o_std
    @property
    def rho_g_std(self): return self._hydro.rho_g_std
    def Rs_eq(self, p): return self._hydro.Rs_eq(p)
    def Bo(self, p, Rs): return self._hydro.Bo(p, Rs)
    def Bg(self, p): return self._hydro.Bg(p)
    def mu_o(self, p, Rs): return self._hydro.mu_o(p, Rs)
    def mu_g(self, p): return self._hydro.mu_g(p)
    def pb(self, Rs): return self._hydro.pb(Rs)

    # --- Тепловые свойства (скалярные) ---
    def c_p_oil(self, p, T): return np.full_like(p, self._cp_o)
    def c_p_gas(self, p, T): return np.full_like(p, self._cp_g)
    def mu_JT_oil(self, p, T): return np.full_like(p, self._mu_JT_o)
    def mu_JT_gas(self, p, T): return np.full_like(p, self._mu_JT_g)
    def L_degas(self, p, T): return np.full_like(p, self._L)
```

### Вариант 2: StandingFullPVT (корреляции)

Самостоятельная реализация Bo, Bg, μ_o, μ_g через Standing/Beggs-Robinson + скалярные тепловые. Не использует PVT прототипа. Для случая, когда прототип не подключён (AnalyticalHydroSolver — удалён в DEBT-005, ныне тестовый двойник `LogProfileHydroStub`).

## Как подключается

### Гидро-модуль видит только HydroPVT

Прототип (RadialBlackOilModel) принимает PVT через конструктор. Его интерфейс: `bo(p_bar, rs)`, `mu_o(p_bar, rs)`, ... Это **не** наш ABC — это duck typing прототипа.

При интеграции: прототип **продолжает** использовать свой BlackOilPVT (в барах). PrototypeHydroAdapter (из P1) использует `self._model.pvt` для пересчёта G→Q.

Но наш ABC HydroPVT — для **нашего** кода (EnergySolver, fluxes.py, тесты). Не для прототипа.

### EnergySolver видит FullPVT

```python
class EnergySolver:
    def __init__(self, grid, pvt: FullPVT, rock_config):
        self._pvt = pvt   # FullPVT: и гидро, и тепловые свойства
```

EnergySolver вызывает:
- `pvt.rho_o(p, Rs)`, `pvt.rho_g(p)` — для конвективных коэффициентов
- `pvt.c_p_oil(p, T)`, `pvt.c_p_gas(p, T)` — для теплоёмкостей
- `pvt.mu_JT_oil(p, T)`, `pvt.mu_JT_gas(p, T)` — для JT
- `pvt.L_degas(p, T)` — для теплоты дегазации

Все в SI (Па, К). FullPVT обеспечивает.

### Simulator → Factory

```python
# Factory создаёт единый FullPVT:
proto_pvt_adapter = PrototypePVTAdapter(model_input.pvt, rho_o_std, rho_g_std)
full_pvt = TableFullPVT(proto_pvt_adapter, c_p_oil, c_p_gas, mu_JT_oil, mu_JT_gas, L_degas)

# Гидро: прототип использует свой BlackOilPVT (внутри model)
hydro = PrototypeHydroAdapter(model, grid, rho_o_std, rho_g_std)

# Энергия: использует full_pvt (единый для всех модулей)
energy = TridiagEnergySolver(grid, full_pvt, rock_config)
```

## Согласованность

HydroPVT-часть FullPVT — это PrototypePVTAdapter, который вызывает **тот же** BlackOilPVT, что и прототип. Bo, Bg, μ_o, μ_g — из одних таблиц. Рассогласованности нет.

Единственное различие: прототип работает в барах/сП (внутри), адаптер конвертирует в Па/Па·с. Но значения одинаковы (одна таблица, одна интерполяция).

## Подключаемость PVT в прототипе (п. 4)

PVT в прототипе **не hard-coded**. Передаётся через конструктор RadialBlackOilModel:

```python
model = RadialBlackOilModel(grid, rock, pvt, relperm, ...)
```

Сейчас единственная реализация — BlackOilPVT (табличный PVTO). Но можно подставить любой объект с интерфейсом:
- `bo(p_bar, rs)`, `mu_o(p_bar, rs)`, `bg(p_bar)`, `mu_g(p_bar)`
- `rs_sat(p_bar)`, `pb` (массив), `max_rs` (скаляр)

Это duck typing — формального ABC в прототипе нет, но интерфейс де-факто стабилен. Если потребуется подставить другой PVT в прототип — достаточно реализовать тот же набор методов.

## Подключаемые стратегии PVT

ABC `HydroPVT` / `FullPVT` определяют **интерфейс**. Конкретная стратегия выбирается пользователем при инициализации расчёта.

### Реализованные стратегии

| Стратегия | Класс | Гидро-свойства | Тепловые свойства | Производные |
|---|---|---|---|---|
| Корреляции | `StandingFullPVT` | Standing, Beggs-Robinson, LGE | скалярные | аналитические |
| Табличные | `TableFullPVT` | ECLIPSE PVTO через `PrototypePVTAdapter` | скалярные | конечные разности |
| Будущие (EOS, ...) | `EosFullPVT` | уравнение состояния | из EOS | аналитические или FD |

### Выбор стратегии в JSON

```json
"pvt": {
    "model": "standing",
    "rho_o_std": 850.0,
    "rho_g_std": 1.2,
    "...": "параметры корреляций"
}
```

или

```json
"pvt": {
    "model": "table",
    "oil_pvt_file": "oil_pvt.csv",
    "gas_pvt_file": "gas_pvt.csv",
    "rho_o_std": 850.0,
    "rho_g_std": 1.2
}
```

### Создание в Factory

```python
def create_pvt(config) -> FullPVT:
    if config.pvt.model == "standing":
        return StandingFullPVT(
            rho_o_std=config.pvt.rho_o_std,
            rho_g_std=config.pvt.rho_g_std,
            c_p_oil=config.thermal.c_p_oil,
            mu_JT_oil=config.thermal.mu_JT_oil,
            # ... остальные параметры
        )
    elif config.pvt.model == "table":
        proto_pvt = BlackOilPVT(oil_rows, gas_rows)  # из CSV/XLSX
        adapter = PrototypePVTAdapter(proto_pvt,
                                      config.pvt.rho_o_std,
                                      config.pvt.rho_g_std)
        return TableFullPVT(adapter,
                            c_p_oil=config.thermal.c_p_oil,
                            mu_JT_oil=config.thermal.mu_JT_oil,
                            # ... тепловые из config
        )
    else:
        raise ValueError(f"Unknown PVT model: {config.pvt.model}")
```

### Все модули работают с абстракцией

```python
class Simulator:
    def __init__(self, ..., pvt: FullPVT, ...):
        # pvt может быть StandingFullPVT, TableFullPVT, или любой другой

class EnergySolver:
    def __init__(self, grid, pvt: FullPVT, rock):
        # вызывает pvt.rho_o(), pvt.c_p_oil(), pvt.mu_JT_oil() — не зная реализации

class PrototypeHydroAdapter(HydroSolver):
    def __init__(self, model, grid, pvt: FullPVT):
        # использует pvt для пересчёта G → Q (Bo, Bg из того же PVT)
```

HydroSolver, EnergySolver, fluxes.py — никогда не импортируют StandingFullPVT или TableFullPVT напрямую. Только ABC FullPVT. Замена стратегии — без переписывания кода.

## Файловая структура

```
numerical_solver/gpn_multiphase_solver/pvt/
├── __init__.py
├── base.py             # ABC: HydroPVT, FullPVT
├── standing.py         # StandingFullPVT (корреляции)
├── prototype_adapter.py # PrototypePVTAdapter (обёртка BlackOilPVT → HydroPVT)
├── table_full.py       # TableFullPVT (табличные гидро + скалярные тепловые)
├── consistency.py      # проверка согласованности PVT: c_ot, c_g, c_o (BUG-019)
└── relperm.py          # RelPermModel, CoreyRP, PrototypeRPAdapter
```

## Связанные заметки

- [[модули-pvt-контракт]] — предыдущая версия ABC (обновить)
- [[P1-адаптер-единицы]] — PrototypeHydroAdapter использует model.pvt
- [[hydro-prototype-анализ]] — интерфейс BlackOilPVT
- [[архитектура библиотеки numerical_solver]] — общая архитектура
