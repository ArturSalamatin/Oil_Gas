---
tags:
  - план
  - инфраструктура
date: 2026-10-18
issue: DEBT-082
github: 138
branch: refactor/debt-082/locked-output-dir
status: реализован
worktree: .worktrees/debt-082
audit:
  date: 2026-10-18
  round: 1
  found: 6
  auto-fixed: 6
  manual-required: 0
---

# DEBT-082: очистка каталога вывода переименованием — занятый каталог не удаляется частично

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-082 в `vault/roadmap/известные баги и технический долг.md` и тело issue #138 (`vault/issues/debt-082/01-issue-body.md`). Тело issue написано до решений пользователя: там вариант Г с открытым «запасным правилом», здесь оно решено (§3). Отдельной заметки в `vault/knowledge/` у задачи нет; связанные решения — [[расчёт по книге очищает каталог вывода до перевода — input и результаты от одного запуска]] (FEAT-036) и [[пример — это конфиг и README, штатный набор рисунков и проверок даёт команда пакета]] (FEAT-030, п. 3).
3. Пробы задачи — `vault/issues/debt-082/probes/` (§2.2): `rename_check.py`, `edge_cases.py`, настоящий Excel `excel_lock.ps1`, проверка кода шага 1 `plan_code/helpers_check.py` (вывод — `*.out.txt` рядом). Готовый тестовый файл шагов 1–2 — `plan_code/test_output_dir.py` (совпадает с блоками §5); эмуляция всего плана на копии дерева — `plan_emulate.py` (§11).
4. Worktree и ветка — по `/implement`: база `numerical_scheme/implementation`, ветка `refactor/debt-082/locked-output-dir` (на 2026-10-18 её нет), каталог `.worktrees/debt-082`.
5. Обозначения: `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas`; `<W>` = `<КОРЕНЬ>\.worktrees\debt-082`; `<PY>` = `<КОРЕНЬ>\numerical_solver\.venv\Scripts\python.exe`. Venv один, в основном каталоге, **своего `.venv` в worktree нет**. Все команды ниже — из `<W>\numerical_solver` интерпретатором `<PY>`. pytest берёт пакет worktree (`python -m` кладёт текущий каталог в `sys.path`) и прототип worktree (`pythonpath` в `numerical_solver/pyproject.toml`). Прототип не меняется: его тесты и регрессия не нужны.
6. **Исходная точка** — `35d2980` (2026-10-18, после влития FEAT-038 `225985e` во время аудита 1; план писался на `49e75bd`). FEAT-038 в решателе изменила только `README.md` (+24 строки выше §3.4 — номера строк README в шаге 5 уже сдвинуты), `examples/README.md`, `pyproject.toml` и прототип; `gpn_multiphase_solver/`, `tests/`, примеры 01/02/05/18, `CHANGELOG.md` и `.gitignore` — побитово те же (`git diff --quiet 49e75bd 35d2980 -- …`). Задача добавляет **16 тестов**:

   | База | всего | быстрый | `tests/test_output_dir.py` (новый) | `tests/test_cli.py` |
   |---|---|---|---|---|
   | `35d2980` (= `49e75bd` по тестам) | 2461 → **2477** | 2177 → **2193** | 0 → **15** | +1 |

   Сверка: `<PY> -m pytest tests/ --collect-only -q`, `<PY> -m pytest tests/ -m "not slow" --collect-only -q`. Правая часть подтверждена эмуляцией на копии (§11). Все новые тесты — быстрого уровня (метку `slow` ставит хук `tests/conftest.py:38-44` только тестам на тяжёлых фикстурах). На Windows проходят все 16; на POSIX три теста с настоящей блокировкой файла пропускаются (`skipif`). Если база к началу `/implement` уйдёт дальше — ожидание «база + 16».
7. Перед шагом 1 прогнать быстрый уровень (`<PY> -m pytest tests/ -m "not slow" -q`) и запомнить время (на копии с правками плана — 190 с, §11). В worktree один тест пропускается: `tests/test_xlsx_reader.py:476` без черновика руководителя `numerical_solver/configs/INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx` (файл не в git). Итог в worktree — «(быстрый − 1) passed, 1 skipped».
8. Шаги 1 → 2 → 3 → 4 → 5 → 6. После шагов 1–3 — быстрый уровень; после 4 — проверки примеров; после 5 — тесты справки и `--collect-only`; шаг 6 — только vault. Полный прогон — в конце (`/implement` §3.1).

## 1. Задача

### 1.1. Что не так

`run_case` (`numerical_solver/gpn_multiphase_solver/report/pipeline.py:76`) при расчёте по JSON-конфигу очищает каталог вывода **после** расчёта — решение пользователя 2026-10-13 (FEAT-030): если решатель откажет, прежние результаты уцелеют. Очистка — прямой `shutil.rmtree` (`pipeline.py:191-193`):

```python
    if workbook is None and output_dir.is_dir():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
```

На Windows файл, открытый в другой программе без права удаления (так открывает Excel — `well_history.csv`), не удаляется: `PermissionError` WinError 32. Исключение не ловят ни `run_case`, ни `cli.main` (`numerical_solver/gpn_multiphase_solver/cli.py:185-197` ловит только `CaseConfigError` → код 2 и `CaseRunError` → код 1). Итог: трассировка и код 1, как у ошибки кода; результаты расчёта не записаны — время расчёта потеряно; `rmtree` до отказа успевает удалить часть прежних файлов.

У расчёта по книге (FEAT-036) очистка — **до** расчёта, в `_translate_workbook` (`pipeline.py:384-398`); её `OSError` ловится и превращается в `CaseConfigError` с подсказкой, расчёт не теряется. Но частичное удаление то же.

Сценарий обычен для заказчика (поставка FEAT-031): инженер смотрит историю скважины в Excel и запускает расчёт снова; или запускает расчёт и, пока он идёт, открывает прежний CSV.

### 1.2. Чего нет в задаче

- Правило «очистка после расчёта» у конфига и «до расчёта» у книги не меняется (решения 2026-10-13 и 2026-10-18).
- Числа расчёта не меняются: правка только в файловых операциях конвейера. Истории примеров побитово те же.
- Прототип (`HydroSolverPrototype/`) не трогается.
- `--output`, указывающий на существующий **файл**, — отдельная задача (§10, DEBT-083).

## 2. Факты

### 2.1. Код на `49e75bd`

| Место | Строки | Что |
|---|---|---|
| `report/pipeline.py`, импорты | 18-22, 34-37 | `import platform, shutil, time`; `os` и `user_log` не импортированы |
| `CaseConfigError` | 56-57 | «расчёт не начат» — контракт кода 2 |
| `CaseResult` | 64-73 | `output_dir: Path` — каталог, куда записаны результаты |
| `run_case`, докстринг | 80-115 | правило очистки — 84-92 |
| `run_case`, ветка конфига до расчёта | 151-154 | `_check_inputs_outside` — единственная проверка каталога до расчёта |
| `run_case`, очистка после расчёта | 185-193 | комментарий + `shutil.rmtree` |
| `_print_summary` | 470-483 | печатает `Результаты: {output_dir}` |
| `_check_inputs_outside` | 346-360 | образец отказа до расчёта (`CaseConfigError`) |
| `_translate_workbook`, очистка | 384-398 | `rmtree` в `try`, `CaseConfigError` «очищен не полностью — <файл>» |
| `cli.py`, докстринг модуля | 1-22 | коды возврата — 4-6 |
| `cli.py`, справка `run` | 82-85 | эпилог; тест `test_run_help_mentions_workbook` (`tests/test_cli.py:420-427`) требует фразу «по книге — до него» |
| `log.py` | 33 | `user_log = logging.getLogger("gpn_multiphase_solver")`; обработчик ставит `setup_logging` в `SimulatorFactory` — к моменту очистки после расчёта он есть, предупреждения уходят в stderr с префиксом `[WARNING]` (образец — `io/config.py:838`, `_warn_large_skin`) |

Пишут в каталог вывода после `run_case` (по `here / "output"`, а не по `r.output_dir`) примеры:

| Пример | Строки | Что пишет |
|---|---|---|
| `numerical_solver/examples/01_single_phase_no_jt/main.py` | 184-205 | `_add_dupuit_curve(output_dir=here / "output")`, `_add_temperature_analytics(output_dir=here / "output")`, `export_emf(here / "output")` |
| `numerical_solver/examples/02_single_phase_jt/main.py` | 289-305 | те же три вызова позиционно |
| `numerical_solver/examples/05_standing_table_rp/main.py` | 90-120 | `_add_temperature_analytics(..., here / "output", r.title)`, `export_emf(here / "output")` |
| `numerical_solver/examples/18_prototype_input/main.py` | 16-25 | `output = here / "output"` → `report_and_plot(..., output, ...)`, `export_emf(output)` |

Остальные примеры зовут `cli.main` или ничего не пишут после `run_case` (`03` — только печать, `04` — только печать; `04_table_table/grid_convergence.py` — своя функция `run_case(N)`, к конвейеру не относится).

Тесты, которые трогают очистку:

| Тест | Файл:строки | Что |
|---|---|---|
| `test_locked_output_file_refused` | `tests/test_workbook_run.py:202-218` | подменяет `pipeline.shutil.rmtree`; требует в сообщении «открыт в другой программе», путь каталога и `well_history.csv` — **меняется на шаге 3** |
| `test_config_run_clears_output_after_run` | `tests/test_workbook_run.py:221-235` | очистка у конфига после расчёта — должен остаться зелёным |
| `test_run_case_run_failure` | `tests/test_examples.py:828-844` | отказ решателя — прежний каталог цел |
| `test_run_case_refuses_output_containing_inputs` | `tests/test_examples.py:791-809` | отказ до расчёта, образец |
| `test_pipeline_writes_output` | `tests/test_examples.py:623-` | `r.output_dir == tmp_path` — при свободном каталоге путь не меняется |
| `test_output_with_config_refused`, `test_run_failure_returns_1` | `tests/test_cli.py:158-180` | образцы тестов команды |

### 2.2. Пробы (2026-10-18, Windows 10, NTFS)

