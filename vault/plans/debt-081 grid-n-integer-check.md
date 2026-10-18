---
tags:
  - план
  - рефакторинг
date: 2026-10-18
issue: DEBT-081
github: 135
branch: refactor/debt-081/grid-n-integer-check
status: реализован
worktree: .worktrees/debt-081; удалён после влития
merged: f2d77db (2026-10-18)
audit:
  date: 2026-10-18
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# DEBT-081: `grid.N` проверяется на целое в `_validate`

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-081 в `vault/roadmap/известные баги и технический долг.md` и тело issue #135 (`vault/issues/debt-081/01-issue-body.md`). Тело issue написано до аудита: его фраза о страже `test_field_list_covers_known_fields` неверна, здесь исправлена (§4). Отдельной заметки в `vault/knowledge/` у задачи нет.
3. Образец проверки — `numerics.newton_max_iter`, `max_active_set_iter` (`numerical_solver/gpn_multiphase_solver/io/config.py:730-736`) и `max_retries` (`:711-719`). Образцы тестов — `TestNumericsWiredFields::test_int_field_rejected` и `TestMaxRetriesValidation` (`numerical_solver/tests/test_config.py:1336-1343`, `:604-659`), а для стража по аннотациям — `_FLOAT_FIELDS` и `test_field_list_covers_known_fields` (`:861-871`, `:883-892`).
4. Worktree и ветка — по `/implement`: база `numerical_scheme/implementation`, ветка `refactor/debt-081/grid-n-integer-check` (на 2026-10-18 её нет), каталог `.worktrees/debt-081`.
5. Обозначения: `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas`; `<W>` = `<КОРЕНЬ>\.worktrees\debt-081`; `<PY>` = `<КОРЕНЬ>\numerical_solver\.venv\Scripts\python.exe`. Venv один, в основном каталоге, **своего `.venv` в worktree нет**: команда `.venv\Scripts\python` из `<W>\numerical_solver` не найдёт интерпретатор. Все команды ниже запускаются из `<W>\numerical_solver` интерпретатором `<PY>`. pytest берёт пакет worktree (`python -m` добавляет текущий каталог в `sys.path`) и прототип worktree (`pythonpath` в `numerical_solver/pyproject.toml`). Прототип не меняется: его тесты и регрессия не нужны.
6. **Исходная точка** — `30a64f7` (2026-10-18, FEAT-037 влит во время аудита 1: `5ea30e7`). Задача добавляет **20 тестов**:

   | База | всего | быстрый | `tests/test_config.py` |
   |---|---|---|---|
   | `30a64f7` | 2401 → **2421** | 2125 → **2145** | 338 → **358** |

   Сверка: `<PY> -m pytest tests/ --collect-only -q`, `<PY> -m pytest tests/ -m "not slow" --collect-only -q`. Правая колонка подтверждена эмуляцией на копии `30a64f7` (§11). Если база к началу `/implement` уйдёт дальше — ожидание «база + 20», `test_config.py` — 358 (если чужая задача его не меняла). До FEAT-037 (`86671fc`) было 2395 / 2119.
7. Перед шагом 1 прогнать быстрый уровень (`<PY> -m pytest tests/ -m "not slow" -q`) и запомнить время (на копии `30a64f7` с правкой при аудите — 150 с; §11, `plan_emulate.out.txt`). В worktree один тест пропускается: `tests/test_xlsx_reader.py:476` без черновика книги руководителя `numerical_solver/configs/INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx`. Файл не в git (`reason` теста: «черновик руководителя вне git (решение 11)»), поэтому ни в worktree, ни в копии `git archive` его нет. В основном каталоге тот же тест проходит. Итог в worktree — «(быстрый − 1) passed, 1 skipped».
8. Шаг 1, затем 2, затем 3. После шага 1 — быстрый уровень, после шагов 2 и 3 — `--collect-only -q` и `tests/test_eq_references.py`. Полный прогон — в конце (`/implement` §3.1).

## 1. Задача

### 1.1. Что не так

`_validate` (`numerical_solver/gpn_multiphase_solver/io/config.py:520-521`) проверяет у `grid.N` только `N < 1`:

```python
    if cfg.grid.N < 1:
        raise ValueError(f"N должен быть ≥ 1, получено {cfg.grid.N}")
```

Проверку типа DEBT-051 (`_check_numeric_fields`, `:486-497`) `grid.N` проходит не целиком: она проверяет поле на число и конечность, только если аннотация `float`/`Optional[float]` или значение — `float`. У `GridConfig.N` аннотация `int` (`:34`), поэтому `true`, `"100"` и `null` её минуют, а `100.0` проходит как конечное число.

Конструктор сетки `LogRadialGrid` (`numerical_solver/gpn_multiphase_solver/grid/log_radial.py:35-36`) проверяет `not isinstance(N, int) or N < 1`. Но `bool` — подкласс `int`, так что `True` проходит и здесь, а `self._N = int(N)` (`:40`) даёт 1.

Из пяти полей конфига с аннотацией `int` проверки на целое нет только у `grid.N`. У `numerics.max_retries` (`:713-715`), `newton_max_iter` и `max_active_set_iter` (`:733-736`), `output.n_profiles` (`:761`) она есть, у `history[i].repeat` краткой формы (`:327`; это ключ словаря, не поле dataclass) — тоже, и везде `bool` исключён явно. Все шесть проверок написаны руками, и ни один тест не сторожит, что у каждого целого поля такая проверка есть. Так пробел у `grid.N` и прожил до DEBT-081.

### 1.2. Замер (2026-10-18, `vault/issues/debt-081/probes/`)

**A — разбор значений** (`red_state.py`, `red_state.out.txt`; на `86671fc`, код `io/config.py`, `grid/` с `b9454a6` не менялся). Конфиг — `numerical_solver/examples/01_single_phase_no_jt/config.json` (без CSV); история укорочена до 2 ч, две записи по 1 ч, $p_{wf}$ = 15 МПа. `grid.N` подменяется, затем `load_config` → `SimulatorFactory.from_config` → `Simulator.run`.

