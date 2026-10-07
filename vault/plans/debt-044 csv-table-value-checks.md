---
tags:
  - план
  - рефакторинг
date: 2026-10-07
issue: DEBT-044
github: 74
branch: refactor/debt-044/csv-table-value-checks
status: реализован
worktree: .worktrees/debt-044
audit:
  date: 2026-10-07
  round: 2
  focus: реализуемость — тесты под настройками pytest проекта, тесты, читающие правленые документы, якоря Edit, сдвиг базы
  found: 5
  auto-fixed: 5
  manual-required: 0
---

# План DEBT-044: проверка допустимости значений CSV-таблиц фабрики

**Задача:** DEBT-044 в `vault/roadmap/известные баги и технический долг.md` · GitHub [#74](https://github.com/ArturSalamatin/Oil_Gas/issues/74) · ветка `refactor/debt-044/csv-table-value-checks` в worktree `.worktrees/debt-044` · база `numerical_scheme/implementation` (на аудите 2 — `6b98ffd`, после влития DEBT-045 и DEBT-041; `factory.py` и `test_factory_prototype.py` с `3a1dcc3` не менялись; README 04 и P8 DEBT-041 правил в других местах — строки 297-301 и 194, — правки этого плана к ним применимы: `plan_check.py` на `9d4321d`)

**Подтип:** рефакторинг с ужесточением проверки ввода. CSV-путь фабрики получает проверки значений не слабее XLSX-ридера прототипа и сообщения с именем файла. Корректные таблицы читаются побитово как раньше. Числа решателя, результаты примеров и код прототипа не меняются.

## Кратко

Сейчас CSV-путь фабрики (`pvt.model = "table"`, `relperm.model = "table"`) проверяет формат таблиц (DEBT-042) и ветви PVTO (DEBT-038), но не значения. Проба `vault/issues/debt-044/probes/red_state.py` (2026-10-07, `3a1dcc3`) подменяла одну строку таблиц `configs/table_pvt` и запускала 24 ч при $p_{wf}$ = 15 МПа (штатный режим, $= p_b$) и 10 МПа (газовая зона у забоя). Результат:

| что в таблице | что происходит сейчас |
|---|---|
| $B_o < 0$ | при 15 МПа расчёт проходит до конца: **$T_{\min} = -245.8$ К**, сообщений нет |
| $\mu_o < 0$ | при 15 МПа молча: $T_{\min} = 169.8$ К |
| $B_o = 0$, $\mu_o = 0$ | Ньютон не сходится на первом шаге, `RuntimeWarning: divide by zero` |
| $B_g = 0$ | при 10 МПа молча, `divide by zero`: $S_{g,\max}$ = 0.0068 вместо 0.0098 |
| $\mu_g = 0$ | при 10 МПа молча: $S_{g,\max}$ = 0.0043 |
| $B_g < 0$, $\mu_g < 0$ | при 10 МПа Ньютон не сходится на первом шаге |
| $p < 0$ в газе / в нефти | при 10 МПа молча: $S_{g,\max}$ = 0.0081 / $T_{\max}$ = 351.58 К вместо 351.02 |
| $S_g < 0$ в ОФП | при 15 МПа Ньютон не сходится ($t$ = 0.33 сут), при 10 МПа молча $S_{g,\max}$ = 0.035 |
| $k_{ro} > 1$ | при 10 МПа молча: $S_{g,\max}$ = 0.0116 |
| $k_r < 0$, газ или ОФП из одной строки / только заголовок, давление газа или $S_g$ не растёт, одна ветвь $R_s$ | `ValueError` конструктора прототипа на английском, без имени файла (`pvt.py:32`, `:46`, `relperm.py:5`, `:6`) |

При 15 МПа газовые ошибки себя не проявляют: свободного газа нет ($S_{g,\max} = 0$).

После правки:
- **значения столбцов** проверяет разборщик `_read_numeric_csv` (там известен номер строки файла): $R_s \ge 0$; $p$, $B_o$, $\mu_o$, $B_g$, $\mu_g > 0$; $S_g$, $k_{ro}$, $k_{rg} \in [0, 1]$. Сообщение: `gas_pvt.csv: строка 3, столбец Bg: '-0.008' — должно быть > 0.`;
- **таблицу целиком** проверяют функции фабрики до конструкторов прототипа: газ — не меньше 2 строк, давление строго растёт (`_check_gas_pvt_table`, новая); ОФП — не меньше 2 строк, $S_g$ строго растёт (`_check_relperm_table`, новая); нефть — не меньше 2 ветвей $R_s$ (новое правило в `_check_pvto_branches`). Сообщения на русском, начинаются с имени файла.

Объём: `factory.py` — 3 константы правил, 3 словаря пределов, 2 новые функции (~35 строк), 4 строки проверки в разборщике, 2 вызова, правка `_check_pvto_branches` (+8 строк) и комментариев; 26 тестов; 2 документа. Тестов: 1344 → 1370 (быстрый уровень 1108 → 1134).

**Код плана проверен подменой** — см. раздел «Проверка плана» в конце.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-044 в реестре, тело issue `vault/issues/debt-044/01-issue-body.md` и замер `vault/issues/debt-044/probes/red_state.out.txt`. В теле issue номера строк `factory.py` от раздела ридеров и ниже (`:425-523`, `:445-447`, `:517-519`) устарели на +4: issue писался до влития BUG-020. Верные номера — в этом плане.
3. Реализация — по `/implement` в worktree `<W>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-044` (создаёт `/implement`, шаг 1.5). Основной каталог `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas` занят параллельными сессиями: в `vault/` есть чужие незакоммиченные правки (DEBT-041, DEBT-045, FEAT-029, DEBT-015, DEBT-040). Их не трогать и не коммитить.
4. Интерпретатор общий, по абсолютному пути (в worktree нет `.venv`):
   ```powershell
   $py = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   $pr = "<W>\vault\issues\debt-044\probes"
   cd <W>\numerical_solver
   & $py -c "import gpn_multiphase_solver as g; print(g.__file__)"   # путь <W>\... — иначе стоп
   ```
   Все команды pytest и проб — из `<W>\numerical_solver`. Пробы берут код из текущего каталога (`SOLVER = Path.cwd()`) и печатают первой строкой `Код: <путь к factory.py>`. Путь должен вести в `<W>`.
5. Baseline (замер при планировании 2026-10-07, код `3a1dcc3`):
   ```powershell
   & $py -m pytest tests/ --collect-only -q                # 1344 тестов
   & $py -m pytest tests/ --collect-only -q -m "not slow"  # 1108/1344 (236 deselected)
   & $py -m pytest tests/ -m "not slow" -q                 # быстрый уровень, ~70 с
   & $py -m pytest tests/test_factory_prototype.py -q      # 53 passed, ~2 с
   ```
   Числа перепроверены аудитом 2 на `9d4321d`: те же 1344 и 1108, `test_pvt_consistency.py` — 37, `TestReadme` — 55. Если чисел больше, база сдвинулась: параллельно реализуется DEBT-040 (`.worktrees/debt-040`, новый файл `tests/test_prototype_open_branch_skip.py`). Запиши новые числа и дальше считай от них. План добавляет ровно 26 тестов, все в быстром уровне.
6. Начни с шага 1. После каждого шага — его проверка. Полный прогон — шаг 6.

## Контекст для читателя без контекста

**Где читаются CSV.** Для `pvt.model = "table"` и `relperm.model = "table"` фабрика `SimulatorFactory.from_config` (`numerical_solver/gpn_multiphase_solver/factory.py`) читает три CSV-файла из каталога JSON-конфига (номера строк — на `3a1dcc3`):

```
_create_pvt, ветвь "table" (:115-149)
  _read_oil_pvt_csv (:123, определена :493-500) → [(Rs, p_бар, Bo, mu_сП), ...]
  _read_gas_pvt_csv (:124, определена :503-510) → [(p_бар, Bg, mu_сП), ...]
  _check_pvto_branches (:127, определена :168-218) — ветви PVTO (DEBT-038)
  BlackOilPVT(oil_rows, gas_rows) (:130) — прототип, radial_blackoil/pvt.py
_create_relperm, ветвь "table" (:316-322)
  _read_relperm_csv (:318, определена :513-527) → (Sg, kro, krg) — три списка
  TabulatedRelPerm(Sg, kro, krg) (:321) — прототип, radial_blackoil/relperm.py
```

Все три ридера вызывают общий разборщик `_read_numeric_csv(csv_path, columns, kind)` (`:438-490`, DEBT-042). Он проверяет заголовок, число полей и что каждое поле — конечное число. Значения он не проверяет (комментарий `:449-451` прямо ссылается на DEBT-044). Единицы в файлах — СИ (Па, Па·с); ридеры нефти и газа переводят давление в бары, вязкость в сП: так их принимает `BlackOilPVT`.

**Что проверяют XLSX-ридер и конструкторы прототипа** (эталон «не слабее»):

| правило | XLSX `input_reader.py` | конструктор прототипа |
|---|---|---|
| газ: ≥ 2 строк, $p$ строго растёт | `:71-72` | `pvt.py:32`: `GAS_PVT pressure must be strictly increasing with >=2 rows` |
| газ: $B_g > 0$, $\mu_g > 0$ | `:73` | нет |
| ОФП: ≥ 2 строк, $S_g$ строго растёт | `:80` (только число) | `relperm.py:5`: `RELPERM Sg must be strictly increasing with >=2 rows` |
| ОФП: $S_g \in [0, 1]$ | `:81` | нет |
| ОФП: $k_r \ge 0$ | `:82` | `relperm.py:6`: `RELPERM values must be non-negative` |
| нефть: ≥ 2 ветвей $R_s$ | нет | `pvt.py:46`: `OIL_PVT needs >=2 Rs branches, got 1` |

**Почему значения важны.** $B$ и $\mu$ стоят в знаменателях запасов и подвижностей прототипа: `blackoil.py:162` — `pv*so/bo, pv*(rs*so/bo + sg/bg)`, `blackoil.py:182` — `kro/(muo·…)/bo, krg/(mug·…)/bg`. Ноль даёт деление на ноль, отрицательное значение — отрицательную массу или подвижность. Те же $B$ входят и в плотности фаз нашего уравнения энергии: `pvt/base.py:70`, $\rho_o = (\rho_{o,ст} + R_s\rho_{g,ст})/B_o$ (через `PrototypePVTAdapter.Bo`, `pvt/prototype_adapter.py:35`). При $B_o < 0$ плотность нефти отрицательна, гидродинамика прототипа при этом сходится, а уравнение энергии считает с нефизичными коэффициентами — отсюда $T = -246$ К без отказа: проверки $T > 0$ в пакете нет (grep). Таблицы интерполируются `np.interp`. Он не проверяет, что узлы растут, и при нарушении молча даёт неверные значения (документация numpy). Поэтому узел вне $[0, 1]$ по $S_g$ искажает кривую ОФП на соседнем отрезке внутри $[0, 1]$.

**OPM Flow Manual 2025-10** (`Refs/incoming/OPM_Flow_Reference_Manual_2025-10_Rev-0_compressed.pdf`):
- PVDG (§8.3.239, табл. 8.127): давление растёт, $B_g$ убывает, $\mu_g$ растёт, не меньше двух строк;
- SGOF (§8.3.291, табл. 8.165, с. 1205): $S_g$ растёт «начиная с нуля и заканчивая единицей», $k_{rg}$ не убывает, $k_{ro}$ не возрастает, оба в $[0, 1]$, не меньше двух строк. Требование «$S_g$ до единицы» план не вводит: все 15 таблиц ОФП проекта кончаются на $S_g = 0.8$, пример самого руководства — тоже на 0.80, а выше последнего узла `np.interp` держит $k_r$ постоянными. Это не ошибка ввода, а выбор области таблицы.

**Таблицы проекта.** 47 таблиц (16 нефть, 16 газ, 15 ОФП; пересчитано 2026-10-07 на `299d6a7`). Диапазоны по снимку `vault/issues/debt-042/probes/tables_snapshot.json` (единицы на выходе ридера):

| таблица | диапазоны |
|---|---|
| `oil_pvt.csv` | $R_s$ 0…180, $p$ 1.013…300 бар, $B_o$ 0.986…1.53, $\mu_o$ 0.456…19.96 сП |
| `gas_pvt.csv` | $p$ 50…300 бар, $B_g$ 0.004…0.02, $\mu_g$ 0.012…0.018 сП |
| `relperm.csv` | $S_g$ 0…0.8, $k_{ro}$ 0…1.0, $k_{rg}$ 0…0.8 |

Все 47 проходят новые правила. Монотонность по OPM они тоже соблюдают ($B_g$ убывает, $\mu_g$ растёт, $k_{rg}$ не убывает, $k_{ro}$ не возрастает, $k_{ro}$ последней строки = 0, $S_g$ первой строки = 0), но эти правила план не вводит (см. решения).

**Решения пользователя (2026-10-07, при планировании):**
1. **Вариант 3 issue.** Пределы столбцов проверяет разборщик при разборе строки: номер строки файла известен только там (`reader.line_num`). Правила таблицы целиком — функции фабрики после разбора.
2. **Объём правил** сверх XLSX-ридера: $B_o > 0$, $\mu_o > 0$; $R_s \ge 0$, $p > 0$; $k_r \le 1$. Монотонность ОФП по SGOF не вводится.
3. **Проверки конструкторов прототипа повторяются в фабрике** ради русского сообщения с именем файла: ≥ 2 строк и рост $p$ (газ), ≥ 2 строк и рост $S_g$ (ОФП), $k_r \ge 0$, плюс ≥ 2 ветвей $R_s$ в `_check_pvto_branches`. Конструкторы остаются вторым рубежом и на таблицах, прошедших фабрику, не срабатывают.

**Решения плана (не требовали выбора пользователя):**
4. **Убывание $B_g$ не проверяется.** PVDG его требует, но рост $B_g$ — это отрицательная сжимаемость газа $c_g < 0$. BUG-019 сознательно сделал её предупреждением, как ECLIPSE («Negative Compressibility Found»): `_warn_negative_compressibility` (`factory.py:249-291`). На этом стоит тест `tests/test_pvt_consistency.py:195`: таблица `GAS_BAD` с ростом $B_g$ на 10–15 МПа обязана пройти `from_config` с одним предупреждением. Рост $\mu_g$ (его PVDG тоже требует) не проверяется по другой причине: решение 2 не включает монотонность свойств, а предупреждения BUG-019 о $\mu_g$ нет — сжимаемость от вязкости не зависит.
5. **Пределы — по значению из файла**, до перевода единиц: знак и сравнение с нулём от единиц не зависят, а $S_g$, $k_r$ безразмерны.
6. **Сообщения правил таблицы называют значения, а не номер строки.** После разбора номер строки файла потерян: пустые строки пропускаются, и порядковый номер строки данных не совпадает со строкой файла. Возвращать номера строк из разборщика — менять тип его результата и тесты `TestCSVReaders`. Значение однозначно находит строку, так же поступает DEBT-038 («20 МПа после 30 МПа»).
7. **Пределы записаны парой «текст для сообщения, проверка»** (`lambda`), а не тройкой границ. Правил три (`> 0`, `≥ 0`, `в [0, 1]`), текст сообщения задан рядом с проверкой, и код читается без расшифровки флагов включения границ.
8. **`limits` — обязательный аргумент разборщика.** Вызовов три, все в ридерах; тесты вызывают ридеры, а не `_read_numeric_csv`. Забытый словарь даёт `TypeError` сразу, а не молча пропущенную проверку.
9. **Порядок отказов.** Сначала разбор нефти (значения), затем газа (значения), затем ветви нефти, затем таблица газа, затем `BlackOilPVT`; для ОФП — значения, затем таблица. Для таблицы с несколькими ошибками отказ называет первую по этому порядку.

## Текущее состояние (baseline)

- Тесты: 1344 всего, 1108 в быстром уровне (HEAD `3a1dcc3`, замер 2026-10-07). `tests/test_factory_prototype.py` — 53 passed.
- Вызовы в пакете: `_read_numeric_csv` — только из трёх ридеров (`factory.py:499`, `:509`, `:518`). Ридеры — `factory.py:123`, `:124`, `:318`. `_check_pvto_branches` — `factory.py:127`. Вне пакета — только `tests/test_factory_prototype.py` (импорт ридеров, `:24`). grep по `numerical_solver/` без `.venv`.
- Таблицы, которые пишут тесты (`test_factory_prototype.py`, `test_pvt_consistency.py:40-51`), — с допустимыми значениями и не меньше чем двумя ветвями (проверено чтением): новые правила их не задевают.
- Красное состояние — `vault/issues/debt-044/probes/red_state.out.txt` (таблица в «Кратко»).

## Целевое состояние

- `factory.py`, раздел `# ── CSV-ридеры ──`: константы правил `_POSITIVE`, `_NON_NEGATIVE`, `_FRACTION`; словари `_OIL_PVT_LIMITS`, `_GAS_PVT_LIMITS`, `_RELPERM_LIMITS`; `_read_numeric_csv(csv_path, columns, limits, kind)` проверяет `limits[col]` после проверки конечности; ридеры передают свои пределы. Сигнатуры и типы возврата ридеров не меняются.
- Новые функции `_check_gas_pvt_table(gas_rows, gas_pvt_file)` и `_check_relperm_table(Sg, relperm_file)` рядом с `_check_pvto_branches`; вызовы — в `_create_pvt` после `_check_pvto_branches` и в `_create_relperm` после ридера, до конструкторов прототипа.
- `_check_pvto_branches` отвергает таблицу из одной ветви.
- Комментарии `_read_numeric_csv` и `_read_relperm_csv`, ссылающиеся на DEBT-044 и «отказ даёт TabulatedRelPerm», обновлены.
- Импорты не меняются: `np`, `BAR_TO_PA` уже импортированы.
- Прототип (`HydroSolverPrototype/`) не меняется.

## Варианты и выбор

Подробно — тело issue #74, раздел «Анализ вариантов решения».

| Вариант | Суть | Итог |
|---|---|---|
| 1 | все проверки в функциях фабрики после разбора | отклонён: номер строки файла потерян, сообщение о значении без строки |
| 2 | проверки в конструкторах прототипа, фабрика перевыбрасывает с именем файла | отклонён: `BlackOilPVT` получает нефть и газ разом, файл не определить без разбора текста; сообщения на английском; правка прототипа требует его регрессии |
| 3 | пределы столбцов в разборщике, правила таблицы — в фабрике | **выбран** (решение 1) |

Промежуточные состояния: шаг 2 пишет тесты (красные), но **не коммитит** их. Тесты и реализация уходят одним коммитом в конце шага 3: `/implement` запрещает коммитить сломанное состояние. Так же сделаны DEBT-038 и DEBT-042.

## Подводные камни (чеклист)

- ✅ **Все места вызова найдены.** `_read_numeric_csv` вызывается только тремя ридерами, все три правятся в шаге 3. Ридеры и `_check_pvto_branches` сигнатур не меняют.
- ✅ **Зависимости пакетов:** не меняются.
- ✅ **Обратная совместимость:** закрытые функции; `TestCSVReaders` (7 тестов) читает таблицы с допустимыми значениями и проходит без правок. Сигнатура `_read_numeric_csv` меняется, но вне ридеров её никто не вызывает.
- ✅ **Состояние при ошибке:** `raise` до создания объектов PVT/ОФП; файл закрывается `with`.
- ⚠️ **Существующие тесты с испорченными таблицами.** Порядок отказов (решение 9) не меняет ни одного существующего сообщения:
  - `TestPVTOBranches` (DEBT-038): значения допустимы, ветвей ≥ 2 (`test_one_row_last_branch_raises` — ветви 0 и 30), газ и ОФП — копии `configs/table_pvt`. Сообщения те же;
  - `test_empty_table_raises`: пустая нефть ловится первой проверкой `_check_pvto_branches` («нет ни одной числовой строки»), до новой «≥ 2 ветвей»;
  - `TestCSVStrictParsing` (DEBT-042): ошибки формата отвергаются раньше проверки значения (порядок в разборщике: число полей → `float` → конечность → предел);
  - `test_pvt_consistency.py`: `GAS_BAD`, `OIL_BAD`, `OIL_UNDER_BAD` — все значения положительны, давление растёт: проходят `from_config`, предупреждения BUG-019 те же.
- ⚠️ **Таблицы проекта.** Ни одна из 47 не должна отвергаться. Проверка — шаг 4: проба `tables_check.py` прогоняет новые ридеры и проверки таблиц на всех 47 и `from_config` на каждом конфиге с табличным PVT или ОФП. Если хоть одна отвергнута — **стоп**, вопрос пользователю (таблица проекта нефизична или правило слишком строгое).
- ⚠️ **Побитовая неизменность чтения.** Новые проверки только читают значения, разбор и перевод единиц не меняются. Сверка — снимок DEBT-042 (`vault/issues/debt-042/probes/tables_check.py --compare`) в шаге 4: «побитово совпадает».
- ✅ **Граница включается там, где она допустима.** $S_g = 0$ и $k_{ro} = 1$ стоят в первой строке всех 15 таблиц ОФП, $R_s = 0$ — у ветви дегазированной нефти, $k_{ro} = 0$ и $k_{rg} = 0$ — на концах. Тест `test_boundary_values_accepted` ловит строгое неравенство вместо нестрогого.
- ✅ **Циклические импорты:** новых импортов нет.
- ✅ **Docstrings:** однострочные; `\eqref{}` нет (проверка ввода).
- ✅ **Конфиги:** имена параметров не меняются.
- ✅ **Связь с другими задачами:**
  - DEBT-038, DEBT-042 влиты; план их расширяет (одна новая ветка проверки в `_check_pvto_branches`, один аргумент разборщика);
  - BUG-017 (`_check_rs0_in_table`), BUG-019 (`_warn_negative_compressibility`) — после `BlackOilPVT`, не меняются; решение 4 сохраняет поведение BUG-019;
  - DEBT-041 влит (`d73624c`): правил P8 у строки 194 и README 04 в строках 297-301 — ниже правок этого плана (P8 77-114, README 04 47-55). Правки плана на базе с DEBT-041 применимы (`plan_check.py`, аудит 2);
  - DEBT-040 (в реализации, `.worktrees/debt-040`) правит прототип `radial_blackoil/blackoil.py`, `CHANGELOG_1.0.3.md` и добавляет `tests/test_prototype_open_branch_skip.py` (таблица файлов его плана). С файлами этого плана не пересекается. Если он влит до реализации DEBT-044: число тестов базы вырастет (шаг 1 пишет новое), а замер шага 1 сверяется с `red_state.out.txt` — расхождение «эталона» укажет, что DEBT-040 изменил и сценарий без останова (в пробе остановов нет, ожидается совпадение);
  - DEBT-045 правит только `examples/README.md`; FEAT-029, DEBT-015, DEBT-040 — `factory.py` и `test_factory_prototype.py` не трогают (grep по их планам и пробам).
- ✅ **Другие пути чтения тех же таблиц (аудит).** Прямого чтения `oil_pvt.csv`, `gas_pvt.csv`, `relperm.csv` вне фабрики нет: grep `oil_pvt\.csv|gas_pvt\.csv|relperm\.csv|loadtxt|genfromtxt|read_csv` по `gpn_multiphase_solver/` и `examples/` даёт только docstring ридеров, комментарии и `examples/04a_high_gas_saturation/plot_profiles_50k.py:44` (читает CSV результатов). `examples/two_phase_analytics.py:116-118` строит ОФП через `_create_relperm` фабрики и получит новые проверки автоматически. XLSX-путь прототипа (`input_reader.py`) GPN не использует.
- ✅ **Производительность:** проверка при создании симулятора, сотни строк — пренебрежимо.
- ✅ **Прототип:** не меняется. Регрессия против `regression/golden/` не нужна.

## Шаги

### Шаг 1: Подготовка — worktree, baseline, красное состояние

**Цель:** ветка от актуальной базы; числа тестов и красное состояние зафиксированы до правки.

**Файлы:** `vault/issues/debt-044/probes/red_state.out.txt` (переснимается).

**Что сделать** (из `<W>\numerical_solver`, переменные `$py`, `$pr` — «Как начать», пункт 4):
1. Команды «Как начать работу», пункты 3–5.
2. Воспроизвести красное состояние:
   ```powershell
   & $py "$pr\red_state.py" 2>$null | Tee-Object -FilePath "$pr\red_state.out.txt"
   ```
   Первая строка — `Код: <W>\numerical_solver\gpn_multiphase_solver\factory.py`. Дальше — как в таблице «Кратко». Эталон — закоммиченный `red_state.out.txt`, снятый из основного каталога: `git -C <W> diff -U0 -- vault/issues/debt-044/probes/red_state.out.txt` после перезаписи покажет ровно одну изменённую строку — первую, с путём к коду. Любое другое расхождение — стоп, разобраться (база изменила поведение решателя). После сверки вернуть закоммиченный замер, чтобы он не уехал в коммит ветки с путём worktree:
   ```powershell
   git -C <W> checkout -- vault/issues/debt-044/probes/red_state.out.txt
   ```
   Проба создаёт и удаляет `red_state_tmp/` рядом с собой, ~2 мин.

**Проверка:** Регресс: быстрый — 1108 passed (или новое число базы).

**Зависимости:** блокирует шаги 2–7.

**Оценка:** 0 строк, ~5 мин.

### Шаг 2: Тесты допустимости значений (красные)

**Цель:** 26 тестов на новые правила. До реализации 25 красных и 1 зелёный: `test_boundary_values_accepted` проходит и сейчас — он защищает от избыточной строгости (граница должна включаться).

**Файлы:** `numerical_solver/tests/test_factory_prototype.py`

**Контекст:** пределы столбцов — свойство ридера: тесты `test_value_out_of_range_raises` вызывают ридеры напрямую и проверяют строку и столбец. Правила таблицы целиком — свойство фабрики: тесты идут через `SimulatorFactory.from_config` и проверяют, что сообщение начинается с имени файла. Один тест значения идёт через `from_config`: он ловит вызов ридера в обход проверки. Константы `OIL_HEADER`, `OIL_BRANCH_0`, `OIL_BRANCH_30` (раздел G, `:423-425`), `GAS_HEADER`, `RP_HEADER`, функции `_csv`, `_parse_error` (раздел H, `:554-569`) уже есть. Строка файла: заголовок — 1, первая строка данных — 2.

`pytest.param(..., id="...")` — один набор аргументов параметризованного теста с именем для отчёта: pytest запускает `test_value_out_of_range_raises` по разу на каждый элемент `VALUE_CASES`, в выводе — `test_value_out_of_range_raises[gas_Bg_zero]`.

**Что сделать:**
1. В docstring модуля после строки 11 («Строгий разбор CSV…») добавить строку:

<!-- правка numerical_solver/tests/test_factory_prototype.py #1 до -->
```python
- Строгий разбор CSV: заголовок, число полей, конечные числа (DEBT-042)
"""
```
<!-- правка numerical_solver/tests/test_factory_prototype.py #1 после -->
```python
- Строгий разбор CSV: заголовок, число полей, конечные числа (DEBT-042)
- Допустимость значений CSV: пределы столбцов, число строк, рост p и S_g, ветви R_s (DEBT-044)
"""
```

2. В конец файла (после `test_relperm_bad_row_fails_in_from_config`, последняя строка 726) добавить раздел I. Якорь для Edit — две последние строки файла: строка `SimulatorFactory.from_config(config)` встречается в файле много раз, а вместе с предыдущей — один:
   ```python
           with pytest.raises(ValueError, match="relperm.csv: строка 6, столбец kro"):
               SimulatorFactory.from_config(config)
   ```
   Новый текст идёт сразу за ними, начиная с двух пустых строк перед `# ═══`:

<!-- правка numerical_solver/tests/test_factory_prototype.py #2 в конец -->
```python


# ═══════════════════════════════════════════════════════════
# I. Допустимость значений CSV-таблиц (DEBT-044)
# ═══════════════════════════════════════════════════════════

# До DEBT-044 CSV-путь не проверял B > 0, μ > 0, p > 0, R_s ≥ 0, S_g и k_r
# в [0, 1]; число строк и рост p, S_g проверяли только конструкторы прототипа —
# на английском и без имени файла. Поведение до правки — проба
# vault/issues/debt-044/probes/red_state.out.txt (2026-10-07): таблица
# configs/table_pvt с одной испорченной строкой, run 24 ч при p_wf = 15 МПа
# (штатный, = p_b, газа нет) и 10 МПа (газовая зона у забоя). Эталон при
# 10 МПа: S_g max 0.0098, T 349.91…351.02 К.

# Строки данных gas_pvt.csv и relperm.csv конфига configs/table_pvt
TABLE_GAS_ROWS = ["5000000,0.020,0.000012\n", "15000000,0.008,0.000014\n",
                  "30000000,0.004,0.000018\n"]
TABLE_RP_ROWS = ["0.0,1.0,0.0\n", "0.1,0.8,0.01\n", "0.2,0.6,0.05\n",
                 "0.4,0.3,0.2\n", "0.6,0.1,0.5\n", "0.8,0.0,0.8\n"]


def _with_row(header, rows, index, line):
    """Текст таблицы header + rows, где строка данных rows[index] заменена на line."""
    rows = list(rows)
    rows[index] = line
    return header + "".join(rows)


def _table_config_with_csv(tmp_path, name, text):
    """TABLE_CONFIG, где таблица name заменена на text; остальные — копии configs/table_pvt."""
    for fname in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        shutil.copy(TABLE_CONFIG.parent / fname, tmp_path / fname)
    (tmp_path / name).write_text(text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = tmp_path
    return config


# Значение вне пределов столбца: (файл, текст таблицы, строка файла, столбец, правило).
# Комментарий к случаю — что было до правки (проба red_state).
VALUE_CASES = [
    # ── Газ: p, B_g, μ_g > 0 (строка 3 — узел 15 МПа) ──
    # при 10 МПа счёт проходит с «divide by zero»: S_g max 0.0068 вместо 0.0098
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 1, "15000000,0.0,0.000014\n"),
                 3, "Bg", "> 0", id="gas_Bg_zero"),
    # при 10 МПа Ньютон не сходится на первом шаге
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 1, "15000000,-0.008,0.000014\n"),
                 3, "Bg", "> 0", id="gas_Bg_negative"),
    # при 10 МПа молча: S_g max 0.0043
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 1, "15000000,0.008,0\n"),
                 3, "mu_g_Pa_s", "> 0", id="gas_mu_zero"),
    # при 10 МПа Ньютон не сходится на первом шаге
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 1, "15000000,0.008,-0.000014\n"),
                 3, "mu_g_Pa_s", "> 0", id="gas_mu_negative"),
    # узел 5 МПа записан как −5 МПа: при 10 МПа молча S_g max 0.0081
    pytest.param("gas_pvt.csv",
                 _with_row(GAS_HEADER, TABLE_GAS_ROWS, 0, "-5000000,0.020,0.000012\n"),
                 2, "pressure_Pa", "> 0", id="gas_p_negative"),
    # ── Нефть: p, B_o, μ_o > 0, R_s ≥ 0 (строка 4 — насыщенная точка ветви 30) ──
    # Ньютон не сходится на первом шаге, «divide by zero»
    pytest.param("oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                 + "30.0,15000000,0.0,0.0015\n30.0,30000000,1.18,0.0016\n",
                 4, "Bo", "> 0", id="oil_Bo_zero"),
    # при 15 МПа счёт проходит до конца: T min = −245.8 К, сообщений нет
    pytest.param("oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                 + "30.0,15000000,-1.20,0.0015\n30.0,30000000,1.18,0.0016\n",
                 4, "Bo", "> 0", id="oil_Bo_negative"),
    # Ньютон не сходится на первом шаге, «divide by zero»
    pytest.param("oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                 + "30.0,15000000,1.20,0\n30.0,30000000,1.18,0.0016\n",
                 4, "mu_o_Pa_s", "> 0", id="oil_mu_zero"),
    # при 15 МПа молча: T min = 169.8 К
    pytest.param("oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                 + "30.0,15000000,1.20,-0.0015\n30.0,30000000,1.18,0.0016\n",
                 4, "mu_o_Pa_s", "> 0", id="oil_mu_negative"),
    # лишняя ветвь R_s = −5 (p_b = 4 МПа) перед ветвями 0 и 30: в сценарии
    # пробы не задействована, но таблица нефизична
    pytest.param("oil_pvt.csv", OIL_HEADER + "-5.0,4000000,1.02,0.0031\n-5.0,30000000,1.01,0.0033\n"
                 + OIL_BRANCH_0 + OIL_BRANCH_30,
                 2, "Rs_sm3_sm3", "≥ 0", id="oil_Rs_negative"),
    # p_b ветви 0 записано как −5 МПа: при 10 МПа молча T max 351.58 К вместо 351.02
    pytest.param("oil_pvt.csv", OIL_HEADER + "0.0,-5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
                 + OIL_BRANCH_30,
                 2, "pressure_Pa", "> 0", id="oil_p_negative"),
    # ── ОФП: S_g, k_ro, k_rg в [0, 1] ──
    # при 15 МПа Ньютон не сходится (t = 0.33 сут), при 10 МПа молча S_g max 0.035
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 0, "-0.1,1.0,0.0\n"),
                 2, "Sg", "в [0, 1]", id="rp_Sg_negative"),
    # узел за S_g = 1 искажает k_r у S_g → 1; в коротком сценарии не задействован
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "1.2,0.0,0.8\n"),
                 7, "Sg", "в [0, 1]", id="rp_Sg_above_one"),
    # отвергал и TabulatedRelPerm — на английском, без имени файла
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,-0.1,0.8\n"),
                 7, "kro", "в [0, 1]", id="rp_kro_negative"),
    # при 10 МПа молча: S_g max 0.0116
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 0, "0.0,1.2,0.0\n"),
                 2, "kro", "в [0, 1]", id="rp_kro_above_one"),
    # отвергал и TabulatedRelPerm — на английском, без имени файла
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 1, "0.1,0.8,-0.01\n"),
                 3, "krg", "в [0, 1]", id="rp_krg_negative"),
    # в коротком сценарии не задействован (S_g у забоя < 0.01)
    pytest.param("relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,0.0,1.2\n"),
                 7, "krg", "в [0, 1]", id="rp_krg_above_one"),
]

VALUE_READERS = {"oil_pvt.csv": _read_oil_pvt_csv, "gas_pvt.csv": _read_gas_pvt_csv,
                 "relperm.csv": _read_relperm_csv}


class TestCSVValueChecks:
    """CSV-путь отвергает недопустимые значения и неполные таблицы с именем файла (DEBT-044)."""

    # ── Пределы столбцов: проверка при разборе, с номером строки ──

    @pytest.mark.parametrize("name, text, line, column, rule", VALUE_CASES)
    def test_value_out_of_range_raises(self, tmp_path, name, text, line, column, rule):
        """Значение вне пределов столбца → ValueError ридера: файл, строка, столбец, правило.

        Пределы — _OIL_PVT_LIMITS, _GAS_PVT_LIMITS, _RELPERM_LIMITS в factory.py.
        """
        msg = _parse_error(VALUE_READERS[name], _csv(tmp_path, name, text))
        assert f"{name}: строка {line}, столбец {column}:" in msg
        assert f"должно быть {rule}" in msg

    def test_boundary_values_accepted(self, tmp_path):
        """Границы включаются: S_g, k_ro, k_rg = 0 и 1; R_s = 0.

        Ловит строгое неравенство там, где граница допустима: S_g = 0 и
        k_ro = 1 стоят в первой строке всех 15 таблиц ОФП проекта, R_s = 0 —
        ветвь дегазированной нефти.
        """
        Sg, kro, krg = _read_relperm_csv(
            _csv(tmp_path, "relperm.csv", RP_HEADER + "0.0,1.0,0.0\n1.0,0.0,1.0\n"))
        assert (Sg, kro, krg) == ([0.0, 1.0], [1.0, 0.0], [0.0, 1.0])
        rows = _read_oil_pvt_csv(_csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0))
        assert rows[0][0] == 0.0

    def test_value_error_fails_in_from_config(self, tmp_path):
        """B_o < 0 ловится в from_config с именем файла, а не при счёте.

        До правки from_config и run проходили: T min = −245.8 К при
        p_wf = 15 МПа. Ловит вызов ридера в обход проверки пределов.
        """
        config = _table_config_with_csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                                        + "30.0,15000000,-1.20,0.0015\n30.0,30000000,1.18,0.0016\n")
        with pytest.raises(ValueError, match="oil_pvt.csv: строка 4, столбец Bo"):
            SimulatorFactory.from_config(config)

    # ── Таблица целиком: число строк, рост p и S_g, число ветвей ──

    def test_gas_header_only_raises(self, tmp_path):
        """Только заголовок.

        До правки — «GAS_PVT pressure must be strictly increasing with >=2 rows» (pvt.py:32).
        """
        config = _table_config_with_csv(tmp_path, "gas_pvt.csv", GAS_HEADER)
        with pytest.raises(ValueError, match="gas_pvt.csv: строк данных 0, нужно не меньше двух"):
            SimulatorFactory.from_config(config)

    def test_gas_one_row_raises(self, tmp_path):
        """Одна строка: B_g(p) не интерполировать. До правки — то же английское сообщение."""
        config = _table_config_with_csv(tmp_path, "gas_pvt.csv", GAS_HEADER + TABLE_GAS_ROWS[1])
        with pytest.raises(ValueError, match="gas_pvt.csv: строк данных 1, нужно не меньше двух"):
            SimulatorFactory.from_config(config)

    def test_gas_pressure_not_increasing_raises(self, tmp_path):
        """Строки 5 и 15 МПа переставлены.

        До правки — английское сообщение pvt.py:32 без имени файла.
        """
        config = _table_config_with_csv(
            tmp_path, "gas_pvt.csv",
            GAS_HEADER + TABLE_GAS_ROWS[1] + TABLE_GAS_ROWS[0] + TABLE_GAS_ROWS[2])
        with pytest.raises(ValueError,
                           match="gas_pvt.csv: давление не растёт строго: 5 МПа после 15 МПа"):
            SimulatorFactory.from_config(config)

    def test_relperm_header_only_raises(self, tmp_path):
        """Только заголовок: до правки — «RELPERM Sg must be strictly increasing with >=2 rows»."""
        config = _table_config_with_csv(tmp_path, "relperm.csv", RP_HEADER)
        with pytest.raises(ValueError, match="relperm.csv: строк данных 0, нужно не меньше двух"):
            SimulatorFactory.from_config(config)

    def test_relperm_one_row_raises(self, tmp_path):
        """Одна строка ОФП; до правки — то же английское сообщение relperm.py:5."""
        config = _table_config_with_csv(tmp_path, "relperm.csv", RP_HEADER + TABLE_RP_ROWS[0])
        with pytest.raises(ValueError, match="relperm.csv: строк данных 1, нужно не меньше двух"):
            SimulatorFactory.from_config(config)

    def test_relperm_sg_not_increasing_raises(self, tmp_path):
        """Строки S_g = 0.2 и 0.4 переставлены; до правки — английское сообщение relperm.py:5."""
        swapped = TABLE_RP_ROWS[:2] + [TABLE_RP_ROWS[3], TABLE_RP_ROWS[2]] + TABLE_RP_ROWS[4:]
        config = _table_config_with_csv(tmp_path, "relperm.csv", RP_HEADER + "".join(swapped))
        with pytest.raises(ValueError, match="relperm.csv: S_g не растёт строго: 0.2 после 0.4"):
            SimulatorFactory.from_config(config)

    def test_oil_one_branch_raises(self, tmp_path):
        """Одна ветвь R_s = 30: до правки — «OIL_PVT needs >=2 Rs branches, got 1» (pvt.py:46)."""
        config = _table_config_with_csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_30)
        with pytest.raises(ValueError, match="oil_pvt.csv: одна ветвь R_s = 30 м³ст/м³ст"):
            SimulatorFactory.from_config(config)
```

**Проверка после этого шага:**
```powershell
& $py -m pytest tests/test_factory_prototype.py -q -k TestCSVValueChecks   # 25 failed, 1 passed
& $py -m pytest tests/test_factory_prototype.py -q                         # 25 failed, 54 passed
```
- Регресс: не нужен — меняется только файл тестов, остальные тесты не затронуты; быстрый уровень — в шаге 3.
- Не коммитить: красное состояние (см. «Варианты и выбор»).

**Подводные камни:** имена `TABLE_GAS_ROWS`, `TABLE_RP_ROWS`, `VALUE_READERS` выбраны так, чтобы не совпасть с `GAS_ROWS` в `tests/test_prototype_adapter.py:68` (другой модуль, но при поиске по проекту путаница).

**Зависимости:** требует шаг 1; блокирует шаг 3.

**Оценка:** ~190 строк, ~15 мин.

### Шаг 3: Реализация в factory.py

**Цель:** все 26 тестов шага 2 зелёные, остальные не изменились.

**Файлы:** `numerical_solver/gpn_multiphase_solver/factory.py`

**Контекст:** правки 1–2 — `_create_pvt` и `_check_pvto_branches`; правка 3 — две новые функции после `_check_pvto_branches`; правка 4 — `_create_relperm`; правки 5–9 — раздел `# ── CSV-ридеры ──`. Номера строк — на `3a1dcc3`; если база сдвинулась, искать по тексту блока «до» (он встречается в файле ровно один раз — проверено пробой `plan_check.py`).

`lambda v: v > 0` — короткая безымянная функция одного аргумента: возвращает `True`, если значение `v` допустимо. `text, ok = limits[col]` — распаковка пары из словаря: `text` — строка для сообщения, `ok` — функция проверки.

**Что сделать:**

1. `_create_pvt` (`:123-127`): вызвать проверку таблицы газа после ветвей нефти.

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #1 до -->
```python
        # DEBT-038: ветви PVTO — до BlackOilPVT: он их не проверяет, ошибочную
        # таблицу молча интерполирует, а пустую встречает IndexError
        _check_pvto_branches(oil_rows, pc.oil_pvt_file)
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #1 после -->
```python
        # DEBT-038: ветви PVTO — до BlackOilPVT: он их не проверяет, ошибочную
        # таблицу молча интерполирует, а пустую встречает IndexError
        _check_pvto_branches(oil_rows, pc.oil_pvt_file)
        # DEBT-044: число строк и рост давления газа проверяет и BlackOilPVT
        # (pvt.py:32), но на английском и без имени файла
        _check_gas_pvt_table(gas_rows, pc.gas_pvt_file)
```

2. `_check_pvto_branches` (`:168-194`): docstring и правило «не меньше двух ветвей».

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #2 до -->
```python
    """Ветви PVTO: ≥ 2 строк, p и p_b(R_s) растут, иначе ValueError (DEBT-038)."""
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #2 после -->
```python
    """PVTO: ≥ 2 ветвей по ≥ 2 строк, p и p_b(R_s) растут, иначе ValueError (DEBT-038, DEBT-044)."""
```

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #3 до -->
```python
    for Rs, p_bar, _, _ in oil_rows:
        branches.setdefault(Rs, []).append(p_bar)
    for Rs, p_bar in sorted(branches.items()):
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #3 после -->
```python
    for Rs, p_bar, _, _ in oil_rows:
        branches.setdefault(Rs, []).append(p_bar)
    # DEBT-044: B_o, μ_o интерполируются между соседними ветвями R_s; с одной
    # ветвью BlackOilPVT отказывает без имени файла (pvt.py:46)
    if len(branches) < 2:
        Rs = list(branches)[0]
        raise ValueError(
            f"{oil_pvt_file}: одна ветвь R_s = {Rs:g} м³ст/м³ст, нужно не меньше "
            f"двух: B_o и μ_o интерполируются между ветвями R_s. У дегазированной "
            f"нефти (Rs0 = 0) добавьте ветвь с R_s > 0.")
    for Rs, p_bar in sorted(branches.items()):
```

3. Новые функции — после `_check_pvto_branches`, перед комментарием `# Допуск пересыщения на старте` (`:221`).

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #4 до -->
```python
                f"м³ст/м³ст. p_b — давление первой строки ветви.")


# Допуск пересыщения на старте, м³ст/м³ст, — rs_switch_tol решателя
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #4 после -->
```python
                f"м³ст/м³ст. p_b — давление первой строки ветви.")


