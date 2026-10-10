---
tags:
  - план
  - рефакторинг
date: 2026-10-10
issue: DEBT-049
github: 81
branch: refactor/debt-049/thermal-scalars-finite-check
status: в процессе
worktree: .worktrees/debt-049
audit:
  date: 2026-10-10
  round: 1
  focus: предметная суть — физика знака μ_JT, верность утверждений о совместимости и цепочке, соседние задачи
  found: 8
  auto-fixed: 7
  manual-required: 1   # предупреждение при μ_JT,o > 0 — решено пользователем в ходе аудита, внесено
---

# План DEBT-049: проверка конечности $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ при загрузке конфига и предупреждение при $\mu_{JT,o} > 0$

**Задача:** DEBT-049 в `vault/roadmap/известные баги и технический долг.md` · GitHub [#81](https://github.com/ArturSalamatin/Oil_Gas/issues/81) · ветка `refactor/debt-049/thermal-scalars-finite-check` в worktree `.worktrees/debt-049` · база `numerical_scheme/implementation` (план — на `7b34a33`; аудит 1 — на `521cd26`: за время аудита влит DEBT-046 `1171a84`, +52 теста, файлы плана `io/config.py`, `test_config.py`, P8, заметка о нефизичной температуре не тронуты — `git diff --stat 7b34a33 HEAD` по ним пуст)

**Подтип:** рефакторинг с ужесточением проверки ввода. На допустимых конфигах (все конфиги проекта) числа решателя, истории и README примеров не меняются: проверка только читает три значения. Новое предупреждение ни на одном конфиге проекта не срабатывает: у всех $\mu_{JT,o} \le 0$. Прототип не меняется.

## Кратко

Сейчас `_validate` (`numerical_solver/gpn_multiphase_solver/io/config.py:334`) проверяет на конечность шесть тепловых параметров (DEBT-047): $c_{p,o}$, $c_{p,g}$, $(\rho c_p)_s$ — условием `0 < v < inf`, $\lambda_s$, $\lambda_o$, $\lambda_g$ — `0 <= v < inf`. Три оставшихся тепловых скаляра — `thermal.L_degas` ($L$, теплота дегазации), `thermal.mu_JT_oil`, `thermal.mu_JT_gas` (коэффициенты Джоуля–Томсона) — не проверяются: у $L$ только знак ($L < 0$ — предупреждение в журнале), у $\mu_{JT}$ — ничего.

Красная проба `vault/issues/debt-049/probes/red_state.py` (2026-10-10, `7b34a33`, вывод `red_state.out.txt`, раздел 1): `configs/baseline.json`, один подменённый скаляр, 24 ч при $p_{wf}$ = 10 МПа (газа нет, $p_b \approx 9.4$ МПа) и 6 МПа (газовая зона у забоя).

| что в конфиге | 10 МПа | 6 МПа | после плана |
|---|---|---|---|
| эталон | $T$ 349.78…352.4 К | $T$ 349.73…352.24 К, $S_{g,\max}$ = 0.0999 | без изменений |
| $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ = NaN, +inf, −inf (9 случаев) | `run: ValueError: array must not contain infs or NaNs [_function_base_impl.py:684]` | то же | `load_config: ValueError: thermal.<параметр> должно быть конечным числом (знак любой), получено …` |

Отказ громкий (scipy `solve_banded` с `check_finite` ловит NaN в СЛАУ энергии), но сообщение не называет параметр: пользователь ищет причину в схеме энергии, а не в конфиге. Даже при 10 МПа, где газа нет, NaN в $\mu_{JT,g}$ и $L$ даёт отказ: $\mathrm{NaN} \cdot 0 = \mathrm{NaN}$.

После правки:
- **`_validate`** проверяет $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ условием `-inf < v < inf` (отсекает NaN, +inf, −inf), знак не ограничивает. Проверка стоит **до** предупреждения о $L < 0$.
- **`_validate`** при $\mu_{JT,o} > 0$ пишет предупреждение в журнал, расчёт идёт (решение пользователя 4, аудит 1). У жидкости $\mu_{JT} = v(\alpha T - 1)/c_p < 0$; положительный знак — почти наверняка $\varepsilon = -\mu_{JT}$ из литературы, такая ошибка в проекте уже была. При $\mu_{JT,g} < 0$ предупреждения нет: у газа это законно выше давления инверсии.
- **P8 §5** перечисляет девять тепловых параметров с проверкой конечности и предупреждение о $\mu_{JT,o} > 0$; в образце JSON P8 исправлены перевёрнутые знаки $\mu_{JT}$ (решение пользователя 2).
- **Заметка о нефизичной температуре** (DEBT-047) — пункт «Что не закрыто» про NaN в $L$, $\mu_{JT}$ закрыт ссылкой на DEBT-049.

Объём: `io/config.py` — блок проверки ~13 строк и блок предупреждения ~14 строк с комментариями; `test_config.py` — 13 тестов (4 функции) и строка докстринга модуля; 2 заметки vault. Тестов: 1481 → 1494, быстрый уровень 1231 → 1244, `test_config.py` 134 → 147 (все новые — в быстром: `test_config.py` без метки `slow`). Числа — на базе `521cd26` (после DEBT-046).

**Код плана проверен подменой** — раздел «Проверка плана» в конце.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-049 в реестре, тело issue `vault/issues/debt-049/01-issue-body.md` и замер `vault/issues/debt-049/probes/red_state.out.txt`. Варианты решения в issue пронумерованы 1–3; выбран вариант 1 (раздел «Решения пользователя»).
3. Worktree и ветка — от базы `numerical_scheme/implementation` (не от `master`: там нет `numerical_solver/`):
   ```powershell
   git worktree add .worktrees/debt-049 -b refactor/debt-049/thermal-scalars-finite-check numerical_scheme/implementation
   ```
   Venv — основного каталога: из `.worktrees/debt-049/numerical_solver` запускать `..\..\..\numerical_solver\.venv\Scripts\python`. pytest в worktree берёт пакет worktree (проверено на прошлых задачах); пробы — по `Path.cwd()` и печатают путь к коду первой строкой — сверить, что это worktree.
4. Исходный замер (из `numerical_solver/` worktree):
   ```powershell
   <python> -m pytest tests/ --collect-only -q          # ожидание: 1481 tests collected
   <python> -m pytest tests/ -m "not slow" -q           # ожидание: 1231 passed, 250 deselected (~80 с)
   ```
   Запомни число тестов (всего и в быстром уровне) и время быстрого уровня. Числа — на `521cd26` (после влития DEBT-046, 2026-10-10; замер аудита 1: `--collect-only` 1481, быстрый уровень на коде плана 1231 passed за 79 с). Если до реализации в базу влита ещё одна задача с тестами, абсолютные числа сдвигаются — проверять приращение: **+13 всего, +13 в быстром уровне, `test_config.py` 134 → 147**. Параллельно идёт DEBT-050 (только vault, `.worktrees/debt-050`) — тестов не меняет.
5. Начни с шага 1. После каждого шага — проверка по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

## Решения пользователя (2026-10-10)

1. **Объём — только три скаляра** (вариант 1 issue). NaN в прочих числовых полях конфига — отдельная запись [[DEBT-051]] (раздел «Обнаруженные проблемы»).
2. **Знаки $\mu_{JT}$ в образце JSON P8 исправить в этой задаче** (шаг 2): `"mu_JT_oil": 4.0e-7` → `-4.0e-7`, `"mu_JT_gas": -4.0e-6` → `4.0e-6`. Образец расходился с конфигами проекта (`configs/baseline.json:36-37`: $-4\cdot10^{-7}$ и $4\cdot10^{-6}$) и с физикой.
3. **Зарегистрировать** DEBT-051 и дополнить [[DEBT-008]] полем `time.start_day` (сделано при планировании).
4. **Предупреждение при $\mu_{JT,o} > 0$, только для нефти** (аудит 1, 2026-10-10). Предупреждение, а не отказ, и только для нефти. Обоснование:
   - $\mu_{JT} = (\partial T/\partial p)_h = v(\alpha T - 1)/c_p$ (`numerical_solver/doc/problem_statement.tex`, `eq:muJT_def`, строка 2696). У нефти $\alpha \approx 10^{-3}$ 1/К, $T \approx 350$ К, $\alpha T \approx 0.3$: $\mu_{JT,o} \approx (1/850)(0.3 - 1)/2000 \approx -4.1\cdot10^{-7}$ К/Па — ровно значение `configs/baseline.json`. $\mu_{JT,o} > 0$ требует $\alpha_o T > 1$ (по `eq:alpha_via_muJT`: $\alpha T = 1 + \rho c_p \mu_{JT}$), то есть $\alpha_o > 1/T \approx 2.9\cdot10^{-3}$ 1/К — для жидкости вдали от критической точки нереально.
   - Ошибка уже была: до 2026-09-29 в конфигах примеров стояли $\varepsilon_1, \varepsilon_2$ из статьи Шарафутдинова и др. 2019, где $\varepsilon = -\mu_{JT}$; в расчёте нефть при дросселировании охлаждалась. Знаки исправлены в 11 примерах и двух конфигах `configs/`, а в образце JSON P8 старый знак остался (решение 2).
   - У газа $\mu_{JT,g} < 0$ законен выше давления инверсии — предупреждение там было бы ложным.
   - Запись реестра «знак не ограничивать» соблюдена: расчёт идёт, как при $L < 0$ (DEBT-047).

## Текущее состояние

### Код

`numerical_solver/gpn_multiphase_solver/io/config.py`:
- `:88-95` — `ThermalConfig`: `c_p_oil`, `c_p_gas`, `mu_JT_oil: float = 0.0`, `mu_JT_gas: float = 0.0`, `L_degas: float = 0.0`. Типы не проверяются (dataclass), значения — как в JSON.
- `:271-331` — `load_config`: `json.load` (литералы `NaN`, `Infinity`, `-Infinity` модуль `json` принимает по умолчанию) → dataclass-секции → `_validate(config)` (`:330`, единственный вызов `_validate` в коде).
- `:334-412` — `_validate`. Тепловой блок `:353-385`:
  - `:361` — `inf = float("inf")`; `:362` — `th = cfg.thermal`;
  - `:363-367` — $(\rho c_p)_s$, $c_{p,o}$, $c_{p,g}$: `if not (0 < value < inf): raise ValueError(f"{name} должна быть конечной и > 0, получено {value}")`;
  - `:369-373` — $\lambda_s$, $\lambda_o$, $\lambda_g$: `0 <= value < inf`, «… ≥ 0»;
  - `:374-385` — комментарий и предупреждение: `if th.L_degas < 0: user_log.warning(f"thermal.L_degas = {th.L_degas} Дж/кг < 0: …")`.

Путь значений дальше: `SimulatorFactory.from_config` (`factory.py:38`) → `_create_pvt` (`factory.py:96`) → `StandingFullPVT(mu_JT_oil_val=tc.mu_JT_oil, mu_JT_gas_val=tc.mu_JT_gas, L_degas_val=tc.L_degas)` (`factory.py:111-113`) или `TableFullPVT(mu_JT_oil=…, mu_JT_gas=…, L_degas=…)` (`factory.py:150-152`) → `float(...)` в конструкторах (`pvt/standing.py:66-68`, `pvt/table_full.py:22-24`) → `energy/tridiag.py:215-217` (`pvt.mu_JT_oil(p, T_old)` и др.), `:261-262`. Обе модели PVT берут значения из одной секции `thermal` — одна проверка в `_validate` закрывает обе.

### Тесты

`numerical_solver/tests/test_config.py` (134 теста):
- `:1-10` — докстринг модуля; `:6` — строка о тепловых параметрах (DEBT-047);
- `:124-140` — `TestBaselineThermal`: `test_mu_JT_oil` (−4e-7), `test_mu_JT_gas` (4e-6), `test_L_degas` (168000) — чтение baseline;
- `:247-252` — `_write_json(tmp_path, data)`: `json.dumps` по умолчанию пишет `NaN`/`Infinity` литералами — так тесты подают их в `load_config`;
- `:254-…` — `_minimal_raw()`: секция `"thermal": {}` (все тепловые поля по умолчанию);
- `:518-589` — `TestValidationThermal`: `test_invalid_rejected` ×13 (`:553`), `test_zero_conductivity_accepted` (`:560`), `test_negative_L_warns` (`:567`), `test_nonnegative_L_no_warning` ×2 (`:583`).

Ни один тест и ни один JSON проекта не подаёт NaN или inf в $L$, $\mu_{JT}$ (grep `NaN|Infinity` по `numerical_solver/**/*.json` — только `HydroSolverPrototype/.../FINAL_REGRESSION_METRICS_20260825a.json`, это не конфиг; grep `float(`/`np.nan`/`np.inf` рядом с этими именами в `*.py` — пусто).

### Документы

- `vault/knowledge/decisions/P8-формат-ввода-json.md:207-216` — §5 «Валидация»: `:214` — $L$ «любой знак», `:216` — «для шести параметров … `NaN` и `Infinity` отвергаются»; $\mu_{JT}$ не упомянуты. `:313-314` — образец JSON с перевёрнутыми знаками $\mu_{JT}$.
- `vault/knowledge/debugging/нефизичная температура доходила до истории молча — проверка T ловит грубые ошибки, остальное проверка ввода.md:49` — «Что не закрыто»: «$L$ = NaN или $\mu_{JT}$ = NaN — отказ scipy без имени параметра … отдельная запись, если понадобится».

## Целевое состояние

- `_validate`: после цикла по λ (`:369-373`) и до предупреждения о $L < 0$ (`:374`) — цикл по `thermal.L_degas`, `thermal.mu_JT_oil`, `thermal.mu_JT_gas` с условием `-inf < value < inf`; при нарушении — `ValueError(f"{name} должно быть конечным числом (знак любой), получено {value}")`.
- Порядок: сначала конечность, потом знак $L$. Иначе при $L = -\infty$ в журнал сначала уйдёт предупреждение «L < 0: выделение газа нагревает пласт», а следом отказ — два сообщения о разных причинах.
- `_validate`: сразу после предупреждения о $L < 0$ (`:381-385`) — `if th.mu_JT_oil > 0: user_log.warning(...)` с именем `thermal.mu_JT_oil`, значением и подсказкой про $\varepsilon = -\mu_{JT}$. Так же после проверки конечности: при $\mu_{JT,o} = +\infty$ — только отказ, без предупреждения. $\mu_{JT,o} = 0$ (примеры 01, 07, 09, `configs/val001.json`) — без предупреждения.
- Интерфейсы не меняются: `load_config`, `_validate`, dataclass-секции — те же сигнатуры. Новых импортов нет (`inf` уже определён на `:361`).

## Анализ вариантов

Варианты — из тела issue (`vault/issues/debt-049/01-issue-body.md`, «Анализ вариантов решения»):

| | Суть | Плюсы | Минусы | Выбор |
|---|---|---|---|---|
| 1 | Цикл по трём скалярам в `_validate` | ~13 строк, стиль DEBT-047, обе модели PVT | Прочие поля пропускают NaN | **выбран** |
| 2 | Конечность всех числовых полей (обход dataclass-полей) | Закрывает класс ошибок | Шире задачи; P8 §5 отдаёт проверку гидродинамики прототипу; Optional-поля; номер блока истории теряется | → [[DEBT-051]] |
| 3 | `json.load(parse_constant=...)` | Одна строка | Нет имени параметра (ради него задача); `1e999` → inf мимо `parse_constant` | отклонён |

Промежуточные состояния варианта 1: шаг 1 (тесты + код) — зелёный; шаг 2 (только документы) — зелёный; шаг 3 (проба, vault) — код не меняется.

## Подводные камни (чеклист)

- ✅ **Все места вызова:** `_validate` вызывается только из `load_config` (`config.py:330`; grep `_validate\(` по `numerical_solver/**/*.py`). `SimulatorFactory.from_config` не валидирует — конфиг, изменённый в коде после `load_config`, проверку обходит. Так же и для шести параметров DEBT-047; вне задачи.
- ✅ **Зависимости пакетов, циклические импорты:** новых импортов нет.
- ✅ **Обратная совместимость:** все конфиги проекта конечны (grep выше) — загружаются как прежде. Это проверяет уже быстрый уровень: `tests/test_examples.py::TestConfigs::test_load_config_passes` (`:174-178`, параметризован по всем примерам, без фикстуры `results`, метки `slow` нет) вызывает `load_config` для каждого примера. Полный уровень (фикстура `results`) — сквозные расчёты тех же конфигов.
- ✅ **Новое предупреждение на конфигах проекта:** grep `"mu_JT_oil"\s*:\s*[0-9+]` по `numerical_solver/**/*.json` — только `0.0` (`configs/val001.json`, примеры 01, 07, 09); положительных нет — предупреждение не сработает ни в примерах, ни в тестах. Тесты с $\mu_{JT,o} = 4\cdot10^{-7}$ (`tests/test_energy.py:777, 1429`, `tests/test_pvt.py:34, 255`) создают PVT напрямую, минуя `load_config`, — предупреждения не видят.
- ⚠️ **Нечисловые значения** (проверено в интерпретаторе при аудите 1):
  - `null` в `mu_JT_oil`/`mu_JT_gas` — раньше `TypeError` в `float(None)` конструктора PVT (`from_config`), теперь `TypeError` в `_validate`: отказ остаётся, меняются место и текст;
  - **строка-число** (`"mu_JT_oil": "-4e-7"`) — раньше расчёт **шёл**: `float("-4e-7")` в конструкторе PVT её преобразовывал. Теперь — `TypeError: '<' not supported between instances of 'float' and 'str'` в `_validate`, без имени параметра. Совместимость нарушается только для таких конфигов; в проекте их нет (grep `"(L_degas|mu_JT_oil|mu_JT_gas)"\s*:\s*[^0-9\-\s]` по `*.json` — пусто). У $c_p$, λ (DEBT-047) и у `L_degas` (`th.L_degas < 0`) строка и раньше давала `TypeError` — поведение $\mu_{JT}$ становится таким же;
  - `true`/`false` (bool — подкласс int) проходят как 1/0, как и до правки; `true` в `mu_JT_oil` даст предупреждение о знаке.

  Проверка типов с именем параметра — вне задачи ([[DEBT-051]], пункт «типы»).
- ✅ **Состояние при ошибке:** `_validate` ничего не меняет, только бросает исключение.
- ✅ **Тесты:** существующие тесты `TestValidationThermal` не меняются; `test_negative_L_warns` ($L = -1.68\cdot10^5$, конечно) — предупреждение по-прежнему выдаётся, проверка конечности его пропускает.
- ✅ **Configs:** имена параметров не меняются.
- ✅ **Связь с другими задачами:** DEBT-047 влит (`2ea602f`) — правка встаёт в его блок. DEBT-046 влит во время аудита 1 (`1171a84`) — файлов плана не тронул. DEBT-048 (`m2s` в адаптере, план готов) `io/config.py`, `test_config.py`, P8 не трогает. DEBT-050 (в реализации, только vault) ссылается на заметку о нефизичной температуре, но не правит её (`debt-050 orchestrator-note-local-splitting.md:441, 463`). DEBT-051 (новая) будет править тот же `_validate` — после DEBT-049, конфликт строк возможен, но тривиален.
- ✅ **Производительность:** три сравнения при загрузке.
- ✅ **Прототип:** не меняется — регрессия прототипа не нужна.
- ✅ **Docstrings:** ссылок `\eqref{}` в затронутом коде нет.

## Шаги

### Шаг 1: Тесты и проверка конечности в `_validate`

**Цель:** `load_config` отвергает NaN, +inf, −inf в $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ с именем параметра; знак не ограничен; при $\mu_{JT,o} > 0$ — предупреждение в журнале.

**Файлы:**
- `numerical_solver/tests/test_config.py`
- `numerical_solver/gpn_multiphase_solver/io/config.py`

**Контекст:** тест пишется до реализации (CLAUDE.md, «Тестирование»). Новые тесты сначала проверяются на текущем коде — должны упасть (12 из 13), затем вносится правка кода. Отказ — только при не конечном значении: знак $L$ и $\mu_{JT}$ не ограничивается (запись реестра). $L < 0$ возможна для систем, где растворимость газа растёт с $T$ (P8 §5); $\mu_{JT,g} < 0$ — у газа выше давления инверсии. Для нефти $\mu_{JT,o} = v(\alpha T - 1)/c_p < 0$ при $\alpha T \approx 0.3$ (нагрев при дросселировании), поэтому $\mu_{JT,o} > 0$ — предупреждение, как $L < 0$ (решение пользователя 4).

**Что сделать:**
1. Правка #1 в `test_config.py` — докстринг модуля (`:6`).
2. Правка #2 в `test_config.py` — четыре новые тестовые функции в конце `TestValidationThermal`, после `test_nonnegative_L_no_warning` (`:582-589`).
3. Прогнать только новые тесты на текущем коде:
   ```powershell
   <python> -m pytest tests/test_config.py -q -k "nonfinite_scalar or nonfinite_no_sign_warning or mu_JT_oil_warns or mu_JT_gas_no_warning"
   ```
   Ожидание: **12 failed, 1 passed**. Падают: 9 × `test_nonfinite_scalar_rejected` и 2 × `test_nonfinite_no_sign_warning` — `Failed: DID NOT RAISE <class 'ValueError'>`; `test_positive_mu_JT_oil_warns` — на `assert "thermal.mu_JT_oil" in text` (предупреждения ещё нет). Проходит `test_negative_mu_JT_gas_no_warning`: он страхует от предупреждения для газа и от ограничения знака.
4. Правки #1 и #2 в `io/config.py`: проверка конечности — между циклом по λ и предупреждением о $L < 0$; предупреждение о $\mu_{JT,o} > 0$ — сразу после предупреждения о $L < 0$.
5. Повторить команду п. 3 — ожидание **13 passed**; весь файл `tests/test_config.py` — **147 passed**.

**Изменения (старый → новый код):**

Правка #1, `test_config.py:6`:

<!-- правка numerical_solver/tests/test_config.py #1 до -->
```python
- Тепловые параметры: c_p, (ρc_p)_s > 0, λ ≥ 0, предупреждение при L < 0 (DEBT-047).
```
<!-- правка numerical_solver/tests/test_config.py #1 после -->
```python
- Тепловые параметры: c_p, (ρc_p)_s > 0, λ ≥ 0, предупреждение при L < 0 (DEBT-047);
  L, μ_JT,o, μ_JT,g — конечные, знак любой, предупреждение при μ_JT,o > 0 (DEBT-049).
```

Правка #2, `test_config.py:582-589` — после последнего теста класса:

<!-- правка numerical_solver/tests/test_config.py #2 до -->
```python
    @pytest.mark.parametrize("L", [0.0, 1.68e5], ids=["zero", "positive"])
    def test_nonnegative_L_no_warning(self, tmp_path, caplog, L):
        """L ≥ 0 — без предупреждения; L = 0 (теплота дегазации выключена) — граница."""
        raw = _minimal_raw()
        raw["thermal"]["L_degas"] = L
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
```
<!-- правка numerical_solver/tests/test_config.py #2 после -->
```python
    @pytest.mark.parametrize("L", [0.0, 1.68e5], ids=["zero", "positive"])
    def test_nonnegative_L_no_warning(self, tmp_path, caplog, L):
        """L ≥ 0 — без предупреждения; L = 0 (теплота дегазации выключена) — граница."""
        raw = _minimal_raw()
        raw["thermal"]["L_degas"] = L
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    # L, μ_JT,o, μ_JT,g: знак по физике любой (P8 §5), проверяется только
    # конечность (DEBT-049). Замер до DEBT-049 (vault/issues/debt-049/probes/
    # red_state.out.txt, раздел 1): все 9 случаев при p_wf = 10 и 6 МПа
    # проходили load_config и from_config, а run падал в solve_banded scipy —
    # «array must not contain infs or NaNs», без имени параметра.
    # _write_json пишет NaN и ±inf литералами JSON NaN, Infinity, -Infinity.
    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")],
                             ids=["nan", "inf", "-inf"])
    @pytest.mark.parametrize("key", ["L_degas", "mu_JT_oil", "mu_JT_gas"])
    def test_nonfinite_scalar_rejected(self, tmp_path, key, value):
        """NaN и ±inf в L, μ_JT,o, μ_JT,g → ValueError с полным именем параметра."""
        raw = _minimal_raw()
        raw["thermal"][key] = value
        with pytest.raises(ValueError, match=f"thermal.{key} .*конечным"):
            load_config(_write_json(tmp_path, raw))

    # Конечность проверяется раньше знака. При обратном порядке в журнал
    # ушло бы предупреждение о знаке (L < 0 или μ_JT,o > 0), а следом
    # отказ — два сообщения о разных причинах.
    @pytest.mark.parametrize("key, value", [
        ("L_degas", float("-inf")),
        ("mu_JT_oil", float("inf")),
    ], ids=["L_minus_inf", "mu_JT_oil_plus_inf"])
    def test_nonfinite_no_sign_warning(self, tmp_path, caplog, key, value):
        """Не конечное значение со «знаком предупреждения»: отказ без предупреждения."""
        raw = _minimal_raw()
        raw["thermal"][key] = value
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            with pytest.raises(ValueError, match=f"thermal.{key}"):
                load_config(_write_json(tmp_path, raw))
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_positive_mu_JT_oil_warns(self, tmp_path, caplog):
        """μ_JT,o > 0 — предупреждение, не отказ (решение пользователя, DEBT-049)."""
        # μ_JT = v(αT − 1)/c_p: у нефти αT ≈ 0.3, μ_JT,o ≈ −4e-7 К/Па.
        # +4e-7 — знак ε = −μ_JT из литературы (Шарафутдинов и др., 2019);
        # так было в конфигах примеров до 2026-09-29.
        raw = _minimal_raw()
        raw["thermal"]["mu_JT_oil"] = 4.0e-7
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.thermal.mu_JT_oil == 4.0e-7
        text = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno >= logging.WARNING)
        assert "thermal.mu_JT_oil" in text

    def test_negative_mu_JT_gas_no_warning(self, tmp_path, caplog):
        """μ_JT,g < 0 при μ_JT,o < 0 — без отказа и без предупреждения."""
        # У газа μ_JT < 0 законен выше давления инверсии: проверка конечности
        # не должна стать проверкой знака, а предупреждение — касаться газа.
        # μ_JT,o = −4e-7 — значение конфигов проекта (нагрев нефти).
        raw = _minimal_raw()
        raw["thermal"].update(mu_JT_oil=-4.0e-7, mu_JT_gas=-4.0e-6)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert (cfg.thermal.mu_JT_oil, cfg.thermal.mu_JT_gas) == (-4.0e-7, -4.0e-6)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
```

Правка #1, `io/config.py:372-374` — между циклом по λ и предупреждением о $L < 0$:

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #1 до -->
```python
        if not (0 <= value < inf):
            raise ValueError(f"{name} должна быть конечной и ≥ 0, получено {value}")
    # L < 0 — предупреждение, не отказ (решение пользователя, DEBT-047).
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #1 после -->
```python
        if not (0 <= value < inf):
            raise ValueError(f"{name} должна быть конечной и ≥ 0, получено {value}")
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

Почему `-inf < value < inf`, а не `np.isfinite`: так записаны шесть проверок DEBT-047 (`0 < value < inf`, `0 <= value < inf`), `numpy` в `io/config.py` не импортирован, а сравнение с NaN всегда ложно — NaN отсекается тем же условием.

Правка #2, `io/config.py:381-385` — после предупреждения о $L < 0$ (якорь — сам блок предупреждения; правка #1 его не меняет):

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #2 до -->
```python
    if th.L_degas < 0:
        user_log.warning(
            f"thermal.L_degas = {th.L_degas} Дж/кг < 0: выделение газа в расчёте "
            f"нагревает пласт (Q_deg = −L·ṁ > 0); при L > 0 дегазация охлаждает. "
            f"Проверьте знак.")
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #2 после -->
```python
    if th.L_degas < 0:
        user_log.warning(
            f"thermal.L_degas = {th.L_degas} Дж/кг < 0: выделение газа в расчёте "
            f"нагревает пласт (Q_deg = −L·ṁ > 0); при L > 0 дегазация охлаждает. "
            f"Проверьте знак.")
    # μ_JT,o > 0 — предупреждение, не отказ (решение пользователя, DEBT-049).
    # μ_JT = (∂T/∂p)_h = v(αT − 1)/c_p (problem_statement.tex, eq:muJT_def):
    # у нефти αT ≈ 0.3 (α ≈ 1e-3 1/К, T ≈ 350 К), μ_JT,o ≈ −4e-7 К/Па —
    # при дросселировании нефть греется. μ_JT,o > 0 требует αT > 1, для
    # нефти в пласте это нереально; вероятная причина — знак ε = −μ_JT из
    # литературы (Шарафутдинов и др., 2019), так было в конфигах примеров
    # до 2026-09-29. У газа μ_JT,g < 0 законен выше давления инверсии —
    # без предупреждения.
    if th.mu_JT_oil > 0:
        user_log.warning(
            f"thermal.mu_JT_oil = {th.mu_JT_oil} К/Па > 0: нефть при дросселировании "
            f"в расчёте охлаждается; у жидкости μ_JT = v(αT − 1)/c_p < 0 (нагрев). "
            f"Проверьте знак: в литературе встречается ε = −μ_JT.")
```

Почему здесь: после проверки конечности ($\mu_{JT,o} = +\infty$ отвергнута раньше и предупреждения не даёт — тест `test_nonfinite_no_sign_warning[mu_JT_oil_plus_inf]`) и рядом с предупреждением о $L < 0$ — два предупреждения о знаке в одном месте. `user_log` уже импортирован (`config.py:14`).

**Проверка после этого шага:**
- Тесты шага: п. 3 и п. 5 выше.
- Регресс: быстрый — `<python> -m pytest tests/ -m "not slow" -q`; ожидание **1244 passed, 250 deselected** (было 1231). В том числе `tests/test_examples.py::TestConfigs::test_load_config_passes` — все конфиги примеров загружаются.
- `--collect-only -q` — **1494** (было 1481).

**Подводные камни:** «Нечисловые значения», «Новое предупреждение на конфигах проекта», «Тесты» (чеклист). Сообщение отказа — «должно быть конечным числом» (средний род: «значение параметра»), у шести параметров DEBT-047 — «должна быть конечной» (теплоёмкость, теплопроводность). Шаблон `match` в тесте — `thermal.{key} .*конечным`: точка в регулярном выражении совпадает с любым символом, включая саму точку.

**Зависимости:** требует — ничего; блокирует — шаг 3 (зелёный замер).

**Оценка:** ~27 строк кода (с комментариями), ~70 строк тестов, ~25 минут.

### Шаг 2: Документы — P8 §5, образец JSON, заметка о нефизичной температуре

**Цель:** проектные заметки описывают новую проверку и предупреждение; образец JSON P8 согласован с конфигами по знакам $\mu_{JT}$.

**Файлы:**
- `vault/knowledge/decisions/P8-формат-ввода-json.md`
- `vault/knowledge/debugging/нефизичная температура доходила до истории молча — проверка T ловит грубые ошибки, остальное проверка ввода.md`

**Контекст:** P8 §5 — справочник проверок ввода; после DEBT-047 он перечислял шесть параметров с проверкой конечности. Образец JSON P8 (`:310-316`) содержит `"mu_JT_oil": 4.0e-7`, `"mu_JT_gas": -4.0e-6` — знаки противоположны `configs/baseline.json:36-37` и физике. Это след $\varepsilon = -\mu_{JT}$ из статьи Шарафутдинова и др. 2019: до 2026-09-29 с этим знаком были и конфиги примеров, их исправили, а образец P8 — нет (решение пользователя 4). Исправить — решение пользователя 2; обратно не возвращать. Заметка о нефизичной температуре в «Что не закрыто» (`:49`) ссылается на будущую запись — теперь это DEBT-049 (закрыт) и DEBT-051 (прочие поля).

**Что сделать:** правки #1, #2 в P8 и #1 в заметке — ниже.

**Изменения:**

Правка #1, `P8-формат-ввода-json.md:214-216`:

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #1 до -->
````markdown
- `thermal.L_degas` — любой знак (физически); L < 0 — предупреждение в журнале, расчёт идёт. Для Стендинга L > 0: $p_b$ растёт с T, растворение газа экзотермично, дегазация поглощает теплоту; L < 0 возможен для систем, где растворимость газа растёт с T
- `initial_conditions.T0` > 0
- для шести параметров $c_p$, $(\rho c_p)_s$, λ литералы JSON `NaN` и `Infinity` отвергаются теми же проверками
````
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #1 после -->
````markdown
- `thermal.L_degas` — конечное, любой знак (физически); L < 0 — предупреждение в журнале, расчёт идёт. Для Стендинга L > 0: $p_b$ растёт с T, растворение газа экзотермично, дегазация поглощает теплоту; L < 0 возможен для систем, где растворимость газа растёт с T
- `thermal.mu_JT_oil`, `thermal.mu_JT_gas` — конечные, любой знак (DEBT-049). $\mu_{JT,o} > 0$ — предупреждение в журнале, расчёт идёт: $\mu_{JT} = v(\alpha T - 1)/c_p$ (`problem_statement.tex`, `eq:muJT_def`), у нефти $\alpha T \approx 0.3$ и $\mu_{JT,o} \approx -4\cdot10^{-7}$ К/Па (нагрев при дросселировании); положительный знак — вероятно $\varepsilon = -\mu_{JT}$ из литературы (Шарафутдинов и др., 2019). $\mu_{JT,g} < 0$ — без предупреждения: у газа законно выше давления инверсии
- `initial_conditions.T0` > 0
- для девяти тепловых параметров ($c_p$, $(\rho c_p)_s$, λ — DEBT-047; $L$, $\mu_{JT}$ — DEBT-049) литералы JSON `NaN`, `Infinity`, `-Infinity` отвергаются теми же проверками, сообщение называет параметр. Прочие числовые поля конфига NaN пропускают — [[DEBT-051]]
````

Правка #2, `P8-формат-ввода-json.md:313-314` — образец JSON:

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #2 до -->
````json
        "mu_JT_oil": 4.0e-7,
        "mu_JT_gas": -4.0e-6,
````
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #2 после -->
````json
        "mu_JT_oil": -4.0e-7,
        "mu_JT_gas": 4.0e-6,
````

Правка #1, заметка о нефизичной температуре, `:49`:

<!-- правка vault/knowledge/debugging/нефизичная температура доходила до истории молча — проверка T ловит грубые ошибки, остальное проверка ввода.md #1 до -->
````markdown
- $L$ = NaN или $\mu_{JT}$ = NaN — отказ scipy без имени параметра: громкий, но неинформативный. Знак $L$ и $\mu_{JT}$ не ограничен; конечность всех тепловых скаляров — отдельная запись, если понадобится.
````
<!-- правка vault/knowledge/debugging/нефизичная температура доходила до истории молча — проверка T ловит грубые ошибки, остальное проверка ввода.md #1 после -->
````markdown
- $L$ = NaN или $\mu_{JT}$ = NaN давали отказ scipy без имени параметра — закрыто [[DEBT-049]]: $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ проверяются на конечность при загрузке, знак не ограничен; при $\mu_{JT,o} > 0$ — предупреждение (вероятный знак $\varepsilon = -\mu_{JT}$ из литературы). NaN в прочих числовых полях конфига (гидродинамика, начальные условия, шаг по времени) проходит проверку ввода — [[DEBT-051]].
````

**Проверка после этого шага:**
- Регресс: `--collect-only -q` (шаг меняет только документы) — 1494.
- Правки шага — только два файла vault: `git diff --stat` после коммита шага 1 (или `git diff --stat -- vault/knowledge`) показывает P8 и заметку о нефизичной температуре, без файлов кода.

**Подводные камни:** имя файла заметки о нефизичной температуре содержит длинное русское название с «—» — в PowerShell брать в кавычки.

**Зависимости:** требует — ничего (можно параллельно с шагом 1); блокирует — ничего.

**Оценка:** 3 правки, ~10 минут.

### Шаг 3: Зелёный замер и vault задачи

**Цель:** подтвердить пробой, что 9 случаев отвергаются при загрузке, а остальное поведение (эталон, раздел 2) не изменилось.

**Файлы:**
- `vault/issues/debt-049/probes/green_state.out.txt` (новый)
- запись DEBT-049 в реестре, этот план (статус), `vault/issues/debt-049/05-comment-done.md` — по контракту `/implement`

**Что сделать:**
1. Из `numerical_solver/` worktree:
   ```powershell
   $env:PYTHONIOENCODING = "utf-8"; <python> ..\vault\issues\debt-049\probes\red_state.py > ..\vault\issues\debt-049\probes\green_state.out.txt
   ```
   (~4 мин: раздел 2 — 17 случаев с дроблением шага до dt/512.) Первая строка — `Код: …\.worktrees\debt-049\numerical_solver\…` — сверить, что это worktree.
2. Сравнить с `red_state.out.txt`:
   - раздел 1, обе таблицы: эталон — построчно как в красном замере; 9 случаев — `load_config: ValueError: thermal.<параметр> должно быть конечным числом (знак любой), получено nan|inf|-inf  [config.py:385]` (строка `raise` после правки; так дала проверка плана, этап 4);
   - раздел 2 — построчно как в красном замере (правка эти поля не трогает).

   Предупреждение о $\mu_{JT,o} > 0$ проба не показывает: в её конфигах $\mu_{JT,o} = -4\cdot10^{-7}$, а дочерний процесс отключает журнал (`logging.disable`). Его проверяет `test_positive_mu_JT_oil_warns`.
3. Записать итог в реестр и комментарий issue.

**Проверка после этого шага:** код не меняется — регресс не нужен. Полный прогон — в конце (`/implement` §3.1): ожидание **1494 passed** (фикстура `results` — сквозные расчёты конфигов примеров; все конечны, $\mu_{JT,o} \le 0$).

**Зависимости:** требует — шаг 1.

**Оценка:** ~10 минут.

## Тестовая стратегия

**Тест:** `test_nonfinite_scalar_rejected` ×9
**Файл:** `numerical_solver/tests/test_config.py` (существующий), класс `TestValidationThermal`
**Сценарий:** `_minimal_raw()`, в `thermal` один из `L_degas`, `mu_JT_oil`, `mu_JT_gas` = NaN, +inf, −inf
**Ожидание:** `ValueError`, сообщение содержит `thermal.<параметр>` и «конечным»
**Baseline:** до правки — `DID NOT RAISE` (load_config проходит; красная проба — отказ scipy в `run`)
**Предотвращает:** возврат к отказу без имени параметра; удаление одного из трёх имён из цикла

**Тест:** `test_nonfinite_no_sign_warning` ×2
**Файл:** там же
**Сценарий:** `L_degas = -inf`; `mu_JT_oil = +inf` (значения, которые попали бы под предупреждение о знаке); журнал `gpn_multiphase_solver` на уровне WARNING
**Ожидание:** `ValueError` с `thermal.<параметр>`; записей WARNING нет
**Baseline:** до правки — `DID NOT RAISE` (для $L = -\infty$ — ещё и предупреждение о знаке)
**Предотвращает:** перестановку проверки конечности после предупреждений о знаке

**Тест:** `test_positive_mu_JT_oil_warns`
**Файл:** там же
**Сценарий:** `mu_JT_oil = 4e-7` (знак $\varepsilon = -\mu_{JT}$ из литературы)
**Ожидание:** загружается (не отказ), значение сохранено; в журнале WARNING с `thermal.mu_JT_oil`
**Baseline:** до правки — загружается без предупреждения (тест падает на проверке текста журнала)
**Предотвращает:** молчаливый возврат знака $\varepsilon$; превращение предупреждения в отказ

**Тест:** `test_negative_mu_JT_gas_no_warning`
**Файл:** там же
**Сценарий:** `mu_JT_oil = -4e-7`, `mu_JT_gas = -4e-6` (газ выше давления инверсии)
**Ожидание:** загружается, значения сохранены, записей WARNING нет
**Baseline:** проходит и до правки
**Предотвращает:** превращение проверки конечности в проверку знака; ложное предупреждение для газа или для нормальной нефти

**Граничный случай** $\mu_{JT,o} = 0$ (умолчание `ThermalConfig`, примеры 01, 07, 09): без предупреждения — покрыт существующим `test_nonnegative_L_no_warning` ×2 (`_minimal_raw` не задаёт $\mu_{JT}$, проверяет отсутствие WARNING) и `test_load_config_passes`.

**Регрессия (без изменений):** `TestValidationThermal::test_invalid_rejected` ×13, `test_zero_conductivity_accepted`, `test_negative_L_warns` (конечное $L < 0$ — предупреждение остаётся), `test_nonnegative_L_no_warning` ×2; `TestBaselineThermal` (чтение $\mu_{JT}$, $L$ из baseline); быстрый уровень — `tests/test_examples.py::TestConfigs::test_load_config_passes` (все конфиги примеров); полный уровень — фикстура `results`.

## Критерии завершения

- [ ] Шаги 1–3 выполнены
- [ ] Новые тесты: 13 passed; `tests/test_config.py` — 147 passed
- [ ] Быстрый уровень: 1244 passed, 250 deselected; полный — 1494 passed (база `521cd26`; при другой базе — её итог +13)
- [ ] Зелёный замер `green_state.out.txt`: 9 случаев — `load_config: ValueError: thermal.…`; эталон и раздел 2 — как в красном
- [ ] При $\mu_{JT,o} > 0$ — предупреждение в журнале с `thermal.mu_JT_oil`, расчёт не прерывается; при $\mu_{JT,g} < 0$ — без предупреждения
- [ ] P8 §5 — девять параметров, $\mu_{JT}$ и предупреждение о $\mu_{JT,o} > 0$ упомянуты; образец JSON — `-4.0e-7` / `4.0e-6`
- [ ] Заметка о нефизичной температуре: пункт про NaN в $L$, $\mu_{JT}$ закрыт ссылкой на DEBT-049, DEBT-051
- [ ] Прототип не тронут (`git diff --stat` — без `HydroSolverPrototype/`)
- [ ] Vault: статус DEBT-049, план — «реализован»; комментарий в issue #81

## Обнаруженные проблемы

1. **NaN в прочих числовых полях конфига проходит `_validate`** — зарегистрировано как [[DEBT-051]] (решение пользователя 3). Проверки вида `if v <= 0: raise` NaN пропускают: сравнение с NaN ложно. Замер — раздел 2 `red_state.out.txt` (6 МПа, 24 ч):
   - `porosity`, `rho_o_std`, `rho_g_std`, `co_undersaturated`, `n_o`, `n_g`, `p0`, `T0`, `Rs0`, `skin`, `history.p_wf` (11 полей) — `run: RuntimeError: HydroSolver не сошёлся при дроблении шага до dt/512 …` после девяти уровней дробления первого шага; сообщение советует увеличить `numerics.max_retries` или уменьшить `dt_integration` — ложный след;
   - `dt_integration`, `history.dt` — `run: ValueError: cannot convert float NaN to integer [simulator.py:75]`;
   - `r_well`, `R_ext`, `h`, `permeability` — `from_config: ValueError: invalid radial grid parameters [grid.py:8]` (прототип, без имени параметра);
   - `S_or`, `S_gc`, `kro_max`, `krg_max` — `from_config: ValueError` прототипа с именем параметра (английский текст);
   - `start_day`, `dt_min`, `dt_max` — расчёт проходит, числа как у эталона: поля нигде не читаются.

   DEBT-049 не блокирует.
2. **`time.start_day` — мёртвое поле конфига**: grep по `numerical_solver/**/*.py` — только объявление (`config.py:132`) и тест умолчания (`test_config.py:158-159`). Дописано в [[DEBT-008]] (мёртвые поля конфига) по решению пользователя 3. DEBT-049 не блокирует.

## Проверка плана

Проба `vault/issues/debt-049/probes/plan_check.py` применяет правки плана к текстам файлов в памяти (по меткам `<!-- правка <файл> #N до|после -->`), файлы проекта не меняет. Запуск из `numerical_solver/`:

```powershell
$env:PYTHONIOENCODING = "utf-8"; .venv\Scripts\python ..\vault\issues\debt-049\probes\plan_check.py --fast
```

Результат аудита 1 на `521cd26` (2026-10-10; правки плана после решения пользователя 4; при планировании на `7b34a33` прогон без предупреждения о $\mu_{JT,o}$ дал согласованные числа — 6 правок, 10 failed / 145 passed, быстрый 1179):

1. **Правки плана:** все 7 меток («до» каждой найдено в своём файле ровно 1 раз): `test_config.py` #1, #2; `io/config.py` #1, #2; P8 #1, #2; заметка о нефизичной температуре #1. Самая длинная добавленная строка кода — 88 символов.
2. **`test_config.py` плана на текущем коде:** 12 failed, 135 passed — падают 9 × `test_nonfinite_scalar_rejected`, 2 × `test_nonfinite_no_sign_warning`, `test_positive_mu_JT_oil_warns`; `test_negative_mu_JT_gas_no_warning` проходит (ожидаемо).
3. **На коде с правками:** 147 passed; с настройками pytest проекта, хуком `conftest.py` и `-m "not slow"` — тоже 147 passed (все новые тесты — в быстром уровне).
4. **Раздел 1 пробы на коде с правками:** эталоны при 10 и 6 МПа — те же строки, что в `red_state.out.txt`; все 18 случаев — `load_config: ValueError: thermal.<параметр> должно быть конечным числом (знак любой), получено nan|inf|-inf  [config.py:385]` (385 — строка `raise` после правки).
5. **Быстрый уровень существующих тестов на коде с правками:** 1231 passed, 250 deselected, 1 warning, 79 с — ни один существующий тест не задевает новое предупреждение. Предупреждение pytest — `PytestRemovedIn10Warning` о фикстуре класса; по замеру DEBT-047 оно есть и без подмены, к задаче не относится.

Итого ожидания плана: `test_config.py` 134 → 147, всего 1481 → 1494, быстрый уровень 1231 → 1244.