| `grid.N` | `load_config` | сборка решателя | расчёт 2 ч |
|---|---|---|---|
| `150` (контроль) | проходит | проходит | 150 ячеек; $q_o$ = 167.847 м³ст/сут; $T_{wf}$ = 349.4773 К в $r_0$ = 0.1021 м |
| `true` | **проходит**, `cfg.grid.N = True` | **проходит** | **1 ячейка**; $q_o$ = 167.847 м³ст/сут; $T_{wf}$ = 349.6223 К в $r_0$ = **2.2361 м** |
| `false` | `ValueError: N должен быть ≥ 1, получено False` | — | — |
| `"100"` | **`TypeError: '<' not supported between instances of 'str' and 'int'`** | — | — |
| `null` | **`TypeError: '<' not supported between instances of 'NoneType' and 'int'`** | — | — |
| `100.0` | **проходит**, `cfg.grid.N = 100.0` | `ValueError: N must be an integer >= 1, got 100.0` | — |
| `100.5` | **проходит** | тот же отказ | — |
| `0`, `-1` | `ValueError: N должен быть ≥ 1, получено 0` (`-1`) | — | — |
| `NaN` | `ValueError: grid.N должно быть конечным числом, получено nan` (DEBT-051) | — | — |

**B — `true` при разгазировании** (`audit1_degassing.py`, `audit1_degassing.out.txt`, аудит 1). Пример 03 (`numerical_solver/examples/03_standing_corey/config.json`: Стендинг + Кори, $R_{s,0}$ = 50, $p_0$ = 20 МПа), 2 ч при $p_{wf}$ = 8 МПа:

| `grid.N` | ячеек | $q_o$, м³ст/сут | ГФ, м³ст/м³ст | $S_g[0]$ | $T_{wf}$, К | $r_0$, м |
|---|---|---|---|---|---|---|
| `150` | 150 | 937.809 | 50.000 | 0.0813 | 351.0801 | 0.1021 |
| `true` | 1 | 947.443 (+1.0 %) | 50.000 | **0** | 349.6470 (−1.43 К) | 2.2361 |

Выводы:
- **`true` — неверный расчёт без сообщения.** На одной ячейке давление в её центре $r_0 = \sqrt{r_w R_{ext}}$ = 2.24 м выше $p_b$, и газ не выделяется вовсе: $S_g$ = 0 вместо 0.0813 у забоя. Дебит отличается на 1 %, $T_{wf}$ — на 1.43 К и относится к точке в 2.24 м от оси, а не в 0.102 м (`T_wf` — температура центра ячейки 0, BUG-015). В однофазном примере 01 дебит совпал с контролем точно: двухточечный поток на логарифмической сетке точен для $p \propto \ln r$ при любом $N$, и ошибку выдаёт только $T_{wf}$.
- **`"100"`, `null`** — `TypeError` без имени поля. По правилу DEBT-051 такой отказ должен быть `ValueError` с узлом JSON.
- **`100.0`, `100.5`** — отказ откладывается до сборки решателя, звучит по-английски и не называет узел JSON.
- **`0`, `-1`, `false`** — отказ есть, но в сообщении нет префикса `grid.`, а `false` назван как число («≥ 1, получено False»).

### 1.3. Мотивация и приоритет

Конфиг — канонический вход команды расчёта `gpn-solver run` (FEAT-030) и результат перевода книги Excel (`gpn-solver convert`, FEAT-035, влит `86348ed`). Перевод пишет `grid.N` целым (`numerical_solver/gpn_multiphase_solver/io/workbook_convert.py:220-222`: `int(v) if limit.integer`), так что дефекта не задевает. Не защищён JSON, набранный или правленный вручную, — а именно так конфиг правит команда разработки заказчика (поставка, модель Б). Логическое значение в числовом поле DEBT-051 уже признал опечаткой, а не 1 (`_require_finite_number`, `:476-477`). Приоритет средний: `true` даёт неверный расчёт молча.

## 2. Текущее состояние

### 2.1. Код