def _check_gas_pvt_table(gas_rows: list[tuple], gas_pvt_file: str) -> None:
    """Таблица газа: ≥ 2 строк, давление строго растёт, иначе ValueError (DEBT-044)."""
    # Правила PVDG (OPM Flow Manual, табл. 8.127). Их же проверяют XLSX-ридер
    # прототипа (input_reader.py:71-72) и BlackOilPVT (pvt.py:32) — последний
    # без имени файла. B_g(p), μ_g(p) интерполируются np.interp по давлению,
    # а он не проверяет рост узлов и на нерастущих молча ошибается.
    # Убывание B_g (PVDG его тоже требует) не проверяется: рост B_g — это
    # c_g < 0, о нём предупреждает _warn_negative_compressibility (BUG-019).
    # Значения столбцов (p, B_g, μ_g > 0) проверены при разборе (_GAS_PVT_LIMITS).
    if len(gas_rows) < 2:
        raise ValueError(
            f"{gas_pvt_file}: строк данных {len(gas_rows)}, нужно не меньше двух: "
            f"B_g и μ_g интерполируются по давлению.")
    for k in range(1, len(gas_rows)):
        # давление в барах — как его получает BlackOilPVT; в сообщении — МПа
        p_prev, p_k = gas_rows[k - 1][0], gas_rows[k][0]
        if p_k <= p_prev:
            raise ValueError(
                f"{gas_pvt_file}: давление не растёт строго: "
                f"{p_k * BAR_TO_PA / 1e6:g} МПа после {p_prev * BAR_TO_PA / 1e6:g} МПа. "
                f"Строки — по возрастанию давления.")