**A. Аудит 1 FEAT-036** (`vault/issues/feat-036/probes/audit_locked_output.py`): файл открыт `open(..., "w")` — `rmtree` падает `PermissionError` WinError 32, из трёх файлов удалён один.

**B. Переименование** (`vault/issues/debt-082/probes/rename_check.py`, `rename_check.out.txt`): каталог с открытым файлом — в корне или в подкаталоге `input/` — `os.rename` в соседний отказывает `PermissionError` WinError 5, каталог и файлы целы.

**C. Краевые случаи** (`edge_cases.py`, `edge_cases.out.txt`) — для каждого случая свежий каталог из трёх файлов, отдельно `os.rename` туда и обратно и отдельно `shutil.rmtree`:

| Что держит каталог | `os.rename` | `shutil.rmtree` | Вывод |
|---|---|---|---|
| 1. файл открыт без права удаления (Python `open`, как Excel) | отказ WinError 5, всё цело | отказ WinError 32, удалён 1 файл из 3 | переименование ловит, ничего не трогая |
| 2. файл открыт с правом удаления (`CreateFileW`, `FILE_SHARE_DELETE`) | отказ WinError 5 | прошло | **ложный отказ** проверки — с запасом; такие программы редки |
| 3. дескриптор самого каталога (наблюдение Проводника за открытой папкой) | прошло | прошло | согласованно |
| 4. текущий каталог другого процесса (консоль сделала `cd output`) | отказ WinError 32, всё цело | отказ WinError 32, **удалены все 3 файла**, сам каталог остался | хуже Excel: прямой `rmtree` стирает все прежние результаты и падает |

**D. Код шага 1** (`plan_code/helpers_check.py`, `plan_code/helpers_check.out.txt`) — функции §4 дословно, на реальной ФС:

| Сценарий | Итог |
|---|---|
| свободный каталог: проверка | прошло, файлы целы, соседних каталогов нет |
| свободный каталог: очистка | каталога нет, соседних нет |
| нет каталога: проверка и очистка | ничего не делают |
| открытый файл: проверка | `CaseConfigError` «… не удаётся очистить (Access is denied): …», файлы целы |
| открытый файл: очистка | `PermissionError` WinError 5, файлы целы |
| консоль в каталоге: проверка / очистка | `CaseConfigError` (WinError 32) / `PermissionError`, файлы целы |
| корень диска `D:\` | `CaseConfigError` «— корень диска …», до любого переименования |
| соседнее имя `output.check-<pid>` занято | берётся `output.check-<pid>-1`, проверка прошла |
| обратное переименование не прошло | `CaseConfigError` с путём `output.check-<pid>`, каталог под этим именем |
| удаление переименованного не прошло | `[WARNING] прежние результаты перенесены в …output.old-<pid> и не удалены …` |
| запасной каталог | `output_2026-10-18_15-34-34`, при занятом имени — `…-1` |

Проба D перезапущена после правки аудита 1 (`abspath` вместо `resolve` в `_sibling`) — итоги те же.

**E. Настоящий Excel** (аудит 1, `excel_lock.ps1`, `excel_lock.out.txt`): невидимый экземпляр Excel через COM открывает `well_history.csv`. Пока файл открыт: `os.rename` каталога — отказ WinError 5, все три файла целы; `shutil.rmtree` во втором каталоге — отказ WinError 32, `a.png` уже удалён. Посылка «Excel держит файл без права удаления, как `open()` Python» подтверждена на самом Excel, а не только эмуляцией.

**F. `resolve()` на диске `subst`** (аудит 1, команда в отчёте аудита): `subst Q: <каталог>`, `Path("Q:/out").resolve()` → `D:\…\out`, `os.path.abspath` → `Q:\out`, у `abspath("D:/")` имя пустое. `resolve()` заменяет букву подключённого диска реальным путём (у сетевого диска — путём `\\сервер\ресурс`), поэтому `_sibling` берёт `os.path.abspath`: сообщения и запасной каталог называют путь в том виде, в каком его ввёл инженер; отказ для корня диска сохраняется.

## 3. Решения пользователя (2026-10-18, `/plan-improve`)

1. **Файл открыли во время расчёта** (проверка до расчёта прошла, очистка после расчёта отказала): результаты пишутся в **соседний каталог** `<имя каталога>_<ГГГГ-ММ-ДД>_<чч-мм-сс>`, прежний каталог не трогается, предупреждение `[WARNING]` с обоими путями, код возврата **0** (расчёт выполнен). `CaseResult.output_dir` — фактический каталог. Примеры 01, 02, 05, 18 дописывают рисунки в `r.output_dir`.
   Отклонены: отказ без записи результатов (код 1 — расчёт теряется); ожидание закрытия файла с повторами (блокирует пакетные запуски, больше кода).
2. **Очистка у книги** (`_translate_workbook`) — через ту же функцию «переименовать, затем удалить»: занятый каталог не удаляется частично. Сообщение об отказе — общее с конфигом.

## 4. Решение

### 4.1. Две операции на переименовании

Переименование каталога на Windows — неразрушающая проверка «каталог удаляется целиком»: система отказывает, если в каталоге открыт файл без права удаления или каталог — текущий у процесса, и при этом ничего не трогает (пробы B, C). На POSIX переименование проходит — как и `rmtree`, который там удаляет и открытые файлы.

- `_check_output_free(output_dir)` — **проба до расчёта**: переименовать в соседний `<имя>.check-<pid>` и обратно. Отказ первого переименования — `CaseConfigError` (код 2, расчёт не начат, каталог не изменён). Отказ обратного — `CaseConfigError` с путём временного имени (почти невозможно: имя свободно, держателей нет).
- `_clear_output(output_dir)` — **очистка**: переименовать в соседний `<имя>.old-<pid>`, затем `rmtree` его. Переименование — точка невозврата: не прошло — `OSError` вызывающему, ни один файл не тронут; прошло — каталог свободен, удаляется уже переименованный. Отказ его удаления (файл открыли под новым именем — почти невозможно) — предупреждение с путём, расчёт идёт.

Окно гонки между проверкой и очисткой у конфига — весь расчёт; поэтому после расчёта очистка тоже идёт переименованием, а не проверкой + `rmtree`: окна между ними нет.

### 4.2. Поведение

| Ветка | Каталог занят до расчёта | Каталог заняли во время расчёта |
|---|---|---|
| Конфиг (`run_case(config.json)`) | `_check_output_free` → `CaseConfigError`, код 2, stdout пуст, каталог не изменён | `_clear_output` → `OSError` → результаты в `<имя>_<дата>_<время>`, `[WARNING]`, код 0 |
| Книга (`run_case(книга.xlsx)`) | `_clear_output` в `_translate_workbook` → `CaseConfigError`, код 2, каталог не изменён | не бывает: каталог очищен до расчёта |

Корень диска как каталог вывода (`--output D:\`) — `CaseConfigError` в `_sibling` до любого действия. Сейчас `rmtree("D:\\")` пытался бы стереть диск; проверка закрывает это попутно — у корня нет имени, без отказа `with_name` упал бы `ValueError`.

### 4.3. Сравнение вариантов

| Вариант | Суть | Плюсы | Минусы |
|---|---|---|---|
| **А + Г (выбран)** | проверка переименованием до расчёта; очистка переименованием после; при отказе — соседний каталог | обычный случай — мгновенный отказ без потери времени; во время расчёта — без потери расчёта; ни в одном случае нет частичного удаления | ложный отказ, если файл открыт с правом удаления (проба C2) |
| Только ловить `OSError` после `rmtree` | `try: rmtree … except OSError:` → соседний каталог | минимальный diff | частичное удаление остаётся; при консоли в каталоге прежние результаты стёрты целиком (C4); время расчёта тратится и в обычном случае |
| Запись в `<имя>.new` и замена | результаты в промежуточный каталог, затем замена | замена «всё или ничего» | все записи конвейера и примеров — через промежуточный каталог; больше кода; против правила «сначала простое» |
| Очистка до расчёта и у конфига | как у книги | убирает потерю расчёта | отменяет решение 2026-10-13: при отказе решателя прежних результатов нет |
| Точная проверка `CreateFileW(..., DELETE)` по каждому файлу | `ctypes`, без ложного отказа C2 | точнее | только Windows, `ctypes` в пакете, больше кода ради редкого случая |

## 5. Шаги

### Шаг 1: функции проверки и очистки каталога вывода

**Цель:** в `pipeline.py` появляются `_sibling`, `_busy_message`, `_check_output_free`, `_clear_output` с тестами; поведение `run_case` пока не меняется.

**Файлы:** `numerical_solver/gpn_multiphase_solver/report/pipeline.py`, `numerical_solver/tests/test_output_dir.py` (новый).

**Контекст:** §4.1. Код функций проверен пробой D дословно (`vault/issues/debt-082/probes/plan_code/helpers_check.py`). Функции внутренние (имена с `_`), докстринг — одна строка + ссылка на задачу (CLAUDE.md, «Файлы и код»).

**Что сделать:**

1. Импорты `pipeline.py`. До (строки 18-22 и 34-36):
   ```python
   import platform
   import shutil
   import time
   ...
   from ..io.workbook_convert import workbook_to_config, write_files
   from ..io.xlsx_reader import WorkbookError, read_workbook
   from ..simulator import Simulator
   ```
   После:
   ```python
   import os
   import platform
   import shutil
   import time
   ...
   from ..io.workbook_convert import workbook_to_config, write_files
   from ..io.xlsx_reader import WorkbookError, read_workbook
   from ..log import user_log
   from ..simulator import Simulator
   ```
   `log.py` ничего из пакета не импортирует — цикла нет.

2. После `_check_inputs_outside` (конец — строка 360), перед `_translate_workbook`, вставить:
   ```python
   def _sibling(path: Path, suffix: str) -> Path:
       """Свободное имя <имя каталога><suffix>[-k] рядом с каталогом path; корень диска — CaseConfigError. DEBT-082."""
       # abspath, а не resolve: resolve на сетевом диске и диске subst заменил
       # бы букву диска реальным путём (проба аудита 1), и сообщения назвали бы
       # путь, которого инженер не вводил
       path = Path(os.path.abspath(path))
       # У корня диска (D:\) нет имени: соседнего каталога нет, переименовать
       # корень нельзя, а rmtree стёр бы весь диск. Отказ до любого действия
       if not path.name:
           raise CaseConfigError(
               f"каталог вывода {path} — корень диска: перед записью результатов "
               f"каталог очищается целиком. Укажите подкаталог.")
       k = 0
       while True:
           cand = path.with_name(f"{path.name}{suffix}" + (f"-{k}" if k else ""))
           if not cand.exists():
               return cand
           k += 1


   def _busy_message(output_dir: Path, exc: OSError) -> str:
       """Текст отказа очистки каталога вывода: причина ОС и подсказка. DEBT-082."""
       return (f"каталог вывода {output_dir} не удаётся очистить ({exc.strerror or exc}): "
               f"файл в нём открыт в другой программе (например, CSV в Excel) или "
               f"каталог — текущий в консоли. Закройте файл или перейдите в консоли "
               f"в другой каталог")


   def _check_output_free(output_dir: Path) -> None:
       """Каталог вывода удаляется целиком: проба переименованием туда и обратно, иначе CaseConfigError. DEBT-082."""
       # Windows не переименовывает каталог, в котором открыт файл без права
       # удаления (так открывает Excel) или который служит текущим каталогом
       # процесса, — и ничего при этом не трогает. rmtree на том же каталоге
       # удалил бы часть файлов, а при консоли в каталоге — все, и только
       # потом упал бы (пробы DEBT-082, vault/issues/debt-082/probes/).
       # Файл, открытый с правом удаления, переименование тоже не пропускает,
       # хотя rmtree прошёл бы, — отказ с запасом. На POSIX переименование
       # проходит, как и rmtree
       if not output_dir.is_dir():
           return
       probe = _sibling(output_dir, f".check-{os.getpid()}")
       try:
           os.rename(output_dir, probe)
       except OSError as exc:
           raise CaseConfigError(
               f"{_busy_message(output_dir, exc)} и повторите расчёт. Расчёт не "
               f"начат, каталог не изменён.") from exc
       try:
           os.rename(probe, output_dir)
       except OSError as exc:
           raise CaseConfigError(
               f"каталог вывода {output_dir} при проверке переименован в {probe} и "
               f"не возвращён ({exc.strerror or exc}): верните ему прежнее имя и "
               f"повторите расчёт.") from exc


   def _clear_output(output_dir: Path) -> None:
       """Очистка каталога вывода: переименование в соседний, затем его удаление; OSError переименования — каталог цел. DEBT-082."""
       # Переименование — точка невозврата. Прошло — каталог свободен (см.
       # _check_output_free), удаляется уже переименованный. Не прошло —
       # OSError вызывающему, ни один файл не тронут: прямой rmtree успевал
       # удалить часть файлов до отказа (проба аудита 1 FEAT-036)
       if not output_dir.is_dir():
           return
       trash = _sibling(output_dir, f".old-{os.getpid()}")
       os.rename(output_dir, trash)
       try:
           shutil.rmtree(trash)
       except OSError as exc:
           # Файл открыли в уже переименованном каталоге — почти невозможно, но
           # прежние результаты под чужим именем не должны остаться молча
           user_log.warning(f"прежние результаты перенесены в {trash} и не удалены "
                            f"({exc.strerror or exc}); удалите этот каталог вручную.")
   ```
   Почему `os.rename`, а не `os.replace`: при занятом имени назначения `replace` на POSIX молча заменил бы пустой каталог; `_sibling` и так даёт свободное имя, а `rename` честно отказывает. Почему `exc.strerror or exc`: у `OSError` без `strerror` (собственные подмены в тестах) печатается текст исключения.

3. Новый файл `numerical_solver/tests/test_output_dir.py` — 11 тестов функций (расчёт не нужен). Шапка и общие части:
   ```python
   """Каталог вывода: проверка и очистка переименованием (DEBT-082).

   Windows не переименовывает каталог, в котором открыт файл без права удаления
   (CSV в Excel) или который служит текущим каталогом консоли, — и ничего не
   трогает; прямой rmtree успевал удалить часть файлов, а при консоли в каталоге
   — все (пробы vault/issues/debt-082/probes/). Проверяется:
     - функции _check_output_free, _clear_output, _sibling: свободный и
       отсутствующий каталог, занятый (подмена os.rename — тест не зависит от
       ОС), неудача обратного переименования, корень диска, занятое соседнее
       имя, неудача удаления переименованного каталога;
     - настоящая блокировка на Windows: открытый файл и консоль в каталоге;
     - run_case по конфигу: занятый каталог — отказ до расчёта; заняли во время
       расчёта — результаты в соседнем каталоге с датой и временем, прежний цел
       (решение пользователя 2026-10-18); свободный — очищен, временных
       каталогов не осталось.
   Отказ команды (код 2) — tests/test_cli.py, очистка у книги —
   tests/test_workbook_run.py.
   """

   import contextlib
   import io
   import json
   import logging
   import os
   import re
   import subprocess
   import sys
   import time
   from pathlib import Path

   import pytest

   import gpn_multiphase_solver.report.pipeline as pipeline
   from gpn_multiphase_solver.report.pipeline import CaseConfigError, run_case
   from gpn_multiphase_solver.simulator import Simulator

   SOLVER = Path(__file__).resolve().parents[1]                 # numerical_solver/
   EXAMPLES_DIR = SOLVER / "examples"
   OLD_FILES = ["a.png", "well_history.csv", "z.csv"]
   windows_only = pytest.mark.skipif(sys.platform != "win32",
                                     reason="блокировка открытого файла — только Windows")


   def _old_output(folder: Path) -> Path:
       """Каталог вывода прошлого расчёта folder/out с тремя файлами."""
       out = folder / "out"
       out.mkdir()
       for name in OLD_FILES:
           (out / name).write_text("1", encoding="utf-8")
       return out


   def _names(folder: Path) -> list[str]:
       return sorted(p.name for p in folder.iterdir())


   def _lock_rename(monkeypatch, out: Path) -> None:
       """os.rename каталога out отказывает, как Windows при открытом в нём файле (WinError 5); остальные — настоящие."""
       real = os.rename
       target = out.resolve()

       def fake(src, dst):
           if Path(src).resolve() == target:
               raise PermissionError(13, "Access is denied", str(src))
           return real(src, dst)
       monkeypatch.setattr(pipeline.os, "rename", fake)


   def _must_not_run(self, *args, **kwargs):
       raise AssertionError("расчёт начат при занятом каталоге вывода")
   ```
   `pipeline.os` — сам модуль `os`: подмена действует на всех, поэтому `fake` пропускает в настоящий `rename` всё, кроме каталога `out`; `monkeypatch` возвращает оригинал после теста.

   Тесты (комментарии — в коде теста, по правилам CLAUDE.md):
   ```python
   def test_free_dir_passes_and_stays(tmp_path):
       """Свободный каталог: проверка проходит, файлы на месте, временных каталогов рядом не осталось."""
       out = _old_output(tmp_path)
       pipeline._check_output_free(out)
       assert _names(out) == OLD_FILES
       assert _names(tmp_path) == ["out"]


   def test_missing_dir_noop(tmp_path):
       """Нет каталога: проверка и очистка ничего не делают и ничего не создают."""
       out = tmp_path / "out"
       pipeline._check_output_free(out)
       pipeline._clear_output(out)
       assert _names(tmp_path) == []


   def test_busy_dir_refused(tmp_path, monkeypatch):
       """Занятый каталог: CaseConfigError с путём и подсказкой, файлы целы (подмена os.rename)."""
       out = _old_output(tmp_path)
       _lock_rename(monkeypatch, out)
       with pytest.raises(CaseConfigError, match="открыт в другой программе") as e:
           pipeline._check_output_free(out)
       assert str(out) in str(e.value) and "Расчёт не начат" in str(e.value)
       assert _names(out) == OLD_FILES


   def test_rename_back_failure_names_probe(tmp_path, monkeypatch):
       """Обратное переименование не прошло: CaseConfigError называет временное имя, каталог под ним цел."""
       out = _old_output(tmp_path)
       real = os.rename

       def back_fails(src, dst):
           if Path(dst) == out:                 # второе переименование — обратно в out
               raise PermissionError(13, "Access is denied", str(src))
           return real(src, dst)
       monkeypatch.setattr(pipeline.os, "rename", back_fails)
       with pytest.raises(CaseConfigError, match="не возвращён") as e:
           pipeline._check_output_free(out)
       probe = out.with_name(f"out.check-{os.getpid()}")
       assert str(probe) in str(e.value)
       assert _names(probe) == OLD_FILES


   def test_drive_root_refused():
       """Корень диска: CaseConfigError «корень диска» до любого переименования — и у проверки, и у очистки."""
       root = Path(Path.cwd().anchor)
       for fn in (pipeline._check_output_free, pipeline._clear_output):
           with pytest.raises(CaseConfigError, match="корень диска"):
               fn(root)


   def test_sibling_skips_taken_name(tmp_path):
       """Занятое соседнее имя: берётся следующее с суффиксом -1."""
       out = _old_output(tmp_path)
       (tmp_path / f"out.check-{os.getpid()}").mkdir()
       assert pipeline._sibling(out, f".check-{os.getpid()}").name == f"out.check-{os.getpid()}-1"


   def test_clear_removes_whole_dir(tmp_path):
       """Очистка свободного каталога: каталога нет, временного рядом тоже."""
       out = _old_output(tmp_path)
       pipeline._clear_output(out)
       assert _names(tmp_path) == []


   def test_clear_busy_keeps_files(tmp_path, monkeypatch):
       """Очистка занятого каталога: OSError вызывающему, rmtree не вызван, файлы целы."""
       out = _old_output(tmp_path)
       _lock_rename(monkeypatch, out)
       called = []
       monkeypatch.setattr(pipeline.shutil, "rmtree", lambda p, *a, **k: called.append(p))
       with pytest.raises(PermissionError):
           pipeline._clear_output(out)
       assert called == [] and _names(out) == OLD_FILES


   def test_clear_trash_left_warns(tmp_path, monkeypatch, caplog):
       """Переименованный каталог не удалился: предупреждение с его путём, каталог под временным именем цел."""
       out = _old_output(tmp_path)

       def rmtree_fails(path, *args, **kwargs):
           raise PermissionError(13, "Access is denied", str(path))
       monkeypatch.setattr(pipeline.shutil, "rmtree", rmtree_fails)
       with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
           pipeline._clear_output(out)
       trash = out.with_name(f"out.old-{os.getpid()}")
       assert _names(trash) == OLD_FILES
       assert str(trash) in caplog.text and "удалите этот каталог вручную" in caplog.text


   @contextlib.contextmanager
   def _hold_open_file(out: Path):
       """Файл каталога открыт на запись — как CSV в Excel (без права удаления)."""
       f = open(out / "well_history.csv", "a", encoding="utf-8")
       try:
           yield
       finally:
           f.close()


   @contextlib.contextmanager
   def _hold_cwd(out: Path):
       """Каталог — текущий у другого процесса, как у консоли после cd."""
       p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=out)
       time.sleep(0.5)                          # как в пробе edge_cases.py
       try:
           yield
       finally:
           p.kill()
           p.wait()


   @windows_only
   @pytest.mark.parametrize("hold", [_hold_open_file, _hold_cwd], ids=["open_file", "cwd"])
   def test_real_lock_keeps_files(tmp_path, hold):
       """Windows, настоящая блокировка: проверка — CaseConfigError, очистка — OSError; ни один файл не удалён.

       Прямой rmtree при открытом файле удалял часть файлов, при консоли в
       каталоге — все (проба edge_cases.py, случаи 1 и 4).
       """
       out = _old_output(tmp_path)
       with hold(out):
           with pytest.raises(CaseConfigError, match="не удаётся очистить"):
               pipeline._check_output_free(out)
           with pytest.raises(OSError):
               pipeline._clear_output(out)
           assert _names(out) == OLD_FILES
       assert _names(tmp_path) == ["out"]
   ```
   Итого в файле после шага 1 — 11 тестов (9 + 2 параметра). Файл целиком в состоянии после шага 2 — `vault/issues/debt-082/probes/plan_code/test_output_dir.py` (проверен эмуляцией, §11).

**Проверка после этого шага:**
- `<PY> -m pytest tests/test_output_dir.py -q` — 11 passed (на POSIX — 9 passed, 2 skipped).
- Регресс: быстрый. Поведение `run_case` не изменилось — все прежние тесты зелёные.

**Подводные камни:**
- `Path.cwd().anchor` в `test_drive_root_refused` — корень диска рабочего каталога (`D:\`); функции отказывают в `_sibling` до любого `os.rename` и `rmtree` (проба D, «корень диска»). Отдельно следить, чтобы порядок не поменялся при правке: сначала `is_dir()`, затем `_sibling`, и только потом `os.rename`.
- `out.with_name(...)` в ожиданиях: `_sibling` возвращает `os.path.abspath` пути, а `tmp_path` pytest уже абсолютный и нормализованный — пути совпадают побитово. `resolve()` в `_sibling` не применять (проба F): на `subst`- и сетевом диске он заменил бы букву диска.
- `_hold_cwd` порождает процесс на 60 с — `kill` в `finally` обязателен, иначе `tmp_path` не удалится.

**Зависимости:** блокирует шаги 2 и 3.

**Оценка:** ~70 строк кода, ~200 строк тестов, ~30 минут.

### Шаг 2: `run_case` по конфигу — отказ до расчёта и соседний каталог после

**Цель:** ветка конфига проверяет каталог до расчёта и очищает его переименованием после; при отказе очистки — результаты в соседнем каталоге.

**Файлы:** `numerical_solver/gpn_multiphase_solver/report/pipeline.py`, `numerical_solver/tests/test_output_dir.py`, `numerical_solver/tests/test_cli.py`.

**Контекст:** §3 п. 1, §4.2. Отказ до расчёта — `CaseConfigError`: у него уже контракт «расчёт не начат», код 2; печать команды — «Ошибка конфига: каталог вывода … не удаётся очистить …» — так же, как у соседнего отказа `_check_inputs_outside` («Ошибка конфига: каталог вывода … содержит входной файл …»). Отдельный класс исключения ради другой приставки сообщения не заводится.

**Что сделать:**

1. Ветка конфига до расчёта. До (`pipeline.py:151-154`):
   ```python
       if workbook is None:
           # Перевод книги лежит в output/input/ по замыслу; саму книгу
           # проверил _translate_workbook
           _check_inputs_outside(config_path, config, output_dir)
   ```
   После:
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
   Проверка — до печати заголовка: при отказе stdout пуст, как у прочих отказов до расчёта (`test_run_case_config_errors`).

2. Очистка после расчёта. До (`pipeline.py:185-193`):
   ```python
       # Чистим output/ от результатов прошлых прогонов: иначе файлы, которые
       # текущая конфигурация уже не порождает (например, rs_profiles.png после
       # перехода примера на однофазный режим), остаются лежать и выглядят как
       # актуальные. Удаление ПОСЛЕ расчёта, а не до: если решатель упадёт,
       # прошлые результаты уцелеют. Книга — исключение: каталог очищен до
       # перевода (_translate_workbook), в нём только input/ этого расчёта.
       if workbook is None and output_dir.is_dir():
           shutil.rmtree(output_dir)
       output_dir.mkdir(parents=True, exist_ok=True)
   ```
   После:
   ```python
       # Чистим output/ от результатов прошлых прогонов: иначе файлы, которые
       # текущая конфигурация уже не порождает (например, rs_profiles.png после
       # перехода примера на однофазный режим), остаются лежать и выглядят как
       # актуальные. Удаление ПОСЛЕ расчёта, а не до: если решатель упадёт,
       # прошлые результаты уцелеют. Книга — исключение: каталог очищен до
       # перевода (_translate_workbook), в нём только input/ этого расчёта.
       # Очистка переименованием (_clear_output, DEBT-082): каталог заняли во
       # время расчёта (проверка до расчёта прошла) — ни один файл не удалён,
       # а расчёт не теряется: результаты пишутся в соседний каталог с датой и
       # временем в имени, прежний не тронут (решение пользователя
       # 2026-10-18). Расчёт выполнен — код команды 0, CaseResult.output_dir —
       # новый каталог
       if workbook is None and output_dir.is_dir():
           try:
               _clear_output(output_dir)
           except OSError as exc:
               busy = output_dir
               output_dir = _sibling(busy, time.strftime("_%Y-%m-%d_%H-%M-%S"))
               user_log.warning(f"{_busy_message(busy, exc)}. Результаты записаны в "
                                f"{output_dir}; прежние результаты в {busy} не тронуты.")
       output_dir.mkdir(parents=True, exist_ok=True)
   ```
   `_sibling` здесь не может отказать «корнем диска»: такой каталог отверг бы `_check_output_free` до расчёта. Все последующие записи конвейера (CSV, рисунки, EMF, `_print_summary`, `CaseResult`) идут через переменную `output_dir` — их менять не нужно; строка «Результаты: …» сводки называет новый каталог.

3. Докстринги `pipeline.py`:
   - `CaseConfigError` (строка 57): «Конфиг или книга не читаются, не проходят проверку или не собираются фабрикой; расчёт не начат. FEAT-030.» → «Конфиг или книга не читаются, не проходят проверку или не собираются фабрикой, каталог вывода занят; расчёт не начат. FEAT-030, DEBT-082.»
   - `CaseResult` (строка 66): «… заголовок, каталог вывода, время расчёта, с. FEAT-030.» → «… заголовок, каталог вывода (фактический: занятый после расчёта заменяется соседним, DEBT-082), время расчёта, с. FEAT-030.»
   - `run_case`, после абзаца «Книга: … scipy (FEAT-037).» (строки 88-94) — новый абзац:
     ```
         Каталог вывода занят (файл в нём открыт в другой программе, консоль в
         нём) — CaseConfigError до расчёта; ни один файл не удаляется. Заняли во
         время расчёта по конфигу — результаты пишутся в соседний каталог
         <имя>_<ГГГГ-ММ-ДД>_<чч-мм-сс>, прежний не тронут, предупреждение в
         журнал; CaseResult.output_dir — этот каталог (DEBT-082).
     ```
   - Докстринг модуля (строки 11-13) — дописать абзац: «Каталог вывода очищается переименованием (DEBT-082): занятый — отказ до расчёта; занятый во время расчёта по конфигу — результаты в соседнем каталоге с датой и временем в имени.»

4. Тесты в `tests/test_output_dir.py` (4 теста, каждый с расчётом ~1 с + рисунки ~3 с, кроме первого — он без расчёта). Помощник малого конфига — копия `_small_case` из `tests/test_cli.py:74-91` (импорт из соседнего тестового модуля в проекте не принят):
   ```python
   def _small_case(dst: Path) -> Path:
       """Конфиг примера 03 на сетке N = 20, одни сутки — в dst/case (как _small_case в test_cli.py). Расчёт ~1 с."""
       raw = json.loads((EXAMPLES_DIR / "03_standing_corey" / "config.json")
                        .read_text(encoding="utf-8"))
       raw["grid"]["N"] = 20
       h0 = raw["time"]["history"][0]
       raw["time"]["history"] = [dict(h0, duration=86400.0, dt_out=43200.0)]
       raw["output"] = {"log_level": "INFO", "title": "тест каталога вывода"}
       case = dst / "case"
       case.mkdir(parents=True)
       cfg = case / "config.json"
       cfg.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
       return cfg


   STAMPED = re.compile(r"out_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(-\d+)?")


   def test_run_case_busy_refused_before_run(tmp_path, monkeypatch, capsys):
       """Занятый каталог: CaseConfigError до расчёта и до печати заголовка, файлы целы."""
       monkeypatch.setattr(Simulator, "run", _must_not_run)
       cfg = _small_case(tmp_path)
       out = _old_output(tmp_path)
       _lock_rename(monkeypatch, out)
       with pytest.raises(CaseConfigError, match="не удаётся очистить"):
           run_case(cfg, out)
       assert capsys.readouterr().out == ""
       assert _names(out) == OLD_FILES


   def test_run_case_busy_after_run_writes_sibling(tmp_path, monkeypatch, caplog):
       """Каталог заняли во время расчёта: результаты в out_<дата>_<время>, прежний цел, предупреждение с обоими путями.

       _check_output_free настоящий (каталог свободен), отказывает очистка
       после расчёта — подмена _clear_output: тест не зависит от ОС.
       """
       cfg = _small_case(tmp_path)
       out = _old_output(tmp_path)

       def busy(path):
           raise PermissionError(13, "Access is denied", str(path))
       monkeypatch.setattr(pipeline, "_clear_output", busy)
       buf = io.StringIO()
       with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"), \
               contextlib.redirect_stdout(buf):
           r = run_case(cfg, out)
       assert STAMPED.fullmatch(r.output_dir.name), r.output_dir
       assert r.output_dir.parent == out.parent
       assert {"well_history.csv", "versions.txt"} <= set(_names(r.output_dir))
       assert _names(out) == OLD_FILES                     # прежний каталог не тронут
       assert str(out) in caplog.text and str(r.output_dir) in caplog.text
       # Сводка (_print_summary) называет новый каталог
       assert any(s.startswith("Результаты:") and s.endswith(str(r.output_dir))
                  for s in buf.getvalue().splitlines())


   @windows_only
   def test_run_case_locked_during_run(tmp_path, monkeypatch):
       """Windows: файл открыт после расчёта, до очистки — как Excel посреди расчёта: результаты в соседнем каталоге, прежний цел."""
       cfg = _small_case(tmp_path)
       out = _old_output(tmp_path)
       real_run = Simulator.run
       held = []

       def run_then_open(self, *args, **kwargs):
           history = real_run(self, *args, **kwargs)
           held.append(open(out / "well_history.csv", "a", encoding="utf-8"))
           return history
       monkeypatch.setattr(Simulator, "run", run_then_open)
       try:
           with contextlib.redirect_stdout(io.StringIO()):
               r = run_case(cfg, out)
       finally:
           for f in held:
               f.close()
       assert STAMPED.fullmatch(r.output_dir.name), r.output_dir
       assert _names(out) == OLD_FILES
       assert (r.output_dir / "well_history.csv").is_file()


   def test_run_case_free_output_cleared(tmp_path):
       """Свободный каталог: прежние файлы удалены, результаты на месте, временных каталогов (.check-, .old-) не осталось; путь не меняется."""
       cfg = _small_case(tmp_path)
       out = _old_output(tmp_path)
       with contextlib.redirect_stdout(io.StringIO()):
           r = run_case(cfg, out)
       assert r.output_dir == out
       names = _names(out)
       assert "a.png" not in names and "z.csv" not in names and "well_history.csv" in names
       assert _names(tmp_path) == ["case", "out"]
   ```
   Итого в `test_output_dir.py` — 15 тестов.

5. Тест команды в `tests/test_cli.py` — после `test_output_with_config_refused` (строка 180):
   ```python
   def test_busy_output_returns_2(tmp_path, capsys, monkeypatch):
       """Каталог вывода занят (файл открыт в другой программе) → код 2 до расчёта, без трассировки, файлы целы (DEBT-082).

       os.rename каталога вывода подменён на отказ, как Windows при открытом
       CSV (WinError 5): тест не зависит от ОС.
       """
       def must_not_run(self, *args, **kwargs):
           raise AssertionError("расчёт начат при занятом каталоге вывода")
       monkeypatch.setattr(Simulator, "run", must_not_run)

       cfg = _small_case(tmp_path)
       out = cfg.parent / "output"
       out.mkdir()
       (out / "well_history.csv").write_text("1", encoding="utf-8")
       real = os.rename

       def locked(src, dst):
           if Path(src).resolve() == out.resolve():
               raise PermissionError(13, "Access is denied", str(src))
           return real(src, dst)
       monkeypatch.setattr(os, "rename", locked)

       assert cli.main(["run", str(cfg)]) == 2
       err = capsys.readouterr().err
       assert "не удаётся очистить" in err and str(out.resolve()) in err
       assert "Traceback" not in err
       assert [p.name for p in out.iterdir()] == ["well_history.csv"]
   ```
   `os`, `Path`, `cli`, `Simulator` в `test_cli.py` уже импортированы (строки 30-42). Докстринг модуля `test_cli.py` (строки 7-8, список кодов возврата) — дописать «занятый каталог вывода — 2 до расчёта (DEBT-082)».

**Проверка после этого шага:**
- `<PY> -m pytest tests/test_output_dir.py tests/test_cli.py tests/test_workbook_run.py -q` — зелёные; в `test_output_dir.py` 15 passed.
- Регресс: быстрый. Особо — `test_pipeline_writes_output` (`r.output_dir == tmp_path`: при свободном каталоге путь не меняется), `test_run_case_run_failure`, `test_config_run_clears_output_after_run`, `test_run_case_config_errors`.

**Подводные камни:**
- Порядок проверок до расчёта: `_check_inputs_outside` → `_check_output_free`. Каталог, содержащий конфиг, отвергается первой с прежним сообщением (`test_run_case_refuses_output_containing_inputs`, `test_output_with_config_refused`) — проба переименованием до неё не доходит. Обратный порядок переименовал бы каталог с конфигом туда и обратно — безвредно, но лишне.
- `test_run_case_busy_after_run_writes_sibling`: предупреждение приходит через `user_log`, `caplog` ловит его на корневом обработчике (логгер `gpn_multiphase_solver` передаёт записи вверх; уровень INFO ставит `setup_logging` по `output.log_level` малого конфига). Проверять `capsys.err` нельзя: обработчик `setup_logging` создаётся один раз и держит `sys.stderr` момента создания — у другого теста.
- `r.output_dir` в запасном случае — абсолютный путь (`_sibling` делает `os.path.abspath`); при свободном каталоге — прежний объект `output_dir` без преобразований, поэтому `test_pipeline_writes_output` (`== tmp_path`) не меняется.
- Предупреждение уходит в журнал; при `output.log_level = "ERROR"` оно скрыто, но строка «Результаты: <новый каталог>» сводки печатается всегда.

**Зависимости:** требует шаг 1; блокирует шаг 4.

**Оценка:** ~25 строк кода, ~110 строк тестов, ~30 минут.

### Шаг 3: очистка у книги — той же функцией

**Цель:** `_translate_workbook` очищает каталог через `_clear_output`; занятый каталог у книги тоже не удаляется частично.

**Файлы:** `numerical_solver/gpn_multiphase_solver/report/pipeline.py`, `numerical_solver/tests/test_workbook_run.py`.

**Контекст:** §3 п. 2. Сейчас отказ `rmtree` ловится, но часть файлов уже удалена, а сообщение называет файл («очищен не полностью — <файл>»). При переименовании имя занятого файла неизвестно — сообщение общее с конфигом (`_busy_message`), зато каталог не изменён.

**Что сделать:**

1. До (`pipeline.py:384-398`):
   ```python
       # Очистка — до записи перевода и до расчёта (решение пользователя
       # 2026-10-18): input/ и результаты в каталоге всегда от одного запуска.
       # Цена: при ошибке конфига или отказе решателя прежних результатов нет,
       # остаётся input/ — вход, на котором расчёт остановился
       if output_dir.is_dir():
           try:
               shutil.rmtree(output_dir)
           except OSError as exc:
               # Windows: файл каталога открыт в другой программе (CSV в Excel) —
               # WinError 32, rmtree успевает удалить часть файлов (аудит 1). Расчёт
               # ещё не начат: отказ с подсказкой, а не трассировка (у конфига — DEBT-082)
               raise CaseConfigError(
                   f"каталог вывода {output_dir} очищен не полностью — {exc.filename}: "
                   f"{exc.strerror}. Файл открыт в другой программе? Закройте его и "
                   f"повторите расчёт.") from exc
   ```
   После:
   ```python
       # Очистка — до записи перевода и до расчёта (решение пользователя
       # 2026-10-18): input/ и результаты в каталоге всегда от одного запуска.
       # Цена: при ошибке конфига или отказе решателя прежних результатов нет,
       # остаётся input/ — вход, на котором расчёт остановился.
       # Очистка переименованием (_clear_output, DEBT-082): каталог занят (файл
       # открыт в Excel, консоль в каталоге) — отказ с подсказкой, ни один файл
       # не удалён; прямой rmtree успевал удалить часть (аудит 1 FEAT-036).
       # Корень диска _clear_output отвергает сам (CaseConfigError)
       try:
           _clear_output(output_dir)
       except OSError as exc:
           raise CaseConfigError(
               f"{_busy_message(output_dir, exc)} и повторите расчёт. Расчёт не "
               f"начат, каталог не изменён.") from exc
   ```
   Проверка `output_dir.is_dir()` теперь внутри `_clear_output`.

2. `tests/test_workbook_run.py:202-218` — до:
   ```python
   def test_locked_output_file_refused(tmp_path, monkeypatch):
       """Файл каталога вывода открыт в другой программе: отказ с путём и подсказкой, а не трассировка.

       На Windows rmtree падает PermissionError (WinError 32) на открытом файле,
       успев удалить часть файлов (проба аудита 1, audit_locked_output.py). Здесь
       rmtree подменён: тест не зависит от ОС. Расчёт не начат.
       """
       monkeypatch.setattr(Simulator, "run", _must_not_run)
       book = _small_book(tmp_path / "b.xlsx")
       out = _old_output(tmp_path)

       def locked(path, *args, **kwargs):
           raise PermissionError(13, "файл занят", str(Path(path) / "well_history.csv"))
       monkeypatch.setattr(pipeline.shutil, "rmtree", locked)
       with pytest.raises(CaseConfigError, match="открыт в другой программе") as e:
           run_case(book)
       assert str(out) in str(e.value) and "well_history.csv" in str(e.value)
   ```
   После:
   ```python
   def test_locked_output_file_refused(tmp_path, monkeypatch):
       """Файл каталога вывода открыт в другой программе: отказ с путём и подсказкой, ни один файл не удалён (DEBT-082).

       На Windows каталог с открытым файлом не переименовывается (WinError 5),
       и очистка переименованием (_clear_output) отказывает, ничего не удалив;
       прямой rmtree успевал удалить часть файлов (проба аудита 1,
       audit_locked_output.py; пробы DEBT-082). Здесь os.rename каталога вывода
       подменён: тест не зависит от ОС. Расчёт не начат.
       """
       monkeypatch.setattr(Simulator, "run", _must_not_run)
       book = _small_book(tmp_path / "b.xlsx")
       out = _old_output(tmp_path)
       real = os.rename

       def locked(src, dst):
           if Path(src).resolve() == out.resolve():
               raise PermissionError(13, "Access is denied", str(src))
           return real(src, dst)
       monkeypatch.setattr(pipeline.os, "rename", locked)
       with pytest.raises(CaseConfigError, match="открыт в другой программе") as e:
           run_case(book)
       assert str(out) in str(e.value) and "Расчёт не начат" in str(e.value)
       # Очистка переименованием: прежний каталог не изменён
       assert [p.name for p in out.iterdir()] == ["прошлый.csv"]
   ```
   `os` в `test_workbook_run.py` уже импортирован (строка 22). Пункт докстринга модуля (строка 12) — «файл каталога вывода открыт в другой программе — отказ с подсказкой, каталог не изменён (аудит 1, DEBT-082)».

**Проверка после этого шага:**
- `<PY> -m pytest tests/test_workbook_run.py -q` — зелёный, число тестов прежнее.
- Регресс: быстрый.

**Подводные камни:**
- Старый тест подменял `rmtree` и ждал `CaseConfigError`; с новым кодом он получил бы `[WARNING] … не удалены` вместо отказа (переименование прошло бы) и упал — поэтому правится в том же шаге.
- `test_input_saved_and_output_cleared` (фикстура `case`) и `test_book_error_leaves_output` — очистка свободного каталога и книга с ошибкой (до очистки) — должны остаться зелёными без правки.

**Зависимости:** требует шаг 1.

**Оценка:** ~10 строк кода, ~10 строк теста, ~15 минут.

### Шаг 4: примеры дописывают рисунки в `r.output_dir`; соседние каталоги примеров — вне git

**Цель:** примеры 01, 02, 05, 18 пишут перестроенные рисунки и EMF туда, куда `run_case` фактически записал результаты; соседние и временные каталоги вывода примеров игнорируются git.

**Файлы:** `numerical_solver/examples/01_single_phase_no_jt/main.py`, `numerical_solver/examples/02_single_phase_jt/main.py`, `numerical_solver/examples/05_standing_table_rp/main.py`, `numerical_solver/examples/18_prototype_input/main.py`, `.gitignore` (корень проекта).

**Контекст:** §3 п. 1. При занятом `here / "output"` результаты уходят в соседний каталог, а перестроенные примером рисунки ушли бы в занятый. При свободном каталоге `r.output_dir` — тот же объект `here / "output"`: рисунки и истории не меняются. `.gitignore:47` игнорирует только `numerical_solver/examples/**/output/`: каталог `output_<дата>_<время>` (полный прогон тестов при открытом в Excel CSV примера) появился бы в `git status` как неотслеживаемый.

**Что сделать:**

1. `01_single_phase_no_jt/main.py:184-205` — после `r = run_case(here / "config.json", here / "output")` три вхождения `here / "output"` (`output_dir=here / "output",` в двух вызовах и `export_emf(here / "output")`) → `r.output_dir`. Над первым вызовом — комментарий:
   ```python
       # Каталог, куда run_case записал результаты: при занятом here/output —
       # соседний с датой и временем в имени (DEBT-082)
   ```
2. `02_single_phase_jt/main.py:292, 296, 305` — три вхождения `here / "output"` после `run_case` → `r.output_dir`, тот же комментарий над строкой 292.
3. `05_standing_table_rp/main.py:112, 120` — два вхождения → `r.output_dir`, комментарий над строкой 111.
4. `18_prototype_input/main.py:16-25` — до:
   ```python
       here = Path(__file__).parent
       output = here / "output"
       # Заголовок, 6 моментов профилей ...
       r = run_case(here / "config.json", output)
       # Прототип на той же книге и эталон CMG IMEX T07: сводка и два рисунка.
       prototype_input.report_and_plot(r.history, r.grid, output, r.title)
   ```
   После:
   ```python
       here = Path(__file__).parent
       # Заголовок, 6 моментов профилей ...
       r = run_case(here / "config.json", here / "output")
       # Каталог, куда run_case записал результаты: при занятом here/output —
       # соседний с датой и временем в имени (DEBT-082)
       output = r.output_dir
       # Прототип на той же книге и эталон CMG IMEX T07: сводка и два рисунка.
       prototype_input.report_and_plot(r.history, r.grid, output, r.title)
   ```
   (`export_emf(output)` в конце не меняется.)
5. Аргументы `here / "output"` **в самих вызовах `run_case`** не трогать — это каталог по умолчанию примера.
6. `.gitignore` — после строки 47 (`numerical_solver/examples/**/output/`) добавить:
   ```
   # Соседний каталог вывода при занятом output/ (output_<дата>_<время>) и
   # временные имена очистки (output.check-<pid>, output.old-<pid>) — DEBT-082
   numerical_solver/examples/**/output[._]*/
   ```
   Шаблон проверен при планировании (`git -c core.excludesFile=… check-ignore --no-index`): игнорируются `output_2026-10-18_15-30-12/…`, `output.old-123/…`, `output.check-123-1/…`; не задеты `outputs.md`, `main.py`.

**Проверка после этого шага:**
- `Select-String -Path examples\01_single_phase_no_jt\main.py, examples\02_single_phase_jt\main.py, examples\05_standing_table_rp\main.py, examples\18_prototype_input\main.py -Pattern 'here / "output"'` — по одному совпадению на файл (вызов `run_case`).
- `<PY> -m pytest tests/test_example_scripts.py -q` — проверка имён скриптов примеров разбором AST (DEBT-046) зелёная.
- `git check-ignore -v numerical_solver/examples/01_single_phase_no_jt/output_2026-10-18_15-30-12/well_history.csv` (из `<W>`) — печатает правило `.gitignore:<строка>:numerical_solver/examples/**/output[._]*/`.
- Запуск примера 01 в worktree (правило 3 `/implement`: `PYTHONPATH` на пакет и прототип worktree, иначе скрипт возьмёт пакет основного каталога): `$env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"; <PY> examples\01_single_phase_no_jt\main.py` — код 0, `examples\01_single_phase_no_jt\output\pressure_profiles.png` перестроен (время изменения — после запуска). Каталог `output/` примеров в `.gitignore`.
- Регресс: быстрый.