| Файл | Строки | Что |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/io/config.py` | 34 | `GridConfig.N: int` |
| там же | 451 | `load_config` → `_validate(config)` — единственный вызов `_validate` в `numerical_solver/` |
| там же | 465-466 | `_NUMERIC_SECTIONS` — `grid` входит, `output` нет |
| там же | 474-483 | `_require_finite_number`: bool, строка, `null` → «должно быть числом»; NaN, ±inf → «должно быть конечным» |
| там же | 486-497 | `_check_numeric_fields`: поля `float`/`Optional[float]` и любое значение `float` (NaN в `grid.N`) |
| там же | 509-510 | вызов `_check_numeric_fields` по секциям — **до** проверок диапазона |
| там же | **520-521** | `if cfg.grid.N < 1` — **место правки** |
| там же | 711-719, 730-736, 760-763, 327 | проверки целого у `max_retries`, `newton_max_iter`/`max_active_set_iter`, `n_profiles`, `repeat`. Тексты: «numerics.max_retries должен быть целым, …», «numerics.<поле> должен быть целым ≥ 1, …», «output.n_profiles должен быть целым ≥ 2 или null, …» |
| `numerical_solver/gpn_multiphase_solver/grid/log_radial.py` | 35-36, 40 | предохранитель сетки `not isinstance(N, int) or N < 1` (англ.), `self._N = int(N)` — **не меняется** |
| `numerical_solver/gpn_multiphase_solver/io/workbook_convert.py` | 220-222 | перевод книги пишет целые поля как `int` — **не меняется** |

Поля с аннотацией `int`/`Optional[int]` в `io/config.py` — ровно пять: `grid.N`, `numerics.newton_max_iter`, `max_active_set_iter`, `max_retries`, `output.n_profiles` (grep `^\s+\w+: (Optional\[)?int\b`; находит и вид `int | None`).

Конфиги, собранные в коде (`cfg.grid.N = N` в `examples/*/grid_convergence.py`, `spatial_convergence.py`, `closed_form_convergence.py`, тестах `test_val001.py`, `test_mass_balance.py` и др.), `_validate` не проходят — правка их не касается. Все 33 файла `*.json` в `numerical_solver/` задают `"N"` целым литералом (grep `"N":\s*(\d+\.|[^\d\s])` — пусто). `examples/18_prototype_input/prototype_input.py:171` пишет `int(float(...))`.

### 2.2. Тесты, которые касаются кода

| Тест | Файл | Что проверяет | После правки |
|---|---|---|---|
| `TestValidationGrid::test_N_zero` | `numerical_solver/tests/test_config.py:349-353` | `N = 0` → `ValueError`, `match="N"` | зелёный без правки (новый текст содержит «N») |
| `TestValidationNumbers::test_nonfinite_in_int_field_rejected` | там же, `:921-927` | NaN в `grid.N` → «grid.N должно быть конечным» | зелёный без правки: `_check_numeric_fields` срабатывает раньше новой проверки |
| `TestValidationNumbers::test_field_list_covers_known_fields` | там же, `:883-892` | страж отбора **float**-полей по аннотациям | не меняется; о целых полях не знает — их страж добавляет шаг 1 |
| `TestMaxRetriesValidation::test_float_rejected`, `test_bool_rejected`; `TestNumericsWiredFields::test_int_field_rejected` | там же, `:647-659`, `:1336-1343` | `max_retries`, `newton_max_iter`, `max_active_set_iter`: дробное и bool | не меняются; новый страж частично их повторяет (§7) |
| `TestBaselineGrid`, `TestMinimalConfig` | там же, `:60-66`, `:289-302` | `cfg.grid.N == 100`, `== 10` | зелёные |
| `TestValidation` (три теста о `N`) | `numerical_solver/tests/test_grid.py:39-47` | предохранитель `LogRadialGrid`: «N must be an integer >= 1» | не меняются |
| перевод книги: `test_integer_fields_written_as_int` и др. | `numerical_solver/tests/test_workbook_convert.py` | целые поля → `int`, `load_config` проходит | зелёные (эмуляция, §11) |

### 2.3. Документы с правилом `N ≥ 1`

| Документ | Строка | Что сейчас | Правка |
|---|---|---|---|
| `vault/knowledge/decisions/P8-формат-ввода-json.md` | 267 | «rw > 0, re > rw, h > 0, N ≥ 1» | шаг 2 |
| `vault/knowledge/decisions/перевод книги в конфиг проверяет только книгу — моменты SCHEDULE в целых мс.md` | 28 | «у `grid.N` проверки целого в `_validate` нет — [[DEBT-081]]» — после правки неверно | шаг 2 |
| `vault/knowledge/decisions/json-config-schema.md` | 38 | «Ограничения: `N >= 1` (обновлено, см. P8)» — ранняя заметка, отсылает к P8 | не меняется |
| `numerical_solver/README.md` | 123 | строка таблицы полей: «число ячеек логарифмической сетки…» | не меняется: таблица не указывает тип ни у одного поля, у `max_retries` и прочих целых тоже |

## 3. Целевое состояние

- `_validate`: `grid.N` — целое ≥ 1, `bool` исключён явно. Иначе — `ValueError("grid.N должен быть целым ≥ 1, получено <repr>")` при загрузке конфига, до сборки решателя. Текст — как у `numerics.newton_max_iter`.
- Порядок отказов прежний: сначала тип и конечность `_check_numeric_fields` (NaN, inf → «должно быть конечным»), потом геометрия (`r_well`, `R_ext`, `h`), потом `grid.N`.
- `TestValidationGrid`: параметризованный отказ (8 случаев) и тест, что `N = 1` принимается.
- `TestValidationNumbers`: страж целых полей по аннотациям — каждое поле с аннотацией `int`/`Optional[int]` отвергает `true` и `2.5` текстом «<секция>.<поле> должен быть целым» (5 полей × 2 значения), плюс страж способа отбора. Новое целое поле без своей проверки в `_validate` уронит тест. Это закрывает класс дефекта, а не только `grid.N`.
- Тестов +20 (§«Как начать», п. 6).
- P8 и заметка о переводе книги — с новым правилом.
- Истории примеров не меняются: меняется только проверка ввода, все конфиги задают `N` целым.

Не меняется (зона неприкосновенности):
- `LogRadialGrid` (`grid/log_radial.py`) и его тесты: внутренний предохранитель для конфигов, собранных в коде, и прямых вызовов;
- `_check_numeric_fields`, `_require_finite_number` — правило DEBT-051;
- проверки остальных целых полей и их тексты;
- перевод книги (`io/workbook_convert.py`, `io/workbook_format.py`) и его тесты;
- прототип `numerical_solver/HydroSolverPrototype/`, в том числе `input_reader.py:50` (своя проверка «Grid cells N must be an integer»);
- конфиги и CSV примеров, `numerical_solver/README.md`, `numerical_solver/CHANGELOG.md` (см. §5, FEAT-037).

## 4. Варианты

| | Суть | Плюсы | Минусы |
|---|---|---|---|
| **1** (выбран) | в `_validate` заменить `N < 1` на `isinstance(N, bool) or not isinstance(N, int) or N < 1` → `ValueError` с узлом `grid.N`; плюс тест-страж целых полей по аннотациям (добавлен аудитом 1) | одна правка кода на месте прежней проверки; тот же код и текст, что у пяти других целых полей; `test_N_zero` зелёный без правки; страж ловит следующее целое поле без проверки — без правки кода проверок | проверки целого в `_validate` остаются разными строками у каждого поля. **Аудит 1:** до аудита здесь стояло «страж `test_field_list_covers_known_fields` о новом поле напомнит» — неверно: тот страж отбирает только `f.type == "float"` (`test_config.py:870`) и о целых полях не знает. Без нового стража у варианта 1 защиты от повторения нет |
| 2 | общая проверка целых полей в `_check_numeric_fields` по аннотациям `int`/`Optional[int]`; диапазоны — на местах | одно место в коде; новое целое поле защищено без правки кода | правка шире задачи: меняется путь проверки четырёх полей и их тексты, на которые завязаны тесты (`match=` «должен быть целым»); `output` не входит в `_NUMERIC_SECTIONS` — пришлось бы менять и перечень секций; `history[i].repeat` — ключ словаря, не поле, в общую проверку не попадает. Ту же защиту от повторения даёт страж варианта 1 без правки кода проверок |
| 3 | приводить `100.0` к `100` | JSON из стороннего генератора с `100.0` проходит | молчаливое приведение типа: DEBT-051 отверг его для строк, `max_retries` = 9.5 (и 9.0: `isinstance(9.0, int)` ложно) отвергается (`test_float_rejected`); в JSON целое пишется без точки; перевод книги пишет `int`. **Отклонён** |
| 4 | исключить `bool` и перевести сообщение в `LogRadialGrid` | закрывает и конфиги, собранные в коде | `TypeError` на строке и `null` возникает раньше, в `_validate`; узел JSON сетке неизвестен; отказ остаётся отложенным до сборки решателя; меняются тексты `test_grid.py`. **Отклонён** |

Выбор по критериям DEBT: минимальный diff кода, обратная совместимость (все прежние рабочие конфиги проходят), тестируемость (отказ — в `load_config`, без сборки решателя).

## 5. Подводные камни

| Пункт | | Как адресовано |
|---|---|---|
| Все вызовы найдены | ✅ | `_validate` вызывается только из `load_config` (`config.py:451`; grep `_validate\(` по `numerical_solver/**/*.py`). Текст «N должен быть ≥ 1» встречается только в `config.py:521` и в пробе `vault/issues/debt-008/probes/plan_check.py:203` — это снимок на дату, тестами не запускается, не правится |
| Зависимости пакетов | ✅ | нет |
| Обратная совместимость | ✅ | `load_config` — прежняя сигнатура. Из конфигов, по которым раньше шёл расчёт, отказ получает только `"N": true` — это и есть дефект. `100.0` и `100.5` и раньше до расчёта не доходили (отказ `LogRadialGrid`), `"100"` и `null` давали `TypeError`. Все 33 JSON проекта задают целое (§2.1). По правилу номеров `CHANGELOG.md` (FEAT-037) это исправление, не несовместимое изменение формата |
| Состояние при ошибке | ✅ | `ValueError` из `_validate` до создания сетки и решателя; предупреждения `load_config` идут после всех отказов (порядок DEBT-056) — не меняется |
| Тесты | ✅ | ни один существующий тест не ломается (§2.2; эмуляция на копии — §11). Конфиги, собранные в коде (`cfg.grid.N = 25`), `_validate` не проходят |
| Порядок проверок | ✅ | NaN и inf отсекает `_check_numeric_fields` (`:509-510`) раньше — `test_nonfinite_in_int_field_rejected` сохраняет текст «должно быть конечным». Геометрия — раньше `grid.N`, как сейчас. Страж со значением `2.5`: у полей `grid`, `numerics` `_check_numeric_fields` пропускает конечное `2.5`, отказ даёт проверка целого; у `output.n_profiles` секция не входит в `_NUMERIC_SECTIONS` — отказ сразу от проверки `:761` |
| Страж целых полей (аудит 1) | ✅ | отбор `f.type in ("int", "Optional[int]")` по десяти классам секций; аннотации — строки (`from __future__ import annotations`, как у `_FLOAT_FIELDS`). Сменят вид (`int \| None`) — список опустеет; это ловит `test_int_field_list_covers_known_fields` (пять известных полей). Тексты всех пяти полей содержат «<секция>.<поле> должен быть целым» (§2.1) — общий `match` подходит |
| Циклические импорты | ✅ | новых импортов нет: `GridConfig`, `OutputConfig`, `fields` уже импортированы в `test_config.py:27-35` |
| Ссылки на уравнения | ✅ | новых ссылок на `.tex` нет. Тексты плана для кода и заметок не попадают под шаблоны `FORBIDDEN` (`numerical_solver/tests/test_eq_references.py`), а сторож проверяет и комментарии, и заметки `vault/knowledge`, кроме `literature/` (DEBT-074). Прогон — после шагов 1 и 2 (эмуляция — зелёный) |
| Конфиги | ✅ | имена параметров не меняются |
| Связь с другими задачами | ✅ | **FEAT-037** (журнал версий, #134): влит во время аудита 1 (`5ea30e7`, «влит» `30a64f7`). Его файлы (`CHANGELOG.md`, `README.md`, `examples/README.md`, `__init__.py`, `cli.py`, `report/pipeline.py`, `pyproject.toml`, `test_cli.py`, `test_examples.py`, `test_packaging.py`) с файлами DEBT-081 не пересекаются (`git diff --stat 86671fc 30a64f7` по файлам задачи пуст); база + 6 тестов учтены в п. 6 «Как начать». Незавершённых веток задач нет (`git branch --no-merged`). `CHANGELOG.md` говорит: «Изменения, ещё не вошедшие в выпуск, — в разделе «Не выпущено»». Однако решение 6 плана FEAT-037 — журнал между выпусками сводится при выпуске по истории git, `/implement` не меняется. DEBT-081 `CHANGELOG.md` **не правит**. **DEBT-051** (влита `d5fd87e`): её правило «bool в числовом поле — опечатка» распространяется на `grid.N`, её тест NaN не меняется. **FEAT-035** (влит `86348ed`): перевод пишет `int`, его тесты проходят через `load_config` (эмуляция); заметку FEAT-035 правит шаг 2 |
| Производительность | ✅ | три сравнения при загрузке; +20 тестов по ~10 мс (`load_config` минимального конфига) |
| Прототип | ✅ | не меняется — тесты прототипа и регрессия не нужны |
| Длина строк | ✅ | линтера длины строки в проекте нет (`pyproject.toml` без `[tool.ruff]`); новые строки кода и тестов не длиннее 98 символов (≤ 100; замер по блокам плана, `plan_emulate.out.txt`) |
| Окружение worktree (аудит 1) | ✅ | своего `.venv` в worktree нет — все команды через `<PY>` (§«Как начать», п. 5) |

## 6. Шаги

### Шаг 1: проверка `grid.N` на целое, тесты и страж целых полей

**Цель:** `load_config` отвергает нецелое `grid.N` (`true`, `false`, строку, `null`, `100.0`, `100.5`) и `N < 1` сообщением с узлом JSON; тесты `grid.N` и страж, что каждое целое поле отвергает `true` и дробное.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/io/config.py`
- `numerical_solver/tests/test_config.py`

**Контекст:** §1–§2. Порядок внутри шага: сначала тесты (п. 1–4), прогон — новые красные; затем правка `config.py` (п. 5) — все зелёные. Каждый блок «До» ниже встречается в своём файле ровно один раз (на `30a64f7`): это проверяет `vault/issues/debt-081/probes/plan_emulate.py`, который берёт блоки из текста этого плана по порядку. Блоки п. 1–4 правят один файл в разных местах и друг от друга не зависят.

**Что сделать:**

1. `numerical_solver/tests/test_config.py`, докстринг модуля (`:16`) — два пункта перед пунктом о породе.

До:
```python
- Порода: сжимаемость rock.compressibility ≥ 0 (DEBT-068).
```
После:
```python
- Сетка: grid.N — целое ≥ 1; true, строка, null, 100.0 — отказ при загрузке (DEBT-081).
- Целые поля: каждое поле секции с аннотацией int отвергает true и 2.5 (страж, DEBT-081).
- Порода: сжимаемость rock.compressibility ≥ 0 (DEBT-068).
```

2. `numerical_solver/tests/test_config.py`, класс `TestValidationGrid` (`:348-353`) — два теста после `test_N_zero`; сам `test_N_zero` не меняется.

До:
```python
class TestValidationGrid:
    def test_N_zero(self, tmp_path):
        raw = _minimal_raw()
        raw["grid"]["N"] = 0
        with pytest.raises(ValueError, match="N"):
            load_config(_write_json(tmp_path, raw))
```
После:
```python
class TestValidationGrid:
    def test_N_zero(self, tmp_path):
        raw = _minimal_raw()
        raw["grid"]["N"] = 0
        with pytest.raises(ValueError, match="N"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("value", [True, False, "100", None, 100.0, 100.5, 0, -1],
                             ids=["true", "false", "str", "null", "float_integral",
                                  "fraction", "zero", "negative"])
    def test_N_not_positive_integer_rejected(self, tmp_path, value):
        """grid.N — целое ≥ 1, иначе ValueError с узлом JSON при загрузке (DEBT-081)."""
        # До DEBT-081 (vault/issues/debt-081/probes/red_state.out.txt): true —
        # расчёт на одной ячейке молча (bool — подкласс int); "100" и null —
        # TypeError в сравнении без имени поля; 100.0 и 100.5 load_config
        # пропускал, отказ давал LogRadialGrid при сборке решателя, по-английски;
        # 0, -1, false — отказ без префикса grid. 100.0 не приводится к 100 — как
        # max_retries (test_float_rejected): в JSON целое пишется без точки,
        # перевод книги (FEAT-035) пишет int.
        raw = _minimal_raw()
        raw["grid"]["N"] = value
        with pytest.raises(ValueError, match=r"grid\.N должен быть целым ≥ 1"):
            load_config(_write_json(tmp_path, raw))

    def test_N_one_accepted(self, tmp_path):
        """N = 1 — нижняя граница: сетку из одной ячейки LogRadialGrid строит."""
        # Отличие от true — тип: 1 записано целым, это осознанный выбор, не опечатка
        raw = _minimal_raw()
        raw["grid"]["N"] = 1
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.grid.N == 1 and type(cfg.grid.N) is int
```

3. `numerical_solver/tests/test_config.py`, после `_FLOAT_FIELDS` (`:864-871`) — список целых полей по аннотациям.

До:
```python
_FLOAT_FIELDS = [
    (section, f.name)
    for section, cls in (("geometry", GeometryConfig), ("rock", RockConfig),
                         ("pvt", PVTConfig), ("relperm", RelPermConfig),
                         ("thermal", ThermalConfig), ("initial_conditions", InitialConfig),
                         ("time", TimeConfig), ("numerics", NumericsConfig))
    for f in fields(cls) if f.type == "float"
]
```
После:
```python
_FLOAT_FIELDS = [
    (section, f.name)
    for section, cls in (("geometry", GeometryConfig), ("rock", RockConfig),
                         ("pvt", PVTConfig), ("relperm", RelPermConfig),
                         ("thermal", ThermalConfig), ("initial_conditions", InitialConfig),
                         ("time", TimeConfig), ("numerics", NumericsConfig))
    for f in fields(cls) if f.type == "float"
]


# Целые поля секций — по аннотациям, как _FLOAT_FIELDS (DEBT-081). Проверку
# целого _validate пишет у каждого поля отдельно: _check_numeric_fields тип int
# не проверяет, а bool — подкласс int. До DEBT-081 у grid.N её не было, и
# "N": true давал расчёт на одной ячейке молча. Новое поле с аннотацией int
# попадает в test_int_field_rejects_non_integer само и без своей проверки в
# _validate уронит тест. repeat краткой формы истории — ключ словаря, не поле.
_INT_FIELDS = [
    (section, f.name)
    for section, cls in (("geometry", GeometryConfig), ("grid", GridConfig),
                         ("rock", RockConfig), ("pvt", PVTConfig),
                         ("relperm", RelPermConfig), ("thermal", ThermalConfig),
                         ("initial_conditions", InitialConfig), ("time", TimeConfig),
                         ("numerics", NumericsConfig), ("output", OutputConfig))
    for f in fields(cls) if f.type in ("int", "Optional[int]")
]
```

4. `numerical_solver/tests/test_config.py`, класс `TestValidationNumbers` — два теста после `test_nonfinite_in_int_field_rejected` (`:921-927`); сам тест не меняется.

До:
```python
    def test_nonfinite_in_int_field_rejected(self, tmp_path):
        """NaN в целом поле (grid.N) — тоже отказ по конечности."""
        # `N < 1` NaN пропускает: сравнение с NaN ложно
        raw = _minimal_raw()
        raw["grid"]["N"] = float("nan")
        with pytest.raises(ValueError, match=r"grid\.N должно быть конечным"):
            load_config(_write_json(tmp_path, raw))
```
После:
```python
    def test_nonfinite_in_int_field_rejected(self, tmp_path):
        """NaN в целом поле (grid.N) — тоже отказ по конечности."""
        # `N < 1` NaN пропускает: сравнение с NaN ложно
        raw = _minimal_raw()
        raw["grid"]["N"] = float("nan")
        with pytest.raises(ValueError, match=r"grid\.N должно быть конечным"):
            load_config(_write_json(tmp_path, raw))

    def test_int_field_list_covers_known_fields(self):
        """Список целых полей из аннотаций содержит пять известных (DEBT-081)."""
        # Страж способа отбора, как test_field_list_covers_known_fields: сменят
        # аннотации вид («int | None») — список опустеет вместе с тестом ниже
        known = {("grid", "N"), ("numerics", "newton_max_iter"),
                 ("numerics", "max_active_set_iter"), ("numerics", "max_retries"),
                 ("output", "n_profiles")}
        assert known <= set(_INT_FIELDS)

    @pytest.mark.parametrize("value", [True, 2.5], ids=["bool", "fraction"])
    @pytest.mark.parametrize("section, key", _INT_FIELDS,
                             ids=[f"{s}.{k}" for s, k in _INT_FIELDS])
    def test_int_field_rejects_non_integer(self, tmp_path, section, key, value):
        """true и 2.5 в целом поле → ValueError «<секция>.<поле> должен быть целым» (DEBT-081)."""
        # Тексты у полей разные («целым», «целым ≥ 1», «целым ≥ 2 или null»),
        # общий префикс — «<секция>.<поле> должен быть целым»
        raw = _minimal_raw()
        raw.setdefault(section, {})[key] = value
        with pytest.raises(ValueError, match=rf"{section}\.{key} должен быть целым"):
            load_config(_write_json(tmp_path, raw))
```

   Прогон: `<PY> -m pytest tests/test_config.py -q -k "TestValidationGrid or int_field_rejects or int_field_list"` — ожидается **10 failed, 11 passed**:
   - `TestValidationGrid` — 8 failed, 2 passed (`test_N_zero`, `test_N_one_accepted`). Причины: `true`, `float_integral`, `fraction` — исключения нет; `str`, `null` — `TypeError` вместо `ValueError`; `false`, `zero`, `negative` — `ValueError` с текстом «N должен быть ≥ 1», без `grid.` и «целым».
   - страж — 2 failed (`grid.N-bool`, `grid.N-fraction`: исключения нет), 9 passed (остальные четыре поля × 2 и `test_int_field_list_covers_known_fields`). Страж находит именно дефект DEBT-081.

5. `numerical_solver/gpn_multiphase_solver/io/config.py`, `_validate` (`:520-521`).

До:
```python
    if cfg.grid.N < 1:
        raise ValueError(f"N должен быть ≥ 1, получено {cfg.grid.N}")
```
После:
```python
    # grid.N — целое ≥ 1 (DEBT-081); bool исключается явно, как у max_retries.
    # До DEBT-081 здесь было только N < 1, и "N": true проходил и это сравнение
    # (True == 1), и LogRadialGrid (bool — подкласс int): расчёт шёл на сетке из
    # одной ячейки молча. Давление в её центре r_0 = sqrt(r_w·R_ext) (2.24 м в
    # примерах 01, 03) выше, чем у забоя: в примере 03 газ не выделялся вовсе,
    # T_wf — на 1.43 К ниже и в 2.24 м от оси вместо 0.102 м (vault/issues/
    # debt-081/probes/). Строка "100" и null давали TypeError в сравнении без
    # имени поля, 100.0 — отказ LogRadialGrid по-английски при сборке решателя.
    # 100.0 к 100 не приводится: в JSON целое пишется без точки, перевод книги
    # (FEAT-035) пишет int. NaN и inf отсёк _check_numeric_fields выше.
    N = cfg.grid.N
    if isinstance(N, bool) or not isinstance(N, int) or N < 1:
        raise ValueError(f"grid.N должен быть целым ≥ 1, получено {N!r}")
```

   `{N!r}`: строка видна в кавычках (`'100'`), `True` и `None` — как есть, так же, как у `newton_max_iter`. Пустая строка после блока и комментарий `grid.type` (`:523`) — без изменений.

**Проверка после этого шага:**
- `<PY> -m pytest tests/test_config.py -q` — **358 passed** (было 338).
- Регресс: быстрый — `<PY> -m pytest tests/ -m "not slow" -q`. В worktree на базе `30a64f7` — **2144 passed, 1 skipped** («(быстрый − 1) passed, 1 skipped», п. 7 «Как начать»; так и вышло на копии при аудите, 150 с).
- `<PY> -m pytest tests/test_eq_references.py -q` — зелёный (комментарии проверяет сторож).
- Проба «после»: из `<W>\numerical_solver` — `<PY> ..\vault\issues\debt-081\probes\red_state.py green_state.out.txt`. Путь пакета в первой строке вывода — worktree (скрипт сам ставит текущий каталог первым в `sys.path`). Ожидание: строка `150` — как в `red_state.out.txt` (150 ячеек, $q_o$ = 167.847, $T_{wf}$ = 349.4773 К); `NaN` — прежний отказ «должно быть конечным»; остальные восемь — `ValueError: grid.N должен быть целым ≥ 1, получено …` из `load_config`.

**Подводные камни:** §5 — «Порядок проверок», «Страж целых полей», «Тесты».

**Зависимости:** требует — ничего; блокирует — шаги 2, 3.

**Оценка:** ~15 строк кода, ~75 строк тестов, ~30 минут.

### Шаг 2: документы с правилом

**Цель:** P8 и заметка о переводе книги говорят то, что делает код после шага 1.

**Файлы:**
- `vault/knowledge/decisions/P8-формат-ввода-json.md`
- `vault/knowledge/decisions/перевод книги в конфиг проверяет только книгу — моменты SCHEDULE в целых мс.md`

**Что сделать:**

1. P8, раздел «Геометрия, сетка, порода» (`:267`).

До:
```markdown
- rw > 0, re > rw, h > 0, N ≥ 1
```
После:
```markdown
- rw > 0, re > rw, h > 0; `grid.N` — целое ≥ 1: `true`/`false`, строка, `null`, `100.0` — отказ `grid.N должен быть целым ≥ 1` ([[DEBT-081]]; до него `true` давал расчёт на одной ячейке молча, `"100"` и `null` — `TypeError`, `100.0` — отказ `LogRadialGrid` при сборке решателя; `LogRadialGrid` `bool` по-прежнему принимает — предохранитель для конфигов, собранных в коде). Что у каждого поля с аннотацией `int` такая проверка есть, сторожит `test_config.py::TestValidationNumbers::test_int_field_rejects_non_integer`
```

2. Заметка о переводе книги, строка таблицы «Целые поля» (`:28`).

До:
```markdown
| Целые поля | `grid.N`, `max_retries`, `newton_max_iter`, `max_active_set_iter` — `int` (100.0 → 100, 100.5 — отказ) | Excel хранит числа вещественными; у `grid.N` проверки целого в `_validate` нет — [[DEBT-081]] |
```
После:
```markdown
| Целые поля | `grid.N`, `max_retries`, `newton_max_iter`, `max_active_set_iter` — `int` (100.0 → 100, 100.5 — отказ) | Excel хранит числа вещественными, а `_validate` у всех четырёх полей требует `int`: 100.0 в JSON — отказ (у `grid.N` — с [[DEBT-081]]) |
```

**Проверка после этого шага:**
- Регресс: `--collect-only -q` (меняются только документы) — число из таблицы п. 6 «Как начать» (база + 20).
- `<PY> -m pytest tests/test_eq_references.py -q` — зелёный (сторож читает заметки `vault/knowledge`).

**Зависимости:** требует — шаг 1.

**Оценка:** 2 строки, ~5 минут.

### Шаг 3: vault

**Цель:** запись задачи и итог.

**Файлы:** `vault/roadmap/известные баги и технический долг.md`; `vault/issues/debt-081/probes/green_state.out.txt` (шаг 1); `vault/issues/debt-081/05-comment-done.md` (по `/implement`).

**Что сделать:**
- статус DEBT-081 — по правилам `/implement` (реализован, ветка, коммиты, число тестов, быстрый, полный);
- `green_state.out.txt` закоммитить вместе с vault задачи: это текстовый вывод пробы, не `*.npz` и не `*.png`;
- в `05-comment-done.md` упомянуть, что тело issue (вариант 1, «минус») поправлено аудитом 1: страж float-полей о целых не знает, добавлен страж целых.

**Проверка после этого шага:**
- Регресс: `--collect-only -q` — число из таблицы п. 6 «Как начать».

**Оценка:** ~10 минут.

## 7. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `TestValidationGrid::test_N_not_positive_integer_rejected[true]` (новый) | `numerical_solver/tests/test_config.py` | `_minimal_raw()`, `grid.N = true` | `ValueError` «grid.N должен быть целым ≥ 1» из `load_config` | расчёт на одной ячейке молча: `bool` принят как 1 |
| `…[false]` | там же | `grid.N = false` | то же | `false` назван числом («≥ 1, получено False») |
| `…[str]`, `…[null]` | там же | `grid.N = "100"`, `null` | то же, не `TypeError` | `TypeError` без имени поля |
| `…[float_integral]` | там же | `grid.N = 100.0` | то же | отказ отложен до сборки решателя, по-английски; или молчаливое приведение к 100 (вариант 3 не выбран) |
| `…[fraction]` | там же | `grid.N = 100.5` | то же | то же |
| `…[zero]`, `…[negative]` | там же | `grid.N = 0`, `-1` | то же | диапазон снят при переписывании условия; текст без `grid.` |
| `TestValidationGrid::test_N_one_accepted` (новый) | там же | `grid.N = 1` | `load_config` без исключения, `cfg.grid.N == 1`, тип `int` | слишком строгая проверка (`N < 2`) или отказ на `1` из-за сравнения типа вместо исключения `bool` |
| `TestValidationNumbers::test_int_field_rejects_non_integer[<секция>.<поле>-bool / -fraction]` (новый, 10 случаев) | там же | `_minimal_raw()`, каждое поле с аннотацией `int`/`Optional[int]` = `true`, `2.5` | `ValueError` «<секция>.<поле> должен быть целым» | **новое целое поле без проверки целого** — повторение DEBT-081; снятая при правке проверка у `max_retries`, `newton_max_iter`, `max_active_set_iter`, `n_profiles` |
| `TestValidationNumbers::test_int_field_list_covers_known_fields` (новый) | там же | `_INT_FIELDS` | содержит пять известных полей | смена вида аннотаций (`int \| None`) опустошает страж молча |
| `TestValidationGrid::test_N_zero` (существующий) | там же | `grid.N = 0` | `ValueError`, `match="N"` | — (остаётся) |
| `TestValidationNumbers::test_nonfinite_in_int_field_rejected` (существующий) | там же | `grid.N = NaN` | «grid.N должно быть конечным» | новая проверка поставлена раньше `_check_numeric_fields` |
| `TestValidation` (существующие) | `numerical_solver/tests/test_grid.py` | прямой вызов `LogRadialGrid` | прежние тексты | правка предохранителя сетки вне задачи |
| регресс: быстрый уровень, полный в конце | `numerical_solver/tests/` | все примеры (в медленных) | зелёные; истории не меняются | поломку примеров и перевода книги |

Пересечение стража с существующими тестами (`max_retries` bool и 9.5, `newton_max_iter`/`max_active_set_iter` bool и 2.5) — сознательное. Те тесты проверяют конкретные поля, страж — что ни одно целое поле не осталось без проверки.

## 8. Критерии завершения

- [ ] `_validate` отвергает `grid.N`, если это не `int`, `bool` или `< 1`: `ValueError("grid.N должен быть целым ≥ 1, получено …")`; комментарий со ссылкой на DEBT-081 и замер.
- [ ] Новые тесты зелёные: `TestValidationGrid` — 8 + 1, страж — 10 + 1. `test_N_zero`, `test_nonfinite_in_int_field_rejected`, `test_grid.py` — без правок и зелёные.
- [ ] Тестов — база + 20 (таблица п. 6 «Как начать»), `test_config.py` — 358. Быстрый уровень в worktree — «(быстрый − 1) passed, 1 skipped» (черновик книги вне git); полный прогон зелёный с тем же пропуском.
- [ ] `green_state.out.txt`: восемь случаев — `ValueError` из `load_config` с `grid.N`; контроль 150 — прежние числа; NaN — прежний отказ.
- [ ] P8 и заметка о переводе книги — с правилом; `tests/test_eq_references.py` зелёный.
- [ ] `LogRadialGrid`, перевод книги, прототип, `CHANGELOG.md` не тронуты: `git diff --stat <база> -- numerical_solver/gpn_multiphase_solver/grid numerical_solver/gpn_multiphase_solver/io/workbook_convert.py numerical_solver/HydroSolverPrototype numerical_solver/CHANGELOG.md` пуст.
- [ ] Vault: статус DEBT-081; комментарий в #135 (`05-comment-done.md`).

## 9. Обнаруженные проблемы

1. **`LogRadialGrid` принимает `N = True` как 1** (`grid/log_radial.py:35`, `isinstance(True, int)`), сообщение — по-английски. После DEBT-081 путь через конфиг закрыт. Остаются конфиги, собранные в коде, и прямые вызовы — там `True` вместо числа ячеек маловероятен. Прототип (`radial_blackoil/grid.py`) не проверялся. Не блокирует; не регистрируется. При желании пользователя — одна строка `isinstance(N, bool) or …` в предохранителе (тексты `test_grid.py` прежние).
2. **Совпадение дебита — не признак верной сетки** (§1.2). В однофазном несжимаемом примере 01 `N = 1` даёт тот же дебит, что 150 ячеек, — это точность двухточечного потока на логарифмической сетке для $p \propto \ln r$, свойство схемы, не дефект. При разгазировании (пример 03) одна ячейка теряет газ целиком: давление в центре ячейки выше $p_b$. Записано, чтобы при проверках сеточной сходимости не судить по дебиту.
3. **Тело issue #135 (вариант 1, «минус») повторяет неверную фразу о страже** `test_field_list_covers_known_fields`. Исправлено в плане (§4) и в комментарии аудита к issue; само тело не переписывается — это снимок на дату открытия.

## 10. Связи

- Запись: DEBT-081 в `vault/roadmap/известные баги и технический долг.md`; issue [#135](https://github.com/ArturSalamatin/Oil_Gas/issues/135); тело — `vault/issues/debt-081/01-issue-body.md`.
- [[debt-051 config-numeric-fields-finite]] (#85, влита `d5fd87e`) — тип и конечность числовых полей; правило «bool в числовом поле — опечатка»; образец стража по аннотациям (`_FLOAT_FIELDS`).
- FEAT-035 (#133, влит `86348ed`) — перевод книги пишет целые поля `int`; заметка [[перевод книги в конфиг проверяет только книгу — моменты SCHEDULE в целых мс]].
- [[P8-формат-ввода-json]] — перечень проверок ввода.
- FEAT-037 (#134, влит `5ea30e7` 2026-10-18) — журнал версий; DEBT-081 в него не пишет (§5).

## 11. Файлы проб (`vault/issues/debt-081/probes/`)

| Файл | Что |
|---|---|
| `red_state.py`, `red_state.out.txt` | замер §1.2 A: пример 01, 2 ч, `grid.N` = 150 / true / false / "100" / null / 100.0 / 100.5 / 0 / -1 / NaN → `load_config`, `from_config`, `run`. Пакет и пример — из текущего каталога; аргумент — имя файла вывода (после правки — `green_state.out.txt`). `null` добавлен аудитом 1 |
| `audit1_degassing.py`, `audit1_degassing.out.txt` | замер §1.2 B (аудит 1): пример 03, 2 ч, $p_{wf}$ = 8 МПа, `N` = 150 и `true` на коде до правки. Запуск — из `numerical_solver/` основного каталога; после правки `true` отвергается при загрузке, повторять не нужно |
| `plan_emulate.py`, `plan_emulate.out.txt` | эмуляция плана (переснята аудитом 1 на `30a64f7`). Копия `numerical_solver/` и `vault/knowledge/` из `git archive HEAD` в `probes/_emu/` (удаляется в конце). Семь блоков «До/После» шагов 1–2 берутся из текста этого плана по порядку, каждый «До» найден ровно один раз; самая длинная новая строка кода — 98 символов. Тесты без правки кода → 10 failed, 11 passed (п. 4 шага 1). Весь план → 2421 / 2145 тестов; `test_config.py` + `test_grid.py` + `test_workbook_convert.py` + `test_eq_references.py` — 550 passed; быстрый уровень — 2144 passed, 1 skipped, 150 с; `red_state.py` на копии — контроль 150 прежний, восемь случаев — `ValueError: grid.N должен быть целым ≥ 1, получено …`, NaN — прежний отказ. Запуск — только из основного каталога (`ROOT/numerical_solver/.venv`): в worktree venv нет. Снимок при планировании (`b9454a6`, 5 блоков) перезаписан |