def _check_relperm_table(Sg: list, relperm_file: str) -> None:
    """Таблица ОФП: ≥ 2 строк, S_g строго растёт, иначе ValueError (DEBT-044)."""
    # Правила SGOF (OPM Flow Manual, табл. 8.165). Их же проверяет
    # TabulatedRelPerm (relperm.py:5) — без имени файла; k_ro(S_g), k_rg(S_g)
    # интерполируются np.interp по S_g. Пределы S_g, k_r в [0, 1] проверены
    # при разборе (_RELPERM_LIMITS). Монотонность k_r, которую требует SGOF,
    # не проверяется (решение пользователя 2026-10-07, план DEBT-044).
    if len(Sg) < 2:
        raise ValueError(
            f"{relperm_file}: строк данных {len(Sg)}, нужно не меньше двух: "
            f"k_ro и k_rg интерполируются по S_g.")
    for k in range(1, len(Sg)):
        if Sg[k] <= Sg[k - 1]:
            raise ValueError(
                f"{relperm_file}: S_g не растёт строго: {Sg[k]:g} после {Sg[k - 1]:g}. "
                f"Строки — по возрастанию S_g.")


# Допуск пересыщения на старте, м³ст/м³ст, — rs_switch_tol решателя
```

4. `_create_relperm` (`:318-320`): вызвать проверку таблицы ОФП до `TabulatedRelPerm`.

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #5 до -->
```python
        Sg, kro, krg = _read_relperm_csv(config.config_dir / rc.file)

        from radial_blackoil.relperm import TabulatedRelPerm
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #5 после -->
```python
        Sg, kro, krg = _read_relperm_csv(config.config_dir / rc.file)
        # DEBT-044: те же правила проверяет TabulatedRelPerm, но без имени файла
        _check_relperm_table(Sg, rc.file)

        from radial_blackoil.relperm import TabulatedRelPerm
```

