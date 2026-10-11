---
tags:
  - план
  - удаление
date: 2026-10-10
issue: DEBT-008
github: 89
branch: refactor/debt-008/dead-config-fields
status: в процессе
worktree: .worktrees/debt-008
audit:
  date: 2026-10-11
  round: 2
  found: 5
  auto-fixed: 5
  manual-required: 0
---

# DEBT-008: мёртвые поля конфига — удалить, проверить или передать решателю

## Кратко

- **Дефект.** В `io/config.py` 12 полей конфига, которых решатель не читает: `grid.type`, `rock.p_ref`, `time.start_day`, `numerics.dt_min`, `dt_max`, `newton_max_iter`, `newton_rtol`, `newton_atol`, `max_active_set_iter`, `rs_switch_tol`, `sg_switch_tol`, `output.format`. Они загружаются и проходят `_validate` с любым конечным значением (проба `vault/issues/debt-008/probes/red_state.out.txt`: `grid.type` = «ЭТО_ЧУШЬ_А_НЕ_СЕТКА», `newton_max_iter = -3`, `rs_switch_tol = -1` — `_validate` и фабрика проходят, прототип считает со своими умолчаниями). P8 и докстринг `NumericsConfig` обещают, что поля передаются решателю. Смежное: опечатка в `output.log_level` молча даёт `INFO` (`log.py:18`).
- **Что делается** (решения пользователя 2026-10-10, раздел 0):
  - **передаются решателю** 4 поля: `rs_switch_tol`, `sg_switch_tol` — фабрика в конструктор `RadialBlackOilModel`; `newton_max_iter`, `max_active_set_iter` — адаптер в каждый вызов `advance` (и `advance_fourth_stage` DEBT-048). У прототипа эти аргументы уже есть — **прототип не правится**. `rs_switch_tol` становится единственным источником допуска пересыщения: его берут и проверка старта (`factory._check_undersaturated_start`, вместо константы `_RS0_SUPERSAT_TOL`), и проверка $R_s$ примеров (`examples/rs_analytics.py`, вместо константы `RS_TOL`);
  - **удаляются** 7 полей: `rock.p_ref`, `time.start_day`, `numerics.dt_min`, `dt_max`, `newton_rtol`, `newton_atol`, `output.format`. В старом конфиге ключ пропускается с предупреждением в журнал — после `_validate`, как предупреждения DEBT-056 (результат не меняется — поле и раньше не читалось); из 31 JSON-конфига репозитория ключи вычищаются, из конвертера примера 18 (`examples/18_prototype_input/prototype_input.py`) — `start_day`;
  - **проверяются литералы** `grid.type` (только `"log_radial"`) и `output.log_level` (DEBUG…CRITICAL без учёта регистра);
  - проверки диапазона новых передаваемых полей: лимиты — целые ≥ 1, допуски — > 0.
- **Числа не меняются.** Умолчания конфига совпадают с умолчаниями прототипа (15, 12, 1e-5, 1e-9; страж — новый тест); передача тех же значений явными аргументами даёт те же операции. `p_ref` фабрика не читала и прежде ($p_{ref} = p_0$ всегда; у примера 18 $c_r \ne 0$, но `p_ref` в его конфиге нет). Истории примеров — побитово прежние, README-числа не трогаются.
- **Шагов:** 9 (0 — подготовка, 8 — итог). Код: ~75 строк `io/config.py`, ~15 `factory.py`, ~15 `hydro/prototype_adapter.py`, ~15 `examples/rs_analytics.py`, 1 строка конвертера примера 18. Тесты: +28 / −16 в `test_config.py`, +3 `test_factory_prototype.py`, +3 `test_prototype_adapter.py`, +1 `test_rs_analytics.py`, замена одного параметризованного теста в `test_examples.py` — итого **+19** (база `ccc5ae3`: 1722 → 1741, быстрый уровень 1451 → 1470). Данные и тексты: 31 JSON (скрипт), 17 README примеров (скрипт), 7 заметок vault.
- **Оценка:** ~2.5 ч, из них ~10 мин — полный прогон.

## 0. Решения пользователя (2026-10-10)

1. **Поля Ньютона.** `rs_switch_tol`, `sg_switch_tol`, `newton_max_iter`, `max_active_set_iter` — передавать прототипу (аргументы у него уже есть); `newton_rtol`, `newton_atol` — удалить (прототип не принимает их ни в конструкторе, ни в `advance`; правка прототипа ради них не нужна). `rs_switch_tol` — единый источник допуска пересыщения для `factory._check_undersaturated_start` и `rs_analytics`.
2. **`rock.p_ref` — удалить; пористость задаётся при $p_0$.** У прототипа $\varphi(p) = \varphi_{ref}\,e^{c_r(p - p_{ref})}$ (`radial_blackoil/rock.py:6`), а это тождественно $\varphi(p_0)\,e^{c_r(p - p_0)}$: любая пара $(\varphi_{ref}, p_{ref})$ пересчитывается в $\varphi(p_0) = \varphi_{ref}\,e^{c_r(p_0 - p_{ref})}$ точно, поле не добавляет модели возможностей. Энергия берёт постоянную `rock.porosity` (`energy/tridiag.py:208, 440, 478`) — при $p_0$ она совпадает с $\varphi$ гидродинамики.
3. **Удалённые ключи в старом конфиге** — предупреждение в журнал и пропуск, не отказ. Отличие от `save_every` (DEBT-013, отказ): там пропуск менял бы состав вывода, здесь результат тот же. Пробы vault и `numerical_solver/deliverables/` (не в git, переданы разработчику прототипа) продолжают загружаться.
4. **Литералы** `grid.type` и `output.log_level` — проверять в `_validate`; JSON с `"type": "log_radial"` не трогать.

`time.start_day`, `numerics.dt_min`, `dt_max`, `output.format` — удаляются (смысла в архитектуре нет: шаг задаёт `time.dt_integration`, дробление — `max_retries`, формат файла — вызывающий код; время истории всегда от 0).

## Как начать работу по этому плану

1. Прочитай этот файл целиком; затем запись DEBT-008 в [[известные баги и технический долг]] и раздел «Порядок влития» ниже.
2. Ветка от базовой — в worktree, как делает `/implement`:
   ```powershell
   git worktree add .worktrees/debt-008 -b refactor/debt-008/dead-config-fields numerical_scheme/implementation
   ```
3. Переменные (PowerShell; в worktree `.venv` нет — интерпретатор основного каталога. pytest из worktree берёт пакеты worktree: `pythonpath` в `[tool.pytest.ini_options]` `numerical_solver/pyproject.toml`, DEBT-059. Скрипты вне pytest без подготовки взяли бы пакеты **основного** каталога (оба установлены в общий venv в редактируемом режиме, правило 3 `/implement`); проба `red_state.py` ставит `Path.cwd()` первым в `sys.path` сама и печатает путь пакета, а `strip_removed_keys.py` и `fix_readmes.py` пакет не импортируют — правят файлы относительно текущего каталога; `PYTHONPATH` им не нужен, запускать из `$WT`):
   ```powershell
   $PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   $P  = "D:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-008\probes"   # скрипты и пробы — в основном каталоге
   $WT = "D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-008\numerical_solver"
   ```
4. Базовое состояние — шаг 0. **Прототип этот план не меняет** — тесты и регрессия прототипа не нужны (проверка — шаг 0, п. 5).
5. После каждого шага — проверка шага и регресс по полю «Регресс». Полный прогон GPN — шаг 8.
6. Точки коммитов (на ветке задачи; формат — CLAUDE.md, «Коммиты»; vault — отдельно от кода):
   - после шага 5 — `refactor: мёртвые поля конфига удалены, проверены или переданы решателю (DEBT-008)`: `io/config.py`, `factory.py`, `hydro/prototype_adapter.py`, `examples/rs_analytics.py`, `examples/18_prototype_input/prototype_input.py`, 31 JSON, `tests/test_config.py`, `tests/test_factory_prototype.py`, `tests/test_prototype_adapter.py`, `tests/test_rs_analytics.py`, `tests/test_examples.py`. До шага 5 не коммитить: после шагов 1–4 есть красные тесты;
   - после шага 6 — `docs: README примеров — поля конфига после DEBT-008`;
   - после шага 7 — `vault: P8, json-config-schema и заметки — поля конфига после DEBT-008`;
   - шаг 8 — vault задачи (реестр, план, index), как требует `/implement`.

## Порядок влития

План написан на `26ddb34`, сверен аудитом 1 с базой **`ccc5ae3`** (2026-10-11): тестов 1722, быстрый уровень 1451. Номера строк — на `ccc5ae3`. Все задачи, которые должны были влиться раньше, влиты:

