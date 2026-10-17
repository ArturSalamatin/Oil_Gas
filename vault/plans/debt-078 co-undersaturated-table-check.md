---
tags:
  - план
  - проверка-входа
date: 2026-10-17
issue: DEBT-078
github: 130
branch: refactor/debt-078/co-undersaturated-table-check
status: реализован
worktree: .worktrees/debt-078
audit:
  date: 2026-10-17
  round: 2
  base: f5239de
  found: 6
  auto-fixed: 5
  manual-required: 1   # размещение после влития DEBT-076 — решено пользователем в ходе аудита
---

# DEBT-078: `pvt.co_undersaturated` — отказ при табличном PVT и при $c_o < 0$

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-078 в `vault/roadmap/известные баги и технический долг.md` и тело issue #130 (`vault/issues/debt-078/01-issue-body.md`).
3. Образцы: отказ опции Стендинга при таблице — `test_beal_with_table_raises` и проверка `mu_o_undersaturated` в `create_pvt` ([[feat-027 undersaturated-oil-viscosity|FEAT-027]]); отказ по знаку сжимаемости в `_validate` — [[debt-068 rock-compressibility-sign]] (`rock.compressibility` ≥ 0, тесты `TestValidationRock`).
4. Worktree и ветка — по `/implement`: базовая ветка `numerical_scheme/implementation`, ветка `refactor/debt-078/co-undersaturated-table-check`, каталог `.worktrees/debt-078`.
5. Python: `.venv\Scripts\python` основного каталога `numerical_solver/`. Тесты — из `numerical_solver/` worktree, pytest берёт код worktree. Пробы вне pytest — с `PYTHONPATH` на `numerical_solver` worktree (печатают путь пакета первой строкой). Прототип не меняется: его тесты и регрессия не нужны.
6. Исходная точка (аудит 2, база `f5239de` — после влития FEAT-033 `7036854`, DEBT-080 `ecb4c36` и DEBT-076 `f6e9aa0`): `.venv\Scripts\python -m pytest tests/ --collect-only -q` — **2129** тестов; `-m "not slow" --collect-only -q` — **1853**. Цель — **2136** / **1860** (+7). Если база снова ушла — число тестов взять по факту, цель = база + 7, и до шага 1 прогнать `plan_apply.py <worktree>` без `--write`: все якоря «OK». Перед шагом 1 — быстрый уровень (`-m "not slow" -q`): все зелёные, время запомнить (аудит 2 с правками плана на `f5239de` — §11, `audit2_fast.out.txt`).
7. Правки шагов 1–3 собраны в пробе `vault/issues/debt-078/probes/plan_apply.py` — те же блоки «До → После», что ниже, символ в символ. Можно править руками по плану, можно применить пробой из корня основного каталога: `numerical_solver\.venv\Scripts\python vault\issues\debt-078\probes\plan_apply.py .worktrees\debt-078` (проверка: каждый «До» найден ровно один раз), затем то же с `--write`. Путь к дереву — аргументом; README правится только с `--readme` (шаг 3). Пробы `vault/issues/debt-078/probes/` на 2026-10-17 не в git — `/implement` коммитит их в базу вместе с планом до создания worktree.
8. Шаг 1, затем 2, 3, 4. После шагов 1 и 2 — быстрый уровень; после шага 3 — `--collect-only` и `tests/test_eq_references.py`. Полный прогон — в конце (`/implement` §3.1).

## 1. Задача

### 1.1. Что не так

**Табличный PVT.** Поле `pvt.co_undersaturated` (сжимаемость недонасыщенной нефти $c_o$, 1/Па) читает только ветвь `"standing"` функции `create_pvt` (`numerical_solver/gpn_multiphase_solver/factory.py:105`) → `StandingFullPVT` (`pvt/standing.py`), где при $p \ge p_b(R_s)$ $B_o = B_o(p_b)\,e^{-c_o (p - p_b)}$ (`StandingFullPVT.Bo`, `pvt/standing.py:102-112`). В ветви `"table"` (`factory.py:125-162`) $B_o$ выше $p_b$ задают недонасыщенные ветви таблицы PVTO, поле не читается — и никто об этом не сообщает. Соседнее поле той же группы, `mu_o_undersaturated`, в ветви `"table"` даёт `ValueError` (`factory.py:126-131`, FEAT-027; комментарий: «молча игнорировать опцию нельзя»).

**Знак.** `_validate` (`io/config.py:499`) проверяет у `co_undersaturated` только тип и конечность (`_check_numeric_fields`, DEBT-051). У `rock.compressibility` при $c_r < 0$ — отказ (`io/config.py:546-550`, DEBT-068). $c_o = -(1/B_o)\,\partial B_o/\partial p$ при постоянном $R_s$ (`eq:co_cg`, `problem_statement.tex`) — сжимаемость жидкости при постоянном составе; условие механической устойчивости $(\partial p/\partial V)_T < 0$ требует $c_o \ge 0$ (Ландау, Лифшиц, т. V, §21). Отрицательное число в конфиге — ошибка знака, а не свойство нефти.

Условие корректности уравнения давления слабее: в недонасыщенной зоне $C_p = \phi\,(c_r + c_o)/B_g$, и $C_p \ge 0 \Leftrightarrow c_o \ge -c_r$ (абзац под `eq:c_ot`, `problem_statement.tex`). При $c_o < -c_r$ уравнение давления — обратное уравнение теплопроводности, неявный шаг вырождается на последовательности $\Delta t$ (механизм BUG-019). Отказ по знаку $c_o$ строже этого условия: конфиг с $c_r > |c_o|$, $c_o < 0$ корректен математически, но отвергается — по физике жидкости (так задумано, решение 2 в §1.3).

### 1.2. Замер

Пробы — `vault/issues/debt-078/probes/`, база `8ddb08d`.

**A. Табличный PVT** (`co_undersaturated.py`, `co_undersaturated_8ddb08d.out.txt`; совпадает дословно с замером при регистрации на `130b88d`, `co_undersaturated.out.txt`). Конфиг примера 04 (`pvt.model = "table"`, $p_0$ = 20 МПа, $R_{s,0}$ = 30), $c_o$ = 0 и $3.3\cdot10^{-9}$ 1/Па: `create_pvt` и `SimulatorFactory.from_config` — без отказа и без предупреждений (перехвачены `warnings` и журнал `logging`); $B_o$ на ветви $R_s = 30$ от $p_b$ до $p_0$: `[1.2 1.198667 1.197333 1.196 1.194667 1.193333]` в обоих случаях, $\max|\Delta B_o| = 0$.

**B. $c_o < 0$, Стендинг** (`co_undersaturated.py` п. 2; `co_negative_run.py`, `co_negative_run.out.txt`; зависимость от шага — `audit1_dt_dependence.py`, `audit1_dt_dependence.out.txt`, аудит 1). Пример 03 (Стендинг, $c_r = 0$, $R_{s,0} = 50$, $p_{wf}$ = 8 МПа, 1 сут). При $c_r = 0$ **любое** $c_o < 0$ даёт $C_p < 0$ в недонасыщенной зоне (§1.1), поэтому исход зависит от шага по времени:

