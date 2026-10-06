---
tags:
  - план
  - рефакторинг
date: 2026-10-03
issue: DEBT-030
github: 62
branch: refactor/debt-030/rejected-step-report
status: готов к реализации
audit:
  date: 2026-10-06
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# DEBT-030: отчёт отклонённого шага прототипа — план

## Кратко

Если шаг прототипа гидродинамики не проходит ни одну из трёх ступеней `advance`, сейчас возвращается отчёт **последней** попытки. При контроле по забойному давлению (BHP) это обычно ветка скважины `shut` (закрыта): на неизменном начальном состоянии она «сходится» за 0 итераций с невязкой 0 и сразу отбрасывается как несогласованная. В итоге журнал шагов `step_log.csv`, блок `failure` в `run_summary.json` и отладочное сообщение гидро-адаптера показывают каждый отказ как «0 итераций, невязка 0». После правки при общем отказе поля Ньютона в отчёте берутся от исходного алгоритма — так было до BUG-014.

- Подтип: рефакторинг (диагностика; расчёт не меняется).
- Шагов: 6 (базовое состояние, тесты до правки, правка `advance`, документация, полная регрессия с пересъёмом `step_log.csv` в эталоне, итоговая проверка и vault).
- Код: ~15 строк в `blackoil.py` (5 точечных правок E1–E5), ~95 строк тестов в `numerical_solver/tests/` (3 теста и помощник подмены), ~25 строк теста прототипа, тексты в `CHANGELOG_1.0.3.md` и `docs/OUTPUT_FORMAT.md`, 6 файлов `step_log.csv` в `regression/golden/`.
- **Правка `advance` проверена при планировании.** Проба `trace_stages.py` подменяла метод в памяти (вывод — `.txt`, код на `38df988`; прототип с тех пор не менялся). На T03, T04, T05S_N200_DT5m отчёт после правки — это отчёт исходного алгоритма, а все принятые шаги совпадают с нынешними. Тест прототипа на входе T04 без правки падает, с правкой проходит, поля совпадают побитно (`planned_tests_check.py`).
- **Аудит, раунд 1 (2026-10-06, база `eb1723e`; код с `5f0b2ab` не менялся).** Правки E1–E5 применены буквально к копии прототипа (`apply_plan.py`): каждый якорь найден ровно один раз; тесты прототипа на копии — 84 passed. Регрессия T03, T04 на копии — PASS. В `step_log.csv` изменились только 3 отклонённые строки, ровно как в таблице шага 5. Три логических теста шага 2 проверены на текущем коде, на коде плана и на «мутанте» — `replace` без условия (`audit_gpn_tests_check.py`): тест C ловит мутанта, а регрессия его не видит (шаг 3, «Подводные камни»).

## Решения пользователя (2026-10-03, при планировании)

