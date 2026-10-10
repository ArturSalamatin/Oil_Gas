---
tags:
  - план
  - инфраструктура
date: 2026-10-10
issue: DEBT-046
github: 77
branch: refactor/debt-046/examples-scripts-import-check
status: в процессе
worktree: .worktrees/debt-046
audit:
  date: 2026-10-10
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# DEBT-046: проверка имён скриптов `examples/` без их исполнения

**Реестр:** `vault/roadmap/известные баги и технический долг.md`, секция DEBT-046.
**GitHub:** [#77](https://github.com/ArturSalamatin/Oil_Gas/issues/77) (тело — `vault/issues/debt-046/01-issue-body.md`).
**Ветка:** `refactor/debt-046/examples-scripts-import-check` (не существует; создаётся `/implement` в worktree `.worktrees/debt-046`).
**База:** `numerical_scheme/implementation`, HEAD `7b34a33` (2026-10-10). Пробы сняты на `51a4d8e`; `git diff --stat 51a4d8e 7b34a33 -- numerical_solver/examples numerical_solver/tests/test_examples.py numerical_solver/tests/conftest.py` пуст — замеры действительны.
**Подтип:** инфраструктура (тест).

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай реестр (секция DEBT-046) и тело issue `vault/issues/debt-046/01-issue-body.md` — там таблица непокрытых скриптов и классы поломок (а)–(д).
3. Worktree (делает `/implement`): `git worktree add .worktrees/debt-046 -b refactor/debt-046/examples-scripts-import-check numerical_scheme/implementation`. Проверка базы: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`.
4. Python — venv основного каталога (в worktree своего нет):
   ```powershell
   $py = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-046\numerical_solver
   ```
   Пакет `gpn_multiphase_solver` установлен в venv в режиме editable (`.venv\Lib\site-packages\__editable__.gpn_multiphase_solver-0.1.0.pth` → основной каталог). `python -m pytest` из `numerical_solver/` worktree кладёт каталог запуска в `sys.path` первым — берётся пакет worktree. Скрипт, запущенный напрямую, получает в `sys.path` свою папку, не каталог запуска, — и пакет основного каталога. Поэтому пробы вставляют `Path.cwd()` первым и печатают путь пакета — сверять.
5. Baseline:
   ```powershell
   & $py -m pytest tests/ --collect-only -q                 # ожидается 1429 tests collected
   & $py -m pytest tests/ -m "not slow" -q                  # ожидается 1179 passed (250 deselected), ~70 с
   ```
   Запомнить оба числа и время быстрого уровня.
6. Начать с шага 2 (шаг 1 — baseline выше). После каждого шага — тест шага и регресс по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

## Решения пользователя (2026-10-10)

Вопросы и замеры — в разговоре планирования; варианты — раздел 3.

1. **Механизм — статический.** Текст скрипта разбирается модулем `ast`, скрипт не исполняется. Варианты с импортом файла (`runpy`, как в DEBT-031) отклонены: пропускают импорты в функциях и в блоке `__main__`, обращения `tpa.report`; требуют правки `spatial_convergence.py`; дают ложное срабатывание (раздел 3).
2. **Охват — все `.py` в `examples/`** (45 файлов: 22 `main.py`, 10 скриптов ручного запуска, 13 общих модулей), список строится по диску.
3. **Тест DEBT-031 `test_convergence_users_import` удалить** — новый тест покрывает его содержание (проба: `run_series` и потеря `from copy import deepcopy` пойманы).
4. **Сверять именованные аргументы `run_example(...)` с её сигнатурой.**

Не решалось пользователем, выбрано планом (возразить на аудите): тест — в **новом файле** `numerical_solver/tests/test_example_scripts.py`, а не в `test_examples.py`. Причины: `test_examples.py` — 2700+ строк о расчётах примеров, проверка текста скриптов к ним не относится; вспомогательных функций ~120 строк; VAL-005 (план готов, не реализован) правит `test_examples.py` в начале и в конце — отдельный файл не конфликтует.

## 1. Текущее состояние

### 1.1. Что не проверяется

- Скрипты `examples/` запускаются вручную. Фикстура `results` (`numerical_solver/tests/test_examples.py:83-136`: `_run`, `_LazyResults`, `results`) считает примеры через `load_config` + `SimulatorFactory.from_config`, минуя `main.py`; `main.py` тесты только читают как текст и ищут строки (`test_examples.py:1780`, `:1790`, `:2001`, `:2012`, `:2145`, `:2268`, `:2273`, `:2427`, `:2612`, `:2836`).
- Единственный тест, исполняющий скрипты, — `TestSharedChecks::test_convergence_users_import` (`numerical_solver/tests/test_examples.py:800-840`, DEBT-031): `runpy.run_path` трёх файлов (`convergence.py`, `energy_balance_convergence.py`, `04a_high_gas_saturation/grid_convergence.py`) с `run_name="__import_check__"` и проверка `LOAD_GLOBAL` в теле `run_series` через `dis`.
- Общие модули (`two_phase_analytics.py`, `example_runner.py`, …) тесты импортируют, но импорты **внутри их функций** исполняются, только если тест вызывает именно эту функцию.

### 1.2. Опись (проба `inventory`, `vault/issues/debt-046/probes/inventory.out.txt`)

45 файлов `examples/**/*.py`. Без защиты `if __name__ == "__main__"`: `01_single_phase_no_jt/spatial_convergence.py` (расчёт N = 50/200/800 и запись PNG/EMF на верхнем уровне, строки 106–161), `compare_script_copies.py` (цикл по группам, безвреден), общие модули `closed_form.py`, `convergence.py`, `example_runner.py`, `figure_io.py`, `pvt_plot.py`, `relperm_plot.py`, `rs_analytics.py`. Импорты из `examples/` и пакета внутри функций или в блоке `__main__` (их не исполняет импорт файла): `main.py` 01–05 (`SimulatorFactory`, `load_config`, `temperature_asymptotics as ta`), `closed_form.py`, `convergence.py`, `energy_balance.py`, `energy_balance_convergence.py`, `mass_balance.py`, `pvt_plot.py`, `relperm_plot.py`, `two_phase_analytics.py` (перечень — по `red.out.txt`, столбец «только 2» для `SimulatorFactory` и `load_config`). Обращения `alias.name` к модулям `examples/`: 13 мест — 12 к `tpa`/`ta` (`tpa.report`, `tpa.SG_EPS`, `tpa.degassing_front`, `tpa._build_relperm`, `tpa.solve_closed`, `ta.single_phase_asymptote`; `main.py` 02–05 и `closed_form_convergence.py`) и `eb.compute_balance` в `verify_balance_vs_solver.py`. Вызовы `run_example(...)`: 22, по одному в каждом `main.py`.

### 1.3. Baseline

- `7b34a33`: 1429 тестов, быстрый уровень — 1179 (250 с меткой `slow`).
- `run_example` (`numerical_solver/examples/example_runner.py:80-83`): `(config_path, output_dir, title, overlays=None, n_profiles=None, steady_state=True)`, без `**kwargs`.
- Python venv — 3.13.3; проект заявляет 3.10+. Код плана версионно-нейтрален: `LOAD_GLOBAL` и его `argval` (имя) одинаковы в 3.10–3.13; в 3.10–3.11 списковые включения — отдельные code-объекты, их обходит рекурсия `_nested_code`.

## 2. Целевое состояние

- Новый файл `numerical_solver/tests/test_example_scripts.py`:
  - `test_script_names_resolve[<файл>]` — 45 элементов (по одному на `.py` в `examples/`): все имена, которые файл берёт из общих модулей `examples/`, из модулей своей папки, из пакетов `gpn_multiphase_solver` и `radial_blackoil`, существуют; глобальные имена функций связаны в модуле; именованные аргументы `run_example(...)` есть в её сигнатуре.
  - `test_checker_sees_broken_names[<класс>]` — 8 элементов: на синтетическом скрипте в `tmp_path` проверка замечает пропавшее имя каждого класса.
- `test_convergence_users_import` удалён; на его месте — комментарий-указатель.
- `numerical_solver/examples/README.md`, раздел «Автоматические тесты» — абзац о новой проверке.
- Число тестов: 1429 − 1 + 53 = **1481**; быстрый уровень: 1179 − 1 + 53 = **1231**. Новые тесты без метки `slow` (не используют `results`), ~3 с.
- Код решателя, примеров, конфигов не меняется; выход примеров побитово тот же.

## 3. Варианты и выбор

Замеры — `vault/issues/debt-046/probes/plan_probe.py` (режимы `inventory`, `v1`, `v2`, `red`, `static_g`), выводы `*.out.txt` рядом. Классы поломок: (а) `from M import name` на верхнем уровне; (б) то же внутри функции или в блоке `__main__`; (в) `alias.name` при `import M as alias`; (г) имя, нужное функции, но не связанное в модуле (потерянная строка импорта самого файла); (д) атрибуты объектов и аргументы вызовов.

| Вариант | Суть | Ловит | Замер |
|---|---|---|---|
| 1. `runpy` + `LOAD_GLOBAL` | обобщение теста DEBT-031 на все файлы | (а), (г) | удалено `SimulatorFactory` — пропущено 10 файлов из 17 (один из них — `spatial_convergence.py`, который вариант 1 импортировать не может); удалено `two_phase_analytics.report` — пропущены все 3 пользователя; ложное срабатывание: `name` в генераторе блока `__main__` `temperature_asymptotics.py:117-120`; `spatial_convergence.py` нельзя импортировать (расчёт) |
| 2. AST | разбор текста, `hasattr` у импортированных модулей | (а), (б), (в) | все пользователи пойманы; 150 имён, 0 ложных; 0.37 с с загруженными модулями |
| 2 + статическая (г) — **выбран** | вариант 2 + `LOAD_GLOBAL` вложенных code-объектов против имён, связанных на уровне модуля по AST | (а)–(г) | 45 файлов: 0 ложных за 0.33 с; потерянные `from copy import deepcopy` (`convergence.py`) и `import two_phase_analytics as tpa` (`03/main.py`) пойманы |
| + сверка `run_example` | `inspect.signature(run_example).bind(...)` по вызовам | часть (д) | переименование `title → figure_title` поймано во всех 22 `main.py` |
| 3. `runpy` + AST | оба механизма | (а)–(г) | минусы варианта 1 (правка примера, фильтр блока `__main__`) без выигрыша перед выбранным |
| 4. Линтер | ruff/pyflakes F821 | только имена своего файла | в venv линтера нет; чужие модули не разрешает |
| 5. Пробный прогон скриптов | исполнять на малой сетке | всё | параметризация каждого скрипта, минуты, запись файлов — несоразмерно |

Не ловится выбранным: атрибуты объектов (`sim._energy._rock` — `main.py` 01, 02, `spatial_convergence.py`, `check_slopes.py`), типы аргументов, позиционные аргументы `*args`. Это ограничение, записано в docstring теста.

Красное состояние **кода плана** на настоящих файлах (`probes/red_plan_check.py`, вывод `red_plan_check.out.txt`): 10 удалённых имён — помечены ровно файлы, использующие имя; лишних нет. Расхождения с грубым поиском по тексту объяснены: `plot_profiles_50k.py:32` и `temperature_asymptotics.py:32` определяют свои `S_TO_DAY` и `SG_EPS`; `report` входит в другие имена (`report_rs`, `report_relperm`); `closed_form_convergence.py` берёт `solve_closed` через реэкспорт `tpa.solve_closed` — пойман при удалении из `two_phase_analytics`, а при удалении из `closed_form` падает сам реэкспорт (`two_phase_analytics.py:222`).

## 4. Подводные камни

- ✅ **Все места вызова удаляемого теста.** `grep test_convergence_users_import` по коду — только `numerical_solver/tests/test_examples.py:800`. Упоминания в vault (план и issue DEBT-031, реестр) — история, не править.
- ✅ **Зависимости пакетов.** Только стандартная библиотека (`ast`, `dis`, `inspect`, `importlib`, `functools`, `types`, `builtins`) и pytest. `pyproject.toml` не меняется.
- ✅ **Обратная совместимость.** Код решателя и примеров не меняется.
- ⚠️ **Побочные эффекты импорта.** Тест импортирует модули, из которых скрипты берут имена: общие модули `examples/` (их импортируют и другие быстрые тесты — `test_pipeline_writes_output`, `test_mass_balance.py`), пакет, прототип. Сами скрипты не импортируются: `spatial_convergence.py` и `compare_script_copies.py` не исполняются.
- ⚠️ **Откат `sys.path` после теста** (аудит 1). `monkeypatch.syspath_prepend` при откате восстанавливает `sys.path` целиком — исчезают и вставки, сделанные во время теста импортированными модулями (общие модули `examples/` при импорте кладут в `sys.path` свои каталоги), а сами модули остаются в `sys.modules`. Файл `test_example_scripts.py` идёт в сессии 6-м из 29, раньше `test_examples.py`: тест, позже импортирующий новый модуль в расчёте на чужую вставку, упал бы только при общем прогоне. Замер аудита: быстрый уровень с копией теста на её месте в порядке файлов — **1232 passed** (`probes/audit1_fast_tier.out.txt`; единственное предупреждение — старое, `test_val002.py`, устаревшая фикстура уровня класса). Тот же откат делал и удаляемый тест DEBT-031 (`monkeypatch.setattr(sys, "path", list(sys.path))`).
- ⚠️ **Модуль из папки примера** (`import own_helper` из `main.py` в той же папке) грузится по пути файла (`importlib.util.spec_from_file_location`) под уникальным именем, папка в `sys.path` не кладётся (в ней `main.py`). Сейчас таких модулей нет; появится с VAL-005 (`examples/18_prototype_input/prototype_input.py`, `main.py` 18 делает `import prototype_input`). Проверка своего модуля — синтетический случай `v_own_folder_module_alias`. Без этой ветки `_module_for` проверка не просто пропустила бы такой модуль: `importlib.util.find_spec("prototype_input")` вернёт `None` (папки примера в `sys.path` нет), и `main.py` 18 упал бы ложным «нет модуля». Ограничение: модуль папки, импортирующий соседа по папке, при загрузке по пути не найдёт его — тест упадёт с `ModuleNotFoundError`; тогда класть папку в `sys.path` на время загрузки.
- ⚠️ **Удалённый целиком общий модуль.** Модуль, которого нет ни в `examples/`, ни в папке скрипта, ни среди установленных (`importlib.util.find_spec`), — проблема «нет модуля» (синтетический случай `removed_module`). Иначе удаление `two_phase_analytics.py` выглядело бы как «сторонний модуль, не проверяется».
- ⚠️ **Чего на текущем коде нет, но даст ложное падение** (аудит 1; проба `static_g`: `import *` — ни в одном файле). (1) `from M import *` — `_module_level_names` добавит имя `*`, а не имена модуля: каждое имя из него, взятое в функции, станет ложной находкой (г). (2) Необязательный сторонний модуль в `try: import X / except ImportError:` — если `X` не установлен, `find_spec` вернёт `None` и будет ложное «нет модуля». Если такое появится — явный импорт вместо `*`; для необязательного модуля — пропуск `ImportFrom`/`Import` внутри `try` с обработчиком `ImportError` в `_script_problems`.
- ⚠️ **Ложные срабатывания (в).** Локальная переменная или параметр с именем алиаса (`def f(tpa): tpa.x`) даст ложное «нет имени». На текущем коде 0 (проба `v2`). Если появится — переименовать переменную в скрипте.
- ⚠️ **Ложные срабатывания (г).** Имена уровня модуля собираются по AST, включая блок `__main__`, `global`, `try/except`, циклы. Аннотация без значения (`x: int`) считается связанной — пропуск, не ложное срабатывание.
- ✅ **Циклические импорты.** Новый файл ничего не экспортирует.
- ✅ **Docstrings / `\eqref{}`.** Не затрагиваются.
- ✅ **Конфиги.** Не меняются.
- ⚠️ **Связь с другими задачами.** VAL-005 (план `vault/plans/val-005 prototype-template-example.md`, не реализован): добавляет `examples/18_prototype_input/{main.py, prototype_input.py}`. Если DEBT-046 влит раньше — у VAL-005 тестов на 2 больше ожидаемого (два новых элемента `test_script_names_resolve`), и его новые файлы должны пройти проверку: `main.py` 18 вызывает `run_example(config_path=…, output_dir=…, title=…, n_profiles=6, steady_state=False)` — по сигнатуре; `prototype_input.report_and_plot` — существует в модуле; `radial_blackoil.xlsxio.read_workbook_tables`, `radial_blackoil.runner.run_workbook` (импорты внутри функций) — проверяются по пакету прототипа. Если VAL-005 влит раньше — шаг 2 этого плана даст 47 файлов вместо 45 (ожидаемые числа тестов +2), а в `red_impl_check.out.txt` изменятся два числа: `figure_io.export_emf` — 12 (`main.py` 18 импортирует `export_emf`), `run_example` — 23 (по `main.py` из плана VAL-005, §5.2, и черновику `vault/issues/val-005/probes/draft_18/prototype_input.py`). DEBT-048, BUG-022 правят прототип (`radial_blackoil/blackoil.py`) — переименование имени, которое берёт `prototype_input.py`, этот тест поймает (так и задумано). DEBT-031 (влит) — его тест заменяется. DEBT-037 (влит) — тот же приём «список по диску».
- ✅ **Производительность.** +~3 с к быстрому уровню (1.97 с — первый файл, холодная загрузка matplotlib/scipy; в общей сессии они уже загружены).
- ✅ **Прототип.** Не меняется.

## 5. Шаги

### Шаг 1. Подготовка

**Цель:** worktree и baseline.
**Что сделать:** «Как начать работу», пункты 3–5.
**Проверка:** 1429 collected; быстрый уровень 1179 passed.
**Оценка:** ~5 мин.

### Шаг 2. Новый тест `tests/test_example_scripts.py`

**Цель:** проверка имён всех `.py` в `examples/` без их исполнения.

**Файлы:** `numerical_solver/tests/test_example_scripts.py` (новый).

**Контекст:** код ниже прогнан пробой — копия `vault/issues/debt-046/probes/test_plan_debt046.py` отличается двумя местами: строка `EXAMPLES_DIR` (в пробе `Path.cwd() / "examples"`) и последний абзац docstring («ПРОБА ПЛАНА…»). Результат пробы: 53 passed за 2.78 с (`probes/test_plan_green.out.txt`). Почему каждый блок нужен — раздел 3 и комментарии в коде.

**Что сделать:** создать файл с содержимым:

```python
"""Имена, которые скрипты examples/ берут из других модулей, на месте (DEBT-046).

Скрипты examples/ — main.py примеров, скрипты сходимости и проверок,
общие модули — запускаются вручную, и тесты их целиком не исполняют:
фикстура results (test_examples.py) считает примеры через SimulatorFactory,
минуя main.py. Имя, удалённое или переименованное в общем модуле examples/,
в пакете решателя или в прототипе, ломало бы скрипт молча — до следующего
ручного запуска, возможно через недели и другим человеком.

Проверка статическая: текст скрипта разбирается модулем ast, сам скрипт
не исполняется — ни расчётов, ни записи файлов, ни блока __main__.
Импортируются только модули, из которых скрипт берёт имена. Ловится:
  (а) from M import name на верхнем уровне;
  (б) from M import name внутри функции или в блоке __main__ — импорт
      файла (runpy, как в DEBT-031) такие строки не исполняет;
  (в) alias.name при import M as alias: tpa.report, ta.single_phase_asymptote;
  (г) имя, нужное функции, но не связанное в модуле: потерянная строка
      импорта самого файла (deepcopy в run_series, DEBT-031);
  (д) именованные аргументы вызовов run_example(...) против её сигнатуры.
Не ловится: атрибуты объектов (sim._energy._rock), типы аргументов.
"""

import ast
import builtins
import dis
import functools
import importlib
import importlib.util
import inspect
import types
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Все .py в examples/ и в папках примеров: main.py, скрипты ручного запуска,
# общие модули. Список строится по диску, как SHARED_EXAMPLE_FILES в
# test_examples.py (DEBT-037): новый файл попадает под проверку сам.
EXAMPLE_SCRIPTS = sorted(p.relative_to(EXAMPLES_DIR).as_posix()
                         for p in EXAMPLES_DIR.rglob("*.py"))

# Пакеты, имена из которых проверяются наравне с общими модулями examples/:
# решатель и прототип гидродинамики (его код правится в проекте). Остальное —
# numpy, scipy, matplotlib, стандартная библиотека — стороннее, имена из него
# не проверяются.
CHECKED_PACKAGES = ("gpn_multiphase_solver", "radial_blackoil")

# Имена, которые Python сам кладёт в пространство имён модуля.
MODULE_DUNDERS = {"__file__", "__name__", "__doc__", "__spec__", "__loader__",
                  "__package__", "__builtins__", "__annotations__", "__cached__"}

# Узлы со своей областью имён: связанное внутри них не видно на уровне модуля.
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
           ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


@pytest.fixture(autouse=True)
def _examples_on_path(monkeypatch):
    """examples/ в sys.path на время теста — общие модули импортируются по имени, как в скриптах."""
    monkeypatch.syspath_prepend(str(EXAMPLES_DIR))


@functools.lru_cache(maxsize=None)
def _load_own(path: Path) -> types.ModuleType:
    """Модуль из папки примера, загруженный по пути файла (один раз на сессию)."""
    # Папку примера в sys.path не кладём: в ней main.py, он перекрыл бы
    # одноимённые модули для всех следующих тестов. Имя модуля уникально
    # по папке, чтобы модули разных примеров не смешались в sys.modules.
    spec = importlib.util.spec_from_file_location(
        f"_script_check_{path.parent.name}_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_for(modname: str, script_dir: Path):
    """Модуль, из которого скрипт берёт имена; None — сторонний, не проверяется."""
    top = modname.split(".")[0]
    if top in CHECKED_PACKAGES or (EXAMPLES_DIR / f"{top}.py").is_file():
        return importlib.import_module(modname)
    # Модуль из папки примера: Python кладёт папку запускаемого скрипта в
    # sys.path, поэтому main.py импортирует соседние модули по имени.
    own = script_dir / f"{top}.py"
    if script_dir != EXAMPLES_DIR and own.is_file():
        return _load_own(own)
    # Модуля нет ни в examples/, ни в папке скрипта, ни среди установленных:
    # удалён или переименован общий модуль.
    if importlib.util.find_spec(top) is None:
        raise ModuleNotFoundError(f"модуль {top} не найден")
    return None


def _module_level_names(tree: ast.Module) -> set:
    """Имена, связанные на уровне модуля: импорты, def/class, присваивания, global, блок __main__."""
    names = set(MODULE_DUNDERS)

    def visit(node, at_module):
        for child in ast.iter_child_nodes(node):
            # global x внутри функции связывает x на уровне модуля.
            if isinstance(child, ast.Global):
                names.update(child.names)
            if at_module:
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    for a in child.names:
                        names.add(a.asname or a.name.split(".")[0])
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                        ast.ClassDef)):
                    names.add(child.name)
                elif (isinstance(child, ast.Name)
                      and isinstance(child.ctx, ast.Store)):
                    names.add(child.id)
                elif isinstance(child, ast.ExceptHandler) and child.name:
                    names.add(child.name)
            visit(child, at_module and not isinstance(child, _SCOPES))
    visit(tree, True)
    return names