**Подводные камни:**
- 18 — пример с прототипом и эталоном IMEX, расчёт длинный; запускать его не нужно — правка механическая, проверка AST её покрывает.
- `test_folder_holds_only_book_as_input` (`tests/test_examples.py:3344-3348`) перечисляет папку примера 22, исключая только `output` и `__pycache__`. Соседний каталог у 22 не появляется: это книга, её каталог очищается до расчёта, занятый — отказ. Временные `.check-`/`.old-` живут доли секунды.

**Зависимости:** требует шаг 2.

**Оценка:** ~15 строк, ~15 минут.

### Шаг 5: справка команды, README, журнал

**Цель:** документация описывает отказ при занятом каталоге и соседний каталог.

**Файлы:** `numerical_solver/gpn_multiphase_solver/cli.py`, `numerical_solver/README.md`, `numerical_solver/examples/README.md`, `numerical_solver/CHANGELOG.md`.

**Что сделать:**

1. `cli.py`, докстринг модуля (строки 4-6). До:
   ```
   рисунки, печать проверок. Коды возврата: 0 — расчёт завершён; 1 — решатель
   отказал на шаге по времени; 2 — ошибка аргументов или конфига (расчёт не
   начат). Та же команда — gpn-solver run config.json ([project.scripts]).
   ```
   После:
   ```
   рисунки, печать проверок. Коды возврата: 0 — расчёт завершён; 1 — решатель
   отказал на шаге по времени; 2 — ошибка аргументов или конфига, занятый
   каталог вывода (расчёт не начат). Каталог заняли во время расчёта —
   результаты в соседнем каталоге, код 0 (DEBT-082). Та же команда —
   gpn-solver run config.json ([project.scripts]).
   ```
