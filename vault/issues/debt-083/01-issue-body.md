## Описание

Если `--output` (или аргумент `output_dir` функции `run_case`) указывает на существующий **файл** — например, опечаткой названа `well_history.csv` или книга Excel вместо каталога, — расчёт по JSON-конфигу выполняется целиком и только потом падает с трассировкой и кодом 1, как ошибка кода. Расчёт теряется. Нужна проверка до расчёта с понятным сообщением и кодом 2 — как у остальных ошибок аргументов (README пакета, §3.4, «Коды возврата»).

Обнаружено при планировании DEBT-082 (2026-10-18, план DEBT-082 §10).

## Текущее состояние

**Расчёт по конфигу** (`run_case(config.json, файл)`):

1. `_check_inputs_outside` пропускает путь: конфиг и его таблицы не лежат «внутри» файла.
2. `_check_output_free` (DEBT-082) — `if not output_dir.is_dir(): return`: файл для неё — «каталога нет, проверять нечего».
3. Расчёт выполняется полностью.
4. Очистка после расчёта пропускается (`output_dir.is_dir()` — ложь), затем `output_dir.mkdir(parents=True, exist_ok=True)` — `FileExistsError` (errno 17): `exist_ok` не спасает, если по пути лежит файл.
5. Исключение не `CaseConfigError` и не `CaseRunError` → `cli.main` его не ловит → трассировка, код 1. Файлы результатов не записаны.

То же при файле среди **предков** каталога вывода (`--output well_history.csv\sub`): `mkdir(parents=True)` доходит до файла и падает тем же `FileExistsError`.

**Расчёт по книге** (`run_case(книга.xlsx, файл)`): `_translate_workbook` читает и переводит книгу, `_clear_output` файл пропускает, `write_files(output_dir / "input")` → `FileExistsError` → `CaseConfigError`, код 2, расчёт не начат. Здесь только текст невнятный: `…\файл\input: Cannot create a file when that file already exists` — о том, что `--output` указывает на файл, не сказано.

Проба (Python из `.venv` решателя): `vault/issues/debt-083/probes/mkdir_on_file.py`, вывод — `mkdir_on_file.out.txt`:

```
config: FileExistsError errno=17 strerror='Cannot create a file when that file already exists'
book: FileExistsError errno=17 strerror='Cannot create a file when that file already exists' filename='…\not_a_dir.csv'
```

## Целевое состояние

- Путь вывода, который сам или один из предков — файл, отвергается **до расчёта**: `CaseConfigError` с сообщением вида «каталог вывода `<путь>`: `<файл>` — файл, а не каталог. Укажите каталог.» → код 2, stdout пуст, файл не тронут.
- У книги — та же проверка и то же сообщение, до чтения книги (по образцу отказа «каталог вывода содержит книгу»).
- Числа расчёта, истории примеров и прочее поведение `run_case` не меняются.

## Затронутые файлы

Строки — по состоянию после влития DEBT-082.