5. Пределы столбцов — после `_RELPERM_COLUMNS` (`:435`).

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #6 до -->
```python
_RELPERM_COLUMNS = ["Sg", "kro", "krg"]
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #6 после -->
```python
_RELPERM_COLUMNS = ["Sg", "kro", "krg"]

# Допустимые значения столбцов (DEBT-044): пара (текст для сообщения, проверка).
# lambda v: v > 0 — короткая функция: True, если значение v допустимо.
# Проверяется значение из файла, до перевода единиц: сравнение с 0 и 1 от
# единиц не зависит. Почему такие пределы:
#   - B и μ стоят в знаменателях запасов и подвижностей (blackoil.py:162, 182):
#     ноль — деление на ноль, отрицательное значение — отрицательная масса или
#     подвижность (проба vault/issues/debt-044/probes/red_state.py: при B_o < 0
#     расчёт проходит до конца с T = −246 К и без единого сообщения);
#   - давление абсолютное, R_s — объём растворённого газа: меньше нуля не бывают;
#   - S_g, k_ro, k_rg — доли, [0, 1], как в SGOF (OPM Flow Manual, табл. 8.165)
#     и в CoreyRP (k_r,max ≤ 1, pvt/relperm.py:21).
_POSITIVE = ("> 0", lambda v: v > 0)
_NON_NEGATIVE = ("≥ 0", lambda v: v >= 0)
_FRACTION = ("в [0, 1]", lambda v: 0 <= v <= 1)
_OIL_PVT_LIMITS = {"Rs_sm3_sm3": _NON_NEGATIVE, "pressure_Pa": _POSITIVE,
                   "Bo": _POSITIVE, "mu_o_Pa_s": _POSITIVE}
