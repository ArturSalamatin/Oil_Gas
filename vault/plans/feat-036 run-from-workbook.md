---
tags:
  - план
  - инфраструктура
date: 2026-10-18
issue: FEAT-036
github: 136
branch: feat/feat-036/run-from-workbook
model_level: null
status: реализован
worktree: .worktrees/feat-036
audit:
  date: 2026-10-18
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# FEAT-036: расчёт по книге — `gpn-solver run книга.xlsx`

**GitHub issue:** [#136](https://github.com/ArturSalamatin/Oil_Gas/issues/136) — найденное при открытии (2026-10-18, `b9454a6`) — в теле issue, `vault/issues/feat-036/01-issue-body.md`.

Цепочка: [[feat-033 workbook-input-format|FEAT-033]] (формат; влит `7036854`) → [[feat-034 xlsx-cell-reader|FEAT-034]] (разбор; влит `25b7eee`) → [[feat-035 workbook-to-config|FEAT-035]] (перевод; влит `86348ed`) → **FEAT-036** → FEAT-031 (поставка). [[FEAT-037]] (номер версии, `CHANGELOG.md`, `versions.txt`) влита `5ea30e7` — план стоит поверх неё.

## Как начать работу по этому плану

1. Прочитай этот файл целиком. Новых формул нет; `problem_statement.tex` и `moments_method.tex` не нужны.
2. **Код плана проверен на копии дерева** — `vault/issues/feat-036/probes/plan_code/`:
   - `edits.py` — правки существующих файлов: словарь `{путь от numerical_solver/: [(было, стало), …]}`; каждое «было» — ровно одно вхождение в файле базы. **Источник правок шагов 1–4 — этот файл**: переносить парами `old_string` → `new_string` (Edit), не пересказом;
   - `test_workbook_run.py` — новый файл тестов (как есть);
   - `test_cli_block.py`, `test_examples_block.py` — блоки в конец `tests/test_cli.py` и `tests/test_examples.py`;
   - `example_22/main.py`, `example_22/README.md` — файлы примера 22, как есть (README — итоговый, числа из пробы).
   Проверка — `probes/plan_apply.py`, вывод — `probes/plan_apply.out.txt`, печать примера 22 — `probes/example22.out.txt`, числа README — `probes/plan_apply_extra.out.txt` (§11). Правки применять на `/implement` Edit-ом по парам; `plan_apply.py` — только проба, в worktree не запускать (он строит свою копию из `git archive`).
3. Прочитай заметку [[перевод книги в конфиг проверяет только книгу — моменты SCHEDULE в целых мс]] (контракт перевода) и §0 ниже — решения пользователя 12–15 меняют порядок черновика.
4. Worktree и ветка — `/implement` (база `numerical_scheme/implementation`, ветка `feat/feat-036/run-from-workbook`; на 2026-10-18 её нет ни локально, ни на origin).
5. Обозначения — как в `/implement`: `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas`; `<W>` = `<КОРЕНЬ>\.worktrees\feat-036`; `<PY>` = `<КОРЕНЬ>\numerical_solver\.venv\Scripts\python.exe` — venv один, в основном каталоге: **в worktree своего `.venv` нет**. pytest из `<W>\numerical_solver` берёт пакет и прототип worktree.
6. Baseline (из `<W>\numerical_solver`): `<PY> -m pytest tests/ --collect-only -q` — **2421 тест на `ee2be23`** (после влития [[DEBT-081]]); `<PY> -m pytest tests/ -m "not slow" -q` — быстрый уровень, на базе 2145 тестов. Прототип не меняется: его тесты и регрессия не нужны. База могла уйти дальше — число сверить при baseline, ожидания сдвинуть на разницу (задача добавляет 40 тестов: 32 быстрых, 8 `slow`).
   **Команды — только из `<W>\numerical_solver`** и только `<PY> -m gpn_multiphase_solver …` или `<PY> examples\…\main.py` с `PYTHONPATH` на worktree (память «Worktree и PYTHONPATH»): каталог запуска стоит первым в `sys.path` у `-m`, а скрипт примера без `PYTHONPATH` возьмёт пакет основного каталога (редактируемая установка). Консольной команды `gpn-solver` в `.venv` основного каталога нет — в шагах она не используется.
7. **Докстринги** (CLAUDE.md, «Файлы и код»): `_translate_workbook` — внутренняя, одна строка. `run_case` — публичный интерфейс (README §4), докстринг дополняется абзацем о книге; перевод в стиль NumPy — FEAT-031, не эта задача.
8. Начни с шага 1. После каждого шага — проверка по полю «Регресс»; полный прогон — в конце (`/implement` §3.1). Если база ушла от `ee2be23` — сначала `<PY> <КОРЕНЬ>\vault\issues\feat-036\probes\audit_anchors.py` (из `<КОРЕНЬ>`): каждое «было» `edits.py` должно найтись ровно один раз в HEAD.

**Аудит 1 (2026-10-18, `ee2be23`):** 🟡 4, 🔵 5, исправлены все; код плана перепроверен на копии (§11). Главное: файл каталога вывода, открытый в другой программе (CSV в Excel), ломает очистку — у книги теперь отказ с подсказкой до расчёта (умолчание 29), у конфига — [[DEBT-082]]; добавлен тест очистки у конфига (правка 1.11 меняет именно эту строку, а тестов на неё не было); `CaseRunError`, README §3.4 и заметка решений FEAT-030 больше не обещают «прежние результаты целы» для книги.

## 0. Решения пользователя

Записаны в черновике 2026-10-14…18 (1–11), приняты при планировании 2026-10-18 (12–15), умолчания плана — предложены здесь, «если не возразите» (16–28; 29 — добавлено аудитом 1).

1. **Одна книга — один расчёт** (2026-10-14).
2. **Результаты выводятся так же, как сейчас** (2026-10-14) — штатный набор [[feat-030 run-command-from-config|FEAT-030]] (с [[FEAT-037]] — и `versions.txt`).
3. **Вход расчёта сохраняется** (2026-10-14): переведённые `config.json` и CSV — в `output/input/`; расчёт воспроизводится командой по ним.
4. **Защита книги от очистки каталога вывода** (2026-10-14): книга внутри каталога вывода — отказ.
5. **Книга — часть поставки**, FEAT-031 ждёт цепочку (2026-10-14). Инструкция инженера — в комплект.
6. **Файл `~$имя.xlsx`** рядом с открытой книгой команде на один файл не мешает (2026-10-14).
7. **Отдельный демонстрационный пример** (2026-10-15); значения книги подбираем сами ([[feat-033 workbook-input-format|FEAT-033]], решение 7); точно повторять существующий пример не нужно, тестов на совпадение примеров нет; книга примера — своя, в папке примера, без теста на равенство с книгой генератора и без ссылки на `configs/` (§0.1 черновика).
8. **Листа OUTPUT в книге нет** (FEAT-033 решение 44): параметры вывода — умолчания конфига, заголовок — имя книги без расширения; флаги `--title`, `--profiles` действуют и для книги.
9. **Инструкция инженера — в README пакета** (`numerical_solver/README.md`): все три команды — `template`, `convert`, `run книга.xlsx`; ошибки книги — код 2.
10. **Книга и её значения — на английском, сообщения — русские** (FEAT-033 решение 34).
11. **Строка «Run» листа COMMENTS — в этой задаче** (FEAT-033 решение 62), после «Template»; `test_comments_sheet` её проверяет.

**Приняты при планировании (2026-10-18, ответы на вопросы плана):**

12. **Каталог вывода у книги очищается до перевода** (вариант Г из issue). Решение FEAT-030 «очистка после расчёта» (2026-10-13) для расчёта по книге **отменено**: при ошибке конфига или отказе решателя прежних результатов нет. Взамен в каталоге остаётся `input/` — вход, на котором расчёт остановился: `input/` и результаты всегда от одного запуска. Расчёт по JSON-конфигу не меняется.
13. **Книгу принимает `run_case`**: вход по расширению; команда и скрипты на Python (README §4) получают одно и то же. Командная строка меняется только в справке и в подписи ошибки.
14. **Пример 22 — в общем списке `ALL_EXAMPLES`** `tests/test_examples.py`: тестам книга переводится во временный каталог (`_config_path`); идут все общие проверки (балансы энергии $10^{-12}$ и массы $10^{-6}$, границы $p$, $T$, $S_g$, $R_s$, разделы README). Исключения с причиной — §6, шаг 4.
15. **Книга примера — `22_workbook_input.xlsx`**: заголовок рисунков «22_workbook_input».

**Умолчания плана (если не возразите):**

16. **Ошибки книги каталог вывода не трогают.** Перевод — в памяти (`workbook_to_config(read_workbook(книга))`), до очистки; очистка, затем запись перевода (`write_files`). Это уточняет решение 12: «очистка до перевода» — до **записи** перевода. Отказ разбора или ячеек (код 2) оставляет прошлые результаты; после очистки отказать могут только проверки конфига и таблиц (`load_config`, фабрика) и решатель.
17. **Расширения книги** — `.xlsx`, `.xlsm`, `.xls`, `.xlsb` без учёта регистра (`EXCEL_SUFFIXES`): `.xlsm` разбор читает так же, `.xls` и `.xlsb` отвергает с подсказкой пересохранить — понятнее, чем «Expecting value» загрузчика JSON. Прочие расширения — JSON, как сейчас (конфиг `case.cfg` по-прежнему считается).
18. **Печать и сообщения называют книгу:** вторая строка печати — «Книга: <путь>» вместо «Конфиг: …»; отказ `load_config` и фабрики по переводу — с путём книги (`<книга>: Rs0 = 70 …`); ключ строки книги равен пути поля JSON (FEAT-035), поэтому ошибку находят в книге. Командная строка: при входе-книге любая ошибка с кодом 2 — «Ошибка книги: …».
19. **Явный `n_profiles` проверяется первым** — до перевода и очистки (раньше — после `load_config`): ошибка аргумента в скрипте не стирает вывод. Для конфига поведение то же, меняется только порядок двух отказов.
20. **Книга внутри каталога вывода** — `CaseConfigError` «каталог вывода … содержит книгу …» до чтения книги, код 2; проверка — как `_check_inputs_outside` (сама книга или предок).
21. **Нет книги** — «<путь>: книга не найдена»; прочие `OSError` чтения и записи — путь и причина (`strerror`). Все — `CaseConfigError`, код 2.
22. **Перевод в публичный интерфейс не входит** (открытый вопрос 9 FEAT-035, решение 27 FEAT-035): книга доступна из Python через `run_case`; `convert_workbook`, `workbook_to_config` остаются внутренними, `tests/test_public_api.py` не меняется. README §4 — одна фраза.
23. **Книга примера 22 — шаблон генератора**: `gpn-solver template` с демонстрационными значениями FEAT-033 (сценарий черновика §0.1: $k$ = 1 мД, $R_e$ = 100 м, $p_0$ = 200 бар, $R_{s,0}$ = 50, $p_{wf}$ 150 → 120 → 100 бар, 30 сут, $N$ = 100, ветвь $R_s$ = 60, $h_0$ = 0.11 с, $\rho_{ma}$ = 2650 кг/м³, $c_{ma}$ = 820 Дж/(кг·К), $T_0$ = 350 К, $L$ = 230 кДж/кг). Пересоздаётся той же командой.
24. **`configs/INPUT_TEMPLATE_v1.xlsx` пересоздаётся** (удалить файл — решение 58 FEAT-033 — и `template`): `TestGeneratorBook` лист COMMENTS не сверяет, без пересоздания книга в `configs/` молча осталась бы без строки «Run».
25. **README пакета — новый §3.6** «Книга ввода Excel» в конце §3; разделы не перенумеровываются (на «README §4» ссылаются CLAUDE.md, `tests/test_public_api.py`, планы).
26. **Тесты расчёта по книге — новый файл `tests/test_workbook_run.py`** на малой книге ($N$ = 20, сутки при 150 бар, ~4 с с рисунками); в `tests/test_cli.py` — справка и коды возврата (без расчёта).
27. **Журнал** `numerical_solver/CHANGELOG.md` («Не выпущено» → «Добавлено») — строка о расчёте по книге.
28. **`examples/README.md`** — пример 22 в таблицах наравне с остальными (сценарий, время, $R_s$, балансы, замкнутое решение — «не строится»), без сравнения с другими примерами (память «Examples independent»).
29. **Файл каталога вывода открыт в другой программе** (аудит 1, 2026-10-18): на Windows `shutil.rmtree` падает `PermissionError` (WinError 32) и успевает удалить часть файлов (проба `vault/issues/feat-036/probes/audit_locked_output.py`). У книги очистка — до расчёта, поэтому `_translate_workbook` ловит `OSError` очистки → `CaseConfigError` «каталог вывода … очищен не полностью — <файл>: <причина>. Файл открыт в другой программе? Закройте его и повторите расчёт.», код 2 вместо трассировки. У расчёта по конфигу тот же отказ — после расчёта, с потерей результатов: зарегистрирован [[DEBT-082]], в этой задаче не правится.

## 1. Сводка

- **Подтип:** инфраструктура (ввод, командная строка). Уровень модели — нет.
- **Суть:** `run_case(вход)` — вход по расширению. Книга: проверка «вне каталога вывода» → перевод в памяти (ошибки книги — до очистки) → очистка каталога вывода → `output/input/`: `config.json` и три CSV → расчёт по `output/input/config.json`, как по любому конфигу, но без второй очистки и без защиты входных файлов. Командная строка: справка, подпись ошибки «Ошибка книги». Строка «Run» на листе COMMENTS. Пример `22_workbook_input`. Документация инженера.
- **Файлы кода:** `numerical_solver/gpn_multiphase_solver/report/pipeline.py` (+~50 строк), `numerical_solver/gpn_multiphase_solver/cli.py` (+~15), `numerical_solver/gpn_multiphase_solver/io/workbook_template.py` (+11), `numerical_solver/examples/check_energy_balance_all.py` (+~15). Перевод (`io/workbook_convert.py`), разбор, загрузчик конфига, фабрика, прототип — не меняются.
- **Тесты:** новый `tests/test_workbook_run.py` (17), `tests/test_cli.py` (+3), `tests/test_workbook_template.py` (две проверки строки «Run» в существующем тесте), `tests/test_examples.py` (пример 22 в `ALL_EXAMPLES`: +17 параметризованных, из них 7 `slow`; +2 в `TestWorkbookInput`), `tests/test_energy_matrix_examples.py` (+1 `slow`). Всего 2421 → 2461 (+40); быстрый уровень 2145 → 2177.
- **Документы:** `numerical_solver/README.md`, `numerical_solver/examples/README.md`, `numerical_solver/examples/22_workbook_input/README.md` (новый), `numerical_solver/CHANGELOG.md`, `CLAUDE.md`.
- **Шагов:** 6.

## 2. Контекст

### 2.1. Как устроен расчёт сейчас (база `ee2be23`)

`run_case` (`numerical_solver/gpn_multiphase_solver/report/pipeline.py`, `run_case`):

1. `load_config(config_path)`; ошибки — `CaseConfigError(f"{config_path}: {exc}")`;
2. `output.title`, `n_profiles` (явный аргумент проверяется здесь, после чтения конфига), `steady_state`;
3. `output_dir` по умолчанию — `config_path.parent / "output"`; `_check_inputs_outside` — отказ, если конфиг или его CSV внутри каталога вывода (FEAT-030);
4. печать «=== заголовок ===», «Конфиг: …», «Версии: …» ([[FEAT-037]]);
5. `SimulatorFactory.from_config` — отказ таблиц → `CaseConfigError(f"{config_path}: …")`;
6. `simulator.run` — отказ → `CaseRunError`, каталог вывода не тронут;
7. **после расчёта** `shutil.rmtree(output_dir)` → `mkdir` → `versions.txt`, CSV, рисунки, печать проверок.

Командная строка (`numerical_solver/gpn_multiphase_solver/cli.py`, `main`): `run_case(args.config.resolve(), output, title=…, n_profiles=…)`; `CaseConfigError` → «Ошибка конфига: …», код 2; `CaseRunError` → код 1; прочее — трассировка.

Перевод (FEAT-035, `numerical_solver/gpn_multiphase_solver/io/workbook_convert.py`): `workbook_to_config(book) -> (config, tables)` — чистая функция без файлов, `write_files(out_dir, config, tables) -> Path` — запись (каталог создаётся), `convert_workbook(книга, каталог)` — обе с проверкой «каталог новый или пустой». Перевод пишет `output.title` = имя книги без расширения. Ошибки: `WorkbookError` (разбор) и подкласс `WorkbookContentError` (ячейки, поле `errors`); сообщение начинается с пути книги.

### 2.2. Почему порядок черновика не работал

Черновик: «очистка → перевод в `output/input/` → `run_case`». Прямой вызов `run_case(output/input/config.json, output/)` отвергает `_check_inputs_outside` (вход внутри каталога вывода), а `rmtree` после расчёта удалил бы `output/input/`. Поэтому книгу обрабатывает сам `run_case` (решение 13): у книги нет второй очистки и нет защиты входных файлов — её заменяет проверка самой книги.

### 2.3. Пример 22 и тесты примеров

`tests/test_examples.py` читает `EXAMPLES_DIR / name / "config.json"` у каждого примера: `_run` (фикстура `results`), `_output`, `TestStructure.test_required_files`, `TestConfigs` (4 теста), `TABLE_PVT` — **при сборке модуля**, на уровне модуля. У примера 22 `config.json` нет. Отсюда `_config_path(name)`: для примеров с книгой — перевод во временный каталог сессии (`tempfile.mkdtemp`, удаление `atexit`), кешируется `functools.cache`; фикстура `tmp_path_factory` не годится — `TABLE_PVT` вычисляется до фикстур. `examples/run_all.py` отбирает папки по `main.py` — пример 22 подхватит без правок; `tests/test_example_scripts.py` разбирает все `*.py` — `main.py` примера проверит.

## 3. Варианты

| Вариант | Суть | Плюсы | Минусы | Итог |
|---|---|---|---|---|
| А. Временный каталог | перевод во временный каталог → расчёт → после успеха копия в `output/input/` | правило FEAT-030 «очистка после расчёта» сохраняется | при отказе (код 1) нового перевода нет; печать и ошибки называли бы временный файл | отклонён (решение 12) |
| В. `run_case` бережёт `input/` | перевод в `output/input/` до расчёта, `input/` вне защиты и вне очистки | без временного каталога | при отказе решателя — старые результаты рядом с новым входом | отклонён |
| **Г. Очистка до перевода** | очистка → перевод → расчёт | `input/` и результаты всегда от одного запуска; при отказе остаётся вход для разбора | при отказе прежних результатов нет | **принят** (решение 12), с уточнением 16 |
| Точка входа: `run_case` | вход по расширению в `run_case` | Python и команда одинаковы; печать и ошибки называют книгу | расширяется публичная функция (совместимо) | **принят** (решение 13) |
| Точка входа: только `cli` | `run_case` не меняется | меньше правок | Python-пользователь книгу не считает; печать «Конфиг: output/input/config.json» | отклонён |
| Тесты 22: общий список | `ALL_EXAMPLES` + `_config_path` | все общие проверки | 17 правок `test_examples.py` | **принят** (решение 14) |
| Тесты 22: свой класс | вне `ALL_EXAMPLES` | проще | без общих проверок балансов и границ | отклонён |

## 4. Подводные камни

- ✅ **Размерности, граничные случаи, устойчивость, ОДУ, PVT** — не касаются: новых вычислений нет; перевод и расчёт — прежние функции.
- ⚠️ **Потеря результатов при отказе** — цена решения 12, записана в README §3.6, на листе COMMENTS и в справке команды («по книге — до него»). Ошибки книги — до очистки (умолчание 16, тест `test_book_error_leaves_output`).
- ⚠️ **Повтор по `output/input/config.json` без `--output`** пишет в `output/input/output/` — внутрь каталога, который следующий расчёт по книге очистит. README §3.6 и строка «Run» советуют `--output`. Отказа не нужно: `_check_inputs_outside` такой вызов пропускает (конфиг не внутри `output/input/output/`), расчёт корректен.
- ⚠️ **Явный `n_profiles`** — до перевода (умолчание 19, тест `test_invalid_profiles_argument_leaves_output`). Остальные отказы аргументов командной строки — у argparse, до `run_case`.
- ✅ **Состояние при ошибке:** до очистки — каталог вывода не тронут; после — в нём `input/` (4 файла) и ничего больше; при ошибке записи перевода (`OSError`) — `CaseConfigError` с путём, часть файлов может остаться (как у `convert`, FEAT-035 §4).
- ⚠️ **Файл каталога вывода открыт в другой программе** (аудит 1): на Windows `rmtree` падает `PermissionError` WinError 32, удалив часть файлов (проба `audit_locked_output.py`: из трёх файлов удалён один). У книги — отказ `CaseConfigError` с подсказкой до расчёта (умолчание 29, тест `test_locked_output_file_refused`); каталог при этом очищен частично — расчёт не начат, повтор после закрытия файла. У конфига — [[DEBT-082]].
- ⚠️ **Докстринг `CaseRunError`** обещал «результаты прошлого прогона не тронуты» — у книги это неверно (решение 12): пара 1.3а `edits.py`.
- ✅ **Import-цепочки:** `report/pipeline.py` импортирует `io.workbook_convert` и `io.xlsx_reader` (стандартная библиотека + `io.config`, `io.workbook_format`) — цикла нет (проба: все тесты собрались). `template` и `convert` конвейер не импортируют — их тесты «без решателя» не меняются.
- ✅ **Производительность:** перевод книги — десятки мс; у примеров по конфигу — без изменений.
- ⚠️ **Сборка `tests/test_examples.py` теперь переводит книгу** (`TABLE_PVT` на уровне модуля): сломанная книга примера 22 роняет сборку всего модуля с трассировкой перевода — сразу видно, но громко. Цена решения 14.
- ✅ **Связь с задачами:** [[FEAT-037]] влита — правки стоят рядом с её строками (`versions`, «Версии: …»), якоря `edits.py` проверены на `30a64f7`, `42ef497` и `ee2be23`. [[DEBT-081]] (`grid.N` целое в `_validate`) влита `f2d77db` во время планирования — `io/config.py`, `tests/test_config.py`; правки этой задачи на её базе применяются без изменений. FEAT-031 ждёт README §3.6.
- ✅ **Прототип** не меняется: тесты и регрессия прототипа не нужны.
- ⚠️ **Книги XlsxWriter в тестах** помечены `fullCalcOnLoad` — формул в них нет, значения ячеек на месте (FEAT-035 §2): перевод их принимает.

## 5. Обратная совместимость

- [x] Конфиги и их расчёт не меняются: путь JSON — тот же код, кроме порядка проверки явного `n_profiles` (решение 19).
- [x] Существующие тесты проходят без изменений, кроме: `test_comments_sheet` (+2 проверки), `tests/test_examples.py` (пример 22 в списках, `_config_path` вместо пути к `config.json` в 6 местах, пропуск книги в `test_output_explicit`), `tests/test_energy_matrix_examples.py` (22 в списке, `_example_config`), докстринг `tests/test_cli.py`.
- [x] Очистка после успешного расчёта по конфигу — прежняя; до аудита её не проверял ни один тест, а правка 1.11 меняет именно эту строку — добавлен `test_config_run_clears_output_after_run` (аудит 1).
- [x] Публичный интерфейс расширяется совместимо: `run_case` принимает книгу; новые имена модуля `EXCEL_SUFFIXES`, `INPUT_DIR`.
- [x] Справка `run`: `metavar` аргумента — «вход»; имя `args.config` прежнее (`test_flags_passed_to_run_case` не меняется).
- [x] Прототип, перевод, загрузчик, фабрика — не меняются.

## 6. Шаги

### Шаг 1: `run_case` принимает книгу

**Цель:** `run_case(книга.xlsx)` переводит книгу в `output/input/` и считает по переводу; порядок — решения 12, 16, 19, 20.
**Файлы:** `numerical_solver/gpn_multiphase_solver/report/pipeline.py`, новый `numerical_solver/tests/test_workbook_run.py`.

**Что сделать:**
1. Правки `edits.py`, ключ `PIPELINE`, 13 пар 1.1–1.12 (с 1.3а) по порядку (Edit, `old_string` → `new_string`):
   - 1.1 — абзац о книге в докстринге модуля;
   - 1.2 — импорт `workbook_to_config`, `write_files`, `WorkbookError`, `read_workbook` после импорта `..io.output`;
   - 1.3 — константы `EXCEL_SUFFIXES`, `INPUT_DIR` перед `CaseConfigError`, докстринг `CaseConfigError` («конфиг или книга»);
   - 1.3а — докстринг `CaseRunError`: у книги в каталоге вывода только `input/` (аудит 1);
   - 1.4 — абзац о книге в докстринге `run_case`;
   - 1.5 — проверка явного `n_profiles` первой; блок «Книга ввода»: `workbook`, `output_dir` по умолчанию рядом с книгой, `config_path = _translate_workbook(...)`, `source`; ошибка `load_config` — с `source`;
   - 1.6 — прежняя ветка `elif` проверки `n_profiles` удаляется (проверка теперь вверху);
   - 1.7 — `_check_inputs_outside` только при `workbook is None`;
   - 1.8 — печать «Книга: …» / «Конфиг: …»;
   - 1.9 — ошибка фабрики — с `source`;
   - 1.10 — комментарий к отказу решателя;
   - 1.11 — очистка после расчёта только при `workbook is None`;
   - 1.12 — новая функция `_translate_workbook` после `_check_inputs_outside`.
2. Скопировать `plan_code/test_workbook_run.py` → `numerical_solver/tests/test_workbook_run.py`.

**Ключевой код (из `edits.py`, для самодостаточности):**

```python
    config_path = Path(config_path)
    t_start = time.perf_counter()
    # Явный аргумент проверяется до всего, что трогает файлы: у книги
    # каталог вывода очищается до расчёта (FEAT-036)
    if n_profiles is not None and (isinstance(n_profiles, bool)
                                   or not isinstance(n_profiles, int) or n_profiles < 2):
        raise ValueError(f"n_profiles = {n_profiles!r}: нужно целое не меньше двух")
    # ── Книга ввода (FEAT-036) ──
    # ...
    workbook = config_path if config_path.suffix.lower() in EXCEL_SUFFIXES else None
    if workbook is not None:
        output_dir = (Path(output_dir) if output_dir is not None
                      else workbook.parent / "output")
        config_path = _translate_workbook(workbook, output_dir)
    source = workbook if workbook is not None else config_path
```

```python
def _translate_workbook(workbook: Path, output_dir: Path) -> Path:
    """Книга → output_dir/input/ (config.json и CSV таблиц), каталог вывода очищается до записи; путь config.json. FEAT-036."""
    out, book = output_dir.resolve(), workbook.resolve()
    if book == out or out in book.parents:
        raise CaseConfigError(f"каталог вывода {out} содержит книгу {book}: ...")
    try:
        config, tables = workbook_to_config(read_workbook(workbook))   # ошибки книги — до очистки
    except WorkbookError as exc:
        raise CaseConfigError(str(exc)) from exc
    except FileNotFoundError as exc:
        raise CaseConfigError(f"{workbook}: книга не найдена") from exc
    except OSError as exc:
        raise CaseConfigError(f"{workbook}: {exc.strerror or exc}") from exc
    if output_dir.is_dir():                                            # решение 12
        try:
            shutil.rmtree(output_dir)
        except OSError as exc:              # файл открыт в другой программе (умолчание 29)
            raise CaseConfigError(f"каталог вывода {output_dir} очищен не полностью — "
                                  f"{exc.filename}: {exc.strerror}. Файл открыт ...") from exc
    try:
        return write_files(output_dir / INPUT_DIR, config, tables)
    except OSError as exc:
        raise CaseConfigError(f"{output_dir / INPUT_DIR}: {exc.strerror or exc}") from exc
```

После расчёта: `if workbook is None and output_dir.is_dir(): shutil.rmtree(output_dir)`, затем `mkdir(exist_ok=True)` — у книги в каталоге остаётся `input/`.

**Проверка после шага:**
- Тест: `<PY> -m pytest tests/test_workbook_run.py -q` — 17 passed (~20 с: расчёт малой книги по `run_case`, по её переводу как по конфигу и в отдельном процессе).
- `<PY> -m pytest tests/test_examples.py -k "pipeline or run_case" -q` — прежние тесты `run_case` по конфигу (отказ при входе в каталоге вывода, прежний вывод цел при отказе решателя).
- Регресс: быстрый.

**Подводные камни:** §4 — потеря результатов, `n_profiles`, состояние при ошибке.
**Зависимости:** блокирует шаги 2, 4.
**Оценка:** ~70 строк кода, ~250 строк тестов (готовы), ~20 мин.

### Шаг 2: командная строка

**Цель:** `gpn-solver run книга.xlsx` — справка о книге, «Ошибка книги: …» с кодом 2.
**Файлы:** `numerical_solver/gpn_multiphase_solver/cli.py`, `numerical_solver/tests/test_cli.py`.

**Что сделать:**
1. Правки `edits.py`, ключ `CLI`, 4 пары: абзац докстринга модуля; подкоманда `run` — `help`, `description`, `epilog` («по книге — до него»), `metavar="вход"`, `help` аргумента, `--output`, `--title`; импорт `EXCEL_SUFFIXES`; подпись ошибки по расширению входа.
2. Правка `edits.py`, ключ `TEST_CLI` — абзац докстринга `tests/test_cli.py`; блок `plan_code/test_cli_block.py` — в конец `tests/test_cli.py` (3 теста).

**Изменения (главное):**
До:
```python
    except CaseConfigError as exc:
        print(f"Ошибка конфига: {exc}", file=sys.stderr)
        return 2
```
После:
```python
    except CaseConfigError as exc:
        # Книга (FEAT-036): и ошибки ячеек, и отказ проверки конфига по её
        # переводу — ключ строки книги равен пути поля JSON (FEAT-035)
        what = "книги" if config.suffix.lower() in EXCEL_SUFFIXES else "конфига"
        print(f"Ошибка {what}: {exc}", file=sys.stderr)
        return 2
```

**Проверка после шага:**
- Тест: `<PY> -m pytest tests/test_cli.py -q` — прежние + 3 passed.
- Регресс: быстрый.

**Зависимости:** требует шаг 1.
**Оценка:** ~25 строк, ~10 мин.

### Шаг 3: строка «Run» листа COMMENTS и книга генератора

**Цель:** шаблон описывает расчёт по книге; книга `configs/` пересоздана.
**Файлы:** `numerical_solver/gpn_multiphase_solver/io/workbook_template.py`, `numerical_solver/tests/test_workbook_template.py`, `numerical_solver/configs/INPUT_TEMPLATE_v1.xlsx`.

**Что сделать:**
1. Правки `edits.py`, ключи `TEMPLATE` (2 пары: комментарий над `COMMENTS`, строка `("Run", …)` после `("Template", …)`) и `TEST_TEMPLATE` (2 проверки в `test_comments_sheet`).
2. Текст строки (описательная форма, без тире «−–—» — `test_comments_sheet`):
   - EN: «gpn-solver run my_case.xlsx runs the calculation. Results go to the folder output next to the workbook; the folder is cleared before the run. The subfolder output/input keeps the workbook converted to config.json and CSV tables in SI units: gpn-solver run output/input/config.json --output new_folder repeats the run without the workbook.»
   - RU: «Команда gpn-solver run my_case.xlsx выполняет расчёт. Результаты записываются в папку output рядом с книгой; перед расчётом папка очищается. В папке output/input сохраняется книга, переведённая в config.json и таблицы CSV в единицах СИ: команда gpn-solver run output/input/config.json --output new_folder повторяет расчёт без книги.»
3. Пересоздать книгу генератора (умолчание 24), из `<W>\numerical_solver`:
   ```powershell
   <PY> -c "import gpn_multiphase_solver.io.workbook_template as m; print(m.__file__)"   # путь — в <W>
   Remove-Item configs\INPUT_TEMPLATE_v1.xlsx
   <PY> -m gpn_multiphase_solver template configs\INPUT_TEMPLATE_v1.xlsx
   ```
   Первая строка — путь модуля в worktree (иначе книгу написал бы код основного каталога без строки «Run»). Проба: код 0, 22 489 байт.

**Проверка после шага:**
- Тест: `<PY> -m pytest tests/test_workbook_template.py tests/test_workbook_convert.py tests/test_xlsx_reader.py tests/test_cli.py -q` — книга генератора по-прежнему переводится, `TestGeneratorBook` зелёный.
- Регресс: быстрый.

**Зависимости:** независим от шагов 1–2; блокирует шаг 4 (книга примера пишется уже со строкой «Run»).
**Оценка:** ~15 строк, ~10 мин.

### Шаг 4: пример `22_workbook_input`

**Цель:** демонстрационный пример расчёта по книге; тесты примеров его считают.
**Файлы:** новый `numerical_solver/examples/22_workbook_input/` (`22_workbook_input.xlsx`, `main.py`, `README.md`), `numerical_solver/tests/test_examples.py`, `numerical_solver/tests/test_energy_matrix_examples.py`, `numerical_solver/examples/check_energy_balance_all.py`.

**Что сделать:**
1. Книга (умолчание 23), из `<W>\numerical_solver`:
   ```powershell
   New-Item -ItemType Directory examples\22_workbook_input
   <PY> -m gpn_multiphase_solver template examples\22_workbook_input\22_workbook_input.xlsx
   ```
2. `main.py` — `plan_code/example_22/main.py` как есть (обёртка команды `run` по книге; комментарии AST-сравнение не видит).
3. `README.md` — текст §6.1 ниже.
4. `tests/test_examples.py`: правки `edits.py`, ключ `TEST_EXAMPLES` (17 пар) и блок `plan_code/test_examples_block.py` в конец файла:
   - докстринг модуля (структура, «все 24 — около 6 мин»); импорт `atexit`, `functools`, `shutil`, `tempfile`, `convert_workbook`;
   - `"22_workbook_input"` в `ALL_EXAMPLES` и `NEEDS_SG_SECTION`;
   - `_THIN_MAIN` — шаблон с `{input}`; `WORKBOOK_EXAMPLES`, `_TRANSLATED`, `_config_path`;
   - `_config_path(name)` вместо `EXAMPLES_DIR / name / "config.json"` в `_run`, `_output`, `test_load_config_passes`, `test_referenced_csv_present`, `test_no_removed_keys`, `TABLE_PVT`;
   - `test_required_files`: книга вместо `config.json`, и `config.json` рядом с книгой — отказ;
   - `test_thin_main_py_is_command_wrapper`: образец с входом примера;
   - `test_output_explicit`: пример с книгой пропускается (листа OUTPUT нет — FEAT-033, решение 44);
   - класс `TestWorkbookInput` (2 теста): перевод книги (таблицы, $N$ = 100, 22 интервала, ровно 30 сут, $p_{wf}$ = 100/120/150 бар, заголовок, без стационарной аналитики) и состав папки (книга, `main.py`, `README.md` — перевода нет).
5. `tests/test_energy_matrix_examples.py` (сверка матрицы энергии, DEBT-016) — правки `edits.py`, ключ `TEST_MATRIX` (7 пар): `"22_workbook_input"` в собственный список `ALL_EXAMPLES` (дублирует список `test_examples.py` намеренно — докстринг модуля), `WORKBOOK_EXAMPLES`, `_example_config(example, tmp_path)` — перевод книги в `tmp_path`; `test_matrix_matches_reference(example, tmp_path)`; «23» → «24» в двух комментариях. **Без этого `test_coverage_matches_disk` падает на быстром уровне** (проба 1: список разошёлся с `examples/`).
6. `examples/check_energy_balance_all.py` (сводная проверка баланса энергии, README примеров) — правки `edits.py`, ключ `CHECK_BALANCE` (5 пар): вход примера — `config.json` или книга `<имя папки>.xlsx` (`_source`); книга переводится во временный каталог на время сборки решателя. Иначе автопоиск по `config.json` молча пропустил бы пример 22 — ровно то, от чего автопоиск заведён.
7. Прогнать пример (с `PYTHONPATH` на worktree, `GPN_EXAMPLES_EMF=0` — без EMF, как в замерах README):
   ```powershell
   $env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"; $env:GPN_EXAMPLES_EMF = "0"
   <PY> examples\22_workbook_input\main.py
   ```
   Ожидание (проба, `probes/example22.out.txt`, числа — `probes/plan_apply_extra.out.txt`): код 0, ~23 с (расчёт 14.4 с); в `output\` — штатный набор и `input\` (4 файла); $T(r_w)$ = 350.105 К, $p(r_w)$ = 10.071 МПа, $q_o = 3.5618\cdot10^{-5}$ м³ст/с, $S_g^{max}$ = 0.06504; невязка баланса энергии $5.47\cdot10^{-15}$. Числа README 22 и `examples/README.md` сверить с печатью; расхождение в последних знаках — переписать число и отметить в отчёте. Числа README по записям — скрипт `vault/issues/feat-036/probes/example22_numbers.py <каталог вывода>`.
8. Сводная проверка баланса для 22 (не весь набор — ~5 мин): `<PY> -c "import sys; sys.path.insert(0, 'examples'); import check_energy_balance_all as m; print(len(m.find_examples()), m.check_one('22_workbook_input'))"` — `24`, статус `OK`, невязка $5.5\cdot10^{-15}$.

**Проверка после шага:**
- Тест: `<PY> -m pytest tests/test_examples.py -m "not slow" -q`; `<PY> -m pytest tests/test_examples.py -k "22_workbook_input or TestWorkbookInput" -q`; `<PY> -m pytest tests/test_energy_matrix_examples.py -k "coverage or 22_workbook_input" -q` (2 passed, ~18 с).
- Регресс: **полный** — шаг меняет фикстуру `results` и сборку `tests/test_examples.py` (`TABLE_PVT`, `_run`): ошибку ловят только медленные тесты (общие проверки по `ALL_EXAMPLES`). Полный прогон шага можно совместить с итоговым полным `/implement`, если шаги 5–6 меняют только документы.

**Зависимости:** требует шаги 1 (команда по книге) и 3 (книга со строкой «Run»).
**Оценка:** ~60 строк тестов (готовы), README ~120 строк, ~40 мин.

#### 6.1. `examples/22_workbook_input/README.md`

Текст — `vault/issues/feat-036/probes/plan_code/example_22/README.md` **как есть** (итоговый, проверен пробой: разделы «Как модифицировать», «Как увеличить газонасыщенность», классы `PrototypeHydroAdapter`, `TridiagEnergySolver` — `TestReadme`; ссылок на уравнения нет — `test_eq_references`). Разделы: описание; как устроен расчёт по книге (4 действия команды, что остаётся при отказе, таблица «лист → что задаёт → перевод в СИ»); комбинация модулей; ключевые параметры книги; расписание; ожидаемое поведение (таблица 11 моментов: $p_{wf}$, $q_o$, GOR, $T(r_w) - T_0$; двухфазная зона 3.06 / 9.23 / 14.96 м; балансы, $R_s$); как увеличить газонасыщенность; как модифицировать (своя книга — `template`, расчёт, `convert`; тесты привязаны к шаблону); графики; запуск. Сравнений с другими примерами нет (решение 7, память «Examples independent»).

#### 6.2. Пример 22 в `examples/README.md` (тексты к шагу 5, п. 5.2)

Подраздел «### Расчёт по книге ввода Excel» после «Охлаждение забоя на корреляциях (Standing + Corey)»:

```markdown
### Расчёт по книге ввода Excel

| № | Папка | вход | $p_{wf}$ | длительность | запись | $T(r_w)$, К |
|---|---|---|---|---|---|---|
| 22 | [22_workbook_input](22_workbook_input/) | книга `22_workbook_input.xlsx` (шаблон `gpn-solver template`) | 150 → 120 → 100 бар на 5 и 15 сут | 30 сут | строки SCHEDULE: 1 мин … 30 сут, 23 записи | 350.105 |

Вход — только книга ввода Excel решателя: все параметры в инженерных
единицах, таблицы PVTO, газа и ОФП. Команда `run` переводит книгу в
`output\input\` (`config.json` и CSV в СИ) и считает по переводу; каталог
вывода очищается до расчёта. $k$ = 1 мД, $R_e$ = 100 м, $R_{s,0}$ = 50,
$p_b$ = 180 бар, PVTO из семи ветвей, $N$ = 100; тепловые свойства —
демонстрационные значения шаблона. Забой охлаждается после каждой ступени
$p_{wf}$ на 0.13–0.27 К и прогревается; к 30 сут $T(r_w)$ на 0.105 К выше
$T_0$. Стационарная аналитика не строится: листа OUTPUT в книге нет,
`steady_state` — умолчание `false`.
```

Строки таблиц:

| таблица | строка |
|---|---|
| время прогона | последняя строка «\| 18 \| 40 с \| \| \|» → «\| 18 \| 40 с \| 22 \| 23 с \|» |
| замкнутое решение | «\| 22 \| таблицы / таблицы \| — \| — \| не строится (`output.steady_state = false`) \|» |
| проверка $R_s$ | «\| 22 \| таблица \| 25.24 … 50 \| 73 \| $7.1\cdot10^{-15}$ \| 0 \| 0 \|» |
| баланс энергии | «\| **22** \| **2.5 / 0.13 / 0.05** \| $5.5\cdot10^{-15}$ \| $+4.26\cdot10^{6}$ \|» |
| баланс массы | «\| \| \| \| \| 22 \| $2.4\cdot10^{-10}$ \| $1.6\cdot10^{-8}$ \|» после строки 21 |

### Шаг 5: документация

**Цель:** инженер находит в README, как получить шаблон, заполнить и посчитать книгу.
**Файлы:** `numerical_solver/README.md`, `numerical_solver/examples/README.md`, `numerical_solver/CHANGELOG.md`, `CLAUDE.md`.

**5.1. `numerical_solver/README.md`** (якоря — по тексту на `30a64f7`):

1. «Состав каталога», строка `configs/`: «исходный файл конфигурации для первого расчёта (`baseline.json`)» → «исходный файл конфигурации для первого расчёта (`baseline.json`) и шаблон книги ввода Excel (`INPUT_TEMPLATE_v1.xlsx`)».
2. §2: «# все 23 примера подряд, около 12 мин» → «# все 24 примера подряд, около 12 мин» (пример 22 добавляет ~23 с); «В 17 примерах `main.py` только вызывает эту команду.» → «В 18 примерах `main.py` только вызывает эту команду (в примере 22 — с книгой Excel вместо файла конфигурации).»
3. §3, сразу после заголовка «## 3. Расчёт собственного варианта» — абзац: «Вариант задаётся файлом конфигурации JSON в единицах СИ (3.1–3.5) или книгой Excel в инженерных единицах (3.6). Книга переводится в такой же файл конфигурации, и дальше расчёт идёт одинаково.»
4. §3.4, в конец врезки «После успешного расчёта каталог вывода полностью очищается…» — строка: «> При расчёте по книге Excel каталог очищается до расчёта (3.6).» В абзаце кодов возврата: «1 — решатель не смог выполнить шаг по времени (сообщение решателя выводится в консоль, прежние результаты в каталоге вывода сохраняются)» → «… (сообщение решателя выводится в консоль; при расчёте по файлу конфигурации прежние результаты в каталоге вывода сохраняются, по книге — в каталоге остаётся только перевод книги, 3.6)».
5. §3.5: «перед расчётом — путь к файлу конфигурации и версии» → «перед расчётом — путь к файлу конфигурации (или к книге) и версии»; в таблице `output`, поле `title`: «имя каталога файла конфигурации» → «имя каталога файла конфигурации; у книги — имя книги без расширения».
6. Новый §3.6 — после абзаца «Сравнение со стационарным режимом имеет смысл включать…» перед «## 4.»:

````markdown
### 3.6. Книга ввода Excel

Вместо файла конфигурации расчёт можно задать книгой Excel (`.xlsx`):
величины — в инженерных единицах (бар, мД, сП, м³ст/сут, сутки, часы),
у числовых ячеек — проверка допустимых значений. Одна книга — один расчёт.

1. Получить шаблон с демонстрационными значениями:

   ```powershell
   .venv\Scripts\python -m gpn_multiphase_solver template my_case.xlsx
   ```

   Существующий файл команда не перезаписывает.
2. Заполнить книгу: на листах MODEL, THERMAL, NUMERICS — столбец Value
   (значение нужно в каждой строке), таблицы режима скважины SCHEDULE и
   свойств OIL_PVT, GAS_PVT, RELPERM. Единицы фиксированы и проверяются
   при чтении. Правила листов — на листе COMMENTS книги. Книга сохраняется
   в формате «Книга Excel (*.xlsx)».
3. Рассчитать:

   ```powershell
   .venv\Scripts\python -m gpn_multiphase_solver run my_case.xlsx [--output КАТАЛОГ] [--title ЗАГОЛОВОК] [--profiles N]
   ```

Результаты — те же, что у расчёта по файлу конфигурации (3.5), по
умолчанию в каталоге `output` рядом с книгой; заголовок рисунков — имя
книги без расширения. В `output\input\` сохраняется вход расчёта: книга,
переведённая в файл конфигурации `config.json` и таблицы CSV в единицах
СИ. По нему расчёт повторяется без книги (команда — из папки книги):

```powershell
.venv\Scripts\python -m gpn_multiphase_solver run output\input\config.json --output другой_каталог
```

Без `--output` результаты повтора легли бы в `output\input\output\` —
внутрь каталога, который следующий расчёт по книге очистит.

> **При расчёте по книге каталог вывода очищается до расчёта** — сразу
> после проверки книги. Если в книге ошибка, каталог не меняется. Если
> ошибку находит проверка файла конфигурации или таблиц либо решатель не
> может выполнить шаг по времени, в каталоге остаётся только `input\` —
> вход, на котором расчёт остановился; прежних результатов нет. Книга
> внутри каталога вывода — отказ до расчёта. Если файл каталога вывода
> открыт в другой программе (например, CSV в Excel), каталог не удаётся
> очистить: команда завершается с ошибкой до расчёта — файл нужно закрыть
> и повторить расчёт.

Ошибки книги выводятся все сразу, с листом и ячейкой: `NUMERICS!C2 (Grid
cells (N)): 20.5 — нужно целое число ≥ 1`. Ошибки, которые находит проверка файла конфигурации
и таблиц, называют поле конфигурации — оно совпадает с ключом строки книги
(столбец Key), например `initial_conditions.Rs0`. Коды возврата — как в
3.4; код 2 — также ошибка книги.

Перевести книгу без расчёта (посмотреть, какие значения в СИ получит
расчёт) — команда `convert`; каталог — новый или пустой:

```powershell
.venv\Scripts\python -m gpn_multiphase_solver convert my_case.xlsx каталог
```

Пример расчёта по книге — [examples/22_workbook_input](examples/22_workbook_input/README.md).
````

7. §4, после «`run_case` записывает файлы и выводит сводку в консоль так же, как команда.» — «Первым аргументом можно передать и книгу Excel (3.6): `run_case("my_case.xlsx")`.»

**5.2. `numerical_solver/examples/README.md`:**

1. Вступление: «Каждая подпапка самодостаточна — конфиг, нужные CSV, `main.py` и README» → «Каждая подпапка самодостаточна — конфиг и нужные CSV (у 22 — книга Excel), `main.py` и README»; «У 17 примеров `main.py` — обёртка команды пакета» → «У 18 примеров …».
2. «С какого начать», после строки 18 — строка: «| Исходные данные — в книге ввода Excel решателя (шаблон `gpn-solver template`): расчёт одной командой, без файла конфигурации | **22** |».
3. «Все сценарии», после подраздела «Охлаждение забоя на корреляциях (Standing + Corey)» — подраздел «### Расчёт по книге ввода Excel» (§6.2 — таблица и абзац, числа из пробы).
4. «## Запуск», в блоке команд после строки примера 06 по конфигу — «.venv\Scripts\python -m gpn_multiphase_solver run examples\22_workbook_input\22_workbook_input.xlsx   # пример 22 — по книге».
5. «### Команда расчёта по конфигу (FEAT-030)» — в конец первого абзаца после кодов возврата: «Вход может быть и книгой ввода Excel (`run книга.xlsx`): книга переводится в `output\input\` (файл конфигурации и CSV — вход, по которому расчёт повторяется без книги), каталог вывода очищается **до** расчёта — подробно в [README пакета, §3.6](../README.md).»; «У 17 примеров `main.py` — обёртка этой команды» → «У 18 примеров …».
6. Таблица времени прогона: последняя строка «| 18 | 40 с | | |» → «| 18 | 40 с | 22 | 23 с |» (§6.2); в перечень дат замеров — «22 — 2026-10-18».
7. Таблица замкнутого решения: «| 22 | таблицы / таблицы | — | — | не строится (`output.steady_state = false`) |»; в абзац после таблицы — «У 22 флаг — умолчание: листа OUTPUT в книге нет.»
8. Таблицы проверки $R_s$, баланса энергии, баланса массы — строки 22 (§6.2).

**5.3. `numerical_solver/CHANGELOG.md`**, «## Не выпущено» → «### Добавлено», последним пунктом:

```markdown
- Расчёт по книге ввода Excel: `gpn-solver run книга.xlsx` и
  `run_case("книга.xlsx")`. Книга переводится в `output/input/`
  (`config.json` и таблицы CSV в СИ — по ним расчёт повторяется без
  книги); каталог вывода очищается до расчёта. Пример 22.
```

**5.4. `CLAUDE.md`**, строка «Расчёт по конфигу: …» → «Расчёт по конфигу: `python -m gpn_multiphase_solver run <config.json>` (или `gpn-solver run …`), результаты — `output/` рядом с конфигом (FEAT-030); по книге Excel — `run <книга.xlsx>`, перевод сохраняется в `output/input/`, каталог вывода очищается до расчёта (FEAT-036).»

**Проверка после шага:** `<PY> -m pytest tests/test_eq_references.py tests/test_packaging.py -q` (ссылки на уравнения в README примеров, журнал); число тестов — `--collect-only -q`. Регресс: только документы — `--collect-only -q`.
**Зависимости:** требует шаг 4 (числа и время примера 22 — из его прогона).
**Оценка:** ~120 строк текста, ~30 мин.

### Шаг 6: vault

**Цель:** решение и контракт записаны; реестр и индекс обновлены.
**Файлы:** новая заметка `vault/knowledge/decisions/расчёт по книге очищает каталог вывода до перевода — input и результаты от одного запуска.md`; `vault/plans/feat-036 run-from-workbook.md` (статус), `vault/roadmap/планируемые фичи.md`, `vault/00-home/index.md`; заметка [[перевод книги в конфиг проверяет только книгу — моменты SCHEDULE в целых мс]] — строка «потребитель — `run_case` (FEAT-036)»; заметка [[пример — это конфиг и README, штатный набор рисунков и проверок даёт команда пакета]] (решения FEAT-030) — к пунктам «коды возврата» и «3. Каталог вывода очищается целиком» строка «у расчёта по книге очистка — до расчёта, при отказе в каталоге только `input/` (FEAT-036, решение 12)», к «все 23 примера задают поле явно» — «кроме 22: листа OUTPUT в книге нет» (аудит 1: заметка утверждает обратное новому поведению).

**Что сделать:** заметка — решения 12, 13, 16–21; порядок `run_case` для книги (§1); почему не А и не В (§3); цена — потеря результатов при отказе; где описано для инженера (README §3.6, COMMENTS, справка). Ссылки на `problem_statement.tex` — нет (меток не требуется; сторож DEBT-074 проверит).
**Проверка:** `<PY> -m pytest tests/test_eq_references.py -q`.

## 7. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_input_saved_and_output_cleared` | `test_workbook_run.py` | малая книга «малая книга.xlsx», рядом `output/прошлый.csv`; `run_case(книга)` | вывод — `output` рядом с книгой; `input/` = 4 файла; `прошлый.csv` нет; штатные CSV, PNG есть; `INPUT_DIR == "input"` | нет очистки до записи перевода; `input/` стирается после расчёта |
| `test_title_and_print` | там же | та же | заголовок «малая книга»; строки печати 1–2: «=== малая книга ===», «Книга: <путь>» | печать временного/переведённого пути вместо книги |
| `test_saved_input_reproduces_run` | там же | `load_config(output/input/config.json)` → новый расчёт | `times`, $p$, $T$, $S_g$, $R_s$ всех записей, $q_o$, $T_{wf}$ — побитово (`np.array_equal`) | перевод в `input/` расходится с тем, по которому считали |
| `test_book_inside_output_refused` | там же | `run_case(книга, папка книги)`, `run_case(книга, предок)`; `Simulator.run` — падение | `CaseConfigError` «содержит книгу»; книга цела | очистка удаляет книгу |
| `test_book_error_leaves_output` | там же | `grid.N` = 20.5 | `CaseConfigError` «книга не переведена», `NUMERICS!C2`; `output/` = только `прошлый.csv` | очистка до проверки книги (решение 16) |
| `test_not_workbook_and_missing` | там же | текст под `.xlsx`; нет файла | «не zip»; «книга не найдена»; `output/` не создан | сообщение ОС вместо понятного |
| `test_config_error_after_cleanup_keeps_input` | там же | $R_{s,0}$ = 70 вне ветвей 5…60 | `CaseConfigError` «Rs0 = 70», начинается с пути книги; `output/` = только `input/` с 4 файлами | ошибка с путём перевода; пустой каталог без входа |
| `test_run_failure_keeps_input` | там же | `Simulator.run` → `RuntimeError` | `CaseRunError`; `output/` = только `input/` | — (фиксирует цену решения 12) |
| `test_invalid_profiles_argument_leaves_output` | там же | `n_profiles=1` | `ValueError`; `output/` не тронут | ошибка аргумента стирает вывод |
| `test_locked_output_file_refused` (аудит 1) | там же | `shutil.rmtree` подменён на `PermissionError` (как WinError 32 на открытом файле); `Simulator.run` — падение | `CaseConfigError` «открыт в другой программе», путь каталога и имя файла в сообщении | трассировка вместо подсказки |
| `test_config_run_clears_output_after_run` (аудит 1) | там же | перевод малой книги как JSON-конфиг; рядом `output/прошлый.csv`; `run_case(config, output)` | `прошлый.csv` удалён, `input/` нет, штатные файлы есть; заголовок «b» | правка 1.11 отключила очистку у конфига |
| `test_excel_suffixes_take_workbook_path` ×4 | там же | `B.XLSX`, `.xlsm`, `.xls`, `.xlsb` с JSON внутри | «не zip» — путь книги | расширение с учётом регистра; `.xls` в загрузчик JSON |
| `test_excel_suffixes` | там же | — | `(".xlsx", ".xlsm", ".xls", ".xlsb")` | молчаливая смена набора |
| `test_command_runs_workbook` | там же | `python -m gpn_multiphase_solver run "case/скважина 1.xlsx"` из постороннего каталога, отдельный процесс | код 0; `input/` = 4 файла; строки «=== скважина 1 ===», «Книга: <абсолютный путь>» | зависимость от каталога запуска; пробел и кириллица в пути |
| `test_run_help_mentions_workbook` | `test_cli.py` | `run --help` | «книга ввода Excel (.xlsx)», «по книге — до него» (текст без переносов) | справка не говорит об очистке до расчёта |
| `test_run_book_error_returns_2` | там же | текст под `.xlsx` | код 2, `Ошибка книги:`, «не zip», без трассировки | «Ошибка конфига» у книги |
| `test_run_missing_book_returns_2` | там же | нет файла | код 2, `Ошибка книги:`, «книга не найдена» | — |
| `test_comments_sheet` (+2 проверки) | `test_workbook_template.py` | шаблон | вторая строка COMMENTS — «Run», команда на обоих языках | строку забыли или переставили |
| `TestWorkbookInput` (2) | `test_examples.py` | перевод книги примера 22 | §6, шаг 4, п. 4 | книгу заменили, README и ожидания прежние; перевод рядом с книгой |
| общие проверки ×22 | `test_examples.py` | 22 в `ALL_EXAMPLES` | структура, конфиг, расчёт, физика двухфазного, балансы, $R_s$, PVT, README | пример по книге вне общих проверок |
| `test_matrix_matches_reference[22_workbook_input]` (slow), `test_coverage_matches_disk` | `test_energy_matrix_examples.py` | матрица энергии примера 22 против эталона по формулам постановки | rtol $10^{-12}$ на каждом вызове `solve` (~18 с); список совпадает с диском | матрица 22 не сверяется; охват отстал от `examples/` |

**Отличие от записи реестра** («команда на демонстрационной книге в отдельном процессе»): команда в отдельном процессе проверяется на малой книге (`test_command_runs_workbook`, ~8 с вместо ~25 с у книги примера — быстрый уровень); книгу примера 22 тесты переводят и считают в процессе (`_config_path` + фикстура `results`), её команда — `main.py` в шаге 4, п. 7, вручную. Вместе это покрывает и путь `run_case(книга)`, и демонстрационную книгу.

Категории: unit — порядок и отказы `run_case` на малой книге; предельные случаи — книга в каталоге вывода, отсутствующая книга, ошибка ячейки, ошибка конфига после очистки, отказ решателя, неверный аргумент; инвариант — побитовое воспроизведение по `input/`; интеграционные — команда в отдельном процессе, пример 22 в общих проверках; регрессия — все прежние тесты (`run_case` по конфигу не меняется). Аналитики и сходимости в задаче нет — новых вычислений нет.

## 8. Критерии завершения

- [ ] `run_case(книга)`: порядок решений 12, 16, 19, 20; печать и ошибки называют книгу (18).
- [ ] `gpn-solver run книга.xlsx`: коды 0 / 1 / 2, «Ошибка книги», справка.
- [ ] Строка «Run» на листе COMMENTS; `configs/INPUT_TEMPLATE_v1.xlsx` пересоздана.
- [ ] Пример 22: книга, `main.py`, README; в `ALL_EXAMPLES`; печать примера сверена с README.
- [ ] README пакета §3.6, §2, §3.4, §3.5, §4; `examples/README.md`; `CHANGELOG.md`; `CLAUDE.md`.
- [ ] Тесты: 2461 собрано (на базе `ee2be23`); быстрый уровень и полный прогон зелёные.
- [ ] Заметка решения, план, реестр, индекс; комментарий в #136.

## 9. Новые проблемы

Блокирующих нет. Зарегистрирован [[DEBT-082]] (аудит 1).

0. **[[DEBT-082]]** — у расчёта по JSON-конфигу файл каталога вывода, открытый в другой программе, ломает очистку **после** расчёта: `PermissionError` WinError 32, трассировка, результаты не записаны, каталог очищен частично. У книги в этой задаче — отказ до расчёта (умолчание 29).

1. **Свои списки примеров по `config.json`** — `tests/test_energy_matrix_examples.py` (проба 1: `test_coverage_matches_disk` упал) и `examples/check_energy_balance_all.py` (молча пропустил бы 22). Учтены в шаге 4 (п. 5, 6), не отдельная задача.
2. **`examples/two_phase_analytics.py`** как скрипт (`_resolve_example` → `folder / "config.json"`) на примере 22 упадёт `FileNotFoundError`. Не правится: он строит стационарную двухфазную аналитику, а у 22 режим меняется (`steady_state = false`); вызывают его 03–05.
3. **README пакета §3.4 советует `time.dt_after_control_change` = 2** — устарело после [[BUG-026]] (0.11 с); известно, README доводит FEAT-031; в шаблоне книги — 0.11 с.
4. **Параллельная работа:** [[DEBT-081]] влита во время планирования (`ee2be23`) — не пересекается; база может уйти снова, число тестов сверить при baseline.

## 10. Связь формула → код

Формул нет. Ссылок на уравнения в новом коде нет; сторож `tests/test_eq_references.py` проверяет README примера 22 и докстринги.

## 11. Проверка плана на копии дерева

`vault/issues/feat-036/probes/plan_apply.py`: копия `git archive <база> numerical_solver`, правки `edits.py` (каждое «было» — ровно одно вхождение), новые файлы и блоки, книги примера 22 и генератора — командой `template` копии; venv основного каталога, запуск из каталога копии. Режимы: без аргумента — всё (вывод `plan_apply.out.txt`); `tests`, `fast`, `examples`, `extra` — разбор по частям, копия остаётся (`plan_tree/`, удалить после).

| Проверка | База | Итог |
|---|---|---|
| якоря `edits.py` на HEAD (`probes/audit_anchors.py`, аудит 1) | `ee2be23` | 8 файлов, 50 пар, ошибок 0 — запустить перед шагом 1, если база ушла |
| новые и затронутые тесты, сторожа (`test_workbook_run`, `test_cli`, `test_workbook_template`, `test_workbook_convert`, `test_xlsx_reader`, `test_workbook_format`, `test_eq_references`, `test_public_api`, `test_example_scripts`, `test_packaging`) | `ee2be23` (после аудита 1) | 508 passed, 3 skipped (черновик руководителя вне git; 2 — нет vault в копии), 44 с |
| число тестов | `ee2be23` | 2461 (база 2421) |
| быстрый уровень | `ee2be23` (после аудита 1) | 2174 passed, 3 skipped, 173 с. Проба 1 (на `30a64f7`, до правки `test_energy_matrix_examples.py`) — 1 failed: `test_coverage_matches_disk` (список примеров разошёлся с `examples/`) → шаг 4, п. 5 |
| 14 порч кода — каждая ловится | `ee2be23` (после аудита 1) | книга в каталоге вывода не отвергается — 1 failed; очистка до чтения книги — 2; нет очистки до записи — 4; очистка после расчёта и у книги — 3; защита входных файлов и у книги — 3 + 3 errors; печать «Конфиг» вместо «Книга» — 2; ошибка фабрики с путём перевода — 1; расширение с учётом регистра — 1; `n_profiles` не проверяется до перевода — 1; сообщение ОС вместо «книга не найдена» — 2; очистка у конфига отключена — 1; отказ очистки (файл открыт) не ловится — 1; «Ошибка конфига» у книги — 2; нет строки «Run» — 1 |
| пример 22 `main.py` (`GPN_EXAMPLES_EMF=0`) | `42ef497`, `ee2be23` | код 0, 20.9–23.1 с (расчёт 14.4 с); `output/`: штатный набор + `input/` (4 файла); печать — `example22.out.txt`, числа README — `plan_apply_extra.out.txt` |
| сверка матрицы энергии 22 + охват | `42ef497` | 2 passed, 18 с |
| `check_energy_balance_all`: поиск и `check_one("22_workbook_input")` | `42ef497` | 24 примера; невязка $5.47\cdot10^{-15}$, OK |
| `tests/test_examples.py` целиком (все 24 примера) | `30a64f7`; `ee2be23` (дважды, второй — после аудита 1) | 487 passed (255 с); 487 passed (254 с, 249 с) |
| очистка каталога с открытым файлом (`probes/audit_locked_output.py`, аудит 1) | — | `PermissionError` WinError 32 «The process cannot access the file…», из трёх файлов удалён один |

**Ложный отказ при параллельном влитии.** Прогон `test_examples.py` на `42ef497` (13:27–13:30) дал 7 failed, 12 errors: во время сессии пропали и каталоги `tmp_path` pytest, и каталог перевода `%TEMP%\gpn-examples-…` (`config.json`, `oil_pvt.csv` не найдены после успешных `test_completes[22_workbook_input]`). Сессия совпала с влитием [[DEBT-081]] другой сессией (13:19–13:23). Тот же код на `ee2be23` — 487 passed. Код задачи временные каталоги не удаляет (поиск `rmtree`, `gettempdir` по `numerical_solver/`: только `run_case` — свой каталог вывода — и тесты прототипа). Если на `/implement` отказ повторится без параллельной работы — разбирать: `_TRANSLATED` (шаг 4) живёт всю сессию pytest, удаляется `atexit`.
