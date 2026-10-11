---
tags:
  - план
  - рефакторинг
date: 2026-10-11
issue: DEBT-054
github: 102
branch: refactor/debt-054/cell-test-failure-report
status: в процессе
worktree: .worktrees/debt-054
audit:
  date: 2026-10-11
  found: 8
  auto-fixed: 8
  manual-required: 0
---

# DEBT-054 (+ DEBT-061): причина отказа Ньютона в отчёте прототипа и в тексте отказа

**Подтип:** рефакторинг (улучшение диагностики; численная схема не меняется).
**База:** `numerical_scheme/implementation`, `73ef031` (аудит 1). План писался на `ccc5ae3`; между ними влиты DEBT-064 (только vault) и **DEBT-008** (`23d2cec`): лимиты Ньютона из конфига в `advance` и `advance_fourth_stage`, +19 тестов. Номера строк `blackoil.py`, `simulator.py`, `test_simulator.py` не изменились; номера строк `prototype_adapter.py` ниже — на `73ef031`. Пробы `test_scenarios.py` и `failure_census.py --shutin`, повторённые на `73ef031`, дали те же числа строка в строку: умолчания лимитов DEBT-008 (15, 12, 1e-5, 1e-9) равны умолчаниям прототипа. Реализация начата от `f89c08b`: после `73ef031` влит DEBT-023 (теплопроводность примеров 03–09, их README и тесты, одна строка `io/config.py`) — файлов и сценариев этого плана он не касается.
**Ветка:** `refactor/debt-054/cell-test-failure-report`.
**Issue:** [#102](https://github.com/ArturSalamatin/Oil_Gas/issues/102). DEBT-061 поглощается этой задачей (решение пользователя 2026-10-11), отдельного issue у неё нет.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай записи DEBT-054 и DEBT-061 в `vault/roadmap/известные баги и технический долг.md` и заметку `vault/knowledge/debugging/абсолютный допуск Ньютона один на все ячейки недорешал забойную — условие по ячейке отнесено к её поровому объёму.md` (BUG-022: откуда условие по ячейке).
3. Рабочее дерево — по `/implement`: `git worktree add .worktrees/debt-054 -b refactor/debt-054/cell-test-failure-report numerical_scheme/implementation`. Интерпретатор — `numerical_solver\.venv\Scripts\python.exe` **основного** каталога по абсолютному пути (в worktree `.venv` нет). Пробы этого плана сами ставят в начало `sys.path` каталог запуска и прототип из него и печатают, откуда взят код (`Код: …`, `Прототип: …`). Проверяй по этим строкам, что код взят из worktree.
4. Базовый вариант (из `<worktree>\numerical_solver`):
   ```powershell
   $PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   & $PY -m pytest tests/ --collect-only -q          # ожидается 1741 (на 73ef031)
   & $PY -m pytest tests/ -m "not slow" -q           # ожидается 1470 passed, ~70 с
   & $PY ..\vault\issues\debt-054\probes\histories.py save before   # ~60 с, 5 сценариев
   cd HydroSolverPrototype\Prototype_1.0.3
   & $PY -m pytest tests -q                          # ожидается 97 passed, ~45 с
   & $PY regression\run_regression.py --quick        # ожидается 11/11 PASS, ~8 мин
   ```
   Если база к началу реализации ушла вперёд (например, влит DEBT-008), числа будут другими. Запиши фактические, а сценарии `histories.py` всё равно снимай **до** правки кода.
5. Запомни число тестов (всего и в быстром уровне) и время быстрого уровня.
6. Начни с шага 1. После каждого шага — тест шага и регресс по полю «Регресс». Полный прогон и полная регрессия прототипа — в шаге 7.

---

## 0. Решения пользователя (2026-10-11, при планировании)

1. **Объём отчёта — вариант 3 issue.** Кроме меры ячеек и абсолютного допуска в отчёт Ньютона идёт причина выхода (`exit_reason`). DEBT-061 (отказ ступени 4 пишет `iterations = max_iter` и при досрочном выходе) решается здесь же и закрывается вместе с DEBT-054.
2. **Текст `Simulator` — вариант 5.** При исчерпании дробления в конец текста `RuntimeError` дописывается текст последнего `HydroConvergenceError`. Начало текста не меняется.

---

## 1. Контекст и замеры

### 1.1. Что не так

**Два условия сходимости (BUG-022).** Ньютон прототипа принимает решение, только если выполнены оба условия:
- **абсолютное** $\|F\|_\infty \le$ `tol` = `atol + rtol·max(‖F₀‖∞, 1e-9)`, где `atol` = 1e-11 м³ст/с, `rtol` = 1e-8, а газовые строки поделены на `gas_residual_scale`;
- **по ячейке** $\max_c |F_{c,i}|\,\Delta t / V_{p,i} \le$ `cell_tol`, где $V_{p,i}$ — поровый объём на начало шага. Фабрика GPN передаёт `numerics.newton_cell_tol` = 1e-8.

**DEBT-054.** Решение, отвергнутое только условием ячейки, возвращает `BlackOilNewtonReport(converged=False, residual_inf=…)` с невязкой на 8 порядков ниже допуска. Ни допуска, ни меры ячеек, ни причины выхода в отчёте нет. Адаптер печатает «итераций 4, невязка 6.51e-15», и пользователь ищет причину в дроблении или физике. Текст адаптера виден только в цепочке traceback и в отладочном журнале. Собственный текст `Simulator` невязку не называет.

**DEBT-061.** `_newton_switching` (ступень 4) при отказе пишет `iterations = max_iter` (40), даже если цикл прерван раньше: исключение линейного решателя или нечисловое обновление. С DEBT-048 отчёт ступени 4 по памяти печатает адаптер (`(ступень 4 по памяти) … итераций 40`). Поэтому запись реестра «влияние на выход: нет» устарела: в текст отказа и отладочный журнал это число попадает.

### 1.2. Перепись отказов (проба `vault/issues/debt-054/probes/failure_census.py`)

Проба обёртывает оба Ньютона и по возвращённому приближению пересчитывает допуск и меру. По счётчикам якобианов и исключений решателя она выводит причину выхода. Выход — `failure_census.out.txt` (разделы 1–3) и `failure_census_shutin.out.txt` (раздел 4), база `ccc5ae3`.

| Сценарий | Отказов адаптера | Класс печатаемого отчёта | Пример |
|---|---|---|---|
| BUG-018 ($R_{s0}$ = 500), $N$ = 350, первые сутки (`Simulator.run`) | 2 | 2 × «только ячейка» | ступень 1: 4 итерации, выход — линейный поиск, невязка 6.509e-15, допуск 5.355e-7, мера 2.596e-8 > 1e-8 (при 43200 с — 6 итераций, мера 1.167e-8) |
| пример 14 | 1 | «только ячейка» | 11 итераций, линейный поиск, невязка 1.78e-15, допуск 1.45e-7, мера 1.139e-8 |
| пример 17 | 0 | — | — |
| суточный останов rs300 (`TestDailyShutin`) | 7 | 4 × «оба не выполнены» (через `advance`), 2 × «только ячейка» и 1 × «оба» (ступень 4 по памяти) | по памяти: 40 итераций, выход — лимит, невязка 7.57e-16, допуск 1.03e-11, мера 1.290e-8 |

- **Классы.** «Только ячейка» — 5 отказов из 10, и для всех пяти текст отказа сейчас не называет причину.
- **Линейный поиск на пределе округления.** В сценарии BUG-018 мера пропорциональна шагу: 2.60e-8 при 86400 с, 1.17e-8 при 43200 с, при 21600 с условие выполнено. Здесь дробление решает задачу. Случай, когда условие не выполняется ни на каком подшаге, — DEBT-055.
- **Ступень 4 в сценарии воспроизведения** отказывает иначе: лимит 40, невязка 18.2, мера 3.6e7. В отчёт она не попадает: при отказе всех ступеней `advance` подставляет поля ступени 1 (DEBT-030, `blackoil.py:432-434`).
- **Невязка отказа ступени 4 считается при удержанных ячейках «выше по потоку».** `_upwind_frozen` сбрасывается в `finally` уже после вычисления возвращаемого выражения (`:604-605`). Пересчёт пробой после выхода дал 6.744e-7 против 4.635e-7 в отчёте. Мера в отчёте должна считаться **по той же `f`**, что `residual_inf`, иначе в тексте отказа они не согласуются.

### 1.3. Сценарии тестов на текущем коде (проба `test_scenarios.py`, выход `test_scenarios.out.txt`)

| № | Сценарий | Сейчас | Нужно для теста |
|---|---|---|---|
| 1 | Nabor_1b, $N$ = 12, `cell_tol` = 1e-8, `_newton_fixed_active_set` | сошлось за 3 итерации, невязка 9.165e-16, допуск 1.9368e-11 | `pack(unpack(z)) == z` побитово; мера по `f` кода **побитово** равна `_measure` теста (3.440676894137998e-12) |
| 2 | то же, `max_iter=1` | отказ, 1 итерация, невязка 5.7e-5; $z$ сдвинулся (линейный поиск принял точку) | выход — лимит, не линейный поиск |
| 3 | то же, `_linear_solve` бросает исключение | отказ, 1 итерация, невязка = ‖F₀‖∞ побитово | выход — линейный решатель, отчёт о стартовой точке |
| 4 | `_advance_phases(…, max_active_iter=1)`, $N$ = 12 | отказ, 5 смен фаз, 3 итерации Ньютона | выход — набор фаз (при $N$ = 50 — 21 смена) |
| 5 | ступень 4, останов rs300, 168.75 с, `cell_tol` = 1e-8 | сошлось за 16 итераций, невязка 6.877e-15, допуск 4.384e-11 | выход 'converged' |
| 5 | то же, `cell_tol` = 1e-30 | отказ, 40 итераций, невязка 8.07e-15 ≤ допуска, мера 9.8e-12 | «только ячейка», выход — лимит |
| 6 | ступень 4, исключение решателя на 3-м вызове | отказ, **iterations = 40** | после правки — 2 (DEBT-061) |
| 7 | ступень 4, NaN в направлении на 2-м вызове | отказ, **iterations = 40** | после правки — 1 (DEBT-061) |

### 1.4. Где формируется отчёт (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`, `ccc5ae3`)

| Функция | Строка | Возврат | Причина выхода после правки |
|---|---|---|---|
| `_newton_fixed_active_set` | `:362` | старт уже удовлетворяет обоим условиям | `converged` |
| | `:366` | исключение `_linear_solve` | `linear_solver` |
| | `:379` | линейный поиск не принял ни одной из 12 точек | `line_search` |
| | `:381` | сошлось | `converged` |
| | `:382` | исчерпан `max_iter` | `max_iter` |
| `_advance_phases` | `:499-501` | отказ Ньютона — его отчёт как есть | (Ньютона) |
| | `:506` | успех — отчёт последнего Ньютона | `converged` |
| | `:517` | исчерпан цикл набора фаз (`max_active_iter`), невязка пересчитана на новом наборе | `active_set` |
| `_newton_switching` | `:579` | сошлось; `ok = False` при двухфазной $S_g > 0.98$ | `converged` / `sg_bound` |
| | `:584` | `it > max_iter` → `break` | `max_iter` |
| | `:586` | исключение `_linear_solve` → `break` | `linear_solver` |
| | `:601` | нечисловые `pn`, `xn` → `break` | `nonfinite` |
| | `:605` | после цикла — отчёт отказа | причина `break`; `iterations = it-1` (DEBT-061) |
| `_fallback` | `:487-488` | обе ветки испробованы: Ньютон отказал **или** сошёлся на несогласованной ветке | у второго случая — `branch` |
| `advance` | `:432-434` | отказ всех ступеней — подмена полями ступени 1 (DEBT-030) | + три новых поля ступени 1 |

---

## 2. Анализ

### 2.1. Базовый вариант

- Тесты `numerical_solver`: **1741** всего, **1470** в быстром уровне (271 с меткой `slow`) — на `73ef031`, после DEBT-008 (на `ccc5ae3` было 1722 / 1451). База зелёная по правилу мёржа.
- Тесты прототипа: **97**. Регрессия прототипа: 17/17 (с DEBT-048), быстрая — 11/11.
- Истории пяти сценариев `histories.py` на `ccc5ae3` воспроизводятся побитово от прогона к прогону (`histories_selfcheck_ccc5ae3.out.txt`: ИТОГ OK). Время: BUG-018 1.1 с, пример 14 11.9 с, пример 16 16.1 с, пример 17 22.8 с, суточный останов 5.3 с.
- **Интерфейсы, которые читают отчёт.**
  - Адаптер GPN (`prototype_adapter.py:162, 169-177` на `73ef031`): `converged`, `iterations`, `residual_inf`, `phase_switching`.
  - Прототип: `simulation.py:83, 99` (строки `step_log.csv`), `runner.py:91` (блок `failure` в `run_summary.json`) — читают явный набор полей.
  - Регрессия сравнивает выходы прототипа; `step_log.csv` она не сравнивает (`CHANGELOG_1.0.3.md`, раздел DEBT-030).

### 2.2. Целевое состояние

**Отчёт `BlackOilNewtonReport`** — три новых поля со значениями по умолчанию (в конце, позиционное создание не меняется):

| Поле | Тип | Смысл | `None` / `''` когда |
|---|---|---|---|
| `residual_tol` | `float \| None` | допуск абсолютного условия того Ньютона, чья невязка в `residual_inf` | выход `active_set`: невязка — у начального приближения нового набора фаз, которое ни один Ньютон не решал |
| `cell_measure` | `float \| None` | $\max_c |F_{c,i}|\,\Delta t/V_{p,i}$ **на той же `f`**, что `residual_inf` | условие по ячейке выключено (`cell_tol=None`, собственные расчёты прототипа) |
| `exit_reason` | `str` | `converged`, `line_search`, `linear_solver`, `max_iter`, `nonfinite`, `active_set`, `sg_bound`, `branch` | `''` — отчёт создан не Ньютоном (подставные отчёты тестов) |

**Ступень 4 (DEBT-061):** отказ пишет `iterations = it-1` — сколько проходов цикла выполнено до выхода, минус один, как у сошедшегося решения (`:579`). При исчерпании лимита это по-прежнему 40.

**Текст адаптера** (`HydroConvergenceError`) — прежний текст плюс хвост. Прежний текст остаётся началом нового. Ожидаемые тексты на сценариях 1.2:
```
advance не сошёлся: dt = 8.640e+04 с, t = 0.0000 сут, итераций 4, невязка 6.51e-15 (допуск 5.35e-07), мера ячеек 2.60e-08 (порог numerics.newton_cell_tol = 1e-08), выход: линейный поиск не принял ни одной точки — не выполнено только условие по ячейке; числа — Ньютона ступени 1
advance не сошёлся (ступень 4 по памяти): dt = 8.640e+04 с, t = 11.0000 сут, итераций 40, невязка 7.57e-16 (допуск 1.03e-11), мера ячеек 1.29e-08 (порог numerics.newton_cell_tol = 1e-08), выход: исчерпан лимит итераций — не выполнено только условие по ячейке; числа — Ньютона ступени 4
```
Тексты собраны пробой `check_failure_details.py` по числам переписи. Последняя цифра допуска (5.35 при 5.355e-7) зависит от округления, тесты её не закрепляют.

- **Вывод «какое условие не выполнено» — факт, а не догадка.** Адаптер сравнивает `residual_inf <= residual_tol` и `cell_measure <= cell_tol` — те же числа и те же сравнения, что в Ньютоне прототипа.
- **«Числа — Ньютона ступени N».** После DEBT-030 числа отказа `advance` — исходного алгоритма (ступень 1), у ступени 4 по памяти — её собственные. Без этой пометки пользователь принял бы их за числа последней ступени.
- **«Оба условия сходимости выполнены» при отказе** — отказ не по условиям сходимости. Возможные причины: несогласованная ветвь скважины (`branch`), корень с $S_g > 0.98$ (`sg_bound`) или, у ступени 4 с выходом по лимиту, переключения фаз или удержанные ячейки выше по потоку, не устоявшиеся к 40-й итерации. Ступень 4 принимает решение только при `switched == 0` и согласии удержанных ячеек (`:571-573`). Текст это сообщает фактами: причина выхода стоит рядом.
- **Порог в тексте назван ключом конфига.** Это и есть подсказка реестра «при отказе только по условию ячейки — подсказка о `numerics.newton_cell_tol`». Совета «увеличьте порог» нет: правило текста отказа — «факты, а не догадка о причине» (`simulator.py:312-317`). К тому же в сценариях 1.2 дробление решает отказ без смены порога.

**Текст `Simulator`** при исчерпании дробления — прежний, в конце добавлено ` Последний отказ гидродинамики: <текст HydroConvergenceError>`.

**Что станет проще.**
- Отказ «только по условию ячейки» виден из одной строки текста.
- Пробы и отчёты реестра (BUG-025 «Не проверено», DEBT-055) различают классы отказа без обёрток.
- Число итераций отказавшей ступени 4 — фактическое.

### 2.3. Варианты (подробно — в issue #102) и выбор

| Вариант | Суть | Решение |
|---|---|---|
| 1 | только `cell_measure` | отвергнут: адаптер не знает абсолютного допуска и не скажет «только по ячейке» |
| 2 | `cell_measure` + `residual_tol` | входит в выбранный |
| **3** | **+ `exit_reason`, DEBT-061** | **выбран пользователем** |
| 4 | мера в адаптере по возвращённому состоянию | отвергнут: при отказе `_advance_phases` возвращает `guess` (начало последнего прохода набора фаз, `:501`), а не приближение Ньютона; после подмены DEBT-030 отчёт относится к ступени 1, а состояние — к последней попытке |
| **5** | **факты отказа в конце текста `Simulator`** | **выбран пользователем** |

**Где считать меру.** Новый метод `_cell_measure(f, w)` возвращает меру или `None`. `_cells_converged` сравнивает её с порогом: операции те же, что сейчас в `:257`, поэтому условие побитово прежнее. Вспомогательный `_newton_report(...)` собирает отчёт с мерой, допуском и причиной, чтобы девять точек возврата не повторяли одно и то же.

**Подставные отчёты тестов.** `SimpleNamespace(converged=…, iterations=…, residual_inf=…)` в `tests/test_prototype_adapter.py:839-840` и `tests/test_prototype_stage4_memory.py:138-139` новых полей не имеют (третья — `test_prototype_adapter.py:867`, из DEBT-008 — сошедшийся отчёт, на путь отказа не попадает). Адаптер читает новые поля через `getattr(report, …, None)`, и при их отсутствии хвоста нет — текст прежний. Эти тесты не меняются.

### 2.4. Зона неприкосновенности

- Итерации Ньютона, линейный поиск, ограничения шага, условия сходимости, переключение фаз и ветвей. Принятые шаги и последовательность вызовов гидродинамики — побитово.
- Прежние поля отчёта: `converged`, `iterations`, `residual_inf`, `active_set_iterations`, `phase_switches`, ветвевые поля. Исключение: `iterations` отказа ступени 4 после досрочного `break` (DEBT-061, намеренно).
- `_newton_fixed_active_set`: отказ на итерации `it` пишет `it`, как и прежде. Семантику не трогаем: строки `step_log.csv` прототипа (эталон `regression/golden/*/step_log.csv`) остаются прежними.
- Формат `step_log.csv` и `run_summary.json` прототипа, `docs/OUTPUT_FORMAT.md`.
- Начало текста `Simulator` — его цитируют README примеров 03, 05, 06, 07, 10 и тесты (`test_simulator.py:559`, `test_prototype_activation_cap.py:230`). Прежний текст адаптера — тоже: он становится началом нового.
- Конфиги, фабрика, `io/config.py`.

### 2.5. Подводные камни

| Пункт | Статус | Как адресовано |
|---|---|---|
| Все точки создания отчёта найдены | ✅ | grep `BlackOilNewtonReport(` по `numerical_solver/`: 8 в `blackoil.py` (`:362, 366, 379, 381, 382, 517, 579, 605`) + подмена `replace` в `advance` (`:432`) + `_fallback` (`:480, 488` — меняет поля на месте). Остальные — подставные отчёты в тестах (`test_prototype_well_branch.py:116`, `_globalization.py:175, 185, 263-308`, `_phase_switching.py:374`, `_activation_cap.py:224`): создаются позиционно, новые поля получают значения по умолчанию |
| Зависимости пакетов | ✅ | новых импортов в прототипе нет; аннотация `float \| None` — Python ≥ 3.10 (`requires-python` обоих `pyproject.toml`) |
| Обратная совместимость API | ✅ | поля в конце dataclass со значениями по умолчанию; `replace(...)` с новыми именами; адаптер — через `getattr` |
| Состояние при ошибке | ✅ | правка не трогает `try/finally` ступеней. Новая точка — `reason='…'; break` в `_newton_switching` до `finally` |
| Мера и невязка из одной `f` | ⚠️ | у отказа ступени 4 `f` пересчитывается при удержанных ячейках «выше по потоку» (1.2) — меру считать по ней же, внутри `try`, тем же вызовом `_newton_report` |
| `exit_reason` у общего отчёта | ⚠️ | `_fallback` меняет отчёт на месте. Подставные отчёты в `_install_fake_reports` копируются (`replace(rep)`), в `_install_fake_phases` создаются заново — общих объектов нет |
| Сравнение dataclass `==` | ✅ | `None` вместо NaN: NaN ≠ NaN сломал бы `==`. Целиком отчёты тесты не сравнивают (grep) |
| Тесты | ✅ | существующие тесты читают прежние поля; закрепляющих `iterations == 40` у **настоящего** отказа ступени 4 нет: `test_prototype_stage4_memory.py:76` — подставной отчёт; `test_prototype_cell_tolerance.py:206` проверяет только `not rc.converged` |
| Циклические импорты | ✅ | новых импортов в пакетах нет; тестовый модуль импортирует помощники соседних (принятый приём, напр. `test_prototype_globalization.py:30`) |
| Docstring / метки уравнений | ✅ | однострочные докстринги без номеров уравнений; `tests/test_eq_references.py` не затронут |
| Конфиги | ✅ | не меняются |
| Связь с другими задачами | ⚠️ | 2.6 |
| Производительность | ✅ | одна мера $O(N)$ на выход из Ньютона на уже вычисленной `f` ($N \le 350$), против якобиана $O(N)$ вызовов невязки |
| Прототип | ⚠️ | меняется `blackoil.py`: тесты прототипа и `run_regression.py --quick` после шага 3; полная регрессия — в шаге 7. **Ожидание: 17/17 PASS побитово.** Собственные расчёты прототипа не используют ступень 4 (`phase_switching_stage=False`) и условие по ячейке (`cell_tol=None`); новые поля в выходные файлы не пишутся |

### 2.6. Связь с другими задачами

- **DEBT-008** (#89) — **влит `23d2cec`** во время планирования, база этого плана — `73ef031` (после него). Адаптер теперь передаёт лимиты `max_active_iter`, `max_newton` в оба вызова (`prototype_adapter.py:157-161`, `**limits`). Текст отказа (`:169-176`) DEBT-008 не трогал, фрагмент «До» шага 4 совпадает с файлом. `blackoil.py` DEBT-008 не трогал. Умолчания лимитов равны умолчаниям прототипа: числа проб не изменились (шапка плана).
- **DEBT-011** (#91, план готов) меняет `simulator.py` в другой части: конструктор и свойства `grid`, `pvt`, `relperm`. Этот план трогает `_advance` (`:254-255`) и `_failure_message` (`:310-329`). Пересечения нет; тот, кто реализует вторым, сверяет «До» по цитате.
- **DEBT-061** — поглощается (решение 0.1): шаг 2 и тесты C3, C4. В реестре закрывается вместе с DEBT-054 (шаг 8).
- **DEBT-055** (пол округления условия по ячейке) не затронут. После этой задачи текст отказа показывает его случай («только ячейка» при невязке на пределе округления); в мотивации DEBT-055 поправить «сообщение причину не называет» (шаг 8).
- **BUG-025** (шаг < 0.1 с не сходится). В записи «Не проверено: … отказ только по абсолютному условию, а не по линейному поиску (отчёт отказа этого не различает — DEBT-054)». После задачи отчёт различает — отметить в записи (шаг 8).
- **DEBT-030** — подмена полей ступени 1 расширяется на новые поля; смысл прежний.
- **DEBT-048** — текст отказа ступени 4 по памяти получает хвост с «числа — Ньютона ступени 4».
- **FEAT** в `vault/roadmap/планируемые фичи.md`, зависящие от отчёта Ньютона или текста отказа: нет (FEAT-030/031 — поставка: версия дистрибутива `radial-blackoil` повышается при поставке, не здесь).

### 2.7. Обнаруженные проблемы

1. **Запись DEBT-061 «Влияние на выход: нет» устарела** после DEBT-048: отчёт ступени 4 по памяти печатается в тексте отказа адаптера. Исправляется при закрытии DEBT-061 (шаг 8). Новой записи не нужно.
2. **Невязка отказа ступени 4 — при удержанных ячейках «выше по потоку»** (1.2: 4.635e-7 в отчёте против 6.744e-7 по исходной схеме против потока). Для отказавшего шага состояние отбрасывается, на расчёт это не влияет. Пробы, пересчитывающие невязку по возвращённому состоянию, видят другое число. Документируется комментарием в шаге 2, новой записи не нужно.
3. **Разная семантика `iterations` у отказа двух Ньютонов.** `_newton_fixed_active_set` на итерации `it` пишет `it` (неудачная итерация считается), `_newton_switching` после правки пишет `it-1` (как у своего сошедшегося решения). Первую не меняем: это строки `step_log.csv` эталона регрессии. Документируется в комментарии и `CHANGELOG`.

Блокирующих проблем нет. Новых записей реестра план не создаёт.

---

## 3. Шаги

### Шаг 0: Подготовка

**Цель:** worktree, базовый вариант, истории «до».

**Файлы:** —

**Что сделать:** раздел «Как начать работу», пп. 3–5. `histories.py save before` — **до** любой правки кода, из `<worktree>\numerical_solver`. Убедиться, что строки `Код:` и `Прототип:` указывают на worktree.

**Проверка:** числа базового варианта записаны; 5 файлов `vault/issues/debt-054/probes/hist_*_before.npz` в worktree.

**Оценка:** ~15 мин (из них 8 — регрессия прототипа).

---

### Шаг 1: Отчёт и Ньютон ступеней 1–3

**Цель:** новые поля отчёта, мера ячеек отдельным методом, причина выхода во всех возвратах `_newton_fixed_active_set` и при исчерпании набора фаз.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`, `numerical_solver/tests/test_prototype_failure_diagnostics.py` (новый).

**Контекст:** 1.1, 1.4, 2.2. Отчёт нужен адаптеру (шаг 4), чтобы назвать, какое условие не выполнено. Мера считается по той же `f`, что `residual_inf`: в `_newton_fixed_active_set` это `f` текущего `z` в каждой точке возврата. Комментарий BUG-021 (`:356-361`): `f` — побитово `residual(z)`. В `:366` `f` — та, что вернул вызов якобиана в том же `z`. В `:379` `f` не менялась с вызова якобиана: пробная точка принимается только вместе со своей `ft`.

**Что сделать:**

1. Докстринг модуля (`:1-34`): после строк DEBT-048 (`:32-33`), перед `"""`, добавить:
   ```
   DEBT-054: the Newton report says why a solve stopped (exit_reason), with the absolute
   tolerance of its test (residual_tol) and the per-cell measure (cell_measure) on the
   residual it reports; a failed fourth-stage Newton reports the iterations it ran,
   not max_iter (DEBT-061).
   ```
2. `BlackOilNewtonReport` (`:43-54`). До (последняя строка класса):
   ```python
       phase_switching: bool = False  # advance's fourth stage ran (phase switches inside Newton), BUG-020
   ```
   После:
   ```python
       phase_switching: bool = False  # advance's fourth stage ran (phase switches inside Newton), BUG-020
       # DEBT-054: why the Newton stopped and how far it was from each convergence test, on
       # the residual of residual_inf.  residual_tol -- atol + rtol*scale of the absolute test
       # (None: exit 'active_set', the residual of a guess no Newton solved); cell_measure --
       # max_c |F_c,i|*dt/PV_i of the per-cell test, BUG-022 (None: the test is off);
       # exit_reason -- 'converged', 'line_search', 'linear_solver', 'max_iter', 'nonfinite',
       # 'active_set', 'sg_bound' (fourth stage: a root with two-phase Sg > 0.98), 'branch'
       # (_fallback: the Newton converged on an inconsistent BHP branch); '' -- not set.
       residual_tol: float | None = None
       cell_measure: float | None = None
       exit_reason: str = ''
   ```
3. `_cells_converged` (`:253-257`). До:
   ```python
       def _cells_converged(self,f,w):
           """BUG-022: max_c |f_c,i|*dt/PV_i <= cell_tol over the oil and gas rows of f = residual(); True when the test is off."""
           if w is None: return True
           n=self.grid.n
           return max(float(np.max(np.abs(f[:n])*w)),float(np.max(np.abs(f[n:])*w)))<=self.cell_tol
   ```
   После:
   ```python
       def _cell_measure(self,f,w):
           """BUG-022, DEBT-054: max_c |f_c,i|*dt/PV_i over the oil and gas rows of f = residual(); None when the test is off."""
           if w is None: return None
           n=self.grid.n
           return max(float(np.max(np.abs(f[:n])*w)),float(np.max(np.abs(f[n:])*w)))
       def _cells_converged(self,f,w):
           """BUG-022: max_c |f_c,i|*dt/PV_i <= cell_tol over the oil and gas rows of f = residual(); True when the test is off."""
           # the same operations as before DEBT-054, so the test is bitwise unchanged
           m=self._cell_measure(f,w)
           return m is None or m<=self.cell_tol
       def _newton_report(self,converged,iterations,nrm,tol,f,w,reason,**fields):
           """DEBT-054: report of a Newton solve -- ||F||_inf, its absolute tolerance, the per-cell measure of the same f, the exit reason."""
           return BlackOilNewtonReport(converged,iterations,float(nrm),
                                       residual_tol=None if tol is None else float(tol),
                                       cell_measure=self._cell_measure(f,w),exit_reason=reason,**fields)
   ```
4. `_newton_fixed_active_set` (`:347-382`) — пять возвратов. До → после (остальные строки без изменений):
   - `:362` `if nrm<=tol and self._cells_converged(f,w): return z,BlackOilNewtonReport(True,0,float(nrm))` → `if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,0,nrm,tol,f,w,'converged')`
   - `:366` `except Exception: return z,BlackOilNewtonReport(False,it,float(nrm))` → `except Exception: return z,self._newton_report(False,it,nrm,tol,f,w,'linear_solver')`
   - `:379` `if not accepted: return z,BlackOilNewtonReport(False,it,float(nrm))` → `if not accepted: return z,self._newton_report(False,it,nrm,tol,f,w,'line_search')`
   - `:381` `if nrm<=tol and self._cells_converged(f,w): return z,BlackOilNewtonReport(True,it,float(nrm))` → `if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,it,nrm,tol,f,w,'converged')`
   - `:382` `return z,BlackOilNewtonReport(False,max_iter,float(nrm))` → `return z,self._newton_report(False,max_iter,nrm,tol,f,w,'max_iter')`

   Над `:362` добавить комментарий:
   ```python
           # DEBT-054: every report carries the absolute tolerance, the per-cell measure of f
           # (the residual of the z it returns: the Jacobian call returns residual(z) at the same
           # z, see BUG-021 below; a rejected trial leaves f untouched) and why the solve stopped.
           # A failure at iteration it reports it (the failed iteration counted), as before.
   ```
5. `_advance_phases`, `:517`. До:
   ```python
           r=self.residual(self.pack(guess,mask),state_old,dt_s,mask); return guess,BlackOilNewtonReport(False,total_newton,float(np.linalg.norm(r,np.inf)),max_active_iter,total_switches)
   ```
   После:
   ```python
           # DEBT-054: the phase loop ran out; r is the residual of the guess with the new phase set,
           # which no Newton solved -- no absolute tolerance, the per-cell measure of r
           r=self.residual(self.pack(guess,mask),state_old,dt_s,mask)
           return guess,BlackOilNewtonReport(False,total_newton,float(np.linalg.norm(r,np.inf)),max_active_iter,total_switches,
                                             cell_measure=self._cell_measure(r,self._cell_weights(state_old,dt_s)),
                                             exit_reason='active_set')
   ```
6. Создать `numerical_solver/tests/test_prototype_failure_diagnostics.py` — шапка, помощники и разделы A, B (код — раздел 4.1 ниже). Импорты `_failure_details` и `SimpleNamespace` в шапку **не** ставить до шага 4: `_failure_details` появляется только там, а импорт несуществующего имени уронит сбор всего файла на шагах 1–3 (4.1, пометка у шапки).

**Проверка после этого шага:**
- `& $PY -m pytest tests/test_prototype_failure_diagnostics.py -q` — 5 passed (A1–A4, B1).
- Регресс: быстрый (1470 + 5).
- Регресс прототипа: `& $PY -m pytest tests -q` из `HydroSolverPrototype/Prototype_1.0.3` — 97 passed. `--quick` — после шага 3.

**Подводные камни:** 2.5 «Мера и невязка из одной `f`», «Сравнение dataclass».

**Зависимости:** требует шаг 0; блокирует шаги 2–4.

**Оценка:** ~30 строк кода, ~120 строк тестов, ~40 мин.

---

### Шаг 2: Ступень 4 — отчёт и число итераций (DEBT-061)

**Цель:** `_newton_switching` пишет допуск, меру, причину выхода и фактическое число итераций отказа.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`, `numerical_solver/tests/test_prototype_failure_diagnostics.py`.

**Контекст:**
- **Проходы цикла.** Цикл `for it in range(1,max_iter+2)` (`:562`) строит якобиан в начале каждого прохода. Сошедшееся решение пишет `it-1` (`:579`). Выход по лимиту — `break` при `it > max_iter` (`:584`, тогда `it-1` = `max_iter`). Обрыв — `break` после исключения решателя (`:586`) или нечисловых `pn`, `xn` (`:601`).
- **Сейчас** всё после цикла пишет `max_iter` (`:605`): замер 1.3 п. 6, 7 — 40 вместо 2 и 1.
- **Удержанные ячейки.** `f` отказа (`:604`) вычисляется внутри `try`, пока ячейки «выше по потоку» ещё удерживаются (`_upwind_frozen` сбрасывается в `finally`, `:606-607`). Меру считать по ней же.

**Что сделать:**

1. После `switched=total=0; flips=…` (`:558`) добавить:
   ```python
           # DEBT-054, DEBT-061: why the loop stopped; a pass with it > max_iter breaks on the limit
           reason='max_iter'
   ```
2. `:579`. До:
   ```python
                               return new,BlackOilNewtonReport(ok,it-1,float(nrm),1,total)
   ```
   После:
   ```python
                               return new,self._newton_report(ok,it-1,nrm,tol,f,w,'converged' if ok else 'sg_bound',
                                                              active_set_iterations=1,phase_switches=total)
   ```
3. `:586`. До: `                except Exception: break` → После: `                except Exception: reason='linear_solver'; break`
4. `:601`. До: `                if not (np.all(np.isfinite(pn)) and np.all(np.isfinite(xn))): break` → После: `                if not (np.all(np.isfinite(pn)) and np.all(np.isfinite(xn))): reason='nonfinite'; break`
5. `:604-605`. До:
   ```python
               f=self.residual(z,state_old,dt_s,mask)
               return self.unpack(z,mask),BlackOilNewtonReport(False,max_iter,float(np.linalg.norm(f,np.inf)),1,total)
   ```
   После:
   ```python
               # DEBT-061: the passes it ran minus one, as the converged report (:579) -- not max_iter,
               # which a break after a linear-solver failure or a non-finite update reported too.
               # f is evaluated here, before finally drops the held upstream cells: residual_inf and
               # the per-cell measure are of the scheme the Newton was solving (DEBT-054)
               f=self.residual(z,state_old,dt_s,mask)
               return self.unpack(z,mask),self._newton_report(False,it-1,np.linalg.norm(f,np.inf),tol,f,w,reason,
                                                              active_set_iterations=1,phase_switches=total)
   ```
   Выход по лимиту: `it` = `max_iter+1`, `it-1` = 40 — как прежде. Если последний проход ушёл в доводку (`continue`, `:583`), цикл кончается сам с `it` = `max_iter+1`, причина по умолчанию — лимит.
6. Докстринг `_newton_switching` (`:537`) не менять.
7. Тесты раздела C (4.1).

**Проверка после этого шага:**
- `& $PY -m pytest tests/test_prototype_failure_diagnostics.py -q` — 9 passed.
- Регресс: быстрый. Особо — `tests/test_prototype_phase_switching.py`, `tests/test_prototype_stage4_memory.py`, `tests/test_prototype_cell_tolerance.py`.
- Регресс прототипа: тесты прототипа — 97 passed.

**Подводные камни:** 2.5 «Мера и невязка из одной `f`»; 2.7 п. 2, 3.

**Зависимости:** требует шаг 1; блокирует шаг 4.

**Оценка:** ~15 строк кода, ~70 строк тестов, ~30 мин.

---

### Шаг 3: Ветвь скважины и подмена DEBT-030

**Цель:** `_fallback` отмечает отказ по несогласованной ветви; `advance` при общем отказе переносит три новых поля ступени 1 вместе с прежними полями Ньютона.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`, `numerical_solver/tests/test_prototype_failure_diagnostics.py`.

**Контекст:**
- **`_fallback`.** Если Ньютон сошёлся, но ветвь несогласована (`:484`), и вторую ветвь пробовать нельзя, `_fallback` пишет `rep.converged=False` (`:488`). Причина выхода сошедшегося Ньютона — `converged`, в тексте отказа это читалось бы абсурдно.
- **Подмена DEBT-030.** При отказе всех ступеней `advance` берёт поля Ньютона из отчёта ступени 1. Новые поля — тоже поля Ньютона: без переноса допуск, мера и причина относились бы к последней попытке, а итерации и невязка — к ступени 1.

**Что сделать:**

1. `_fallback`, `:487-488`. До:
   ```python
                   if other in tried or (other=='open' and open_hopeless):
                       rep.converged=False; return new,rep
   ```
   После:
   ```python
                   if other in tried or (other=='open' and open_hopeless):
                       # DEBT-054: a Newton that converged on an inconsistent branch failed by the
                       # branch, not by the Newton; a failed Newton keeps its own exit reason
                       if rep.converged: rep.exit_reason='branch'
                       rep.converged=False; return new,rep
   ```
2. `advance`, `:424-434`. До:
   ```python
               # attempt's.  Accepted steps are untouched (_grow_dt reads them).
               rep=replace(rep,iterations=orig.iterations,residual_inf=orig.residual_inf,
                           active_set_iterations=orig.active_set_iterations,
                           phase_switches=orig.phase_switches)
   ```
   После:
   ```python
               # attempt's.  Accepted steps are untouched (_grow_dt reads them).
               # DEBT-054: the absolute tolerance, the per-cell measure and the exit reason are
               # Newton fields too -- the original algorithm's, consistent with its residual.
               rep=replace(rep,iterations=orig.iterations,residual_inf=orig.residual_inf,
                           active_set_iterations=orig.active_set_iterations,
                           phase_switches=orig.phase_switches,
                           residual_tol=orig.residual_tol,cell_measure=orig.cell_measure,
                           exit_reason=orig.exit_reason)
   ```
3. Докстринг `advance` (`:384-389`), последняя строка `:389`. До:
   ```
           If all stages fail, the report carries the original algorithm's Newton (DEBT-030)."""
   ```
   После:
   ```
           If all stages fail, the report carries the original algorithm's Newton (DEBT-030),
           with its tolerance, per-cell measure and exit reason (DEBT-054)."""
   ```
4. Тесты раздела D и E (4.1).

**Проверка после этого шага:**
- `& $PY -m pytest tests/test_prototype_failure_diagnostics.py -q` — 13 passed.
- Регресс: быстрый. Особо — `tests/test_prototype_globalization.py`, `tests/test_prototype_well_branch.py`, `tests/test_prototype_open_branch_skip.py`.
- Регресс прототипа: тесты прототипа — 97 passed. **`regression\run_regression.py --quick` — 11/11 PASS** (правка прототипа закончена). Ожидание — побитово (2.5 «Прототип»). Выходы `OUTPUT/REGRESSION_<время>/` удалить после проверки.

**Подводные камни:** 2.5 «`exit_reason` у общего отчёта».

**Зависимости:** требует шаги 1, 2; блокирует шаг 4.

**Оценка:** ~10 строк кода, ~60 строк тестов, ~25 мин + 8 мин регрессии.

---

### Шаг 4: Текст отказа адаптера

**Цель:** `HydroConvergenceError` — прежний текст плюс допуск, мера с порогом, причина выхода, невыполненное условие и чья это статистика.

**Файлы:** `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`, `numerical_solver/tests/test_prototype_failure_diagnostics.py`.

**Контекст:** 2.2. Порог `cell_tol` берётся у модели (`self._model.cell_tol`), куда его положила фабрика из `numerics.newton_cell_tol` (`factory.py:442`). Подставные отчёты тестов без новых полей → хвоста нет.

**Что сделать:**

1. Докстринг модуля (`:1-35`): после абзаца «Память ступени 4 (DEBT-048)» (`:27-30`) добавить абзац:
   ```
   Текст отказа (DEBT-054): прежний текст (dt, t, итерации, невязка) и хвост из отчёта
   Ньютона — абсолютный допуск, мера условия по ячейке с порогом numerics.newton_cell_tol,
   причина выхода, какое условие сходимости не выполнено и чья это статистика (ступень 1
   после подмены DEBT-030 или ступень 4 по памяти).
   ```
2. После `STAGE4_MAX_FAILURES = 2 …` (`:54`) добавить:
   ```python


   # Причина выхода из Ньютона прототипа — поле exit_reason отчёта (DEBT-054). Неизвестный
   # код печатается как есть: прототип может добавить причину раньше, чем адаптер — перевод.
   _EXIT_REASONS = {
       "line_search": "линейный поиск не принял ни одной точки",
       "linear_solver": "отказ линейного решателя",
       "max_iter": "исчерпан лимит итераций",
       "nonfinite": "нечисловое приближение",
       "active_set": "набор фаз не установился",
       "sg_bound": "корень с S_g > 0.98",
       "branch": "ветвь скважины несогласована",
   }


   def _failure_details(report, cell_tol: float | None, stage: int) -> str:
       """Хвост текста отказа: допуск, мера ячеек, причина выхода, невыполненное условие (DEBT-054)."""
       # Поля residual_tol, cell_measure, exit_reason несёт BlackOilNewtonReport с DEBT-054.
       # Подставные отчёты тестов (SimpleNamespace, отчёт без этих полей) их не имеют —
       # хвоста нет, текст прежний.
       tol = getattr(report, "residual_tol", None)
       measure = getattr(report, "cell_measure", None)
       reason = getattr(report, "exit_reason", "")
       if tol is None and measure is None and not reason:
           return ""
       text = ""
       if tol is not None:
           text += f" (допуск {tol:.2e})"
       if measure is not None:
           text += f", мера ячеек {measure:.2e}"
           if cell_tol is not None:
               text += f" (порог numerics.newton_cell_tol = {cell_tol:g})"
       if reason:
           text += f", выход: {_EXIT_REASONS.get(reason, reason)}"
       # Какое условие не выполнено — те же сравнения, что в Ньютоне прототипа
       # (||F||_inf <= residual_tol; мера <= cell_tol, BUG-022), поэтому это факт,
       # а не догадка. Только для отчёта о приближении Ньютона (есть допуск): у выхода
       # 'active_set' невязка — начального приближения нового набора фаз. «Оба
       # выполнены» при отказе — отказ не по условиям: ветвь скважины, S_g > 0.98,
       # у ступени 4 — переключения фаз или удержанные ячейки выше по потоку не
       # устоялись к лимиту итераций (причина выхода — рядом в тексте).
       if tol is not None:
           abs_ok = report.residual_inf <= tol
           if measure is None or cell_tol is None:
               text += " — абсолютное условие " + ("выполнено" if abs_ok else "не выполнено")
           else:
               text += " — " + {
                   (True, False): "не выполнено только условие по ячейке",
                   (False, True): "не выполнено только абсолютное условие",
                   (False, False): "не выполнены оба условия сходимости",
                   (True, True): "оба условия сходимости выполнены",
               }[(abs_ok, measure <= cell_tol)]
       # Чьи числа: при отказе advance — исходного алгоритма (подмена DEBT-030), у ступени 4
       # по памяти (DEBT-048) — её собственные
       return text + f"; числа — Ньютона ступени {stage}"
   ```
3. `solve`, шаг 3 (`:169-176` на `73ef031`; на `ccc5ae3` было `:157-164`, текст тот же). До:
   ```python
               # Дробит шаг Simulator (DEBT-015): делит пополам только этот
               # подшаг и повторяет его из того же состояния. Здесь — факты
               # отказа для журнала; текст для пользователя — в Simulator.
               raise HydroConvergenceError(
                   f"advance не сошёлся{' (ступень 4 по памяти)' if by_memory else ''}: "
                   f"dt = {dt:.3e} с, "
                   f"t = {state.t / DAY_TO_S:.4f} сут, итераций {report.iterations}, "
                   f"невязка {report.residual_inf:.2e}")
   ```
   После:
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
   `m` — `self._model`, определён в `:151` (на `73ef031`).
4. В шапку `test_prototype_failure_diagnostics.py` добавить импорты `from types import SimpleNamespace` и `from gpn_multiphase_solver.hydro.prototype_adapter import _failure_details` (4.1, пометка у шапки). Тесты раздела F (4.1).

**Проверка после этого шага:**
- `& $PY -m pytest tests/test_prototype_failure_diagnostics.py -q` — 25 passed (13 + F1 + F2 × 11).
- Регресс: быстрый. Особо — `tests/test_prototype_adapter.py`, `tests/test_prototype_stage4_memory.py`, `tests/test_prototype_activation_cap.py`.

**Подводные камни:** 2.6 DEBT-008 (те же методы адаптера). Подставные отчёты — 2.3 «Подставные отчёты тестов».

**Зависимости:** требует шаг 3; блокирует шаг 5.

**Оценка:** ~60 строк кода, ~70 строк тестов, ~30 мин.

---

### Шаг 5: Текст отказа `Simulator`

**Цель:** при исчерпании дробления текст `RuntimeError` кончается текстом последнего `HydroConvergenceError`.

**Файлы:** `numerical_solver/gpn_multiphase_solver/simulator.py`, `numerical_solver/tests/test_simulator.py`, `numerical_solver/tests/test_prototype_failure_diagnostics.py`.

**Контекст:** 1.1. Сейчас пользователь видит текст адаптера только в цепочке traceback (`raise … from exc`, `:255`) и в отладочном журнале (`:253`). Начало текста `Simulator` цитируют README и тесты — дописывается только конец.

**Что сделать:**

1. `_advance`, `:254-255`. До:
   ```python
                   if size == 1:
                       raise RuntimeError(self._failure_message(state, dt)) from exc
   ```
   После:
   ```python
                   if size == 1:
                       raise RuntimeError(self._failure_message(state, dt, exc)) from exc
   ```
2. `_failure_message`, `:310-329`. До (заголовок, докстринг, конец):
   ```python
       def _failure_message(self, state: SimulationState, dt: float) -> str:
           """Текст отказа: факты подшага, на котором исчерпано дробление (BUG-018, DEBT-015)."""
           …
               f"Если отказ вызван величиной шага, поможет больший "
               f"numerics.max_retries или меньший time.dt_integration; если шаг "
               f"не сходится и при мелких подшагах, причина не в его величине.")
   ```
   После:
   ```python
       def _failure_message(self, state: SimulationState, dt: float,
                            exc: HydroConvergenceError) -> str:
           """Текст отказа: факты подшага, на котором исчерпано дробление, и его отказ гидродинамики (BUG-018, DEBT-015, DEBT-054)."""
           …
           # Конец текста — текст HydroConvergenceError этого подшага (DEBT-054): у
           # прототипа там допуск, мера условия по ячейке, причина выхода Ньютона и
           # какое условие сходимости не выполнено. Прежде он был виден только в
           # цепочке traceback и в отладочном журнале.
           …
               f"Если отказ вызван величиной шага, поможет больший "
               f"numerics.max_retries или меньший time.dt_integration; если шаг "
               f"не сходится и при мелких подшагах, причина не в его величине. "
               f"Последний отказ гидродинамики: {exc}")
   ```
   Комментарий ставить после существующего блока комментариев (`:312-317`), перед `n_units = …`. Существующие комментарии не удалять.
3. `tests/test_simulator.py`, класс `TestEnergySubstepsUnderRetry`: после `test_exhausted_subdivision_raises` (`:549-566`) добавить тест G1 (4.1).
4. `test_prototype_failure_diagnostics.py`: тест G2 (4.1).

**Проверка после этого шага:**
- `& $PY -m pytest tests/test_simulator.py tests/test_prototype_failure_diagnostics.py tests/test_prototype_activation_cap.py -q` — зелёные.
- Регресс: быстрый.

**Зависимости:** требует шаг 4; блокирует шаг 7.

**Оценка:** ~10 строк кода, ~35 строк тестов, ~20 мин.

---

### Шаг 6: `CHANGELOG` прототипа

**Цель:** запись о правке отчёта в `CHANGELOG_1.0.3.md`.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`.

**Что сделать:** в конец файла (после раздела DEBT-048) добавить раздел. Числа тестов и регрессии — фактические из шагов 3 и 7:
```markdown

## Local changes — GPN project (DEBT-054): why a Newton solve stopped
- Problem: after BUG-022 a Newton solve converges only when the absolute test and the per-cell test both hold. A solve rejected by the per-cell test alone was reported as an ordinary failure with a residual far below the absolute tolerance: on the first day of the GPN BUG-018 case at N = 350, "4 iterations, residual 6.51e-15" against the tolerance 5.4e-7 -- the line search stalled at round-off while max_c |F_c,i|*dt/PV_i = 2.6e-8 > cell_tol = 1e-8. The report carried neither the tolerance, nor the per-cell measure, nor why the Newton stopped. A failed fourth-stage Newton reported `iterations = max_iter` also when it stopped early (DEBT-061).
- `BlackOilNewtonReport`: new fields `residual_tol` (atol + rtol*scale of the absolute test; None for the 'active_set' exit), `cell_measure` (max_c |F_c,i|*dt/PV_i on the residual of `residual_inf`; None with `cell_tol=None`), `exit_reason` ('converged', 'line_search', 'linear_solver', 'max_iter', 'nonfinite', 'active_set', 'sg_bound', 'branch'). They are filled at every return of `_newton_fixed_active_set` and `_newton_switching` and at the phase-loop exit of `_advance_phases`; `_fallback` sets 'branch' when a converged Newton is dropped as an inconsistent BHP branch; `advance()` carries the three fields of the original algorithm together with its other Newton fields (DEBT-030). New methods `_cell_measure`, `_newton_report`; `_cells_converged` uses `_cell_measure`, bitwise the former test.
- `_newton_switching`: a failed solve reports the passes it ran minus one, as a converged one, not `max_iter`. `_newton_fixed_active_set` keeps reporting the failed iteration (`step_log.csv` rows unchanged). The residual of a failed fourth-stage solve and its per-cell measure are of the scheme with held upstream cells, as `residual_inf` was before.
- Accepted steps and all former report fields are bitwise unchanged (except `iterations` of an early-stopped failed fourth-stage Newton): tests <N> passed, regression 17/17 PASS bitwise; `step_log.csv` and `run_summary.json` keep their columns. In GPN the failure message names the tolerance, the measure, the exit reason and which test failed.
- Tests: `numerical_solver/tests/test_prototype_failure_diagnostics.py` of the GPN project. Physics, residual equations, tolerances, Newton/active-set logic and well semantics are unchanged. The distribution version stays `1.0.3+gpn.1`. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/102; plan: `vault/plans/debt-054 newton-failure-diagnostics.md` of the GPN project.
```

**Проверка:** документ; `& $PY -m pytest tests/ --collect-only -q`.

**Зависимости:** требует шаг 3 (правка прототипа закончена). Числа тестов и регрессии вписываются в шаге 7, п. 5 — до них в тексте стоят `<N>`.

**Оценка:** ~10 мин.

---

### Шаг 7: Проверка целиком

**Цель:** истории побитово; текст отказа на трёх сценариях называет тот класс, что проба; полный прогон; полная регрессия прототипа.

**Файлы:** — (выходы проб в `vault/issues/debt-054/probes/`).

**Что сделать** (из `<worktree>\numerical_solver`):
1. ```powershell
   & $PY ..\vault\issues\debt-054\probes\histories.py save after
   & $PY ..\vault\issues\debt-054\probes\histories.py compare *> ..\vault\issues\debt-054\probes\histories_compare.out.txt
   ```
   **Ожидание:** все 5 сценариев — «побитово», `calls` равны, у всех 10 отказов (2 + 1 + 0 + 0 + 7) новый текст начинается с прежнего, ИТОГ OK. Строки «стало» — для шага 8 и комментария issue.
2. ```powershell
   & $PY ..\vault\issues\debt-054\probes\failure_census.py 14_high_gor_cooling *> ..\vault\issues\debt-054\probes\failure_census_after.out.txt
   & $PY ..\vault\issues\debt-054\probes\failure_census.py --shutin *> ..\vault\issues\debt-054\probes\failure_census_shutin_after.out.txt
   ```
   **Ожидание:** у каждого отказа класс в тексте адаптера (хвост после «—») совпадает с классом пробы в строке «печатаемый отчёт» («только ячейка» → «не выполнено только условие по ячейке», «оба не выполнены» → «не выполнены оба условия сходимости»). Выход в тексте совпадает с выходом пробы (`line_search` → «линейный поиск…», `max_iter` → «исчерпан лимит итераций»). Проба считает независимо от нового кода, по обёрткам.
3. Полный прогон: `& $PY -m pytest tests/ -q`. **Ожидание:** 1741 + 27 = 1768 passed (или база + 27).
4. Регрессия прототипа полная. Перед запуском зафиксировать HEAD worktree (каждый кейс — отдельный процесс). Из `HydroSolverPrototype\Prototype_1.0.3`: `& $PY regression\run_regression.py` (~45 мин). **Ожидание:** 17/17 PASS. FAIL — не повод переснимать эталон: разобрать, с какого шага расхождение (правка не должна менять ни одного принятого шага). `OUTPUT/REGRESSION_<время>/` удалить после разбора.
5. Вписать числа в `CHANGELOG` (шаг 6).

**Проверка:** пп. 1–4.

**Зависимости:** требует шаги 1–5.

**Оценка:** ~70 мин (из них 45 — регрессия, 10 — полный прогон).

---

### Шаг 8: Vault и issue

**Цель:** реестр, заметки, issue.

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md` (DEBT-054, DEBT-061, DEBT-055, BUG-025)
- `vault/knowledge/decisions/P4-адаптивный-шаг.md`
- `vault/knowledge/decisions/модули-simulator-оркестратор.md`
- `vault/knowledge/decisions/P1-адаптер-единицы.md`
- `vault/knowledge/debugging/абсолютный допуск Ньютона один на все ячейки недорешал забойную — условие по ячейке отнесено к её поровому объёму.md`
- `vault/issues/debt-054/05-comment-done.md`

**Что сделать:**
1. **Реестр.**
   - DEBT-054: статус — реализовано (формат `/implement`).
   - DEBT-061: **Статус:** `✅ ЗАКРЫТ (<дата>) — поглощена [[DEBT-054]] (решение пользователя 2026-10-11)`, поле **План:** `[[debt-054 newton-failure-diagnostics]]`. Строку «Влияние на выход: нет» дополнить: «с DEBT-048 отчёт ступени 4 по памяти печатается в тексте отказа адаптера».
   - DEBT-055, «Мотивация»: «а сообщение ([[DEBT-054]]) причину не называет» → «сообщение с [[DEBT-054]] называет: „не выполнено только условие по ячейке“ с мерой и порогом».
   - BUG-025, «Не проверено»: после «(отчёт отказа этого не различает — [[DEBT-054]])» дописать «; с DEBT-054 различает — `exit_reason`, `residual_tol`».
2. **`P4-адаптивный-шаг.md`**, таблица «Логирование» (`:100`, `:102`):
   - DEBUG: «текст `HydroConvergenceError` (dt, t, итерации, невязка)» → «текст `HydroConvergenceError` (dt, t, итерации, невязка; с DEBT-054 — допуск, мера условия по ячейке, причина выхода Ньютона, какое условие не выполнено)»;
   - ERROR: дописать «…; в конце — „Последний отказ гидродинамики: <текст HydroConvergenceError>“ (DEBT-054)».
3. **`модули-simulator-оркестратор.md`**:
   - фрагмент кода `:117`: `self._failure_message(state, dt)` → `self._failure_message(state, dt, exc)`;
   - текст `:163-167`: после «…причину текст не называет.» дописать «В конце — текст отказа гидродинамики последнего подшага (DEBT-054): у прототипа он называет, какое условие сходимости не выполнено».
4. **`P1-адаптер-единицы.md`**, раздел 6 «Обработка расходимости» (`:477-483`): дописать абзац «Текст `HydroConvergenceError` (DEBT-054): прежний (dt, t, итерации, невязка) и хвост из отчёта Ньютона — допуск, мера ячеек с порогом `numerics.newton_cell_tol`, причина выхода, невыполненное условие, чьи числа (ступень 1 после подмены DEBT-030 или ступень 4 по памяти)». Фрагмент кода `:232-239` — исторический эскиз, не трогать.
5. **Заметка BUG-022** (`…отнесено к её поровому объёму.md:44`): «Решение, отвергнутое только условием ячейки, в отчёте выглядит как „невязка 6.5e-15, не сошлось“ ([[DEBT-054]])» → «…выглядело как „невязка 6.5e-15, не сошлось“; с [[DEBT-054]] текст отказа называет меру, порог и „не выполнено только условие по ячейке“».
6. **`05-comment-done.md`** и комментарий в issue #102 — по `/implement`. Приложить строки «было/стало» из `histories_compare.out.txt` для BUG-018 и суточного останова.
7. `vault/00-home/index.md` — секция Plans, если `/implement` её ведёт (план добавлен при планировании, шаг 5.2 `/plan-improve`).

**Проверка:** `& $PY -m pytest tests/ --collect-only -q` (документы).

**Зависимости:** требует шаг 7.

**Оценка:** ~25 мин.

---

## 4. Тестовая стратегия

### 4.1. Новый файл `numerical_solver/tests/test_prototype_failure_diagnostics.py`

Шапка и помощники (шаг 1). **Две строки, помеченные `# шаг 4`, добавлять только в шаге 4.** `_failure_details` до него не существует, и импорт уронит сбор всего файла.

```python
"""DEBT-054: отчёт Ньютона прототипа называет причину отказа, текст отказа — какое условие не выполнено.

После BUG-022 решение Ньютона принимается, только если выполнены абсолютный критерий
||F||_inf <= atol + rtol*max(||F_0||_inf, 1e-9) и условие по ячейке
max_c |F_c,i|*dt/PV_i <= cell_tol. Решение, отвергнутое только условием ячейки, выглядело
в отчёте как «итераций 4, невязка 6.51e-15, не сошлось» (BUG-018 при N = 350, шаг
86400 с): ни допуска, ни меры ячеек, ни причины выхода (линейный поиск встал на пределе
округления). Теперь отчёт несёт residual_tol, cell_measure (на той же невязке, что
residual_inf) и exit_reason; адаптер печатает их и какое условие не выполнено; Simulator
дописывает текст адаптера в свой при исчерпании дробления. Отказ ступени 4 пишет число
выполненных итераций, а не max_iter (DEBT-061, поглощена DEBT-054).

План: vault/plans/debt-054 newton-failure-diagnostics.md; замеры —
vault/issues/debt-054/probes/failure_census.out.txt, test_scenarios.out.txt.
"""

from types import SimpleNamespace                                    # шаг 4

import numpy as np
import pytest

from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from gpn_multiphase_solver.hydro.prototype_adapter import _failure_details  # шаг 4
from gpn_multiphase_solver.units import BAR_TO_PA
from radial_blackoil.blackoil import BlackOilNewtonReport
from radial_blackoil.state import BlackOilState

from .test_prototype_activation_cap import _sim
from .test_prototype_cell_tolerance import (  # noqa: F401
    _build as _nabor, _measure, CELL_TOL, DT, DT_STAGE4, shutin)
from .test_prototype_globalization import ORIG3, _install_fake_reports
from .test_prototype_well_branch import _model, drawn_down  # noqa: F401

ATOL, RTOL = 1e-11, 1e-8      # умолчания обоих Ньютонов прототипа (atol_sm3s, rtol)


def _tol(model, z0, s_old, dt, mask):
    """Абсолютный допуск Ньютона: atol + rtol*max(||F(z0)||_inf, 1e-9) — те же операции, что в прототипе."""
    f0 = model.residual(z0, s_old, dt, mask)
    return ATOL + RTOL * max(float(np.linalg.norm(f0, np.inf)), 1e-9)


def _bug018_model(N=350):
    """BUG-018 (R_s0 = 500, p_wf = 5 МПа) на N ячейках: модель фабрики, начальное состояние прототипа, шаг 1 сут."""
    sim, init, dt = _sim(N=N)
    model = sim._hydro._model
    # Управление — как ставит адаптер перед advance (prototype_adapter.solve, шаг 1)
    model.set_bhp_control(sim._schedule.intervals[0].bc.well.p_wf / BAR_TO_PA)
    ps = BlackOilState(pressure_bar=init.p / BAR_TO_PA, rs_sm3_sm3=init.Rs.copy(),
                       sg=init.Sg.copy(), gas_active=(init.regime == 1))
    return model, ps, dt
```

> Перед записью сверить: `sim._schedule.intervals[0].bc.well` у сценария BUG-018 — `PressureControl` с полем `p_wf` (Па). Конфиг `tests/data/bug018_rs500/config.json` — управление по забойному давлению, $p_{wf}$ = 5 МПа (шапка `test_prototype_activation_cap.py:31-34`).

**Раздел A — `_newton_fixed_active_set` (шаг 1):**

```python
class TestFixedActiveSet:
    """Ступени 1–3: _newton_fixed_active_set на Nabor_1b (N = 12, отбор 200 -> 100 бар, 1 ч)."""

    def test_converged_report(self):
        """Сошедшееся решение: допуск, мера той же невязки, выход 'converged'.

        Замер (test_scenarios.out.txt, п. 1): 3 итерации, невязка 9.2e-16, допуск 1.94e-11,
        мера 3.44e-12 — побитово мера теста (pack(unpack(z)) == z).
        Ловит: мера не той невязки или не теми весами, допуск не той формулы.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)
        z0 = model.pack(state)
        z, rep = model._newton_fixed_active_set(z0, state, DT, state.gas_active)
        assert rep.converged and rep.exit_reason == "converged"
        assert rep.residual_tol == _tol(model, z0, state, DT, state.gas_active)
        assert rep.residual_inf <= rep.residual_tol
        assert rep.cell_measure == _measure(model, state, model.unpack(z, state.gas_active), DT)
        assert rep.cell_measure <= CELL_TOL

    def test_cell_test_off(self):
        """Условие по ячейке выключено (cell_tol=None, собственные расчёты прототипа): меры нет, допуск есть."""
        model, state = _nabor(12)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active)
        assert rep.converged and rep.exit_reason == "converged"
        assert rep.cell_measure is None and rep.residual_tol is not None

    def test_limit_exit(self):
        """max_iter = 1, а решению нужно 3: выход по лимиту, абсолютное условие не выполнено.

        Замер (п. 2): 1 итерация, невязка 5.7e-5 при допуске 1.9e-11; линейный поиск точку
        принял (z сдвинулся), поэтому выход — лимит, а не линейный поиск.
        Ловит: выход по лимиту записан другой причиной.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active,
                                                max_iter=1)
        assert not rep.converged and rep.iterations == 1 and rep.exit_reason == "max_iter"
        assert rep.residual_inf > rep.residual_tol

    def test_linear_solver_exit(self, monkeypatch):
        """Исключение линейного решателя на первой итерации: выход 'linear_solver', отчёт — о стартовой точке.

        z не сдвинулся: невязка и мера — начального приближения (замер п. 3: невязка = ||F_0||).
        Ловит: мера или невязка не той точки при досрочном выходе.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)

        def broken(*args, **kwargs):
            raise np.linalg.LinAlgError("вырожденная матрица (тест)")

        monkeypatch.setattr(model, "_linear_solve", broken)
        z0 = model.pack(state)
        _, rep = model._newton_fixed_active_set(z0, state, DT, state.gas_active)
        f0 = model.residual(z0, state, DT, state.gas_active)
        assert not rep.converged and rep.iterations == 1 and rep.exit_reason == "linear_solver"
        assert rep.residual_inf == float(np.linalg.norm(f0, np.inf))
        assert rep.cell_measure == _measure(model, state, state, DT)