_GAS_PVT_LIMITS = {"pressure_Pa": _POSITIVE, "Bg": _POSITIVE, "mu_g_Pa_s": _POSITIVE}
_RELPERM_LIMITS = {"Sg": _FRACTION, "kro": _FRACTION, "krg": _FRACTION}
```

6. `_read_numeric_csv`: сигнатура и комментарий правил. Docstring не меняется: значение вне пределов — тоже «ошибка в строке», ссылку на DEBT-044 даёт комментарий правил.

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #7 до -->
```python
def _read_numeric_csv(csv_path: Path, columns: list[str], kind: str) -> list[tuple]:
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #7 после -->
```python
def _read_numeric_csv(csv_path: Path, columns: list[str], limits: dict,
                      kind: str) -> list[tuple]:
```

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #8 до -->
```python
    #   - в остальных строках полей ровно len(columns), каждое — конечное
    #     число (float() принимает nan и inf, их отсекает np.isfinite).
    # Число строк и допустимость значений здесь не проверяются. Часть из них
    # делают _check_pvto_branches (нефть) и конструкторы прототипа (газ, ОФП);
    # B_g > 0, mu_g > 0, S_g в [0, 1] не проверяет никто — DEBT-044.
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #8 после -->
```python
    #   - в остальных строках полей ровно len(columns), каждое — конечное
    #     число (float() принимает nan и inf, их отсекает np.isfinite);
    #   - значение в пределах столбца limits[col] (DEBT-044): здесь известен
    #     номер строки файла, после разбора он теряется.
    # Правила таблицы целиком (число строк, рост давления и S_g, ветви R_s)
    # проверяют _check_pvto_branches, _check_gas_pvt_table, _check_relperm_table.
