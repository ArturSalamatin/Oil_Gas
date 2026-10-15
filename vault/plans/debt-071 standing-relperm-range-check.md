---
tags:
  - план
  - рефакторинг
date: 2026-10-14
issue: DEBT-071
github: 122
branch: refactor/debt-071/standing-relperm-range-check
status: в процессе
worktree: .worktrees/debt-071
audit:
  date: 2026-10-15
  round: 1
  found: 8
  auto-fixed: 8
  manual-required: 0
---

# DEBT-071: выход $S_g$ за таблицу ОФП на пути Стендинга — диагностика

**Задача:** [[известные баги и технический долг#DEBT-071]], issue [#122](https://github.com/ArturSalamatin/Oil_Gas/issues/122).
**Подтип:** рефакторинг (выделение функции в прототипе + выбор проверки в адаптере; числа расчёта не меняются).
**Ветка:** `refactor/debt-071/standing-relperm-range-check` от `numerical_scheme/implementation`.
**База плана:** `a7b0dc0` (аудит 1; план написан на `4abe804`, после него влиты DEBT-067 — `8c045d7`: `prototype_adapter.py` +2 строки у `_failure_details`, раздел CHANGELOG прототипа, — и DEBT-062 — `aecd1e4`: `tests/test_eq_references.py`). Номера строк — на `a7b0dc0`.
**Пробы планирования:** `vault/issues/debt-071/probes/` (скрипты + `*.out.txt`, таблицы ОФП проб — CSV там же).
**Продолжение:** [[DEBT-027]] (та же проверка на табличной PVT, план [[debt-027 table-range-diagnostics]]).

## Решения плана (можно оспорить на аудите)

1. **Вариант 1 issue:** в прототипе ОФП-часть `pvt_range_warnings` выделяется в функцию `relperm_range_warnings(model, state)`; `pvt_range_warnings` зовёт её последней — тексты и порядок предупреждений побитово прежние, эталон регрессии прототипа не меняется.
2. **Адаптер:** параметр `table_pvt: bool = True` рядом с `check_table_range`. `True` — как сейчас (`pvt_range_warnings`, PVT и ОФП), `False` — только `relperm_range_warnings`. Фабрика передаёт `check_table_range=True` всегда и `table_pvt=isinstance(pvt, TableFullPVT)`.
3. **ОФП проверяется на всём пути Стендинга, включая Кори.** Кори фабрика табулирует на $S_g \in [0, 1]$ (`factory.py:504-508`), а принятые состояния держат $S_g \ge 0$ точно (§2.5): проверка на Кори молчит. Отдельное условие `relperm.model == "table"` ничего не добавляет.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-071 в `vault/roadmap/известные баги и технический долг.md` и тело issue `vault/issues/debt-071/01-issue-body.md`.
3. Worktree и ветку создаёт `/implement`: `.worktrees/debt-071`, ветка `refactor/debt-071/standing-relperm-range-check` от `numerical_scheme/implementation`. Проверка базы: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`.
4. Все команды pytest — из `numerical_solver/` worktree. Venv — общий, основного каталога; в worktree его нет: `$PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"`.
5. ⚠️ **Скрипты вне pytest** (пробы `vault/issues/debt-071/probes/*.py`, `fingerprint_bug026.py`) в worktree берут пакет основного каталога, если не задать `PYTHONPATH` (память «Worktree и PYTHONPATH»): перед запуском `$env:PYTHONPATH = "<worktree>\numerical_solver;<worktree>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"`. Пробы печатают «код: …» и «прототип: …» — сверяй, что это worktree.
6. Исходный замер (шаг 0) — до любых правок.
7. После каждого шага — тест шага и регресс по полю «Регресс». Полный прогон — в конце (`/implement` §3.1).

## 1. Контекст

### 1.1. Что не так

Прототип (`radial_blackoil`) берёт $k_{ro}$, $k_{rg}$ за краями таблицы ОФП с краёв, без экстраполяции и молча: `relperm.py:7-8`, `np.interp`. Выход называет `pvt_range_warnings` (`radial_blackoil/diagnostics.py:22-65`): девять категорий, из них две — ОФП (строки 60-64, `RELPERM Sg below table`, `RELPERM Sg above table`). С [[DEBT-027]] адаптер GPN зовёт её после каждого принятого шага и для начального состояния — но только на табличной PVT: `check_table_range=isinstance(pvt, TableFullPVT)` (`gpn_multiphase_solver/factory.py:468-471`). Функция первой строкой проверки читает газовую таблицу `model.pvt.gp`, а у `HydroPVTtoBlackOilAdapter` (обёртка корреляций Стендинга) её нет — `AttributeError`.

Итог: на пути Стендинга молчат и PVT-категории (правильно: свойства вычисляются по формулам, краёв нет), и ОФП-категории (неправильно: таблица ОФП из CSV — та же, что на табличном пути).

### 1.2. Где это видно — замеры планирования

| Что | Замер | Проба |
|---|---|---|
| 8 примеров Стендинга (01, 02, 03, 05, 17, 19, 20, 21), все принятые шаги | min $S_g$ = 0 у всех; max — 0 (01, 02), 0.081 (03), **0.014 (05, таблица до 0.8)**, 0.41–0.45 (17, 19–21, Кори) | `scan.out.txt` |
| 05: принятых шагов | 72 из 72 интервалов, без дробления | `scan.out.txt` |
| 05 с таблицей до $S_g$ = 0.01 ($k_{ro}$ = 0.98, $k_{rg}$ = 0.001 на краю), код плана | принятый подшаг 56.25 с: max $S_g$ = **0.917**, запись «RELPERM Sg above table»; затем отказ первого часа при dt/512 | `scenarios.out.txt` |
| 05 с таблицей с $S_g$ = 0.05 (не по SGOF), код плана | одна запись «Начальное состояние … RELPERM Sg below table: min Sg=0, table min=0.05», дальше не повторяется | `scenarios.out.txt` |
| 23 примера, код плана в памяти | записи «вне таблиц» — только три у 04a, как на базе (DEBT-027); у примеров Стендинга — 0 | `warnings_emulate.out.txt` ↔ `warnings_base.out.txt` |

Пример 05 — единственный путь «Стендинг + таблица ОФП» в примерах — края таблицы не достигает (×57 запаса). Задача закрывает дыру для пользовательских таблиц.

**Настоящий случай — обрезанная таблица.** Таблица ОФП, у которой $k_{ro}$ последнего узла больше нуля, выше края держит $k_{ro}$ и $k_{rg}$ постоянными: нефть подвижна при любой $S_o$ и уходит, газ остаётся. В 05 с таблицей до 0.01 у забоя за 56 с $S_g$ доходит до 0.917 на **принятом** подшаге, а затем шаг не сходится и при dt/512. Текст отказа таблицу не называет («4 открыта — корень с S_g > 0.98»); после задачи ему предшествует запись «вне таблиц» с краем таблицы. Сам отказ — отдельная задача DEBT-073 (§2.6).

### 1.3. Что станет после

- На пути Стендинга адаптер проверяет только таблицу ОФП — `relperm_range_warnings` прототипа — на начальном состоянии и после каждого принятого шага, по правилам DEBT-027: одна запись на категорию за расчёт, с моментом первого выхода.
- Табличный путь не меняется: та же `pvt_range_warnings` с `free_gas_sg`, те же тексты (замер `warnings_emulate.out.txt`: записи 04a побитово те же).
- Прототип: `pvt_range_warnings` возвращает те же тексты в том же порядке — регрессия 17/17 побитово, включая `warnings` эталона.
- Числа расчёта не меняются: проверка только читает состояние.

## 2. Анализ

### 2.1. Исходное состояние (база `a7b0dc0`, аудит 1, 2026-10-15)

| Что | Значение |
|---|---|
| Тесты GPN (`--collect-only -q`) | 1987, быстрый уровень 1711 (при планировании на `4abe804` — 1970 / 1694) |
| Тесты прототипа (`--collect-only -q`) | 107 |
| Регрессия прототипа | 17/17 PASS побитово — по CHANGELOG DEBT-067 (влит `8c045d7`) |
| Записей «вне таблиц» в 23 примерах | 3 (только 04a) — `audit1_warnings_base.out.txt` (на `4abe804` — `warnings_base.out.txt`, то же) |
| Время расчёта 05, 72 ч | ~0.2 с (`scan.out.txt`) |

### 2.2. Затронутые файлы

| Файл | Строки (база) | Что меняется |
|---|---|---|
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/diagnostics.py` | 22-25, 60-65 | новая `relperm_range_warnings`; `pvt_range_warnings` зовёт её |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvt_clamp.py` | 1-3, после 32 | импорт, +2 теста |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` | конец (после 194) | раздел «Local changes — GPN project (DEBT-071)» |
| `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py` | 44-48, 184-221, 223-240 | докстринг модуля; параметр `table_pvt`; выбор проверки в `warn_table_range` |
| `numerical_solver/gpn_multiphase_solver/factory.py` | 357-360, 464-471 | комментарии; `check_table_range=True`, `table_pvt=…` |
| `numerical_solver/gpn_multiphase_solver/pvt/hydro_to_blackoil_adapter.py` | 25, 29-32 | устаревший комментарий о диагностике |
| `numerical_solver/tests/test_table_range_warnings.py` | 1-30, 156-159 | докстринг, импорт `pytest`, помощник; −1 тест, +класс из 5 тестов |
| `numerical_solver/tests/test_factory_standing_hydro.py` | 260-265 | докстринг `test_no_range_warnings` |

**Не меняются (зона неприкосновенности):** `simulation.py` прототипа (его цикл зовёт `pvt_range_warnings` без параметра — тексты те же); `blackoil.py`, `relperm.py`, всё прочее в прототипе; `simulator.py`, `hydro/base.py`; README примеров (в 05 выхода нет; README 04a, 18 описывают табличный путь — без изменений); `FREE_GAS_SG`.

**Вызывающие:** `pvt_range_warnings` — `simulation.py:57, 97` (прототип), `prototype_adapter.py:232` (адаптер), тесты `tests/test_pvt_clamp.py` (прототип), `tests/test_table_range_warnings.py` (GPN). `PrototypeHydroAdapter(…)` с `check_table_range` — только `factory.py:468-471`; прочие создания адаптера в тестах (`tests/test_prototype_adapter.py` и др.) параметр не передают — у них проверка выключена, как прежде. `_check_table_range` читает только `test_table_range_warnings.py:159` (удаляется шагом 2).

### 2.3. Варианты

| | Суть | Плюсы | Минусы |
|---|---|---|---|
| **1 (выбран)** | `relperm_range_warnings(model, state)` в прототипе; `pvt_range_warnings` зовёт её последней; адаптер на пути Стендинга зовёт только её | разделение по смыслу: ОФП не зависит от модели PVT; правка прототипа, а не обход (память «Prototype editable») | правка прототипа — тесты и регрессия прототипа |
| 2 | параметр `pvt_range_warnings(…, pvt_tables=True)`; при `False` — только ОФП | одна функция, одно место вызова | логический флаг, выключающий 7 из 9 категорий; имя «pvt…» у вызова без PVT вводит в заблуждение |
| 3 | адаптер сам сравнивает $S_g$ с `model.relperm.sg[0]`, `sg[-1]` | без правки прототипа | копия логики и текстов прототипа в адаптере — против правила проекта, копии разойдутся |

Промежуточные состояния варианта 1 рабочие: после шага 1 прототип уже содержит функцию, адаптер её ещё не зовёт — GPN ведёт себя как на базе.

### 2.4. Подводные камни

| Пункт | Статус | Как адресован |
|---|---|---|
| Все вызывающие найдены | ✅ | §2.2; `pvt_range_warnings` сохраняет сигнатуру и вывод |
| Зависимости пакетов | ✅ | новых нет; адаптер импортирует из `radial_blackoil.diagnostics` внутри метода, как сейчас |
| Обратная совместимость API | ✅ | `table_pvt` — новый параметр по ключу с умолчанием `True` (= прежнее поведение); `check_table_range` по умолчанию `False` — адаптеры тестов не проверяют, как прежде |
| Состояние при ошибке | ✅ | проверка только пишет журнал, исключений не бросает; на пути Стендинга `AttributeError` больше невозможен — `pvt_range_warnings` там не зовётся (тест `test_relperm_above_table_reported_alone` проверяет предусловие) |
| Тесты | ✅ | эмуляция: 5 новых тестов GPN passed (`plan_tests_emulate.out.txt`), 2 теста прототипа OK (`proto_tests_emulate.out.txt`); `TestInitialRangeWarnings`, `test_no_range_warnings`, остальные тесты DEBT-027 — без изменения ожиданий |
| Циклические импорты | ✅ | `relperm_range_warnings` — в том же модуле `diagnostics.py`, новых импортов нет |
| Ссылки на уравнения | ✅ | формул нет; докстринги — по `DEBT-071`, без `eq:` (`tests/test_eq_references.py` не задет) |
| Конфиги | ✅ | новых полей нет |
| Связь с задачами | ⚠️ | DEBT-067 и DEBT-062 влиты до аудита 1 (`8c045d7`, `aecd1e4`) — учтены в базе `a7b0dc0`: строки адаптера +2, раздел DEBT-067 в конце CHANGELOG (раздел DEBT-071 — после него), сторож `tests/test_eq_references.py` запрещает номер после метки — новые тексты плана меток не содержат. Активных worktree на аудите нет. **DEBT-073** (issue #123, план не написан; рекомендованы варианты 1 + 3 — предупреждение фабрики и край таблицы в тексте отказа): тест шага 2 `test_relperm_above_table_before_failure` фильтрует журнал по «вне таблиц» и ищет в отказе «не сошёлся» — к вариантам 1 и 3 устойчив; вариант 2 (отказ фабрики) заменит `RuntimeError` на `ValueError` — тогда тест переписывает DEBT-073. Если база уедет к началу реализации: числа шага 0 записать как есть, целевые = база шага 0 + приращение плана; влитие посреди замеров даёт ложные расхождения (память «Параллельное влитие») — сверять `git log` базы до и после шагов 0 и 3 |
| Производительность | ✅ | на пути Стендинга добавляется min/max по $S_g$ на каждом принятом шаге — пренебрежимо; табличный путь не меняется. Быстрый уровень тестов: +~3.5 с (из них 2.8 с — `test_relperm_above_table_before_failure`: отказ дроблением до dt/512; `plan_tests_emulate.out.txt`) |
| Прототип | ⚠️ | правка `diagnostics.py`; тексты и порядок прежние → регрессия 17/17 PASS **побитово, включая текст предупреждений** (`regression/run_regression.py` сравнивает `warning_count` и `warnings` с эталоном). FAIL с «warning text differs from golden» = нарушен порядок или текст — исправлять код, не эталон |
| Таблица ОФП с $S_g$ первого узла > 0 | ⚠️ | SGOF (OPM Flow Manual, табл. 8.165) требует начала с 0, проект это не проверяет (DEBT-044). С такой таблицей запись «RELPERM Sg below table» будет у **каждого** расчёта при $t = 0$ — на табличной PVT это уже так с DEBT-027. Это верная диагностика (ниже первого узла $k_r$ — с края), не шум |

### 2.5. Почему проверка на Кори безопасна

`_get_or_create_proto_rp` (`factory.py:504-508`) табулирует Кори на `np.linspace(0.0, 1.0, 101)`. Категории ОФП срабатывают при $S_g < 0 - 10^{-9}$ или $S_g > 1 + 10^{-9}$ (`_range_tol`). Отрицательной $S_g$ в принятом состоянии нет при любом `numerics.sg_switch_tol`: прототип при принятии обнуляет малые отрицательные $S_g$ газовых ячеек (`radial_blackoil/blackoil.py`, `_advance_phases` — `trial.sg[tiny]=0.0`; ступень 4 — `new.sg[mask&(new.sg<0)]=0.0`), а ячейки с $S_g < -$`sg_switch_tol` переводит в однофазные с $S_g = 0$. Поэтому «RELPERM Sg below table» возможна только у таблицы, начинающейся с $S_g > 0$. Замер: на всех 8 примерах Стендинга min $S_g$ = 0 точно, max ≤ 0.452 (`scan.out.txt`); `baseline.json` (Стендинг + Кори, 96 ч) — записей нет (`scenarios.out.txt`). Запись на Кори означала бы $S_g > 1$ — её стоит видеть.

### 2.6. Обнаруженные проблемы

1. **[[DEBT-073]] (зарегистрирована после плана, issue [#123](https://github.com/ArturSalamatin/Oil_Gas/issues/123)): таблица ОФП, у которой $k_{ro}$ последнего узла больше нуля, — у забоя $S_g \to 1$, первый шаг не сходится, текст отказа таблицу не называет.** Выше края $k_{ro}$ и $k_{rg}$ постоянны (`np.interp`): нефть подвижна при любой $S_o$. Замеры (`scenarios.out.txt`, `cut21.out.txt`, `cut21cap.out.txt`):
   - 05 с таблицей до 0.01: принятый подшаг 56 с с $S_g$ = 0.917, затем отказ при dt/512 (с DEBT-071 — запись «вне таблиц» перед отказом);
   - 05 при $R_{s,0}$ = 100 с таблицей до 0.1 ($k_{ro}$ = 0.8 на краю): отказ первого подшага, принятых состояний нет — записи нет и с DEBT-071;
   - 21 с таблицей Кори примера, обрезанной на 0.2 / 0.3 / 0.35: отказ первого подшага; та же таблица до 1.0 (контроль) — сходится;
   - подмена ограничения начального $S_g$ ([[BUG-018]], `_sg_activation_cap`: без узла $k_{ro} = 0$ оно `None`) на 0.94 не помогает — причина в таблице, а не в начальном приближении.
   
   Не блокирует DEBT-071. Варианты для DEBT-073: предупреждение (или отказ) фабрики при $k_{ro} > 0$ в последнем узле; край таблицы в тексте отказа (issue рекомендует 1 + 3). ⚠️ Тест `test_relperm_above_table_before_failure` этого плана использует такую таблицу и ожидает отказ: к вариантам 1 и 3 он устойчив (§2.4), отказ фабрики (вариант 2) его изменит.
2. **Устаревший комментарий** `pvt/hydro_to_blackoil_adapter.py:25, 29-32`: «diagnostics.py — rs_values и pb для предупреждений о выходе за таблицу». На пути Стендинга PVT-проверка не зовётся ни до, ни после задачи; `rs_values` никто не читает, `pb` нужен `blackoil.py` (`_pressure_fd_step`). Исправляется шагом 2.

## 3. Шаги

### Шаг 0: исходный замер

**Цель:** зафиксировать числа базы в worktree до правок.

**Файлы:** нет правок.

**Что сделать** (из `numerical_solver/` worktree, `$env:PYTHONPATH` — п. 5 «Как начать»):
1. `git log --oneline -3 numerical_scheme/implementation` — записать (база плана `a7b0dc0`; если уехала — см. §2.4 «Связь с задачами»).
2. `& $PY -m pytest tests/ --collect-only -q` → 1987 на базе плана (больше — влиты другие задачи; записать — целевые числа сдвигаются на ту же разницу).
3. `& $PY -m pytest tests/ -m "not slow" -q` → все passed (1711 на базе плана), записать время.
4. Из `HydroSolverPrototype/Prototype_1.0.3`: `& $PY -m pytest tests -q` → все passed (107 на базе плана); `& $PY regression\run_regression.py --quick` → 11/11 PASS (~8 мин). Выход `OUTPUT/REGRESSION_<время>/` удалить.
5. `$env:PYTHONIOENCODING = "utf-8"; & $PY ..\vault\issues\bug-026\probes\fingerprint_bug026.py > ..\vault\issues\debt-071\probes\fingerprint_base.out.txt` (~4 мин) — отпечатки 23 историй. На `a7b0dc0` — «итог: расхождений 1 из 23»: у 14 `d801857e833491c7` вместо ожидаемого скриптом `762bb8afd474ffa8` (DEBT-067 меняет первые сутки 14, ожидания скрипта не обновлялись; замер аудита 1 — `audit1_fingerprint_base.out.txt`, кодировка cp1251). Это не ошибка: эталон для шага 3 — файл этого пункта, а не «ОК» скрипта.
6. `& $PY ..\vault\issues\debt-071\probes\standing_relperm_scan.py warnings > ..\vault\issues\debt-071\probes\warnings_wt_base.out.txt` (~2 мин) → как `audit1_warnings_base.out.txt`: «итог: записей «вне таблиц» 3 в 23 примерах», только 04a, прочих WARNING 0. Записать длительность.

**Проверка:** числа записаны в отчёт реализации.

**Оценка:** ~20 мин (в основном ожидание).

### Шаг 1: прототип — `relperm_range_warnings`

**Цель:** ОФП-часть проверки выхода за таблицы вызывается отдельно; вывод `pvt_range_warnings` побитово прежний.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/diagnostics.py`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvt_clamp.py`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`

**Контекст:** `pvt_range_warnings` (строки 22-65) проверяет PVT и ОФП одним вызовом и первой проверкой читает `model.pvt.gp`. У обёртки Стендинга `gp` нет. ОФП-часть (строки 60-64) от PVT не зависит: читает `model.relperm` и `state.sg`. Стиль прототипа — плотный, однострочный; комментарии GPN-правок — английские, с пометкой «(GPN project)», как у DEBT-027 (строки 46-50).

**Что сделать:**
1. `diagnostics.py`: перед `def pvt_range_warnings` (строка 22) вставить функцию; в `pvt_range_warnings` убрать `rp=model.relperm` из строки 25 и заменить строки 60-64 вызовом.

   До (строки 22-25):
   ```python
   def pvt_range_warnings(model,state,free_gas_sg=None):
       """Return warnings for ACCEPTED states only. Evaluation itself always clamps."""
       p=np.asarray(state.pressure_bar,float); rs=np.asarray(state.rs_sm3_sm3,float)
       w=[]; pvt=model.pvt; rp=model.relperm
   ```
   После:
   ```python
   def relperm_range_warnings(model,state):
       """Relperm part of pvt_range_warnings: Sg outside the RELPERM table, ACCEPTED states only."""
       # DEBT-071 (GPN project): callable alone -- the GPN adapter on the Standing correlation
       # path has a RELPERM table but no PVT tables (its PVT object has no gp).
       sg=np.asarray(state.sg,float); rp=model.relperm; w=[]
       if np.min(sg) < rp.sg[0]-_range_tol(rp.sg[0]):
           w.append(f'RELPERM Sg below table: min Sg={np.min(sg):.8g}, table min={rp.sg[0]:.8g}. Endpoint value used; no extrapolation.')
       if np.max(sg) > rp.sg[-1]+_range_tol(rp.sg[-1]):
           w.append(f'RELPERM Sg above table: max Sg={np.max(sg):.8g}, table max={rp.sg[-1]:.8g}. Endpoint value used; no extrapolation.')
       return w


   def pvt_range_warnings(model,state,free_gas_sg=None):
       """Return warnings for ACCEPTED states only. Evaluation itself always clamps."""
       p=np.asarray(state.pressure_bar,float); rs=np.asarray(state.rs_sm3_sm3,float)
       w=[]; pvt=model.pvt
   ```
   До (строки 60-65):
   ```python
       sg=np.asarray(state.sg,float)
       if np.min(sg) < rp.sg[0]-_range_tol(rp.sg[0]):
           w.append(f'RELPERM Sg below table: min Sg={np.min(sg):.8g}, table min={rp.sg[0]:.8g}. Endpoint value used; no extrapolation.')
       if np.max(sg) > rp.sg[-1]+_range_tol(rp.sg[-1]):
           w.append(f'RELPERM Sg above table: max Sg={np.max(sg):.8g}, table max={rp.sg[-1]:.8g}. Endpoint value used; no extrapolation.')
       return w
   ```
   После:
   ```python
       # DEBT-071 (GPN project): the relperm part is a function of its own -- same texts, same order (last).
       w.extend(relperm_range_warnings(model,state))
       return w
   ```
   Тексты f-строк скопировать **побитово** (регрессия сравнивает текст). Переменная `sgc` в блоке кривой насыщения (строка 51) — своя, её не трогать.
2. `test_pvt_clamp.py`, строки 1-3.
   До:
   ```python
   import unittest, numpy as np
   from tests.helpers import model_and_state
   from radial_blackoil.diagnostics import pvt_range_warnings, warning_category, unique_warnings
   ```
   После:
   ```python
   import unittest, numpy as np
   from types import SimpleNamespace
   from tests.helpers import model_and_state
   from radial_blackoil.diagnostics import pvt_range_warnings, relperm_range_warnings, warning_category, unique_warnings
   ```
3. `test_pvt_clamp.py`: после `test_warning_category_ignores_numbers` (строка 32), перед пустой строкой и `if __name__`:
   ```python
       # DEBT-071 (GPN project): the relperm part of the range check is callable alone -- the GPN
       # adapter on the Standing correlation path has a relperm table but no PVT tables (no gp).
       def test_relperm_warnings_close_pvt_range_warnings(self):
           _,m,s=model_and_state(p0=350); s.sg[0]=0.9; w=pvt_range_warnings(m,s); r=relperm_range_warnings(m,s)
           self.assertEqual(r,['RELPERM Sg above table: max Sg=0.9, table max=0.85. Endpoint value used; no extrapolation.'])
           self.assertEqual(w[-1:],r); self.assertTrue(any(x.startswith('GAS_PVT pressure above') for x in w))
       def test_relperm_warnings_need_no_pvt(self):
           _,m,s=model_and_state(); s.sg[0]=-0.01; stub=SimpleNamespace(relperm=m.relperm)
           self.assertEqual([warning_category(x) for x in relperm_range_warnings(stub,s)],['RELPERM Sg below table'])
           with self.assertRaises(AttributeError): pvt_range_warnings(stub,s)
   ```
   Таблица ОФП фикстуры `Nabor_1b.xlsx` — $S_g$ = 0…0.85 (15 узлов): 0.9 выше края, −0.01 ниже. При $p_0$ = 350 бар `pvt_range_warnings` даёт и `GAS_PVT pressure above` (существующий тест строки 13) — первый тест проверяет, что ОФП-записи идут последними. Второй — что ОФП-проверке PVT не нужен, а полной проверке нужен (почему GPN её не зовёт на пути Стендинга).
4. `CHANGELOG_1.0.3.md` — в конец, после раздела «Local changes — GPN project (DEBT-067): the per-cell test accepts a solve at its rounding limit» (последний раздел на `a7b0dc0`, строки 196-203):
   ```markdown

   ## Local changes — GPN project (DEBT-071): relperm part of the range check callable alone
   - Problem: `pvt_range_warnings` checks the PVT tables and the RELPERM table in one call and reads the gas table `model.pvt.gp` first. On the Standing correlation path the GPN adapter wraps the correlations in a PVT object without tables (no `gp`): the call would fail with `AttributeError`, so GPN did not call it there, and Sg outside a user RELPERM table went unreported (GPN example 05: Standing PVT + RELPERM table up to Sg = 0.8).
   - New `relperm_range_warnings(model, state)`: the two RELPERM categories; reads only `model.relperm` and `state.sg`. `pvt_range_warnings` calls it last: its texts and their order are the former ones.
   - The prototype's own runs are unchanged: tests N passed, regression 11/11 quick and 17/17 full PASS bitwise, golden warnings unchanged. The GPN adapter calls `relperm_range_warnings` alone on the Standing path, `pvt_range_warnings` on tabular PVT as before.
   - Physics, residual equations, Newton and well semantics are unchanged. The distribution version stays `1.0.3+gpn.1`. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
   - Tests: `tests/test_pvt_clamp.py` (+2); `numerical_solver/tests/test_table_range_warnings.py` of the GPN project (+5, −1).
   - Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/122; plan: `vault/plans/debt-071 standing-relperm-range-check.md` of the GPN project.
   ```
   «N passed» и «17/17 full» — вписать фактические числа шага 3 (до шага 3 оставить «N», шаг 3 п. 6 сверяет).

**Проверка после шага:**
- Из `HydroSolverPrototype/Prototype_1.0.3`: `& $PY -m pytest tests -q` → все passed (107 + 2 = 109 на базе плана).
- `& $PY regression\run_regression.py --quick` → 11/11 PASS (побитово, включая `warnings`). FAIL «warning text differs» — сверить f-строки с `git show HEAD:…/diagnostics.py`.
- Регресс GPN: быстрый (`& $PY -m pytest tests/ -m "not slow" -q` → 1711 passed): адаптер ещё зовёт `pvt_range_warnings`, вывод прежний. Эквивалентность правки проверена аудитом 1 на копии `diagnostics.py` в памяти: обе цитаты «До» найдены ровно по разу, `pvt_range_warnings` побитово та же на 6000 сравнениях со всеми 9 категориями (`audit1_diag_equivalence.py`, `.out.txt`).

**Подводные камни:** §2.4 «Прототип», «Связь с задачами» (CHANGELOG).

**Зависимости:** требует шаг 0; блокирует шаг 2.

**Оценка:** ~15 строк кода + 10 тестов + 7 CHANGELOG; ~25 мин (из них 8 — регрессия).

### Шаг 2: адаптер, фабрика, тесты GPN

**Цель:** на пути Стендинга адаптер проверяет таблицу ОФП на начальном состоянии и после каждого принятого шага; на табличном — как прежде.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`
- `numerical_solver/gpn_multiphase_solver/factory.py`
- `numerical_solver/gpn_multiphase_solver/pvt/hydro_to_blackoil_adapter.py`
- `numerical_solver/tests/test_table_range_warnings.py`
- `numerical_solver/tests/test_factory_standing_hydro.py`

**Контекст:** `warn_table_range` (`prototype_adapter.py:223-240`) — единая точка: её зовёт фабрика для начального состояния (`_warn_initial_table_range`, `factory.py:353-362`) и `solve` после принятого шага (строка 341). Флаг `check_table_range` фабрика ставит только для табличной PVT. После шага: флаг включён всегда, а какую проверку звать, решает новый флаг `table_pvt`.

**Что сделать:**
1. `prototype_adapter.py`, докстринг модуля, строка 48.
   До:
   ```
   Только табличная PVT (check_table_range): у HydroPVTtoBlackOilAdapter нет таблицы gp.
   ```
   После:
   ```
   PVT Стендинга (table_pvt=False, DEBT-071) — только таблица ОФП, relperm_range_warnings:
   свойства по формулам, краёв нет, а у HydroPVTtoBlackOilAdapter нет газовой таблицы gp.
   ```
2. `prototype_adapter.py`, `__init__` (строка 184): сигнатура (строка 187), докстринг (строки 197-198), поля (строки 220-221).
   До:
   ```python
                    check_table_range: bool = False):
   ...
           check_table_range — проверять выход принятых состояний за PVT- и ОФП-таблицы
                             (DEBT-027); фабрика включает только для табличной PVT
   ...
           self._check_table_range = check_table_range
           self._range_categories: set[str] = set()
   ```
   После:
   ```python
                    check_table_range: bool = False, table_pvt: bool = True):
   ...
           check_table_range — проверять выход принятых состояний за таблицы (DEBT-027);
                             фабрика включает всегда, адаптеры тестов — без проверки
           table_pvt       — PVT задана таблицами: проверять PVT- и ОФП-таблицы; False —
                             PVT Стендинга, только таблица ОФП (DEBT-071)
   ...
           self._check_table_range = check_table_range
           self._table_pvt = table_pvt
           self._range_categories: set[str] = set()
   ```
3. `prototype_adapter.py`, `warn_table_range` (строки 223-240).
   До:
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
   ```
   После (докстринг — прежний: строка уже 109 символов, DEBT-071 назван в комментарии ветки):
   ```python
       def warn_table_range(self, proto_state, t: float) -> None:
           """Выход состояния за PVT- и ОФП-таблицы — в журнал, одна запись на категорию за расчёт (DEBT-027)."""
           if not self._check_table_range:
               return
           from radial_blackoil.diagnostics import (pvt_range_warnings, relperm_range_warnings,
                                                    warning_category)

           # Прототип берёт свойства за краями таблиц с краёв, без экстраполяции и молча;
           # его pvt_range_warnings называет категорию и значение. Категория — по
           # warning_category: в тексте о ветвях давления двоеточия нет, а числа меняются.
           if self._table_pvt:
               warnings = pvt_range_warnings(self._model, proto_state, free_gas_sg=FREE_GAS_SG)
           else:
               # PVT Стендинга (DEBT-071): свойства по формулам, краёв нет — только таблица
               # ОФП, та же, что на табличном пути. pvt_range_warnings здесь упала бы на
               # газовой таблице gp, которой у HydroPVTtoBlackOilAdapter нет.
               warnings = relperm_range_warnings(self._model, proto_state)
           for warning in warnings:
               category = warning_category(warning)
   ```
   Остаток метода (учёт категорий, `where`, `user_log.warning`) — без изменений. Импорт — внутри метода, как сейчас: тест-шпион (п. 6) подменяет функции модуля `radial_blackoil.diagnostics`, и подмена видна только при импорте во время вызова.