| $c_o$, 1/Па | `load_config` | фабрика | расчёт 1 сут, `dt_integration` 3600 / 1800 / 900 с |
|---|---|---|---|
| 0 | принят | — | проходит при всех трёх: $p(r_0)$ = 8.0466 МПа, $T(r_0)$ = 352.278 / 352.283 / 352.285 К, двухфазных ячеек 16 |
| −1e-9 | принят | одно предупреждение `_warn_negative_compressibility` (BUG-019): «отрицательная сжимаемость недонасыщенной нефти … Расчёт продолжается» | 3600 и 1800 с — **молча проходит** (8.0463 МПа, 352.266 / 352.271 К, 17 ячеек); 900 с — **отказ** на $t$ = 0.015 сут после дробления шага до dt/512. $B_o$ выше $p_b$ растёт с $p$: 1.1672 → 1.1796 на 9.4–20 МПа |
| −3.3e-9 (знак значения примеров 17, 20) | принят | то же предупреждение | **отказ** при всех трёх ($t$ = 0.136 / 0.075 / 0.105 сут) после дробления шага до dt/512 с советом увеличить `max_retries`, без имени параметра |

То есть $c_o = -10^{-9}$ проходит не потому, что задача корректна, а потому, что шаг не попал на вырождение (BUG-019: «якобиан шага вырождается на последовательности $\Delta t$»).

**C. Ошибка единиц** (`co_magnitude.py`, `co_magnitude.out.txt`; пример 03, 6 ч) — к задаче не относится (§1.3, решение 3), записано для полноты: $c_o = 10^{-5}$ 1/Па (число из справочника без перевода) — $B_o(p_0) = 1.4\cdot10^{-46}$, расчёт **проходит** с правдоподобной $T(r_0)$ = 350.38 К и без газа (предупреждение numpy «overflow», в журнал не попадает); $10^{-4}$ и $10^{-3}$ — отказ с советом про дробление шага.

### 1.3. Решения пользователя (2026-10-17)