```

7. `_read_numeric_csv`: проверка предела после проверки конечности.

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #9 до -->
```python
                if not np.isfinite(value):
                    raise ValueError(f"{where}, столбец {col}: {field!r} — не конечное число.")
                values.append(value)
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #9 после -->
```python
                if not np.isfinite(value):
                    raise ValueError(f"{where}, столбец {col}: {field!r} — не конечное число.")
                text, ok = limits[col]
                if not ok(value):
                    raise ValueError(f"{where}, столбец {col}: {field!r} — должно быть {text}.")
                values.append(value)
```

8. Ридеры передают свои пределы.

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #10 до -->
```python
    rows = _read_numeric_csv(csv_path, _OIL_PVT_COLUMNS, "oil PVT")
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #10 после -->
```python
    rows = _read_numeric_csv(csv_path, _OIL_PVT_COLUMNS, _OIL_PVT_LIMITS, "oil PVT")
```

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #11 до -->
```python
    rows = _read_numeric_csv(csv_path, _GAS_PVT_COLUMNS, "gas PVT")
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #11 после -->
```python
    rows = _read_numeric_csv(csv_path, _GAS_PVT_COLUMNS, _GAS_PVT_LIMITS, "gas PVT")
```

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #12 до -->
```python
    rows = _read_numeric_csv(csv_path, _RELPERM_COLUMNS, "relperm")
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #12 после -->
```python
    rows = _read_numeric_csv(csv_path, _RELPERM_COLUMNS, _RELPERM_LIMITS, "relperm")
```

9. `_read_relperm_csv`: комментарий о пустой таблице.

<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #13 до -->
```python
    # падает ValueError без имени файла; так — три пустых списка, и отказ
    # даёт TabulatedRelPerm, как до DEBT-042
```
<!-- правка numerical_solver/gpn_multiphase_solver/factory.py #13 после -->
```python
    # падает ValueError без имени файла; так — три пустых списка, и отказ
    # с именем файла даёт _check_relperm_table (DEBT-044)