4. `factory.py`, строки 464-471.
   До:
   ```python
       # Выход за PVT- и ОФП-таблицы (BUG-017, DEBT-027): прототип берёт свойства с
       # краёв таблиц без экстраполяции и молча; адаптер проверяет каждое принятое
       # состояние. Только табличная PVT: у HydroPVTtoBlackOilAdapter (Стендинг) нет
       # газовой таблицы gp — pvt_range_warnings упал бы AttributeError.
       adapter = PrototypeHydroAdapter(model, grid, pvt,
                                       max_newton=nc.newton_max_iter,
                                       max_active_iter=nc.max_active_set_iter,
                                       check_table_range=isinstance(pvt, TableFullPVT))
   ```
   После:
   ```python
       # Выход за PVT- и ОФП-таблицы (BUG-017, DEBT-027): прототип берёт свойства с
       # краёв таблиц без экстраполяции и молча; адаптер проверяет каждое принятое
       # состояние. PVT Стендинга (DEBT-071) — только таблица ОФП: свойства по формулам,
       # краёв нет, а у HydroPVTtoBlackOilAdapter нет газовой таблицы gp. Кори
       # протабулирована на S_g ∈ [0, 1] (_get_or_create_proto_rp) — на ней проверка молчит.
       adapter = PrototypeHydroAdapter(model, grid, pvt,
                                       max_newton=nc.newton_max_iter,
                                       max_active_iter=nc.max_active_set_iter,
                                       check_table_range=True,
                                       table_pvt=isinstance(pvt, TableFullPVT))
   ```
   Строки 458-463 над этим блоком (DEBT-006, DEBT-008) — не трогать.
