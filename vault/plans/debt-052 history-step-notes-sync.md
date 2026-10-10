---
tags:
  - план
  - реструктуризация
date: 2026-10-10
issue: DEBT-052
github: 83
branch: refactor/debt-052/history-step-notes-sync
status: реализован
worktree: .worktrees/debt-052; удалён после влития
merged: 734e782 (2026-10-10)
audit:
  date: 2026-10-10
  found: 7
  auto-fixed: 7
  manual-required: 0
---

# DEBT-052: заметки vault о `SimulationHistory` и шаге по времени — по коду после DEBT-013, DEBT-015, DEBT-039

Подтип: **реструктуризация документации**. Правятся четыре заметки vault и одна строка P8, код и тесты не меняются.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай правимые заметки (все короткие, целиком):
   - `vault/knowledge/decisions/контейнер-simulation-history.md` (134 строки);
   - `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md` (316 строк; править только шапку, §6 и «Связанные заметки»);
   - `vault/knowledge/validation/матрица температурной задачи сверена с постановкой поэлементно.md` (131 строка);
   - `vault/knowledge/decisions/модули-io-вывод.md` (201 строка; правится только раздел «output.py»);
   - `vault/knowledge/decisions/P8-формат-ввода-json.md` — только строки 196-203 (правится `:199`).
