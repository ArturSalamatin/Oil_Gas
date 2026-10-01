---
tags:
  - план
  - баг
  - валидация-ввода
date: 2026-10-01
issue: BUG-017
github: 45
branch: fix/bug-017/rs0-table-range-check
status: готов к реализации
---

# BUG-017: проверка начального состояния против PVT — $R_{s,0}$ внутри таблицы, старт недонасыщенный, диагностика выхода за таблицы

**Реестр:** [[известные баги и технический долг]] → BUG-017. **Issue:** [#45](https://github.com/ArturSalamatin/Oil_Gas/issues/45). **Ветка:** `fix/bug-017/rs0-table-range-check` (от `numerical_scheme/implementation`).

## Цель

`SimulatorFactory.from_config` принимает начальное состояние, которое решатель не может корректно обработать, и молча идёт в расчёт. Исход — отказ первого шага с ложным советом «увеличьте `max_retries`» или, после вливания [[BUG-016]], **молча нефизичный** скачок давления на первом шаге. После правки фабрика:

1. **отвергает** `Rs0` вне диапазона веток PVTO-таблицы (`ValueError`) — обе границы;
2. **отвергает** пересыщенный старт $R_{s,0} > R_s^{eq}(p_0)$ (`ValueError`) — обе модели PVT;
3. **предупреждает** в журнале о выходе начального состояния за PVT- и ОФП-таблицы (готовая диагностика прототипа `pvt_range_warnings`) — табличный путь.

Расчёт не меняется: у всех штатных конфигов проверки проходят, предупреждений нет — результаты побитово прежние.

## 0. Решения пользователя

| № | Вопрос | Решение | Дата |
|---|---|---|---|
| 1 | Пересыщенный старт $R_{s,0} > R_s^{eq}(p_0)$ | **Ошибка** (`ValueError`). Спецификация уже требует однофазный старт (`json-config-schema.md:106`) | 2026-10-01 |
| 2 | $R_{s,0}$ ниже первой ветки таблицы | **Ошибка**, как и выше последней: одно правило «таблица покрывает $R_{s,0}$» | 2026-10-01 |
| 3 | `json-config-schema.md:104-106`: `Rs0` «опционален, по умолчанию $R_s^{eq}(p_0)$», а код требует `Rs0` | **Поправить схему** в этом плане (код не меняется): `Rs0` обязателен; ограничение проверяется фабрикой | 2026-10-01 |
| 4 | Подключать ли `pvt_range_warnings` прототипа | **Да, в этом плане** — на начальном состоянии табличного пути, предупреждения в журнал | 2026-10-01 |

## 1. Измерения (2026-10-01, база `cc12520` — после вливания BUG-016)

Все прогоны — в памяти (`cfg.initial_conditions.Rs0 = …`, файлы конфигов не менялись), из `numerical_solver`, `PYTHONPATH=HydroSolverPrototype/Prototype_1.0.3`.

### 1.1 Выход $R_{s,0}$ за таблицу (пример 12: ветки 0/30, $p_b(30) = 15$ МПа, $p_0 = 15.5$ МПа, $N = 50$)

Первый шаг `RadialBlackOilModel.advance(state, 3600 с)`:

| $R_{s,0}$ | до BUG-016 (`281320a`) | после BUG-016 (`cc12520`) |
|---|---|---|
| 150 | отказ | **отказ** (третья ступень тоже); `Simulator.run` → `RuntimeError … Увеличьте numerics.max_retries` |
| 40 | отказ | **сходится третьей ступенью: $p_{max}$ = 111.0 МПа**, $S_g$ = 0.030…0.066 |
| 31 | — | сходится без третьей ступени: $p_{max}$ = 20.14 МПа (+4.6 МПа к $p_0$) |

Механизм (запись реестра, п. 2–4): `BlackOilPVT` обрезает $R_s$ крайней веткой — $R_s^{sat}(p) \le 30$ при любом $p$, $B_o(p, R_{s,0}) = B_o(p, 30)$, а запас газа в ячейке считается с полным $R_{s,0}$. Логика переключения фаз видит пересыщение при любом давлении и выделяет избыток «в закрытом сосуде». Объём должен уместиться в прежний поровый: $B_o(p) + (R_{s,0}-30)\,B_g(p) = B_o(p_0) = 1.199$. При $R_{s,0} = 31$ корень $p \approx 20.4$ МПа — совпадает с измеренным 20.14 (часть массы уходит через контур). При 40 корня в пределах таблицы нет ($1.18 + 10\cdot0.004 = 1.22$), третья ступень находит «решение» с давлением 111 МПа (вне таблиц, свойства с краёв). При 150 решения нет вовсе.

**Вывод:** после BUG-016 баг частично перешёл из «падает с ложным советом» в «молча считает чушь». Проверка на входе обязательна.

### 1.2 Пересыщенный старт внутри таблицы и у Стендинга (закрывает «Не проверено» записи реестра)

| PVT | $R_{s,0}$ | $p_0$, МПа | $p_b(R_{s,0})$, МПа | первый шаг 3600 с |
|---|---|---|---|---|
| таблица примера 14 (рабочая копия, 0…180) | 150 | 22.0 | 23.723 | сходится (третья ступень): $p_{max}$ = 23.714 МПа, $S_g$ до 0.249 |
| то же | 150 | 23.0 | 23.723 | сходится: $p_{max}$ = 23.717 МПа |
| Стендинг (пример 03) | 50 | 9.0 | 9.426 | сходится: $p_{max}$ = 9.417 МПа, $S_g$ до 0.074 |
| Стендинг | 80 | 10.0 | 14.008 | сходится: **$p_{max}$ = 13.780 МПа** (+3.8 МПа за час), $S_g$ на контуре 0.123 |

Пересыщенный старт не падает, а **молча** даёт скачок давления почти до $p_b(R_{s,0})$ за первый шаг — решатель «уравновешивает» неравновесное начальное состояние. Начальное состояние в фабрике всегда однофазное ($S_g = 0$, `regime = 2`, `factory.py:74-81`), инициализации со свободным газом нет; приток с контура несёт тот же пересыщенный $R_{s,0}$ (`factory.py:201`). Отсюда решение 1.

### 1.3 Все конфиги проекта — обе проверки проходят, предупреждений нет

`examples/*/config.json` (17) и `configs/**/*.json` (3), рабочая копия 2026-10-01:

| группа | $R_{s,0}$ | $p_0$, МПа | $R_s^{eq}(p_0)$ | диапазон таблицы |
|---|---|---|---|---|
| Стендинг: 01, 02 | 0 | 20 | 122.3 | — |
| Стендинг: 03, 05, `baseline`, `val001` | 50 | 20 | 122.3 | — |
| таблица: 04, 04a, 06–10, `table_pvt` | 30 | 20 | 30 | [0, 30] |
| таблица: 11 | 30 | 15.05 | 30 | [0, 30] |
| таблица: 12, 13a, 13b, 15 | 30 | 15.5 | 30 | [0, 30] |
| таблица: 14 | 150 | 24.5 | 155.9 | [0, 180] |

Граничные: у табличных примеров с $R_{s,0} = 30$ — ровно последняя ветка и $R_s^{eq}(p_0) = 30$ ровно (обрезка) — обе проверки должны пропускать равенство. Пример 14: и версия `HEAD` (ветки 0/150/180, $p_b(150) = 24$ МПа), и незакоммиченная рабочая копия (31 ветка, $p_b(150) = 23.72$ МПа) проходят.

`pvt_range_warnings` на начальном состоянии всех 14 табличных конфигов — **пустой список**. Контроль: `configs/table_pvt` с $p_0 = 32$ МПа — два предупреждения (`GAS_PVT pressure above table: max P=320 bar, table max=300 bar…`, `OIL_PVT branch pressure above supplied range by up to 20 bar…`).

### 1.4 Тесты — кто вызывает `from_config` с нестандартным начальным состоянием

Проба `vault/issues/bug-017/probes/check_ic_plugin.py` — pytest-плагин: оборачивает `SimulatorFactory.from_config`, вычисляет обе проверки и пишет нарушения в `check_ic_violations.txt`, исходники не меняет. Полный прогон `tests/` (рабочая копия 2026-10-01, 1035 тестов — на один больше HEAD из-за незакоммиченной правки `test_examples.py` параллельной сессии, 530 с): **нарушений нет** — ни один вызов `from_config` в тестах не нарушил бы ни одну из проверок (файл нарушений не создан). 8 падений того прогона — тесты примера 14 (`test_examples.py::TestHighGorCooling` ×4, `test_energy_matrix_examples.py[14_high_gor_cooling]`, `test_prototype_globalization.py` ×3): вызваны незакоммиченными правками конфига и таблицы примера 14 в рабочей копии, к BUG-017 не относятся (плагин результатов не меняет).

Статически: `p0`/`Rs0` в коде меняют только `tests/test_config.py:366, 378` (отрицательные значения — отказ в `_validate` раньше фабрики). `_create_pvt` напрямую зовут `tests/test_examples.py:817`, `examples/pvt_plot.py:92`, пробы `examples/measure_spurious_degas_heat.py:31`, `examples/measure_negative_sg_scale.py:48` — проверка 1 (внутри `_create_pvt`) сработает и там; все они берут штатные конфиги — проходят.

### 1.5 Код шагов 2–3 проверен в памяти

Функции `_check_rs0_in_table` и `_check_undersaturated_start` из шагов 2–3 (копия текста плана) вызваны на объектах `_create_pvt` без правки файлов. Исходы совпадают с ожиданиями тестов шага 1: `Rs0` = 150 / 40 на ветках 0/30 → «вне диапазона таблицы … от 0 до 30» (без «пересыщ»); ветки 5/30, `Rs0 = 0` → «… от 5 до 30»; таблица `Rs0 = 20`, $p_0$ = 10 МПа → «пересыщено газом … Rs_eq(p0) = 15 … p_b(Rs0) = 11.6667 МПа»; Стендинг `Rs0 = 80`, $p_0$ = 10 МПа → «пересыщено … Rs_eq(p0) = 53.6219 … p_b = 14.007»; проходят: штатный табличный, $p_0 = p_b$, $p_0 = p_b - 1$ Па (таблица и Стендинг), `Rs0 = 0` при $p_0$ = 3 МПа (таблица), `Rs0 = 0` (Стендинг).

## 2. Анализ

### 2.1 Воспроизведение

Сейчас теста нет. Команда (PowerShell, из `numerical_solver`):

```powershell
$env:PYTHONPATH = "HydroSolverPrototype/Prototype_1.0.3"
.venv\Scripts\python -c "from gpn_multiphase_solver.io.config import load_config; from gpn_multiphase_solver.factory import SimulatorFactory; c=load_config('examples/12_large_drainage_radius/config.json'); c.initial_conditions.Rs0=150.0; s,st=SimulatorFactory.from_config(c); s.run(st)"
```

Сейчас: `RuntimeError: HydroSolver не сошёлся после 512 подшагов …`. После правки: `ValueError: Rs0 = 150 м³ст/м³ст вне диапазона таблицы oil_pvt.csv …` из `from_config` (до расчёта).

Тесты-воспроизводители — шаг 1 (красные до шагов 2–4).

### 2.2 Цепочка

1. **Вход.** `io/config.py:271-272` (`_validate`) проверяет только $R_{s,0} \ge 0$; таблицу `_validate` не читает (CSV читаются в фабрике).
2. **PVT.** `factory.py:107-123` строит `BlackOilPVT` без сверки с `Rs0`. `BlackOilPVT` (`HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/pvt.py:32-35, 52`) обрезает $R_s$ крайними ветками.
3. **Начальное состояние.** `factory.py:74-81`: $S_g = 0$, `regime = 2` при любом соотношении $p_0$ и $p_b(R_{s,0})$.
4. **Решатель.** `blackoil.py:124` — запас газа с полным $R_s$; `blackoil.py:272` — активация при $R_s > R_s^{sat}(p) + 10^{-5}$; `blackoil.py:277-279` — начальное $S_g$ «закрытого сосуда».
5. **Проявление.** Отказ (`prototype_adapter.py:137-143`, ложный совет) или молча нефизичный скачок давления (§1.1, §1.2).

### 2.3 Целевое состояние

- `from_config` бросает `ValueError` с причиной и способом исправления: (а) `Rs0` вне `[rs_values[0], rs_values[-1]]` табличной PVT; (б) $R_{s,0} > R_s^{eq}(p_0) + 10^{-5}$ для обеих моделей.
- Порядок: (а) раньше (б) — при выходе за таблицу $p_b(R_{s,0})$ обрезано (у таблицы примера 12 $p_b(150) = 15$ МПа $< p_0$), и сообщение (б) было бы противоречивым.
- Табличный путь: предупреждения `pvt_range_warnings` для начального состояния — в `user_log.warning`.
- Все штатные конфиги: без ошибок и предупреждений, результаты побитово прежние (код расчёта не трогается).

### 2.4 Варианты

| | Суть | Плюсы | Минусы |
|---|---|---|---|
| **A** | Проверка 1 (диапазон) — в табличной ветке `_create_pvt`, где локально доступен `proto_pvt.rs_values` | без нового API и приватных цепочек; срабатывает и при прямых вызовах `_create_pvt` (тесты, `pvt_plot.py`) | `_create_pvt` получает обязанность проверки (уже бросает `ValueError` для неизвестной модели) |
| B | Проверка 1 в `from_config` через новое публичное свойство диапазона у `PrototypePVTAdapter`/`TableFullPVT` | проверки в одном месте | новый API ради одной проверки; правка двух классов и их ABC-контракта |
| **C** | Проверка 2 как $R_{s,0} \le R_s^{eq}(p_0) + 10^{-5}$ в `from_config` после `_create_pvt` | ровно критерий активации решателя (`blackoil.py:272`, `rs_switch_tol = 1e-5`); дегазированная нефть ($R_{s,0} = 0$) при $p_0 <$ табличного $p_b(0)$ допустима | — |
| D | Проверка 2 как $p_0 \ge p_b(R_{s,0})$ (формулировка issue) | буквально как в спецификации | ложная ошибка для $R_{s,0} = 0$ при $p_0 < p_b(0)$ таблицы (демо-таблица: $p_b(0) = 5$ МПа, хотя $R_s^{sat}(p) = 0 = R_{s,0}$ и пересыщения нет); на обрезанном $p_b$ таблицы молчит при $R_{s,0} > R_s^{max}$ |
| **E** | Диагностика — в `_create_prototype_hydro` сразу после создания модели, только `isinstance(pvt, TableFullPVT)` | модель локальна; состояние строится из `ic` | английский текст прототипа — с русским префиксом |
| F | Диагностика в адаптере (`PrototypeHydroAdapter.solve`) на первом шаге | ближе к месту расчёта | адаптер не знает «первый ли шаг»; лишний флаг состояния |

### 2.5 Выбор

**A + C + E.** A — проще B и без нового API; C — точнее D и совпадает с решателем; E — по решению 4, без флагов в адаптере. Отклонение от анализа issue #45: там вариант 2 сформулирован как $p_0 \ge p_b(R_{s,0})$ (D) и помечен «в одиночку наш случай не ловит». Формулировка C ловит и выход выше таблицы ($R_s^{eq} \le R_s^{max}$ при любом $p_0$), но проверка A всё равно нужна: (1) нижняя граница (решение 2); (2) понятное сообщение «таблица не покрывает `Rs0`» вместо «пересыщено» с обрезанным $p_b$.

**Допуск C = $10^{-5}$ м³ст/м³ст** — `rs_switch_tol` решателя (`blackoil.py:32`, `RadialBlackOilModel` создаётся фабрикой без этого аргумента, `factory.py:197-205` — значит, всегда по умолчанию). Проверка отвергает ровно те начальные состояния, которые решатель на первом шаге объявил бы пересыщенными. Округление ввода: Стендинг, $R_{s,0} = 50$, $dR_s/dp \approx 6.4\cdot10^{-6}$ м³ст/м³ст на Па — $p_0$ на 1 Па ниже $p_b$ даёт избыток $6\cdot10^{-6} < 10^{-5}$, проходит.

### 2.6 Подводные камни

| Пункт | Оценка | Комментарий |
|---|---|---|
| Побочные эффекты | ✅ | `_create_pvt` зовут `from_config`, `tests/test_examples.py:817`, `examples/pvt_plot.py:92`, две пробы — все со штатными конфигами (§1.3) |
| Граничные: $R_{s,0} = R_s^{max}$, $R_s^{eq}(p_0) = R_s^{max}$ | ✅ | нестрогие сравнения; тест `test_rs0_on_last_branch_passes` |
| Граничные: $p_0 = p_b(R_{s,0})$ и на 1 Па ниже | ✅ | допуск $10^{-5}$; тесты `test_p0_at_bubble_point_passes`, `test_p0_1pa_below_pb_passes` |
| Граничные: $R_{s,0} = 0$ | ✅ | Стендинг $p_b(0) = -0.176$ МПа, $R_s^{eq} > 0$; таблица — $R_s^{eq}(p_0) \ge 0$; тест `test_dead_oil_below_table_pb0_passes` |
| Граничные: таблица из одной ветки | ✅ | `BlackOilPVT` с одной веткой уже неработоспособен (`_oil_prop`: `j` clip к `len-2 = -1`) — вне задачи, проверка диапазона с одной веткой даёт `rs_lo == rs_hi` |
| Производительность | ✅ | одна проверка при создании, не на шаге |
| Обратная совместимость | ✅ | все конфиги проходят (§1.3); прогон тестов с плагином — §1.4 |
| Порядок вызовов | ✅ | A внутри `_create_pvt` (шаг 2 `from_config`) раньше C (сразу после) раньше E (шаг 4 `from_config`); в E модель уже создана |
| Состояние при ошибке | ✅ | `ValueError` до создания `Simulator` — частично созданных объектов наружу нет; `setup_logging` уже вызван — безвредно |
| Численная устойчивость | ✅ | сравнения скаляров, без вычитаний близких величин |
| Связь с задачами | ⚠️ | [[DEBT-008]] правит `_validate` (другие поля) — конфликта нет; [[BUG-016]] влит — §1.1 измерен после него. Параллельные сессии правят рабочее дерево основного каталога (пример 14, `test_examples.py`, vault) — работать в worktree (§6) |
| Import-цепочки | ✅ | `radial_blackoil.state`, `radial_blackoil.diagnostics` — импорт внутри функции, как `radial_blackoil.pvt` в `_create_pvt`; `user_log` — из `.log` (уже импортируется `setup_logging`) |
| Журнал в тестах | ✅ | логгер `gpn_multiphase_solver` не отключает `propagate` (`log.py:16-28`) — `caplog` его видит |
| Соответствие формулам | ✅ | физика не меняется; критерий C = критерий активации `blackoil.py:272` |

### 2.7 Новые проблемы

1. **Выход состояния за PVT/ОФП-таблицы в ходе расчёта не диагностируется** — после этого плана `pvt_range_warnings` вызывается только на начальном состоянии. Пример: README 04 приводит прогоны с $p_{wf}$ = 2 / 1 / 0.5 МПа на газовой таблице от 5 МПа — $B_g$ ниже 5 МПа постоянен (0.020), $R_s^{sat} = 0$, молча. Собственный цикл прототипа (`radial_blackoil/simulation.py:95-97`) зовёт диагностику на каждом принятом шаге. Не блокирует; зарегистрировано как [[DEBT-027]] (2026-10-01).
2. Текст ошибки адаптера (`prototype_adapter.py:137-143`) по-прежнему советует `max_retries` при любом отказе — после этого плана для BUG-017 он недостижим; отдельной записи не требует (вариант 4 issue #45 отвергнут).

## 3. Шаги

### Шаг 0: Подготовка

**Предусловия:**
1. Этот план закоммичен в `numerical_scheme/implementation` (worktree читает закоммиченную версию). Проверка: `git status --short -- "vault/plans/bug-017 rs0-table-range-check.md"` — пусто.
2. С `cc12520` не менялись затронутые места: `git diff --stat cc12520 numerical_scheme/implementation -- numerical_solver/gpn_multiphase_solver/factory.py numerical_solver/tests/test_factory_prototype.py numerical_solver/tests/test_factory_standing_hydro.py` — пусто; иначе сверить блоки «До» шагов 2–4.
3. **База зелёная.** На `cc12520` красные 7 тестов примера 14 (см. Baseline ниже) — внесены коммитами `bc91297` «fix example 14 config» и `cc12520` «fix» (конфиг и таблицы примера 14 изменены, тесты — нет); в рабочей копии основного каталога идёт незакоммиченная доработка примера 14 (`oil_pvt.csv`, `config.json`, `test_examples.py`). К BUG-017 не относится, но по CLAUDE.md регрессии блокируют работу: старт — после того, как пример 14 доведён и закоммичен, а прогон базы даёт 0 failed. Старт на красной базе — только с явного согласия пользователя; тогда критерий шага 6 — те же падения, ни одного нового.

```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
git worktree add -b fix/bug-017/rs0-table-range-check .worktrees/bug-017 numerical_scheme/implementation
cd .worktrees\bug-017\numerical_solver
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider
```

Baseline на `cc12520` (2026-10-01, временный отсоединённый worktree, 465 с): **1034 теста — 1027 passed, 7 failed, 1 warning**. Падения — только пример 14: `test_energy_matrix_examples.py::test_matrix_matches_reference[14_high_gor_cooling]`, `test_examples.py::TestHighGorCooling::{test_wellbore_cools_by_5_to_10_K, test_well_saturation_matches_relperm, test_main_disables_saturation_overlay}`, `test_prototype_globalization.py::TestFirstStepConverges::{test_example14_fine_grid_first_step[100-…], [150-…], test_sg_step_limited_in_third_stage}` (предусловие 3). На зелёной базе ожидается 1034 passed — перемерить. venv — основного каталога (в worktree `.venv` нет). pytest из `<worktree>\numerical_solver` берёт код worktree (`tests/conftest.py` подключает прототип worktree). Скрипты вне pytest — только с `$env:PYTHONPATH` на worktree (память «Worktree и PYTHONPATH»).

Воспроизвести баг в worktree (команда §2.1 с `$env:PYTHONPATH = "HydroSolverPrototype/Prototype_1.0.3;" + (Get-Location).Path`) — `RuntimeError`.

**Оценка:** ~15 мин (прогон ~8 мин).

### Шаг 1: Тесты-воспроизводители (красные)

**Цель:** зафиксировать целевое поведение до правки.
**Файлы:** `numerical_solver/tests/test_factory_prototype.py` (табличный путь), `numerical_solver/tests/test_factory_standing_hydro.py` (Стендинг).

**Что сделать:**

1. `numerical_solver/tests/test_factory_prototype.py`: в шапку модуля (докстринг, строки 3-8) добавить пункт `- Начальное состояние против таблиц: Rs0 в диапазоне, недонасыщенный старт, предупреждения (BUG-017)`. Импорты: добавить `import logging`, `import shutil` к стандартным (после `from pathlib import Path`).
2. Там же — в конец файла (после `TestConfigErrors`, строка ~275) новый раздел:

```python
# ═══════════════════════════════════════════════════════════
# F. Начальное состояние против PVT-таблиц (BUG-017)
# ═══════════════════════════════════════════════════════════

def _table_config_with_oil_csv(tmp_path, oil_csv_text):
    """TABLE_CONFIG с подменённой oil_pvt.csv: копия CSV в tmp_path, config_dir → tmp_path."""
    for name in ("gas_pvt.csv", "relperm.csv"):
        shutil.copy(TABLE_CONFIG.parent / name, tmp_path / name)
    (tmp_path / "oil_pvt.csv").write_text(oil_csv_text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = tmp_path
    return config


class TestInitialStateVsTable:
    """Фабрика отвергает начальное состояние, которое таблица не описывает (BUG-017).

    Таблица configs/table_pvt: ветки Rs = 0 (p_b = 5 МПа) и 30 (p_b = 15 МПа),
    газ 5…30 МПа. BlackOilPVT не экстраполирует: Rs вне веток обрезается,
    а запас газа считается с полным Rs0 — решатель видит пересыщение при
    любом давлении (отказ или скачок давления до 111 МПа при Rs0 = 40).
    """

    def test_rs0_above_last_branch_raises(self):
        """Rs0 = 150 > 30: ошибка про диапазон таблицы, а не про пересыщение.

        Проверка диапазона идёт раньше проверки пересыщения: p_b(150) обрезан
        до 15 МПа < p0, и сообщение о пересыщении было бы противоречивым.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 150.0
        with pytest.raises(ValueError, match="вне диапазона таблицы") as exc:
            SimulatorFactory.from_config(config)
        assert "пересыщ" not in str(exc.value)
        assert "Rs0 = 150" in str(exc.value)

    def test_rs0_below_guard_threshold_raises(self):
        """Rs0 = 40: ниже порога 1.5·Rs_max = 45 пробного вектора Ньютона.

        До правки (после BUG-016) первый шаг молча «сходился» с давлением
        111 МПа. Ловит проверку, ограниченную порогом решателя.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 40.0
        with pytest.raises(ValueError, match="вне диапазона таблицы"):
            SimulatorFactory.from_config(config)

    def test_rs0_below_first_branch_raises(self, tmp_path):
        """Таблица с ветками 5 и 30, Rs0 = 0 < 5: ошибка (решение 2 плана).

        Ниже первой ветки нефть молча не разгазируется никогда
        (R_s^sat(p) >= 5 > Rs0), а B_o, μ_o берутся с ветки 5.
        """
        config = _table_config_with_oil_csv(tmp_path, (
            "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
            "5.0,6000000,1.07,0.0028\n"
            "5.0,30000000,1.06,0.0030\n"
            "30.0,15000000,1.20,0.0015\n"
            "30.0,30000000,1.18,0.0016\n"))
        config.initial_conditions.Rs0 = 0.0
        with pytest.raises(ValueError, match="вне диапазона таблицы"):
            SimulatorFactory.from_config(config)

    def test_rs0_on_last_branch_passes(self):
        """Rs0 = 30 ровно на последней ветке, p0 = 20 МПа > p_b = 15 МПа — допустимо.

        Граница включается: R_s^eq(p0) = 30 ровно (обрезка), Rs0 = 30.
        Так стоят 13 из 14 табличных примеров.
        """
        config = load_config(TABLE_CONFIG)
        assert config.initial_conditions.Rs0 == 30.0
        SimulatorFactory.from_config(config)   # не бросает

    def test_supersaturated_start_raises(self):
        """Rs0 = 20 внутри таблицы, p0 = 10 МПа: R_s^eq(10 МПа) = 15 < 20 — ошибка.

        p_b(20) = 11.67 МПа > p0. Решатель стартует только из однофазного
        состояния; без проверки давление на первом шаге скачком росло бы к p_b.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 20.0
        config.initial_conditions.p0 = 10e6
        with pytest.raises(ValueError, match="пересыщено") as exc:
            SimulatorFactory.from_config(config)
        assert "11.6667" in str(exc.value)   # p_b(20) = 5 + 20/30·10 МПа

    def test_p0_at_bubble_point_passes(self):
        """p0 = p_b(30) = 15 МПа ровно: R_s^eq(p0) = Rs0 — допустимо (как пример 11, p0 = 15.05)."""
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 15e6
        SimulatorFactory.from_config(config)

    def test_p0_1pa_below_pb_passes(self):
        """p0 на 1 Па ниже p_b(30): избыток Rs 3e-6 < допуска 1e-5 — округление ввода не ошибка."""
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 15e6 - 1.0
        SimulatorFactory.from_config(config)

    def test_dead_oil_below_table_pb0_passes(self):
        """Rs0 = 0, p0 = 3 МПа ниже табличного p_b(0) = 5 МПа — допустимо.

        R_s^eq(3 МПа) = 0 = Rs0: пересыщения нет, решатель газ не включит.
        Ловит переход на формулировку p0 >= p_b(Rs0) — она дала бы ложную ошибку.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 0.0
        config.initial_conditions.p0 = 3e6
        SimulatorFactory.from_config(config)


class TestInitialRangeWarnings:
    """Предупреждения pvt_range_warnings прототипа для начального состояния (BUG-017)."""

    def test_p0_above_tables_warns(self, caplog):
        """p0 = 32 МПа выше газовой таблицы и веток нефти (до 30 МПа): два предупреждения.

        Расчёт допустим (Rs0 = 30 = R_s^eq), но B_g и B_o молча берутся с краёв
        таблиц — пользователь должен это видеть.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 32e6
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            SimulatorFactory.from_config(config)
        text = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno == logging.WARNING)
        assert "GAS_PVT pressure above table" in text
        assert "OIL_PVT branch pressure above supplied range" in text

    def test_in_range_no_warnings(self, caplog):
        """Штатный табличный конфиг: начальное состояние внутри всех таблиц — предупреждений нет."""
        config = load_config(TABLE_CONFIG)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            SimulatorFactory.from_config(config)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
```

3. `numerical_solver/tests/test_factory_standing_hydro.py`: в конец файла:

```python
# ═══════════════════════════════════════════════════════════
# Начальное состояние против корреляции (BUG-017)
# ═══════════════════════════════════════════════════════════

class TestStandingInitialState:
    """Пересыщенный старт отвергается и для Стендинга; без таблиц — без предупреждений."""

    def test_supersaturated_start_raises(self):
        """Rs0 = 80, p0 = 10 МПа < p_b(80) = 14.0 МПа — ошибка.

        Без проверки первый шаг молча поднимал давление до 13.78 МПа за час
        (замер плана BUG-017, §1.2).
        """
        config = load_config(BASELINE)
        config.initial_conditions.Rs0 = 80.0
        config.initial_conditions.p0 = 10e6
        with pytest.raises(ValueError, match="пересыщено"):
            SimulatorFactory.from_config(config)

    def test_p0_1pa_below_pb_passes(self):
        """p0 = p_b(50) − 1 Па: избыток ~6e-6 < 1e-5 — допустимо (округление ввода)."""
        config = load_config(BASELINE)
        simulator, _ = SimulatorFactory.from_config(config)
        pb = float(simulator._pvt.pb(np.array([50.0]))[0])
        config.initial_conditions.p0 = pb - 1.0
        SimulatorFactory.from_config(config)

    def test_dead_oil_passes(self):
        """Rs0 = 0: p_b(0) = −0.176 МПа < 0 — допустимо при любом p0 (примеры 01, 02)."""
        config = load_config(BASELINE)
        config.initial_conditions.Rs0 = 0.0
        SimulatorFactory.from_config(config)

    def test_no_range_warnings(self, caplog):
        """Путь Стендинга не зовёт pvt_range_warnings (у адаптера нет газовой таблицы gp)."""
        config = load_config(BASELINE)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            SimulatorFactory.from_config(config)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
```

Импорт `import logging` — в начало `test_factory_standing_hydro.py` (после `from pathlib import Path`). `BASELINE`, `np`, `pytest`, `load_config`, `SimulatorFactory` там уже импортированы (строки 8-23).

**Проверка после шага:**
```powershell
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/test_factory_prototype.py tests/test_factory_standing_hydro.py -q -p no:cacheprovider -k "InitialState or InitialRange or StandingInitial"
```
Ожидание до правки — **красные 6**: `test_rs0_above_last_branch_raises`, `test_rs0_below_guard_threshold_raises`, `test_rs0_below_first_branch_raises`, `test_supersaturated_start_raises` (оба файла), `test_p0_above_tables_warns`; **зелёные 8** — проверки «проходит» и «нет предупреждений» (они защищают от ложных срабатываний будущей правки).

**Оценка:** ~170 строк, 30 мин.

### Шаг 2: Проверка диапазона таблицы (вариант A)

**Цель:** `Rs0` вне `[rs_values[0], rs_values[-1]]` → `ValueError`.
**Файл:** `numerical_solver/gpn_multiphase_solver/factory.py`

**Контекст:** табличная ветка `_create_pvt` (строки 107-123) строит `BlackOilPVT` — его `rs_values` (отсортированные уникальные $R_s$ веток, `pvt.py:12, 24`) доступны локально. `ic` уже определён в начале функции (строка 92).

**Изменения** (`_create_pvt`, строки ~112-115):

До:
```python
        from radial_blackoil.pvt import BlackOilPVT
        proto_pvt = BlackOilPVT(oil_rows, gas_rows)

        proto_adapter = PrototypePVTAdapter(proto_pvt, pc.rho_o_std, pc.rho_g_std)
```
После:
```python
        from radial_blackoil.pvt import BlackOilPVT
        proto_pvt = BlackOilPVT(oil_rows, gas_rows)

        # BUG-017: таблица обязана покрывать Rs0. BlackOilPVT не экстраполирует:
        # B_o, μ_o берутся с крайней ветки, R_s^sat(p) и p_b(R_s) обрезаются, а
        # запас газа в ячейке считается с полным Rs0. Выше последней ветки нефть
        # «пересыщена» при любом давлении — отказ первого шага или нефизичный
        # скачок давления (111 МПа при Rs0 = 40 на ветках 0/30); ниже первой —
        # молча не разгазируется. Проверка — до проверки пересыщения в
        # from_config: там p_b(Rs0) обрезан и сообщение было бы ложным.
        _check_rs0_in_table(ic.Rs0, proto_pvt.rs_values, pc.oil_pvt_file)

        proto_adapter = PrototypePVTAdapter(proto_pvt, pc.rho_o_std, pc.rho_g_std)
```

Новая функция — в раздел помощников, сразу после `_create_pvt` (перед `def _create_relperm`, строка ~129):

```python
def _check_rs0_in_table(Rs0: float, rs_values, oil_pvt_file: str) -> None:
    """Rs0 внутри диапазона веток PVTO-таблицы, иначе ValueError (BUG-017)."""
    rs_lo, rs_hi = float(rs_values[0]), float(rs_values[-1])
    # Границы включаются: Rs0 ровно на крайней ветке — штатный случай
    # (Rs0 = 30 на ветках 0/30 у 13 табличных примеров).
    if not rs_lo <= Rs0 <= rs_hi:
        raise ValueError(
            f"Rs0 = {Rs0:g} м³ст/м³ст вне диапазона таблицы {oil_pvt_file}: "
            f"ветки R_s от {rs_lo:g} до {rs_hi:g} м³ст/м³ст. Таблица не "
            f"экстраполируется — добавьте ветки, покрывающие Rs0, или задайте "
            f"Rs0 в этих пределах.")
```

**Проверка после шага:** тесты шага 1 — `test_rs0_above_last_branch_raises`, `test_rs0_below_guard_threshold_raises`, `test_rs0_below_first_branch_raises` зелёные; `test_supersaturated_start_raises` (оба), `test_p0_above_tables_warns` — ещё красные. Регрессия (проверка 1 стоит в `_create_pvt`, который `test_examples.py:817` зовёт для всех табличных примеров): `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/test_factory_prototype.py tests/test_examples.py -q -p no:cacheprovider -m "not slow"` (маркер `slow` объявлен в `numerical_solver/pyproject.toml:29-31`).

**Зависимости:** шаг 1. **Оценка:** ~20 строк, 10 мин.

### Шаг 3: Проверка недонасыщенного старта (вариант C)

**Цель:** $R_{s,0} > R_s^{eq}(p_0) + 10^{-5}$ → `ValueError` для обеих моделей PVT.
**Файл:** `numerical_solver/gpn_multiphase_solver/factory.py`

**Контекст:** `pvt` — `FullPVT` с методами `Rs_eq(p)` и `pb(Rs)` (`pvt/base.py:39, 64`; массивы на входе и выходе). Решатель включает газ в ячейке при $R_s > R_s^{sat}(p) + $ `rs_switch_tol` (`blackoil.py:272`, `rs_switch_tol = 1e-5` по умолчанию, `blackoil.py:32`; фабрика его не задаёт, `factory.py:197-205`).

**Изменения:**

(а) `from_config`, строки 52-53:

До:
```python
        # 2. PVT (FullPVT — гидро + тепловые)
        pvt = _create_pvt(config)
```
После:
```python
        # 2. PVT (FullPVT — гидро + тепловые)
        pvt = _create_pvt(config)
        _check_undersaturated_start(config.initial_conditions, pvt)
```

(б) Константа и функция — сразу после `_check_rs0_in_table` (шаг 2):

```python
# Допуск пересыщения на старте, м³ст/м³ст, — rs_switch_tol решателя
# (RadialBlackOilModel, blackoil.py:32; фабрика его не меняет): проверка
# отвергает ровно те состояния, которые решатель на первом шаге объявил бы
# пересыщенными. Округление ввода не мешает: p0 на 1 Па ниже p_b даёт избыток
# ~6e-6 (Стендинг, Rs0 = 50) и 3e-6 (таблица 0/30).
_RS0_SUPERSAT_TOL = 1e-5


def _check_undersaturated_start(ic, pvt) -> None:
    """Начальное состояние недонасыщенное: Rs0 <= Rs_eq(p0), иначе ValueError (BUG-017)."""
    # Начальное состояние всегда однофазное (S_g = 0, шаг 8 from_config) —
    # инициализации со свободным газом нет. При Rs0 > Rs_eq(p0) решатель на
    # первом шаге выделяет избыток «в закрытом сосуде», и давление молча
    # скачет почти до p_b(Rs0) (Стендинг, Rs0 = 80, p0 = 10 МПа: 13.78 МПа
    # за час). Критерий через Rs_eq(p0), а не p0 >= p_b(Rs0): у дегазированной
    # нефти табличное p_b(0) условно (5 МПа в демо-таблице), а Rs_eq(p0) = 0 =
    # Rs0 при любом p0 ниже — пересыщения нет.
    Rs_eq = float(pvt.Rs_eq(np.array([ic.p0]))[0])
    if ic.Rs0 > Rs_eq + _RS0_SUPERSAT_TOL:
        pb = float(pvt.pb(np.array([ic.Rs0]))[0])
        raise ValueError(
            f"Начальное состояние пересыщено газом: Rs0 = {ic.Rs0:g} м³ст/м³ст "
            f"больше равновесного Rs_eq(p0) = {Rs_eq:.6g} при p0 = "
            f"{ic.p0 / 1e6:.6g} МПа (давление насыщения p_b(Rs0) = "
            f"{pb / 1e6:.6g} МПа). Решатель стартует только из однофазного "
            f"состояния (S_g = 0): задайте p0 >= p_b(Rs0) или уменьшите Rs0.")
```

Формат `{pb / 1e6:.6g}` при $p_b(20) = 11.6667$ МПа печатает `11.6667` — на это опирается `test_supersaturated_start_raises` (табличный).

**Проверка после шага:** все 14 тестов шага 1, кроме `test_p0_above_tables_warns`, зелёные. Регрессия: `pytest tests/test_factory_prototype.py tests/test_factory_standing_hydro.py tests/test_config.py -q -p no:cacheprovider`.

**Зависимости:** шаг 2 (порядок проверок). **Оценка:** ~30 строк, 15 мин.

### Шаг 4: Предупреждения о выходе начального состояния за таблицы (вариант E)

**Цель:** табличный путь — `pvt_range_warnings` прототипа для начального состояния в `user_log.warning`.
**Файл:** `numerical_solver/gpn_multiphase_solver/factory.py`

**Контекст:** `radial_blackoil/diagnostics.py:22-53` — `pvt_range_warnings(model, state)` возвращает список строк (английский текст прототипа): давление вне газовой таблицы, `Rs` вне веток, давление выше последней строки ветки, насыщенная кривая (только для ячеек с газом), `S_g` вне таблицы ОФП. Использует `model.pvt.gp`, `rs_values`, `pb`, `max_pressure_of_rs` и `model.relperm.sg` — у `HydroPVTtoBlackOilAdapter` (Стендинг) `gp` и `max_pressure_of_rs` нет, поэтому только `TableFullPVT`. ОФП Кори табулируется фабрикой в `TabulatedRelPerm` (`factory.py:225-238`) — `sg` есть на обоих путях ОФП. `BlackOilState` — dataclass `radial_blackoil/state.py:5-9` (`pressure_bar`, `rs_sm3_sm3`, `sg`, `gas_active`).

**Изменения:**

(а) Импорт, `factory.py:27`:

До:
```python
from .log import setup_logging
```
После:
```python
from .log import setup_logging, user_log
```

(б) `_create_prototype_hydro`, после создания `model` (строки ~197-207):

До:
```python
        linear_solver=nc.linear_solver,
    )

    # our_pvt: HydroPVT для PrototypeHydroAdapter (пересчёт потоков)
```
После:
```python
        linear_solver=nc.linear_solver,
    )

    # Выход начального состояния за PVT- и ОФП-таблицы (BUG-017): прототип
    # берёт свойства с краёв таблиц без экстраполяции и молча. Только
    # табличная PVT: у HydroPVTtoBlackOilAdapter (Стендинг) нет газовой
    # таблицы gp — pvt_range_warnings упал бы AttributeError.
    if isinstance(pvt, TableFullPVT):
        _warn_initial_table_range(model, ic)

    # our_pvt: HydroPVT для PrototypeHydroAdapter (пересчёт потоков)
```

(в) Функция — после `_check_undersaturated_start` (шаг 3):

```python
def _warn_initial_table_range(model, ic) -> None:
    """Предупреждения pvt_range_warnings прототипа для начального состояния (BUG-017)."""
    from radial_blackoil.state import BlackOilState
    from radial_blackoil.diagnostics import pvt_range_warnings

    # Начальное состояние однородно (p0, Rs0, S_g = 0, газ неактивен), а
    # pvt_range_warnings смотрит только min/max — одной ячейки достаточно.
    state = BlackOilState(
        pressure_bar=np.array([ic.p0 / BAR_TO_PA]),
        rs_sm3_sm3=np.array([float(ic.Rs0)]),
        sg=np.zeros(1),
        gas_active=np.zeros(1, dtype=bool),
    )
    for warning in pvt_range_warnings(model, state):
        user_log.warning(f"Начальное состояние вне таблиц: {warning}")
```

**Проверка после шага:** все 14 тестов шага 1 зелёные. Регрессия: `pytest tests/test_factory_prototype.py tests/test_factory_standing_hydro.py -q -p no:cacheprovider`. Вручную — примеры не печатают `[WARNING]`: запуск одного табличного (`examples/04_table_table/main.py` с `$env:PYTHONPATH` на worktree) — в консоли нет строк `Начальное состояние вне таблиц`.

**Зависимости:** шаг 3. **Оценка:** ~25 строк, 15 мин.

### Шаг 5: Документация

**Цель:** спецификация и README согласованы с кодом.
**Файлы:** `vault/knowledge/decisions/json-config-schema.md`, `numerical_solver/examples/04_table_table/README.md`.

1. `vault/knowledge/decisions/json-config-schema.md`, строки 104 и 106 (решение 3):

До:
```markdown
| `Rs0` | float | м³ст/м³ст | Начальное газосодержание (опционально) |

Если `Rs0` не задано, вычисляется как `Rs_eq(p0)`. Ограничение: `p0 > pb`, чтобы начальное состояние было однофазным (Sg=0).
```
После:
```markdown
| `Rs0` | float | м³ст/м³ст | Начальное газосодержание (обязательно) |

Начальное состояние однофазное ($S_g = 0$), поэтому нефть на старте недонасыщенная: `Rs0 <= Rs_eq(p0)` (то есть `p0 >= pb(Rs0)`), допуск $10^{-5}$ м³ст/м³ст. Для табличной PVT `Rs0` должен лежать в диапазоне веток `oil_pvt.csv`. Обе проверки — `SimulatorFactory.from_config`, нарушение — `ValueError` (BUG-017). Выход начального давления за газовую таблицу или ветки нефти — предупреждение в журнале.
```

2. `numerical_solver/examples/04_table_table/README.md`, строки 314-315:

До:
```markdown
Выше 30 не задать: в `oil_pvt.csv` есть только ветки $R_s \in \{0, 30\}$.
Для больших $R_s$ нужна своя PVTO-таблица.
```
После:
```markdown
Выше 30 не задать: в `oil_pvt.csv` есть только ветки $R_s \in \{0, 30\}$ —
конфиг с $R_{s,0} > 30$ не загрузится (фабрика требует, чтобы таблица
покрывала $R_{s,0}$). Для больших $R_s$ нужна своя PVTO-таблица.
```

**Проверка после шага:** `git diff --stat` — два файла.
**Оценка:** 10 мин.

### Шаг 6: Верификация

1. Полный прогон в worktree: `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider` — **baseline + 14 passed** (шаг 1: 10 в `test_factory_prototype.py`, 4 в `test_factory_standing_hydro.py`): при базе 1034 — **1048 passed, 0 failed**. Время прогона почти не меняется (новые тесты не считают, только строят объекты; ~1 с).
2. Воспроизведение §2.1 в worktree (`$env:PYTHONPATH = "HydroSolverPrototype/Prototype_1.0.3;" + (Get-Location).Path`): `ValueError: Rs0 = 150 м³ст/м³ст вне диапазона таблицы oil_pvt.csv: ветки R_s от 0 до 30 м³ст/м³ст …` — из `from_config`, расчёт не начинается.
3. Все конфиги загружаются без ошибок и `[WARNING]` (скрипт §1.3; запуск с `$env:PYTHONPATH` на worktree):
   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\bug-017\numerical_solver
   $env:PYTHONPATH = "HydroSolverPrototype/Prototype_1.0.3;" + (Get-Location).Path
   D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -c "import glob; from gpn_multiphase_solver.io.config import load_config; from gpn_multiphase_solver.factory import SimulatorFactory; [SimulatorFactory.from_config(load_config(p)) for p in sorted(glob.glob('examples/*/config.json')+glob.glob('configs/**/*.json', recursive=True))]; print('OK')"
   ```
   Ожидание: вывод — `OK`, ни одной строки `[WARNING]` (у всех 14 табличных конфигов `pvt_range_warnings` на старте пуст, §1.3).
4. Результаты расчёта не меняются (код решателя не тронут): отдельного сравнения не нужно — `tests/test_examples.py` уже сверяет числа примеров с README.

**Оценка:** ~15 мин (прогон ~8 мин).

### Шаг 7: Очистка, vault, issue

1. Реестр `vault/roadmap/известные баги и технический долг.md`, запись BUG-017: поле `**Результат:**` (что сделано, тестов было → стало), статус `✅ ИСПРАВЛЕНО (<дата>)`.
2. Комментарий в issue #45 — `vault/issues/bug-017/05-comment-done.md`, `gh issue comment 45 --repo ArturSalamatin/Oil_Gas --body-file …`.
3. Коммиты (по CLAUDE.md): код и тесты — `fix: BUG-017 — проверка начального состояния против PVT в фабрике`; README 04 — `docs: README 04 — Rs0 выше таблицы не загрузится (BUG-017)`; vault (схема, реестр, план) — отдельным коммитом `vault: …`.

## 4. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_rs0_above_last_branch_raises` | `test_factory_prototype.py` | ветки 0/30, $R_{s,0} = 150$ | `ValueError` «вне диапазона таблицы», без «пересыщ», с `Rs0 = 150` | молчаливый ввод вне таблицы; неверный порядок проверок |
| `test_rs0_below_guard_threshold_raises` | то же | $R_{s,0} = 40 < 1.5 R_s^{max}$ | `ValueError` | проверку, привязанную к порогу Ньютона; молчаливые 111 МПа |
| `test_rs0_below_first_branch_raises` | то же (`tmp_path`) | ветки 5/30, $R_{s,0} = 0$ | `ValueError` | пропуск нижней границы |
| `test_rs0_on_last_branch_passes` | то же | $R_{s,0} = 30$, $p_0 = 20$ МПа | без ошибки | строгое сравнение на границе (сломало бы 13 примеров) |
| `test_supersaturated_start_raises` | то же | $R_{s,0} = 20$, $p_0 = 10$ МПа | `ValueError` «пересыщено», $p_b$ = 11.6667 в тексте | молчаливый скачок давления на старте |
| `test_p0_at_bubble_point_passes` | то же | $p_0 = p_b(30)$ | без ошибки | строгое сравнение на $p_b$ |
| `test_p0_1pa_below_pb_passes` | то же | $p_0 = p_b - 1$ Па | без ошибки | ошибку на округлении ввода |
| `test_dead_oil_below_table_pb0_passes` | то же | $R_{s,0} = 0$, $p_0 = 3$ МПа $< p_b(0)$ таблицы | без ошибки | формулировку $p_0 \ge p_b(R_{s,0})$ |
| `test_p0_above_tables_warns` | то же | $p_0 = 32$ МПа | 2 `WARNING` (газ, ветка нефти) | потерю диагностики |
| `test_in_range_no_warnings` | то же | штатный | 0 `WARNING` | ложные предупреждения |
| `test_supersaturated_start_raises` | `test_factory_standing_hydro.py` | Стендинг, $R_{s,0} = 80$, $p_0 = 10$ МПа | `ValueError` «пересыщено» | проверку только табличного пути |
| `test_p0_1pa_below_pb_passes` | то же | $p_0 = p_b(50) - 1$ Па | без ошибки | ошибку на округлении |
| `test_dead_oil_passes` | то же | $R_{s,0} = 0$ ($p_b < 0$) | без ошибки | поломку примеров 01, 02 |
| `test_no_range_warnings` | то же | Стендинг | 0 `WARNING`, без `AttributeError` | вызов диагностики на пути без `gp` |

Регрессия — весь `tests/` (все 17 примеров и 3 конфига `configs/` грузятся через `from_config` в `test_examples.py` и др.).

## 5. Критерии завершения

- [ ] 14 новых тестов зелёные; до правки — 6 красных (шаг 1)
- [ ] Все существующие тесты зелёные (baseline + 14; на зелёной базе `cc12520`+ — 1048 passed)
- [ ] Воспроизведение §2.1 даёт `ValueError` из `from_config`
- [ ] Все конфиги проекта грузятся без ошибок и `[WARNING]` (шаг 6.3)
- [ ] `json-config-schema.md` и README 04 обновлены
- [ ] Реестр, issue #45 — обновлены

## 6. Как начать работу по этому плану

1. Прочитать этот файл целиком и запись BUG-017 в [[известные баги и технический долг]].
2. Шаг 0: worktree `.worktrees/bug-017` от `numerical_scheme/implementation` — рабочее дерево основного каталога делят параллельные сессии (незакоммиченные правки примера 14, `test_examples.py`, vault).
3. venv — основного каталога: `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe`. pytest из `<worktree>\numerical_solver` берёт код worktree; скрипты вне pytest — с `$env:PYTHONPATH = "HydroSolverPrototype/Prototype_1.0.3;" + (Get-Location).Path` в той же команде.
4. Baseline (шаг 0), затем шаг 1 — тесты красные, шаги 2–4 — по одному, после каждого — указанная проверка.
5. Проба §1.4 (`vault/issues/bug-017/probes/check_ic_plugin.py`) — в `.gitignore`, в worktree её нет; для повторного замера запускать из основного каталога: `cd numerical_solver; $env:PYTHONPATH = "../vault/issues/bug-017/probes;HydroSolverPrototype/Prototype_1.0.3"; .venv\Scripts\python -m pytest tests/ -q -p check_ic_plugin -p no:cacheprovider`.

## 7. Связанные

- [[известные баги и технический долг]] — BUG-017, [[BUG-016]] (третья ступень `advance` — после неё $R_{s,0} = 40$ даёт 111 МПа вместо отказа), [[DEBT-008]] (валидация конфига, другие поля), [[BUG-014]], [[DEBT-007]]
- [[json-config-schema]] — спецификация `initial_conditions`
- Issue [#45](https://github.com/ArturSalamatin/Oil_Gas/issues/45)
