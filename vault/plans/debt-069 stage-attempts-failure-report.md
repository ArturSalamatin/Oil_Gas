---
tags:
  - план
  - рефакторинг
date: 2026-10-14
issue: DEBT-069
github: 118
branch: refactor/debt-069/stage-attempts-failure-report
status: в процессе
worktree: .worktrees/debt-069
audit:
  date: 2026-10-14
  found: 7
  auto-fixed: 6
  manual-required: 1   # длина строки попыток — решено пользователем 2026-10-14: формат оставить
---

# DEBT-069: отчёт `advance` перечисляет попытки ступеней — ветка «открыта» ступеней 2–4 больше не теряется

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай связанные заметки:
   - запись DEBT-069 в `vault/roadmap/известные баги и технический долг.md` (и DEBT-030, DEBT-054 там же);
   - `vault/knowledge/debugging/отказ Ньютона только по условию ячейки выглядел обычным — отчёт называет допуск, меру и причину выхода.md` (DEBT-054: поля отчёта и хвост текста отказа);
   - `vault/knowledge/decisions/P1-адаптер-единицы.md`, раздел 6, абзац «Текст `HydroConvergenceError` (DEBT-054)»;
   - замеры этого плана: `vault/issues/debt-069/probes/` (`bug018.out.txt`, `example19.out.txt`, `example21.out.txt`, `t04_attempts.out.txt`, `histories_save_before.out.txt`).
