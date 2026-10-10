---
tags:
  - план
  - инфраструктура
date: 2026-10-10
issue: DEBT-056
github: 87
branch: refactor/debt-056/skin-bhp-range-check
status: реализован
worktree: .worktrees/debt-056; удалён после влития
merged: 8b0715a (2026-10-10)
audit:
  date: 2026-10-10
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# DEBT-056: скин и забойное давление — проверка на физический смысл при загрузке конфига

**Подтип:** инфраструктура (проверка входных данных конфига). Расчётный код не меняется. Прототип `HydroSolverPrototype/` не меняется (решение пользователя).

**База:** `numerical_scheme/implementation` @ `4ab46f5` (DEBT-051 влит `d5fd87e`, BUG-023 влит `1302c02`; план писался на `eee5334`, с тех пор `config.py`, `test_config.py`, P8, `problem_statement.tex` не менялись — номера строк плана действительны). Тестов 1592 (`--collect-only`, аудит 2026-10-10). Параллельно в `.worktrees/bug-022` реализуется BUG-022, он правит те же `config.py` и `test_config.py` — раздел «Порядок влития с BUG-022».

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-056 в `vault/roadmap/известные баги и технический долг.md` (секция `### DEBT-056`, вместе с пунктом «Решения пользователя») и issue #87 (`gh issue view 87 --repo ArturSalamatin/Oil_Gas`).
3. Прочитай `vault/knowledge/decisions/P8-формат-ввода-json.md`, §5 «Валидация» (строки 207–236): его переписывает шаг 5.
4. Worktree и ветка (по контракту `/implement`): `git worktree add .worktrees/debt-056 -b refactor/debt-056/skin-bhp-range-check numerical_scheme/implementation`. Ветка `refactor/debt-056/skin-bhp-range-check` на момент планирования не существует.
5. Все команды pytest — из `.worktrees/debt-056/numerical_solver`; Python — venv основного каталога: `..\..\..\numerical_solver\.venv\Scripts\python` (или `.venv\Scripts\python`, если в worktree создан свой venv). Пакет `gpn_multiphase_solver` pytest берёт из worktree (`tests/conftest.py`); пробы — из текущего каталога (`SOLVER = Path.cwd()`) и печатают путь к коду: проверить, что это worktree.
6. Baseline (шаг 1): `python -m pytest tests/ --collect-only -q` (ожидается 1592), `python -m pytest tests/ -m "not slow" -q` — запомни число passed и время.
7. Начни с шага 1. После каждого шага — тесты шага и регресс по полю «Регресс». Полный прогон — шаг 6.

## Контекст для читателя без контекста

### Что не так сейчас

Конфиг GPN-решателя (`numerical_solver/configs/*.json`, `examples/*/config.json`) читает `load_config` (`numerical_solver/gpn_multiphase_solver/io/config.py`). Три параметра скважины проверяются только на тип, конечность (DEBT-051) и знак `> 0`, но не на физический смысл:

1. **`numerics.skin`** (скин-фактор $s$) уходит в прототип без проверки (`factory.py:433`, `skin=nc.skin`). Прототип считает проводимость забойной грани (`HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/grid.py:20-21`):
   $$T_w = \frac{2\pi k h}{\ln(r_1/r_w) + s},$$
   $r_1$ — центр первой ячейки сетки прототипа (среднее геометрическое граней, `grid.py:9-10`), $\ln(r_1/r_w) = \ln(R_{ext}/r_w)/(2N)$. На сетках проекта это 0.011…0.155 (замер аудита по 32 конфигам: минимум — `deliverables/rs150_for_sergey/config.json`, $N$ = 350, $R_{ext}/r_w$ = 2000; максимум — `configs/val001.json`, $N$ = 20, $R_{ext}/r_w$ = 500; у baseline — 0.031), поэтому обычный скин стимулированной скважины ($s \approx -0.5\ldots-5$, кислотная обработка, ГРП) даёт $T_w < 0$. Замер (`vault/issues/debt-056/probes/skin_range.out.txt`, baseline, 24 ч при $p_{wf}$ = 6 МПа): $s$ = −0.5 и −2 — `RuntimeError: HydroSolver не сошёлся при дроблении шага до dt/512 …` с советом увеличить `max_retries` — ложный след.
2. **Большой положительный скин** ($s$ = 1e3 — почти без притока, 1e6 — без притока) — расчёт идёт молча.
3. **`p_wf` или `min_bhp` $\ge p_0$** ($p_0$ — `initial_conditions.p0`, начальное пластовое давление) — расчёт без притока, молча (замер: `p_wf` = 25 МПа, `min_bhp` = 25 МПа при $p_0$ = 20 МПа). Причина — ограничение «только добыча» (`problem_statement.tex`, `eq:bc_pwf_shutin`, строка 697; FEAT-020): при $p_{wf} \ge p$ в ячейке забоя скважина закрыта. При добыче давление в пласте не выше $p_0$ (контур питания держит $p_0$, источников нет), поэтому такой интервал целиком без притока.

### Решения пользователя (2026-10-10)

- Прототип не трогать; проверка — в оболочке, на уровне чтения конфига (`io/config.py`).
- **Любой $s < 0$ → `ValueError`.** Отрицательный скин в проекте не предусмотрен. В сообщении — обход: `geometry.r_well` = $r_w e^{-s}$ (приведённый радиус скважины: при $s = 0$ он даёт тот же установившийся однофазный приток, что скважина $r_w$ со скином $s$, — $p - p_{wf} = \frac{q\mu}{2\pi kh}\ln\frac{r}{r_w e^{-s}}$; при разгазировании у забоя равенство приближённое), `numerics.skin` = 0, с оговоркой, что температура забоя тогда относится к радиусу $r_w e^{-s}$. Отдельную FEAT на эквивалентный радиус не регистрировать.
- **$s > 50$ → предупреждение** в журнале, расчёт идёт.
- **`p_wf` / `min_bhp` $\ge p_0$ → предупреждение для любого интервала истории**, расчёт идёт.

Выбор «любой $s < 0$», а не «$s \le -\ln(r_1/r_w)$» снимает зависимость проверки от формулы центра ячейки прототипа (P8 §6 собирается её менять) — сетка проверке не нужна.

### Решения, принятые при планировании (вынести на аудит)

- **`min_bhp` $\ge p_0$ при `q_oil = 0` — без предупреждения.** `q_oil = 0` — намеренный останов (так заданы остановы примеров 16, 17: `control = "rate"`, `q_oil = 0`, `min_bhp` = 101325 Па); при нулевом дебите `min_bhp` на итог не влияет — предупреждать не о чем.
- **Одно предупреждение на объект `time.history` JSON, не на развёрнутый интервал**, с местом `history[i]` — как сообщения об ошибках интервалов (FEAT-018: «номер в сообщении — номер объекта в JSON, то есть место, которое пользователь правит»). Блок `{duration: 15 сут, dt_out: 1 сут}` даёт одно предупреждение, а не 15.
- **Предупреждения — после всех отказов `load_config`.** Оба предупреждения — отдельные функции (`_warn_large_skin`, `_warn_well_shut`) в конце модуля, `load_config` вызывает их после `_validate`. Отказ при $s < 0$ — внутри `_validate`, после проверок породы. Так конфиг с ошибкой в любом поле — в том числе в полях, которые `_validate` проверит в будущем (BUG-022 добавляет `newton_cell_tol` в конец `_validate`), — не выдаёт сначала предупреждение, а следом отказ (тот же принцип — `config.py:420-424`, порядок конечности и знака $L$). Исправлено аудитом 1: в первой версии предупреждение о скине стояло в конце `_validate` — ровно там, куда BUG-022 вставляет свой блок (конфликт слияния и предупреждение до отказа по `newton_cell_tol`).
- **Сообщение о скине > 50 даёт долю притока** установившегося однофазного режима $q(s)/q(0) = \ln(R_{ext}/r_w)/(\ln(R_{ext}/r_w) + s)$ — у baseline при $s = 50$ это 11.1 %. На сетке прототипа формула точная для однофазного стационара: сопротивления граней складываются в $\ln(r_1/r_w) + \sum \ln(r_{j+1}/r_j) + \ln(R_{ext}/r_N) = \ln(R_{ext}/r_w)$. Замер её приближённо подтверждает: при $s = 50$ минимум $p$ 18.46 МПа против 6.095 при $s = 0$, перепад в пласте 1.54 / 13.9 = 11 % (перепад пропорционален дебиту; расчёт 24 ч — не стационар, при $s = 0$ у забоя есть газ).
- **`problem_statement.tex`**: скин в постановке не упоминается — формула $\mathcal{T}_{1/2}$ (строки 1701-1709, без номера) записана без $s$, а код его учитывает. Добавить абзац о скине и ограничении $s \ge 0$ (шаг 5). Если аудит сочтёт это лишним — шаг 5.2 вычёркивается без последствий для кода.

