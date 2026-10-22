---
tags:
  - план
  - инфраструктура
date: 2026-10-18
issue: DEBT-083
github: 139
branch: refactor/debt-083/output-path-is-file
status: реализован
worktree: .worktrees/debt-083; удалён после влития
merged: c4362aa (2026-10-19)
audit:
  date: 2026-10-19
  round: 2
  found: 6
  auto-fixed: 6
  manual-required: 0
---

# DEBT-083: путь вывода — файл — отказ до расчёта, а не трассировка после него

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-083 в `vault/roadmap/известные баги и технический долг.md` и тело issue #139 (`vault/issues/debt-083/01-issue-body.md`; номера строк там — по базе до FEAT-031, верны номера этого плана). Отдельной заметки в `vault/knowledge/` у задачи нет. Ближайшее решение — [[каталог вывода очищается переименованием — занятый каталог не удаляется частично]] (DEBT-082): та же группа проверок каталога вывода до расчёта.
3. Пробы задачи — `vault/issues/debt-083/probes/` (вывод — `*.out.txt` рядом):
   - `mkdir_on_file.py` — `mkdir` на файле и на пути через файл (оба пути `run_case`);
   - `plan_path_checks.py` — `exists()`, `mkdir` и «первый существующий предок» на восьми видах пути;
   - `resolve_through_file.py` — `Path.resolve()` на пути через файл (его зовут `_check_inputs_outside`, отказ «содержит книгу» и `cli.main` до новой проверки): исключений нет, Python 3.13.3;
   - `plan_code/check_output_path.py` — функция шага 1 дословно, на случаях модульных тестов: все утверждения выполнены;
   - `audit_symptom.py` — симптом: `gpn-solver run config.json --output <файл>` в отдельном процессе. Пакет и прототип берёт из дерева, где лежит сам скрипт (подпроцессу — `PYTHONPATH` и `cwd` этого дерева, путь пакета печатается первой строкой): копия в worktree проверяет код worktree. На базе — расчёт выполнен, затем `FileExistsError`, код 1; после реализации — код 2;
   - `plan_emulate.py` — эмуляция шагов 1–2 без правки дерева (аудит 1): пропатченная копия `pipeline.py` подменяет модуль, тесты плана — в копиях трёх тестовых файлов; 77 passed (65 прежних + 7 новых + 5 проверок докстрингов по правилу `tests/test_docs.py`), без правки 7 новых тестов падают. Только до реализации и из основного каталога: правки ищутся в `pipeline.py` базы, пакет — установленный (основного каталога). Команды — в докстринге скрипта; каталог `_emulate/` после разбора удаляется.
4. Worktree и ветка — по `/implement`: база `numerical_scheme/implementation`, ветка `refactor/debt-083/output-path-is-file` (на 2026-10-19 её нет), каталог `.worktrees/debt-083`.
5. Обозначения: `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas`; `<W>` = `<КОРЕНЬ>\.worktrees\debt-083`; `<PY>` = `<КОРЕНЬ>\numerical_solver\.venv\Scripts\python.exe`. Venv один, в основном каталоге, **своего `.venv` в worktree нет**. Все команды — из `<W>\numerical_solver` интерпретатором `<PY>`: pytest берёт пакет worktree (`python -m` кладёт текущий каталог в `sys.path`) и прототип worktree (`pythonpath` в `numerical_solver/pyproject.toml`). Прототип не меняется: его тесты и регрессия не нужны.
6. **Исходная точка** — `ccf740e` (2026-10-19: выпуск 1.0.1 `bd5952b` и начало 1.0.2.dev0 поверх `757b5e2` — влития FEAT-031 `df52b19`; план писался на `650cbbc`). FEAT-031 переписала докстринги `run_case`, `CaseConfigError` в стиле NumPy и перенесла номера задач из них в комментарии над объектами, правила README и `cli.py`; выпуск 1.0.1 изменил только `CHANGELOG.md` (раздел «Не выпущено» теперь пуст) и номер версии в `__init__.py`. Тестовые файлы задачи (`test_output_dir.py`, `test_cli.py`, `test_workbook_run.py`) и тексты блоков «До:» в коде — те же. Номера строк ниже — по `ccf740e` (в коде и README они те же, что на `757b5e2`). Если база снова уехала — сверять по тексту.
7. Baseline:
   ```powershell
   & <PY> -m pytest tests/ --collect-only -q          # 2616 тестов на ccf740e
   & <PY> -m pytest tests/ -m "not slow" -q           # 2331 в быстром уровне
   ```
   Три затронутых файла тестов: `tests/test_output_dir.py tests/test_cli.py tests/test_workbook_run.py -m "not slow"` — 65 passed (~55 с).
8. Начни с шага 1. После каждого шага — тест шага и регресс по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

**Итог по тестам:** +7 (2616 → 2623; быстрый уровень 2331 → 2338 — новые тесты без метки `slow`; тест диска на POSIX собирается и пропускается).

## 1. Задача и границы

**Симптом** (`audit_symptom.out.txt`, база `757b5e2`). `gpn-solver run config.json --output well_history.csv` (опечатка: имя существующего файла вместо каталога) — расчёт выполняется целиком, затем `output_dir.mkdir(parents=True, exist_ok=True)` в `run_case` падает `FileExistsError` (errno 17, WinError 183): `exist_ok` не спасает, если по пути лежит файл. Исключение не `CaseConfigError` и не `CaseRunError`, и `cli.main` его не ловит — трассировка, код 1, результаты не записаны. Расчёт потерян.

**Цель.** Путь вывода, который сам — файл, или проходит через файл, или лежит на несуществующем диске, отвергается **до расчёта**: `CaseConfigError` → код 2, stdout пуст, ничего не создано и не изменено. У расчёта по книге — та же проверка до чтения книги.