```

**Проверка после этого шага:**
```powershell
& $py -m pytest tests/test_factory_prototype.py -q          # 79 passed
& $py -m pytest tests/test_pvt_consistency.py -q            # 37 passed (BUG-019 не задет)
& $py -m pytest tests/ -m "not slow" -q                     # 1134 passed
```
- Регресс: быстрый.
- Коммит: `feat: проверка допустимости значений CSV-таблиц фабрики — пределы столбцов с номером строки, число строк, рост p и S_g, ветви R_s; 26 тестов (DEBT-044)` — `factory.py` и `test_factory_prototype.py` одним коммитом.

**Подводные камни:** порядок проверок в разборщике (число полей → `float` → конечность → предел) сохраняет все сообщения DEBT-042; см. чеклист «Существующие тесты с испорченными таблицами».

**Зависимости:** требует шаг 2; блокирует шаги 4–7.

**Оценка:** ~75 строк, ~15 мин.

### Шаг 4: Таблицы и конфиги проекта проходят новые проверки

**Цель:** ни одна из 47 таблиц не отвергнута, чтение побитово прежнее, каждый испорченный случай пробы отвергнут в `from_config` с именем файла.

**Файлы:** `vault/issues/debt-044/probes/tables_check.py`, `tables_check.out.txt`, `red_state.out.txt` → `green_state.out.txt`.

**Что сделать** (из `<W>\numerical_solver`):
1. Таблицы и конфиги:
   ```powershell
   & $py "$pr\tables_check.py" 2>$null | Tee-Object -FilePath "$pr\tables_check.out.txt"
   ```
   Ожидание:
   - `Код: <W>\...\factory.py`;
   - «Таблиц: 47 {'oil_pvt.csv': 16, 'gas_pvt.csv': 16, 'relperm.csv': 15}, отвергнуто: 0»;
   - «Конфигов с табличным PVT или ОФП: 17, from_config отказал: 0 (не конфиги решателя: 0)».

   Если таблиц или конфигов больше — база сдвинулась, это нормально; важно «0».
   Если хоть одна таблица или конфиг отвергнуты — **стоп**, вопрос пользователю.
2. Побитовое чтение — проба DEBT-042 со снимком:
   ```powershell
   & $py "<W>\vault\issues\debt-042\probes\tables_check.py" --compare
   ```
   Ожидание: «Сверка со снимком: побитово совпадает».
3. Зелёное состояние той же пробой:
   ```powershell
   & $py "$pr\red_state.py" 2>$null | Tee-Object -FilePath "$pr\green_state.out.txt"
   ```
   Ожидание: в каждом из двух режимов строка «эталон (без подмены)» — та же, что в `red_state.out.txt`; остальные 23 случая — `from_config: ValueError: <имя файла>: …` с местом в `factory.py`, ни одного `run:` и ни одного `ПРОШЛИ`. Тексты сообщений — как в выводе `plan_check.out.txt`, этап 5.
4. Коммит новых выводов на ветке (`git -C <W> add` по именам): `tables_check.out.txt`, `green_state.out.txt` — `vault: DEBT-044 — проверка таблиц проекта и зелёное состояние`. Пробы (`*.py`) и `red_state.out.txt` уже в базе с предварительного коммита `/implement` и не меняются.

**Проверка:** Регресс: не нужен (код не менялся).

**Зависимости:** требует шаг 3.

**Оценка:** 0 строк кода, ~5 мин.

### Шаг 5: Документация формата CSV

**Цель:** правила допустимости записаны там, где ищут формат таблиц.

**Файлы:**
- `vault/knowledge/decisions/P8-формат-ввода-json.md` (строки 77, 93, 102-114)
- `numerical_solver/examples/04_table_table/README.md` (строки 47-55)

README 04 читает один класс тестов — `TestReadme` (`tests/test_examples.py:453-478`, быстрый уровень, 55 тестов на все README): он ищет «Как модифицировать», `PrototypeHydroAdapter`, `TridiagEnergySolver` и, для части примеров, «увеличить газонасыщенность». Правка этих строк не трогает (`plan_check.py`, этап 1: «строки, которые ищет TestReadme, сохранены»), но прогон `TestReadme` после правки обязателен — см. «Проверка». (До аудита 2 план утверждал, что README 04 тестами не читается, — это неверно.)

**Что сделать:**

1. P8, общие правила (строка 77) — дописать абзац о пределах:

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #1 до -->
```markdown
Нарушение — `ValueError` фабрики с именем файла, номером строки и столбцом.
```
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #1 после -->
```markdown
Нарушение — `ValueError` фабрики с именем файла, номером строки и столбцом.

Допустимые значения (DEBT-044, проверка при разборе, сообщение с номером строки и столбцом): $R_s \ge 0$; давление, $B_o$, $\mu_o$, $B_g$, $\mu_g$ больше нуля; $S_g$, $k_{ro}$, $k_{rg}$ — от 0 до 1 включительно. Значение проверяется в единицах файла. До DEBT-044 недопустимое значение проходило молча или роняло счёт: при $B_o < 0$ расчёт `configs/table_pvt` шёл до конца с $T = -246$ К (проба `vault/issues/debt-044/probes/red_state.py`).
```

2. P8, ветви PVTO (строка 93, меняется только скобка «число ветвей — …») — источник проверки числа ветвей:

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #2 до -->
```markdown
Ветвь — все строки с одним $R_s$. В ветви не меньше двух строк: первая — насыщенная точка $p_b(R_s)$, дальше давление строго растёт по порядку строк. Давление насыщения $p_b$ строго растёт с $R_s$. Ветвей не меньше двух. Нарушение — `ValueError` фабрики с именем файла и ветвью (`_check_pvto_branches`, DEBT-038; число ветвей — `BlackOilPVT`, DEBT-036). OPM допускает ветвь из одной строки (кроме последней) и достраивает её по следующей ветви с недонасыщенными строками; решатель так не делает, поэтому такая ветвь — ошибка.
```
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #2 после -->
```markdown
Ветвь — все строки с одним $R_s$. В ветви не меньше двух строк: первая — насыщенная точка $p_b(R_s)$, дальше давление строго растёт по порядку строк. Давление насыщения $p_b$ строго растёт с $R_s$. Ветвей не меньше двух. Нарушение — `ValueError` фабрики с именем файла и ветвью (`_check_pvto_branches`, DEBT-038; число ветвей — DEBT-044, до него отказывал `BlackOilPVT` без имени файла). OPM допускает ветвь из одной строки (кроме последней) и достраивает её по следующей ветви с недонасыщенными строками; решатель так не делает, поэтому такая ветвь — ошибка.
```

3. P8, газ — после образца `gas_pvt.csv`, перед заголовком раздела ОФП (вставка абзаца и пустой строки перед `### Формат relperm.csv`; заголовок в файле один):

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #3 до -->
```markdown
### Формат relperm.csv
```
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #3 после -->
```markdown
Не меньше двух строк, давление строго растёт по порядку строк (`_check_gas_pvt_table`, DEBT-044). Убывание $B_g$ с давлением, которого требует PVDG (OPM Flow Manual, табл. 8.127), не проверяется: рост $B_g$ — отрицательная сжимаемость газа, о ней фабрика предупреждает (BUG-019), расчёт продолжается.

### Формат relperm.csv
```

4. P8, ОФП — после «Безразмерные — конвертация не нужна.»:

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #4 до -->
```markdown
Безразмерные — конвертация не нужна.
```
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #4 после -->
```markdown
Безразмерные — конвертация не нужна.

Не меньше двух строк, $S_g$ строго растёт (`_check_relperm_table`, DEBT-044). Монотонность $k_{rg}$ (не убывает) и $k_{ro}$ (не возрастает), которой требует SGOF (OPM Flow Manual, табл. 8.165), не проверяется.
```

5. README 04 — значения и правила газа и ОФП:

<!-- правка numerical_solver/examples/04_table_table/README.md #1 до -->
```markdown
Заголовок — ровно эти имена через запятую, в этом порядке. Десятичный
разделитель — точка. В каждой строке столько же чисел, сколько столбцов.
Иначе расчёт не начнётся: фабрика назовёт файл, строку и столбец.

`oil_pvt.csv` — таблица PVTO: строки сгруппированы по веткам $R_s$.
В каждой ветке не меньше двух строк: первая — давление насыщения,
дальше давление строго растёт; давление насыщения растёт от ветки
к ветке. Иначе расчёт не начнётся: фабрика сообщит, какая ветка ошибочна.
В демонстрационном файле только две ветки: $R_s \in \{0, 30\}$.
```
<!-- правка numerical_solver/examples/04_table_table/README.md #1 после -->
```markdown
Заголовок — ровно эти имена через запятую, в этом порядке. Десятичный
разделитель — точка. В каждой строке столько же чисел, сколько столбцов.
Давление, $B_o$, $\mu_o$, $B_g$, $\mu_g$ больше нуля, $R_s \ge 0$,
$S_g$, $k_{ro}$, $k_{rg}$ — от 0 до 1.
Иначе расчёт не начнётся: фабрика назовёт файл, строку и столбец.

`oil_pvt.csv` — таблица PVTO: строки сгруппированы по веткам $R_s$.
Веток не меньше двух. В каждой ветке не меньше двух строк: первая —
давление насыщения, дальше давление строго растёт; давление насыщения
растёт от ветки к ветке. Иначе расчёт не начнётся: фабрика сообщит,
какая ветка ошибочна. В демонстрационном файле только две ветки:
$R_s \in \{0, 30\}$.

В `gas_pvt.csv` не меньше двух строк, давление строго растёт. В
`relperm.csv` не меньше двух строк, $S_g$ строго растёт.
```

**Проверка:**
```powershell
& $py -m pytest tests/test_examples.py -q -k TestReadme   # 55 passed
& $py -m pytest tests/ --collect-only -q                  # 1370 (или база + 26)
```
Регресс: только `TestReadme` — шаг меняет документы, из тестов их читает лишь он.

- Коммиты: README 04 — `docs: README 04 — допустимые значения CSV-таблиц (DEBT-044)` на ветке задачи; P8 — `vault: P8 — допустимые значения CSV-таблиц (DEBT-044)` на ветке задачи.

**Зависимости:** требует шаг 3.

**Оценка:** ~20 строк, ~10 мин.

### Шаг 6: Верификация — полный прогон

**Цель:** весь набор тестов зелёный.

```powershell
& $py -m pytest tests/ -q        # 1370 passed, ~10 мин
```

Регресс: полный — конец реализации (`/implement` §3.1). Примеры (`test_examples.py`, метка `slow`) строят все табличные конфиги через `from_config`: это вторая, независимая от пробы шага 4 проверка того, что таблицы проекта проходят.