3. Ветка `refactor/debt-069/stage-attempts-failure-report` от `numerical_scheme/implementation` в worktree `.worktrees/debt-069` (делает `/implement`). Проверка базы: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`.
4. Python: `<PY>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe` — venv один, в основном каталоге; в worktree своего `.venv` нет. Все команды — `<PY>` из каталога worktree (`<W>\numerical_solver` или `<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3`). pytest берёт код worktree (`pythonpath` в `numerical_solver/pyproject.toml`, DEBT-059). Пробы — **скриптом основного каталога** (`<ROOT>\vault\issues\debt-069\probes\…`, `<ROOT>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas`) из `<W>\numerical_solver`: код берётся из каталога запуска (`SOLVER = Path.cwd()`, путь печатается — проверить, что это worktree); истории `hist_*.npz` пишутся рядом со скриптом (в git не идут, в worktree их нет).
5. Baseline (из `<W>\numerical_solver`), база `8e432a3` (код планируемых файлов — как у `0eeaa42` и `6adea25`; после `6adea25` влиты DEBT-066 — только `.tex` — и DEBT-068 — `_validate` конфига):
   - `<PY> -m pytest tests/ --collect-only -q` — ожидается **1938**;
   - `<PY> -m pytest tests/ -m "not slow" -q` — ожидается **1662 passed**, ~70 с;
   - прототип, из `<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3`: `<PY> -m pytest tests -q` — **101 passed**; `<PY> regression\run_regression.py --quick` — **11/11 PASS**.

   Если база ушла дальше и числа другие — разобрать причину до правки. **Параллельно идёт реализация BUG-028** (`_advance_phases` прототипа, CHANGELOG, докстринг модуля `blackoil.py`) и готов план DEBT-067 (условие по ячейке, правит те же тесты `test_prototype_failure_diagnostics.py`, комментарий `prototype_adapter.py:118-121`, CHANGELOG). Если одна из них влита до начала:
   - числа реальных проверок этого плана (раздел 2.1) от них не зависят (обоснование — 2.5, п. 9); всё равно повторить пробы: `<PY> <ROOT>\vault\issues\debt-069\probes\attempts_probe.py bug018` из `<W>\numerical_solver` и `<PY> <ROOT>\vault\issues\debt-069\probes\t04_attempts.py` из `<W>\…\Prototype_1.0.3` — попытки должны совпасть с таблицей 2.1.

   Обе пробы берут решатель и прототип из каталога запуска и печатают пути — проверить, что это worktree. Без этого установленный `radial_blackoil` указывает на основной каталог (аудит 1: из worktree `import radial_blackoil` без `PYTHONPATH` даёт основной каталог).
6. Запомни числа и время быстрого уровня. Начни с шага 0. После каждого шага — проверка по полю «Регресс»; полный прогон и полная регрессия прототипа — шаг 4.

## Резюме

Когда ступень 1 `advance` (исходный алгоритм) не решает шаг, прототип пробует до трёх запасных ступеней, а при управлении по забойному давлению каждая из них — до двух веток скважины. Каждая следующая попытка затирает отчёт предыдущей, и при общем отказе подмена DEBT-030 оставляет числа ступени 1. Причина отказа ветки «открыта» ступеней 2–4 теряется. Замер: из 7 попыток в тексте отказа видна одна.

**Решения пользователя (2026-10-14):**
1. Поле `attempts` заполняется, **как только ступень 1 не решила шаг** — и у отказа, и у шага, принятого ступенями 2–4. Пусто, если шаг решила ступень 1: почти все шаги, их отчёт побитово прежний.
2. Текст отказа: **все попытки**; у ветки, которая сошлась, но несогласована (выход `branch`), — только число итераций.
3. `run_summary.json` и `step_log.csv` прототипа **не трогать**.
4. Находку пробы — ветка «открыта» ступени 2 побитово повторяет ступень 1 — **зарегистрировать отдельной DEBT** (DEBT-072, раздел «Обнаруженные проблемы»).

**Решение плана (технический выбор, не пользовательский):** запись попытки — `StageAttempt(stage, branch, report)` (NamedTuple), где `report` — копия (`dataclasses.replace`) отчёта попытки на момент её окончания. Новый тип с копией всех полей Ньютона вместо плоской записи из 11 полей: ничего не дублируется, все поля DEBT-054/055 (допуск, мера, предел) доступны потребителю.

Числа решения не меняются: только копии отчётов и список. Ожидания: истории 5 сценариев (в четырёх — отказы, в примере 16 — шаги ступени 4 без отказов) побитово, тексты отказов без новой строки — побуквенно прежние, регрессия прототипа 11/11 и 17/17 PASS побитово.

## 1. Контекст

### 1.1. Подтип

Рефакторинг диагностики (улучшение отчёта): одно новое поле отчёта прототипа, одна функция текста в адаптере. Шаблон «Рефакторинг» в упрощённом виде: подготовка → ядро (прототип) + тесты → текст (адаптер) + тесты → документы → проверка.

### 1.2. Как устроен `advance` сейчас (база `8e432a3`)

`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`:

| Строки | Что |
|---|---|
| `:16-17` | докстринг модуля: «DEBT-030: when all **three** stages of advance() fail…» — устарело с BUG-020, ступеней четыре |
| `:34-43` | докстринг модуля, абзацы DEBT-054, BUG-025, DEBT-055 — новый абзац DEBT-069 ставится после `:43` |
| `:45` | `from dataclasses import dataclass, replace` |
| `:58-87` | `BlackOilNewtonReport` — последнее поле `cell_floor` (`:87`) |
| `:462-520` | `advance`: ступень 1 (`_advance_phases`, `:470`), ступень 2 (`_fallback`, `:481`), ступень 3 (`_fallback` с `_line_search_l2`, `_sg_step_max`, `:489-495`), ступень 4 (`advance_fourth_stage`, `:496-503`), подмена DEBT-030 (`:504-519`) |
| `:521-537` | `advance_fourth_stage`: `_fallback` с `_phase_switching = True` |
| `:538-579` | `_fallback`: управление по дебиту — одна попытка (`:545-547`); по давлению — ветки по очереди (`:561-577`), возврат отчёта **последней** ветки |

Ступени различаются флагами модели в момент вызова `_advance_phases`:

| Ступень | `_sg_lower_bound` | `_line_search_l2` | `_phase_switching` | `_well_branch` |
|---|---|---|---|---|
| 1 | −0.05 | False | False | None (ветка — по $p[0]$ приближения, `:209-210`) |
| 2 | None | False | False | 'open' / 'shut' (управление по давлению) или None |
| 3 | None | True | False | то же |
| 4 | None | False | True | то же |

Порядок веток в `_fallback`: первой — ветка старого состояния (`'shut'`, если $p[0]^{old} \le p_{wf}$, иначе `'open'`, `:550`), затем другая, один раз. «Открыта» не пробуется, если не может быть согласована (`open_hopeless`, DEBT-040, `:560`).

Адаптер `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`:
- `_EXIT_REASONS` (`:65-73`) — перевод `exit_reason`;
- `_failure_details` (`:76-126`) — хвост текста отказа; кончается «; числа — Ньютона ступени {stage}» (`:126`);
- текст `HydroConvergenceError` (`:246-251`);
- докстринг модуля, абзац «Текст отказа (DEBT-054)» (`:32-36`).

`Simulator._failure_message` (`numerical_solver/gpn_multiphase_solver/simulator.py:377-411`) дописывает текст адаптера в конец своего текста («Последний отказ гидродинамики: …»); `dev_log.debug` (`:319`) пишет его при каждом отказе подшага. Начало текста `Simulator` цитируют README примеров 03, 05, 06, 07, 10 — оно не меняется.

### 1.3. Потребители отчёта (кто читает поля)

| Потребитель | Что читает | Затрагивается? |
|---|---|---|
| `simulation.py:23-26` `_grow_dt` прототипа | `iterations` принятого шага | нет: `iterations` не меняется |
| `simulation.py:83`, `:99` журнал шагов прототипа | `iterations`, `active_set_iterations`, `phase_switches`, `residual_inf` | нет: поля перечислены явно |
| `runner.py:87-91` блок `failure` в `run_summary.json` | те же 4 поля | нет (решение 3) |
| адаптер `:234-252` | `converged`, `iterations`, `residual_inf`, поля DEBT-054/055 (при отказе), `phase_switching` (при успехе) | да: новая строка в конце текста отказа |
| тесты GPN | `SimpleNamespace`-отчёты в `test_prototype_adapter.py:839`, `test_prototype_stage4_memory.py:138` | нет: поле читается через `getattr(…, "attempts", ())` |

Сравнений отчётов целиком (`==`, `asdict`) в `numerical_solver/` нет (grep `asdict|astuple` и `rep… == rep…` — пусто).

## 2. Анализ

### 2.1. Замеры (база `0eeaa42`, код планируемых файлов = `8e432a3`)

Проба `vault/issues/debt-069/probes/attempts_probe.py` перехватывает `_advance_phases` на экземпляре модели — как подмены тестов DEBT-030. Каждый вызов — одна попытка; ступень определяется по флагам из таблицы 1.2. `t04_attempts.py` — то же для первого шага T04 прототипа.

**BUG-018, $N$ = 350, шаг 86400 с** (`bug018.out.txt`; сценарий `test_real_total_failure_only_cell_test`):

| Ступень | Ветка | Выход | Итераций | Проходов | Переключений | Невязка |
|---|---|---|---|---|---|---|
| 1 | — | `line_search` | 4 | 1 | 0 | 6.51e-15 |
| 2 | открыта | `line_search` | 4 | 1 | 0 | 6.51e-15 |
| 2 | закрыта | сошлась, $p[0]$ = 469 > 50 → `branch` | 0 | 1 | 0 | 0 |
| 3 | открыта | `line_search` | 4 | 1 | 0 | 6.51e-15 |
| 3 | закрыта | → `branch` | 0 | 1 | 0 | 0 |
| 4 | открыта | `max_iter` | 40 | 1 | 1101 | 1.82e+01 |
| 4 | закрыта | → `branch` | 0 | 1 | 0 | 0 |

Отчёт `advance`: `line_search`, 4 итерации, ветка `'shut'`, 1 смена. Ступень 2 «открыта» — **побитово** ступень 1: состояние и все числа отчёта.

**Пример 19, первый шаг** (`example19.out.txt`):
- $\Delta t$ = 1 с: ступени 1, 2 «открыта», 3 «открыта» — `active_set` (31/31/29 итераций, 12 проходов, 364 переключения); 4 «открыта» — `max_iter` (40, 424 переключения); три «закрыта» — `branch`. Ступень 2 «открыта» — побитово ступень 1.
- $\Delta t$ = 120 с: ступень 2 «открыта» отказывает иначе, чем ступень 1 (`max_iter`, 15 итераций, 2 прохода против `active_set`, 29 итераций, 12 проходов).

**Пример 21, $\Delta t$ = 30 с** (`example21.out.txt`): ступени 1–3 отказывают, ступень 4 «открыта» сходится (31 итерация) — шаг принят. Ступень 2 «открыта» — те же три знака чисел, что у ступени 1, но не побитово.

**T04 прототипа, 60 с** (`t04_attempts.out.txt`; `phase_switching_stage = False`):

| Ступень | Ветка | Выход | Итераций | Проходов | Переключений | Невязка |
|---|---|---|---|---|---|---|
| 1 | — | `max_iter` | 15 | 2 | 21 | 2.35e-07 |
| 2 | открыта | `max_iter` | 15 | 2 | 21 | 2.35e-07 |
| 2 | закрыта | → `branch` | 0 | 1 | 0 | 0 |
| 3 | открыта | `max_iter` | 15 | 2 | 21 | 3.67e-05 |
| 3 | закрыта | → `branch` | 0 | 1 | 0 | 0 |

Отчёт `advance` — ступени 1 (15, 2.35e-07, 2, 21), ветка `'shut'`, 1 смена. Nabor_1b тем же шагом решает ступень 1: сошлась, `fallback` False, 12 итераций.

**Длина строки попыток** (черновики пробы, сокращения «ит.», «пр.»): все 7 попыток полностью — 590–626 символов; «закрыта» кратко — ~470; без «закрыта» — ~340. Выбран второй вариант (решение 2). В формате плана (2.4) — 579–613 (аудит 1).

**Истории сценариев с отказами** (`histories.py save before`, `histories_save_before.out.txt`, ~70 с):

| Сценарий | Вызовов гидро | Отказов |
|---|---|---|
| BUG-018, $N$ = 350 | 5 | 2 |
| пример 14 | 362 | 1 |
| пример 16 | 735 | 0 (ступень 4 принимает шаги — `attempts` у принятых) |
| пример 17 | 745 | 5 |
| суточный останов rs300 | 27 | 7 (ступень 4 по памяти) |

### 2.2. Целевое состояние

- `blackoil.py`: тип `StageAttempt(stage, branch, report)`; поле `BlackOilNewtonReport.attempts: tuple = ()`.
- `_fallback(…, stage=2)` записывает каждую ветку: копию её отчёта на момент окончания. Ветка, где Ньютон сошёлся, но $p[0]$ противоречит ветке, записывается как отказ с выходом `branch` — так же, как отчёт последней ветки сейчас. Возвращаемый отчёт несёт `attempts` всех веток этого вызова.
- `advance`: после отказа ступени 1 собирает попытки по порядку (ступень 1 + попытки каждого `_fallback`) и ставит их на возвращаемый отчёт — принятый ступенями 2–4 или общий отказ (в подмене DEBT-030 — тоже). Ступень 1 решила шаг — `attempts == ()`.
- `advance_fourth_stage` (вызывается и адаптером напрямую, DEBT-048): попытки своих веток с `stage = 4`.
- Адаптер: `_attempts_text(report)` — строка «; попытки ступеней: [1 — …; 2 открыта — …; 2 закрыта — ветвь скважины несогласована (итераций 0); …]» в конце текста `HydroConvergenceError`, после хвоста DEBT-054. Прежний текст — начало нового.
- Не меняются: числа и последовательность шагов, подмена DEBT-030, `_grow_dt`, журнал шагов, `run_summary.json`, начало текстов отказа.

### 2.3. Варианты

**Вариант 1 (выбран; рекомендация issue, решения 1–3 пользователя).** Поле `attempts` в отчёте + строка в тексте адаптера. Поле — кортеж `StageAttempt`.
- Подварианты записи:
  - (1а, выбран) `StageAttempt(stage, branch, report)`, `report` — копия отчёта попытки;
  - (1б) плоская запись из 11 полей (дублирует поля отчёта; при следующем поле отчёта — правка в двух местах).
- Где собирать:
  - (выбран) `_fallback` отдаёт попытки своих веток на возвращаемом отчёте, `advance` склеивает;
  - (отвергнут) список на экземпляре модели (`self._attempts`): изменяемое состояние модели между вызовами; DEBT-048 держится на том, что ступень 4 — функция $(state_{old}, \Delta t, \text{управление})$;
  - (отвергнут) третий элемент возврата `_fallback`: ломает 2 теста, вызывающих его напрямую (`test_prototype_failure_diagnostics.py:238`, `:250`), и 3 места в коде.
- Номер ступени передаётся в `_fallback` ключевым аргументом `stage=2` (явно), а не выводится из флагов: флаги ставят `advance` и `advance_fourth_stage`, им номер и известен.
- Промежуточные состояния: шаг 1 (прототип) — тексты прежние, все тесты зелёные; шаг 2 (адаптер) — новая строка.
- Риски: конфликты слияния с BUG-028/DEBT-067 (докстринг модуля, CHANGELOG, тесты) — механические (2.5, п. 9).

**Вариант 2.** Готовая строка в отчёте прототипа (`failure_note: str`). Отвергнут: английский текст прототипа рядом с русским адаптера, тесты на строки вместо полей, решение 1 (попытки у принятого шага) строкой не выразить.

**Вариант 3.** Повторный прогон ступеней в адаптере при отказе (как проба). Отвергнут: дублирует логику `advance`, удваивает стоимость отказа.

**Вариант 4.** `logging.debug` в `advance`. Отвергнут как основной: в текст отказа `Simulator` не попадает.

### 2.4. Формат строки попыток

`_attempts_text(report)` (адаптер):
- поля `attempts` нет или оно пусто → `""`;
- иначе `"; попытки ступеней: [" + "; ".join(записи) + "]"`. Квадратные скобки отделяют список от «;» хвоста DEBT-054;
- запись:
  - голова — `"{stage}"` или `"{stage} {открыта|закрыта}"` (ветка `''` — без слова);
  - сошлась → `"{голова} — сошлась (итераций {n})"` (только у принятого шага, в тексте отказа не встречается);
  - выход `branch` → `"{голова} — ветвь скважины несогласована (итераций {n})"` (решение 2: проходы, переключения и невязка сошедшегося решения причину не объясняют);
  - иначе → `"{голова} — {причина} (итераций {n}, проходов {a}, переключений {s}, невязка {r:.2e})"`; причина — `_EXIT_REASONS.get(code, code)`, при пустом коде (подставные отчёты тестов) — «отказ».

Формат чисел — как у начала текста («итераций 4, невязка 6.51e-15»): без склонений («1 проход / 12 проходов»). Отличие от превью, показанного пользователю («31 итер., 12 проходов»), — только оформление чисел; состав и порядок записей — по решению 2.

**Длина (аудит 1, замер `_attempts_text` на копии дерева):** 579 символов у примера 19 (1 с, 7 попыток) и 613 у BUG-018 ($N$ = 350). В превью было ≈470: слова «итераций», «проходов», «переключений» перед числами длиннее сокращений превью. Это длина варианта «все попытки полностью» из вопроса пользователю (590–626). Состав записей — по решению 2. **Решение пользователя 2026-10-14 (после аудита 1): формат оставить** — слова перед числами, как в начале текста отказа; длина 579–613 принята.

Пример (BUG-018, $N$ = 350; конец текста):
```
…; числа — Ньютона ступени 1; попытки ступеней: [1 — линейный поиск не принял ни одной точки (итераций 4, проходов 1, переключений 0, невязка 6.51e-15); 2 открыта — линейный поиск не принял ни одной точки (итераций 4, проходов 1, переключений 0, невязка 6.51e-15); 2 закрыта — ветвь скважины несогласована (итераций 0); 3 открыта — линейный поиск не принял ни одной точки (итераций 4, проходов 1, переключений 0, невязка 6.51e-15); 3 закрыта — ветвь скважины несогласована (итераций 0); 4 открыта — исчерпан лимит итераций (итераций 40, проходов 1, переключений 1101, невязка 1.82e+01); 4 закрыта — ветвь скважины несогласована (итераций 0)]
```

### 2.5. Подводные камни

| # | Пункт | Оценка | Комментарий |
|---|---|---|---|
| 1 | Все места вызова | ✅ | `_fallback`: `blackoil.py:481`, `:491`, `:533` + тесты `test_prototype_failure_diagnostics.py:238`, `:250` (позиционные 4 аргумента — `stage` по умолчанию 2). `advance_fourth_stage`: `advance` `:502`, адаптер `:231`, тесты `test_prototype_stage4_memory.py`. Подмены `_advance_phases` в тестах (`test_prototype_well_branch.py:118`, `test_prototype_phase_switching.py:376`, `test_prototype_open_branch_skip.py:152`, `test_prototype_globalization.py:177`, `:200`) возвращают настоящий `BlackOilNewtonReport` — `replace` работает (grep 2026-10-14) |
| 2 | Зависимости пакетов | ✅ | `typing.NamedTuple` — стандартная библиотека |
| 3 | Обратная совместимость | ✅ | Новое поле — последним, со значением по умолчанию: позиционные конструкторы тестов (до 5 аргументов) не меняются. `SimpleNamespace`-отчёты — `getattr(report, "attempts", ())` |
| 4 | Состояние при ошибке | ✅ | Исключение внутри ступени пробрасывается, как прежде; `finally` в `advance`, `advance_fourth_stage`, `_fallback` не меняются (`_assert_restored` тестов) |
| 5 | Тесты | ⚠️ | Меняется конец текста отказа: `test_prototype_failure_diagnostics.py:410` (`msg.endswith("; числа — Ньютона ступени 1")`) — правится в шаге 2. Прочие проверки текста — `startswith` или `match` начала (`test_prototype_adapter.py:843`, `test_prototype_stage4_memory.py:151`, `test_simulator.py`). `test_failure_details` (`:422-476`) — `_failure_details` не меняется |
| 6 | Циклы импорта | ✅ | Тест импортирует `StageAttempt` из `radial_blackoil.blackoil`, адаптер — ничего нового (поле читается через `getattr`) |
| 7 | Ссылки на уравнения | ✅ | Нет формул; в докстрингах и комментариях — только ID задач (`tests/test_eq_references.py` ищет номера уравнений) |
| 8 | Конфиги | ✅ | Не меняются |
| 9 | Другие задачи | ⚠️ | **BUG-028** (реализация начата, `b678a07`): меняет `_advance_phases` (счёт проходов), CHANGELOG, возможно докстринг модуля. Числа реальных проверок этого плана от неё не зависят: BUG-018 — отказ первого же Ньютона прохода 1; T04 — `max_iter` на проходе 2, проход 1 включает газ (считается и после BUG-028); шаг останова `test_bhp_shutin_step_without_open_branch` проверяется через `branches` теста, а не через числа. **DEBT-067** (план): вставляет `monkeypatch.setattr(blackoil, "CELL_FLOOR_KAPPA", 0.0)` в те же тесты (`test_real_total_failure_only_cell_test`, `test_adapter_message_cell_test_only`); при κ = 0 условие — прежнее строгое, попытки те же. Конфликты слияния — текстовые (докстринги, соседние строки тестов, конец CHANGELOG): сохранить обе стороны |
| 10 | Производительность | ✅ | `dataclasses.replace` на попытку — микросекунды против секунд Ньютона; у шага, решённого ступенью 1, — ничего |
| 11 | Прототип | ⚠️ | Меняется `radial_blackoil/blackoil.py`: тесты прототипа (101 → 103) и регрессия. Ожидание: **11/11 (`--quick`) и 17/17 (полная) PASS побитово** — числа не меняются, журнал шагов и `run_summary.json` перечисляют поля явно. FAIL — не пересъёмка эталона: разобрать, решение за пользователем. Перед полной регрессией зафиксировать HEAD |
| 12 | Длина текста | ⚠️ | До 7 записей: 579 символов на шаге 1 с примера 19, 613 у BUG-018 (замер аудита 1; превью обещало ≈470, см. 2.4). `dev_log.debug` пишет текст каждого отказа подшага — на уровне DEBUG строки станут длиннее; на уровне INFO не видны |
| 13 | Копия, а не сам отчёт | ✅ | В `attempts` — копии: возвращаемый отчёт не входит в собственный список (нет циклической ссылки), правки полей отчёта после записи (`rep.globalized = True`, подмена DEBT-030) копию не трогают. У копий `attempts == ()`. Флаги `fallback`, `globalized`, `phase_switching` копии выставлены не единообразно (ступень 3 ставит `globalized` после возврата `_fallback`) — ступень несёт `StageAttempt.stage`, об этом комментарий у типа |

### 2.6. Обнаруженные проблемы

1. **DEBT-072 (регистрируется при планировании, решение 4).** Ветка «открыта» ступени 2 отличается от ступени 1 только двумя вещами: снятой границей $S_g \ge -0.05$ (`_trial_is_reasonable`, `:416-417`) и веткой, зафиксированной на весь Ньютон (`:209-210`). Если в ступени 1 граница ни разу не отвергла пробную точку и $p[0]$ ни одного приближения не опустился до $p_{wf}$, ступень 2 «открыта» решает ту же задачу теми же операциями. Замер:
   - побитово — BUG-018 ($N$ = 350, сутки) и пример 19 (1 с);
   - те же три знака — пример 21 (30 с) и T04 (60 с);
   - отличается — пример 19 при 120 с.

   На отказавшем шаге это около четверти стоимости. Не блокирует. После DEBT-069 повтор виден в тексте отказа (записи «1 —» и «2 открыта —» совпадают).
2. Докстринг `test_real_total_failure_only_cell_test` (`test_prototype_failure_diagnostics.py:283-284`): «Ступень 4 отказала иначе (лимит 40, мера 3.6e7) — в отчёт не попадает (DEBT-030)». На `0eeaa42` мера — 2.93e7 (`bug018.out.txt`), и с DEBT-069 числа ступени 4 в отчёт попадают. Правится в шаге 1.
3. Докстринг модуля `blackoil.py:16` — «all three stages» (с BUG-020 ступеней четыре). Правится в шаге 1.

## 3. Шаги

### Шаг 0: Подготовка

**Цель:** зафиксировать исходное состояние в worktree до правки.

**Файлы:** нет правок.

**Что сделать:**
1. Baseline по п. 5 «Как начать» (1938 / 1662 passed / 101 passed / 11/11 PASS).
2. `git -C <W> log -1 --format=%h` — записать базу ветки.
3. Исходные истории — **всегда снять заново на коде worktree до правки**: из `<W>\numerical_solver` — `<PY> <ROOT>\vault\issues\debt-069\probes\histories.py save before > <ROOT>\vault\issues\debt-069\probes\histories_save_before.out.txt` (~70 с; печатает пути — должен быть worktree; перезаписывает `hist_*_before.npz` планирования). Почему не брать файлы планирования: они сняты в основном каталоге, где лежат незакоммиченные правки других сессий, и база может уйти дальше `8e432a3` (BUG-028). Записать число отказов по сценариям (на `0eeaa42`: 2, 1, 0, 5, 7 — всего 15) — его ждёт шаг 4.

**Проверка:** числа совпали с п. 5 или расхождение разобрано.

**Оценка:** ~15 мин (регрессия `--quick` ~8 мин).

### Шаг 1: Прототип — `StageAttempt`, поле `attempts`, сбор в `_fallback`, `advance`, `advance_fourth_stage`

**Цель:** отчёт `advance` несёт все попытки по порядку, как только ступень 1 не решила шаг.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_failure_report.py`
- `numerical_solver/tests/test_prototype_stage_attempts.py` (новый)
- `numerical_solver/tests/test_prototype_failure_diagnostics.py` (`test_real_total_failure_only_cell_test`, `:279-292`)
- `numerical_solver/tests/test_prototype_open_branch_skip.py` (`test_bhp_shutin_step_without_open_branch`, `:135-159`)