**Не меняется:**
- числа расчёта, истории примеров, рисунки — правка только в проверках до расчёта;
- `_check_output_free`, `_clear_output`, `_sibling` (DEBT-082) — без изменений;
- порядок прежних проверок: каталог, содержащий конфиг или книгу, по-прежнему отвергают `_check_inputs_outside` и проверка «содержит книгу» с прежним текстом (`test_run_case_refuses_output_containing_inputs`, `test_output_with_config_refused`, `test_book_inside_output_refused`);
- `cli.py`: код 2 для `CaseConfigError` уже есть; докстринг `main` («2 — ошибка аргументов, файла конфигурации…») и справка `run --help` («2 — ошибка аргументов…») покрывают неверный `--output`;
- прототип `HydroSolverPrototype/`.

**Вне задачи** (§8, DEBT-084): путь с недопустимыми символами (`out<1>`) и каталог без права записи — `mkdir` после расчёта падает `OSError`/`PermissionError`; проверка «первый существующий предок» их не видит.

## 2. Факты

### 2.1. Код на `ccf740e`

`numerical_solver/gpn_multiphase_solver/report/pipeline.py`:

| Строки | Что |
|---|---|
| 1–18 | докстринг модуля (внутренний, номера задач допустимы): последний абзац — DEBT-082 (15–17) |
| 22 | `import os` — уже есть |
| 39–40 | `from ..io.workbook_convert import workbook_to_config, write_files`; `from ..io.xlsx_reader import WorkbookError, read_workbook` — `read_workbook` в пространстве имён модуля, тест подменяет `pipeline.read_workbook` |
| 62–65 | комментарий с номерами задач (62–63) и `class CaseConfigError(ValueError)` — публичный однострочный докстринг (65) |
| 103–110 | комментарий с номерами задач над `run_case`: строка 107 — «расчёта по конфигу — соседний каталог и предупреждение в журнал.» |
| 111–179 | `run_case` и его публичный докстринг NumPy; раздел «Исключения» — 155–165, запись `CaseConfigError` — 159–162 |
| 215–222 | проверки до расчёта у конфига: `_check_inputs_outside` (218), `_check_output_free` (222) |
| 228 | печать заголовка `=== {title} ===` — после всех проверок |
| 265–273 | очистка после расчёта и `output_dir.mkdir(parents=True, exist_ok=True)` (273) — место падения |
| 443–460 | `_sibling`: `Path(os.path.abspath(path))` — не `resolve()` (диск `subst`, сетевой) |
| 463–468 | `_busy_message` |
| 471–496 | `_check_output_free`: `if not output_dir.is_dir(): return` (481–482) — файл для неё «каталога нет» |
| 518–556 | `_translate_workbook`: отказ «содержит книгу» (522–527), чтение книги (528–538), `_clear_output` (547–552), `write_files(output_dir / INPUT_DIR, …)` (553–556) |

`numerical_solver/gpn_multiphase_solver/cli.py`: пути `config` и `output` — `resolve()` (223–224); `except CaseConfigError` → «Ошибка конфига/книги: …», код 2 (227–); прочее — трассировка, код 1.

**Правило публичных докстрингов** (FEAT-031, `tests/test_docs.py`, `test_public_docstring`): объекты `doc/source/api.rst` — в том числе `run_case`, `CaseResult`, `CaseConfigError`, `CaseRunError` — проверяются по D1–D7; **D6 — без ID задач (`BUG/DEBT/FEAT/VAL-NNN`) и путей `vault/`**. Номера задач — в комментарии над объектом. Внутренние функции (`_check_output_path` и др.) и докстринг модуля `pipeline` под правило не попадают.

### 2.2. Пробы

`mkdir_on_file.out.txt` — оба пути `run_case`:
```
config: FileExistsError errno=17 strerror='Cannot create a file when that file already exists'
book: FileExistsError errno=17 strerror='Cannot create a file when that file already exists' filename='…\not_a_dir.csv'
```
У книги `FileExistsError` ловится в `_translate_workbook` (553–556) → `CaseConfigError` «`…\файл\input: Cannot create a file when that file already exists`», код 2, до расчёта, но книга уже прочитана, а причина не названа.

`plan_path_checks.out.txt` (Windows 10, Python venv проекта):

| Путь | `exists()` | Первый существующий среди пути и предков | `mkdir(parents=True, exist_ok=True)` |
|---|---|---|---|
| файл | True | сам файл (не каталог) | `FileExistsError` 17 / WinError 183 |
| `файл\sub`, `файл\a\b` | False | файл (не каталог) | `FileExistsError` 17 / WinError 183 |
| нет пути, предок — каталог | False | каталог | создан |
| существующий каталог | True | он же | проходит |
| `Q:\out`, диска нет | False | **нет** (`None`) | `FileNotFoundError` 2 / WinError 3 |
| `out<1>` | False | каталог | `OSError` 22 / WinError 123 — вне задачи |
| относительный | False | каталог (абсолютный путь от текущего) | — |

`exists()` исключений не бросает: «путь не найден» и «недопустимое имя» Python гасит и возвращает False. `resolve()` на пути через файл тоже проходит (`resolve_through_file.out.txt`).

### 2.3. Тесты, которые касаются затронутого кода