5. `factory.py`, `_warn_initial_table_range`, строки 359-360.
   До:
   ```python
       # Через адаптер: категория, выведенная при t = 0, по ходу расчёта не
       # повторяется (DEBT-027). Без табличной PVT адаптер не проверяет.
   ```
   После:
   ```python
       # Через адаптер: категория, выведенная при t = 0, по ходу расчёта не
       # повторяется (DEBT-027). На PVT Стендинга — только таблица ОФП (DEBT-071).
   ```
6. `pvt/hydro_to_blackoil_adapter.py`, строка 25 и строки 29-32.
   До:
   ```python
           n_knots    — число узлов для rs_values/pb (для FD-якобиана и диагностики)
   ...
           # Протабулировать кривую насыщения для атрибутов BlackOilPVT.
           # _pressure_fd_step в blackoil.py использует searchsorted по self.pb
           # для выбора направления FD-шага; diagnostics.py — rs_values и pb
           # для предупреждений о выходе за таблицу.
   ```
   После:
   ```python
           n_knots    — число узлов для rs_values/pb (для FD-якобиана)
   ...
           # Протабулировать кривую насыщения для атрибутов BlackOilPVT.
           # _pressure_fd_step в blackoil.py использует searchsorted по self.pb
           # для выбора направления FD-шага. PVT-проверку выхода за таблицы
           # (pvt_range_warnings) на этом пути адаптер не зовёт (DEBT-071): свойства
           # по формулам, краёв нет; rs_values — для полноты интерфейса BlackOilPVT.
   ```