**Контекст:** таблица 1.2; решения 1, 4 «Резюме»; формат — 2.2. Прототип пишется в своём стиле: короткие имена, несколько операторов в строке через `;`, комментарии на английском.

**Что сделать:**

1. Импорт (`:45-46`). До:
   ```python
   from dataclasses import dataclass, replace
   import numpy as np
   ```
   После:
   ```python
   from dataclasses import dataclass, replace
   from typing import NamedTuple
   import numpy as np
   ```

2. Докстринг модуля, `:16-17`. До:
   ```
   DEBT-030: when all three stages of advance() fail, the report carries the Newton
   fields of the original algorithm, not those of the last fallback attempt.
   ```
   После:
   ```
   DEBT-030: when all stages of advance() fail, the report carries the Newton
   fields of the original algorithm, not those of the last fallback attempt.
   ```
   В конец докстринга модуля, после абзаца DEBT-055 (`:41-43`, перед закрывающими `"""` на `:44`):
   ```
   DEBT-069: once the original algorithm fails, the report of advance() lists every attempt
   in order (attempts: StageAttempt -- stage, BHP well branch, a copy of the attempt's report),
   accepted or not; a total failure no longer hides why the fallback stages failed.
   ```
   (Если BUG-028 уже дописал сюда свой абзац — ставить после него.)

3. Поле и тип — после `cell_floor: float | None = None` (`:87`). До:
   ```python
       cell_floor: float | None = None

   def _sg_activation_cap(relperm):
   ```
   После:
   ```python
       cell_floor: float | None = None
       # DEBT-069: every attempt of advance() (advance_fourth_stage()) in order, StageAttempt; set
       # on the report returned, accepted or not, once the original algorithm has failed; () when
       # it solved the step.  The copies inside carry no attempts of their own
       attempts: tuple = ()

   class StageAttempt(NamedTuple):
       """DEBT-069: one attempt of advance() -- stage 1-4, BHP well branch ('open'/'shut', '' without one), a copy of its report as it ended."""
       # The Newton fields of report (converged, iterations, residual_inf, active_set_iterations,
       # phase_switches, residual_tol, cell_measure, exit_reason, cell_floor) are the attempt's; a
       # Newton converged on an inconsistent BHP branch is recorded as failed with exit 'branch'.
       # Its fallback/globalized/phase_switching flags are not set uniformly -- the stage is here.
       stage: int
       branch: str
       report: BlackOilNewtonReport

   def _sg_activation_cap(relperm):
   ```