```

**Раздел B — `_advance_phases` (шаг 1):**

```python
def test_active_set_exit():
    """Цикл набора фаз исчерпан (max_active_iter = 1, газ появляется на шаге): выход 'active_set'.

    Невязка — начального приближения нового набора фаз, которое ни один Ньютон не решал:
    допуска нет (None), мера — той же невязки. Замер (п. 4): N = 12 — 5 смен фаз.
    Ловит: отчёт исчерпания набора фаз без причины или с допуском чужого Ньютона.
    """
    model, state = _nabor(12, cell_tol=CELL_TOL)
    _, rep = model._advance_phases(state, DT, max_active_iter=1)
    assert not rep.converged and rep.exit_reason == "active_set"
    assert (rep.active_set_iterations, rep.phase_switches) == (1, 5)
    assert rep.residual_tol is None
    assert rep.cell_measure is not None and rep.cell_measure > 0.0
```

**Раздел C — ступень 4 (шаг 2):**

```python
class TestSwitching:
    """Ступень 4: _newton_switching на шаге останова 168.75 с (rs300 после 10 сут добычи, q_oil = 0)."""

    def test_converged_report(self, shutin):
        """Замер (п. 5): 16 итераций, невязка 6.9e-15 при допуске 4.38e-11, мера 1.21e-11."""
        model, ps = shutin
        z0 = model.pack(ps, ps.gas_active)
        _, rep = model._newton_switching(ps, DT_STAGE4)
        assert rep.converged and rep.exit_reason == "converged"
        assert rep.residual_tol == _tol(model, z0, ps, DT_STAGE4, ps.gas_active)
        assert rep.residual_inf <= rep.residual_tol and rep.cell_measure <= CELL_TOL

    def test_limit_only_cell_test(self, shutin):
        """Недостижимый порог 1e-30: 40 итераций, выход по лимиту, абсолютное условие выполнено.

        Тот же класс, что у отказов ступени 4 по памяти на суточном останове
        (failure_census_shutin.out.txt: невязка 7.6e-16, мера 1.29e-8 > 1e-8).
        Замер (п. 5): невязка 8.1e-15 при допуске 4.38e-11. Порог возвращается в finally:
        фикстура модульная.
        """
        model, ps = shutin
        try:
            model.cell_tol = 1e-30
            _, rep = model._newton_switching(ps, DT_STAGE4)
        finally:
            model.cell_tol = CELL_TOL
        assert not rep.converged and rep.iterations == 40 and rep.exit_reason == "max_iter"
        assert rep.residual_inf <= rep.residual_tol and rep.cell_measure > 1e-30

    def test_linear_solver_break_reports_iterations_run(self, shutin, monkeypatch):
        """DEBT-061: исключение решателя на 3-м вызове — 2 итерации и 'linear_solver', а не 40.

        До правки отчёт после break писал max_iter = 40 (замер п. 6).
        """
        model, ps = shutin
        orig, calls = model._linear_solve, []

        def third_fails(*args, **kwargs):
            calls.append(1)
            if len(calls) == 3:
                raise np.linalg.LinAlgError("вырожденная матрица (тест)")
            return orig(*args, **kwargs)

        monkeypatch.setattr(model, "_linear_solve", third_fails)
        _, rep = model._newton_switching(ps, DT_STAGE4)
        assert not rep.converged
        assert (rep.iterations, rep.exit_reason) == (2, "linear_solver")

    def test_nonfinite_break_reports_iterations_run(self, shutin, monkeypatch):
        """DEBT-061: NaN в направлении 2-го вызова — 1 итерация и 'nonfinite', а не 40 (замер п. 7)."""
        model, ps = shutin
        orig, calls = model._linear_solve, []

        def nan_on_second(*args, **kwargs):
            calls.append(1)
            dz = orig(*args, **kwargs)
            if len(calls) == 2:
                dz = dz.copy()
                dz[0] = np.nan
            return dz

        monkeypatch.setattr(model, "_linear_solve", nan_on_second)
        _, rep = model._newton_switching(ps, DT_STAGE4)
        assert not rep.converged
        assert (rep.iterations, rep.exit_reason) == (1, "nonfinite")