| Задача | Влита | Что учтено в плане |
|---|---|---|
| **BUG-022** (#82) — `numerics.newton_cell_tol` | `7b47ac8` | Докстринг `NumericsConfig` с комментарием «Читаются… Не читаются…» (`io/config.py:141-144`), блок `newton_cell_tol` в конце `NumericsConfig` (`:166-180`) и в `_validate` (`:545-552`), `cell_tol=` в `RadialBlackOilModel(...)` (`factory.py:440-442`), таблица `numerics` в `json-config-schema.md`, P8 §4–5. Шаг 3 заменяет его докстринг и комментарий, последнюю строку комментария `newton_cell_tol`; блок `_validate` DEBT-008 — **после** его блока. |
| **DEBT-048** (#78) — память ступени 4 | `fb69869` | Адаптер вызывает `m.advance_fourth_stage(proto_state, dt)` и `m.advance(proto_state, dt)` (`prototype_adapter.py:146-149`); шаг 4 передаёт лимиты в оба вызова; тест `test_limits_reach_fourth_stage_by_memory` пишется. |
| **DEBT-056** (#87) — скин и `p_wf` | вместе с BUG-022 | Строка `skin` в `NumericsConfig` — с комментарием DEBT-056 (переносится как есть); **предупреждения — только после `_validate`** (`load_config`, `:359-364`; тест `test_no_warning_before_error`) — предупреждения DEBT-008 подчиняются тому же порядку (шаг 3); **P8 §5 — таблица** «Этап \| Где \| Что» (шаг 7, п. 3). |
| **DEBT-006** (#88) — фабрика без приватных полей | `87e99a1` | Последняя строка `_create_prototype_hydro`: `return PrototypeHydroAdapter(model, grid, pvt)` с комментарием DEBT-006 над ней (`factory.py:452-457`). |
| **VAL-005** (#79) — пример 18 | с DEBT-006 | `examples/18_prototype_input/config.json` содержит `"start_day": 0.0` и **порождается конвертером** `prototype_input.py` (`convert`, `:184`); `test_examples.py::TestPrototypeInput::test_files_reproduce_conversion` (`:2903-2915`) построчно сверяет файл с выводом конвертера — ключ убирается в обоих (шаг 2, проба `audit1_converter18.py`). Отказ конвертера при Reference pressure $\ne p_0$ (`:128-134`) остаётся корректным: фабрика по-прежнему берёт $p_{ref} = p_0$. |
| **DEBT-014**, **DEBT-020**, **DEBT-059**, **DEBT-063**, **BUG-024** | влиты | DEBT-014 переписал истории конфигов в краткой форме — удаляемые ключи остались, скрипт шага 2 сверен на новой базе (31 файл); DEBT-059 — прототип в общем venv, pytest берёт пакеты дерева через `pythonpath` в `pyproject.toml` (не `conftest.py`); DEBT-063 изменил числа README, тексты замен шага 6 не задел (скрипт сверен: 17 README). |

Ожидают после DEBT-008: **DEBT-011** (#91, перенос `examples/rs_analytics.py` в пакет; по своему плану — после DEBT-008, переносит код уже с допуском из конфига). **DEBT-023** (#100, λ в примерах 03–09) — по его плану конфликтов с DEBT-008 нет (другие строки `config.json`, README-тексты шага 6 не трогает).

## 1. Замеры при планировании (`26ddb34`; повторены аудитом 1 на `ccc5ae3` — те же результаты, кроме отмеченных)

- **Проба** `$P\red_state.py` → `$P\red_state.out.txt` (каждый пункт на свежем конфиге, отказы перехватываются — та же проба в шаге 8 даёт итоговое состояние; на `ccc5ae3` вывод тот же):
  1. абсурдные значения 12 полей проходят `_validate` и `SimulatorFactory.from_config`; сетка `LogRadialGrid`; у прототипа `rs_switch_tol = 1e-05`, `sg_switch_tol = 1e-09`, `p_ref_bar = 200` (= $p_0$);
  2. `dt_min = NaN` — отказ «`numerics.dt_min должно быть конечным числом`» (DEBT-051 проверяет и мёртвые поля), конечное — проходит;
  3. `log_level = 'DEBG'` — `setup_logging` ставит `INFO`, `_validate` проходит;
  4. `configs/table_pvt`, $p_0$ на 1 Па ниже $p_b(30)$ (избыток $R_s$ ~3e-6), `rs_switch_tol = 1e-6` — старт принят: допуск 1e-5 зашит в фабрике;
  5. конфиг с `newton_max_iter = 7`, `max_active_set_iter = 5`, `rs_switch_tol = 2e-5`, `sg_switch_tol = 3e-9` — у адаптера полей лимитов нет, у модели 1e-05 и 1e-09 (умолчания);
  6. `vault/issues/bug-019/probes/frozen/config.json` (старые ключи `start_day`, `dt_min`, `dt_max`) — загружен, предупреждений 0.
- **Где встречаются удаляемые ключи** (grep по `numerical_solver/**/*.json`, `ccc5ae3`): `time.start_day`, `numerics.dt_min`, `dt_max` — в 30 отслеживаемых конфигах (`examples/*/config.json` — 22, `configs/` — 3, `tests/data/*/config.json` — 5), `time.start_day` (без `dt_min`, `dt_max`) — в `examples/18_prototype_input/config.json`; в 2 неотслеживаемых `deliverables/rs150_for_sergey/*.json`; `output.format` — в 3 файлах `configs/`; `rock.p_ref`, `newton_rtol`, `newton_atol` — нигде. `"compressibility"` — ни в одном конфиге, кроме примера 18 ($c_r$ = 4.5e-5 1/бар; `p_ref` в нём нет). Генератор конфига с удаляемым ключом — один: конвертер примера 18 (`prototype_input.py:184`, `"start_day": 0.0`; grep `start_day|"dt_min"|"dt_max"|"format":|"p_ref"` по `*.py`).
- **Скрипты реализации, прогон в режиме проверки** (без записи; рабочее дерево не изменилось; на `ccc5ae3`):
  - `$P\strip_removed_keys.py`: «файлов: 31, меняется: 31»; каждый результат сверен с исходным JSON без удалённых ключей;
  - `$P\fix_readmes.py`: «README меняется: 17»; после замен ни в одном README (и в README 18) нет `dt_min`, `dt_max`, `start_day`, `output.format`, `p_ref`, «не читаются»;
  - `$P\audit1_converter18.py` → `$P\audit1_converter18.out.txt`: вывод конвертера примера 18 без ключа `start_day` (тот же `json.dumps(indent=2, ensure_ascii=False)`) построчно равен `config.json` 18 после `strip` — правка конвертера шага 2 и скрипт дают один и тот же файл.
- **Поля `float` в страже DEBT-051** (`_FLOAT_FIELDS`, `test_config.py:694-708`): 37 (проба аудита); удаление убирает 6 (`p_ref`, `start_day`, `dt_min`, `dt_max`, `newton_rtol`, `newton_atol`) → 31, параметризованных `test_nonfinite_rejected` — на 12 меньше. `newton_cell_tol` (BUG-022) — `Optional[float]`, в список не входит.
- **Тесты, требующие «ни одного предупреждения»** при загрузке/фабрике: в `test_config.py` — на `_minimal_raw()` (удаляемых ключей нет; среди них `TestValidationWell.test_no_warning_before_error`, DEBT-056), `test_factory_prototype.py:482-487` `test_in_range_no_warnings` (`configs/table_pvt/config.json` — **есть** `start_day`, `dt_min`, `dt_max`, `format`), `test_factory_standing_hydro.py` `test_no_range_warnings` (`configs/baseline.json` — **есть**). Поэтому JSON вычищаются (шаг 2) **раньше**, чем поля уходят из dataclass (шаг 3): иначе между шагами эти два теста ловили бы предупреждение `load_config` (caplog собирает записи всего теста).
- **Подмены `advance` / `advance_fourth_stage` в тестах** принимают ключевые аргументы: `test_prototype_adapter.py:836` (`*args, **kwargs`), `test_prototype_activation_cap.py:222` (`*a, **kw`), `test_prototype_stage4_memory.py:135, 281` (`*args, **kwargs`, `*a, **kw`). Остальные подмены (`test_prototype_globalization.py`, `_phase_switching.py`, `_open_branch_skip.py`, `_well_branch.py`) — у `_advance_phases`, его прототип зовёт позиционно, как прежде.

## 2. Анализ

### 2.1. Текущее состояние (`ccc5ae3`)

| Поле | Объявление | Что происходит на деле |
|---|---|---|
| `grid.type` | `io/config.py:35` | фабрика всегда строит `LogRadialGrid` (`factory.py:48`) |
| `rock.p_ref` | `io/config.py:51` (комментарий `:50` «Компрессия породы (пока не используется)» неверен и для `compressibility`) | `CompressibleRock(p_ref_bar = ic.p0 / BAR_TO_PA)` (`factory.py:410-415`) |
| `time.start_day` | `io/config.py:134` | время истории всегда от 0 |
| `numerics.dt_min`, `dt_max` | `io/config.py:145-146` | дробление — `max_retries` в `Simulator` (DEBT-015) |
| `numerics.newton_max_iter`, `max_active_set_iter` | `io/config.py:148, 151` | адаптер: `m.advance(proto_state, dt)` и `m.advance_fourth_stage(proto_state, dt)` (`hydro/prototype_adapter.py:146-149`) — умолчания `advance(…, max_active_iter=12, max_newton=15)` (`blackoil.py:383`), `advance_fourth_stage` (`:436`) — те же |
| `numerics.newton_rtol`, `newton_atol` | `io/config.py:149-150` | умолчания `_newton_fixed_active_set(…, max_iter=15, rtol=1e-8, atol_sm3s=1e-11)` (`blackoil.py:347`) и `_newton_switching` (`:536`); `_advance_phases` передаёт только `max_iter` |
| `numerics.rs_switch_tol`, `sg_switch_tol` | `io/config.py:152-153` | конструктор `RadialBlackOilModel(…, rs_switch_tol=1e-5, sg_switch_tol=1e-9, …)` (`blackoil.py:64-68, 72`), фабрика их не передаёт (`factory.py:428-443`); копии 1e-5 — `factory._RS0_SUPERSAT_TOL` (`:273-278`), `rs_analytics.RS_TOL` (`examples/rs_analytics.py:69-78`) |
| `output.format` | `io/config.py:189` | ни один модуль не читает; `test_examples.py:202-211` запрещает поле в конфигах примеров |
| `output.log_level` (смежное) | `io/config.py:188` | `getattr(logging, level.upper(), logging.INFO)` (`log.py:18`) — неизвестное имя молча `INFO` |

Загрузка: `XxxConfig(**raw[...])` (`io/config.py:316-332`) — строгая распаковка: лишний ключ даёт `TypeError … unexpected keyword argument`. Прецедент отказа с объяснением — `save_every` (`:338-347`, DEBT-013); прецедент отказа по неприменимому полю — `_validate_interval` («Мёртвые поля (DEBT-008)» для `q_oil`, `min_bhp` при `control='pressure'`). Предупреждения загрузки — после `_validate` (`:359-364`, правило DEBT-056).

### 2.2. Целевое состояние

- `GridConfig.type` — проверяется (`"log_radial"`).
- `RockConfig` без `p_ref`; комментарий секции — правило «`porosity` задана при $p_0$».
- `TimeConfig` без `start_day`; `OutputConfig` без `format`; `log_level` проверяется.
- `NumericsConfig` без `dt_min`, `dt_max`, `newton_rtol`, `newton_atol`; остальные поля читаются: `skin`, `jacobian_mode`, `linear_solver`, `rs_switch_tol`, `sg_switch_tol`, `newton_cell_tol` — фабрика (в конструктор модели); `newton_max_iter`, `max_active_set_iter` — адаптер (в `advance`); `max_retries` — `Simulator`. Докстринг говорит это.
- `load_config`: до разбора секций `_drop_removed_keys(raw)` убирает удалённые ключи и возвращает тексты предупреждений; `user_log.warning(...)` — после `_validate`, рядом с предупреждениями DEBT-056.
- Конвертер примера 18 не пишет `start_day`.
- `factory._check_undersaturated_start(ic, pvt, rs_tol)` — допуск из `numerics.rs_switch_tol`; `_RS0_SUPERSAT_TOL` удалён.
- `PrototypeHydroAdapter(..., max_newton=15, max_active_iter=12)` — передаёт лимиты в каждый вызов.
- `rs_analytics`: `RS_TOL` удалён, допуск — `config.numerics.rs_switch_tol`.
- 31 JSON без удалённых ключей; 17 README без «не читаются»; P8, `json-config-schema.md` и 5 заметок — по коду.

Import-граф не меняется; публичный API: `PrototypeHydroAdapter` — новые ключевые параметры с умолчаниями (вызовы `(model, grid, pvt)` работают); `rs_supersaturation(history, pvt)` → `(history, pvt, tol)` — вызывающий один (`report_rs`).

### 2.3. Варианты (выбор — решения раздела 0)

| Вариант | Суть | Итог |
|---|---|---|
| 1. Удалить все 12, старые ключи — отказ | как `save_every` | отклонён: отказ из-за поля, которое и раньше ни на что не влияло, несоразмерен; ломает пробы и `deliverables/` |
| 2. Удалить все 12, старые ключи — предупреждение | минимальный код | отклонён для полей Ньютона и `grid.type` (решения 1, 4) |
| 3. Задействовать все 12 | `start_day` — сдвиг времени, `dt_min/max` — границы подшага, `format` — выбор записи, `rtol/atol` — правка прототипа | отклонён: механизмы ради полей; вариант «дробить, пока `dt_sub > dt_min`» отклонён ещё в DEBT-007 |
| **4. По полю** | 4 передать, 7 удалить с предупреждением, 2 литерала проверить | **принят** |

### 2.4. Подводные камни

- ✅ **Все места вызова** (`ccc5ae3`). `_check_undersaturated_start` — один вызов (`factory.py:58`); `_RS0_SUPERSAT_TOL` — только `factory.py`; `RS_TOL` — `examples/rs_analytics.py` и `tests/test_rs_analytics.py`; `rs_supersaturation` — только `report_rs`; `PrototypeHydroAdapter(` — `factory.py:457`, фикстура `test_prototype_adapter.py:114`, `test_prototype_stage4_memory.py:236, 289` (с `stage4_memory=` ключом — новые параметры с умолчаниями их не ломают); `NumericsConfig(` / `RockConfig(` / `TimeConfig(` / `OutputConfig(` с удаляемыми полями — нигде; чтения удаляемых полей — только `test_config.py` (переписываются шагом 3).
- 🔴→✅ **Генератор конфига.** `config.json` примера 18 порождается конвертером `prototype_input.py` и сверяется с его выводом (`test_files_reproduce_conversion`). Ключ `start_day` убирается и из файла (скрипт), и из конвертера — в одном шаге 2 (аудит 1; проба `audit1_converter18.py`: результат один и тот же).
- ✅ **Зависимости пакетов, циклы import.** Новых import в пакете нет; `test_config.py` импортирует `radial_blackoil.blackoil` и `gpn_multiphase_solver.hydro.prototype_adapter` (pytest — `pythonpath` в `pyproject.toml`, DEBT-059; голый `python -c "import radial_blackoil"` из основного каталога тоже проходит — прототип установлен в venv).
- ✅ **Обратная совместимость.** Конфиг с удалёнными ключами загружается (предупреждение). Конфиг с неизвестным ключом — по-прежнему `TypeError` (тест `test_unknown_key_still_rejected`). Конфиг с недопустимыми `grid.type`, `log_level`, лимитами, допусками — **новый отказ**: в репозитории таких нет (все 31 JSON: `"log_radial"`, `"INFO"`, полей Ньютона нет).
- 🟡→✅ **Порядок предупреждений (DEBT-056).** `load_config` выдаёт предупреждения только после `_validate`: «конфиг с ошибкой в любом поле не выдаёт предупреждение перед отказом» (`io/config.py:360-361`, тест `test_no_warning_before_error`). Предупреждения об удалённых ключах — так же: `_drop_removed_keys` возвращает тексты, журнал — после `_validate` (шаг 3), страж — `TestRemovedKeys.test_no_warning_before_error`.
- ⚠️ **Побитовость.** Фабрика передаёт `rs_switch_tol=1e-5`, `sg_switch_tol=1e-9` — те же `float`, что умолчания конструктора; адаптер — `max_newton=15`, `max_active_iter=12` — те же `int`. Операции те же — истории те же. Страж — `test_defaults_match_prototype` (сверка с сигнатурами, ловит и смену умолчания в прототипе). Отдельной побитовой пробы по примерам нет: полный прогон (шаг 8) проверяет числа README и балансы.
- ⚠️ **Ступень 4 лимитов не читает.** `advance_fourth_stage` → `_fallback(…, max_active_iter, max_newton)` → `_advance_phases` → при `_phase_switching` сразу `_newton_switching(state_old, dt_s)` (свой `max_iter=40`). Лимиты передаются и ей — чтобы шаг по памяти (DEBT-048) оставался побитово шагом `advance` после трёх отказов при любых будущих правках. Записано в комментарии поля и адаптера.
- ⚠️ **Порядок шагов 2 → 3** (раздел 1): JSON вычищаются до удаления полей, иначе `test_in_range_no_warnings` и `test_no_range_warnings` падают между шагами.
- ⚠️ **Предупреждение до `setup_logging`.** `load_config` зовут раньше фабрики; у `user_log` ещё нет обработчика — запись уходит в `logging.lastResort` (stderr, уровень WARNING и выше): пользователь её видит. Тесты ловят через `caplog`, как `L_degas < 0` (`TestValidationThermal`).
- ⚠️ **`grid.type` не строкой** (`5`): `_check_numeric_fields` поле `str` не проверяет, литерал — да: `5 != "log_radial"` → отказ «`grid.type`». `log_level` не строкой — `isinstance` до `.upper()`.
- ⚠️ **`rs_switch_tol = 0`** отвергается (> 0): ноль снимает запас на шум ~1e-13 горизонтальной ветви таблицы (комментарий `RS_TOL`, `rs_analytics.py:76-77`) — газ включался бы в недонасыщенных ячейках, проверка старта отвергала бы $p_0$ на 1 Па ниже $p_b$.
- ✅ **Состояние при ошибке.** `_drop_removed_keys` меняет только локальный `raw` из `json.load`; `load_config` и так его меняет (`time_raw.pop("history")`).
- ✅ **Docstring / `\eqref`.** Формул не меняется; `problem_statement.tex` полей конфига не упоминает (grep `newton|switch_tol|p\_ref|start\_day` по `numerical_solver/doc` — пусто).
- ✅ **Configs.** Имена параметров не меняются; удаляемые ключи вычищаются скриптом шага 2.
- ✅ **Прототип** не меняется: аргументы `rs_switch_tol`, `sg_switch_tol`, `max_active_iter`, `max_newton` — существующие (`blackoil.py:64-68, 383, 436`). Его тесты и регрессия не нужны.
- ✅ **Ссылки на уравнения (DEBT-010).** `tests/test_eq_references.py` проверяет докстринги, комментарии и README примеров на «eq. N», «ур. N», «.tex:N»; новые тексты плана таких форм и меток `eq:` не содержат.
- ✅ **Производительность** — без изменений.
- ⚠️ **Связь с задачами** — раздел «Порядок влития».

## 3. Шаги

### Шаг 0: Подготовка — база, якоря, базовые числа

**Цель:** убедиться, что база — `ccc5ae3` или новее без правок затронутых файлов, и записать базовые числа.

**Файлы:** — (только чтение).

**Что сделать:**
1. `git log --oneline ccc5ae3..numerical_scheme/implementation` — что влито после аудита. Пусто — номера строк плана действительны. Иначе: `git diff --stat ccc5ae3 numerical_scheme/implementation -- numerical_solver/gpn_multiphase_solver/io/config.py numerical_solver/gpn_multiphase_solver/factory.py numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py numerical_solver/examples/rs_analytics.py numerical_solver/examples/18_prototype_input numerical_solver/tests/test_config.py numerical_solver/tests/test_examples.py numerical_solver/tests/test_factory_prototype.py numerical_solver/tests/test_prototype_adapter.py numerical_solver/tests/test_rs_analytics.py` — затронутые файлы менялись: сверять «До» шагов по тексту; правку, которую план не описывает (например, DEBT-011 уже перенёс `rs_analytics.py`), — остановиться и спросить пользователя.
2. Worktree и переменные — «Как начать работу», пп. 2–3.
3. Якоря (из `$WT`):
   ```powershell
   Select-String -Path gpn_multiphase_solver\io\config.py -Pattern "часть полей никто не читает|newton_cell_tol: Optional|в отличие от newton_atol|_warn_large_skin\(config\)"
   Select-String -Path gpn_multiphase_solver\hydro\prototype_adapter.py -Pattern "advance_fourth_stage\(proto_state, dt\)|m\.advance\(proto_state, dt\)"
   Select-String -Path examples\18_prototype_input\prototype_input.py -Pattern '"time": \{"start_day": 0.0'
   ```
   Ожидание — 4, 2 и 1 совпадение.
4. Подмены `advance` / `advance_fourth_stage` без ключевых аргументов, появившиеся после аудита: `Select-String -Path tests\*.py -Pattern "def \w+\((proto_state|state_old|ps), (dt|dt_s)\):"` — пусто. Если нет — дописать им `**kw` в шаге 4 (иначе передача лимитов даст `TypeError`).
5. Базовые числа:
   ```powershell
   cd $WT
   & $PY -m pytest tests/ --collect-only -q | Select-Object -Last 1     # N_ALL
   & $PY -m pytest tests/ -m "not slow" -q | Select-Object -Last 3      # N_FAST passed, время
   ```
   На `ccc5ae3` — 1722 / 1451 (аудит 1); записать фактические.
6. Проба исходного состояния на базе (из `$WT`): `& $PY $P\red_state.py` — вывод как в `$P\red_state.out.txt` (пп. 1–6; строка «пакет:» — путь worktree).

**Проверка:** быстрый уровень зелёный. **Регресс:** —
**Оценка:** ~10 мин.

### Шаг 1: Тесты (красные)

**Цель:** зафиксировать целевое поведение; падают ровно ожидаемые тесты.

**Файлы:** `numerical_solver/tests/test_config.py`, `numerical_solver/tests/test_factory_prototype.py`, `numerical_solver/tests/test_prototype_adapter.py`, `numerical_solver/tests/test_rs_analytics.py`, `numerical_solver/tests/test_examples.py`.

**Изменения:**

1. `test_config.py`, шапка модуля — последней строкой списка «Проверяет:» (после «- Минимальный конфиг: только обязательные секции.»; строки BUG-022 и DEBT-056 стоят выше — не трогать):
   ```
   - Мёртвые поля (DEBT-008): удалённые ключи — предупреждение и пропуск; grid.type,
     output.log_level, лимиты и допуски Ньютона — проверка; умолчания = умолчаниям прототипа.
   ```
2. `test_config.py` — новый раздел перед блоком-заголовком `# E. Мульти-интервальная история` (после класса `TestValidationWell` DEBT-056; на `ccc5ae3` — `:961-963`, рамка `# ═══…` над заголовком — якорь `Edit` вместе с ней):
   ```python
   # ═════════════════════════════════════════════════════════════
   # D2. Мёртвые поля (DEBT-008): удалены, проверены или переданы решателю
   # ═════════════════════════════════════════════════════════════

   # Удалённые из схемы ключи (секция, ключ). Решатель их не читал: абсурдные
   # значения 12 полей проходили _validate и фабрику, прототип считал со своими
   # умолчаниями (vault/issues/debt-008/probes/red_state.out.txt). Поэтому старый
   # конфиг загружается — ключ пропускается с предупреждением, результат тот же.
   _REMOVED = [("rock", "p_ref"), ("time", "start_day"),
               ("numerics", "dt_min"), ("numerics", "dt_max"),
               ("numerics", "newton_rtol"), ("numerics", "newton_atol"),
               ("output", "format")]

   _SECTION_CLASSES = {"rock": RockConfig, "time": TimeConfig,
                       "numerics": NumericsConfig, "output": OutputConfig}


   class TestRemovedKeys:
       """Удалённые из схемы ключи: предупреждение и пропуск (DEBT-008)."""

       @pytest.mark.parametrize("section, key", _REMOVED,
                                ids=[f"{s}.{k}" for s, k in _REMOVED])
       def test_warns_and_loads(self, tmp_path, caplog, section, key):
           """Старый конфиг с удалённым ключом загружается; в журнале — имя ключа и DEBT-008."""
           raw = _minimal_raw()
           raw.setdefault(section, {})[key] = "npz" if key == "format" else 1.0
           with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
               cfg = load_config(_write_json(tmp_path, raw))
           # Поля в объекте нет: значение не могло никуда попасть
           assert not hasattr(getattr(cfg, section), key)
           text = "\n".join(r.getMessage() for r in caplog.records
                            if r.levelno >= logging.WARNING)
           assert f"{section}.{key}" in text and "DEBT-008" in text

       def test_removed_keys_are_not_fields(self):
           """Удалённый ключ не совпадает с живым полем: пропуск не прячет настоящий параметр."""
           for section, key in _REMOVED:
               names = {f.name for f in fields(_SECTION_CLASSES[section])}
               assert key not in names, f"{section}.{key} — поле dataclass"

       def test_unknown_key_still_rejected(self, tmp_path):
           """Опечатка вне списка удалённых — по-прежнему отказ, а не молчаливый пропуск."""
           raw = _minimal_raw()
           raw["numerics"] = {"newton_max_itr": 15}
           with pytest.raises(TypeError, match="newton_max_itr"):
               load_config(_write_json(tmp_path, raw))

       def test_no_warning_before_error(self, tmp_path, caplog):
           """Удалённый ключ и ошибка в другом поле → ValueError без предупреждений.

           Порядок DEBT-056 (load_config): предупреждения — только после всех
           проверок _validate, конфиг с ошибкой их не выдаёт. Ловит журнал
           удалённых ключей в _drop_removed_keys, до разбора секций.
           """
           raw = _minimal_raw()
           raw["time"]["start_day"] = 0.0
           raw["rock"]["porosity"] = 1.5
           with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
               with pytest.raises(ValueError, match="porosity"):
                   load_config(_write_json(tmp_path, raw))
           assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

       def test_project_configs_have_no_removed_keys(self):
           """В configs/ и tests/data/ удалённых ключей нет — загрузка без предупреждений.

           Конфиги примеров — test_examples.py::TestConfigs::test_no_removed_keys.
           Без этой чистки test_in_range_no_warnings (configs/table_pvt) и
           test_no_range_warnings (configs/baseline.json) ловили бы предупреждение.
           """
           root = Path(__file__).parent.parent
           paths = (sorted((root / "configs").rglob("*.json"))
                    + sorted((root / "tests" / "data").glob("*/config.json")))
           assert len(paths) >= 8
           for path in paths:
               raw = json.loads(path.read_text(encoding="utf-8"))
               for section, key in _REMOVED:
                   assert key not in raw.get(section, {}), \
                       f"{path.relative_to(root)}: {section}.{key}"


   class TestLiteralValidation:
       """Строковые литералы grid.type и output.log_level (DEBT-008)."""

       @pytest.mark.parametrize("value", ["cartesian", 1], ids=["cartesian", "int"])
       def test_grid_type_rejected(self, tmp_path, value):
           """Сетки, которой нет, — отказ; до DEBT-008 расчёт молча шёл на логарифмической."""
           raw = _minimal_raw()
           raw["grid"]["type"] = value
           with pytest.raises(ValueError, match=r"grid\.type"):
               load_config(_write_json(tmp_path, raw))

       @pytest.mark.parametrize("value", ["DEBG", "", 5], ids=["typo", "empty", "int"])
       def test_log_level_rejected(self, tmp_path, value):
           """Опечатка в уровне журнала — отказ; до DEBT-008 setup_logging молча ставил INFO."""
           raw = _minimal_raw()
           raw["output"] = {"log_level": value}
           with pytest.raises(ValueError, match=r"output\.log_level"):
               load_config(_write_json(tmp_path, raw))

       def test_log_level_case_insensitive(self, tmp_path):
           """«debug» допустим: setup_logging приводит имя к верхнему регистру (log.py)."""
           raw = _minimal_raw()
           raw["output"] = {"log_level": "debug"}
           assert load_config(_write_json(tmp_path, raw)).output.log_level == "debug"


   class TestNumericsWiredFields:
       """Поля Ньютона, которые фабрика и адаптер передают прототипу (DEBT-008)."""

       @pytest.mark.parametrize("key", ["newton_max_iter", "max_active_set_iter"])
       @pytest.mark.parametrize("value", [0, 2.5, True], ids=["zero", "fraction", "bool"])
       def test_int_field_rejected(self, tmp_path, key, value):
           """Лимит итераций — целое ≥ 1: при 0 Ньютон не делает ни одной итерации, bool — опечатка."""
           raw = _minimal_raw()
           raw["numerics"] = {key: value}
           with pytest.raises(ValueError, match=rf"numerics\.{key} должен быть целым"):
               load_config(_write_json(tmp_path, raw))

       @pytest.mark.parametrize("key", ["rs_switch_tol", "sg_switch_tol"])
       @pytest.mark.parametrize("value", [0.0, -1e-5], ids=["zero", "negative"])
       def test_switch_tol_rejected(self, tmp_path, key, value):
           """Допуск переключения фаз > 0: при −1e-5 газ включался бы в недонасыщенной нефти."""
           raw = _minimal_raw()
           raw["numerics"] = {key: value}
           with pytest.raises(ValueError, match=rf"numerics\.{key} должен быть > 0"):
               load_config(_write_json(tmp_path, raw))

       def test_defaults_match_prototype(self):
           """Умолчания конфига = умолчаниям прототипа и адаптера: без numerics счёт прежний."""
           # Фабрика и адаптер передают эти поля всегда; разойдись умолчания —
           # сменились бы истории всех примеров. Сверка с сигнатурами, а не с
           # числами: смена умолчания в прототипе тоже ловится.
           import inspect
           from radial_blackoil.blackoil import RadialBlackOilModel
           from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
           init = inspect.signature(RadialBlackOilModel.__init__).parameters
           adv = inspect.signature(RadialBlackOilModel.advance).parameters
           ada = inspect.signature(PrototypeHydroAdapter.__init__).parameters
           nc = NumericsConfig()
           assert nc.rs_switch_tol == init["rs_switch_tol"].default
           assert nc.sg_switch_tol == init["sg_switch_tol"].default
           assert nc.newton_max_iter == adv["max_newton"].default == ada["max_newton"].default
           assert (nc.max_active_set_iter == adv["max_active_iter"].default
                   == ada["max_active_iter"].default)
   ```
3. `test_factory_prototype.py`, класс `TestFactoryTablePVT` — после `test_factory_default_max_retries` (`:157-162`; следом — `test_prototype_relperm_from_csv` DEBT-006):
   ```python
       def test_factory_passes_newton_fields(self):
           """Поля Ньютона из конфига доходят до прототипа (DEBT-008).

           До DEBT-008 фабрика их не передавала: прототип считал со своими
           умолчаниями при любом значении в конфиге (проба
           vault/issues/debt-008/probes/red_state.out.txt).
           """
           config = load_config(TABLE_CONFIG)
           nc = config.numerics
           nc.newton_max_iter, nc.max_active_set_iter = 7, 5
           nc.rs_switch_tol, nc.sg_switch_tol = 2e-5, 3e-9
           simulator, _ = SimulatorFactory.from_config(config)
           hydro = simulator._hydro
           assert (hydro._max_newton, hydro._max_active_iter) == (7, 5)
           assert (hydro._model.rs_switch_tol, hydro._model.sg_switch_tol) == (2e-5, 3e-9)

       def test_factory_default_newton_fields(self):
           """Без numerics в конфиге — умолчания прототипа: 15, 12, 1e-5, 1e-9."""
           config = load_config(TABLE_CONFIG)
           simulator, _ = SimulatorFactory.from_config(config)
           hydro = simulator._hydro
           assert (hydro._max_newton, hydro._max_active_iter) == (15, 12)
           assert (hydro._model.rs_switch_tol, hydro._model.sg_switch_tol) == (1e-5, 1e-9)
   ```
   Класс `TestInitialStateVsTable` — после `test_p0_1pa_below_pb_passes` (`:446-450`):
   ```python
       def test_supersaturation_tolerance_from_config(self):
           """Допуск пересыщения старта — numerics.rs_switch_tol (DEBT-008).

           p0 на 1 Па ниже p_b(30): избыток R_s 3e-6. При умолчании 1e-5 старт
           допустим (тест выше), при допуске 1e-6 — нет: проверка берёт тот же
           допуск, по которому решатель включает газ. До DEBT-008 допуск 1e-5 был
           зашит в фабрике (проба red_state.out.txt, п. 4).
           """
           config = load_config(TABLE_CONFIG)
           config.initial_conditions.p0 = 15e6 - 1.0
           config.numerics.rs_switch_tol = 1e-6
           with pytest.raises(ValueError, match="пересыщено"):
               SimulatorFactory.from_config(config)
   ```
4. `test_prototype_adapter.py` — в конец файла:
   ```python
   # ═══════════════════════════════════════════════════════════
   # Лимиты Ньютона из конфига (DEBT-008)
   # ═══════════════════════════════════════════════════════════

   class TestNewtonLimits:
       """Адаптер передаёт лимиты Ньютона в каждый вызов прототипа (DEBT-008).

       До DEBT-008 адаптер звал advance(proto_state, dt), и поля
       numerics.newton_max_iter, max_active_set_iter ни на что не влияли.
       Решения здесь нет: подмена возвращает исходное состояние как
       сошедшееся и записывает переданные ключевые аргументы.
       """

       @staticmethod
       def _recorder(calls, name, phase_switching=False):
           def call(proto_state, dt, **kw):
               calls.append((name, kw))
               return proto_state, SimpleNamespace(
                   converged=True, phase_switching=phase_switching,
                   iterations=0, residual_inf=0.0)
           return call

       def test_limits_reach_advance(self, model, our_grid, our_pvt,
                                     initial_state, bc, monkeypatch):
           """Лимиты из конструктора — ключевыми аргументами advance."""
           adapter = PrototypeHydroAdapter(model, our_grid, our_pvt,
                                           max_newton=7, max_active_iter=5)
           calls = []
           monkeypatch.setattr(model, "advance", self._recorder(calls, "advance"))
           adapter.solve(initial_state, dt=DT, bc=bc)
           assert calls == [("advance", dict(max_active_iter=5, max_newton=7))]

       def test_default_limits_are_prototype_defaults(self, model, adapter,
                                                      initial_state, bc, monkeypatch):
           """Адаптер без лимитов (фикстура) передаёт 12 и 15 — умолчания advance."""
           calls = []
           monkeypatch.setattr(model, "advance", self._recorder(calls, "advance"))
           adapter.solve(initial_state, dt=DT, bc=bc)
           assert calls == [("advance", dict(max_active_iter=12, max_newton=15))]

       def test_limits_reach_fourth_stage_by_memory(self, model, our_grid, our_pvt,
                                                    initial_state, bc, monkeypatch):
           """Шаг по памяти ступени 4 (DEBT-048) получает те же лимиты, что advance."""
           # Память включается после STAGE4_MEMORY принятых подряд шагов ступени 4
           # на продолжении траектории; подмена сообщает phase_switching=True.
           from gpn_multiphase_solver.hydro.prototype_adapter import STAGE4_MEMORY
           adapter = PrototypeHydroAdapter(model, our_grid, our_pvt,
                                           max_newton=7, max_active_iter=5)
           calls = []
           monkeypatch.setattr(model, "advance",
                               self._recorder(calls, "advance", phase_switching=True))
           monkeypatch.setattr(model, "advance_fourth_stage",
                               self._recorder(calls, "fourth", phase_switching=True))
           state = initial_state
           for _ in range(STAGE4_MEMORY + 1):
               state = adapter.solve(state, dt=DT, bc=bc).state
           assert [name for name, _ in calls] == ["advance"] * STAGE4_MEMORY + ["fourth"]
           assert all(kw == dict(max_active_iter=5, max_newton=7) for _, kw in calls)
   ```
   `SimpleNamespace` уже импортирован (`:20`); фикстуры `model`, `our_grid`, `our_pvt`, `adapter`, `initial_state`, `bc` — `:96-134`.
5. `test_rs_analytics.py`:
   - шапка (`:5`): `Rs <= Rs_eq(p) + RS_TOL —` → `Rs <= Rs_eq(p) + rs_switch_tol —`;
   - `test_supersaturation_within_solver_tolerance_is_accepted` (`:170-190`) целиком. До — см. файл. После:
     ```python
     def test_supersaturation_within_solver_tolerance_is_accepted(capsys):
         """Пересыщение до rs_switch_tol — состояние, принятое решателем; сверх — нарушение.

         Прототип включает газ в ячейке только при Rs > Rs_eq(p) + rs_switch_tol
         (blackoil.py, _advance_phases): ячейка с меньшим пересыщением остаётся
         однофазной законно. Допуск проверки — numerics.rs_switch_tol конфига, тот
         же, что фабрика передаёт прототипу (DEBT-008); равенство умолчания конфига
         умолчанию прототипа — test_config.py::test_defaults_match_prototype.
         """
         cfg, pvt = _case("04_table_table")
         tol = cfg.numerics.rs_switch_tol
         p = [10, 12, 13]
         regime = [1, 2, 2]
         Rs = pvt.Rs_eq(np.array(p, float) * MPA)
         Rs[1] += 0.5 * tol     # в пределах допуска решателя
         Rs[2] += 2.0 * tol     # сверх допуска: решатель включил бы газ
         rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
         assert rep["n_supersaturated"] == 1
     ```
   - сразу после него:
     ```python
     def test_supersaturation_tolerance_from_config(capsys):
         """Допуск пересыщения — numerics.rs_switch_tol конфига, а не константа модуля (DEBT-008).

         С допуском решателя 1e-4 однофазная ячейка с пересыщением 2e-5 —
         законное состояние; с константой 1e-5 проверка печатала бы нарушение.
         """
         cfg, pvt = _case("04_table_table")
         p = [10, 12, 13]
         regime = [1, 2, 2]
         Rs = pvt.Rs_eq(np.array(p, float) * MPA)
         Rs[2] += 2e-5                          # сверх умолчания 1e-5
         assert _report(cfg, _history(p, Rs, regime), pvt, capsys)["n_supersaturated"] == 1
         cfg.numerics.rs_switch_tol = 1e-4      # решатель с таким допуском газ не включил бы
         assert _report(cfg, _history(p, Rs, regime), pvt, capsys)["n_supersaturated"] == 0
     ```
6. `test_examples.py`, `TestConfigs.test_no_dead_output_format` (`:202-211`, с декоратором `@pytest.mark.parametrize`) заменить:
   ```python
       @pytest.mark.parametrize("name", ALL_EXAMPLES)
       def test_no_removed_keys(self, name):
           """В конфигах примеров нет ключей, удалённых из схемы (DEBT-008).

           Загрузчик пропускает их с предупреждением; в примере такой ключ
           внушал бы, что поле на что-то влияет (до DEBT-008 — output.format,
           numerics.dt_min, dt_max, time.start_day: объявлены, но не читались).
           """
           raw = json.loads((EXAMPLES_DIR / name / "config.json").read_text(encoding="utf-8"))
           removed = {"rock": ("p_ref",), "time": ("start_day",),
                      "numerics": ("dt_min", "dt_max", "newton_rtol", "newton_atol"),
                      "output": ("format",)}
           for section, keys in removed.items():
               for key in keys:
                   assert key not in raw.get(section, {}), f"{name}: {section}.{key}"
   ```

**Проверка после шага** (из `$WT`):
```powershell
& $PY -m pytest tests/test_config.py tests/test_factory_prototype.py tests/test_prototype_adapter.py tests/test_rs_analytics.py tests/test_examples.py::TestConfigs -q
```
Ожидание — **падают ровно**:
- `test_config.py` — 25: `TestRemovedKeys::test_warns_and_loads` (7: поле есть, `hasattr` истинно), `test_removed_keys_are_not_fields`, `test_project_configs_have_no_removed_keys`; `TestLiteralValidation::test_grid_type_rejected` (2), `test_log_level_rejected` (3); `TestNumericsWiredFields::test_int_field_rejected` (6: проверки нет), `test_switch_tol_rejected` (4), `test_defaults_match_prototype` (`KeyError: 'max_newton'` у адаптера). Зелёные: `test_unknown_key_still_rejected`, `TestRemovedKeys::test_no_warning_before_error` (страж порядка: сейчас ключ — поле, предупреждений нет), `test_log_level_case_insensitive`;
- `test_factory_prototype.py` — 3 (`AttributeError: _max_newton`; старт принят);
- `test_prototype_adapter.py` — 3 (`TypeError: unexpected keyword argument 'max_newton'`; у фикстуры — `calls` с пустыми аргументами);
- `test_rs_analytics.py` — 1 (`test_supersaturation_tolerance_from_config`: константа 1e-5 → 1 вместо 0);
- `test_examples.py::TestConfigs::test_no_removed_keys` — 23 (все примеры: `start_day`, у 01–17, 19–21 и `dt_min`, `dt_max`; `ALL_EXAMPLES` с примером 18).

Итого 55. Любое другое падение — разобрать.
**Регресс:** быстрый — упавших ровно 55 (те же), остальное зелёное.
**Зависимости:** требует шаг 0. Блокирует: 2–5.
**Оценка:** ~200 строк, ~30 мин.

### Шаг 2: JSON-конфиги — удалённые ключи

**Цель:** 31 конфиг репозитория без `start_day`, `dt_min`, `dt_max`, `format` и конвертер примера 18 без `start_day` — до удаления полей из dataclass (раздел 1, «Тесты, требующие ни одного предупреждения»).

**Файлы:** `numerical_solver/examples/*/config.json` (23, с примером 18), `numerical_solver/configs/baseline.json`, `configs/val001.json`, `configs/table_pvt/config.json`, `numerical_solver/tests/data/*/config.json` (5); `numerical_solver/examples/18_prototype_input/prototype_input.py`. Скрипт: `vault/issues/debt-008/probes/strip_removed_keys.py` (готов, проверен при планировании и аудите 1).

**Контекст.** Скрипт вырезает строку ключа целиком (форматирование, числа, порядок ключей остаются), у предыдущей строки снимает запятую, если ключ был последним в объекте (`output.format` в `configs/`), и сверяет `json.loads` результата с исходным JSON без удалённых ключей — расхождение даёт отказ без записи. `deliverables/` (не в git) и пробы vault не трогаются. `config.json` примера 18 порождается конвертером книги прототипа (`prototype_input.py`, `convert`), и `test_examples.py::TestPrototypeInput::test_files_reproduce_conversion` сверяет его построчно с выводом конвертера — без правки конвертера тест упадёт. Проба аудита `$P\audit1_converter18.py`: конвертер без ключа и скрипт дают один и тот же файл.

**Что сделать** (из `$WT`):
```powershell
& $PY $P\strip_removed_keys.py            # проверка: «файлов: 31, меняется: 31»
& $PY $P\strip_removed_keys.py --write
git status --short -- examples configs tests/data   # 31 изменённый config.json / *.json
git diff --stat -- examples configs tests/data      # −3 строки у примеров 01–17, 19–21 и tests/data, −1 у 18, −4 у configs/
```
Конвертер `examples/18_prototype_input/prototype_input.py`, `convert` (`:184`). До:
```python
        "time": {"start_day": 0.0, "dt_integration": float(m["DTMAX"]) * 60.0,
                 "history": history},
```
После:
```python
        # start_day не пишется: поле удалено из схемы (DEBT-008), время истории — от 0
        "time": {"dt_integration": float(m["DTMAX"]) * 60.0,
                 "history": history},
```
Комментарий над `"time"` (`:181-183`, про шаг интегрирования = DTMAX) — оставить, новую строку — под ним, перед `"time"`.

**Проверка:**
- `& $PY -m pytest tests/test_examples.py::TestConfigs tests/test_examples.py::TestPrototypeInput tests/test_config.py::TestRemovedKeys -q -m "not slow"` — `test_no_removed_keys` (23), `test_files_reproduce_conversion`, `test_project_configs_have_no_removed_keys` зелёные; `test_warns_and_loads` (7), `test_removed_keys_are_not_fields` — ещё красные.
- **Регресс:** быстрый — упавших 31 (55 − 24). Поля в dataclass ещё есть, умолчания те же — расчёты не меняются.
**Зависимости:** требует шаг 1. Блокирует: шаг 3.
**Оценка:** ~5 мин.

### Шаг 3: `io/config.py` — удаление полей, пропуск старых ключей, проверки

**Цель:** схема без 7 полей; удалённые ключи — предупреждение (после `_validate`) и пропуск; `grid.type`, `log_level`, лимиты и допуски Ньютона проверяются.

**Файлы:** `numerical_solver/gpn_multiphase_solver/io/config.py`, `numerical_solver/tests/test_config.py`.

**Изменения** (номера строк — `ccc5ae3`):

1. `GridConfig.type` (`:35`). До: `    type: str = "log_radial"     # тип сетки (пока только log_radial)`. После:
   ```python
       type: str = "log_radial"     # тип сетки: только "log_radial" (проверка — _validate, DEBT-008)
   ```
2. `RockConfig`, конец (`:50-52`). До:
   ```python
       # Компрессия породы (пока не используется)
       p_ref: float = 1e7              # опорное давление, Па
       compressibility: float = 0.0    # c_r, 1/Па
   ```
   После:
   ```python
       # Сжимаемость породы: прототип считает φ(p) = porosity·exp(c_r·(p − p0)),
       # porosity задана при начальном давлении initial_conditions.p0 (factory.py,
       # CompressibleRock). Опорного давления в конфиге нет (DEBT-008): пара
       # (φ_ref, p_ref) пересчитывается точно — porosity = φ_ref·exp(c_r·(p0 − p_ref)).
       # Энергия берёт постоянную porosity (energy/tridiag.py) — при c_r ≠ 0 см. DEBT-057.
       compressibility: float = 0.0    # c_r, 1/Па
   ```
3. `TimeConfig` (`:134`): строку `    start_day: float = 0.0                 # начало истории, сут` удалить.
4. `NumericsConfig` (`:141-155`) — от докстринга до `linear_solver` включительно. До:
   ```python
       """Параметры численного метода; часть полей никто не читает (DEBT-008)."""
       # Читаются: skin, jacobian_mode, linear_solver, newton_cell_tol — фабрика (прототипу),
       # max_retries — Simulator. Не читаются: dt_min, dt_max; newton_max_iter, newton_rtol,
       # newton_atol, max_active_set_iter, rs_switch_tol, sg_switch_tol (прототип — свои умолчания).
       dt_min: float = 1.0                    # минимальный шаг, с
       dt_max: float = 86400.0                # максимальный шаг, с
       skin: float = 0.0                      # скин-фактор: ≥ 0, > 50 — предупреждение (DEBT-056)
       newton_max_iter: int = 15
       newton_rtol: float = 1e-8
       newton_atol: float = 1e-11
       max_active_set_iter: int = 12
       rs_switch_tol: float = 1e-5
       sg_switch_tol: float = 1e-9
       jacobian_mode: str = "grouped"
       linear_solver: str = "sparse"
   ```
   После:
   ```python
       """Параметры численного метода — фабрике, адаптеру прототипа и Simulator (DEBT-008)."""
       skin: float = 0.0                      # скин-фактор: ≥ 0, > 50 — предупреждение (DEBT-056)
       # Лимиты Ньютона прототипа: адаптер передаёт их в каждый advance (DEBT-008).
       # Умолчания — умолчания RadialBlackOilModel.advance (тест test_defaults_match_prototype).
       # Ступень 4 advance (BUG-020, _newton_switching) их не читает: у неё свой предел
       # 40 итераций и один проход набора фаз.
       newton_max_iter: int = 15              # итераций Ньютона при фиксированном наборе фаз
       max_active_set_iter: int = 12          # проходов уточнения набора фаз (газ есть / нет)
       # Допуски переключения фаз прототипа: фабрика передаёт их в конструктор модели
       # (DEBT-008). Газ включается в ячейке при R_s > R_s,eq(p) + rs_switch_tol
       # (м³ст/м³ст), выключается при S_g < −sg_switch_tol. rs_switch_tol — ещё и допуск
       # проверки пересыщения старта (factory._check_undersaturated_start, BUG-017) и
       # проверки R_s примеров (examples/rs_analytics.py, DEBT-026).
       rs_switch_tol: float = 1e-5
       sg_switch_tol: float = 1e-9
       # Якобиан и решатель СЛАУ прототипа (допустимые значения проверяет его конструктор)
       jacobian_mode: str = "grouped"
       linear_solver: str = "sparse"
   ```
   Блок `max_retries` (`:156-165`) не трогать. В блоке `newton_cell_tol` (BUG-022) последнюю строку комментария (`:179`). До: `    # Передаётся прототипу (cell_tol), в отличие от newton_atol и newton_rtol (DEBT-008).` После:
   ```python
       # Передаётся прототипу (cell_tol). Допуски абсолютного критерия (atol, rtol) —
       # умолчания прототипа, в конфиге их нет (DEBT-008).
   ```
5. `OutputConfig` (`:186-191`). До:
   ```python
       """Параметры вывода."""
       log_level: str = "INFO"
       format: str = "npz"       # формат записи: "npz" или "csv"
   ```
   После:
   ```python
       """Параметры вывода."""
       # Уровень журнала: DEBUG, INFO, WARNING, ERROR, CRITICAL без учёта регистра (иное
       # значение отвергает _validate, DEBT-008). Формата записи в конфиге нет: файл
       # выбирает вызывающий код (io/output.py: save_npz, save_csv).
       log_level: str = "INFO"
   ```
6. Перед заголовком `# ── Загрузка ───…` над `def load_config` (`:298`; выше — раздел FEAT-018 «Краткие формы time.history» с `_expand_history`), отделив двумя пустыми строками:
   ```python
   # Поля, удалённые из схемы конфига (DEBT-008): объявлялись, но решатель их не
   # читал. Старый конфиг с ними загружается — ключ пропускается с предупреждением:
   # результат расчёта от этого не меняется, поле игнорировалось и раньше. Иначе
   # с save_every (DEBT-013): его пропуск менял бы состав вывода, поэтому — отказ.
   # Неизвестный ключ вне этого списка — по-прежнему ошибка распаковки dataclass.
   _NEWTON_TOL_REMOVED = ("допуски абсолютного критерия Ньютона — умолчания прототипа "
                          "(rtol = 1e-8, atol = 1e-11 м³ст/с); условие по ячейке — "
                          "numerics.newton_cell_tol")
   _STEP_REMOVED = ("шаг задаёт time.dt_integration, глубину дробления шага — "
                    "numerics.max_retries")
   _REMOVED_KEYS = {
       "rock": {"p_ref": "пористость rock.porosity задаётся при начальном давлении p0; "
                         "пару (φ_ref, p_ref) пересчитайте: "
                         "porosity = φ_ref·exp(c_r·(p0 − p_ref))"},
       "time": {"start_day": "время расчёта отсчитывается от начала истории, t = 0"},
       "numerics": {"dt_min": _STEP_REMOVED, "dt_max": _STEP_REMOVED,
                    "newton_rtol": _NEWTON_TOL_REMOVED, "newton_atol": _NEWTON_TOL_REMOVED},
       "output": {"format": "формат записи выбирает вызывающий код "
                            "(io/output.py: save_npz, save_csv)"},
   }

   # Уровни журнала, которые принимает output.log_level (без учёта регистра)
   _LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


   def _drop_removed_keys(raw: dict) -> list[str]:
       """Удалённые из схемы ключи (DEBT-008): убрать из raw, вернуть тексты предупреждений."""
       messages = []
       for section, keys in _REMOVED_KEYS.items():
           sec = raw.get(section)
           if not isinstance(sec, dict):
               continue
           for key, why in keys.items():
               if key in sec:
                   del sec[key]
                   messages.append(
                       f"{section}.{key} удалён из конфига (DEBT-008) и пропущен — "
                       f"решатель его не читал, результат не меняется: {why}.")
       return messages
   ```
   Контракт: `raw` — словарь из `json.load` (меняется на месте, как и прежде меняется `raw["time"]`); секция не словарь или отсутствует — пропускается (её отсутствие или тип ловит дальнейший код); ключей нет — пустой список.
7. `load_config` (`:300-365`), две вставки:
   - после цикла обязательных секций (`:310-314`), перед `geometry = GeometryConfig(**raw["geometry"])`:
     ```python

         # Ключи, удалённые из схемы (DEBT-008), — до распаковки секций: иначе
         # строгая распаковка dataclass дала бы TypeError про лишний аргумент.
         # Предупреждения о них — после _validate (порядок DEBT-056, ниже).
         removed = _drop_removed_keys(raw)
     ```
   - после `_validate(config)` и его комментария «Предупреждения — после всех проверок _validate…» (`:359-361`), перед `_warn_large_skin(config)`:
     ```python
         for message in removed:
             user_log.warning(message)
     ```
8. `_validate` — после проверки `grid.N` (`:425-426`):
   ```python

       # grid.type (DEBT-008): фабрика строит только логарифмическую радиальную сетку
       # (LogRadialGrid). До DEBT-008 любое значение проходило молча — расчёт шёл на
       # той же сетке (vault/issues/debt-008/probes/red_state.out.txt).
       if cfg.grid.type != "log_radial":
           raise ValueError(
               f"grid.type: поддерживается только \"log_radial\", получено {cfg.grid.type!r}")
   ```
9. `_validate` — в конец, после блока `newton_cell_tol` (BUG-022, `:545-552`; переменной `nc` в `_validate` до этого места нет):
   ```python

       # Лимиты Ньютона прототипа (DEBT-008; адаптер передаёт их в advance) — целые ≥ 1.
       # bool исключается явно, как у max_retries; NaN отсёк _check_numeric_fields.
       nc = cfg.numerics
       for name in ("newton_max_iter", "max_active_set_iter"):
           v = getattr(nc, name)
           if isinstance(v, bool) or not isinstance(v, int) or v < 1:
               raise ValueError(f"numerics.{name} должен быть целым ≥ 1, получено {v!r}")
       # Допуски переключения фаз (DEBT-008; фабрика — в конструктор модели) — > 0.
       # Ноль снял бы запас на шум ~1e-13 горизонтальной ветви PVT-таблицы: газ
       # включался бы в недонасыщенных ячейках, а проверка старта отвергала бы p0
       # на 1 Па ниже p_b. Тип и конечность проверил _check_numeric_fields.
       for name in ("rs_switch_tol", "sg_switch_tol"):
           v = getattr(nc, name)
           if not v > 0:
               raise ValueError(f"numerics.{name} должен быть > 0, получено {v}")

       # output.log_level (DEBT-008): setup_logging (log.py) неизвестное имя молча
       # заменял на INFO — опечатка «DEBG» прятала отладочный вывод.
       lvl = cfg.output.log_level
       if not isinstance(lvl, str) or lvl.upper() not in _LOG_LEVELS:
           raise ValueError(
               f"output.log_level должен быть одним из {', '.join(_LOG_LEVELS)} "
               f"(регистр не важен), получено {lvl!r}")
   ```
10. `test_config.py` — старые тесты удалённых полей:
    - удалить `TestBaselineTime.test_start_day` (`:164-165`), `TestBaselineNumerics.test_dt_min` и `test_dt_max_default` (`:197-202`), `TestBaselineOutput.test_format` (`:220-221`);
    - `TestOptionalSections.test_no_numerics_uses_defaults` (`:286`): `assert cfg.numerics.dt_min == 1.0` → `assert cfg.numerics.max_active_set_iter == 12`;
    - `test_no_output_uses_defaults` (`:293`): строку `assert cfg.output.format == "npz"` удалить;
    - `TestValidationNumbers.test_field_list_covers_known_fields` (`:713-721`): докстринг «…их не меньше 37.» → «…их не меньше 31.»; `assert len(_FLOAT_FIELDS) >= 37` → `assert len(_FLOAT_FIELDS) >= 31` и над ним комментарий `# 37 до DEBT-008: удалены p_ref, start_day, dt_min, dt_max, newton_rtol, newton_atol`.

**Проверка после шага:**
- `& $PY -m pytest tests/test_config.py -q` — зелёные все, кроме `test_defaults_match_prototype` (адаптеру нужен шаг 4).
- **Регресс:** быстрый — упавших 8: `test_defaults_match_prototype`, 3 фабрики, 3 адаптера, 1 `rs_analytics`.
**Подводные камни:** 2.4 «Порядок шагов», «Порядок предупреждений (DEBT-056)», «Предупреждение до setup_logging», «`grid.type` не строкой».
**Зависимости:** требует шаг 2. Блокирует: 4.
**Оценка:** ~85 строк, ~25 мин.

### Шаг 4: Фабрика и адаптер — передача полей Ньютона

**Цель:** `rs_switch_tol`, `sg_switch_tol` — в конструктор модели; лимиты — в каждый `advance`; допуск пересыщения старта — из конфига.

**Файлы:** `numerical_solver/gpn_multiphase_solver/factory.py`, `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`.

**Изменения:**

1. `factory.py`, вызов (`:58`). До: `        _check_undersaturated_start(config.initial_conditions, pvt)`. После:
   ```python
           _check_undersaturated_start(config.initial_conditions, pvt,
                                       config.numerics.rs_switch_tol)
   ```
2. `factory.py`, константа и функция (`:273-291`). До:
   ```python
   # Допуск пересыщения на старте, м³ст/м³ст, — rs_switch_tol решателя
   # (RadialBlackOilModel, blackoil.py:32; фабрика его не меняет): проверка
   # отвергает ровно те состояния, которые решатель при давлении p0 счёл бы
   # пересыщенными. Округление ввода не мешает: p0 на 1 Па ниже p_b даёт избыток
   # ~6e-6 (Стендинг, Rs0 = 50) и 3e-6 (таблица 0/30).
   _RS0_SUPERSAT_TOL = 1e-5


   def _check_undersaturated_start(ic, pvt) -> None:
       """Начальное состояние недонасыщенное: Rs0 <= Rs_eq(p0), иначе ValueError (BUG-017)."""
   ```
   После:
   ```python
   def _check_undersaturated_start(ic, pvt, rs_tol: float) -> None:
       """Начальное состояние недонасыщенное: Rs0 <= Rs_eq(p0) + rs_tol, иначе ValueError (BUG-017)."""
       # Допуск rs_tol, м³ст/м³ст, — numerics.rs_switch_tol, тот же, что фабрика
       # передаёт решателю (DEBT-008): проверка отвергает ровно те состояния,
       # которые решатель при давлении p0 счёл бы пересыщенными. При умолчании
       # 1e-5 округление ввода не мешает: p0 на 1 Па ниже p_b даёт избыток ~6e-6
       # (Стендинг, Rs0 = 50) и 3e-6 (таблица 0/30).
   ```
   и в теле: `if ic.Rs0 > Rs_eq + _RS0_SUPERSAT_TOL:` → `if ic.Rs0 > Rs_eq + rs_tol:`. Остальные комментарии функции не трогать.
3. `factory.py`, `CompressibleRock` (`:410-415`). Комментарий `    # Порода прототипа (p_ref в бар, cr в 1/бар)` заменить:
   ```python
       # Порода прототипа (p_ref в бар, cr в 1/бар): φ(p) = porosity·exp(c_r·(p − p0)).
       # Опорное давление — начальное p0: rock.porosity задана при p0, поля p_ref
       # в конфиге нет (DEBT-008).
   ```
4. `factory.py`, `RadialBlackOilModel(...)` — после строки `        skin=nc.skin,`:
   ```python
           # Допуски переключения фаз (DEBT-008): газ включается в ячейке при
           # Rs > Rs_eq(p) + rs_switch_tol, выключается при Sg < −sg_switch_tol.
           rs_switch_tol=nc.rs_switch_tol,
           sg_switch_tol=nc.sg_switch_tol,
   ```
5. `factory.py`, последняя строка `_create_prototype_hydro` (`:457`; над ней — комментарий DEBT-006 «Пересчёт потоков (Q, u, m) — тем же объектом FullPVT…», `:452-456`, не трогать). До:
   ```python
       return PrototypeHydroAdapter(model, grid, pvt)
   ```
   После:
   ```python
       # Лимиты Ньютона (DEBT-008): адаптер передаёт их в каждый вызов advance
       return PrototypeHydroAdapter(model, grid, pvt,
                                    max_newton=nc.newton_max_iter,
                                    max_active_iter=nc.max_active_set_iter)
   ```
6. `prototype_adapter.py`, конструктор (`:60-78`). Сигнатура `(self, model, grid: Grid, pvt: HydroPVT, stage4_memory: int | None = STAGE4_MEMORY):` — вторую строку заменить:
   ```python
                    stage4_memory: int | None = STAGE4_MEMORY,
                    max_newton: int = 15, max_active_iter: int = 12):
   ```
   В докстринг — после описания `stage4_memory` (`:66-67`):
   ```
           max_newton      — итераций Ньютона на одно решение при фиксированном наборе
                             фаз (numerics.newton_max_iter, DEBT-008)
           max_active_iter — проходов уточнения набора фаз (numerics.max_active_set_iter)
   ```
   В тело — после `self._stage4_key = None` (`:78`):
   ```python
           # Лимиты Ньютона прототипа (DEBT-008): передаются в каждый вызов advance и
           # advance_fourth_stage. Умолчания — умолчания advance (blackoil.py): адаптер,
           # созданный без них (тесты), считает как прежде. Ступень 4 (_newton_switching)
           # их не читает — у неё свой предел 40 итераций; передаются и ей, чтобы шаг по
           # памяти (DEBT-048) оставался побитово шагом advance после трёх отказов.
           self._max_newton = max_newton
           self._max_active_iter = max_active_iter
   ```
7. `prototype_adapter.py`, `solve`, шаг 3 (`:146-149`). До:
   ```python
           if by_memory:
               new_proto, report = m.advance_fourth_stage(proto_state, dt)
           else:
               new_proto, report = m.advance(proto_state, dt)
   ```
   После:
   ```python
           limits = dict(max_active_iter=self._max_active_iter, max_newton=self._max_newton)
           if by_memory:
               new_proto, report = m.advance_fourth_stage(proto_state, dt, **limits)
           else:
               new_proto, report = m.advance(proto_state, dt, **limits)
   ```

**Проверка после шага:**
- `& $PY -m pytest tests/test_config.py tests/test_factory_prototype.py tests/test_prototype_adapter.py tests/test_factory_standing_hydro.py tests/test_prototype_stage4_memory.py -q -m "not slow"` — зелёные (`test_prototype_stage4_memory.py` — подмены `advance`/`advance_fourth_stage` с `**kwargs` и конструктор с `stage4_memory=`).
- **Регресс:** быстрый — упавший 1: `test_rs_analytics.py::test_supersaturation_tolerance_from_config`.
**Подводные камни:** 2.4 «Побитовость», «Ступень 4 лимитов не читает».
**Зависимости:** требует шаг 3. Блокирует: 5.
**Оценка:** ~30 строк, ~20 мин.

### Шаг 5: `examples/rs_analytics.py` — допуск из конфига

**Цель:** проверка $R_s$ примеров берёт `config.numerics.rs_switch_tol`; константа `RS_TOL` удалена.

**Файлы:** `numerical_solver/examples/rs_analytics.py`.

**Изменения:**
1. Шапка модуля: строка `:10` «до допуска решателя RS_TOL).» → «до допуска решателя rs_switch_tol).»; строка `:28` «Rs > Rs_eq(p) + RS_TOL, а выключается…» → «Rs > Rs_eq(p) + rs_switch_tol, а выключается…» (выравнивание строк сохранить).
2. Блок от строки `# Допуск пересыщения ячейки без газа, м³ст/м³ст, — допуск переключения фаз` (`:69`) до `RS_TOL = 1e-5` (`:78`) включительно удалить; пустая строка перед ним и две после остаются — между `SG_GAS = 1e-8` и `def rs_expected` две пустые строки (проверено пробой `plan_check.py`).
3. `rs_supersaturation` (`:107-119`). Обоснование допуска переезжает из удалённого блока в комментарий над функцией; докстринг — одна строка (CLAUDE.md, «Docstring — одна строка»), его прежнее продолжение «Возвращает (max_excess, n_bad)…» не трогать. До:
   ```python
   def rs_supersaturation(history, pvt):
       """Пересыщение ячеек без свободного газа: Rs > Rs_eq(p) + RS_TOL.
   ```
   После:
   ```python
   # Допуск пересыщения tol — numerics.rs_switch_tol конфига, м³ст/м³ст (DEBT-008): тот же,
   # что фабрика передаёт решателю. Прототип включает газ в ячейке только при
   # Rs > Rs_eq(p) + rs_switch_tol (blackoil.py, _advance_phases): однофазная ячейка с
   # меньшим пересыщением — принятое решателем состояние, а не дефект; проверка строже
   # решателя давала бы ложные нарушения. Тот же допуск у проверки начального состояния
   # (factory._check_undersaturated_start, BUG-017). Шум ~1e-13 на горизонтальной ветви
   # таблицы (Rs_eq = Rs0 при p >= pb) он покрывает тоже.
   def rs_supersaturation(history, pvt, tol):
       """Пересыщение ячеек без свободного газа: Rs > Rs_eq(p) + tol (tol — numerics.rs_switch_tol).
   ```
   В теле `excess > RS_TOL` → `excess > tol`.
4. `report_rs` (`:206-241`): после `st = history.states[-1]` добавить `    tol = config.numerics.rs_switch_tol      # допуск пересыщения решателя (DEBT-008)`; `rs_supersaturation(history, pvt)` → `rs_supersaturation(history, pvt, tol)`; `st.Rs > Rs0 + RS_TOL` → `st.Rs > Rs0 + tol`; в печати `{RS_TOL:g}` → `{tol:g}` (вывод при умолчании тот же: `1e-05`).
5. Проверка, что констант не осталось: `Select-String -Path examples\*.py, tests\*.py, gpn_multiphase_solver\*.py -Pattern "RS_TOL|_RS0_SUPERSAT_TOL"` — пусто (`gpn_multiphase_solver\*.py` — без подкаталогов, `factory.py` там).

**Проверка после шага:**
- `& $PY -m pytest tests/test_rs_analytics.py tests/test_example_scripts.py -q` — зелёные (`test_example_scripts.py` разбирает AST скриптов `examples/` — DEBT-046: ни один скрипт не импортирует `RS_TOL`).
- **Регресс:** быстрый — **все зелёные**, N_FAST + 19 (на `ccc5ae3` — 1470).
**Зависимости:** требует шаг 4. Блокирует: коммит кода.
**Оценка:** ~15 строк, ~10 мин.

Коммит кода (раздел «Как начать», п. 6).

### Шаг 6: README примеров

**Цель:** README не говорят о полях, которых нет, и о «не читаются».

**Файлы:** 17 `numerical_solver/examples/*/README.md`: 01–10, 13b, 14, 16, 17, 19, 20, 21. Скрипт `vault/issues/debt-008/probes/fix_readmes.py` (готов, проверен при планировании).

**Контекст.** Семь групп текстов (скрипт, список `REPLACEMENTS`): 01–04 и 19–21 — «`grid.type` и `output.format` не трогать: объявлены, но не читаются» → «`grid.type` не трогать: решатель знает только `"log_radial"`, иное значение отвергается при загрузке конфига»; 05–10 (раздел «Не трогать») — то же короче; 13b, 14, 16, 17 — из фразы «шаг задаёт только `time.dt_integration`» убирается хвост про `dt_min`, `dt_max`, `start_day`. Каждая замена — ровно одно вхождение на файл, иначе отказ; после замен в README не должно остаться `dt_min`, `dt_max`, `start_day`, `output.format`, `p_ref`, «не читаются».

**Что сделать** (из `$WT`):
```powershell
& $PY $P\fix_readmes.py            # «README меняется: 17»
& $PY $P\fix_readmes.py --write
git diff --stat -- examples          # 17 README
```

**Проверка:** `& $PY -m pytest tests/test_examples.py::TestReadme tests/test_eq_references.py -q` — зелёные (`test_eq_references.py` проверяет и README примеров, DEBT-010). **Регресс:** `--collect-only -q` (только документы).
**Зависимости:** требует шаг 5 (README описывает итоговое поведение).
**Оценка:** ~5 мин.

### Шаг 7: Заметки vault

**Цель:** спецификация и заметки описывают поля конфига по коду.

**Файлы:** `vault/knowledge/decisions/P8-формат-ввода-json.md`, `vault/knowledge/decisions/json-config-schema.md`, `vault/knowledge/decisions/временная-сетка-и-история.md`, `vault/knowledge/decisions/модули-simulator-оркестратор.md`, `vault/knowledge/decisions/hydro-prototype-анализ.md`, `vault/knowledge/decisions/проверка Rs — равенство только в ячейках со свободным газом, без газа — неравенство с допуском решателя.md`, `vault/knowledge/debugging/пересыщенный старт решатель молча уравновешивает скачком давления.md`.

**Что сделать** (номера строк — на `ccc5ae3`, сверены аудитом 1; якорь `Edit` — по тексту):

1. **P8 §3** (`:126-138`): в образце JSON удалить строку `    "start_day": 0.0,`; строку «`start_day` — дата начала истории (по умолчанию 0). Единицы: сутки.» заменить:
   > Время расчёта отсчитывается от начала истории ($t = 0$). Поле `start_day` удалено ([[DEBT-008]]): решатель его не читал; в старом конфиге — предупреждение и пропуск (§5).

   Перед `### Конвертация TimeSchedule → Schedule` вставить:
   > ⚠️ Проектный этап: функции `_build_prototype_schedule` в коде нет — управление скважиной по интервалам задаёт `Simulator` (`WellControl` интервала, [[временная-сетка-и-история]]). `start_day` в псевдокоде ниже — поле, удалённое [[DEBT-008]].
2. **P8 §4** (`:179-207`): образец JSON (`:181-196`; в нём `"dt_integration": 3600` — поля `numerics` такого нет, загрузка дала бы `TypeError`) заменить:
   ```json
   "numerics": {
       "skin": 0.0,
       "newton_max_iter": 15,
       "max_active_set_iter": 12,
       "rs_switch_tol": 1e-5,
       "sg_switch_tol": 1e-9,
       "jacobian_mode": "grouped",
       "linear_solver": "sparse",
       "max_retries": 9,
       "newton_cell_tol": 1e-8
   }
   ```
   Пункты списка: удалить «`dt_integration` — шаг интегрирования… Дублируется из секции time.» (`:199`) и «`dt_min`, `dt_max` — ⚠️ объявлены…» (`:200`); строку BUG-022 «`jacobian_mode`, `linear_solver`, `newton_cell_tol` — передаются в `RadialBlackOilModel`; `newton_max_iter`, `newton_rtol`, `newton_atol`, `max_active_set_iter`, `*_switch_tol` — ⚠️ не передаются никуда…» (`:204`) и строку «Если параметр не задан в JSON — берётся default из прототипа» (`:205`) заменить на:
   ```
   - `skin`, `jacobian_mode`, `linear_solver`, `newton_cell_tol`, `rs_switch_tol`, `sg_switch_tol` — фабрика передаёт в конструктор `RadialBlackOilModel`
   - `newton_max_iter`, `max_active_set_iter` — лимиты Ньютона ступеней 1–3 `advance`: итераций на одно решение при фиксированном наборе фаз, проходов уточнения набора фаз. Адаптер передаёт их в каждый вызов `advance` и `advance_fourth_stage` ([[DEBT-008]]). Ступень 4 (BUG-020, `_newton_switching`) их не читает: свой предел 40 итераций
   - `rs_switch_tol`, `sg_switch_tol` — допуски переключения фаз: газ включается в ячейке при $R_s > R_s^{eq}(p) +$ `rs_switch_tol` (м³ст/м³ст), выключается при $S_g < -$`sg_switch_tol`. `rs_switch_tol` — ещё и допуск проверки недонасыщенного старта (BUG-017) и проверки $R_s$ примеров (`examples/rs_analytics.py`, DEBT-026)
   - Допуски абсолютного критерия Ньютона ($\|F\|_\infty \le$ atol + rtol·$\max(\|F_0\|_\infty, 10^{-9})$, atol = 1e-11 м³ст/с, rtol = 1e-8) — умолчания прототипа; полей `newton_atol`, `newton_rtol` в конфиге нет ([[DEBT-008]]): прототип не принимает их ни в конструкторе, ни в `advance`
   - Не заданный в JSON параметр берёт умолчание `NumericsConfig` (`io/config.py`); умолчания полей, передаваемых прототипу, равны его умолчаниям (тест `test_defaults_match_prototype`)
   - Удалены ([[DEBT-008]]): `dt_min`, `dt_max` (шаг — `time.dt_integration`, дробление — `max_retries`), `newton_atol`, `newton_rtol`; в старом конфиге — предупреждение и пропуск (§5)
   ```
   Пункты `max_retries` (с уточнением DEBT-041) и `newton_cell_tol` (BUG-022) и «Примечание: dt_integration…» не трогать.
3. **P8 §5** (`:209-262`; таблица «Этап | Где | Что» — DEBT-056, `:213-222`):
   - таблица: первую строку `| \`load_config\` | \`io/config.py\`: \`_check_numeric_fields\`, \`_require_finite_number\` | тип и конечность всех чисел ([[DEBT-051]]) |` (`:215`) заменить двумя:
     ```
     | `load_config` | `io/config.py`: `_drop_removed_keys` (до разбора секций) | удалённые поля ([[DEBT-008]]): ключ убирается, предупреждение — после `_validate` |
     | | `_check_numeric_fields`, `_require_finite_number` | тип и конечность всех чисел ([[DEBT-051]]) |
     ```
     строку `| | \`_validate\` | геометрия, сетка, порода, тепловые параметры, начальные условия, \`dt_integration\`, \`max_retries\`, \`skin\` |` (`:217`) — дописать в конец третьей ячейки «, `grid.type`, `output.log_level`, лимиты и допуски Ньютона (DEBT-008)»; строку `| | \`_warn_large_skin\`, \`_warn_well_shut\` (после \`_validate\`) | …(DEBT-056) |` (`:218`) — во вторую ячейку перед `_warn_large_skin` вписать «предупреждения об удалённых полях, », в третью — в начало «удалённые поля (DEBT-008); »;
   - пункт «- мёртвые поля (DEBT-008) проверяются так же.» (`:238`) удалить;
   - пункт «обе модели PVT: недонасыщенный старт `Rs0 <= Rs_eq(p0)` (допуск 1e-5 м³ст/м³ст)» (`:257`) → «(допуск `numerics.rs_switch_tol`, по умолчанию 1e-5 м³ст/м³ст; DEBT-008)»;
   - в блок BUG-022 «Численные параметры — наш config (`_validate`):» (`:260-262`) дописать:
     ```
     - `numerics.newton_max_iter`, `numerics.max_active_set_iter` — целые ≥ 1, bool отвергается (DEBT-008)
     - `numerics.rs_switch_tol`, `numerics.sg_switch_tol` — > 0 (DEBT-008)
     ```
   - после этого блока (конец §5, перед `## 6. Единая Grid`):
     ```
     Литералы — наш config (`_validate`, [[DEBT-008]]): `grid.type` — только `"log_radial"` (до DEBT-008 любое значение проходило, расчёт шёл на логарифмической сетке); `output.log_level` — `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` без учёта регистра (до DEBT-008 опечатка молча давала `INFO`).

     Удалённые поля ([[DEBT-008]]): `rock.p_ref`, `time.start_day`, `numerics.dt_min`, `numerics.dt_max`, `numerics.newton_rtol`, `numerics.newton_atol`, `output.format`. Решатель их не читал, поэтому старый конфиг загружается: ключ убирается до разбора секций, предупреждение с причиной — после `_validate`, как у DEBT-056 (конфиг с ошибкой в другом поле предупреждений не выдаёт). Неизвестный ключ вне этого списка — ошибка распаковки dataclass (`TypeError`). `output.save_every` ([[DEBT-013]]) — отказ: его пропуск изменил бы состав вывода.
     ```
4. **P8, «Структура JSON (обновлённая)»** (`:316-380`): удалить строки `"p_ref": 1e7,` (`:329`), `"start_day": 0.0,` (`:360`), `"dt_min": 1.0,` и `"dt_max": 86400,` (`:367-368`), `"format": "npz"` (`:377`) и запятую после `"log_level": "INFO"` (`:376`).
5. **`json-config-schema.md`:**
   - `grid`, строка `type` (`:36`): «`"log_radial"` — единственный пока» → «`"log_radial"` — единственный; иное значение отвергает `_validate` (DEBT-008)»;
   - `rock` (`:42-49`): после строки `lambda_gas` добавить `| \`compressibility\` | float | 1/Па | Сжимаемость породы $c_r$: $\varphi(p) = \varphi\,e^{c_r(p - p_0)}$, `porosity` — при $p_0$; опорного давления нет (DEBT-008) |`;
   - `numerics` (таблица BUG-022, `:168-175`): последнюю строку (`:175`, поля в обратных кавычках: «`newton_atol`, `newton_rtol`, `newton_max_iter`, `max_active_set_iter`, `rs_switch_tol`, `sg_switch_tol`, `dt_min`, `dt_max` | — | ⚠️ объявлены, но никем не читаются ([[DEBT-008]])») заменить тремя:
     ```
     | `newton_max_iter`, `max_active_set_iter` | int, int | Лимиты Ньютона ступеней 1–3 `advance`, целые ≥ 1; адаптер передаёт в каждый вызов (DEBT-008) |
     | `rs_switch_tol`, `sg_switch_tol` | float, float | Допуски переключения фаз, > 0; фабрика передаёт в конструктор модели; `rs_switch_tol` — и допуск проверки старта (DEBT-008) |
     | `dt_min`, `dt_max`, `newton_atol`, `newton_rtol` | — | Удалены (DEBT-008): в старом конфиге — предупреждение и пропуск |
     ```
   - `output` (`:177-182`): таблицу заменить:
     ```
     | Поле | Тип | Описание |
     |---|---|---|
     | `log_level` | str | `DEBUG`, `INFO` (по умолчанию), `WARNING`, `ERROR`, `CRITICAL` без учёта регистра; иное — отказ (DEBT-008) |
     ```
     и после неё: «Поля `format` (удалено DEBT-008: формат записи выбирает вызывающий код, `save_npz`/`save_csv`; в старом конфиге — предупреждение и пропуск) и `fields` (проектного этапа, в коде не было) в секции нет.»
6. **`временная-сетка-и-история.md`** (`:22-37`): в образце удалить `    "start_day": 0.0,`; пункт «`start_day` — дата начала истории…» → «время отсчитывается от начала истории, $t = 0$ (`start_day` удалён, [[DEBT-008]])»; пункт «dt_min, dt_max — в секции `numerics`, не здесь» → «`dt_min`, `dt_max` удалены ([[DEBT-008]]): шаг — `dt_integration`, дробление — `numerics.max_retries`».
7. **`модули-simulator-оркестратор.md`** (`:192`): «`dt_integration`, `start_day`, `history: list[HistoryInterval]`» → «`dt_integration`, `history: list[HistoryInterval]` (`start_day` удалён, [[DEBT-008]])».
8. **`hydro-prototype-анализ.md`** (`:71`): в конец абзаца «…но прототип поддерживает c_r ≠ 0.» дописать « GPN передаёт φ_ref = `rock.porosity`, p_ref = $p_0$ (`factory.py`): пористость конфига задана при начальном давлении, опорного давления в конфиге нет ([[DEBT-008]]).»
9. **«проверка Rs — …»** (`:38`): фразу «Поле `NumericsConfig.rs_switch_tol` прототипу не передаётся ([[DEBT-008]]), поэтому `RS_TOL` — константа модуля; тест сверяет её с умолчанием прототипа.» заменить: «После [[DEBT-008]] допуск один — `numerics.rs_switch_tol`: фабрика передаёт его прототипу, проверка старта и `rs_analytics` берут его из конфига (констант `RS_TOL`, `_RS0_SUPERSAT_TOL` нет).» В той же строке «`factory._RS0_SUPERSAT_TOL`» → «`factory._check_undersaturated_start`».
10. **«пересыщенный старт …»** (`:31`): «$R_{s,0} \le R_s^{eq}(p_0) + 10^{-5}$ (`rs_switch_tol`)» → «$R_{s,0} \le R_s^{eq}(p_0) +$ `numerics.rs_switch_tol` (по умолчанию $10^{-5}$; до [[DEBT-008]] — константа фабрики)».

**Проверка:** `Select-String -Path vault\knowledge\decisions\*.md -Pattern "start_day|dt_min|newton_rtol|newton_atol|_RS0_SUPERSAT_TOL|RS_TOL"` (из корня worktree) — остаются только упоминания с «удал…» / [[DEBT-008]] и строки вне задачи: `модули-hydro-newton.md:274` (проектный этап), `hydro-prototype-анализ.md:104` (собственный цикл прототипа), `временная-сетка-и-история.md:99, 101` (история: отказ от адаптивного шага 2026-08-25). **Регресс:** `--collect-only -q`.
**Зависимости:** требует шаг 5.
**Оценка:** ~30 мин.

### Шаг 8: Полный прогон, реестр, issue

**Цель:** итог зелёный; vault и issue отражают результат.

**Что сделать:**
1. Полный прогон GPN (из `$WT`): `& $PY -m pytest tests/ -q` — все зелёные, N_ALL + 19 (на `ccc5ae3` — 1741). Время записать.
2. Проба итогового состояния (из `$WT`):
   ```powershell
   $env:PYTHONIOENCODING = "utf-8"; & $PY $P\red_state.py | Out-File -Encoding utf8 $P\green_state.out.txt
   ```
   Ожидание: 1 — отказ `grid.type: поддерживается только "log_radial"…` (удалённые поля проба присваивает атрибутами — `_validate` их не видит, до лимитов не доходит: первым отказывает `grid.type`); 2 — «проходит» (поля `dt_min` больше нет, NaN-атрибут никто не читает); 3 — `setup_logging` по-прежнему `INFO` (`log.py` не менялся), `_validate` — отказ `output.log_level…`; 4 — отказ «Начальное состояние пересыщено…»; 5 — `max_newton = 7`, `max_active_iter = 5`, `rs_switch_tol = 2e-05`, `sg_switch_tol = 3e-09`; 6 — предупреждений 3: `time.start_day`, `numerics.dt_min`, `numerics.dt_max … удалён из конфига (DEBT-008) и пропущен`. Иное — разобрать.
3. Реестр DEBT-008: статус → ✅ ЗАКРЫТ (влит — `/merge`), поле **Итог**: что передано, что удалено, что проверяется; тестов было/стало.
4. `vault/issues/debt-008/05-comment-done.md` → `gh issue comment 89 …`.
5. `vault/00-home/index.md` — строка плана (если не добавлена при планировании).

**Регресс:** полный — итог реализации.
**Оценка:** ~20 мин (из них ~10 — полный прогон).

## 4. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_warns_and_loads` ×7 | `test_config.py` (новый класс) | `_minimal_raw()` + удалённый ключ | загрузка; поля нет; в журнале `секция.ключ` и DEBT-008 | отказ старых конфигов; молчаливый пропуск |
| `test_removed_keys_are_not_fields` | то же | список против полей dataclass | пересечения нет | пропуск живого параметра |
| `test_unknown_key_still_rejected` | то же | `numerics.newton_max_itr` | `TypeError` с именем ключа | пропуск любых опечаток |
| `TestRemovedKeys.test_no_warning_before_error` | то же | `time.start_day` + `porosity = 1.5` | `ValueError` по `porosity`, предупреждений нет | журнал удалённых ключей до `_validate` (порядок DEBT-056) |
| `test_project_configs_have_no_removed_keys` | то же | `configs/**`, `tests/data/*` | ключей нет | предупреждения в тестах «без предупреждений» |
| `test_grid_type_rejected` ×2 | то же | `"cartesian"`, `1` | `ValueError` `grid.type` | расчёт не на той сетке без сообщения |
| `test_log_level_rejected` ×3, `test_log_level_case_insensitive` | то же | `"DEBG"`, `""`, `5`; `"debug"` | отказ; `"debug"` допустим | молчаливый `INFO` |
| `test_int_field_rejected` ×6, `test_switch_tol_rejected` ×4 | то же | 0, 2.5, true; 0.0, −1e-5 | `ValueError` с именем поля | абсурдные лимиты и допуски в прототипе |
| `test_defaults_match_prototype` | то же | сигнатуры прототипа и адаптера | равенство умолчаний | смену историй всех примеров |
| `test_factory_passes_newton_fields`, `test_factory_default_newton_fields` | `test_factory_prototype.py` | `configs/table_pvt` | значения у модели и адаптера | возврат «фабрика не передаёт» (корень DEBT-007, DEBT-008) |
| `test_supersaturation_tolerance_from_config` | то же | $p_0 = p_b - 1$ Па, допуск 1e-6 | отказ «пересыщено» | расхождение допуска старта и решателя |
| `TestNewtonLimits` ×3 | `test_prototype_adapter.py` | подмена `advance` / `advance_fourth_stage` | ключевые аргументы 5/7 и 12/15; ступень 4 по памяти — те же | потерю лимитов на одном из путей |
| `test_supersaturation_tolerance_from_config` | `test_rs_analytics.py` | пересыщение 2e-5 при допуске 1e-5 и 1e-4 | 1 и 0 нарушений | константу допуска в проверке примеров |
| `test_no_removed_keys` ×23 | `test_examples.py` (замена) | конфиги примеров | ключей нет | возврат удалённых полей в примеры |
| `TestPrototypeInput.test_files_reproduce_conversion` (существующий) | `test_examples.py` | конвертация книги примера 18 | файлы примера = вывод конвертера | правку `config.json` 18 без правки конвертера (и наоборот) |

**Неизменность поведения:** все существующие тесты (быстрый уровень после каждого шага, полный — шаг 8); числа README и балансы примеров проверяет полный уровень (`results`). Умолчания — `test_defaults_match_prototype`.

## 5. Критерии завершения

- [ ] Шаги 0–8 выполнены; полный прогон зелёный, тестов N_ALL + 19.
- [ ] В `NumericsConfig`, `RockConfig`, `TimeConfig`, `OutputConfig` нет `dt_min`, `dt_max`, `newton_rtol`, `newton_atol`, `p_ref`, `start_day`, `format`; каждое оставшееся поле кем-то читается (grep по пакету).
- [ ] `RS_TOL`, `_RS0_SUPERSAT_TOL` — нигде (grep).
- [ ] 31 JSON без удалённых ключей; конвертер примера 18 не пишет `start_day`, `test_files_reproduce_conversion` зелёный; 17 README без «не читаются».
- [ ] Прототип не изменён (`git diff --stat numerical_scheme/implementation -- HydroSolverPrototype` пусто).
- [ ] P8, `json-config-schema.md` и 5 заметок — по коду.
- [ ] Реестр DEBT-008 — итог; комментарий в #89.
- [ ] DEBT-057 зарегистрирован (сделано при планировании).

## 6. Обнаруженные проблемы

- **DEBT-057** (зарегистрирован при планировании): энергетический блок берёт постоянную пористость `rock.porosity` (`energy/tridiag.py:208, 440, 478`), гидродинамика прототипа — $\varphi(p) = \varphi_0 e^{c_r(p - p_0)}$. При $c_r \ne 0$ ёмкость, адиабатический член и временная часть $\dot m$ (правило Лейбница BUG-012 опирается на ту же запись запаса нефти, что у гидродинамики) считаются с $\varphi_0$. Порядок — $c_r\Delta p$: у примера 18 VAL-005 ($c_r$ = 4.5e-5 1/бар = 4.5e-10 1/Па — пример влит, это единственный конфиг с $c_r \ne 0$) при $\Delta p$ = 100 бар — 0.45 %. Не замерено. DEBT-008 не блокирует.
- `vault/knowledge/decisions/json-config-schema.md`: таблица `output` описывает поле `fields`, которого в коде нет; образец §4 P8 содержит `dt_integration` в `numerics` (загрузка дала бы `TypeError`). Исправляются шагом 7 — отдельной записи не нужно.

## 7. Связанные

- Issue: [#89](https://github.com/ArturSalamatin/Oil_Gas/issues/89); тело и комментарии — `vault/issues/debt-008/`; пробы и скрипты — `vault/issues/debt-008/probes/` (`red_state.py`, `strip_removed_keys.py`, `fix_readmes.py` и их выводы; `audit1_converter18.py` — проба аудита 1: конвертер 18 без `start_day` = файл после скрипта; `plan_check.py` — проба аудита 2: блоки плана дословно на копии дерева, быстрый уровень после каждого шага, `--probe` — итоговая проба без тестов; выводы `plan_check.out.txt`, `green_state_plan.out.txt`).
- Реестр: [[известные баги и технический долг]] — DEBT-008; [[BUG-022]] (влит, `newton_cell_tol`), [[DEBT-048]] (влит, `advance_fourth_stage`), [[DEBT-056]] (P8 §5, `_validate`), [[DEBT-006]] (последняя строка `_create_prototype_hydro`), [[VAL-005]] (Reference pressure, пример 18), [[DEBT-051]] (проверка конечности, страж `_FLOAT_FIELDS`), [[DEBT-007]] (`dt_min` и дробление), [[DEBT-026]] (`RS_TOL`), [[BUG-017]] (проверка старта), [[DEBT-013]] (`save_every` — отказ), [[DEBT-057]] (пористость в энергии), [[DEBT-011]] (#91, ждёт DEBT-008: переносит `rs_analytics.py` в пакет), [[DEBT-023]] (#100, без пересечений).
- Заметки: [[P8-формат-ввода-json]], [[json-config-schema]], [[временная-сетка-и-история]], [[hydro-prototype-анализ]].
- Планы: [[bug-022 newton-cell-relative-tolerance]], [[debt-048 shutin-remember-solving-stage]], [[debt-056 skin-bhp-range-check]], [[debt-006 factory-explicit-proto-access]], [[val-005 prototype-template-example]], [[debt-011 diagnostics-into-package]].

## 8. Аудит 1 (2026-10-11, база `ccc5ae3`, фокус — предметная суть)

План писался на `26ddb34`; с тех пор влиты BUG-022, DEBT-056, DEBT-048, DEBT-006, VAL-005, DEBT-014, DEBT-020, DEBT-059, DEBT-063, BUG-024. Аудит повторил пробы и скрипты плана на новой базе (`red_state.py` — тот же вывод; `strip_removed_keys.py` — 31 файл; `fix_readmes.py` — 17 README), сверил «До» всех шагов с кодом, тестов 1722 / быстрый 1451.

- 🔴 **[5B, шаг 2] Конвертер примера 18.** `examples/18_prototype_input/config.json` (VAL-005) порождается `prototype_input.py` (`:184` пишет `"start_day": 0.0`), `test_files_reproduce_conversion` сверяет файл с выводом конвертера построчно — скрипт шага 2 вырезал бы ключ из файла, тест упал бы. Шаг 2 правит и конвертер; проба `audit1_converter18.py`: вывод конвертера без ключа = файл после скрипта (`True`).
- 🟡 **[5A, шаг 3] Порядок предупреждений.** DEBT-056 закрепил: предупреждения `load_config` — только после `_validate` (`io/config.py:360-361`, тест `test_no_warning_before_error`). План журналировал удалённые ключи до разбора секций. Исправлено: `_drop_removed_keys` возвращает тексты, журнал — после `_validate`; новый страж `TestRemovedKeys.test_no_warning_before_error` (+1 тест, итого +19).
- 🟡 **[6/7] Базовые числа и номера строк** — на `26ddb34` (1592 / 1342). Обновлены на `ccc5ae3`: 1722 / 1451 → 1741 / 1470; номера строк всех шагов.
- 🟡 **[2] Условные ветви «если не влит»** (BUG-022, DEBT-048, DEBT-056, DEBT-006, VAL-005) устарели — все влиты. Шаги 0, 4, 7 сведены к фактическому состоянию; P8 §5 — правка таблицы DEBT-056 (шаг 7, п. 3), а не блоков.
- 🟡 **[4, шаги 1–2] Счётчики красных тестов.** `ALL_EXAMPLES` — 23 (с примером 18): `test_no_removed_keys` ×23, красных в шаге 1 — 55, после шага 2 — 31; JSON — 31.
- 🔵 **[0] «$c_r = 0$ во всех конфигах»** — неверно: у примера 18 $c_r$ = 4.5e-10 1/Па. На побитовость не влияет (`p_ref` фабрика не читала, в конфиге 18 его нет); формулировки исправлены, DEBT-057 актуален для примера 18.
- 🔵 **[1, шаг 4] «До»** последней строки `_create_prototype_hydro` — после DEBT-006 (`pvt`, комментарий над ней), конструктор адаптера — с `stage4_memory`.
- 🔵 **[6] «Как начать»** — путь прототипа для pytest теперь `pythonpath` в `pyproject.toml` (DEBT-059), не `conftest.py`; скрипты строк файлов пакет не импортируют.
- 🔵 **[1, шаг 7] Якоря заметок:** строка таблицы `numerics` в `json-config-schema.md` — с обратными кавычками (`:175`); таблица `output` — `:177-182`; в образце P8 §4 `dt_integration` в `numerics` — несуществующее поле (удаляется вместе с `dt_min`, `dt_max`).

**Проверено и верно:** тождество $\varphi_{ref}e^{c_r(p-p_{ref})} = \varphi(p_0)e^{c_r(p-p_0)}$; семантика `rs_switch_tol`/`sg_switch_tol` в `_advance_phases` и `_switch_phases` (ступень 4) — проверка старта и `rs_analytics` используют тот же допуск, что включение газа; ступень 4 лимитов `max_newton`/`max_active_iter` не читает (`_advance_phases` → `_newton_switching(state_old, dt_s)`), `advance_fourth_stage` их принимает; умолчания конфига = умолчаниям прототипа; подмены `advance`/`advance_fourth_stage` в тестах принимают `**kwargs`; вызовы `PrototypeHydroAdapter(` (фабрика, две фикстуры) совместимы с новыми параметрами; `_validate` не содержит переменной `nc`; float-полей 37 → 31; сериализации конфига целиком (`asdict`) нет — удаление полей вывод не меняет; новые тексты не нарушают `test_eq_references.py` (DEBT-010); пересечений с DEBT-023 нет, DEBT-011 ждёт DEBT-008.

## 9. Аудит 2 (2026-10-11, база `ccc5ae3`, фокус — реализуемость)

Проба `vault/issues/debt-008/probes/plan_check.py`: копия дерева (`gpn_multiphase_solver`, `tests`, `configs`, `examples` без выводов, `doc`, `HydroSolverPrototype`, `pyproject.toml`); блоки «До/После» шагов 1–5 взяты из плана дословно по якорям пунктов (каждое «До» найдено ровно один раз), прозаические правки (шаг 3 п. 10, шаг 5) — по тексту плана; скрипты шагов 2 и 6 — с `--write`; страж в `conftest.py` копии проверяет, что pytest берёт пакет копии. Быстрый уровень после каждого шага (`plan_check.out.txt`):

| Состояние | Упало | Ожидание плана |
|---|---|---|
| S1 — шаг 1 | 55 (test_config 25, TestConfigs 23, фабрика 3, адаптер 3, rs_analytics 1) | 55 |
| S2 — + шаг 2 | 31 | 31 |
| S3 — + шаг 3 | 8 | 8 |
| S4 — + шаг 4 | 1 (`test_supersaturation_tolerance_from_config`) | 1 |
| S5 — + шаг 5 | 0, 1470 passed | 0, N_FAST + 19 |
| S6 — + шаг 6 | 0, 1470 passed | 0 |

`plan_check.py --probe` (`green_state_plan.out.txt`): проба `red_state.py` на итоговом дереве — все 6 пунктов как в ожидании шага 8 (отказ `grid.type`; `dt_min = NaN` проходит; отказ `output.log_level`; отказ «пересыщено»; адаптер 7/5, модель 2e-05/3e-09; старый конфиг — 3 предупреждения). «1 warning» во всех прогонах — `PytestRemovedIn10Warning` базы (быстрый уровень `ccc5ae3`: 1451 passed, 1 warning, 94 с), не от плана.

- 🔵 **[1, шаг 1] Номера строк** `test_factory_prototype.py` (`:156-161`, `:378-382`) и `test_examples.py` (`:200-209`) — с `26ddb34`, аудит 1 их пропустил. Обновлены: `:157-162`, `:446-450`, `:202-211`.
- 🔵 **[1B, шаг 3 п. 6] В блок кода попала инструкция** «# Место — перед load_config…, после SimulationConfig» (внесена аудитом 1), к тому же неточная: между `SimulationConfig` и `load_config` — раздел FEAT-018. Строка убрана из блока, место указано в тексте пункта: перед заголовком `# ── Загрузка` (`:298`).
- 🔵 **[1B, шаг 5 п. 3] Докстринг `rs_supersaturation`** разрастался до 9 строк обоснования — против правила CLAUDE.md «Docstring — одна строка». Обоснование — комментарием над функцией, докстринг — одна строка.
- 🔵 **[2, шаг 5 п. 2] Границы удаляемого блока `RS_TOL`** — уточнены (с `# Допуск пересыщения…` по `RS_TOL = 1e-5`); после удаления между `SG_GAS` и `rs_expected` — две пустые строки (проверено).
- 🔵 **[4, шаг 6] Проверка README** дополнена `tests/test_eq_references.py` — он сканирует и README примеров (DEBT-010).