4. `advance` (`:462-520`). До:
   ```python
       def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):
           """One implicit step: the original algorithm; on failure a fallback with the
           BHP well branch as an outer constraint and no lower bound on Sg (BUG-014);
           if that fails too, the fallback again with a globalized Newton (BUG-016);
           if that fails too and phase_switching_stage is on, the fallback with phase
           switches inside Newton (BUG-020) -- advance_fourth_stage.
           If all stages fail, the report carries the original algorithm's Newton (DEBT-030),
           with its tolerance, per-cell measure and exit reason (DEBT-054)."""
           new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
           if rep.converged:
               if self.control_mode=='BHP':
                   # branch the automatic rule takes on the accepted state
                   p0=float(new.pressure_bar[0])
                   rep.well_branch='shut' if p0<=float(self.p_bhp_bar) else 'open'
               return new,rep
           orig=rep  # DEBT-030: reported if the fallback and the third stage fail too
           # Fallback only: where the original algorithm converges, results stay
           # bitwise; with the bound removed always, deep drawdowns needed more
           # step splitting than before (BUG-014 audit).
           new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
           if rep.converged: return new,rep
           # Third stage (BUG-016), ...
           # ... (комментарий :484-488 без изменений)
           self._line_search_l2=True; self._sg_step_max=0.2
           try:
               new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
               rep.globalized=True
           finally:
               self._line_search_l2=False; self._sg_step_max=None
           if rep.converged: return new,rep
           if self.phase_switching_stage:
               # Fourth stage (BUG-020), ...
               # ... (комментарий :497-501 без изменений)
               new,rep=self.advance_fourth_stage(state_old,dt_s,max_active_iter,max_newton)
               if rep.converged: return new,rep
           if not rep.converged:
               # DEBT-030: ...
               # ... (комментарий :505-514 без изменений)
               rep=replace(rep,iterations=orig.iterations,residual_inf=orig.residual_inf,
                           active_set_iterations=orig.active_set_iterations,
                           phase_switches=orig.phase_switches,
                           residual_tol=orig.residual_tol,cell_measure=orig.cell_measure,
                           exit_reason=orig.exit_reason,cell_floor=orig.cell_floor)
           return new,rep
   ```
   После (комментарии, помеченные «без изменений», — дословно прежние):
   ```python
       def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):
           """One implicit step: the original algorithm; on failure a fallback with the
           BHP well branch as an outer constraint and no lower bound on Sg (BUG-014);
           if that fails too, the fallback again with a globalized Newton (BUG-016);
           if that fails too and phase_switching_stage is on, the fallback with phase
           switches inside Newton (BUG-020) -- advance_fourth_stage.
           If all stages fail, the report carries the original algorithm's Newton (DEBT-030),
           with its tolerance, per-cell measure and exit reason (DEBT-054).
           Once the original algorithm fails, the report lists every attempt (DEBT-069)."""
           new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
           if rep.converged:
               if self.control_mode=='BHP':
                   # branch the automatic rule takes on the accepted state
                   p0=float(new.pressure_bar[0])
                   rep.well_branch='shut' if p0<=float(self.p_bhp_bar) else 'open'
               return new,rep
           orig=rep  # DEBT-030: reported if the fallback and the third stage fail too
           # DEBT-069: every attempt of this call in order -- the original algorithm, then each
           # branch of each fallback stage (_fallback lists its own); set on the report returned
           attempts=[StageAttempt(1,'',replace(orig))]
           # Fallback only: where the original algorithm converges, results stay
           # bitwise; with the bound removed always, deep drawdowns needed more
           # step splitting than before (BUG-014 audit).
           new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
           attempts+=rep.attempts
           if rep.converged: rep.attempts=tuple(attempts); return new,rep
           # Third stage (BUG-016), ...   (комментарий без изменений)
           self._line_search_l2=True; self._sg_step_max=0.2
           try:
               new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton,stage=3)
               rep.globalized=True
           finally:
               self._line_search_l2=False; self._sg_step_max=None
           attempts+=rep.attempts
           if rep.converged: rep.attempts=tuple(attempts); return new,rep
           if self.phase_switching_stage:
               # Fourth stage (BUG-020), ...   (комментарий без изменений)
               new,rep=self.advance_fourth_stage(state_old,dt_s,max_active_iter,max_newton)
               attempts+=rep.attempts
               if rep.converged: rep.attempts=tuple(attempts); return new,rep
           if not rep.converged:
               # DEBT-030: ...   (комментарий :505-514 без изменений)
               # DEBT-069: and every attempt, so the fallback stages' failures stay visible.
               rep=replace(rep,iterations=orig.iterations,residual_inf=orig.residual_inf,
                           active_set_iterations=orig.active_set_iterations,
                           phase_switches=orig.phase_switches,
                           residual_tol=orig.residual_tol,cell_measure=orig.cell_measure,
                           exit_reason=orig.exit_reason,cell_floor=orig.cell_floor,
                           attempts=tuple(attempts))
           return new,rep
   ```
   `attempts+=rep.attempts` — список расширяется кортежем (`list.extend`). Ступень 2 вызывает `_fallback` без `stage` (по умолчанию 2).

5. `advance_fourth_stage` (`:521-537`). До:
   ```python
       def advance_fourth_stage(self,state_old,dt_s,max_active_iter=12,max_newton=15):
           """The fourth stage of advance alone (BUG-020, DEBT-048): the BUG-014 fallback with
           phase switches inside Newton; its own report, also when it fails."""
           ...
           self._phase_switching=True
           try:
               new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
   ```
   После:
   ```python
       def advance_fourth_stage(self,state_old,dt_s,max_active_iter=12,max_newton=15):
           """The fourth stage of advance alone (BUG-020, DEBT-048): the BUG-014 fallback with
           phase switches inside Newton; its own report, also when it fails, with the attempts of
           its branches (DEBT-069)."""
           ...   (комментарий :524-530 без изменений)
           self._phase_switching=True
           try:
               new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton,stage=4)
   ```

6. `_fallback` (`:538-579`). До:
   ```python
       def _fallback(self,state_old,dt_s,max_active_iter,max_newton):
           """BUG-014 fallback: no lower bound on Sg; BHP control fixes the well branch
           (start from the old state's branch, accept a consistent result only, try the
           other branch once, 'open' only where it can be consistent, DEBT-040);
           OIL_RATE control: a plain retry without the Sg bound."""
           self._sg_lower_bound=None
           try:
               if self.control_mode!='BHP':
                   new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                   rep.fallback=True; return new,rep
               target=float(self.p_bhp_bar)
               ...   (:549-560 без изменений)
               tried=[]
               while True:
                   tried.append(branch); self._well_branch=branch
                   new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                   rep.fallback=True; rep.well_branch=branch; rep.well_switches=len(tried)-1
                   if rep.converged:
                       p0=float(new.pressure_bar[0])
                       # open: q = WI*lambda*(p0-target) >= 0; shut: p0 <= target
                       if (p0>=target) if branch=='open' else (p0<=target): return new,rep
                   # Newton failed or the branch is inconsistent: the other branch, once
                   other='open' if branch=='shut' else 'shut'
                   if other in tried or (other=='open' and open_hopeless):
                       # DEBT-054: a Newton that converged on an inconsistent branch failed by the
                       # branch, not by the Newton; a failed Newton keeps its own exit reason
                       if rep.converged: rep.exit_reason='branch'
                       rep.converged=False; return new,rep
                   branch=other
           finally:
               self._sg_lower_bound=-0.05; self._well_branch=None
   ```
   После:
   ```python
       def _fallback(self,state_old,dt_s,max_active_iter,max_newton,stage=2):
           """BUG-014 fallback: no lower bound on Sg; BHP control fixes the well branch
           (start from the old state's branch, accept a consistent result only, try the
           other branch once, 'open' only where it can be consistent, DEBT-040);
           OIL_RATE control: a plain retry without the Sg bound.
           The report lists every branch tried as StageAttempt(stage, ...) (DEBT-069)."""
           self._sg_lower_bound=None
           try:
               if self.control_mode!='BHP':
                   new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                   # DEBT-069: one attempt, no well branch
                   rep.fallback=True; rep.attempts=(StageAttempt(stage,'',replace(rep)),); return new,rep
               target=float(self.p_bhp_bar)
               ...   (:549-560 без изменений)
               tried=[]; attempts=[]
               while True:
                   tried.append(branch); self._well_branch=branch
                   new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                   rep.fallback=True; rep.well_branch=branch; rep.well_switches=len(tried)-1
                   consistent=False
                   if rep.converged:
                       p0=float(new.pressure_bar[0])
                       # open: q = WI*lambda*(p0-target) >= 0; shut: p0 <= target
                       consistent=(p0>=target) if branch=='open' else (p0<=target)
                   # DEBT-069: every branch tried, as it ended; a Newton converged on an inconsistent
                   # branch is recorded as failed with exit 'branch', as the report returned below
                   snap=replace(rep) if consistent or not rep.converged else replace(rep,converged=False,exit_reason='branch')
                   attempts.append(StageAttempt(stage,branch,snap)); rep.attempts=tuple(attempts)
                   if consistent: return new,rep
                   # Newton failed or the branch is inconsistent: the other branch, once
                   other='open' if branch=='shut' else 'shut'
                   if other in tried or (other=='open' and open_hopeless):
                       # DEBT-054: a Newton that converged on an inconsistent branch failed by the
                       # branch, not by the Newton; a failed Newton keeps its own exit reason
                       if rep.converged: rep.exit_reason='branch'
                       rep.converged=False; return new,rep
                   branch=other
           finally:
               self._sg_lower_bound=-0.05; self._well_branch=None
   ```
   Логика возврата прежняя: `consistent` — то же условие, что прежний `if`; выход по `consistent` — тот же `return new,rep`. Новое — только `snap` и `rep.attempts`.

