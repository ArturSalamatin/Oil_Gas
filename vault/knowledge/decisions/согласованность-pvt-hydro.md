---
name: согласованность-pvt-hydro
description: Согласованность PVT/ОФП — один объект на всю симуляцию, передаётся по ссылке во все модули через полиморфизм
metadata:
  type: project
---

# Согласованность PVT/ОФП и модулей

## Принцип

Гидро-модуль и энергетический модуль зависят от **абстрактных классов** (HydroPVT/FullPVT, RelPermModel). Конкретные объекты принимают через конструктор по ссылке. Полиморфизм.

Ни один модуль не знает, какая конкретная реализация PVT или ОФП используется. Ни один модуль не создаёт PVT/ОФП самостоятельно.

## Гарантия согласованности

Factory создаёт **один** конкретный объект FullPVT и **один** объект RelPermModel. Оба передаются **по ссылке** во все модули, которые от них зависят:

```python
# Factory:
pvt = create_pvt(config)        # один объект FullPVT
relperm = create_relperm(config) # один объект RelPermModel
grid = LogRadialGrid(...)        # один объект Grid

# Все модули получают те же объекты:
hydro = PrototypeHydroAdapter(model, grid, pvt, relperm, ...)
energy = TridiagEnergySolver(grid, pvt, rock)
```

`hydro` и `energy` держат ссылки на **один и тот же** pvt, relperm, grid. Рассогласованность исключена по построению.

## Зависимости модулей

```
HydroSolver (ABC)
    зависит от: Grid (ABC), HydroPVT (ABC), RelPermModel (ABC)
    НЕ зависит от: конкретных StandingFullPVT, TableFullPVT, CoreyRP, ...

EnergySolver (ABC)
    зависит от: Grid (ABC), FullPVT (ABC), RockConfig
    НЕ зависит от: конкретных реализаций

Simulator
    зависит от: HydroSolver (ABC), EnergySolver (ABC), TimeSchedule, ...

SimulatorFactory
    единственное место, где создаются конкретные объекты
    передаёт их по ссылке в модули
```

## Следствие для прототипа (пока не модифицирован)

Прототип (RadialBlackOilModel) принимает **свой** BlackOilPVT (duck typing, бар/сП), не наш ABC. Прототип не знает про наши абстракции.

Согласованность обеспечивается **через общий источник данных**:

```python
# Factory:
proto_pvt = BlackOilPVT(oil_rows, gas_rows)   # один источник (одни таблицы)

# Прототипу — его родной объект:
model = RadialBlackOilModel(grid_proto, rock, proto_pvt, proto_rp, ...)

# Нашим модулям — обёртка того же объекта:
pvt_adapter = PrototypePVTAdapter(proto_pvt, rho_o_std, rho_g_std)
full_pvt = TableFullPVT(pvt_adapter, c_p_oil, ...)

# Adapter и EnergySolver получают full_pvt:
hydro = PrototypeHydroAdapter(model, grid, full_pvt, ...)
energy = TridiagEnergySolver(grid, full_pvt, rock)
```

`proto_pvt` — один объект BlackOilPVT. Прототип вызывает `proto_pvt.bo(p_bar, rs)`. Adapter через full_pvt → pvt_adapter вызывает тот же `proto_pvt.bo(p_bar, rs)` (с конвертацией Па→бар). Одна таблица, одна интерполяция, одни значения.

При модификации прототипа (будущая задача) — прототип примет наш ABC напрямую, обёртка станет не нужна.

## Следствие для ОФП

Аналогично:

```python
proto_rp = TabulatedRelPerm(sg, kro, krg)   # один источник

# Прототипу:
model = RadialBlackOilModel(..., relperm=proto_rp, ...)

# Нашим модулям:
rp_adapter = PrototypeRPAdapter(proto_rp)
```

Один объект TabulatedRelPerm, два интерфейса.

## Нет «запрещённых комбинаций»

Ранее предполагалось, что Factory проверяет совместимость (table vs standing). Это не нужно — архитектура исключает рассогласованность. Пользователь выбирает PVT-стратегию один раз, Factory создаёт один объект, все модули его разделяют.

Если пользователь выбрал `pvt.model = "standing"` — StandingFullPVT создаётся и передаётся в гидро и энергию. Если `pvt.model = "table"` — TableFullPVT. Гидро-модуль не знает и не проверяет тип — работает через ABC.

## Как фабрика получает объекты прототипа (DEBT-006)

`SimulatorFactory` выбирает ветку по классу, а не по приватным полям обёрток:

| Объект наших модулей | Прототипу (`RadialBlackOilModel`) |
|---|---|
| `TableFullPVT` | `pvt.hydro.proto_pvt` — тот же `BlackOilPVT` |
| любой другой `HydroPVT` (`StandingFullPVT`) | `HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)` |
| `PrototypeRPAdapter` | `relperm.proto_rp` — тот же `TabulatedRelPerm` |
| любая другая `RelPermModel` (`CoreyRP`) | `TabulatedRelPerm` на 101 узле `np.linspace(0, 1, 101)` |

Свойства `hydro`, `proto_pvt`, `proto_rp` — только для чтения. `PrototypeHydroAdapter`, `TridiagEnergySolver` и `Simulator` держат **один** объект `FullPVT`. Объект ОФП из фабрики нужен только для сборки ОФП прототипа: наши модули в расчёте его не держат (пересчёт потоков идёт от покомпонентных потоков прототипа).

До DEBT-006 ветку выбирали `hasattr(pvt, '_hydro')` и `hasattr(relperm, '_rp')`. Переименование приватного поля молча уводило таблицу ОФП в табуляцию на 101 узел: порог активации газа `sg_activation_cap` (BUG-018) у таблиц примеров сдвигался с 0.6 на 0.79, история менялась в последних битах — числовые тесты этого не видят. Скрипты графиков (`examples/pvt_plot.py`, `examples/relperm_plot.py`) тоже переведены на свойства.

## Связанные заметки

- [[P5-pvt-архитектура]] — HydroPVT → FullPVT, стратегии
- [[P8-формат-ввода-json]] — Factory, JSON
- [[архитектура библиотеки numerical_solver]] — паттерны (Strategy, DI)
- [[модули-grid-сетка]] — единая Grid, immutable
