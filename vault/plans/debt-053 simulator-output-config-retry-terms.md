---
tags:
  - план
  - удаление
date: 2026-10-10
issue: DEBT-053
github: 84
branch: refactor/debt-053/simulator-output-config-retry-terms
status: реализован
worktree: .worktrees/debt-053; удалён после влития
merged: 031d6d8 (2026-10-10)
audit:
  date: 2026-10-10
  found: 5
  auto-fixed: 5
  manual-required: 0
---

# DEBT-053: мёртвый `Simulator(output_config=...)` и термин «A-retry» в настоящем времени

Подтип: **удаление** (мёртвый параметр, избыточный тест) + правка комментариев. Расчётный код не меняется: числа всех расчётов побитово прежние.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Источник истины о дроблении шага — `numerical_solver/gpn_multiphase_solver/simulator.py:205-312` (`Simulator._advance`, комментарий «Локальное дробление (DEBT-015)»). Для справки (не править): `vault/knowledge/decisions/модули-simulator-оркестратор.md` (правится на шаге 5), `vault/knowledge/decisions/P4-адаптивный-шаг.md`.
3. Ветка `refactor/debt-053/simulator-output-config-retry-terms` от `numerical_scheme/implementation`, worktree `.worktrees/debt-053` (контракт `/implement`).
4. Venv: `numerical_solver/.venv/Scripts/python` (команды — из `numerical_solver/` worktree).
5. Baseline:
   - `.venv\Scripts\python -m pytest tests/ --collect-only -q` — **записать число**. На `d3aabff` (DEBT-049 влит; замер аудита 2026-10-10) — 1494. Критерий — «после = до − 1» (удаляется один тест), а не константа: к старту могут влить другие задачи.
   - `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` — записать число и время. На `d3aabff`: 1244 из 1494 в быстром уровне (сбор `-m "not slow"`), ~70 с.
6. Шаги 2–4 правят код и тесты; после каждого — быстрый уровень. Шаг 5 — vault. Полный прогон — в конце (`/implement`).

## Контекст

**`output_config`.** `Simulator.__init__` (`simulator.py:98-102`) принимает `output_config: OutputConfig | None = None`, но не сохраняет его и нигде не читает: атрибута `self._output_config` нет. Docstring (`:109`) обещает «параметры вывода (log_level, format)», комментарий (`:119-121`) — «output_config остаётся ради log_level и format, поэтому из сигнатуры не убирается». На деле:
- уровень журнала настраивает фабрика: `setup_logging(config.output.log_level)` (`factory.py:45`);
- `OutputConfig.format` не читает никто в пакете — это уже учтено в [[DEBT-008]] (`известные баги и технический долг.md:156, 167`) и охраняется тестом `tests/test_examples.py:202` (поле запрещено в конфигах примеров). В эту задачу поле `format` **не входит**.

Параметр остался после удаления `save_every` в [[DEBT-013]]: план DEBT-013 (`vault/plans/debt-013 remove-save-every.md:682`) прямо запретил удалять его «ради log_level» — но `Simulator` и тогда `log_level` не читал.