7. Тесты прототипа — `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_failure_report.py`. В класс `FailureReportTests` после `test_total_failure_reports_original_newton` добавить (стиль файла — `unittest`, комментарии на английском):
   ```python
       def test_total_failure_lists_attempts(self):
           # DEBT-069: the report lists every attempt in order.  T04 (BHP 100 bar, p_ext = 200 bar,
           # the old p0 = 200 > 100: 'open' first): stage 1; stages 2 and 3 -- 'open' fails by the
           # iteration limit, 'shut' "converges" in 0 iterations on the unchanged state and is
           # dropped as inconsistent ('branch').  Measured (GPN vault/issues/debt-069/probes/
           # t04_attempts.out.txt): stage 1 and stage 2 'open' 15 iterations, 2 passes, 21 switches.
           _,m,s=model_and_state(n=100,bhp=100.0,p0=200.0,case=T04)
           _,rep=m.advance(s,60.0)
           self.assertFalse(rep.converged)
           self.assertEqual([(a.stage,a.branch) for a in rep.attempts],
                            [(1,''),(2,'open'),(2,'shut'),(3,'open'),(3,'shut')])
           self.assertEqual([a.report.exit_reason for a in rep.attempts],
                            ['max_iter','max_iter','branch','max_iter','branch'])
           self.assertEqual([a.report.iterations for a in rep.attempts],[15,15,0,15,0])
           self.assertFalse(any(a.report.converged for a in rep.attempts))
           # the first attempt is the original algorithm whose Newton fields the report carries (DEBT-030)
           first=rep.attempts[0].report
           self.assertEqual((first.iterations,first.residual_inf,first.active_set_iterations,first.phase_switches),
                            (rep.iterations,rep.residual_inf,rep.active_set_iterations,rep.phase_switches))
           # copies: no attempts of their own
           self.assertTrue(all(a.report.attempts==() for a in rep.attempts))

       def test_accepted_original_has_no_attempts(self):
           # DEBT-069: where the original algorithm solves the step the report has no attempts
           # (the Nabor_1b fixture converges on this step: 12 iterations, no fallback)
           _,m,s=model_and_state(n=100,bhp=100.0,p0=200.0)
           _,rep=m.advance(s,60.0)
           self.assertTrue(rep.converged); self.assertFalse(rep.fallback)
           self.assertEqual(rep.attempts,())
   ```
   Комментарий в начале файла (`:4-10`) дополнить строкой: `# DEBT-069: the report also lists every attempt of the fallback stages (attempts).`

8. Новый файл `numerical_solver/tests/test_prototype_stage_attempts.py` — логика на подменах (текст адаптера добавит шаг 2):
   ```python
   """DEBT-069: отчёт advance перечисляет попытки ступеней — ступень, ветка, копия отчёта.

   При отказе всех ступеней отчёт несёт числа Ньютона ступени 1 (DEBT-030), а поля ветки —
   последней попытки. Отчёт ветки «открыта» ступеней 2–4 затирался отчётом «закрыта»
   (0 итераций на неизменном состоянии, отвергнута как несогласованная), и причину отказа
   этих ступеней в BUG-028 нашла только отдельная проба. Теперь, как только ступень 1 не
   решила шаг, отчёт несёт attempts — все попытки по порядку (StageAttempt: ступень, ветка,
   копия отчёта); текст отказа адаптера заканчивается строкой попыток.

   План: vault/plans/debt-069 stage-attempts-failure-report.md; замеры —
   vault/issues/debt-069/probes/ (attempts_probe.py, t04_attempts.py).
   """

   from radial_blackoil.blackoil import BlackOilNewtonReport

   # Подмена _advance_phases с ключом (ветка, граница S_g, ||F||_2): у каждой ступени свой отчёт
   from .test_prototype_globalization import ORIG3, ORIG_REPORT, _install_fake_reports
   # Подмена с ключом (ветка, граница, ||F||_2, ступень 4); отчёт (сошлась, its, невязка its)
   from .test_prototype_phase_switching import (
       OPEN, OPEN3, OPEN4, ORIG, SHUT, SHUT3, SHUT4, _install_fake_phases)
   # Модель Nabor_1b (p_ext = 200 бар) и состояние после часа отбора при 100 бар (p[0] = 111.7)
   from .test_prototype_well_branch import _build, _model, drawn_down  # noqa: F401


   def _key(a):
       """(ступень, ветка) попытки."""
       return (a.stage, a.branch)


   # ═══════════════════════════════════════════════════════════
   # A. Сбор попыток в advance и _fallback (подмена _advance_phases)
   # ═══════════════════════════════════════════════════════════

   class TestAttemptsOnFakeStages:
       """Модель p_wf = 150 бар, drawn_down (p[0] = 111.7 < 150): ветки стартуют с «закрыта»."""

       def test_original_converged_no_attempts(self, drawn_down):
           # Шаг решила ступень 1 (почти все шаги) — попыток нет, отчёт побитово прежний
           model = _model(150.0)
           _install_fake_reports(model, {ORIG3: (151.0, BlackOilNewtonReport(True, 3, 1e-15))})
           _, rep = model.advance(drawn_down, 3600.0)
           assert rep.converged and rep.attempts == ()

       def test_total_failure_lists_every_attempt(self, drawn_down):
           # Отказ трёх ступеней (флаг ступени 4 выключен). Ступени 2 и 3: «закрыта» не сошлась,
           # «открыта» сошлась за 0 итераций, но p[0] = 140 < 150 — несогласована, записана
           # отказом 'branch'. До DEBT-069 отчёт «закрыта» ступеней 2 и 3 терялся.
           model = _model(150.0)
           calls = _install_fake_reports(model, {
               ORIG3: (0.0, ORIG_REPORT),
               ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7,
                                                                 exit_reason="max_iter")),
               ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0,
                                                                   exit_reason="converged")),
               ("shut", None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9,
                                                                exit_reason="line_search")),
               ("open", None, True): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0,
                                                                  exit_reason="converged"))})
           _, rep = model.advance(drawn_down, 3600.0)
           # По попытке на каждый вызов _advance_phases, в том же порядке
           assert len(rep.attempts) == len(calls) == 5
           assert [_key(a) for a in rep.attempts] == [
               (1, ""), (2, "shut"), (2, "open"), (3, "shut"), (3, "open")]
           assert [a.report.exit_reason for a in rep.attempts] == [
               "", "max_iter", "branch", "line_search", "branch"]
           assert [a.report.iterations for a in rep.attempts] == [15, 14, 0, 13, 0]
           assert not any(a.report.converged for a in rep.attempts)
           # Подмена DEBT-030 прежняя: поля Ньютона — ступени 1 (ORIG_REPORT: 15, 2.5e-7, 2, 21)
           assert (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                   rep.phase_switches) == (15, 2.5e-7, 2, 21)
           # Копии: своих попыток нет (нет вложенности), с возвращённым отчётом не связаны
           assert all(a.report.attempts == () and a.report is not rep for a in rep.attempts)

       def test_rate_control_one_attempt_per_stage(self):
           # Управление по дебиту: запасной путь без ветки — по попытке на ступень, ветка ''
           model, state = _build(150.0)
           model.set_oil_rate_control(2.0, 100.0)
           _install_fake_reports(model, {
               ORIG3: (0.0, ORIG_REPORT),
               (None, None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
               (None, None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9))})
           _, rep = model.advance(state, 60.0)
           assert [_key(a) for a in rep.attempts] == [(1, ""), (2, ""), (3, "")]
           assert [a.report.iterations for a in rep.attempts] == [15, 14, 13]

       def test_accepted_third_stage_carries_attempts(self, drawn_down):
           # Решение пользователя 2026-10-14: попытки — как только ступень 1 не решила шаг,
           # и у принятого шага. Ступень 3 сошлась на «закрыта» (p[0] = 149 <= 150 —
           # согласована): последняя попытка — принятая; поля отчёта — её собственные (17)
           model = _model(150.0)
           _install_fake_reports(model, {
               ORIG3: (0.0, ORIG_REPORT),
               ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
               ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0)),
               ("shut", None, True): (149.0, BlackOilNewtonReport(True, 17, 2.0e-16, 2, 15))})
           _, rep = model.advance(drawn_down, 3600.0)
           assert rep.converged and rep.iterations == 17
           assert [_key(a) for a in rep.attempts] == [(1, ""), (2, "shut"), (2, "open"), (3, "shut")]
           assert [a.report.converged for a in rep.attempts] == [False, False, False, True]
           assert rep.attempts[2].report.exit_reason == "branch"

       def test_all_four_stages(self, drawn_down):
           # Флаг ступени 4 включён, отказ везде: семь попыток, у ступеней 2–4 — обе ветки
           model = _model(150.0)
           model.phase_switching_stage = True
           plan = {k: (False, 0.0, 9) for k in (SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4)}
           plan[ORIG] = (False, 0.0, 15)
           _install_fake_phases(model, plan)
           _, rep = model.advance(drawn_down, 3600.0)
           assert [_key(a) for a in rep.attempts] == [
               (1, ""), (2, "shut"), (2, "open"), (3, "shut"), (3, "open"), (4, "shut"), (4, "open")]
           assert [a.report.iterations for a in rep.attempts] == [15, 9, 9, 9, 9, 9, 9]

       def test_fourth_stage_alone(self, drawn_down):
           # advance_fourth_stage (ступень 4 по памяти адаптера, DEBT-048): только её ветки
           model = _model(150.0)
           _install_fake_phases(model, {SHUT4: (False, 0.0, 40), OPEN4: (False, 0.0, 40)})
           _, rep = model.advance_fourth_stage(drawn_down, 3600.0)
           assert not rep.converged
           assert [_key(a) for a in rep.attempts] == [(4, "shut"), (4, "open")]

       def test_hopeless_open_not_listed(self, drawn_down):
           # p_wf = 210 > p_ext = 200 >= max p_old (drawn_down): «открыта» не пробуется (DEBT-040)
           # и в попытках её нет — видно, что ступени 2–4 пробовали только «закрыта»
           model = _model(210.0)
           model.phase_switching_stage = True
           _install_fake_phases(model, {k: (False, 0.0, 3)
                                        for k in (ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4)})
           _, rep = model.advance(drawn_down, 3600.0)
           assert [_key(a) for a in rep.attempts] == [(1, ""), (2, "shut"), (3, "shut"), (4, "shut")]
   ```