```

**Раздел D, E — ветвь и подмена DEBT-030 (шаг 3):**

```python
class TestBranchAndTotalFailure:
    """_fallback и advance на подменённом _advance_phases (Nabor_1b, p_wf = 150 бар, drawn_down: p[0] = 111.7)."""

    def test_inconsistent_branch_exit(self, drawn_down):
        """Ньютон сошёлся на обеих ветках, обе несогласованы — выход 'branch', а не 'converged'.

        «Закрыта» с p[0] = 160 > p_wf, «открыта» с p[0] = 140 < p_wf (p_ext = 200 > 150 —
        «открыта» пробуется, DEBT-040).
        """
        model = _model(150.0)
        ok = BlackOilNewtonReport(True, 2, 1e-15, residual_tol=1e-11, exit_reason="converged")
        calls = _install_fake_reports(model, {("shut", None, False): (160.0, ok),
                                              ("open", None, False): (140.0, ok)})
        _, rep = model._fallback(drawn_down, 3600.0, 12, 15)
        assert calls == [("shut", None, False), ("open", None, False)]
        assert not rep.converged and rep.exit_reason == "branch"
        assert (rep.well_branch, rep.well_switches) == ("open", 1)

    def test_failed_newton_keeps_its_exit(self, drawn_down):
        """Последняя ветка — отказ Ньютона: выход его ('line_search'), не 'branch'."""
        model = _model(150.0)
        ok = BlackOilNewtonReport(True, 2, 1e-15, residual_tol=1e-11, exit_reason="converged")
        bad = BlackOilNewtonReport(False, 7, 1e-3, residual_tol=1e-11, exit_reason="line_search")
        _install_fake_reports(model, {("shut", None, False): (160.0, ok),
                                      ("open", None, False): (0.0, bad)})
        _, rep = model._fallback(drawn_down, 3600.0, 12, 15)
        assert not rep.converged and rep.exit_reason == "line_search"

    def test_total_failure_carries_original_diagnostics(self, drawn_down):
        """Отказ всех ступеней: допуск, мера и выход — исходного алгоритма, как итерации и невязка (DEBT-030).

        У попыток запасного пути и третьей ступени поля другие: видно, чей отчёт вернул advance.
        Ловит: подмена DEBT-030 без новых полей (допуск и мера последней попытки при невязке ступени 1).
        """
        model = _model(150.0)
        orig = BlackOilNewtonReport(False, 4, 6.5e-15, 2, 21, residual_tol=5.4e-7,
                                    cell_measure=2.6e-8, exit_reason="line_search")
        other = BlackOilNewtonReport(False, 40, 18.2, residual_tol=5.4e-7,
                                     cell_measure=3.6e7, exit_reason="max_iter")
        branch = BlackOilNewtonReport(True, 0, 0.0, residual_tol=1e-11, cell_measure=0.0,
                                      exit_reason="converged")
        _install_fake_reports(model, {
            ORIG3: (0.0, orig),
            ("shut", None, False): (0.0, other), ("open", None, False): (140.0, branch),
            ("shut", None, True): (0.0, other), ("open", None, True): (140.0, branch)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert not rep.converged
        assert (rep.iterations, rep.residual_inf) == (4, 6.5e-15)
        assert (rep.residual_tol, rep.cell_measure, rep.exit_reason) == (5.4e-7, 2.6e-8, "line_search")


def test_real_total_failure_only_cell_test():
    """BUG-018 при N = 350, шаг 86400 с: все ступени отказали, отчёт — ступени 1, «только по ячейке».

    Замер (failure_census.out.txt, раздел 1): ступень 1 — линейный поиск после 4 итераций,
    невязка 6.51e-15 при допуске 5.36e-7, мера 2.60e-8 > 1e-8. Ступень 4 отказала иначе
    (лимит 40, мера 3.6e7) — в отчёт не попадает (DEBT-030).
    Ловит: класс отказа сценария воспроизведения DEBT-054 не виден из отчёта.
    """
    model, ps, dt = _bug018_model()
    assert model.cell_tol == CELL_TOL                  # фабрика включила условие по ячейке
    _, rep = model.advance(ps, dt)
    assert not rep.converged and rep.iterations == 4 and rep.exit_reason == "line_search"
    assert rep.residual_inf <= rep.residual_tol       # абсолютное условие выполнено
    assert rep.cell_measure > CELL_TOL                 # условие по ячейке — нет
```

**Раздел F — текст адаптера (шаг 4):**

```python
def test_adapter_message_cell_test_only():
    """Тот же шаг через адаптер: прежний текст и хвост — допуск, мера, выход, невыполненное условие.

    Прежний текст (до DEBT-054) — начало нового: тесты и журналы, искавшие его, совпадают.
    """
    sim, init, dt = _sim(N=350)
    with pytest.raises(HydroConvergenceError) as exc:
        sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
    msg = str(exc.value)
    assert msg.startswith("advance не сошёлся: dt = 8.640e+04 с, t = 0.0000 сут, "
                          "итераций 4, невязка 6.51e-15 (допуск ")
    for part in ("мера ячеек ", "(порог numerics.newton_cell_tol = 1e-08)",
                 "выход: линейный поиск не принял ни одной точки",
                 " — не выполнено только условие по ячейке"):
        assert part in msg
    assert msg.endswith("; числа — Ньютона ступени 1")


def _rep(res, tol=None, meas=None, reason=""):
    """Отчёт отказа с полями DEBT-054 для проверки текста."""
    return BlackOilNewtonReport(False, 3, res, residual_tol=tol, cell_measure=meas, exit_reason=reason)


_THRESHOLD = " (порог numerics.newton_cell_tol = 1e-08)"


@pytest.mark.parametrize("report, cell_tol, stage, expected", [
    # только ячейка: 1e-15 <= 1e-9, мера 3e-8 > 1e-8 (класс сценария воспроизведения)
    (_rep(1e-15, 1e-9, 3e-8, "line_search"), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", выход: линейный поиск не принял "
     "ни одной точки — не выполнено только условие по ячейке; числа — Ньютона ступени 1"),
    # только абсолютное
    (_rep(1e-3, 1e-9, 1e-9, "max_iter"), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 1.00e-09" + _THRESHOLD + ", выход: исчерпан лимит итераций"
     " — не выполнено только абсолютное условие; числа — Ньютона ступени 1"),
    # оба не выполнены; ступень 4 по памяти
    (_rep(1e-3, 1e-9, 1.0, "max_iter"), 1e-8, 4,
     " (допуск 1.00e-09), мера ячеек 1.00e+00" + _THRESHOLD + ", выход: исчерпан лимит итераций"
     " — не выполнены оба условия сходимости; числа — Ньютона ступени 4"),
    # оба выполнены: отказ не по сходимости
    (_rep(0.0, 1e-11, 0.0, "branch"), 1e-8, 1,
     " (допуск 1.00e-11), мера ячеек 0.00e+00" + _THRESHOLD + ", выход: ветвь скважины несогласована"
     " — оба условия сходимости выполнены; числа — Ньютона ступени 1"),
    # условие по ячейке выключено: только абсолютное
    (_rep(1e-3, 1e-9, None, "linear_solver"), None, 1,
     " (допуск 1.00e-09), выход: отказ линейного решателя — абсолютное условие не выполнено;"
     " числа — Ньютона ступени 1"),
    # исчерпан набор фаз: допуска нет — вывода об условиях нет
    (_rep(2.7e-4, None, 5e-3, "active_set"), 1e-8, 1,
     ", мера ячеек 5.00e-03" + _THRESHOLD + ", выход: набор фаз не установился; числа — Ньютона ступени 1"),
    # неизвестный код — как есть
    (_rep(1e-3, None, None, "new_code"), None, 1, ", выход: new_code; числа — Ньютона ступени 1"),
    # корень с S_g > 0.98 (ступень 4): условия выполнены, отказ — по границе S_g
    (_rep(1e-15, 1e-11, 1e-12, "sg_bound"), 1e-8, 4,
     " (допуск 1.00e-11), мера ячеек 1.00e-12" + _THRESHOLD + ", выход: корень с S_g > 0.98"
     " — оба условия сходимости выполнены; числа — Ньютона ступени 4"),
    # нечисловое обновление ступени 4
    (_rep(9.2e-3, 4.4e-11, 2.0, "nonfinite"), 1e-8, 4,
     " (допуск 4.40e-11), мера ячеек 2.00e+00" + _THRESHOLD + ", выход: нечисловое приближение"
     " — не выполнены оба условия сходимости; числа — Ньютона ступени 4"),
    # подставной объект тестов без полей DEBT-054 — хвоста нет, текст прежний
    (SimpleNamespace(converged=False, iterations=0, residual_inf=1.0), 1e-8, 1, ""),
    # отчёт, созданный без новых полей (как в старых тестах) — хвоста нет
    (BlackOilNewtonReport(False, 0, 1.0), 1e-8, 1, ""),
])
def test_failure_details(report, cell_tol, stage, expected):
    """Хвост текста отказа по классам: какое условие не выполнено — те же сравнения, что в Ньютоне."""
    assert _failure_details(report, cell_tol, stage) == expected
```

**Раздел G — текст `Simulator` (шаг 5):**

G1, в `tests/test_simulator.py`, класс `TestEnergySubstepsUnderRetry`, после `test_exhausted_subdivision_raises`:
```python
    def test_exhausted_subdivision_reports_last_failure(self):
        """Конец текста отказа — текст HydroConvergenceError последнего подшага (DEBT-054).

        Двойник отказывает на всех подшагах, max_retries = 2: последний — 900 с при t = 0.
        Начало текста прежнее: его цитируют README примеров 03, 05, 06, 07, 10.
        """
        sim, _, _ = _retry_run(lambda s, dt: True, max_retries=2)
        with pytest.raises(RuntimeError) as exc:
            sim.run(_initial_state())
        msg = str(exc.value)
        assert msg.startswith("HydroSolver не сошёлся при дроблении шага до dt/4 = ")
        assert msg.endswith(
            "Последний отказ гидродинамики: двойник: отказ при dt = 900 с, t = 0 с")
```
Текст двойника — `tests/_doubles.py:90-91`: `f"двойник: отказ при dt = {dt:g} с, t = {state.t:g} с"`.

G2, в `test_prototype_failure_diagnostics.py`:
```python
def test_simulator_message_ends_with_adapter_text():
    """max_retries = 0: первый же отказ — RuntimeError Simulator; конец текста — текст адаптера.

    До DEBT-054 класс отказа был виден только в цепочке traceback (__cause__).
    """
    sim, init, _ = _sim(N=350, retries=0)
    with pytest.raises(RuntimeError) as exc:
        sim.run(init)
    msg = str(exc.value)
    assert msg.startswith("HydroSolver не сошёлся при дроблении шага до dt/1 = 8.64e+04 с")
    tail = msg.split("Последний отказ гидродинамики: ", 1)[1]
    assert tail == str(exc.value.__cause__)
    assert tail.startswith("advance не сошёлся: dt = 8.640e+04 с")
    assert "не выполнено только условие по ячейке" in tail
```

### 4.2. Сводка

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| A1 `test_converged_report` | новый | Nabor_1b $N$ = 12, сошлось | допуск = формула, мера = мера теста побитово, `converged` | меру не той невязки, допуск не той формулы |
| A2 `test_cell_test_off` | новый | `cell_tol=None` | мера `None`, допуск есть | меру при выключенном условии |
| A3 `test_limit_exit` | новый | `max_iter=1` | `max_iter`, 1 итерация | путаницу лимита и линейного поиска |
| A4 `test_linear_solver_exit` | новый | решатель бросает | `linear_solver`, невязка и мера стартовой точки | отчёт не той точки |
| B1 `test_active_set_exit` | новый | `max_active_iter=1` | `active_set`, допуск `None`, 5 смен | отчёт исчерпания набора фаз без причины |
| C1–C2 | новый | ступень 4, 1e-8 и 1e-30 | `converged`; `max_iter`, 40, абсолютное выполнено | отсутствие полей ступени 4 |
| C3–C4 | новый | обрыв ступени 4 | 2 / 1 итерации, `linear_solver` / `nonfinite` | DEBT-061 (40 при досрочном выходе) |
| D1–D2 | новый | `_fallback`, подставные отчёты | `branch` только у сошедшегося Ньютона | `converged` в отчёте отказа; затирание причины отказавшего Ньютона |
| E1 `test_total_failure_carries_original_diagnostics` | новый | все ступени отказали, подставные | три поля — ступени 1 | несогласованный отчёт после DEBT-030 |
| E2 `test_real_total_failure_only_cell_test` | новый | BUG-018 $N$ = 350 | `line_search`, 4 итерации, абсолютное выполнено, мера > 1e-8 | невидимый класс сценария воспроизведения |
| F1 `test_adapter_message_cell_test_only` | новый | то же через адаптер | прежний текст — начало; хвост с классом | регрессию текста отказа |
| F2 `test_failure_details` ×11 | новый | классы, `None`, неизвестный код, подставные; все 7 переводов причин | точный текст | ошибки формулировок, перевода и случаев `None` |
| G1 | `test_simulator.py` | двойник, `max_retries=2` | конец — текст двойника | потерю текста отказа в `Simulator` |
| G2 | новый | BUG-018, `max_retries=0` | хвост = `__cause__`, класс в нём | то же на настоящем отказе |

**Итого:** 26 тестов в новом файле + 1 в `test_simulator.py` = **27**. Меток `slow` нет: фикстура `shutin` ~2 с, `drawn_down` — доли секунды, BUG-018 — ~1 с на тест. 1741 → **1768**, быстрый уровень 1470 → **1497** (на `73ef031`).

**Не покрыто тестом прототипа:** выход `sg_bound` (`_newton_switching`, `:579`, `ok = False`). Естественного сценария с двухфазной $S_g > 0.98$ в корне нет. Правка в этом месте — одно условное выражение `'converged' if ok else 'sg_bound'` рядом с прежним `ok`. Перевод кода в текст проверяет F2.

### 4.3. Неизменность поведения

- Существующие тесты — зелёные после каждого шага. Особо: `test_prototype_cell_tolerance.py` (`_cells_converged` через `_cell_measure`), `test_prototype_globalization.py`, `test_prototype_well_branch.py`, `test_prototype_open_branch_skip.py` (`_fallback`, DEBT-030), `test_prototype_phase_switching.py`, `test_prototype_stage4_memory.py` (ступень 4, память), `test_prototype_adapter.py`, `test_prototype_activation_cap.py`, `test_simulator.py` (тексты).
- Тесты прототипа (97) и регрессия: `--quick` после шага 3, полная — шаг 7. Ожидание — побитово.
- `histories.py` (шаг 7): пять сценариев побитово, новый текст отказа начинается с прежнего.
- Сверка класса в тексте с независимой пробой `failure_census.py` (шаг 7).
- Пункт «визуальная верификация» не применим: рисунков и чисел истории правка не меняет.

---

## 5. Критерии завершения

- [ ] Шаги 0–8 выполнены.
- [ ] Существующие тесты зелёные; новых 27, всего база + 27 (1768 на `73ef031`).
- [ ] Тесты прототипа зелёные (97); полная регрессия `run_regression.py` — 17/17 PASS.
- [ ] `histories.py compare` — ИТОГ OK: пять сценариев побитово, 10 отказов, новый текст начинается с прежнего.
- [ ] `failure_census.py` после правки: у всех отказов класс и выход в тексте совпадают с пробой.
- [ ] `CHANGELOG_1.0.3.md` — раздел DEBT-054 с фактическими числами.
- [ ] Import graph чистый: новых импортов в пакетах нет.
- [ ] Vault: DEBT-054 реализован, DEBT-061 закрыт поглощением, DEBT-055 и BUG-025 поправлены, заметки P4, P1, оркестратор, BUG-022 обновлены.
- [ ] Комментарий в issue #102 с результатом; issue закрывается при `/merge`.
- [ ] Производительность: время быстрого уровня в пределах ±5 % базового варианта (на каждый выход из Ньютона добавлена одна мера $O(N)$).

---

## 6. Верификация плана

**Раунд 1 — полнота.**
- Затронутые файлы и шаги:
  - `blackoil.py` — шаги 1–3;
  - `prototype_adapter.py` — шаг 4;
  - `simulator.py` — шаг 5;
  - `CHANGELOG_1.0.3.md` — шаг 6;
  - новый файл тестов — шаги 1–5;
  - `test_simulator.py` — шаг 5;
  - vault (реестр, четыре заметки, комментарий) — шаг 8.
- У каждого шага есть проверка. Зависимости линейные (0 → 1 → 2 → 3 → 4 → 5 → 7 → 8; 6 — после 3, числа после 7), циклов нет.
- Подводные камни 2.5 адресованы в шагах. Тесты остаются зелёными после каждого шага: новые тесты пишутся в том же шаге, что и код, а прежние поля отчёта не меняются.

**Раунд 2 — корректность** (сверено grep/Read на `ccc5ae3`):
- **Сигнатуры и атрибуты.** `BlackOilNewtonReport` `:44-54`; `_cells_converged` `:253`; `_cell_weights` `:249`; `_newton_fixed_active_set(…, max_iter=15, rtol=1e-8, atol_sm3s=1e-11)` `:347`; `_advance_phases(state_old, dt_s, max_active_iter=12, max_newton=15)` `:492`; `_newton_switching(state_old, dt_s, max_iter=40, …)` `:536`; `_fallback(state_old, dt_s, max_active_iter, max_newton)` `:453`; `advance` `:383`; `pack(state, gas_active=None)` `:184`; `cell_tol` — атрибут модели (`:124`).
- **Адаптер** (на `73ef031`). `m = self._model` `:151`, `if not report.converged` `:162`, текст отказа `:169-176`. `Simulator`: `:249-257`, `_failure_message` `:310-329`.
- **Аудит 1** проверил дополнительно:
  - `finite_difference_jacobian` возвращает `f`, побитово равную `residual(z)` — на этом стоит равенство мер в A4;
  - `_initial_state().t == 0.0` — текст двойника в G1 кончается на `t = 0 с`;
  - регрессия прототипа запускает `run_prototype.py` подпроцессом с `cwd=ROOT` (`run_regression.py:89-90`), поэтому в worktree проверяет код worktree;
  - базовый вариант прототипа на `73ef031`: тесты 97 passed, `--quick` 11/11 PASS (`vault/issues/debt-054/probes/audit1_regression_quick_73ef031.out.txt`).
- **Помощники тестов:**
  - `_sim(N, retries)` — `test_prototype_activation_cap.py:38`;
  - `_build(n, cell_tol)`, `_measure`, `shutin`, `CELL_TOL`, `DT`, `DT_STAGE4` — `test_prototype_cell_tolerance.py:37-69, 166`;
  - `_model`, `drawn_down` — `test_prototype_well_branch.py:69, 124`;
  - `ORIG3`, `_install_fake_reports` (ключ — ветка, граница, L2) — `test_prototype_globalization.py:181, 188`;
  - `_retry_run`, `_initial_state` — `test_simulator.py:456, 71`.
- **Числа ожиданий** — из проб на `ccc5ae3`: `test_scenarios.out.txt` (A, B, C), `failure_census*.out.txt` (E2, F1, G2). Строки F2 сверены исполнением кода `_failure_details` из шага 4 на тех же входах: `check_failure_details.out.txt` — 11 из 11 совпали. Там же полные тексты двух сценариев 1.2: допуск BUG-018 печатается как `5.35e-07`.
- **Инварианты.** Операции условия по ячейке те же, что прежде (`_cell_measure` — тело прежнего `_cells_converged`). `residual_inf` вычисляется тем же `float(nrm)`. Итерации Ньютона не меняются.

**Раунд 3 — автономность.**
- Полные пути, команды запуска с интерпретатором по абсолютному пути, проверка, откуда взят код (строки `Код:`, `Прототип:` проб), базовый вариант (1741 / 1470 / 97 / 11 из 11 на `73ef031`).
- Каждый шаг объясняет, почему так: 1.1–1.4, 2.2.
- Термины: «абсолютное условие» и «условие по ячейке» (1.1), «подмена DEBT-030», «ступень 4 по памяти» (2.2), «удержанные ячейки выше по потоку» (1.2).