def _nested_code(code: types.CodeType):
    """Code-объекты функций, методов, лямбд и генераторов внутри code, рекурсивно."""
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield const
            yield from _nested_code(const)


def _script_problems(path: Path) -> list:
    """Пропавшие имена скрипта: импорты, alias.name, глобальные имена функций, run_example."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems = []
    aliases = {}   # alias → модуль: для проверки alias.name, класс (в)

    def module_or_problem(modname, lineno):
        try:
            return _module_for(modname, path.parent)
        except ImportError as exc:
            problems.append(f"строка {lineno}: нет модуля {modname} ({exc})")
            return None

    # ── (а), (б): импорты на любом уровне вложенности ──
    # ast.walk обходит всё дерево: верхний уровень, тела функций, блок
    # __main__ — независимо от того, что исполнилось бы при импорте файла.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            module = module_or_problem(node.module, node.lineno)
            if module is None:
                continue
            for a in node.names:
                if a.name == "*" or hasattr(module, a.name):
                    continue
                # from пакет import подмодуль: подмодуль может быть ещё не
                # загружен, тогда атрибута у пакета нет.
                try:
                    importlib.import_module(f"{node.module}.{a.name}")
                except ImportError:
                    problems.append(f"строка {node.lineno}: в {node.module} "
                                    f"нет имени {a.name}")
        elif isinstance(node, ast.Import):
            for a in node.names:
                module = module_or_problem(a.name, node.lineno)
                # import пакет.модуль без as связывает имя пакета, не модуля —
                # такие алиасы не проверяем.
                if module is not None and (a.asname or "." not in a.name):
                    aliases[a.asname or a.name] = module

    # ── (в): alias.name — tpa.report, ta.single_phase_asymptote ──
    # Ни импорт файла, ни LOAD_GLOBAL этого не видят: LOAD_GLOBAL даёт tpa,
    # а .report берётся у модуля только при вызове.
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and not hasattr(aliases[node.value.id], node.attr)):
            problems.append(f"строка {node.lineno}: в модуле {node.value.id} "
                            f"нет имени {node.attr}")

    # ── (г): глобальные имена функций против имён уровня модуля ──
    # Функция берёт имя модуля инструкцией LOAD_GLOBAL при вызове; если
    # строку импорта удалили, ошибка появится только при вызове функции.
    # Код уровня модуля (LOAD_NAME) пропускаем: его имена — из (а), (б).
    bound = _module_level_names(tree)
    for code in _nested_code(compile(tree, str(path), "exec")):
        for ins in dis.get_instructions(code):
            if (ins.opname == "LOAD_GLOBAL" and ins.argval not in bound
                    and not hasattr(builtins, ins.argval)):
                problems.append(f"{code.co_name} (строка {code.co_firstlineno}): "
                                f"имя {ins.argval} не связано в модуле")

    # ── (д): именованные аргументы run_example(...) ──
    # main.py 17 из 22 примеров — только вызов run_example; переименованный
    # параметр (title → figure_title) ломал бы их TypeError при запуске.
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "run_example"]
    runner = importlib.import_module("example_runner") if calls else None
    if runner is not None and hasattr(runner, "run_example"):
        signature = inspect.signature(runner.run_example)
        for call in calls:
            try:
                signature.bind(*call.args, **{k.arg: k.value
                                              for k in call.keywords if k.arg})
            except TypeError as exc:
                problems.append(f"строка {call.lineno}: run_example(...) — {exc}")

    # Одно пропавшее имя встречается в функции несколько раз — без повторов.
    return list(dict.fromkeys(problems))


@pytest.mark.parametrize("script", EXAMPLE_SCRIPTS)
def test_script_names_resolve(script):
    """Всё, что скрипт берёт из общих модулей, решателя и прототипа, существует."""
    problems = _script_problems(EXAMPLES_DIR / script)
    assert not problems, f"examples/{script}:\n  " + "\n  ".join(problems)


# Поломка каждого класса на синтетическом скрипте. Без этих тестов зелёный
# test_script_names_resolve не отличить от проверки, которая ничего не видит.
# Во всех случаях пропавшее имя содержит «no_such» — проверяем, что замечено
# именно оно, а не что-то постороннее. Ключи — латиницей: pytest экранирует
# не-ASCII в именах тестов (а…), имя упавшего случая было бы нечитаемо.
# Первая буква — класс из docstring: a, b, v, g, d = (а), (б), (в), (г), (д).
BROKEN_SNIPPETS = {
    "a_top_level_import": "from figure_io import no_such_name\n",
    "b_import_in_function": (
        "def f():\n"
        "    from gpn_multiphase_solver.factory import no_such_factory\n"),
    "b_import_in_main_block": (
        'if __name__ == "__main__":\n'
        "    from closed_form import no_such_name\n"),
    "v_module_alias": (
        "import two_phase_analytics as tpa\n\n"
        "def f():\n"
        "    return tpa.no_such_name\n"),
    "v_own_folder_module_alias": (
        "import own_helper\n\n"
        "def f():\n"
        "    return own_helper.no_such_name\n"),
    "g_name_without_import": (
        "def f(config):\n"
        "    return no_such_function(config)\n"),
    "d_run_example_keyword": (
        "from example_runner import run_example\n"
        "run_example(config_path=1, output_dir=2, title=3, no_such_arg=4)\n"),
    "removed_module": "import no_such_module\n",
}


@pytest.mark.parametrize("case", sorted(BROKEN_SNIPPETS))
def test_checker_sees_broken_names(tmp_path, case):
    """Проверка замечает пропавшее имя каждого класса."""
    # Папка примера с соседним модулем own_helper.py — как main.py,
    # импортирующий модуль из своей папки.
    folder = tmp_path / "99_synthetic"
    folder.mkdir()
    (folder / "own_helper.py").write_text("PRESENT = 1\n", encoding="utf-8")
    script = folder / "main.py"
    script.write_text(BROKEN_SNIPPETS[case], encoding="utf-8")

    problems = _script_problems(script)
    assert any("no_such" in p for p in problems), (
        f"{case}: пропавшее имя не замечено, найдено: {problems}")
```

**Проверка после шага:**
- Сверка с пробой: `git diff --no-index ..\vault\issues\debt-046\probes\test_plan_debt046.py tests\test_example_scripts.py` — отличия только в строке `EXAMPLES_DIR` (с комментарием «ПРОБА…») и в абзаце docstring «ПРОБА ПЛАНА…».
- `& $py -m pytest tests/test_example_scripts.py -q` → **53 passed** (45 + 8), ~3 с. Если VAL-005 уже влит — 55 passed (два файла примера 18).
- Красное состояние на коде ветки: `& $py ..\vault\issues\debt-046\probes\red_plan_check.py impl` → строка `проверка:` указывает на `tests\test_example_scripts.py` worktree, `пакет:` — на `gpn_multiphase_solver` worktree; числа «помечено» совпадают с `red_plan_check.out.txt` (11, 3, 17, 14, 4, 3, 3, 3, 1, 2; `run_example` — 22; `deepcopy` и `tpa` пойманы). Вывод — `red_impl_check.out.txt`.
- Регресс: быстрый — 1179 + 53 = **1232 passed**.

**Подводные камни:** раздел 4 — модуль папки примера, удалённый модуль, ложные (в).
**Зависимости:** требует шаг 1; блокирует шаг 3 (старый тест удаляется после того, как новый зелёный — покрытие не проседает ни на одном коммите).
**Оценка:** ~200 строк (код готов), ~15 мин.

### Шаг 3. Удалить `test_convergence_users_import`

**Цель:** убрать дублирующий тест DEBT-031 (решение пользователя 3).

**Файлы:** `numerical_solver/tests/test_examples.py`, строки 800–841 (метод класса `TestSharedChecks` и пустая строка после него).

**Контекст:** тест импортирует три файла через `runpy` и проверяет `LOAD_GLOBAL` в теле `run_series`. Новый тест проверяет те же три файла и сильнее: проба — `from convergence import run_series` (класс (а)) и потеря `from copy import deepcopy` (класс (г), `run_series (строка 38): имя deepcopy не связано в модуле`). Два теста на одну поломку дали бы двойное падение.

**Что сделать:** удалить метод целиком — от строки `    def test_convergence_users_import(self, monkeypatch):` до строки `                f"неопределённые имена {missing}")` включительно и следующую пустую строку. На его место (между `test_shared_modules_exist` и `test_energy_balance_reported_for_all_examples`) — комментарий:

До (строки 794–842, сокращено):
```python
    def test_shared_modules_exist(self):
        """Общие модули на месте — иначе примеры не считают проверки."""
        for module in SHARED_CHECK_MODULES + ["convergence.py"]:
            path = EXAMPLES_DIR / module
            assert path.is_file(), f"нет общего модуля examples/{module}"

    def test_convergence_users_import(self, monkeypatch):
        """convergence.py и скрипты на run_series импортируются (DEBT-031).
        ...
            assert not missing, (
                f"examples/{script}: run_series ссылается на "
                f"неопределённые имена {missing}")

    def test_energy_balance_reported_for_all_examples(self, tmp_path):