9. `numerical_solver/tests/test_prototype_failure_diagnostics.py`, `test_real_total_failure_only_cell_test` (`:279-292`). Докстринг, строки `:283-284`. До:
   ```
       невязка 6.51e-15 при допуске 5.36e-7, мера 2.60e-8 > 1e-8. Ступень 4 отказала иначе
       (лимит 40, мера 3.6e7) — в отчёт не попадает (DEBT-030).
   ```
   После:
   ```
       невязка 6.51e-15 при допуске 5.36e-7, мера 2.60e-8 > 1e-8. Ступень 4 отказала иначе
       (лимит 40 итераций, 1101 переключение фаз): в числа отчёта не попадает (DEBT-030),
       видна в попытках (DEBT-069; vault/issues/debt-069/probes/bug018.out.txt).
   ```
   В конец тела (после `assert rep.cell_measure > CELL_TOL`):
   ```python
       # DEBT-069: все попытки по порядку. Ступени 2 и 3 «открыта» — побитово ступень 1
       # (граница S_g не сработала, ветка не менялась — DEBT-072); «закрыта» на неизменном
       # состоянии сходится за 0 итераций при p[0] = 469 > 50 бар — несогласована
       assert [(a.stage, a.branch) for a in rep.attempts] == [
           (1, ""), (2, "open"), (2, "shut"), (3, "open"), (3, "shut"), (4, "open"), (4, "shut")]
       assert [a.report.exit_reason for a in rep.attempts] == [
           "line_search", "line_search", "branch", "line_search", "branch", "max_iter", "branch"]
       assert [a.report.iterations for a in rep.attempts] == [4, 4, 0, 4, 0, 40, 0]
   ```
   (Если DEBT-067 влита раньше, в начале тела будет её `monkeypatch.setattr(blackoil, "CELL_FLOOR_KAPPA", 0.0)` — при κ = 0 попытки те же.)

10. `numerical_solver/tests/test_prototype_open_branch_skip.py`, `test_bhp_shutin_step_without_open_branch` (`:135-159`): в конец тела:
    ```python
        # DEBT-069: принятый ступенью 4 шаг несёт все попытки — по одной на вызов
        # _advance_phases с теми же ветками; решила последняя
        assert [a.branch or None for a in rep.attempts] == branches
        assert [a.stage for a in rep.attempts] == [1, 2, 3, 4]
        assert rep.attempts[-1].report.converged
        assert not any(a.report.converged for a in rep.attempts[:-1])
    ```
    Проверка через `branches` теста, а не через числа: если BUG-028 изменит исход ступеней 2–3 на этом шаге, тест поправят вместе с `branches`, а связь «попытка = вызов» останется.

**Проверка после этого шага:**
- Регресс: быстрый — `<PY> -m pytest tests/ -m "not slow" -q` из `<W>\numerical_solver`: **1669 passed** (1662 + 7 новых), `--collect-only` — 1945.
- Регресс прототипа: из `<W>\…\Prototype_1.0.3` — `<PY> -m pytest tests -q`: **103 passed**; `<PY> regression\run_regression.py --quick`: **11/11 PASS** (побитово: числа не меняются).
- Тексты отказа ещё прежние: `test_prototype_failure_diagnostics.py` зелёный без правок `:392-410`.

**Подводные камни:** 2.5, пп. 1, 3, 4, 9, 11, 13.

**Зависимости:** требует шаг 0; блокирует шаги 2–4.

**Оценка:** ~40 строк кода прототипа, ~150 строк тестов; ~1 ч (из них ~10 мин — прогоны).

### Шаг 2: Адаптер — строка попыток в тексте отказа

**Цель:** текст `HydroConvergenceError` заканчивается строкой попыток (формат 2.4).

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`
- `numerical_solver/tests/test_prototype_stage_attempts.py`
- `numerical_solver/tests/test_prototype_failure_diagnostics.py` (`test_adapter_message_cell_test_only`, `:392-410`)

**Контекст:** решение 2; 2.4. `_failure_details` не меняется — его 14 параметризованных случаев (`test_failure_details`) остаются как есть. Новая функция — отдельно, вызывается последней в f-строке текста.

**Что сделать:**

1. Константа ветки — после `_EXIT_REASONS` (`:65-73`):
   ```python
   # Ветка скважины попытки ступени (DEBT-069) — поле branch записи StageAttempt прототипа
   _BRANCHES = {"open": "открыта", "shut": "закрыта"}
   ```

2. Функция — после `_failure_details` (после `:126`, перед `class PrototypeHydroAdapter`):
   ```python
   def _attempts_text(report) -> str:
       """Строка попыток ступеней advance по порядку: ступень, ветка, причина выхода, итерации, проходы, переключения, невязка (DEBT-069)."""
       # Поле attempts несёт BlackOilNewtonReport с DEBT-069: пусто, если шаг решила ступень 1.
       # Подставные отчёты тестов (SimpleNamespace) его не имеют — строки нет, текст прежний
       attempts = getattr(report, "attempts", ())
       if not attempts:
           return ""
       items = []
       for a in attempts:
           r = a.report
           head = f"{a.stage} {_BRANCHES.get(a.branch, a.branch)}" if a.branch else f"{a.stage}"
           if r.converged:
               # только у шага, принятого ступенями 2–4: последняя попытка
               items.append(f"{head} — сошлась (итераций {r.iterations})")
           elif r.exit_reason == "branch":
               # Ньютон сошёлся, но p[0] противоречит ветке: проходы, переключения и невязка
               # сошедшегося решения причину не объясняют; на старте добычи «закрыта»
               # «сходится» за 0 итераций на неизменном состоянии (DEBT-030)
               items.append(f"{head} — {_EXIT_REASONS['branch']} (итераций {r.iterations})")
           else:
               # Пустая причина — у подставных отчётов тестов; настоящий отказ её всегда имеет (DEBT-054)
               reason = _EXIT_REASONS.get(r.exit_reason, r.exit_reason) or "отказ"
               items.append(f"{head} — {reason} (итераций {r.iterations}, "
                            f"проходов {r.active_set_iterations}, "
                            f"переключений {r.phase_switches}, невязка {r.residual_inf:.2e})")
       return "; попытки ступеней: [" + "; ".join(items) + "]"
   ```

3. Текст отказа (`:241-251`). До:
   ```python
               # Дробит шаг Simulator (DEBT-015): делит пополам только этот
               # подшаг и повторяет его из того же состояния. Здесь — факты
               # отказа для журнала; текст для пользователя — в Simulator, он
               # дописывает этот текст в конец своего (DEBT-054). Хвост
               # _failure_details — после прежнего текста: тот остаётся началом.
               raise HydroConvergenceError(
                   f"advance не сошёлся{' (ступень 4 по памяти)' if by_memory else ''}: "
                   f"dt = {dt:.3e} с, "
                   f"t = {state.t / DAY_TO_S:.4f} сут, итераций {report.iterations}, "
                   f"невязка {report.residual_inf:.2e}"
                   f"{_failure_details(report, m.cell_tol, 4 if by_memory else 1)}")
   ```
   После:
   ```python
               # Дробит шаг Simulator (DEBT-015): делит пополам только этот
               # подшаг и повторяет его из того же состояния. Здесь — факты
               # отказа для журнала; текст для пользователя — в Simulator, он
               # дописывает этот текст в конец своего (DEBT-054). Хвост
               # _failure_details — после прежнего текста: тот остаётся началом.
               # Строка попыток ступеней (DEBT-069) — последней: прежний текст
               # и хвост DEBT-054 остаются началом.
               raise HydroConvergenceError(
                   f"advance не сошёлся{' (ступень 4 по памяти)' if by_memory else ''}: "
                   f"dt = {dt:.3e} с, "
                   f"t = {state.t / DAY_TO_S:.4f} сут, итераций {report.iterations}, "
                   f"невязка {report.residual_inf:.2e}"
                   f"{_failure_details(report, m.cell_tol, 4 if by_memory else 1)}"
                   f"{_attempts_text(report)}")
   ```

4. Докстринг модуля, абзац `:32-36`. До:
   ```
   Текст отказа (DEBT-054): прежний текст (dt, t, итерации, невязка) и хвост из отчёта
   Ньютона — абсолютный допуск, мера условия по ячейке с порогом numerics.newton_cell_tol
   и её предел округления (DEBT-055), причина выхода, какое условие сходимости не выполнено
   (отказ на пределе округления — отдельной оговоркой) и чья это статистика (ступень 1
   после подмены DEBT-030 или ступень 4 по памяти).
   ```
   После — тот же абзац и в конце:
   ```
   В конце (DEBT-069) — попытки ступеней advance по порядку из поля attempts отчёта:
   ступень, ветка, причина выхода, итерации, проходы набора фаз, переключения, невязка.
   ```

5. Тесты текста — дописать в `numerical_solver/tests/test_prototype_stage_attempts.py`. Импорты: строку шага 1 `from radial_blackoil.blackoil import BlackOilNewtonReport` **заменить** блоком ниже (первые четыре группы — перед импортами `from .test_prototype_globalization …`), а импорт фикстур адаптера добавить **после** `from .test_prototype_well_branch import …`:
   ```python
   from dataclasses import replace
   from types import SimpleNamespace

   import pytest

   from gpn_multiphase_solver.hydro.base import HydroConvergenceError
   from gpn_multiphase_solver.hydro.prototype_adapter import _attempts_text
   from radial_blackoil.blackoil import BlackOilNewtonReport, StageAttempt
   ```
   ```python
   # Малая модель адаптера (N = 20, BHP 150 бар) и её фикстуры
   from .test_prototype_adapter import (  # noqa: F401
       DT, adapter, bc, initial_state, model, our_grid, our_pvt,
       proto_grid, proto_pvt, proto_rock, proto_rp)
   ```
   Импорт фикстуры `model` и локальные `model = _model(150.0)` в тестах класса A уживаются — так же устроен `test_prototype_stage4_memory.py` (`:39-41`, `:58`).
   Тесты:
   ```python
   # ═══════════════════════════════════════════════════════════
   # B. Строка попыток в тексте отказа адаптера
   # ═══════════════════════════════════════════════════════════

   def _att(stage, branch, converged, its, reason, passes=1, switches=0, res=0.0):
       """Попытка с отчётом: сошлась, итераций, причина, проходов, переключений, невязка."""
       return StageAttempt(stage, branch, BlackOilNewtonReport(
           converged, its, res, passes, switches, exit_reason=reason))


   # Первый шаг примера 19 при 1 с (vault/issues/debt-069/probes/example19.out.txt), без ступени 3
   _EX19 = (_att(1, "", False, 31, "active_set", 12, 364, 2.83e-3),
            _att(2, "open", False, 31, "active_set", 12, 364, 2.83e-3),
            _att(2, "shut", False, 0, "branch"),
            _att(4, "open", False, 40, "max_iter", 1, 424, 4.64e-4))


   @pytest.mark.parametrize("report, expected", [
       # отказ по давлению: ветки по-русски, несогласованная — только итерации
       (BlackOilNewtonReport(False, 31, 2.83e-3, attempts=_EX19),
        "; попытки ступеней: [1 — набор фаз не установился (итераций 31, проходов 12, "
        "переключений 364, невязка 2.83e-03); 2 открыта — набор фаз не установился (итераций 31, "
        "проходов 12, переключений 364, невязка 2.83e-03); 2 закрыта — ветвь скважины "
        "несогласована (итераций 0); 4 открыта — исчерпан лимит итераций (итераций 40, "
        "проходов 1, переключений 424, невязка 4.64e-04)]"),
       # управление по дебиту: ветки нет — только номер ступени
       (BlackOilNewtonReport(False, 15, 2.5e-7, attempts=(
           _att(1, "", False, 15, "line_search", 2, 21, 2.5e-7),
           _att(2, "", False, 14, "max_iter", 3, 7, 3e-6))),
        "; попытки ступеней: [1 — линейный поиск не принял ни одной точки (итераций 15, "
        "проходов 2, переключений 21, невязка 2.50e-07); 2 — исчерпан лимит итераций "
        "(итераций 14, проходов 3, переключений 7, невязка 3.00e-06)]"),
       # принятая попытка (шаг ступеней 2–4)
       (BlackOilNewtonReport(True, 17, 2e-16, attempts=(_att(3, "shut", True, 17, "converged"),)),
        "; попытки ступеней: [3 закрыта — сошлась (итераций 17)]"),
       # неизвестный код — как есть; пустой (подставные отчёты) — «отказ»
       (BlackOilNewtonReport(False, 3, 1.0, attempts=(
           _att(1, "", False, 3, "new_code", res=1.0), _att(2, "", False, 3, "", res=1.0))),
        "; попытки ступеней: [1 — new_code (итераций 3, проходов 1, переключений 0, невязка "
        "1.00e+00); 2 — отказ (итераций 3, проходов 1, переключений 0, невязка 1.00e+00)]"),
       # шаг решила ступень 1 / отчёт без поля — строки нет
       (BlackOilNewtonReport(False, 0, 1.0), ""),
       (SimpleNamespace(converged=False, iterations=0, residual_inf=1.0), ""),
   ])
   def test_attempts_text(report, expected):
       """Формат строки попыток (план, 2.4): решение пользователя 2026-10-14 — все попытки, несогласованная кратко."""
       assert _attempts_text(report) == expected


   def test_adapter_message_ends_with_attempts(model, adapter, initial_state, bc, monkeypatch):
       """Текст отказа адаптера: прежний текст и хвост DEBT-054 — начало, строка попыток — конец.

       Подмена advance возвращает отказ с попытками; хвост DEBT-054 у отчёта без допуска и
       меры — только причина выхода. Ловит: строку попыток не в конце текста или без неё.
       """
       rep = BlackOilNewtonReport(False, 31, 2.83e-3, 12, 364, exit_reason="active_set",
                                  attempts=_EX19)
       monkeypatch.setattr(model, "advance", lambda s, dt, **kw: (s, replace(rep)))
       with pytest.raises(HydroConvergenceError) as exc:
           adapter.solve(initial_state, DT, bc)
       msg = str(exc.value)
       assert msg.startswith("advance не сошёлся: dt = ")
       assert msg.endswith(", выход: набор фаз не установился; числа — Ньютона ступени 1"
                           + _attempts_text(rep))
   ```
   Проверить при реализации: фикстура `model` из `test_prototype_adapter.py` создаёт `RadialBlackOilModel` без `cell_tol` (`m.cell_tol` = None) — хвост `_failure_details` у отчёта без `residual_tol` и `cell_measure` равен `", выход: набор фаз не установился; числа — Ньютона ступени 1"` (случай `active_set` в `test_failure_details`, `:457-458`, — с мерой). Если у фикстуры другой `cell_tol` — хвост не меняется: мера None, допуск None.

6. `test_adapter_message_cell_test_only` (`test_prototype_failure_diagnostics.py:392-410`). До (`:410`):
   ```python
       assert msg.endswith("; числа — Ньютона ступени 1")
   ```
   После:
   ```python
       # DEBT-069: после «чьих чисел» — строка попыток; ступени 2 и 3 «открыта» — те же
       # числа, что у ступени 1, ступень 4 «открыта» — лимит 40 (attempts_probe.py bug018)
       assert "; числа — Ньютона ступени 1; попытки ступеней: [" in msg
       attempts = msg.split("; попытки ступеней: [", 1)[1]
       assert attempts.startswith(
           "1 — линейный поиск не принял ни одной точки (итераций 4, проходов 1, переключений 0, "
           "невязка 6.51e-15); 2 открыта — линейный поиск не принял ни одной точки (итераций 4, "
           "проходов 1, переключений 0, невязка 6.51e-15); 2 закрыта — ветвь скважины "
           "несогласована (итераций 0); 3 открыта — линейный поиск не принял ни одной точки "
           "(итераций 4, проходов 1, переключений 0, невязка 6.51e-15); 3 закрыта — ветвь "
           "скважины несогласована (итераций 0); 4 открыта — исчерпан лимит итераций "
           "(итераций 40, проходов 1, переключений ")
       assert attempts.endswith("; 4 закрыта — ветвь скважины несогласована (итераций 0)]")
   ```
   Переключения и невязка ступени 4 не закрепляются: их сдвигает любая правка ступени 4. Закреплены лимит, порядок и ветки.

**Проверка после этого шага:**
- Регресс: быстрый — **1676 passed** (1669 + 7: 6 случаев `test_attempts_text` + `test_adapter_message_ends_with_attempts`), `--collect-only` — 1952.
- `test_simulator_message_ends_with_adapter_text` (`:483-497`) зелёный без правок: конец текста `Simulator` — по-прежнему текст адаптера целиком.

**Подводные камни:** 2.5, пп. 3, 5, 12.

**Зависимости:** требует шаг 1; блокирует шаги 3, 4.

**Оценка:** ~35 строк адаптера, ~80 строк тестов; ~40 мин.

### Шаг 3: Документы прототипа

**Цель:** описать поле в CHANGELOG и формате вывода.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/docs/OUTPUT_FORMAT.md`

