---
name: контейнер-simulation-history
description: SimulationHistory — контейнер результатов расчёта, контракт Simulator→I/O, отбор записей по расписанию, накопленные балансы энергии и массы
metadata:
  type: project
---

# SimulationHistory — контейнер результатов

> **Обновлено 2026-10-10 ([[DEBT-052]]):** разделы «Методы», «Жизненный цикл» и «История» — по коду (`state.py:138-185`, `io/output.py`). Проектные разделы «Методы (будущее, не реализуем в фазе 3)» и «Реализация в фазе 3» сняты.

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
    balance: list[dict]          # DEBT-013
    mass_balance: list[dict | None]  # DEBT-039
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `times` | `list[float]` | Моменты времени сохранённых шагов, с |
| `states` | `list[SimulationState]` | Состояния (p, Sg, Rs, T, regime) |
| `hydro_results` | `list[HydroResult]` | Потоки через грани (G, Q, u, m, Gm) |
| `well_data` | `list[WellData]` | Скважинные данные (дебиты, p_wf, T_wf) |
| `balance` | `list[dict]` | Накопленные члены баланса энергии (DEBT-013) |
| `mass_balance` | `list[dict \| None]` | Запас компонентов и интегралы потоков через забой и контур (DEBT-039) |

Все списки имеют одинаковую длину K.

### Отбор записей (DEBT-013)

Запись делается **на конце каждого интервала** `time.history`, плюс
начальное состояние при t = 0. Отсюда `K = n_intervals + 1` всегда.

Механизм отбора **единственный**: моменты записи задаёт расписание, а
`time.dt_integration` отвечает только за точность схемы. Ранее существовал
второй, независимый — счётчик `output.save_every`; при значении 1 он
перебивал расписание и писал каждый подшаг, из-за чего рекуррентная
постобработка ломалась трижды (BUG-004, BUG-005, FEAT-016). Параметр
удалён, конфиг с ним отвергается.

Кратность `dt_hist` шагу интегрирования не требуется: `substeps()` делит
интервал так, что `n_sub · dt_actual = dt_hist` ровно.

### balance — накопленные члены баланса энергии (DEBT-013)

Словарь скаляров на момент записи, шесть ключей: `delta_E`, `cum_adiab`,
`cum_conv`, `cum_jt`, `cum_deg`, `cum_cond`. Производные величины
(`total`, `residual`, `rel_residual`) не хранятся — считаются при сборке.

Ключевое свойство: значения накоплены по **всем подшагам** внутри
решателя (`energy/balance.py`), а не восстановлены по записям. Поэтому
они не зависят от структуры истории — совпадают побитово при записи
каждого подшага, раз в 12 подшагов и при неравномерном расписании.
Восстановление постфактум так не умеет: потоки внутри интервала успевают
существенно измениться, и интерполяция по его концам этой информации не
содержит (замер на 04a: 2e-1 против 1e-3).

На начальном состоянии — нулевой снимок по всем шести членам.

### mass_balance — баланс массы компонентов (DEBT-039)

Словарь скаляров на момент записи, ключи `MASS_KEYS`
(`gpn_multiphase_solver/mass_balance.py`): `M_o`, `M_g` — запас нефтяного и
газового компонентов, м³ст; `cum_o_well`, `cum_o_ext`, `cum_g_well`,
`cum_g_ext` — интегралы потоков через забой и контур от $t = 0$, м³ст (знак
как у $G$). Невязка $\Delta M + \int G_N\,dt - \int G_0\,dt$ и графики —
`examples/mass_balance.py`.

Интегралы, как и члены баланса энергии, копятся по всем принятым шагам
(по принятым подшагам локального дробления, DEBT-015); запас — функция состояния, его на каждой
записи отдаёт решатель (`HydroSolver.component_inventories`). На начальном
состоянии — запас $M(0)$ и нулевые интегралы, не нулевой снимок. У тестовых
двойников, не сохраняющих массу, все снимки — `None`.

### Методы (реализовано: state.py)

```python
def append(self, t: float, state: SimulationState,
           hydro: HydroResult, well: WellData,
           balance: dict | None = None,
           mass_balance: dict | None = None) -> None:
    """Добавить один сохранённый шаг."""

@property
def n_saved(self) -> int:
    """Число сохранённых шагов."""
    return len(self.times)
```

`append` дописывает по элементу во все шесть списков. `balance=None` даёт
нулевой снимок, `mass_balance=None` записывается как `None` — нулевого
снимка массы нет (см. выше). Начальную запись `Simulator.run` делает без
`balance` и с запасом $M(0)$ в `mass_balance`, записи на концах интервалов —
со снимками обоих накопителей ([[модули-simulator-оркестратор]]).

Упаковка в массивы — не метод контейнера, а функция
`history_to_arrays(history)` модуля `io/output.py`: `times` — `[K]`; `p`,
`T`, `Sg`, `Rs` — `[K, N]`; `q_o_std`, `q_g_std`, `p_wf`, `T_wf` — `[K]`.
Поля `balance` и `mass_balance` в неё не входят — их читают постобработки
`examples/energy_balance.py` и `examples/mass_balance.py`.

## Жизненный цикл

```
Factory ──создаёт──→ (Simulator, initial_state)
                         │
                    run(initial_state) — цикл по времени
                         │
                    ◄──── SimulationHistory (наполняется)
                         │
                    return SimulationHistory
                         │
I/O (io/output.py) ◄─────┘
    save_npz(history, grid, path), save_csv(history, grid, path)
    save_well_csv(history, path)
    plot_profiles(history, grid, ...), plot_2d_map(history, grid, ...)
    plot_wellbore_dynamics(history, ...), plot_well_rate(history, ...)
```

## История

Фаза 3 (2026-08): `@dataclass` с четырьмя полями (`times`, `states`,
`hydro_results`, `well_data`), пустые списки по умолчанию, метод
`append(t, state, hydro, well)`. Задуманный метод `to_arrays` реализован
функцией `history_to_arrays` модуля I/O. Поле `balance` и аргумент `append`
к нему — [[DEBT-013]], `mass_balance` — [[DEBT-039]].

## Связанные заметки

- [[словарь-код-физика]] — §2a
- [[модули-simulator-оркестратор]] — наполнение SimulationHistory
- [[модули-io-вывод]] — чтение SimulationHistory
- [[P8-формат-ввода-json]] — секция output (без save_every, DEBT-013)
- [[временная-сетка-и-история]] — расписание задаёт моменты записи