| Файл | Тесты | Что держат |
|---|---|---|
| `tests/test_output_dir.py` | 15 тестов DEBT-082 | `_check_output_free`, `_clear_output`, `_sibling`, `run_case` при занятом каталоге |
| `tests/test_cli.py` | `test_output_with_config_refused` (172), `test_busy_output_returns_2` (184) | код 2 до расчёта |
| `tests/test_workbook_run.py` | `test_book_inside_output_refused` (141), `test_not_workbook_and_missing` (165: каталог вывода не создан), `test_locked_output_file_refused` (203) | порядок проверок у книги, «ничего не создано» |
| `tests/test_examples.py` | `test_run_case_refuses_output_containing_inputs` (791), `test_run_case_config_errors` (812: stdout пуст при ошибке) | отказы до расчёта у конфига |
| `tests/test_docs.py` | `test_public_docstring[…report.pipeline.run_case]`, `[…CaseConfigError]` | правило D1–D7 для докстрингов, которые правит шаг 2 |
| `tests/test_docs.py` | `test_docs_build_without_warnings` (метка `slow`, ~11 с) | сборка HTML-документации, в которую входит README (шаг 3) |

Все тесты каталога вывода передают каталог или несуществующий путь внутри каталога — новая проверка их пропускает.

## 3. Варианты

| | Суть | Плюсы | Минусы |
|---|---|---|---|
| **1** | В начале `_check_output_free`: `if output_dir.exists() and not output_dir.is_dir(): raise` | две строки | не ловит путь через файл (`файл\sub` — та же трассировка после расчёта) и нет диска; у книги `_check_output_free` не вызывается — невнятный текст остаётся; функция о занятом каталоге отвечает ещё и за вид пути |
| **2** ✅ | Отдельная `_check_output_path`: первый существующий путь среди `output_dir` и его предков должен быть каталогом; вызов у конфига (до `_check_output_free`) и у книги (до чтения) | оба случая (файл и путь через файл) и диск — одной проверкой; оба пути `run_case` — одним текстом; ничего не создаёт | на одну функцию больше |
| 3 | `output_dir.mkdir(...)` до расчёта, `OSError` → `CaseConfigError` | ловит любую причину, в том числе права и недопустимое имя | создаёт каталог до расчёта: при ошибке конфига или отказе решателя остаётся пустой каталог, которого не было; ломает `test_not_workbook_and_missing` («каталог вывода не создан») |

