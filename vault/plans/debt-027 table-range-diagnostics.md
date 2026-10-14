---
tags:
  - план
  - рефакторинг
date: 2026-10-14
issue: DEBT-027
github: 116
branch: refactor/debt-027/table-range-diagnostics
status: в процессе
worktree: .worktrees/debt-027
audit:
  date: 2026-10-14
  round: 1
  found: 11
  auto-fixed: 11
  manual-required: 0
---

# DEBT-027: выход состояния за PVT- и ОФП-таблицы в ходе расчёта — диагностика

**Задача:** [[известные баги и технический долг#DEBT-027]], issue [#116](https://github.com/ArturSalamatin/Oil_Gas/issues/116).
**Подтип:** рефакторинг (диагностика; числа расчёта не меняются).
**Ветка:** `refactor/debt-027/table-range-diagnostics` от `numerical_scheme/implementation`.
**База плана:** `8e432a3` (аудит 1). План написан на `6adea25`; после него влита DEBT-068 (`b7d1ba4`: `io/config.py::_validate`, +6 тестов) и закоммичены комментарии DEBT-066 в `energy/tridiag.py`. Код, который правит план, с тех пор не менялся.
**Пробы планирования:** `vault/issues/debt-027/probes/` (скрипты + `*.out.txt`).

## Решения пользователя (2026-10-14)

1. **Ложное срабатывание исправляется в прототипе параметром с прежним умолчанием.** `pvt_range_warnings(model, state, free_gas_sg=None)`: без параметра прототип пишет предупреждения как прежде — эталон его регрессии (17 кейсов) не меняется. GPN передаёт порог. Так же сделаны BUG-020 (`phase_switching_stage`) и BUG-022 (`cell_tol`). Сводка прототипа и пример 18 по-прежнему печатают ложное предупреждение — README 18 это объясняет (шаг 3).
2. **Проверка — в адаптере, одна запись на категорию за расчёт** (вариант А1 issue): после каждого сошедшегося `advance`, с моментом первого выхода и значением в этот момент. Начальное состояние проверяется тем же методом адаптера: категория, выведенная при $t = 0$, по ходу расчёта не повторяется. Итоговой сводки с крайними значениями нет (это был вариант А2).

Решение плана (не пользователя, можно оспорить на аудите): **порог свободного газа $S_g > 10^{-6}$** (`FREE_GAS_SG`, константа адаптера, не поле конфига) — обоснование в §2.4.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-027 в `vault/roadmap/известные баги и технический долг.md` и тело issue `vault/issues/debt-027/01-issue-body.md`.
3. Worktree и ветку создаёт `/implement`: `.worktrees/debt-027`, ветка `refactor/debt-027/table-range-diagnostics` от `numerical_scheme/implementation`. Проверка базы: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`.
4. Все команды pytest — из `numerical_solver/` worktree: `.venv\Scripts\python -m pytest ...`. Venv — общий, основного каталога (`D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv`); в worktree его нет — вызывай по полному пути, например `$PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"`.
5. ⚠️ **Скрипты вне pytest** (пробы `vault/issues/debt-027/probes/*.py`) в worktree берут пакет основного каталога, если не задать `PYTHONPATH` (память проекта «Worktree и PYTHONPATH»): перед запуском `$env:PYTHONPATH = "<worktree>\numerical_solver;<worktree>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"`. Каждая проба печатает путь пакета («код: …» / «пакет: …» / «прототип: …») — сверяй, что это worktree.
6. Исходный замер (шаг 0) — до любых правок.
7. После каждого шага — тест шага и регресс по полю «Регресс». Полный прогон — в конце (`/implement` §3.1).

## 1. Контекст

### 1.1. Что не так

Прототип (`radial_blackoil`) берёт PVT- и ОФП-свойства за краями таблиц с краёв, без экстраполяции: `np.interp`/`np.clip` в `radial_blackoil/pvt.py:35-42, 78-84, 98-99` и `relperm.py:7-8`. Своя диагностика у него есть — `pvt_range_warnings` (`radial_blackoil/diagnostics.py:22-53`, 9 категорий), его цикл зовёт её на каждом принятом шаге (`simulation.py:95-98`). Наш расчёт зовёт её только для начального состояния (`gpn_multiphase_solver/factory.py:353-362`, BUG-017). Давление у забоя ниже газовой таблицы или газ выше наибольшего $p_b$ таблицы пользователь не видит.

### 1.2. Почему нельзя просто подключить

Категория `OIL_PVT saturated locus above table` срабатывает на любой ячейке с флагом газового режима при $p$ выше наибольшего $p_b$ таблицы. Такая ячейка есть на фронте почти в каждом расчёте, где $R_{s,0}$ — последняя ветвь PVTO: флаг газа уже включён, но $S_g$ на уровне округления Ньютона, $R_s = R_{s,0}$. Обрезка $R_s^{sat}$ на последней ветви там ничего не меняет — свободного газа, который мог бы раствориться, нет.

Замеры (пробы `scan_examples.py`, `golden_locus_cases.py`, `front_cell_locus.py`, `gas_above_pb_04a.py`):

| Где | Срабатываний | max $S_g$ газовых ячеек выше max $p_b$ | Вывод |
|---|---|---|---|
| 12 табличных примеров GPN (04, 06–13b, 16, 18) | на 2–72 подшагах | ≤ 1.2·10⁻¹¹ | ложное |
| пример 04a ($p_{wf}$ = 4 МПа) | все 864 подшага | 0.082 | **настоящее** |
| примеры 14, 15 | 0 | — | — |
| эталон прототипа: T00–T09, T11, 6 × T05 (15 кейсов) | записано в `run_summary.json` | ≤ 3.6·10⁻⁹ | ложное |
| эталон прототипа: T10 | записано | 2.6·10⁻³ | **настоящее** |
| эталон прототипа: T08c | нет | — | — |

«Ещё воспроизведение» из реестра (книга VAL-005, «gas-active max P = 182.14005 bar») — ложное: ячейки 12 и 13 при $t$ = 60 с, $S_g$ = 1.9·10⁻¹⁴ и 0, $R_s$ = 50 = $R_{s,0}$.

**Настоящий случай 04a.** Изобара $p_b$ за 0.75 ч уходит до $r \approx 1.8$ м и к 12 ч возвращается к ≈ 1.5 м (README 04a, «Переходный процесс»). В ячейках между ними давление поднимается выше 15 МПа, а выделившийся газ раствориться не может: таблица кончается ветвью $R_s = 30 = R_{s,0}$, и выше 15 МПа $R_s^{sat}$ обрезан на 30. Газ выше $p_b$ появляется скачком на 2 ч (подшаг 24, сразу $S_g > 10^{-3}$), максимум 0.082 на 0.36 сут, к 72 ч в ячейках 65–69 ($r$ = 1.5–1.8 м) $S_g$ = 0.0018–0.014 при $p$ = 15.00–15.24 МПа. Это пять ячеек разницы «65 / 70» в README 04a.

### 1.3. Что станет после

- После каждого принятого подшага адаптер проверяет состояние; каждая категория — одна запись журнала (`user_log.warning`) за расчёт: «Состояние при t = 0.04167 сут вне таблиц: GAS_PVT pressure below table: min P=…».
- Начальное состояние — «Начальное состояние вне таблиц: …» (текст BUG-017 не меняется); эта категория по ходу расчёта не повторяется.
- «Кривая насыщения выше таблицы» в GPN — только при свободном газе ($S_g > 10^{-6}$), с текстом «free gas Sg up to … at P up to …».
- Путь Стендинга не проверяется (флаг адаптера выключен): у `HydroPVTtoBlackOilAdapter` нет газовой таблицы `gp`.
- Числа расчёта не меняются: проверка только читает состояние. Истории 23 примеров побитово прежние — замер аудита 1: отпечатки с кодом плана, подставленным в память, совпали с базой, 0 расхождений из 23 (`audit1_fingerprint_emulate.out.txt`, `audit1_fingerprint_base.out.txt`).

Эмуляция кода плана (`emulate_debt027.py`, `warnings_examples.py --emulate`) по 23 примерам: записи «вне таблиц» только у 04a, три:

```
Состояние при t = 0.003472 сут вне таблиц: GAS_PVT pressure below table: min P=42.334878 bar, table min=50 bar. Endpoint value used; no extrapolation.
Состояние при t = 0.003472 сут вне таблиц: OIL_PVT saturated locus below table: gas-active min P=42.334878 bar, min Pb=50 bar. Endpoint Rs used; no extrapolation.
Состояние при t = 0.08333 сут вне таблиц: OIL_PVT saturated locus above table: free gas Sg up to 0.00721 at P up to 150.05581 bar, max Pb=150 bar. Endpoint Rs used, the gas cannot dissolve; no extrapolation.
```

На базе — ни одной записи «вне таблиц» и ни одного прочего WARNING ни в одном примере (`warnings_examples_base.out.txt`).

## 2. Анализ

### 2.1. Исходное состояние (аудит 1, 2026-10-14, база `8e432a3`)

| Что | Значение |
|---|---|
| Тесты GPN (`--collect-only -q`) | 1938, быстрый уровень 1662 (при планировании на `6adea25` — 1932 / 1656) |
| Тесты прототипа | 101 passed (44.5 с, аудит 1) |
| Регрессия прототипа | `--quick` 11/11 PASS (аудит 1, `audit1_regression_quick.out.txt`); полная 17/17 — по CHANGELOG DEBT-055 |
| Записей «вне таблиц» в 23 примерах | 0 |
| Время одного расчёта `configs/table_pvt` (24 ч, N = 20) | ~0.3 с |

### 2.2. Затронутые файлы

| Файл | Что меняется |
|---|---|
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/diagnostics.py` | параметр `free_gas_sg`; `WARNING_CATEGORIES`, `warning_category` |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvt_clamp.py` | +4 теста |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` | раздел «Local changes — GPN project (DEBT-027)» |
| `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py` | `FREE_GAS_SG`, флаг `check_table_range`, метод `warn_table_range`, вызов в `solve` |
| `numerical_solver/gpn_multiphase_solver/factory.py` | флаг адаптеру; `_warn_initial_table_range` через адаптер |
| `numerical_solver/tests/test_table_range_warnings.py` | новый, 8 тестов |
| `numerical_solver/examples/04_table_table/README.md` | прогоны при $p_{wf} \le 4$ МПа — ниже газовой таблицы |
| `numerical_solver/examples/04a_high_gas_saturation/README.md` | раздел «Предупреждения „вне таблиц“» |
| `numerical_solver/examples/18_prototype_input/README.md` | исправить пункт «Край таблицы PVTO» |

**Не меняются (зона неприкосновенности):** `simulator.py`, `hydro/base.py` (вариант А2 отклонён), `blackoil.py` и всё прочее в прототипе, кроме `diagnostics.py`; `simulation.py` прототипа (его цикл зовёт `pvt_range_warnings` без параметра); тесты `TestInitialRangeWarnings` (`tests/test_factory_prototype.py:502-525`) и `test_no_range_warnings` (`tests/test_factory_standing_hydro.py:260-265`) — проходят без правки (проверено эмуляцией: текст начального предупреждения тот же).

**Вызывающие:** `pvt_range_warnings` — `simulation.py:57, 97` (прототип, без параметра), `factory.py:356-361` (заменяется), `tests/test_pvt_clamp.py`. `unique_warnings` — `simulation.py:79, 86, 107`. `_warn_initial_table_range` — только `factory.py:463`.

### 2.3. Варианты (выбор — решения пользователя выше)

| | Где проверять | Ложное срабатывание |
|---|---|---|
| **выбран** | А1: адаптер после сошедшегося `advance` | Б1а: параметр прототипа, умолчание прежнее |
| отклонён | А2: `HydroSolver` + `Simulator`, итоговая сводка — правка базового класса ради одного решателя | Б1б: новое умолчание + пересъём `warnings` в эталоне 16 кейсов — меняет вывод прототипа руководителя |
| отклонён | А3: по записям истории — теряет выход между записями | Б2: фильтр в адаптере — копия логики прототипа, против правила проекта |

**Почему состояние в адаптере — принятое.** `Simulator._advance` (`simulator.py:313-367`) отвергает подшаг только по `HydroConvergenceError`, которую `solve` бросает до проверки. После сошедшегося `solve` отказ возможен только в `_check_temperature` (`simulator.py:346`) — это `RuntimeError`, обрывающий весь расчёт. Поэтому проверка в адаптере видит только принятые состояния, как цикл прототипа (`simulation.py:95`: «catch transient range/sanity issues, not Newton trial excursions»).

### 2.4. Порог свободного газа $10^{-6}$

- Шум фронта: до 1.2·10⁻¹¹ в табличных примерах GPN, кроме 04a (условие сходимости по ячейке BUG-022 включено), до 3.6·10⁻⁹ в эталонных кейсах прототипа (без него: T01 1.09·10⁻⁹, T09 1.48·10⁻⁹, T11 3.6·10⁻⁹).
- ⚠️ Шум замерен на шагах до 1 ч: примеры — `dt_integration` = 3600 с, эталон прототипа — до 60 мин (T05T_N100_DT60m). Шум растёт с допуском Ньютона, а газовые строки невязки делятся на `gas_residual_scale` = max($R_{s,ext}$, 1), то есть допуск по газу растёт с $R_{s,0}$. На суточных шагах при большом $R_{s,0}$ и выключенном условии по ячейке (`numerics.newton_cell_tol = null`) запас меньше — не замерено. Если на таком расчёте появится запись «free gas Sg up to» порядка $10^{-6}$ — это шум, а не газ; порог поднимать, а не фильтровать в адаптере.
- Настоящий газ: 04a — сразу $> 10^{-3}$ при появлении (2 ч), максимум 0.082; T10 — до 2.6·10⁻³.
- `sg_switch_tol` (10⁻⁹) не годится: шум T01, T09, T11 его превышает.
- Запас: в 280 раз выше наибольшего шума и в 1000 раз ниже настоящего газа в момент появления. Любой порог от 10⁻⁹ до 10⁻³ даёт в 04a то же время первой записи (`free_gas_threshold_04a.out.txt`).
- Физический смысл: при $S_g \le 10^{-6}$ газа, который обрезка не даёт растворить, не больше $10^{-6}/B_g \approx 10^{-4}$ м³ст на м³ пор (при $B_g$ = 0.008) — на 4–5 порядков меньше растворённого ($S_o R_s / B_o \approx 25$ м³ст/м³).

### 2.5. Подводные камни

| Пункт | Статус | Как адресован |
|---|---|---|
| Все вызывающие найдены | ✅ | §2.2: `pvt_range_warnings` — 2 места в `simulation.py` без параметра, фабрика заменяется; `_warn_initial_table_range` — один вызов |
| Зависимости пакетов | ✅ | новых нет; адаптер импортирует `radial_blackoil.diagnostics` внутри метода, как фабрика сейчас |
| Обратная совместимость API | ✅ | `pvt_range_warnings` — новый параметр по ключу с умолчанием `None`; `PrototypeHydroAdapter(..., check_table_range=False)` — по умолчанию проверка выключена: тесты, создающие адаптер напрямую (`tests/test_prototype_adapter.py:113` и др.), поведения не меняют |
| Состояние при ошибке | ✅ | проверка после всех изменений полей адаптера (`_stage4_*`); исключений не бросает, только пишет журнал |
| Тесты | ✅ | эмуляция: истории не меняются; `TestInitialRangeWarnings` и `test_no_range_warnings` — тексты прежние |
| Циклические импорты | ✅ | `from ..log import user_log` в адаптере — `log.py` ничего из пакета не импортирует |
| Ссылки на уравнения | ✅ | формул нет; docstring — по `DEBT-027`, без `eq:` |
| Конфиги | ✅ | новых полей нет: порог — константа адаптера |
| Связь с задачами | ⚠️ | DEBT-068 влита до аудита (`b7d1ba4`, `io/config.py`) — учтена в базе. В работе на момент аудита 1 (worktree): **BUG-028** (`.worktrees/bug-028`) правит прототип (`blackoil.py::_advance_phases`) и **дописывает раздел в конец `CHANGELOG_1.0.3.md`** — тот же конец файла, что шаг 1: при влитии второй из задач конфликт, разрешение — оба раздела подряд, в порядке влития. Она же добавляет тесты (GPN +10, прототипа — свои) и может сменить отпечатки примеров 19, 21. **DEBT-062** (`.worktrees/debt-062`) ужесточает `tests/test_eq_references.py` (номер уравнения после метки) — новые тексты плана меток не содержат. Влитие посреди замеров даёт ложные расхождения (память «Параллельное влитие»): сверять `git log` базы до и после шагов 0 и 4; эталон отпечатков и журнала — замер шага 0 на той же базе |
| Производительность | ✅ | `pvt_range_warnings` — min/max по ячейкам и список верхних давлений ветвей; цикл прототипа зовёт её на каждом шаге и так. Проверка шага 4: время `warnings_examples.py` не выросло заметно |
| Прототип | ⚠️ | правка `diagnostics.py`; умолчание прежнее → регрессия 17/17 PASS **побитово, включая текст предупреждений** (`run_regression.py:72-77` сравнивает `warning_count` и `warnings` с эталоном). FAIL с «warning text differs from golden» = нарушено умолчание — исправлять код, не эталон |
| Повторный `run` того же симулятора | ⚠️ | учёт категорий живёт в адаптере, то есть на один `from_config`. Второй `run` того же объекта ничего не напишет. Так никто не делает (CLI и примеры строят симулятор заново); записать в docstring |

### 2.6. Обнаруженные проблемы

1. **README 18, «Край таблицы PVTO»** утверждает, что у фронта «нефть берётся с края таблицы» при 182.14 бар, — это ложное срабатывание (§1.2). Исправляется шагом 3.
2. **04a: газ выше $p_b$ не растворяется** — следствие таблицы (нет ветвей выше $R_{s,0}$), не решателя. Описывается в README 04a шагом 3; отдельной задачи нет.
3. **Путь Стендинга с табличной ОФП не проверяет категории ОФП** (пример 05: таблица до $S_g$ = 0.8). `pvt_range_warnings` на этом пути упала бы на `pvt.gp`. Вне DEBT-027 (запись реестра: «только табличный путь»). Регистрируется как новая DEBT после плана.

## 3. Шаги

### Шаг 0: исходный замер

**Цель:** зафиксировать числа базы в worktree до правок.

**Файлы:** нет правок.

**Что сделать** (из `numerical_solver/` worktree, `$env:PYTHONPATH` — п. 5 «Как начать»):
1. `& $PY -m pytest tests/ --collect-only -q` → ожидается 1938 (больше — влиты другие задачи, например BUG-028 (+10); записать — все целевые числа плана сдвигаются на ту же разницу).
2. `& $PY -m pytest tests/ -m "not slow" -q` → все passed (1662 на базе плана), записать время.
3. Из `HydroSolverPrototype/Prototype_1.0.3`: `& $PY -m pytest tests -q` → все passed (101 на базе плана; BUG-028 добавляет свои); `& $PY regression\run_regression.py --quick` → 11/11 PASS (~8 мин). Выход `OUTPUT/REGRESSION_<время>/` удалить после разбора.
4. `& $PY ..\vault\issues\bug-026\probes\fingerprint_bug026.py > ..\vault\issues\debt-027\probes\fingerprint_base.out.txt` (~4 мин) — отпечатки 23 историй базы. Ожидается «итог: расхождений 0 из 23»; если база уехала (другие влитые задачи) и есть расхождения — не страшно: эталон для шага 4 — этот файл, а не «ОК».
5. `& $PY ..\vault\issues\debt-027\probes\warnings_examples.py > ..\vault\issues\debt-027\probes\warnings_examples_wt_base.out.txt` (~5 мин) → «итог: записей «вне таблиц» 0 в 23 примерах», прочих WARNING — 0 у всех.

**Проверка:** числа записаны в отчёт реализации.

**Оценка:** ~20 мин (в основном ожидание).

### Шаг 1: прототип — `free_gas_sg` и `warning_category`

**Цель:** проверка «кривая насыщения выше таблицы» по свободному газу — по запросу, без изменения умолчания; категория текста предупреждения — функцией модуля.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/diagnostics.py`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvt_clamp.py`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`

**Контекст:** §1.2. Прототип — код руководителя группы, сверенный с CMG IMEX; его эталон регрессии сравнивает и текст предупреждений. Поэтому новое поведение — только при явном параметре (решение пользователя 1). `warning_category` нужна адаптеру (шаг 2): текст `OIL_PVT branch pressure above supplied range by up to 20 bar…` без двоеточия, и разбор `split(':')` дал бы разные «категории» при разных числах. Категории уже перечислены внутри `unique_warnings` — выносим их на уровень модуля, поведение `unique_warnings` то же.

**Что сделать:**
1. `diagnostics.py`, `pvt_range_warnings` — сигнатура и блок кривой насыщения (стр. 22-42).
2. `diagnostics.py`, `unique_warnings` (стр. 56-68) — категории на уровень модуля + `warning_category`.
3. `tests/test_pvt_clamp.py` — 4 теста (ниже).
4. `CHANGELOG_1.0.3.md` — раздел в конец файла (ниже).

**Изменения:**

`diagnostics.py`, до (стр. 22-42):
```python
def pvt_range_warnings(model,state):
    """Return warnings for ACCEPTED states only. Evaluation itself always clamps."""
    ...
    # Gas-active saturated locus is defined only over the supplied Pb(Rs) anchors.
    ga=np.asarray(state.gas_active,bool)
    if np.any(ga):
        pg=p[ga]
        if np.min(pg) < pvt.pb[0]-_range_tol(pvt.pb[0]):
            w.append(f'OIL_PVT saturated locus below table: gas-active min P={np.min(pg):.8g} bar, min Pb={pvt.pb[0]:.8g} bar. Endpoint Rs used; no extrapolation.')
        if np.max(pg) > pvt.pb[-1]+_range_tol(pvt.pb[-1]):
            w.append(f'OIL_PVT saturated locus above table: gas-active max P={np.max(pg):.8g} bar, max Pb={pvt.pb[-1]:.8g} bar. Endpoint Rs used; no extrapolation.')
```
после:
```python
def pvt_range_warnings(model,state,free_gas_sg=None):
    """Return warnings for ACCEPTED states only. Evaluation itself always clamps."""
    ...
    # Gas-active saturated locus is defined only over the supplied Pb(Rs) anchors.
    ga=np.asarray(state.gas_active,bool)
    if np.any(ga):
        pg=p[ga]
        if np.min(pg) < pvt.pb[0]-_range_tol(pvt.pb[0]):
            w.append(f'OIL_PVT saturated locus below table: gas-active min P={np.min(pg):.8g} bar, min Pb={pvt.pb[0]:.8g} bar. Endpoint Rs used; no extrapolation.')
        top=pvt.pb[-1]+_range_tol(pvt.pb[-1])
        if free_gas_sg is None:
            if np.max(pg) > top:
                w.append(f'OIL_PVT saturated locus above table: gas-active max P={np.max(pg):.8g} bar, max Pb={pvt.pb[-1]:.8g} bar. Endpoint Rs used; no extrapolation.')
        else:
            # DEBT-027 (GPN project): above the last Pb the endpoint Rs matters only where free gas
            # could dissolve. A cell switched to gas-active at the saturation front keeps Sg at Newton
            # round-off (up to 3.6e-9 in the regression cases) with Rs = max Rs: nothing is clamped
            # there, yet the plain test above reports it. With free_gas_sg the test counts only
            # gas-active cells with Sg > free_gas_sg. Default None: the former test, bitwise.
            sgc=np.asarray(state.sg,float)
            hot=ga&(sgc>free_gas_sg)&(p>top)
            if np.any(hot):
                w.append(f'OIL_PVT saturated locus above table: free gas Sg up to {np.max(sgc[hot]):.3g} at P up to {np.max(p[hot]):.8g} bar, max Pb={pvt.pb[-1]:.8g} bar. Endpoint Rs used, the gas cannot dissolve; no extrapolation.')
```
Остальное тело функции (газовая таблица, $R_s$, ветви, ОФП) — без изменений. При `free_gas_sg=None` условие `np.max(pg) > top` — то же выражение, что было (`top` — тот же порог), текст тот же.

`diagnostics.py`, до (стр. 56-68):
```python
def unique_warnings(items):
    # Keep one representative per warning category to prevent run_summary flooding.
    categories=(
        'GAS_PVT pressure below table','GAS_PVT pressure above table',
        'OIL_PVT Rs below table','OIL_PVT Rs above table',
        'OIL_PVT saturated locus below table','OIL_PVT saturated locus above table',
        'OIL_PVT branch pressure above supplied range',
        'RELPERM Sg below table','RELPERM Sg above table')
    out=[]; seen=set()
    for s in items:
        key=next((c for c in categories if s.startswith(c)),s.split(':',1)[0])
        if key not in seen: seen.add(key); out.append(s)
    return out
```
после:
```python
# Leading words of every pvt_range_warnings text. A text is grouped by them, not by its numbers
# (the branch-pressure text has no colon); the GPN adapter reports each category once per run (DEBT-027).
WARNING_CATEGORIES=(
    'GAS_PVT pressure below table','GAS_PVT pressure above table',
    'OIL_PVT Rs below table','OIL_PVT Rs above table',
    'OIL_PVT saturated locus below table','OIL_PVT saturated locus above table',
    'OIL_PVT branch pressure above supplied range',
    'RELPERM Sg below table','RELPERM Sg above table')


def warning_category(s):
    """Category of a pvt_range_warnings text: its leading words from WARNING_CATEGORIES."""
    return next((c for c in WARNING_CATEGORIES if s.startswith(c)),s.split(':',1)[0])


def unique_warnings(items):
    # Keep one representative per warning category to prevent run_summary flooding.
    out=[]; seen=set()
    for s in items:
        key=warning_category(s)
        if key not in seen: seen.add(key); out.append(s)
    return out
```

`tests/test_pvt_clamp.py`: импорт — `from radial_blackoil.diagnostics import pvt_range_warnings, warning_category, unique_warnings`; в класс `PVTClampTests` после последнего теста (стил файла — однострочники):
```python
    # DEBT-027 (GPN project): cell 0 gas-active 1 bar above the last Pb (Nabor_1b: 180 bar);
    # Sg = 0 is a saturation-front cell (nothing clamped), Sg = 0.02 is free gas that cannot dissolve.
    def _cell_above_locus(self,sg):
        _,m,s=model_and_state(p0=200); s.gas_active[0]=True; s.pressure_bar[0]=m.pvt.pb[-1]+1.0; s.sg[0]=sg; return m,s
    def test_locus_above_default_reports_any_gas_active_cell(self):
        m,s=self._cell_above_locus(0.0); w=pvt_range_warnings(m,s); self.assertTrue(any(x.startswith('OIL_PVT saturated locus above table: gas-active max P=') for x in w))
    def test_locus_above_free_gas_test_skips_front_cell(self):
        m,s=self._cell_above_locus(0.0); w=pvt_range_warnings(m,s,free_gas_sg=1e-6); self.assertFalse(any(x.startswith('OIL_PVT saturated locus above') for x in w))
    def test_locus_above_free_gas_test_reports_free_gas(self):
        m,s=self._cell_above_locus(0.02); w=pvt_range_warnings(m,s,free_gas_sg=1e-6); self.assertTrue(any(x.startswith('OIL_PVT saturated locus above table: free gas Sg up to 0.02 at P up to 181 bar') for x in w))
    def test_warning_category_ignores_numbers(self):
        a='OIL_PVT branch pressure above supplied range by up to 1 bar. Endpoint branch property used; no extrapolation.'; b=a.replace('up to 1 bar','up to 2 bar')
        self.assertEqual(warning_category(a),'OIL_PVT branch pressure above supplied range'); self.assertEqual(warning_category(b),warning_category(a)); self.assertEqual(unique_warnings([a,b]),[a])
```
Проверено пробой `proto_tests_emulate.py` на эмулированной функции: исходное состояние фикстуры (12 ячеек, 200 бар, $R_s$ = 50) — без предупреждений; max $p_b$ = 180 бар; при $S_g$ = 0 без параметра — «gas-active max P=181 bar», с параметром — нет; при $S_g$ = 0.02 с параметром — «free gas Sg up to 0.02 at P up to 181 bar».

`CHANGELOG_1.0.3.md` — в конец:
```markdown
## Local changes — GPN project (DEBT-027): free-gas test of the saturated locus above the table (off by default)
- Problem: `pvt_range_warnings` reports 'OIL_PVT saturated locus above table' for any gas-active cell above the last Pb. A cell switched to gas-active at the saturation front keeps Sg at Newton round-off with Rs = max Rs: nothing is clamped there, no free gas could dissolve. The golden outputs record this warning for 16 of the 17 regression cases; in 15 of them the gas-active cells above the last Pb have Sg <= 3.6e-9 (T10 has free gas there, Sg up to 2.6e-3). In GPN it fires in 12 of the 15 tabular examples, Sg <= 1.2e-11.
- `pvt_range_warnings(model, state, free_gas_sg=None)`: with a number the test counts only gas-active cells with Sg > free_gas_sg, and the text names the free gas ('free gas Sg up to ... at P up to ...'). With the default `None` the test and the text are the former ones.
- New `WARNING_CATEGORIES` and `warning_category(text)`: the categories `unique_warnings` listed inside it; `unique_warnings` calls the function, its output is unchanged.
- The prototype's own runs call `pvt_range_warnings` without the argument: tests 105 passed, regression 17/17 PASS bitwise, golden warnings unchanged. The GPN adapter calls it after every converged `advance` with free_gas_sg = 1e-6 and reports each category once per run.
- Physics, residual equations, Newton and well semantics are unchanged. The distribution version stays `1.0.3+gpn.1`. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Tests: `tests/test_pvt_clamp.py` (+4); `numerical_solver/tests/test_table_range_warnings.py` of the GPN project (8).
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/116; plan: `vault/plans/debt-027 table-range-diagnostics.md` of the GPN project.
```
Числа «105 passed» и «17/17» — подтвердить шагом 4 и поправить, если иначе.

**Проверка после этого шага:**
- Тесты прототипа: `& $PY -m pytest tests -q` (из `Prototype_1.0.3`) → 105 passed.
- Регресс прототипа: `& $PY regression\run_regression.py --quick` → 11/11 PASS, побитово (включая `warnings`). Полная регрессия — шаг 4.
- Регресс GPN: быстрый — 1662 passed (код GPN не менялся; `TestInitialRangeWarnings` зовёт функцию без параметра).

**Подводные камни:** §2.5 «Прототип». Умолчание `None` обязано давать прежний текст: проверяет `test_locus_above_default_reports_any_gas_active_cell` и регрессия.

**Зависимости:** требует шаг 0; блокирует шаг 2.

**Оценка:** ~25 строк кода, 8 строк тестов, 7 строк CHANGELOG; ~30 мин + 8 мин регрессии.

### Шаг 2: адаптер и фабрика + тесты GPN

**Цель:** проверка каждого принятого состояния табличного расчёта, одна запись на категорию; начальное состояние — тем же методом.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`
- `numerical_solver/gpn_multiphase_solver/factory.py`
- `numerical_solver/tests/test_table_range_warnings.py` (новый)

**Контекст:** §1.3, §2.3. Тесты пишутся вместе с кодом. Порядок и ожидаемые исходы (замер `emu_tests_step1_only.out.txt`: код шага 1 подставлен, шага 2 — нет):
1. Файл тестов (п. 9) до правок адаптера — ошибка сбора: `ImportError: FREE_GAS_SG`.
2. После п. 2 (константа) — 3 красных: `test_below_gas_table_reported_once` и `test_free_gas_above_table_reported` (записей нет), `test_standing_path_not_checked` (`AttributeError`: нет `_check_table_range`). 5 зелёных: `TestFreeGasFilter` (проверяют прототип шага 1), `test_inside_tables_silent`, `test_front_cell_not_reported` (без проверки записей нет — тест сторожит возврат ложного срабатывания после п. 6), `test_initial_category_not_repeated` (записи пока только начальные — тест сторожит повтор по ходу расчёта).
3. После остальных пунктов (1, 3–8) — 8 зелёных (`emu_tests.out.txt`: копия тестов плана против эмуляции кода — 8 passed, 2.7 с).

Поэтому порядок работы: п. 9 → п. 2 → п. 1, 3–8.

**Что сделать:**

1. `prototype_adapter.py`, импорты (стр. 43-53) — добавить после `from ..fluxes import phase_fluxes_from_components`:
   ```python
   from ..log import user_log
   ```
2. `prototype_adapter.py`, после констант памяти ступени 4 (после стр. 60, `STAGE4_MAX_FAILURES = 2 …`):
   ```python
   # Свободный газ для проверки «кривая насыщения выше таблицы» (DEBT-027), доля порового
   # объёма. Выше наибольшего p_b таблицы R_s^sat обрезан на последней ветви; это меняет
   # решение только там, где есть газ, который мог бы раствориться. Ячейка фронта с флагом
   # газа держит S_g на уровне округления Ньютона: до 1.2e-11 в табличных примерах (кроме
   # 04a, где газ настоящий), до 3.6e-9 в эталонных кейсах прототипа (без условия по ячейке
   # BUG-022); замерено на шагах до 1 ч. Настоящий газ выше p_b — сразу больше 1e-3 (пример
   # 04a, 2 ч), до 0.08. Порог — в 280 раз выше шума и в 1000 раз ниже настоящего газа
   # (vault/plans/debt-027 table-range-diagnostics.md, §2.4).
   FREE_GAS_SG = 1e-6
   ```
3. `prototype_adapter.py`, docstring модуля — абзац в конец (после «Баланс массы (DEBT-039) …», перед закрывающими `"""`):
   ```
   Выход за таблицы (DEBT-027): после каждого сошедшегося advance — pvt_range_warnings
   прототипа, категория «кривая насыщения выше таблицы» — только по свободному газу
   (FREE_GAS_SG); каждая категория — одна запись журнала за расчёт, с моментом первого
   выхода. Начальное состояние проверяет фабрика тем же методом warn_table_range.
   Только табличная PVT (check_table_range): у HydroPVTtoBlackOilAdapter нет таблицы gp.
   ```
4. `prototype_adapter.py`, `__init__` (стр. 132-161): сигнатура до —
   ```python
       def __init__(self, model, grid: Grid, pvt: HydroPVT,
                    stage4_memory: int | None = STAGE4_MEMORY,
                    max_newton: int = 15, max_active_iter: int = 12):
   ```
   после —
   ```python
       def __init__(self, model, grid: Grid, pvt: HydroPVT,
                    stage4_memory: int | None = STAGE4_MEMORY,
                    max_newton: int = 15, max_active_iter: int = 12,
                    check_table_range: bool = False):
   ```
   В docstring `__init__` после строки `max_active_iter — …`:
   ```
           check_table_range — проверять выход принятых состояний за PVT- и ОФП-таблицы
                             (DEBT-027); фабрика включает только для табличной PVT
   ```
   В конец тела `__init__` (после `self._max_active_iter = max_active_iter`):
   ```python
           # Выход за таблицы (DEBT-027): уже выведенные категории — на весь расчёт.
           # Адаптер живёт один расчёт (фабрика строит его заново): второй run того же
           # симулятора выведенные категории не повторит.
           self._check_table_range = check_table_range
           self._range_categories: set[str] = set()
   ```
5. `prototype_adapter.py`, новый метод — после `component_inventories` (перед `def solve`):
   ```python
       def warn_table_range(self, proto_state, t: float) -> None:
           """Выход состояния за PVT- и ОФП-таблицы — в журнал, одна запись на категорию за расчёт (DEBT-027)."""
           if not self._check_table_range:
               return
           from radial_blackoil.diagnostics import pvt_range_warnings, warning_category

           # Прототип берёт свойства за краями таблиц с краёв, без экстраполяции и молча;
           # его pvt_range_warnings называет категорию и значение. Категория — по
           # warning_category: в тексте о ветвях давления двоеточия нет, а числа меняются.
           for warning in pvt_range_warnings(self._model, proto_state,
                                             free_gas_sg=FREE_GAS_SG):
               category = warning_category(warning)
               if category in self._range_categories:
                   continue
               self._range_categories.add(category)
               where = ("Начальное состояние" if t == 0.0
                        else f"Состояние при t = {t / DAY_TO_S:.4g} сут")
               user_log.warning(f"{where} вне таблиц: {warning}")
   ```
6. `prototype_adapter.py`, `solve` — до (стр. 252-256):
   ```python
           self._stage4_run = self._stage4_run + 1 if report.phase_switching else 0
           self._stage4_failures = 0
           self._stage4_key = (control, state.t + dt)

           # ── Шаг 4: BlackOilState (бар) → SimulationState (Па) ──
   ```
   после:
   ```python
           self._stage4_run = self._stage4_run + 1 if report.phase_switching else 0
           self._stage4_failures = 0
           self._stage4_key = (control, state.t + dt)

           # Выход принятого состояния за таблицы (DEBT-027). Состояние принятое:
           # Simulator отвергает подшаг только по HydroConvergenceError выше, а отказ
           # проверки температуры после solve обрывает весь расчёт.
           self.warn_table_range(new_proto, state.t + dt)

           # ── Шаг 4: BlackOilState (бар) → SimulationState (Па) ──
   ```
7. `factory.py`, `_warn_initial_table_range` (стр. 353-362) — до:
   ```python
   def _warn_initial_table_range(model, ic) -> None:
       """Предупреждения pvt_range_warnings прототипа для начального состояния (BUG-017)."""
       from radial_blackoil.state import BlackOilState
       from radial_blackoil.diagnostics import pvt_range_warnings

       # Начальное состояние однородно (p0, Rs0, S_g = 0, газ неактивен), а
       # pvt_range_warnings смотрит только min/max — одной ячейки достаточно.
       state = BlackOilState.undersaturated(1, ic.p0 / BAR_TO_PA, ic.Rs0)
       for warning in pvt_range_warnings(model, state):
           user_log.warning(f"Начальное состояние вне таблиц: {warning}")
   ```
   после:
   ```python
   def _warn_initial_table_range(adapter, ic) -> None:
       """Выход начального состояния за таблицы (BUG-017) — проверкой адаптера, общей с расчётом (DEBT-027)."""
       from radial_blackoil.state import BlackOilState

       # Начальное состояние однородно (p0, Rs0, S_g = 0, газ неактивен), а
       # pvt_range_warnings смотрит только min/max — одной ячейки достаточно.
       # Через адаптер: категория, выведенная при t = 0, по ходу расчёта не
       # повторяется (DEBT-027). Без табличной PVT адаптер не проверяет.
       state = BlackOilState.undersaturated(1, ic.p0 / BAR_TO_PA, ic.Rs0)
       adapter.warn_table_range(state, 0.0)
   ```
8. `factory.py`, конец `_create_prototype_hydro` (стр. 458-473) — до:
   ```python
       # Выход начального состояния за PVT- и ОФП-таблицы (BUG-017): прототип
       # берёт свойства с краёв таблиц без экстраполяции и молча. Только
       # табличная PVT: у HydroPVTtoBlackOilAdapter (Стендинг) нет газовой
       # таблицы gp — pvt_range_warnings упал бы AttributeError.
       if isinstance(pvt, TableFullPVT):
           _warn_initial_table_range(model, ic)

       # Пересчёт потоков (Q, u, m) — тем же объектом FullPVT, что у решателя
       # энергии и Simulator (DEBT-006). Прежде табличный путь разворачивал
       # TableFullPVT до PrototypePVTAdapter проверкой поля _hydro через hasattr;
       # числа те же побитово: TableFullPVT делегирует гидро-методы без
       # арифметики, а rho_o, rho_g — общие методы HydroPVT.
       # Лимиты Ньютона (DEBT-008): адаптер передаёт их в каждый вызов advance
       return PrototypeHydroAdapter(model, grid, pvt,
                                    max_newton=nc.newton_max_iter,
                                    max_active_iter=nc.max_active_set_iter)
   ```
   после (комментарий DEBT-006 о пересчёте потоков — дословно прежний, стр. 465-469):
   ```python
       # Пересчёт потоков (Q, u, m) — тем же объектом FullPVT, что у решателя
       # энергии и Simulator (DEBT-006). Прежде табличный путь разворачивал
       # TableFullPVT до PrototypePVTAdapter проверкой поля _hydro через hasattr;
       # числа те же побитово: TableFullPVT делегирует гидро-методы без
       # арифметики, а rho_o, rho_g — общие методы HydroPVT.
       # Лимиты Ньютона (DEBT-008): адаптер передаёт их в каждый вызов advance.
       # Выход за PVT- и ОФП-таблицы (BUG-017, DEBT-027): прототип берёт свойства с
       # краёв таблиц без экстраполяции и молча; адаптер проверяет каждое принятое
       # состояние. Только табличная PVT: у HydroPVTtoBlackOilAdapter (Стендинг) нет
       # газовой таблицы gp — pvt_range_warnings упал бы AttributeError.
       adapter = PrototypeHydroAdapter(model, grid, pvt,
                                       max_newton=nc.newton_max_iter,
                                       max_active_iter=nc.max_active_set_iter,
                                       check_table_range=isinstance(pvt, TableFullPVT))
       _warn_initial_table_range(adapter, ic)
       return adapter
   ```
   `TableFullPVT` в `factory.py` уже импортирован (стр. 17), `user_log` — ещё используется другими функциями фабрики (не удалять импорт).
9. `tests/test_table_range_warnings.py` — новый файл:
   ```python
   """Выход состояния за PVT- и ОФП-таблицы в ходе расчёта (DEBT-027).

   Прототип берёт свойства за краями таблиц с краёв, без экстраполяции; его
   pvt_range_warnings называет категорию выхода. Адаптер зовёт её после каждого
   сошедшегося шага и пишет каждую категорию в журнал один раз за расчёт; начальное
   состояние проверяет фабрика тем же методом (категория при t = 0 не повторяется).
   «Кривая насыщения выше таблицы» — только по свободному газу (FREE_GAS_SG): ячейка
   фронта с флагом газа при S_g ≈ 0 давала её в 12 из 15 табличных примеров.

   Конфиг — configs/table_pvt: таблицы примера 04 (газ 5–30 МПа, ветви R_s = 0 и 30,
   p_b(30) = 15 МПа), N = 20, p0 = 20 МПа, 24 интервала по 1 ч, ~0.3 с на расчёт.
   Числа ожиданий — эмуляция плана (vault/issues/debt-027/probes/emulate_debt027.out.txt).
   """

   import logging
   from pathlib import Path

   from radial_blackoil.diagnostics import pvt_range_warnings, warning_category
   from radial_blackoil.state import BlackOilState

   from gpn_multiphase_solver.factory import SimulatorFactory
   from gpn_multiphase_solver.hydro.prototype_adapter import FREE_GAS_SG
   from gpn_multiphase_solver.io.config import load_config
   from gpn_multiphase_solver.units import BAR_TO_PA

   ROOT = Path(__file__).parent.parent
   TABLE_CONFIG = ROOT / "configs" / "table_pvt" / "config.json"
   BASELINE = ROOT / "configs" / "baseline.json"
   EXAMPLE_04A = ROOT / "examples" / "04a_high_gas_saturation" / "config.json"
   ABOVE = "OIL_PVT saturated locus above table"


   def _table_config(p_wf=None, p0=None):
       """configs/table_pvt; p_wf — на всех 24 интервалах, p0 — начальное давление."""
       config = load_config(TABLE_CONFIG)
       if p_wf is not None:
           for interval in config.time.history:
               interval.p_wf = p_wf
       if p0 is not None:
           config.initial_conditions.p0 = p0
       return config


   def _run(config, caplog):
       """Фабрика и расчёт; (simulator, history, тексты записей журнала уровня WARNING)."""
       with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
           simulator, state0 = SimulatorFactory.from_config(config)
           history = simulator.run(state0)
       messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
       return simulator, history, messages


   def _proto(state):
       """SimulationState (Па) → BlackOilState прототипа (бар), как в адаптере."""
       return BlackOilState(pressure_bar=state.p / BAR_TO_PA, rs_sm3_sm3=state.Rs.copy(),
                            sg=state.Sg.copy(), gas_active=(state.regime == 1))


   def _category(message):
       """Категория записи журнала «… вне таблиц: <текст прототипа>»."""
       return warning_category(message.split("вне таблиц: ", 1)[1])


   class TestFreeGasFilter:
       """pvt_range_warnings с free_gas_sg: ячейка фронта — не выход, свободный газ — выход."""

       def _cell_above_locus(self, sg):
           """Модель configs/table_pvt и одна ячейка в газовом режиме на 1 бар выше max p_b (150 бар)."""
           simulator, _ = SimulatorFactory.from_config(_table_config())
           model = simulator._hydro._model
           state = BlackOilState.undersaturated(1, model.pvt.pb[-1] + 1.0, model.pvt.rs_values[-1])
           state.gas_active[0] = True
           state.sg[0] = sg
           return model, state

       def test_front_cell_not_reported(self):
           """S_g = 0, R_s = 30 при 151 бар: прежняя проверка (без параметра) сообщает, с порогом — нет.

           Так выглядит ячейка фронта в 12 табличных примерах: флаг газа, свободного
           газа нет, обрезка R_s^sat на последней ветви ничего не меняет.
           """
           model, state = self._cell_above_locus(0.0)
           assert any(w.startswith(ABOVE) for w in pvt_range_warnings(model, state))
           assert not any(w.startswith(ABOVE)
                          for w in pvt_range_warnings(model, state, free_gas_sg=FREE_GAS_SG))

       def test_free_gas_reported(self):
           """S_g = 0.02 при 151 бар: газ, который не может раствориться, — выход за таблицу."""
           model, state = self._cell_above_locus(0.02)
           warnings = pvt_range_warnings(model, state, free_gas_sg=FREE_GAS_SG)
           assert any(w.startswith(f"{ABOVE}: free gas Sg up to 0.02") for w in warnings)


   class TestRunWarnings:
       """Журнал расчёта: категория — одна запись за расчёт, с моментом первого выхода."""

       def test_inside_tables_silent(self, caplog):
           """Штатный конфиг (p_wf = 15 МПа = p_b): все состояния в таблицах — записей нет."""
           _, _, messages = _run(_table_config(), caplog)
           assert messages == []

       def test_front_cell_not_reported(self, caplog):
           """p_wf = 8 МПа: ячейка фронта выше p_b есть, но свободного газа в ней нет — записей нет.

           Предусловие: прежняя проверка (без free_gas_sg) на записях истории сообщает
           о кривой насыщения выше таблицы — тест проверяет именно фильтр, а не пустой расчёт.
           """
           simulator, history, messages = _run(_table_config(p_wf=8e6), caplog)
           model = simulator._hydro._model
           assert any(w.startswith(ABOVE)
                      for s in history.states for w in pvt_range_warnings(model, _proto(s)))
           assert messages == []

       def test_below_gas_table_reported_once(self, caplog):
           """p_wf = 2 МПа: у забоя p ниже газовой таблицы (от 5 МПа) на всех 24 шагах — две записи за расчёт.

           Газовая таблица и ветвь R_s = 0 начинаются при 5 МПа: B_g, μ_g и кривая
           насыщения берутся с края. Обе категории — с первого шага (1 ч = 0.04167 сут).
           """
           _, _, messages = _run(_table_config(p_wf=2e6), caplog)
           assert len(messages) == 2
           assert all(m.startswith("Состояние при t = 0.04167 сут вне таблиц: ") for m in messages)
           assert {_category(m) for m in messages} == {
               "GAS_PVT pressure below table", "OIL_PVT saturated locus below table"}

       def test_initial_category_not_repeated(self, caplog):
           """p0 = 32 МПа выше газовой таблицы и ветвей (до 30 МПа): записи только начальные.

           Вдали от забоя давление остаётся выше таблицы весь расчёт (предусловие ниже),
           но категории, выведенные при t = 0, адаптер не повторяет.
           """
           simulator, history, messages = _run(_table_config(p0=32e6), caplog)
           model = simulator._hydro._model
           assert any(w.startswith("GAS_PVT pressure above table")
                      for w in pvt_range_warnings(model, _proto(history.states[-1])))
           assert len(messages) == 2
           assert all(m.startswith("Начальное состояние вне таблиц: ") for m in messages)
           assert {_category(m) for m in messages} == {
               "GAS_PVT pressure above table", "OIL_PVT branch pressure above supplied range"}

       def test_free_gas_above_table_reported(self, caplog):
           """Пример 04a, первые 3 ч: газ выше p_b = 15 МПа, который не может раствориться, — с 2 ч.

           Изобара p_b за 0.75 ч уходит до r ≈ 1.8 м и возвращается (README 04a); в
           ячейках между давление снова выше 15 МПа, а таблица кончается ветвью
           R_s = 30 = R_s0. Плюс две категории первого шага (p у забоя 4.23 МПа < 5 МПа).
           """
           config = load_config(EXAMPLE_04A)
           config.time.history = config.time.history[:36]   # 36 интервалов по 300 с
           _, _, messages = _run(config, caplog)
           assert len(messages) == 3
           above = [m for m in messages if _category(m) == ABOVE]
           assert len(above) == 1
           assert above[0].startswith(f"Состояние при t = 0.08333 сут вне таблиц: {ABOVE}: free gas")

       def test_standing_path_not_checked(self):
           """Стендинг: у HydroPVTtoBlackOilAdapter нет газовой таблицы gp — проверка выключена."""
           simulator, _ = SimulatorFactory.from_config(load_config(BASELINE))
           assert simulator._hydro._check_table_range is False
   ```
   8 тестов: 1938 → 1946 (быстрый уровень 1662 → 1670, медленных нет).

**Проверка после этого шага:**
- `& $PY -m pytest tests/test_table_range_warnings.py -q` → 8 passed (~3 с).
- `& $PY -m pytest tests/test_factory_prototype.py tests/test_factory_standing_hydro.py tests/test_prototype_adapter.py -q` → все passed (начальные предупреждения, Стендинг, адаптер без флага).
- Регресс: быстрый → 1670 passed.

**Подводные камни:** §2.5 «Обратная совместимость», «Повторный run». `new_proto` в `solve` — состояние прототипа после `advance`, бар; эмуляция брала давление из `result.state` (Па → бар) — разница до 1 ulp, на восьмую значащую цифру текста не влияет.

**Зависимости:** требует шаг 1 (`free_gas_sg`, `warning_category`); блокирует шаги 3, 4.

**Оценка:** ~45 строк кода, ~150 строк тестов; ~45 мин.

### Шаг 3: README 04, 04a, 18

**Цель:** README описывают предупреждения, которые теперь печатает расчёт, и не утверждают опровергнутого.

**Файлы:**
- `numerical_solver/examples/04_table_table/README.md`
- `numerical_solver/examples/04a_high_gas_saturation/README.md`
- `numerical_solver/examples/18_prototype_input/README.md`

**Контекст:** README 04 приводит прогоны при $p_{wf}$ = 4…0.5 МПа без оговорки, что они ниже газовой таблицы (проба `readme04_pwf.py`, первые сутки: при $p_{wf} \le 4$ МПа min $p(r_w)$ = 4.23 / 3.24 / 2.25 / 1.26 / 0.77 МПа, при 6 МПа — 6.20). README 04a объясняет плато (обрезка ниже 5 МПа), но не газ выше $p_b$; его $p(r_w)$ = 4.171 МПа — конец расчёта (таблица «Ожидаемое поведение»), 4.23 МПа — первый шаг (текст предупреждения). README 18 называет ложное срабатывание настоящим выходом; ячейки 12 и 13 при $t$ = 60 с подтверждены на конфиге самого примера 18 (`audit1_front_cell_18.out.txt`).

**Что сделать:**
1. README 04, раздел «Сходимость Newton: $p_{wf}$ и $N$» — после абзаца «Замер 2026-10-07 (DEBT-041), … При локальном дроблении шага (DEBT-015) — те же числа.» (стр. 308-309) вставить абзац:
   ```markdown
   При $p_{wf} \le 4$ МПа давление у забоя ниже начала газовой таблицы и
   ветви $R_s = 0$ (5 МПа; при 4 МПа $p(r_w)$ = 4.23 МПа на первых сутках): $B_g$, $\mu_g$ и
   кривая насыщения берутся с края таблиц, константой. Расчёт предупреждает
   об этом с первого шага — «GAS_PVT pressure below table» и «OIL_PVT
   saturated locus below table» (DEBT-027). При 6 МПа и выше давление в
   таблицах.
   ```
2. README 04a — новый раздел после раздела «Плато: …» (после абзаца «⚠️ Плато — **свойство демонстрационной PVT-таблицы** …», стр. 345-346), перед «## Независимость $S_g(p)$ …»:
   ```markdown
   ## Предупреждения «вне таблиц»

   Расчёт печатает три предупреждения (DEBT-027). Все три — свойства
   демонстрационной таблицы, а не ошибка расчёта:

   | Момент | Категория | Причина |
   |---|---|---|
   | 5 мин (первый шаг) | `GAS_PVT pressure below table`, min P = 42.3 бар | у забоя $p$ = 4.23 МПа на первом шаге (4.171 МПа к 72 ч), газовая таблица — от 5 МПа: $B_g$, $\mu_g$ — константа (плато выше) |
   | 5 мин | `OIL_PVT saturated locus below table` | ветвь $R_s = 0$ начинается при 5 МПа: ниже — $R_s^{sat} = 0$ и свойства нефти с края ветви |
   | 2 ч | `OIL_PVT saturated locus above table`, свободный газ $S_g$ до 0.0072 при $p$ до 15.006 МПа | газ выше $p_b$ = 15 МПа не растворяется — ниже |

   Изобара $p_b$ за 0.75 ч уходит до $r \approx 1.8$ м и к 12 ч возвращается
   к ≈ 1.5 м («Переходный процесс»). В ячейках между ними давление снова
   поднимается выше 15 МПа, а выделившийся газ раствориться не может:
   таблица кончается ветвью $R_s = 30 = R_{s,0}$, и выше 15 МПа $R_s^{sat}$
   обрезан на 30. Это 5 ячеек разницы в строке «ячеек с $p < p_b$ / с
   $S_g > 0$ — 65 / 70»: к 72 ч в них $S_g$ = 0.002–0.014 при $p$ =
   15.00–15.24 МПа (наибольшая $S_g$ таких ячеек за расчёт — 0.082, на
   0.36 сут). Чтобы этот газ мог раствориться, нужны ветви PVTO выше
   $R_s = 30$.
   ```
3. README 18, раздел «Ограничения», пункт «Край таблицы PVTO» (стр. 177-182) — до:
   ```markdown
   - **Край таблицы PVTO.** Последняя ветвь — $R_s = 50 = R_{s,0}$, её
     $p_b$ = 180 бар. По ходу расчёта газ бывает и в ячейках у фронта с
     давлением до 182.14 бар: нефть там берётся с края таблицы (ветвь
     $R_s = 50$, без экстраполяции). Прототип об этом предупреждает — `main.py` печатает его
     предупреждение; сам решатель — нет (DEBT-027). Таблицу с ветвью
     $R_s = 60$ авторы прототипа сделали для кейса T08c.
   ```
   после:
   ```markdown
   - **Край таблицы PVTO.** Последняя ветвь — $R_s = 50 = R_{s,0}$, её
     $p_b$ = 180 бар. Прототип предупреждает «OIL_PVT saturated locus above
     table: gas-active max P=182.14005 bar», `main.py` печатает это
     предупреждение. Это ячейки фронта (12 и 13 при $t$ = 60 с): газовый
     режим в них уже включён, но $S_g$ = 1.9·10⁻¹⁴ и 0, $R_s = R_{s,0}$.
     Свободного газа нет, и обрезка $R_s^{sat}$ на краю таблицы ничего не
     меняет. Решатель проверяет выход за таблицы на каждом шаге, эту
     категорию — только по ячейкам со свободным газом ($S_g > 10^{-6}$),
     и расчёт примера идёт без предупреждений (DEBT-027). В эталоне
     регрессии прототипа то же предупреждение записано у 16 кейсов из 17,
     у 15 из них это тоже ячейка фронта. Таблицу с ветвью $R_s = 60$ авторы
     прототипа сделали для кейса T08c.
   ```

**Проверка после этого шага:** регресс — `--collect-only -q` (1946; меняются только документы) и `& $PY -m pytest tests/test_eq_references.py tests/test_examples.py -m "not slow" -q`. README читают только эти тесты: `test_examples.py` (стр. 540-563) — наличие разделов «Как модифицировать», «увеличить газонасыщенность» и имён `PrototypeHydroAdapter`, `TridiagEnergySolver`; `test_eq_references.py` — ссылки на уравнения (`eq. N`, `.tex:N`). Новые абзацы разделов не удаляют и ссылок на уравнения не содержат.

**Зависимости:** требует шаг 2 (тексты предупреждений).

**Оценка:** ~40 строк текста; ~20 мин.

### Шаг 4: проверка

**Цель:** поведение по плану, числа расчёта — побитово прежние, прототип — побитово прежний.

**Что сделать** (из `numerical_solver/` worktree, `$env:PYTHONPATH` на worktree):
1. `& $PY ..\vault\issues\bug-026\probes\fingerprint_bug026.py > ..\vault\issues\debt-027\probes\fingerprint_impl.out.txt` → отпечатки 23 примеров **те же, что в `fingerprint_base.out.txt`** шага 0 (сравнить построчно, кроме строки «код:»).
2. `& $PY ..\vault\issues\debt-027\probes\warnings_examples.py > ..\vault\issues\debt-027\probes\warnings_examples_impl.out.txt` → совпадает с `warnings_examples_emulate.out.txt` (без строк «код:» и «эмуляция …»): «итог: записей «вне таблиц» 3 в 23 примерах», три записи 04a (§1.3), прочих WARNING 0 у всех. Если отличается восьмая значащая цифра давления в тексте — допустимо (эмуляция брала давление из Па; объяснить в отчёте). Иное расхождение — стоп, разбор.
3. Время: строка времени не печатается — сравнить длительность п. 2 с шагом 0 (п. 5); рост больше 10 % — разобрать (`pvt_range_warnings` на каждом подшаге).
4. Из `HydroSolverPrototype/Prototype_1.0.3`: полная регрессия `& $PY regression\run_regression.py` (~45 мин, запускать в фоне; HEAD worktree зафиксировать до запуска — «Правка прототипа» в шапке) → 17/17 PASS. Выход `OUTPUT/REGRESSION_<время>/` удалить.
5. Тесты прототипа → 105 passed.
6. Полный прогон GPN: `& $PY -m pytest tests/ -q` → 1946 passed (~10 мин).
7. Числа CHANGELOG шага 1 («105 passed», «17/17») — сверить с п. 4–5.

**Регресс:** полный (п. 6) — итоговый прогон `/implement`.

**Оценка:** ~1 ч (в основном ожидание).

### Шаг 5: vault

**Что сделать:**
1. Реестр, запись DEBT-027: статус «✅ ГОТОВО (дата)» с итогом (тесты GPN 1938 → 1946, прототипа 101 → 105, регрессия 17/17, отпечатки 23/23 побитово, записи «вне таблиц» только 04a); поле **План:** уже есть (шаг 5.2 планирования).
2. Заметка `vault/knowledge/numerics/ячейка фронта даёт ложный выход за кривую насыщения таблицы.md`: механизм (§1.2), таблица замеров, порог (§2.4), случай 04a; ссылки на план и issue. Ссылку — в `vault/00-home/index.md` (раздел numerics).
2a. `vault/knowledge/decisions/P8-формат-ввода-json.md:222` — строка таблицы проверок фабрики называет `_warn_initial_table_range` проверкой «выход за таблицы (BUG-017)» только начального состояния. Дописать: выход за таблицы — начальное состояние (BUG-017) и каждый принятый шаг (DEBT-027, `PrototypeHydroAdapter.warn_table_range`, одна запись на категорию; только табличная PVT). P8 — источник перечня проверок ввода для README пакета (FEAT-031).
3. `vault/issues/debt-027/05-comment-done.md` — результат; `gh issue comment 116 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-027/05-comment-done.md`.
4. Выходы проб реализации (`*_impl.out.txt`, `*_base.out.txt`) — в `vault/issues/debt-027/probes/`.

## 4. Тестовая стратегия

**Неизменность поведения:**
- Истории 23 примеров побитово (`fingerprint_bug026.py`, шаг 0 ↔ шаг 4).
- Регрессия прототипа 17/17 PASS, включая текст предупреждений эталона.
- Существующие тесты, покрывающие затронутый код: `tests/test_factory_prototype.py::TestInitialRangeWarnings` (2), `tests/test_factory_standing_hydro.py::test_no_range_warnings`, `tests/test_prototype_adapter.py` (адаптер без флага), тесты прототипа `test_pvt_clamp.py` (7), `test_output_contract.py::test_run_summary_records_range_warning_without_extrapolation`.

**Новые тесты:**

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_locus_above_default_reports_any_gas_active_cell` | прототип `tests/test_pvt_clamp.py` | ячейка с флагом газа, $S_g$ = 0, 181 бар > 180 | без параметра — прежний текст «gas-active max P=» | смену умолчания (эталон регрессии) |
| `test_locus_above_free_gas_test_skips_front_cell` | то же | то же, `free_gas_sg=1e-6` | категории нет | возврат ложного срабатывания |
| `test_locus_above_free_gas_test_reports_free_gas` | то же | $S_g$ = 0.02 | «free gas Sg up to 0.02 at P up to 181 bar» | потерю настоящего выхода |
| `test_warning_category_ignores_numbers` | то же | два текста о ветвях давления с разными числами | одна категория, `unique_warnings` — один | повторы записи в журнале |
| `TestFreeGasFilter::test_front_cell_not_reported` | `tests/test_table_range_warnings.py` | модель `configs/table_pvt`, 151 бар > 150, $S_g$ = 0 | без параметра есть, с `FREE_GAS_SG` — нет | то же на таблицах GPN |
| `TestFreeGasFilter::test_free_gas_reported` | то же | $S_g$ = 0.02 | «free gas Sg up to 0.02» | то же |
| `TestRunWarnings::test_inside_tables_silent` | то же | штатный `configs/table_pvt` | записей нет | шум в штатном расчёте |
| `TestRunWarnings::test_front_cell_not_reported` | то же | $p_{wf}$ = 8 МПа (предусловие: без фильтра срабатывание есть) | записей нет | ложное срабатывание (12 примеров) |
| `TestRunWarnings::test_below_gas_table_reported_once` | то же | $p_{wf}$ = 2 МПа | 2 записи, t = 0.04167 сут, газ ниже таблицы и кривая ниже | молчаливый выход / повторы на каждом шаге |
| `TestRunWarnings::test_initial_category_not_repeated` | то же | $p_0$ = 32 МПа (предусловие: выход и в конце) | 2 записи, обе «Начальное состояние» | повтор начальной категории |
| `TestRunWarnings::test_free_gas_above_table_reported` | то же | пример 04a, 3 ч | 3 записи, «кривая выше» при t = 0.08333 сут, «free gas» | потерю настоящего случая |
| `TestRunWarnings::test_standing_path_not_checked` | то же | `configs/baseline.json` (Стендинг) | `_check_table_range is False` | `AttributeError` на пути Стендинга |

**Baseline:** 1938 / 1662 (GPN, `8e432a3`), 101 (прототип), `--quick` 11/11 (аудит 1), полная 17/17.

## 5. Критерии завершения

- [ ] Шаги 0–5 выполнены.
- [ ] GPN: 1946 тестов (или база шага 0 + 8), полный прогон passed; быстрый уровень 1670 passed.
- [ ] Прототип: 105 passed; полная регрессия 17/17 PASS побитово (включая `warnings`), CHANGELOG — раздел DEBT-027 с фактическими числами.
- [ ] Отпечатки 23 примеров — как в шаге 0.
- [ ] `warnings_examples.py`: записи «вне таблиц» только у 04a (3), совпадают с эмуляцией.
- [ ] README 04, 04a, 18 обновлены.
- [ ] Vault: реестр, заметка, index, комментарий в issue #116.
- [ ] Время расчёта примеров не выросло больше чем на 10 %.

## 6. Связь формула → код

Формул нет: задача — диагностика входных данных. Ссылки `eq:` в новых docstring и комментариях не нужны (`tests/test_eq_references.py` проверяет только наличие корректных меток там, где они есть).

## 7. Верификация плана

**Раунд 1 (полнота):** все файлы §2.2 — в шагах 1–3; у каждого шага есть проверка; зависимости 0 → 1 → 2 → 3 → 4 → 5 без циклов; подводные камни §2.5 адресованы (два ⚠️ — с действиями); критерии проверяемы командами шага 4.

**Раунд 2 (корректность):** функции и строки сверены на базе: `pvt_range_warnings` — `diagnostics.py:22`, блок кривой — 35-42, `unique_warnings` — 56-68; `PrototypeHydroAdapter.__init__` — `prototype_adapter.py:132`, `_stage4_key` — 254, `# ── Шаг 4` — 256; `_warn_initial_table_range` — `factory.py:353`, вызов — 462-463, `return PrototypeHydroAdapter` — 471-473; README 04 — 304-313, 04a — 328-346, 18 — 177-182. Код шагов 1–2 проверен эмуляцией (`emulate_debt027.py`, `proto_tests_emulate.py`, `warnings_examples.py --emulate`) — ожидания тестов взяты из её вывода. Импорт `user_log` в адаптере циклов не даёт (`log.py` пакет не импортирует). Истории от проверки не зависят (только чтение состояния).

**Раунд 3 (автономность):** пути полные; `$PY` и `PYTHONPATH` — «Как начать»; почему именно так — §1–2; термины: «ячейка фронта» (§1.2), «свободный газ» ($S_g$ выше порога), «категория» (начальные слова текста предупреждения прототипа).

## 8. Пробы планирования (`vault/issues/debt-027/probes/`)

| Скрипт | Что показал |
|---|---|
| `repro_pwf2.py` | 04 при 2 МПа: журнал пуст, диагностика прототипа — газ ниже таблицы; при 8 МПа — ложное «кривая выше» (ячейка 26, $S_g$ = 0) |
| `front_cell_locus.py` | VAL-005: 182.14 бар — ячейки фронта, $S_g$ = 1.9·10⁻¹⁴ / 0 |
| `rs0_last_branch.py` | 14 из 15 табличных примеров: $R_{s,0}$ = последняя ветвь |
| `scan_examples.py` | диагностика без фильтра на всех подшагах 15 табличных примеров |
| `gas_above_pb_04a.py` | 04a: газ выше $p_b$ в ячейках 65–69 до конца |
| `golden_locus_cases.py` | эталон прототипа: 15 кейсов — шум ≤ 3.6·10⁻⁹, T10 — газ 2.6·10⁻³ |
| `free_gas_threshold_04a.py` | 04a: газ выше $p_b$ появляется на 2 ч сразу > 10⁻³ |
| `table_config_cases.py` | сценарии тестов на `configs/table_pvt` (без фильтра) |
| `emulate_debt027.py` | эмуляция кода шагов 1–2, сценарии тестов |
| `warnings_examples.py` | журнал 23 примеров: база (`_base`) и эмуляция (`_emulate`) |
| `readme04_pwf.py` | README 04: ниже газовой таблицы при $p_{wf} \le 4$ МПа |
| `proto_tests_emulate.py` | сценарии тестов прототипа на фикстуре `Nabor_1b.xlsx` |
| `extract_plan_tests.py`, `emu_tests/` | код тестов шага 2 извлекается из плана и гоняется против эмуляции: 8 passed (`emu_tests.out.txt`); только с кодом шага 1 — 3 красных (`emu_tests_step1_only.out.txt`) |
| `fingerprint_emulate.py` (аудит 1) | отпечатки 23 примеров с кодом плана — как на базе (`audit1_fingerprint_emulate.out.txt` ↔ `audit1_fingerprint_base.out.txt`) |
| `front_cell_locus.py examples\18_prototype_input\config.json` (аудит 1) | ячейки 12, 13 при $t$ = 60 с — на конфиге самого примера 18 (`audit1_front_cell_18.out.txt`) |
| `audit1_regression_quick.out.txt` (аудит 1) | регрессия прототипа `--quick` на `8e432a3`: 11/11 PASS |