7. `tests/test_table_range_warnings.py`:
   a. Докстринг модуля (строки 1-13): после абзаца о конфиге (перед `"""`) дописать абзац:
      ```
      PVT Стендинга (DEBT-071): проверяется только таблица ОФП — relperm_range_warnings.
      Конфиг — пример 05 (Стендинг + таблица ОФП до S_g = 0.8), первые часы; таблицы ОФП
      сценариев — во временном каталоге теста. Числа — эмуляция плана
      (vault/issues/debt-071/probes/plan_tests_emulate.out.txt, scenarios.out.txt).
      ```
   b. Импорты: после `from pathlib import Path` (строка 16) — пустая строка и `import pytest` (стандартная группа — `logging`, `Path`; `pytest` — сторонняя, отдельной группой, как в других тестах проекта).
   c. После `ABOVE = "OIL_PVT saturated locus above table"` (строка 30):
      ```python
      EXAMPLE_05 = ROOT / "examples" / "05_standing_table_rp" / "config.json"
      RELPERM_ABOVE = "RELPERM Sg above table"
      ```
   d. После `_category` (строка 61) — помощник:
      ```python
      def _standing_config(tmp_path, rows=None, hours=6):
          """Пример 05 (Стендинг + ОФП до S_g = 0.8), первые hours часов; rows — своя таблица ОФП."""
          config = load_config(EXAMPLE_05)
          config.time.history = config.time.history[:hours]
          if rows is not None:
              csv = tmp_path / "relperm.csv"
              csv.write_text("Sg,kro,krg\n" + "\n".join(rows) + "\n", encoding="utf-8")
              config.relperm.file = str(csv)
          return config
      ```
      `load_config` разворачивает историю примера 05 в 72 интервала по 1 ч — срез `[:hours]` даёт первые часы. Абсолютный путь в `relperm.file` фабрика принимает: `config.config_dir / rc.file` с абсолютным `rc.file` даёт его самого.
   e. Удалить `TestRunWarnings::test_standing_path_not_checked` (строки 156-159): он закреплял выключенную проверку на пути Стендинга. Его заменяет `test_standing_corey_silent` ниже.
   f. В конец файла — класс:
      ```python
      class TestStandingRelperm:
          """Путь Стендинга (DEBT-071): проверяется только таблица ОФП — PVT по формулам, краёв нет."""

          def test_relperm_above_table_reported_alone(self, tmp_path, caplog):
              """S_g = 0.85 выше таблицы примера 05 (до 0.8): одна запись, PVT-категорий нет.

              Давление 500 бар и R_s = 300 — далеко за псевдотаблицей адаптера Стендинга
              (rs_values, pb — до p0 = 200 бар), но PVT не проверяется: свойства по
              формулам. Вызванная, PVT-проверка упала бы на газовой таблице gp, которой у
              HydroPVTtoBlackOilAdapter нет (предусловие).
              """
              simulator, _ = SimulatorFactory.from_config(_standing_config(tmp_path))
              adapter = simulator._hydro
              state = BlackOilState.undersaturated(3, 500.0, 300.0)
              state.gas_active[0] = True
              state.sg[0] = 0.85
              with pytest.raises(AttributeError):
                  pvt_range_warnings(adapter._model, state)
              with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
                  adapter.warn_table_range(state, 3600.0)
              messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
              assert messages == ["Состояние при t = 0.04167 сут вне таблиц: RELPERM Sg above table: "
                                  "max Sg=0.85, table max=0.8. Endpoint value used; no extrapolation."]

          def test_relperm_above_table_before_failure(self, tmp_path, caplog):
              """Таблица до S_g = 0.01 (k_ro = 0.98 на краю): запись с 56 с, затем отказ первого часа.

              Выше края k_ro и k_rg постоянны: нефть подвижна при любой S_o и уходит, газ
              остаётся — у забоя S_g = 0.917 на принятом подшаге 3600/64 = 56.25 с. Затем
              подшаг не сходится и при dt/512 (DEBT-073: отказ — свойство таблицы, текст
              отказа её не называет). Запись «вне таблиц» — единственное указание на таблицу.
              """
              config = _standing_config(tmp_path, ["0.0,1.0,0.0", "0.01,0.98,0.001"], hours=1)
              with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
                  simulator, state0 = SimulatorFactory.from_config(config)
                  with pytest.raises(RuntimeError, match="не сошёлся"):
                      simulator.run(state0)
              messages = [r.getMessage() for r in caplog.records
                          if r.levelno >= logging.WARNING and "вне таблиц" in r.getMessage()]
              assert len(messages) == 1
              assert messages[0].startswith(
                  f"Состояние при t = 0.000651 сут вне таблиц: {RELPERM_ABOVE}: max Sg=0.917")

          def test_initial_below_table_not_repeated(self, tmp_path, caplog):
              """Таблица ОФП с S_g = 0.05: S_g = 0 ниже таблицы — одна запись, при t = 0.

              SGOF требует начала таблицы с S_g = 0, фабрика это не проверяет. Вдали
              от забоя S_g = 0 весь расчёт (предусловие), но категория, выведенная для
              начального состояния, по ходу расчёта не повторяется.
              """
              rows = ["0.05,0.9,0.005", "0.1,0.8,0.01", "0.2,0.6,0.05",
                      "0.4,0.3,0.2", "0.6,0.1,0.5", "0.8,0.0,0.8"]
              _, history, messages = _run(_standing_config(tmp_path, rows), caplog)
              assert history.states[-1].Sg.min() == 0.0
              assert messages == ["Начальное состояние вне таблиц: RELPERM Sg below table: min Sg=0, "
                                  "table min=0.05. Endpoint value used; no extrapolation."]

          def test_checked_after_every_accepted_step(self, tmp_path, monkeypatch):
              """ОФП проверяется в начале и после каждого принятого шага, PVT — ни разу.

              Пример 05 считает каждый час одним шагом, без дробления (72 из 72, проба
              DEBT-071 scan.out.txt): за 6 ч — 1 + 6 вызовов.
              """
              import radial_blackoil.diagnostics as diagnostics
              calls = {"pvt": 0, "relperm": 0}
              relperm_orig = diagnostics.relperm_range_warnings
              pvt_orig = diagnostics.pvt_range_warnings

              def relperm_spy(model, state):
                  calls["relperm"] += 1
                  return relperm_orig(model, state)

              def pvt_spy(model, state, free_gas_sg=None):
                  calls["pvt"] += 1
                  return pvt_orig(model, state, free_gas_sg=free_gas_sg)

              monkeypatch.setattr(diagnostics, "relperm_range_warnings", relperm_spy)
              monkeypatch.setattr(diagnostics, "pvt_range_warnings", pvt_spy)
              simulator, state0 = SimulatorFactory.from_config(_standing_config(tmp_path))
              simulator.run(state0)
              assert calls == {"pvt": 0, "relperm": 7}

          def test_standing_corey_silent(self, caplog):
              """Стендинг + Кори (configs/baseline, 96 ч): Кори — таблица на S_g ∈ [0, 1], записей нет."""
              _, _, messages = _run(load_config(BASELINE), caplog)
              assert messages == []
      ```
      Числа ожиданий (0.04167 сут, 0.000651 сут, max Sg=0.917, 7 вызовов) — эмуляция плана: `plan_tests_emulate.out.txt` (5 passed), `scenarios.out.txt`. `0.8` в тексте: `f"{0.8:.8g}"` = `0.8`; `0.85` — то же.
