---
tags:
  - план
  - инфраструктура
date: 2026-10-18
issue: FEAT-035
github: 133
branch: feat/feat-035/workbook-to-config
model_level: null
status: реализован
merged: 86348ed (2026-10-18)
worktree: .worktrees/feat-035; удалён после влития
audit:
  date: 2026-10-18
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# FEAT-035: перевод книги в конфиг — `gpn-solver convert`

**GitHub issue:** [#133](https://github.com/ArturSalamatin/Oil_Gas/issues/133) — найденное при открытии (2026-10-18, `55868a6`) — в разделе «Найдено при открытии» тела issue (`vault/issues/feat-035/01-issue-body.md`).

Цепочка: [[feat-033 workbook-input-format|FEAT-033]] (формат, таблица полей; влит `7036854`) → [[feat-034 xlsx-cell-reader|FEAT-034]] (разбор ячеек; влит `25b7eee`) → **FEAT-035** (перевод) → [[feat-036 run-from-workbook|FEAT-036]] (расчёт по книге) → FEAT-031 (поставка).

## Как начать работу по этому плану

1. Прочитай этот файл целиком. Новых формул в задаче нет; `problem_statement.tex` нужен только для метки `eq:main_rhocpeff` ($(\rho c_p)_s$), `moments_method.tex` не нужен.
2. **Код плана проверен на копии дерева** — `vault/issues/feat-035/probes/plan_code/`: `workbook_convert.py` (модуль), `test_workbook_convert.py` (тесты), `cli.py` (командная строка целиком), `test_cli_convert.py` (блок в конец `tests/test_cli.py`). **Источник кода шагов 1–3 — эти файлы**, переносятся как есть. Проверка — `probes/plan_apply.py`, вывод — `probes/plan_apply.out.txt` (§12).
3. Прочитай заметки [[книга ввода Excel версии 1 — все параметры явно, единицы фиксированы]] (формат) и [[разбор книги xlsx сообщает тип ячейки — отказ по типу решает перевод]] (API разбора).
4. Worktree и ветка — `/implement` (база `numerical_scheme/implementation`, ветка `feat/feat-035/workbook-to-config`; на 2026-10-18 её нет ни локально, ни на origin).
5. Обозначения — как в `/implement`: `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas`; `<W>` = `<КОРЕНЬ>\.worktrees\feat-035`; `<PY>` = `<КОРЕНЬ>\numerical_solver\.venv\Scripts\python.exe` — venv один, в основном каталоге: **в worktree своего `.venv` нет**. pytest из `<W>\numerical_solver` берёт пакет и прототип worktree.
6. Baseline (из `<W>\numerical_solver`): `<PY> -m pytest tests/ --collect-only -q` — **2288 тестов на `55868a6`**; `<PY> -m pytest tests/ -m "not slow" -q` — быстрый уровень. Прототип не меняется: его тесты и регрессия не нужны. Быстрый уровень на базе — 2011 passed, 1 skipped (черновик руководителя вне git). База могла уйти дальше — число сверить при baseline, ожидания сдвинуть на разницу (задача добавляет 107 тестов).
   **Команды — только из `<W>\numerical_solver`** и только `<PY> -m gpn_multiphase_solver …`: каталог запуска стоит первым в `sys.path`, и берётся пакет worktree; из `<W>` или другого каталога `<PY>` импортирует пакет основного каталога (редактируемая установка). Консольной команды `gpn-solver` в `.venv` основного каталога нет (установка сделана до FEAT-030) — в шагах она не используется.
   **Чужие незакоммиченные правки** (аудит 1, 2026-10-18): в основном каталоге другая сессия правит `vault/plans/feat-031 customer-delivery-kit.md` и реестр `планируемые фичи.md` (FEAT-037). Первый коммит `/implement` (материалы задачи в базу): реестры и `index.md` — целиком (общие файлы), план FEAT-031 — не трогать, он не этой задачи.
7. **Докстринги** (CLAUDE.md, «Файлы и код»): перевод — внутренний код (решение 27): одна строка у каждой функции, ссылка на метку уравнения — только у $(\rho c_p)_s$ (`eq:main_rhocpeff`, в комментарии).
8. Начни с шага 1. После каждого шага — проверка по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

## 0. Решения пользователя

Записаны в черновике 2026-10-14…18 (1–18), приняты при планировании 2026-10-18 (19–22), умолчания плана — предложены здесь, «если не возразите» (23–34; 35 — добавлено аудитом 1).

1. **JSON — канонический формат, книга переводится в него** (2026-10-14).
2. **Перевод — в файлы** (предложение 2026-10-14, принято решением 1): `config.json` + `oil_pvt.csv`, `gas_pvt.csv`, `relperm.csv`; дальше обычный `load_config(path)`. Вход расчёта сохраняется (пункт 17 обсуждения, согласовано) — у [[feat-036 run-from-workbook|FEAT-036]] это `output/input/`.
3. **Единицы инженерные, фиксированные, столбец единиц сверяется точно** (2026-10-14); пробелы по краям — решение 20.
4. **Сообщения:** физические ошибки — пока по узлам JSON (2026-10-14). Ошибки самой книги (тип ячейки, единица, неизвестный ключ, порядок времён) возникают до JSON — с листом и ячейкой (предложение).
5. **Интервал истории — с точностью 1 мс** (2026-10-15), как в конвертере примера 18 (`examples/18_prototype_input/prototype_input.py`: `round((t_b − t_a)·DAY, 3)`). Без округления 10 с, записанные в книге как $1.157\ldots\cdot10^{-4}$ сут, дают интервал 10.0000000000x с. Нулевой интервал после округления — отказ. **Способ округления — решение 19** (моменты, а не разности).
6. **Типы ячеек** (2026-10-14): целые поля — из вещественных (350.0 → 350, 350.5 — отказ); дата, число строкой, логическое в числовом поле, формула без значения — отказ с адресом; пустое обязательное значение — отказ. ~~Слово «выключено» — `null`~~ — отменено решением 17 (слова `none` в книге нет).
7. **Конвертер примера 18 и тесты [[VAL-005]] не меняются** (2026-10-15).
8. **Смысл SCHEDULE** ([[feat-033 workbook-input-format|FEAT-033]], решения 9, 32): строка $k$ — момент $t_k$ и режим на $[t_k, t_{k+1}]$; последняя строка — только момент завершения расчёта (2026-10-15), её режим не используется, заполненный — молча пропускается (FEAT-033, решение 40); общее время расчёта отдельно не задаётся. Каждая строка — момент записи, столбца «шаг записи» нет (решение 30). Шаги `dt_integration`, `dt_after_control_change` — в часах (решение 31).
9. **Тест «шаблон читается»** (2026-10-15): `numerical_solver/configs/INPUT_TEMPLATE_v1.xlsx` ([[feat-033 workbook-input-format|FEAT-033]], решение 38) переводится в конфиг, и `load_config` его принимает. Не сравнение книг: снимок генератора отстаёт от таблицы полей при её изменении — новое обязательное поле, переименованный ключ, другая единица, другой `format_version` дают отказ перевода; тест ловит это у нас, а не у заказчика. Нет строки — отказ (решение 15). Актуальную книгу всегда даёт `gpn-solver template`.
10. **Умолчания перевода** (предложены 2026-10-15 как «решу при `/plan-feature`, если не возразите» — возражений не было): `convert` в непустой каталог — отказ; одна строка SCHEDULE — один интервал `{"dt": …}` (без сжатия в `{dt, repeat}`); неизвестный ключ на листе — отказ; лишние листы — пропускаются.
11. **Листа OUTPUT нет** ([[feat-033 workbook-input-format|FEAT-033]] решение 44): секцию `output` перевод не заполняет, кроме заголовка — имя книги без расширения ([[feat-036 run-from-workbook|FEAT-036]], решение 8); остальное — умолчания конфига.
12. ~~**Выключено — `none`** → `null` в JSON~~ — отменено решением 17.
13. **Сообщения — русские**, подписи и ячейки в них — как в книге (FEAT-033 решение 34).
14. **Пара пористости и плотности при ст. у.** (FEAT-033 решения 49, 54): $\varphi_0 = \varphi_{ref}\,e^{c_r(p_0 - p_{ref})}$; плотности проверяются на > 0 переводом (предел `POSITIVE` строки) и `_validate` ([[DEBT-076]], влит).
15. **Все параметры обязательны** ([[feat-033 workbook-input-format|FEAT-033]] решение 57, 2026-10-17): на MODEL, THERMAL, NUMERICS нет строки ключа — отказ; пустая Value — отказ с адресом для любого поля. Умолчания `io/config.py` перевод не подставляет: в `config.json` — каждое поле книги явно. Книга с `format_version` ≠ 1 — отказ.
16. **SCHEDULE: ячейки чужого режима не читаются** ([[feat-033 workbook-input-format|FEAT-033]] решение 61, 2026-10-17): строка BHP — только BHP target, строка OIL_RATE — Oil-rate target и Minimum BHP; остальные заполненные ячейки молча пропускаются, как режим последней строки (решение 8). Единицы → СИ — `io/workbook_format.UNIT_TO_SI`; поля вне книги — `NOT_FROM_WORKBOOK`, вычисляемые — `DERIVED`; проверка значения строки — `Param.accepts`. Первая строка SCHEDULE — $t = 0$ (раскладка FEAT-033; проверка Excel `A2 = 0`), иное — отказ с адресом. Демо-числа генератора — с 15 цифрами (FEAT-033 решение 63): ячейка книги генератора равна литералу `workbook_template.DEMO_*` бит в бит. Сам перевод не округляет: в ячейках — то, что хранит Excel.
17. **Изменения формата после реализации FEAT-033** (решения 64–68 плана FEAT-033, 2026-10-17): слова `none` в книге нет — `dt_after_control_change` и `newton_cell_tol` всегда числа; постоянные строки (`Param.fixed`: `format_version`, `numerics.jacobian_mode` = grouped, `numerics.linear_solver` = sparse) — иное значение отвергается с адресом ячейки; лист «параметр–значение» — 6 столбцов, «Комментарии» (F) перевод не читает; RELPERM — первая строка (0, k_ro, 0) и последняя (1, 0, k_rg) по `RELPERM_FIRST_ROW`, `RELPERM_LAST_ROW` проверяются переводом (защита листа без пароля).
18. **Разбор FEAT-034** ([[feat-034 xlsx-cell-reader|план]], заметка [[разбор книги xlsx сообщает тип ячейки — отказ по типу решает перевод]]; реализован 2026-10-18): `read_workbook(path)` из `gpn_multiphase_solver/io/xlsx_reader.py` → `Workbook` (`path`, `sheets` — словарь в порядке книги, `recalc_on_open`); `Sheet.cell(row, col)`, `Sheet.cells` (только ячейки со значением или формулой), `Sheet.max_row`; `Cell.kind` (`number` — `float`, `string`, `bool`, `error`, `empty`), `is_date`, `formula`, `formula_without_value`, `ref` (`MODEL!C5`). Что берёт перевод:
    - отказы решения 6 — по `kind`, `is_date`, `formula_without_value`; адрес в сообщении — `Cell.ref`, у отсутствующей ячейки — `Sheet.cell(row, col).ref`;
    - книга с `fullCalcOnLoad` (XlsxWriter, openpyxl) — формулы приходят без значения (FEAT-034 решение 9; Excel при сохранении пометку снимает — проверено): подсказка «откройте книгу в Excel и сохраните **или введите число вместо формулы**» — книгу у заказчика могут сохранить Р7-Офис или МойОфис;
    - строки разбор не срезает — срезает перевод (решение 20);
    - исключения разбора: `WorkbookError` (подкласс `ValueError`) — любой отказ содержимого файла, сообщение выводить как есть; `OSError` — файловая система;
    - тестовые книги XlsxWriter с формулами — снимать пометку `fullCalcOnLoad`, иначе формула придёт без значения; готовые книги Excel — `tests/data/feat034_excel/` (`template_saved.xlsx` — книга генератора версии 1 после Excel, с формулой `=0.2/2` в `geometry.r_well`).

**Приняты при планировании (2026-10-18, ответы на вопросы плана):**

19. **Моменты SCHEDULE — в целых миллисекундах:** $M_k = \mathrm{round}(t_k \cdot 86\,400\,000)$ — целое; $\Delta t_k = (M_{k+1} - M_k)/1000$ с. Уточняет решение 5: при моментах вне сетки 1 мс (например, $k/7$ сут) округление каждой разности, как в примере 18, сдвигает моменты записи на сумму ошибок — до 0.5 мс на интервал (за 700 интервалов по $1/7$ сут — на 0.1 с); округление моментов ошибку не накапливает: $\sum \Delta t_k = M_N/1000$ точно в целых. На книге генератора оба способа дают одни и те же 22 интервала. $M_{k+1} \le M_k$ — отказ с адресом («интервал нулевой или отрицательный»).
20. **Пробелы по краям строк книги срезаются** при сравнении: ключи, единицы, заголовки листов и таблиц, режим (BHP / OIL_RATE), постоянные слова (grouped, sparse); регистр — точно («bhp» — отказ). Как заголовки CSV в `factory._read_numeric_csv`. Пробел, попавший при вставке из буфера, в ячейке не виден. В сообщении строка книги — в кавычках (`repr`), пробел виден.
21. **`convert` проверяет только книгу.** Перевод проверяет своё (листы, заголовки, ключи, единицы, типы и пределы ячеек, постоянные строки, крайние строки RELPERM, SCHEDULE). Проверки конфига (`load_config`, `_validate`) и таблиц целиком (фабрика: ветви PVTO, $p_b$ растёт с $R_s$, недонасыщенный старт, ОФП) — при расчёте: `run` делает их до первого шага. `convert` не импортирует решатель, scipy и прототип — как `template`.
22. **Все ошибки ячеек — одним сообщением**, в порядке листов книги и строк (не больше `MAX_ERRORS` = 30 строк, затем «… и ещё N»). Составные поля и интервалы SCHEDULE считаются, только если их ячейки верны (ошибка опорной ячейки не порождает второй ошибки). Исключение — решение 26.

**Умолчания плана (если не возразите):**

23. **Полностью пустая строка таблицы пропускается** (SCHEDULE, OIL_PVT, GAS_PVT, RELPERM), строки ниже читаются; частично заполненная — ошибка пустой ячейки. Как пустая строка CSV в `_read_numeric_csv`. «Последняя строка» SCHEDULE и крайние строки RELPERM — последняя и первая непустые.
24. **Ячейки вне таблиц не читаются:** столбцы правее последнего заголовка таблицы; столбцы Comment (E) и «Комментарии» (F) листов «параметр–значение». Как лишние листы (решение 10) и ячейки чужого режима (решение 16).
25. **Строки листов «параметр–значение»:** строка без ключа (A пуста) — пропускается, если пусты и B–D; иначе ошибка «строка без ключа». Ключ другого листа — ошибка «эта строка листа NUMERICS»; повтор ключа — ошибка со строкой первого вхождения. Заголовок сверяется в A1–D1 (вставленный столбец сдвинул бы чтение Value и Unit); с ошибкой заголовка строки листа не читаются.
26. **Отказы до остальных проверок — одной ошибкой:** нет листа (книга не того формата) — по ошибке на лист; нет строки `format_version` или версия ≠ 1 — одна ошибка (решение 15: прочие ошибки книги другой версии — шум). В сообщении — состав листов версии 1 и «шаблон пишет команда gpn-solver template».
27. **Имена и интерфейс:** модуль `gpn_multiphase_solver/io/workbook_convert.py`; `convert_workbook(workbook, out_dir) -> Path` (путь `config.json`), `workbook_to_config(book) -> (config, tables)`, `write_files(out_dir, config, tables) -> Path`, `WorkbookContentError(WorkbookError)` с полем `errors`; подкоманда `gpn-solver convert книга.xlsx каталог`, коды 0 / 2. Модуль — внутренний код (однострочные докстринги): в публичный интерфейс (README §4, `tests/test_public_api.py`) — решит FEAT-036 вместе с README для инженера.
28. **Файлы пишутся после всех проверок:** книга с ошибкой не оставляет ни файлов, ни каталога. Каталог создаётся (`mkdir(parents=True)`), если его нет: FEAT-036 пишет в `output/input/` после очистки `output/`. Каталог-файл на месте каталога — отказ, как непустой каталог (`FileExistsError`).
29. **Заголовок — имя книги без расширения** (`Path.stem`; FEAT-036 решение 8), записывается в `output.title` (открытый вопрос 4 черновика FEAT-036 этим закрывается).
30. **README пакета в этой задаче не меняется:** инструкцию инженера (`template`, `convert`, `run книга.xlsx`) пишет FEAT-036 (её решение 9) — строка в план FEAT-036 (шаг 4).
31. **Тексты файлов:** UTF-8, окончания строк «\n»; `config.json` — `json.dumps(indent=2, ensure_ascii=False)` (кириллица в заголовке читаема); числа JSON и CSV — через `repr` (обратное чтение точное). Поля секций — в порядке строк книги; `pvt.model`, `relperm.model` — первыми.
32. **Вид сообщения:** `<лист>!<ячейка> (<подпись строки или заголовок столбца>): <что в ячейке> — <что нужно>`; первая строка — `<путь книги>: книга не переведена, ошибок — N:`. Тексты для дат и формул — с причиной и действием (§7).
33. **Номер строки Excel в физических ошибках по `time.history[k]`** (открытый вопрос 5 черновика) — не дописывается: строка SCHEDULE $k$ (Excel, без пустых строк) ↔ `history[k − 2]`, это записано в заметке и проверено тестом `test_history_from_template`; сообщения `_validate` не меняются (решение 4).
34. **`grid.type`** не пишется (умолчание `log_radial` — единственная сетка, `NOT_FROM_WORKBOOK`); `pvt.co_undersaturated`, `mu_o_undersaturated`, параметры Кори — умолчания (у таблиц фабрика их и требует такими: DEBT-078, FEAT-027).
35. **$\varphi_0 \le 1$ проверяет перевод** (аудит 1, 2026-10-18; уточняет решение 21). Ключ строки книги — путь поля JSON, поэтому отказ `_validate` при расчёте называет строку, которую инженер находит в книге, — у всех полей, кроме составных. Из составных отказ возможен только у пористости: `_validate` отвергает `rock.porosity` > 1 («porosity должна быть в (0, 1]»), а строки `rock.porosity` в книге нет — есть $\varphi_{ref}$, $p_{ref}$, $c_r$, $p_0$. $(\rho c_p)_s = \rho_{ma}c_{ma} > 0$ при обоих сомножителях > 0; пределы интервалов SCHEDULE равны пределам `_validate_interval` (тест FEAT-033 `test_schedule_limits_match_validate_interval`). Ошибка — у ячейки $\varphi_{ref}$ с вычисленным $\varphi_0$ и перечнем источников; $\varphi_0 > 0$ всегда ($\varphi_{ref} > 0$). Пример: $c_r$ = 0.05 1/бар (опечатка вместо 5e-5), $p_0 - p_{ref}$ = 50 бар → $\varphi_0 = 0.2\,e^{2.5} \approx 2.44$.

## 1. Сводка

- **Подтип:** инфраструктура (ввод). Уровень модели — нет.
- **Суть:** `read_workbook` (FEAT-034) → `workbook_to_config`: листы «параметр–значение» по таблице полей (ключ, единица, тип, предел, целое, постоянные), составные поля `DERIVED`, таблицы PVT и ОФП в СИ, SCHEDULE → `time.history` (моменты в целых мс, режим строки, только его ячейки) → `write_files`: `config.json` и три CSV в новом или пустом каталоге. Подкоманда `gpn-solver convert`.
- **Файлы:** новый `numerical_solver/gpn_multiphase_solver/io/workbook_convert.py` (460 строк), `numerical_solver/gpn_multiphase_solver/cli.py` (подкоманда `convert`, +44 −1 строка), новый `numerical_solver/tests/test_workbook_convert.py` (742 строки), `numerical_solver/tests/test_cli.py` (+71 строка блока и пункт docstring), заметка `vault/knowledge/decisions/` (новая), строки в планах FEAT-036 и в заметке о формате. Существующий код решателя, загрузчик конфига, фабрика, прототип, пример 18 — не меняются.
- **Тесты:** 2288 → 2395 (+107): 100 в `test_workbook_convert.py`, 7 в `test_cli.py`; быстрые (100 тестов перевода и 7 командной строки — около 4 с вместе с запуском pytest), метки `slow` нет.
- **Шагов:** 5.

## 2. Контекст

### 2.1. Как конфиг и таблицы проверяются сейчас (на `55868a6`)

- `load_config` (`io/config.py`): `json.load` → словарь; на словаре — только структура: обязательные секции, удалённые ключи ([[DEBT-008]]), формы `history` (`_expand_history`, [[FEAT-018]]). Словарь → dataclass-секции: неизвестный ключ — ошибка распаковки. Типы, конечность, пределы — `_validate` на `SimulationConfig` ([[DEBT-051]], [[DEBT-056]]); интервалы истории — `_validate_interval`: при `control='pressure'` поля `q_oil`, `min_bhp` — отказ, при `'rate'` — `p_wf` (поэтому решение 16 обязательно).
- Таблицы: в конфиге — имена файлов (`pvt.oil_pvt_file`, `pvt.gas_pvt_file`, `relperm.file`) относительно папки конфига; `load_config` их не открывает. Читает и проверяет фабрика при сборке решателя: `create_pvt` → `_read_numeric_csv` (заголовок, числа, пределы — [[DEBT-044]]; пустая строка пропускается) → `_check_pvto_branches` ([[DEBT-038]]), `_check_gas_pvt_table`, `_check_rs0_in_table`; `create_relperm` → `_check_relperm_table` ($k_{rg}[0] = 0$ — DEBT-079, $k_{ro}[-1] = 0$ — DEBT-073); затем согласованность PVT ([[BUG-019]]) и недонасыщенный старт ([[BUG-017]]).
- Перевод в файлы проходит оба этапа без изменений — ни одна проверка не дублируется и не обходится. Рефакторинг загрузчика (`config_from_dict`, таблицы в памяти) **не нужен**.

### 2.2. Столбцы CSV, которые ждёт фабрика

| Файл | Столбцы (СИ) | Из книги |
|---|---|---|
| `oil_pvt.csv` | `Rs_sm3_sm3, pressure_Pa, Bo, mu_o_Pa_s` | OIL_PVT: бар × 1e5, сП ÷ 1e3 |
| `gas_pvt.csv` | `pressure_Pa, Bg, mu_g_Pa_s` | GAS_PVT: бар × 1e5, сП ÷ 1e3 |
| `relperm.csv` | `Sg, kro, krg` | RELPERM: без перевода |

Порядок столбцов и пределы таблицы полей равны фабрике — тест FEAT-033 `test_table_columns_match_factory`; столбец CSV — `Column.target`. В конфиг: `pvt.model = "table"`, `relperm.model = "table"`, имена файлов.

### 2.3. Единицы и составные поля

`io/workbook_format.UNIT_TO_SI` (множители — `units.py`): `bar(a)` × `BAR_TO_PA` (1e5); `mD` × `MD_TO_M2` (9.869233e-16); `1/bar` ÷ `BAR_TO_PA`; `cP` ÷ `PA_S_TO_CP` (1e3); `K/MPa` ÷ 1e6; `kJ/kg` × 1e3; `h` × `HOUR_TO_S` (3600); `day` × `DAY_TO_S`; `Sm3/day` ÷ `DAY_TO_S`; прочие (`-`, `m`, `kg/m3`, `K`, `J/(kg*K)`, `W/(m*K)`, `Sm3/Sm3`, `rm3/Sm3`) — без перевода. «На единицу» — деление на точный множитель: одно округление вместо двух (`v * 1e-5` округляется дважды: 1e-5 в double неточно).

Составные поля (`DERIVED`, FEAT-033 решения 33, 49):

$$\varphi_0 = \varphi_{ref}\,e^{c_r(p_0 - p_{ref})}, \qquad (\rho c_p)_s = \rho_{ma}\,c_{ma}.$$

$c_r$ — в 1/Па, давления — в Па, после перевода единиц. Порода решателя — `CompressibleRock` прототипа (`radial_blackoil/rock.py`): $\varphi(p) = \varphi_{ref}\,e^{c_r(p - p_{ref})}$ с опорным давлением $p_0$ (фабрика передаёт `p_ref_bar = p0`), поэтому перенос опорной точки точный: $\varphi_0\,e^{c_r(p - p_0)} \equiv \varphi_{ref}\,e^{c_r(p - p_{ref})}$. Пара $(\varphi_{ref}, p_{ref})$ — как ключевое слово ROCK в Eclipse/OPM, где поровый объём — разложение экспоненты до второго порядка: $V(P_i) = V(P_r)\,[1 + c_f(P_i - P_r) + (c_f(P_i - P_r))^2/2]$ (OPM Flow Reference Manual 2025-10, ключевое слово ROCK, табл. 8.138, формула (8.97); `Refs/incoming/OPM_Flow_Reference_Manual_2025-10_Rev-0_compressed.pdf` — сверено аудитом 1). При $c_r$ = 4.5e-5 1/бар и $|p_0 - p_{ref}| \le 100$ бар расхождение с экспонентой $X^3/6 \le 1.5\cdot10^{-8}$, $X = c_r(p_0 - p_{ref})$, — пренебрежимо: значения $(\varphi_{ref}, p_{ref})$ модели OPM переносятся в книгу как есть. $(\rho c_p)_s$ — определение под `eq:main_rhocpeff` (`problem_statement.tex`); демо: 2650 · 820 = 2 173 000 Дж/(м³·К).

**Последний разряд** (замер 2026-10-18, проба `plan_apply.py` и пробный перевод): `rock.compressibility` 4.5e-5 1/бар → 4.5000000000000005e-10 1/Па (тот же результат, что `× 1e-5`); `thermal.mu_JT_oil` −0.4 К/МПа → −4.0000000000000003e-07 К/Па; $h_0$ 3.05555555555556e-05 ч → **0.11000000000000017 с** (черновик плана писал 0.10999999999999999 или 0.11000000000000001 — неверно). На расчёт не влияет: $h_0$ округляется вниз до $\Delta t/2^m$ (`TimeSchedule.first_substep_depth`). Прототип получает давления и вязкости таблиц в барах и сП обратным переводом фабрики (`p / BAR_TO_PA`, `mu / CP_TO_PA_S`): на демо-таблицах 4 из 47 давлений и 6 из 47 вязкостей отличаются от ячейки книги на 1 ULP — свойство канонического JSON в СИ, а не перевода; тесты сравнивают файлы с `UNIT_TO_SI(ячейка)`.

### 2.4. Точность

Числа в JSON и CSV — через `repr` (у Python точное обратное чтение; `json.dumps` пишет `float` тем же `repr`). Целые поля (`grid.N`, `max_retries`, `newton_max_iter`, `max_active_set_iter`) — `int`: Excel хранит 100 как 100.0, а `_validate` у трёх лимитов Ньютона требует `int`; у `grid.N` проверки целого в `_validate` нет — дробное доходит до `LogRadialGrid` и отвергается по-английски, `true` проходит молча (сетка из одной ячейки) — [[DEBT-081]], зарегистрирована при планировании. Значения в инженерных единицах после перевода в СИ не обязаны быть «круглыми» (1 мД = 9.869233e-16 м²) — побитовое совпадение с конфигами примеров, заданными в СИ, не гарантируется и не требуется (примеры независимы).

### 2.5. Книги и пробы (2026-10-18, `55868a6`)

- **Книга генератора** `configs/INPUT_TEMPLATE_v1.xlsx`: `recalc_on_open = True`, формул в Value нет — переводится как есть. Листов 8; строк данных: MODEL 14, THERMAL 10, NUMERICS 11, SCHEDULE 23, OIL_PVT 34, GAS_PVT 13, RELPERM 16. Расположение: строка 1 — заголовок; листы «параметр–значение» — A Key, B Parameter, C Value, D Unit, E Comment, F «Комментарии»; таблицы — столбцы `Column.header` с A.
- **Книга после Excel** `tests/data/feat034_excel/template_saved.xlsx`: `recalc_on_open = False`, `geometry.r_well` — формула `0.2/2` со значением 0.1 — случай «формула с сохранённым значением допустима».
- **SCHEDULE генератора** — 23 момента → 22 интервала: 60, 86340, 86400, 172800, 86400, 6 × 10, 86340, 691200, 86400, 6 × 10, 86340, 1209600 с; сумма — 2 592 000 с точно. Моменты в книге — с 15 значащими цифрами (5.00011574074074 сут).
- **Пробный перевод** (код плана на основном дереве, каталог в папке проб, удалён): обе книги → 4 файла; `load_config` и `SimulatorFactory.from_config` принимают; `rock.porosity` = 0.2 ($p_{ref} = p_0$), `rho_cp_solid` = 2173000.0, `output.title` = имя книги.
- **Импорты:** `io.config`, `io.xlsx_reader`, `io.workbook_format` тянут из пакета только `io`, `log`, `units` — ни scipy, ни прототипа, ни matplotlib (проверено `sys.modules`).
- **Сценарий книги генератора `convert` → `run`** на копии дерева — §12.

## 3. Правило → код → тест

| Правило | Решение | Код (`workbook_convert.py`) | Тест (`test_workbook_convert.py`, если не указано) |
|---|---|---|---|
| Листы MODEL…RELPERM обязательны, COMMENTS и лишние — нет | 10, 26 | `workbook_to_config`: `missing` | `test_missing_sheet` (7), `test_comments_and_extra_sheets_not_read` |
| `format_version` = 1 — до остальных проверок | 15, 26 | `_check_version` | `test_format_version` (3), `test_format_version_row_missing` |
| Заголовки листов (A1–D1) и таблиц, пробелы срезаются | 20, 25 | `_header_ok` | `test_param_header_mismatch`, `test_table_cell_errors[…B1]`, `test_table_header_with_spaces_accepted` |
| Ключ: неизвестный, другого листа, повтор, без ключа | 10, 25 | `_param_sheet`, первый цикл | `test_unknown_and_foreign_keys`, `test_duplicate_key`, `test_row_without_key` |
| Все строки обязательны | 15 | `_param_sheet`: «нет строки» | `test_missing_key_row`, `test_unknown_and_foreign_keys` |
| Единица — точно (после среза пробелов) | 3, 20 | `_param_sheet`: `_text(unit) != p.unit` | `test_unit_mismatch`, `test_key_and_unit_with_spaces_accepted` |
| Тип ячейки: пусто, текст, логическое, ошибка, дата, формула без значения (в том числе общая) | 6, 18 | `_number` | `test_value_kinds` (9), `test_table_cell_errors`, `test_formula_in_recalc_book_refused`, `test_date_cell_through_reader` |
| Формула с сохранённым значением допустима | FEAT-033 26 | `_number`: `NUMBER` с `formula` | `test_formula_with_saved_value_accepted`, `test_excel_saved_template_converts` |
| Пределы строки и столбца — `Limit.accepts`; $r_e > r_w$ — если $r_w$ верен | 22, FEAT-033 50 | `_param_sheet`, второй цикл; `_table_number` | `test_limits` (7), `test_above_skipped_when_reference_invalid`, `test_schedule_errors` |
| Целые поля — `int` | 6 | `out[p.key] = int(v)` | `test_integer_fields_written_as_int`, `test_integer_from_float`, `test_param_cells_to_json_bitwise` |
| Постоянные строки | 17 | `_param_sheet`: `p.demo` | `test_fixed_values` (4) |
| Составные поля | 14 | `_porosity`, `_config` | `test_derived_porosity_and_rho_cp`, `test_every_book_field_explicit` |
| $\varphi_0 \le 1$ — ошибка у ячейки $\varphi_{ref}$ | 35 | `_check_porosity` (после листа MODEL) | `test_porosity_above_one_refused` |
| Каждое поле книги явно, умолчаний нет | 15, 34 | `_config` | `test_every_book_field_explicit`, `test_param_cells_to_json_bitwise` |
| Таблицы → CSV в СИ побитово | 2, 16 | `_table`, `UNIT_TO_SI`, `_write_csv` | `test_table_cells_to_csv_bitwise` |
| Пустая строка таблицы пропускается; столбцы вне таблицы не читаются | 23, 24 | `_data_rows` | `test_empty_row_in_table_skipped` (3), `test_empty_row_in_schedule_skipped`, `test_cells_right_of_tables_not_read` |
| Крайние строки RELPERM — у листа без ошибок | 17 | `_relperm_ends` | `test_relperm_end_rows` (4), `test_relperm_without_rows`, `test_relperm_ends_not_checked_after_cell_error` |
| SCHEDULE: $t_0 = 0$, возрастание в мс, ≥ 2 строк | 5, 8, 19 | `_schedule` | `test_schedule_errors` (12), `test_moments_in_whole_ms_do_not_drift` |
| SCHEDULE: режим и только его ячейки; последняя строка — только момент | 8, 16 | `_schedule` | `test_rate_rows_shut_in_and_foreign_cells`, `test_last_row_mode_not_read`, `test_mode_with_spaces_accepted` |
| Строка $k$ ↔ `history[k − 2]` | 33 | `_schedule` | `test_history_from_template` |
| Заголовок — имя книги, `output` — только он | 11, 29 | `_config` | `test_title_and_output_section` |
| Все ошибки сразу, порядок листов, не больше 30 | 22, 32 | `WorkbookContentError` | `test_all_errors_at_once_in_sheet_order`, `test_error_list_capped`, `test_content_error_is_workbook_error` |
| Новый или пустой каталог; файлы — после проверок | 10, 28 | `convert_workbook` | `test_convert_into_empty_existing_dir`, `test_convert_refuses_non_empty_dir_or_file` (2), `test_book_error_leaves_no_files` |
| Ошибки разбора и файловой системы проходят как есть | 18 | `convert_workbook` | `test_reader_errors_pass_through` |
| Тексты файлов: UTF-8, «\n», кириллица | 31 | `write_files`, `_write_csv` | `test_files_text_format`, `test_title_and_output_section` |
| Книга генератора и после Excel → `load_config` и сборка решателя | 9 | — | `test_template_converts_and_builds`, `test_excel_saved_template_converts` |
| Книга XlsxWriter из таблицы полей = книга генератора | 9 | — | `test_xlsxwriter_book_equals_template` |
| Подкоманда `convert`: коды, сообщения, без решателя | 21, 27 | `cli._convert` | `test_cli.py`: `test_convert_via_module`, `test_convert_help`, `test_convert_book_error_returns_2`, `test_convert_not_xlsx_returns_2`, `test_convert_missing_book_returns_2`, `test_convert_non_empty_dir_returns_2`, `test_convert_does_not_import_solver` |

## 4. Обратная совместимость

- Существующий код не меняется, кроме `cli.py`: новая подкоманда; `run` и `template` — побайтно те же ветви (`main` получает одну ветку `convert` до импорта конвейера).
- `tests/test_cli.py` — только дописывается блок и пункт в докстринге модуля; существующие тесты не меняются.
- Конфиги, примеры, истории — без изменений; фабрика, загрузчик, прототип не тронуты; пример 18 и VAL-005 не меняются (решение 7).
- Зависимости пакета не меняются: перевод — стандартная библиотека и numpy (`test_declared_dependencies_cover_imports`).
- Публичный интерфейс (README §4, `test_public_api.py`) не меняется (решение 27).

## 5. Варианты и выбор

| Вариант | Суть | Плюсы | Минусы | Итог |
|---|---|---|---|---|
| А. Перевод в файлы → `load_config` | книга → `config.json` + CSV, дальше обычный путь | все проверки конфига и фабрики — без дублирования; вход расчёта сохраняется (FEAT-036) | файлы на диске | **принят** (решения 1, 2) |
| Б. Словарь в память → `config_from_dict` | загрузчик и фабрика принимают таблицы из памяти | без файлов | рефакторинг `load_config` и фабрики (имена CSV, `config_dir`), вход расчёта не сохраняется | отклонён |
| Ошибки: первая / все сразу | отказ на первой — как `load_config` | проще код | несколько запусков на книгу | все сразу (решение 22) |
| Интервалы: разности / моменты | `round(Δt·86400, 3)` / целые мс | разности — как пример 18 | разности накапливают ошибку моментов | моменты (решение 19) |
| Проверки в `convert` | только книга / + `load_config` / + фабрика | только книга — без решателя, проверки один раз в `run` | физическая ошибка — при расчёте | только книга (решение 21) |

## 6. Подводные камни

- ✅ **Размерности:** все переводы — `UNIT_TO_SI` таблицы полей (FEAT-033 проверил единицы и множители: `test_unit_to_si`, `test_per_unit_conversion_divides`); последний разряд — §2.3, на расчёт не влияет.
- ✅ **Целые поля:** пишутся `int` (тест на текст JSON); без этого `grid.N` = 100.0 дал бы английский отказ `LogRadialGrid`, лимиты Ньютона — отказ `_validate`. Пробел `_validate` для `grid.N` — [[DEBT-081]].
- ✅ **Ячейки чужого режима:** не читаются (решение 16) — иначе `_validate_interval` отверг бы интервал; тест с заполненными чужими ячейками проходит `load_config`.
- ✅ **Моменты:** $t \cdot 86\,400\,000$ точно представимо до $2^{53}$ мс (≈ 285 000 лет); `round(float)` — `int`; деление целых на 1000 — ближайший double.
- ✅ **Формулы книги генератора:** у неё `fullCalcOnLoad`, но формул нет; инженер, набравший формулу в Excel, сохраняет книгу без пометки (ворота FEAT-034 пройдены). Р7-Офис и МойОфис не проверены — подсказка «или введите число вместо формулы».
- ✅ **Состояние при ошибке:** запись — после всех проверок; книга с ошибкой каталога не создаёт.
- ⚠️ **Ошибка записи посреди файлов** (диск, права): часть файлов остаётся, каталог непуст — повторный `convert` в него откажет. Допустимо: `OSError` → код 2 с путём; FEAT-036 очищает `output/` перед переводом сам.
- ✅ **Импорты:** `workbook_convert` → `workbook_format`, `config`, `xlsx_reader` — ни один не импортирует перевод (циклов нет); решатель и прототип не импортируются — тест `test_convert_does_not_import_solver`.
- ✅ **Производительность:** книга ~150 ячеек, SCHEDULE до тысяч строк — миллисекунды; тест на 700 интервалов — доли секунды.
- ✅ **Связь с задачами:** FEAT-036 вызывает `convert_workbook(книга, output/input)`, ловит `WorkbookError` и `OSError` (контракт — шаг 4); FEAT-031 — README у FEAT-036 (решение 30); VAL-005 и пример 18 не меняются; DEBT-076 влит — плотности > 0 и в `_validate`; [[DEBT-081]] — не блокирует.
- ✅ **Прототип:** не меняется; тесты и регрессия прототипа не нужны.
- ✅ **Пробелы и регистр:** срез пробелов только по краям строк (решение 20); «bhp» — отказ (тест).
- ✅ **Кириллица в имени книги:** заголовок пишется читаемо (`ensure_ascii=False`), тест `test_title_and_output_section`.
- ⚠️ **Книга, открытая в Excel:** чтение открытой книги другим процессом обычно разрешено, но в проекте не проверялось (аудит 1); при отказе — `PermissionError` → код 2 «Ошибка: <файл>: <причина>». Файл `~$…` рядом — не книга, не читается (FEAT-036 решение 6).
- ✅ **Составные поля и отказы при расчёте** (аудит 1): отказ `_validate` по переведённому конфигу называет ключ книги (ключ строки = путь JSON); единственное исключение — $\varphi_0 > 1$, его ловит перевод (решение 35).
- ⚠️ **`cli.py` меняется целиком** (шаг 3): если до реализации файл изменит другая задача (FEAT-036, [[FEAT-037]] — версия в командной строке), замена файлом плана её правку сотрёт. В шаге 3 — проверка `git diff 55868a6 -- …/cli.py` и запасной путь (вставки по одной).
- ⚠️ **Журнал изменений** ([[FEAT-037]], зарегистрирована другой сессией 2026-10-18, `numerical_solver/CHANGELOG.md`): если к реализации журнал уже есть — строка о `gpn-solver convert` в разделе «Не выпущено» (шаг 4); если нет — ничего.
- ✅ **Сторож меток** (`test_eq_references.py`): единственная ссылка на уравнение — «определение под `eq:main_rhocpeff`» в комментарии `_config`; номеров уравнений и строк `.tex` нет.

## 7. API (итог)

`numerical_solver/gpn_multiphase_solver/io/workbook_convert.py`:

```python
CONFIG_NAME = "config.json"
CSV_NAMES = {"OIL_PVT": "oil_pvt.csv", "GAS_PVT": "gas_pvt.csv", "RELPERM": "relperm.csv"}
MAX_ERRORS = 30                  # строк ошибок в сообщении (решение 22)
MS_PER_DAY = 86_400_000          # моменты SCHEDULE — целые мс (решение 19)
CONFIG_FIELDS: frozenset[str]    # «секция.поле» всех dataclass-секций io/config.py

class WorkbookContentError(WorkbookError):   # WorkbookError → ValueError
    errors: list[str]            # по строке на ошибку: «MODEL!C5 (подпись): что — что нужно»

def convert_workbook(workbook, out_dir) -> Path      # книга → файлы; путь config.json
def workbook_to_config(book: Workbook) -> tuple[dict, dict]
    # (конфиг — словарь JSON в СИ, {имя CSV: (заголовок, [строки в СИ])})
def write_files(out_dir: Path, config: dict, tables: dict) -> Path
```

Исключения `convert_workbook`: `FileExistsError` — каталог непуст или это файл (до чтения книги); `FileNotFoundError` и прочие `OSError` — файловая система; `WorkbookError` — файл не книга `.xlsx` (разбор FEAT-034); `WorkbookContentError` — значения книги. FEAT-036 ловит `WorkbookError` (оба последних) и `OSError`.

Тексты причин (`_number`): пусто — «пусто — нужно число: все значения книги обязательны»; текст — «текст '1,5' — нужно число; десятичный разделитель — точка, число вводится без кавычек и апострофа»; дата — «46143.0 с форматом даты или времени — Excel мог принять ввод за дату; задайте ячейке формат «Общий» и введите число заново»; логическое — «логическое значение TRUE — нужно число»; ошибка — «ошибка Excel #DIV/0! — нужно число»; формула без значения — «формула без сохранённого значения — откройте книгу в Excel и сохраните её или введите число вместо формулы», при `recalc_on_open` — с объяснением пометки «пересчитать при открытии». Пределы словами (`_limit_text`): «число > 0», «число ≥ 0», «число в (0, 1]», «число от 0 до 1», «целое число от 0 до 20», «целое число ≥ 1», «число больше, чем Wellbore radius (rw)», «конечное число».

Пример сообщения (книга с тремя ошибками):

```
D:\cases\well7.xlsx: книга не переведена, ошибок — 3:
  MODEL!C6 (Absolute permeability (k)): -1.0 — нужно число > 0
  NUMERICS!C2 (Grid cells (N)): 100.5 — нужно целое число ≥ 1
  SCHEDULE!B5 (Control mode): 'RATE' — нужен BHP или OIL_RATE
```

Командная строка (`cli.py`): `gpn-solver convert книга.xlsx каталог` → `_convert(workbook, output)`: 0 — «Конфиг записан: <путь>» и строка «Таблицы gas_pvt.csv, oil_pvt.csv, relperm.csv — там же. Конфиг и таблицы целиком проверяются при расчёте: gpn-solver run <путь>»; 2 — «Ошибка книги: …» (`WorkbookError`), «Ошибка: … не пустой каталог …» (`FileExistsError`), «Ошибка: книга … не найдена» (`FileNotFoundError`), «Ошибка: <файл>: <причина>» (`OSError`). Импорт перевода — внутри `_convert`.

## 8. Шаги

### Шаг 1: модуль перевода

**Цель:** `workbook_to_config`, `convert_workbook`, `write_files` в пакете.
**Файлы:** `numerical_solver/gpn_multiphase_solver/io/workbook_convert.py` (новый).

**Контекст:** книга читается разбором FEAT-034; формат — таблица полей `io/workbook_format.py` (`PARAM_SHEETS`, `TABLE_SHEETS`, `SCHEDULE`, `CONTROL_MODES`, `UNIT_TO_SI`, `DERIVED`, `RELPERM_FIRST_ROW`, `RELPERM_LAST_ROW`, `Param.accepts`, `Limit.accepts`); результат — словарь, который `load_config` читает как обычный JSON.

**Что сделать:** скопировать `vault/issues/feat-035/probes/plan_code/workbook_convert.py` в `numerical_solver/gpn_multiphase_solver/io/workbook_convert.py` без изменений. Устройство (для проверки при переносе):

1. Постоянные §7; `_SECTIONS` — dataclass-секции `io/config.py` → `CONFIG_FIELDS` (ключ строки книги — поле конфига, если он там есть; иначе ключ только книги — `format_version`, $\varphi_{ref}$, $p_{ref}$, $\rho_{ma}$, $c_{ma}$); `_SHEETS` = `PARAM_SHEETS` + `TABLE_SHEETS`.
2. `convert_workbook`: каталог непуст или файл → `FileExistsError`; `read_workbook` → `workbook_to_config` → `write_files`.
3. `workbook_to_config`: нет листов → `WorkbookContentError` (решение 26); `_check_version`; листы «параметр–значение» по порядку → значения в СИ и адреса строк (`refs`), после MODEL — `_check_porosity` (решение 35); `_schedule`; таблицы OIL_PVT, GAS_PVT, RELPERM (`_relperm_ends` — только у листа без ошибок) → строки в СИ; ошибки → `WorkbookContentError`; иначе `_config`.
4. `_param_sheet`: заголовок A1–D1; первый цикл — строки → ключи (неизвестный, другого листа, повтор, строка без ключа); второй — по строкам таблицы полей: нет строки, единица, постоянное слово, `_number`; третий — постоянные числа, пределы (`above_key` — только если опорная строка верна), `int` / `UNIT_TO_SI`.
5. `_table`, `_data_rows` (строки с ячейками в столбцах таблицы), `_table_number`.
6. `_schedule`: ≥ 2 строк; момент — `_table_number` → `round(t·MS_PER_DAY)`; первая строка — $t = 0$ точно; $M$ строго растёт; последняя строка — только момент; режим — `_text` ∈ `CONTROL_MODES`, ячейки — только `used`; при ошибках — `[]`; иначе `{"dt": (M[k+1] − M[k])/1000, "control": …, поля режима}`.
7. `_number` (у ячейки общей формулы текст пуст — «общая формула»), `_header_ok`, `_text` (срез пробелов), `_filled`, `_show` (строка — `repr`), `_limit_text`.
8. `_porosity` ($\varphi_0$ по `wf.DERIVED["rock.porosity"]`; `None`, если у источника ошибка), `_check_porosity` ($\varphi_0 > 1$ — ошибка у ячейки $\varphi_{ref}$).
9. `_config`: секции в порядке `_SECTIONS`; `model = "table"` первыми; поля книги; $\varphi_0$ — `_porosity`, $(\rho c_p)_s$; имена CSV; `time.history`; `output.title` — имя книги без расширения.
10. `write_files`, `_write_csv`: UTF-8, «\n» (`write_text(..., newline="\n")`), `repr`.

Docstring каждой функции — одна строка; ссылка на задачу — в docstring модуля и публичных по смыслу функций (`convert_workbook`, `workbook_to_config`); метка уравнения — только `eq:main_rhocpeff` в комментарии.

**Проверка после шага:**
- Из `<W>\numerical_solver`: `<PY> -c "import sys; from gpn_multiphase_solver.io.xlsx_reader import read_workbook; import gpn_multiphase_solver.io.workbook_convert as m; c, t = m.workbook_to_config(read_workbook('configs/INPUT_TEMPLATE_v1.xlsx')); print(m.__file__); print(len(c['time']['history']), sorted(t), 'scipy' in sys.modules)"` → путь модуля внутри `<W>`; `22 ['gas_pvt.csv', 'oil_pvt.csv', 'relperm.csv'] False`.
- Регресс: быстрый — 2011 passed, 1 skipped (новых тестов ещё нет; модуль тестам сторожей не мешает).

**Подводные камни:** §6 — целые поля, ячейки чужого режима; `write_text` без `newline="\n"` на Windows пишет «\r\n» (найдено пробой плана, в коде плана учтено).
**Зависимости:** блокирует шаги 2–4.
**Оценка:** 460 строк (перенос), ~5 минут.

### Шаг 2: тесты перевода

**Цель:** правила §3 — каждое тестом; книги — в памяти (правка `Cell` книги генератора) и сквозь разбор (XlsxWriter, фикстура Excel).
**Файлы:** `numerical_solver/tests/test_workbook_convert.py` (новый).

**Что сделать:** скопировать `vault/issues/feat-035/probes/plan_code/test_workbook_convert.py` без изменений. Средства: `book` (книга генератора, фикстура модуля), `_value_cell` / `_edit` / `_set` / `_row` (правка ячеек в памяти; `("date", v)`, `("error", код)`, `("formula", текст)` — особые ячейки), `_shift_down` (пустая строка), `_with_schedule` (свой SCHEDULE), `_errors` / `_one_error`, `_write_book` (книга XlsxWriter из таблицы полей и демо-значений `workbook_template.DEMO_TABLES`), `_excel_saved` (снять `fullCalcOnLoad`, как в `test_xlsx_reader.py`). Состав — §9.

**Проверка после шага:**
- Тест (из `<W>\numerical_solver`): `<PY> -m pytest tests/test_workbook_convert.py -q` → **100 passed**.
- Сторож меток: `<PY> -m pytest tests/test_eq_references.py -q` — зелёный.
- `<PY> -m pytest tests/ --collect-only -q` → **2288 + 100 = 2388**.
- Регресс: быстрый — 2111 passed, 1 skipped.

**Подводные камни:** XlsxWriter другой версии может писать формулу иначе — `_excel_saved` откажет «найдено 0 раз» (тогда сверить с `vault/issues/feat-034/probes/xlsxwriter_xml.out.txt` и поправить якорь теста, не модуль).
**Зависимости:** требует шаг 1.
**Оценка:** 742 строки (перенос), ~5 минут.

### Шаг 3: подкоманда `convert`

**Цель:** `gpn-solver convert книга.xlsx каталог`, коды 0 / 2, без решателя и прототипа.
**Файлы:** `numerical_solver/gpn_multiphase_solver/cli.py`, `numerical_solver/tests/test_cli.py`.

**Что сделать:**
1. `cli.py`. **Сначала** (из `<W>`): `git diff 55868a6 -- numerical_solver/gpn_multiphase_solver/cli.py` — пусто → заменить файлом `vault/issues/feat-035/probes/plan_code/cli.py`; не пусто (файл менялся после базы плана — FEAT-036, [[FEAT-037]]) → **не заменять**, а внести вставки по одной из того же файла плана. Отличия файла плана от `55868a6` (после замены `git diff` должен показать только их, +44 −1): абзац о `convert` в docstring модуля; docstring `_parser` — «подкоманды run, template, convert и их параметры»; подпарсер `convert` (аргументы `workbook`, `output`; справка, коды возврата) в `_parser` после подпарсера `template`; новая функция `_convert` после `_template`; в `main` — ветка `if args.command == "convert": return _convert(args.workbook.resolve(), args.output.resolve())` сразу после ветки `template`.
2. `tests/test_cli.py` — дописать в конец файла содержимое `vault/issues/feat-035/probes/plan_code/test_cli_convert.py` (7 тестов; `SOLVER`, `_run`, `cli` — из самого `test_cli.py`); в docstring модуля после пункта о шаблоне — пункт «перевод книги (convert, FEAT-035): книга генератора — код 0, 4 файла; ошибка книги, не книга .xlsx, нет файла, непустой каталог — код 2; решатель и прототип не импортируются».

**Проверка после шага:**
- `<PY> -m pytest tests/test_cli.py -q -k "convert or template"` — зелёный (7 новых + 6 шаблона).
- `<PY> -m gpn_multiphase_solver convert --help` — справка с кодами возврата.
- `<PY> -m pytest tests/ --collect-only -q` → **2395**.
- Регресс: быстрый — **2118 passed, 1 skipped, 276 deselected** (проба плана на копии `HEAD` без vault: 2116 passed, 3 skipped — два пропуска сторожа заметок vault).

**Зависимости:** требует шаг 1.
**Оценка:** +44 −1 строка кода, +71 строка тестов, ~10 минут.

### Шаг 4: документы

**Цель:** заметка о переводе, контракт для FEAT-036, ссылки.
**Файлы:**
- `vault/knowledge/decisions/перевод книги в конфиг проверяет только книгу — моменты SCHEDULE в целых мс.md` (новая): назначение и место в цепочке; API (§7) и исключения; правила — решения 15–17, 19–26 (таблица «что — как — почему», как в заметке FEAT-034); соответствие строк SCHEDULE и `history[k − 2]`; что проверяется при расчёте, а не переводом (решение 21); последний разряд (§2.3); [[DEBT-081]]. Ссылки: [[книга ввода Excel версии 1 — все параметры явно, единицы фиксированы]], [[разбор книги xlsx сообщает тип ячейки — отказ по типу решает перевод]], [[feat-035 workbook-to-config]], [[P8-формат-ввода-json]]. Формул — только $\varphi_0$ и $(\rho c_p)_s$ (метка `eq:main_rhocpeff` — сторож меток проверяет заметки `vault/knowledge/`).
- `vault/knowledge/decisions/книга ввода Excel версии 1 — все параметры явно, единицы фиксированы.md`: в начале (абзац «Инженер задаёт расчёт…») — ссылка на новую заметку рядом с [[FEAT-035]]; в «Правила», пункт SCHEDULE — «моменты переводятся в целые мс (FEAT-035, решение 19)».
- `vault/00-home/index.md`: строка новой заметки рядом с заметками FEAT-033/034; строка плана FEAT-035 в списке «Ввод параметров книгой Excel» — «влит»/итог пишет `/implement`.
- `numerical_solver/CHANGELOG.md` — **только если он уже есть** ([[FEAT-037]] влита раньше): в раздел «Не выпущено» — строка «Перевод книги ввода Excel в JSON-конфиг и CSV таблиц: `gpn-solver convert книга.xlsx каталог`». Нет файла — пропустить.
- `vault/plans/feat-036 run-from-workbook.md`, раздел 0: к решению 9 — контракт FEAT-035 (`convert_workbook(книга, output/input) -> Path`; исключения §7: `WorkbookError` — и разбор, и перевод (`WorkbookContentError`), `FileExistsError`, `OSError`; перевод пишет `output.title` = имя книги без расширения — открытый вопрос 4 закрыт); к решению 9 «инструкция инженера в README» — описать в README все три команды (`template`, `convert`, `run книга.xlsx`), FEAT-035 README не меняет (решение 30).

**Проверка после шага:** `<PY> -m pytest tests/test_eq_references.py -q` — зелёный; `--collect-only -q` — число как после шага 3. Регресс: только документы.
**Зависимости:** требует шаги 1–3.
**Оценка:** ~70 строк текста, ~20 минут.

### Шаг 5: итоговая проверка

**Цель:** полный прогон, сценарий книги генератора, отчёт.
**Что сделать:**
1. Полный прогон из `<W>\numerical_solver`: `<PY> -m pytest tests/ -q` (`/implement` §3.1) — ожидание 2395 собрано, **2394 passed, 1 skipped** (тест черновика руководителя: черновик вне git).
2. Сценарий книги генератора (после полного прогона): из `<W>\numerical_solver` — `<PY> -m gpn_multiphase_solver convert configs/INPUT_TEMPLATE_v1.xlsx ..\vault\issues\feat-035\probes\scenario_case` → код 0, «Конфиг записан: …»; `<PY> -m gpn_multiphase_solver run ..\vault\issues\feat-035\probes\scenario_case\config.json` → код 0, без строк предупреждений, 30–40 с (пробы плана — 36.8 и 28.6 с), заголовок «=== INPUT_TEMPLATE_v1 ===», в `output/` — 12 файлов штатного набора и каталог `emf` (проба плана — §12). Каталог `scenario_case` удалить, в git не добавлять.
3. Комментарий в issue `vault/issues/feat-035/05-comment-done.md`; запись в реестре.

**Регресс:** полный (итог реализации).

## 9. Тестовая стратегия

Все тесты — `numerical_solver/tests/test_workbook_convert.py`, кроме командной строки (`tests/test_cli.py`). Книги с ошибками — в памяти: правка `Cell` книги генератора (разбор FEAT-034 уже проверен своими тестами); сквозь разбор — книги XlsxWriter в `tmp_path` и фикстура Excel `template_saved.xlsx`.

| Категория | Тесты | Сценарий → ожидание | Предотвращает |
|---|---|---|---|
| Согласованность: книга генератора | `test_template_converts_and_builds`, `test_excel_saved_template_converts`, `test_xlsxwriter_book_equals_template` | 4 файла; `load_config`, `create_pvt`, `create_relperm`, `SimulatorFactory.from_config` проходят ($N$ = 100); после Excel $r_w$ = 0.1 м (формула `=0.2/2`); книга из таблицы полей = книга генератора | отставший снимок генератора; перевод, который не принимает загрузчик |
| Unit: ячейка → файл | `test_param_cells_to_json_bitwise`, `test_table_cells_to_csv_bitwise`, `test_integer_fields_written_as_int`, `test_every_book_field_explicit` | каждое поле JSON = `UNIT_TO_SI(ячейка)` побитово, тип тот же; CSV — заголовок фабрики, числа побитово; `"N": 100,` в тексте; поля конфига = поля книги + `DERIVED` + model/file/title | потеря точности; подставленные умолчания; 100.0 в целом поле |
| Аналитика: составные поля | `test_derived_porosity_and_rho_cp`, `test_porosity_above_one_refused` | $p_{ref} = p_0$: $\varphi_0 = 0.2$; $p_{ref}$ = 150 бар: $\varphi_0 = 0.2\,e^{2.25\cdot10^{-3}}$; обратно $\varphi_0 e^{c_r(p_{ref}-p_0)} = 0.2$ (rel 1e-14); $(\rho c_p)_s$ = 2 173 000 Дж/(м³·К); $c_r$ = 0.05 1/бар, $p_{ref}$ = 150 бар: $\varphi_0 = 0.2\,e^{2.5} \approx 2.44$ — ошибка у `MODEL!C7 (Reference porosity (φref))` с вычисленным $\varphi_0$ | пористость при $p_{ref}$ вместо $p_0$; единицы $c_r$; отказ при расчёте по полю, которого нет в книге |
| Инвариант: время | `test_history_from_template`, `test_moments_in_whole_ms_do_not_drift` | 22 интервала = `TEMPLATE_DT`, сумма 2 592 000 с ровно; 700 интервалов по $1/7$ сут: накопленное время ≤ 0.5 мс от $t_k$, $\Delta t$ ∈ {12342.857, 12342.858} | дрейф моментов записи (округление разностей); строка ↔ интервал |
| Предельные случаи: SCHEDULE | `test_schedule_errors` (12), `test_rate_rows_shut_in_and_foreign_cells`, `test_last_row_mode_not_read`, `test_mode_with_spaces_accepted`, `test_empty_row_in_schedule_skipped` | $t_0 \ne 0$, убывание, интервал < 0.5 мс, одна строка, неверный режим и регистр, пустые и отрицательные уставки, дата — отказ с адресом; OIL_RATE и останов (0, 1.01325 бар) — `load_config` принимает при заполненных чужих ячейках; режим последней строки не читается | отказ `_validate_interval` из-за чужих ячеек; молчаливый ноль |
| Предельные случаи: таблицы | `test_empty_row_in_table_skipped` (3), `test_cells_right_of_tables_not_read`, `test_table_header_with_spaces_accepted`, `test_table_cell_errors` (8), `test_relperm_end_rows` (4), `test_relperm_without_rows`, `test_relperm_ends_not_checked_after_cell_error` | пустая строка и столбцы вне таблицы — без изменений CSV; заголовок, текст, дата, пусто, предел, ошибка Excel, логическое — отказ с адресом; крайние строки RELPERM | потеря строк ниже пустой; ложная «первая строка» после ошибки |
| Предельные случаи: листы «параметр–значение» | `test_missing_sheet` (7), `test_comments_and_extra_sheets_not_read`, `test_format_version` (3), `test_format_version_row_missing`, `test_param_header_mismatch`, `test_unknown_and_foreign_keys`, `test_duplicate_key`, `test_missing_key_row`, `test_row_without_key`, `test_key_and_unit_with_spaces_accepted`, `test_unit_mismatch`, `test_value_kinds` (9), `test_limits` (7), `test_above_skipped_when_reference_invalid`, `test_integer_from_float`, `test_fixed_values` (4) | правила решений 6, 10, 15, 17, 20, 25, 26: каждое — отказ с адресом (`MODEL!C…`, подпись строки) или приём | ячейка молча в умолчание; ошибки, зависящие от другой ошибки |
| Сообщение | `test_all_errors_at_once_in_sheet_order`, `test_error_list_capped`, `test_content_error_is_workbook_error` | 4 ошибки на 4 листах — в порядке MODEL, NUMERICS, SCHEDULE, GAS_PVT; 34 ошибки — 30 строк и «… и ещё 4»; подкласс `WorkbookError` и `ValueError` | несколько запусков на книгу; трассировка в командной строке |
| Файлы | `test_convert_into_empty_existing_dir`, `test_convert_refuses_non_empty_dir_or_file` (2), `test_book_error_leaves_no_files`, `test_reader_errors_pass_through`, `test_files_text_format`, `test_title_and_output_section` | пустой каталог — можно; непустой или файл — `FileExistsError`, содержимое не тронуто; книга с ошибкой — каталог не создан; нет файла — `FileNotFoundError`, не zip — `WorkbookError` разбора; «\n», UTF-8; заголовок «скважина 7» читаем | затирание чужих файлов; полупереведённый каталог |
| Сквозь разбор | `test_formula_with_saved_value_accepted`, `test_formula_in_recalc_book_refused`, `test_date_cell_through_reader` | `=0.11/3600` после Excel — $h_0$ = значение ячейки × 3600 с; та же книга с пометкой пересчёта — отказ «пересчитать при открытии»; формат 14 — отказ «с форматом даты» | ложный 0 XlsxWriter; «1.5 → 1 мая» числом |
| Командная строка | 7 тестов `test_cli.py` (§3) | код 0 и 4 файла в отдельном процессе; справка; код 2 на ошибку книги («нет листа THERMAL», каталог не создан), не zip, нет файла, непустой каталог; `scipy` и `radial_blackoil` не в `sys.modules` | трассировка вместо сообщения; тяжёлый импорт |
| Регрессия | все 2288 | без изменений | — |

**Проверка самих тестов** (проба `plan_apply.py`): 20 порч кода плана — каждую ловит хотя бы один тест (§12).

## 10. Критерии завершения

- [ ] `io/workbook_convert.py` — как `plan_code/workbook_convert.py`; docstring — одна строка у каждой функции.
- [ ] `cli.py` — как `plan_code/cli.py` (`git diff` — только подкоманда `convert`).
- [ ] `tests/test_workbook_convert.py` — 100 тестов; `tests/test_cli.py` — +7; зелёные.
- [ ] Быстрый уровень и полный прогон зелёные: 2395 (при ушедшей базе — её число + 107).
- [ ] `test_declared_dependencies_cover_imports`, `test_eq_references.py`, `test_public_api.py` зелёные; зависимости пакета не изменились.
- [ ] Сценарий книги генератора `convert` → `run` — код 0, предупреждений нет.
- [ ] Прототип, загрузчик, фабрика, пример 18 не тронуты (`git diff --stat` по `numerical_solver/`: только `io/workbook_convert.py`, `cli.py`, два файла тестов и, если он уже есть, `CHANGELOG.md`).
- [ ] Заметка `vault/knowledge/decisions/…`, правки заметки о формате, `index.md`, контракт в плане FEAT-036.
- [ ] Реестр FEAT-035 и issue #133 прокомментированы.

## 11. Новые проблемы

- **[[DEBT-081]]** (зарегистрирована 2026-10-18, без issue): `grid.N` не проверяется на целое в `_validate` — `true` проходит и `_validate`, и `LogRadialGrid` (`bool` — подкласс `int`): расчёт на сетке из одной ячейки молча; `"100"` — `TypeError` без имени поля; `100.0` — отказ сетки по-английски. Перевод книги пишет `int` и дефекта не задевает (`test_integer_fields_written_as_int`); не блокирует.
- Черновик плана §2.3 (множители «× 1e-5», «× 1e-3»; $h_0$ = 0.10999999999999999 с) устарел — исправлен в §2.3 этой версии.
- Связь с FEAT-036: открытый вопрос 4 черновика (заголовок) закрывается решением 29; контракт исключений — шаг 4.
- Наблюдение аудита 1 (не задача): консольной команды `gpn-solver` в `numerical_solver/.venv` основного каталога нет — редактируемая установка сделана до FEAT-030 (`[project.scripts]`); `<PY> -m gpn_multiphase_solver` работает. Появится после `pip install -e HydroSolverPrototype/Prototype_1.0.3 -e ".[dev]"`; у заказчика — сразу (установка из среза, FEAT-031).

## 12. Проверка плана

- **Полнота:** правила → код → тесты — §3, у каждого правила есть тест; шаги без циклов (1 → 2, 1 → 3, 1–3 → 4 → 5); подводные камни — §6; совместимость — §4; категории тестов — §9 (аналитика — составные поля; сходимости в задаче нет).
- **Корректность:** имена, на которые ссылается план, существуют на `55868a6`: `io/workbook_format.py` (`PARAM_SHEETS`, `TABLE_SHEETS`, `SCHEDULE`, `CONTROL_MODES`, `UNIT_TO_SI`, `DERIVED`, `NOT_FROM_WORKBOOK`, `RELPERM_FIRST_ROW`, `RELPERM_LAST_ROW`, `Param.accepts`, `Limit.accepts`, `FORMAT_VERSION`, `PARAM_HEADER`, `SHEET_ORDER`), `io/xlsx_reader.py` (`read_workbook`, `Workbook.path/sheets/recalc_on_open`, `Sheet.cells/cell/max_row`, `Cell.kind/value/is_date/formula/formula_without_value/ref`, `WorkbookError`, типы `NUMBER`…`EMPTY`), `io/workbook_template.py` (`DEMO_TABLES`), `io/config.py` (dataclass-секции, `load_config`, `_validate_interval`), `factory.py` (`create_pvt`, `create_relperm`, `SimulatorFactory.from_config`), `units.py` (`DAY_TO_S`), `cli.py` (`_parser`, `_template`, `main`), `tests/test_cli.py` (`SOLVER`, `_run`).
- **Код плана проверен** (`probes/plan_apply.py`; копия `git archive HEAD numerical_solver`, рабочий код не тронут) — вывод `probes/plan_apply.out.txt` (2026-10-18, `55868a6`):
  - новые тесты, весь `test_cli.py` и сторожа (`test_eq_references.py`, `test_public_api.py`, `test_declared_dependencies_cover_imports`) — **150 passed, 2 skipped** (сторож заметок: в копии нет vault); собрано 100 в `test_workbook_convert.py`, 7 `convert` в `test_cli.py`, всего **2395**;
  - весь быстрый уровень на копии — **2116 passed, 3 skipped, 276 deselected**, 0 failed (пропуски: 2 — сторож заметок vault, 1 — черновик руководителя); в worktree vault есть — ожидать 2118 passed, 1 skipped;
  - **20 порч кода плана — каждую ловит хотя бы один тест** (число упавших): пробелы не срезаются — 4; округление разностей вместо целых мс — 2; целые не в `int` — 6; читаются ячейки чужого режима — 81; пустая строка таблицы — ошибка — 4; постоянные слова не проверяются — 3; крайние строки RELPERM не проверяются — 5; крайние строки и после ошибки ячейки — 1; дата принимается — 4; формула без значения как пустая ячейка — 4; только первая ошибка — 3; единица не сверяется — 1; заголовки не сверяются — 2; пористость без пересчёта к $p_0$ — 2; $\varphi_0 > 1$ не проверяется — 1; пустой текст общей формулы в сообщении — 1; первая строка SCHEDULE не проверяется — 1; сравнение $r_e > r_w$ при ошибке $r_w$ — 10; непустой каталог не проверяется — 3; командная строка не ловит `WorkbookError` — 2;
  - сценарий: `convert` книги генератора — код 0; `run` по её `config.json` — код 0, **28.6 с (прогон до аудита — 36.8 с), предупреждений нет**, 12 файлов штатного набора и `emf`;
  - первый прогон пробы (планирование) нашёл 2 ошибки кода плана — исправлены: `config.json` писался с «\r\n» (`Path.write_text` на Windows без `newline="\n"`), тест целых полей ждал запятую после последнего поля секции.
- **Аудит 1 ✅ (2026-10-18, база `55868a6`, 2288 тестов; фокус — предметная суть):** 🟡 3, 🔵 6, исправлены все; код плана перепроверен пробой (числа выше — после аудита). Найдено:
  - 🟡 $\varphi_0 > 1$ при расчёте отвергал бы `_validate` сообщением о `rock.porosity` — поле, которого нет в книге (ключ строки = путь JSON у всех полей, кроме составных; $(\rho c_p)_s > 0$ и пределы SCHEDULE совпадают с программой) → умолчание 35, `_check_porosity`, тест, порча;
  - 🟡 шаг 3 заменял `cli.py` целиком — правка другой задачи до реализации стёрлась бы → проверка `git diff 55868a6` и запасной путь вставками;
  - 🟡 параллельная работа: другая сессия правит план FEAT-031 и реестр (FEAT-037 — `__version__`, `CHANGELOG.md`, `pyproject.toml`) → «Как начать», п. 6 (что коммитить), шаг 4 (строка журнала, если он есть), §6;
  - 🔵 ROCK в OPM сверен по руководству (табл. 8.138, формула (8.97)) — отметка «не сверено» снята; пример сообщения — `MODEL!C6` (проницаемость в строке 6, не 5); у ячейки общей формулы без значения сообщение «формула = без…» → «общая формула»; две строки кода длиннее 100 символов перенесены (длинные однострочные докстринги в пакете — принятая практика, 25 строк); «книга, открытая в Excel, читается» — не проверено, ⚠️ в §6; docstring `_parser` устарел ещё с FEAT-033 — обновлён; команды — только из `<W>\numerical_solver` (`gpn-solver` в `.venv` нет); ссылка на [[временная-сетка-и-история]].
  - Перепроверено и верно: $(1-\varphi_0)(\rho c_p)_s$ и $(1-\varphi_0)\lambda_s$ в `energy/tridiag.py` — $\rho_{ma}c_{ma}$ — свойство зёрен, как и задумано (FEAT-033 решение 52); `CompressibleRock(p_ref_bar = p0, cr_per_bar = c_r·1e5)` — перенос опорной точки точный; К/МПа → К/Па делением на 1e6, кДж/кг × 1e3, м³ст/сут ÷ 86400 — по смыслу полей конфига; baseline 2288 на `55868a6` — совпал; невлитых веток нет.
- **Автономность:** код шагов 1–3 — файлы `plan_code/`; команды — `<PY>` из `<W>\numerical_solver`; ожидания — числами.

## 13. Итог реализации (2026-10-18)

Ветка `feat/feat-035/workbook-to-config` (от `4b67213`): `7059178` (модуль), `fbf2438` (тесты перевода), `fed9dd8` (подкоманда и тесты командной строки), `9f55080` (документы). Код шагов 1–3 — `probes/plan_code/` побайтно; `git diff 55868a6` у `cli.py` перед заменой был пуст. Ожидания плана сошлись точно: baseline 2288 / быстрый 2011 passed, 1 skipped; после шага 2 — 2388 / 2111; после шага 3 — 2395 / 2118; полный прогон 2394 passed, 1 skipped (599 с). Сценарий книги генератора (`PYTHONPATH` на worktree, пакеты — из `<W>`): `convert` — код 0, `run` — код 0, 29.5 с, предупреждений нет. `CHANGELOG.md` нет — строка журнала (шаг 4) пропущена. Новых задач при реализации не найдено.

## Связанные заметки

- Реестр: `vault/roadmap/планируемые фичи.md` — FEAT-035; [[DEBT-081]] — `известные баги и технический долг.md`
- [[feat-033 workbook-input-format]], [[feat-034 xlsx-cell-reader]], [[feat-036 run-from-workbook]]
- [[книга ввода Excel версии 1 — все параметры явно, единицы фиксированы]], [[разбор книги xlsx сообщает тип ячейки — отказ по типу решает перевод]]
- [[P8-формат-ввода-json]], [[json-config-schema]], [[временная-сетка-и-история]] (интервалы `time.history` и моменты записи)