2. `cli.py`, эпилог `run` (строки 82-85). До:
   ```python
           epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; "
                  "2 — ошибка аргументов, конфига или книги. Каталог вывода "
                  "очищается целиком: при расчёте по конфигу — после расчёта, "
                  "по книге — до него.")
   ```
   После:
   ```python
           epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; "
                  "2 — ошибка аргументов, конфига или книги, занятый каталог "
                  "вывода. Каталог вывода очищается целиком: при расчёте по "
                  "конфигу — после расчёта, по книге — до него. Если файл "
                  "каталога открыт в другой программе — отказ до расчёта; если "
                  "его открыли во время расчёта — результаты в соседнем каталоге "
                  "с датой и временем в имени.")
   ```
   Фраза «по книге — до него» сохраняется (`test_run_help_mentions_workbook`).
3. `README.md` §3.4 (заголовок — строка 247 на `35d2980`), блок-примечание (строки 258-262). До:
   ```
   > **После успешного расчёта каталог вывода полностью очищается** и только
   > затем заполняется результатами. Не указывайте каталог, в котором хранятся
   > другие файлы. Если внутри каталога вывода находится сам файл конфигурации
   > или его таблицы CSV, команда завершается с ошибкой ещё до расчёта.
   > При расчёте по книге Excel каталог очищается до расчёта (3.6).
   ```
   После (добавлен абзац):
   ```
   > **После успешного расчёта каталог вывода полностью очищается** и только
   > затем заполняется результатами. Не указывайте каталог, в котором хранятся
   > другие файлы. Если внутри каталога вывода находится сам файл конфигурации
   > или его таблицы CSV, команда завершается с ошибкой ещё до расчёта.
   > При расчёте по книге Excel каталог очищается до расчёта (3.6).
   >
   > Если файл каталога вывода открыт в другой программе (например, CSV в
   > Excel) или в этом каталоге стоит консоль, каталог не удаётся очистить:
   > команда завершается с ошибкой до расчёта (код 2), каталог не меняется —
   > файл нужно закрыть и повторить расчёт. Если файл открыли уже во время
   > расчёта, результаты записываются в соседний каталог с датой и временем в
   > имени, например `output_2026-10-18_15-30-12`; об этом выводится
   > предупреждение, прежний каталог не меняется.
   ```
   Строки 264-268 (коды возврата): «2 — ошибка в аргументах или файле конфигурации, расчёт не начинался» → «2 — ошибка в аргументах или файле конфигурации либо занятый каталог вывода, расчёт не начинался».