| Файл | Строки | Роль |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/report/pipeline.py` | 163–170 | проверки до расчёта у конфига: `_check_inputs_outside`, `_check_output_free` — место вызова новой проверки |
| там же | 213–221 | очистка после расчёта и `output_dir.mkdir(...)` — место падения |
| там же | 419–444 | `_check_output_free` (DEBT-082): `if not output_dir.is_dir(): return` |
| там же | 466–504 | `_translate_workbook`: отказ «содержит книгу» (470–475), `write_files` → невнятный `CaseConfigError` (501–504) |
| там же | 62–63, 86–106 | докстринги `CaseConfigError` и `run_case` (публичный интерфейс, FEAT-031) — добавить причину отказа |
| `numerical_solver/gpn_multiphase_solver/cli.py` | 184–197 | `CaseConfigError` → код 2; прочее — трассировка, код 1. Не меняется |
| `numerical_solver/tests/test_output_dir.py` | новый у DEBT-082 | модульные тесты проверки |
| `numerical_solver/tests/test_cli.py` | 171–180 | образец: `test_output_with_config_refused` (запрет `Simulator.run`, код 2) |
| `numerical_solver/tests/test_workbook_run.py` | 140–150 | образец: `test_book_inside_output_refused` |
| `numerical_solver/README.md` | 317–335 | §3.4: отказы до расчёта и коды возврата — одна фраза |
| `numerical_solver/CHANGELOG.md` | 35–37 | «Не выпущено → Исправлено» |

## Анализ вариантов решения

### Вариант 1 — две строки в `_check_output_free` (из реестра)

- **Суть:** в начале `_check_output_free` — `if output_dir.exists() and not output_dir.is_dir(): raise CaseConfigError(...)`.
- **Изменения:** `pipeline.py`, одна функция; тест `run_case(cfg, файл)` с запретом `Simulator.run` и `cli.main` → код 2.
- **Плюсы:** минимум кода, функция уже вызывается до расчёта.
- **Минусы:** не ловит файл среди предков (`файл.csv\sub` — та же трассировка после расчёта); у книги `_check_output_free` не вызывается — невнятное сообщение остаётся; функция о «занятом каталоге» начинает отвечать и за «путь — файл».

### Вариант 2 — отдельная проверка пути, вызов в обоих местах (рекомендуется)

- **Суть:** функция `_check_output_path(output_dir)` — найти первый существующий путь среди `output_dir` и его предков; если он не каталог — `CaseConfigError`. Вызов: у конфига — после `_check_inputs_outside`, перед `_check_output_free`; у книги — в `_translate_workbook` после отказа «содержит книгу», до чтения книги.
- **Изменения:** `pipeline.py` (~10 строк + докстринги), тесты в `test_output_dir.py`, `test_cli.py`, `test_workbook_run.py`; README §3.4, CHANGELOG.
- **Плюсы:** закрывает оба случая (файл и файл-предок) и оба пути (конфиг и книга) одним сообщением; порядок проверок до расчёта сохраняется — каталог с конфигом по-прежнему отвергает `_check_inputs_outside` с прежним текстом (`--output cfg.json` тоже отвергается ею: путь совпадает с входным файлом).
- **Минусы:** на одну функцию больше, чем в варианте 1.

### Вариант 3 — создать каталог вывода до расчёта

- **Суть:** `output_dir.mkdir(parents=True, exist_ok=True)` до расчёта, `OSError` → `CaseConfigError`.
- **Плюсы:** ловит любую причину, по которой каталог не создаётся (права, файл, недопустимое имя).
- **Минусы:** побочное действие до расчёта: при ошибке конфига или отказе решателя остаётся пустой каталог, которого не было; нарушает «расчёт не начат — каталог не изменён» (`test_not_workbook_and_missing` проверяет, что каталог не создан). Отклоняется.

**Рекомендация:** вариант 2.

## План решения

1. **Подготовка.** База — `numerical_scheme/implementation` после влития DEBT-082 (`_check_output_free`, `test_output_dir.py`). Число тестов — `--collect-only`, быстрый уровень зелёный.
2. **Реализация.**
   - `_check_output_path` в `pipeline.py` с докстрингом-ссылкой на DEBT-083; вызовы у конфига и у книги.
   - Тесты (до или вместе с кодом): модульные — файл, файл-предок, несуществующий путь в каталоге, существующий каталог; `cli.main(["run", cfg, "--output", файл])` → код 2, `Simulator.run` запрещён, файл цел, в stderr «не каталог», без `Traceback`; `run_case(книга, файл)` → `CaseConfigError` до чтения книги (`read_workbook` запрещён), файл цел.
   - Докстринги `CaseConfigError` и `run_case`; README §3.4 — одна фраза; CHANGELOG.
3. **Верификация.** Быстрый уровень после каждого шага, полный — в конце. Истории примеров не меняются (правка только в проверках до расчёта).

## Ветка

`refactor/debt-083/output-path-is-file`

## Связанные issues

Related: #138 (DEBT-082 — та же группа проверок каталога вывода до расчёта), #136 (FEAT-036 — расчёт по книге)

## Связанные заметки в vault

- Реестр: `vault/roadmap/известные баги и технический долг.md`, DEBT-083
- План DEBT-082: `vault/plans/debt-082 locked-output-dir.md`, §1 и §10
- Проба: `vault/issues/debt-083/probes/mkdir_on_file.py`