8. `tests/test_factory_standing_hydro.py`, строка 261 (докстринг `test_no_range_warnings`).
   До:
   ```python
           """Путь Стендинга не зовёт pvt_range_warnings (у адаптера нет газовой таблицы gp)."""
   ```
   После:
   ```python
           """Стендинг + Кори: PVT не проверяется, ОФП (DEBT-071) молчит — Кори на S_g ∈ [0, 1]."""
   ```
   Тело теста не меняется: начальное состояние $S_g = 0$ внутри таблицы Кори.

**Проверка после шага:**
- `& $PY -m pytest tests/test_table_range_warnings.py tests/test_factory_standing_hydro.py tests/test_factory_prototype.py tests/test_prototype_adapter.py -q` → все passed (новые 5 — по эмуляции; `TestInitialRangeWarnings` и тесты адаптера без флага — без изменений).
- Регресс: быстрый (`& $PY -m pytest tests/ -m "not slow" -q` → 1711 − 1 + 5 = 1715 passed на базе плана). На исходном коде из 5 новых тестов красные 4, зелёный — `test_standing_corey_silent` (страж шума на Кори): `audit1_plan_tests_base.py`.

**Подводные камни:** §2.4 «Обратная совместимость», «Состояние при ошибке», «Связь с задачами» (DEBT-067: строки адаптера +2), «Таблица с $S_g$ первого узла > 0».