4. `README.md` §3.6, конец примечания (строки 351-354). До:
   ```
   > внутри каталога вывода — отказ до расчёта. Если файл каталога вывода
   > открыт в другой программе (например, CSV в Excel), каталог не удаётся
   > очистить: команда завершается с ошибкой до расчёта — файл нужно закрыть
   > и повторить расчёт.
   ```
   После:
   ```
   > внутри каталога вывода — отказ до расчёта. Если файл каталога вывода
   > открыт в другой программе (например, CSV в Excel) или в каталоге стоит
   > консоль, каталог не удаётся очистить: команда завершается с ошибкой до
   > расчёта, каталог не меняется — файл нужно закрыть и повторить расчёт.
   ```
5. `examples/README.md`, абзац о команде (строки 287-292 на `35d2980`) — повторяет правило очистки и коды возврата README пакета. До:
   ```
   `output` рядом с конфигом. **Каталог вывода после расчёта очищается
   целиком** — не указывайте папку с другими файлами; папку, внутри которой
   лежит сам конфиг или его CSV-таблицы, команда отвергает до расчёта. Коды
   возврата: 0 — расчёт завершён; 1 — решатель отказал на шаге по времени
   (сообщение решателя в консоли, прежние результаты не тронуты); 2 — ошибка
   аргументов или конфига, расчёт не начат. Вход может быть и книгой ввода
   ```
   После:
   ```
   `output` рядом с конфигом. **Каталог вывода после расчёта очищается
   целиком** — не указывайте папку с другими файлами; папку, внутри которой
   лежит сам конфиг или его CSV-таблицы, команда отвергает до расчёта. Если
   файл каталога вывода открыт в другой программе (CSV в Excel), команда
   отказывает до расчёта; если его открыли во время расчёта — результаты в
   соседней папке `output_<дата>_<время>` ([README пакета, §3.4](../README.md)).
   Коды возврата: 0 — расчёт завершён; 1 — решатель отказал на шаге по времени
   (сообщение решателя в консоли, прежние результаты не тронуты); 2 — ошибка
   аргументов или конфига либо занятый каталог вывода, расчёт не начат. Вход
   может быть и книгой ввода
   ```
   Строка 293 и далее («Excel (`run книга.xlsx`): …») продолжают ту же фразу — перенос строк выровнять, текст не менять.