**Что сделать:**

1. `OUTPUT_FORMAT.md`, после строки `:30` (строка отказа `step_log.csv`) — подпункт:
   ```
     - The attempts of the fallback stages (`attempts` of the report: stage, BHP branch, a copy of each attempt's report; GPN project, DEBT-069) are not written to `step_log.csv` or `run_summary.json`.
   ```

2. `CHANGELOG_1.0.3.md` — раздел в конец файла (после DEBT-055; если BUG-028 или DEBT-067 уже дописали свои — после них). Числа в `<…>` — из шагов 1, 4:
   ```
   ## Local changes — GPN project (DEBT-069): every attempt of advance in the report
   - Problem: once the original algorithm fails, `advance()` tries up to three fallback stages, and under BHP control each of them up to two well branches; every attempt overwrote the report of the previous one. On a total failure the report carried the original algorithm's Newton (DEBT-030) and the branch fields of the last attempt -- usually the 'shut' branch that "converges" in 0 iterations on the unchanged state and is dropped as inconsistent. Why the 'open' branch of stages 2-4 failed was recorded nowhere: on the first production step of GPN example 19 (1 s) one of the seven attempts was visible (stage 1: active-set loop ran out; stage 4 'open': 40 iterations, 424 phase switches -- not visible).
   - New type `StageAttempt(stage, branch, report)` (NamedTuple; `report` -- a copy of the attempt's report as it ended; a Newton converged on an inconsistent BHP branch is recorded as failed with exit 'branch') and new field `BlackOilNewtonReport.attempts` (tuple, default `()`). `_fallback()` takes the stage number (`stage=2` by default) and lists every branch it tried; `advance()` sets every attempt in order on the report it returns once the original algorithm has failed, accepted or not; `advance_fourth_stage()` -- the attempts of its branches. Where the original algorithm solves the step, `attempts` is empty and the report is unchanged.
   - Accepted steps, iterates and all former report fields are bitwise unchanged; the DEBT-030 substitution is unchanged; `step_log.csv` and `run_summary.json` keep their columns: tests <103> passed, regression 11/11 quick and 17/17 full PASS bitwise. In GPN five runs (BUG-018 at N = 350, examples 14, 16, 17, a daily shut-in; <15> failures in all, example 16 -- fourth-stage steps without failures) reproduce their histories and step sequences bitwise; the failure message ends with the attempts. In the GPN BUG-018 case at N = 350 and on the first step of GPN example 19 (1 s) the 'open' branch of stage 2 repeats stage 1 bitwise; on the T04 first step -- to three digits, not bitwise (GPN DEBT-072).
   - Tests: `tests/test_failure_report.py` (+2); `numerical_solver/tests/test_prototype_stage_attempts.py` of the GPN project (14). Physics, residual equations, tolerances, Newton/active-set logic and well semantics are unchanged. The distribution version stays `1.0.3+gpn.1`. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
   - Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/118; plan: `vault/plans/debt-069 stage-attempts-failure-report.md` of the GPN project.
   ```

**Проверка после этого шага:** Регресс: `--collect-only -q` (только документы) — 1952.

**Зависимости:** требует шаги 1, 2.

**Оценка:** ~10 строк; ~15 мин.

### Шаг 4: Проверка — истории, полный прогон, полная регрессия прототипа

**Цель:** подтвердить, что числа решения не изменились, а каждый отказ несёт строку попыток.