1. **Табличный PVT и $c_o \ne 0$ — отказ в `create_pvt`**, рядом с проверкой `mu_o_undersaturated`: правило «опция только для Стендинга» — в одном месте (вариант 1 issue #130).
2. **$c_o < 0$ — отказ в `_validate`** по образцу DEBT-068 (вариант 3 issue #130). Предупреждение BUG-019 об отрицательной сжимаемости остаётся — для таблиц и корреляций.
3. **Верхнюю границу $c_o$ (ошибка единиц, замер C) не регистрировать** — ни в этой задаче, ни отдельной.
4. **`numerical_solver/README.md`** (вне git; в worktree его нет) — править в основном каталоге без коммита (шаг 3).

### 1.4. Мотивация и приоритет

Пользователь, задавший $c_o$ при табличном PVT, считает сжимаемость нефти учтённой; расчёт идёт по таблице. Два поля одной группы ведут себя по-разному. $c_o < 0$ даёт либо молча неверный расчёт с одним предупреждением, либо отказ шага с ложным советом. Приоритет низкий: ни один конфиг проекта этого не делает.

## 2. Текущее состояние

### 2.1. Конфиги проекта

`co_undersaturated` задают только конфиги Стендинга: примеры 17, 20 (`3.3e-09`), `tests/data/bug020_rs300/config.json` (`3.3e-09`), `configs/val001.json` (`0.0`). Табличные (`examples/`, `configs/`, `tests/data/`) поле не задают. Тесты, меняющие поле в коде (`test_examples.py:1403`, `:2781`, `:2842`; `test_energy.py`, `test_pvt.py`, `test_val001.py` и др.), — Стендинг и $c_o \ge 0$. Книга Excel (FEAT-033, ветка `feat/feat-033/workbook-input-format`) поле не задаёт: `NOT_FROM_WORKBOOK["pvt.co_undersaturated"] = "только Стендинг"` (план FEAT-033); файлы задачи на ветке FEAT-033 не меняются (`git diff --stat 8ddb08d...feat/feat-033/workbook-input-format`).

### 2.2. Код

| Файл | Строки | Что |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/factory.py` | 105–165 | `create_pvt`; 117 — `co_undersaturated` в `StandingFullPVT`; 126–131 — отказ для `mu_o_undersaturated` при таблице |
| `numerical_solver/gpn_multiphase_solver/factory.py` | 61, 354–396 | `_warn_negative_compressibility` (BUG-019): $c_{ot}$, $c_g$ и $c_o$ недонасыщенной нефти по объекту PVT — **не меняется** |
| `numerical_solver/gpn_multiphase_solver/io/config.py` | 67–69 | `PVTConfig`: комментарий «Для Standing» у `co_undersaturated`, `mu_o_undersaturated` |
| `numerical_solver/gpn_multiphase_solver/io/config.py` | 499, 534–550, 552–575 | `_validate`; образец — отказ при $c_r < 0$ (DEBT-068); блок «PVT: плотности» (DEBT-076, `pc = cfg.pvt`) — сюда встаёт проверка $c_o$ (на `f5239de`) |
| `numerical_solver/gpn_multiphase_solver/pvt/standing.py` | 56, 102–112 | $B_o$ выше $p_b$ по $c_o$ — **не меняется** |

Вызовы `create_pvt` (`grep "create_pvt("`): `factory.py:57` (`from_config`), `report/pvt.py:87`, тесты (`test_factory_standing_hydro.py`, `test_factory_prototype.py:293`, `test_isobar_radius.py:124`, `test_examples.py:1106`, `test_public_api.py:158`, `test_rs_analytics.py:43`), `deliverables/rs150_for_sergey/make_tables.py:55` (вне git). Все — на конфигах проекта, табличных с $c_o \ne 0$ среди них нет.

Порядок: `load_config` → `_validate` (отказ при $c_o < 0$ — шаг 2) → `from_config` → `create_pvt` (отказ при таблице и $c_o \ne 0$ — шаг 1). Конфиг, собранный в коде без `load_config`, `_validate` не проходит (P8 §5: «Проверки — только на пути JSON → `load_config` → `from_config`»); отказ `create_pvt` он получает.

### 2.3. Тесты, которые касаются кода

| Тест | Файл | Что проверяет |
|---|---|---|
| `TestFactoryStandingHydro::test_beal_with_table_raises` | `tests/test_factory_standing_hydro.py:113-122` | образец: `mu_o_undersaturated = "beal"` при `configs/table_pvt` → `ValueError` |
| `TestFactoryStandingHydro::test_beal_reaches_pvt` | там же, `:99-111` | опция Стендинга доходит до PVT — не меняется |
| `TestBaselinePVT::test_co_default` | `tests/test_config.py:96-98` | умолчание 0 — не меняется |
| `TestValidationRock::test_negative_compressibility_rejected`, `test_nonnegative_compressibility_accepted` | `tests/test_config.py:373-410` | образец отказа и приёма по знаку (DEBT-068) |
| табличные тесты на `configs/table_pvt`, примеры 04–09, 13–18 | `tests/test_factory_prototype.py`, `tests/test_examples.py` и др. | $c_o = 0$ (умолчание) при таблице проходит — после шага 1 то же |
| `TestFactoryWarning::test_inconsistent_undersaturated_table_warns` | `tests/test_pvt_consistency.py:199-206` | недонасыщенная ветвь `_warn_negative_compressibility` на табличных данных ($c_o \approx -1.7\cdot10^{-9}$ из ветвей PVTO, поле `co_undersaturated` не задано) — сторож того, что предупреждение для таблиц осталось (§5, п. 5) |
| `test_excel_not_stricter_than_program` | `tests/test_workbook_format.py:249-275` (FEAT-033) | перебирает только поля книги (`PARAMS`); `co_undersaturated` в книге нет (`NOT_FROM_WORKBOOK`) — проверка $c_o$ его не меняет (§5, п. 12) |
| `tests/test_eq_references.py` | — | метки в комментариях кода, тестов и заметок `vault/knowledge/` (шаги 1–3 ссылаются на `eq:co_cg`, `eq:c_ot`) |

| `TestValidationPVT` (DEBT-076, влита) | `tests/test_config.py:414-460` | плотности при ст. у. > 0; новый класс DEBT-078 встаёт сразу после него (шаг 2) |

## 3. Целевое состояние

- `create_pvt`, ветвь `"table"`: `co_undersaturated != 0` → `ValueError` «co_undersaturated = … 1/Па — только для model = 'standing'; у табличного PVT B_o выше p_b задают недонасыщенные ветви таблицы. Уберите поле из секции pvt.» Явный 0 проходит (неотличим от умолчания `PVTConfig`).
- `_validate`: `co_undersaturated < 0` → `ValueError` «pvt.co_undersaturated = … 1/Па < 0: сжимаемость недонасыщенной нефти … должна быть ≥ 0 …» — при любой модели PVT, без допуска.
- `_warn_negative_compressibility` — без изменений (таблицы, корреляции, конфиги в коде).
- Тестов: 2129 → **2136**, быстрый уровень 1853 → **1860** (+7: 6 в `test_config.py`, 1 в `test_factory_standing_hydro.py`; база `f5239de`, после влития DEBT-076). Истории примеров не меняются: меняется только проверка ввода, ни один конфиг её не задевает.
- Документы: P8 (§2 — поля Стендинга при таблице; §5 — две строки таблицы и абзац о $c_o$), `json-config-schema.md`, `pvt-корреляции-стендинг.md`, README пакета п. 3.1.

## 4. Варианты

Разобраны в issue #130 и выбраны пользователем (§1.3). Кратко отвергнутое:

- предупреждение вместо отказа при таблице — два поля группы по-прежнему вели бы себя по-разному, предупреждение теряется в журнале длинного расчёта;
- отказ при таблице в `_validate` (с переносом туда же проверки `mu_o_undersaturated`) — раньше, при загрузке, но шире правка и правило ушло бы от `create_pvt`, которую вызывают и без `load_config` (диагностика, `report/pvt.py`, DEBT-011);
- оставить предупреждение BUG-019 при $c_o < 0$ — расчёт либо молча идёт с неверным знаком, либо падает с ложным советом (§1.2, B).

## 5. Подводные камни

| # | Пункт | Оценка |
|---|---|---|
| 1 | **DEBT-076 влита** (#129, `f6e9aa0`, 2026-10-17): в `_validate` — блок «PVT: плотности при стандартных условиях» после проверки $c_r$ (`io/config.py:552-575` на `f5239de`, `pc = cfg.pvt`); в `test_config.py` — класс `TestValidationPVT` (`:414-460`) и строка докстринга модуля; в P8 §5 — группа «PVT (…)» в строке `_validate` и абзац «PVT»; в `json-config-schema.md` — строка «Ограничения». Шаги 2–3 ставят $c_o$ **в эти группы** (решение пользователя, аудит 2): проверка — в блок «PVT» после плотностей (заголовок блока расширяется), класс — после `TestValidationPVT`, запись — в группу «PVT (…)», абзац — после абзаца «PVT», знак — в строку «Ограничения». Якоря шагов 2–3 сняты с влитого кода (`plan_apply.py` на `f5239de` — все «OK»). Размещение аудита 1 («до мест DEBT-076», независимое от порядка реализации, `audit1_order_check.py`) больше не нужно — порядок известен. **Класс назван `TestValidationOilCompressibility`, а не `TestValidationPVT`:** второй одноимённый класс в модуле молча заменил бы первый | ✅ |
| 2 | Порядок проверок: `_validate` раньше `create_pvt`; при таблице и $c_o < 0$ сообщение — о знаке (тест `test_negative_co_rejected_for_table`) | ✅ |
| 3 | Явный `0.0` и `-0.0` при таблице: `-0.0 != 0.0` и `-0.0 < 0` ложны — проходят обе проверки; вреда нет | ✅ |
| 4 | Путь Стендинга при $c_o \ge 0$ не меняется: примеры 17, 20, `bug020_rs300`, `val001` — прежние числа (медленные тесты в полном прогоне) | ✅ |
| 5 | `_warn_negative_compressibility` не удалять: недонасыщенная ветвь нужна для таблиц ($c_o$ из ветвей PVTO) и для конфигов, собранных в коде. На пути JSON со Стендингом она больше не сработает — это ожидаемо | ✅ |
| 6 | Конфиг в коде без `load_config` (тесты, примеры): $c_o < 0$ со Стендингом по-прежнему проходит с предупреждением BUG-019 — так задумано (P8 §5) | ✅ |
| 7 | Все вызовы `create_pvt` (§2.2) — на конфигах без $c_o \ne 0$ при таблице | ✅ |
| 8 | `numerical_solver/README.md` вне git: в worktree его нет; правка — в основном каталоге (`plan_apply.py <корень основного каталога> --readme`), без коммита. Перед правкой — проверка якоря (без `--write`): файл могла изменить сессия FEAT-031 | ⚠️ адресован (шаг 3) |
| 9 | Сторож меток `test_eq_references.py`: новые комментарии и заметки ссылаются на `eq:co_cg`, `eq:c_ot` — метки есть в `problem_statement.tex` (`:569`, `:600`); при эмуляции сторож зелёный (§11) | ✅ |
| 10 | Импорты, конфиги, pyproject, прототип — не меняются | ✅ |
| 11 | Производительность — не затронута (две проверки скаляра) | ✅ |
| 12 | FEAT-033 влита (`7036854`): `test_workbook_format.py::test_excel_not_stricter_than_program` (`:250-276`; после DEBT-076 — `assert stricter == set()`) сравнивает пределы книги с `load_config` только по полям книги; `co_undersaturated` — в `NOT_FROM_WORKBOOK`, тест не меняется (аудит 2: зелёный вместе с новыми тестами). Проверка «каждое поле конфига — ровно в одном месте» не затронута: новых полей нет | ✅ |
| 13 | Проверка $c_o$ пользуется `pc` блока «PVT» (DEBT-076, `pc = cfg.pvt` — выше в том же блоке); своей переменной не заводит. Текст отказа — «должна быть ≥ 0», у плотностей — «должна быть > 0»: тест `test_negative_co_rejected_for_table` по тексту их не спутает | ✅ |
| 14 | Правило докстрингов публичного интерфейса в стиле NumPy (`CLAUDE.md`, «Файлы и код», правка 2026-10-17 — на момент аудита 2 не закоммичена): `create_pvt` и `load_config` — публичные (`tests/test_public_api.py`). План их докстрингов **не меняет**: перевод публичного интерфейса в стиль NumPy — FEAT-031 (в пакете таких докстрингов пока нет ни одного); при переводе в разделы исключений `create_pvt` и `load_config` войдут и отказы DEBT-078. Новые тесты — не публичный интерфейс; многострочные докстринги тестов — как у соседних (`test_beal_with_table_raises`, `TestValidationPVT`) | ✅ |

## 6. Шаги

### Шаг 1: отказ `create_pvt` при табличном PVT и $c_o \ne 0$, тест

**Цель:** ненулевое `co_undersaturated` при `pvt.model = "table"` — `ValueError`, как `mu_o_undersaturated`.

**Файлы:** `numerical_solver/gpn_multiphase_solver/factory.py`, `numerical_solver/tests/test_factory_standing_hydro.py`.

**Контекст:** у таблицы недонасыщенные ветви PVTO задают $B_o$ выше $p_b$ сами; $c_o$ к ним неприменима. Проверка — сразу после проверки `mu_o_undersaturated`, до чтения CSV: отказ не зависит от таблиц.

**Изменения.** `factory.py`, ветвь `elif pc.model == "table":` функции `create_pvt`.

До:
```python
        if pc.mu_o_undersaturated != "none":
            raise ValueError(
                f"mu_o_undersaturated = {pc.mu_o_undersaturated!r} — только для "
                f"model = 'standing'; у табличного PVT вязкость выше p_b задаёт таблица.")
        # CSV → BlackOilPVT (прототип) → PrototypePVTAdapter → TableFullPVT
```
После:
```python
        if pc.mu_o_undersaturated != "none":
            raise ValueError(
                f"mu_o_undersaturated = {pc.mu_o_undersaturated!r} — только для "
                f"model = 'standing'; у табличного PVT вязкость выше p_b задаёт таблица.")
        # То же для B_o (DEBT-078): выше p_b его задают недонасыщенные ветви
        # PVTO, c_o читает только StandingFullPVT.Bo. До DEBT-078 значение
        # пропускалось молча: пример 04 с c_o = 3.3e-9 1/Па давал B_o, побитово
        # равный c_o = 0 (vault/issues/debt-078/probes/co_undersaturated.out.txt).
        # Явный 0 проходит: от умолчания PVTConfig он неотличим и ничего не
        # меняет. Знак c_o при загрузке конфига проверяет _validate (io/config.py).
        if pc.co_undersaturated != 0.0:
            raise ValueError(
                f"co_undersaturated = {pc.co_undersaturated} 1/Па — только для "
                f"model = 'standing'; у табличного PVT B_o выше p_b задают "
                f"недонасыщенные ветви таблицы. Уберите поле из секции pvt.")
        # CSV → BlackOilPVT (прототип) → PrototypePVTAdapter → TableFullPVT
```

`test_factory_standing_hydro.py`, класс `TestFactoryStandingHydro` — новый тест после `test_beal_with_table_raises`.

До:
```python
        config = load_config(TABLE_PVT)
        config.pvt.mu_o_undersaturated = "beal"
        with pytest.raises(ValueError, match="mu_o_undersaturated"):
            create_pvt(config)


class TestStandingDeepDrawdownDenseGrid:
```
После:
```python
        config = load_config(TABLE_PVT)
        config.pvt.mu_o_undersaturated = "beal"
        with pytest.raises(ValueError, match="mu_o_undersaturated"):
            create_pvt(config)

    def test_co_with_table_raises(self):
        """co_undersaturated ≠ 0 при табличном PVT — ValueError (DEBT-078).

        Выше p_b у таблицы B_o задают её недонасыщенные ветви, c_o читает только
        StandingFullPVT. До DEBT-078 значение пропускалось молча: пример 04 с
        c_o = 3.3e-9 1/Па давал B_o, побитово равный c_o = 0
        (vault/issues/debt-078/probes/co_undersaturated.out.txt). c_o = 0 у
        табличных конфигов (умолчание) проходит — это проверяют остальные тесты
        на TABLE_PVT.
        """
        config = load_config(TABLE_PVT)
        config.pvt.co_undersaturated = 3.3e-9
        with pytest.raises(ValueError, match="co_undersaturated") as exc:
            create_pvt(config)
        # значение — как в конфиге: по нему пользователь найдёт поле
        assert "= 3.3e-09 1/Па" in str(exc.value)


class TestStandingDeepDrawdownDenseGrid:
```

`f"{3.3e-9}"` в Python — `3.3e-09`; утверждение о тексте проверено эмуляцией.

**Проверка после шага:**
- `pytest tests/test_factory_standing_hydro.py -q` — зелёный, +1 тест;
- Регресс: быстрый — 1854 passed (база 1853 + 1).

**Подводные камни:** §5, пп. 3, 7.

**Зависимости:** требует — ничего; блокирует — шаг 3 (документы описывают отказ).

**Оценка:** ~30 строк, ~15 минут.

### Шаг 2: отказ `_validate` при $c_o < 0$, комментарий `PVTConfig`, тесты

**Цель:** отрицательное `co_undersaturated` отвергается при загрузке конфига — при любой модели PVT.

**Файлы:** `numerical_solver/gpn_multiphase_solver/io/config.py`, `numerical_solver/tests/test_config.py`.

**Контекст:** по образцу DEBT-068 (`rock.compressibility` ≥ 0): отказ по знаку, без допуска, с полным именем поля и значением в тексте. Место — блок «PVT» в `_validate`, который завела DEBT-076 (влита `f6e9aa0`; `io/config.py:552-575` на `f5239de`): после цикла проверки плотностей, перед заголовком скин-фактора. Решение пользователя 2026-10-17 (аудит 2): все проверки секции `pvt` — в одном блоке. `pc = cfg.pvt` в блоке уже задан — проверка пользуется им. Заголовок блока расширяется: теперь в нём и плотности, и сжимаемость. Связь с $c_r$ (входят в $C_p$ вместе, §1.1) — в комментарии: $c_r$ проверен выше, в разделе породы. Класс тестов — сразу после `TestValidationPVT` (DEBT-076).

**Изменения.** `io/config.py`, `PVTConfig`.

До:
```python
    # Для Standing
    co_undersaturated: float = 0.0   # сжимаемость нефти при p > pb, 1/Па
    mu_o_undersaturated: str = "none"  # μ_o при p > pb: "none" | "beal" (FEAT-027)
```
После:
```python
    # Для Standing. При model = "table" выше p_b B_o и μ_o задаёт таблица:
    # c_o ≠ 0 или μ_o ≠ "none" — отказ create_pvt (factory.py; DEBT-078, FEAT-027)
    co_undersaturated: float = 0.0   # c_o ≥ 0 (_validate, DEBT-078) при p > pb, 1/Па
    mu_o_undersaturated: str = "none"  # μ_o при p > pb: "none" | "beal" (FEAT-027)
```

`io/config.py`, `_validate`, заголовок блока «PVT» (DEBT-076).

До:
```python
    # ── PVT: плотности при стандартных условиях (DEBT-076, P8 §5) ──
```
После:
```python
    # ── PVT: плотности при ст. у. (DEBT-076), сжимаемость нефти (DEBT-078); P8 §5 ──
```

`io/config.py`, `_validate`, конец блока «PVT» — после цикла плотностей, перед заголовком скин-фактора.

До:
```python
                f"{name} = {value} кг/м³: плотность {phase} при стандартных "
                f"условиях (не пластовая) должна быть > 0")

    # ── Скважина: скин-фактор (DEBT-056, P8 §5) ──
```
После:
```python
                f"{name} = {value} кг/м³: плотность {phase} при стандартных "
                f"условиях (не пластовая) должна быть > 0")

    # Сжимаемость недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p при постоянном
    # R_s ≥ 0 (DEBT-078, eq:co_cg problem_statement.tex): при постоянном составе
    # объём жидкости с ростом давления не растёт — условие механической
    # устойчивости (∂p/∂V)_T < 0; c_o < 0 — ошибка знака. В недонасыщенной зоне
    # C_p = φ(c_r + c_o)/B_g (абзац под eq:c_ot; c_r проверен выше, DEBT-068):
    # при c_o < −c_r C_p < 0 — задача некорректна, неявный шаг вырождается на
    # последовательности Δt. Проверка строже: c_o < 0 отвергается и при
    # c_r > |c_o|. Замер до DEBT-078 (vault/issues/debt-078/probes/
    # audit1_dt_dependence.out.txt; пример 03, Стендинг, c_r = 0, 1 сут):
    # c_o = −1e-9 — при dt_integration 3600 и 1800 с расчёт молча (одно
    # предупреждение фабрики, BUG-019), при 900 с — отказ после дробления шага
    # до dt/512 с советом увеличить max_retries; −3.3e-9 (значение примеров
    # 17, 20 с обратным знаком) — отказ при всех трёх шагах. Проверка — при
    # любой модели PVT: при таблице c_o ≠ 0 отвергает и create_pvt, но позже и
    # без слова о знаке; отрицательная c_o табличных данных — свойство таблицы,
    # о ней предупреждает фабрика (_warn_negative_compressibility, BUG-019).
    # Верхней границы нет: ошибку единиц (1e-5 1/Па вместо 1e-9) проверка не
    # ловит (vault/issues/debt-078/probes/co_magnitude.out.txt).
    if pc.co_undersaturated < 0:
        raise ValueError(
            f"pvt.co_undersaturated = {pc.co_undersaturated} 1/Па < 0: сжимаемость "
            f"недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p должна быть ≥ 0 — объём "
            f"нефти с ростом давления не растёт (вероятно, ошибка знака)")

    # ── Скважина: скин-фактор (DEBT-056, P8 §5) ──