1. **Вариант 1:** поля Ньютона берутся от исходного алгоритма, поля ветки — от последней попытки. Формат `step_log.csv` и `run_summary.json` не меняется. Список попыток в отчёте и колонка в `step_log.csv` (варианты 3 и 3') отклонены.
2. **Эталон:** переснять только `step_log.csv` шести расчётов DEBT-029. Остальные 4 файла этих расчётов и 11 других эталонов не трогать. Запись — в `CHANGELOG_1.0.3.md`.
3. **Колонка `newton_iterations`:** поведение не менять, смысл описать. В принятой строке это сумма итераций Ньютона по циклу набора фаз (`blackoil.py:361`), в отклонённой — итерации последнего, неудавшегося решения Ньютона (`:356`).
4. **BUG-021** (Ньютон не проверяет невязку после последней итерации) зарегистрирован отдельно и в DEBT-030 не входит: его исправление меняет последовательность шагов и регрессию.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай: запись DEBT-030 в `vault/roadmap/известные баги и технический долг.md`, issue #62 (`gh issue view 62 --repo ArturSalamatin/Oil_Gas`), записи BUG-014, BUG-016, DEBT-029 там же (запасной путь, третья ступень, пересъём эталона).
3. Ветка от базовой `numerical_scheme/implementation` (проверка: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`): `git checkout -b refactor/debt-030/rejected-step-report` (или worktree `.worktrees/debt-030` — так делает `/implement`).
4. Venv: `numerical_solver\.venv\Scripts\python` основного каталога (в worktree своего `.venv` может не быть — тогда полный путь `d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python`).
5. Базовое состояние (до правок, подробно — шаг 1):
   - из `numerical_solver`: `.venv\Scripts\python -m pytest tests/ --collect-only -q` → **1241** (на `5f0b2ab`); `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` → **1017 passed** (~70 с);
   - из `numerical_solver\HydroSolverPrototype\Prototype_1.0.3`: `..\..\.venv\Scripts\python -m pytest tests -q` → **83 passed** (в шапке `/plan-improve` указано 80 — устарело, DEBT-033 добавил 3); `..\..\.venv\Scripts\python regression\run_regression.py --quick` → **11/11 PASS** (~8 мин).
   - Числа сверены аудитом 2026-10-06 на `eb1723e`: 1241, 1017, 83 passed.
6. Запомни числа тестов и время быстрого уровня — это базовое состояние.

⚠️ **Параллельно идёт DEBT-036** (#59, worktree `.worktrees/debt-036`, план «в процессе»): он тоже правит `blackoil.py` (строка в docstring модуля после DEBT-033, кеш запасов в `__init__`, `component_inventories` — всё выше `advance`, сам `advance` не трогает), добавляет раздел в конец `CHANGELOG_1.0.3.md` и 9 тестов прототипа (`test_inventories_cache.py`, `test_pvto_vectorized.py`). Если DEBT-036 влит раньше начала работы:
- номера строк `blackoil.py` в плане сдвинутся примерно на +22 (`advance` ~316 вместо 294) — правки шага 3 искать по якорям E1–E5, не по номерам;
- база тестов прототипа — 92, после DEBT-030 — 93; во всех местах плана «83/84» читать как «база/база + 1»;
- якорь E2 (последняя строка docstring модуля) — строка DEBT-036; строку DEBT-030 ставить после неё;
- раздел CHANGELOG DEBT-030 — после раздела DEBT-036.
Если DEBT-030 вливается раньше — то же разрешает тот, кто вливается вторым (конфликт в двух соседних строках docstring модуля и в конце CHANGELOG, оба — «оставить обе стороны»).
7. Начни с шага 1. После каждого шага — тест шага и регресс по полю «Регресс». Полный прогон `tests/` — в конце (`/implement` §3.1).

⚠️ **Пробы лежат только в основном каталоге.** `vault/issues/` в `.gitignore`, поэтому в worktree каталога `vault/issues/debt-030/probes/` нет. Пробы запускаются по абсолютному пути основного каталога **из `numerical_solver\HydroSolverPrototype\Prototype_1.0.3` того дерева, чей код проверяется**: они берут код из каталога запуска (`Path.cwd()`) и первой строкой печатают `код: <путь radial_blackoil>`. Если там не путь worktree — результат недействителен.

```powershell
# из <дерево>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3
$P = "d:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-030\probes"
$PY = "d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python"
& $PY $P\trace_stages.py                                   # ступени advance на отклонённых шагах, ~25 с
& $PY $P\compare_step_logs.py OUTPUT\REGRESSION_<время>     # сверка step_log.csv выхода регрессии с golden/
```

| проба | что делает | сохранённый вывод |
|---|---|---|
| `trace_stages.py` | T03, T04, T05S_N200_DT5m: первые шаги истории (60, 30, … с до первого принятого); все вызовы `_advance_phases` (ступень, ветка, сошлась, согласована, итерации, $\|F\|_\infty$); отчёт текущего `advance` и `advance` по плану (функция `advance_planned` — копия кода шага 3) | `trace_stages.txt` |
| `planned_tests_check.py` | сценарий теста прототипа шага 2 (фикстура Nabor_1b и вход T04, $n$ = 100, первый шаг 60 с): исходный алгоритм, текущий `advance`, `advance` по плану | `planned_tests_check.txt` |
| `planned_gpn_test_check.py` (запуск из `numerical_solver`) | логический тест A шага 2 на текущем `advance` и на `advance` по плану (планирование) | `planned_gpn_test_check.txt` |
| `audit_gpn_tests_check.py` (запуск из `numerical_solver`) | сценарии A, B, C тестов шага 2 на трёх версиях `advance`: текущей, по плану и «мутанте» (`replace` без условия `if not rep.converged`) | `audit_gpn_tests_check.txt` |
| `apply_plan.py` (запуск из корня проекта) | копирует прототип в `probes/_work/`, применяет правки E1–E5 шага 3 точной заменой (проверяет, что каждый якорь встречается один раз) и пишет тест прототипа шага 2; дальше в копии — `pytest tests -q`, `run_regression.py --case …`. Копию удалить после разбора | — |
| `compare_step_logs.py` | по каждому расчёту в каталоге выхода регрессии: совпадает ли `step_log.csv` с эталоном побайтно, сколько строк различаются в целых колонках, сколько — только в `residual_inf`, а также изменившиеся отклонённые строки | `compare_step_logs_before.txt` (до правки: T03, T04, T05S_N200_DT5m) |

## Контекст для читателя без контекста

### Прототип и неявный шаг

Гидродинамику (давление $p$, насыщенность газом $S_g$, газосодержание $R_s$) решает прототип `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/` — код коллеги («Sergey solver»), править его разрешено. Библиотека GPN вызывает его через адаптер `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`. У прототипа есть и собственный запуск по книге Excel (`runner.run_workbook` → `simulation.simulate_schedule`), и своя регрессия против эталона `regression/golden/` (сверен авторами с CMG IMEX).

Один неявный шаг по времени — метод `RadialBlackOilModel.advance(state_old, dt_s)` (`blackoil.py:294-321`). Он возвращает пару `(new_state, report)`. `report` — это `BlackOilNewtonReport` (`blackoil.py:22-32`):

| поле | смысл |
|---|---|
| `converged` | шаг принят |
| `iterations` | итерации Ньютона (смысл — ниже) |
| `residual_inf` | $\|F\|_\infty$ невязки баланса компонентов (строки газа нормированы) |
| `active_set_iterations` | итерации цикла набора фаз (сколько раз решался Ньютон при пересмотре однофазных и двухфазных ячеек) |
| `phase_switches` | сколько ячеек сменили режим за шаг |
| `well_branch`, `well_switches`, `fallback` | BUG-014: ветка скважины при BHP (`'open'`/`'shut'`), число смен ветки на запасном пути, флаг «шаг решён запасным путём» |
| `globalized` | BUG-016: запускалась третья ступень |

### Три ступени `advance`

1. **Исходный алгоритм** — `_advance_phases` (`blackoil.py:350-372`): цикл набора фаз; внутри — Ньютон с фиксированным набором (`_newton_fixed_active_set`, `:270-293`, не больше 15 итераций, линейный поиск по $\|F\|_\infty$). Ветку скважины выбирает автоматическое правило по текущему $p_0$. Если ступень сошлась — шаг принят, `rep.well_branch` записывается по принятому состоянию (`:299-304`).
2. **Запасной путь BUG-014** — `_fallback` (`:322-349`): без нижней границы $S_g$. При BHP ветка скважины закрепляется на всё решение: стартовая — по старому состоянию (`p0 <= BHP` → `shut`). Принимается только согласованный результат: `open` при $p_0 \ge p_{BHP}$, `shut` при $p_0 \le p_{BHP}$. Иначе другая ветка пробуется один раз. Если не подошла ни одна, выполняется `rep.converged=False; return new,rep` (`:345-346`) — с отчётом **последней перебранной ветки**.
3. **Третья ступень BUG-016** (`:310-321`) — тот же `_fallback`, но с линейным поиском по $\|F\|_2$ и ограничением шага $|\Delta S_g| \le 0.2$. Отчёт возвращается как есть, с `globalized=True`.

Отказ всех трёх ступеней — штатная ситуация: шаг делится пополам — в `simulate_schedule` (`simulation.py:82-88`) или в адаптере (`prototype_adapter.py:106-111`). Содержимое отчёта на дробление не влияет.

### Откуда «0 итераций, невязка 0»

При пуске скважины ($p_0$ = 200 бар, $p_{BHP}$ = 100 бар) старое состояние равновесное. На ветке `shut` скважина не добывает, и невязка на начальном приближении (старом состоянии) — ровно 0. Ньютон «сходится» за 0 итераций, результат $p_0$ = 200 > 100 несогласован, ветка отбрасывается. Ветку `shut` запасной путь пробует второй, после неудачной `open`, поэтому её отчёт последний и на запасном пути, и на третьей ступени.

Трассировка до правки (`trace_stages.txt`, первый шаг T04, $\Delta t$ = 60 с):

| ступень | ветка | сошлась | итераций | итераций набора фаз | смен фаз | $\|F\|_\infty$ |
|---|---|---|---|---|---|---|
| исходный алгоритм | авто | нет | 15 | 2 | 21 | 2.350242e-07 |
| запасной путь | open | нет | 15 | 2 | 21 | 2.350241e-07 |
| запасной путь | shut | да, несогласована | 0 | 1 | 0 | 0 |
| третья ступень | open | нет | 15 | 2 | 21 | 3.669505e-05 |
| третья ступень | shut | да, несогласована | 0 | 1 | 0 | 0 |
| **отчёт сейчас** | shut | нет | **0** | **1** | **0** | **0** |
| **отчёт по плану** | shut | нет | **15** | **2** | **21** | **2.350242e-07** |

То же на всех отклонённых шагах T03 (60, 30 с) и T05S_N200_DT5m (60, 30, 15, 7.5, 3.75 с).

### Кто читает отчёт отклонённого шага

| где | что пишет |
|---|---|
| `radial_blackoil/simulation.py:83` | строка журнала `(t, dt, False, iterations, active_set_iterations, phase_switches, residual_inf)` |
| `simulation.py:87` → `radial_blackoil/runner.py:89-91` | при останове по DTMIN — блок `failure` в `run_summary.json` (те же 4 поля) |
| `radial_blackoil/runner.py:31-32` | запись журнала в `step_log.csv` |
| `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py:106-109` | `dev_log.debug(f"  Substep ... failed: iters=..., res=...")` (строки после DEBT-028; `advance` вызывается на `:104`) |

Принятый шаг: `simulation.py:99` (журнал) и `:100` — **`_grow_dt(attempt, rep)` (`:23-26`) выбирает следующий шаг по `rep.iterations`**. Поэтому отчёт принятого шага трогать нельзя: сменится последовательность шагов, а с ней и регрессия.

### Эталон регрессии уже содержит такие строки

`step_log.csv` в сравнение не входит (`regression/run_regression.py:21`: `CSV_FILES = ['profiles.csv','rates.csv','material_balance.csv']`; `compare_summary`, `:69-75`, сверяет `status`, версии, число принятых и отклонённых шагов и предупреждения). Но файл лежит в `golden/`. В DEBT-029 эталон шести расчётов переснят на коде GPN `00af963`, вместе с вводящими в заблуждение строками:

| расчёт эталона | отклонённых строк | из них «0, 1, 0, 0.0» |
|---|---|---|
| T03 | 2 | 2 |
| T04 | 1 | 1 |
| T05/T05S_N100_DT5m | 1 | 1 |
| T05/T05T_N100_DT10m | 1 | 1 |
| T05/T05T_N100_DT3m | 1 | 1 |
| T05/T05T_N100_DT60m | 1 | 1 |
| T05/T05S_N200_DT5m (эталон авторов, до BUG-014) | 5 | 0 |
| остальные 10 | 0 | — |

Эталон T05S_N200_DT5m снят авторами в другой среде. В нём отклонённые строки — отчёты исходного алгоритма, например первая: `0.0,60.0,False,15,2,42,2.3517051254296277e-05`. Сейчас прототип пишет туда «0, 1, 0, 0.0» (`compare_step_logs_before.txt`): пять строк различаются целыми колонками. Кроме того, во **всех** 8694 строках этого расчёта `residual_inf` расходится с эталоном на уровне округления (принятые: $10^{-16}$–$10^{-11}$, например `8.699e-17` против `1.343e-16`). Это среда авторов, а не правка, и регрессию это не валит — она сверяет профили с допуском abs 2e-7 / rel 2e-10. T03 и T04 сейчас совпадают с эталоном побайтно.

## Текущее и целевое состояние

**Сейчас:** при общем отказе `advance` возвращает отчёт последнего вызова `_advance_phases` — чаще всего несогласованной ветки `shut` (0 итераций, невязка 0).

**После:**
- при общем отказе поля Ньютона отчёта (`iterations`, `residual_inf`, `active_set_iterations`, `phase_switches`) — от исходного алгоритма, а поля ветки (`well_branch`, `well_switches`, `fallback`, `globalized`) — от последней попытки, как сейчас. `converged = False`;
- отклонённые строки `step_log.csv`, блок `failure` в `run_summary.json` и сообщение адаптера показывают настоящий отказ Ньютона. Код адаптера и `simulation.py` не меняется;
- смысл колонок `step_log.csv` описан в `docs/OUTPUT_FORMAT.md` и `CHANGELOG_1.0.3.md`;
- `step_log.csv` шести расчётов DEBT-029 в `golden/` соответствует новому выходу.

**Зона неприкосновенности:**
- отчёт принятого шага — побитно (от него зависит `_grow_dt`): ветви `if rep.converged` в `advance` не трогаются;
- последовательность шагов, профили, дебиты, баланс, `run_summary.json` — побитно; полная регрессия прототипа 17/17 PASS;
- `_fallback`, `_advance_phases`, `_newton_fixed_active_set` — без изменений (BUG-021 — отдельно);
- адаптер GPN и истории 20 примеров GPN — побитно (адаптер читает поля отчёта отказа только для отладочного сообщения);
- `regression/golden/`: кроме 6 файлов `step_log.csv` — ничего; `regression/evidence/`, `PACKAGE_MANIFEST_SHA256.txt` — не обновляются (как в BUG-014, BUG-016, DEBT-029, DEBT-033).

## Варианты и выбор

| вариант | суть | итог |
|---|---|---|
| 1 | при общем отказе — поля Ньютона исходного алгоритма | **выбран** (решение пользователя). Минимальная правка, однозначное правило, возвращает журналу смысл до BUG-014; формат вывода тот же |
| 2 | отчёт ступени с наименьшей $\|F\|_\infty$ | отклонён: невязки разных ступеней — невязки разных задач (свободная или закреплённая ветка, $\|F\|_\infty$ или $\|F\|_2$); из журнала не видно, какая ступень записана; несогласованные ветки (невязка 0) пришлось бы исключать явно |
| 3 | список попыток в отчёте, печать в отладочном сообщении адаптера | отклонён пользователем (лишний код для низкоприоритетной задачи) |
| 3' | то же плюс колонка в `step_log.csv` | отклонён: меняет формат вывода прототипа |

Почему поля ветки берутся от последней попытки, а не от исходного алгоритма. Тесты `test_all_fail` и `test_both_branches_inconsistent` (`numerical_solver/tests/test_prototype_well_branch.py:351-374`) проверяют при общем отказе `(converged, well_branch, well_switches, fallback) == (False, "open", 1, True)`. Подмена всего отчёта отчётом исходного алгоритма (`well_branch = ''`, `well_switches = 0`) сломала бы их без пользы для диагностики. `dataclasses.replace` меняет ровно четыре поля Ньютона и оставляет эти тесты как есть.

## Подводные камни (чеклист)

- ✅ **Все места вызова найдены.** `advance` вызывают `simulation.py:81`, `prototype_adapter.py:104`, тесты (аудит: grep `\.advance\(` вне `tests/` — только эти два места). Поля отчёта отказа читают `simulation.py:83`, `runner.py:89-91`, `prototype_adapter.py:107-109`. Grep `residual_inf|well_switches|globalized|\.fallback\b` по `numerical_solver/` — других читателей нет.
- ✅ **Зависимости пакетов:** только `dataclasses.replace` (стандартная библиотека), импорт в `blackoil.py:14`.
- ✅ **Обратная совместимость API:** сигнатура `advance` и состав `BlackOilNewtonReport` не меняются; меняются значения четырёх полей только при `converged = False` после третьей ступени.
- ✅ **Состояние при ошибке:** исключение внутри третьей ступени по-прежнему проходит через `try/finally` (`_line_search_l2`, `_sg_step_max` восстанавливаются); `replace` стоит внутри `try` до `return`. Тест `test_exception_in_third_stage` (`test_prototype_globalization.py:227`) — без изменений.
- ⚠️ **Существующие тесты.** `test_all_fail`, `test_both_branches_inconsistent` (`test_prototype_well_branch.py`), `test_all_three_stages_fail` (`test_prototype_globalization.py:216-225`) используют подмену с одинаковыми отчётами `BlackOilNewtonReport(converged, 3, 0.0)` на всех ступенях: их проверки (`converged`, `well_branch`, `well_switches`, `fallback`, `globalized`, порядок вызовов) остаются верными. Отличить источник отчёта они не могут — для этого новые тесты шага 2 с разными отчётами по ступеням (A — BHP, B — по дебиту, C — сошедшаяся третья ступень сохраняет свой отчёт).
- ✅ **Циклические импорты:** нет новых импортов между модулями.
- ✅ **Docstring:** `advance` — дописать одно предложение про DEBT-030 (E3). Docstring модуля `blackoil.py` (`:1-13`) перечисляет локальные правки (BUG-014, BUG-018, DEBT-033) — дописать строку DEBT-030 (E2; найдено аудитом).
- ✅ **Конфиги:** не затронуты.
- ⚠️ **Связь с другими задачами.**
  - **BUG-021** (новый, зарегистрирован этим планованием) правит `_newton_fixed_active_set` — другой метод; порядок не важен. После BUG-021 часть отказов станет принятыми шагами; правило DEBT-030 от этого не зависит.
  - **BUG-020** (останов из развитой газовой зоны): его разбор жалуется, что отказ «Ньютон сошёлся, шаг отвергнут внешним циклом» нельзя различить — исчерпан набор фаз или обе ветки несогласованы. После DEBT-030 отчёт отказа покажет исходный алгоритм. Исчерпание набора фаз (`:372`): `iterations` — сумма по циклу, `active_set_iterations = 12`. Отказ Ньютона (`:356`): его собственные итерации (15 — исчерпан лимит, меньше — отказ линейного поиска или линейного решателя, `:279`, `:292`), `active_set_iterations` ≤ 12. Однозначно различает только одно: сошёлся ли последний Ньютон исходного алгоритма. Это поможет разбору BUG-020, но не заменит его пробы.
  - **DEBT-036** (#59, в процессе, worktree): правит `blackoil.py` выше `advance`, конец `CHANGELOG_1.0.3.md`, добавляет 9 тестов прототипа. Порядок влития любой, последствия — в «Как начать» (⚠️ DEBT-036).
  - **FEAT-019** (worktree): прототип и `test_prototype_globalization.py` не трогает (аудит: `git diff` ветки по этим путям пуст).
- ✅ **Производительность:** один `replace` на общий отказ — пренебрежимо.
- ⚠️ **Прототип: да.** Тесты прототипа и регрессия в плане (шаги 1, 3, 5). Ожидаемый исход регрессии записан заранее: **17/17 PASS** (профили, дебиты, баланс, `run_summary.json` не меняются, потому что отчёт принятого шага и решение о дроблении не меняются). Если регрессия разойдётся — значит, правка задела принятый путь: шаг 3 сделан неверно, эталон не переснимать. Обратное неверно: PASS не доказывает, что принятые отчёты целы (шаг 3, «Подводные камни»; ловят тест C и сверка шага 5).
- ⚠️ **`step_log.csv` T05S_N200_DT5m побайтно с эталоном не совпадёт и после правки:** `residual_inf` всех строк расходится на уровне округления (среда авторов). Критерий для этого расчёта — **целые колонки** (время, шаг, флаг принятия, итерации, итерации набора фаз, смены фаз) совпадают во всех строках. Эталон T05S_N200_DT5m не переснимается.

## Затронутые файлы

Пути от `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/`, кроме отмеченных.

| файл | шаг | что меняется |
|---|---|---|
| `radial_blackoil/blackoil.py` | 3 | импорт `replace`, docstring модуля и `advance`, `orig=rep`, `replace` при общем отказе (E1–E5) |
| `tests/test_failure_report.py` (новый) | 2 | тест прототипа на первом шаге T04 |
| `numerical_solver/tests/test_prototype_globalization.py` | 2 | импорт `replace`, помощник `_install_fake_reports`, тесты A, B, C |
| `docs/OUTPUT_FORMAT.md` | 4 | смысл колонок `step_log.csv` |
| `CHANGELOG_1.0.3.md` | 4, 5 | раздел DEBT-030 |
| `regression/golden/{T03,T04}/step_log.csv`, `regression/golden/T05/{T05S_N100_DT5m,T05T_N100_DT10m,T05T_N100_DT3m,T05T_N100_DT60m}/step_log.csv` | 5 | 7 отклонённых строк |
| `vault/roadmap/известные баги и технический долг.md`, `vault/issues/debt-030/05-comment-done.md` | 6 | результат |

Не меняются (читают отчёт): `radial_blackoil/simulation.py`, `radial_blackoil/runner.py`, `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`, `regression/run_regression.py`.

## Шаги

### Шаг 1: Базовое состояние

**Цель:** зафиксировать числа тестов, зелёную регрессию прототипа и `step_log.csv` до правки.

**Файлы:** — (только прогоны); вывод сверки сохранить в `vault/issues/debt-030/probes/compare_step_logs_quick_before.txt` (основной каталог).

**Контекст:** база зелёная по правилу мёржа. Регрессия `--quick` нужна, чтобы дальше отличать своё расхождение от чужого. Сверка `step_log.csv` выхода `--quick` с эталоном фиксирует состояние 11 расчётов до правки — по нему на шаге 5 видно, что изменились только отклонённые строки.

**Что сделать:**
1. Из `numerical_solver`: `.venv\Scripts\python -m pytest tests/ --collect-only -q` (ожидается 1241, если на базовой ветке с `5f0b2ab` не прибавились тесты — тогда записать фактическое); `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` — все прошли, записать число и время.
2. Из `numerical_solver\HydroSolverPrototype\Prototype_1.0.3`: `..\..\.venv\Scripts\python -m pytest tests -q` → 83 passed (92, если DEBT-036 уже влит).
3. Там же: `git rev-parse --short HEAD` (зафиксировать), затем `..\..\.venv\Scripts\python regression\run_regression.py --quick` (~8 мин, можно в фоне) → 11/11 PASS. Записать каталог выхода `OUTPUT\REGRESSION_<время>`.
4. `& $PY $P\compare_step_logs.py OUTPUT\REGRESSION_<время>` → сохранить в `compare_step_logs_quick_before.txt`. Ожидание: T03 и T04 — `байт-в-байт: True`. По остальным 9 расчётам (T00–T02, T06–T11, отклонённых шагов нет) — `целые колонки различаются: 0`; `residual_inf` может расходиться на уровне округления, как у T05S_N200_DT5m. Если у кого-то различаются целые колонки — это состояние до правки, записать его.
5. `& $PY $P\trace_stages.py` → сравнить с `trace_stages.txt` (строки «advance сейчас» — «0, 1, 0, 0»). Убедиться, что прототип с `38df988` не изменился и проба показывает то же.
6. Удалить `OUTPUT\REGRESSION_<время>` после записи сверки.

**Проверка после этого шага:**
- Регресс: быстрый (п. 1).
- Регресс прототипа: тесты прототипа + `--quick` (пп. 2–3); ожидание — 83 passed, 11/11 PASS.

**Подводные камни:** если `--quick` не 11/11 — остановиться и разобрать до правки (см. шапку `/plan-improve`, «Правка прототипа»).

**Зависимости:** блокирует шаги 2–6.

**Оценка:** ~15 мин (из них ~8 мин регрессия).

### Шаг 2: Тесты до правки (сейчас падают)

**Цель:** тесты, которые ловят «отчёт последней попытки» при общем отказе: три логических (подмена `_advance_phases`: A — BHP, B — управление по дебиту, C — сошедшаяся третья ступень сохраняет свой отчёт) и один на реальном Ньютоне (вход T04).

**Файлы:**
- `numerical_solver/tests/test_prototype_globalization.py` (существующий) — импорт `replace`, помощник `_install_fake_reports` после `ORIG3` (`:175`), три теста в классе `TestThirdStageLogic` (`:178`);
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_failure_report.py` (новый).

**Контекст:** существующие тесты логики `advance` подменяют `_advance_phases` и отдают **одинаковый** отчёт `BlackOilNewtonReport(converged, 3, 0.0)` на всех ступенях (`_install_fake_phases3`, `test_prototype_globalization.py:151-172`; `_install_fake_phases`, `test_prototype_well_branch.py:98-119`), поэтому источник отчёта им не виден. Новый логический тест отдаёт разные отчёты по ступеням, а последней попытке — «сошлась за 0 итераций, несогласована», как ветка `shut` в T04.

В модели теста $p_{wf}$ = 150 бар, а состояние `drawn_down` имеет $p_0$ = 111.7 бар < 150. Поэтому запасной путь стартует с `shut`, а последней пробуется `open`, и несогласованной (0 итераций) сделана `open` с $p_0$ = 140 < 150. Механизм тот же, что в T04, только ветки поменялись местами.

Тест B — то же правило при управлении по дебиту. Запасной путь там — простой повтор без ветки (ключ `(None, None, ·)`), и последняя попытка — настоящий отказ Ньютона, а не ложная ветка. Правило единое: поля Ньютона берутся у исходного алгоритма. До правки тест падает: отчёт берётся от третьей ступени.

Тест C сторожит размещение `replace`. Если применить его и к сошедшейся третьей ступени, ни регрессия прототипа, ни существующие тесты этого не заметят. `_grow_dt` (`simulation.py:23-26`) различает только `iterations >= 10` и `>= 6`, а у T03 и T04 сошедшаяся третья ступень даёт 17 итераций против 15 у исходного алгоритма: шаг тот же, профили те же. Тесты BUG-014/016 отдают одинаковые отчёты на всех ступенях. Аудит проверил это на «мутанте» (`audit_gpn_tests_check.txt`): A и B его пропускают, C — нет. До правки C проходит: сейчас сошедшаяся ступень возвращает свой отчёт.

Подмену с разными отчётами по ступеням дают три теста, поэтому она вынесена в помощник `_install_fake_reports`. Ключи у него те же, что у `_install_fake_phases3`; прежний помощник не трогается.

Тест прототипа повторяет реальный сценарий: первый шаг регрессии T04. Фикстура `tests/fixtures/Nabor_1b.xlsx` не годится — на $n$ = 12, 50, 100 её первый шаг 60 с решает исходный алгоритм (`planned_tests_check.txt`). T04 (`regression/inputs/T04.xlsx`) отличается от неё только таблицами ОФП (`kro_tab`, `krg_tab`; параметры совпадают, $N$ = 100). `tests/helpers.model_and_state` склеивает путь как `ROOT/'tests'/'fixtures'/case`; pathlib при абсолютном `case` возвращает сам `case`, поэтому вход T04 передаётся абсолютным путём без правки `helpers.py`. Время теста ~1.6 с.

**Что сделать:**

1. `numerical_solver/tests/test_prototype_globalization.py`:
   - в импорты перед `from pathlib import Path` (`:16`, порядок по алфавиту модулей) добавить `from dataclasses import replace`;
   - после `ORIG3 = (None, -0.05, False)` (`:175`) добавить помощник и отчёт исходного алгоритма:

```python
# DEBT-030: отчёт исходного алгоритма в тестах ниже; у остальных ступеней — другие
# числа, чтобы было видно, чей отчёт вернул advance.
ORIG_REPORT = BlackOilNewtonReport(False, 15, 2.5e-7, 2, 21)


def _install_fake_reports(model, reports):
    """DEBT-030: как _install_fake_phases3, но у каждой ступени свой отчёт."""
    calls = []

    def fake(state_old, dt_s, max_active_iter, max_newton):
        key = (model._well_branch, model._sg_lower_bound, model._line_search_l2)
        calls.append(key)
        p0_bar, rep = reports[key]
        new = state_old.copy()
        new.pressure_bar[0] = p0_bar
        return new, replace(rep)   # копия: advance и _fallback меняют поля отчёта на месте

    model._advance_phases = fake
    return calls
```

   - в класс `TestThirdStageLogic` после `test_all_three_stages_fail` (`:216-225`) добавить:

```python
    def test_all_fail_reports_original_newton(self, drawn_down):
        # DEBT-030 (A): отказ всех ступеней. Последняя попытка — ветка «открыта»
        # третьей ступени: «сошлась» за 0 итераций с невязкой 0, но несогласована
        # (p[0] = 140 < p_wf = 150). Так в T04 ведёт себя ветка «закрыта» на
        # неизменном начальном состоянии; до DEBT-030 её отчёт уходил в журнал шагов.
        # Ожидание: поля Ньютона (итерации, ||F||_inf, итерации набора фаз, смены
        # фаз) — исходного алгоритма; поля ветки — последней попытки, как раньше.
        model = _model(150.0)
        calls = _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
            ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0)),
            ("shut", None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9)),
            ("open", None, True): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0))})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3, ("shut", None, False), ("open", None, False),
                         ("shut", None, True), ("open", None, True)]
        assert not rep.converged
        assert (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                rep.phase_switches) == (15, 2.5e-7, 2, 21)
        assert rep.fallback and rep.globalized
        assert (rep.well_branch, rep.well_switches) == ("open", 1)
        _assert_restored(model)

    def test_all_fail_rate_control_reports_original_newton(self):
        # DEBT-030 (B): управление по дебиту. Запасной путь — повтор без ветки
        # (ключ (None, None, ·)), третья ступень — то же с ||F||_2. Последняя
        # попытка — настоящий отказ Ньютона, но правило то же: поля Ньютона —
        # исходного алгоритма; ветки нет ('', 0 смен).
        model, state = _build(150.0)
        model.set_oil_rate_control(2.0, 100.0)
        calls = _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            (None, None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
            (None, None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9))})
        _, rep = model.advance(state, 60.0)
        assert calls == [ORIG3, (None, None, False), (None, None, True)]
        assert not rep.converged
        assert (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                rep.phase_switches) == (15, 2.5e-7, 2, 21)
        assert rep.fallback and rep.globalized
        assert (rep.well_branch, rep.well_switches) == ("", 0)
        _assert_restored(model)

    def test_converged_third_stage_keeps_own_report(self, drawn_down):
        # DEBT-030 (C): замена полей — только при общем отказе. Третья ступень
        # сошлась на «закрыта» (p[0] = 149 <= 150 — согласована): отчёт её
        # собственный (17 итераций), не исходного алгоритма. Регрессия прототипа
        # ошибку здесь не видит: _grow_dt различает только iterations >= 10 и >= 6,
        # а 17 и 15 дают один и тот же следующий шаг.
        model = _model(150.0)
        calls = _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
            ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0)),
            ("shut", None, True): (149.0, BlackOilNewtonReport(True, 17, 2.0e-16, 2, 15))})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3, ("shut", None, False), ("open", None, False),
                         ("shut", None, True)]
        assert rep.converged
        assert (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                rep.phase_switches) == (17, 2.0e-16, 2, 15)
        assert rep.fallback and rep.globalized
        assert (rep.well_branch, rep.well_switches) == ("shut", 0)
        _assert_restored(model)
```

   `_build`, `_model`, `drawn_down` уже импортированы (`:29`), `BlackOilNewtonReport` — `:23`, `_assert_restored` — `:54`. Ожидания A, B, C сверены пробой `audit_gpn_tests_check.py` (сценарии те же, вызовы `advance` через подмену метода).

2. Новый файл `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_failure_report.py` (стиль тестов прототипа — `unittest`, английские комментарии):

```python
import unittest
from tests.helpers import ROOT, model_and_state

# DEBT-030 (GPN project): first step of regression case T04 (Nabor_1b with other
# relperm tables, N = 100, p0 = 200 bar, BHP = 100 bar, dt = 60 s).  All three
# stages of advance() fail; the BHP 'shut' branch "converges" in 0 iterations with
# ||F|| = 0 on the unchanged initial state and is dropped as inconsistent.  Before
# DEBT-030 its report went to step_log.csv; now the Newton fields of the failure
# report are the original algorithm's.  The Nabor_1b fixture itself converges on
# this step.  An absolute case path: ROOT/'tests'/'fixtures'/<absolute> == <absolute>.
T04=ROOT/'regression'/'inputs'/'T04.xlsx'

class FailureReportTests(unittest.TestCase):
    def test_total_failure_reports_original_newton(self):
        _,ref,s=model_and_state(n=100,bhp=100.0,p0=200.0,case=T04)
        _,orig=ref._advance_phases(s,60.0)
        self.assertFalse(orig.converged,'precondition: the original algorithm fails on this step')
        _,m,_=model_and_state(n=100,bhp=100.0,p0=200.0,case=T04)
        _,rep=m.advance(s,60.0)
        self.assertFalse(rep.converged); self.assertTrue(rep.fallback and rep.globalized)
        self.assertGreater(rep.iterations,0)
        self.assertEqual((rep.iterations,rep.residual_inf,rep.active_set_iterations,rep.phase_switches),
                         (orig.iterations,orig.residual_inf,orig.active_set_iterations,orig.phase_switches))

if __name__=='__main__': unittest.main()
```

Сравнение `residual_inf` точное: обе модели свежие, исходный алгоритм в `advance` и прямой вызов `_advance_phases` идут с атрибутами по умолчанию, вычисления детерминированы. В пробе равенство выполнено побитно: (15, 2.350242e-07, 2, 21).

**Проверка после этого шага:**
- `.venv\Scripts\python -m pytest tests/test_prototype_globalization.py -q` (из `numerical_solver`) → **2 failed** (A: `iterations == 0`; B: `iterations == 13` — отчёт третьей ступени), 12 passed (11 прежних + C, который до правки проходит).
- `..\..\.venv\Scripts\python -m pytest tests/test_failure_report.py -q` (из `Prototype_1.0.3`) → **1 failed** (`rep.iterations` = 0, `assertGreater` или `assertEqual`).
- Регресс: быстрый — 2 новых теста падают, остальные зелёные (ожидаемо до шага 3). В коммит шага 2 — только если `/implement` коммитит тест отдельно от правки; иначе шаги 2 и 3 — один коммит.

**Подводные камни:**
- Не трогать `_install_fake_phases3` и `_install_fake_phases`: на них стоят тесты логики `advance` (классы `TestThirdStageLogic`, `TestAdvanceBranchLogic` и др.), одинаковые отчёты там — норма для проверки порядка вызовов.
- Если предусловие теста прототипа (`orig.converged is False`) когда-нибудь перестанет выполняться (например, после BUG-021 или правки Ньютона), тест упадёт с понятным сообщением. Тогда нужен другой сценарий, а не ослабление проверки.

**Зависимости:** требует шаг 1; блокирует шаг 3.

**Оценка:** ~120 строк, ~30 мин.

### Шаг 3: Правка `advance`

**Цель:** при общем отказе вернуть поля Ньютона исходного алгоритма.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (`:1-13` docstring модуля, `:14` импорт, `:294-321` `advance`; номера — до влития DEBT-036, см. «Как начать»).

**Контекст:** см. «Три ступени `advance`» и «Откуда „0 итераций, невязка 0“». Ветви, где ступень сошлась, не меняются (зона неприкосновенности: `_grow_dt`).

**Что сделать:** пять точечных правок (Edit). Каждый якорь «было» встречается в файле ровно один раз — аудит проверил это применением к копии (`apply_plan.py`; там же тексты правок). Комментарии BUG-014/BUG-016 не трогать. Стиль прототипа компактный, `;` в строке допустим.

**E1 — импорт** (`:14`):
- было: `from dataclasses import dataclass`
- стало: `from dataclasses import dataclass, replace`

**E2 — docstring модуля** (`:11-13`; если DEBT-036 влит — после его строки `where the PVT has it.`):
- было:
```python
(bitwise the former dense one); _linear_solve takes sparse or dense J.
"""
```
- стало:
```python
(bitwise the former dense one); _linear_solve takes sparse or dense J.
DEBT-030: when all three stages of advance() fail, the report carries the Newton
fields of the original algorithm, not those of the last fallback attempt.
"""
```

**E3 — docstring `advance`** (`:297`):
- было: `        if that fails too, the fallback again with a globalized Newton (BUG-016)."""`
- стало (две строки):
```python
        if that fails too, the fallback again with a globalized Newton (BUG-016).
        If all three fail, the report carries the original algorithm's Newton (DEBT-030)."""
```

**E4 — запомнить отчёт исходного алгоритма** (`:304-305`, после выхода по сошедшемуся шагу, перед комментарием «Fallback only»):
- было:
```python
            return new,rep
        # Fallback only: where the original algorithm converges, results stay
```
- стало:
```python
            return new,rep
        orig=rep  # DEBT-030: reported if the fallback and the third stage fail too
        # Fallback only: where the original algorithm converges, results stay
```

**E5 — отчёт общего отказа** (`:319`, внутри `try` третьей ступени):
- было: `            rep.globalized=True; return new,rep`
- стало:
```python
            rep.globalized=True
            if not rep.converged:
                # DEBT-030: the last attempt is often the BHP 'shut' branch, which
                # "converges" in 0 iterations with ||F|| = 0 on an unchanged state and
                # is dropped as inconsistent; its report made every rejected step in
                # step_log.csv read "0 iterations, residual 0".  Report the original
                # algorithm's Newton instead (as before BUG-014); the branch fields
                # (well_branch, well_switches, fallback, globalized) stay the last
                # attempt's.  Accepted steps are untouched (_grow_dt reads them).
                rep=replace(rep,iterations=orig.iterations,residual_inf=orig.residual_inf,
                            active_set_iterations=orig.active_set_iterations,
                            phase_switches=orig.phase_switches)
            return new,rep
```

**`advance` после правок E3–E5 (для чтения; комментарий третьей ступени сокращён):**
```python
    def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """One implicit step: the original algorithm; on failure a fallback with the
        BHP well branch as an outer constraint and no lower bound on Sg (BUG-014);
        if that fails too, the fallback again with a globalized Newton (BUG-016).
        If all three fail, the report carries the original algorithm's Newton (DEBT-030)."""
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
        # Third stage (BUG-016), ... (комментарий без изменений)
        self._line_search_l2=True; self._sg_step_max=0.2
        try:
            new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
            rep.globalized=True
            if not rep.converged:
                # DEBT-030: the last attempt is often the BHP 'shut' branch, which
                # "converges" in 0 iterations with ||F|| = 0 on an unchanged state and
                # is dropped as inconsistent; its report made every rejected step in
                # step_log.csv read "0 iterations, residual 0".  Report the original
                # algorithm's Newton instead (as before BUG-014); the branch fields
                # (well_branch, well_switches, fallback, globalized) stay the last
                # attempt's.  Accepted steps are untouched (_grow_dt reads them).
                rep=replace(rep,iterations=orig.iterations,residual_inf=orig.residual_inf,
                            active_set_iterations=orig.active_set_iterations,
                            phase_switches=orig.phase_switches)
            return new,rep
        finally:
            self._line_search_l2=False; self._sg_step_max=None
```

`new` при отказе остаётся состоянием последней попытки: его никто не читает (`simulation.py:82-88` и адаптер `prototype_adapter.py:106-111` отбрасывают его).

**Проверка после этого шага:**
- Тесты шага 2 — все четыре проходят.
- `.venv\Scripts\python -m pytest tests/test_prototype_globalization.py tests/test_prototype_well_branch.py -q` (из `numerical_solver`) → 33 passed (30 до плана + 3 новых).
- Регресс: быстрый → все прошли, число = базовое + 3.
- Регресс прототипа: `..\..\.venv\Scripts\python -m pytest tests -q` → 84 passed (база + 1); `regression\run_regression.py --quick` → **11/11 PASS** (ожидание: профили и балансы побитно, принятый путь не тронут; на копии с правкой T03, T04 — PASS, аудит).
- `& $PY $P\trace_stages.py` из дерева с правкой: строки «advance сейчас» совпадают со строками «advance по плану» из `trace_stages.txt`. На первом шаге T04 — `it=15 aset= 2 sw= 21 |F|=2.350242e-07`.

**Подводные камни:**
- `replace` вызывать только внутри `if not rep.converged` после третьей ступени. **Регрессия ошибку размещения не поймает.** Если применить `replace` и к сошедшейся третьей ступени, у T03 и T04 итерации принятого шага станут 15 вместо 17. `_grow_dt` для обоих чисел выберет один и тот же следующий шаг (`>= 10` → ×0.75), поэтому профили и регрессия не изменятся; сменятся только принятые строки `step_log.csv`, а их регрессия не сверяет. Ловят такую ошибку тест C (шаг 2) и сверка `step_log.csv` в шаге 5 (у T03, T04 разошлись бы целые колонки принятых строк).
- `orig` присваивается после `if rep.converged: ... return`, то есть только при отказе исходного алгоритма — на принятом пути лишней работы нет.

**Зависимости:** требует шаг 2; блокирует шаги 4–5.

**Оценка:** ~16 строк, ~15 мин (+ ~8 мин `--quick`).

### Шаг 4: Документация прототипа

**Цель:** описать смысл колонок `step_log.csv` и правку.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/docs/OUTPUT_FORMAT.md` (`:25-26`, раздел `step_log.csv`);
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` (новый раздел в конце, после «DEBT-033», `:70-77`).

**Контекст:** решение пользователя 3 — смысл `newton_iterations` описать, поведение не менять. В `OUTPUT_FORMAT.md` сейчас одна строка «Internal accepted/rejected timestep/Newton information.» Документы прототипа — на английском.

**Что сделать:**
1. `docs/OUTPUT_FORMAT.md`, раздел `### step_log.csv` — заменить строку описания на:

```markdown
### `step_log.csv`
Internal accepted/rejected timestep/Newton information, one row per `advance()` call:
- `time_s_or_start` — model time after an accepted step, or the start of a rejected attempt, s; `dt_s` — step size, s; `accepted` — `True`/`False`.
- `newton_iterations`, `active_set_iterations`, `phase_switches`, `residual_inf` — from the `advance()` report.
  - Accepted row: Newton iterations summed over the phase active-set loop; `residual_inf` — ||F||_inf of the accepted state (the next step size is chosen from `newton_iterations`).
  - Rejected row (all stages of `advance()` failed): the original algorithm's Newton — iterations of its failed Newton solve (the sum over the loop if the active-set loop ran out, `active_set_iterations` = 12) and its ||F||_inf; not the last fallback attempt (GPN project, DEBT-030).
```

2. `CHANGELOG_1.0.3.md` — раздел (числа подставить фактические по итогам шага 5):

```markdown
## Local changes — GPN project (DEBT-030): report of a rejected step
- Problem: when all three stages of `advance()` failed, the report of the last `_advance_phases()` call was returned. Under BHP control that is usually the 'shut' branch: on an unchanged state it "converges" in 0 iterations with ||F||_inf = 0 and is dropped as inconsistent, so `step_log.csv`, the `failure` block of `run_summary.json` and the GPN adapter's debug message showed every rejected step as "0 iterations, residual 0".
- `advance()`: if the third stage fails too, the Newton fields of the report (`iterations`, `residual_inf`, `active_set_iterations`, `phase_switches`) are the original algorithm's, as before BUG-014; the branch fields (`well_branch`, `well_switches`, `fallback`, `globalized`) stay the last attempt's. Accepted steps and the step sequence are unchanged: full regression 17/17 PASS.
- `newton_iterations` in `step_log.csv` keeps its meaning (accepted rows: sum over the phase active-set loop; rejected rows: the failed Newton solve), now documented in `docs/OUTPUT_FORMAT.md`.
- `regression/golden/*/step_log.csv` refreshed for the six DEBT-029 jobs (T03, T04, T05S_N100_DT5m, T05T_N100_DT10m, T05T_N100_DT3m, T05T_N100_DT60m): the 7 rejected rows "0, 1, 0, 0.0" replaced by the original algorithm's reports; all other rows and the other four files of these jobs are unchanged. `step_log.csv` is not compared by `run_regression.py`. In T05S_N200_DT5m (authors' golden, not refreshed) the rejected rows again match the golden in all integer columns; `residual_inf` differs at round-off in every row of this job, as before.
- Tests: `tests/test_failure_report.py` (first step of T04). Physics, residual equations, tolerances and Newton/active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/62; plan: `vault/plans/debt-030 rejected-step-report.md` of the GPN project.
```

**Проверка после этого шага:** регресс — `--collect-only -q` (меняются только документы).

**Подводные камни:** строку про эталон в CHANGELOG окончательно сверить после шага 5: сколько строк заменено и какие значения.

**Зависимости:** требует шаг 3; окончательная правка CHANGELOG — после шага 5.

**Оценка:** ~20 строк текста, ~10 мин.

### Шаг 5: Полная регрессия прототипа и пересъём `step_log.csv` шести расчётов

**Цель:** 17/17 PASS на коде с правкой; убедиться, что изменились только отклонённые строки `step_log.csv`; переснять `step_log.csv` шести расчётов DEBT-029.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/regression/golden/{T03,T04}/step_log.csv`, `.../golden/T05/{T05S_N100_DT5m,T05T_N100_DT10m,T05T_N100_DT3m,T05T_N100_DT60m}/step_log.csv`; вывод сверки — `vault/issues/debt-030/probes/compare_step_logs_after.txt` (основной каталог).

**Контекст:** решение пользователя 2. T05 нужен целиком: четыре из шести переснимаемых расчётов — в блоке T05, а `--quick` его пропускает. Каждый кейс регрессии — отдельный процесс, который импортирует код заново, поэтому HEAD нельзя менять до конца прогона (шапка `/plan-improve`).

**Что сделать:**
1. Закоммитить шаги 2–4 (или зафиксировать HEAD), записать `git rev-parse --short HEAD`.
2. Из `Prototype_1.0.3`: `..\..\.venv\Scripts\python regression\run_regression.py` (полная, ~45 мин, в фоне) → ожидание **17/17 PASS**. FAIL — не пересъём: принятый путь задет, вернуться к шагу 3.
3. `& $PY $P\compare_step_logs.py OUTPUT\REGRESSION_<время>` → сохранить в `compare_step_logs_after.txt`. Ожидание (до копирования в `golden/`):

   | расчёт | целые колонки различаются | изменившиеся отклонённые строки (выход) |
   |---|---|---|
   | T03 | 2 | `60.0,False,15,2,21,5.613487456558634e-05`; `30.0,False,15,2,18,6.891223734492581e-05` (аудит, копия с правкой) |
   | T04 | 1 | `60.0,False,15,2,21,2.350242322954159e-07` (аудит, копия с правкой) |
   | T05S_N100_DT5m, T05T_N100_DT10m, T05T_N100_DT3m, T05T_N100_DT60m | по 1 | `60.0,False,15,2,21,2.350242322954159e-07` — предсказание: первая минута у них та же, что у T04 (DEBT-029), включая отклонённую строку эталона |
   | T05S_N200_DT5m | **0** (было 5) | 5 строк: целые колонки = эталону (`15,2,42`, `15,2,37`, `15,2,31`, `15,2,26`, `15,2,21`), `residual_inf` — до округления (в пробе 2.351705e-05, 3.563296e-05, 3.164823e-05, 6.338680e-05, 4.170449e-16; эталон 6.338679441e-05, 4.169e-16) |
   | T00–T02, T06–T11 | как в `compare_step_logs_quick_before.txt` (шаг 1) | — (отклонённых шагов нет) |
   | T05S_N050_DT5m | 0 (до правки не снимался; отклонённых шагов нет, правка его не касается) | — |

   Для шести расчётов DEBT-029 строк «только residual_inf» — 0: их эталон снят в этой среде, принятые строки совпадают побайтно. Проверено у T03, T04 (до правки и на копии с правкой); у четырёх T05 — предсказание. Если там будет не 0 — это округление, а не правка: сверять целые колонки и копировать файл как есть.
4. Скопировать `step_log.csv` шести расчётов из `OUTPUT\REGRESSION_<время>\...` в `regression\golden\...` (T03, T04, T05\T05S_N100_DT5m, T05\T05T_N100_DT10m, T05\T05T_N100_DT3m, T05\T05T_N100_DT60m). Остальные файлы не трогать.
5. Повторить сверку → для этих шести `байт-в-байт: True`; дописать в `compare_step_logs_after.txt`.
6. `git diff --stat -- numerical_solver/HydroSolverPrototype/Prototype_1.0.3/regression/golden` → ровно 6 файлов; на файл T03 — 2 изменённые строки, на остальные пять — по 1 (`git diff --word-diff` на одном файле для контроля).
7. Окончательно поправить раздел CHANGELOG (шаг 4) по фактическим числам. Удалить `OUTPUT\REGRESSION_<время>`.

**Проверка после этого шага:**
- Регресс: быстрый (код с шага 3 не менялся — только эталонные данные; для порядка).
- Регресс прототипа: полная регрессия — 17/17 PASS (п. 2). Повторный прогон после копирования не нужен: `step_log.csv` в сравнение не входит.

**Подводные камни:**
- Не копировать остальные файлы выхода в `golden/`: профили и балансы шести расчётов побитно равны эталону (PASS), и их пересъём размыл бы историю DEBT-029.
- T05S_N200_DT5m не переснимать — эталон авторов (решение пользователя 2).
- Если у T05S_N200_DT5m целые колонки различаются (не 0) — правка возвращает не то, что ожидалось: разобрать по `trace_stages.py`.

**Зависимости:** требует шаги 3–4; блокирует шаг 6.

**Оценка:** ~50 мин (из них ~45 мин регрессия).

### Шаг 6: Итоговая проверка и vault

**Цель:** полный прогон `tests/`, запись результата.

**Файлы:** `vault/roadmap/известные баги и технический долг.md` (DEBT-030), `vault/issues/debt-030/05-comment-done.md`.

**Что сделать:**
1. Полный прогон из `numerical_solver`: `.venv\Scripts\python -m pytest tests/ -q` (`/implement` §3.1) → все прошли, число = базовое + 3. Истории 20 примеров GPN не меняются: адаптер читает поля отчёта отказа только для отладочного сообщения, а отчёт принятого шага не тронут.
2. DEBT-030 в реестре: поле «Результат» (коммиты, числа тестов, регрессия 17/17, сверка `step_log.csv`, 6 файлов эталона), статус ✅.
3. Комментарий в issue #62 (`05-comment-done.md`).

**Проверка после этого шага:** регресс — полный (п. 1, итоговый).

**Зависимости:** требует шаг 5.

**Оценка:** ~15 мин (из них ~10 мин полный прогон).

## Тестовая стратегия

**Тест:** `test_all_fail_reports_original_newton`
**Файл:** `numerical_solver/tests/test_prototype_globalization.py` (существующий, класс `TestThirdStageLogic`)
**Сценарий:** отказ всех пяти вызовов `_advance_phases`; последняя попытка — «сошлась за 0 итераций, несогласована»; отчёты ступеней различаются.
**Setup:** модель Nabor_1b с $p_{wf}$ = 150 бар (`_model`), состояние `drawn_down` ($p_0$ = 111.7 бар), подмена `_advance_phases`.
**Ожидание:** `converged = False`; `(iterations, residual_inf, active_set_iterations, phase_switches) == (15, 2.5e-7, 2, 21)` (исходный); `fallback`, `globalized` — `True`; `(well_branch, well_switches) == ("open", 1)`; порядок вызовов — 5 ключей; атрибуты восстановлены.
**Baseline:** до правки падает (`iterations == 0`).
**Предотвращает:** возврат к отчёту последней попытки; подмену полей ветки.

**Тест:** `test_all_fail_rate_control_reports_original_newton`
**Файл:** `numerical_solver/tests/test_prototype_globalization.py` (класс `TestThirdStageLogic`)
**Сценарий:** управление по дебиту, отказ всех трёх вызовов `_advance_phases` (исходный, повтор без границы $S_g$, третья ступень); отчёты различаются.
**Setup:** `_build(150.0)`, `set_oil_rate_control(2.0, 100.0)`, начальное состояние, $\Delta t$ = 60 с.
**Ожидание:** `converged = False`; поля Ньютона `(15, 2.5e-7, 2, 21)`; `fallback`, `globalized`; `(well_branch, well_switches) == ("", 0)`; 3 вызова; атрибуты восстановлены.
**Baseline:** до правки падает (отчёт третьей ступени: 13 итераций).
**Предотвращает:** правило, зависящее от режима управления (например, замену только при BHP).

**Тест:** `test_converged_third_stage_keeps_own_report`
**Файл:** `numerical_solver/tests/test_prototype_globalization.py` (класс `TestThirdStageLogic`)
**Сценарий:** исходный и запасной путь отказывают, третья ступень сходится на согласованной ветке `shut` ($p_0$ = 149 ≤ 150).
**Setup:** как у A, четыре вызова.
**Ожидание:** `converged = True`; поля Ньютона — собственные `(17, 2.0e-16, 2, 15)`; `fallback`, `globalized`; `("shut", 0)`.
**Baseline:** проходит и до правки (сторож размещения `replace`).
**Предотвращает:** замену полей у принятого шага — её не видит ни регрессия прототипа (`_grow_dt`: 17 и 15 дают один шаг), ни тесты BUG-014/016 (одинаковые отчёты); на «мутанте» тест падает (`audit_gpn_tests_check.txt`).

**Тест:** `test_total_failure_reports_original_newton`
**Файл:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_failure_report.py` (новый)
**Сценарий:** реальный Ньютон, первый шаг T04 (60 с), все три ступени отказывают.
**Setup:** `model_and_state(n=100, bhp=100, p0=200, case=<абсолютный путь regression/inputs/T04.xlsx>)`.
**Ожидание:** предусловие `orig.converged is False`; `rep.converged is False`; `fallback`, `globalized`; `iterations > 0`; четыре поля Ньютона побитно равны прямому вызову `_advance_phases` (в пробе: 15, 2.350242e-07, 2, 21).
**Baseline:** до правки падает (`iterations = 0`, `residual_inf = 0`).
**Предотвращает:** то же на реальном механизме (ветка `shut` с нулевой невязкой на начальном состоянии); тест живёт в наборе прототипа, который запускается при каждой его правке.

**Регрессия (существующие тесты, должны остаться зелёными без изменений):**
- `numerical_solver/tests/test_prototype_well_branch.py` — 19 тестов логики и реального Ньютона BUG-014, в том числе `test_all_fail`, `test_both_branches_inconsistent`;
- `numerical_solver/tests/test_prototype_globalization.py` — 11 тестов BUG-016 (станет 14), в том числе `test_all_three_stages_fail`, `test_exception_in_third_stage`;
- тесты прототипа `test_failure_semantics.py`, `test_runner_failure.py` (подменяют `advance` целиком — не затронуты), `test_output_contract.py` (наличие `step_log.csv`);
- регрессия прототипа 17/17 и быстрый уровень `numerical_solver` (истории примеров через фикстуру `results` — в полном прогоне).

**Инвариант:** профили, дебиты, баланс, `run_summary.json` всех 17 расчётов регрессии — PASS против эталона; `step_log.csv` — изменились только отклонённые строки (сверка шага 5).

## Критерии завершения

- [ ] Шаги 1–6 выполнены.
- [ ] Быстрый уровень и полный прогон `numerical_solver/tests/` зелёные; тестов = базовое + 3 (A, B, C).
- [ ] Тесты прототипа: база + 1 passed (84; 93, если DEBT-036 влит раньше) — `test_failure_report.py`.
- [ ] Docstring модуля `blackoil.py` и `advance` дополнены (E2, E3).
- [ ] Полная регрессия прототипа `run_regression.py` — 17/17 PASS на коде с правкой.
- [ ] Сверка `step_log.csv` (`compare_step_logs_after.txt`): у шести расчётов DEBT-029 изменились только 7 отклонённых строк, после копирования — побайтно с эталоном; у T05S_N200_DT5m целые колонки = эталону во всех строках; у остальных 10 — как до правки.
- [ ] В `golden/` изменены ровно 6 файлов `step_log.csv`.
- [ ] `CHANGELOG_1.0.3.md` (раздел DEBT-030) и `docs/OUTPUT_FORMAT.md` (колонки `step_log.csv`) обновлены.
- [ ] `trace_stages.py` на коде с правкой: «advance сейчас» = «advance по плану» из `trace_stages.txt`.
- [ ] Vault: DEBT-030 — результат и статус; комментарий в #62; issue закрывается при мёрже.

## Обнаруженные проблемы

| ID | суть | блокирует DEBT-030 | где |
|---|---|---|---|
| **BUG-021** | `_newton_fixed_active_set` (`blackoil.py:270-293`) не сверяет невязку с допуском после последней (15-й) итерации: Ньютон, сошедшийся на ней, считается отказом. Проба: T05S_N200_DT5m, $\Delta t$ = 3.75 с — исходный алгоритм 15 итераций / 4.17e-16, запасной путь 4.21e-16, третья ступень 5.16e-10, все «не сошлись»; шаг дробится до 1.875 с | нет | зарегистрирован в реестре (решение пользователя) |
| — | в шапке `/plan-improve` для тестов прототипа указано «80 шт.», фактически 83 (DEBT-033 добавил 3) | нет | поправить в `.claude/commands/plan-improve.md` при случае (не в этой задаче) |

## Связанные заметки

- [[известные баги и технический долг]] — DEBT-030, BUG-021, BUG-014, BUG-016, BUG-020, DEBT-029, DEBT-033
- [[bug-014 well-shutin-active-set]], [[bug-016 newton-line-search-norm]] — планы запасного пути и третьей ступени
- issue: https://github.com/ArturSalamatin/Oil_Gas/issues/62
