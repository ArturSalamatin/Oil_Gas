---
tags:
  - план
  - рефакторинг
date: 2026-10-10
issue: DEBT-051
github: 85
branch: refactor/debt-051/config-numeric-fields-finite
status: реализован
worktree: .worktrees/debt-051; удалён после влития
implemented: 2026-10-10 — d4138a0 (код и тесты), 7dac745 (P8, заметка DEBT-049), 03ad371 (vault итога); база 1493 (после DEBT-053) → 1591, полный прогон 1591 passed
merged: d5fd87e (2026-10-10)
audit:
  date: 2026-10-10
  round: 1
  focus: предметная суть — что именно закрывает проверка конечности, конечные абсурдные значения, совместимость с тестами DEBT-047/049, база после DEBT-052
  found: 4
  auto-fixed: 4
  manual-required: 0
---

# План DEBT-051: число и конечность всех числовых полей конфига при загрузке

**Задача:** DEBT-051 в `vault/roadmap/известные баги и технический долг.md` · GitHub [#85](https://github.com/ArturSalamatin/Oil_Gas/issues/85) · ветка `refactor/debt-051/config-numeric-fields-finite` в worktree `.worktrees/debt-051` · база `numerical_scheme/implementation` (план — на `d3aabff`, DEBT-049 влит; аудит 1 — на `27b7144`: влит DEBT-052 `734e782`, он поменял одну строку P8 (`:199`), правки этого плана применимы, числа тестов прежние — перепроверено `plan_check.py`)

**Подтип:** рефакторинг с ужесточением проверки ввода. На допустимых конфигах (все конфиги проекта) числа решателя, истории и README примеров не меняются: проверка только читает значения. Прототип не меняется.

## Кратко

`load_config` пропускает NaN, ±inf и нечисловые значения почти во всех числовых полях. Проверки диапазона в `_validate` и `_validate_interval` записаны как `v <= 0`, а сравнение с NaN ложно. Конечность проверялась только у девяти тепловых параметров (DEBT-047, DEBT-049).

Красная проба `vault/issues/debt-051/probes/red_state.py` (2026-10-10, `d3aabff`, вывод `red_state.out.txt`): `configs/baseline.json`, одно подменённое поле, 24 ч по 1 ч.

| Что в конфиге | Итог до правки | После плана |
|---|---|---|
| **`numerics.skin` = ±inf; `history.p_wf` = +inf** | **проходит молча: скважина не добывает** ($p$ = 20 МПа везде, $S_g$ = 0) | `ValueError` при загрузке |
| **`history.min_bhp` = NaN при активном ограничении** (1000 м³ст/сут, `min_bhp` = 15 МПа) | **проходит молча: ограничение снято**, забой 7.12 МПа, $S_{g,\max}$ = 0.091 (эталон: забой 15.03 МПа, газа нет) | `ValueError` |
| `history.q_oil` = +inf; `time.dt_integration` = +inf | проходят: первое — как управление по давлению 6 МПа, второе — шаг равен интервалу истории | `ValueError` |
| NaN в `porosity`, `compressibility`, `rho_o_std`, `rho_g_std`, `co_undersaturated`, `n_o`, `n_g`, `p0`, `T0`, `Rs0`, `skin`, `history.p_wf`, `history.q_oil`; inf в `R_ext`, `h`, `permeability`, `compressibility`, `co_undersaturated`, `n_o`, `p0` | отказ `HydroSolver не сошёлся при дроблении шага до dt/512 …` с советом увеличить `max_retries` — **ложный след** | `ValueError` с именем поля |
| inf в `rho_o_std`, `T0`, `Rs0` | `from_config`: «Начальное состояние пересыщено газом…» — ложный след | `ValueError` |
| NaN в `r_well`, `R_ext`, `h`, `permeability` | `from_config`: прототип, `invalid radial grid parameters` — без имени | `ValueError` с именем |
| NaN в `S_or`, `S_gc`, `kro_max`, `krg_max` | `from_config`: `CoreyRP`, английский текст | `ValueError` с именем, при загрузке |
| NaN или inf в `dt_integration`, `history.dt` | `run`: `cannot convert float NaN to integer` / `OverflowError` | `ValueError` |
| NaN в `duration`, `dt_out` краткой формы истории | `load_config`: `cannot convert float NaN to integer` (`config.py:239`) — без имени | `ValueError` с `history[i].duration` |
| NaN в мёртвых полях `p_ref`, `start_day`, `dt_min`, `dt_max`, `newton_rtol`, `newton_atol`, `rs_switch_tol`, `sg_switch_tol` | проходит, числа как у эталона (поля не читаются, DEBT-008) | `ValueError` |
| строка (`"0.2"`, `"abc"`), `null` в числовом поле с проверкой | `load_config`: `TypeError: '<=' not supported …` — без имени | `ValueError: … должно быть числом` |
| строка в поле без проверки: `pvt.rho_o_std = "850"`; `numerics.skin = "0"` | `from_config`: `TypeError` в `pvt/standing.py:21` — без имени; `skin` — **проходит молча** (строка доходит до прототипа) | `ValueError: … должно быть числом` |
| `true` в `permeability` | 1 м², отказ после дробления до dt/512 | `ValueError: … должно быть числом` |

После правки:
- **`_validate`** первым делом проходит по всем секциям (`geometry`, `grid`, `rock`, `pvt`, `relperm`, `thermal`, `initial_conditions`, `time`, `numerics`). Каждое поле с аннотацией `float`, а также `Optional[float]` со значением, должно быть числом (не строкой, `null`, `true`/`false`) и конечным. Перечень полей берётся из аннотаций dataclass, поэтому новое поле проверяется без правки кода. Любое значение типа `float` в поле другого типа (NaN в `grid.N`) проверяется на конечность.
- **`_validate_interval`** так же проверяет `dt`, `p_wf`, `q_oil`, `min_bhp`; имя в сообщении — `history[i].<поле>`.
- **`_expand_history`** проверяет `duration`, `dt_out` до `round(duration / dt_out)`.
- Цикл конечности DEBT-049 ($L$, $\mu_{JT}$) удаляется: общий проход его покрывает (решение пользователя 2). Проверки диапазона DEBT-047 и предупреждения о знаке ($L < 0$, $\mu_{JT,o} > 0$) остаются.
- Тексты отказа: `<имя> должно быть числом, получено <repr>` и `<имя> должно быть конечным числом, получено <значение>`. Существующие сообщения `_validate` не меняются (решение пользователя 3).

⚠️ **Чего план не закрывает (аудит 1).** Проверка конечности снимает молча неверные расчёты только для не конечных значений. Конечные абсурдные значения дают тот же расчёт без добычи без единого сообщения: `skin` = 1e6, ±1e300; `p_wf` = 1e12; `min_bhp` = 1e300 при управлении по дебиту — $p$ = 20 МПа везде, $S_g$ = 0 (проба `vault/issues/debt-051/probes/audit1_finite_extremes.py`, вывод `audit1_finite_extremes.out.txt`). Это вопрос диапазонов параметров скважины: P8 §5 отдаёт их прототипу, а прототип их не проверяет. В этой задаче не решается — раздел «Обнаруженные проблемы», п. 2.

Объём: `io/config.py` — 2 новые функции и константа, вызовы в трёх местах, удаление цикла DEBT-049 (~+45 / −13 строк с комментариями); `test_config.py` — класс `TestValidationNumbers`, 98 тестов, импорт и строка докстринга; 2 заметки vault. Тестов 1494 → 1592, быстрый уровень 1244 → 1342, `test_config.py` 147 → 245.

**Код плана проверен подменой** — раздел «Проверка плана» в конце.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-051 в реестре, тело issue `vault/issues/debt-051/01-issue-body.md` и замер `vault/issues/debt-051/probes/red_state.out.txt`. ⚠️ Тело issue утверждает «молча неверного расчёта не найдено» — опровергнуто этой пробой (см. «Кратко»); поправка — комментарий плана в #85.
3. Worktree и ветка — от базы `numerical_scheme/implementation` (не от `master`: там нет `numerical_solver/`). Venv — основного каталога: `<PY>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe`. Пробы берут код из текущего каталога (`Path.cwd()`) и печатают путь к коду первой строкой — сверить, что это worktree.
4. Исходный замер (из `numerical_solver/` worktree):
   ```powershell
   <PY> -m pytest tests/ --collect-only -q          # ожидание: 1494 tests collected
   <PY> -m pytest tests/ -m "not slow" -q           # ожидание: 1244 passed, 250 deselected (~80 с)
   <PY> -m pytest tests/test_config.py --collect-only -q   # 147
   ```
   Если до реализации в базу влита задача с тестами, абсолютные числа сдвигаются — проверять приращение: **+98 всего, +98 в быстром уровне, `test_config.py` +98**. Порядок с другими задачами — раздел «Порядок влития».
5. Начни с шага 1. После каждого шага — проверка по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

## Решения пользователя (2026-10-10)

1. **Тип проверяется заодно:** строка, `null`, `true`/`false` в поле `float` (или в `Optional[float]`, кроме `null`) → `ValueError` с именем поля. Обоснование: сейчас строка и `null` дают `TypeError` без имени, а `true` молча становится 1.0 (bool — подкласс int). Конфиги проекта не задеты: grep `"\w+"\s*:\s*("[-+0-9.][0-9.eE+-]*"|true|false|null)` по `configs/**/*.json`, `examples/**/config*.json`, `tests/data/**/*.json` — пусто.
2. **Общий проход — по всем секциям, включая `thermal`; цикл конечности DEBT-049 удалить.** Он стал бы недостижим. Проверки диапазона DEBT-047 (`0 < v < inf`, `0 <= v < inf`) остаются: они проверяют знак, а `< inf` в них просто не срабатывает.
3. **Существующие сообщения `_validate` не трогать** (`r_well должен быть > 0` — без приставки секции). Новые сообщения — с полным именем.
4. **`CoreyRP` не трогать:** его `n_o <= 0 or n_g <= 0` (`gpn_multiphase_solver/pvt/relperm.py:19`) пропускает NaN только при прямом создании класса; из конфига NaN туда больше не дойдёт.

## Текущее состояние

### Код

`numerical_solver/gpn_multiphase_solver/io/config.py` (на `d3aabff`):
- `:7` — `from __future__ import annotations`: аннотации полей dataclass хранятся строками. Замер (`dataclasses.fields`): `'float'`, `'Optional[float]'`, `'int'`, `'str'`, `'Optional[str]'`, `'list[HistoryInterval]'`.
- `:10` — `from dataclasses import dataclass, field, replace`.
- `:17-189` — секции. Поля `float`: `GeometryConfig` 3, `RockConfig` 8, `PVTConfig` 3, `RelPermConfig` 6, `ThermalConfig` 5, `InitialConfig` 3, `TimeConfig` 2 (`dt_integration`, `start_day`), `NumericsConfig` 7 — всего 37; `GridConfig` — только `N: int`, `type: str`. `HistoryInterval`: `dt: float`, `p_wf`, `q_oil`, `min_bhp: Optional[float]`.
- `:215-266` — `_expand_history`: краткая форма — `duration = entry.pop("duration")`, `dt = entry.pop("dt_out")` (`:231-232`), `if duration <= 0` (`:233`), `if dt <= 0` (`:236`), `n = round(duration / dt)` (`:239`). Затем `HistoryInterval(dt=dt, **entry)` и `_validate_interval(proto, where)` (`:257-261`), `where = f"history[{i}]"`.
- `:271-331` — `load_config` → `_validate(config)` (`:330`) — единственный вызов.
- `:334-438` — `_validate`: геометрия `:336-342`, сетка `:344-345`, порода `:347-351`, тепловой блок `:353-411`, начальные условия `:413-419`, время `:421-424`, `max_retries` `:430-438`. В тепловом блоке: комментарий DEBT-047 `:353-360`, `inf = float("inf")` `:361`, проверки DEBT-047 `:363-373`, цикл конечности DEBT-049 `:374-386`, предупреждения $L < 0$ `:387-398` и $\mu_{JT,o} > 0$ `:399-411`.
- `:441-473` — `_validate_interval(h, where)`: `if h.dt <= 0` `:443`, `p_wf <= 0` `:448`, `q_oil < 0` `:460`, `min_bhp <= 0` `:465`.

Где NaN всё-таки ловился (проверки «от противного»): прототип `RadialGrid` — `not (0 < rw < re and n >= 1 and h > 0 and k > 0)` (`HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/grid.py:7-8`); наш `CoreyRP` — `not (0 <= S_or < 1)` и т. п. (`gpn_multiphase_solver/pvt/relperm.py:13-22`). Оба вызываются из `SimulatorFactory.from_config` — после `load_config`.

### Тесты

`numerical_solver/tests/test_config.py` (147 тестов на `d3aabff`):
- `:1-11` — докстринг модуля; `:5` — «- Валидацию: отсутствующие секции, невалидные значения.»;
- `:13-23` — импорты (`json`, `logging`, `pytest`, `pathlib.Path`; классы секций из `io.config` — `GeometryConfig`, `RockConfig`, `PVTConfig`, `RelPermConfig`, `ThermalConfig`, `InitialConfig`, `TimeConfig`, `NumericsConfig` уже импортированы);
- `:248-252` — `_write_json` (`json.dumps`: NaN, inf — литералами `NaN`, `Infinity`);
- `:255-269` — `_minimal_raw()`: `relperm` — `{"model": "corey"}`, `thermal` — `{}`, секции `numerics` нет, история — `[{"dt": 86400, "control": "pressure", "p_wf": 10e6}]`, `dt_integration` — целое 3600;
- `:323-457` — `TestValidationGeometry`, `…Grid`, `…Rock`, `…Initial`, `…Time`: `match` — только имя поля (`"r_well"`, `"p0"`, `"dt"`), подстрокой;
- `:519-648` — `TestValidationThermal`: тесты DEBT-047 (`match=f"{section}.{key}"`) и DEBT-049 (`match=f"thermal.{key} .*конечным"`, `match=f"thermal.{key}"`);
- `:651-653` — разделитель «# E. Мульти-интервальная история».

`tests/test_examples.py::TestConfigs::test_load_config_passes` (`:174-178`, быстрый уровень) — `load_config` всех конфигов примеров.

### Документы

- `vault/knowledge/decisions/P8-формат-ввода-json.md:209` — «Валидация данных для гидро — ответственность прототипа…»; `:217` — «для девяти тепловых параметров … Прочие числовые поля конфига NaN пропускают — [[DEBT-051]]».
- `vault/knowledge/debugging/положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке.md:21` — текст отказа DEBT-049 «… (знак любой) …»; `:40-41` — «Что не закрыто» со ссылками на DEBT-051.

## Целевое состояние

- `io/config.py`: импорт `fields`; константа `_NUMERIC_SECTIONS`; функции `_require_finite_number(value, name)` и `_check_numeric_fields(obj, where)` перед `_validate`; вызовы — в начале `_validate` (цикл по секциям), в начале `_validate_interval`, в `_expand_history` для `duration` и `dt_out`. Цикл DEBT-049 удалён, комментарии DEBT-047/049 поправлены.
- Сигнатуры `load_config`, `_validate`, `_validate_interval`, `_expand_history` не меняются; новых зависимостей нет (`dataclasses` — стандартная библиотека).
- Порядок отказов: тип и конечность — раньше любой проверки диапазона и раньше предупреждений о знаке.

## Анализ вариантов

Варианты — из тела issue (`vault/issues/debt-051/01-issue-body.md`):

| | Суть | Плюсы | Минусы | Выбор |
|---|---|---|---|---|
| 1 | Общий проход по полям dataclass-секций | все поля, включая будущие; не трогает распределение диапазонов между `_validate` и прототипом (P8 §5) | мёртвые поля тоже проверяются (безвредно) | **выбран** |
| 2 | Переписать каждую проверку «от противного» | конечность и диапазон в одном условии | ручной перечень; решать диапазоны гидродинамики здесь | отклонён |
| 3 | `json.load(parse_constant=...)` | одна строка | без имени поля; `1e999` → inf мимо `parse_constant` | отклонён |

Промежуточные состояния: шаг 1 (тесты + код) — зелёный; шаг 2 — только документы; шаг 3 — проба и vault.

## Порядок влития

| Ситуация | Что меняется в плане |
|---|---|
| Как написано: база `d3aabff` | ничего |
| **BUG-022** (план готов: `vault/plans/bug-022 newton-cell-relative-tolerance.md`) влит раньше | Он добавляет поле `numerics.newton_cell_tol: Optional[float] = 1e-8` со своей проверкой после блока `max_retries` (`_validate`) и класс `TestNewtonCellTolValidation` после `TestMaxRetriesValidation`, строку докстринга модуля после строки DEBT-049 (`:7`). С этим планом пересечений по строкам нет: правки здесь — начало `_validate`, тепловой блок, `_validate_interval`, `_expand_history`, строка докстринга `:5`, класс после `TestValidationThermal`. Поле `newton_cell_tol` попадёт в общий проход автоматически; его тесты (`match="newton_cell_tol"`, значения NaN, inf, `True`, `"1e-8"`) пройдут — сообщение общего прохода содержит имя поля. Числа тестов — +98 к итогу базы. |
| **BUG-022** вливается после этого плана | Его проверка `newton_cell_tol` на NaN, inf, bool, строку станет недостижимой (общий проход раньше) — диапазонная часть (`> 0`) остаётся нужной. Упомянуть в его реализации; тесты BUG-022 проходят (см. выше). |
| **DEBT-052** — влит во время аудита 1 (`734e782`) | Поменял P8 `:199` (термин); правки этого плана (`:209`, `:217`) применимы — перепроверено на `27b7144`. Тестов не менял (1494). |
| **DEBT-053** (в реализации, `.worktrees/debt-053`), **VAL-005**, **DEBT-048** | `io/config.py`, `test_config.py`, P8 §5 не правят (grep по планам). DEBT-053 только ссылается на импорт `OutputConfig` `test_config.py:22`; правка #1 этого плана вставляет строку импорта выше — `:22` станет `:23`. DEBT-053 по плану убирает 1 тест — базовые числа сдвинутся, проверять приращение +98. |

## Подводные камни (чеклист)

- ✅ **Все места вызова:** `_validate` — только из `load_config` (`config.py:330`); `_validate_interval` — только из `_expand_history` (`:261`). grep `_validate\(|_validate_interval\(` по `numerical_solver/**/*.py`.
- ✅ **Зависимости, циклы импортов:** только `dataclasses.fields` (стандартная библиотека).
- ✅ **Конфиги проекта:** все числа конечны, строк-чисел, `true`/`false`, `null` в числовых полях нет (grep в «Решениях пользователя» и `NaN|Infinity` — только `FINAL_REGRESSION_METRICS_20260825a.json` прототипа, не конфиг). Целые JSON в `float`-полях (`dt_integration: 3600`, `dt_max: 86400` в `configs/baseline.json`) допустимы — `int` проходит проверку типа. Проверяет быстрый уровень: `test_load_config_passes` по всем примерам, `TestBaseline*` по `baseline.json`.
- ⚠️ **Существующие тесты с NaN, inf:** DEBT-047 (`test_invalid_rejected` — `c_p_oil` NaN/inf, `lambda_solid` NaN/inf, `match=f"{section}.{key}"`) и DEBT-049 (`test_nonfinite_scalar_rejected` — `match=f"thermal.{key} .*конечным"`; `test_nonfinite_no_sign_warning` — `match=f"thermal.{key}"`, без предупреждений). После правки их ловит общий проход с текстом `thermal.<поле> должно быть конечным числом, получено …` — все шаблоны совпадают, предупреждений нет (отказ раньше). Проверено подменой: `test_config.py` 245 passed.
- ⚠️ **Сравнение строк аннотаций:** проход опирается на `f.type == "float"` / `"Optional[float]"`. Если аннотацию переписать иначе (`float | None`, `typing.Optional[float]`), поле молча выпадет из проверки. Страж — тест `test_field_list_covers_known_fields` (известные поля в списке, их не меньше 37) и комментарий у `_check_numeric_fields`.
- ✅ **bool:** `True`/`False` в `float`-поле — отказ (решение 1). В `int`-полях (`grid.N`, `numerics.newton_max_iter`, …) тип не проверяется — как и раньше (у `max_retries` своя проверка).
- ✅ **`null`:** в `float`-поле — отказ «должно быть числом»; в `Optional[float]` — допустим, дальше работают прежние проверки (`control='pressure', но p_wf не задано` и т. п.).
- ✅ **Состояние при ошибке:** функции только читают и бросают исключение.
- ✅ **Мёртвые поля** (`p_ref`, `start_day`, `dt_min`, `dt_max`, `newton_*`, DEBT-008): тоже проверяются — NaN в них станет отказом. Конфиги проекта их не портят.
- ✅ **Производительность:** ~45 полей при загрузке.
- ✅ **Прототип:** не меняется.

## Шаги

### Шаг 1: Тесты и общий проход числа и конечности

**Цель:** `load_config` отвергает строку, `null`, `true`/`false`, NaN и ±inf в любом числовом поле конфига с полным именем поля.

**Файлы:**
- `numerical_solver/tests/test_config.py`
- `numerical_solver/gpn_multiphase_solver/io/config.py`

**Контекст:** тест пишется до реализации (CLAUDE.md, «Тестирование»). Новые тесты сначала запускаются на текущем коде: 90 из 98 должны упасть (п. 2). Затем правка кода. Проверки диапазона не трогаем: P8 §5 отдаёт диапазоны гидродинамики прототипу, а тип и конечность — общая проверка ввода, она не зависит от модели.

**Что сделать:**
1. Правки #1–#3 в `test_config.py`: импорт `fields`, строка докстринга модуля, класс `TestValidationNumbers` после `TestValidationThermal`.
2. Прогнать новые тесты на текущем коде:
   ```powershell
   <PY> -m pytest tests/test_config.py -q -k TestValidationNumbers
   ```
   Ожидание: **90 failed, 8 passed** (проверено подменой). Проходят:
   - `test_field_list_covers_known_fields` — тест про способ отбора полей;
   - `test_integer_values_accepted` — целые допустимы и до правки;
   - 6 × `test_nonfinite_rejected` для `thermal.L_degas`, `mu_JT_oil`, `mu_JT_gas` (NaN, inf): текст отказа DEBT-049 «… должно быть конечным числом (знак любой) …» уже подходит под шаблон.

   Падают: `DID NOT RAISE` — `load_config` пропускает NaN, inf; `Regex pattern did not match` — тепловые $c_p$, λ (текст DEBT-047 «должна быть конечной»); необработанный `TypeError` — строки и `null`; `ValueError: cannot convert float NaN to integer` и `OverflowError` — краткая форма истории.
3. Правки #1–#6 в `io/config.py`.
4. Повторить п. 2 — **98 passed**; весь `tests/test_config.py` — **245 passed**.

**Изменения (старый → новый код):**

Правка #1, `test_config.py:13-16` — импорт `fields`:

<!-- правка numerical_solver/tests/test_config.py #1 до -->
```python
import pytest
from pathlib import Path
```
<!-- правка numerical_solver/tests/test_config.py #1 после -->
```python
import pytest
from dataclasses import fields
from pathlib import Path
```

Правка #2, `test_config.py:5` — докстринг модуля:

<!-- правка numerical_solver/tests/test_config.py #2 до -->
```python
- Валидацию: отсутствующие секции, невалидные значения.
```
<!-- правка numerical_solver/tests/test_config.py #2 после -->
```python
- Валидацию: отсутствующие секции, невалидные значения; любое числовое поле —
  число и конечное, с именем поля в отказе (DEBT-051).
```

Правка #3, `test_config.py:647-653` — класс после `TestValidationThermal`:

<!-- правка numerical_solver/tests/test_config.py #3 до -->
```python
        assert (cfg.thermal.mu_JT_oil, cfg.thermal.mu_JT_gas) == (-4.0e-7, -4.0e-6)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# ═════════════════════════════════════════════════════════════
# E. Мульти-интервальная история
```
<!-- правка numerical_solver/tests/test_config.py #3 после -->
```python
        assert (cfg.thermal.mu_JT_oil, cfg.thermal.mu_JT_gas) == (-4.0e-7, -4.0e-6)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# Поля float секций — по аннотациям dataclass, как в _check_numeric_fields:
# новое поле попадает в тест без правки списка. grid — без float-полей
# (N — int), интервалы истории — отдельными тестами (номер объекта JSON).
_FLOAT_FIELDS = [
    (section, f.name)
    for section, cls in (("geometry", GeometryConfig), ("rock", RockConfig),
                         ("pvt", PVTConfig), ("relperm", RelPermConfig),
                         ("thermal", ThermalConfig), ("initial_conditions", InitialConfig),
                         ("time", TimeConfig), ("numerics", NumericsConfig))
    for f in fields(cls) if f.type == "float"
]


# Число и конечность любого числового поля (DEBT-051). Замер до DEBT-051
# (vault/issues/debt-051/probes/red_state.out.txt, 24 ч при p_wf = 6 МПа):
# NaN в p0, porosity и ещё 11 полях — отказ после дробления первого шага до
# dt/512 с советом увеличить max_retries; skin = ±inf, p_wf = +inf — расчёт
# без добычи; min_bhp = NaN — ограничение по забою снято молча (забой
# 7.12 МПа при min_bhp = 15 МПа); строка или null — TypeError без имени поля.
class TestValidationNumbers:
    """Числовые поля конфига: число (не строка, null, bool) и конечное (DEBT-051)."""

    def test_field_list_covers_known_fields(self):
        """Список float-полей из аннотаций содержит известные поля, их не меньше 37."""
        # Страж способа отбора: если аннотации сменят вид («float | None»),
        # список опустеет вместе с проверкой в _check_numeric_fields
        known = {("geometry", "r_well"), ("rock", "porosity"), ("pvt", "rho_o_std"),
                 ("relperm", "n_o"), ("thermal", "L_degas"), ("initial_conditions", "p0"),
                 ("time", "dt_integration"), ("numerics", "skin")}
        assert known <= set(_FLOAT_FIELDS)
        assert len(_FLOAT_FIELDS) >= 37

    @pytest.mark.parametrize("value", [float("nan"), float("inf")], ids=["nan", "inf"])
    @pytest.mark.parametrize("section, key", _FLOAT_FIELDS,
                             ids=[f"{s}.{k}" for s, k in _FLOAT_FIELDS])
    def test_nonfinite_rejected(self, tmp_path, section, key, value):
        """NaN и inf в float-поле секции → ValueError «<секция>.<поле> должно быть конечным»."""
        raw = _minimal_raw()
        raw.setdefault(section, {})[key] = value
        with pytest.raises(ValueError, match=rf"{section}\.{key} должно быть конечным"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("section, key, value", [
        ("rock", "porosity", "0.2"),           # строка-число: был TypeError без имени
        ("time", "dt_integration", "3600"),
        ("initial_conditions", "p0", "abc"),
        ("geometry", "h", None),               # null в обязательном числе
        ("rock", "permeability", True),        # было 1 м² — отказ после dt/512
        ("numerics", "skin", False),
        ("thermal", "c_p_oil", "2000"),
    ], ids=["porosity_str", "dt_integration_str", "p0_text", "h_null",
            "permeability_true", "skin_false", "c_p_oil_str"])
    def test_non_number_rejected(self, tmp_path, section, key, value):
        """Строка, null, true/false в float-поле → ValueError «… должно быть числом»."""
        raw = _minimal_raw()
        raw.setdefault(section, {})[key] = value
        with pytest.raises(ValueError, match=rf"{section}\.{key} должно быть числом"):
            load_config(_write_json(tmp_path, raw))

    def test_nonfinite_in_int_field_rejected(self, tmp_path):
        """NaN в целом поле (grid.N) — тоже отказ по конечности."""
        # `N < 1` NaN пропускает: сравнение с NaN ложно
        raw = _minimal_raw()
        raw["grid"]["N"] = float("nan")
        with pytest.raises(ValueError, match=r"grid\.N должно быть конечным"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("value", [float("nan"), float("inf")], ids=["nan", "inf"])
    @pytest.mark.parametrize("interval, key", [
        ({"control": "pressure", "p_wf": 6e6}, "dt"),
        ({"control": "pressure", "p_wf": 6e6}, "p_wf"),
        ({"control": "rate", "q_oil": 5.787e-4, "min_bhp": 6e6}, "q_oil"),
        ({"control": "rate", "q_oil": 5.787e-4, "min_bhp": 6e6}, "min_bhp"),
    ], ids=["dt", "p_wf", "q_oil", "min_bhp"])
    def test_interval_nonfinite_rejected(self, tmp_path, interval, key, value):
        """NaN и inf в поле интервала истории → ValueError с history[i].<поле>."""
        # Второй интервал испорчен — номер в сообщении указывает на него
        raw = _minimal_raw()
        good = {"dt": 3600.0, **interval}
        raw["time"]["history"] = [good, dict(good, **{key: value})]
        with pytest.raises(ValueError, match=rf"history\[1\]\.{key} должно быть конечным"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("key, value", [("p_wf", "6e6"), ("dt", True)],
                             ids=["p_wf_str", "dt_true"])
    def test_interval_non_number_rejected(self, tmp_path, key, value):
        """Строка или bool в поле интервала → ValueError «history[i].<поле> должно быть числом»."""
        raw = _minimal_raw()
        good = {"dt": 3600.0, "control": "pressure", "p_wf": 6e6}
        raw["time"]["history"] = [good, dict(good, **{key: value})]
        with pytest.raises(ValueError, match=rf"history\[1\]\.{key} должно быть числом"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("key, value", [
        ("duration", float("nan")), ("dt_out", float("nan")),
        ("duration", float("inf")), ("dt_out", "3600"),
    ], ids=["duration_nan", "dt_out_nan", "duration_inf", "dt_out_str"])
    def test_block_fields_checked(self, tmp_path, key, value):
        """duration, dt_out краткой формы — число и конечное до round(duration / dt_out)."""
        # До DEBT-051 NaN давал «cannot convert float NaN to integer» без имени поля
        raw = _minimal_raw()
        block = {"duration": 86400.0, "dt_out": 3600.0, "control": "pressure", "p_wf": 6e6}
        block[key] = value
        raw["time"]["history"] = [block]
        with pytest.raises(ValueError, match=rf"history\[0\]\.{key} должно быть"):
            load_config(_write_json(tmp_path, raw))

    def test_integer_values_accepted(self, tmp_path):
        """Целые числа JSON в float-полях допустимы (dt_integration: 3600 в baseline.json)."""
        raw = _minimal_raw()
        raw["geometry"]["h"] = 10
        cfg = load_config(_write_json(tmp_path, raw))
        assert (cfg.geometry.h, cfg.time.dt_integration) == (10, 3600)


# ═════════════════════════════════════════════════════════════
# E. Мульти-интервальная история
```

Правка #1, `io/config.py:10` — импорт:

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #1 до -->
```python
from dataclasses import dataclass, field, replace
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #1 после -->
```python
from dataclasses import dataclass, field, fields, replace
```

Правка #2, `io/config.py:231-233` — `duration`, `dt_out` краткой формы:

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #2 до -->
```python
            duration = entry.pop("duration")
            dt = entry.pop("dt_out")
            if duration <= 0:
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #2 после -->
```python
            duration = entry.pop("duration")
            dt = entry.pop("dt_out")
            # Число и конечность — до сравнений: NaN проходит `<= 0`, а
            # round(duration / dt) ниже падал на нём без имени поля (DEBT-051)
            _require_finite_number(duration, f"{where}.duration")
            _require_finite_number(dt, f"{where}.dt_out")
            if duration <= 0:
```

Правка #3, `io/config.py:330-336` — функции и общий проход в начале `_validate`:

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #3 до -->
```python
    _validate(config)
    return config


def _validate(cfg: SimulationConfig) -> None:
    """Физическая валидация параметров."""
    g = cfg.geometry
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #3 после -->
```python
    _validate(config)
    return config


# Секции, числовые поля которых проверяет _check_numeric_fields (DEBT-051).
# Интервалы истории — в _validate_interval: там известен номер объекта JSON.
_NUMERIC_SECTIONS = ("geometry", "grid", "rock", "pvt", "relperm", "thermal",
                     "initial_conditions", "time", "numerics")


def _require_finite_number(value, name: str) -> None:
    """Число (не строка, null, bool) и конечное, иначе ValueError с именем name (DEBT-051)."""
    # bool — подкласс int: true в числовом поле — опечатка, а не 1.0
    # (замер: permeability = true — 1 м², отказ после дробления до dt/512)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} должно быть числом, получено {value!r}")
    # Сравнение с NaN ложно: условие отсекает и NaN, и ±inf (литералы JSON
    # NaN, Infinity, -Infinity; 1e999 модуль json тоже читает как inf)
    if not (-float("inf") < value < float("inf")):
        raise ValueError(f"{name} должно быть конечным числом, получено {value}")


def _check_numeric_fields(obj, where: str) -> None:
    """Числовые поля dataclass-секции obj — через _require_finite_number (DEBT-051)."""
    # Аннотации — строки (from __future__ import annotations): «float»,
    # «Optional[float]». Поле с иначе записанной аннотацией выпадет из проверки
    # (страж — test_config.py::test_field_list_covers_known_fields). null
    # допустим только в Optional-поле. Значение float в поле другого типа
    # (NaN в grid.N) проверяется на конечность.
    for f in fields(obj):
        value = getattr(obj, f.name)
        typed = f.type == "float" or (f.type == "Optional[float]" and value is not None)
        if typed or isinstance(value, float):
            _require_finite_number(value, f"{where}.{f.name}")


def _validate(cfg: SimulationConfig) -> None:
    """Физическая валидация параметров."""
    # Число и конечность всех числовых полей — до проверок диапазона (DEBT-051).
    # Проверки вида `v <= 0` NaN пропускают: сравнение с NaN ложно. Замер до
    # DEBT-051 (vault/issues/debt-051/probes/red_state.out.txt, 24 ч при
    # p_wf = 6 МПа): NaN в p0, porosity и ещё 11 полях — отказ после дробления
    # первого шага до dt/512 с советом увеличить max_retries; skin = ±inf и
    # p_wf = +inf — расчёт без добычи; min_bhp = NaN — ограничение по забою
    # снято молча (забой 7.12 МПа при min_bhp = 15 МПа).
    for name in _NUMERIC_SECTIONS:
        _check_numeric_fields(getattr(cfg, name), name)

    g = cfg.geometry
```

Правка #4, `io/config.py:357-360` — комментарий DEBT-047 (условие `< inf` больше не единственная защита от NaN):

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #4 до -->
```python
    # отклонения; λ < 0 — тысячные доли кельвина. Условие `0 < v < inf`
    # отсекает и NaN (JSON допускает литералы NaN и Infinity, сравнение с NaN
    # всегда False), и inf (иначе отказ дала бы scipy в СЛАУ энергии —
    # «array must not contain infs or NaNs», без имени параметра).
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #4 после -->
```python
    # отклонения; λ < 0 — тысячные доли кельвина. NaN и inf сюда не доходят:
    # их отвергает _check_numeric_fields в начале функции (DEBT-051). Условие
    # `0 < v < inf` осталось от DEBT-047, где отсекало и их (иначе отказ дала
    # бы scipy в СЛАУ энергии без имени параметра).
```

Правка #5, `io/config.py:374-387` — цикл DEBT-049 удаляется (решение пользователя 2):

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #5 до -->
```python
    # L, μ_JT,o, μ_JT,g — только конечность, знак любой (DEBT-049, P8 §5):
    # у жидкости μ_JT обычно < 0 (нагрев при дросселировании), у газа > 0;
    # L < 0 возможна (см. ниже). Без проверки NaN и ±inf проходили загрузку,
    # а run падал в СЛАУ энергии — «array must not contain infs or NaNs»,
    # без имени параметра (vault/issues/debt-049/probes/red_state.out.txt).
    # Проверка — до предупреждения о L < 0: иначе при L = −inf в журнал
    # сначала ушло бы предупреждение о знаке, а следом отказ.
    for name, value in (("thermal.L_degas", th.L_degas),
                        ("thermal.mu_JT_oil", th.mu_JT_oil),
                        ("thermal.mu_JT_gas", th.mu_JT_gas)):
        if not (-inf < value < inf):
            raise ValueError(f"{name} должно быть конечным числом (знак любой), "
                             f"получено {value}")
    # L < 0 — предупреждение, не отказ (решение пользователя, DEBT-047).
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #5 после -->
```python
    # L, μ_JT,o, μ_JT,g — знак любой (P8 §5): у жидкости μ_JT обычно < 0
    # (нагрев при дросселировании), у газа > 0; L < 0 возможна (см. ниже).
    # Конечность проверил _check_numeric_fields в начале функции (DEBT-051;
    # до него — отдельный цикл DEBT-049): раньше предупреждений о знаке, так
    # что при L = −inf в журнал не уходит предупреждение перед отказом.
    # L < 0 — предупреждение, не отказ (решение пользователя, DEBT-047).
```

Правка #6, `io/config.py:441-443` — интервал истории:

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #6 до -->
```python
def _validate_interval(h: HistoryInterval, where: str) -> None:
    """Проверка одного интервала истории; where — его место в JSON."""
    if h.dt <= 0:
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #6 после -->
```python
def _validate_interval(h: HistoryInterval, where: str) -> None:
    """Проверка одного интервала истории; where — его место в JSON."""
    # Число и конечность dt, p_wf, q_oil, min_bhp — до сравнений (DEBT-051):
    # `h.min_bhp <= 0` NaN пропускал, и ограничение по забою снималось молча
    _check_numeric_fields(h, where)
    if h.dt <= 0:
```

Почему `-float("inf") < value < float("inf")`, а не `np.isfinite`: так записаны проверки DEBT-047; `numpy` в `io/config.py` не импортирован; сравнение с NaN ложно — NaN отсекается тем же условием. Переменная `inf` из `_validate` (`:361`) остаётся — её используют проверки DEBT-047.

**Проверка после этого шага:**
- Тесты шага — п. 2 и п. 4.
- Регресс: быстрый — `<PY> -m pytest tests/ -m "not slow" -q`; ожидание **1342 passed, 250 deselected** (было 1244). В том числе `TestValidationThermal` (тесты DEBT-047, DEBT-049 — теперь их ловит общий проход), `TestConfigs::test_load_config_passes` (все конфиги примеров).
- `--collect-only -q` — **1592** (было 1494).

**Подводные камни:** «Существующие тесты с NaN, inf», «Сравнение строк аннотаций», «Конфиги проекта» (чеклист).

**Зависимости:** требует — ничего; блокирует — шаг 3.

**Оценка:** ~45 строк кода с комментариями (−13 строк цикла DEBT-049), ~130 строк тестов, ~30 минут.

### Шаг 2: Документы — P8 §5, заметка DEBT-049

**Цель:** P8 §5 описывает общий проход; заметка DEBT-049 — что её цикл заменён и пункты «Что не закрыто» закрыты.

**Файлы:**
- `vault/knowledge/decisions/P8-формат-ввода-json.md`
- `vault/knowledge/debugging/положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке.md`

**Контекст:** P8 §5 — справочник проверок ввода; сейчас он отдаёт гидродинамику прототипу целиком и говорит, что прочие поля NaN пропускают. После DEBT-051 тип и конечность всех чисел проверяет config, диапазоны — по-прежнему там, где были. Заметка DEBT-049 цитирует текст отказа «… (знак любой) …» — он исчезает вместе с циклом.

**Изменения:**

Правка #1, `P8-формат-ввода-json.md:209`:

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #1 до -->
````markdown
Валидация данных для гидро — ответственность прототипа (конструкторы BlackOilPVT, TabulatedRelPerm, RadialGrid проверяют входные данные).
````
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #1 после -->
````markdown
Валидация данных для гидро — ответственность прототипа (конструкторы BlackOilPVT, TabulatedRelPerm, RadialGrid проверяют входные данные). Исключение — тип и конечность чисел: их для всех полей проверяет наш config (DEBT-051, ниже).
````

Правка #2, `P8-формат-ввода-json.md:217`:

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #2 до -->
````markdown
- для девяти тепловых параметров ($c_p$, $(\rho c_p)_s$, λ — DEBT-047; $L$, $\mu_{JT}$ — DEBT-049) литералы JSON `NaN`, `Infinity`, `-Infinity` отвергаются теми же проверками, сообщение называет параметр. Прочие числовые поля конфига NaN пропускают — [[DEBT-051]]
````
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #2 после -->
````markdown

Тип и конечность всех чисел — наш config, до любых проверок диапазона ([[DEBT-051]]; `_check_numeric_fields`, `_require_finite_number` в `io/config.py`):
- каждое поле с аннотацией `float` в секциях `geometry`, `grid`, `rock`, `pvt`, `relperm`, `thermal`, `initial_conditions`, `time`, `numerics` и в интервалах истории (`dt`; `p_wf`, `q_oil`, `min_bhp` — `Optional[float]`, `null` допустим) — число, не строка, `null`, `true`/`false`, и конечное; поля выбираются по аннотациям dataclass — новое поле проверяется без правки кода;
- `duration`, `dt_out` краткой формы истории — так же, до разворачивания блока;
- значение `float` в поле другого типа (NaN в `grid.N`) — на конечность;
- литералы JSON `NaN`, `Infinity`, `-Infinity` (и `1e999`, который `json` читает как inf) отвергаются при загрузке: `<секция>.<поле> должно быть конечным числом`, `history[i].<поле> …`; строка, `null`, bool — `… должно быть числом`;
- мёртвые поля (DEBT-008) проверяются так же.

Замер до DEBT-051 (`vault/issues/debt-051/probes/red_state.out.txt`): `skin` = ±inf и `p_wf` = +inf давали расчёт без добычи, `min_bhp` = NaN снимал ограничение по забою молча (7.12 МПа при 15 МПа), NaN в 13 полях — отказ после дробления до dt/512 с советом увеличить `max_retries`.
````

Правка #1, заметка DEBT-049, `:21`:

<!-- правка vault/knowledge/debugging/положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке.md #1 до -->
````markdown
- `_validate`: $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ — условие `-inf < v < inf`, иначе `ValueError: thermal.<параметр> должно быть конечным числом (знак любой), получено …`. Проверка стоит до предупреждений о знаке: не конечное значение даёт только отказ.
````
<!-- правка vault/knowledge/debugging/положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке.md #1 после -->
````markdown
- `_validate`: $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ — условие `-inf < v < inf`, иначе `ValueError: thermal.<параметр> должно быть конечным числом (знак любой), получено …`. Проверка стоит до предупреждений о знаке: не конечное значение даёт только отказ. С [[DEBT-051]] этот цикл заменён общим проходом `_check_numeric_fields` по всем числовым полям конфига (в начале `_validate`); текст отказа — `thermal.<параметр> должно быть конечным числом, получено …`, порядок «отказ раньше предупреждений» сохранён.
````

Правка #2, заметка DEBT-049, `:40-41` — «Что не закрыто»:

<!-- правка vault/knowledge/debugging/положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке.md #2 до -->
````markdown
- NaN в прочих числовых полях конфига проходит `_validate` (проверки вида `v <= 0` его пропускают) — [[DEBT-051]]. Худший случай — 11 полей (`porosity`, `p0`, `T0`, `Rs0`, …): отказ после дробления первого шага до dt/512 с советом увеличить `max_retries` (раздел 2 пробы).
- Строка-число в `mu_JT_*` (`"-4e-7"`) раньше проходила через `float()` в конструкторе PVT, теперь — `TypeError` в `_validate` без имени параметра. Проверка типов — [[DEBT-051]].
````
<!-- правка vault/knowledge/debugging/положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке.md #2 после -->
````markdown
- ~~NaN в прочих числовых полях конфига~~ — закрыто [[DEBT-051]]: тип и конечность всех числовых полей проверяются при загрузке. Его проба нашла и молча неверные расчёты: `skin` = ±inf, `p_wf` = +inf — без добычи, `min_bhp` = NaN — ограничение по забою снято. Конечные абсурдные значения (`skin` = 1e6, `p_wf` = 1e12, `min_bhp` = 1e300) дают тот же расчёт без добычи по-прежнему — диапазоны параметров скважины не проверяет никто (план DEBT-051, «Обнаруженные проблемы»).
- ~~Строка-число в `mu_JT_*`~~ — закрыто [[DEBT-051]]: строка, `null`, bool в числовом поле — `ValueError` «… должно быть числом» с именем поля.
````

**Проверка после этого шага:**
- Регресс: `--collect-only -q` (шаг меняет только документы) — 1592.
- Правки шага — только два файла vault (`git diff --stat -- vault/knowledge`).

**Подводные камни:** имя файла заметки DEBT-049 содержит «—» и «;» — в PowerShell брать в кавычки.

**Зависимости:** требует — ничего; блокирует — ничего.

**Оценка:** 4 правки, ~10 минут.

### Шаг 3: Зелёный замер и vault задачи

**Цель:** проба подтверждает: все испорченные случаи отвергаются при загрузке с именем поля, эталонные расчёты не изменились.

**Файлы:**
- `vault/issues/debt-051/probes/green_state.out.txt` (новый)
- запись DEBT-051 в реестре, этот план (статус), `vault/issues/debt-051/05-comment-done.md` — по контракту `/implement`

**Что сделать:**
1. Из `numerical_solver/` worktree:
   ```powershell
   $env:PYTHONIOENCODING = "utf-8"; <PY> ..\vault\issues\debt-051\probes\red_state.py > ..\vault\issues\debt-051\probes\green_state.out.txt
   ```
   (~2 мин: 63 случая, каждый — отдельный процесс с импортом пакета; после правки отказ при загрузке, расчёт идёт только у четырёх эталонов. Красный замер шёл ~10 мин из-за дробления до dt/512.) Первая строка — путь к коду в worktree.
2. Сравнить с `red_state.out.txt`:
   - эталоны (раздел A, C — оба, D) — построчно как в красном замере;
   - остальные случаи — `load_config: ValueError: <секция>.<поле> должно быть конечным числом, получено nan|inf|-inf` или `… должно быть числом, получено …`; у истории — `history[0].<поле>` (проба портит все интервалы — первый отказывает первым).
3. Записать итог в реестр и комментарий issue.

**Проверка после этого шага:** код не меняется — регресс не нужен. Полный прогон — в конце (`/implement` §3.1): ожидание **1592 passed**.

**Зависимости:** требует — шаг 1.

**Оценка:** ~10 минут.

## Тестовая стратегия

**Тест:** `test_field_list_covers_known_fields`
**Файл:** `numerical_solver/tests/test_config.py`, класс `TestValidationNumbers`
**Сценарий:** список `_FLOAT_FIELDS` из аннотаций dataclass
**Ожидание:** содержит 8 известных полей разных секций; длина ≥ 37
**Baseline:** проходит и до правки (тест про способ отбора)
**Предотвращает:** молчаливое выпадение полей из проверки при смене вида аннотаций

**Тест:** `test_nonfinite_rejected` ×74 (37 полей × NaN, inf)
**Сценарий:** `_minimal_raw()`, одно float-поле = NaN или inf
**Ожидание:** `ValueError`, `<секция>.<поле> должно быть конечным`
**Baseline:** до правки — 68 падают (`DID NOT RAISE`; у $c_p$, $(\rho c_p)_s$, λ — текст DEBT-047 «должна быть конечной» не подходит под шаблон), 6 проходят ($L$, $\mu_{JT}$ — текст DEBT-049 подходит)
**Предотвращает:** возврат к отказу через dt/512 и к молча неверным расчётам при не конечных `skin`, `p_wf` (конечные абсурдные значения — вне задачи, «Обнаруженные проблемы», п. 2). `-inf` отдельно не параметризован: его проверяют тесты DEBT-049 `TestValidationThermal::test_nonfinite_scalar_rejected[...--inf]` (`L_degas`, `mu_JT_oil`, `mu_JT_gas`), которые после правки ловит общий проход, — они страхуют условие `-float("inf") < value` от упрощения до `value < inf`

**Тест:** `test_non_number_rejected` ×7
**Сценарий:** строка-число, строка, `null`, `true`, `false` в float-полях
**Ожидание:** `ValueError`, `<секция>.<поле> должно быть числом`
**Baseline:** до правки — `TypeError` или проходит (`true`, `false`)
**Предотвращает:** `TypeError` без имени; bool как число

**Тест:** `test_nonfinite_in_int_field_rejected`
**Сценарий:** `grid.N` = NaN
**Ожидание:** `ValueError`, `grid.N должно быть конечным`
**Предотвращает:** NaN в целом поле мимо `N < 1`

**Тест:** `test_interval_nonfinite_rejected` ×8 (`dt`, `p_wf`, `q_oil`, `min_bhp` × NaN, inf)
**Сценарий:** два интервала, второй испорчен; для `q_oil`, `min_bhp` — `control = "rate"`
**Ожидание:** `ValueError`, `history[1].<поле> должно быть конечным`
**Предотвращает:** снятое ограничение по забою (`min_bhp` = NaN), расчёт без добычи (`p_wf` = inf); неверный номер интервала в сообщении

**Тест:** `test_interval_non_number_rejected` ×2 (`p_wf` = `"6e6"`, `dt` = `true`)
**Ожидание:** `history[1].<поле> должно быть числом`

**Тест:** `test_block_fields_checked` ×4 (`duration`, `dt_out` = NaN; `duration` = inf; `dt_out` = `"3600"`)
**Ожидание:** `ValueError`, `history[0].<поле> должно быть …`
**Baseline:** до правки — `ValueError: cannot convert float NaN to integer`, `OverflowError`, `TypeError` — без имени
**Предотвращает:** `round(NaN)` в `load_config` без имени поля

**Тест:** `test_integer_values_accepted`
**Сценарий:** `geometry.h` = 10, `dt_integration` = 3600 — целые JSON
**Ожидание:** загружается, значения сохранены
**Baseline:** проходит и до правки
**Предотвращает:** отказ на целых числах в float-полях (их пишут конфиги проекта)

**Регрессия (без изменений):** весь `test_config.py` (`TestValidation*` — диапазоны; `TestValidationThermal` — тесты DEBT-047 с NaN/inf и DEBT-049 теперь проходят через общий проход; `TestHistoryBlocks`; `TestBaseline*` — целые в `baseline.json`); быстрый уровень — `tests/test_examples.py::TestConfigs::test_load_config_passes`; полный уровень — фикстура `results`.

## Критерии завершения

- [ ] Шаги 1–3 выполнены
- [ ] `TestValidationNumbers` — 98 passed; `tests/test_config.py` — 245 passed
- [ ] Быстрый уровень 1342 passed, 250 deselected; полный — 1592 passed (база `d3aabff`; при другой — её итог +98)
- [ ] Зелёный замер: все испорченные случаи — `load_config: ValueError` с именем поля; четыре эталона — как в красном
- [ ] Цикл DEBT-049 удалён; предупреждения $L < 0$, $\mu_{JT,o} > 0$ и проверки DEBT-047 на месте
- [ ] P8 §5 — раздел о типе и конечности; заметка DEBT-049 — ссылки на DEBT-051
- [ ] Прототип не тронут
- [ ] Vault: статус DEBT-051, план — «реализован»; комментарий в issue #85

## Обнаруженные проблемы

1. **Молча неверные расчёты при не конечных `skin`, `p_wf`, `min_bhp`** — не новая задача, а поправка оценки DEBT-051: запись реестра и тело issue утверждали «молча неверного расчёта не найдено». Опровергнуто разделами B, C пробы. Приоритет DEBT-051 поднят с «низкого» на «средний» (запись реестра, комментарий #85).
2. **Конечные абсурдные значения параметров скважины молча дают расчёт без добычи** (аудит 1, проба `vault/issues/debt-051/probes/audit1_finite_extremes.py`, `27b7144`, `configs/baseline.json`, 24 ч): `numerics.skin` = 1e6, 1e300, −1e300; `history.p_wf` = 1e12 (при $p_0$ = 20 МПа); `history.min_bhp` = 1e300 при 1000 м³ст/сут — расчёт проходит, $p$ = 20 МПа во всём пласте, $S_g$ = 0, ни отказа, ни предупреждения. `q_oil` = 1e300 — забой держится на `min_bhp` (15.03 МПа, как у эталона с активным ограничением) — это ожидаемое поведение. DEBT-051 закрывает только не конечные значения; диапазоны параметров скважины не проверяет ни `_validate`, ни прототип. Не блокирует. **Зарегистрировано как [[DEBT-056]]** (решение пользователя после аудита 1): там же — отрицательный скин $s \le -\ln(r_1/r_w)$ (у baseline −0.031) даёт $T_w < 0$ и отказ через dt/512 (проба `vault/issues/debt-056/probes/skin_range.py`: $s$ = −0.5, −2).
3. **P8 §5, строки «Общая валидация (geometry, grid) — наш Factory: rw > 0, re > rw, h > 0, N ≥ 1; 0 < φ ≤ 1, k > 0»** — эти проверки живут в `_validate` (`io/config.py:336-351`), а не в фабрике. Неточность документа, задачей не правится (решение пользователя 3 — сообщения `_validate` не трогать; P8 правится только в части DEBT-051). Не регистрируется отдельно: мелкая, исправить при следующей правке P8.

## Проверка плана

Проба `vault/issues/debt-051/probes/plan_check.py` применяет правки плана к текстам файлов в памяти (по меткам `<!-- правка <файл> #N до|после -->`), файлы проекта не меняет. Запуск из `numerical_solver/`:

```powershell
$env:PYTHONIOENCODING = "utf-8"; .venv\Scripts\python ..\vault\issues\debt-051\probes\plan_check.py --fast
```

Результат на `d3aabff` (2026-10-10), вывод — `vault/issues/debt-051/probes/plan_check.out.txt`:

1. **Правки плана:** все 13 меток («до» каждой найдено в своём файле ровно 1 раз): `test_config.py` #1–#3; `io/config.py` #1–#6; P8 #1, #2; заметка DEBT-049 #1, #2. Самая длинная добавленная строка кода — 99 символов.
2. **`TestValidationNumbers` на текущем коде:** 90 failed, 8 passed (состав — шаг 1, п. 2).
3. **`test_config.py` плана на коде с правками:** 245 passed; с настройками pytest проекта, хуком `conftest.py` и `-m "not slow"` — тоже 245 (все новые — в быстром уровне). В том числе тесты DEBT-047 и DEBT-049 с NaN, inf — их теперь ловит общий проход.
4. **Проба `red_state.py` на коде с правками** (все разделы, в одном процессе): четыре эталона — те же строки, что в `red_state.out.txt`; все остальные 58 случаев (A — 30, B — 15, C — 4, D — 2, E — 7) — `load_config: ValueError`: `<секция>.<поле> должно быть конечным числом, получено nan|inf|-inf` (`[config.py:353]`), у истории — `history[0].<поле>` (`dt`, `p_wf`, `q_oil`, `min_bhp`, `duration`, `dt_out`); раздел E — `… должно быть числом, получено '0.2'` (`'3600'`, `'abc'`, `None`, `True`, `'850'`, `'0'`) (`[config.py:349]`). Строки 349 и 353 — `raise` в `_require_finite_number` после правки.
5. **Быстрый уровень существующих тестов на коде с правками:** 1244 passed, 250 deselected, 1 warning (`PytestRemovedIn10Warning`, есть и без подмены), 79 с — ни один существующий тест и ни один конфиг примеров не задеты.

Итого ожидания плана: `test_config.py` 147 → 245, всего 1494 → 1592, быстрый уровень 1244 → 1342.

Аудит 1 повторил этапы 1–4 на `27b7144` (после влития DEBT-052): 13 правок применимы, `TestValidationNumbers` до правки — 90 failed, 8 passed, после — `test_config.py` 245 passed (оба режима), проба — 4 эталона прошли, 58 случаев — `load_config: ValueError`. Числа тестов базы — 1494 / 1244 / 147, как в плане.