**Зависимости:** требует шаги 3–5.

**Оценка:** ~10 мин.

### Шаг 7: Vault и issue

**Цель:** задача отмечена реализованной, issue прокомментирован.

**Что сделать:**
1. Реестр, запись DEBT-044: статус «✅ ГОТОВО (<дата>), не влит — ветка … : 1344 → 1370 тестов, полный прогон зелёный, 47 таблиц проходят, чтение побитово».
2. План: `status: реализован`.
3. Комментарий в issue #74: `vault/issues/debt-044/05-comment-done.md` (итог, числа тестов, ссылки на `green_state.out.txt`, `tables_check.out.txt`).

**Зависимости:** требует шаг 6.

**Оценка:** ~10 мин.

## Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_value_out_of_range_raises` ×17 | `tests/test_factory_prototype.py` (раздел I, новый) | одна строка таблицы `configs/table_pvt` со значением вне пределов: $B$, $\mu$, $p$ = 0 или < 0; $R_s < 0$; $S_g$, $k_{ro}$, $k_{rg}$ < 0 или > 1 | `ValueError` ридера, `"<файл>: строка N, столбец X:"` и `"должно быть <правило>"` | молчаливое принятие нефизичного значения (замер — комментарий к каждому случаю) |
| `test_boundary_values_accepted` | там же | $S_g$, $k_r$ = 0 и 1, $R_s = 0$ | читается без ошибки | строгое неравенство вместо нестрогого |
| `test_value_error_fails_in_from_config` | там же | $B_o < 0$ через `from_config` | `ValueError` `oil_pvt.csv: строка 4, столбец Bo` | ридер вызван без пределов (до правки — $T_{\min} = -246$ К) |
| `test_gas_header_only_raises`, `test_gas_one_row_raises` | там же | газ: 0 и 1 строка | `gas_pvt.csv: строк данных 0/1, нужно не меньше двух` | английский отказ `pvt.py:32` без файла |
| `test_gas_pressure_not_increasing_raises` | там же | строки 5 и 15 МПа переставлены | `gas_pvt.csv: давление не растёт строго: 5 МПа после 15 МПа` | то же |
| `test_relperm_header_only_raises`, `test_relperm_one_row_raises` | там же | ОФП: 0 и 1 строка | `relperm.csv: строк данных 0/1, …` | английский отказ `relperm.py:5` |
| `test_relperm_sg_not_increasing_raises` | там же | строки 0.2 и 0.4 переставлены | `relperm.csv: S_g не растёт строго: 0.2 после 0.4` | то же |
| `test_oil_one_branch_raises` | там же | нефть: одна ветвь $R_s = 30$ | `oil_pvt.csv: одна ветвь R_s = 30 м³ст/м³ст` | английский отказ `pvt.py:46` |

**Неизменность поведения:**
- `TestCSVReaders`, `TestCSVStrictParsing` (DEBT-042), `TestPVTOBranches` (DEBT-038), `TestInitialStateVsTable` (BUG-017), `TestConfigErrors` — без правок, зелёные;
- `tests/test_pvt_consistency.py` (BUG-019, 37 тестов) — предупреждения о $c < 0$ те же: убывание $B_g$ не проверяется (решение 4);
- `tests/test_examples.py::TestReadme` (55 тестов, быстрый уровень) — README 04 после шага 5 сохраняет разделы и имена классов, которые он ищет;
- `tests/test_examples.py` (slow) — все примеры с табличным PVT и ОФП строятся и считаются как раньше;
- проба DEBT-042 `tables_check.py --compare` — чтение 47 таблиц побитово прежнее.

## Критерии завершения

- [x] Шаги 1–7 выполнены
- [x] Быстрый уровень 1134 passed (88.8 с); полный 1370 passed (379 с, 1 warning — `PytestRemovedIn10Warning` в `test_val002.py`, был и в базе)
- [x] 47 таблиц и все 17 табличных конфигов проходят (`tables_check.out.txt`), чтение побитово прежнее (`debt-042/probes/tables_check.py --compare`)
- [x] Каждый случай `red_state.py` отвергнут в `from_config` с именем файла: 48 из 48 (24 случая × 2 режима), «эталон» совпадает с красным замером (`green_state.out.txt`)
- [x] Прототип не изменён (`git diff --stat cf86aa2 HEAD -- numerical_solver/HydroSolverPrototype` пуст)
- [x] P8 и README 04 описывают новые правила; `TestReadme` 55 passed
- [x] Реестр, план, комментарий issue обновлены

**Реализация (2026-10-07).** Worktree `.worktrees/debt-044`, ветка от `cf86aa2`. Код, тесты и документы перенесены из блоков плана без отклонений: после каждого шага текст файла сверен программой с результатом применения правок плана к версии `cf86aa2` — совпадает побайтно (`factory.py`, `test_factory_prototype.py`, P8, README 04). Красное состояние на коде ветки до правки совпало с замером плана (отличается только строка с путём к коду).

## Обнаруженные проблемы

Новых записей в реестр план не добавляет:
- отказ `BlackOilPVT` при одной ветви (`pvt.py:46`) без имени файла — найден при `/issue`, входит в эту задачу (решение 3);
- монотонность $k_r$ по SGOF и убывание $B_g$ по PVDG — сознательно вне задачи (решения 2 и 4), не долг;
- **(аудит)** решатель принимает состояние с $T \le 0$: при $B_o < 0$ расчёт дошёл до конца с $T_{\min} = -245.8$ К без отказа, проверки $T > 0$ в `gpn_multiphase_solver/` нет (grep). DEBT-044 убирает этот источник для CSV-таблиц, но не сам пробел. Зарегистрировано по решению пользователя — [[DEBT-047]] (2026-10-07); на реализацию DEBT-044 не влияет.

## Оценка

`factory.py` ~+75 строк, тесты ~+190 строк, документы ~+20 строк. Время реализации ~1 ч, из них ~10 мин — полный прогон.

## Проверка плана

Проба `vault/issues/debt-044/probes/plan_check.py` (2026-10-07, код `3a1dcc3`, вывод — `plan_check.out.txt`). Она берёт правки прямо из этого файла: перед каждым блоком кода стоит метка `<!-- правка <файл> #N до|после|в конец -->`. Правки применяются к текстам файлов в памяти, файлы проекта не меняются. Код `factory.py` с правками исполняется в пространстве имён загруженного модуля (подмена в памяти). Файл тестов с правками пишется во временный каталог рядом с пробой и прогоняется настоящим pytest. Каждый этап — отдельный процесс. Результаты:

1. Все 20 правок применимы: каждый блок «до» встречается в своём файле ровно один раз (13 в `factory.py`, 2 в тестах, 4 в P8, 1 в README 04).
2. Тесты плана на текущем коде: 25 failed, 54 passed (53 прежних + `test_boundary_values_accepted`).
3. На коде с правками: 79 passed.
4. Таблицы проекта: 47, отвергнуто 0; конфигов с табличным PVT или ОФП 17, `from_config` отказал 0.
5. Проба `red_state.py` на коде с правками: «эталон» в обоих режимах совпадает с красным замером, все 23 испорченных случая отвергнуты в `from_config` с именем файла (строка и столбец — для пределов).
6. Быстрый уровень существующих тестов на коде с правками (`--fast`): 1108 passed, 1 warning — как без подмены.

**Аудит (2026-10-07, база `6d14a5c`).** После правок аудита (перенос длинных строк, docstring `_read_numeric_csv` оставлен прежним) этапы 1–5 повторены: правки применимы, 25 failed / 54 passed → 79 passed, таблицы и конфиги — 0 отказов, «эталон» пробы совпадает с красным замером. Добавленные строки кода не длиннее 100 символов (максимум в файлах сейчас: `factory.py` — 96, тесты — 100). Быстрый уровень после правок аудита не повторялся: изменились только форматирование тестов и docstring, логика кода — нет.

**Аудит 2 (2026-10-07, база `9d4321d`, после влития DEBT-041).** Проба дополнена этапом 3a: тесты плана с настройками pytest из `numerical_solver/pyproject.toml`, хуком `tests/conftest.py` (подключён плагином) и отбором `-m "not slow"`, как в быстром уровне, — 79 passed. До этого тесты шли из временного каталога без настроек проекта. Этап 1 дополнен проверкой README 04: строки, которые ищет `TestReadme`, сохранены. Полный прогон пробы с `--fast` (вывод — `plan_check.out.txt`): правки применимы, 25 failed / 54 passed → 79 passed (и 79 в условиях быстрого уровня), 47 таблиц и 17 конфигов — 0 отказов, 23 испорченных случая отвергнуты с именем файла, быстрый уровень на коде с правками — 1108 passed.

При реализации правки вносятся Edit-ом по тем же блокам «до → после». Если база сдвинулась, перед шагом 2 запусти `plan_check.py` из `<W>\numerical_solver`: этап 1 покажет, какая правка перестала находиться.

## Связанные заметки

- [[известные баги и технический долг]] — записи DEBT-044, DEBT-042, DEBT-038, BUG-019
- [[debt-042 strict-csv-readers]] — разборщик, на котором строится план
- [[P8-формат-ввода-json]] — формат CSV-таблиц
- `vault/issues/debt-044/` — тело issue, пробы
