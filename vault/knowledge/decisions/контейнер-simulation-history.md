---
name: контейнер-simulation-history
description: SimulationHistory — контейнер результатов расчёта, контракт Simulator→I/O, save_every, состав полей
metadata:
  type: project
---

# SimulationHistory — контейнер результатов

## Мотивация

Simulator на каждом временном шаге вычисляет SimulationState, HydroResult, WellData. Нужен единый контейнер для передачи результатов в I/O-модуль (запись CSV/NPZ, графики). Без контейнера — россыпь списков, неудобно и нет явного контракта.

## Определение

```python
@dataclass
class SimulationHistory:
    """Результаты расчёта — сохранённые шаги."""
    times: list[float]
    states: list[SimulationState]
    hydro_results: list[HydroResult]
    well_data: list[WellData]
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `times` | `list[float]` | Моменты времени сохранённых шагов, с |
| `states` | `list[SimulationState]` | Состояния (p, Sg, Rs, T, regime) |
| `hydro_results` | `list[HydroResult]` | Потоки через грани (G, Q, u, m, Gm) |
| `well_data` | `list[WellData]` | Скважинные данные (дебиты, p_wf, T_wf) |

Все списки имеют одинаковую длину K.

### save_every

Не все шаги хранятся. Логика отбора (реализуется в Simulator, фаза 6):
- Каждый `save_every`-й шаг
- Последний шаг каждого интервала истории (гарантированно)
- Первый шаг (t=0, начальное состояние)

`save_every` задаётся в JSON (секция `output`). По умолчанию = 1 (все шаги).

### Методы (будущее, не реализуем в фазе 3)

```python
def append(self, t, state, hydro, well):
    """Добавить шаг."""

def to_arrays(self) -> dict[str, np.ndarray]:
    """Конвертация в словарь массивов для NPZ."""

@property
def n_saved(self) -> int:
    return len(self.times)
```

Методы добавятся в фазе 6–7. В фазе 3 — чистый dataclass без логики.

## Жизненный цикл

```
Factory ──создаёт──→ Simulator
                         │
                    run() цикл по времени
                         │
                    ◄──── SimulationHistory (наполняется)
                         │
                    return SimulationHistory
                         │
I/O ◄────────────────────┘
    save_npz(history, path)
    plot_profiles(history, ...)
    plot_well_dynamics(history, ...)
```

## Реализация в фазе 3

В `state.py`:
- Определить `SimulationHistory` как `@dataclass` с четырьмя полями
- Конструктор по умолчанию: пустые списки
- Метод `append(t, state, hydro, well)` для удобства наполнения

## Связанные заметки

- [[словарь-код-физика]] — §2a
- [[модули-simulator-оркестратор]] — наполнение SimulationHistory
- [[модули-io-вывод]] — чтение SimulationHistory
- [[P8-формат-ввода-json]] — save_every в секции output
