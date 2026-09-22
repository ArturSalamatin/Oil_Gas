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

## ABC WellControl

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

### PressureControl (реализуется сейчас)

```python
class PressureControl(WellControl):
    """Задано забойное давление p_wf = const на интервале."""

    def __init__(self, p_wf: float):
        self.p_wf = p_wf

    def boundary_pressure(self, state, grid, pvt, relperm) -> float:
        return self.p_wf
```

### RateControl (будущее, FEAT-020)

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

Сейчас: `"control": "pressure"` — единственный вариант, поле `control` опционально (по умолчанию pressure).

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

Simulator вызывает `well_ctrl.boundary_pressure(state, grid, pvt, relperm)`.

## Граничные условия на контуре

Контур питания (r = R_ext): всегда Дирихле (p = p_ext, T = T_ext, Sg = 0, Rs = Rs0). Не меняется между интервалами. Задаётся в initial_conditions JSON, хранится в BoundaryConditions.

В будущем может потребоваться: убывающее пластовое давление p_ext(t), непостоянная температура притока. Для этого BoundaryConditions уже содержит p_ext и T_ext как поля — их можно обновлять между интервалами.

## Связанные заметки

- [[architecture-numerical-solver]]
- [[модули-simulator-оркестратор]]
- [[временная-сетка-и-история]]
- [[P8-формат-ввода-json]] — структура JSON, секция time
- [[вопросы-реализации-2]] — п. 9