3. Источник истины (не править): `numerical_solver/gpn_multiphase_solver/state.py:138-185` (`SimulationHistory`), `io/output.py:29-253` (`history_to_arrays`, сохранение, графики), `simulator.py:98-102, 123, 151-158, 194-197, 205-247` (`Simulator`, `run`, `_advance`), `energy/base.py:27-30`, `hydro/base.py:33-34, 54`, `grid/base.py:55-69`, `pvt/base.py:19, 79, 113, 153`, `factory.py:34-41`.
4. Для справки (не править): `vault/knowledge/decisions/модули-simulator-оркестратор.md` — заметка, сверенная с кодом в DEBT-050 (#80); на неё ведут новые ссылки.
5. Ветка `refactor/debt-052/history-step-notes-sync` от `numerical_scheme/implementation`, worktree `.worktrees/debt-052` (контракт `/implement`).
6. Baseline из `numerical_solver/` worktree: `.venv\Scripts\python -m pytest tests/ --collect-only -q` — **записать число**. На `d3aabff` (2026-10-10, после влития DEBT-049) — 1494; если к старту влит DEBT-053 (удаляет один тест) — 1493. Критерий — число после правки равно числу до неё, а не константе. Быстрый уровень не нужен: код не меняется.
7. Шаги 2–6 правят по одной заметке; шаг 7 — сверка всех пяти с кодом.

## Контекст

Три заметки vault остались в состоянии проектного этапа (2026-08), хотя код с тех пор переписан:

- **DEBT-013** (#26) добавил в `SimulationHistory` поле `balance` (накопленные члены баланса энергии) и аргумент `append(..., balance=None)`;
- **DEBT-039** (#65) — поле `mass_balance` и аргумент `append(..., mass_balance=None)`;
- **DEBT-015** (#61, влит `e684ee2`) — перенёс дробление шага из гидро-адаптера («A-retry» — равномерное дробление внутри адаптера) в `Simulator._advance` и сделал его **локальным**: подшаг, на котором гидродинамика не сошлась (`HydroConvergenceError`), делится пополам; подшаги одного шага имеют вид $dt/2^k$ и бывают разной длины; энергия идёт ровно по подшагам гидро (BUG-010).

Найдено при планировании и аудите DEBT-050 (план `vault/plans/debt-050 orchestrator-note-local-splitting.md`, «Обнаруженные проблемы», пп. 1–3), зарегистрировано как DEBT-052. При открытии issue #83 и при планировании объём расширен (см. «Решения пользователя»). Планирование DEBT-053 (#84, план `vault/plans/debt-053 simulator-output-config-retry-terms.md`, «Обнаруженные проблемы», пп. 1–2) дописало в реестр DEBT-052 два пункта: сигнатуру `Simulator` брать из `simulator.py` на момент реализации (DEBT-053 удаляет `output_config`) и термин «A-retry» в `P8-формат-ввода-json.md:199`.

**Термин.** «Плашка» — цитатный блок Markdown (`> **...**`) в начале раздела или заметки: предупреждает читателя, что текст ниже не совпадает с кодом, и даёт ссылку на текущее описание. Образцы — `модули-simulator-оркестратор.md:10`, `модули-io-вывод.md:194`.

### Решения пользователя (2026-10-10, при планировании)

1. `контейнер-simulation-history` — **заменить по коду**: «Методы» — текущие `append` и `n_saved`, упаковка в массивы — функция `history_to_arrays`; «Реализация в фазе 3» удалить, вместо неё — короткий раздел «История».
2. `архитектура библиотеки numerical_solver` — **плашка вверху заметки** с перечнем расхождений и ссылками на текущие описания, плюс короткая плашка над §6. Текст разделов не трогается.
3. `модули-io-вывод` (найдено при планировании) — **включить в DEBT-052**: плашка над разделом «output.py». Раздел «config.py» не трогать.

## Расхождения заметок с кодом (на `d0a8c05`; до `d3aabff` из файлов-источников менялся только `io/config.py` — DEBT-049, +26 строк, цитируемые `:282-283`, `:334` прежние)

### `контейнер-simulation-history.md`

| # | Строки | Сейчас написано | Код | Шаг |
|---|---|---|---|---|
| К1 | `:3` | description: «…накопленный баланс энергии» | ещё баланс массы, `mass_balance` (DEBT-039) | 2 |
| К2 | `:87` | «Методы (будущее, не реализуем в фазе 3)» | `append`, `n_saved` реализованы (`state.py:165-185`) | 2 |
| К3 | `:90` | `append(self, t, state, hydro, well)` | `append(t, state, hydro, well, balance=None, mass_balance=None)` (`state.py:165-168`) | 2 |
| К4 | `:93-94` | метод `to_arrays(self)` | метода нет и не было (`git log -S "def to_arrays"` пуст); функция `history_to_arrays(history)` (`io/output.py:29`) | 2 |
| К5 | `:96-98` | `def n_saved` без docstring | `@property`, docstring «Число сохранённых шагов.» (`state.py:182-185`) | 2 |
| К6 | `:101` | «Методы добавятся в фазе 6–7. В фазе 3 — чистый dataclass без логики» | устарело | 2 |
| К7 | `:106` | `Factory ──создаёт──→ Simulator` | `from_config(config) → (Simulator, initial_state)` (`factory.py:38`) | 2 |
| К8 | `:108` | `run()` | `run(initial_state)` (`simulator.py:123`) | 2 |
| К9 | `:115` | `save_npz(history, path)` | `save_npz(history, grid, path)` (`io/output.py:60`) | 2 |
| К10 | `:117` | `plot_well_dynamics(history, ...)` | функции нет; `plot_wellbore_dynamics` (`:171`), `plot_well_rate` (`:200`) | 2 |
| К11 | `:120-125` | «Реализация в фазе 3»: «`@dataclass` с четырьмя полями», `append(t, state, hydro, well)` | полей шесть (`state.py:158-163`) | 2 |

Верно, не правится: `:10-85` (мотивация, определение, поля, отбор записей, `balance`, `mass_balance`), `:127-133` («Связанные заметки»).

### `архитектура библиотеки numerical_solver.md`

Заметка — проектная целиком. Расхождения, проверенные grep-ом по `numerical_solver/gpn_multiphase_solver/`:

| # | Строки | В заметке | Код |
|---|---|---|---|
| А1 | `:24` | `HydroUnitDecorator`, `EnergyUnitDecorator` | классов нет; `units.py` — только константы (`BAR_TO_PA`, `S_TO_DAY`, …) |
| А2 | `:106` | ABC `PVTModel` | `HydroPVT` (`pvt/base.py:19`), `FullPVT` (`:79`), `DifferentiableHydroPVT` (`:113`) |
| А3 | `:130` | ABC `RPModel` | `RelPermModel` (`pvt/base.py:153`) |
| А4 | `:147-149` | `transmissibilities`, `trans_left`, `trans_right` | `trans_internal`, `trans_well`, `trans_ext` (`grid/base.py:55-69`) |
| А5 | `:155` | `HydroSolver.solve(state, dt, bc) → state` | `→ HydroResult` (`hydro/base.py:33-34`) |
| А6 | `:156` | `velocities(state)` | метода нет; в ABC — `solve`, `component_inventories` (`hydro/base.py:33, 54`) |
| А7 | `:172` | `EnergySolver.solve(state, dt, bc) → T` | `solve(hydro_result, state_prev, dt, bc, collect=None) -> np.ndarray` (`energy/base.py:27-30`) |
| А8 | `:178` | `Simulator.__init__(self, grid, pvt, relperm, hydro, energy, config)` | `(grid, hydro, energy, pvt, schedule, output_config=None, max_retries=9)` (`simulator.py:98-102`) |
| А9 | `:181` | `run(self) -> SimulationResult` | `run(self, initial_state) -> SimulationHistory` (`simulator.py:123`); класса `SimulationResult` нет |
| А10 | `:182-187` | цикл «p_wf → гидро → u → энергия → сохранить» на каждом шаге | `run` → `_advance` с локальным дроблением (`simulator.py:205-247`), накопители балансов, запись на концах интервалов `time.history` |
| А11 | `:195-202` | `from_config(path) -> Simulator`; `StandingPVT`, `NewtonHydroSolver` | `from_config(config) -> tuple[Simulator, SimulationState]` (`factory.py:38`); `StandingFullPVT` (`pvt/standing.py:31`); `NewtonHydroSolver` нет — гидродинамику решает прототип через `PrototypeHydroAdapter` |
| А12 | `:48-102` | дерево пакета и `tests/` из 5 файлов | нет `units.py`, `mass_balance.py`, `energy/balance.py`, `pvt/consistency.py`, `pvt/hydro_to_blackoil_adapter.py`; в `tests/` — 29 файлов `test_*.py` |
| А13 | `:218-282` | образец JSON: секции `boundary_conditions`, `numerics.dt_init` | обязательные секции — `geometry`, `grid`, `rock`, `pvt`, `relperm`, `thermal`, `initial_conditions`, `time` (`io/config.py:282-283`); схема — P8 |
| А14 | `:284-295` | «Гидродинамический блок коллеги ещё не передан» | передан и обёрнут (`hydro/prototype_adapter.py`) |

Правка — плашки (решение 2), текст разделов не меняется.

### `матрица температурной задачи сверена с постановкой поэлементно.md`

| # | Строки | Сейчас написано | Факт | Шаг |
|---|---|---|---|---|
| М1 | `:39-41` | «При A-retry `Simulator._advance` дробит шаг и вызывает `solve` с $\Delta t_{sub} = \Delta t / n_{sub}$» | A-retry удалён в DEBT-015; подшаги $dt/2^k$, не обязательно равные (`simulator.py:211-247`). Утверждение «проба отдаёт фактический $\Delta t$ вызова» верно | 4 |
| М2 | `:127-128` | «[[DEBT-015]] — перенос A-retry на уровень `Simulator`; при реализации потребует пересмотра теста на сохранение времени» | DEBT-015 переписал у `test_energy_substeps_preserve_total_time` (`tests/test_energy_matrix_examples.py:788`) только тексты: docstring (`639c80f`, довод про удалённое `HydroResult.n_substeps`) и комментарии к `SUBDIVIDING_EXAMPLES` (`15be88d`, `e75b1d2`); проверки и список примеров не менялись, проверка «сумма $\Delta t$ по вызовам `solve` = расписание» зелёная | 4 |

### `модули-io-вывод.md`

| # | Строки | Сейчас написано | Код | Шаг |
|---|---|---|---|---|
| И1 | `:106, 122, 143, 158, 184` | `history.to_arrays()` | метода нет; `history_to_arrays(history)` (`io/output.py:29`) | 5 |
| И2 | `:105, 121` | `save_npz(history, path, r_centers)`, `save_csv(history, path, r_centers)` | `save_npz(history, grid, path)`, `save_csv(history, grid, path)` (`:60, 80`); ещё `save_well_csv(history, path)` (`:106`) | 5 |
| И3 | `:141, 157, 172, 183` | `plot_profiles(history, r, ...)`, `plot_wellbore_dynamics(history)`, `plot_well_rate(history, grid)`, `plot_2d_map(history, r, ...)` | `plot_profiles(history, grid, times_to_plot, field='T', ax=None)` (`:138`), `plot_wellbore_dynamics(history, axes=None)` (`:171`), `plot_well_rate(history, ax=None)` (`:200`), `plot_2d_map(history, grid, field='T', ax=None)` (`:219`); ещё `plot_pvt_properties` (`:298`) | 5 |
| И4 | `:107-113` | NPZ: `times`, `r`, `p`, `T`, `Sg`, `Rs` | ещё `q_o_std`, `q_g_std`, `p_wf`, `T_wf` (`:64-73`) | 5 |

Правка — плашка (решение 3), эскизы не меняются. Плашка `:194` (FEAT-022, время в сутках) остаётся.

### `P8-формат-ввода-json.md` (добавлено планированием DEBT-053; на `d3aabff`, после правок DEBT-049)

| # | Строки | Сейчас написано | Факт | Шаг |
|---|---|---|---|---|
| П1 | `:199` | «A-retry их не использует: глубина дробления задаётся `max_retries`, а не нижней границей подшага» | A-retry удалён в DEBT-015; по существу верно и для локального дробления (`dt_min`, `dt_max` не читает никто), устарел термин. Соседняя `:200` уже в терминах DEBT-015 | 6 |

## Варианты

**A. Переписать все устаревшие разделы по коду** (включая §§1–7 `архитектура…` и эскизы `модули-io-вывод`). Заметки точны, но `архитектура…` и `модули-io-вывод` начинают дублировать код и `модули-simulator-оркестратор` — два места, которые разойдутся при следующей правке. Отклонён (решения 2, 3).

**B. Плашки везде.** Минимум правок. Для `контейнер-simulation-history` не годится: это справочник по контейнеру, верх уже актуален — плашка внутри одной заметки оставит противоречие. Для `матрица…` неверный прогноз о тесте остался бы. Отклонён (решение 1).

**C (выбран). По типу заметки.** Справочник `контейнер-simulation-history` — переписать по коду; проектные `архитектура…` и `модули-io-вывод` — плашки с перечнем расхождений и ссылками на текущее; `матрица…` — точечная правка двух мест.

## Подводные камни (чеклист 2.5)

- ✅ **Call sites / import-ы / циклы / configs / прототип** — код не меняется.
- ✅ **Тесты** — не меняются; число тестов до и после одинаково (1494 на `d3aabff`).
- ⚠️ **Плашка ≠ код.** Риск — переписать сигнатуру по памяти и внести новое расхождение. Адресовано: каждая сигнатура в блоках «После» сверена с кодом на `d0a8c05` (таблицы выше со ссылками на строки; до `d3aabff` источники, кроме `io/config.py`, не менялись); шаг 1 — `git diff --stat` по файлам-источникам; шаг 7 — повторная сверка grep-ом.
- ⚠️ **Плашки не должны менять текст разделов** (решения 2, 3). Адресовано: шаг 7, п. 4 — `git diff --numstat` по `архитектура…` и `модули-io-вывод` показывает 0 удалённых строк.
- ⚠️ **Wiki-ссылки.** Новые ссылки: [[модули-simulator-оркестратор]], [[контейнер-simulation-history]], [[P8-формат-ввода-json]], [[DEBT-052]], [[DEBT-050]], [[DEBT-015]], [[DEBT-013]], [[DEBT-039]], [[BUG-010]]. Первые три — файлы в `vault/knowledge/decisions/` (проверено Glob); ID задач — заголовки реестра, так ссылаются другие заметки. Шаг 7 — Glob каждой цели-файла.
- ✅ **DEBT-049** влит во время планирования (`d94f9e8`, «влит» `d3aabff`): правил `io/config.py` (+26 строк, цитируемые строки не сдвинулись), `P8-формат-ввода-json.md` и заметку о нефизичной температуре. Строка P8 `:199` прочитана на `d3aabff` — после его правок.
- ⚠️ **DEBT-053** (#84, план `vault/plans/debt-053 simulator-output-config-retry-terms.md`, вариант А1) удаляет `output_config` из `Simulator` и фабрики, правит `модули-simulator-оркестратор.md` и комментарии тестов «A-retry»; P8 и четыре заметки DEBT-052 не трогает. Порядок влития неизвестен. Адресовано: шаг 1 сверяет `simulator.py:98-102`; шаг 3 берёт сигнатуру из кода на момент реализации — правило там же. Термин «A-retry» в правке `матрица…` (шаг 4) — в прошедшем времени, как оставляет DEBT-053 в `simulator.py:230`.
- ✅ **Расследование [[BUG-010]]** (`vault/knowledge/debugging/энергия решается одним шагом там где гидро раздробило.md:64`) описывает прежний механизм как историю — не трогать (реестр DEBT-052, «Не входит»).

## Шаги

Номера строк — по файлам до правки. Внутри заметки после верхней правки нижние строки сдвигаются — искать по тексту «До», а не по номеру. `<дата>` в блоках «После» — дата реализации (`ГГГГ-ММ-ДД`).

### Шаг 1: Подготовка

**Цель:** worktree, baseline, проверка, что код не ушёл от плана.

**Что сделать:**
1. По контракту `/implement` — коммит плана в базу, worktree `.worktrees/debt-052` на ветке `refactor/debt-052/history-step-notes-sync`.
2. Из `numerical_solver/` worktree: `.venv\Scripts\python -m pytest tests/ --collect-only -q` — записать число.
3. Из корня worktree:
   ```powershell
   git diff --stat d3aabff HEAD -- "vault/knowledge/decisions/P8-формат-ввода-json.md" numerical_solver/gpn_multiphase_solver/state.py numerical_solver/gpn_multiphase_solver/io/output.py numerical_solver/gpn_multiphase_solver/simulator.py numerical_solver/gpn_multiphase_solver/factory.py numerical_solver/gpn_multiphase_solver/energy/base.py numerical_solver/gpn_multiphase_solver/hydro/base.py numerical_solver/gpn_multiphase_solver/grid/base.py numerical_solver/gpn_multiphase_solver/pvt/base.py "vault/knowledge/decisions/контейнер-simulation-history.md" "vault/knowledge/decisions/архитектура библиотеки numerical_solver.md" "vault/knowledge/validation/матрица температурной задачи сверена с постановкой поэлементно.md" "vault/knowledge/decisions/модули-io-вывод.md"
   ```
   Пусто — номера строк и сигнатуры плана верны. Иначе — сверить затронутые строки таблиц «Расхождения» с кодом заново. Ожидаемое непустое: `simulator.py` и `factory.py`, если влит DEBT-053, — тогда записать, есть ли `output_config` в `simulator.py:98-102` (для шага 3).
4. Число файлов тестов для плашки шага 3: Glob `numerical_solver/tests/test_*.py` (на `d3aabff` — 29).
5. Проба аудита (до правок): из корня worktree `$env:PYTHONIOENCODING = "utf-8"; numerical_solver\.venv\Scripts\python vault\issues\debt-052\probes\apply_plan_blocks.py`. Она применяет все пары «До → После» плана к копиям заметок в памяти (файлы не меняет), проверяет, что каждый блок «До» встречается ровно один раз, и пересчитывает grep-проверки шагов 2–6. Ожидание — «ИТОГ: все проверки сошлись», 12 пар, удалено: `контейнер…` −19, `архитектура…` −0, `матрица…` −5, `модули-io-вывод` −0, P8 −1 (замер аудита на `f99cdbe`). FAIL на «До» — заметку правили после плана: сверить блок с файлом. После правок проба не нужна (блоков «До» в файлах уже нет).

**Проверка:** число тестов записано; diff пуст или расхождения учтены; проба — «все проверки сошлись».

**Оценка:** ~5 мин.

### Шаг 2: `контейнер-simulation-history.md` — по коду

**Цель:** снять расхождения К1–К11; заметка перестаёт противоречить сама себе.

**Файлы:** `vault/knowledge/decisions/контейнер-simulation-history.md`

**Контекст:** заметка — справочник по контейнеру результатов (на неё ссылаются `модули-simulator-оркестратор.md:246`, `модули-io-вывод.md:178`). Верх (`:14-85`) актуален, низ (`:87-125`) — проект фазы 3. Решение 1: заменить по коду, проектный текст свести к разделу «История».

**Изменения:**

2.1. description (`:3`).

До:
~~~
description: SimulationHistory — контейнер результатов расчёта, контракт Simulator→I/O, отбор записей по расписанию, накопленный баланс энергии
~~~
После:
~~~
description: SimulationHistory — контейнер результатов расчёта, контракт Simulator→I/O, отбор записей по расписанию, накопленные балансы энергии и массы
~~~

2.2. Плашка о пересмотре — после заголовка `# SimulationHistory — контейнер результатов` (`:8`), отделить пустыми строками.

До:
~~~
# SimulationHistory — контейнер результатов

## Мотивация
~~~
После:
~~~
# SimulationHistory — контейнер результатов

> **Обновлено <дата> ([[DEBT-052]]):** разделы «Методы», «Жизненный цикл» и «История» — по коду (`state.py:138-185`, `io/output.py`). Проектные разделы «Методы (будущее, не реализуем в фазе 3)» и «Реализация в фазе 3» сняты.

## Мотивация
~~~

2.3. Раздел «Методы» (`:87-101`) — К2–К6.

До:
~~~
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
~~~
После:
~~~
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
~~~

Сверено: `state.py:165-185` (сигнатура, docstring-и, `@property`); `simulator.py:152-158` (начальный `append` без `balance`, с `mass_balance=self._mass_snapshot(mass, state)`), `:194-197` (`balance=balance.snapshot()`, `mass_balance=...`); `io/output.py:29-53` (ключи); `examples/energy_balance.py`, `examples/mass_balance.py` — grep `\.balance\b|\.mass_balance\b` по `numerical_solver/examples/*.py` находит только эти два файла.

2.4. «Жизненный цикл» (`:105-118`) — К7–К10.

До:
~~~
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
~~~
После:
~~~
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
~~~

Сверено: `factory.py:38`, `simulator.py:123`, `io/output.py:60, 80, 106, 138, 171, 200, 219`.

2.5. «Реализация в фазе 3» (`:120-125`) → «История» — К11.

До:
~~~
## Реализация в фазе 3

В `state.py`:
- Определить `SimulationHistory` как `@dataclass` с четырьмя полями
- Конструктор по умолчанию: пустые списки
- Метод `append(t, state, hydro, well)` для удобства наполнения
~~~
После:
~~~
## История

Фаза 3 (2026-08): `@dataclass` с четырьмя полями (`times`, `states`,
`hydro_results`, `well_data`), пустые списки по умолчанию, метод
`append(t, state, hydro, well)`. Задуманный метод `to_arrays` реализован
функцией `history_to_arrays` модуля I/O. Поле `balance` и аргумент `append`
к нему — [[DEBT-013]], `mass_balance` — [[DEBT-039]].
~~~

**Проверка после шага:**
- Регресс: только документ — `--collect-only` не нужен до шага 7.
- Grep по заметке: `def to_arrays` — 0; `plot_well_dynamics` — 0; `save_npz\(history, path\)` — 0; `### Методы \(будущее` — 0; `не реализуем` — 1 (только цитата в плашке 2.2); `## Реализация в фазе 3` — 0; `четырьмя` — 1 («История»); `balance: dict \| None = None` — 2 (строки `balance` и `mass_balance` сигнатуры); `history_to_arrays` — 2 («Методы», «История»); `DEBT-052` — 1 (плашка).

**Подводные камни:** «Плашка ≠ код», «Wiki-ссылки».

**Зависимости:** требует шаг 1.

**Оценка:** ~40 строк, ~15 мин.

### Шаг 3: `архитектура библиотеки numerical_solver.md` — плашки

**Цель:** читатель видит, что интерфейсы и псевдокод заметки — проектные, и находит текущее описание (расхождения А1–А14).

**Файлы:** `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`

**Контекст:** заметка названа в `CLAUDE.md` («Ключевые заметки») как описание модулей, паттернов и ABC; на неё ссылаются 19 заметок (`[[architecture-numerical-solver]]`). Решение 2: одна плашка вверху с перечнем расхождений, короткая — над §6 (псевдокод шага — тема DEBT-052), текст разделов не меняется. Переписывать §6 по коду не нужно: схема шага описана в [[модули-simulator-оркестратор]], два места разошлись бы при следующей правке `Simulator`.

**Изменения:**

3.1. Плашка — после заголовка `# Архитектура библиотеки numerical_solver` (`:8`).

До:
~~~
# Архитектура библиотеки numerical_solver

## Контекст
~~~
После (число файлов тестов — из шага 1, п. 4). **Сигнатура `Simulator` — по `simulator.py:98-102` на момент реализации:**
- DEBT-053 влит (`output_config` в сигнатуре нет) — `Simulator(grid, hydro, energy, pvt, schedule, max_retries=9)`;
- не влит — как в блоке ниже, с `output_config=None`, и в реестре, секция DEBT-053, дописать: «плашка `архитектура библиотеки numerical_solver.md` (DEBT-052) содержит сигнатуру с `output_config` — убрать при реализации DEBT-053». Обратную сторону план DEBT-053 уже предусматривает (`vault/plans/debt-053 simulator-output-config-retry-terms.md`, шаг 5, п. 5: «если влит DEBT-052 — плашка без `output_config`»).

На 2026-10-10 (аудит) DEBT-053 в реализации (`.worktrees/debt-053`, старт `f99cdbe`) — вероятнее первый вариант. Если DEBT-053 влит в базу, пока идёт DEBT-052, — шаг 7, п. 8.
~~~
# Архитектура библиотеки numerical_solver

> **Проектный этап (2026-08); сверено с кодом в [[DEBT-052]] (<дата>).** Заметка начата как замысел до передачи гидродинамического прототипа и обновлялась выборочно (дерево пакета, абзац FEAT-020 в §4). Интерфейсы, псевдокод и образцы ниже — **не текущий код**:
> - нет в коде: `NewtonHydroSolver` (гидродинамику решает прототип через `PrototypeHydroAdapter`), `StandingPVT` (есть `StandingFullPVT`), `HydroUnitDecorator`, `EnergyUnitDecorator` (единицы переводят адаптеры прототипа по константам `units.py`), `HydroSolver.velocities`, `SimulationResult`;
> - ABC названы иначе: `PVTModel` → `HydroPVT`, `FullPVT`, `DifferentiableHydroPVT`; `RPModel` → `RelPermModel`; проводимости `Grid` — `trans_internal`, `trans_well`, `trans_ext`;
> - сигнатуры: `HydroSolver.solve(state, dt, bc) → HydroResult`; `EnergySolver.solve(hydro_result, state_prev, dt, bc, collect=None) → T`; `Simulator(grid, hydro, energy, pvt, schedule, output_config=None, max_retries=9)`, `run(initial_state) → SimulationHistory`; `SimulatorFactory.from_config(config) → (Simulator, initial_state)`;
> - дерево пакета неполное (нет `units.py`, `mass_balance.py`, `energy/balance.py`, `pvt/consistency.py`, `pvt/hydro_to_blackoil_adapter.py`), в `tests/` — 29 файлов, а не 5;
> - образец JSON и раздел «Связь с внешним гидродинамическим модулем» — до прототипа.
>
> Текущее: контракты — `pvt/base.py`, `grid/base.py`, `hydro/base.py`, `energy/base.py` в `numerical_solver/gpn_multiphase_solver/`; цикл шага, `Simulator` и фабрика — [[модули-simulator-оркестратор]] (сверена с кодом в [[DEBT-050]]); результаты — [[контейнер-simulation-history]]; JSON — [[P8-формат-ввода-json]].

## Контекст
~~~

3.2. Плашка над псевдокодом §6 (`:174-176`).

До:
~~~
### 6. Simulator — оркестратор

```python
class Simulator:
~~~
После:
~~~
### 6. Simulator — оркестратор

> Псевдокод проектного этапа. Текущий цикл: `run(initial_state)` → `_advance` с локальным дроблением шага ([[DEBT-015]]), накопители балансов, запись на концах интервалов `time.history` — [[модули-simulator-оркестратор]], раздел «Цикл по времени».

```python
class Simulator:
~~~

3.3. «Связанные заметки» (`:308-315`) — добавить две строки после `[[модули-energy-tridiag]]`.

До:
~~~
- [[модули-energy-tridiag]] — детали тепловой прогонки
- [[P8-формат-ввода-json]] — актуальная схема JSON
~~~
После:
~~~
- [[модули-energy-tridiag]] — детали тепловой прогонки
- [[модули-simulator-оркестратор]] — текущий цикл шага, `Simulator`, фабрика
- [[контейнер-simulation-history]] — контейнер результатов
- [[P8-формат-ввода-json]] — актуальная схема JSON
~~~

Сверено (на `d0a8c05`): классов `NewtonHydroSolver`, `StandingPVT`, `HydroUnitDecorator`, `EnergyUnitDecorator`, `SimulationResult`, `PVTModel`, `RPModel` и метода `velocities` в пакете нет (grep `class X|def velocities`); `units.py` — без `class`/`def`; `pvt/base.py:19, 79, 113, 153`; `grid/base.py:55-69`; `hydro/base.py:33-34`; `energy/base.py:27-30`; `simulator.py:98-102, 123`; `factory.py:38`; файлы пакета — Glob `numerical_solver/gpn_multiphase_solver/**/*.py`; `io/config.py:282-283`.

**Проверка после шага:**
- Регресс: только документ — `--collect-only` в шаге 7.
- Grep по заметке: `Проектный этап` — 1; `Псевдокод проектного этапа` — 1; `модули-simulator-оркестратор` — 3 (плашка вверху, плашка §6, «Связанные заметки»).
- `git diff --numstat -- "vault/knowledge/decisions/архитектура библиотеки numerical_solver.md"` — во втором столбце (удалено) **0**: текст разделов не тронут.

**Подводные камни:** «Плашка ≠ код», «Плашки не должны менять текст разделов», DEBT-053.

**Зависимости:** требует шаг 1.

**Оценка:** ~15 строк, ~15 мин.

### Шаг 4: `матрица температурной задачи сверена с постановкой поэлементно.md` — термин и прогноз

**Цель:** снять М1, М2.

**Файлы:** `vault/knowledge/validation/матрица температурной задачи сверена с постановкой поэлементно.md`

**Контекст:** заметка — запись верификации DEBT-016 (2026-09-19). Абзац `:39-41` объясняет, почему проба берёт фактический $\Delta t$ вызова, — по сути верно, но термин «A-retry» и формула $\Delta t/n_{sub}$ равных подшагов описывают механизм, удалённый в DEBT-015. Пункт `:127-128` — прогноз, что DEBT-015 потребует пересмотра теста на сохранение времени; прогноз не сбылся. Остальной текст — замеры на дату заметки, не трогать (см. «Обнаруженные проблемы», п. 2).

**Изменения:**

4.1. `:39-41`.

До:
~~~
Проба отдаёт **фактический** $\Delta t$ вызова. При A-retry `Simulator._advance` дробит
шаг и вызывает `solve` с $\Delta t_{sub} = \Delta t / n_{sub}$ ([[BUG-010]]), а
$\text{cap} = V(\rho c_p)/\Delta t$ зависит именно от него.
~~~
После:
~~~
Проба отдаёт **фактический** $\Delta t$ вызова. `Simulator._advance` вызывает `solve` с
длиной подшага $h$ (без дробления $h = dt$): подшаг, на котором гидродинамика не сошлась, делится
пополам (локальное дробление, [[DEBT-015]]; до него — равномерное, по сигналу A-retry
адаптера, [[BUG-010]]). Подшаги одного шага имеют вид $dt/2^k$ и бывают разной длины, а
$\text{cap} = V(\rho c_p)/\Delta t$ зависит именно от фактической длины.
~~~

Сверено: `simulator.py:211-217` (комментарий «Локальное дробление»), `:230-235` («Равномерное дробление (A-retry адаптера до DEBT-015)»), `:247` (`h = dt / (n_units // size)`), `:251` (`self._hydro.solve(state, h, bc)`).

4.2. `:127-128`.

До:
~~~
- [[DEBT-015]] — перенос A-retry на уровень `Simulator`; при реализации потребует
  пересмотра теста на сохранение времени
~~~
После:
~~~
- [[DEBT-015]] — дробление перенесено из адаптера в `Simulator._advance` и сделано
  локальным. Тест на сохранение времени (`test_energy_substeps_preserve_total_time`)
  пересмотра не потребовал: DEBT-015 переписал только его docstring и комментарии
  к `SUBDIVIDING_EXAMPLES` (`639c80f`, `15be88d`, `e75b1d2`), проверка «сумма
  $\Delta t$ по вызовам `solve` равна расписанию» осталась прежней и зелёная —
  подшаги $dt/2^k$ стыкуются без остатка, $\sum h = dt$
~~~

Сверено (аудит 2026-10-10): `git log --oneline -- numerical_solver/tests/test_energy_matrix_examples.py` — коммиты DEBT-015 `639c80f`, `15be88d`, `e75b1d2`; `git show` каждого по этому файлу — изменены только docstring (`639c80f`, `-3/+2`) и строки комментариев над `SUBDIVIDING_EXAMPLES` (`15be88d` — `:767-768`, `e75b1d2` — `:778-782`); `tests/test_energy_matrix_examples.py:808-813` — проверка `np.isclose(total_actual, total_scheduled, rtol=1e-12)`.

**Проверка после шага:**
- Регресс: только документ — `--collect-only` в шаге 7.
- Grep по заметке: `A-retry` — 1 (только «по сигналу A-retry адаптера»); `потребует` — 0; `n_\{sub\}` — 0; `639c80f` — 1.

**Подводные камни:** «Плашка ≠ код».

**Зависимости:** требует шаг 1.

**Оценка:** ~10 строк, ~10 мин.

### Шаг 5: `модули-io-вывод.md` — плашка над «output.py»

**Цель:** снять И1–И4 плашкой; эскизы не трогать.

**Файлы:** `vault/knowledge/decisions/модули-io-вывод.md`

**Контекст:** разделы «output.py» (`:100-134`) и «Визуализация» (`:136-192`) — эскизы проектного этапа: все вызывают несуществующий `history.to_arrays()` и дают старые сигнатуры. Плашка `:194` (FEAT-022) оговаривает только единицы времени на графиках. Решение 3: одна плашка над «output.py», эскизы и раздел «config.py» (`:10-98`) не трогать.

**Изменения:**

До:
~~~
## output.py — сохранение результатов

### NPZ (по умолчанию)
~~~
После:
~~~
## output.py — сохранение результатов

> **Эскизы проектного этапа; сверено с кодом в [[DEBT-052]] (<дата>).** Код в разделах «output.py» и «Визуализация» — замысел, не текущий `numerical_solver/gpn_multiphase_solver/io/output.py`. Метода `SimulationHistory.to_arrays` нет: упаковку в массивы делает функция `history_to_arrays(history)` того же модуля ([[контейнер-simulation-history]]). Текущие сигнатуры: `save_npz(history, grid, path)`, `save_csv(history, grid, path)`, `save_well_csv(history, path)`, `plot_profiles(history, grid, times_to_plot, field='T', ax=None)`, `plot_wellbore_dynamics(history, axes=None)`, `plot_well_rate(history, ax=None)`, `plot_2d_map(history, grid, field='T', ax=None)`, `plot_pvt_properties(pvt, Rs0, p_range, ...)`. Состав NPZ: `r`, `times`, `p`, `T`, `Sg`, `Rs`, `q_o_std`, `q_g_std`, `p_wf`, `T_wf`. Время на графиках — в сутках (плашка FEAT-022 в конце раздела «Визуализация»).

### NPZ (по умолчанию)
~~~

Сверено: `io/output.py:29-53, 60-73, 80-81, 106, 138-140, 171, 200, 219-220, 298-299`.

**Проверка после шага:**
- Регресс: только документ — `--collect-only` в шаге 7.
- Grep по заметке: `Эскизы проектного этапа` — 1; `history_to_arrays` — 1.
- `git diff --numstat -- "vault/knowledge/decisions/модули-io-вывод.md"` — удалено **0**.

**Подводные камни:** «Плашка ≠ код», «Плашки не должны менять текст разделов».

**Зависимости:** требует шаг 1.

**Оценка:** ~3 строки, ~10 мин.

### Шаг 6: `P8-формат-ввода-json.md:199` — термин

**Цель:** снять П1.

**Файлы:** `vault/knowledge/decisions/P8-формат-ввода-json.md`

**Контекст:** P8 — справочник по формату JSON-конфига. Пункт о мёртвых полях `dt_min`, `dt_max` объясняет, почему они не нужны дроблению шага, но называет дробление удалённым термином «A-retry» в настоящем времени. Соседний пункт `:200` (`max_retries`) уже описывает локальное дробление DEBT-015 — правка выравнивает `:199` по нему. Добавлено в DEBT-052 планированием DEBT-053 (план DEBT-053, «Обнаруженные проблемы», п. 2). DEBT-049 правил P8 и влит до этого плана — строка прочитана после его правок.

**Изменения:**

До (`:199`):
~~~
- `dt_min`, `dt_max` — ⚠️ объявлены в `NumericsConfig`, но **никакой модуль их не читает** (проверено grep при DEBT-007). A-retry их не использует: глубина дробления задаётся `max_retries`, а не нижней границей подшага. Учтено в DEBT-008
~~~
После:
~~~
- `dt_min`, `dt_max` — ⚠️ объявлены в `NumericsConfig`, но **никакой модуль их не читает** (проверено grep при DEBT-007). Дробление шага в `Simulator._advance` (локальное, DEBT-015) их не использует: глубина дробления задаётся `max_retries`, а не нижней границей подшага. Учтено в DEBT-008
~~~

Сверено: `simulator.py:216-217` («Наименьший подшаг — dt/2**max_retries»); grep `dt_min|dt_max` по `numerical_solver/gpn_multiphase_solver/` — только объявления в `io/config.py` (DEBT-008, DEBT-051).

**Проверка после шага:**
- Регресс: только документ — `--collect-only` в шаге 7.
- Grep по P8: `A-retry` — 0; `локальное, DEBT-015` — 2 (`:199`, `:200`).
- `git diff --numstat` по P8: 1 добавлена, 1 удалена.

**Подводные камни:** —

**Зависимости:** требует шаг 1.

**Оценка:** 1 строка, ~5 мин.

### Шаг 7: Сверка пяти заметок с кодом

**Цель:** доказать, что расхождения К1–К11, А1–А14 (плашкой), М1–М2, И1–И4 (плашкой), П1 сняты и новых нет.

**Что сделать** (в worktree):
1. Повторить grep-проверки шагов 2–6.
2. Каждое имя из блоков «После» — существует в коде (Grep по `numerical_solver/gpn_multiphase_solver/`): `def history_to_arrays`, `def save_npz`, `def save_csv`, `def save_well_csv`, `def plot_profiles`, `def plot_wellbore_dynamics`, `def plot_well_rate`, `def plot_2d_map`, `def plot_pvt_properties`, `def n_saved`, `def component_inventories`, `class StandingFullPVT`, `class PrototypeHydroAdapter`, `class HydroPVT`, `class FullPVT`, `class DifferentiableHydroPVT`, `class RelPermModel`, `def trans_internal`, `def trans_well`, `def trans_ext`, `def _advance` — каждый ≥ 1. Имена из списка «нет в коде» (`class NewtonHydroSolver`, `class StandingPVT\b`, `UnitDecorator`, `def velocities`, `class SimulationResult`, `def to_arrays`) — 0.
3. Wiki-ссылки: Glob `vault/knowledge/decisions/модули-simulator-оркестратор.md`, `vault/knowledge/decisions/контейнер-simulation-history.md`, `vault/knowledge/decisions/P8-формат-ввода-json.md` — существуют. [[DEBT-052]], [[DEBT-050]], [[DEBT-015]], [[DEBT-013]], [[DEBT-039]], [[BUG-010]] — заголовки реестра `vault/roadmap/известные баги и технический долг.md`.
4. `git diff --numstat` по всем пяти заметкам: удалено 0 строк в `архитектура…` и `модули-io-вывод`; в `контейнер-simulation-history`, `матрица…` и P8 — удалены только строки из блоков «До».
5. `git diff --stat` от точки ветвления — только `vault/` (код и тесты не менялись).
6. `numerical_solver/`: `.venv\Scripts\python -m pytest tests/ --collect-only -q` → то же число, что в baseline шага 1.
7. Перечитать `контейнер-simulation-history.md` целиком один раз: верх (`balance`, `mass_balance`) и новые «Методы» не противоречат друг другу.
8. Сигнатура `Simulator` в плашке `архитектура…` совпадает с `numerical_solver/gpn_multiphase_solver/simulator.py:98-102` **базы** на момент проверки: `git log --oneline HEAD..numerical_scheme/implementation -- numerical_solver/gpn_multiphase_solver/simulator.py` — пусто, иначе база ушла (например, влит DEBT-053) — сверить сигнатуру с `git show numerical_scheme/implementation:numerical_solver/gpn_multiphase_solver/simulator.py` и поправить плашку; пометку в секции DEBT-053 реестра (шаг 3) тогда не оставлять или снять.

**Проверка:** Регресс: `--collect-only` (код не менялся). Итоговый полный прогон — по контракту `/implement`; изменений кода нет, ожидание — тот же итог, что у базы.

**Оценка:** ~15 мин.

### Шаг 8: Vault и issue

**Цель:** статус задачи, комментарий в issue.

**Что сделать:**
1. Реестр `vault/roadmap/известные баги и технический долг.md`, секция DEBT-052: статус по контракту `/implement`.
2. `vault/issues/debt-052/05-comment-done.md` — итог: какие заметки и разделы правлены, таблица «расхождение → снято (правкой / плашкой)», число тестов без изменений; `gh issue comment 83 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-052/05-comment-done.md`.
3. `vault/00-home/index.md` — не трогать: новых заметок нет (строка плана добавлена при планировании).

**Оценка:** ~10 мин.

## Тестовая стратегия

Код не меняется — новых тестов нет. Неизменность поведения подтверждает число тестов (одно и то же до и после; 1494 на `d3aabff`). Корректность документов — шаг 7: grep-проверки (нет устаревших имён в исправленных местах, есть новые; каждое имя из плашек существует в коде), `git diff --numstat` (плашки не удалили текст) и перечитывание `контейнер-simulation-history`.

**Тест:** — (документ)
**Предотвращает:** возврат устаревшего API `SimulationHistory` и схемы шага в справочники; ложное впечатление, что проектные интерфейсы — текущий код.

## Критерии завершения

- [ ] К1–К11 сняты правкой `контейнер-simulation-history` (шаг 2, шаг 7 пп. 1, 7)
- [ ] А1–А14 перечислены в плашке `архитектура…`, над §6 — плашка; текст разделов не тронут (шаг 7 п. 4); сигнатура `Simulator` совпадает с `simulator.py` базы (шаг 7 п. 8), при невлитом DEBT-053 — запись в его секции реестра (шаг 3)
- [ ] М1, М2 сняты (шаг 4)
- [ ] И1–И4 перечислены в плашке `модули-io-вывод`; эскизы и «config.py» не тронуты (шаг 7 п. 4)
- [ ] П1 снят (шаг 6)
- [ ] Каждое имя в плашках существует в коде, каждое «нет в коде» — отсутствует (шаг 7 п. 2)
- [ ] Wiki-ссылки разрешаются (шаг 7 п. 3)
- [ ] Число тестов равно baseline шага 1; код и тесты не менялись (шаг 7 пп. 5–6)
- [ ] Реестр: статус DEBT-052; issue #83 прокомментирован; закрывается при `/merge`

## Обнаруженные проблемы (не блокируют, не правятся в этой задаче)

1. **`vault/knowledge/decisions/модули-io-вывод.md:10-98`** — раздел «config.py» тоже эскиз проектного этапа: проверки в `__post_init__` dataclass-ов (в коде — функции `_validate`, `_validate_interval`, `io/config.py:334`), JSON-загрузка через `**data["section"]`. Детально не сверялся. Решение 3 пользователя: в DEBT-052 не трогать.
2. **`vault/knowledge/validation/матрица температурной задачи сверена с постановкой поэлементно.md:13-16, 84-96`** — замеры на дату заметки (2026-09-19): «по конфигам всех 12 примеров» (сейчас `ALL_EXAMPLES` — 22, `tests/test_energy_matrix_examples.py:58-81`); таблица «Верификация обратным ходом» — ошибка «$\Delta t$ из расписания» ловится «на 10, 11 — там, где есть дробление», «дробление 16×» на 11. После BUG-016 пример 11 не дробится (комментарий `test_energy_matrix_examples.py:770-771`, `SUBDIVIDING_EXAMPLES = ["10_deep_degassing"]`). Это запись эксперимента с датой, а не утверждение о текущем коде; правка не обязательна, возможна пометка «замеры на 2026-09-19».
3. **`[[architecture-numerical-solver]]`** — ссылка по полю `name:` frontmatter в 19 заметках `vault/knowledge/decisions/`. Файл называется `архитектура библиотеки numerical_solver.md`, поля `aliases` у него нет. Obsidian разрешает wiki-ссылки по имени файла или `aliases`, поэтому ссылка, вероятно, висячая — не проверено в Obsidian (настроек `.obsidian/` в `vault/` нет). Касается всего vault, не DEBT-052.

Регистрировать ли пп. 1–3 в реестре — решение пользователя.

## Оценка

5 файлов vault, ~70 строк правки (из них ~40 — `контейнер-simulation-history`), ~1 ч 20 мин с проверкой.