**Зависимости:** требует шаг 1 (`relperm_range_warnings`); блокирует шаг 3.

**Оценка:** ~25 строк кода и комментариев, ~110 строк тестов; ~30 мин.

### Шаг 3: проверка

**Цель:** поведение по плану; истории — побитово прежние; прототип — побитово прежний.

**Что сделать** (из `numerical_solver/` worktree, `$env:PYTHONPATH` на worktree):
1. `& $PY ..\vault\issues\bug-026\probes\fingerprint_bug026.py > ..\vault\issues\debt-071\probes\fingerprint_impl.out.txt` → отпечатки 23 примеров **те же, что в `fingerprint_base.out.txt`** шага 0 (сравнить построчно, кроме строки «код:»).
2. `& $PY ..\vault\issues\debt-071\probes\standing_relperm_scan.py warnings > ..\vault\issues\debt-071\probes\warnings_impl.out.txt` → совпадает с `audit1_warnings_emulate.out.txt` (эмуляция на `a7b0dc0`; построчно та же, что `warnings_emulate.out.txt` на `4abe804`) без строк «код:», «прототип:», «эмуляция …»: «итог: записей «вне таблиц» 3 в 23 примерах», три записи 04a, у примеров Стендинга 0, прочих WARNING 0 у всех. Длительность — сравнить с шагом 0 п. 6: рост больше 10 % — разобрать.
3. `& $PY ..\vault\issues\debt-071\probes\standing_relperm_scan.py scenarios > ..\vault\issues\debt-071\probes\scenarios_impl.out.txt` → записи те же, что в `audit1_scenarios_emulate.out.txt` (эмуляция на `a7b0dc0`; без заголовков `===` та же, что `scenarios.out.txt`), без строки «эмуляция …»; длительности расчётов могут отличаться.
4. Из `HydroSolverPrototype/Prototype_1.0.3`: тесты прототипа → 109 passed (база шага 0 + 2); полная регрессия `& $PY regression\run_regression.py` (~45 мин, в фоне; HEAD worktree зафиксировать до запуска — шапка «Правка прототипа» `/plan-improve`) → 17/17 PASS. Выход `OUTPUT/REGRESSION_<время>/` удалить.
5. Полный прогон GPN: `& $PY -m pytest tests/ -q` → 1991 passed (база шага 0 + 4) (~10 мин).
6. CHANGELOG шага 1: вписать фактические «N passed» (п. 4) и «17/17 full» (п. 4).