**«A-retry».** Так назывался механизм равномерного дробления внутри гидро-адаптера: при отказе Ньютона весь шаг пересчитывался на 2, 4, 8, … равных подшагах. [[DEBT-015]] (#61, `e684ee2`) его удалил: теперь адаптер только сообщает отказ (`HydroConvergenceError`), а шаг дробит `Simulator._advance` **локально** — делится пополам только не сошедшийся подшаг, после удачи подшаг растёт ×2 с выравниванием; подшаги имеют вид $dt/2^k$, но внутри одного шага могут быть разными. Комментарии части тестов и один скрипт примера по-прежнему пишут «при A-retry …» в настоящем времени, а два docstring говорят, что шаг дробит «гидро».

**Замер при планировании (2026-10-10, `d0a8c05`).** `tests/test_dt_convergence.py:35` утверждает, что в примере 07 при dt = 1200, 720, 450, 400 с «срабатывает A-retry». Проба `vault/issues/debt-053/probes/splitting_ex07.py` (постановка `_run_first_interval` теста + обёртка-счётчик вызовов энергии), вывод — `splitting_ex07.out.txt`:

| dt, с | шагов на интервал 3600 с | вызовов энергии | наименьший dt | дробление |
|---|---|---|---|---|
| 1800 | 2 | 2 | 1800 | нет |
| 1200 | 3 | 3 | 1200 | нет |
| 900 | 4 | 4 | 900 | нет |
| 720 | 5 | 5 | 720 | нет |
| 600 | 6 | 6 | 600 | нет |
| 450 | 8 | 8 | 450 | нет |
| 400 | 9 | 9 | 400 | нет |
| 360 | 10 | 10 | 360 | нет |

Шаг примера 07 не дробится **ни на одном** dt из `DT_LIST`. Почему дробление исчезло — не выяснялось: BUG-016, BUG-020, BUG-021 сняли его и в примерах 11, 12, 13b, 16 (`test_energy_matrix_examples.py:770-777`); для задачи это не нужно.

Следствие: `test_retry_steps_match_their_neighbours` (`test_dt_convergence.py:99-115`) заявляет «прямую проверку механизма BUG-010 при дроблении», а дробления в его сценарии нет. Кроме того, он **логически следует** из соседнего `test_temperature_converges_monotonically_in_dt` (`:63-80`): тот требует $e(dt_{fine}) \le 1.5\,e(dt_{coarse})$ для каждой пары соседей по убыванию $dt$; у каждого из четырёх dt (1200, 720, 450, 400) есть более крупный сосед (1800, 900, 600, 450), поэтому $e(dt) \le 1.5\,e(\text{крупнее}) \le 2\max(\text{соседи})$ — ровно условие удаляемого теста. Если зелёный тест на монотонность, удаляемый не может упасть.

Механизм BUG-010 (энергия идёт по подшагам гидродинамики) проверяют другие тесты, их не трогать:
- `tests/test_simulator.py:471` — `TestEnergySubstepsUnderRetry::test_energy_steps_match_hydro_substeps` (двойник гидродинамики, точные списки dt вызовов);
- `tests/test_energy_matrix_examples.py:788` — `test_energy_substeps_preserve_total_time` на примере 10 (живой конфиг, где дробление есть; проверяет и сумму dt, и сам факт дробления).

## Решения пользователя (2026-10-10, при планировании)

1. `output_config` — **удалить** из сигнатуры `Simulator`, вызова фабрики и заметки vault (вариант А1 issue #84).
2. `test_retry_steps_match_their_neighbours` и константу `DT_WITH_RETRY` — **удалить**; комментарии модуля переписать по замеру.

## Текущее и целевое состояние

| Место | Сейчас | После |
|---|---|---|
| `simulator.py:30` | `from .io.config import OutputConfig` | строки нет |
| `simulator.py:101` | параметр `output_config` | параметра нет; `max_retries` — шестой |
| `simulator.py:109` | строка docstring про `output_config` | строки нет |
| `simulator.py:119-121` | «output_config остаётся ради log_level и format» | «output_config удалён (DEBT-053): не читался, журнал настраивает фабрика» |
| `factory.py:77` | `output_config=config.output` | аргумента нет |
| `test_dt_convergence.py:26-37` | «A-retry срабатывает», `DT_WITH_RETRY` | история BUG-010 + замер DEBT-053 + где проверяется механизм |
| `test_dt_convergence.py:99-115` | `test_retry_steps_match_their_neighbours` | теста нет |
| `test_energy_matrix_examples.py:547, 620-622, 747, 792-793, 820` | «при A-retry», «гидро … раздробило» | «локальное дробление (DEBT-015)», «Simulator раздробил» |
| `test_rate_control.py:107` | «A-retry не раздробил шаги» | «Simulator не раздробил шаги (локальное дробление, DEBT-015)» |
| `closed_form_convergence.py:72` | «Глубина дробления шага в A-retry» | «Глубина локального дробления шага (DEBT-015)» |
| `модули-simulator-оркестратор.md:25, 39-41` | сигнатура с `output_config`, абзац «принимает, но не читает» | сигнатура без него, абзац об удалении |
| `архитектура библиотеки numerical_solver.md`, плашка (только если DEBT-052 влит раньше) | `Simulator(…, output_config=None, max_retries=9)` | `Simulator(grid, hydro, energy, pvt, schedule, max_retries=9)` |

Число тестов: −1 (только удаляемый тест). Import graph: `simulator.py` перестаёт импортировать `io.config`; `io.config` по-прежнему импортирует фабрика (`factory.py`), циклов не возникает (удаление импорта цикл создать не может).

## Зона неприкосновенности

- Расчётный код: тело `Simulator._advance`, `run`, адаптер, решатель энергии — ни строки.
- `OutputConfig` и поле `format` в `io/config.py` — [[DEBT-008]].
- Верные упоминания A-retry в прошедшем времени: `simulator.py:230, 246`, `tests/test_simulator.py:525`, `tests/test_prototype_phase_switching.py:286`, `tests/test_energy_matrix_examples.py:768`.
- `simulator.py:219-222` — «замерено −1.39 К против −0.06 К при дроблении, пример 07 при dt = 450 с»: исторический замер BUG-010 в прошедшем времени, обоснование правила. Не править, хотя сейчас пример 07 при 450 с не дробится.
- Имя класса `TestEnergySubstepsUnderRetry` (`test_simulator.py:468`) и параметр `max_retries`: «retry» здесь — повтор подшага, что верно и для локального дробления.
- Заметки vault, кроме `модули-simulator-оркестратор.md`, — [[DEBT-052]] (см. «Обнаруженные проблемы»).
- `vault/issues/val-005/probes/impl/numerical_solver/tests/test_dt_convergence.py` — копия в пробе другой задачи, не трогать.
- Исторические планы (`vault/plans/debt-013…`, `debt-015…`, `debt-050…`, `bug-010…`) — не трогать.

## Анализ вариантов

### `output_config`

| Вариант | Суть | Плюсы | Минусы |
|---|---|---|---|
| **А1 (выбран)** | удалить параметр, docstring, импорт, аргумент фабрики | сигнатура честная; diff 5 строк кода | формально меняется API конструктора; внешних пользователей нет |
| А2 | оставить, исправить docstring и комментарий | сигнатура не меняется | мёртвый параметр остаётся без причины |
| А3 | перенести `setup_logging` в `Simulator` | параметр начинает работать | глобальный побочный эффект в конструкторе: каждый тест, создающий `Simulator`, перенастраивал бы журнал |

### `test_dt_convergence.py`

| Вариант | Суть | Плюсы | Минусы |
|---|---|---|---|
| **Б-удалить (выбран)** | удалить тест и `DT_WITH_RETRY`, переписать комментарии | убирает ложное утверждение и избыточную проверку | −1 тест |
| Б-переименовать | `DT_BUG010_ANOMALIES`, `test_former_anomaly_dt_match_their_neighbours` | число тестов прежнее | тест остаётся логически избыточным |
| Б-текст | только комментарии | минимальный diff | «retry» в именах продолжает вводить в заблуждение |

## Чеклист подводных камней

- ✅ **Все места вызова найдены.** Grep `Simulator(` по `numerical_solver/` без прототипа: `factory.py:75` (единственный с `output_config`), `tests/test_output.py:67`, `tests/test_mass_balance.py:80, 143, 166, 183`, `tests/test_val001.py:185`, `tests/test_simulator.py` (≈20 мест, все по 5 позиционных; `:464` — `**kw` с единственным ключом `max_retries`). Позиционно больше пяти аргументов не передаёт никто — сдвиг `max_retries` на шестое место вызовов не ломает.
- ✅ **Зависимости пакетов** — не меняются.
- ✅ **Обратная совместимость API** — внутри проекта вызывающих с `output_config`, кроме фабрики, нет. Примеры (`examples/`) создают `Simulator` только через `SimulatorFactory` (grep `Simulator(` по `examples/` — 0 совпадений).
- ✅ **Состояние при ошибке** — не затрагивается.
- ✅ **Тесты.** Удаляемый тест — единственный, ссылающийся на `DT_WITH_RETRY` (grep по репозиторию без `.worktrees/`, `vault/issues/`). Фикстура `errors` от `DT_WITH_RETRY` не зависит — время модуля не меняется.
- ✅ **Циклические импорты** — удаление импорта цикл создать не может.
- ✅ **Docstrings / `\eqref{}`** — не затрагиваются.
- ✅ **Конфиги** — `output.log_level`, `output.format` в JSON не меняются: `OutputConfig` остаётся.
- ⚠️ **Связь с другими задачами.**
  - [[DEBT-049]] влит (`d94f9e8`): менял `io/config.py`, `tests/test_config.py` и заметки P8 — с файлами DEBT-053 не пересекается; сдвинул baseline (1481 → 1494) и импорт `OutputConfig` в `test_config.py` (`:21` → `:22`). Учтено в «Как начать» и шаге 1.
  - [[DEBT-052]] (#83, план `vault/plans/debt-052 history-step-notes-sync.md`) правит четыре другие заметки, `модули-simulator-оркестратор.md` не трогает; конфликта файлов нет. Порядок влития важен: шаг 3 плана DEBT-052 пишет в плашку `архитектура библиотеки numerical_solver.md` сигнатуру `Simulator` по коду на момент своей реализации — если DEBT-053 ещё не влит, **с** `output_config=None`, и оставляет пометку в секции DEBT-053 реестра. Адресовано: шаг 5, п. 5 и итоговый grep `output_config` по `vault/knowledge` (шаг 6).
  - [[BUG-022]] (план `vault/plans/bug-022 newton-cell-relative-tolerance.md`) правит `factory.py` в сборке модели прототипа (`:429-441`) — далеко от вызова `Simulator` (`:75-78`); слияние без конфликта.
  - [[DEBT-048]] (план готов) правит комментарии `test_energy_matrix_examples.py:685` и `:778-782` — в 9 строках от правки DEBT-053 `:791-794`. Блоки не перекрываются, но кто вливается вторым — сверить docstring `test_energy_substeps_preserve_total_time` после слияния. `simulator.py` DEBT-048 не правит.
- ✅ **Производительность** — не меняется.
- ✅ **Прототип** — не меняется; тесты и регрессия прототипа не нужны.

## Шаги

### Шаг 1: Подготовка и baseline

**Цель:** зафиксировать число тестов и исходные совпадения grep.

**Файлы:** —

**Что сделать** (из `numerical_solver/` worktree):
1. `.venv\Scripts\python -m pytest tests/ --collect-only -q` — записать число (на `d3aabff` — 1494, см. «Как начать», п. 5).
2. `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` — записать число passed и время.
3. Grep (инструмент Grep, путь `numerical_solver`, исключить `HydroSolverPrototype/**`):
   - `output_config|OutputConfig` — ожидается: `simulator.py:30, 101, 109, 120`, `factory.py:77`, `io/config.py` (166, 188, 307, 319, 321), `tests/test_config.py:22`, `tests/test_output.py:23`;
   - `A-retry` — ожидается 15 строк: `test_dt_convergence.py:28, 35, 100, 113`, `simulator.py:230, 246`, `test_energy_matrix_examples.py:547, 620, 747, 768, 820`, `test_rate_control.py:107`, `test_simulator.py:525`, `test_prototype_phase_switching.py:286`, `closed_form_convergence.py:72`.
   Если номера строк сдвинулись — искать по цитатам из шагов ниже, не по номерам.

**Проверка:** числа записаны.

**Оценка:** ~3 минуты.

### Шаг 2: Удалить `output_config` из `Simulator` и фабрики

**Цель:** сигнатура `Simulator` без мёртвого параметра.

**Файлы:** `numerical_solver/gpn_multiphase_solver/simulator.py`, `numerical_solver/gpn_multiphase_solver/factory.py`

**Контекст:** см. раздел «Контекст». `Simulator` параметр не хранит и не читает; журнал настраивает `factory.py:45`.

**Изменения:**

`simulator.py:30` — удалить строку:
```python
from .io.config import OutputConfig
```

`simulator.py:98-122` — до:
```python
    def __init__(self, grid: Grid, hydro: HydroSolver,
                 energy: EnergySolver, pvt: HydroPVT,
                 schedule: TimeSchedule,
                 output_config: OutputConfig | None = None,
                 max_retries: int = 9):
        """
        grid          — пространственная сетка (immutable, общая для всех модулей)
        hydro         — гидродинамический солвер (ABC: PrototypeHydroAdapter, ...)
        energy        — тепловой солвер (ABC: TridiagEnergySolver, ...)
        pvt           — PVT-модель (для rho_o_std, rho_g_std в WellData)
        schedule      — расписание: интервалы + шаг интегрирования
        output_config — параметры вывода (log_level, format), опционально
        max_retries   — глубина дробления шага: наименьший подшаг
                        dt/2**max_retries (numerics.max_retries, DEBT-015)
        """
        self._grid = grid
        self._hydro = hydro
        self._energy = energy
        self._pvt = pvt
        self._schedule = schedule
        self._max_retries = int(max_retries)
        # save_every удалён (DEBT-013): состав истории определяет только
        # структура time.history. output_config остаётся ради log_level
        # и format, поэтому из сигнатуры не убирается.
```
После:
```python
    def __init__(self, grid: Grid, hydro: HydroSolver,
                 energy: EnergySolver, pvt: HydroPVT,
                 schedule: TimeSchedule,
                 max_retries: int = 9):
        """
        grid          — пространственная сетка (immutable, общая для всех модулей)
        hydro         — гидродинамический солвер (ABC: PrototypeHydroAdapter, ...)
        energy        — тепловой солвер (ABC: TridiagEnergySolver, ...)
        pvt           — PVT-модель (для rho_o_std, rho_g_std в WellData)
        schedule      — расписание: интервалы + шаг интегрирования
        max_retries   — глубина дробления шага: наименьший подшаг
                        dt/2**max_retries (numerics.max_retries, DEBT-015)
        """
        self._grid = grid
        self._hydro = hydro
        self._energy = energy
        self._pvt = pvt
        self._schedule = schedule
        self._max_retries = int(max_retries)
        # save_every удалён (DEBT-013): состав истории определяет только
        # структура time.history. output_config удалён (DEBT-053): Simulator
        # его не читал — уровень журнала задаёт фабрика (setup_logging).
```
Выравнивание docstring оставить прежним (колонка «—» на 23-й позиции): строки `grid` … `max_retries` не трогать, только удалить строку `output_config`.

`factory.py:75-78` — до:
```python
        simulator = Simulator(
            grid=grid, hydro=hydro, energy=energy, pvt=pvt,
            schedule=schedule, output_config=config.output,
            max_retries=config.numerics.max_retries)
```
После:
```python
        simulator = Simulator(
            grid=grid, hydro=hydro, energy=energy, pvt=pvt,
            schedule=schedule, max_retries=config.numerics.max_retries)
```

**Проверка после шага:**
- Grep `output_config` по `numerical_solver/gpn_multiphase_solver` — 1 совпадение (новый комментарий `simulator.py`); по `numerical_solver/tests`, `numerical_solver/examples` — 0.
- Grep `OutputConfig` по `numerical_solver/gpn_multiphase_solver/simulator.py` — 0.
- Регресс: быстрый. Ожидание — число passed как в baseline (поведение не меняется).

**Подводные камни:** вызовы с позиционным `max_retries` — нет (чеклист, п. 1).

**Зависимости:** требует шаг 1.

**Оценка:** ~6 строк, ~5 минут.

### Шаг 3: `test_dt_convergence.py` — удалить избыточный тест, переписать комментарии

**Цель:** модуль не утверждает дробления, которого нет, и не держит логически избыточную проверку.

**Файлы:** `numerical_solver/tests/test_dt_convergence.py`

**Контекст:** замер при планировании (таблица в «Контексте»): шаг примера 07 не дробится ни на одном dt из `DT_LIST`. Удаляемый тест следует из `test_temperature_converges_monotonically_in_dt`. История BUG-010 (dt = 1200, 720, 450, 400 с, ошибка до 0.48 К) уже записана в docstring этого теста (`:66-69`) и `test_no_dt_deviates_from_linear_trend` (`:87`) — при удалении она не теряется.

**Изменения:**

`:26-37` — до:
```python
# Пример 07: mu_JT = 0, L_degas = 0, lambda = 0 — в энергии работают
# только конвекция и адиабатический член. Табличный PVT: именно на нём
# A-retry срабатывает и проявлялся BUG-010.
CONFIG = (Path(__file__).parent.parent / "examples"
          / "07_degassing_adiabatic_only" / "config.json")

DT_REF = 50.0          # эталон: 72 подшага на интервал 3600 с
DT_LIST = [1800.0, 1200.0, 900.0, 720.0, 600.0, 450.0, 400.0, 360.0]

# Аномальные до фикса dt (n_sub = 3, 5, 8, 9 — там срабатывает A-retry).
# Именно они выбивались из тренда в 6–24 раза.
DT_WITH_RETRY = [1200.0, 720.0, 450.0, 400.0]
```
После:
```python
# Пример 07: mu_JT = 0, L_degas = 0, lambda = 0 — в энергии работают
# только конвекция и адиабатический член. Табличный PVT: на нём проявлялся
# BUG-010 — при dt = 1200, 720, 450, 400 с гидродинамика дробила шаг,
# а энергия шла одним шагом, и ошибка выбивалась из тренда в 6–24 раза.
# Замер DEBT-053 (2026-10-10, vault/issues/debt-053/probes/): сейчас шаг
# примера 07 не дробится ни при одном dt из DT_LIST, поэтому здесь
# проверяется только сходимость T по dt. Сам механизм (энергия идёт по
# подшагам гидродинамики) проверяют test_simulator.py
# (test_energy_steps_match_hydro_substeps, двойник) и
# test_energy_matrix_examples.py (test_energy_substeps_preserve_total_time,
# пример 10).
CONFIG = (Path(__file__).parent.parent / "examples"
          / "07_degassing_adiabatic_only" / "config.json")

DT_REF = 50.0          # эталон: 72 подшага на интервал 3600 с
DT_LIST = [1800.0, 1200.0, 900.0, 720.0, 600.0, 450.0, 400.0, 360.0]
```

`:99-115` — удалить метод целиком (вместе с пустой строкой перед ним, чтобы класс не кончался двумя пустыми строками):
```python
    def test_retry_steps_match_their_neighbours(self, errors):
        """Шаги с A-retry не хуже соседних без него.
        ...
                f"не сработало")
```
Класс `TestTemperatureConvergenceInDt` после правки кончается методом `test_no_dt_deviates_from_linear_trend`.

Модульный docstring (`:1-15`) и docstring двух оставшихся тестов не трогать: они в прошедшем времени и верны.

**Проверка после шага:**
- Grep `A-retry|DT_WITH_RETRY|retry_steps` по `numerical_solver/tests/test_dt_convergence.py` — 0.
- `.venv\Scripts\python -m pytest tests/test_dt_convergence.py -q` — 2 passed.
- Регресс: быстрый. Ожидание — passed на 1 меньше baseline; `--collect-only -q` — на 1 меньше.

**Подводные камни:** не удалить вместе с методом фикстуру `errors` (она нужна двум оставшимся тестам).

**Зависимости:** требует шаг 1; от шага 2 не зависит.

**Оценка:** −17 строк, +8 строк, ~5 минут.

### Шаг 4: Термин «A-retry» в тестах и примере 05

**Цель:** комментарии, docstring и сообщения `assert` описывают текущий механизм.

**Файлы:** `numerical_solver/tests/test_energy_matrix_examples.py`, `numerical_solver/tests/test_rate_control.py`, `numerical_solver/examples/05_standing_table_rp/closed_form_convergence.py`

**Контекст:** после [[DEBT-015]] шаг дробит `Simulator._advance` локально, подшаги вида $dt/2^k$ могут быть разными внутри одного шага; гидродинамика только сообщает отказ.

**Изменения:**

`test_energy_matrix_examples.py:546-547` — до:
```python
    # Накопительный член [Вт/К]. Δt — ФАКТИЧЕСКИЙ шаг, с которым
    # собрана матрица (при A-retry это dt_sub, а не шаг расписания).
```
После:
```python
    # Накопительный член [Вт/К]. Δt — ФАКТИЧЕСКИЙ шаг, с которым
    # собрана матрица (при локальном дроблении, DEBT-015, это подшаг,
    # а не шаг расписания).
```

`test_energy_matrix_examples.py:620-622` — до:
```python
    dt — фактический шаг вызова, НЕ шаг расписания: при A-retry Simulator
    дробит интервал и вызывает solve с dt_sub = dt/n_sub (BUG-010), а
    cap = V·(ρcp)/dt зависит именно от dt_sub.
```
После:
```python
    dt — фактический шаг вызова, НЕ шаг расписания: при локальном дроблении
    (DEBT-015) Simulator вызывает solve с подшагом h = dt/2**k (BUG-010),
    а cap = V·(ρcp)/dt зависит именно от h.
```

`test_energy_matrix_examples.py:747` — до:
```python
# B. Дробление шага энергии при A-retry
```
После:
```python
# B. Энергия по подшагам локального дробления (DEBT-015)
```

`test_energy_matrix_examples.py:791-794` — до:
```python
    Физика: расщепление «гидро → энергия» имеет порядок O(dt) и применимо
    лишь там, где устойчивы обе половины. Если гидро признало шаг слишком
    крупным и раздробило его, энергия обязана пройти те же подшаги
    (BUG-010). Инвариант, который это фиксирует, — сохранение времени:
```
После:
```python
    Физика: расщепление «гидро → энергия» имеет порядок O(dt) и применимо
    лишь там, где устойчивы обе половины. Если гидродинамика не сошлась и
    Simulator раздробил шаг, энергия обязана пройти те же подшаги
    (BUG-010). Инвариант, который это фиксирует, — сохранение времени:
```

`test_energy_matrix_examples.py:819-821` — до:
```python
    assert dt_min < dt_max, (
        f"{example}: ожидалось дробление A-retry, но все вызовы прошли "
        f"с одинаковым dt={dt_max:g} с — конфиг или гидродинамика изменились")
```
После:
```python
    assert dt_min < dt_max, (
        f"{example}: ожидалось локальное дробление шага, но все вызовы прошли "
        f"с одинаковым dt={dt_max:g} с — конфиг или гидродинамика изменились")
```

`test_rate_control.py:106-108` — до:
```python
    По образцу _CountingEnergySolver (test_simulator.py). Нужна, чтобы
    убедиться, что A-retry не раздробил шаги: при разном дроблении двух
    прогонов их совпадение не обязано выполняться.
```
После:
```python
    По образцу _CountingEnergySolver (test_simulator.py). Нужна, чтобы
    убедиться, что Simulator не раздробил шаги (локальное дробление,
    DEBT-015): при разном дроблении двух прогонов их совпадение не обязано
    выполняться.
```

`examples/05_standing_table_rp/closed_form_convergence.py:72` — до:
```python
    # Глубина дробления шага в A-retry — см. GRIDS.
```
После:
```python
    # Глубина локального дробления шага (DEBT-015) — см. GRIDS.
```

Не трогать: `test_energy_matrix_examples.py:768` («при глубине 1 побитово как прежний A-retry» — прошедшее время, верно).

**Проверка после шага:**
- Grep `A-retry` по `numerical_solver` (без `HydroSolverPrototype/**`) — ровно 5 строк, все в прошедшем времени: `simulator.py:230, 246`, `test_simulator.py:525`, `test_prototype_phase_switching.py:286`, `test_energy_matrix_examples.py` (бывшая `:768`, после правки `:769` — сдвиг на одну строку от `:547`).
- Grep `гидро признало|гидродинамика дробит` по `numerical_solver/tests` — 0.
- `.venv\Scripts\python -m py_compile examples\05_standing_table_rp\closed_form_convergence.py` — без вывода (сам скрипт не запускать: правка — комментарий, прогон — минуты).
- Регресс: быстрый. Ожидание — как после шага 3. `test_energy_substeps_preserve_total_time` и `test_rate_control.py` — в быстром уровне (сбор `-m "not slow"` их включает).

**Подводные камни:** текст сообщения `assert` (`:820`) виден только при падении — проверить глазами строку после правки.

**Зависимости:** требует шаг 1.

**Оценка:** ~20 строк, ~10 минут.

### Шаг 5: Vault

**Цель:** заметка оркестратора и реестр согласованы с кодом.

**Файлы:** `vault/knowledge/decisions/модули-simulator-оркестратор.md`, `vault/roadmap/известные баги и технический долг.md`; если влит DEBT-052 — `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md` (п. 5)

**Что сделать:**

1. `модули-simulator-оркестратор.md:22-26` — из блока кода удалить строку `                 output_config: OutputConfig | None = None,`. После:
   ```python
       def __init__(self, grid: Grid, hydro: HydroSolver,
                    energy: EnergySolver, pvt: HydroPVT,
                    schedule: TimeSchedule,
                    max_retries: int = 9):
   ```
2. `модули-simulator-оркестратор.md:39-41` — до:
   ```
   output_config Simulator принимает, но не сохраняет и не читает (после
   DEBT-013 — только ради сигнатуры); уровень журнала задаёт фабрика
   (`setup_logging(config.output.log_level)`).
   ```
   После:
   ```
   Параметр output_config удалён в [[DEBT-053]]: Simulator его не читал;
   уровень журнала задаёт фабрика (`setup_logging(config.output.log_level)`).
   ```
3. Grep `output_config` по заметке — только в новой фразе; если в разделе о фабрике есть вызов `Simulator(...)` с `output_config` — убрать (на `d0a8c05` такого нет: grep дал только `:25`, `:39`).
4. Реестр, запись DEBT-053: статус и итог — по контракту `/implement`.
5. **Если к старту влит [[DEBT-052]]** (`git log --oneline numerical_scheme/implementation | Select-String "DEBT-052"`): его плашка в `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md` может содержать `Simulator(grid, hydro, energy, pvt, schedule, output_config=None, max_retries=9)` — план DEBT-052 пишет так, если DEBT-053 не влит, и оставляет пометку в секции DEBT-053 реестра. Убрать `output_config=None, ` из сигнатуры: `Simulator(grid, hydro, energy, pvt, schedule, max_retries=9)`. Пометку DEBT-052 в секции DEBT-053 реестра отметить выполненной.

**Проверка:** сигнатура в заметке побитно совпадает с `simulator.py` после шага 2 (имена, типы, умолчания). Grep `output_config` по `vault/knowledge` — только новая фраза в `модули-simulator-оркестратор.md` (на `d3aabff` до правки: `:25`, `:39` этой заметки). Регресс: `--collect-only -q` (только документ).

**Зависимости:** требует шаг 2.

**Оценка:** ~5 строк, ~5 минут.

### Шаг 6: Итоговая проверка

**Что сделать:**
1. Полный прогон `.venv\Scripts\python -m pytest tests/ -q` (контракт `/implement`). Ожидание: все зелёные, число = baseline − 1. Истории примеров (фикстура `results`) не меняются — расчётный код не затронут.
2. Итоговые grep (шаги 2–5): `output_config` в пакете — только комментарий `simulator.py`; `output_config` в `vault/knowledge` — только фраза об удалении в `модули-simulator-оркестратор.md`; `A-retry` — 5 строк в прошедшем времени; `DT_WITH_RETRY` в `numerical_solver/` — 0.

**Оценка:** ~10 минут (полный прогон).

## Тестовая стратегия

Новых тестов нет: задача удаляет мёртвый параметр, логически избыточный тест и правит текст.

**Регрессия (существующие тесты, покрывают затронутый код):**
- `tests/test_simulator.py` — 20+ конструкций `Simulator` без `output_config`, в том числе `_retry_run` с `max_retries` по имени; `TestFactory` (`:229`) — сборка через `SimulatorFactory.from_config` (ловит опечатку в вызове `factory.py:75-78`).
- `tests/test_examples.py`, `tests/test_energy_matrix_examples.py`, `tests/test_rate_control.py`, `tests/test_dt_convergence.py`, `tests/test_val001.py`, `tests/test_mass_balance.py`, `tests/test_output.py` — все создают `Simulator` фабрикой или напрямую.

**Удаляемый тест:**
- **Тест:** `TestTemperatureConvergenceInDt::test_retry_steps_match_their_neighbours`
- **Файл:** `numerical_solver/tests/test_dt_convergence.py` (существующий)
- **Почему безопасно:** его условие $e(dt) \le 2\max(\text{соседи})$ для dt = 1200, 720, 450, 400 с следует из условия `test_temperature_converges_monotonically_in_dt` ($e(dt) \le 1.5\,e(\text{крупнее})$); заявленный механизм (дробление) в сценарии не возникает — замер `vault/issues/debt-053/probes/splitting_ex07.out.txt`.
- **Что остаётся на месте:** механизм BUG-010 — `test_simulator.py:471`, `test_energy_matrix_examples.py:788`; симптом BUG-010 (скачок ошибки T при отдельных dt) — два оставшихся теста `test_dt_convergence.py`. Все они и `test_rate_control.py` — в быстром уровне (сбор `-m "not slow"` на `d3aabff`: 15 из 15).

**Код плана проверен подстановкой при аудите** (`vault/issues/debt-053/probes/audit_apply_plan.py`, вывод — `audit_apply_plan.out.txt`): 11 блоков «до:» найдены в файлах ровно по одному разу; правки тестов и примера не меняют AST (без строковых констант); `test_dt_convergence.py` после правки = исходный − `DT_WITH_RETRY` − тест; итоговые grep — `A-retry` 5 строк (`:769` вместо `:768`), `output_config` в пакете 1; пропатченные `simulator.py` + `factory.py` считают пример 07 (первый интервал) и пример 10 побитово как исходные, при `max_retries = 0` на 10 — тот же `RuntimeError` (передача `max_retries` фабрикой не сломана).

## Критерии завершения

- [ ] Шаги 1–6 выполнены.
- [ ] Полный прогон зелёный; тестов на 1 меньше baseline.
- [ ] `Simulator.__init__` без `output_config`; `simulator.py` не импортирует `OutputConfig`; `factory.py` не передаёт его.
- [ ] `A-retry` в `numerical_solver/` (без прототипа) — только 5 строк в прошедшем времени.
- [ ] `DT_WITH_RETRY`, `test_retry_steps_match_their_neighbours` — 0 совпадений в `numerical_solver/`.
- [ ] Заметка `модули-simulator-оркестратор.md` — сигнатура и абзац по коду; если влит DEBT-052 — плашка `архитектура библиотеки numerical_solver.md` без `output_config` (`output_config` в `vault/knowledge` — только фраза об удалении).
- [ ] Реестр: статус DEBT-053; issue #84 прокомментирован (`05-comment-done.md`), закрывается при `/merge`.
- [ ] Прототип не менялся.

## Связь формула → код

Не применимо: формулы и расчётный код не меняются.

## Обнаруженные проблемы

1. **[[DEBT-052]] — сигнатура `Simulator` в `архитектура библиотеки numerical_solver.md`.** Тело issue #83 (`vault/issues/debt-052/01-issue-body.md:33`) писало сигнатуру с `output_config`. План DEBT-052 учёл DEBT-053: шаг 3 берёт сигнатуру по коду на момент реализации, при невлитом DEBT-053 оставляет пометку в его секции реестра. Обратная сторона — шаг 5, п. 5 этого плана. Записано и в реестр DEBT-052 (поле «Добавлено при планировании DEBT-053»).
2. **`vault/knowledge/decisions/P8-формат-ввода-json.md:199`** — «A-retry их не использует: глубина дробления задаётся `max_retries`» — настоящее время, вне заметок DEBT-052. Утверждение по существу верно и для локального дробления, устарел только термин. Не блокирует; добавлено в реестр DEBT-052 и вошло в его план (шаг 6, строка прочитана на `d3aabff` — после правок P8 в DEBT-049).
3. **Причина исчезновения дробления в примере 07** (dt = 1200, 720, 450, 400 с, до DEBT-015 дробились) не выяснялась. Для этой задачи не нужна: удаляемый тест избыточен при любом ответе. В реестр не заносится.

Новых записей в реестре не создано: пп. 1–2 дополняют существующую [[DEBT-052]].

## Связанные заметки

- Реестр: `vault/roadmap/известные баги и технический долг.md` — DEBT-053, DEBT-052, DEBT-050, DEBT-015, DEBT-013, DEBT-008
- [[модули-simulator-оркестратор]]
- [[P4-адаптивный-шаг]]
- [[энергия решается одним шагом там где гидро раздробило]] — расследование BUG-010
- Проба: `vault/issues/debt-053/probes/splitting_ex07.py`, `splitting_ex07.out.txt`
- Аудит: `vault/issues/debt-053/probes/audit_apply_plan.py`, `audit_apply_plan.out.txt` (работает только до реализации: ищет блоки «до:» в файлах)
