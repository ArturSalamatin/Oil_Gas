---
tags:
  - план
  - рефакторинг
date: 2026-10-07
issue: DEBT-042
github: 72
branch: refactor/debt-042/strict-csv-readers
worktree: .worktrees/debt-042 (код и тесты — в ветке; vault задачи — в основном каталоге)
status: в процессе
audit:
  date: 2026-10-07
  round: 2
  focus: реализуемость тестов под настоящим pytest, контракт коммитов /implement, предметная суть правил разбора
  found: 6
  auto-fixed: 6
  manual-required: 0
---

# План DEBT-042: строгий разбор CSV-таблиц фабрики

**Задача:** DEBT-042 в `vault/roadmap/известные баги и технический долг.md` · GitHub [#72](https://github.com/ArturSalamatin/Oil_Gas/issues/72) · ветка `refactor/debt-042/strict-csv-readers` в worktree `.worktrees/debt-042` · база `numerical_scheme/implementation` (`1e09b14`; код `numerical_solver/` с `3bd659e` не менялся)

**Подтип:** рефакторинг с ужесточением проверки ввода. Три CSV-ридера фабрики переводятся на общий разборщик строк. Корректные таблицы разбираются побитово как раньше: числа решателя, результаты примеров и код прототипа не меняются.

## Кратко

Сейчас три CSV-ридера фабрики (`_read_oil_pvt_csv`, `_read_gas_pvt_csv`, `_read_relperm_csv`) молча пропускают строку с нечисловым значением и строку короче нужного. Лишние поля они отбрасывают, `nan` и `inf` принимают, заголовок пропускают не глядя. Последствия, подтверждённые пробой:
- опечатка в числе удаляет строку таблицы;
- десятичная запятая сдвигает значения на столбец: $\mu_o$ = 20 Па·с вместо 1.5 мПа·с;
- файл без заголовка теряет первую строку данных;
- у ОФП ошибка во 2-м или 3-м столбце даёт столбцы разной длины. `from_config` проходит, а `run` падает с `ValueError: fp and xp are not of the same length` из `np.interp`.

После правки ридеры строятся на общей функции `_read_numeric_csv`. Она отвергает с `ValueError` (имя файла, номер строки, столбец):
- заголовок, не совпадающий с ожидаемым;
- пустой файл;
- строку, в которой число полей не равно числу столбцов;
- нечисловое или не конечное значение.

Пустые строки по-прежнему пропускаются.

Объём: 1 функция (~45 строк), 3 константы, 3 ридера переписаны короче (~75 → ~30 строк), 16 тестов, 2 абзаца документации. Тестов: 1307 → 1323.

**Код плана проверен подменой** (2026-10-07, `3bd659e`, проба `vault/issues/debt-042/probes/plan_check.py`, вывод в `plan_check.out.txt`). Проба берёт блоки кода шагов 2 и 3 прямо из этого файла и исполняет реализацию в пространстве имён модуля `factory` в памяти, не меняя файлов. Результаты:
- тесты шага 2 на текущих ридерах: 15 failed, 1 passed;
- на ридерах шага 3: 16 passed;
- разбор 47 таблиц совпадает со снимком побитово;
- быстрый уровень на подменённых ридерах (`plan_check.py --pytest`): 1071 passed — как без подмены, с тем же единственным `PytestRemovedIn10Warning`.

Аудит 2 проверил блок тестов шага 2 под **настоящим pytest** (`probes/test_plan_block.py`: модуль собирает класс из блока плана, реализация шага 3 подставляется в память при `DEBT042_PATCHED=1`). Результат: до подмены 15 failed, 1 passed, у `test_oil_empty_file_raises` — `StopIteration` из `factory.py:439`; после подмены 16 passed.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-042 в `vault/roadmap/известные баги и технический долг.md` и тело issue `vault/issues/debt-042/01-issue-body.md` (таблица «Ошибка → поведение → сигнал»).
3. ⚠️ **Работай в worktree `.worktrees/debt-042`, не переключай ветку основного каталога** (аудит 2026-10-07). Основной каталог `D:\Lessons\Grants\2026\GPN\Oil_Gas` занят параллельными сессиями:
   - сессия DEBT-043 коммитит туда vault на `numerical_scheme/implementation` (`1e09b14`);
   - реализация DEBT-043 и BUG-020 идёт в `.worktrees/debt-043` и `.worktrees/bug-020`.

   `git checkout -b` в основном каталоге увёл бы их vault-коммиты в ветку DEBT-042. Так же реализованы DEBT-038, DEBT-039, BUG-018, FEAT-020. Ветка `/implement` (`git checkout -b`, `.claude/commands/implement.md:92-93`) здесь заменяется на `git worktree add`.
   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   git branch --show-current          # numerical_scheme/implementation — НЕ менять
   git log -1 --oneline               # 1e09b14 или новее
   git diff --stat 3bd659e numerical_scheme/implementation -- numerical_solver   # пусто, если код базы не менялся
   git worktree add .worktrees/debt-042 -b refactor/debt-042/strict-csv-readers numerical_scheme/implementation
   cd .worktrees\debt-042\numerical_solver
   ```
   Если `git diff --stat` не пуст и затрагивает `factory.py`, сверь номера строк шага 3 по grep `# ── CSV-ридеры`. Вероятный случай — влит BUG-020: он добавляет 4 строки в `_create_prototype_hydro` (`factory.py:328`) выше ридеров, и тогда ридеры стоят на `429-505`.

   **Что есть только в основном каталоге** (в worktree этого нет, править и запускать — по абсолютному пути):
   - этот план (на 2026-10-07 не отслеживается git) и поля записей DEBT-042, DEBT-044 в реестре (не закоммичены);
   - `vault/issues/debt-042/` — тело и комментарии issue, пробы `probes/`. Каталог `vault/issues/` в `.gitignore` (строка 48).

   В `vault/` основного каталога есть чужие незакоммиченные правки (DEBT-041, DEBT-043 — параллельная работа): не трогать и не коммитить их.
   **Поправка при реализации (2026-10-07).** С `458d6a2` `vault/issues` отслеживается git (игнорируются только `.npz` и графики), и материалы DEBT-042 уже в базе. Значит, пробы есть и в worktree. По правилу 4 `/implement` их запускают из `<W>`: `$pr = "<W>\vault\issues\debt-042\probes"`. Пробы берут код из текущего каталога, поэтому результат тот же. Снимок `tables_snapshot.json` и `*.out.txt` — отслеживаемые текстовые файлы. Если они изменились, коммитить на ветке (`vault:`). Шаг 1 переснимает те же таблицы тем же кодом, поэтому снимок побитово не меняется.
4. Интерпретатор и пробы — по абсолютным путям: в worktree нет `.venv` (каталог в `.gitignore`), venv общий.
   ```powershell
   $py = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   $pr = "D:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-042\probes"
   & $py -c "import gpn_multiphase_solver as g; print(g.__file__)"   # путь .worktrees\debt-042\... — иначе стоп
   ```
   Все команды pytest и проб — из `.worktrees\debt-042\numerical_solver` (текущий каталог первым в `sys.path`, поэтому pytest берёт код worktree; проверено аудитом из `.worktrees/debt-043`: 1310 собрано, `test_factory_prototype.py` 37 passed). Пробы берут код **из текущего каталога** и печатают первой строкой `Код: <путь к factory.py>`. Путь должен вести в worktree.
5. Baseline (замер при планировании и аудите 2026-10-07, код `3bd659e` = `1e09b14`):
   ```powershell
   & $py -m pytest tests/ --collect-only -q                # 1307 тестов
   & $py -m pytest tests/ --collect-only -q -m "not slow"  # 1071/1307 (236 deselected)
   & $py -m pytest tests/ -m "not slow" -q                 # 1071 passed, 1 warning (PytestRemovedIn10Warning, был и до правки), ~63 с
   & $py -m pytest tests/test_factory_prototype.py -q      # 37 passed, ~2 с
   ```
   Если чисел больше, база сдвинулась: параллельно идут DEBT-043 (+3 теста) и BUG-020. Запиши новые числа и дальше считай от них. План добавляет ровно 16 тестов, все в быстром уровне.
6. Начни с шага 1. После каждого шага — его проверка. Полный прогон — в шаге 6. Влитие — из основного каталога, он уже на базовой ветке: `git merge --no-ff refactor/debt-042/strict-csv-readers`, затем `git worktree remove .worktrees/debt-042`.

## Контекст для читателя без контекста

**Где читаются CSV.** Для `pvt.model = "table"` и `relperm.model = "table"` фабрика `SimulatorFactory.from_config` (`numerical_solver/gpn_multiphase_solver/factory.py`) читает три CSV-файла из каталога JSON-конфига:

```
_create_pvt, ветвь "table" (:115-146)
  _read_oil_pvt_csv (:427-451) → [(Rs, p_бар, Bo, mu_сП), ...]
  _read_gas_pvt_csv (:454-477) → [(p_бар, Bg, mu_сП), ...]
  _check_pvto_branches (:127, определена :168-218) — ветви PVTO (DEBT-038)
  BlackOilPVT(oil_rows, gas_rows) (:130) — прототип, radial_blackoil/pvt.py
_create_relperm, ветвь "table" (:316-322)
  _read_relperm_csv (:480-501) → (Sg, kro, krg) — три списка
  TabulatedRelPerm(Sg, kro, krg) (:321) — прототип, radial_blackoil/relperm.py
```

Единицы в файлах — СИ (Па, Па·с). Ридеры нефти и газа переводят давление в бары, вязкость в сП, потому что так их принимает `BlackOilPVT`. ОФП безразмерны.

**Формат таблиц** (`vault/knowledge/decisions/P8-формат-ввода-json.md`, раздел 2). Заголовки фиксированы:

| Файл | Заголовок |
|---|---|
| `oil_pvt.csv` | `Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s` |
| `gas_pvt.csv` | `pressure_Pa,Bg,mu_g_Pa_s` |
| `relperm.csv` | `Sg,kro,krg` |

Все 47 таблиц проекта (16 нефть, 16 газ, 15 ОФП: `configs/table_pvt`, примеры 04, 04a, 05–16, `tests/data/bug016_example14`) имеют ровно эти заголовки. BOM нет ни в одной, все строки разбираются в конечные числа с правильным числом полей. Проверено пробой `vault/issues/debt-042/probes/tables_check.py` 2026-10-07: «Нарушают правила строгого разбора: 0 из 47», 647 строк данных. Все конфиги ссылаются на файлы с этими именами.

**Как устроены ридеры сейчас** (на примере нефти, `factory.py:436-451`):

```python
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # заголовок
        for line in reader:
            if len(line) < 4:
                continue
            try:
                Rs = float(line[0])
                p_bar = float(line[1]) / BAR_TO_PA
                Bo = float(line[2])
                mu_cP = float(line[3]) / CP_TO_PA_S
            except ValueError:
                continue
            rows.append((Rs, p_bar, Bo, mu_cP))
    return rows
```

`csv.reader` делит строку по запятым и возвращает список строк-полей. Пустая строка файла даёт `[]`. `continue` — переход к следующей строке без сообщения.

**Красное состояние — замер.** Проба `vault/issues/debt-042/probes/red_state.py`, вывод в `red_state.out.txt` (2026-10-07, `3bd659e`):

| Случай | Что вернул ридер / что сделала фабрика |
|---|---|
| `30.0,15OOOOOO,1.20,0.0015` (буква O) | 3 строки из 4: строка пропала молча |
| `30.0,15000000,1,20,0.0015` (десятичная запятая) | 4 строки, у третьей $B_o$ = 1.0, $\mu_o$ = 20000 сП |
| `30.0,15000000,1.20` (пропущено значение) | 3 строки |
| `30.0,15000000,1.20,0.0015,` (запятая в конце) | 4 строки, лишнее поле отброшено |
| `30.0,nan,1.20,0.0015` / `inf` в $B_o$ | приняты: `(30.0, nan, 1.2, 1.5)`, `(30.0, 150.0, inf, 1.5)` |
| строка из пробелов | пропущена (так и должно остаться) |
| файл без заголовка | первая строка данных `(0.0, 50.0, ...)` съедена как заголовок, 3 строки из 4 |
| заголовок `...,mu_o_Pa_s,Bo` (переставлены) | принят, столбцы читаются по позиции |
| пустой файл (0 байт) | `StopIteration` из `next(reader)` |
| BOM в начале файла | принят: заголовок пропускается не глядя |
| `;` и десятичная запятая (Excel, русская локаль) | 0 строк, без сообщения |
| `gas_pvt.csv`: `15000000,0.0O8,0.000014` | 2 узла из 3 |
| `relperm.csv`: ошибка во 2-м / 3-м столбце | длины `(Sg, kro, krg)` = (3, 2, 2) / (3, 3, 2) |
| `from_config` + `run`, ОФП с ошибкой в `kro` | `from_config` проходит; `run`: `ValueError: fp and xp are not of the same length` (`numpy/_function_base_impl.py`) |
| `from_config`, `gas_pvt.csv` через `;` | `ValueError: GAS_PVT pressure must be strictly increasing with >=2 rows` (`pvt.py:32`) — без имени файла, причина другая |
| `from_config`, `relperm.csv` через `;` | `ValueError: RELPERM Sg must be strictly increasing with >=2 rows` (`relperm.py:5`) — то же |

**XLSX-ридер прототипа** (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/input_reader.py:56-58`, `68-70`, `76-78`) пропускает нечисловые строки так же (`except (TypeError, ValueError, IndexError): continue`). Эталона строгости в проекте нет. Правила ниже — решение этого плана. Прототип не меняется: GPN читает только CSV.

**Решения пользователя (2026-10-07, при планировании):**
1. Объём — только разбор строк (вариант 2 issue). Проверки допустимости значений, которые есть в XLSX-ридере и которых нет на CSV-пути ($B_g > 0$, $\mu_g > 0$, $S_g \in [0, 1]$), — отдельная запись DEBT-044 (см. «Обнаруженные проблемы»).
2. Заголовок сверяется по именам столбцов, а не только по их числу. Это ловит файл без заголовка и перестановку столбцов. Пробелы вокруг имён допустимы.
3. Пустое поле в конце строки (`...,0.003,`) — ошибка: правило одно, число полей равно числу столбцов.

**Решения плана (не требовали выбора пользователя):**
4. Пустая строка — нет полей или все поля пустые/из пробелов (`[]`, `['   ']`, `['', '', '', '']`). Она пропускается, как сейчас. Строка `,,,` из пустых ячеек — типичный хвост экспорта из Excel.
5. Таблица без строк данных (только заголовок) разборщиком не отвергается. Это вопрос числа строк, а не разбора. У нефти такую таблицу ловит `_check_pvto_branches` («нет ни одной числовой строки», тест DEBT-038 `test_empty_table_raises`), у газа и ОФП — конструкторы прототипа. Пустой файл без заголовка — ошибка разборщика: заголовка нет.
6. В сообщении указывается имя файла `csv_path.name` и номер строки файла `reader.line_num`, где заголовок — строка 1. DEBT-038 пишет строку из конфига (`pc.oil_pvt_file`). Для всех конфигов проекта (`"oil_pvt.csv"`) префикс одинаков: `oil_pvt.csv: ...`. Различие появится только при подкаталоге в конфиге (`"tables/oil.csv"` → `oil.csv:` против `tables/oil.csv:`), это допустимо (аудит).
7. Кодировка `utf-8-sig`: BOM (его пишут Excel и «Блокнот» Windows) не попадает в имя первого столбца. Для файлов без BOM это та же `utf-8`. `newline=""` — режим, который документация модуля `csv` требует для `open`.

## Текущее состояние (baseline)

- Тесты: 1307 всего, 1071 в быстром уровне — 1071 passed за 63 с (HEAD `3bd659e`, замер 2026-10-07). `tests/test_factory_prototype.py` — 37 passed.
- Вызовы ридеров в пакете: `factory.py:123`, `:124`, `:318`. В тестах: `tests/test_factory_prototype.py:23` (импорт), `TestCSVReaders` (`:38-114`). Других вызовов нет: grep `_read_\w+_csv` по `numerical_solver/` без `.venv` и прототипа. `examples/` CSV-таблицы сами не читают (grep `csv.reader|loadtxt|genfromtxt|read_csv` → только `factory.py` и `examples/04a_high_gas_saturation/plot_profiles_50k.py:44`, который читает CSV результатов, не таблицы).
- Тексты CSV в тестах (`test_factory_prototype.py`, `test_pvt_consistency.py:40-51`) — со стандартными заголовками, корректные.
- Снимок разбора 47 таблиц текущими ридерами: `vault/issues/debt-042/probes/tables_snapshot.json` (снят 2026-10-07 на `3bd659e`; шаг 1 переснимает его на базе ветки).

## Целевое состояние

- `factory.py`, раздел `# ── CSV-ридеры ──`:
  - константы `_OIL_PVT_COLUMNS`, `_GAS_PVT_COLUMNS`, `_RELPERM_COLUMNS`;
  - функция `_read_numeric_csv(csv_path, columns, kind) -> list[tuple]` — все правила разбора в одном месте;
  - три ридера — обёртки: вызов разборщика + перевод единиц (нефть, газ) или раскладка по столбцам (ОФП). Сигнатуры, типы возврата и сообщение «Файл … не найден: …» прежние.
- ОФП: столбцы собираются из целых строк. Если в строке ошибка, разборщик бросает исключение до записи строки, поэтому длины `Sg`, `kro`, `krg` совпадают по построению.
- Ошибка в любой CSV-таблице — `ValueError` в `from_config` с именем файла, номером строки и (для значения) именем столбца.
- Корректные таблицы: результат ридеров побитово прежний (проба `tables_check.py --compare`). Деление `p / BAR_TO_PA`, `mu / CP_TO_PA_S` то же, что сейчас.
- Импорты не меняются: `csv`, `numpy as np`, `Path`, `BAR_TO_PA`, `CP_TO_PA_S` уже импортированы в `factory.py`.

## Варианты и выбор

Подробно — в теле issue #72, раздел «Анализ вариантов решения». Кратко:

| Вариант | Суть | Итог |
|---|---|---|
| 1 | точечная правка трёх ридеров: `continue` → `raise` | отклонён: одни правила и сообщения в трёх копиях, три набора одинаковых тестов, у ОФП рассинхрон устраняется отдельной правкой |
| 2 | общий разборщик `_read_numeric_csv`, ридеры — обёртки | **выбран** (решение 1): правила в одном месте, рассинхрон ОФП невозможен по построению, сигнатуры ридеров не меняются |
| 3 | вариант 2 + проверки значений как у XLSX | вне задачи (решение 1) → DEBT-044 |
| 4 | `np.loadtxt(path, delimiter=",", skiprows=1)` вместо своего разборщика (аудит) | отклонён: принимает `nan`/`inf`, заголовок не читает (файл без заголовка теряет строку, как сейчас), сообщение без имени файла, строку `,,,` отвергает, а план её пропускает (решение 4). Своего кода меньше не станет: проверки заголовка и конечности всё равно писать |

Промежуточные состояния: шаг 2 пишет тесты и фиксирует красное состояние (15 новых тестов красные, остальные зелёные), но **не коммитит** его. Тесты и реализация уходят одним коммитом в конце шага 3, когда зелёное всё. Причина: `/implement` запрещает коммитить сломанное состояние (`.claude/commands/implement.md:150-164`). DEBT-038 по плану той же формы сделал так же — тесты и код в одном коммите `e551d4c` (аудит 2).

## Подводные камни (чеклист)

- ✅ **Все места вызова найдены:** `factory.py:123`, `:124`, `:318` и тесты `TestCSVReaders`. Имена и сигнатуры ридеров не меняются, места вызова не трогаются.
- ✅ **Зависимости пакетов:** не меняются (`csv` — стандартная библиотека, `numpy` уже импортирован).
- ✅ **Обратная совместимость:** закрытые функции, типы возврата прежние. `TestCSVReaders` (7 тестов) проходит без правок:
  - тесты формата — стандартные заголовки, корректные строки;
  - `test_oil_csv_skips_blank_lines` — пустая строка `[]` пропускается (решение 4);
  - `test_*_missing_file` ждут «не найден» — сообщение то же.
- ✅ **Состояние при ошибке:** `raise` до создания объектов PVT/ОФП, частично построенного состояния нет. Файл закрывается `with` и при исключении.
- ✅ **Существующие тесты:**
  - `TestPVTOBranches` (DEBT-038, `test_factory_prototype.py:427-540`): все таблицы с `OIL_HEADER`, строки корректны. `test_empty_table_raises` (только заголовок) — разборщик возвращает `[]` (решение 5), сообщение даёт `_check_pvto_branches`, как раньше;
  - `test_pvt_consistency.py` (BUG-019) — стандартные заголовки;
  - `TestCSVReaders` пишет CSV через `write_text` без `encoding` (кодировка локали, cp1251). Текст ASCII, байты те же, `utf-8-sig` читает их так же.
- ⚠️ **Побитовая неизменность корректных таблиц.** Риски: другой порядок операций при переводе единиц; `newline=""` вместо универсальных переводов строк (CRLF-файлы); `utf-8-sig`. Перевод единиц — то же одно деление. `csv.reader` при `newline=""` сам разбирает `\r\n`, поля те же. Без BOM `utf-8-sig` = `utf-8`. Проверка — снимок 47 таблиц до правки (шаг 1) и `--compare` после (шаг 4). Ожидание: «побитово совпадает».
- ⚠️ **Номер строки в сообщении.** `reader.line_num` — число строк, прочитанных из файла, с заголовком и пустыми строками. Если внутри кавычек нет переводов строки (в таблицах проекта кавычек нет вовсе), это номер строки в файле. Тесты проверяют номер явно (`строка 4`, `строка 3`, `строка 6`). Тестовые файлы на Windows пишутся с `\r\n` (`write_text` переводит `\n`), номера от этого не меняются: проверено пробой `plan_check.py`.
- ⚠️ **Кодировка (аудит).** Файл не в UTF-8 с кириллицей (Excel «CSV» в cp1251 с русским текстом) даёт `UnicodeDecodeError`. Это подкласс `ValueError`, но без имени файла. Так было и до правки (`encoding="utf-8"`), регрессии нет. Заголовок и числа — ASCII, так что cp1251-файл без кириллицы читается правильно. Отдельная обработка не входит в задачу.
- ⚠️ **Worktree и пробы (аудит).** Пробы лежат в `vault/issues/` основного каталога (`.gitignore`). До аудита они вставляли в `sys.path` путь от своего расположения, то есть код **основного** каталога. Из worktree сверка шага 4 проверила бы неизменённый код и всегда давала бы «побитово совпадает». Теперь пробы берут код из текущего каталога и печатают `Код: <путь>`. Это проверено из `.worktrees/debt-043/numerical_solver`: путь worktree, сверка проходит.
- ⚠️ **Строки-комментарии (аудит 2).** До правки строка `# источник: …` или строка с пояснением текстом молча пропускалась: в ней меньше полей или нечисловое поле. Теперь это ошибка. Изменение поведения для внешних таблиц, не для проекта: в 47 таблицах строк, начинающихся с `#`, нет (grep), все строки разбираются (`tables_check.py`). Правило записано в P8 (шаг 5).
- ⚠️ **`float()` принимает больше, чем десятичная запись:** пробелы вокруг числа, `1e6`, `1_000` (подчёркивания, Python 3.6+), `nan`, `inf`, `Infinity`. Первые три безвредны, `nan`/`inf` отсекает `np.isfinite`. Подчёркивания в таблицах проекта не встречаются, запрещать их отдельно не нужно.
- ✅ **Циклические импорты:** новых импортов нет.
- ✅ **Docstrings:** `\eqref{}` нет (разбор ввода). Однострочный docstring у новой функции. Docstring ридеров не меняются.
- ✅ **Конфиги:** имена параметров не меняются. Все конфиги ссылаются на `oil_pvt.csv`, `gas_pvt.csv`, `relperm.csv` со стандартными заголовками.
- ✅ **Связь с другими задачами:**
  - DEBT-038 (`_check_pvto_branches`) получает строки уже без NaN. Её проверка пустой таблицы остаётся рабочей (решение 5);
  - BUG-017 (`_check_rs0_in_table`), BUG-019 (согласованность PVT) — после разбора, не меняются;
  - DEBT-043 (`.worktrees/debt-043`) `factory.py`, `test_factory_prototype.py`, P8, README 04 не трогает (`git diff --stat` против базы, аудит 2026-10-07);
  - BUG-020 (`.worktrees/bug-020`) добавляет 4 строки в `_create_prototype_hydro` (`phase_switching_stage=True`, `factory.py:328`). Это другой фрагмент файла, конфликта слияния нет, но ридеры сдвигаются на +4 строки. BUG-020 ждёт DEBT-043, которая уже в реализации, поэтому он вероятно будет влит раньше DEBT-042. Шаг 3 ищет границы по тексту;
  - DEBT-041 (план не закоммичен) правит README 03, `io/config.py`, два теста и **те же два документа**: P8 (шаг 6 DEBT-041, около строки 192 — раздел `max_retries`) и, по решению пользователя, README 04 (таблица `max_retries`, строки 290-294). Этот план правит P8 после строки 75 и README 04 перед строкой 47. Фрагменты разные и стоят ниже наших, поэтому git сольёт без конфликта, а номера строк шага 5 не сдвинутся при любом порядке влития.
- ✅ **Производительность:** разбор при создании симулятора, сотни строк, пренебрежимо.
- ✅ **Прототип:** не меняется (`radial_blackoil/` и его тесты не затрагиваются). Регрессия против `regression/golden/` не нужна.

## Шаги

### Шаг 1: Подготовка — ветка, baseline, снимок разбора

**Цель:** ветка от актуальной базы, числа тестов и снимок разбора 47 таблиц зафиксированы до правки.

**Файлы:** `vault/issues/debt-042/probes/tables_snapshot.json` (переснимается, в `.gitignore`).

**Что сделать** (из `.worktrees\debt-042\numerical_solver`, переменные `$py`, `$pr` — «Как начать», пункт 4):
1. Команды из «Как начать работу», пункты 3–5.
2. Воспроизвести красное состояние:
   ```powershell
   & $py "$pr\red_state.py"
   ```
   Первая строка вывода — `Код: D:\...\.worktrees\debt-042\numerical_solver\gpn_multiphase_solver\factory.py`. Дальше ожидание — как в таблице раздела «Контекст» (эталон — `$pr\red_state.out.txt`). Строки `[INFO]` логгера идут в stderr, это нормально. Проба создаёт и удаляет `red_state_tmp/` рядом с собой (в основном каталоге).
3. Переснять снимок на базе ветки (до правки кода!):
   ```powershell
   & $py "$pr\tables_check.py"
   ```
   Ожидание:
   - `Код: …\.worktrees\debt-042\…\factory.py`;
   - «Таблиц: 47 {'oil_pvt.csv': 16, 'gas_pvt.csv': 16, 'relperm.csv': 15}»;
   - «Нарушают правила строгого разбора: 0 из 47»;
   - «Снимок: tables_snapshot.json, 47 таблиц, 647 строк данных».

   Таблицы ищутся в текущем дереве (`rglob` от `numerical_solver/` worktree). Если таблиц или строк больше — база сдвинулась, это нормально. Если есть нарушения — **стоп**: таблица проекта не пройдёт новый разборщик, вопрос к пользователю.

**Проверка:** Регресс: быстрый — 1071 passed (или новое число базы).

**Зависимости:** блокирует шаги 2–7.

**Оценка:** 0 строк, ~3 мин.

### Шаг 2: Тесты строгого разбора (красные)

**Цель:** 16 тестов на правила разбора. До реализации 15 красных и 1 зелёный.

**Файлы:** `numerical_solver/tests/test_factory_prototype.py`

**Контекст:** тесты вызывают ридеры напрямую: правила разбора — свойство ридера, а не фабрики. Один тест идёт через `SimulatorFactory.from_config`. Он проверяет, что ошибка ОФП ловится в `from_config`, а не при `run`. Имена файлов в тестах — настоящие (`oil_pvt.csv`, …), потому что сообщение начинается с имени файла. Константы `OIL_HEADER`, `OIL_BRANCH_0`, `OIL_BRANCH_30` уже есть в разделе G (`test_factory_prototype.py:422-424`):
```python
OIL_HEADER = "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
OIL_BRANCH_0 = "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
OIL_BRANCH_30 = "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"
```
Нумерация строк файла: заголовок — 1, `OIL_BRANCH_0` — 2 и 3, следующая строка — 4.

**Что сделать:**
1. В docstring модуля (строки 3–10, список «Проверяют:») после строки 10 добавить:
   ```
   - Строгий разбор CSV: заголовок, число полей, конечные числа (DEBT-042)
   ```
2. В конец файла (после `TestPVTOBranches`, последняя строка 541) добавить раздел H:

```python


# ═══════════════════════════════════════════════════════════
# H. Строгий разбор CSV-таблиц (DEBT-042)
# ═══════════════════════════════════════════════════════════

# До DEBT-042 ридеры пропускали ошибочную строку молча (continue), лишние
# поля отбрасывали, заголовок не читали. Поведение до правки — замер
# vault/issues/debt-042/probes/red_state.out.txt (2026-10-07).
# Номер строки в сообщении — номер строки файла, заголовок — строка 1.

GAS_HEADER = "pressure_Pa,Bg,mu_g_Pa_s\n"
RP_HEADER = "Sg,kro,krg\n"


def _csv(tmp_path, name, text):
    """Записать text в tmp_path/name (UTF-8) и вернуть путь."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _parse_error(reader, path):
    """Текст ValueError, который ридер бросает на файле path."""
    with pytest.raises(ValueError) as excinfo:
        reader(path)
    return str(excinfo.value)


class TestCSVStrictParsing:
    """Ридеры отвергают строку, которую нельзя разобрать без потерь (DEBT-042)."""

    # ── Нефть: строки данных ──

    def test_oil_number_typo_raises(self, tmp_path):
        """Буква O вместо нуля в давлении.

        До правки строка пропадала, ветвь R_s = 30 оставалась из одной
        строки — DEBT-038 сообщил бы о ветви, а не об опечатке.
        """
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15OOOOOO,1.20,0.0015\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4, столбец pressure_Pa" in msg
        assert "15OOOOOO" in msg

    def test_oil_decimal_comma_raises(self, tmp_path):
        """Десятичная запятая «1,20» даёт 5 полей вместо 4.

        До правки значения сдвигались на столбец: B_o = 1, μ_o = 20 Па·с
        (20000 сП вместо 1.5) — молча.
        """
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15000000,1,20,0.0015\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4: число полей 5, а столбцов в заголовке 4" in msg

    def test_oil_short_row_raises(self, tmp_path):
        """Пропущено значение μ_o: 3 поля. До правки строка пропадала."""
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15000000,1.20\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4: число полей 3, а столбцов в заголовке 4" in msg

    def test_oil_trailing_comma_raises(self, tmp_path):
        """Запятая в конце строки — лишнее пустое поле (решение пользователя 3).

        До правки лишнее поле отбрасывалось. Правило одно для всех строк:
        полей столько же, сколько столбцов в заголовке.
        """
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15000000,1.20,0.0015,\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4: число полей 5" in msg

    def test_oil_nan_raises(self, tmp_path):
        """float() принимает 'nan'; сравнения с NaN ложны, и DEBT-038 строку не ловит."""
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,nan,1.20,0.0015\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4, столбец pressure_Pa" in msg
        assert "не конечное число" in msg

    def test_oil_inf_raises(self, tmp_path):
        """'inf' в B_o: до правки принимался как бесконечный объёмный коэффициент."""
        path = _csv(tmp_path, "oil_pvt.csv", OIL_HEADER + OIL_BRANCH_0
                    + "30.0,15000000,inf,0.0015\n30.0,30000000,1.18,0.0016\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: строка 4, столбец Bo" in msg
        assert "не конечное число" in msg

    # ── Нефть: заголовок и файл ──

    def test_oil_no_header_raises(self, tmp_path):
        """Файл без заголовка: до правки первая строка данных (p_b ветви 0) пропадала."""
        path = _csv(tmp_path, "oil_pvt.csv", OIL_BRANCH_0 + OIL_BRANCH_30)
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: заголовок" in msg
        assert "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s" in msg   # ожидаемый заголовок назван

    def test_oil_swapped_header_raises(self, tmp_path):
        """Столбцы Bo и mu_o_Pa_s переставлены: до правки читались по позиции, молча."""
        path = _csv(tmp_path, "oil_pvt.csv",
                    "Rs_sm3_sm3,pressure_Pa,mu_o_Pa_s,Bo\n" + OIL_BRANCH_0)
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: заголовок" in msg

    def test_oil_semicolon_raises(self, tmp_path):
        """CSV из Excel в русской локали (; и запятая в числах): до правки 0 строк молча."""
        path = _csv(tmp_path, "oil_pvt.csv",
                    "Rs_sm3_sm3;pressure_Pa;Bo;mu_o_Pa_s\n0,0;5000000;1,05;0,003\n")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: заголовок" in msg
        assert "Разделитель столбцов — запятая" in msg

    def test_oil_empty_file_raises(self, tmp_path):
        """Файл нулевой длины: до правки — StopIteration из next(reader)."""
        path = _csv(tmp_path, "oil_pvt.csv", "")
        msg = _parse_error(_read_oil_pvt_csv, path)
        assert "oil_pvt.csv: файл пуст" in msg

    def test_oil_bom_spaces_and_blank_rows_accepted(self, tmp_path):
        """Допустимо: BOM, пробелы вокруг имён столбцов, строка из пробелов, строка из пустых полей.

        Результат — как у той же таблицы без этих особенностей. Тест зелёный
        и до правки: он защищает от избыточной строгости.
        """
        text = ("﻿Rs_sm3_sm3, pressure_Pa, Bo, mu_o_Pa_s\n"
                "0.0,5000000,1.05,0.003\n"
                "   \n"                        # строка из пробелов
                ",,,\n"                        # пустые ячейки — хвост экспорта из Excel
                "0.0,30000000,1.04,0.0032\n")
        rows = _read_oil_pvt_csv(_csv(tmp_path, "oil_pvt.csv", text))
        clean = _read_oil_pvt_csv(_csv(tmp_path, "clean.csv", OIL_HEADER + OIL_BRANCH_0))
        assert rows == clean
        assert len(rows) == 2

    # ── Газ ──

    def test_gas_number_typo_raises(self, tmp_path):
        """Буква O в B_g: до правки узел 15 МПа пропадал, B_g интерполировался через пропуск."""
        path = _csv(tmp_path, "gas_pvt.csv", GAS_HEADER
                    + "5000000,0.020,0.000012\n15000000,0.0O8,0.000014\n30000000,0.004,0.000018\n")
        msg = _parse_error(_read_gas_pvt_csv, path)
        assert "gas_pvt.csv: строка 3, столбец Bg" in msg

    # ── ОФП ──

    def test_relperm_swapped_header_raises(self, tmp_path):
        """Заголовок Sg,krg,kro: до правки ОФП нефти и газа молча менялись местами."""
        path = _csv(tmp_path, "relperm.csv", "Sg,krg,kro\n0.0,0.0,1.0\n0.8,0.8,0.0\n")
        msg = _parse_error(_read_relperm_csv, path)
        assert "relperm.csv: заголовок" in msg

    def test_relperm_error_in_kro_raises(self, tmp_path):
        """Ошибка во 2-м столбце: до правки Sg дописывался, kro — нет, длины (3, 2, 2)."""
        path = _csv(tmp_path, "relperm.csv",
                    RP_HEADER + "0.0,1.0,0.0\n0.4,0.3x,0.2\n0.8,0.0,0.8\n")
        msg = _parse_error(_read_relperm_csv, path)
        assert "relperm.csv: строка 3, столбец kro" in msg

    def test_relperm_error_in_krg_raises(self, tmp_path):
        """Ошибка в 3-м столбце: до правки длины (3, 3, 2)."""
        path = _csv(tmp_path, "relperm.csv",
                    RP_HEADER + "0.0,1.0,0.0\n0.4,0.3,0.2x\n0.8,0.0,0.8\n")
        msg = _parse_error(_read_relperm_csv, path)
        assert "relperm.csv: строка 3, столбец krg" in msg

    def test_relperm_bad_row_fails_in_from_config(self, tmp_path):
        """Ошибка ОФП ловится в from_config с именем файла, а не при счёте.

        До правки from_config проходил, а run падал на первом вычислении
        ОФП: «ValueError: fp and xp are not of the same length» из np.interp.
        Таблица — configs/table_pvt/relperm.csv с опечаткой в kro строки 6.
        """
        for name in ("oil_pvt.csv", "gas_pvt.csv"):
            shutil.copy(TABLE_CONFIG.parent / name, tmp_path / name)
        _csv(tmp_path, "relperm.csv", RP_HEADER
             + "0.0,1.0,0.0\n0.1,0.8,0.01\n0.2,0.6,0.05\n"
               "0.4,0.3,0.2\n0.6,0.1x,0.5\n0.8,0.0,0.8\n")
        config = load_config(TABLE_CONFIG)
        config.config_dir = tmp_path
        with pytest.raises(ValueError, match="relperm.csv: строка 6, столбец kro"):
            SimulatorFactory.from_config(config)
```

3. Прогнать новый класс:
   ```powershell
   & $py -m pytest tests/test_factory_prototype.py -q -k TestCSVStrictParsing
   ```
   Ожидание: **15 failed, 1 passed** (`test_oil_bom_spaces_and_blank_rows_accepted`). `test_oil_empty_file_raises` падает с `StopIteration`, остальные 14 — `Failed: DID NOT RAISE`.

**Проверка:**
- `& $py -m pytest tests/test_factory_prototype.py -q` — 15 failed, 38 passed (37 прежних + 1 новый зелёный). Эталон поведения каждого теста до правки — раздел «до_правки» в `$pr\plan_check.out.txt`.
- Регресс: только файл шага (пункт выше). Шаг меняет один файл тестов и ничего не импортирует заново, а быстрый уровень дал бы те же 15 ожидаемых падений. Быстрый уровень — после шага 3.
- ⚠️ **Не коммитить и не «чинить».** Падения 15 тестов здесь ожидаемы, это не случай п. 6 `/implement` («Если тест падает… исправь код»). Код меняет шаг 3, коммит тестов — вместе с ним.

**Подводные камни:** `shutil`, `load_config`, `SimulatorFactory`, `TABLE_CONFIG`, `_read_*_csv` уже импортированы/определены в файле (строки 14, 20-24, 31). Новых импортов не нужно.

**Зависимости:** требует шаг 1, блокирует шаг 3.

**Оценка:** ~185 строк тестов, ~15 мин.

### Шаг 3: Общий разборщик и три ридера-обёртки

**Цель:** правила разбора в `_read_numeric_csv`, ридеры — обёртки. Все 16 тестов шага 2 зелёные.

**Файлы:** `numerical_solver/gpn_multiphase_solver/factory.py` (строки 425-501 на `1e09b14`, раздел `# ── CSV-ридеры ──`; после влития BUG-020 — 429-505)

**Контекст:** см. «Контекст для читателя» и решения 1–7. Сигнатуры ридеров и сообщение «Файл {вид} не найден: {путь}» сохраняются: на них опираются `TestCSVReaders` и места вызова. Перевод единиц — то же одно деление на `BAR_TO_PA`, `CP_TO_PA_S`, что и сейчас: так результат побитово прежний.

**Что сделать:** заменить блок от строки `# ── CSV-ридеры ──────…` до `    return Sg, kro, krg` включительно (конец `_read_relperm_csv`) на код ниже. Границы искать по тексту, не по номерам: номера сдвигаются от параллельных веток (BUG-020: +4 строки выше блока). Две пустые строки перед `def _create_schedule` и всё после неё не трогать.

**До** (`factory.py:425-501`) — три ридера целиком. Перед заменой прочитай блок: нефть — см. «Контекст для читателя», газ (`:454-477`) и ОФП (`:480-501`) устроены так же. У ОФП `Sg.append`, `kro.append`, `krg.append` идут по одному внутри `try`.

**После:**

```python
# ── CSV-ридеры ──────────────────────────────────────────────

# Столбцы CSV-таблиц в порядке чтения. Значения берутся по позиции, поэтому
# заголовок файла обязан совпасть с этим списком (DEBT-042).
_OIL_PVT_COLUMNS = ["Rs_sm3_sm3", "pressure_Pa", "Bo", "mu_o_Pa_s"]
_GAS_PVT_COLUMNS = ["pressure_Pa", "Bg", "mu_g_Pa_s"]
_RELPERM_COLUMNS = ["Sg", "kro", "krg"]


def _read_numeric_csv(csv_path: Path, columns: list[str], kind: str) -> list[tuple]:
    """Строки числовой CSV-таблицы в единицах файла; ошибка в строке → ValueError (DEBT-042)."""
    # До DEBT-042 ошибочная строка пропускалась молча, лишние поля
    # отбрасывались: опечатка удаляла строку таблицы, десятичная запятая
    # сдвигала значения на столбец, у ОФП столбцы расходились по длине.
    # Правила:
    #   - заголовок совпадает с columns (пробелы вокруг имён допустимы):
    #     без проверки файл без заголовка терял первую строку данных;
    #   - пустая строка (нет полей или все поля пустые) пропускается;
    #   - в остальных строках полей ровно len(columns), каждое — конечное
    #     число (float() принимает nan и inf, их отсекает np.isfinite).
    # Число строк и допустимость значений здесь не проверяются. Часть из них
    # делают _check_pvto_branches (нефть) и конструкторы прототипа (газ, ОФП);
    # B_g > 0, mu_g > 0, S_g в [0, 1] не проверяет никто — DEBT-044.
    if not csv_path.exists():
        raise ValueError(f"Файл {kind} не найден: {csv_path}")
    name = csv_path.name
    expected = ",".join(columns)
    rows = []
    # utf-8-sig: BOM (его пишут Excel и «Блокнот») не попадает в имя первого
    # столбца; newline="" — режим open, который требует модуль csv
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"{name}: файл пуст, нужен заголовок {expected}.")
        if [h.strip() for h in header] != columns:
            raise ValueError(
                f"{name}: заголовок {','.join(header)!r}, ожидается {expected!r}. "
                f"Столбцы читаются по порядку, поэтому заголовок обязателен. "
                f"Разделитель столбцов — запятая, десятичный разделитель — точка.")
        for line in reader:
            if not any(field.strip() for field in line):
                continue
            # reader.line_num — номер строки файла (заголовок — строка 1)
            where = f"{name}: строка {reader.line_num}"
            if len(line) != len(columns):
                raise ValueError(
                    f"{where}: число полей {len(line)}, а столбцов в заголовке "
                    f"{len(columns)} ({','.join(line)!r}). Частые причины: десятичная "
                    f"запятая (1,20 вместо 1.20), запятая в конце строки, "
                    f"пропущенное значение.")
            values = []
            for col, field in zip(columns, line):
                try:
                    value = float(field)
                except ValueError:
                    raise ValueError(f"{where}, столбец {col}: {field!r} не число.") from None
                if not np.isfinite(value):
                    raise ValueError(f"{where}, столбец {col}: {field!r} — не конечное число.")
                values.append(value)
            rows.append(tuple(values))
    return rows


def _read_oil_pvt_csv(csv_path: Path) -> list[tuple]:
    """Прочитать oil_pvt.csv (SI) → [(Rs, p_bar, Bo, mu_cP), ...].

    CSV: Rs_sm3_sm3, pressure_Pa, Bo, mu_o_Pa_s.
    Конвертация: p Па→бар, μ Па·с→сП.
    """
    rows = _read_numeric_csv(csv_path, _OIL_PVT_COLUMNS, "oil PVT")
    return [(Rs, p / BAR_TO_PA, Bo, mu / CP_TO_PA_S) for Rs, p, Bo, mu in rows]


def _read_gas_pvt_csv(csv_path: Path) -> list[tuple]:
    """Прочитать gas_pvt.csv (SI) → [(p_bar, Bg, mu_cP), ...].

    CSV: pressure_Pa, Bg, mu_g_Pa_s.
    Конвертация: p Па→бар, μ Па·с→сП.
    """
    rows = _read_numeric_csv(csv_path, _GAS_PVT_COLUMNS, "gas PVT")
    return [(p / BAR_TO_PA, Bg, mu / CP_TO_PA_S) for p, Bg, mu in rows]


def _read_relperm_csv(csv_path: Path) -> tuple[list, list, list]:
    """Прочитать relperm.csv → (Sg, kro, krg).

    CSV: Sg, kro, krg. Безразмерные, конвертация не нужна.
    """
    rows = _read_numeric_csv(csv_path, _RELPERM_COLUMNS, "relperm")
    # Столбцы собираются из целых строк: строку с ошибкой разборщик
    # отвергает до записи, поэтому длины Sg, kro, krg совпадают.
    # Не zip(*rows): на таблице из одного заголовка (rows = []) распаковка
    # падает ValueError без имени файла; так — три пустых списка, и отказ
    # даёт TabulatedRelPerm, как до DEBT-042
    Sg = [r[0] for r in rows]
    kro = [r[1] for r in rows]
    krg = [r[2] for r in rows]
    return Sg, kro, krg
```

Пояснения для читателя-новичка в Python:
- `next(reader, None)` — первая строка файла или `None`, если файл пуст. Без второго аргумента `next` бросает `StopIteration`: это и было поведение до правки.
- `any(field.strip() for field in line)` — истина, если хоть одно поле непустое после удаления пробелов.
- `raise ... from None` — в сообщении не будет второго, внутреннего исключения `float()`.
- `[(Rs, p / BAR_TO_PA, ...) for Rs, p, Bo, mu in rows]` — списковое выражение: каждая строка-кортеж раскладывается на четыре имени, и собирается новый кортеж.

**Проверка:**
- `& $py -m pytest tests/test_factory_prototype.py -q` — 53 passed (37 + 16).
- Регресс: быстрый — 1087 passed (1071 + 16).

**Коммит** (первый коммит кода задачи — тесты шага 2 и реализация вместе, см. «Промежуточные состояния»): `feat: строгий разбор CSV-таблиц фабрики — заголовок по именам, число полей, конечные числа, ValueError с файлом и строкой; 16 тестов (DEBT-042)`. Stage по именам: `numerical_solver/gpn_multiphase_solver/factory.py`, `numerical_solver/tests/test_factory_prototype.py`.

**Подводные камни:**
- Не трогать `_check_pvto_branches` и места вызова (`:123-127`, `:318-321`).
- Сообщение пустого файла «файл пуст», заголовка — «заголовок … Разделитель столбцов — запятая», числа полей — «число полей N, а столбцов в заголовке M», значения — «строка N, столбец X». Тесты шага 2 проверяют именно эти фрагменты: при правке текста менять и тесты.
- Если какой-то тест `TestPVTOBranches` упал — значит, таблица теста нарушает правило разбора. По плану таких нет (все с `OIL_HEADER`, корректные строки). Разобрать, не ослаблять правило молча.

**Зависимости:** требует шаг 2, блокирует шаги 4–7.

**Оценка:** ~95 строк вместо ~77, ~15 мин.

### Шаг 4: Побитовая сверка разбора 47 таблиц проекта

**Цель:** убедиться, что корректные таблицы разбираются в те же значения, что до правки.

**Файлы:** нет (проба читает `tables_snapshot.json` шага 1).

**Что сделать** (из `.worktrees\debt-042\numerical_solver`):
```powershell
& $py "$pr\tables_check.py" --compare
```
Ожидание: `Код: …\.worktrees\debt-042\…\factory.py`, «Таблиц: 47 …», «Сверка со снимком: побитово совпадает», код выхода 0.

⚠️ **Сначала строка `Код:`.** Если путь ведёт в основной каталог (`D:\…\Oil_Gas\numerical_solver\…`), сверка проверила неизменённый код и «совпадает» ничего не значит. До аудита пробы брали путь от своего расположения (`vault/issues/` основного каталога) и в worktree давали именно такой ложный результат. ⚠️ Флаг `--compare` обязателен: без него проба перезапишет снимок.

Сравнение побитовое: снимок хранит `float` через `repr` в JSON, а `json` читает их обратно точно. Сравнивается выход ридеров (бар, сП), а не сырые числа файла.

**Проверка:** вывод пробы, как выше. Если «РАСХОЖДЕНИЯ» — стоп: разобрать, какая таблица и почему. Ожидаемая причина — порядок операций при переводе единиц. Регресс: не нужен, шаг не меняет файлов. Коммита нет.

**Зависимости:** требует шаг 1 (снимок `tables_snapshot.json`, снятый до правки кода) и шаг 3.

**Оценка:** 0 строк, ~1 мин.

### Шаг 5: Документация формата CSV

**Цель:** правила разбора записаны там, где ищут формат таблиц.

**Файлы** (оба отслеживаются git — правка в worktree, в ветке задачи; P8 — отдельным vault-коммитом, правило CLAUDE.md «Vault-изменения — отдельным коммитом от кода»):
- `vault/knowledge/decisions/P8-формат-ввода-json.md` (раздел 2, строка 75)
- `numerical_solver/examples/04_table_table/README.md` (строки 41-46)

**Что сделать:**
1. `P8-формат-ввода-json.md`: после строки 75 («CSV и JSON — в одной папке. Factory ищет CSV относительно расположения JSON.») добавить абзац:
   ```markdown

   Правила разбора — общие для трёх таблиц (`_read_numeric_csv`, DEBT-042). Первая строка — заголовок, имена столбцов точно как в образцах ниже, в том же порядке (пробелы вокруг имён допустимы, BOM допустим). Разделитель столбцов — запятая, десятичный разделитель — точка. В каждой непустой строке столько же полей, сколько столбцов в заголовке (запятая в конце строки — лишнее поле), каждое поле — конечное число (`nan`, `inf` — ошибка). Пустые строки и строки из пустых полей (`,,,`) пропускаются. Строк-комментариев нет: строка `# …` или с пояснением текстом — ошибка (до DEBT-042 такие строки молча пропускались). Нарушение — `ValueError` фабрики с именем файла, номером строки и столбцом.
   ```
2. `examples/04_table_table/README.md`: после таблицы столбцов (строка 45, `| relperm.csv | ...`) и пустой строки 46 вставить перед строкой 47 («`oil_pvt.csv` — таблица PVTO: …»):
   ```markdown
   Заголовок — ровно эти имена через запятую, в этом порядке. Десятичный
   разделитель — точка. В каждой строке столько же чисел, сколько столбцов.
   Иначе расчёт не начнётся: фабрика назовёт файл, строку и столбец.

   ```
   README 04 тестами не читается: grep `README` в `tests/` даёт `test_examples.py`, `test_pvt_consistency.py`, `test_prototype_activation_cap.py`, и ни один не читает README 04 (проверено при планировании DEBT-038).

**Проверка:** `--collect-only -q` → 1323 (меняются только документы).

**Зависимости:** требует шаг 3 (текст ссылается на функцию).

**Оценка:** ~8 строк текста, ~5 мин.

### Шаг 6: Верификация — полный прогон

**Цель:** все тесты зелёные, табличные примеры строятся через новый разборщик.

**Что сделать** (из `.worktrees\debt-042\numerical_solver`):
```powershell
& $py -m pytest tests/ -q
```
Ожидание: **1323 passed** (или база + 16). Тесты примеров (`results`, метка `slow`) строят все табличные примеры через `from_config`, то есть через новый разборщик. Шаг 4 уже показал, что разбор побитово прежний, поэтому результаты примеров не меняются. Отдельный тест-перебор таблиц примеров не добавляется: примеры самостоятельны, а их тесты проходят фабрику.

**Зависимости:** требует шаги 3–5.

**Оценка:** 0 строк, ~10 мин.

### Шаг 7: Vault и issue

**Цель:** закрыть запись и оставить результат в issue.

**Файлы** — все в **основном каталоге** `D:\Lessons\Grants\2026\GPN\Oil_Gas` (по абсолютному пути, не в worktree). Реестр, `index.md` и план там не закоммичены, `vault/issues/` в `.gitignore` — в worktree их нет или они устарели:
- `vault/roadmap/известные баги и технический долг.md` (запись DEBT-042)
- `vault/issues/debt-042/05-comment-done.md` (новый)
- `vault/00-home/index.md` (строка плана)
- `vault/plans/debt-042 strict-csv-readers.md` (`status`)

**Что сделать:**
1. DEBT-042: поле «Результат» — функция, 3 константы, ридеры-обёртки, 16 тестов, число тестов было/стало, сверка 47 таблиц «побитово совпадает» (со строкой `Код:` пути worktree), полный прогон. Статус — `✅ ГОТОВО (дата)`.
2. Комментарий в #72 (из основного каталога): `gh issue comment 72 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-042/05-comment-done.md`.
3. Строка в `index.md` — отметить «реализовано», `status` плана — `реализован`.

**Проверка:** `--collect-only -q`.

**Зависимости:** требует шаг 6.

**Оценка:** ~15 строк текста, ~10 мин.

## Тестовая стратегия

Новые тесты — класс `TestCSVStrictParsing` в `numerical_solver/tests/test_factory_prototype.py`, раздел H. Пятнадцать вызывают ридеры напрямую, один (`test_relperm_bad_row_fails_in_from_config`) идёт через `SimulatorFactory.from_config`.

| Тест | Сценарий | Ожидание (фрагмент сообщения) | До правки (проба) | Предотвращает |
|---|---|---|---|---|
| `test_oil_number_typo_raises` | `15OOOOOO` в давлении, строка 4 | «oil_pvt.csv: строка 4, столбец pressure_Pa», «15OOOOOO» | строка пропала | молчаливая потеря строки PVTO |
| `test_oil_decimal_comma_raises` | `1,20` | «строка 4: число полей 5, а столбцов в заголовке 4» | $\mu_o$ = 20000 сП | сдвиг значений на столбец |
| `test_oil_short_row_raises` | 3 поля | «число полей 3, а столбцов в заголовке 4» | строка пропала | потеря строки |
| `test_oil_trailing_comma_raises` | `...,0.0015,` | «строка 4: число полей 5» | поле отброшено | решение пользователя 3 |
| `test_oil_nan_raises` | `nan` в давлении | «строка 4, столбец pressure_Pa», «не конечное число» | принят | NaN мимо проверок DEBT-038 |
| `test_oil_inf_raises` | `inf` в $B_o$ | «строка 4, столбец Bo», «не конечное число» | принят | бесконечные свойства |
| `test_oil_no_header_raises` | нет заголовка | «oil_pvt.csv: заголовок», ожидаемый заголовок назван | первая строка данных потеряна | потеря $p_b$ первой ветви |
| `test_oil_swapped_header_raises` | `...,mu_o_Pa_s,Bo` | «oil_pvt.csv: заголовок» | принят по позиции | перестановка $B_o$ и $\mu_o$ |
| `test_oil_semicolon_raises` | `;` и `,` (Excel RU) | «заголовок», «Разделитель столбцов — запятая» | 0 строк без сообщения | непонятный отказ ниже по цепочке |
| `test_oil_empty_file_raises` | 0 байт | «oil_pvt.csv: файл пуст» | `StopIteration` | непонятное исключение |
| `test_oil_bom_spaces_and_blank_rows_accepted` | BOM, пробелы в заголовке, `   `, `,,,` | как чистая таблица, 2 строки | проходит | избыточная строгость |
| `test_gas_number_typo_raises` | `0.0O8` в $B_g$, строка 3 | «gas_pvt.csv: строка 3, столбец Bg» | узел пропал | потеря узла газовой таблицы |
| `test_relperm_swapped_header_raises` | `Sg,krg,kro` | «relperm.csv: заголовок» | принят по позиции | перестановка фаз в ОФП |
| `test_relperm_error_in_kro_raises` | `0.3x`, строка 3 | «relperm.csv: строка 3, столбец kro» | длины (3, 2, 2) | рассинхрон столбцов |
| `test_relperm_error_in_krg_raises` | `0.2x`, строка 3 | «relperm.csv: строка 3, столбец krg» | длины (3, 3, 2) | рассинхрон столбцов |
| `test_relperm_bad_row_fails_in_from_config` | `0.1x` в `kro`, строка 6, через фабрику | `ValueError` «relperm.csv: строка 6, столбец kro» в `from_config` | `from_config` проходит, `run` падает в `np.interp` | отказ во время счёта без имени файла |

**Неизменность поведения:**
- `TestCSVReaders` (7 тестов, формат и единицы, пустые строки, отсутствующий файл) — без правок.
- `TestFactoryTablePVT`, `TestPipeline`, `TestPVTConsistency`, `TestConfigErrors`, `TestInitialStateVsTable`, `TestInitialRangeWarnings`, `TestPVTOBranches` (тот же файл).
- `tests/test_pvt_consistency.py` (BUG-019, табличные случаи).
- Проба `tables_check.py --compare` — 47 таблиц побитово (шаг 4).
- Тесты примеров (полный прогон) — все табличные примеры через фабрику.

## Критерии завершения

- [ ] `_read_numeric_csv` и константы столбцов в `factory.py`, три ридера — обёртки; сигнатуры прежние
- [ ] 16 тестов `TestCSVStrictParsing` зелёные; до реализации было 15 красных и 1 зелёный (шаг 2)
- [ ] `tables_check.py --compare` — «побитово совпадает» (шаг 4)
- [ ] Быстрый уровень: база + 16 (1087 при базе 1071), все зелёные; полный прогон: база + 16 (1323 при базе 1307), все зелёные
- [ ] Код прототипа не изменён: `git diff --stat numerical_scheme/implementation -- numerical_solver/HydroSolverPrototype` пуст
- [ ] Документация: P8 (правила разбора), README 04
- [ ] Vault: запись DEBT-042 «Результат» и статус, план `status: реализован`, index.md
- [ ] Комментарий в #72 (`05-comment-done.md`); issue закрывается при влитии

## Обнаруженные проблемы

1. **Проверки значений CSV-пути слабее XLSX-ридера** → зарегистрирована **DEBT-044** (решение пользователя 1). XLSX-ридер прототипа проверяет $B_g > 0$, $\mu_g > 0$ (`input_reader.py:73`) и $S_g \in [0, 1]$ (`:81`). На CSV-пути этих проверок нет ни в фабрике, ни в конструкторах прототипа. Монотонность давления газа (`pvt.py:32`), монотонность $S_g$ и $k_r \ge 0$ (`relperm.py:5-6`) конструкторы проверяют, но без имени файла. $B_o > 0$ и $\mu_o > 0$ не проверяет ни один путь. Не блокирует DEBT-042.
2. **Таблица газа или ОФП из одного заголовка** (без строк данных) по-прежнему даёт исключение прототипа без имени файла: `GAS_PVT pressure must be strictly increasing with >=2 rows`, `RELPERM Sg must be strictly increasing with >=2 rows`. Это проверка числа строк, а не разбора (решение 5). Отнесено к DEBT-044.
3. **В записи реестра DEBT-042 устарели номера строк** (`factory.py:371-445` → `427-501` после DEBT-038). Исправлено полем **GitHub:** при `/issue`. Отдельной записи не требует.

## Оценка

Файлов: 1 кода, 1 теста, 2 документации, 4 vault. Строк: ~95 кода (вместо ~77), ~185 тестов, ~8 текста. Время: ~60 мин, из них ~10 — полный прогон. Сложность — простая.

## Связанные заметки

- [[известные баги и технический долг]] — DEBT-042, DEBT-044, DEBT-038, BUG-017, BUG-019
- [[debt-038 pvto-branch-checks]] — проверка ветвей PVTO (`_check_pvto_branches`), где обнаружен DEBT-042
- [[P8-формат-ввода-json]] — формат CSV-таблиц
- [[json-config-schema]] — схема конфига (`pvt.model`, `relperm.model = "table"`)