**Регресс:** полный (п. 5) — итоговый прогон `/implement`.

**Оценка:** ~1 ч (в основном ожидание регрессии).

### Шаг 4: vault

**Что сделать:**
1. Реестр, запись DEBT-071: статус «✅ ГОТОВО (дата)» с итогом (тесты GPN 1987 → 1991 или база шага 0 + 4, прототипа 107 → 109, регрессия 17/17, отпечатки 23/23 как в шаге 0, записи «вне таблиц» — только 04a); **План:** уже есть.
2. Заметка `vault/knowledge/numerics/ячейка фронта даёт ложный выход за кривую насыщения таблицы.md`, строка 33: «Только табличная PVT: у `HydroPVTtoBlackOilAdapter` (Стендинг) нет газовой таблицы. Пробел — [[DEBT-071]]: ОФП на пути Стендинга не проверяется.» → «PVT Стендинга — только таблица ОФП (`relperm_range_warnings`, [[DEBT-071]]): у `HydroPVTtoBlackOilAdapter` нет газовой таблицы, свойства по формулам.»
3. `vault/knowledge/decisions/P8-формат-ввода-json.md:223` — конец строки таблицы «Только табличная PVT (DEBT-027)» → «PVT Стендинга — только таблица ОФП (DEBT-071)». P8 — источник перечня проверок для README пакета (FEAT-031).
4. `vault/issues/debt-071/05-comment-done.md` — результат; `gh issue comment 122 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-071/05-comment-done.md`.
5. Выходы проб реализации (`*_impl.out.txt`, `*_base.out.txt`, `*_wt_base.out.txt`) — в `vault/issues/debt-071/probes/`.

## 4. Тестовая стратегия

**Неизменность поведения:**
- Истории 23 примеров побитово (`fingerprint_bug026.py`, шаг 0 ↔ шаг 3).
- Регрессия прототипа 17/17 PASS, включая текст предупреждений эталона.
- Существующие тесты, покрывающие затронутый код: `tests/test_table_range_warnings.py` (7 тестов DEBT-027 табличного пути), `tests/test_factory_prototype.py::TestInitialRangeWarnings`, `tests/test_factory_standing_hydro.py::test_no_range_warnings`, `tests/test_prototype_adapter.py` (адаптер без флага), тесты прототипа `test_pvt_clamp.py` (11), `test_output_contract.py::test_run_summary_records_range_warning_without_extrapolation`.