Выбран **вариант 2** (рекомендован в issue #139). Критерии DEBT: diff небольшой (~30 строк кода и комментариев), каждый шаг зелёный, внешний интерфейс не меняется (`run_case` бросает тот же `CaseConfigError`, теперь раньше), функция тестируется отдельно.

## 4. Целевое состояние

- Новая функция `_check_output_path(output_dir)` в `pipeline.py`, рядом с `_check_output_free`.
- Тексты отказа (проба `plan_code/check_output_path.out.txt`):
  - путь — файл: `каталог вывода <путь> — файл, а не каталог. Укажите другой каталог вывода. Расчёт не начат.`
  - путь через файл: `каталог вывода <путь> не создать: <файл> — файл, а не каталог. Укажите другой каталог вывода. Расчёт не начат.`
  - нет диска: `каталог вывода <путь>: диск <корень> не найден. Укажите другой каталог вывода. Расчёт не начат.`
- Команда печатает их с префиксом `Ошибка конфига: ` / `Ошибка книги: ` (`cli.main`), код 2.
- Порядок проверок до расчёта у конфига: `load_config` → `_check_inputs_outside` → **`_check_output_path`** → `_check_output_free`. У книги: «содержит книгу» → **`_check_output_path`** → чтение книги → `_clear_output` → `write_files`.

## 5. Шаги

### Шаг 1: функция `_check_output_path` и её модульные тесты

**Цель:** в `pipeline.py` есть `_check_output_path` с четырьмя модульными тестами; `run_case` её пока не вызывает.

**Файлы:** `numerical_solver/gpn_multiphase_solver/report/pipeline.py`, `numerical_solver/tests/test_output_dir.py`.

**Контекст:** `mkdir(parents=True, exist_ok=True)` падает, если первый существующий путь среди `output_dir` и его предков — не каталог: сам файл или файл на месте одного из каталогов пути (`plan_path_checks.out.txt`). Если не существует ни один, нет даже корня — диска нет, `mkdir` падает `FileNotFoundError`. Значит, достаточно найти этот путь и проверить, что он каталог: ничего не создаётся. `abspath`, а не `resolve()` — как в `_sibling` (DEBT-082, аудит 1): на диске `subst` и сетевом `resolve()` подменил бы букву диска, и сообщение назвало бы путь, которого инженер не вводил. Функция внутренняя: однострочный докстринг с номером задачи, как у соседних `_check_output_free`, `_clear_output`.

**Что сделать (сначала тесты, потом код):**

1. В `tests/test_output_dir.py` — новый раздел после `test_clear_trash_left_warns` (кончается строкой 162), перед декоратором `@contextlib.contextmanager` функции `_hold_open_file` (строка 165):

   ```python
   # ── Путь вывода — файл (DEBT-083) ────────────────────────────

   def test_output_path_file_refused(tmp_path):
       """Путь вывода — существующий файл: CaseConfigError «файл, а не каталог» с путём, файл не тронут."""
       f = tmp_path / "well_history.csv"
       f.write_text("1", encoding="utf-8")
       with pytest.raises(CaseConfigError, match="файл, а не каталог") as e:
           pipeline._check_output_path(f)
       assert str(f) in str(e.value) and "Расчёт не начат" in str(e.value)
       assert f.read_text(encoding="utf-8") == "1"


   def test_output_path_under_file_refused(tmp_path):
       """Файл на месте каталога пути (well_history.csv\\sub, …\\a\\b): отказ называет этот файл; ничего не создано.

       mkdir(parents=True) на таком пути падает тем же FileExistsError, что и
       на самом файле (проба plan_path_checks.py DEBT-083), — после расчёта.
       """
       f = tmp_path / "well_history.csv"
       f.write_text("1", encoding="utf-8")
       for out in (f / "sub", f / "a" / "b"):
           with pytest.raises(CaseConfigError, match="файл, а не каталог") as e:
               pipeline._check_output_path(out)
           assert f"{out} не создать: {f}" in str(e.value)
       assert _names(tmp_path) == ["well_history.csv"]


   def test_output_path_dir_or_missing_passes(tmp_path):
       """Существующий каталог и несуществующий путь внутри каталога проходят; проверка ничего не создаёт и не меняет."""
       out = _old_output(tmp_path)
       for p in (out, tmp_path / "new" / "out"):
           pipeline._check_output_path(p)
       assert _names(tmp_path) == ["out"] and _names(out) == OLD_FILES


   @pytest.mark.skipif(sys.platform != "win32", reason="буквы дисков — только Windows")
   def test_output_path_missing_drive_refused():
       """Диска нет (Q:\\out): ни одного существующего предка — отказ «диск … не найден»; mkdir после расчёта упал бы FileNotFoundError."""
       free = [d for d in "QRSTUVWXYZ" if not Path(f"{d}:\\").exists()]
       if not free:
           pytest.skip("все буквы дисков Q…Z заняты")
       with pytest.raises(CaseConfigError, match="не найден"):
           pipeline._check_output_path(Path(f"{free[0]}:\\out"))
   ```

   `sys`, `Path`, `pytest`, `pipeline`, `CaseConfigError`, `_names`, `_old_output`, `OLD_FILES` в модуле уже есть (строки 27–53).

2. Запустить: `& <PY> -m pytest tests/test_output_dir.py -q -k output_path` — 4 падения `AttributeError: … has no attribute '_check_output_path'` (проверено эмуляцией).

3. В `pipeline.py` — функция перед `def _check_output_free` (строка 471), после `_busy_message`:

   ```python
   def _check_output_path(output_dir: Path) -> None:
       """Путь вывода годится под каталог: первый существующий среди него и его предков — каталог, иначе CaseConfigError. DEBT-083."""
       # Опечатка в --output (имя CSV или книги вместо каталога) обнаруживалась
       # только после расчёта: mkdir на файле падает FileExistsError даже с
       # exist_ok, на пути через файл (well_history.csv\sub) — тоже, на
       # несуществующем диске — FileNotFoundError (пробы DEBT-083,
       # vault/issues/debt-083/probes/). Проверка ничего не создаёт. abspath, а
       # не resolve, — как в _sibling: диск subst и сетевой остаются собой
       path = Path(os.path.abspath(output_dir))
       existing = next((p for p in (path, *path.parents) if p.exists()), None)
       if existing is None:
           raise CaseConfigError(
               f"каталог вывода {path}: диск {path.anchor} не найден. Укажите "
               f"другой каталог вывода. Расчёт не начат.")
       if not existing.is_dir():
           head = (f"каталог вывода {path}" if existing == path
                   else f"каталог вывода {path} не создать: {existing}")
           raise CaseConfigError(
               f"{head} — файл, а не каталог. Укажите другой каталог вывода. "
               f"Расчёт не начат.")
   ```

   Текст функции совпадает с `vault/issues/debt-083/probes/plan_code/check_output_path.py` и `plan_emulate.py`.

4. Обновить докстринг модуля `tests/test_output_dir.py`: заголовок `(DEBT-082).` → `(DEBT-082, DEBT-083).`; в список «Проверяется» после пункта о функциях (кончается строкой `    имя, неудача удаления переименованного каталога;`) добавить:
   ```
     - _check_output_path (DEBT-083): путь вывода — файл, путь через файл,
       нет диска — CaseConfigError; каталог и несуществующий путь внутри
       каталога проходят, ничего не создаётся;
   ```

**Проверка после шага:**
- `& <PY> -m pytest tests/test_output_dir.py -q` — 19 passed (15 + 4).
- Регресс: быстрый (`-m "not slow"`), ожидание 2335 passed (2331 + 4).

**Подводные камни:** §6, пп. 1, 3.

**Зависимости:** блокирует шаг 2.

**Оценка:** ~20 строк кода, ~45 строк тестов, ~10 минут.

### Шаг 2: вызовы у конфига и у книги, докстринги, тесты отказа через `run_case` и команду

**Цель:** `run_case` отвергает путь вывода — файл до расчёта (конфиг) и до чтения книги (книга); три теста держат это через `run_case` и `cli.main`; публичные докстринги называют новую причину `CaseConfigError`.

**Файлы:** `numerical_solver/gpn_multiphase_solver/report/pipeline.py`, `numerical_solver/tests/test_output_dir.py`, `numerical_solver/tests/test_cli.py`, `numerical_solver/tests/test_workbook_run.py`.

**Контекст:** у конфига проверки до расчёта стоят после `load_config` (строки 215–222): `_check_inputs_outside` нужен прочитанный конфиг (пути таблиц). Новую проверку ставим между ней и `_check_output_free`: тогда `--output` = папка конфига по-прежнему отвергается первой с текстом «содержит входной файл» (`--output cfg.json` — тоже ею: путь равен входному файлу). У книги очистка каталога вывода — до расчёта, в `_translate_workbook`; проверку ставим после отказа «содержит книгу» и до чтения книги — по образцу этого отказа: книгу не читаем зря, а невнятный `FileExistsError` в `write_files` (553–556) через файл на пути больше не достижим. Докстринги `run_case` и `CaseConfigError` — публичные (FEAT-031, §2.1): номер задачи в них запрещён правилом D6, он идёт в комментарий над объектом.

**Что сделать (сначала тесты, потом код):**

1. `tests/test_output_dir.py` — в конец файла (после `test_run_case_free_output_cleared`, строка 298):

   ```python
   def test_run_case_output_file_refused_before_run(tmp_path, monkeypatch, capsys):
       """Каталог вывода — файл или путь через файл: CaseConfigError до расчёта и до печати заголовка, файл цел (DEBT-083).

       Без проверки расчёт шёл целиком, а потом mkdir падал FileExistsError —
       трассировка, код 1, расчёт потерян. Simulator.run подменён на падение:
       отказ обязан прийти раньше расчёта.
       """
       # Своя подмена, а не _must_not_run модуля: её текст — о занятом каталоге
       def must_not_run(self, *args, **kwargs):
           raise AssertionError("расчёт начат при каталоге вывода — файле")
       monkeypatch.setattr(Simulator, "run", must_not_run)
       cfg = _small_case(tmp_path)
       f = tmp_path / "well_history.csv"
       f.write_text("1", encoding="utf-8")
       for out in (f, f / "sub"):
           with pytest.raises(CaseConfigError, match="файл, а не каталог"):
               run_case(cfg, out)
       assert capsys.readouterr().out == ""
       assert f.read_text(encoding="utf-8") == "1"
   ```

2. `tests/test_cli.py` — после `test_busy_output_returns_2` (кончается строкой 210), перед `# ── Аргументы` (213):

   ```python
   def test_output_file_returns_2(tmp_path, capsys, monkeypatch):
       """--output — существующий файл (имя CSV вместо каталога) → код 2 до расчёта, файл цел (DEBT-083).

       Раньше расчёт шёл целиком, затем mkdir падал FileExistsError:
       трассировка и код 1, расчёт потерян.
       """
       def must_not_run(self, *args, **kwargs):
           raise AssertionError("расчёт начат при --output, указывающем на файл")
       monkeypatch.setattr(Simulator, "run", must_not_run)

       cfg = _small_case(tmp_path)
       f = tmp_path / "well_history.csv"
       f.write_text("1", encoding="utf-8")
       assert cli.main(["run", str(cfg), "--output", str(f)]) == 2
       err = capsys.readouterr().err
       # cli.main передаёт run_case путь после resolve(); abspath его не меняет
       assert "файл, а не каталог" in err and str(f.resolve()) in err
       assert f.read_text(encoding="utf-8") == "1"
   ```

   В докстринге модуля после строки `    занятый каталог вывода — тоже 2 до расчёта (DEBT-082),` добавить строку `    путь --output — файл — тоже 2 до расчёта (DEBT-083),`.

3. `tests/test_workbook_run.py` — после `test_locked_output_file_refused` (кончается строкой 226), перед `test_config_run_clears_output_after_run` (229):

   ```python
   def test_output_file_refused_before_reading_book(tmp_path, monkeypatch):
       """Каталог вывода — файл или путь через файл: отказ «файл, а не каталог» до чтения книги, файл цел (DEBT-083).

       Без проверки книга читалась и переводилась, а write_files падал
       FileExistsError — «…\\input: Cannot create a file when that file
       already exists», о файле вместо каталога ни слова.
       """
       monkeypatch.setattr(Simulator, "run", _must_not_run)

       def must_not_read(*args, **kwargs):
           raise AssertionError("книга прочитана, хотя каталог вывода — файл")
       monkeypatch.setattr(pipeline, "read_workbook", must_not_read)
       book = _small_book(tmp_path / "b.xlsx")
       f = tmp_path / "прошлый.csv"
       f.write_text("1", encoding="utf-8")
       for out in (f, f / "sub"):
           with pytest.raises(CaseConfigError, match="файл, а не каталог"):
               run_case(book, out)
       assert f.read_text(encoding="utf-8") == "1"
   ```

   В докстринге модуля после строки `    не изменён (аудит 1, DEBT-082);` добавить:
   ```
     - каталог вывода — файл или путь через файл — отказ до чтения книги,
       файл цел (DEBT-083);
   ```

4. Запустить три теста — падают (проверено эмуляцией): первый и второй — `AssertionError` «расчёт начат…» (проверки нет, `Simulator.run` вызван), третий — `AssertionError` «книга прочитана…».

5. `pipeline.py`, `run_case`, строки 215–222 — **до:**
   ```python
       if workbook is None:
           # Перевод книги лежит в output/input/ по замыслу; саму книгу
           # проверил _translate_workbook
           _check_inputs_outside(config_path, config, output_dir)
           # Занятый каталог вывода (файл открыт в Excel, консоль в каталоге) —
           # отказ до расчёта, а не трассировка после него (DEBT-082). У книги
           # каталог уже очищен в _translate_workbook
           _check_output_free(output_dir)
   ```
   **после:**
   ```python
       if workbook is None:
           # Перевод книги лежит в output/input/ по замыслу; саму книгу
           # проверил _translate_workbook
           _check_inputs_outside(config_path, config, output_dir)
           # Путь вывода — файл или проходит через файл (опечатка в --output),
           # диска нет — отказ до расчёта, а не FileExistsError после него
           # (DEBT-083). У книги проверено в _translate_workbook
           _check_output_path(output_dir)
           # Занятый каталог вывода (файл открыт в Excel, консоль в каталоге) —
           # отказ до расчёта, а не трассировка после него (DEBT-082). У книги
           # каталог уже очищен в _translate_workbook
           _check_output_free(output_dir)
   ```

6. `pipeline.py`, `_translate_workbook`, после блока отказа «содержит книгу» (строки 522–527, кончается `f"другой каталог вывода.")`) и перед комментарием `# Перевод в памяти — до очистки…` (528) вставить:
   ```python
       # Путь вывода — файл или проходит через файл, диска нет: отказ до чтения
       # книги (DEBT-083); иначе write_files ниже падал FileExistsError с
       # текстом, не называющим причину
       _check_output_path(output_dir)
   ```

7. Докстринги и комментарии `pipeline.py` (тексты проверены эмуляцией: `test_public_docstring` для четырёх объектов `pipeline` из `api.rst` — без нарушений):
   - Комментарий над `CaseConfigError`, строка 63 — **до:** `# книга — FEAT-036` **после:** `# книга — FEAT-036; путь вывода — файл или нет диска — DEBT-083`.
   - Докстринг `CaseConfigError` (строка 65) — **до:**
     `"""Ошибка входа расчёта: конфигурация, таблицы или книга не читаются или не проходят проверку, каталог результатов занят; расчёт не начат."""`
     **после:**
     `"""Ошибка входа расчёта: конфигурация, таблицы или книга не читаются или не проходят проверку, каталог результатов занят, на его пути файл или нет диска; расчёт не начат."""`
   - Комментарий над `run_case`, строка 107 — **до:** `# расчёта по конфигу — соседний каталог и предупреждение в журнал.` **после** (три строки вместо одной):
     ```python
     # расчёта по конфигу — соседний каталог и предупреждение в журнал. Путь
     # вывода — файл, путь через файл или нет диска (DEBT-083): отказ до расчёта,
     # у книги — до её чтения.
     ```
   - Докстринг `run_case`, раздел «Исключения», запись `CaseConfigError` (строки 160–162) — **до:**
     ```
             Ошибка файла конфигурации, таблиц или книги; входные файлы внутри
             каталога результатов; каталог результатов занят другой программой.
             Расчёт не начат.
     ```
     **после:**
     ```
             Ошибка файла конфигурации, таблиц или книги; входные файлы внутри
             каталога результатов; каталог результатов занят другой программой;
             путь каталога результатов — файл, проходит через файл или ведёт на
             несуществующий диск. Расчёт не начат.
     ```
   - Докстринг модуля (внутренний), после абзаца DEBT-082 (кончается строкой `каталоге с датой и временем в имени.`, 17) — новый абзац перед закрывающими кавычками:
     ```

     Путь вывода — файл, путь через файл или несуществующий диск (DEBT-083) —
     отказ до расчёта, у книги — до её чтения.
     ```

**Проверка после шага:**
- `& <PY> -m pytest tests/test_output_dir.py tests/test_cli.py tests/test_workbook_run.py tests/test_examples.py -q -m "not slow"` — все passed; среди них прежние отказы до расчёта (`test_run_case_refuses_output_containing_inputs`, `test_output_with_config_refused`, `test_book_inside_output_refused`, `test_not_workbook_and_missing`) с прежними текстами.
- `& <PY> -m pytest tests/test_docs.py -q -k "public_docstring and pipeline"` — 4 passed (правило D1–D7, в том числе D6 — без номеров задач).
- Регресс: быстрый, ожидание 2338 passed (2331 + 7).

**Подводные камни:** §6, пп. 2, 4, 5.

**Зависимости:** требует шаг 1; блокирует шаг 3.

**Оценка:** ~25 строк кода, комментариев и докстрингов, ~55 строк тестов, ~15 минут.

### Шаг 3: README пакета и журнал изменений

**Цель:** инженер знает, что путь `--output` — файл отвергается до расчёта.

**Файлы:** `numerical_solver/README.md`, `numerical_solver/CHANGELOG.md`.

**Контекст:** README §3.4 перечисляет отказы до расчёта во врезке (строки 368–380); §3.6 (книга) отсылает к кодам возврата §3.4. Строка кодов возврата (382–386) не меняется: «2 — ошибка в аргументах…» покрывает неверный `--output`. README §4 (542–546) называет `CaseConfigError` обобщённо, README примеров (`examples/README.md`, 287–295) отсылает к §3.4 и не перечисляет все отказы, справка `run --help` (`cli.py`, 92–103) говорит «ошибка аргументов» — не трогаем. README входит в HTML-документацию (FEAT-031): после правки — сборка без предупреждений.

**Что сделать:**

1. `numerical_solver/README.md`, врезка §3.4 — **до** (строки 370–372):
   ```
   > другие файлы. Если внутри каталога вывода находится сам файл конфигурации
   > или его таблицы CSV, команда завершается с ошибкой ещё до расчёта.
   > При расчёте по книге Excel каталог очищается до расчёта (3.6).
   ```
   **после:**
   ```
   > другие файлы. Если внутри каталога вывода находится сам файл конфигурации
   > или его таблицы CSV, команда завершается с ошибкой ещё до расчёта.
   > Так же до расчёта отвергается путь `--output`, по которому лежит файл
   > (например, `well_history.csv` вместо каталога) или который проходит
   > через файл, и путь на несуществующем диске — и при расчёте по книге.
   > При расчёте по книге Excel каталог очищается до расчёта (3.6).
   ```

2. `numerical_solver/CHANGELOG.md`: на `ccf740e` раздел «Не выпущено» пуст — выпуск 1.0.1 перенёс прежние пункты в свой раздел. **До** (строки 35–37):
   ```
   ## Не выпущено

   ## 1.0.1 — 2026-10-19
   ```
   **После:**
   ```
   ## Не выпущено

   ### Исправлено

   - Путь `--output`, по которому лежит файл (например, `well_history.csv`
     вместо каталога) или который проходит через файл, а также путь на
     несуществующем диске — ошибка до расчёта (код 2) с указанием файла.
     Прежде расчёт по файлу конфигурации выполнялся целиком и завершался
     трассировкой (код 1) без записи результатов, а при расчёте по книге
     сообщение не называло причину.

   ## 1.0.1 — 2026-10-19
   ```
   Если к началу реализации в «Не выпущено» уже есть пункты другой задачи — пункт DEBT-083 в конец подраздела «Исправлено» (создать его, если нет; порядок подразделов — «Добавлено», «Изменено», «Исправлено», «Удалено», строки 31–32 журнала). Пункт — только в «Не выпущено», не в раздел выпуска.

**Проверка после шага:** Регресс: только документы —
- `& <PY> -m pytest tests/ --collect-only -q` — 2623;
- `& <PY> -m pytest tests/test_docs.py -q -k build` — сборка HTML-документации без предупреждений (~11 с; тест с меткой `slow`, в быстрый уровень не входит);
- `& <PY> -m pytest tests/test_eq_references.py -q` — сторож ссылок (докстринги, тесты, README примеров).

**Зависимости:** требует шаг 2.

**Оценка:** ~12 строк, ~5 минут.

### Завершение (`/implement`)

- Полный прогон: `& <PY> -m pytest tests/ -q` — 2623 собрано, все passed, кроме прежних пропусков (тест диска на Windows выполняется).
- Vault (отдельный коммит):
  - заметка [[каталог вывода очищается переименованием — занятый каталог не удаляется частично]]: в «Правило» — пункт «`_check_output_path` (DEBT-083) — до проверки занятости: путь вывода — файл, путь через файл, нет диска — `CaseConfigError`, код 2; у книги — до чтения»; в «Связи» строку DEBT-083 заменить на «[[DEBT-083]] — путь вывода — файл: отказ до расчёта, `_check_output_path`»;
  - реестр — статус DEBT-083, итог;
  - `vault/issues/debt-083/05-comment-done.md` — комментарий в #139;
  - `vault/issues/debt-083/probes/_emulate/` удалить, если остался.

## 6. Подводные камни (чеклист 2.5)

| # | Пункт | Оценка |
|---|---|---|
| 1 | **Все места вызова.** `_check_output_path` новая; вызовов два (`run_case` у конфига, `_translate_workbook`). `run_case` вызывают `cli.main`, `examples/*/main.py` (01, 02, 05, 18) и тесты — интерфейс не меняется | ✅ |
| 2 | **Порядок проверок.** Новая проверка — после `_check_inputs_outside` и «содержит книгу»: прежние отказы с прежним текстом (`--output` = папка конфига, `--output cfg.json`, книга внутри каталога). Обе прежние проверки и `cli.main` зовут `resolve()` на пути вывода раньше новой: на пути через файл он не бросает исключений (`resolve_through_file.out.txt`). Перед `_check_output_free`: та на файле молча возвращается, поэтому порядок с ней на результат не влияет, но вид пути логично проверить раньше занятости | ✅ |
| 3 | **Состояние при ошибке.** Проверка только читает (`exists`, `is_dir`) — ничего не создаёт и не меняет; `test_output_path_dir_or_missing_passes` и `test_not_workbook_and_missing` держат «ничего не создано» | ✅ |
| 4 | **Существующие тесты.** Все передают каталог или несуществующий путь внутри каталога (§2.3) — проверка проходит; эмуляция: 65 прежних тестов трёх файлов зелёные. stdout пуст при отказе: проверка до печати заголовка (строка 228) | ✅ |
| 5 | **Публичные докстринги (FEAT-031).** `run_case` и `CaseConfigError` в `doc/source/api.rst`; правило D6 `tests/test_docs.py` запрещает в них номера задач — номер только в комментарии над объектом (шаг 2, п. 7). Первая строка докстринга `CaseConfigError` кончается точкой (D1) | ⚠️ адресовано, проверено эмуляцией |
| 6 | **`CHANGELOG.md` и выпуски.** Выпуск 1.0.1 (`bd5952b`) вышел во время аудита 1–2 и оставил «Не выпущено» пустым — шаг 3 даёт точные «До/После» по `ccf740e`. Другие задачи, влитые раньше DEBT-083, могут дописать в «Не выпущено» — тогда при `/merge` конфликт в журнале: оставить оба пункта. Если до влития выйдет следующий выпуск — пункт DEBT-083 должен оказаться в новом «Не выпущено», а не в разделе выпуска. Незакоммиченных правок журнала в основном каталоге на 2026-10-19 (после выпуска) нет | ⚠️ к `/merge` |
| 7 | **ОС.** Модульные тесты, кроме теста диска, от ОС не зависят: `Path.exists()` на пути через файл возвращает False и на Windows (WinError 3), и на POSIX (ENOTDIR). Тест диска — только Windows: на POSIX корень `/` существует всегда | ✅ |
| 8 | **Диск `subst` и сетевой.** `abspath` не раскрывает букву диска (как `_sibling`); `exists()` на сетевом пути работает. Недоступный сетевой ресурс `\\server\share\out` — корень не существует → «диск `\\server\share\` не найден»: текст понятен | ✅ |
| 9 | Зависимости пакета, циклы импорта, конфиги, производительность | не меняются: новых импортов нет (`os`, `Path` уже импортированы), проверка — несколько `stat` до расчёта | ✅ |
| 10 | Прототип | не меняется | ✅ |
| 11 | Ссылки на уравнения | формул нет; сторож `test_eq_references.py` — в проверке шага 3 | ✅ |
| 12 | **HTML-документация.** README и публичные докстринги входят в сборку Sphinx с `-W`; тест сборки помечен `slow` — явный запуск в проверке шага 3 и в полном прогоне | ✅ |

## 7. Критерии завершения

- [ ] Шаги 1–3 выполнены.
- [ ] Тесты: 2623 собрано; быстрый уровень 2338 passed; полный прогон зелёный.
- [ ] `gpn-solver run config.json --output <файл>` — код 2, «Ошибка конфига: каталог вывода … — файл, а не каталог…», расчёт не начат, файл не изменён (`test_output_file_returns_2`; повтор в отдельном процессе: `& <PY> <W>\vault\issues\debt-083\probes\audit_symptom.py` — первая строка `пакет: <W>\numerical_solver\…`, код 2 вместо 1).
- [ ] У книги — тот же отказ до чтения книги (`test_output_file_refused_before_reading_book`).
- [ ] Прежние отказы до расчёта — с прежними текстами (тесты §2.3 зелёные без правок).
- [ ] Публичные докстринги без номеров задач (`test_public_docstring`), документация собирается без предупреждений.
- [ ] README §3.4 и CHANGELOG дополнены.
- [ ] Vault: заметка DEBT-082 дополнена, реестр обновлён, комментарий в #139.

## 8. Обнаруженные проблемы

- **DEBT-084** (зарегистрирована при планировании, без issue): каталог вывода, который не создаётся по другим причинам, — та же трассировка после расчёта. Путь с недопустимыми символами (`out<1>`) — `mkdir` падает `OSError` errno 22 / WinError 123 (проба `plan_path_checks.out.txt`); каталог без права записи (например, в `C:\Program Files`) — `PermissionError`. Проверка DEBT-083 их не видит: первый существующий предок — каталог. Не блокирует DEBT-083.
- Замечание без регистрации: отказы из-за каталога вывода команда печатает с префиксом «Ошибка конфига: …», хотя конфиг верен (так же у занятого каталога DEBT-082) — префикс задаёт `cli.main` по виду входа. На решение пользователя.

## 9. Аудит 1 (2026-10-19)

База уехала с `650cbbc` на `757b5e2` (влита FEAT-031). Найдено 7 (🔴1 🟡4 🔵2), исправлено 7:

- 🔴 Шаг 2, п. 7: докстринги `run_case` и `CaseConfigError` переписаны FEAT-031 в стиле NumPy — блоки «До:» не совпадали; блоки «После:» вносили «DEBT-083» в публичные докстринги — правило D6 `tests/test_docs.py` (`test_public_docstring`) упало бы. Новые тексты без номеров задач, номер — в комментариях над объектами; эмуляция — правило D1–D7 выполнено.
- 🟡 Baseline: 2477/2193 → 2616/2331, ожидание 2484/2200 → 2623/2338, исходная точка `757b5e2`.
- 🟡 Номера строк: `pipeline.py` +52, `cli.py` +38, README +51; тексты блоков «До:» в коде совпадают (эмуляция нашла каждую привязку ровно один раз).
- 🟡 §6, пп. 5–6: прежний пункт о FEAT-031 снят (влита); новый риск — незакоммиченный `CHANGELOG.md` другой сессии в основном каталоге и возможный выпуск 1.0.1 до влития: шаг 3 привязан к тексту.
- 🟡 Шаг 3: README входит в HTML-документацию (FEAT-031), тест сборки помечен `slow` — добавлен явный запуск (~11 с).
- 🔵 Шаг 2: докстринг модуля `pipeline` и комментарий над `run_case` (куда FEAT-031 перенесла номера задач) дополнены строкой DEBT-083.
- 🔵 «Как начать»: пробы `audit_symptom.py` (симптом на `757b5e2` в отдельном процессе: расчёт, затем `FileExistsError`, код 1) и `plan_emulate.py` (77 passed с правкой; без правки 7 новых тестов падают).
Проверено без находок: голый импорт `gpn_multiphase_solver` и `radial_blackoil` из постороннего каталога без `PYTHONPATH` (установка editable) — эмуляция проверяет тот же сценарий, что и `/implement`; симптом воспроизводится на `757b5e2`; все 7 новых тестов падают без правки и проходят с ней.

## 10. Аудит 2 (2026-10-19) — реализуемость

База уехала с `757b5e2` на `ccf740e` (выпуск 1.0.1: только `CHANGELOG.md` и номер версии). Найдено 6 (🟡1 🔵5), исправлено 6:

- 🟡 Критерий завершения «повтор `audit_symptom.py` даёт код 2» в worktree проверил бы не тот код: подпроцесс пробы не задавал ни `PYTHONPATH`, ни `cwd` и взял бы установленный пакет основного каталога — код 1 при исправленном worktree. Проба переписана: пакет и прототип — из дерева, где лежит скрипт, путь пакета печатается; критерий — команда из `<W>` с проверкой строки `пакет:`.
- 🔵 Шаг 3: «Не выпущено» после выпуска 1.0.1 пуст — вместо условной инструкции точные «До/После» по `ccf740e`; §6, п. 6 обновлён (незакоммиченной правки журнала больше нет). Исходная точка и baseline — `ccf740e` (2616 / 2331, без изменений).
- 🔵 Шаг 2, `test_run_case_output_file_refused_before_run`: подмена `_must_not_run` модуля сообщила бы «расчёт начат при занятом каталоге вывода» — своя подмена с верным текстом (эмуляция повторена: 77 passed).
- 🔵 Шаг 3: явное поле «Регресс: только документы».
- 🔵 «Как начать»: `plan_emulate.py` — только до реализации и из основного каталога.
- 🔵 `vault/00-home/index.md`: строка плана после аудита 1 называла базу `650cbbc` и 2477 → 2484 тестов.

Проверено без находок: якоря правок в `pipeline.py` уникальны (каждая однострочная привязка шага 2 встречается один раз); фильтр `-k "public_docstring and pipeline"` выбирает 4 теста; имена новых тестов не заняты; сторож `test_eq_references.py` новым текстам не мешает (в них нет «eq. N», «ур. N», «.tex:N»); тестов, перечисляющих функции модуля, нет — неиспользуемая после шага 1 функция ничего не ломает; сигнатура `_check_output_path(output_dir: Path)` совпадает с типом в обоих местах вызова (`Path` после строк 194 и 213); `Path.exists()` в Python 3.13 — та же логика, что в 3.10–3.12 (`_ignore_error`), поведение одинаково на всём диапазоне `requires-python >= 3.10`.
