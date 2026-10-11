---
tags:
  - план
  - реструктуризация
date: 2026-10-11
issue: DEBT-011
github: 91
branch: refactor/debt-011/diagnostics-into-package
status: в процессе
worktree: .worktrees/debt-011
audit:
  date: 2026-10-11
  found: 5
  auto-fixed: 5
  manual-required: 0
---

# DEBT-011: диагностика примеров переходит в пакет `gpn_multiphase_solver`

## 0. Решения пользователя

**2026-10-10** (при `/issue`, запись реестра «Решение пользователя»):
- решатель с примерами и тестами передаётся заказчику: отдел разработки правит исходный код и развивает проект, инженеры и аналитики запускают расчёты;
- модель запуска «Б»: пакет с командой расчёта по конфигу ([[FEAT-030]]), примеры — конфиги и README; модель «пример как шаблон для копирования» отклонена;
- объём DEBT-011 — вариант 1 из issue полностью: публичный доступ к PVT и ОФП; невязки балансов в ядро; вычислительная часть проверок в `gpn_multiphase_solver/diagnostics/`; рисующие функции проверок в пакет. Конвейер `run_example`, `figure_io` и команда запуска — [[FEAT-030]].

**2026-10-11** (при планировании):
1. **Доступ к объектам задачи — свойства `Simulator` + публичная фабрика.** `Simulator.grid`, `Simulator.pvt`, `Simulator.relperm`; ОФП передаётся в конструктор `Simulator`. В фабрике `_create_pvt`, `_create_relperm` переименовываются в `create_pvt`, `create_relperm` **без псевдонимов**; все вызовы в пакете, тестах и примерах обновляются.
2. **Рисующие функции — в `io/output.py`**, рядом с `plot_pvt_properties` и `plot_profiles`. По образцу FEAT-017: функция пакета рисует на переданных осях и возвращает их, файлов не пишет и не печатает. Сохранение PNG и печать остаются в `examples/` до [[FEAT-030]].
3. **Порядок — после влития [[DEBT-008]] и [[DEBT-063]].** DEBT-008 правит `examples/rs_analytics.py` (допуск `RS_TOL` → `numerics.rs_switch_tol`); DEBT-063 меняет центры ячеек, а с ними все числа в выводе примеров. DEBT-011 переносит уже исправленный код, и снимок вывода снимается на новых центрах. **Выполнено 2026-10-11:** DEBT-008 влит `23d2cec`, DEBT-063 — `d11e3fe` (с ними в базе DEBT-020, DEBT-064); база `73ef031`.
4. **Проверка неизменности — снимок вывода всех примеров.** Печать всех `main.py` и побайтно все файлы `output/` до и после переноса; вдобавок быстрый уровень тестов после шагов и полный прогон.

## 1. Сводка

- **Подтип:** реструктуризация (перенос модулей в пакет) + публичный интерфейс.
- **Суть:** код, проверяющий расчёт, — замкнутое решение стационара, аналитика двухфазного стационара, аналитика $R_s$, однофазная асимптотика $T$, сборка невязок балансов, рисунки ОФП и балансов, узлы таблиц PVT и ОФП — переезжает из `numerical_solver/examples/` в пакет. Примеры и тесты обращаются к объектам задачи только через публичный интерфейс.
- **Числа не меняются.** Перенос побайтный: печать примеров и все файлы `output/` совпадают со снимком «до» (раздел 5.3).
- **Шагов:** 14 (0 — подготовка, 13 — итог).
- **Тесты:** +12 в новом `tests/test_public_api.py`, +1 параметризованный страж в `tests/test_example_scripts.py` (по одному на скрипт `examples/`, на 2026-10-11 — 46). Существующие тесты перенаправляются на пакет, их число не меняется.
- **Код:** ~750 строк переезжает (`examples/` → пакет, с докстрингами-выводами), ~60 строк нового кода (свойства, обёртки), ~250 строк тестов.
- **Оценка:** ~4 ч, из них ~35 мин — два снимка примеров и полный прогон.

**Граница с [[FEAT-030]].** В `examples/` остаются: функции печати отчётов (`report_*`), наложения на профили для `run_example` (`make_overlay_*`, `_draw_rs`), обёртки рисунков с записью PNG (`plot_relperm`, `plot_pvt`, `plot_energy_balance`, `plot_mass_balance`), `example_runner.py`, `figure_io.py`, `convergence.py`, `energy_balance_convergence.py`, CLI-блоки `__main__`. Их перенос — FEAT-030. Вставки `sys.path` в скриптах примеров (папка `examples/` ради соседних модулей) тоже остаются до FEAT-030: критерий «без правки `sys.path`» DEBT-011 выполняет для **пакета** — страж в шаге 12.

## 2. Контекст

### 2.1. Связанные заметки и задачи

