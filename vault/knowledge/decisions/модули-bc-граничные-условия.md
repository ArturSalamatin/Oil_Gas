---
name: модули-bc-граничные-условия
description: Модуль граничных условий — ABC WellControl, PressureControl, расширяемость (Rate, PhaseRate), BoundaryConditions
metadata:
  type: project
---

# Граничные условия — модуль bc.py

## Мотивация

Граничные условия на забое скважины — это **стратегия управления**. Сейчас реализуется только задание давления (Дирихле), но в будущем потребуются:
- Задание общего объёмного расхода
- Задание расхода отдельной фазы
- Задание давления с ограничением по расходу (и наоборот)
- Переключение контроля между интервалами истории

Аналог в InjectorGPN: `WellBottomHolePressureControl`, `WellSurfaceRateControl`, `WellReservoirFlowProfileControl` — разные стратегии управления скважиной.

## Состояние после FEAT-020 (2026-09-30)

> [!important] Управление — только данные
> `WellControl` — базовый класс **без абстрактных методов**; `boundary_pressure`
> удалён. `PressureControl(p_wf)` хранит забойное давление, `RateControl(q_oil,
> min_bhp)` — дебит нефти, м³ст/с, и обязательную нижнюю границу $p_{wf}$, Па.
> Управление читают только модули гидродинамики: `PrototypeHydroAdapter`
> (`set_bhp_control` / `set_oil_rate_control`), `compute_fluxes` и тестовый
> двойник (оба — только `PressureControl`).
>
> Фактическое давление на забойной грани после шага возвращает гидродинамика —
> `HydroResult.p_wf` (адаптер берёт `well_rates(new_proto)['bhp_bar']`). Энергия
> (JT-вклад забойной грани) и `Simulator` (`WellData.p_wf`) берут $p_{wf}$ только
> оттуда — единый источник гидродинамических величин. Причина: при управлении по
> дебиту $p_{wf}$ до шага неизвестно, а вариант «`RateControl.boundary_pressure`
> по формуле прототипа» дублировал бы формулу и требовал ОФП, которых у вызывающих
> не было (`relperm=None`). План: [[feat-020 oil-rate-control]].
>
> Постановка: `eq:bc_rate_well`, `eq:bc_rate_pwf` в `numerical_solver/doc/problem_statement.tex`.
> Пример: `examples/15_oil_rate_ramp_up/`.

Ниже — исходный проект модуля (до FEAT-020); код в нём устарел.

## ABC WellControl (исходный проект — устарел)

```python
from abc import ABC, abstractmethod

class WellControl(ABC):
    """Стратегия управления скважиной на одном интервале истории.

    Определяет, как вычисляются потоки через забойную грань (f=0).
    """

    @abstractmethod
    def boundary_pressure(self, state: SimulationState,
                          grid: Grid, pvt: HydroPVT,
                          relperm: RelPermModel) -> float:
        """Давление на забойной грани для вычисления потоков.

        Для PressureControl: просто p_wf.
        Для RateControl: давление, обеспечивающее заданный расход
        (вычисляется итеративно или из формулы).
        """
        ...
```

## Конкретные реализации

### PressureControl (исходный проект; `boundary_pressure` удалён в FEAT-020)

```python
class PressureControl(WellControl):
    """Задано забойное давление p_wf = const на интервале."""

    def __init__(self, p_wf: float):
        self.p_wf = p_wf

    def boundary_pressure(self, state, grid, pvt, relperm) -> float:
        return self.p_wf
```

### RateControl (FEAT-020 — реализован 2026-09-30, `min_bhp` обязателен)

> [!warning] Проект разошёлся с реализацией
> Здесь изначально проектировался `TotalRateControl` — **суммарный** расход,
> $p_{wf}$ ищется итеративно из условия $G^o_0 + G^g_0 = -q_{\text{total}}$.
> Прототип гидродинамики реализовал **другое**: режим `OIL_RATE` —
> управление по дебиту **нефти**, $p_{bhp}$ исключается **алгебраически**
> (`blackoil.py:56-77`), без итераций:
> $$p_{bhp} = p_0 - \frac{q_{\text{цель}}}{T_w \lambda_o}.$$
> В знаменателе одна $\lambda_o$: целевой дебит приравнен к притоку нефти,
> свободный газ досчитывается по тому же $\Delta p_w$ и не управляется.
> Суммарного расхода прототип не умеет — для него нужен новый режим
> с $(\lambda_o + \lambda_g)$, то есть правка кода прототипа.
>
> Поле конфига переименовано `q_total` → `q_oil` (2026-09-22): имя обещало
> суммарный расход, которого нет. Актуальная постановка — [[FEAT-020]].

