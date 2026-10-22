## Описание

Книга ввода Excel переводится в конфиг командой `gpn-solver convert книга.xlsx каталог` ([FEAT-035](https://github.com/ArturSalamatin/Oil_Gas/issues/133)), но расчёт по книге — два шага вручную: перевести, затем `gpn-solver run каталог/config.json`. Задача добавляет расчёт одной командой: `gpn-solver run книга.xlsx` — вход выбирается по расширению. Переведённые `config.json` и CSV таблиц сохраняются в `output/input/`: расчёт воспроизводится командой по ним (решение пользователя 2026-10-14). Результаты выводятся так же, как при расчёте по конфигу ([FEAT-030](https://github.com/ArturSalamatin/Oil_Gas/issues/104)). Заголовок рисунков по умолчанию — имя книги без расширения (перевод пишет его в `output.title`); флаги `--output`, `--title`, `--profiles` действуют и для книги.

В объёме также: строка «Run» листа COMMENTS шаблона, инструкция инженера в README пакета (три команды — `template`, `convert`, `run книга.xlsx`), демонстрационный пример `examples/22_workbook_input` со своей книгой.

## Мотивация

Поставка заказчику ([FEAT-031](https://github.com/ArturSalamatin/Oil_Gas/issues/114)): инженер получает шаблон, заполняет его и считает одной командой; одна книга — один расчёт. Цепочка: FEAT-033 (формат) ✅ → FEAT-034 (разбор ячеек) ✅ → FEAT-035 (перевод) ✅ → **FEAT-036** → FEAT-031. Последнее звено ввода книгой.

## Физическое/математическое обоснование

Новых уравнений нет. Числа расчёта по книге и по `output/input/config.json` должны совпадать побитово: перевод пишет числа через `repr`, таблицы — те же файлы.

## Предлагаемый API

Предварительно; окончательно — при `/plan-feature`.

- **Команда:** `gpn-solver run книга.xlsx [--output КАТАЛОГ] [--title ЗАГОЛОВОК] [--profiles N]`. `.json` — как сейчас; `.xlsx` — книга. Каталог вывода по умолчанию — `output/` рядом с книгой.
- **Коды возврата** (решение 9 черновика): 0 — расчёт выполнен; 1 — решатель отказал; 2 — ошибка аргументов, книги (`WorkbookError`, включая `WorkbookContentError`) или конфига (`CaseConfigError`), книга не найдена или не читается (`OSError`). Сейчас подкоманда `run` ловит только `CaseConfigError` и `CaseRunError` (`cli.py`, `main`) — исключения разбора и перевода печатались бы с трассировкой как ошибка кода.
- **Защита книги** (решение 4 черновика): отказ до перевода и расчёта, если книга лежит внутри каталога вывода — его очистка удалила бы её. Защита FEAT-030 (`_check_inputs_outside`) проверяет только конфиг и его CSV.
- **Лист COMMENTS:** строка «Run» после «Template» в `io/workbook_template.COMMENTS` (FEAT-033, решение 62) и её проверка в `test_comments_sheet`.

## Найдено при открытии (на `b9454a6`, после влития FEAT-035)

1. **Порядок черновика несовместим с `run_case`.** Черновик: «очистка каталога вывода → перевод в `output/input/` → `run_case`». В коде очистка — внутри `run_case` и **после** расчёта (`report/pipeline.py:141–143`, решение пользователя 2026-10-13: при отказе решателя прежние результаты уцелеют). Отсюда два отказа при прямом порядке:
   - `run_case(output/input/config.json, output/)` отвергнет вход сразу: `_check_inputs_outside` (`pipeline.py:290`) — «каталог вывода содержит входной файл»;
   - если бы проверка пропустила, `shutil.rmtree(output_dir)` после расчёта удалил бы `output/input/`.

   Очистить `output/` до перевода — значит отменить решение 2026-10-13 для расчёта по книге: при отказе решателя прежние результаты потеряны. Варианты — ниже, выбор — при планировании.
2. **Расширение.** Что делать с входом не `.json` и не `.xlsx`: сейчас любой файл идёт в `load_config`. Регистр (`.XLSX`) и `.xlsm` — не определены. `read_workbook` сам отвергает `.xls`, `.xlsb`, книги с паролем — с подсказкой.
3. **Печать «Конфиг: …»** (`pipeline.py:114`) при расчёте по книге назовёт файл перевода, а не книгу; что печатать — решить при планировании.
4. **Повторный расчёт по `output/input/config.json`** без `--output` пишет в `output/input/output/` — внутрь каталога вывода прошлого расчёта; следующий расчёт по книге его удалит. README должен советовать `--output`.
5. **Пример 22 и тесты примеров.** `tests/test_examples.py` ждёт `config.json` в каждой папке примера (`test_required_files` :174, `_run` :105, `test_load_config_passes` :221, `test_referenced_csv_present` :227, `test_no_removed_keys` :247, `test_output_explicit` :262), `test_thin_main_py_is_command_wrapper` :181 — вызов `main(["run", …/config.json])`. У примера по книге `config.json` нет. `examples/run_all.py` отбирает папки по `main.py` — пример 22 подхватит без правок; `tests/test_example_scripts.py` разбирает все `*.py` — `main.py` примера проверит.
6. **Книга генератора устареет молча.** `configs/INPUT_TEMPLATE_v1.xlsx` записана командой `template`; `TestGeneratorBook` (`tests/test_workbook_template.py:259`) сверяет листы, ключи, единицы, заголовки, но не лист COMMENTS — после строки «Run» книга в `configs/` останется без неё, тесты не заметят. Пересоздать её (удалить файл — решение 58 FEAT-033) — шаг плана.
7. **Журнал изменений.** [FEAT-037](https://github.com/ArturSalamatin/Oil_Gas/issues/134) (`CHANGELOG.md`) реализуется в параллельном worktree. Если она будет влита раньше — FEAT-036 добавляет строку в раздел «Не выпущено».

## Анализ вариантов (п. 1)

**А. Перевод во временный каталог, копия в `output/input/` после успешного расчёта.** `cli`: проверка книги вне каталога вывода → `tempfile.TemporaryDirectory()` → `convert_workbook(книга, tmp)` → `run_case(tmp/config.json, output)` → копия файлов перевода в `output/input/`.
- Плюсы: `run_case` и защита FEAT-030 не меняются; решение 2026-10-13 сохраняется (при отказе решателя прежние результаты целы); `output/input/` создаётся после очистки — «свои файлы» под защиту не попадают.
- Минусы: каталог во временной папке пользователя; печать «Конфиг:» — путь временного файла (п. 3); при отказе решателя (код 1) перевод не сохраняется — для разбора ошибки инженер запускает `convert`.

**Б. Запись `output/input/` из памяти после очистки.** То же, что А, но после расчёта `write_files(output/input, config, tables)` повторно из словаря и таблиц `workbook_to_config` — побайтно те же файлы без копирования. Для расчёта файлы всё равно нужны на диске (фабрика читает CSV по `config.config_dir`) — временный каталог остаётся. Отличие от А только в способе получить `output/input/`.

**В. `run_case` знает о сохранённом входе.** Новый параметр (например, каталог входа внутри `output_dir`): `_check_inputs_outside` его пропускает, очистка удаляет всё, кроме него; перевод — в `output/input/` до расчёта.
- Плюсы: без временного каталога; печать указывает на `output/input/config.json`.
- Минусы: меняется `run_case` — публичный интерфейс (README §4); прежний `output/input/` от прошлого расчёта надо удалять до перевода — при отказе решателя в `output/` остаются старые результаты рядом с новым входом (рассогласование); сложнее защита.

**Г. Очистка до перевода** (буквально черновик). Отменяет решение 2026-10-13 для книги и всё равно требует правок `run_case` (проверка входа и `rmtree`). Не рекомендуется.

**Рекомендация:** А (или Б — выбрать по простоте кода при планировании): изменения только в `cli.py`, контракт `run_case` и FEAT-030 не трогаются.

## Зависимости

- [FEAT-035](https://github.com/ArturSalamatin/Oil_Gas/issues/133) — `convert_workbook` (`io/workbook_convert.py`); влит `86348ed` ✅
- [FEAT-030](https://github.com/ArturSalamatin/Oil_Gas/issues/104) — `gpn-solver run`, `run_case` ✅
- [FEAT-033](https://github.com/ArturSalamatin/Oil_Gas/issues/128), [FEAT-034](https://github.com/ArturSalamatin/Oil_Gas/issues/132) ✅
- Блокирует: [FEAT-031](https://github.com/ArturSalamatin/Oil_Gas/issues/114)

## Затронутые файлы

| Файл | Строки | Роль |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/cli.py` | `_parser` :52 (подкоманда `run` :59–75), `_convert` :119 (образец ловушек исключений), `main` :146 (`run` :157–172) | выбор входа по расширению, перевод, защита книги, коды возврата |
| `numerical_solver/gpn_multiphase_solver/report/pipeline.py` | `run_case` :59, заголовок :100–101, каталог по умолчанию :109–110, печать :114, очистка :141–143, `_check_inputs_outside` :290 | расчёт; меняется только в варианте В |
| `numerical_solver/gpn_multiphase_solver/io/workbook_convert.py` | `convert_workbook` :63 (непустой каталог — `FileExistsError` :68), `write_files` :76, `workbook_to_config` :89, `output.title` :451 | перевод; не меняется |
| `numerical_solver/gpn_multiphase_solver/io/workbook_template.py` | `COMMENTS` :129 (комментарий :128) | строка «Run» |
| `numerical_solver/configs/INPUT_TEMPLATE_v1.xlsx` | — | пересоздать командой `template` (п. 6) |
| `numerical_solver/tests/test_cli.py` | расчёт :95–189, перевод :298–353 | тесты команды |
| `numerical_solver/tests/test_workbook_template.py` | `test_comments_sheet` :115, `TestGeneratorBook` :259 | строка «Run» |
| `numerical_solver/tests/test_examples.py` | `ALL_EXAMPLES` :30, `_run` :105, `test_required_files` :174, `test_thin_main_py_is_command_wrapper` :181, `test_no_extra_example_folders` :200 | папка примера с книгой (п. 5) |
| `numerical_solver/examples/22_workbook_input/` | новый | книга, `main.py`, `README.md` |
| `numerical_solver/examples/README.md`, `numerical_solver/README.md` (§3.4 :213–236) | — | инструкция инженера: `template`, `convert`, `run книга.xlsx` |
| `CLAUDE.md` | :274 | строка о расчёте по конфигу |

## План реализации

1. **Проектирование** — вариант п. 1 (А/Б/В); расширения и регистр (п. 2); печать (п. 3); пример 22 в тестах примеров (п. 5); текст строки «Run».
2. **Ядро** — `cli.py`: выбор входа, защита книги, перевод, `run_case`, сохранение `output/input/`; ловушки `WorkbookError`, `OSError` → код 2.
3. **Шаблон** — строка «Run» в `COMMENTS`, `test_comments_sheet`; пересоздать `configs/INPUT_TEMPLATE_v1.xlsx`.
4. **Пример 22** — `examples/22_workbook_input`: своя книга (сценарий на основе примера 18 со значениями FEAT-033: $R_s$ = 60 в PVTO, $h_0$ = 0.11 с, $T_0$ = 350 К), `main.py` — обёртка `run` по книге, `README.md`; поддержка в `tests/test_examples.py`.
5. **Документация** — README пакета §3 (три команды), `examples/README.md`, `CLAUDE.md`; строка журнала, если FEAT-037 влита.
6. **Тесты и верификация** — команда на книге в отдельном процессе (код 0, файлы `output/input/`, заголовок — имя книги); расчёт по `output/input/config.json` повторяет расчёт по книге побитово; отказ, если книга внутри каталога вывода (книга не тронута); книга с ошибкой, не книга, отсутствующая книга — код 2 без трассировки; при отказе решателя (код 1) прежние результаты целы. Быстрый уровень после каждого шага, полный — в конце.

## Ветка

`feat/feat-036/run-from-workbook`

## Связанные issues

Related: #133 (FEAT-035), #132 (FEAT-034), #128 (FEAT-033), #104 (FEAT-030), #114 (FEAT-031), #134 (FEAT-037)

## Связанные заметки в vault

- `vault/plans/feat-036 run-from-workbook.md` — черновик плана, решения пользователя 1–11
- `vault/plans/feat-035 workbook-to-config.md` — контракт перевода
- `vault/knowledge/decisions/перевод книги в конфиг проверяет только книгу — моменты SCHEDULE в целых мс.md`
- `vault/knowledge/decisions/книга ввода Excel версии 1 — все параметры явно, единицы фиксированы.md`
- `vault/plans/feat-030 run-command-from-config.md`