**Что сделать:**
1. Зафиксировать HEAD worktree (`git -C <W> log -1 --format=%h`). Запустить в фоне полную регрессию прототипа из `<W>\…\Prototype_1.0.3`: `<PY> regression\run_regression.py` (~45 мин). Ожидание: **17/17 PASS** побитово. После разбора удалить `OUTPUT/REGRESSION_<время>/`.
2. Истории, из `<W>\numerical_solver`:
   - `<PY> <ROOT>\vault\issues\debt-069\probes\histories.py save after`;
   - `<PY> <ROOT>\vault\issues\debt-069\probes\histories.py compare > <ROOT>\vault\issues\debt-069\probes\histories_compare.out.txt`.

   Ожидание: 5 сценариев «побитово»; в каждом «без строки попыток текст прежний: True», «строка попыток в каждом отказе: True»; всего текстов со строкой попыток — число отказов шага 0, п. 3 (на `0eeaa42` — 15); «ИТОГ: OK». Состав строк (эмуляция аудита 1 на копии дерева, `audit_histories_compare.out.txt`): 3 отказа при управлении по давлению — 7 записей «1; 2 открыта; 2 закрыта; 3 открыта; 3 закрыта; 4 открыта; 4 закрыта»; 4 отказа при управлении по дебиту — 4 записи «1; 2; 3; 4» без веток; 8 отказов ступени 4 по памяти (останов $q_{oil} = 0$) — одна запись «4 — исчерпан лимит итераций (…)».
3. Полный прогон: `<PY> -m pytest tests/ -q` из `<W>\numerical_solver` — **1952 passed** (~10 мин).
4. Повторить пробы на коде worktree (сверка с отчётом, а не с перехватом):
   - `<PY> <ROOT>\vault\issues\debt-069\probes\attempts_probe.py bug018 > <ROOT>\vault\issues\debt-069\probes\bug018_after.out.txt` и `… example 19_rs150_cooling 1 120 > …\example19_after.out.txt` — строка «attempts отчёта (N) = перехват (N): True» в каждом сценарии (до правки её нет: у отчёта нет поля); строки перехвата — как в `bug018.out.txt`, `example19.out.txt` (если BUG-028 влита — пример 19 может сойтись, тогда сравнить только совпадение «attempts отчёта = перехват»).

**Проверка:** все ожидания пп. 1–3 выполнены; расхождение — разобрать до vault.

**Подводные камни:** 2.5, пп. 9, 11.

**Зависимости:** требует шаги 1–3.

**Оценка:** ~1 ч (из них 45 мин регрессия — в фоне, параллельно с пп. 2–3).

### Шаг 5: Vault

**Цель:** записать итог.

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md` — DEBT-069: **Статус** (✅ ГОТОВО, дата, ветка, числа шага 4); у DEBT-072 в «Связано с» — ссылка на итог.
- `vault/knowledge/decisions/P1-адаптер-единицы.md`, раздел 6, абзац «Текст `HydroConvergenceError` (DEBT-054)» (`:485-491`) — в конец абзаца:
  ```
  В конце (DEBT-069) — попытки ступеней по порядку: «; попытки ступеней: [1 — …; 2 открыта — …;
  2 закрыта — ветвь скважины несогласована (итераций 0); …]». У BUG-018 при $N$ = 350 видно, что
  ступени 2 и 3 «открыта» повторили ступень 1, а ступень 4 «открыта» исчерпала 40 итераций.
  ```
- `vault/knowledge/decisions/P4-адаптивный-шаг.md`, строка DEBUG таблицы (`:112`) — после «какое условие не выполнено» дописать «; с DEBT-069 — попытки ступеней advance».
- Новая заметка `vault/knowledge/debugging/отказ всех ступеней advance скрывал ветку «открыта» ступеней 2–4 — отчёт перечисляет попытки.md`: что было (таблица BUG-018 из 2.1), что стало (пример строки 2.4), находка DEBT-072, связи — [[DEBT-030]], [[DEBT-054]], [[BUG-028]], [[DEBT-072]].
- `vault/knowledge/debugging/отказ Ньютона только по условию ячейки выглядел обычным — отчёт называет допуск, меру и причину выхода.md` — в строку «Связано» (`:60`) добавить [[DEBT-069]].
- `vault/00-home/index.md` — строка плана: «реализован …».
- `vault/issues/debt-069/05-comment-done.md` — комментарий в issue #118.

**Проверка:** `--collect-only -q` не нужен (только vault).

**Оценка:** ~30 мин.

## 4. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Ловит |
|---|---|---|---|---|
| `test_total_failure_lists_attempts` | прототип `tests/test_failure_report.py` (новый) | T04, 60 с, три ступени | 5 попыток `(1,''),(2,'open'),(2,'shut'),(3,'open'),(3,'shut')`; выходы `max_iter, max_iter, branch, max_iter, branch`; итерации 15, 15, 0, 15, 0; первая = числа DEBT-030 | потерю ветки; не тот порядок; несогласованную как «сошлась» |
| `test_accepted_original_has_no_attempts` | то же | Nabor_1b, 60 с | сошлась без запасного пути, `attempts == ()` | попытки у шага ступени 1 (решение 1) |
| `TestAttemptsOnFakeStages` (7) | `tests/test_prototype_stage_attempts.py` (новый) | подмена `_advance_phases`: ступень 1 сошлась; общий отказ трёх ступеней; дебит; принятая ступень 3; четыре ступени; ступень 4 одна; «открыта» безнадёжна | см. шаг 1, п. 8 | связь «попытка = вызов», копии без вложенности, `branch` у несогласованной, DEBT-030 прежняя, DEBT-040 видна |
| `test_attempts_text` (6) | то же | синтетические отчёты | строки 2.4 | формат, ветки по-русски, краткая несогласованная, неизвестный и пустой код, отсутствие поля |
| `test_adapter_message_ends_with_attempts` | то же | подмена `advance` в адаптере (N = 20) | конец текста = хвост DEBT-054 + строка попыток | строку не в конце или без неё |
| `test_real_total_failure_only_cell_test` (+3 утверждения) | `test_prototype_failure_diagnostics.py` | BUG-018, $N$ = 350, 86400 с | 7 попыток, выходы и итерации таблицы 2.1 | реальную потерю попыток |
| `test_adapter_message_cell_test_only` (замена `endswith`) | то же | тот же шаг через адаптер | строка попыток после «числа — Ньютона ступени 1», лимит 40 у 4 «открыта» | текст на реальном отказе |
| `test_bhp_shutin_step_without_open_branch` (+4 утверждения) | `test_prototype_open_branch_skip.py` | останов rs300, $p_{wf} = p_{ext}$, принят ступенью 4 | ветки попыток = `branches` теста, ступени 1–4, сошлась последняя | попытки у принятого шага на реальном Ньютоне |
| Истории (`histories.py`) | проба | 5 сценариев, 15 отказов | побитово; текст без строки = прежний | изменение чисел, начала текста |
| Регрессия прототипа | `run_regression.py` | 17 кейсов | 11/11, 17/17 PASS побитово | изменение шагов прототипа |

Число тестов: `numerical_solver/tests` 1938 → 1952 (+14, все в быстром уровне: 1662 → 1676); прототип 101 → 103.

## 5. Критерии завершения

- [ ] Шаги 0–5 выполнены.
- [ ] Быстрый уровень 1676 passed; полный прогон 1952 passed.
- [ ] Тесты прототипа 103 passed; регрессия `--quick` 11/11 и полная 17/17 PASS побитово.
- [ ] Истории 5 сценариев побитово; тексты отказов без строки попыток — прежние; строка — в каждом отказе.
- [ ] Шаг ступени 1 — `attempts == ()` (тесты прототипа и GPN).
- [ ] CHANGELOG и `OUTPUT_FORMAT.md` описывают поле.
- [ ] Vault: статус DEBT-069, заметки P1, P4, новая заметка `debugging/`, index, комментарий в #118.

## 6. Связь с другими задачами

- [[DEBT-030]] — подмена полей Ньютона при общем отказе: не меняется, `attempts` добавляется в тот же `replace`.
- [[DEBT-054]], [[DEBT-055]] — хвост текста отказа: не меняется, строка попыток — после него.
- [[DEBT-048]] — ступень 4 по памяти: `advance_fourth_stage` несёт попытки своих веток; текст «(ступень 4 по памяти)» — прежний.
- [[DEBT-040]] — пропуск «открыта»: виден по отсутствию записи.
- [[BUG-028]] — обнаружено при её планировании; её реализация идёт параллельно (2.5, п. 9).
- [[DEBT-067]] — правит те же тесты; κ = 0 в них сохраняет попытки (2.5, п. 9).
- [[DEBT-072]] — повтор ступени 1 веткой «открыта» ступени 2 (раздел 2.6); строится на `attempts`.

## 7. Аудит 1 (2026-10-14): эмуляция на копии дерева

Блоки «После:» шагов 1 и 2 применены **дословно** к копии дерева `8e432a3` (`git archive` в `vault/issues/debt-069/probes/tree`, после аудита удалена); блоки «До:» нашлись все.

| Проверка | Итог | План |
|---|---|---|
| тесты прототипа после шага 1 | 103 passed | 103 |
| `run_regression.py --quick` после шага 1 | 11/11 PASS; `step_log.csv` T03, T04 побайтно с эталоном | 11/11 |
| быстрый уровень после шага 1 | 1669 passed | 1669 |
| быстрый уровень после шага 2 | 1676 passed (276 deselected → всего 1952) | 1676 / 1952 |
| `histories.py` (before — основной каталог `0eeaa42`, after — копия) | 5 сценариев побитово, 15 текстов со строкой попыток, «ИТОГ: OK» (`audit_histories_compare.out.txt`) | шаг 4 |
| `attempts_probe.py bug018` на копии | «attempts отчёта (7) = перехват (7): True» (`audit_bug018_tree.out.txt`) | шаг 4 |
| длина строки попыток | 579 (пример 19, 1 с), 613 (BUG-018) | было ≈470 — исправлено в 2.4; формат оставлен решением пользователя |

Исправлено аудитом:
- `attempts_probe.py` брал прототип из основного каталога и при запуске из worktree — теперь из каталога запуска;
- шаг 0 переснимает исходные истории всегда;
- CHANGELOG: повтор ступени 1 на T04 не побитовый (`t04_attempts.out.txt`);
- шаг 4 — состав строк попыток;
- шаг 2, п. 5 — где ставить импорты.

## 8. Оценка

5 шагов + подготовка. Код: `blackoil.py` ~40 строк, `prototype_adapter.py` ~35 строк. Тесты: новый файл ~230 строк, правки трёх файлов ~30 строк, прототип ~30 строк. Документы: CHANGELOG, `OUTPUT_FORMAT.md`, vault ~5 заметок. Время: ~3.5 ч, из них ~1 ч прогоны (полная регрессия 45 мин — в фоне).