### Порядок влития с BUG-022 (добавлено аудитом 1)

BUG-022 (#82, ветка `fix/bug-022/newton-cell-relative-tolerance`, worktree `.worktrees/bug-022`) на момент аудита в реализации. По его плану (`vault/plans/bug-022 newton-cell-relative-tolerance.md`, шаги 2, 4, 6) он правит:
- `io/config.py`: докстринг `NumericsConfig` (`:139`), новое поле `newton_cell_tol` после `max_retries: int = 9` (`:160`), блок проверки в `_validate` **после блока `max_retries`** (конец функции);
- `tests/test_config.py`: строку шапки модуля **после строки DEBT-049** (`:8`) и класс `TestNewtonCellTolValidation` после `TestMaxRetriesValidation` (`:463-519`) — уже сделано в его worktree;
- P8 §4 (`:181-203`, `:336`), `problem_statement.tex:2087-2109`.

Этот план ставит свои правки так, чтобы общих строк не было:
| Правка DEBT-056 | Место | Почему не пересекается |
|---|---|---|
| строка шапки `test_config.py` | после строки `- История: несколько интервалов, control type, p_wf.` (`:10`) | BUG-022 вставляет после `:8`, между — строка `:9` |
| класс `TestValidationWell` | перед блоком `# E. Мульти-интервальная история` (`:768`) | BUG-022 — после `:519` |
| комментарий поля `skin` | та же строка `:142`, без новых строк | BUG-022 меняет `:139` и вставляет после `:160`; `:140-141` между ними не меняются |
| отказ $s < 0$ | в `_validate` после проверки `permeability` (`:396-397`) | BUG-022 — в конце `_validate` |
| `_warn_large_skin`, `_warn_well_shut` | конец модуля, после `_validate_interval` | BUG-022 там не правит |
| P8 §5, `problem_statement.tex:1709` | §5 начинается с `:207`; `:1709` | BUG-022 — §4 и `:2087-2109` |

Ожидание: слияние без конфликтов в любом порядке. Если `/merge` всё же покажет конфликт в этих файлах — сохранить обе стороны (правки независимы). Если BUG-022 влит раньше старта реализации DEBT-056 — номера строк сдвинутся: якоря правок — по тексту (блоки «До:»), а не по номерам. После влития обеих задач `test_no_warning_before_error` остаётся верным: предупреждения вызываются после всего `_validate`, включая блок `newton_cell_tol`.

### Кто сейчас проверяет входные данные (по коду, `eee5334`)

P8 §5 пишет «валидация данных для гидро — ответственность прототипа» — по коду это не так:

| Этап | Где | Что |
|---|---|---|
| `load_config` | `io/config.py`: `_check_numeric_fields`, `_require_finite_number` (344-367) | тип и конечность всех чисел (DEBT-051) |
| | `_expand_history` (215-270), `_validate_interval` (479-514) | формы `time.history` (FEAT-018); `control`, `p_wf > 0`, `q_oil ≥ 0`, `min_bhp > 0`, неиспользуемые поля (DEBT-008) |
| | `_validate` (370-476) | геометрия, сетка, порода, тепловые параметры, начальные условия, `dt_integration`, `max_retries` |
| `from_config` | `factory.py`: `_read_numeric_csv` (510), `_check_pvto_branches` (171), `_check_gas_pvt_table` (232), `_check_relperm_table` (255) | CSV-таблицы: числа, пределы, монотонность, ветви PVTO (DEBT-042, DEBT-044, DEBT-038) |
| | `_check_rs0_in_table` (158), `_check_undersaturated_start` (281); `_warn_negative_compressibility` (301), `_warn_initial_table_range` (346) | начальное состояние против PVT (BUG-017); предупреждения $c < 0$ (BUG-019) и выход за таблицы (BUG-017) |
| сетка GPN | `grid/log_radial.py:39-48` | повтор проверок геометрии |
| прототип | `radial_blackoil/grid.py:7-8`, `pvt.py:32,46`, `relperm.py:5-6`, `blackoil.py:90-91,110` | повтор геометрии; монотонность таблиц; режимы якобиана и решателя СЛАУ; $q \ge 0$ |

Скин не проверяет никто. Новые проверки встают в `_validate` — туда, где уже проверяются скалярные поля.

## Целевое состояние

- `io/config.py`:
  - `_validate`, после проверок породы: $s < 0$ → `ValueError` «`numerics.skin = … < 0: …`» с обходом через `geometry.r_well`.
  - Новая функция `_warn_large_skin(cfg)`: $s > 50$ → `user_log.warning` с долей притока.
  - `_expand_history` возвращает ещё список пар `(место в JSON, интервал-образец)` — по одной на объект `time.history`.
  - Новая функция `_warn_well_shut(blocks, p0)`: `p_wf` $\ge p_0$ (`control = "pressure"`) или `min_bhp` $\ge p_0$ при `q_oil > 0` (`control = "rate"`) → `user_log.warning` «`history[i]: …`».
  - `load_config` вызывает `_warn_large_skin` и `_warn_well_shut` после `_validate`.
- `tests/test_config.py`: класс `TestValidationWell` (22 теста), 1592 → 1614.
- P8 §5 переписан по коду (таблица выше + пункт «Скважина»).
- `problem_statement.tex`: абзац о скине у $\mathcal{T}_{1/2}$.
- Две заметки `knowledge/debugging/` — «не закрыто» → закрыто DEBT-056.

Интерфейсы: `load_config(path) -> SimulationConfig` не меняется. `_expand_history`, `_validate` — внутренние (`_`), вызываются только из `config.py` (grep: других вызовов в `numerical_solver/` нет).

## Варианты решения

### Вариант 1 (выбран). Отказ $s < 0$ — в `_validate`; оба предупреждения — отдельными функциями после `_validate`, о забое — по парам `(where, образец)` из `_expand_history`

- **Изменения:** `io/config.py` (~+85 строк), `tests/test_config.py` (~+170), документы.
- **Промежуточные состояния:** шаг 3 (скин) и шаг 4 (забой) независимы по коду (шаг 4 правит строку вызова, добавленную шагом 3), после каждого — зелёный быстрый уровень.
- ➕ Номер объекта JSON в предупреждении; предупреждения после всех отказов `_validate`, в том числе будущих; `_validate` не меняет сигнатуру; правки не пересекаются со строками BUG-022.
- ➖ `_expand_history` меняет тип результата (кортеж) — внутренняя функция, один вызов.
- **Риск:** нет вызовов `_expand_history` вне `config.py` (проверено grep).

### Вариант 2. Предупреждение о забое внутри `_expand_history` (передать туда `p0`)

- ➕ Не меняет тип результата `_expand_history`.
- ➖ `p0` на этом этапе ещё не проверен (`_check_numeric_fields` для `initial_conditions` — в `_validate`, позже): `p0 = "abc"` дал бы `TypeError` при сравнении `h.p_wf >= p0` без имени поля, `p0 = NaN` — молчание. Нужна защита. Предупреждение уходило бы до отказов `_validate` по другим полям.

### Вариант 3. Предупреждение о забое в `_validate` по развёрнутому списку `cfg.time.history`

- ➕ Без изменений `_expand_history`.
- ➖ Номер объекта JSON потерян (`config.py:464-466`); блок из 15 интервалов — 15 предупреждений или группировка подряд идущих по времени (сложнее, сообщение — по времени, а не по месту правки).

**Выбор: вариант 1** — минимальный риск, сообщения указывают на место правки, порядок «отказы → предупреждения».

## Подводные камни (чеклист)

- ✅ **Все call sites найдены.** `_expand_history` — один вызов (`config.py:303`); `_validate` — один (`config.py:334`). Grep `_expand_history|_validate\(` по `numerical_solver/**/*.py` — только `config.py`.
- ✅ **Зависимости пакетов.** `numpy` уже зависимость; в `config.py` добавляется `import numpy as np` (CLAUDE.md: `np.log`, `np.exp`, не `math`). Циклов нет: `config.py` по-прежнему импортирует только `..log`.
- ✅ **Обратная совместимость API.** `load_config` и dataclass-секции не меняются.
- ✅ **Состояние при ошибке.** `ValueError` до возврата `config` — объект не создаётся наружу.
- ⚠️ **Существующие тесты.** Отказ при $s < 0$ и предупреждения могли бы задеть тесты, которые грузят конфиги с такими значениями или требуют отсутствия предупреждений. Проверено:
  - `skin` в тестах: `test_config.py:198-199` (значение по умолчанию 0), `test_config.py:681,701` (`numerics.skin` в списках DEBT-051: NaN, inf, `False` — отказ по типу/конечности раньше новой проверки), `test_prototype_adapter.py:101`, `test_prototype_well_branch.py:64` (прототип напрямую, без `load_config`).
  - Тесты «нет предупреждений»: `test_config.py:592,624,650` (`_minimal_raw`: `p_wf` = 10 МПа < $p_0$ = 20 МПа, скин по умолчанию 0 — не задеты), `test_factory_prototype.py:419`, `test_factory_standing_hydro.py:222` (`load_config` вне `caplog`), `test_pvt_consistency.py:142-150` (фильтр по префиксу сообщения).
  - Тесты, задающие `p_wf` ≥ $p_0$ программно (`cfg.time.history = [...]` после загрузки: `test_examples.py:1796`, `test_rate_control.py:87`), `load_config` не проходят — предупреждений не будет.
- ✅ **Конфиги проекта.** Проба `vault/issues/debt-056/probes/configs_scan.py` на `eee5334` (`configs_scan_base.out.txt`): 32 конфига (30 в git + 2 в неотслеживаемом `numerical_solver/deliverables/`), ни одного с `skin` ≠ 0, `p_wf`/`min_bhp` $\ge p_0$, отказом или предупреждением `load_config`. Остановы примеров 16, 17 — `q_oil = 0`.
- ✅ **Docstrings/`\eqref{}`.** Новые функции — одна строка + ссылка; `eq:bc_pwf_shutin` существует (`problem_statement.tex:697`).
- ✅ **Configs.** Имена параметров не меняются.
- ⚠️ **Связь с другими задачами.** **BUG-022 в реализации и правит те же файлы** — раздел «Порядок влития с BUG-022»: правки разведены по строкам, конфликтов не ждём. BUG-023 влит (`1302c02`), трогал только `test_energy_matrix_examples.py`. DEBT-048 (адаптер, прототип), VAL-005 (новый пример, `prototype_input.py`) — `config.py` и `test_config.py` по их планам не трогают (сверить при `/merge`). DEBT-051 влит — его проверка конечности идёт первой, новая — после.
- ✅ **Производительность.** Несколько сравнений при загрузке.
- ✅ **Прототип.** Не меняется — тесты прототипа и регрессия против эталона не нужны.
- ⚠️ **Конфиг, собранный в коде без `load_config`**, проверки не получает (как и все проверки DEBT-047/049/051). Пользовательский путь — JSON → `load_config`; прототип с $s < 0$ по-прежнему упадёт через dt/512. Решение пользователя — прототип не трогать; записано в P8 §5 (шаг 5).
- ⚠️ **Целое в JSON.** `"skin": -1` — `int`; `np.exp(-s)`, сравнения и формат `{s}` работают с `int`.

## Шаги

### Шаг 1: Baseline

**Цель:** зафиксировать число тестов, быстрый уровень и состояние конфигов до правки.

**Файлы:** —

**Что сделать** (из `.worktrees/debt-056/numerical_solver`):
1. `python -m pytest tests/ --collect-only -q` → ожидается `1592 tests collected`.
2. `python -m pytest tests/ -m "not slow" -q` → запомнить число passed и время.
3. `$env:PYTHONIOENCODING = "utf-8"; python ..\vault\issues\debt-056\probes\configs_scan.py` — проба попадает в worktree с коммитом материалов задачи, который `/implement` делает в базу до ветвления; если её там нет — путь к основному каталогу `..\..\..\vault\issues\debt-056\probes\configs_scan.py`. Проверяемый код проба берёт из текущего каталога в обоих случаях. Первая строка вывода — путь к `config.py`, должен быть в `.worktrees\debt-056`. Ожидается `конфигов: 30, с замечаниями: 0` (больше 30 — если с аудита влиты задачи с новыми конфигами, например VAL-005; в worktree нет неотслеживаемого `numerical_solver/deliverables/` — 30, а не 32, как в `configs_scan_base.out.txt` основного каталога).

**Проверка:** числа записаны.

**Оценка:** ~5 минут.

### Шаг 2: Красные тесты `TestValidationWell`

**Цель:** тесты на отказ при $s < 0$, предупреждения о скине > 50 и о `p_wf`/`min_bhp` $\ge p_0$ — до реализации.

**Файлы:** `numerical_solver/tests/test_config.py`

**Контекст:** образец — `TestValidationThermal` (`test_config.py:521-650`: отказ с именем параметра, предупреждение через `caplog`), вспомогательные `_write_json` (250), `_minimal_raw` (257: `p0` = 20 МПа, `p_wf` = 10 МПа, `r_well` = 0.1, `R_ext` = 50, без секции `numerics`). Журнал — логгер `"gpn_multiphase_solver"` (`gpn_multiphase_solver/log.py:33`, `user_log`).

**Что сделать:**
1. Шапка модуля (строки 3-12) — добавить пункт **после строки `- История: несколько интервалов, control type, p_wf.`** (`:10`), а не после строки DEBT-049 (`:8`): туда же вставляет свою строку BUG-022 — раздел «Порядок влития с BUG-022»:
   ```
   - Скважина: skin ≥ 0 (отказ с обходом через r_well), предупреждения при skin > 50
     и при p_wf / min_bhp ≥ p0 в объекте истории (DEBT-056).
   ```
2. После класса `TestValidationNumbers` (заканчивается строкой 765, перед блоком `# ═══ E. Мульти-интервальная история` на строке 768) вставить:

```python
# Скважина: скин и забойное давление против p0 (DEBT-056). Замер до DEBT-056
# (vault/issues/debt-056/probes/skin_range.out.txt, baseline, 24 ч при
# p_wf = 6 МПа): s = −0.5 и −2 — отказ после дробления шага до dt/512 с советом
# увеличить max_retries (проводимость забойной грани прототипа
# 2πkh/(ln(r_1/r_w) + s) < 0, ln(r_1/r_w) = 0.031); s = 1e6, p_wf = 25 МПа,
# min_bhp = 25 МПа при p0 = 20 МПа — расчёт без притока и без сообщения.
def _warning_messages(caplog):
    """Тексты записей журнала уровня WARNING и выше."""
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def _history_raw(second):
    """Минимальный конфиг с двумя объектами истории: добыча при 10 МПа и second."""
    raw = _minimal_raw()
    raw["time"]["history"] = [
        {"dt": 86400, "control": "pressure", "p_wf": 10e6}, second]
    return raw


class TestValidationWell:
    """Скин ≥ 0; предупреждения при skin > 50 и при p_wf, min_bhp ≥ p0 (DEBT-056)."""

    # −0.01 — внутри окна T_w > 0 (у _minimal_raw ln(r_1/r_w) = ln 500 / 20 = 0.31),
    # но отрицательный скин в проекте не предусмотрен (решение пользователя)
    @pytest.mark.parametrize("skin", [-0.01, -0.5, -2.0],
                             ids=["small", "acid", "fracture"])
    def test_negative_skin_rejected(self, tmp_path, skin):
        """Любой s < 0 → ValueError с именем поля."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with pytest.raises(ValueError, match=r"numerics\.skin = .* < 0"):
            load_config(_write_json(tmp_path, raw))

    def test_negative_skin_message_gives_equivalent_radius(self, tmp_path):
        """Обход в сообщении: r_well = r_w·e^(−s) = 0.1·e^0.5 = 0.1649 м, оговорка о температуре."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": -0.5}
        with pytest.raises(ValueError) as exc:
            load_config(_write_json(tmp_path, raw))
        text = str(exc.value)
        assert "geometry.r_well" in text and "0.1649" in text
        assert "температура забоя" in text

    # −1e300 — конечное (проходит DEBT-051), но r_w·e^(−s) переполнил бы np.exp:
    # сравнение с R_ext — в логарифмах, RuntimeWarning превращён здесь в ошибку
    @pytest.mark.filterwarnings("error::RuntimeWarning")
    @pytest.mark.parametrize("skin", [-7.0, -1e300], ids=["minus7", "minus1e300"])
    def test_equivalent_radius_beyond_drainage(self, tmp_path, skin):
        """s = −7: r_w·e^7 = 109.7 м ≥ R_ext = 50 м — обход неприменим, сообщение так и говорит."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with pytest.raises(ValueError, match="неприменим"):
            load_config(_write_json(tmp_path, raw))

    # 50 — граница: предупреждение строго при s > 50 (решение пользователя)
    @pytest.mark.parametrize("skin", [0.0, 5.0, 50.0],
                             ids=["zero", "damaged", "threshold"])
    def test_skin_up_to_threshold_silent(self, tmp_path, caplog, skin):
        """0 ≤ s ≤ 50 — без отказа и без предупреждения."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == skin
        assert _warning_messages(caplog) == []

    @pytest.mark.parametrize("skin", [50.5, 1e3, 1e6], ids=["above", "1e3", "1e6"])
    def test_large_skin_warns(self, tmp_path, caplog, skin):
        """s > 50 — предупреждение с именем поля; расчёт допускается."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == skin
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1 and "numerics.skin" in msgs[0]

    def test_large_skin_warning_gives_inflow_ratio(self, tmp_path, caplog):
        """s = 1000, R_ext/r_w = 500: приток ln 500 / (ln 500 + 1000) = 0.6 % от притока без скина."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": 1000.0}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        assert "0.6%" in _warning_messages(caplog)[0]

    @pytest.mark.parametrize("p_wf", [20e6, 25e6], ids=["equal_p0", "above_p0"])
    def test_pwf_not_below_p0_warns(self, tmp_path, caplog, p_wf):
        """p_wf ≥ p0 = 20 МПа во втором объекте истории — одно предупреждение с history[1]."""
        # При добыче p ≤ p0 во всём пласте: интервал целиком без притока (eq:bc_pwf_shutin)
        raw = _history_raw({"dt": 86400, "control": "pressure", "p_wf": p_wf})
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1
        assert "history[1]" in msgs[0] and "p_wf" in msgs[0]

    def test_min_bhp_not_below_p0_warns(self, tmp_path, caplog):
        """control='rate', q_oil > 0, min_bhp = 25 МПа > p0 — одно предупреждение с history[1]."""
        raw = _history_raw({"dt": 86400, "control": "rate",
                            "q_oil": 5.787e-4, "min_bhp": 25e6})
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1
        assert "history[1]" in msgs[0] and "min_bhp" in msgs[0]

    # q_oil = 0 — намеренный останов (примеры 16, 17: min_bhp = 101325 Па);
    # min_bhp при нулевом дебите на итог не влияет — предупреждать не о чем
    @pytest.mark.parametrize("min_bhp", [101325.0, 25e6], ids=["atm", "above_p0"])
    def test_shut_in_by_rate_silent(self, tmp_path, caplog, min_bhp):
        """control='rate', q_oil = 0 — без предупреждения при любом min_bhp."""
        raw = _history_raw({"dt": 86400, "control": "rate",
                            "q_oil": 0.0, "min_bhp": min_bhp})
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        assert _warning_messages(caplog) == []

    def test_block_warns_once(self, tmp_path, caplog):
        """Блок {duration, dt_out} с p_wf > p0 разворачивается в 24 интервала, предупреждение — одно."""
        # Одно на объект JSON: номер объекта — место правки (как у ошибок, FEAT-018)
        raw = _minimal_raw()
        raw["time"]["history"] = [{"duration": 86400, "dt_out": 3600,
                                   "control": "pressure", "p_wf": 25e6}]
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert len(cfg.time.history) == 24
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1 and "history[0]" in msgs[0]

    def test_production_silent(self, tmp_path, caplog):
        """Штатный конфиг: s = 0, p_wf = 10 МПа < p0 — предупреждений нет."""
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, _minimal_raw()))
        assert _warning_messages(caplog) == []

    # Предупреждения — после всех отказов: конфиг с ошибкой в другом поле не
    # выдаёт сначала предупреждение, а следом отказ (два сообщения о разном)
    @pytest.mark.parametrize("change, error", [
        ({"history_p_wf": 25e6, "porosity": 0.0}, "porosity"),
        ({"skin": 1e3, "max_retries": 25}, "max_retries"),
    ], ids=["pwf_and_porosity", "skin_and_max_retries"])
    def test_no_warning_before_error(self, tmp_path, caplog, change, error):
        """Ошибка в другом поле → ValueError без предупреждений о скине и забое."""
        raw = _minimal_raw()
        if "history_p_wf" in change:
            raw["time"]["history"][0]["p_wf"] = change["history_p_wf"]
            raw["rock"]["porosity"] = change["porosity"]
        else:
            raw["numerics"] = {"skin": change["skin"],
                               "max_retries": change["max_retries"]}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            with pytest.raises(ValueError, match=error):
                load_config(_write_json(tmp_path, raw))
        assert _warning_messages(caplog) == []
```

3. Прогнать `python -m pytest tests/test_config.py -q -k TestValidationWell`.

**Ожидание (красное):** 22 теста; падают 14 — `test_negative_skin_rejected` (3), `test_negative_skin_message_gives_equivalent_radius`, `test_equivalent_radius_beyond_drainage` (2), `test_large_skin_warns` (3), `test_large_skin_warning_gives_inflow_ratio` (`IndexError`: предупреждений нет), `test_pwf_not_below_p0_warns` (2), `test_min_bhp_not_below_p0_warns`, `test_block_warns_once` — итого 3+1+2+3+1+2+1+1 = 14. Проходят 8 (замер аудита 1 на копии: 13 failed, 8 passed — до добавления случая −1e300): `test_skin_up_to_threshold_silent` (3), `test_shut_in_by_rate_silent` (2), `test_production_silent`, `test_no_warning_before_error` (2). Записать фактические числа в отчёт (`05-comment-done.md`).

**Проверка после этого шага:**
- Регресс: быстрый — остальные тесты не тронуты; ожидание — baseline + 8 passed, 14 failed (все 14 — новые).

**Подводные камни:** формат доли `{ratio:.1%}` даёт `0.6%` (без пробела) — тест ищет `"0.6%"`; при смене формата в шаге 3 поправить тест.

**Зависимости:** требует шаг 1; блокирует шаги 3, 4.

**Оценка:** ~170 строк, ~20 минут.

### Шаг 3: Скин — отказ при $s < 0$ в `_validate`, предупреждение при $s > 50$ после `_validate`

**Цель:** `numerics.skin < 0` → `ValueError` с обходом; `> 50` → предупреждение.

**Файлы:** `numerical_solver/gpn_multiphase_solver/io/config.py`

**Контекст:** `_validate` (строки 370-476) начинается проверкой типа и конечности всех чисел (DEBT-051) — к новой проверке `skin` уже конечное число. Геометрия ($r_w > 0$, $R_{ext} > r_w$) проверена в начале `_validate` (383-388) — `np.log(R_ext / r_well)` и `np.exp` безопасны. Отказ встаёт в `_validate` сразу после проверок породы (`:393-397`), а не в конец функции: туда BUG-022 вставляет свой блок (раздел «Порядок влития с BUG-022»). Предупреждение — отдельной функцией, которую `load_config` зовёт после `_validate`: так оно не уйдёт в журнал перед отказом по любому полю, в том числе по полям, которые в `_validate` добавят позже.

**Что сделать:**
1. Импорт: после строки 12 (`from typing import Optional`) — пустая строка и `import numpy as np` (группа сторонних библиотек), затем `from ..log import user_log`:
   До:
   ```python
   from pathlib import Path
   from typing import Optional

   from ..log import user_log
   ```
   После:
   ```python
   from pathlib import Path
   from typing import Optional

   import numpy as np

   from ..log import user_log
   ```
2. Комментарий поля `NumericsConfig.skin` (строка 142) — правка в той же строке, без новых строк: рядом (`:139`, `:160`) правит BUG-022.
   До:
   ```python
       skin: float = 0.0                      # скин-фактор
   ```
   После:
   ```python
       skin: float = 0.0                      # скин-фактор: ≥ 0, > 50 — предупреждение (DEBT-056)
   ```
3. Константа порога — после `_NUMERIC_SECTIONS` (строки 338-341), с пустой строкой перед ней:
   ```python
   # Порог предупреждения о скине (решение пользователя, DEBT-056). У baseline
   # (R_ext/r_w = 500) при s = 50 установившийся однофазный приток — 11 %
   # от притока без скина при той же депрессии.
   _SKIN_WARN = 50.0
   ```
4. Отказ при $s < 0$ — в `_validate` после проверки `permeability` (`:396-397`), перед комментарием тепловых параметров (`:399`):
   До:
   ```python
       if r.permeability <= 0:
           raise ValueError(f"permeability должна быть > 0, получено {r.permeability}")

       # Тепловые параметры (DEBT-047, P8 §5). Ошибка в них не роняет расчёт,
   ```
   После:
   ```python
       if r.permeability <= 0:
           raise ValueError(f"permeability должна быть > 0, получено {r.permeability}")

       # ── Скважина: скин-фактор (DEBT-056, P8 §5) ──
       # Проводимость забойной грани прототипа (radial_blackoil/grid.py,
       # well_transmissibility_m3): T_w = 2πkh / (ln(r_1/r_w) + s), r_1 — центр
       # первой ячейки; ln(r_1/r_w) = ln(R_ext/r_w)/(2N), на сетках проекта
       # 0.01…0.16. Скин стимулированной скважины (s ≈ −0.5…−5) даёт T_w < 0;
       # замер до DEBT-056 (vault/issues/debt-056/probes/skin_range.out.txt):
       # s = −0.5 и −2 — отказ после дробления шага до dt/512 с советом увеличить
       # max_retries. Отрицательный скин в проекте не предусмотрен (решение
       # пользователя) — отказ при любом s < 0, сетка проверке не нужна. Обход —
       # приведённый радиус скважины r_w·e^(−s): при s = 0 установившийся
       # однофазный приток тот же, p − p_wf = qμ/(2πkh)·ln(r/(r_w·e^(−s))).
       s = cfg.numerics.skin
       if s < 0:
           # r_w·e^(−s) < R_ext сравнивается в логарифмах: при s = −1e300 (конечное,
           # проходит DEBT-051) np.exp(−s) переполняется с RuntimeWarning
           ln_re_rw = np.log(g.R_ext / g.r_well)
           if -s < ln_re_rw:
               r_eq = g.r_well * np.exp(-s)
               hint = (f"Обход: geometry.r_well = r_w·e^(−s) = {r_eq:.4g} м и "
                       f"numerics.skin = 0 (приведённый радиус скважины: тот же "
                       f"установившийся однофазный приток); температура забоя тогда "
                       f"относится к r = {r_eq:.4g} м, а не к r_w = {g.r_well} м.")
           else:
               hint = (f"Приведённый радиус r_w·e^(−s) не меньше R_ext = {g.R_ext} м "
                       f"(s ≤ −ln(R_ext/r_w) = {-ln_re_rw:.3g}) — обход через "
                       f"geometry.r_well неприменим.")
           raise ValueError(
               f"numerics.skin = {s} < 0: отрицательный скин (стимулированная "
               f"скважина) в проекте не предусмотрен — проводимость забойной грани "
               f"2πkh/(ln(r_1/r_w) + s) на сетках проекта неположительна уже при "
               f"s ≈ −0.01…−0.16. {hint}")

       # Тепловые параметры (DEBT-047, P8 §5). Ошибка в них не роняет расчёт,
   ```
   Переменная `g` определена в начале `_validate` (строка 382: `g = cfg.geometry`) и не переприсваивается — блок пользуется ею.
5. Новая функция — в конец модуля, после `_validate_interval` (через две пустые строки):
   ```python
   def _warn_large_skin(cfg: SimulationConfig) -> None:
       """Предупреждение при скине выше _SKIN_WARN (DEBT-056)."""
       # s > 50 — предупреждение, не отказ (решение пользователя, DEBT-056).
       # Доля установившегося однофазного притока при той же депрессии:
       # q(s)/q(0) = ln(R_ext/r_w) / (ln(R_ext/r_w) + s); на сетке прототипа
       # сопротивления граней складываются ровно в ln(R_ext/r_w). Замер до
       # DEBT-056 (vault/issues/debt-056/probes/skin_range.out.txt): s = 1e3 —
       # минимум p 19.91 МПа при p0 = 20, s = 1e6 — притока нет, расчёт молча идёт.
       s = cfg.numerics.skin
       if s > _SKIN_WARN:
           g = cfg.geometry
           ln_re_rw = np.log(g.R_ext / g.r_well)
           ratio = ln_re_rw / (ln_re_rw + s)
           user_log.warning(
               f"numerics.skin = {s} > {_SKIN_WARN:g}: установившийся однофазный приток "
               f"при той же депрессии — {ratio:.1%} от притока без скина "
               f"(ln(R_ext/r_w) / (ln(R_ext/r_w) + s), ln(R_ext/r_w) = {ln_re_rw:.3g}). "
               f"Проверьте значение.")
   ```
6. `load_config`, строки 334-335 — вызов после `_validate`:
   До:
   ```python
       _validate(config)
       return config
   ```
   После:
   ```python
       _validate(config)
       # Предупреждения — после всех проверок _validate: конфиг с ошибкой в любом
       # поле не выдаёт предупреждение перед отказом (DEBT-056)
       _warn_large_skin(config)
       return config
   ```

**Проверка после этого шага:**
- `python -m pytest tests/test_config.py -q -k TestValidationWell` — 18 passed, 4 failed; упасть должны только тесты забоя (шаг 4): `test_pwf_not_below_p0_warns` (2), `test_min_bhp_not_below_p0_warns`, `test_block_warns_once`.
- Регресс: быстрый — ожидание baseline + 18 passed, 4 failed (те же четыре).

**Подводные камни:**
- `test_config.py::TestValidationNumbers::test_nonfinite_rejected[numerics.skin-…]` и `test_non_number_rejected[skin_false]` — отказ по типу/конечности приходит раньше (`_check_numeric_fields` в начале `_validate`), сообщения «должно быть конечным», «должно быть числом» не меняются.
- `{ratio:.1%}` — `numpy.float64` форматируется как `float`.
- `test_no_warning_before_error[skin_and_max_retries]`: `max_retries` = 25 → `ValueError` в `_validate`, до `_warn_large_skin` не доходит.

**Зависимости:** требует шаг 2; блокирует шаг 4 (шаг 4 правит строку вызова `_warn_large_skin`, добавленную здесь).

**Оценка:** ~55 строк, ~15 минут.

### Шаг 4: Предупреждение о `p_wf` / `min_bhp` $\ge p_0$ в любом объекте истории

**Цель:** одно предупреждение `history[i]: …` на объект `time.history`, где скважина заведомо закрыта; после всех отказов `load_config`.

**Файлы:** `numerical_solver/gpn_multiphase_solver/io/config.py`

**Контекст:** `_expand_history` (215-270) разворачивает краткие формы `time.history` и проверяет каждый объект JSON один раз (`_validate_interval(proto, where)`, строка 265), где `where = f"history[{i}]"` — номер объекта в JSON. После разворачивания номер теряется (`config.py:464-466`). $p_0$ к этому моменту не проверен (`_check_numeric_fields` для `initial_conditions` — в `_validate`). Поэтому `_expand_history` возвращает ещё пары `(where, proto)`, а предупреждения выдаёт `_warn_well_shut` после `_validate`.

Почему $p_{wf} \ge p_0$ закрывает скважину на весь интервал: гидродинамика изотермическая (PVT Стендинга строится при $T_0$, `pvt/standing.py:55`; табличная от $T$ не зависит), уравнение баланса массы — параболическое с монотонным членом накопления, скважина — только сток («только добыча», FEAT-020), на контуре $p = p_0$. По принципу максимума $p \le p_0$ во всём пласте в любой момент — значит, при $p_{wf} \ge p_0$ перепад к забою неотрицателен и притока нет (`eq:bc_pwf_shutin`). При `control = "rate"` прототип при $p_{\text{ячейки}} \le$ `min_bhp` закрывает скважину (`blackoil.py:129-130`) — то же при `min_bhp` $\ge p_0$.

**Что сделать:**
1. `_expand_history` — сигнатура, docstring, сбор пар, возврат:
   До:
   ```python
   def _expand_history(raw_history: list[dict]) -> list[HistoryInterval]:
       """Развернуть краткие формы time.history в список интервалов (FEAT-018)."""
       intervals: list[HistoryInterval] = []
       for i, raw_entry in enumerate(raw_history):
   ```
   После:
   ```python
   def _expand_history(raw_history: list[dict]
                       ) -> tuple[list[HistoryInterval], list[tuple[str, HistoryInterval]]]:
       """Развернуть time.history (FEAT-018); второй результат — пары (место в JSON, образец)."""
       intervals: list[HistoryInterval] = []
       # Образец интервала на каждый объект JSON с его местом history[i]:
       # по ним _warn_well_shut предупреждает один раз на объект (DEBT-056)
       blocks: list[tuple[str, HistoryInterval]] = []
       for i, raw_entry in enumerate(raw_history):
   ```
   До (строки 265-270):
   ```python
           _validate_interval(proto, where)
           # replace() — отдельный объект на каждый интервал: общий объект
           # в n позициях списка менял бы весь блок при правке одного
           # интервала (тесты правят history[k] после загрузки).
           intervals.extend(replace(proto) for _ in range(n))
       return intervals
   ```
   После:
   ```python
           _validate_interval(proto, where)
           blocks.append((where, proto))
           # replace() — отдельный объект на каждый интервал: общий объект
           # в n позициях списка менял бы весь блок при правке одного
           # интервала (тесты правят history[k] после загрузки).
           intervals.extend(replace(proto) for _ in range(n))
       return intervals, blocks
   ```
   (`proto` в `intervals` не попадает — там копии `replace(proto)`; правка `history[k]` тестами образец не меняет.)
2. `load_config`, строка 303:
   До:
   ```python
       history = _expand_history(time_raw.pop("history"))
   ```
   После:
   ```python
       history, history_blocks = _expand_history(time_raw.pop("history"))
   ```
3. `load_config`, конец — вызов после `_warn_large_skin` (состояние после шага 3):
   До:
   ```python
       _warn_large_skin(config)
       return config
   ```
   После:
   ```python
       _warn_large_skin(config)
       # p0 к этому моменту проверен в _validate: число, конечное, > 0
       _warn_well_shut(history_blocks, config.initial_conditions.p0)
       return config
   ```
4. Новая функция — в конец модуля, после `_warn_large_skin` (через две пустые строки):
   ```python
   def _warn_well_shut(blocks: list[tuple[str, HistoryInterval]], p0: float) -> None:
       """Объекты истории, где скважина заведомо закрыта (DEBT-056). Ур. (eq:bc_pwf_shutin)."""
       # Только добыча (FEAT-020): при p_wf ≥ p в ячейке забоя приток нулевой,
       # нагнетания нет. При добыче давление в пласте не выше p0 (контур питания
       # держит p0, источников нет), поэтому p_wf ≥ p0 закрывает скважину на весь
       # интервал; при control='rate' то же даёт min_bhp ≥ p0 — забой не может
       # опуститься ниже p0. Замер до DEBT-056 (vault/issues/debt-056/probes/
       # skin_range.out.txt): p_wf = 25 МПа и min_bhp = 25 МПа при p0 = 20 МПа —
       # расчёт без притока и без сообщения.
       for where, h in blocks:
           if h.control == "pressure" and h.p_wf >= p0:
               user_log.warning(
                   f"{where}: p_wf = {h.p_wf:.6g} Па ≥ p0 = {p0:.6g} Па — давление "
                   f"в пласте при добыче не выше p0, скважина в этом интервале "
                   f"закрыта и не добывает (нагнетание не поддержано). Останов "
                   f"обычно задают control='rate', q_oil = 0.")
           # q_oil = 0 — намеренный останов (примеры 16, 17): min_bhp при нулевом
           # дебите на итог не влияет, предупреждать не о чем
           elif h.control == "rate" and h.q_oil > 0 and h.min_bhp >= p0:
               user_log.warning(
                   f"{where}: min_bhp = {h.min_bhp:.6g} Па ≥ p0 = {p0:.6g} Па при "
                   f"q_oil = {h.q_oil:.6g} м³ст/с — забой не может опуститься ниже "
                   f"p0, скважина в этом интервале закрыта, дебит не достигается.")
   ```
   Docstring — одна строка не длиннее 100 символов (CLAUDE.md; соседние функции модуля укладываются в 100).

**Проверка после этого шага:**
- `python -m pytest tests/test_config.py -q -k TestValidationWell` — 22 passed.
- `python -m pytest tests/test_config.py -q` — весь модуль зелёный (в т.ч. `TestHistoryBlocks`, `TestMultiInterval`: `_expand_history` теперь возвращает кортеж).
- Регресс: быстрый — ожидание baseline + 22 passed, 0 failed.

**Подводные камни:**
- `control` проверен в `_validate_interval` до `blocks.append` — в `_warn_well_shut` только `"pressure"` и `"rate"`; `p_wf` при `pressure` и `q_oil`, `min_bhp` при `rate` не `None` (обязательны, `_validate_interval` 486-507) и конечны (DEBT-051).
- Тест `test_no_warning_before_error[pwf_and_porosity]`: `porosity` = 0 → `ValueError` в `_validate` до `_warn_well_shut`.

**Зависимости:** требует шаги 2 и 3 (якорь вызова — строка `_warn_large_skin(config)` из шага 3).

**Оценка:** ~35 строк, ~15 минут.

### Шаг 5: Документы

**Цель:** P8 §5 — по коду; постановка — скин у проводимости забойной грани; заметки «не закрыто» — закрыты.

**Файлы:**
- `vault/knowledge/decisions/P8-формат-ввода-json.md`
- `numerical_solver/doc/problem_statement.tex`
- `vault/knowledge/debugging/NaN и inf в числовых полях конфига давали отказ через dt-512 и молча неверные расчёты — тип и конечность проверяются при загрузке.md`
- `vault/knowledge/debugging/положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке.md`

**Что сделать:**

5.1. **P8 §5** (строки 207-236). Заменить первый абзац (строка 209):
   До:
   ```
   Валидация данных для гидро — ответственность прототипа (конструкторы BlackOilPVT, TabulatedRelPerm, RadialGrid проверяют входные данные). Исключение — тип и конечность чисел: их для всех полей проверяет наш config (DEBT-051, ниже).
   ```
   После:
   ```
   Кто проверяет входные данные — по коду (сверено при [[DEBT-056]]). До DEBT-056 здесь стояло «валидация данных для гидро — ответственность прототипа»; по коду это не так: скалярные поля проверяет наш config, таблицы и согласованность — наша фабрика, проверки прототипа повторяют часть наших и срабатывают позже — на них не полагаемся.

   | Этап | Где | Что |
   |---|---|---|
   | `load_config` | `io/config.py`: `_check_numeric_fields`, `_require_finite_number` | тип и конечность всех чисел ([[DEBT-051]]) |
   | | `_expand_history`, `_validate_interval` | формы `time.history` (FEAT-018); `control`, `p_wf > 0`, `q_oil ≥ 0`, `min_bhp > 0`, неиспользуемые поля (DEBT-008) |
   | | `_validate` | геометрия, сетка, порода, тепловые параметры, начальные условия, `dt_integration`, `max_retries`, `skin` |
   | | `_warn_large_skin`, `_warn_well_shut` (после `_validate`) | предупреждения: `skin` > 50; `p_wf`, `min_bhp` $\ge p_0$ (DEBT-056) |
   | `from_config` | `factory.py`: `_read_numeric_csv`, `_check_pvto_branches`, `_check_gas_pvt_table`, `_check_relperm_table` | CSV-таблицы: числа, пределы, монотонность, ветви PVTO (DEBT-042, DEBT-044, DEBT-038) |
   | | `_check_rs0_in_table`, `_check_undersaturated_start`; `_warn_negative_compressibility`, `_warn_initial_table_range` | начальное состояние против PVT (BUG-017); предупреждения: $c < 0$ (BUG-019), выход за таблицы (BUG-017) |
   | сетка GPN | `grid/log_radial.py` (`LogRadialGrid`) | повтор проверок геометрии |
   | прототип | `radial_blackoil/grid.py`, `pvt.py`, `relperm.py`, `blackoil.py` | повтор геометрии; монотонность таблиц; режимы якобиана и решателя СЛАУ; $q \ge 0$. `skin` прототип не проверяет |

   Проверки — только на пути JSON → `load_config` → `from_config`. Конфиг, собранный в коде, и прототип, вызванный напрямую, их не получают.
   ```
   Строку 211 «Валидация данных для температуры — ответственность нашего config (`_validate`, `io/config.py`; DEBT-047):» → «Тепловые параметры — наш config (`_validate`, `io/config.py`; DEBT-047, DEBT-049):». Список 212-216 не менять.

   После абзаца «Замер до DEBT-051 …» (строка 225) вставить:
   ```
   Скважина — наш config ([[DEBT-056]]; отказ — `_validate`, предупреждения — `_warn_large_skin`, `_warn_well_shut` после `_validate`, в `io/config.py`):
   - `numerics.skin` ≥ 0. $s < 0$ → `ValueError`: проводимость забойной грани прототипа $T_w = 2\pi kh/(\ln(r_1/r_w) + s)$ (`radial_blackoil/grid.py`, `well_transmissibility_m3`) на сетках проекта ($\ln(r_1/r_w) = \ln(R_{ext}/r_w)/(2N) \approx 0.01…0.16$) неположительна уже при $s \approx -0.01…-0.16$; отрицательный скин в проекте не предусмотрен (решение пользователя). Сообщение даёт обход — `geometry.r_well` = $r_w e^{-s}$ (приведённый радиус скважины: тот же установившийся однофазный приток, при разгазировании у забоя — приближённо), `skin` = 0; температура забоя тогда относится к радиусу $r_w e^{-s}$. При $r_w e^{-s} \ge R_{ext}$ сообщение говорит, что обход неприменим
   - $s > 50$ — предупреждение с долей установившегося однофазного притока $\ln(R_{ext}/r_w)/(\ln(R_{ext}/r_w) + s)$ (у baseline при $s = 50$ — 11 %), расчёт идёт
   - `p_wf` $\ge p_0$ (`control = "pressure"`) или `min_bhp` $\ge p_0$ при `q_oil > 0` (`control = "rate"`) в любом объекте `time.history` — предупреждение `history[i]: …`, одно на объект JSON. Оба предупреждения — после всех отказов `load_config`. При добыче давление в пласте не выше $p_0$, поэтому интервал целиком без притока (`eq:bc_pwf_shutin`). `q_oil = 0` — намеренный останов (примеры 16, 17), без предупреждения

   Замер до DEBT-056 (`vault/issues/debt-056/probes/skin_range.out.txt`): $s$ = −0.5, −2 — отказ через dt/512 с советом увеличить `max_retries`; $s$ = 1e6, `p_wf` = 25 МПа, `min_bhp` = 25 МПа при $p_0$ = 20 МПа — расчёт без притока, молча.
   ```
   Блок «Общая валидация (geometry, grid) — наш Factory:» (строки 229-231):
   До:
   ```
   Общая валидация (geometry, grid) — наш Factory:
   - rw > 0, re > rw, h > 0, N ≥ 1
   - 0 < φ ≤ 1, k > 0
   ```
   После:
   ```
   Геометрия, сетка, порода — наш config (`_validate`); `LogRadialGrid` и `RadialGrid` прототипа повторяют:
   - rw > 0, re > rw, h > 0, N ≥ 1
   - 0 < φ ≤ 1, k > 0
   ```

5.2. **`problem_statement.tex`** — после формулы $\mathcal{T}_{\half}$, $\mathcal{T}_{N+\half}$ (строки 1705-1709, закрывающая `\]` на 1709), перед `\paragraph{Забой …}` (1711), вставить абзац:
   ```latex
   Скин-фактор~$s$ (параметр конфигурации) учитывает дополнительное
   сопротивление прискважинной зоны и~прибавляется к~знаменателю
   проводимости забойной грани:
   $\mathcal{T}_{\half} = 2\pi h k / \bigl(\ln(r_0/\rw) + s\bigr)$.
   Допустим только $s \ge 0$: при~$s \le -\ln(r_0/\rw)$ проводимость
   неположительна, а~на~сетках проекта $\ln(r_0/\rw) \approx 0.01$--$0.16$.
   Стимулированную скважину ($s < 0$) можно задать приведённым радиусом
   $\rw e^{-s}$ вместо~$\rw$ при~$s = 0$: установившийся однофазный приток
   тот~же, $p - \pwf = \frac{q\mu}{2\pi k h}\ln\frac{r}{\rw e^{-s}}$, но~температура
   забоя относится к~радиусу $\rw e^{-s}$.
   ```
   Сборка (из `numerical_solver/doc`): `pdflatex -interaction=nonstopmode problem_statement.tex` дважды; в `problem_statement.log` — без новых `Undefined control sequence` и `undefined references` (сравнить число предупреждений с прогоном до правки: `Select-String -Path problem_statement.log -Pattern "Warning" | Measure-Object`).

5.3. **Заметки `knowledge/debugging/`:**
   - «NaN и inf … проверяются при загрузке.md», раздел «Что не закрыто» (строка 32): в конец абзаца после «Диапазоны параметров скважины — [[DEBT-056]].» дописать « Закрыто [[DEBT-056]]: $s < 0$ — отказ при загрузке с обходом через приведённый радиус, $s > 50$ и `p_wf`/`min_bhp` $\ge p_0$ — предупреждения (P8 §5).»
   - «положительный μ_JT нефти … .md», строка 40: в конец пункта после «([[DEBT-056]])» дописать « — закрыто: отказ при $s < 0$, предупреждения при $s > 50$ и `p_wf`/`min_bhp` $\ge p_0$.»

**Проверка после этого шага:**
- Регресс: `python -m pytest tests/ --collect-only -q` — шаг меняет только документы; ожидание 1614.

**Зависимости:** требует шаги 3, 4 (тексты описывают сделанное).

**Оценка:** ~45 строк текста, ~25 минут (с двумя сборками LaTeX).

### Шаг 6: Проверка

**Цель:** полный прогон, проба на баг и проба по конфигам — зелёное состояние.

**Что сделать** (из `.worktrees/debt-056/numerical_solver`):
1. Полный прогон: `python -m pytest tests/ -q` → ожидание 1614 passed.
2. Проба на баг: `$env:PYTHONIOENCODING = "utf-8"; python ..\vault\issues\debt-056\probes\skin_range.py > ..\vault\issues\debt-056\probes\skin_range_green.out.txt`. Проба импортирует пробу DEBT-051 (`vault/issues/debt-051/probes/red_state.py`, в git) и берёт код из текущего каталога. Ожидание: `skin = -0.01`, `-0.5`, `-2` — `load_config: ValueError: numerics.skin = … < 0: …`; остальные строки — как в `skin_range.out.txt` (журнал в пробе выключен, предупреждения не печатаются; расчётный код DEBT-056 не меняет — числа те же). Если к моменту реализации в базу влит BUG-022 (меняет условие сходимости Ньютона — числа 21 примера из 22 по его плану), строки «ПРОШЛИ» могут отличаться в последних знаках: сверять этап и тип отказа, а числа — с прогоном пробы на базе ветки до правки.
3. Проба по конфигам: `python ..\vault\issues\debt-056\probes\configs_scan.py > ..\vault\issues\debt-056\probes\configs_scan_green.out.txt` → `с замечаниями: 0`, число конфигов — как на шаге 1; путь к коду — в worktree.

**Проверка:** все три пункта по ожиданию; выводы проб — в `vault/issues/debt-056/probes/` (`.out.txt` в git, CLAUDE.md «Что не коммитить» их не исключает).

**Регресс:** полный — итоговый прогон `/implement`.

**Оценка:** ~15 минут (полный прогон ~10 минут).

## Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_negative_skin_rejected[small/acid/fracture]` | `tests/test_config.py` (существующий) | $s$ = −0.01, −0.5, −2 | `ValueError` `numerics.skin = … < 0` | отказ через dt/512 с ложным советом про `max_retries` |
| `test_negative_skin_message_gives_equivalent_radius` | там же | $s$ = −0.5, $r_w$ = 0.1 | в тексте `geometry.r_well`, `0.1649`, «температура забоя» | сообщение без обхода и без оговорки |
| `test_equivalent_radius_beyond_drainage[minus7/minus1e300]` | там же | $s$ = −7: $r_w e^7$ = 109.7 > 50 м; $s$ = −1e300 | «неприменим», без `RuntimeWarning` | совет, который нельзя выполнить; переполнение `np.exp` |
| `test_skin_up_to_threshold_silent[zero/damaged/threshold]` | там же | $s$ = 0, 5, 50 | без отказа и предупреждений | ложные предупреждения; сдвиг границы порога |
| `test_large_skin_warns[above/1e3/1e6]` | там же | $s$ = 50.5, 1e3, 1e6 | одно предупреждение с `numerics.skin` | расчёт «без притока» молча |
| `test_large_skin_warning_gives_inflow_ratio` | там же | $s$ = 1000, $R_{ext}/r_w$ = 500 | `0.6%` в тексте | неверная формула доли притока |
| `test_pwf_not_below_p0_warns[equal_p0/above_p0]` | там же | `history[1].p_wf` = 20, 25 МПа | одно предупреждение `history[1]`, `p_wf` | интервал без притока молча |
| `test_min_bhp_not_below_p0_warns` | там же | `rate`, `min_bhp` = 25 МПа | одно предупреждение `history[1]`, `min_bhp` | то же при управлении по дебиту |
| `test_shut_in_by_rate_silent[atm/above_p0]` | там же | `q_oil = 0` | без предупреждений | шум на штатных остановах (примеры 16, 17) |
| `test_block_warns_once` | там же | блок 24 ч по 1 ч, `p_wf` = 25 МПа | 24 интервала, одно предупреждение `history[0]` | 24 одинаковых предупреждения |
| `test_production_silent` | там же | `_minimal_raw` | без предупреждений | ложные предупреждения на штатном конфиге |
| `test_no_warning_before_error[pwf_and_porosity/skin_and_max_retries]` | там же | ошибка в другом поле + повод для предупреждения | `ValueError`, предупреждений нет | «предупреждение, а следом отказ» |

**Регрессия:** все существующие тесты — без правок (расчётный код не меняется). Особо: `tests/test_config.py` целиком (`_expand_history` меняет тип результата), `TestValidationNumbers` (порядок: конечность раньше диапазона скина).

**Baseline:** 1592 теста, `--collect-only`; быстрый уровень — замер шага 1.

## Критерии завершения

- [ ] Шаги 1–6 выполнены.
- [ ] Тестов 1592 → 1614; полный прогон зелёный.
- [ ] `skin_range_green.out.txt`: $s$ = −0.01, −0.5, −2 — `load_config: ValueError: numerics.skin …`; прочие строки совпадают с `skin_range.out.txt`.
- [ ] `configs_scan_green.out.txt`: замечаний 0.
- [ ] Прототип не менялся: `git diff --stat numerical_scheme/implementation -- numerical_solver/HydroSolverPrototype` пуст.
- [ ] P8 §5 переписан; `problem_statement.tex` собирается без новых предупреждений; две заметки `debugging/` обновлены.
- [ ] Vault: статус DEBT-056 в реестре, `05-comment-done.md` в issue #87.

## Обнаруженные проблемы

- **P8 §5 устарел** («гидро — прототип») — исправляется шагом 5.1, отдельной записи не нужно.
- **Постановка не упоминает скин** при $\mathcal{T}_{1/2}$ — исправляется шагом 5.2.
- Новых записей в реестры не требуется.

## Связь формула → код

| Формула | Где в коде |
|---|---|
| $T_w = 2\pi kh/(\ln(r_1/r_w) + s)$ | `radial_blackoil/grid.py:20-21` (прототип, справка) |
| $r_w' = r_w e^{-s}$ (приведённый радиус) | `io/config.py`, `_validate`, блок «Скважина» |
| $q(s)/q(0) = \ln(R_{ext}/r_w)/(\ln(R_{ext}/r_w) + s)$ | `io/config.py`, `_warn_large_skin` |
| `eq:bc_pwf_shutin` (`problem_statement.tex:697`) | `io/config.py`, `_warn_well_shut` |

## Оценка

- Файлов: 2 кода/тестов (`config.py`, `test_config.py`) + 4 документа.
- Строк: ~+90 код, ~+175 тесты, ~+45 документы.
- Время: ~1.5–2 часа с полным прогоном.

## Связанные заметки

- Реестр: `vault/roadmap/известные баги и технический долг.md` → DEBT-056 (связано: [[DEBT-051]], [[DEBT-019]], [[FEAT-020]], [[DEBT-028]])
- Issue: [#87](https://github.com/ArturSalamatin/Oil_Gas/issues/87); материалы — `vault/issues/debt-056/`
- [[P8-формат-ввода-json]] — §5 «Валидация», §6 «Центры ячеек»
- Пробы: `vault/issues/debt-056/probes/skin_range.py` (+ `.out.txt`), `configs_scan.py` (+ `configs_scan_base.out.txt`), `plan_check.py` (+ `.out.txt`, аудит 1)

## Аудит 1 (2026-10-10, база `4ab46f5`, фокус — предметная суть)

Найдено 9 (🟡 5, 🔵 4), все исправлены в тексте плана:
- 🟡 **Конфликт с BUG-022** (в реализации, `.worktrees/bug-022`): обе задачи вставляли строку шапки `test_config.py` после строки DEBT-049 и блок в конец `_validate`; при влитии BUG-022 раньше предупреждение о скине уходило бы до отказа по `newton_cell_tol`. Отказ $s < 0$ перенесён после проверок породы, оба предупреждения — отдельные функции после `_validate`, строка шапки — после строки «История», комментарий поля `skin` — в той же строке. Раздел «Порядок влития с BUG-022».
- 🟡 **Диапазон $\ln(r_1/r_w)$** «0.01…0.09» — замер по 32 конфигам: 0.011…0.155 (`configs/val001.json`, $N$ = 20). Исправлен в сообщении об ошибке, комментарии, P8, абзаце постановки.
- 🟡 **«Тот же приток»** при приведённом радиусе — верно для установившегося однофазного притока; при разгазировании у забоя — приближённо. Уточнено в сообщениях, P8, постановке.
- 🟡 **Переполнение `np.exp`** при $s = -10^{300}$ (конечное, проходит DEBT-051): `RuntimeWarning` в stderr перед отказом. Сравнение $r_w e^{-s} < R_{ext}$ — в логарифмах; тест `test_equivalent_radius_beyond_drainage[minus1e300]` с `filterwarnings("error::RuntimeWarning")`. Тестов 21 → 22, итог 1613 → 1614.
- 🟡 **Докстринги > 100 символов** (`_expand_history`, `_warn_well_shut`), план называл это допустимым «как у соседних» — у соседних ≤ 100. Сокращены.
- 🔵 База `eee5334` → `4ab46f5` (влит BUG-023, правил только `test_energy_matrix_examples.py`; номера строк плана действительны).
- 🔵 Шаг 6: «числа побитово те же» неверно, если BUG-022 влит раньше, — оговорка.
- 🔵 Шаги 1, 6: число конфигов 30 — жёсткое; критерий — 0 замечаний.
- 🔵 Обоснование $p \le p_0$: гидродинамика изотермическая (`pvt/standing.py:55`), принцип максимума; прототип закрывает скважину при $p_{ячейки} \le$ `min_bhp` (`blackoil.py:129-130`). Добавлено в контекст шага 4; «сходится с замером» для доли притока уточнено.

**Прогон в коде** (`plan_check.py`, `plan_check.out.txt`): блоки «До/После» плана применены дословно к копии `gpn_multiphase_solver`, `test_config.py`, `problem_statement.tex`; каждое «До» найдено ровно один раз. Тесты класса: шаг 2 — 14 failed, 8 passed; шаг 3 — 18 passed, 4 failed (тесты забоя); шаг 4 — 22 passed, весь `test_config.py` — 267 passed. 32 конфига проекта через `load_config` копии — ни отказа, ни предупреждения. Тексты сообщений просмотрены (`plan_check.out.txt`). `problem_statement.tex` с абзацем шага 5.2 собирается (pdflatex ×2): ошибок и неопределённых ссылок 0. Новых строк > 100 символов нет.

**Проверено и верно:** формула $T_w$ и центры прототипа (`grid.py:9-10, 20-21`); точность доли притока $\ln(R_{ext}/r_w)/(\ln(R_{ext}/r_w)+s)$ на сетке прототипа (сопротивления граней телескопически дают $\ln(R_{ext}/r_w)$); числа 11.1 %, 0.6 %, 0.1649 м, 109.7 м; вызовы `_expand_history`, `_validate` — только `config.py`; тесты «нет предупреждений» вне `test_config.py` не задеты; VAL-005 учитывает DEBT-056 (у примера 18 скин 0, $p_{wf} < p_0$); голый импорт `numpy` в venv.