```

`tests/test_config.py`, докстринг модуля — строка после строки DEBT-076.

До:
```python
- PVT: плотности при ст. у. pvt.rho_o_std, pvt.rho_g_std > 0 при любой модели PVT (DEBT-076).
```
После:
```python
- PVT: плотности при ст. у. pvt.rho_o_std, pvt.rho_g_std > 0 при любой модели PVT (DEBT-076).
- PVT: сжимаемость недонасыщенной нефти pvt.co_undersaturated ≥ 0 при любой модели (DEBT-078).
```

`tests/test_config.py`, новый класс между `TestValidationPVT` (DEBT-076) и `TestValidationInitial`.

До:
```python
        assert (cfg.pvt.rho_o_std, cfg.pvt.rho_g_std) == (rho_o, rho_g)


class TestValidationInitial:
```
После:
```python
        assert (cfg.pvt.rho_o_std, cfg.pvt.rho_g_std) == (rho_o, rho_g)


class TestValidationOilCompressibility:
    """pvt.co_undersaturated ≥ 0 (DEBT-078).

    Отдельно от TestValidationPVT (плотности, DEBT-076): другая величина и свой
    замер. Имя другое: второй одноимённый класс в модуле молча заменил бы первый.
    """

    @pytest.mark.parametrize("c_o", [
        # при c_r = 0 C_p < 0 в недонасыщенной зоне (абзац под eq:c_ot): расчёт
        # шёл молча с одним предупреждением фабрики (BUG-019) при dt_integration
        # 3600 и 1800 с, при 900 с — отказ шага; B_o выше p_b растёт с давлением
        -1e-9,
        # значение примеров 17, 20 с обратным знаком: отказ после дробления шага
        # до dt/512 с советом увеличить max_retries, при всех трёх шагах
        -3.3e-9,
        # наименьшее по модулю отрицательное число: проверка — по знаку, без допуска
        -5e-324,
    ], ids=["step_dependent", "sign_error_examples_17_20", "tiny"])
    def test_negative_co_rejected(self, tmp_path, c_o):
        """c_o < 0 → ValueError с полным именем поля и значением (DEBT-078).

        c_o = −(1/B_o)·∂B_o/∂p при постоянном R_s (eq:co_cg) ≥ 0: при постоянном
        составе объём жидкости с ростом давления не растёт. Комментарии к случаям —
        замер до DEBT-078 на примере 03 (Стендинг, c_r = 0), 1 сут
        (vault/issues/debt-078/probes/audit1_dt_dependence.out.txt).
        """
        raw = _minimal_raw()
        raw["pvt"]["co_undersaturated"] = c_o
        with pytest.raises(ValueError, match="pvt.co_undersaturated") as exc:
            load_config(_write_json(tmp_path, raw))
        # значение — как в конфиге: по нему пользователь найдёт ошибку
        assert f"= {c_o} 1/Па" in str(exc.value)

    def test_negative_co_rejected_for_table(self, tmp_path):
        """При pvt.model = "table" c_o < 0 отвергает _validate — с сообщением о знаке.

        Без проверки знака отказ дала бы только фабрика (create_pvt: c_o ≠ 0 при
        таблице) — позже и без слова о знаке. CSV-файлы не нужны: load_config
        их не читает.
        """
        raw = _minimal_raw()
        raw["pvt"] = {"model": "table", "rho_o_std": 850.0, "rho_g_std": 0.85,
                      "oil_pvt_file": "oil_pvt.csv", "gas_pvt_file": "gas_pvt.csv",
                      "co_undersaturated": -1e-9}
        with pytest.raises(ValueError, match="должна быть ≥ 0"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("c_o", [0.0, 3.3e-9], ids=["zero_default", "examples_17_20"])
    def test_nonnegative_co_accepted(self, tmp_path, c_o):
        """c_o = 0 и 3.3e-9 1/Па проходят: умолчание и значение примеров 17, 20."""
        raw = _minimal_raw()
        raw["pvt"]["co_undersaturated"] = c_o
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.pvt.co_undersaturated == c_o


class TestValidationInitial:
```

`_minimal_raw()` — Стендинг + Кори, $c_r$ не задано, плотности 850 / 0.85 (проходят проверку DEBT-076); `load_config` CSV не читает (`io/config.py:386-459`), поэтому табличный тест обходится без файлов. В табличном тесте плотности тоже 850 / 0.85 — отказ даёт именно проверка $c_o$ («должна быть ≥ 0»; у плотностей текст «должна быть > 0»).

**Проверка после шага:**
- `pytest tests/test_config.py -q` — зелёный, +6 тестов;
- Регресс: быстрый — **1860 passed** (база 1853 + 7); `--collect-only -q` — **2136**.

**Подводные камни:** §5, пп. 1, 2, 5, 6, 13, 14.

**Зависимости:** требует — ничего (от шага 1 не зависит, порядок — ради последовательной сверки чисел); блокирует — шаг 3.

**Оценка:** ~85 строк, ~20 минут.

### Шаг 3: документы

**Цель:** правило записано там, где пользователь и разработчик его ищут.

**Файлы:** `vault/knowledge/decisions/P8-формат-ввода-json.md`, `vault/knowledge/decisions/json-config-schema.md`, `vault/knowledge/decisions/pvt-корреляции-стендинг.md` — в worktree, коммит в ветке; `numerical_solver/README.md` — **в основном каталоге**, без коммита (§1.3, решение 4).

**Контекст:** P8 §5 сейчас не упоминает и отказ FEAT-027 в `create_pvt` (найдено при открытии #130) — дописывается вместе с DEBT-078. Заметки `vault/knowledge/` проверяет сторож меток (`test_eq_references.py`, DEBT-074): ссылки на постановку — меткой (`eq:co_cg`, `eq:c_ot`). DEBT-076 (влита) завела в P8 группу «PVT (…)» в строке `_validate` и абзац «PVT», в `json-config-schema.md` — строку «Ограничения»: $c_o$ добавляется туда же (решение пользователя, аудит 2).

**Изменения.**

1. P8, §2, после абзаца о расположении CSV.

До:
```markdown
CSV и JSON — в одной папке. Factory ищет CSV относительно расположения JSON.
```
После:
```markdown
CSV и JSON — в одной папке. Factory ищет CSV относительно расположения JSON.

Поля корреляций Стендинга при табличном PVT не используются: выше $p_b$ $B_o$ и $\mu_o$ задают недонасыщенные ветви `oil_pvt.csv`. Ненулевое `co_undersaturated` ([[DEBT-078]]) и `mu_o_undersaturated` ≠ `"none"` ([[FEAT-027]]) — отказ `create_pvt` (`factory.py`). До DEBT-078 `co_undersaturated` при таблице пропускалось молча (проба `vault/issues/debt-078/probes/co_undersaturated.py`: пример 04, $c_o = 3.3\cdot10^{-9}$ 1/Па — $B_o$ побитово тот же, что при $c_o = 0$).
```

2. P8, §5, строка `_validate` таблицы «Этап | Где | Что» — в группу «PVT (…)» DEBT-076 (якорь — сама группа, подстрока строки).

До:
```markdown
PVT (`rho_o_std`, `rho_g_std` > 0 — DEBT-076)
```
После:
```markdown
PVT (`rho_o_std`, `rho_g_std` > 0 — DEBT-076; `co_undersaturated` ≥ 0 — DEBT-078)
```

3. P8, §5, первая строка этапа `from_config` — новая строка `create_pvt` перед проверками CSV (замена — начало строки до второго `|`, остаток строки «CSV-таблицы: …» не меняется).

До:
```markdown
| `from_config` | `factory.py`: `_read_numeric_csv`, `_check_pvto_branches`, `_check_gas_pvt_table`, `_check_relperm_table` |
```
После:
```markdown
| `from_config` | `factory.py`: `create_pvt` | опции Стендинга при `model = "table"`: `mu_o_undersaturated` ≠ `"none"` (FEAT-027), `co_undersaturated` ≠ 0 (DEBT-078) — отказ |
| | `_read_numeric_csv`, `_check_pvto_branches`, `_check_gas_pvt_table`, `_check_relperm_table` |
```

4. P8, §5, новый абзац после абзаца «PVT» (DEBT-076), перед «Тепловые параметры — наш config …»: порядок абзацев — как проверок в коде.

До:
```markdown
Тепловые параметры — наш config (`_validate`, `io/config.py`; DEBT-047, DEBT-049):
```
После:
```markdown
Сжимаемость недонасыщенной нефти — наш config (`_validate`, `io/config.py`, блок «PVT»): `pvt.co_undersaturated` ≥ 0 ([[DEBT-078]]). $c_o = -(1/B_o)\,\partial B_o/\partial p$ при постоянном $R_s$ (`eq:co_cg`): при постоянном составе объём жидкости с ростом давления не растёт, $c_o < 0$ — ошибка знака. Условие корректности уравнения давления слабее — $c_o \ge -c_r$ (абзац под `eq:c_ot`): при $c_o < -c_r$ в недонасыщенной зоне $C_p < 0$, и неявный шаг вырождается на последовательности $\Delta t$. Замер на примере 03 (Стендинг, $c_r = 0$, 1 сут; `vault/issues/debt-078/probes/audit1_dt_dependence.out.txt`): $c_o = -10^{-9}$ при шаге 3600 и 1800 с проходило с одним предупреждением фабрики (BUG-019), при 900 с — отказ шага; $-3.3\cdot10^{-9}$ — отказ при всех трёх шагах. Проверка — при любой модели PVT. Отрицательная сжимаемость, возникающая из таблиц или корреляций, — по-прежнему предупреждение фабрики (BUG-019). Верхней границы нет: ошибку единиц ($10^{-5}$ 1/Па вместо $10^{-9}$ — $B_o(p_0) \approx 10^{-46}$, расчёт без отказа) проверка не ловит (`co_magnitude.out.txt`).

Тепловые параметры — наш config (`_validate`, `io/config.py`; DEBT-047, DEBT-049):
```

(Блоки «До» пп. 1, 4, 5, 5а, 6, 7 — строки целиком; п. 2 — подстрока строки, п. 3 — начало строки до второго `|`. Проба `plan_apply.py` делает те же замены подстрок.)

5. `json-config-schema.md`, таблица секции `pvt`, строка поля — отказ при таблице.

До:
```markdown
| `co_undersaturated` | float | Сжимаемость недонасыщенной нефти при p > pb, 1/Па; по умолчанию 0 (B_o выше pb не меняется). Только `"standing"` |
```
После:
```markdown
| `co_undersaturated` | float | Сжимаемость недонасыщенной нефти при p > pb, 1/Па; по умолчанию 0 (B_o выше pb не меняется). Только `"standing"`: при `"table"` значение ≠ 0 → `ValueError` (DEBT-078) |
```

5а. `json-config-schema.md`, строка «Ограничения» под таблицей секции `pvt` (её завела DEBT-076) — знак.

До:
```markdown
Ограничения: `rho_o_std > 0`, `rho_g_std > 0` — при любой `model` (DEBT-076).
```
После:
```markdown
Ограничения: `rho_o_std > 0`, `rho_g_std > 0` — при любой `model` (DEBT-076); `co_undersaturated ≥ 0` — при любой `model` (DEBT-078).
```

6. `pvt-корреляции-стендинг.md`, раздел «p ≥ pb».

До:
```markdown
co_under — сжимаемость нефти выше pb. Задаётся в JSON как скаляр (порядок 1e-9..1e-10 1/Па).
```
После:
```markdown
co_under — сжимаемость нефти выше pb. Задаётся в JSON как скаляр (порядок 1e-9..1e-10 1/Па), `pvt.co_undersaturated` ≥ 0: отрицательное значение отвергает `_validate` (DEBT-078). При табличном PVT поле не используется — ненулевое значение отвергает `create_pvt`.
```

7. `numerical_solver/README.md` основного каталога, п. 3.1, строка таблицы `pvt`.

До:
```markdown
| | `co_undersaturated` | 1/Па | 0 | для корреляций Стендинга: сжимаемость недонасыщенной нефти $c_o$; при $p \ge p_b(R_s)$ объёмный коэффициент $B_o = B_o(p_b)\,e^{-c_o (p - p_b)}$, при $c_o = 0$ $B_o$ зависит только от $R_s$ |
```
После:
```markdown
| | `co_undersaturated` | 1/Па | 0 | для корреляций Стендинга: сжимаемость недонасыщенной нефти $c_o \ge 0$; при $p \ge p_b(R_s)$ объёмный коэффициент $B_o = B_o(p_b)\,e^{-c_o (p - p_b)}$, при $c_o = 0$ $B_o$ зависит только от $R_s$. При табличном PVT допустимо только 0 |
```

Пробой: `python vault\issues\debt-078\probes\plan_apply.py <корень основного каталога> --readme` — проверка якоря; если «OK» — то же с `--write`. Если якорь не найден (файл менялся) — править руками по смыслу и сообщить пользователю.

**Проверка после шага:**
- `pytest tests/test_eq_references.py -q` — зелёный (13 passed на базе);
- `--collect-only -q` — 2136 (база + 7);
- `git diff --stat` worktree — README в нём не появляется (файл вне git).

**Подводные камни:** §5, пп. 1, 8, 9 — пп. 2, 4, 5а дописывают группы, которые завела DEBT-076.

**Зависимости:** требует — шаги 1, 2.

**Оценка:** ~15 строк текста, ~15 минут.

### Шаг 4: проба «после» и vault

**Цель:** зафиксировать поведение после правки и закрыть запись.

**Файлы:** `vault/issues/debt-078/probes/co_after.py` → `co_after.out.txt`; `vault/roadmap/известные баги и технический долг.md`; `vault/issues/debt-078/05-comment-done.md` (по `/implement`).

**Что сделать:**
1. Проба `co_after.py` — из корня worktree, `vault\issues\debt-078\probes\co_after.py`, с `PYTHONPATH` на `numerical_solver` worktree (первая строка вывода — путь пакета, должен быть в `.worktrees\debt-078`). Проба берёт примеры относительно своего расположения и пишет временный конфиг рядом с примером — запуск копии из worktree не трогает каталог `examples/` основного дерева. Вывод — `co_after.out.txt`. Ожидание (эмуляция, `co_after_emulate.out.txt`):
   - пример 04, $c_o = 3.3\cdot10^{-9}$, `create_pvt` — `ValueError: co_undersaturated = 3.3e-09 1/Па — только для model = 'standing'; …`; то же при $c_o = 0$ — без отказа;
   - пример 03, $c_o = -10^{-9}$, `load_config` — `ValueError: pvt.co_undersaturated = -1e-09 1/Па < 0: …`;
   - пример 04, $c_o = -10^{-9}$, `load_config` — то же сообщение о знаке.
2. Статус DEBT-078 — по правилам `/implement` (реализован, коммиты, число тестов 2129 → 2136, быстрый 1853 → 1860 — или по факту базы + 7).

**Проверка:** `--collect-only -q` — 2136 (база + 7).

**Оценка:** ~10 минут.

## 7. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `TestFactoryStandingHydro::test_co_with_table_raises` (новый) | `tests/test_factory_standing_hydro.py` | `configs/table_pvt`, `co_undersaturated = 3.3e-9` | `ValueError`, в тексте `co_undersaturated` и `= 3.3e-09 1/Па` | $c_o$ при таблице снова молча игнорируется |
| `TestValidationOilCompressibility::test_negative_co_rejected[step_dependent, sign_error_examples_17_20, tiny]` (новые, 3) | `tests/test_config.py` | минимальный конфиг (Стендинг), $c_o$ = −1e-9, −3.3e-9, −5e-324 | `ValueError` с `pvt.co_undersaturated` и `= {c_o} 1/Па` | $c_o < 0$ проходит (молча или до отказа шага — в зависимости от шага); проверка с допуском вместо знака |
| `TestValidationOilCompressibility::test_negative_co_rejected_for_table` (новый) | то же | секция `pvt` табличная, $c_o$ = −1e-9 | `ValueError` «должна быть ≥ 0» при `load_config` | проверка знака только для Стендинга; при таблице — отказ фабрики без слова о знаке |
| `TestValidationOilCompressibility::test_nonnegative_co_accepted[zero_default, examples_17_20]` (новые, 2) | то же | $c_o$ = 0, 3.3e-9 | конфиг загружен, значение прежнее | проверка отвергает умолчание или значение примеров |
| `test_beal_with_table_raises`, `test_beal_reaches_pvt`, `TestBaselinePVT`, `TestValidationRock` (существующие) | `tests/test_factory_standing_hydro.py`, `tests/test_config.py` | — | без изменений | новая проверка мешает соседним |
| табличные тесты и примеры (существующие) | `tests/` | $c_o = 0$ при таблице | зелёные | отказ при умолчании |
| `tests/test_eq_references.py` (существующий) | — | метки в новых комментариях и заметках | зелёный | номер уравнения вместо метки |
| регресс: быстрый уровень после шагов 1, 2; полный в конце | `tests/` | все примеры (медленные) | зелёные; истории не меняются | поломку примеров Стендинга с $c_o > 0$ (17, 20) |

## 8. Критерии завершения

- [ ] `create_pvt`: при `model = "table"` и `co_undersaturated != 0` — `ValueError` (после проверки `mu_o_undersaturated`, до чтения CSV).
- [ ] `_validate`: при `co_undersaturated < 0` — `ValueError` с именем поля и значением; при любой модели PVT.
- [ ] `_warn_negative_compressibility` не изменена.
- [ ] 7 новых тестов зелёные; всего **2136**, быстрый уровень **1860** (база `f5239de` + 7; при другой базе — по факту + 7), все зелёные; полный прогон зелёный.
- [ ] Проверка $c_o$ — в блоке «PVT» `_validate` после проверки плотностей DEBT-076, заголовок блока называет обе задачи; класс `TestValidationOilCompressibility` — сразу после `TestValidationPVT`.
- [ ] P8 (§2, §5 — две строки и абзац), `json-config-schema.md`, `pvt-корреляции-стендинг.md` — в ветке; README пакета — в основном каталоге (вне git); `test_eq_references.py` зелёный.
- [ ] Прототип не тронут: `git diff --stat <база> -- numerical_solver/HydroSolverPrototype` пуст.
- [ ] Проба `co_after.py` — три отказа и приём $c_o = 0$ при таблице (`co_after.out.txt`).
- [ ] Vault: статус DEBT-078; комментарий в #130 (`05-comment-done.md`).

## 9. Обнаруженные проблемы

1. **Ошибка единиц $c_o$ не ловится** (§1.2, C): $10^{-5}$ 1/Па — молча неверный расчёт ($B_o(p_0) \approx 10^{-46}$, газа нет, $T$ правдоподобна); $10^{-4}$, $10^{-3}$ — отказ с советом про дробление шага. То же, по-видимому, у $c_r$ (верхней границы нет, DEBT-068). **Не регистрируется — решение пользователя 2026-10-17.** Факт записан в комментарии `_validate` и в P8 §5, чтобы следующий читатель не считал проверку полной.
2. **P8 §5 не упоминал отказ FEAT-027 в `create_pvt`** — дописывается в шаге 3 вместе с DEBT-078.
3. **Отказ шага при $c_o = -3.3\cdot10^{-9}$ советует увеличить `max_retries`** — ложный совет при ошибке ввода; после шага 2 до расчёта не доходит. Не регистрируется.
4. **Аудит 1: $c_o = -10^{-9}$ «проходит» только при удачном шаге** (`audit1_dt_dependence.out.txt`): при $c_r = 0$ любое $c_o < 0$ даёт $C_p < 0$; при `dt_integration` = 900 с расчёт отказывает. Первоначальный текст плана приписывал $C_p < 0$ только значению $-3.3\cdot10^{-9}$ — исправлено в §1.1, §1.2, комментарии `_validate`, комментариях тестов и абзаце P8. Довод за отказ в `_validate` стал сильнее: «молча проходит» — свойство шага, а не конфига. Не регистрируется.
5. **Аудит 1: якоря DEBT-076 и DEBT-078 совпадали** (план DEBT-076 стал «готов к реализации» во время планирования DEBT-078): `config.py` — оба вставляли после проверки $c_r$; `test_config.py` — оба после `TestValidationRock`; P8 — та же строка и тот же якорь абзаца. Чей план реализовали бы вторым, у того блоки «До» не нашлись бы. Вставки DEBT-078 перенесены до этих мест (§5, п. 1; `audit1_order_check.py`). План DEBT-076 не менялся.
6. **Аудит 2: DEBT-076 влита (`f6e9aa0`) — размещение аудита 1 заменено** решением пользователя: $c_o$ — в группы «PVT» DEBT-076 (блок `_validate`, класс после `TestValidationPVT`, группа и абзац P8, строка «Ограничения» схемы). Якоря сняты с влитого кода. Попутно: в `json-config-schema.md` знак $c_o$ перенесён из строки поля в строку «Ограничения» (в строке поля остался отказ при таблице).

## 10. Связи

- Запись: DEBT-078 в `vault/roadmap/известные баги и технический долг.md`; issue [#130](https://github.com/ArturSalamatin/Oil_Gas/issues/130).
- [[feat-027 undersaturated-oil-viscosity]] (#54) — отказ `mu_o_undersaturated` при таблице, образец шага 1.
- [[debt-068 rock-compressibility-sign]] (#111) — отказ при $c_r < 0$, образец шага 2.
- [[bug-019 pvt-negative-compressibility-check]] (#49) — предупреждение `_warn_negative_compressibility`, остаётся.
- [[debt-076 std-density-sign-check]] (#129, влита `f6e9aa0`) — блок «PVT» `_validate`, `TestValidationPVT`, группы P8 §5 и строка «Ограничения» схемы, в которые шаги 2–3 добавляют $c_o$ (§5, п. 1).
- [[feat-033 workbook-input-format]] (#128) — книга Excel, поле в книге отсутствует.
- [[P8-формат-ввода-json]], [[json-config-schema]], [[pvt-корреляции-стендинг]] — документы шага 3.

## 11. Файлы проб (`vault/issues/debt-078/probes/`)

| Файл | Что |
|---|---|
| `co_undersaturated.py`, `co_undersaturated.out.txt` | замер при регистрации (`130b88d`): §1.2 A и B (B — без расчёта) |
| `co_undersaturated_8ddb08d.out.txt` | тот же замер на базе плана `8ddb08d` — дословно совпадает |
| `co_negative_run.py`, `co_negative_run.out.txt` | §1.2 B: пример 03, $c_o$ = 0 / −1e-9 / −3.3e-9, 1 сут, шаг 3600 с — молча / молча с предупреждением / отказ шага |
| `audit1_dt_dependence.py`, `audit1_dt_dependence.out.txt` | аудит 1, §1.2 B: те же $c_o$ при `dt_integration` 3600 / 1800 / 900 с — при $-10^{-9}$ отказ появляется на 900 с: $C_p < 0$ при любом $c_o < 0$ ($c_r = 0$), исход зависит от шага |
| `co_magnitude.py`, `co_magnitude.out.txt` | §1.2 C: ошибка единиц, $c_o$ = 1.45e-9 / 1e-5 / 1e-4 / 1e-3, 6 ч |
| `plan_apply.py` | блоки «До → После» шагов 1–3 (символ в символ как в плане): проверка якорей и применение `--write`; README — ключ `--readme` |
| `plan_apply_check.out.txt` | все 14 блоков в git и якорь README найдены ровно один раз (переснято после аудита 2 на `f5239de`) |
| `plan_blocks_check.py`, `plan_blocks_check.out.txt` | все 15 пар «До/После» пробы есть в тексте плана дословно (30 блоков; переснято после аудита 2) — план и проба не разошлись |
| `plan_fast.out.txt` | снимок при планировании (блоки до правок аудита 1): правки во временном worktree на `8ddb08d` (удалён) — новые 7 тестов и сторож меток 20 passed; `--collect-only` 2027 / 1751; быстрый уровень 1751 passed |
| `audit1_order_check.py`, `audit1_order_check.out.txt` | снимок аудита 1 на `0f8074d` (до влития DEBT-076; теперь не запускать — её якорей «До» на базе уже нет): совместимость размещения аудита 1 с DEBT-076 при любом порядке; после влития DEBT-076 размещение заменено (аудит 2) |
| `audit2_fast.out.txt` | аудит 2: блоки после переноса в группу «PVT» DEBT-076, временный worktree на `f5239de` (удалён) — затронутые файлы 453 passed, 7 новых passed; `--collect-only` 2136 / 1860; быстрый уровень 1860 passed за 136 с |
| `audit1_fast.out.txt` | аудит 1: блоки после правок аудита во временном worktree на `0f8074d` (удалён) — новые тесты, сторож меток, `test_workbook_format.py` — 66 passed; `--collect-only` 2123 / 1847; быстрый уровень 1847 passed за 141 с; новых строк кода длиннее 95 символов нет |
| `co_after.py`, `co_after_emulate.out.txt` | проба «после» (шаг 4) на коде эмуляции: три отказа с ожидаемым текстом, $c_o = 0$ при таблице — без отказа |