```python
class RateControl(WellControl):
    """Задан дебит нефти в ст. условиях, м³ст/с. Ограничение min_bhp, Па."""

    def __init__(self, q_oil_std: float, min_bhp: float | None = None):
        self.q_oil = q_oil_std
        self.min_bhp = min_bhp
```

Открытый вопрос FEAT-020: откуда берётся фактическое $p_{wf}$. При
`PressureControl` оно известно до шага, при `RateControl` — результат
гидро-шага. Либо `boundary_pressure` дублирует формулу прототипа (риск
расхождения двух путей, ср. DEBT-021), либо адаптер возвращает фактическое
$p_{wf}$ через `HydroResult` (прототип хранит его в `_last_effective_bhp_bar`).

**Решено 2026-09-29 (пользователь), реализовано 2026-09-30:** второй вариант —
`HydroResult.p_wf`, адаптер заполняет его из публичного `well_rates()`; см.
раздел «Состояние после FEAT-020» выше.

## BoundaryConditions — контейнер

```python
@dataclass
class BoundaryConditions:
    """Полный набор граничных условий на текущем шаге."""
    well: WellControl           # управление на забое
    p_ext: float                # давление на контуре, Па
    T_ext: float                # температура на контуре, К
    Rs_ext: float               # газосодержание притока, м³ст/м³ст
    Sg_ext: float = 0.0         # газонасыщенность на контуре
```

Передаётся в HydroSolver.solve() и EnergySolver.solve() вместо россыпи скаляров.

## Связь с историей

В JSON каждый интервал истории задаёт тип контроля и его параметр:

```json
"time": {
    "dt_integration": 3600,
    "history": [
        {"dt": 86400, "control": "pressure", "p_wf": 15e6},
        {"dt": 172800, "control": "pressure", "p_wf": 12e6},
        {"dt": 604800, "control": "rate", "q_oil": 0.001}
    ]
}
```

С FEAT-020 (2026-09-30): `"control": "pressure"` (поле `p_wf`) или `"rate"` (поля `q_oil`, м³ст/с, и `min_bhp`, Па, оба обязательны); поле `control` опционально (по умолчанию pressure). Поля другого управления в интервале отвергаются валидацией как мёртвые, неизвестное значение `control` — тоже.

В будущем: фабрика создаёт WellControl из JSON:

```python
def create_well_control(interval_config) -> WellControl:
    control_type = interval_config.get("control", "pressure")
    if control_type == "pressure":
        return PressureControl(interval_config["p_wf"])
    elif control_type == "rate":
        return RateControl(interval_config["q_oil"],
                           interval_config.get("min_bhp"))
    ...
```

## Два уровня представления интервала

### Уровень данных (config.py → HistoryInterval)

```python
@dataclass
class HistoryInterval:
    dt: float                        # длительность, с
    control: str = "pressure"        # тип управления
    p_wf: Optional[float] = None     # для control="pressure"
```

Хранит сырые данные из JSON. Не знает про WellControl.

### Уровень runtime (Factory создаёт WellControl)

Factory (фаза 6) преобразует `HistoryInterval` → `WellControl`:
```python
if interval.control == "pressure":
    well_ctrl = PressureControl(interval.p_wf)
```

~~Simulator вызывает `well_ctrl.boundary_pressure(state, grid, pvt, relperm)`.~~
Устарело (FEAT-020): Simulator и энергия к управлению не обращаются, $p_{wf}$
берут из `HydroResult.p_wf`.

## Граничные условия на контуре

Контур питания (r = R_ext): всегда Дирихле (p = p_ext, T = T_ext, Sg = 0, Rs = Rs0). Не меняется между интервалами. Задаётся в initial_conditions JSON, хранится в BoundaryConditions.

В будущем может потребоваться: убывающее пластовое давление p_ext(t), непостоянная температура притока. Для этого BoundaryConditions уже содержит p_ext и T_ext как поля — их можно обновлять между интервалами.

## Связанные заметки

- [[архитектура библиотеки numerical_solver]]
- [[модули-simulator-оркестратор]]
- [[временная-сетка-и-история]]
- [[P8-формат-ввода-json]] — структура JSON, секция time
- [[вопросы-реализации-2]] — п. 9