6. `CHANGELOG.md`, раздел `## Не выпущено` — подраздел `### Исправлено` после `### Добавлено` (создать):
   ```
   ### Исправлено

   - Файл каталога вывода, открытый в другой программе (например, CSV в
     Excel), или консоль, стоящая в этом каталоге, больше не прерывают расчёт
     трассировкой и не удаляют прежние результаты частично. Занятый каталог —
     ошибка до расчёта (код 2), каталог не меняется; если каталог заняли во
     время расчёта по файлу конфигурации, результаты записываются в соседний
     каталог `<имя>_<ГГГГ-ММ-ДД>_<чч-мм-сс>` с предупреждением, код 0.
   ```
   FEAT-038 влита (`225985e`), первый выпуск `1.0.0` делается командой `python tools/release.py 1.0.0` после её влития. Если к началу шага выпуск уже сделан (раздел «Не выпущено» сведён в `## 1.0.0 — <дата>`) — создать новый `## Не выпущено` над выпуском по правилу журнала (строки 31-33) и положить пункт туда.

**Проверка после этого шага:**
- `<PY> -m pytest tests/test_cli.py tests/test_eq_references.py -q` — зелёные (справка, ссылки README и докстрингов).
- `<PY> -m pytest tests/ --collect-only -q` — база + 16.
- Регресс: `--collect-only` (шаг меняет только тексты; `cli.py` — строки справки, их ловят тесты выше).

**Подводные камни:**
- FEAT-038 влита во время аудита 1 и сдвинула README на +24 строки — номера выше уже по `35d2980`; если база уйдёт дальше, искать абзацы по тексту блоков «До:». Выпуск `1.0.0` (`tools/release.py`) правит `CHANGELOG.md` и `__version__` — с этим шагом пересекается только раздел «Не выпущено» (см. п. 6).

**Зависимости:** требует шаги 2, 3.

**Оценка:** ~40 строк текста, ~20 минут.

### Шаг 6: vault

**Цель:** решение записано, связанные заметки и реестр обновлены.

**Файлы:**
- новая заметка `vault/knowledge/decisions/каталог вывода очищается переименованием — занятый каталог не удаляется частично.md`;
- `vault/knowledge/decisions/расчёт по книге очищает каталог вывода до перевода — input и результаты от одного запуска.md` — п. 4 (строка 17) и строка 36;
- `vault/knowledge/decisions/пример — это конфиг и README, штатный набор рисунков и проверок даёт команда пакета.md` — п. 3 (строка 29);
- `vault/roadmap/известные баги и технический долг.md` — DEBT-082;
- `vault/00-home/index.md` — строка заметки FEAT-036 (28) и запись плана.

**Что сделать:**
1. Новая заметка (frontmatter `name`, `description`, `tags: [решение]`): правило §4.1–4.2, решения пользователя §3, таблица пробы C (почему переименование, а не `rmtree`; ложный отказ C2 принят), корень диска, ссылки на [[DEBT-082]], [[FEAT-030]], [[FEAT-036]], [[FEAT-031]] и на две заметки выше.
2. Заметка FEAT-036, п. 4: «Очистка каталога вывода `shutil.rmtree` — **до** расчёта … `CaseConfigError` «каталог вывода … очищен не полностью — <файл>: <причина>…» → очистка до расчёта переименованием (`_clear_output`, DEBT-082): занятый каталог — `CaseConfigError` «каталог вывода … не удаётся очистить …», ни один файл не удалён. Строка 36 — «решено в DEBT-082: отказ до расчёта, соседний каталог после».
3. Заметка FEAT-030, п. 3: хвост «открытый в другой программе файл ломает очистку после расчёта у конфига — [[DEBT-082]]» → «очистка — переименованием: занятый каталог — отказ до расчёта, занятый во время расчёта — результаты в соседнем каталоге ([[DEBT-082]])».
4. Реестр DEBT-082: `- **План:** [[debt-082 locked-output-dir]]` (ставит `/plan-improve`), статус и итог — по `/implement`.
5. `index.md`: в строке 28 хвост «файл вывода, открытый в Excel, — отказ с подсказкой до расчёта» дополнить «(переименованием, ни один файл не удаляется — DEBT-082)»; запись новой заметки решения рядом.

**Проверка после этого шага:**
- `<PY> -m pytest tests/test_eq_references.py -q` — сторож меток проверяет и заметки `vault/knowledge/` (DEBT-074): в новой заметке ссылки на постановку — только метками (здесь их нет).

**Зависимости:** требует шаги 1–5.

**Оценка:** ~60 строк, ~20 минут.

## 6. Подводные камни (чеклист 2.5)

| Пункт | Оценка | Как адресовано |
|---|---|---|
| Все места вызова найдены | ✅ | `shutil.rmtree` в пакете — только `pipeline.py:192` и `:390` (`Grep rmtree gpn_multiphase_solver/`); `run_case` вызывают `cli.main`, примеры 01–05, 18 и тесты; пишут после `run_case` — 01, 02, 05, 18 (§2.1) |
| Зависимости пакетов | ✅ | только стандартная библиотека (`os`, `shutil`, `time`) |
| Обратная совместимость API | ✅ | сигнатуры `run_case`, `CaseResult`, исключений прежние; новое — `CaseResult.output_dir` может отличаться от аргумента (только в запасном случае, документировано) |
| Состояние при ошибке | ✅ | отказ проверки — каталог не изменён; отказ обратного переименования — каталог под временным именем, путь в сообщении; отказ очистки — каталог цел, результаты в соседнем |
| Существующие тесты | ⚠️ | `test_locked_output_file_refused` подменял `rmtree` — меняется в шаге 3; остальные не зависят от способа очистки |
| Циклические импорты | ✅ | `log.py` не импортирует пакет |
| Ссылки на уравнения в докстрингах | ✅ | новые докстринги ссылаются на DEBT-082, не на `.tex` |
| Конфиги | ✅ | поля не меняются |
| Связь с другими задачами | ⚠️ | FEAT-036 (влита): сообщение отказа у книги меняется — тест и заметка правятся (шаги 3, 6). FEAT-038 (влита `225985e` во время аудита 1): README сдвинут на +24 строки, номера в шаге 5 обновлены; выпуск `1.0.0` может свести «Не выпущено» журнала (шаг 5, п. 6). FEAT-031: README §3.4 — описание для инженера заказчика |
| Сетевой диск, диск `subst` | ✅ | `_sibling` берёт `os.path.abspath`, не `resolve()` — буква диска в сообщениях и имени запасного каталога сохраняется (проба F, аудит 1). Переименование — в пределах родительского каталога, на том же томе |
| Производительность | ✅ | два переименования каталога — микросекунды |
| Прототип | ✅ | не меняется |
| Ложный отказ (файл открыт с правом удаления, проба C2) | ⚠️ | принят: отказ с запасом, сообщение верно («файл открыт в другой программе»); точная проверка — только Windows через `ctypes` (§4.3) |
| Кратковременные держатели (антивирус, индексатор только что записанных файлов) | ⚠️ | дают тот же отказ, что и прежний `rmtree`; до расчёта — код 2 и повтор, после — соседний каталог. Повторы с ожиданием не вводятся (решение §3) |
| Разные ОС | ✅ | тесты подменой `os.rename` — на любой ОС; настоящая блокировка — `skipif` не Windows |
| Текущий каталог самой команды внутри каталога вывода (`cd output; gpn-solver run ..\config.json`) | ✅ | теперь отказ до расчёта с подсказкой «каталог — текущий в консоли» (проба C4 — тот же случай). Прежде `rmtree` удалял все файлы и падал трассировкой — не регрессия. Тесты так не запускают: единственный `monkeypatch.chdir` (`tests/test_cli.py:190`) — при подменённом `run_case`; подпроцессы `test_cli.py` и примеров стоят в родителе каталога вывода, а родитель переименованию не мешает |
| Соседние каталоги примеров в git | ✅ | шаблон `.gitignore` (шаг 4) |