- Реестр: `vault/roadmap/известные баги и технический долг.md`, запись DEBT-011 (поле «Актуализация 2026-10-10», «Решение пользователя», «Попутно из DEBT-012»).
- Issue: [#91](https://github.com/ArturSalamatin/Oil_Gas/issues/91), тело — `vault/issues/debt-011/01-issue-body.md`.
- Прецеденты расслоения: FEAT-017 (`io/output.py::plot_pvt_properties` + `examples/pvt_plot.py`), DEBT-013 (`energy/balance.py::EnergyBalanceAccumulator`), DEBT-039 (`gpn_multiphase_solver/mass_balance.py::MassBalanceAccumulator`).
- [[DEBT-059]] (влит `29a1ffa`): прототип `radial-blackoil` — установленный дистрибутив; пути к прототипу из `examples/` убраны.
- [[DEBT-006]] (влит `87e99a1`): свойства `TableFullPVT.hydro`, `PrototypePVTAdapter.proto_pvt`, `PrototypeRPAdapter.proto_rp` вместо `hasattr` по приватным полям — на них опираются узлы таблиц (шаги 10–11).
- [[DEBT-046]] (влит `1171a84`): `tests/test_example_scripts.py` разбором AST проверяет, что имена, которые скрипты `examples/` берут из модулей, существуют. Ловит потерянный импорт после переноса, но **не** приватные атрибуты (`sim._energy._rock` — прямо сказано в его докстринге). Это закрывает страж шага 3.
- [[DEBT-037]]: `SHARED_EXAMPLE_FILES`, `SHARED_CHECK_MODULES` в `tests/test_examples.py` — модули `examples/` остаются на месте, списки не меняются.
- [[DEBT-008]] — **влит** `23d2cec`: `examples/rs_analytics.py` — допуск аргументом `tol` из `numerics.rs_switch_tol`, константы `RS_TOL` нет; тесты допуска в `tests/test_rs_analytics.py` идут через `report_rs` (остаётся в `examples/`).
- [[DEBT-063]] — **влит** `d11e3fe`: `LogRadialGrid.r_centers` = $\sqrt{r_{j-1/2}r_{j+1/2}}$; имя свойства прежнее, значения другие; тесты с `sim._grid.r_centers` (`test_val001.py`, `test_factory_standing_hydro.py`) — под замену шага 3.
- [[DEBT-048]] (план готов): правит `Simulator._advance` и адаптер — другая часть `simulator.py`, конфликт слияния маловероятен, порядок не важен.
- [[DEBT-020]] (план готов): `energy/balance.py` в его зоне неприкосновенности; DEBT-011 добавляет туда функцию в конец файла — не пересекаются.
- [[DEBT-023]] — **реализуется** (worktree `.worktrees/debt-023` на 2026-10-11): теплопроводность в конфигах 03–09 меняет вывод этих примеров; правит и файлы этого плана — `tests/test_energy_balance_examples.py`, `tests/test_examples.py` (комментарии), `tests/test_energy_matrix_examples.py`. **Начинать DEBT-011 после её влития**: тогда снимок «до» снимается на окончательных конфигах, а конфликтов слияния в тестах нет. Если DEBT-023 вливается во время реализации — влить базу в ветку, разрешить конфликты в этих тестах (правки DEBT-011 — импорты и имена функций, DEBT-023 — комментарии и числа), снимок «до» снять заново на новой базе (шаг 0, «Подводные камни»).
- [[DEBT-054]] (план готов): правит `Simulator._advance` и `_failure_message` (`simulator.py`), адаптер прототипа, `tests/test_simulator.py` — другая часть `simulator.py`, чем конструктор и свойства DEBT-011; конфликт слияния маловероятен, порядок не важен.
- Блокирует: [[FEAT-030]], [[FEAT-031]].

### 2.2. Текущее состояние (план писался на `123247a`; сверено с `73ef031`, 2026-10-11)

Тесты на `73ef031` (DEBT-008, DEBT-063, DEBT-020 влиты): **1741** (`--collect-only`), быстрый уровень **1470** (на `123247a` было 1699 / 1428). Приватный доступ на `73ef031` — те же 21 файл `examples/` (DEBT-063 добавил обращения `sim._grid` в `tests/test_val001.py`, `tests/test_factory_standing_hydro.py` — под замену шага 3). Скриптов `examples/` — 46. Номера строк ниже — на `123247a`; у затронутых DEBT-008/063 файлов они сдвинулись — сверять grep-ом (шаг 0 даёт команды; `examples/rs_analytics.py` — уже по `73ef031`).

**Что лежит в `examples/` и куда идёт:**

| модуль `examples/` | вычисление → пакет | остаётся в `examples/` |
|---|---|---|
| `closed_form.py` (359) | `_kr_max_Sg`, `Closure`, `_CACHE`, `_rate_closed`, `stationary_pwf`, `solve_closed`, `_front_radius`, `saturation_from_numeric` → `diagnostics/closed_form.py` | `_prepare`, `make_overlay_pressure`, `make_overlay_saturation`, `report_closed` |
| `two_phase_analytics.py` (415) | `SG_EPS`, `compute_gor`, `compute_free_gas_prediction`, `predict_saturation`, `dupuit_check`, `degassing_front` → `diagnostics/two_phase.py` (копия `_kr_max_Sg` удаляется — та же функция из `closed_form`) | `report`, `_resolve_example`, `__main__` |
| `rs_analytics.py` | `SG_GAS`, `rs_expected`, `rs_error`, `rs_supersaturation(history, pvt, tol)`¹, `_degassed_cells` → `degassed_cells`, `front_radius` → `diagnostics/rs.py` | `make_overlay_rs`, `_draw_rs`, `report_rs` (берёт `tol` из конфига) |
| `temperature_asymptotics.py` (121) | `single_phase_asymptote` → `diagnostics/temperature.py` | `SG_EPS`, `report_asymptotics`, `__main__`; `_pvt_of` удаляется (шаг 3) |
| `energy_balance.py` (231) | `compute_balance` → `energy/balance.py::compute_energy_balance(history)`; рисование → `io/output.py::plot_energy_balance_series` | `plot_energy_balance` (обёртка: PNG + печать), `report_energy_balance`, `_resolve_example`, `__main__` |
| `mass_balance.py` (164) | `compute_mass_balance` → `mass_balance.py::compute_mass_balance(history)`; рисование → `io/output.py::plot_mass_balance_series` | `plot_mass_balance` (обёртка), `__main__` |
| `relperm_plot.py` (232) | `_table_nodes` → `io/output.py::relperm_table_nodes`; рисование → `io/output.py::plot_relperm_curves` | `plot_relperm` (обёртка), `report_relperm`, `_sg_range`, `_describe` |
| `pvt_plot.py` (310) | `_pvt_table_nodes` → `io/output.py::pvt_table_nodes` | `plot_pvt`, `report_pvt`, `_get_pvt`, `_physical_rs`, `_describe`, `_nodes_in_range`, `_p_range` |

¹ DEBT-008 (`23d2cec`) убрал константу `RS_TOL`: допуск пересыщения — аргумент `tol` функции `rs_supersaturation` (`examples/rs_analytics.py:103` на `73ef031`), `report_rs` берёт его из `config.numerics.rs_switch_tol` (`:210`). Функция переезжает с аргументом и с блоком комментария о допуске над ней (`:96-102`); сигнатуры не менять.

**Приватный доступ (38 обращений в 21 файле `examples/`, ещё ~40 в тестах):**
- `sim._energy._pvt` / `simulator._energy._pvt` — PVT задачи. Тот же объект, что `simulator._pvt` (фабрика передаёт один `pvt` и решателю энергии, и `Simulator`; тождество проверяет `tests/test_factory_prototype.py:246`).
- `sim._grid` / `simulator._grid` — сетка.
- `sim._energy._rock` — это `config.rock`: фабрика передаёт `TridiagEnergySolver(grid, pvt, config.rock)` (`factory.py:69`), `tridiag.py:67` хранит его как есть.
- `factory._create_relperm(config)`, `factory._create_pvt(config)` — новый объект по конфигу.
- `tpa._build_relperm(config)` (05/main.py:97) — обёртка над `_create_relperm`.
- В тестах заглушки решателя: `SimpleNamespace(_energy=SimpleNamespace(_pvt=pvt))` — `tests/test_rs_analytics.py:73`, `tests/test_examples.py:1994-1995`.

**ОФП у `Simulator` нет.** Фабрика создаёт `relperm = _create_relperm(config)` (`factory.py:63`) и отдаёт его только гидродинамике (`_create_prototype_hydro`). Для Кори прототип получает таблицу на 101 узле (`_get_or_create_proto_rp`, `factory.py:476-492`); диагностика при этом обращает формулу `CoreyRP`. Так было всегда — пользователь решил это в реестр не заносить; DEBT-011 поведение не меняет, а лишь делает объект ОФП доступным.

**Как примеры получают объекты.** `run_example` возвращает `(elapsed, history, grid, config)` без решателя, поэтому `main.py` 01–05 собирают **второй** `Simulator` (`SimulatorFactory.from_config(config)`) ради PVT. DEBT-011 этого не меняет (поменяло бы печать, если фабрика что-то пишет в журнал) — только заменяет приватный доступ; переделка — FEAT-030 (раздел 8).

### 2.3. Целевое состояние

```
numerical_solver/gpn_multiphase_solver/
├── diagnostics/                 # новый подпакет (DEBT-011)
│   ├── __init__.py              # докстринг: что где лежит
│   ├── closed_form.py           # замкнутое решение стационара: Closure, solve_closed, stationary_pwf, ...
│   ├── two_phase.py             # аналитика двухфазного стационара: GOR, S_g из замыкания, Дюпюи, фронт
│   ├── rs.py                    # равновесие R_s: rs_error, rs_supersaturation, front_radius, ...
│   └── temperature.py           # однофазная асимптотика T
├── energy/balance.py            # + compute_energy_balance(history)
├── mass_balance.py              # + compute_mass_balance(history)
├── io/output.py                 # + plot_energy_balance_series, plot_mass_balance_series,
│                                #   relperm_table_nodes, plot_relperm_curves, pvt_table_nodes
├── factory.py                   # _create_pvt → create_pvt, _create_relperm → create_relperm
└── simulator.py                 # + свойства grid, pvt, relperm; аргумент relperm
```

**Граф импортов.** `diagnostics/two_phase.py` → `diagnostics/closed_form.py` (функция `kr_max_Sg`); `diagnostics/*` → только `numpy`, `scipy`. `io/output.py` → `..pvt.table_full`, `..pvt.prototype_adapter`, `..units` (новые; `pvt/*` не импортирует `io` — цикла нет). `examples/*` → `gpn_multiphase_solver.*` (как и раньше), но только публичные имена. Пакет **не** импортирует ничего из `examples/` и не трогает `sys.path` — страж шага 12.

**Публичный интерфейс после задачи** (пользователь пакета без `examples/`):

```python
from gpn_multiphase_solver.factory import SimulatorFactory, create_pvt, create_relperm
from gpn_multiphase_solver.energy.balance import compute_energy_balance
from gpn_multiphase_solver.mass_balance import compute_mass_balance
from gpn_multiphase_solver.diagnostics.closed_form import solve_closed, stationary_pwf, Closure
from gpn_multiphase_solver.diagnostics.two_phase import compute_gor, predict_saturation, dupuit_check, degassing_front
from gpn_multiphase_solver.diagnostics.rs import rs_error, rs_supersaturation, front_radius
from gpn_multiphase_solver.diagnostics.temperature import single_phase_asymptote
from gpn_multiphase_solver.io.output import (plot_energy_balance_series, plot_mass_balance_series,
                                             plot_relperm_curves, relperm_table_nodes, pvt_table_nodes,
                                             plot_pvt_properties)

sim, init = SimulatorFactory.from_config(config)
history = sim.run(init)
cl = solve_closed(config, sim.pvt, sim.relperm, sim.grid.r_centers)
bal = compute_energy_balance(history)
```

### 2.4. Варианты

Решение принято (раздел 0); варианты — для полноты.

- **А. Перенос в пакет с публичным интерфейсом** (принят). Каждый шаг рабочий, тесты зелёные; числа не меняются; пакет пригоден для поставки. Минус — объём (14 шагов, ~40 файлов).
- **Б. Модули `examples/` целиком в пакет, `examples/` их реэкспортирует.** Меньше правок вызовов, но в пакет уходят печать, запись PNG и `figure_io` — граница с FEAT-030 размывается; приватный доступ остаётся внутри пакета.
- **В. Включить `examples/` в дистрибутив** — отвергнут на `/issue` (плоские импорты, правка `sys.path`, демонстрационные файлы в пакете).

### 2.5. Подводные камни

| Пункт | Статус | Как адресован |
|---|---|---|
| Все вызовы найдены | ⚠️ | Переименования — заменой по регулярному выражению с проверкой `git grep` до пустого вывода (шаги 1, 3, 4). Имена из модулей `examples/` в скриптах ловит `test_example_scripts.py` (DEBT-046); приватные атрибуты — новый страж шага 3 |
| `_get_or_create_proto_*` | ⚠️ | Регулярное выражение `(?<![A-Za-z0-9_])_create_(pvt\|relperm)\b` их не задевает (в `_get_or_create_proto_pvt` после `_create_` идёт `proto`) — проверено |
| Зависимости пакета | ✅ | Новых нет: `matplotlib` уже в `dependencies`; `scipy` — тоже |
| Обратная совместимость | ⚠️ | Внешнего API нет (пакет никому не поставлен). Внутри: `examples/energy_balance.compute_balance` удаляется (вызовы и тесты — на `compute_energy_balance`); `_pvt_of`, `_build_relperm`, `_table_nodes`, `_pvt_table_nodes` уходят. Неотслеживаемый `numerical_solver/deliverables/rs150_for_sergey/make_tables.py` импортирует `_create_pvt`, `_create_relperm` — **сломается**; файл не в git и принадлежит пользователю — не править, сообщить в итоге |
| Циклы импорта | ✅ | `diagnostics` → `numpy`, `scipy`; `io/output` → `pvt.*` (в `pvt` нет импорта `io`). Проверка: `python -c "import gpn_multiphase_solver.io.output, gpn_multiphase_solver.diagnostics.two_phase"` |
| Ссылки на уравнения | ✅ | Докстринги переносятся как есть; `tests/test_eq_references.py` проверяет и пакет, и `examples/` |
| Конфиги | ✅ | Не меняются |
| Тестовые заглушки решателя | ⚠️ | `SimpleNamespace(_energy=SimpleNamespace(_pvt=…))` (`test_rs_analytics.py:73`, `test_examples.py:1994`) → `SimpleNamespace(pvt=…, relperm=…)` в шаге 3 |
| Медленные тесты меняются | ⚠️ | Правки в `tests/test_examples.py` на фикстуре `results` быстрый уровень не проверяет. Поэтому: `git grep` старых имён до пустого вывода после каждого шага, точечные медленные тесты по `-k` там, где указано, и шаг 11 — «Регресс: полный» |
| Кэш `solve_closed` | ✅ | `_CACHE` переезжает с функцией; ключ — параметры конфига, не объекты PVT/ОФП: замена `create_relperm(config)` на `sim.relperm` ключ не меняет |
| PNG побайтно | ✅ | Последовательность вызовов `matplotlib` переносится без перестановок; детерминизм снимка проверен на 01 и 03 (два прогона, 23 файла совпали побайтно, 2026-10-11) |
| Производительность | ✅ | Код тот же |
| Прототип | ✅ | Не трогается; тесты и регрессия прототипа не нужны |
| Порядок с DEBT-008/063 | ⚠️ | Шаг 0 проверяет влитие; без него — стоп |

### 2.6. Обнаруженные проблемы

1. **Радиус изобары $p = p_b$ считается тремя функциями с разными краевыми случаями** — `closed_form._front_radius` (за краем сетки — `r[p < pb].max()`), `two_phase_analytics.degassing_front["r_b_interp"]` (NaN), `rs_analytics.front_radius` (NaN). Одна величина — интерполяция $\ln r$ по $p$ между соседними ячейками. DEBT-011 их не объединяет: это изменило бы вывод на краевых случаях. Зарегистрировано: [[DEBT-065]].
2. **`main.py` 01–05 собирают второй `Simulator`** ради PVT: `run_example` решатель не возвращает. Плюс `_resolve_example` в трёх копиях (`energy_balance.py`, `energy_balance_convergence.py`, `two_phase_analytics.py`). Оба — устройство конвейера и CLI примеров, то есть [[FEAT-030]]; дописано в его запись («Открыто к планированию»).
3. **`numerical_solver/deliverables/rs150_for_sergey/make_tables.py`** (не в git) зовёт `_create_pvt`, `_create_relperm` — сломается после шага 1. Не правится; сообщить пользователю.

## 3. Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай: запись DEBT-011 в реестре; `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`; `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md`; докстринг `numerical_solver/tests/test_example_scripts.py`.
3. **Предусловие — DEBT-008 и DEBT-063 влиты** (шаг 0.1; выполнено на `73ef031`). Иначе — стоп, сообщить пользователю. **Желательно — и DEBT-023** (раздел 2.1) — **выполнено: влита `69e2d40`, база `f89c08b`**; число тестов прежнее (1741, быстрый уровень 1470), номера строк `tests/test_examples.py` не сдвинулись.
4. Worktree по контракту `/implement`: `.worktrees/debt-011`, ветка `refactor/debt-011/diagnostics-into-package` от `numerical_scheme/implementation`. Ниже `<W>` — корень worktree, `<M>` — основной каталог `D:\Lessons\Grants\2026\GPN\Oil_Gas`.
5. Python — из основного каталога (в worktree `.venv` нет):
   ```powershell
   $PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   cd <W>\numerical_solver
   ```
   pytest берёт пакет worktree сам (`pythonpath` в `pyproject.toml`). Скрипты вне pytest без `PYTHONPATH` берут пакет **основного каталога** — проба снимка ставит `PYTHONPATH` сама и проверяет путь пакета.
6. Базовый вариант:
   ```powershell
   & $PY -m pytest tests/ --collect-only -q          # N0 — всего тестов
   & $PY -m pytest tests/ -m "not slow" -q           # N0f — быстрый уровень, время
   ```
   Записать N0, N0f, время быстрого уровня.
7. Снимок «до» — шаг 0.4. Начать с шага 1. После каждого шага — тест шага и регресс по полю «Регресс».

## 4. Шаги

### Шаг 0: подготовка — предусловия, базовый вариант, снимок «до»

**Цель:** убедиться, что база содержит DEBT-008 и DEBT-063, и снять эталон вывода примеров на неизменённом коде.

**Файлы:** `vault/issues/debt-011/probes/snapshot_examples.py` (уже есть, создан при планировании).

**Что сделать:**
1. Предусловие:
   ```powershell
   git log --oneline numerical_scheme/implementation | Select-String "DEBT-008|DEBT-063"
   ```
   Должны быть merge-коммиты обеих задач. Нет — стоп.
2. Сверить место правок после этих задач (номера строк плана — на `123247a`):
   ```powershell
   cd <W>\numerical_solver
   git grep -n -P "_energy\._(pvt|rock)|\b(sim|simulator)\._grid|_create_(pvt|relperm)\b|_build_relperm|_pvt_of\b" -- examples tests gpn_multiphase_solver
   git grep -n -E "RS_TOL|rs_switch_tol" -- examples/rs_analytics.py tests/test_rs_analytics.py
   ```
   Ключ `-P` (регулярные выражения Perl) — во всех командах плана, где есть `\b` или просмотр назад: в `-E` git их не поддерживает.
   Первый список — всё, что меняют шаги 1 и 3 (DEBT-063 добавил тесты с `sim._grid` — они в нём будут). Второй показывает, в каком виде DEBT-008 оставил допуск $R_s$ — переносить в шаге 7 именно его.
3. Базовые числа (раздел 3, п. 6).
4. Снимок «до» (в фоне, ~15–20 мин: 01 — 107 с, 17 — ~110 с):
   ```powershell
   New-Item -ItemType Directory -Force <W>\vault\issues\debt-011\probes\out
   & $PY <W>\vault\issues\debt-011\probes\snapshot_examples.py snap --tree <W>\numerical_solver --out <W>\vault\issues\debt-011\probes\out\snap_before.json
   ```
   Проба печатает путь пакета — он обязан быть под `<W>`; иначе проба сама остановится. Все 23 примера — «код 0». Файлы в `probes/out/` не коммитить.

**Проверка:** коды возврата 0; `snap_before.json` есть.

**Подводные камни:** если в ветку позже вливается новая база — снимок «до» снять заново на ней (отдельный worktree в состоянии detached на базе), иначе сравнение покажет чужие изменения.

**Зависимости:** блокирует все шаги.

**Оценка:** ~25 мин (из них ~20 — снимок в фоне).

⚠️ **Пока снимок идёт, код дерева не править.** Каждый пример — отдельный процесс и импортирует код заново: правка посреди прогона даст смешанный снимок (поздние примеры — на новом коде). То же для снимка «после» (шаг 13).

---

### Шаг 1: фабрика — `create_pvt`, `create_relperm` публичные

**Цель:** функции сборки PVT и ОФП по конфигу — часть публичного интерфейса пакета.

**Файлы:** `numerical_solver/gpn_multiphase_solver/factory.py`; все `.py` в `numerical_solver/tests/` и `numerical_solver/examples/`, где встречаются имена.

**Контекст:** без решателя (рисунок PVT по конфигу, скрипты сходимости, тесты) объекты PVT и ОФП можно получить только из фабрики. Сейчас её функции приватные (`_create_pvt`, `factory.py:95`; `_create_relperm`, `:358`), а примеры их всё равно зовут. Решение пользователя — переименовать без псевдонимов.

**Что сделать:**
1. Переименовать определения и вызовы во всём коде пакета, тестов и примеров:
   ```powershell
   cd <W>\numerical_solver
   $files = git grep -l -P "(?<![A-Za-z0-9_])_create_(pvt|relperm)\b" -- "*.py" "*.md"
   foreach ($f in $files) {
       $t = [IO.File]::ReadAllText($f)
       $n = [regex]::Replace($t, '(?<![A-Za-z0-9_])_create_(pvt|relperm)\b', 'create_$1')
       if ($n -ne $t) { [IO.File]::WriteAllText($f, $n, (New-Object Text.UTF8Encoding $false)) }
   }
   git grep -n -P "(?<![A-Za-z0-9_])_create_(pvt|relperm)\b" -- .     # пусто
   git grep -n "_get_or_create_proto" -- gpn_multiphase_solver/factory.py  # остались (не те имена)
   git diff --stat                                                       # меняются только строки с именами
   ```
   Переводы строк: в рабочей копии CRLF (`core.autocrlf=true`, в индексе LF — `git ls-files --eol`); `ReadAllText`/`WriteAllText` их сохраняют. Если `git diff --stat` показывает изменение всех строк файла — перевод строк сбит: вернуть файл (`git checkout -- <файл>`) и заменить через Edit.
   Охват на `73ef031`: `factory.py` (определения 96, 356, вызовы 57, 64), `tests/test_factory_prototype.py`, `tests/test_factory_standing_hydro.py`, `tests/test_examples.py`, `tests/test_rs_analytics.py`, `examples/closed_form.py`, `examples/pvt_plot.py`, `examples/relperm_plot.py` (в т. ч. докстринг `:11`, комментарий `:50`), `examples/two_phase_analytics.py` (докстринг `:7`), `examples/04_table_table/grid_convergence.py`, `examples/04a_high_gas_saturation/grid_convergence.py`, `examples/05_standing_table_rp/closed_form_convergence.py`; README в `examples/` — по выводу `git grep`.
2. В `factory.py` заголовок раздела перед `create_pvt` (сейчас `# ── Помощники (внутренние функции модуля) ──`, `:93`):
   ```python
   # ── Сборка моделей по конфигу и помощники ────────────────────
   # create_pvt, create_relperm — публичные (DEBT-011): по ним диагностика и
   # примеры получают PVT и ОФП без решателя. Остальное — внутреннее.
   ```
3. Докстринги:
   ```python
   def create_pvt(config: SimulationConfig):
       """FullPVT по config.pvt.model; публичная — для диагностики без решателя (DEBT-011)."""

   def create_relperm(config: SimulationConfig):
       """RelPermModel по config.relperm.model; публичная — для диагностики без решателя (DEBT-011)."""
   ```

**Проверка после шага:**
- Регресс: быстрый.
- `git grep` из п. 1 пуст.

**Подводные камни:** раздел 2.5, «Все вызовы», «`_get_or_create_proto_*`», «Обратная совместимость» (`deliverables/`).

**Зависимости:** требует шаг 0; блокирует шаги 2–3.

**Оценка:** ~30 строк в 12 файлах, ~15 мин.

---

### Шаг 2: `Simulator` — свойства `grid`, `pvt`, `relperm`

**Цель:** объекты, которыми считалась задача, доступны через публичные свойства решателя.

**Файлы:** `numerical_solver/gpn_multiphase_solver/simulator.py`, `numerical_solver/gpn_multiphase_solver/factory.py`, `numerical_solver/tests/test_public_api.py` (новый).

**Контекст:** `Simulator` хранит сетку и PVT (`self._grid`, `self._pvt`, `simulator.py:110, 113`), ОФП — нет. Диагностике нужен **тот же** объект, что считал задачу: для табличной ОФП — обёртка над той же `TabulatedRelPerm`, что у модели прототипа. Поэтому фабрика передаёт `relperm` в конструктор. Аргумент необязательный: 23 прямых вызова `Simulator(...)` в тестах (двойники в `test_simulator.py`, `test_mass_balance.py`, `test_output.py`, `test_val001.py`) ОФП не передают.

**Изменения:**

`simulator.py`, импорт (`:29`):
```python
from .pvt.base import HydroPVT
```
→
```python
from .pvt.base import HydroPVT, RelPermModel
```

Конструктор (`:97-118`) — добавить аргумент последним, описание в докстринг, поле:
```python
    def __init__(self, grid: Grid, hydro: HydroSolver,
                 energy: EnergySolver, pvt: HydroPVT,
                 schedule: TimeSchedule,
                 max_retries: int = 9,
                 relperm: RelPermModel | None = None):
        """
        ...
        max_retries   — ... (без изменений)
        relperm       — модель ОФП, отданная гидродинамике; Simulator её не
                        использует, а хранит для диагностики (DEBT-011).
                        None — не задана (тестовые двойники)
        """
        ...
        self._max_retries = int(max_retries)
        self._relperm = relperm
```

После конструктора, до `run`:
```python
    # ── Объекты задачи для диагностики (DEBT-011) ────────────
    # Публичный доступ вместо sim._grid, sim._energy._pvt: диагностика
    # обязана видеть ровно те объекты, которыми считалась задача.

    @property
    def grid(self) -> Grid:
        """Сетка задачи."""
        return self._grid

    @property
    def pvt(self) -> HydroPVT:
        """PVT задачи — тот же объект, что у решателя энергии и гидродинамики."""
        return self._pvt

    @property
    def relperm(self) -> RelPermModel | None:
        """ОФП задачи по конфигу; Кори прототип получает её таблицей на 101 узле."""
        return self._relperm
```

`factory.py`, `from_config` (`:75-77`):
```python
        simulator = Simulator(
            grid=grid, hydro=hydro, energy=energy, pvt=pvt,
            schedule=schedule, max_retries=config.numerics.max_retries)
```
→
```python
        # relperm — тот же объект, что ушёл гидродинамике: Simulator отдаёт
        # его диагностике (DEBT-011)
        simulator = Simulator(
            grid=grid, hydro=hydro, energy=energy, pvt=pvt,
            schedule=schedule, max_retries=config.numerics.max_retries,
            relperm=relperm)
```

**Тесты** — новый `numerical_solver/tests/test_public_api.py` (шапка и первые 4 теста; остальные добавляют шаги 4, 9–12):

```python
"""Публичный интерфейс пакета для диагностики расчёта (DEBT-011).

Решатель с примерами передаётся заказчику: примеры — образец работы с
библиотекой, и всё, что они вызывают, становится интерфейсом. Здесь —
объекты задачи у Simulator, функции сборки фабрики, ряды балансов,
рисунки проверок и страж независимости пакета от examples/.
"""

import ast
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

import gpn_multiphase_solver.factory as factory  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory, create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypeRPAdapter  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from gpn_multiphase_solver.simulator import Simulator  # noqa: E402

SOLVER_ROOT = Path(__file__).resolve().parent.parent
BASELINE = SOLVER_ROOT / "configs" / "baseline.json"                 # Стендинг + Кори
TABLE_CONFIG = SOLVER_ROOT / "configs" / "table_pvt" / "config.json"  # таблицы PVT и ОФП


# ── Фабрика ──────────────────────────────────────────────────

def test_factory_builders_public_without_aliases():
    """Сборка PVT и ОФП по конфигу — публичные create_pvt, create_relperm.

    Приватных имён не осталось (решение пользователя: без псевдонимов —
    два имени одной функции расходятся при следующей правке).
    """
    assert callable(factory.create_pvt) and callable(factory.create_relperm)
    assert not hasattr(factory, "_create_pvt")
    assert not hasattr(factory, "_create_relperm")


# ── Объекты задачи у Simulator ───────────────────────────────

def test_simulator_objects_table():
    """Табличный случай: сетка и PVT — объекты решателя энергии, ОФП — обёртка таблицы модели.

    Тождество (is), а не равенство: диагностика обязана видеть ровно то,
    что считало задачу. Приватные поля здесь — белый ящик, ради проверки
    связки фабрики.
    """
    sim, _ = SimulatorFactory.from_config(load_config(TABLE_CONFIG))
    assert sim.grid is sim._energy._grid
    assert sim.pvt is sim._energy._pvt
    assert isinstance(sim.relperm, PrototypeRPAdapter)
    # Модель прототипа получила ту же TabulatedRelPerm (DEBT-006, BUG-018)
    assert sim._hydro._model.relperm is sim.relperm.proto_rp


def test_simulator_objects_corey():
    """Кори: ОФП — CoreyRP с параметрами конфига; кривые совпадают с create_relperm побитово."""
    cfg = load_config(BASELINE)
    sim, _ = SimulatorFactory.from_config(cfg)
    assert sim.pvt is sim._energy._pvt
    assert isinstance(sim.relperm, CoreyRP)
    S = np.linspace(0.0, 1.0, 11)
    ref = create_relperm(cfg)
    np.testing.assert_array_equal(sim.relperm.kro(S), ref.kro(S))
    np.testing.assert_array_equal(sim.relperm.krg(S), ref.krg(S))


def test_simulator_relperm_none_without_argument():
    """Simulator без ОФП (так его строят тестовые двойники) отдаёт relperm = None."""
    sim = Simulator(grid=None, hydro=None, energy=None, pvt=None, schedule=None)
    assert sim.relperm is None
```

**Проверка после шага:**
- Регресс: быстрый. Ожидание: N0f + 4.
- `& $PY -m pytest tests/test_public_api.py -q` — 4 passed.

**Подводные камни:** `Simulator.__init__` не проверяет аргументы — конструирование с `None` в тесте законно; если к моменту реализации появилась проверка (DEBT-048 и др.) — передать двойники из `tests/test_simulator.py`.

**Зависимости:** требует шаг 1 (`create_relperm`); блокирует шаг 3.

**Оценка:** ~25 строк кода, ~80 строк теста, ~20 мин.

**Точка коммита:** `refactor: публичные create_pvt, create_relperm и объекты задачи у Simulator (DEBT-011)`.

---

### Шаг 3: примеры и тесты — только публичный доступ; страж

**Цель:** ни один скрипт `examples/` не обращается к приватным полям решателя и приватным именам пакета; тесты, не проверяющие связку фабрики, — тоже.

**Файлы:** скрипты `numerical_solver/examples/` (список — вывод `git grep` шага 0.2), `numerical_solver/tests/` (то же), `numerical_solver/tests/test_example_scripts.py`.

**Контекст:** примеры — образец для заказчика; приватный вызов в примере станет интерфейсом, который нельзя менять. Замены один-в-один, числа не меняются: `sim.pvt is sim._energy._pvt`, `sim.grid is sim._grid`, `config.rock is sim._energy._rock`; `sim.relperm` и `create_relperm(config)` дают одинаковые кривые (шаг 2, тест Кори; для таблицы — тот же CSV).

**Что сделать:**
1. Механические замены в `examples/**/*.py` и `tests/*.py`:

   | было | стало |
   |---|---|
   | `sim._energy._pvt`, `simulator._energy._pvt` | `sim.pvt`, `simulator.pvt` |
   | `sim._grid`, `simulator._grid` | `sim.grid`, `simulator.grid` |
   | `simulator._pvt` (`tests/test_energy_matrix_examples.py:854`) | `simulator.pvt` |
   | `sim._energy._rock` | `config.rock` — объект, из которого собран `sim` (см. ниже) |

   ```powershell
   cd <W>\numerical_solver
   # просмотреть каждое место перед заменой
   git grep -n -P "\b(sim|simulator)\._(energy\._pvt|grid|pvt)\b" -- examples tests
   ```
   **Не менять** (белый ящик связки фабрики — проверяют именно приватные поля): `tests/test_factory_prototype.py:246` и `tests/test_factory_standing_hydro.py:62` (`simulator._energy._pvt is simulator._pvt`), тесты `test_public_api.py`.
2. `_energy._rock` → `config.rock` (сверено: `sim` собран из этого же `config`):
   - `examples/01_single_phase_no_jt/main.py:86` — `rock = config.rock`;
   - `examples/02_single_phase_jt/main.py:131` — `rock = config.rock`;
   - `examples/01_single_phase_no_jt/spatial_convergence.py:46` — `rock = config.rock` (`config` — аргумент функции, из него `from_config` на `:43`);
   - `examples/02_single_phase_jt/check_slopes.py:108` — `theoretical_slopes(config, sim.pvt, config.rock, mu_JT)` (`config` — копия, из которой собран `sim` на `:103`).
3. ОФП там, где решатель есть, — его объект:
   - `examples/closed_form.py`, `_prepare`: `relperm = create_relperm(config)` → `relperm = simulator.relperm`, импорт `create_relperm` убрать; `saturation_from_numeric`: `Closure(simulator.pvt, simulator.relperm, ...)`, импорт убрать;
   - `examples/04_table_table/grid_convergence.py:93`, `examples/04a_high_gas_saturation/grid_convergence.py:74`, `examples/05_standing_table_rp/closed_form_convergence.py:85` — `create_relperm(config)` → `sim.relperm`; импорт `create_relperm` из строки `from gpn_multiphase_solver.factory import ...` убрать (в 04a — строка целиком);
   - `examples/05_standing_table_rp/main.py:97` — `relperm = tpa._build_relperm(config)` → `relperm = sim.relperm`;
   - `examples/example_runner.py:188` — `plot_relperm(config, history, output_dir, title)` → `plot_relperm(config, history, output_dir, title, relperm=simulator.relperm)`; комментарий над ним дополнить: «ОФП — объект решателя (DEBT-011), а не пересобранная фабрикой копия».
4. Без решателя — публичная фабрика (после шага 1 имена уже `create_*`): `examples/two_phase_analytics.py::_build_relperm` (зовёт `create_relperm`) **пока остаётся** — на неё ссылается запасная ветка `predict_saturation`; удаляет её шаг 6 вместе с переносом. `examples/relperm_plot.py` (`:95`, `:215`) и `examples/pvt_plot.py::_get_pvt` (`:90`) — уже `create_*`.
5. `examples/temperature_asymptotics.py`: удалить `_pvt_of` (`:35-41`). `examples/pvt_plot.py`: удалить импорт `from temperature_asymptotics import _pvt_of` и комментарий над ним (`:75-77`); в `_get_pvt` — `return simulator.pvt`.
6. `examples/verify_balance_vs_solver.py:31` — убрать `str(_EXAMPLES / "03_standing_corey")` из кортежа путей (запись реестра «Попутно из DEBT-012»: из этой папки ничего не импортируется). `self._grid`, `self._ext_properties` внутри подменённого метода решателя — доступ объекта к своим полям, остаётся.
7. Тестовые заглушки решателя:
   - `tests/test_rs_analytics.py:73`: `sim = SimpleNamespace(_energy=SimpleNamespace(_pvt=pvt))` → `sim = SimpleNamespace(pvt=pvt)`;
   - `tests/test_examples.py:1993-1995`: комментарий → «closed_form берёт PVT и ОФП как simulator.pvt, simulator.relperm (_prepare)»; заглушка → `types.SimpleNamespace(pvt=_pvt_of_config(cfg), relperm=create_relperm(cfg))` (импорт `from gpn_multiphase_solver.factory import create_relperm` в начале теста).
8. `tests/test_examples.py:93-95`: `"grid": simulator.grid,`; комментарий над `"config"` → «конфиг примера — для проверок, которым он нужен» (прежний про `compute_balance` и FEAT-016 устарел с DEBT-013).
9. Страж в `tests/test_example_scripts.py` — в конец файла:
   ```python
   # ── Приватный доступ (DEBT-011) ──────────────────────────────

   # self и cls — доступ объекта к собственным полям: подменённый метод
   # решателя в verify_balance_vs_solver.py работает внутри его класса.
   _OWN = {"self", "cls"}


   def _private_access(tree: ast.AST) -> list[str]:
       """Обращения .имя к приватным полям чужих объектов и from <пакет> import _имя."""
       found = []
       for node in ast.walk(tree):
           if (isinstance(node, ast.Attribute) and node.attr.startswith("_")
                   and not node.attr.startswith("__")
                   and not (isinstance(node.value, ast.Name)
                            and node.value.id in _OWN)):
               found.append(f"строка {node.lineno}: .{node.attr}")
           elif (isinstance(node, ast.ImportFrom) and node.module
                 and node.module.split(".")[0] in CHECKED_PACKAGES):
               found += [f"строка {node.lineno}: from {node.module} import {a.name}"
                         for a in node.names if a.name.startswith("_")]
       return found


   @pytest.mark.parametrize("script", EXAMPLE_SCRIPTS)
   def test_no_private_solver_access(script):
       """Скрипт examples/ берёт объекты задачи через публичный интерфейс пакета (DEBT-011).

       Примеры передаются заказчику как образец работы с библиотекой:
       sim._energy._pvt в примере стал бы интерфейсом, который нельзя
       менять. Ловится .имя у чужого объекта (sim._grid, tpa._build_relperm)
       и from gpn_multiphase_solver... import _имя. Импорт приватных имён
       между модулями examples/ (_resolve_example) — их внутреннее дело
       до FEAT-030 и не ловится.
       """
       tree = ast.parse((EXAMPLES_DIR / script).read_text(encoding="utf-8"))
       found = _private_access(tree)
       assert not found, f"{script}: приватный доступ — {found}"
   ```
   В докстринге модуля строку «Не ловится: атрибуты объектов (sim._energy._rock), типы аргументов.» заменить на «Приватные атрибуты объектов ловит test_no_private_solver_access (DEBT-011); типы аргументов не ловятся.»
10. Проверка полноты:
    ```powershell
    git grep -n -P "_energy\._(pvt|rock)|\b(sim|simulator)\._grid|_build_relperm|_pvt_of\b" -- examples tests
    ```
    Остаются только белый ящик п. 1, `test_public_api.py` и `_build_relperm` внутри `examples/two_phase_analytics.py` (определение и два вызова — до шага 6).

**Проверка после шага:**
- Регресс: быстрый. Ожидание: N0f + 4 + число скриптов `examples/` (46 на 2026-10-11).
- Точечно медленные — заглушка `test_closed_form_hooks_run_for_rate_control` (считает только пример 15):
  ```powershell
  & $PY -m pytest tests/test_examples.py -k "closed_form_hooks_run_for_rate_control" -q
  ```

**Подводные камни:** раздел 2.5, «Тестовые заглушки», «Медленные тесты». Страж (`_private_access`) до правок п. 1–7 падает на 21 скрипте — так и задумано; писать его можно первым и идти по списку его отказов.

**Зависимости:** требует шаг 2; блокирует шаги 4–11.

**Оценка:** ~60 строк в ~30 файлах, ~45 мин.

---

### Шаг 4: невязки балансов энергии и массы — в ядро

**Цель:** ряды баланса энергии и массы (члены, невязка, её нормировка) считаются функциями пакета рядом с накопителями.

**Файлы:** `numerical_solver/gpn_multiphase_solver/energy/balance.py`, `numerical_solver/gpn_multiphase_solver/mass_balance.py`, `numerical_solver/examples/energy_balance.py`, `numerical_solver/examples/mass_balance.py`, `numerical_solver/examples/energy_balance_convergence.py`, `numerical_solver/examples/check_energy_balance_all.py`, `numerical_solver/examples/verify_balance_vs_solver.py`, `numerical_solver/tests/test_energy_balance_examples.py`, `numerical_solver/tests/test_examples.py`, `numerical_solver/tests/test_mass_balance.py`, `numerical_solver/tests/test_public_api.py`.

**Контекст:** накопители членов в ядре с DEBT-013 и DEBT-039, но сборка невязки — в `examples/`. Пользователь пакета получает `history.balance` — сырые суммы — без определения невязки. А нормировка нетривиальна (на сумму модулей всех членов, а не на $\max(|\Delta E|, |\Sigma|)$ — комментарий `examples/energy_balance.py:102-107`).

**Что сделать:**
1. `energy/balance.py` — функция в конец файла (тело — `examples/energy_balance.py:93-113` без изменений, `_CUMULATIVE` → `CUMULATIVE_KEYS`; кортежи совпадают поэлементно и по порядку — сверено):
   ```python
   # ── Ряды баланса по истории ──────────────────────────────


   def compute_energy_balance(history) -> dict:
       """Ряды баланса энергии по накопленным на подшагах членам (DEBT-013, DEBT-011).

       Возвращает dict массивов длины len(history.times): t, шесть членов
       CUMULATIVE_KEYS, total, residual, rel_residual. Набор ключей полный
       при любом конфиге: отсутствующие в сценарии члены — нулевые массивы.
       """
       out = {k: np.array([s[k] for s in history.balance])
              for k in CUMULATIVE_KEYS}
       out["t"] = np.array(history.times)

       # Производные величины: считаются из накопленных, а не хранятся.
       out["total"] = (out["cum_adiab"] + out["cum_conv"] + out["cum_jt"]
                       + out["cum_deg"] + out["cum_cond"])
       out["residual"] = out["delta_E"] - out["total"]

       # (комментарий о нормировке — дословно из examples/energy_balance.py:102-107)
       scale = sum(np.abs(out[k]) for k in CUMULATIVE_KEYS)
       # t = 0: все члены нулевые, делить не на что.
       scale = np.where(scale < 1e-10, 1.0, scale)
       out["rel_residual"] = np.abs(out["residual"]) / scale

       return out
   ```
   Комментарий у `CUMULATIVE_KEYS` (`:136-137`): «…считаются из этих шести при сборке (compute_energy_balance ниже).»
2. `mass_balance.py` — `import numpy as np` после `from typing import TYPE_CHECKING`; функция `compute_mass_balance(history)` в конец файла — дословно `examples/mass_balance.py:56-81`, докстринг тот же (`"""Баланс массы по снимкам истории; None — масса не сохраняется. Ур. (eq:residual_oil)."""`); в комментарии о нормировке `(energy_balance.compute_balance)` → `(energy.balance.compute_energy_balance)`. Докстринг модуля, строки 20–21: «Сборка невязки — compute_mass_balance ниже; график и печать — examples/mass_balance.py.»
3. `examples/energy_balance.py`: удалить `_CUMULATIVE` (`:63-68`) и `compute_balance` (`:71-113`); импорт `from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402`; в `plot_energy_balance` и `report_energy_balance` — `bal = compute_energy_balance(history)`; докстринг модуля, блок «Три функции», — «compute_energy_balance (ядро) собирает ряды; здесь plot_energy_balance — PNG и печать, report_energy_balance — обёртка для run_example»; «ФИЗИКА ЖИВЁТ В ЯДРЕ» — дописать «…и сборка рядов: energy/balance.py::compute_energy_balance».
4. `examples/mass_balance.py`: удалить `compute_mass_balance`; импорт `from gpn_multiphase_solver.mass_balance import MASS_KEYS` → `from gpn_multiphase_solver.mass_balance import compute_mass_balance`, если `MASS_KEYS` больше не используется (проверить grep), иначе оба имени; абзац «ФИЗИКА ЖИВЁТ В ЯДРЕ» — «…сборку рядов — compute_mass_balance».
5. Вызовы `compute_balance(history, <grid>, <config>)` → `compute_energy_balance(history)` с импортом из `gpn_multiphase_solver.energy.balance`:
   - `examples/energy_balance_convergence.py:57, 89` (комментарий над импортом поправить: «Ряды баланса — из ядра»);
   - `examples/check_energy_balance_all.py:35, 73`;
   - `examples/verify_balance_vs_solver.py:148` (`eb.compute_balance(...)`; если `eb` больше не нужен — убрать `import energy_balance as eb`); в докстринге «сравниваем с тем, что считает compute_balance по истории» → «compute_energy_balance»;
   - `tests/test_energy_balance_examples.py:32, 61, 145` (+ упоминание в тексте `:123` → `compute_energy_balance`; номера на `f89c08b`);
   - `tests/test_examples.py:694-699, 745-750, 769, 780-787, 2827, 2836-2839` (номера `test_examples.py` здесь и ниже — на `73ef031`);
   - `from mass_balance import compute_mass_balance` → `from gpn_multiphase_solver.mass_balance import compute_mass_balance`: `tests/test_examples.py:719`, `tests/test_mass_balance.py:35` (если после этого `test_mass_balance.py` ничего не берёт из `examples/` — вставку `sys.path` и её комментарий убрать).
   ```powershell
   git grep -n -P "\bcompute_balance\b|from mass_balance import" -- examples tests   # пусто
   ```
6. Тесты в `tests/test_public_api.py`:
   ```python
   from gpn_multiphase_solver.energy.balance import CUMULATIVE_KEYS, compute_energy_balance
   from gpn_multiphase_solver.mass_balance import compute_mass_balance
   from gpn_multiphase_solver.state import SimulationHistory


   # ── Ряды балансов ────────────────────────────────────────────

   def _energy_history():
       """История из двух записей: нулевая и с членами, где ΔE ≠ Σ источников на 0.5 Дж."""
       zero = dict.fromkeys(CUMULATIVE_KEYS, 0.0)
       last = dict(delta_E=5.0, cum_adiab=1.0, cum_conv=2.0, cum_jt=-1.0,
                   cum_deg=0.5, cum_cond=2.0)
       return SimulationHistory(times=[0.0, 10.0], balance=[zero, last])


   def test_compute_energy_balance_residual_and_scale():
       """Невязка ΔE − Σ, нормировка на сумму модулей всех членов, t = 0 без деления на ноль.

       Σ источников = 1 + 2 − 1 + 0.5 + 2 = 4.5 → невязка 0.5 Дж;
       сумма модулей = 5 + 1 + 2 + 1 + 0.5 + 2 = 11.5.
       """
       bal = compute_energy_balance(_energy_history())
       assert set(bal) == set(CUMULATIVE_KEYS) | {"t", "total", "residual", "rel_residual"}
       assert bal["total"][1] == 4.5 and bal["residual"][1] == 0.5
       assert bal["rel_residual"][1] == pytest.approx(0.5 / 11.5, rel=1e-15)
       assert bal["rel_residual"][0] == 0.0


   def test_compute_mass_balance_none_without_inventories():
       """Решатель без запаса компонентов (двойники): баланса массы нет — None, а не ошибка."""
       assert compute_mass_balance(SimulationHistory()) is None
       assert compute_mass_balance(SimulationHistory(mass_balance=[None])) is None


   def test_compute_mass_balance_closes():
       """Запас нефти 100 → 90 м³ст, добыто 12, притекло 2: ΔM + ∫G[N] − ∫G[0] = −10 − 2 + 12 = 0.

       Знак G — от скважины (CLAUDE.md, конвенция знаков): добыча даёт
       cum_o_well < 0, приток с контура — cum_o_ext < 0. У газа все члены
       нулевые — нормировка 1, невязка 0.
       """
       snaps = [dict(M_o=100.0, M_g=0.0, cum_o_well=0.0, cum_o_ext=0.0,
                     cum_g_well=0.0, cum_g_ext=0.0),
                dict(M_o=90.0, M_g=0.0, cum_o_well=-12.0, cum_o_ext=-2.0,
                     cum_g_well=0.0, cum_g_ext=0.0)]
       bal = compute_mass_balance(SimulationHistory(times=[0.0, 1.0], mass_balance=snaps))
       assert bal["residual_o"][1] == 0.0 and bal["rel_residual_o"][1] == 0.0
       assert bal["prod_o"][1] == 12.0 and bal["inflow_o"][1] == 2.0
       assert bal["rel_residual_g"][1] == 0.0
   ```

**Проверка после шага:**
- Регресс: быстрый. Ожидание: + 3 к предыдущему.
- `git grep` п. 5 пуст.
- Тесты баланса на фикстуре `results` (медленные) — в полном прогоне шага 11.

**Подводные камни:** порядок суммирования в `scale` сохранён (`CUMULATIVE_KEYS` = `_CUMULATIVE`) — побайтность рядов; раздел 2.5, «Медленные тесты».

**Зависимости:** требует шаг 3 (там убран `sim._grid` в вызовах); блокирует шаг 9.

**Оценка:** ~70 строк переезжает, ~60 строк тестов, ~30 мин.

**Точка коммита:** `refactor: ряды балансов энергии и массы в ядре — compute_energy_balance, compute_mass_balance (DEBT-011)`.

---

### Шаг 5: `diagnostics/closed_form.py` — замкнутое решение стационара

**Цель:** замкнутое решение двухфазного стационара — функции пакета.

**Файлы:** `numerical_solver/gpn_multiphase_solver/diagnostics/__init__.py` (новый), `numerical_solver/gpn_multiphase_solver/diagnostics/closed_form.py` (новый), `numerical_solver/examples/closed_form.py`, `numerical_solver/examples/two_phase_analytics.py`, `numerical_solver/examples/04_table_table/grid_convergence.py`, `numerical_solver/examples/04a_high_gas_saturation/grid_convergence.py`, `numerical_solver/examples/05_standing_table_rp/closed_form_convergence.py`, `numerical_solver/tests/test_examples.py`.

**Контекст:** `examples/closed_form.py` — вывод (докстринг `:1-78`: стационарность потоков, замыкание GOR = $R_{s,0}$, ур. (1)–(3), фронт по $p = p_b$) и функции от `(config, pvt, relperm, r)`; от решателя ничего не берут. Наложения на профили и печать — часть конвейера `run_example` (FEAT-030), остаются.

**Что сделать:**
1. `diagnostics/__init__.py`:
   ```python
   """Проверки расчёта по замкнутым формулам и равновесиям Black Oil (DEBT-011).

   closed_form — замкнутое решение двухфазного стационара (GOR = R_s,0);
   two_phase   — аналитика двухфазного стационара: GOR, S_g, Дюпюи, фронт;
   rs          — равновесие R_s без кинетики, радиус изобары p_b;
   temperature — однофазная асимптотика температуры.

   Функции принимают config, history, grid, pvt, relperm и ничего не
   печатают и не рисуют. Печать отчётов и рисунки примеров — examples/.
   """
   ```
2. `diagnostics/closed_form.py`: докстринг модуля — `examples/closed_form.py:1-78` с первой строкой «Замкнутое решение стационарной двухфазной задачи (DEBT-011: из examples/closed_form.py).» и без упоминания примеров как места реализации. Затем импорты (`numpy`, `quad`, `solve_ivp`, `brentq`) и дословно `:87-248`: `_kr_max_Sg` → **`kr_max_Sg`** (имя без подчёркивания: её берёт `two_phase.py`; вызов в `Closure.__init__` поправить), `Closure`, `_CACHE`, `_rate_closed`, `stationary_pwf`, `solve_closed`, `_front_radius`. Плюс `saturation_from_numeric` с новой сигнатурой — PVT и ОФП аргументами вместо решателя:
   ```python
   def saturation_from_numeric(config, history, pvt, relperm):
       """Sg из замыкания (1) при ЧИСЛЕННОМ давлении последней записи, [N].

       (абзацы докстринга examples/closed_form.py:277-287 — дословно)
       """
       clo = Closure(pvt, relperm, config.initial_conditions.Rs0)
       return np.array([clo.Sg(pp) for pp in history.states[-1].p])
   ```
3. `examples/closed_form.py`: удалить перенесённое; докстринг модуля:
   ```python
   """Наложения замкнутого решения на профили и его сверка с расчётом — для run_example.

   Само решение (вывод, ур. (1)–(3), фронт по p = p_b) —
   gpn_multiphase_solver.diagnostics.closed_form (DEBT-011). Здесь —
   хуки наложений для профилей p и S_g и печать сверки report_closed.
   """
   ```
   Импорты: `import numpy as np`, `from gpn_multiphase_solver.diagnostics.closed_form import saturation_from_numeric, solve_closed`. `_prepare` (после шага 3): `return solve_closed(config, simulator.pvt, simulator.relperm, grid.r_centers)`. `report_closed`: `Sg_at_p_num = saturation_from_numeric(config, history, simulator.pvt, simulator.relperm)`. `make_overlay_*` — без изменений. Заголовок `# ── Хуки для example_runner ──` остаётся.
4. Вызовы:
   - `examples/two_phase_analytics.py:213-222` (блок комментария и `from closed_form import Closure, solve_closed, _CACHE`) → `from gpn_multiphase_solver.diagnostics.closed_form import solve_closed  # noqa: E402` с однострочным комментарием «Замкнутое решение — ядро пакета (DEBT-011)». `Closure`, `_CACHE` здесь не используются (проверено grep: `tpa.Closure`, `tpa._CACHE` нигде нет);
   - `examples/04_table_table/grid_convergence.py:58`, `examples/04a_high_gas_saturation/grid_convergence.py:52` — `from closed_form import solve_closed` → `from gpn_multiphase_solver.diagnostics.closed_form import solve_closed`;
   - `examples/05_standing_table_rp/closed_form_convergence.py:89` — `tpa.solve_closed(...)` → `solve_closed(...)` с тем же импортом; если `tpa` в файле больше не нужен — убрать `import two_phase_analytics as tpa`;
   - `tests/test_examples.py:1577` (`from closed_form import Closure`) → `from gpn_multiphase_solver.diagnostics.closed_form import Closure`; `:1776` → то же для `solve_closed`;
   - `tests/test_examples.py:1809-1814`, помощник `_closed_form()`: его зовут и для перенесённых функций (`stationary_pwf`, `solve_closed` — `:1853-1878`), и для оставшихся (`make_overlay_pressure`, `report_closed` — `:1999, 2005`). Завести второй:
     ```python
     def _closed_form_core():
         """Замкнутое решение — модуль пакета (DEBT-011)."""
         from gpn_multiphase_solver.diagnostics import closed_form
         return closed_form
     ```
     `:1853, 1864, 1872, 1878` → `_closed_form_core()`; `_closed_form()` — для наложений и `report_closed`, докстринг «Наложения и сверка — examples/closed_form.py».
   ```powershell
   git grep -n -E "from closed_form import|tpa\.solve_closed|_kr_max_Sg" -- examples tests   # пусто
   ```

**Проверка после шага:**
- Регресс: быстрый.
- Точечно: `& $PY -m pytest tests/test_examples.py -k "closed_form or stationary or rate_control" -q` (считает 04, 05, 15 — несколько минут).
- `& $PY -c "import gpn_multiphase_solver.diagnostics.closed_form"`.

**Подводные камни:** `two_phase_analytics.py` в шаге 6 сам переходит на `kr_max_Sg` — до шага 6 его копия `_kr_max_Sg` ещё жива; это нормально.

**Зависимости:** требует шаг 3; блокирует шаг 6.

**Оценка:** ~170 строк переезжает, ~30 строк правок, ~30 мин.

---

### Шаг 6: `diagnostics/two_phase.py` — аналитика двухфазного стационара

**Цель:** проверки двухфазного стационара (GOR, $S_g$ из замыкания, Дюпюи, фронт) — функции пакета.

**Файлы:** `numerical_solver/gpn_multiphase_solver/diagnostics/two_phase.py` (новый), `numerical_solver/examples/two_phase_analytics.py`, `numerical_solver/examples/03_standing_corey/main.py`, `numerical_solver/examples/05_standing_table_rp/main.py`.

**Что сделать:**
1. `diagnostics/two_phase.py`: докстринг — `examples/two_phase_analytics.py:1-82` (теория A–E, «ЧТО ПОКАЗЫВАЕТ СРАВНЕНИЕ ПРИМЕРОВ 03 И 05», «ПРИМЕНИМОСТЬ»), с правками: первая строка «Аналитика двухфазного стационара (DEBT-011: из examples/two_phase_analytics.py).»; в пункте B «она берётся у фабрики» → «её передаёт вызывающий — тот объект, которым считалась задача (`Simulator.relperm`)»; в пункте E «Реализация — в общем модуле examples/closed_form.py, здесь реэкспорт» → «Реализация — diagnostics/closed_form.py». Блок «Запуск для конкретного примера» не переносить.
   Код: `import numpy as np`, `from scipy.optimize import brentq`, `from .closed_form import kr_max_Sg`; дословно `SG_EPS` с комментарием (`:102-105`), блок A и B (`:133-210`: `compute_gor`, `compute_free_gas_prediction`, `predict_saturation`) и блок C, D (`:225-301`: `dupuit_check`, `degassing_front`). Блок `:213-222` (комментарий и реэкспорт `from closed_form import Closure, solve_closed, _CACHE`) **не переносить** — пакет не импортирует `examples/`, страж шага 12 это поймал бы. Копию `_kr_max_Sg` (`:121-130`) не переносить: в `predict_saturation` — `S_hi = kr_max_Sg(relperm)` (тело функций одинаковое — сверено). `predict_saturation(history, config, pvt, relperm)` — ОФП **обязательна**: ветка `if relperm is None: relperm = _build_relperm(config)` удаляется (пакет не собирает ОФП молча; единственный вызывающий, `report`, её передаёт).
2. `examples/two_phase_analytics.py`: оставить `report`, `_resolve_example`, `__main__` и вставку `sys.path` (`:95-100`). `_build_relperm` удалить; в `report` вместо `relperm = _build_relperm(config)` (`:321`):
   ```python
       # ОФП по конфигу — тем же конструктором, что фабрика собирает решатель
       # (у report решателя нет: сигнатура общая для main.py 03–05 и CLI)
       from gpn_multiphase_solver.factory import create_relperm
       relperm = create_relperm(config)
   ```
   Докстринг:
   ```python
   """Печать аналитики двухфазного стационара для примеров (пункты A–E).

   Проверки — gpn_multiphase_solver.diagnostics.two_phase и .closed_form
   (DEBT-011), там же их вывод. Здесь — сводный отчёт report и CLI.

   Запуск для конкретного примера:
       cd numerical_solver
       .venv\\Scripts\\python examples\\two_phase_analytics.py 03
   """
   ```
   Импорты: `from gpn_multiphase_solver.diagnostics.two_phase import (compute_free_gas_prediction, compute_gor, degassing_front, dupuit_check, predict_saturation)` и `solve_closed` (шаг 5). `import numpy as np` — остаётся (`report` его использует); `from scipy.optimize import brentq` — убрать.
3. `main.py` — имена из пакета вместо `tpa.`:
   - `examples/03_standing_corey/main.py:68, 73` — `tpa.SG_EPS`, `tpa.degassing_front` (внутри `overlay_temperature`) → `from gpn_multiphase_solver.diagnostics.two_phase import SG_EPS, degassing_front` в начале функции (как там импортируется `load_config`); `tpa.report` (`:102`) — остаётся;
   - `examples/05_standing_table_rp/main.py:59, 62` — то же, импорт — к остальным импортам файла (`:39-45`).
   ```powershell
   git grep -n -E "tpa\.(SG_EPS|degassing_front|dupuit_check|predict_saturation|compute_gor|compute_free_gas_prediction|_kr_max_Sg)" -- examples tests   # пусто
   ```

**Проверка после шага:**
- Регресс: быстрый (страж DEBT-046 проверит, что `tpa.report` на месте).
- Точечно: `& $PY -m pytest tests/test_examples.py -k "two_phase or gor or dupuit or front" -q`.

**Зависимости:** требует шаг 5.

**Оценка:** ~170 строк переезжает, ~20 строк правок, ~25 мин.

---

### Шаг 7: `diagnostics/rs.py` — равновесие $R_s$

**Цель:** проверка равновесия $R_s$ и радиус изобары $p_b$ — функции пакета.

**Файлы:** `numerical_solver/gpn_multiphase_solver/diagnostics/rs.py` (новый), `numerical_solver/examples/rs_analytics.py`, `numerical_solver/examples/pvt_plot.py` (ссылки в комментариях), `numerical_solver/tests/test_rs_analytics.py`, `numerical_solver/tests/test_examples.py`.

**Что сделать:**
1. `diagnostics/rs.py`: докстринг — `examples/rs_analytics.py:1-56` (первая строка «Равновесие R_s в модели Black Oil (DEBT-011: из examples/rs_analytics.py).»). Код дословно (строки — на `73ef031`): `SG_GAS` с комментарием (`:62-67`), `rs_expected` (`:70-77`), `rs_error` (`:80-93`), блок комментария о допуске (`:96-102`) и `rs_supersaturation(history, pvt, tol)` (`:103-115`), `_degassed_cells` → **`degassed_cells`** (`:118-122`; берут `_draw_rs` и `report_rs` из `examples/`), `front_radius` (`:125-…`, внутри — вызов `degassed_cells`). В докстринге `rs_expected` «pvt_plot._physical_rs сверяется с ней побитово» → «examples/pvt_plot._physical_rs сверяется с ней побитово».
2. `examples/rs_analytics.py`: оставить `make_overlay_rs`, `_draw_rs`, `report_rs` (в нём `tol = config.numerics.rs_switch_tol` — без изменений). Докстринг:
   ```python
   """Наложение R_s^eq(p) на профиль газосодержания и печать проверки R_s — для run_example.

   Проверка (равенство в ячейках со свободным газом, неравенство с допуском
   решателя без газа) — gpn_multiphase_solver.diagnostics.rs (DEBT-011), там
   же её обоснование.
   """
   ```
   Импорты из `gpn_multiphase_solver.diagnostics.rs`: `SG_GAS`, `degassed_cells`, `front_radius`, `rs_error`, `rs_supersaturation`. Вызовы `_degassed_cells(` → `degassed_cells(`.
3. `tests/test_rs_analytics.py`: модуль `examples/rs_analytics` по-прежнему нужен (`report_rs` — `:64`, `_draw_rs` — `:74`; тесты допуска `:170-203` идут через `report_rs` и не меняются). Из перенесённого тест берёт одно имя:
   ```python
   from gpn_multiphase_solver.diagnostics import rs as rs_core  # noqa: E402
   ```
   `rs_analytics.rs_expected` (`:119`) → `rs_core.rs_expected`. Докстринг модуля теста (строки 1–5): «…общего модуля examples/rs_analytics.py» → «…diagnostics/rs.py (проверка) и examples/rs_analytics.py (печать, наложение)».
4. `tests/test_examples.py:1035` — `from rs_analytics import rs_expected` → `from gpn_multiphase_solver.diagnostics.rs import rs_expected`; текст `:1026` — «rs_analytics.rs_expected» → «diagnostics.rs.rs_expected». `:887` (`report_rs`) — без изменений.
5. `examples/pvt_plot.py:101` (докстринг `_physical_rs`): «Та же формула, что в rs_analytics.rs_expected» → «…в gpn_multiphase_solver.diagnostics.rs.rs_expected».
   ```powershell
   git grep -n -E "_degassed_cells|rs_analytics\.(rs_expected|rs_error|rs_supersaturation|front_radius|SG_GAS)|from rs_analytics import (rs_|front|SG_)" -- examples tests   # пусто
   ```

**Проверка после шага:**
- Регресс: быстрый (`test_rs_analytics.py` — в нём).
- Точечно: `& $PY -m pytest tests/test_examples.py -k "rs_" -q`.

**Зависимости:** требует шаг 3 (заглушка `SimpleNamespace(pvt=…)`).

**Оценка:** ~100 строк переезжает, ~20 строк правок, ~25 мин.

---

### Шаг 8: `diagnostics/temperature.py` — однофазная асимптотика $T$

**Цель:** $T = T_{ext} + \mu_{JT,o}(p - p_0)$ — функция пакета.

**Файлы:** `numerical_solver/gpn_multiphase_solver/diagnostics/temperature.py` (новый), `numerical_solver/examples/temperature_asymptotics.py`, `numerical_solver/examples/02_single_phase_jt/main.py`, `numerical_solver/examples/03_standing_corey/main.py`, `numerical_solver/examples/05_standing_table_rp/main.py`, `numerical_solver/tests/test_examples.py`, `numerical_solver/tests/test_example_scripts.py` (докстринг).

**Что сделать:**
1. `diagnostics/temperature.py`:
   ```python
   """Однофазная асимптотика температуры (DEBT-011: из examples/temperature_asymptotics.py).

   (абзацы examples/temperature_asymptotics.py:3-20 — стационарный предел,
   «ДВУХФАЗНОЙ АСИМПТОТИКИ НЕТ», чем проверяется двухфазная зона)
   """


   def single_phase_asymptote(config, history):
       (дословно :44-63, докстринг тоже)
   ```
2. `examples/temperature_asymptotics.py`: удалить `single_phase_asymptote` (и `_pvt_of`, если шаг 3 его ещё не удалил); импорт `from gpn_multiphase_solver.diagnostics.temperature import single_phase_asymptote`; докстринг — «Печать однофазной проверки температуры для run_example; асимптотика — gpn_multiphase_solver.diagnostics.temperature (DEBT-011)» + блок «Запуск». `SG_EPS`, `report_asymptotics`, `__main__` — остаются. Импорт пакета стоит на уровне модуля, а модуль кладёт `sys.path` только в `__main__` (`:100-104`). Проверить, что `import temperature_asymptotics` из `example_runner` по-прежнему работает: пакет установлен, путь не нужен.
3. `main.py`: `ta.single_phase_asymptote` → `single_phase_asymptote` с импортом из пакета:
   - `examples/02_single_phase_jt/main.py:47` (импорт) и `:208` (вызов); если `ta` больше не используется — импорт `import temperature_asymptotics as ta` убрать;
   - `examples/03_standing_corey/main.py:58, 66` — внутри `overlay_temperature`: `import temperature_asymptotics as ta` → `from gpn_multiphase_solver.diagnostics.temperature import single_phase_asymptote`;
   - `examples/05_standing_table_rp/main.py:45, 58` — то же на уровне модуля.
4. `tests/test_examples.py:382-387` — `_asymptotics_module()`: `:410`, `:453` зовут через него только `single_phase_asymptote` → вернуть модуль пакета:
   ```python
   def _asymptotics_module():
       """Однофазная асимптотика — модуль пакета (DEBT-011)."""
       from gpn_multiphase_solver.diagnostics import temperature
       return temperature
   ```
   Если в файле через помощник зовут и `report_asymptotics` (grep `_asymptotics_module()\.report`) — для него оставить модуль `examples/`.
5. `tests/test_example_scripts.py`, докстринг, пункт (в) и комментарий `:167`: пример `ta.single_phase_asymptote` → `tpa.report` (скрипты больше так не обращаются).
   ```powershell
   git grep -n -P "ta\.single_phase_asymptote|_pvt_of\b" -- examples tests   # пусто (кроме докстринга теста, если он оставлен)
   ```

**Проверка после шага:**
- Регресс: быстрый.
- Точечно: `& $PY -m pytest tests/test_examples.py -k "asymptot" -q`.

**Зависимости:** требует шаг 3.

**Оценка:** ~40 строк переезжает, ~15 строк правок, ~15 мин.

**Точка коммита:** `refactor: диагностика в пакете — gpn_multiphase_solver/diagnostics (замкнутое решение, двухфазный стационар, R_s, асимптотика T) (DEBT-011)`.

---

### Шаг 9: рисунки балансов — `io/output.py`

**Цель:** рисунки баланса энергии и массы — функции пакета; в `examples/` остаются запись PNG и печать.

**Файлы:** `numerical_solver/gpn_multiphase_solver/io/output.py`, `numerical_solver/examples/energy_balance.py`, `numerical_solver/examples/mass_balance.py`, `numerical_solver/tests/test_public_api.py`.

**Контекст:** образец — `plot_pvt_properties` (FEAT-017): функция пакета рисует на переданных осях или создаёт их, возвращает оси, файлов не пишет и не печатает. Чтобы PNG совпали побайтно, последовательность вызовов `matplotlib` сохраняется без перестановок: фигура → кривые и оформление осей (ядро) → заголовок фигуры, `tight_layout`, сохранение (обёртка).

**Изменения:**

`io/output.py` — в шапку-перечень модуля добавить строки:
```
  plot_energy_balance_series — баланс энергии во времени: члены и невязка
  plot_mass_balance_series   — баланс массы нефти и газа во времени
```
Функции — после `plot_2d_map`, перед блоком PVT:
```python
def plot_energy_balance_series(bal: dict, axes=None, title: str = "Баланс энергии"):
    """Баланс энергии во времени: члены и относительная невязка (DEBT-013, DEBT-011).

    bal   — ряды compute_energy_balance (energy/balance.py)
    axes  — пара осей (члены, невязка); None — создаются: 9×8 дюймов,
            общая ось t, высоты 3:1
    title — заголовок верхней панели

    Возвращает axes. Файл не пишет и не печатает — как остальные plot_*.
    """
    import matplotlib.pyplot as plt

    if axes is None:
        _, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
    ax1, ax2 = axes
    t_days = bal["t"] * S_TO_DAY    # время на графиках — в сутках (FEAT-022)

    (дословно examples/energy_balance.py:124-152: семь кривых ax1 с комментарием
     о кондукции, подписи, легенда; ax1.set_title(title) вместо f-строки с
     именем примера; сетка; ticklabel_format; панель невязки ax2 целиком)

    return axes
```
```python
def plot_mass_balance_series(bal: dict, axes=None):
    """Баланс массы нефти и газа во времени: члены и невязка. Ур. (eq:residual_oil), (eq:residual_gas).

    bal  — ряды compute_mass_balance (mass_balance.py)
    axes — сетка 2×2 (столбцы — нефть, газ; строки — члены, невязка);
           None — создаётся: 13×8 дюймов, общая ось t, высоты 3:1

    Возвращает axes. Файл не пишет и не печатает.
    """
    import matplotlib.pyplot as plt

    if axes is None:
        _, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
    axes = np.asarray(axes)
    t_days = bal["t"] * S_TO_DAY    # время на графиках — в сутках (FEAT-022)

    (комментарий «Две колонки, а не одни оси…» и цикл
     examples/mass_balance.py:99-122 — дословно)

    return axes
```

`examples/energy_balance.py`, `plot_energy_balance`:
```python
def plot_energy_balance(history, grid, config, output_dir: Path):
    """Построить график баланса энергии и вернуть финальную отн. невязку."""
    bal = compute_energy_balance(history)
    # Имя примера берём из пути к конфигу: модуль общий для всех примеров.
    axes = plot_energy_balance_series(
        bal, title=f"Баланс энергии — {Path(config.config_dir).name}")
    fig = axes[0].figure

    fig.tight_layout()
    (дальше без изменений: output_dir, save_figure, plt.close, печать)
```
Импорт `from gpn_multiphase_solver.io.output import plot_energy_balance_series  # noqa: E402`; `S_TO_DAY` здесь больше не нужен — убрать импорт, если не используется.

`examples/mass_balance.py`, `plot_mass_balance`:
```python
    bal = compute_mass_balance(history)
    if bal is None:
        (без изменений)
    axes = plot_mass_balance_series(bal)
    fig = axes[0, 0].figure
    # Имя примера — из пути к конфигу: модуль общий для всех примеров.
    fig.suptitle(f"Баланс массы компонентов — {Path(config.config_dir).name}")
    fig.tight_layout()
    (дальше без изменений)
```
Импорт `plot_mass_balance_series`; `S_TO_DAY`, `MASS_KEYS` — убрать, если не используются.

Тест в `tests/test_public_api.py`:
```python
from gpn_multiphase_solver.io.output import plot_energy_balance_series


def test_plot_energy_balance_series_draws_all_terms():
    """Семь кривых членов (ΔE, пять источников, их сумма) и одна кривая невязки; заголовок — аргумент."""
    axes = plot_energy_balance_series(compute_energy_balance(_energy_history()), title="T")
    try:
        assert len(axes[0].get_lines()) == 7
        assert len(axes[1].get_lines()) == 1
        assert axes[0].get_title() == "T"
    finally:
        plt.close(axes[0].figure)
```

**Проверка после шага:**
- Регресс: быстрый. Ожидание: + 1.
- Побайтность PNG — снимок шага 13 (`energy_balance.png`, `mass_balance.png` всех примеров).

**Подводные камни:** не переставлять вызовы оформления между ядром и обёрткой; `ax1.legend` — после всех кривых, как было.

**Зависимости:** требует шаг 4.

**Оценка:** ~60 строк переезжает, ~15 строк обёрток, ~25 мин.

---

### Шаг 10: кривые ОФП — `io/output.py`

**Цель:** рисунок ОФП с рабочим диапазоном и узлы табличной ОФП — функции пакета.

**Файлы:** `numerical_solver/gpn_multiphase_solver/io/output.py`, `numerical_solver/examples/relperm_plot.py`, `numerical_solver/tests/test_examples.py`, `numerical_solver/tests/test_public_api.py`.

**Изменения:**

`io/output.py` — импорт на уровне модуля `from ..pvt.prototype_adapter import PrototypeRPAdapter` (в `pvt/` нет импорта `io` — цикла нет); в перечень шапки:
```
  plot_relperm_curves  — кривые ОФП и рабочий диапазон S_g расчёта
  relperm_table_nodes  — узлы табличной ОФП для маркеров
```
Функции:
```python
def relperm_table_nodes(relperm):
    """Узлы табличной ОФП (Sg, kro, krg); у аналитической модели — None (DEBT-006, DEBT-011)."""
    (тело examples/relperm_plot.py:_table_nodes, :49-59, — дословно, без локального импорта)


def plot_relperm_curves(relperm, sg_range, axes=None, title: str = ""):
    """Кривые ОФП и рабочий диапазон S_g расчёта: панель целиком и увеличение (DEBT-011).

    relperm  — RelPermModel: нужны kro, krg
    sg_range — (S_g,min, S_g,max) расчёта; S_g,max ≤ 1e-12 — расчёт
               однофазный, рисуется одна панель
    axes     — оси формы (1, n) как у plt.subplots(1, n, squeeze=False):
               n = 2 у двухфазного расчёта, 1 у однофазного; None — создаются
               (6.5·n × 5 дюймов)
    title    — заголовок первой панели

    Возвращает axes. Файл не пишет и не печатает.
    """
    import matplotlib.pyplot as plt

    Sg_lo, Sg_hi = float(sg_range[0]), float(sg_range[1])
    # Однофазный сценарий: газ не выделялся вовсе, увеличивать нечего.
    two_phase = Sg_hi > 1e-12

    nodes = relperm_table_nodes(relperm)
    S = np.linspace(0.0, 1.0, 1000)
    kro, krg = relperm.kro(S), relperm.krg(S)

    n_panels = 2 if two_phase else 1
    if axes is None:
        _, axes = plt.subplots(1, n_panels, figsize=(6.5 * n_panels, 5),
                               squeeze=False)
    axes = np.asarray(axes)
    ax1 = axes[0, 0]

    (дословно examples/relperm_plot.py:111-197 — панель 1, панель 2 с twinx;
     единственная правка — ax1.set_title(title, fontsize=9))

    return axes
```

`examples/relperm_plot.py`: удалить `_table_nodes`; импорт `from gpn_multiphase_solver.io.output import plot_relperm_curves  # noqa: E402`; `plot_relperm`:
```python
    if relperm is None:
        from gpn_multiphase_solver.factory import create_relperm
        relperm = create_relperm(config)

    axes = plot_relperm_curves(relperm, _sg_range(history),
                               title=f"{title}\nОФП — {_describe(config)}")
    fig = axes[0, 0].figure

    fig.tight_layout()
    (дальше без изменений: output_dir, save_figure, plt.close, return out)
```
Докстринг модуля: после абзаца о модели — «Само построение — gpn_multiphase_solver.io.output.plot_relperm_curves (DEBT-011); здесь подпись модели по конфигу, рабочий диапазон из истории, запись PNG и печать.»; фраза «через `factory._create_relperm`» (после шага 1 — `create_relperm`) → «объект решателя (`Simulator.relperm`) или фабрика (`create_relperm`)».

`tests/test_examples.py:1459-1478`: `_relperm_module()._table_nodes(...)` → `relperm_table_nodes(...)` с импортом `from gpn_multiphase_solver.io.output import relperm_table_nodes`; в тексте `:1459` «_table_nodes (relperm_plot.py)» → «relperm_table_nodes (io/output.py)». `_relperm_module()._sg_range`, `.report_relperm` — остаются.

Тест в `tests/test_public_api.py`:
```python
from gpn_multiphase_solver.io.output import plot_relperm_curves


@pytest.mark.parametrize("sg_max, n_panels", [(0.05, 2), (0.0, 1)])
def test_plot_relperm_curves_panels(sg_max, n_panels):
    """Двухфазный расчёт — две панели (целиком и увеличение), однофазный — одна."""
    rp = create_relperm(load_config(BASELINE))
    axes = plot_relperm_curves(rp, (0.0, sg_max), title="T")
    try:
        assert axes.shape == (1, n_panels)
        assert axes[0, 0].get_title() == "T"
    finally:
        plt.close(axes[0, 0].figure)
```

**Проверка после шага:**
- Регресс: быстрый. Ожидание: + 2.
- Точечно: `& $PY -m pytest tests/test_examples.py -k "relperm" -q`.

**Зависимости:** требует шаг 3.

**Оценка:** ~110 строк переезжает, ~15 строк обёртки, ~25 мин.

---

### Шаг 11: узлы таблиц PVT — `io/output.py`

**Цель:** пользователь пакета строит рисунок PVT с узлами таблиц без знания внутренних полей прототипа.

**Файлы:** `numerical_solver/gpn_multiphase_solver/io/output.py`, `numerical_solver/examples/pvt_plot.py`, `numerical_solver/tests/test_examples.py`, `numerical_solver/tests/test_public_api.py`.

**Контекст:** `plot_pvt_properties` уже в пакете (FEAT-017), но её аргумент `table_nodes` собирает `examples/pvt_plot.py::_pvt_table_nodes` из полей `BlackOilPVT` прототипа в барах (`gp`, `pb`, `rs_values`, `branches`). Без этой функции пакетный рисунок PVT для таблиц остаётся без узлов.

**Изменения:**
`io/output.py` — импорты на уровне модуля `from ..pvt.table_full import TableFullPVT`, `from ..units import BAR_TO_PA, S_TO_DAY` (вместо `from ..units import S_TO_DAY`); в перечень шапки — `pvt_table_nodes — узлы табличного PVT для маркеров plot_pvt_properties`; функция перед `plot_pvt_properties`:
```python
def pvt_table_nodes(pvt, Rs0: float):
    """Узлы табличного PVT в Па для plot_pvt_properties; у аналитического PVT — None (DEBT-011).

    (абзацы докстринга examples/pvt_plot.py:_pvt_table_nodes, :134-147, — дословно)
    """
    (тело :149-174 дословно)
```
В докстринге `plot_pvt_properties` у параметра `table_nodes` дописать «— см. pvt_table_nodes».

`examples/pvt_plot.py`: удалить `_pvt_table_nodes` и импорты `TableFullPVT`, `BAR_TO_PA`, если больше не используются; импорт `from gpn_multiphase_solver.io.output import plot_pvt_properties, pvt_table_nodes`; вызовы `_pvt_table_nodes(` → `pvt_table_nodes(` (`plot_pvt`, `report_pvt`). Докстринг модуля, строки 12–17: «чтобы та же функция была доступна пользователю установленного пакета, а не только тому, кто выгрузил репозиторий целиком (examples/ в дистрибутив не входит)» — оставить смысл, дописать «узлы таблиц — pvt_table_nodes (DEBT-011)».

`tests/test_examples.py`: `_pvt_module()._pvt_table_nodes` (`:960, 1220, 1223, 1484`) и `pvt_plot._pvt_table_nodes` (`:1083, 1098, 1148`) → `pvt_table_nodes` с импортом из `gpn_multiphase_solver.io.output`. `_pvt_module()`, `pvt_plot.plot_pvt`, `.report_pvt`, `._physical_rs`, `._describe`, `._p_range` — остаются.
```powershell
git grep -n -E "_pvt_table_nodes|_relperm_module\(\)\._table_nodes" -- examples tests   # пусто
```

Тест в `tests/test_public_api.py`:
```python
from gpn_multiphase_solver.factory import create_pvt
from gpn_multiphase_solver.io.output import pvt_table_nodes


def test_pvt_table_nodes_none_for_correlation():
    """У корреляции Стендинга узлов нет — None: маркеры на гладкой кривой вводили бы в заблуждение."""
    assert pvt_table_nodes(create_pvt(load_config(BASELINE)), 50.0) is None
```
(Табличный случай проверяют перенаправленные тесты `test_examples.py:1220-1223`.)

**Проверка после шага:**
- **Регресс: полный** — шаги 3–11 правили медленные тесты `test_examples.py` на фикстуре `results` (балансы, замкнутое решение, PVT, ОФП); быстрый уровень их не исполняет. Один полный прогон после всех переносов ловит ошибку правки до документов. Ожидание: N0 + 12 + число скриптов `examples/`.

**Зависимости:** требует шаг 3.

**Оценка:** ~45 строк переезжает, ~10 строк правок, ~15 мин + ~10 мин прогон.

**Точка коммита:** `refactor: рисунки проверок в io/output — балансы, кривые ОФП, узлы таблиц PVT и ОФП (DEBT-011)`.

---

### Шаг 12: страж независимости пакета; документы

**Цель:** пакет не зависит от `examples/` — это проверяет тест; тексты описывают новое место кода.

**Файлы:** `numerical_solver/tests/test_public_api.py`; README в `numerical_solver/examples/`; заметки vault (список ниже).

**Что сделать:**
1. Страж в `tests/test_public_api.py`:
   ```python
   # ── Независимость пакета от examples/ ────────────────────────

   PACKAGE_DIR = SOLVER_ROOT / "gpn_multiphase_solver"
   EXAMPLES_DIR = SOLVER_ROOT / "examples"


   def test_package_does_not_depend_on_examples():
       """Пакет не импортирует модули examples/ и не правит sys.path (DEBT-011).

       Критерий поставки: пакет работает после установки, без репозитория.
       Проверка статическая, разбором AST: импорт пакета в этом же процессе
       ничего не доказал бы — другие тесты кладут examples/ в sys.path.
       Относительные импорты (from .mass_balance) — свои модули пакета.
       """
       example_modules = {p.stem for p in EXAMPLES_DIR.glob("*.py")}
       found = []
       for path in sorted(PACKAGE_DIR.rglob("*.py")):
           tree = ast.parse(path.read_text(encoding="utf-8"))
           for node in ast.walk(tree):
               if isinstance(node, ast.Import):
                   tops = [a.name.split(".")[0] for a in node.names]
               elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                   tops = [node.module.split(".")[0]]
               else:
                   tops = []
               rel = path.relative_to(PACKAGE_DIR).as_posix()
               found += [f"{rel}:{node.lineno} импорт {t}" for t in tops
                         if t in example_modules]
               if (isinstance(node, ast.Attribute) and node.attr == "path"
                       and isinstance(node.value, ast.Name) and node.value.id == "sys"):
                   found.append(f"{rel}:{node.lineno} sys.path")
       assert not found, found
   ```
   Проверить, что страж ловит: временно вписать `import closed_form` в `diagnostics/two_phase.py` — тест красный; вернуть.
2. README примеров:
   ```powershell
   cd <W>\numerical_solver
   git grep -n -E "closed_form|two_phase_analytics|rs_analytics|temperature_asymptotics|compute_balance|_table_nodes|_pvt_table_nodes|Closure|solve_closed|single_phase_asymptote|degassing_front|dupuit_check|predict_saturation|rs_expected|front_radius" -- "examples/*.md" "examples/**/*.md"
   ```
   Для каждого места: если речь о **проверке, формуле или функции**, переехавшей в пакет, — путь `gpn_multiphase_solver/diagnostics/<модуль>.py` (или `energy/balance.py`, `mass_balance.py`, `io/output.py`); если о печати отчёта, наложении на профиль или запуске CLI — `examples/<модуль>.py` остаётся верным. Числа README не трогать.
3. Vault — живые описания кода (историю расследований не переписывать):
   - `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md` — новый раздел «Диагностика и граница пакет / examples (DEBT-011)»: дерево `diagnostics/`, функции балансов и рисунков, свойства `Simulator.grid/pvt/relperm`, `create_pvt/create_relperm`; что остаётся в `examples/` до [[FEAT-030]]; два стража (`test_no_private_solver_access`, `test_package_does_not_depend_on_examples`);
   - `vault/knowledge/decisions/модули-simulator-оркестратор.md` — свойства и аргумент `relperm`;
   - `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md` — дописать: с DEBT-011 вычислительная часть общих проверок — в пакете, в `examples/` — печать и наложения;
   - `vault/knowledge/decisions/проверка Rs — равенство только в ячейках со свободным газом, без газа — неравенство с допуском решателя.md`, `согласованность-pvt-hydro.md`, `контейнер-simulation-history.md`, `имена скриптов examples проверяются разбором AST — импорт файла не видит импорты в функциях и обращения к модулю через точку.md` — пути и имена (`_create_relperm` → `create_relperm`, `_energy._pvt` → `Simulator.pvt`, `examples/rs_analytics.py` → `diagnostics/rs.py` для проверки), по выводу:
     ```powershell
     git grep -n -E "_create_relperm|_create_pvt|_energy\._pvt|examples/(closed_form|two_phase_analytics|rs_analytics|temperature_asymptotics|relperm_plot|energy_balance|mass_balance)\.py" -- vault/knowledge/decisions
     ```
   Заметки `debugging/`, `science/`, `numerics/` — описание прошлого состояния, не менять.

**Проверка после шага:**
- Регресс: быстрый. Ожидание: + 1.
- Документы — `& $PY -m pytest tests/test_eq_references.py -q` (README примеров под ним).

**Зависимости:** требует шаги 5–11.

**Оценка:** ~35 строк теста, ~20 правок текста, ~30 мин.

**Точка коммита:** код и README — `test: страж независимости пакета от examples/; docs: README примеров — диагностика в пакете (DEBT-011)` (можно двумя); vault — отдельным коммитом `vault: …`.

---

### Шаг 13: итог — снимок «после», сравнение, пробные запуски CLI, vault

**Цель:** доказать, что вывод примеров не изменился, и закрыть задачу в vault.

**Что сделать:**
1. Снимок «после» (в фоне, ~15–20 мин):
   ```powershell
   & $PY <W>\vault\issues\debt-011\probes\snapshot_examples.py snap --tree <W>\numerical_solver --out <W>\vault\issues\debt-011\probes\out\snap_after.json
   & $PY <W>\vault\issues\debt-011\probes\snapshot_examples.py compare <W>\vault\issues\debt-011\probes\out\snap_before.json <W>\vault\issues\debt-011\probes\out\snap_after.json
   ```
   Ожидание: «итог: совпадает», код 0. Расхождение — дефект переноса: найти по выводу `compare` (пример, строка печати или файл), исправить, снять «после» заново (`--only <префиксы>` для повторной проверки затронутых примеров, затем полный снимок). Если расходятся только строки времени выполнения, не пойманные `TIME_PATTERNS`, — дописать шаблон в пробу и повторить `compare` (снимать заново не нужно: текст в снимке полный).
2. Пробные запуски CLI, которых нет в снимке (быстрые примеры; пишут только в `examples/*/output/`):
   ```powershell
   cd <W>\numerical_solver
   $env:PYTHONPATH = "<W>\numerical_solver"; $env:GPN_EXAMPLES_EMF = "0"
   & $PY examples\energy_balance.py 01
   & $PY examples\mass_balance.py 01
   & $PY examples\two_phase_analytics.py 03
   & $PY examples\temperature_asymptotics.py 02
   Remove-Item Env:PYTHONPATH, Env:GPN_EXAMPLES_EMF
   ```
   Ожидание: код 0, печать без трассировок. Скрипты сходимости (`grid_convergence.py` 04/04a, `closed_form_convergence.py` 05, `spatial_convergence.py` 01, `check_slopes.py` 02, `energy_balance_convergence.py`, `check_energy_balance_all.py`, `verify_balance_vs_solver.py`) долгие и в снимок не входят: их правки — замены имён один-в-один, проверены статически (DEBT-046 + страж шага 3). Не запускать.
3. **Подпакет в дистрибутиве.** Исходный дефект DEBT-011 — «диагностика не входит в дистрибутив»; тесты в дереве репозитория этого не видят. Собрать колесо и проверить состав:
   ```powershell
   cd <W>\numerical_solver
   & $PY -m pip wheel . --no-deps -w <W>\vault\issues\debt-011\probes\out\wheel -q
   & $PY -c "import zipfile,glob,sys; w=glob.glob(sys.argv[1]+'/gpn_multiphase_solver-*.whl')[0]; n=zipfile.ZipFile(w).namelist(); print(sorted({x.rsplit('/',1)[0] for x in n if x.startswith('gpn_multiphase_solver/')}))" <W>\vault\issues\debt-011\probes\out\wheel
   Remove-Item -Recurse -Force <W>\numerical_solver\build
   ```
   Ожидание: в списке есть `gpn_multiphase_solver/diagnostics` (на `73ef031` — только `energy`, `grid`, `hydro`, `io`, `pvt`; проверено при аудите). Сборка идёт с изоляцией: в `.venv` нет `setuptools` (Python 3.12+), `pip` скачивает `setuptools>=68` — нужна сеть; `--no-build-isolation` падает с `Cannot import 'setuptools.build_meta'`. Без сети — пропустить и записать в итог. Каталог `build/` (создаёт сборка) — удалить; `*.egg-info` и `build/` в `.gitignore`.
4. Полный прогон — делает `/implement` в конце (§3.1). Ожидание: N0 + 12 + число скриптов `examples/`, все зелёные.
5. Vault и issue — по контракту `/implement`: статус плана «реализован», запись реестра, комментарий в #91 (`vault/issues/debt-011/05-comment-done.md`): итог сравнения снимков (23 примера, число файлов), числа тестов, сообщение о `deliverables/rs150_for_sergey/make_tables.py`.

**Оценка:** ~40 мин (из них ~20 — снимок в фоне).

## 5. Тестовая стратегия

### 5.1. Неизменность поведения — существующие тесты

| Что покрывает | Тесты |
|---|---|
| Замкнутое решение | `test_examples.py`: `Closure` (`:1577`), `solve_closed` (`:1776`), `stationary_pwf`/обращение по дебиту (`:1853-1878`), хуки при управлении по дебиту (`:1974`) |
| Двухфазный стационар | `test_examples.py` — классы проверок 03/04/05 (через `tpa.report` и главные функции) |
| $R_s$ | `test_rs_analytics.py` целиком (быстрый), `test_examples.py:887, 1026-1043` |
| Асимптотика $T$ | `test_examples.py:410, 453` |
| Балансы | `test_energy_balance_examples.py`, `test_examples.py:694-787, 2827-2839`, `test_mass_balance.py` |
| Рисунки PVT, ОФП | `test_examples.py:932-1484` (узлы, рабочий диапазон, сводки) |
| Имена в скриптах | `test_example_scripts.py` (DEBT-046) |
| Ссылки на уравнения | `test_eq_references.py` |

### 5.2. Новые тесты — `tests/test_public_api.py` (12) и страж в `test_example_scripts.py`

| Тест | Шаг | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_factory_builders_public_without_aliases` | 2 | имена фабрики | `create_*` есть, `_create_*` нет | возврат псевдонимов |
| `test_simulator_objects_table` | 2 | `configs/table_pvt/config.json`, без расчёта | `grid`, `pvt` — объекты решателя энергии (`is`); `relperm.proto_rp is` ОФП модели прототипа | диагностика на копии, а не на объекте задачи |
| `test_simulator_objects_corey` | 2 | `configs/baseline.json` | `CoreyRP`, кривые = `create_relperm` побитово | потерю ОФП при сборке |
| `test_simulator_relperm_none_without_argument` | 2 | прямое конструирование | `relperm is None` | поломку тестовых двойников |
| `test_no_private_solver_access[script]` | 3 | AST каждого `.py` в `examples/` (46) | приватного доступа нет | возврат `sim._energy._pvt` в примеры |
| `test_compute_energy_balance_residual_and_scale` | 4 | два снимка | невязка 0.5, нормировка 11.5, $t=0$ → 0 | смену нормировки при переносе |
| `test_compute_mass_balance_none_without_inventories` | 4 | пустая история / `[None]` | `None` | падение на двойниках |
| `test_compute_mass_balance_closes` | 4 | запас 100 → 90, добыча 12, приток 2 | невязка 0; знаки по конвенции | путаницу знаков |
| `test_plot_energy_balance_series_draws_all_terms` | 9 | синтетические ряды | 7 + 1 кривая, заголовок | потерю члена на рисунке |
| `test_plot_relperm_curves_panels[0.05-2, 0.0-1]` | 10 | Кори | 2 / 1 панели, заголовок | поломку однофазной ветки |
| `test_pvt_table_nodes_none_for_correlation` | 11 | Стендинг | `None` | маркеры на корреляции |
| `test_package_does_not_depend_on_examples` | 12 | AST пакета | нет импортов модулей `examples/`, нет `sys.path` | зависимость пакета от репозитория |

### 5.3. Инвариант — снимок вывода

`vault/issues/debt-011/probes/snapshot_examples.py`: 23 `main.py`, печать (без строк времени, путь дерева нормализован) и SHA-256 каждого файла `output/` (PNG, CSV). Снимок «до» — шаг 0 на базе, «после» — шаг 13. Детерминизм проверен при планировании: два прогона 01 и 03 на `123247a` — 23 файла и печать совпали.

## 6. Критерии завершения

- [ ] DEBT-008 и DEBT-063 влиты до начала (шаг 0).
- [ ] Шаги 1–12 выполнены; коммиты по точкам раздела 7.
- [ ] Быстрый уровень после каждого шага зелёный; полный на шаге 11 и в конце `/implement` — зелёный, N0 + 12 + число скриптов `examples/`.
- [ ] `compare` снимков: «итог: совпадает» по 23 примерам.
- [ ] Пробные CLI шага 13 — код 0.
- [ ] Колесо `gpn_multiphase_solver-*.whl` содержит `gpn_multiphase_solver/diagnostics/` (шаг 13, п. 3; без сети — отмечено в итоге).
- [ ] Приватного доступа в `examples/` нет (страж); пакет не зависит от `examples/` (страж).
- [ ] `git grep` старых имён (`_create_pvt`, `_create_relperm`, `compute_balance`, `_pvt_of`, `_build_relperm`, `_table_nodes`, `_pvt_table_nodes`, `_degassed_cells`, `_kr_max_Sg`) по `numerical_solver/` — пусто (кроме `deliverables/`, он не в git).
- [ ] Прототип не тронут (`git diff --stat` по `HydroSolverPrototype/` пуст).
- [ ] Vault: архитектурная заметка с разделом DEBT-011, заметки решений обновлены, запись реестра, комментарий #91; пользователю сообщено о `deliverables/rs150_for_sergey/make_tables.py`.

## 7. Точки коммитов

На ветке задачи (формат — CLAUDE.md, «Коммиты»; файлы — по имени; vault — отдельно):
1. после шага 2 — `refactor: публичные create_pvt, create_relperm и объекты задачи у Simulator (DEBT-011)`;
2. после шага 3 — `refactor: примеры и тесты без приватного доступа к решателю; страж (DEBT-011)`;
3. после шага 4 — `refactor: ряды балансов энергии и массы в ядре (DEBT-011)`;
4. после шага 8 — `refactor: диагностика в пакете — gpn_multiphase_solver/diagnostics (DEBT-011)`;
5. после шага 11 — `refactor: рисунки проверок в io/output (DEBT-011)`;
6. после шага 12 — `test: страж независимости пакета от examples/ (DEBT-011)` и `docs: README примеров — диагностика в пакете (DEBT-011)`;
7. vault — `vault: DEBT-011 …`.

Файлы `vault/issues/debt-011/probes/out/*.json` не коммитить.

## 8. Для следующих задач

- **[[FEAT-030]]**: в `examples/` остаются наложения (`make_overlay_*`, `_draw_rs`), печать (`report_*`), обёртки рисунков с записью PNG, `run_example`, `figure_io`, CLI-блоки — их перенос и есть команда расчёта. Там же: `run_example` не возвращает решатель — `main.py` 01–05 собирают второй `Simulator`; `_resolve_example` — три копии.
- **[[DEBT-065]]**: три реализации радиуса изобары $p_b$.

## 9. Аудит

### Раунд 1 (2026-10-11, база `73ef031`): 🟡 3, 🔵 2 — все исправлены, ✅

**Проверено исполнением** (проба `vault/issues/debt-011/probes/audit_checks.py` — запускается на коде до реализации, после неё имена изменятся):
- страж приватного доступа шага 3 на текущем дереве находит ровно 21 скрипт из 46, и каждая находка покрыта заменами шагов 1, 3 (импорты `_create_*` уходят переименованием); ложных находок нет;
- страж независимости пакета шага 12 — 0 находок; подложенные `import closed_form`, `from figure_io import …`, `sys.path` — пойманы;
- числа синтетических тестов шага 4 — на текущих функциях `examples/`: невязка 0.5, `rel_residual` = 0.5/11.5 точно, $t = 0$ → 0; масса — невязка 0, добыча 12, приток 2; `CUMULATIVE_KEYS` = `_CUMULATIVE` поэлементно;
- **разделение рисования «ядро + обёртка» (шаги 9, 10) даёт PNG побайтно**: `energy_balance.png`, `mass_balance.png`, `relperm.png` (две панели, пример 03) и `relperm.png` однофазной ветки; ожидания тестов шагов 9–10 (7 + 1 кривая, формы осей (1, 2) и (1, 1), заголовок) — выполняются;
- базовые числа: 1741 тест, быстрый уровень 1470; скриптов `examples/` — 46;
- колесо `pip wheel . --no-deps` (с изоляцией сборки) содержит подпакеты `energy`, `grid`, `hydro`, `io`, `pvt` — проверка шага 13 п. 3 работоспособна; `--no-build-isolation` падает (в `.venv` нет `setuptools`).

**Находки и исправления:**
1. 🟡 **Номера строк `tests/test_examples.py` устарели на +12** (DEBT-063 дописал строки выше `:370`): заглушка `:1982` → `:1994`, `_closed_form()` `:1797` → `:1809`, балансы `:682…` → `:694…` и т. д. — обновлены во всех шагах и в разделе 5.1.
2. 🟡 **Нет проверки, что новый подпакет попадает в дистрибутив** — а исходный дефект DEBT-011 именно «не входит в дистрибутив»; тесты в дереве репозитория этого не видят. Добавлено: шаг 13 п. 3 (сборка колеса, состав, уборка `build/`), критерий завершения.
3. 🟡 **DEBT-023 реализуется параллельно** (worktree открыт) и правит `test_energy_balance_examples.py`, `test_examples.py`, меняет вывод 03–09. Добавлено в 2.1 и «Как начать» (п. 3): начинать после её влития; иначе — порядок разрешения конфликтов и пересъём снимка.
4. 🔵 DEBT-054 (план готов) правит `simulator.py` и `test_simulator.py` — внесена в 2.1: другая часть файла, конфликт маловероятен.
5. 🔵 Охват шага 1 по `factory.py` — номера на `73ef031` (96, 356; вызовы 57, 64); сдвиги ≤ 2 строк.

**Решения пользователя не требуется.**