**Новые тесты:**

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_relperm_warnings_close_pvt_range_warnings` | прототип `tests/test_pvt_clamp.py` | `Nabor_1b`, $p_0$ = 350 бар, $S_g$ = 0.9 > 0.85 | одна ОФП-запись; она же — последняя в `pvt_range_warnings` | смену порядка/текста (эталон регрессии) |
| `test_relperm_warnings_need_no_pvt` | то же | модель без PVT (`SimpleNamespace(relperm=…)`), $S_g$ = −0.01 | `RELPERM Sg below table`; `pvt_range_warnings` — `AttributeError` | зависимость ОФП-проверки от PVT |
| `TestStandingRelperm::test_relperm_above_table_reported_alone` | `tests/test_table_range_warnings.py` | адаптер примера 05, состояние $S_g$ = 0.85, 500 бар, $R_s$ = 300 | одна запись ОФП при 0.04167 сут; PVT-категорий нет | `AttributeError` / PVT-шум на пути Стендинга |
| `TestStandingRelperm::test_relperm_above_table_before_failure` | то же | 05, таблица до 0.01, 1 ч | `RuntimeError`; перед ним одна запись «вне таблиц» при 0.000651 сут, max Sg=0.917 | молчаливый выход за таблицу в настоящем расчёте |
| `TestStandingRelperm::test_initial_below_table_not_repeated` | то же | 05, таблица с 0.05, 6 ч (предусловие: $S_g$ = 0 в конце) | одна запись «Начальное состояние» | отсутствие начальной проверки / повтор |
| `TestStandingRelperm::test_checked_after_every_accepted_step` | то же | 05, 6 ч, шпионы на функциях прототипа | `relperm` 7 вызовов, `pvt` 0 | пропуск проверки после шага; вызов PVT-проверки |
| `TestStandingRelperm::test_standing_corey_silent` | то же | `configs/baseline.json`, 96 ч | записей нет | шум на Кори |

**Удаляется:** `TestRunWarnings::test_standing_path_not_checked` (закреплял выключенную проверку).

**Baseline:** 1987 / 1711 (GPN, `a7b0dc0`, аудит 1), 107 (прототип), 17/17 (CHANGELOG DEBT-067).

## 5. Критерии завершения

- [ ] Шаги 0–4 выполнены.
- [ ] GPN: 1991 тест (или база шага 0 + 4), полный прогон passed; быстрый уровень 1715 passed (или база + 4).
- [ ] Прототип: 109 passed (или база + 2); полная регрессия 17/17 PASS побитово (включая `warnings`); CHANGELOG — раздел DEBT-071 с фактическими числами.
- [ ] Отпечатки 23 примеров — как в шаге 0.
- [ ] Журнал 23 примеров (`standing_relperm_scan.py warnings`) совпадает с эмуляцией: «вне таблиц» только у 04a (3).
- [ ] Сценарии (`standing_relperm_scan.py scenarios`) совпадают с эмуляцией.
- [ ] Комментарии: `factory.py`, `prototype_adapter.py`, `hydro_to_blackoil_adapter.py` больше не утверждают «только табличная PVT» / «diagnostics — rs_values и pb».
- [ ] Vault: реестр, заметка «ячейка фронта…», P8, комментарий в issue #122; DEBT-073 зарегистрирована (при планировании).

## 6. Связь формула → код

Формул нет: задача — диагностика входных данных. Ссылки `eq:` в новых докстрингах и комментариях не нужны.

## 7. Верификация плана

**Раунд 1 (полнота):** все файлы §2.2 — в шагах 1–2, заметки vault — в шаге 4; у каждого шага есть проверка; зависимости 0 → 1 → 2 → 3 → 4 без циклов; подводные камни §2.4 адресованы (три ⚠️ — с действиями); критерии проверяемы командами шага 3.

**Раунд 2 (корректность):** функции и строки сверены на `a7b0dc0` (аудит 1): `pvt_range_warnings` — `diagnostics.py:22`, строка `rp=model.relperm` — 25, ОФП-блок — 60-64, `return w` — 65, `WARNING_CATEGORIES` — 70-75 (ОФП-категории в нём уже есть, `warning_category` работает и для текстов новой функции); `PrototypeHydroAdapter.__init__` — `prototype_adapter.py:184`, `check_table_range` — 187, 197-198, 220; `warn_table_range` — 223-240; вызов в `solve` — 341; все цитаты «До» шагов 1–2 найдены в файлах ровно по одному разу (`audit1_before_blocks.py`); `_warn_initial_table_range` — `factory.py:353-362`; создание адаптера — 468-471; Кори — 504-508; `hydro_to_blackoil_adapter.py` — 25, 29-32; `test_standing_path_not_checked` — `test_table_range_warnings.py:156-159`; `test_no_range_warnings` — `test_factory_standing_hydro.py:260-265`; последний тест `test_pvt_clamp.py` — 30-32. Код шагов 1–2 проверен эмуляцией (`standing_relperm_scan.install`): тесты шага 2 — 5 passed (`plan_tests_emulate.out.txt`), тесты шага 1 — OK (`proto_tests_emulate.out.txt`); ожидания тестов взяты из её вывода. `BlackOilState.undersaturated(n, p_bar, rs)` — сигнатура как в `test_table_range_warnings.py:71`. Истории от проверки не зависят (только чтение состояния).

**Раунд 3 (автономность):** пути полные; `$PY` и `PYTHONPATH` — «Как начать»; почему именно так — §1–2; термины: «категория» (начальные слова текста предупреждения прототипа, `WARNING_CATEGORIES`), «путь Стендинга» (`pvt.model = "standing"`, PVT — `HydroPVTtoBlackOilAdapter`), «принятое состояние» (после сошедшегося `advance`, DEBT-027 §2.3).

## 8. Пробы планирования (`vault/issues/debt-071/probes/`)

| Скрипт / файл | Что показал |
|---|---|
| `standing_relperm_scan.py scan` → `scan.out.txt` | 8 примеров Стендинга: min $S_g$ = 0, max ≤ 0.452; 05 — 0.014 при крае 0.8, 72 шага без дробления |
| `… warnings` → `warnings_base.out.txt` | база: «вне таблиц» только 04a (3) |
| `… warnings --emulate` → `warnings_emulate.out.txt` | код плана: то же — 04a (3), Стендинг 0 |
| `… scenarios --emulate` → `scenarios.out.txt` | сценарии тестов шага 2 на 05 и baseline; 05 + таблица до 0.1 при $R_{s,0}$ = 100 — отказ без принятых состояний |
| `scenarios_v1_to001.out.txt` | первая версия пробы: 05 + таблица до 0.01 — отказ (трассировка; записи не печатались) |
| `… variants` → `variants.out.txt` | 05 при $p_{wf}$ 2–8 МПа, $R_{s,0}$ 50/100: max $S_g$ 0.065–0.150 к первому часу |
| `… cut21`, `… cut21cap` → `cut21*.out.txt` | 21 с Кори, обрезанной на 0.2–0.35: отказ первого подшага; полная таблица — сходится; ограничение начального $S_g$ 0.94 не помогает (DEBT-073) |
| `plan_tests_emulate.py` → `plan_tests_emulate.out.txt` | тесты GPN шага 2 на эмуляции: 5 passed, 4.7 с |
| `proto_tests_emulate.py` → `proto_tests_emulate.out.txt` | тесты прототипа шага 1 на эмуляции: 2 OK |
| `relperm_to_001.csv`, `relperm_to_01.csv`, `relperm_from_005.csv`, `relperm_corey21_to_*.csv` | таблицы ОФП проб |
| `audit1_diag_equivalence.py` (аудит 1) | правка шага 1 на копии `diagnostics.py` в памяти: цитаты «До» — по одному разу, `pvt_range_warnings` побитово та же на 6000 сравнениях, все 9 категорий |
| `audit1_before_blocks.py` (аудит 1) | все цитаты «До» шагов 1–2 есть в файлах `a7b0dc0` ровно по разу |
| `audit1_plan_tests_base.py` (аудит 1) | тесты шага 2 на исходном коде: 4 failed, 1 passed (`test_standing_corey_silent`) |
| `audit1_warnings_base/emulate.out.txt`, `audit1_scenarios_emulate.out.txt` (аудит 1) | на `a7b0dc0` — построчно как на `4abe804` |
| `audit1_fingerprint_base.out.txt` (аудит 1) | `fingerprint_bug026.py` на `a7b0dc0`: расхождение 1 из 23 — 14 (DEBT-067) |
| `audit1_long_lines.py` (аудит 1) | строки длиннее 100 символов в блоках кода плана (остались f-строки и тесты прототипа — его стиль, и прежний докстринг `warn_table_range`) |