## 7. Тестовая стратегия

**Регресс:** все существующие тесты зелёные после каждого шага; очистку покрывают `tests/test_workbook_run.py` (вся ветка книги, `test_config_run_clears_output_after_run`), `tests/test_examples.py::test_pipeline_writes_output`, `test_run_case_run_failure`, `test_run_case_refuses_output_containing_inputs`, `tests/test_cli.py` (коды возврата, справка).

**Новые тесты** — 16 (§5, шаги 1, 2):

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_free_dir_passes_and_stays` | `test_output_dir.py` | свободный каталог | файлы целы, рядом ничего | проверка, оставляющая `.check-` |
| `test_missing_dir_noop` | то же | нет каталога | ничего не создано | создание каталога проверкой |
| `test_busy_dir_refused` | то же | подмена `os.rename` | `CaseConfigError`, путь, «Расчёт не начат», файлы целы | трассировку вместо отказа |
| `test_rename_back_failure_names_probe` | то же | обратное переименование отказывает | сообщение с путём `out.check-<pid>`, файлы под ним | потерю каталога без следа |
| `test_drive_root_refused` | то же | `D:\` | «корень диска» у обеих функций | `rmtree` корня, `ValueError` `with_name` |
| `test_sibling_skips_taken_name` | то же | имя занято | суффикс `-1` | ложный отказ из-за остатка прошлого прогона |
| `test_clear_removes_whole_dir` | то же | свободный | каталога и временного нет | остаток `.old-` |
| `test_clear_busy_keeps_files` | то же | подмена `os.rename` | `OSError`, `rmtree` не вызван, файлы целы | частичное удаление |
| `test_clear_trash_left_warns` | то же | подмена `rmtree` | предупреждение с путём `.old-<pid>` | молчаливый остаток прежних результатов |
| `test_real_lock_keeps_files[open_file]`, `[cwd]` | то же | Windows, настоящая блокировка | отказ обеих функций, 3 файла целы | регрессию на реальной ФС (пробы C1, C4) |
| `test_run_case_busy_refused_before_run` | то же | занятый каталог, `run` запрещён | `CaseConfigError`, stdout пуст | расчёт при занятом каталоге |
| `test_run_case_busy_after_run_writes_sibling` | то же | подмена `_clear_output` | `out_<дата>_<время>`, прежний цел, предупреждение, сводка | потерю расчёта |
| `test_run_case_locked_during_run` | то же | Windows, файл открыт после `run` | соседний каталог, прежний цел | то же на реальной ФС |
| `test_run_case_free_output_cleared` | то же | свободный каталог | очищен, путь прежний, временных нет | остатки `.check-`/`.old-`, смену пути |
| `test_busy_output_returns_2` | `test_cli.py` | команда, занятый каталог | код 2, без трассировки, файлы целы | трассировку и код 1 |

**Инварианты:** числа расчёта не меняются — правка только файловых операций; полный прогон в конце (`/implement` §3.1) сверяет истории примеров с README.

## 8. Критерии завершения

- [ ] Шаги 1–6 выполнены.
- [ ] Быстрый уровень — база + 16 (на `49e75bd`: 2193 собрано), зелёный; полный прогон — зелёный.
- [ ] `Grep "shutil.rmtree(output_dir)" numerical_solver/gpn_multiphase_solver` — пусто (оба места через `_clear_output`).
- [ ] Пример 01 из worktree отработал с кодом 0, рисунки перестроены в `output/`.
- [ ] `.gitignore` игнорирует `numerical_solver/examples/**/output[._]*/` (`git check-ignore`, шаг 4).
- [ ] README §3.4, §3.6, README примеров, справка `run`, `CHANGELOG.md` описывают поведение §4.2.
- [ ] Vault: новая заметка решения, правки двух заметок, реестр, `index.md`.
- [ ] Issue #138 прокомментирован с результатом (`/implement`), закрывается при влитии (`/merge`).

## 9. Связь с другими задачами

- [[FEAT-030]] (#104) — решение об очистке после расчёта; не меняется.
- [[FEAT-036]] (#136, влита `c156604`) — очистка у книги до расчёта; меняется способ очистки и текст отказа.
- [[FEAT-038]] (#137, влита `225985e`) — README сдвинут на +24 строки; выпуск `1.0.0` правит журнал (шаг 5).
- [[FEAT-031]] (#114) — поставка; README §3.4 — для инженера заказчика.

## 10. Обнаруженные проблемы

- **DEBT-083** (зарегистрирована при планировании, без issue): `--output`, указывающий на существующий **файл**, — `run_case` по конфигу считает задачу, а затем `output_dir.mkdir(parents=True, exist_ok=True)` падает `FileExistsError` (проверено: `mkdir` на существующем файле с `exist_ok=True` — `FileExistsError`, errno 17) — трассировка после расчёта, как в DEBT-082. У книги тот же случай ловится (`write_files` → `OSError` → `CaseConfigError`). Не блокирует DEBT-082; естественное место проверки — `_check_output_free` (две строки), но объём задачи согласован без неё.

## 11. Аудит 1 (2026-10-18)

Фокус — предметная суть: верна ли посылка «переименование — неразрушающая проверка», полон ли анализ.

**Эмуляция плана на копии** (`vault/issues/debt-082/probes/plan_emulate.py`): `git archive 49e75bd numerical_solver .gitignore` → правки шагов 1–5 строками «До:»/«После:» плана (каждая нашла ровно одно вхождение), тестовый файл — `plan_code/test_output_dir.py`. Файлы кода, тестов, примеров, журнала и `.gitignore` на `35d2980` побитово те же, что на `49e75bd`, — эмуляция действительна для новой базы. Итоги:

| Проверка | Результат |
|---|---|
| `tests/test_output_dir.py` (Windows) | 15 passed за 16 с, включая настоящие блокировки (открытый файл, консоль, файл открыт после `Simulator.run`) |
| `test_output_dir.py`, `test_cli.py`, `test_workbook_run.py`, `test_example_scripts.py`, `test_eq_references.py` | 160 passed, 2 skipped (оба — `test_eq_references.py:80`, «нет vault/knowledge/» — только в копии без vault) |
| `--collect-only` | 2477 всего, 2193 в быстром — как в плане |
| быстрый уровень целиком | 2190 passed, 3 skipped (2 — копия без vault, 1 — черновик книги вне git) за 190 с; в worktree — 2192 passed, 1 skipped |
| пример 01 по инструкции шага 4 (`PYTHONPATH` на копию) | код 0, «Результаты: …\examples\01_single_phase_no_jt\output», рисунки перестроены там; пакет взят из копии |

Копия удалена после разбора; скрипт оставлен для повторного замера.

**Найдено и исправлено:**

1. 🟡 `_sibling` брал `path.resolve()`: на диске `subst` (и на сетевом) `resolve()` подменяет букву диска реальным путём (проба F) — сообщения и имя запасного каталога назвали бы путь, которого инженер не вводил. → `Path(os.path.abspath(path))`; ожидания тестов — `out.with_name(...)`, `out.parent`; проба D перезапущена.
2. 🟡 База ушла: FEAT-038 влита во время аудита (`225985e`, `35d2980`). → Исходная точка и пояснение обновлены; число тестов то же (2461 / 2177), файлы плана, кроме README, не тронуты.
3. 🟡 Номера строк README в шаге 5 сдвинулись на +24 (FEAT-038). → 258-262, 264-268, 351-354.
4. 🟡 `numerical_solver/examples/README.md:287-292` повторяет правило очистки и коды возврата — план его не правил, после реализации README примеров разошёлся бы с README пакета. → Шаг 5, п. 5.
5. 🔵 Посылка «Excel держит файл без права удаления, как `open()` Python» проверялась только эмуляцией. → Проба E на настоящем Excel: переименование — WinError 5, всё цело; `rmtree` — WinError 32, удалён файл.
6. 🔵 Время быстрого уровня не было записано. → 190 с на копии (п. 7 «Как начать»).

## 12. Реализация (2026-10-18)

Ветка `refactor/debt-082/locked-output-dir`, worktree `.worktrees/debt-082`, от `e39fd5b` (база `35d2980` + предварительный коммит). Шаги выполнены по плану без отступлений; код функций и тесты — дословно блоки §5 (`plan_code/test_output_dir.py`).

| Шаг | Коммит | Быстрый уровень |
|---|---|---|
| база | — | 2176 passed, 1 skipped за 168 с (2461 собрано) |
| 1 функции | `91ac121` | 2187 passed, 1 skipped |
| 2 `run_case` по конфигу | `1bd8fb4` | 2192 passed, 1 skipped |
| 3 книга | `e68f69b` | 2192 passed, 1 skipped |
| 4 примеры, `.gitignore` | `ed1888f` | 2192 passed, 1 skipped; `test_example_scripts.py` 84 passed; пример 01 из worktree — код 0, рисунки в `output/` |
| 5 документация | `7517a96` | 2477 собрано; `test_cli.py` + `test_eq_references.py` 46 passed |
| 6 vault | `d3059bf` | `test_eq_references.py` 13 passed |

Полный прогон: 2476 passed, 1 skipped (`test_xlsx_reader.py:476`, черновик книги вне git) за 714 с.

**Влитие.** Пока шла реализация, база выпустила `1.0.0` (`e100fcb`, `9b7dabd`, `024e19a`): «Не выпущено» журнала сведено в `## 1.0.0 — 2026-10-18`, над ним — пустой `## Не выпущено`. Пробное слияние (`git merge-tree --write-tree numerical_scheme/implementation HEAD`) — один конфликт, `numerical_solver/CHANGELOG.md`. Разрешение: блок «### Исправлено» ветки — под пустым `## Не выпущено`, раздел `1.0.0` базы — без изменений. Остальные файлы базы (`__version__` `1.0.1.dev0`, номер прототипа, `pyproject.toml`) с веткой не пересекаются.
