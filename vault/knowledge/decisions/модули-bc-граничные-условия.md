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

### RateControl (будущее)

```python
class TotalRateControl(WellControl):
    """Задан суммарный объёмный расход (при ст. условиях)."""

    def __init__(self, q_total_std: float):
        self.q_total = q_total_std

    def boundary_pressure(self, state, grid, pvt, relperm) -> float:
        # Найти p_wf, при котором G_o[0] + G_g[0] = -q_total
        # Итеративно или из линеаризованной формулы
        ...
```

### PhaseRateControl (будущее)

```python
class OilRateControl(WellControl):
    """Задан расход нефтяной фазы (при ст. условиях)."""
    ...
```

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
        {"dt": 604800, "control": "rate", "q_total": 0.001}
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
        return TotalRateControl(interval_config["q_total"])
    ...
```

## TimeSchedule — обновление

```python
@dataclass
class HistoryInterval:
    dt: float                   # длительность, с
    well_control: WellControl   # стратегия управления
```

Вместо `p_wf: float` — `well_control: WellControl`. Simulator вызывает `interval.well_control.boundary_pressure(...)`.

## Граничные условия на контуре

Контур питания (r = R_ext): всегда Дирихле (p = p_ext, T = T_ext, Sg = 0, Rs = Rs0). Не меняется между интервалами. Задаётся в initial_conditions JSON, хранится в BoundaryConditions.

В будущем может потребоваться: убывающее пластовое давление p_ext(t), непостоянная температура притока. Для этого BoundaryConditions уже содержит p_ext и T_ext как поля — их можно обновлять между интервалами.

## Связанные заметки

- [[architecture-numerical-solver]]
- [[модули-simulator-оркестратор]]
- [[временная-сетка-и-история]]
- [[json-config-schema]]
- [[вопросы-реализации-2]] — п. 9