```
После:
```python
    def test_shared_modules_exist(self):
        """Общие модули на месте — иначе примеры не считают проверки."""
        for module in SHARED_CHECK_MODULES + ["convergence.py"]:
            path = EXAMPLES_DIR / module
            assert path.is_file(), f"нет общего модуля examples/{module}"

    # Имена, которые скрипты examples/ берут из общих модулей, проверяет
    # tests/test_example_scripts.py (DEBT-046) — без исполнения скриптов.
    # Он заменил тест импорта convergence.py и его пользователей (DEBT-031).

    def test_energy_balance_reported_for_all_examples(self, tmp_path):
```

**Проверка после шага:**
- Поиск `test_convergence_users_import|import runpy|runpy\.run_path` по `numerical_solver/tests/` — пусто (на `7b34a33` это только удаляемый тест, строки 800, 811, 822). Просто `runpy` искать нельзя: слово есть в docstring нового `test_example_scripts.py` («импорт файла (runpy, как в DEBT-031)»).
- `& $py -m pytest tests/ --collect-only -q` → **1481** (1429 − 1 + 53).
- Регресс: быстрый → **1231 passed**.

**Зависимости:** требует шаг 2.
**Оценка:** −41 / +3 строки, ~5 мин.

### Шаг 4. `examples/README.md` — раздел «Автоматические тесты»

**Цель:** читатель README знает, что скрипты проверяются и как.

**Файлы:** `numerical_solver/examples/README.md`, раздел «## Автоматические тесты» (строки 775–787).

**Что сделать:** после абзаца «Проверяется: расчёт завершается, … обязательные разделы).» (строка 787) добавить пустую строку и абзац:

```markdown
Скрипты `examples/` — `main.py` примеров, скрипты сходимости и проверок,
общие модули — проверяет `tests/test_example_scripts.py`: всё, что скрипт
берёт из общих модулей, решателя и прототипа, существует — импорты, в том
числе внутри функций и в блоке `__main__`, обращения вида `tpa.report`,
именованные аргументы `run_example`. Скрипты при этом не исполняются: текст
разбирается модулем `ast`, расчёты не запускаются.
```

**Проверка после шага:** документ — `& $py -m pytest tests/ --collect-only -q` → 1481 (README проверяется только на существование, `test_examples.py:166`).
**Оценка:** +7 строк, ~3 мин.

### Шаг 5. Vault

**Цель:** зафиксировать решение и результат.

**Файлы:**
- `vault/knowledge/decisions/имена скриптов examples проверяются разбором AST — импорт файла не видит импорты в функциях и обращения к модулю через точку.md` (новая заметка): почему не `runpy` (замеры раздела 3: пропуски (б) и (в), ложное срабатывание `temperature_asymptotics.py:117-120`, расчёт на верхнем уровне `spatial_convergence.py`); классы (а)–(д) и что ловит каждый механизм; ограничения (атрибуты объектов, ложные (в) при затенении алиаса, модуль папки, импортирующий соседа, `import *`, необязательный импорт в `try`); ссылки на DEBT-031, DEBT-037, DEBT-046, пробы `vault/issues/debt-046/probes/` и на заметку о политике общих модулей `[[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]]` (там `compare_script_copies.py` и защита от копий — соседняя проверка того же каталога).
- `vault/00-home/index.md` — ссылка на заметку в разделе решений.
- Реестр DEBT-046 — результат, статус (делает `/implement`).

**Проверка:** документы — `--collect-only -q` не нужен.
**Оценка:** ~40 строк, ~10 мин.

## 6. Тестовая стратегия

**Тест:** `test_script_names_resolve[<файл>]`
**Файл:** `numerical_solver/tests/test_example_scripts.py` (новый)
**Сценарий:** каждый из 45 `.py` в `examples/` разбирается; имена из общих модулей, модулей папки, `gpn_multiphase_solver`, `radial_blackoil` существуют; глобальные имена функций связаны; аргументы `run_example` есть в сигнатуре.
**Ожидание:** список проблем пуст для всех 45.
**Baseline:** проба на `51a4d8e` (= `7b34a33` по `examples/`): 0 проблем.
**Предотвращает:** молчаливую поломку скрипта при удалении/переименовании имени в общем модуле, пакете или прототипе; потерю строки импорта, нужной только в теле функции; переименование параметра `run_example`.

**Тест:** `test_checker_sees_broken_names[<класс>]`
**Файл:** тот же
**Сценарий:** синтетический `main.py` в `tmp_path/99_synthetic/` с соседним `own_helper.py`; 8 поломок: (а), (б) в функции, (б) в блоке `__main__`, (в) у общего модуля, (в) у модуля папки, (г), (д), удалённый модуль.
**Ожидание:** хотя бы одна проблема, содержащая «no_such».
**Предотвращает:** «зелёную» проверку, которая ничего не видит (регрессия самой проверки при правке).

**Регресс:** все существующие тесты зелёные; удаляется один тест (`test_convergence_users_import`). Решатель и примеры не меняются — тесты на `results` (метка `slow`) затрагиваться не должны; полный прогон — один раз в конце (`/implement`).

**Красное состояние на настоящих файлах** (не тест, проба): `red_plan_check.py impl` — шаг 2.

## 7. Критерии завершения

- [ ] Шаги 1–5 выполнены.
- [ ] `tests/test_example_scripts.py` — 53 passed (55, если VAL-005 влит раньше).
- [ ] `red_impl_check.out.txt` совпадает по числам с `red_plan_check.out.txt`.
- [ ] `test_convergence_users_import` удалён, на его месте комментарий-указатель.
- [ ] Всего 1481 тест; быстрый уровень 1231 passed; полный прогон зелёный.
- [ ] Код решателя, примеров и конфигов не изменён: `git diff --stat numerical_scheme/implementation...HEAD -- numerical_solver/gpn_multiphase_solver numerical_solver/examples ':!numerical_solver/examples/README.md' numerical_solver/HydroSolverPrototype` пуст (три точки — от точки ветвления: база могла уйти вперёд за время работы).
- [ ] `examples/README.md` — абзац о проверке скриптов.
- [ ] Vault: заметка-решение, `index.md`, реестр DEBT-046.
- [ ] GitHub issue #77 прокомментирован результатом (`vault/issues/debt-046/05-comment-done.md`), закрывается при `/merge`.

## 8. Обнаруженные проблемы

Новых записей в реестр нет. Наблюдения:
- Скрипты берут закрытые атрибуты объектов решателя: `sim._grid`, `sim._energy._pvt`, `sim._energy._rock` (опись — тело issue #77). Статически не проверяется; `_rock` берут только непокрытые тестами `main.py` 01, 02, `spatial_convergence.py`, `check_slopes.py`. Отдельной задачи не заводилось — решение пользователя, если понадобится.
- VAL-005: после влития DEBT-046 его ожидаемые числа тестов вырастут на 2 (раздел 4). План VAL-005 не правился — сообщить пользователю.

## 9. Пробы

`vault/issues/debt-046/probes/` (запуск — из `numerical_solver/`, команды в docstring):

| Файл | Что | Вывод |
|---|---|---|
| `plan_probe.py inventory` | опись 45 файлов | `inventory.out.txt` |
| `plan_probe.py v1` | вариант 1 (`runpy` + `LOAD_GLOBAL`), время | `v1.out.txt` — 1 ложное (`temperature_asymptotics.py`), 2.34 / 0.36 с |
| `plan_probe.py v2` | вариант 2 (AST), время | `v2.out.txt` — 150 имён, 0 замечаний, 2.35 / 0.37 с |
| `plan_probe.py red` | какие файлы ловят варианты 1 и 2 при 7 удалённых именах; (г); сигнатура | `red.out.txt` |
| `plan_probe.py static_g` | статическая (г) | `static_g.out.txt` — 0 ложных, `deepcopy` и `tpa` пойманы |
| `test_plan_debt046.py` | код плана (копия теста) под pytest | `test_plan_green.out.txt` — 53 passed, 2.78 с |
| `red_plan_check.py [impl]` | код плана на настоящих файлах: 10 удалённых имён, `title → figure_title`, две удалённые строки импорта | `red_plan_check.out.txt` (план), `red_impl_check.out.txt` (реализация) |
| `plan_code_check.py` | код шага 2 в этом файле = проба `test_plan_debt046.py` | `plan_code_check.out.txt` — отличия только в строке `EXAMPLES_DIR` и абзаце «ПРОБА ПЛАНА» |
| (команда аудита 1) | быстрый уровень с копией теста на её месте в порядке файлов (6-я из 29) | `audit1_fast_tier.out.txt` — 1232 passed, 77 с |
