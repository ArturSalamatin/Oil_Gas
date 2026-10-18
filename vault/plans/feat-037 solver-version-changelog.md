---
tags:
  - план
  - инфраструктура
date: 2026-10-18
issue: FEAT-037
github: 134
branch: feat/feat-037/solver-version-changelog
model_level: null
status: реализован
worktree: .worktrees/feat-037
audit:
  date: 2026-10-18
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# FEAT-037: версионирование решателя

**GitHub issue:** [#134](https://github.com/ArturSalamatin/Oil_Gas/issues/134)

Выделено из [[feat-031 customer-delivery-kit|FEAT-031]] (решение 41 его плана). Блокирует FEAT-031: выпуск 1.0.0 ставится механизмом этой задачи. Зависимостей нет.

## Как начать работу по этому плану

1. Прочитай этот файл целиком. Формул в задаче нет: `moments_method.tex` и `problem_statement.tex` не нужны.
2. Пробы плана — `vault/issues/feat-037/probes/plan_checks.py`, вывод — `plan_checks.out.txt` (2026-10-18, на `55868a6`, режим `--apply-plan`: правки шага 1 внесены в копию пакета): `--version` при обязательной подкоманде выходит с кодом 0; правило номера; колесо копии — `gpn_multiphase_solver-1.0.0.dev0-py3-none-any.whl`, `METADATA Version: 1.0.0.dev0`. Все 22 проверки — ОК.
   **Эмуляция аудита** — `probes/audit_apply.py [REF] [--fast]`: правки шагов 1–5 (строки блоков «После» этого плана, журнал — из его текста) на копии дерева `git archive REF`, якорь каждого «До» — ровно один раз; затем тесты и сценарий команды. Выводы: `audit_apply_HEAD.out.txt` (`4b67213`: 2294 теста, `test_packaging.py` + `test_cli.py` 33 passed, `test_pipeline_writes_output` и `run_case` 5 passed, команда и `versions.txt` — как в плане, `pip` без `--pre` берёт `1.0.0.dev0`) и `audit_apply_feat035.out.txt` (ветка FEAT-035 `9f55080`: 2401 тест, быстрый уровень 2122 passed, 3 skipped — сторожа заметок, в копии нет vault). При расхождении текста плана и пробы источник — план; проба — проверка, что он применяется.
3. Worktree и ветка — `/implement` (база `numerical_scheme/implementation`, ветка `feat/feat-037/solver-version-changelog`; на 2026-10-18 её нет).
4. Обозначения — как в `/implement`: `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas`; `<W>` = `<КОРЕНЬ>\.worktrees\feat-037`; `<PY>` = `<КОРЕНЬ>\numerical_solver\.venv\Scripts\python.exe`. Venv один, в основном каталоге: **своего `.venv` в worktree нет**. pytest из `<W>\numerical_solver` берёт пакет и прототип worktree.
5. ⚠️ **В worktree не запускать `pip install -e`.** Venv общий: установка редактируемая (`site-packages\gpn_multiphase_solver-0.1.0.dist-info`, код — из `<КОРЕНЬ>\numerical_solver`), переустановка из worktree перенаправит её на каталог worktree, и после его удаления пакет перестанет импортироваться. Номер в метаданных проверяется сборкой колеса (шаг 6), а не установкой.
6. **Порядок с FEAT-035.** На 2026-10-18 FEAT-035 (#133) реализован на ветке `feat/feat-035/workbook-to-config` (`9f55080`, worktree `.worktrees/feat-035`), но не влит. Начинать `/implement` FEAT-037 **после его влития**: обе задачи дописывают абзац в конец докстринга `cli.py`, пункт в конец списка докстринга `tests/test_cli.py` и тесты в конец `test_cli.py` — при параллельной реализации это конфликт текста при мерже. Якоря плана на ветке FEAT-035 на месте (эмуляция, п. 2).
7. Baseline (из `<W>\numerical_solver`): `<PY> -m pytest tests/ --collect-only -q` — **2288 тестов на `55868a6`/`4b67213`**; после влития FEAT-035 — **2395** (+107, эмуляция). `<PY> -m pytest tests/ -m "not slow" -q` — быстрый уровень. Прототип не меняется: его тесты и регрессия не нужны. Сверить число при baseline, ожидания плана сдвинуть на разницу. Задача добавляет 6 тестов: 2288 → 2294, или 2395 → 2401 на базе с FEAT-035.
8. **Незакоммиченные правки плана FEAT-031** в основном каталоге (решения 38–44 от 2026-10-18; 41–44 — источник этой задачи). Шаг 7 правит тот же файл. По умолчанию — закоммитить его целиком первым коммитом `/implement` вместе с материалами FEAT-037: иначе правки шага 7 смешаются с чужими незакоммиченными. Если пользователь против — правку шага 7 отложить до его коммита.
9. Докстринги (CLAUDE.md, «Файлы и код»): новая функция `_versions` — внутренняя, одна строка. В докстринг `run_case` (публичный, README §4) добавляется одна фраза; перевод его в стиль NumPy — задача FEAT-031, не эта.
10. Начни с шага 1. После каждого шага — проверка по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

## 0. Решения пользователя

**При регистрации (2026-10-18):**

1. Механизм версий выделен из FEAT-031 в отдельную задачу: библиотеку получают пользователи с регулярными выпусками, номер и журнал нужны каждому выпуску.
2. Номер до выпуска — `1.0.0.dev0` (PEP 440: разработка к 1.0.0). `1.0.0` ставится в момент выпуска: пока FEAT-035 и FEAT-036 открыты, номер не должен утверждать, что код совпадает с поставкой.
3. Вне объёма: номер прототипа `1.0.3+gpn.2` — при выпуске (решение 2026-10-11, DEBT-048); ссылки на `vault/` в README примеров 13a, 14 и в `CHANGELOG_1.0.3.md` — FEAT-031 (решение 27 его плана).

**При планировании (2026-10-18, ответы на вопросы):**

4. Запись версий в `output/` (решение 25 плана FEAT-031) — **в этой задаче**: файл `output/versions.txt` и строка в консоли.
5. Состав записи — оба пакета, а также **Python, numpy и scipy**: от их версий зависят последние разряды результатов (разреженная СЛАУ, BLAS).
6. Журнал между выпусками **сводится при выпуске по истории git**. В FEAT-037 — правило номеров и раздел «Не выпущено» с записью этой задачи. `/implement` не меняется. Описание функционала первого выпуска пишет FEAT-031 (решение 8 его плана: описание функционала, не перечень задач).
7. Ключ `gpn-solver --version` — **только номер решателя**, без импорта прототипа.

**Умолчания плана — если не возразите:**

8. Номер прототипа для записи берётся из `radial_blackoil.__version__` импортированного модуля. Метаданные pip (`importlib.metadata`) не годятся: у редактируемой установки они записаны в момент `pip install -e` и отстают от кода, а в worktree принадлежат основному каталогу. `build_info.VERSION` (`'1.0.3'`) тоже не годится: это номер, по которому регрессия прототипа сверяет эталон, а не номер дистрибутива.
9. Ключ `--version` печатает `gpn-multiphase-solver <номер>` — имя дистрибутива, а не `%(prog)s`. Имя программы зависит от способа запуска (`gpn-solver.exe`, `python -m gpn_multiphase_solver`), а печатная строка должна совпадать с первой строкой `versions.txt`.
10. `__version__` становится публичным через упоминание в README §4. В `tests/test_public_api.py` он не добавляется: литерал и его форму проверяет `test_packaging.py`, а список `test_public_api.py` относится к объектам диагностики.
11. Журнал пишется по-русски, без ID задач: для документации решение 27 плана FEAT-031 — ID не поясняются. Разделы выпусков — `## <номер> — <дата>`, подразделы «Добавлено», «Изменено», «Исправлено», «Удалено».
12. Ссылки на журнал в README — в «Составе каталога», в §1 (после проверки установки), в §4 и в §7.
13. Тест правила номера проверяет две вещи: каноническую форму PEP 440 и ровно три числа. Проба показала, что `'1.0'` по PEP 440 — каноническая форма: проверка одной каноничности пропустила бы номер из двух чисел.
14. `versions.txt` — пять строк вида «имя номер» в UTF-8. В консоль печатается одна строка «Версии: …» — третьей, после «Конфиг: …».

## 1. Текущее состояние (`55868a6`)

| Что | Где | Сейчас |
|---|---|---|
| Номер решателя | `numerical_solver/pyproject.toml:7` | литерал `version = "0.1.0"` |
| `__version__` | `numerical_solver/gpn_multiphase_solver/__init__.py` | нет; файл — одна строка докстринга |
| Метаданные установки | `numerical_solver/gpn_multiphase_solver.egg-info` (вне git) | `importlib.metadata.version("gpn-multiphase-solver")` → `0.1.0` |
| Журнал решателя | — | нет; у прототипа — `HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` (английский, по задачам) |
| Образец единого источника | `Prototype_1.0.3/pyproject.toml:11,25-28`, `radial_blackoil/__init__.py:7` | `dynamic = ["version"]`, `attr = "radial_blackoil.__version__"`, литерал `'1.0.3+gpn.1'` (DEBT-059) |
| Тесты упаковки | `numerical_solver/tests/test_packaging.py:50-80` | `_static_version(init_py)` — разбор литерала без импорта; `test_prototype_version_is_dynamic_from_literal` — образец |
| Команда | `numerical_solver/gpn_multiphase_solver/cli.py:48-80` | `_parser`: подкоманды `run`, `template` (`required=True`); ключа `--version` нет |
| Печать расчёта | `numerical_solver/gpn_multiphase_solver/report/pipeline.py:113-114` | `=== {title} ===`, `Конфиг: {config_path}` — после `load_config` и `_check_inputs_outside` |
| Каталог вывода | `pipeline.py:141-147` | очистка после расчёта, `mkdir`, затем `well_history.csv`, `profiles.csv` |
| Состав вывода в тестах | `tests/test_cli.py:39-44` (точное множество `STANDARD_FILES`), `tests/test_examples.py:605-615` — `test_pipeline_writes_output` (включение) | 12 файлов двухфазного расчёта |
| Состав вывода в документах | `numerical_solver/README.md:238-251` (§3.5), `numerical_solver/examples/README.md:318-335` | таблицы файлов |
| Прототип в пакете | `factory.py`, `hydro/prototype_adapter.py` | импорт `radial_blackoil` **только внутри функций**: модули пакета импортируются без прототипа |

`packaging` в venv есть (26.3) как зависимость pytest (`packaging>=22`); пакет решателя его не использует. `setuptools` в venv нет: колесо собирается с изоляцией сборки (setuptools ≥ 68 скачивается или берётся из кеша pip — в пробе сработало).

## 2. Анализ

### 2.1. Формулы → код

Формул нет: задача упаковки и сопровождения.

### 2.2. Обратная совместимость

- [x] Существующие тесты — без изменений, кроме двух списков состава вывода: `STANDARD_FILES` (точное множество, `test_cli.py`) и `expected` (включение, `test_examples.py`). В оба добавляется `versions.txt`.
- [x] Конфиги — без изменений.
- [x] Публичный интерфейс расширяется: `__version__`, ключ `--version`, файл `versions.txt`. Ничего не удаляется и не переименовывается.
- [x] Печать: строка «Версии: …» вставляется третьей. Тесты сверяют только строки 0 и 1 (`test_cli.py:106-107`) и вхождения подстрок (`test_examples.py:708, 746, 1012-1029`). Полный вывод ни один тест не сравнивает. Ошибка конфига по-прежнему ничего не печатает в stdout (`test_run_case_config_errors`, `test_examples.py:772-785`): версии считаются после `load_config` и `_check_inputs_outside`.
- [x] Числа расчёта не меняются: правки не касаются решателя.

### 2.3. Варианты источника номера

| Вариант | Суть | Итог |
|---|---|---|
| **А** | литерал `__version__` + `dynamic` в `pyproject.toml` | **выбран**: один источник; работает без установки и в изолированной сборке; совпадает с прототипом; проверка по готовому образцу |
| Б | `__version__ = importlib.metadata.version(...)`, номер в `pyproject.toml` | метаданные редактируемой установки отстают от кода до переустановки; в worktree принадлежат основному каталогу; без установки — `PackageNotFoundError` |
| В | `setuptools-scm`, номер из меток git | заказчик получает срез исходников без `.git` (решение 6 плана FEAT-031) — номер не получить; новая зависимость сборки |

Варианты записи версий в `output/` (файл + консоль / только файл / перенос в FEAT-031) решены пользователем — решение 4.

### 2.4. Выбор

Вариант А. Записью версий занимается `_versions()` в `report/pipeline.py`: из одного списка пар печатается строка в консоль и пишется `versions.txt`. Отдельного модуля нет: потребитель один (YAGNI). Если FEAT-036 понадобятся версии вне `run_case`, функцию перенесут тогда.

### 2.5. Подводные камни

- ✅ **Размерности, граничные случаи, численная устойчивость, ODE** — не применимо.
- ⚠️ **Метаданные редактируемой установки.** После смены номера `importlib.metadata.version("gpn-multiphase-solver")` возвращает `0.1.0` до переустановки. Запуск из `numerical_solver` находит устаревший `gpn_multiphase_solver.egg-info` каталога (проверено). Поэтому ни один тест не сверяет метаданные с литералом: проверяются `pyproject.toml` и литерал (шаг 1), а метаданные — колесом (шаг 6). После влития метаданные основного каталога обновляет переустановка (§5, «После влития»).
- ⚠️ **`pip install -e` в worktree** перенаправит общий venv на worktree — запрещено (п. 5 «Как начать»).
- ⚠️ **Правило номера.** `'1.0'` по PEP 440 — каноническая форма (проба). Поэтому тест проверяет ещё и `len(Version(v).release) == 3`.
- ⚠️ **METADATA колеса с CRLF.** Без `strip()` номер приходит с `\r` (проба, первая версия) — учтено в `plan_checks.py`.
- ✅ **Состояние при ошибке.** `versions.txt` пишется после очистки каталога вместе с остальными файлами. При отказе решателя каталог не тронут, прежний `versions.txt` соответствует прежним результатам.
- ✅ **Импорт.** В `cli.py` — `from . import __version__`: `__init__.py` содержит только литерал, поэтому `--help`, `--version` и `template` по-прежнему не импортируют scipy и прототип (это проверяют `test_template_does_not_import_solver` и новый `test_version_does_not_import_solver`). В `_versions()` `radial_blackoil` и `scipy` импортируются внутри функции, как и везде в пакете.
- ✅ **Зависимости пакета.** Новые импорты пакета — `platform` (стандартная библиотека), `radial_blackoil` и `scipy` (уже объявлены). `test_declared_dependencies_cover_imports` проходит без правки `DIST_OF_MODULE`. `packaging` импортирует только тест, а он — зависимость pytest.
- ✅ **Python 3.10.** `_pyproject()` на 3.10 пропускает тесты (`tomllib`); рабочее окружение — 3.13.3.
- ✅ **Номер разработки и pip.** Установка без PyPI (README §1: `pip install --no-index --find-links wheels gpn-multiphase-solver`) без ключа `--pre` берёт `1.0.0.dev0`, если других версий нет: pip отбрасывает предвыпуски, только когда есть подходящий выпуск (эмуляция аудита, `pip download`). Редактируемая установка — по пути, номер не участвует.
- ✅ **`versions.txt` на Windows — с CRLF:** `Path.write_text` переводит `\n` в `\r\n`. Тесты читают `read_text().splitlines()` — от переводов строк не зависят (эмуляция: 105 байт, CRLF).
- 🔵 **«Не выпущено» неполон между выпусками** — по решению 6: в разделе только запись этой задачи; изменения других задач (например, `convert` FEAT-035) сводятся при выпуске по истории git.
- ⚠️ **Связь с задачами.**
  - **FEAT-035** (#133) реализован на ветке `feat/feat-035/workbook-to-config` (`9f55080`), не влит: `cli.py` (+подкоманда `convert`, абзац в конце докстринга модуля), `test_cli.py` (+7 тестов в конце, пункт в конце списка докстринга), `io/workbook_convert.py`, `tests/test_workbook_convert.py`; README и `pyproject.toml` не меняет. Эмуляция правок этого плана на его ветке — якоря на месте, 2401 тест, быстрый уровень зелёный (п. 2 «Как начать»). Порядок — п. 6 «Как начать». Строку о `convert` в журнал FEAT-035 добавляет, только если `CHANGELOG.md` уже есть (его план, шаг 4); при порядке «FEAT-035, затем FEAT-037» её не будет — по решению 6 такие изменения сводятся при выпуске.
  - **FEAT-036** (черновик) пишет вход в `output/input/` и меняет порядок очистки каталога: `versions.txt` теперь входит в штатный набор, это учесть при его планировании.
  - **FEAT-031:** при выпуске — литерал `1.0.0`, раздел «Не выпущено» → `## 1.0.0 — <дата>` с описанием функционала, `release` в `conf.py` Sphinx — из `__version__` (импорт `gpn_multiphase_solver` дешёвый: только литерал).
- ✅ **Прототип** не меняется: регрессия не нужна. Номер прототипа здесь только читается.

### 2.6. Новые проблемы

Блокирующих нет. Неблокирующая: черновик плана FEAT-031 §3 говорит «`pyproject.toml` — 0.1.0 → 1.0.0» и «в пакете нет `__version__`», а §8 п. 3 — «механизм — FEAT-037». После влития эти места устареют — поправить в базовой ветке (шаг 7). Регистрировать отдельно не нужно.

## 3. Шаги

**Затронутые файлы** (все — `numerical_solver/`, кроме vault):

| Файл | Шаги | Что |
|---|---|---|
| `gpn_multiphase_solver/__init__.py` | 1 | литерал `__version__` |
| `pyproject.toml` | 1 | `dynamic`, `[tool.setuptools.dynamic]` |
| `CHANGELOG.md` (новый) | 2 | журнал |
| `gpn_multiphase_solver/cli.py` | 3 | `--version`, докстринг |
| `gpn_multiphase_solver/report/pipeline.py` | 4 | `_versions`, печать, `versions.txt`, докстринг `run_case` |
| `tests/test_packaging.py` | 1, 2 | +3 теста, `SOLVER_INIT`, импорт `Version` |
| `tests/test_cli.py` | 3, 4 | +3 теста, `STANDARD_FILES`, `test_run_from_foreign_directory`, докстринг |
| `tests/test_examples.py` | 4 | `expected` в `test_pipeline_writes_output` |
| `README.md`, `examples/README.md` | 5 | 6 правок + 1 |
| vault (заметка, реестр, `index.md`, черновик FEAT-031, `vault/issues/feat-037/`) | 6, 7 | |

### Шаг 1: единый источник номера

**Цель:** номер решателя — литерал `gpn_multiphase_solver.__version__ = "1.0.0.dev0"`, `pyproject.toml` читает его динамически.
**Файлы:** `numerical_solver/gpn_multiphase_solver/__init__.py`, `numerical_solver/pyproject.toml`, `numerical_solver/tests/test_packaging.py`

**Контекст:** у прототипа так сделано в DEBT-059: литерал, `dynamic = ["version"]`, `[tool.setuptools.dynamic] version = {attr = ...}`. setuptools сначала пытается прочитать литерал разбором исходника и импортирует модуль только если это не удалось; в изолированной сборке numpy нет. Тест-образец — `test_prototype_version_is_dynamic_from_literal` (`test_packaging.py:75-80`).

**Что сделать:**

1. `__init__.py` — после докстринга (докстринг не трогать, его переписывает FEAT-031):

    До:
    ```python
    """gpn_multiphase_solver — FVM solver for two-phase Black Oil with energy equation."""
    ```
    После:
    ```python
    """gpn_multiphase_solver — FVM solver for two-phase Black Oil with energy equation."""

    # Номер версии пакета (FEAT-037) — единственный источник: pyproject.toml
    # берёт его через [tool.setuptools.dynamic]. Только литерал, без вычислений
    # и импортов: setuptools читает его разбором исходника, не импортируя
    # пакет. Форма — PEP 440, три числа MAJOR.MINOR.PATCH; между выпусками —
    # суффикс .devN. Правило номеров — CHANGELOG.md.
    __version__ = "1.0.0.dev0"
    ```

2. `pyproject.toml`, секция `[project]`:

    До:
    ```toml
    [project]
    name = "gpn-multiphase-solver"
    version = "0.1.0"
    description = "FVM solver for two-phase Black Oil filtration with energy equation"
    ```
    После:
    ```toml
    [project]
    name = "gpn-multiphase-solver"
    # Номер — литерал gpn_multiphase_solver.__version__ ([tool.setuptools.dynamic]
    # ниже, FEAT-037); правило номеров — CHANGELOG.md
    dynamic = ["version"]
    description = "FVM solver for two-phase Black Oil filtration with energy equation"
    ```

3. `pyproject.toml`, перед `[tool.setuptools.packages.find]` (сейчас строка 38) — новая секция:
    ```toml
    [tool.setuptools.dynamic]
    # Единственный источник номера — литерал в gpn_multiphase_solver/__init__.py,
    # как у прототипа (DEBT-059). setuptools читает его разбором исходника, без
    # импорта пакета: в изолированной сборке numpy нет.
    version = {attr = "gpn_multiphase_solver.__version__"}

    ```

4. `test_packaging.py`:
    - импорт вверху (после `import pytest`):
      ```python
      # packaging — зависимость pytest (packaging>=22), не пакета решателя
      from packaging.version import Version
      ```
    - постоянная после `PROTO`:
      ```python
      SOLVER_INIT = SOLVER / "gpn_multiphase_solver" / "__init__.py"  # литерал __version__ решателя
      ```
    - в `TestDistributions` после `test_prototype_version_is_dynamic_from_literal`:
      ```python
      def test_solver_version_is_dynamic_from_literal(self):
          """Версия дистрибутива решателя — из gpn_multiphase_solver.__version__: один источник номера (FEAT-037)."""
          proj = _pyproject(SOLVER / "pyproject.toml")
          assert proj["project"]["dynamic"] == ["version"]
          # Статический номер рядом с dynamic — второй источник (setuptools
          # отвергает сборку), его возврат при правке pyproject.toml ловится здесь
          assert "version" not in proj["project"]
          assert proj["tool"]["setuptools"]["dynamic"]["version"] == {
              "attr": "gpn_multiphase_solver.__version__"}

      def test_solver_version_literal_follows_rule(self):
          """__version__ решателя — литерал, каноническая форма PEP 440, ровно три числа MAJOR.MINOR.PATCH."""
          # _static_version отвергает вычисляемое значение (не ast.Constant)
          text = _static_version(SOLVER_INIT)
          version = Version(text)            # InvalidVersion — не PEP 440
          assert str(version) == text, f"не каноническая форма PEP 440: {text!r} → {version}"
          # '1.0' по PEP 440 канонична (проба plan_checks.py) — число частей отдельно
          assert len(version.release) == 3, f"не MAJOR.MINOR.PATCH: {text!r}"
      ```
    - докстринг модуля: «Установка пакетов: зависимости, версия прототипа, …» → «Установка пакетов: зависимости, версии решателя (FEAT-037) и прототипа, …».

**Проверка после шага:**
- Тест: `<PY> -m pytest tests/test_packaging.py -q` — все passed, новых 2.
- Регресс: быстрый.

**Подводные камни:** 2.5 — метаданные (тест их не сверяет), правило номера.
**Зависимости:** блокирует шаги 2–4, 6.
**Оценка:** ~30 строк, 15 мин.

### Шаг 2: журнал изменений

**Цель:** `numerical_solver/CHANGELOG.md` — правило номеров и раздел «Не выпущено»; тест согласованности журнала с номером.
**Файлы:** `numerical_solver/CHANGELOG.md` (новый), `numerical_solver/tests/test_packaging.py`

**Контекст:** решения 6, 11. Читатель — команда разработки заказчика и пользователи библиотеки. Разделы выпусков сводятся при выпуске по истории git; в этой задаче — только её запись.

**Что сделать:**

1. `numerical_solver/CHANGELOG.md` — текст целиком:
    ```markdown
    # Журнал изменений gpn-multiphase-solver

    Изменения пакета `gpn-multiphase-solver` от выпуска к выпуску. Номер
    установленной версии печатает команда `gpn-solver --version` (или
    `python -m gpn_multiphase_solver --version`); из Python он доступен как
    `gpn_multiphase_solver.__version__`. Версии, которыми получены результаты
    расчёта, записаны в файле `versions.txt` каталога вывода.

    ## Правило номеров

    Номер версии — три числа MAJOR.MINOR.PATCH в форме PEP 440.

    - **MAJOR** повышается при несовместимом изменении публичного интерфейса
      пакета (README, раздел «Использование из Python»), формата файла
      конфигурации или книги ввода Excel: прежние программы, конфигурации или
      книги без правки перестают работать.
    - **MINOR** — новые возможности; прежние конфигурации и книги считаются без
      изменений.
    - **PATCH** — исправления ошибок.
    - Изменение, после которого при тех же исходных данных получаются другие
      числа, описывается в разделе выпуска отдельно: какие величины меняются и
      насколько.
    - Между выпусками номер имеет суффикс `.devN`: `1.0.0.dev0` — разработка
      к выпуску 1.0.0. Номер без суффикса ставится при выпуске.
    - Прототип гидродинамики `radial-blackoil` нумеруется отдельно:
      `1.0.3+gpn.N`, где 1.0.3 — версия исходного прототипа, N — номер набора
      изменений, внесённых в него в рамках проекта. N повышается при выпуске
      решателя, если код прототипа изменился с прошлого выпуска. Решатель
      требует ровно одну версию прототипа (`pyproject.toml`).

    Разделы выпусков — `## <номер> — <дата>`, внутри — «Добавлено»,
    «Изменено», «Исправлено», «Удалено». Изменения, ещё не вошедшие в выпуск, —
    в разделе «Не выпущено».

    ## Не выпущено

    ### Добавлено

    - Номер версии пакета: `gpn_multiphase_solver.__version__`, ключ
      `--version` команды `gpn-solver`.
    - Файл `versions.txt` в каталоге вывода расчёта: версии решателя,
      прототипа, Python, numpy и scipy, которыми получены результаты; та же
      строка выводится в консоль перед расчётом.
    - Журнал изменений (этот файл).
    ```

2. `test_packaging.py`, в `TestDistributions` после `test_solver_version_literal_follows_rule`:
    ```python
    def test_changelog_has_section_for_version(self):
        """Журнал согласован с номером: до выпуска — раздел «Не выпущено», выпуск — раздел своего номера (FEAT-037)."""
        # is_prerelease истинно для .devN, aN, bN, rcN. Ловит выпуск без
        # раздела журнала. Суффикс .dev, забытый после выпуска, не ловит:
        # номер ставит выпуск (FEAT-031), журнал за него не отвечает
        version = Version(_static_version(SOLVER_INIT))
        lines = (SOLVER / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
        if version.is_prerelease:
            assert "## Не выпущено" in lines, "номер до выпуска, а раздела «Не выпущено» нет"
        else:
            head = re.compile(rf"## {re.escape(str(version))}( |$)")
            assert any(head.match(s) for s in lines), f"нет раздела «## {version} — <дата>»"
    ```

**Проверка после шага:**
- Тест: `<PY> -m pytest tests/test_packaging.py -q` — новых 3 с шагом 1.
- Регресс: не нужен — меняются только журнал и тест; `<PY> -m pytest tests/ --collect-only -q` — 2291.

**Зависимости:** требует шаг 1.
**Оценка:** ~60 строк, 15 мин.

### Шаг 3: ключ `--version`

**Цель:** `gpn-solver --version` и `python -m gpn_multiphase_solver --version` печатают `gpn-multiphase-solver 1.0.0.dev0`, код 0, без импорта решателя и прототипа.
**Файлы:** `numerical_solver/gpn_multiphase_solver/cli.py`, `numerical_solver/tests/test_cli.py`

**Контекст:** решения 7, 9. Действие argparse `action="version"` печатает строку в stdout и вызывает `parser.exit()` — до проверки обязательной подкоманды (`add_subparsers(required=True)`). Проба: код 0, stdout `'gpn-multiphase-solver 1.0.0.dev0\n'`, без подкоманды — по-прежнему код 2.

**Что сделать:**

1. `cli.py`, докстринг модуля — абзац в конце:
    ```
    Номер версии: gpn-solver --version (FEAT-037) — номер решателя; решатель
    и прототип не импортируются.
    ```
2. `cli.py`, импорт после `from pathlib import Path`:
    ```python

    from . import __version__
    ```
3. `cli.py`, `_parser`, сразу после `p = argparse.ArgumentParser(...)`:
    ```python
    # Номер решателя (FEAT-037). Строка — имя дистрибутива, а не %(prog)s:
    # prog зависит от способа запуска (gpn-solver.exe, python -m …), а
    # строка совпадает с первой строкой versions.txt. argparse печатает её в
    # stdout и выходит с кодом 0 до проверки обязательной подкоманды.
    # Прототип не импортируется — как и для --help.
    p.add_argument("--version", action="version",
                   version=f"gpn-multiphase-solver {__version__}")
    ```
4. `test_cli.py`:
    - импорт: `import gpn_multiphase_solver` (рядом с `import gpn_multiphase_solver.report.pipeline as pipeline`);
    - докстринг модуля, список «Проверяется» — пункт в конец списка, перед пустой строкой и абзацем «Подпроцессы получают PYTHONPATH…»; точку в конце прежнего последнего пункта («…прототип не импортируются.» — пункт шаблона или, после FEAT-035, перевода книги) заменить на «;»:
      ```
        - номер версии (FEAT-037): --version без импорта решателя и прототипа;
          строка «Версии: …» в печати и versions.txt в каталоге вывода.
      ```
    - в конец файла раздел:
      ```python
      # ── Номер версии (FEAT-037) ──────────────────────────────────

      def test_version_flag(capsys):
          """--version: «gpn-multiphase-solver <номер>» в stdout, код 0 — подкоманда не нужна."""
          with pytest.raises(SystemExit) as e:
              cli.main(["--version"])
          assert e.value.code == 0
          assert capsys.readouterr().out == f"gpn-multiphase-solver {gpn_multiphase_solver.__version__}\n"


      def test_version_does_not_import_solver(tmp_path):
          """--version, как и template, не импортирует решатель, scipy и прототип: номер — литерал пакета."""
          code = ("import sys\nfrom gpn_multiphase_solver import cli\n"
                  "try:\n    cli.main(['--version'])\nexcept SystemExit as e:\n    rc = e.code\n"
                  "print(rc, 'scipy' in sys.modules, 'radial_blackoil' in sys.modules)")
          r = _run(["-c", code], cwd=tmp_path)
          assert r.returncode == 0, r.stderr[-2000:]
          assert r.stdout.split()[-3:] == ["0", "False", "False"]
      ```

**Проверка после шага:**
- Тест: `<PY> -m pytest tests/test_cli.py -q` — новых 2.
- Регресс: быстрый.

**Подводные камни:** 2.5 — импорт; FEAT-035 правит тот же `_parser`.
**Зависимости:** требует шаг 1.
**Оценка:** ~35 строк, 15 мин.

### Шаг 4: версии в выводе расчёта

**Цель:** `run_case` печатает «Версии: …» третьей строкой и пишет `versions.txt` в каталог вывода.
**Файлы:** `numerical_solver/gpn_multiphase_solver/report/pipeline.py`, `numerical_solver/tests/test_cli.py`, `numerical_solver/tests/test_examples.py`

**Контекст:** решения 4, 5, 8, 14. По результатам расчёта сейчас нельзя установить, какой версией они получены. Прототип в пакете импортируется только внутри функций — `_versions()` делает так же.

**Что сделать:**

1. `pipeline.py`, импорты: `import platform` — перед `import shutil` (порядок по алфавиту, как в блоке); `from .. import __version__` — перед `from ..factory import SimulatorFactory`.
2. `pipeline.py`, `run_case`, печать заголовка (сейчас строки 113-114):

    До:
    ```python
        print(f"=== {title} ===")
        print(f"Конфиг: {config_path}")
    ```
    После:
    ```python
        # Версии — после проверки конфига: при его ошибке stdout по-прежнему
        # пуст (test_run_case_config_errors). Тот же список пишется в
        # versions.txt после расчёта (FEAT-037)
        versions = _versions()
        print(f"=== {title} ===")
        print(f"Конфиг: {config_path}")
        print("Версии: " + ", ".join(f"{name} {ver}" for name, ver in versions))
    ```
3. `pipeline.py`, `run_case`, сразу после `output_dir.mkdir(parents=True, exist_ok=True)` (сейчас строка 143), перед `# ── Таблицы ──`:
    ```python

    # ── Версии (FEAT-037) ──
    # Какой версией получены результаты: решатель и прототип, а также Python,
    # numpy и scipy — от них зависят последние разряды чисел
    (output_dir / "versions.txt").write_text(
        "".join(f"{name} {ver}\n" for name, ver in versions), encoding="utf-8")
    ```
4. `pipeline.py`, докстринг `run_case`, первый абзац, после строки «…конфиг и его CSV внутри него — отказ до расчёта.» — две строки (без обратных кавычек: докстринги модуля их не используют):
    ```
        В нём же versions.txt — версии решателя, прототипа, Python, numpy и
        scipy (FEAT-037).
    ```
5. `pipeline.py`, новая функция перед `_print_summary`:
    ```python
    def _versions() -> list[tuple[str, str]]:
        """Версии решателя, прототипа, Python, numpy, scipy — пары (имя, номер) для versions.txt и печати. FEAT-037."""
        # Импорт здесь, как во всём пакете: прототип импортируется при сборке
        # задачи, а не при импорте модулей. Номер прототипа — из модуля,
        # который считает задачу, а не из метаданных pip: у редактируемой
        # установки они записаны при pip install -e и отстают от кода, в
        # worktree — принадлежат основному каталогу. build_info.VERSION
        # ('1.0.3') — номер для регрессии прототипа, не номер дистрибутива.
        import radial_blackoil
        import scipy
        return [("gpn-multiphase-solver", __version__),
                ("radial-blackoil", radial_blackoil.__version__),
                ("Python", platform.python_version()),
                ("numpy", np.__version__),
                ("scipy", scipy.__version__)]
    ```
6. `test_cli.py`:
    - `STANDARD_FILES`: добавить `"versions.txt"` (новой строкой списка, с комментарием `# FEAT-037: версии, которыми получены результаты`);
    - `test_run_from_foreign_directory`: докстринг «12 файлов штатного набора» → «13 файлов штатного набора, строка версий и versions.txt»; после `assert lines[1] == …`:
      ```python
      # FEAT-037: строка версий третьей и versions.txt — тот же список. Подпроцесс
      # — тот же интерпретатор и PYTHONPATH на это дерево: пары совпадают
      expected = [f"{name} {ver}" for name, ver in pipeline._versions()]
      assert lines[2] == "Версии: " + ", ".join(expected)
      assert (out / "versions.txt").read_text(encoding="utf-8").splitlines() == expected
      ```
    - в раздел «Номер версии (FEAT-037)» шага 3:
      ```python
      def test_versions_sources():
          """Пары versions.txt: решатель и прототип — литералы модулей этого дерева, затем Python, numpy, scipy.

          Ловит подмену источника метаданными pip: в основном каталоге они
          отстают от литерала до переустановки (0.1.0 на 2026-10-18).
          """
          import platform

          import numpy as np
          import radial_blackoil
          import scipy
          assert pipeline._versions() == [
              ("gpn-multiphase-solver", gpn_multiphase_solver.__version__),
              ("radial-blackoil", radial_blackoil.__version__),
              ("Python", platform.python_version()),
              ("numpy", np.__version__),
              ("scipy", scipy.__version__)]
      ```
7. `test_examples.py`, `test_pipeline_writes_output` (строка 585), список `expected` (сейчас строки 605-615) — в конец:
    ```python
        # FEAT-037: версии, которыми получены результаты
        "versions.txt",
    ```

**Проверка после шага:**
- Тест: `<PY> -m pytest tests/test_cli.py -q`; `<PY> -m pytest tests/test_examples.py -k "test_pipeline_writes_output or run_case" -q`.
- Регресс: быстрый.

**Подводные камни:** 2.2 — порядок печати; 2.5 — состояние при ошибке, импорт.
**Зависимости:** требует шаг 1; шаг 3 — для раздела тестов.
**Оценка:** ~50 строк, 25 мин.

### Шаг 5: README

**Цель:** пользователь узнаёт о номере, ключе, журнале и `versions.txt` из README.
**Файлы:** `numerical_solver/README.md`, `numerical_solver/examples/README.md`

**Что сделать** (строки — на `55868a6`):

1. `README.md`, «Состав каталога», после строки `[doc/](doc/)` (24):
    ```
    | [CHANGELOG.md](CHANGELOG.md) | журнал изменений между выпусками, правило номеров версий |
    ```
2. `README.md`, §1, после блока «Проверка установки» (73):
    ```

    Номер установленной версии решателя печатает
    `.venv\Scripts\python -m gpn_multiphase_solver --version`; изменения между
    версиями и правило номеров — в [CHANGELOG.md](CHANGELOG.md).
    ```
3. `README.md`, §3.5, таблица файлов — строка после `energy_balance.png`, `mass_balance.png` (247):
    ```
    | `versions.txt` | версии решателя, прототипа, Python, numpy и scipy, которыми получены результаты: по строке «имя номер» |
    ```
4. `README.md`, §3.5, абзац 249-251:

    До:
    ```
    В консоль выводятся сводка (давление и температура у забоя и дебиты на конец
    расчёта), невязки балансов энергии и массы, проверка равновесия $R_s$ и
    сводка PVT. Дебиты при добыче положительны. Время на всех графиках — в сутках.
    ```
    После:
    ```
    В консоль выводятся: перед расчётом — путь к файлу конфигурации и версии
    (те же, что в `versions.txt`); после расчёта — сводка (давление и
    температура у забоя и дебиты на конец расчёта), невязки балансов энергии и
    массы, проверка равновесия $R_s$ и сводка PVT. Дебиты при добыче
    положительны. Время на всех графиках — в сутках.
    ```
5. `README.md`, §4, перед «Полезные модули:» (317):
    ```
    Номер версии пакета — строка `gpn_multiphase_solver.__version__` (форма
    PEP 440; правило номеров — [CHANGELOG.md](CHANGELOG.md)).

    ```
6. `README.md`, §7, после строки о `doc/problem_statement.tex` (358):
    ```
    - [CHANGELOG.md](CHANGELOG.md) — изменения решателя между выпусками и правило номеров версий;
    ```
7. `examples/README.md`, «Что получается на выходе», строка после `mass_balance.png` (335):
    ```
    | `versions.txt` | версии решателя, прототипа, Python, numpy и scipy, которыми получены результаты |
    ```

**Проверка после шага:**
- Регресс: `<PY> -m pytest tests/ --collect-only -q` (меняются только документы). `test_eq_references.py` читает README примеров, новых ссылок на уравнения нет.

**Зависимости:** требует шаги 2–4 (описывает их результат).
**Оценка:** ~25 строк, 15 мин.

### Шаг 6: номер в колесе

**Цель:** сборка колеса из дерева worktree даёт номер `1.0.0.dev0` в имени и в METADATA.
**Файлы:** нет правок; проба `vault/issues/feat-037/probes/plan_checks.py`

**Что сделать** (из `<W>`):
```powershell
$env:PYTHONIOENCODING="utf-8"; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
<PY> vault\issues\feat-037\probes\plan_checks.py <W>\numerical_solver | Out-File -Encoding utf8 vault\issues\feat-037\probes\implement_wheel.out.txt
```
(Без `OutputEncoding` PowerShell 5.1 декодирует вывод в кодировке консоли и кириллица в файле портится.)
Без `--apply-plan`: правки уже в дереве worktree. Проба — копия из первого коммита `/implement` (материалы задачи), вывод — в дерево worktree, коммитится с vault задачи. Колесо собирается в `<W>\numerical_solver\build\feat037_probe\`, каталог игнорируется git (`.gitignore:32`).

**Ожидание:** «Литерал в копии: 1.0.0.dev0», `gpn_multiphase_solver-1.0.0.dev0-py3-none-any.whl`, `METADATA Version: 1.0.0.dev0`, «Итог: все проверки пройдены».

**Если `pip wheel` отказал по сети** (изоляции сборки нужен setuptools ≥ 68 с PyPI или из кеша pip): записать это в вывод и в отчёт `/implement`. Шаг не блокирующий: конфигурацию номера проверяют тесты шага 1, а механизм на копии пакета проверен пробой плана.

**После проверки:** удалить `<W>\numerical_solver\build\feat037_probe\`.

**Зависимости:** требует шаг 1.
**Оценка:** 5 мин.

### Шаг 7: vault

**Цель:** решение и ловушки задачи — в базе знаний; связанные планы — без устаревших утверждений.

**Что сделать** (по порядку `/implement`):
1. Заметка `vault/knowledge/decisions/номер версии решателя — литерал __version__, журнал сводится при выпуске.md`: решения 1–14 кратко; ловушки — метаданные редактируемой установки, запрет `pip install -e` в worktree, `'1.0'` канонична по PEP 440; что делает выпуск (литерал без `.dev`, раздел журнала, `+gpn.N` прототипа). Ссылка — в `vault/00-home/index.md`.
2. Реестр `vault/roadmap/планируемые фичи.md`, FEAT-037 — статус и итог по шаблону `/implement`.
3. **В базовой ветке** (файл с незакоммиченными правками основного каталога — не в worktree): черновик `vault/plans/feat-031 customer-delivery-kit.md`:
   - §3 «`pyproject.toml` — 0.1.0 → 1.0.0. В пакете нет `__version__`…» → «номер — литерал `__version__` (FEAT-037); при выпуске `1.0.0.dev0` → `1.0.0`; версии пакетов и Python, numpy, scipy пишутся в `output/versions.txt` (решение 25 выполнено FEAT-037)»;
   - §8 п. 3 — добавить «раздел `## 1.0.0 — <дата>` журнала `CHANGELOG.md` вместо «Не выпущено», сводка по истории git»;
   - §2.А п. 10 «Вывод» — `versions.txt`.
4. Комментарий в issue #134 — `vault/issues/feat-037/05-comment-done.md`.

**Регресс:** не нужен.

## 4. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_solver_version_is_dynamic_from_literal` | `tests/test_packaging.py` (сущ.) | разбор `pyproject.toml` | `dynamic == ["version"]`, статического `version` нет, `attr = "gpn_multiphase_solver.__version__"` | два источника номера; возврат литерала в `pyproject.toml` |
| `test_solver_version_literal_follows_rule` | там же | `_static_version` + `packaging.Version` | литерал; `str(Version(v)) == v`; три числа | вычисляемый номер (setuptools импортирует пакет); `1.0`, `v1.0.0`, `1.0.0-dev0` |
| `test_changelog_has_section_for_version` | там же | номер + `CHANGELOG.md` | `.devN` → «## Не выпущено»; выпуск → «## <номер>» | выпуск без раздела журнала |
| `test_version_flag` | `tests/test_cli.py` (сущ.) | `cli.main(["--version"])` | `SystemExit(0)`, stdout `gpn-multiphase-solver <__version__>\n` | ключ не работает без подкоманды; иная строка |
| `test_version_does_not_import_solver` | там же | подпроцесс | `0 False False` | тяжёлый импорт ради номера |
| `test_versions_sources` | там же | `pipeline._versions()` | 5 пар из модулей этого дерева | номер из метаданных pip (отстают), из `build_info` |
| `test_run_from_foreign_directory` (правка) | там же | команда в подпроцессе | 13 файлов; `lines[2]` — «Версии: …»; `versions.txt` — те же 5 строк | `versions.txt` не записан или расходится с печатью |
| `test_pipeline_writes_output` (правка `expected`) | `tests/test_examples.py` | `run_case` в процессе | `versions.txt` создан, не пуст | файл пропал из штатного набора |

Категории: unit — 6 новых; предельные случаи — правило номера (`1.0`, суффиксы) в пробе и тесте; инварианты — печать и файл из одного списка, журнал согласован с номером; регрессия — быстрый уровень после шагов 1, 3, 4, полный в конце. Аналитических проверок и проверок сходимости нет — задача не численная.

**Счёт тестов:** 2288 → 2294 (+3 `test_packaging.py`, +3 `test_cli.py`).

## 5. Критерии завершения

- [ ] `gpn_multiphase_solver.__version__ == "1.0.0.dev0"`, литерал; `pyproject.toml` — `dynamic`, статического номера нет.
- [ ] `CHANGELOG.md` — правило номеров и «Не выпущено» с записью задачи.
- [ ] `gpn-solver --version` → `gpn-multiphase-solver 1.0.0.dev0`, код 0, без импорта решателя.
- [ ] `run_case`: строка «Версии: …» третьей, `versions.txt` (5 строк) в каталоге вывода.
- [ ] README (6 правок) и README примеров — обновлены.
- [ ] 6 новых тестов зелёные; быстрый уровень и полный прогон зелёные; 2294 теста (с поправкой на сдвиг базы).
- [ ] Колесо из worktree — `1.0.0.dev0` (шаг 6) или отказ сети записан.
- [ ] Прототип не менялся — его тесты и регрессия не требуются.
- [ ] Vault: заметка, реестр, черновик FEAT-031, комментарий в #134.

**После влития (вне `/implement`, по желанию пользователя):** обновить метаданные установки в основном каталоге — `cd numerical_solver; .venv\Scripts\python -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"`; затем `importlib.metadata.version("gpn-multiphase-solver")` → `1.0.0.dev0`. Тесты от этого не зависят.

## 6. Верификация плана

**Раунд 1 — полнота.** Формул нет (2.1). Каждое изменение объёма из реестра (номер, `.dev0`, журнал, правило) и из решений 4–7 (запись в `output/`, состав, сводка при выпуске, `--version`) имеет шаг и тест. Шаги без циклов: 1 → (2, 3, 4) → 5; 6 после 1; 7 последний. Подводные камни 2.5 адресованы шагами или пп. 5–6 «Как начать».

**Раунд 2 — корректность.** Сверено на `55868a6`: `pyproject.toml:5-8, 38` (секции), `__init__.py:1`, `test_packaging.py:50-80` (`_static_version`, образец), `cli.py:48-54` (`_parser`, `required=True`), `pipeline.py:113-114, 141-147` (печать, очистка), `test_cli.py:39-44, 92-112`, `test_examples.py:585-619, 772-785`, `README.md:24, 69-73, 238-251, 317, 358`, `examples/README.md:318-335`. Импорт `radial_blackoil` в пакете — только внутри функций (`factory.py:153, 412, 440, 456-458, 565`; `hydro/prototype_adapter.py:231, 255, 273`). `packaging` — зависимость pytest (`importlib.metadata.requires("pytest")`). Поведение argparse и сборка колеса с `attr` — проба `plan_checks.py --apply-plan`, 22/22 ОК.

**Аудит 1 (2026-10-18).** Эмуляция шагов 1–5 на копиях `git archive` (`audit_apply.py`): все 29 якорей «До» — ровно по одному разу на `4b67213` и на ветке FEAT-035; тесты и сценарий — п. 2 «Как начать». Исправлено: порядок с FEAT-035 и baseline 2395 (было «+105»); незакоммиченный план FEAT-031; место `import platform`; место пункта докстринга `test_cli.py`; вид фразы докстринга `run_case`; команда и путь вывода шага 6; сводная таблица файлов; подводные камни pip / CRLF / «Не выпущено».

**Раунд 3 — автономность.** Код и тексты шагов даны целиком: журнал, комментарии, тесты, строки README. Пути — от корня проекта. Команды — с `<PY>` и каталогом запуска. Baseline 2288 на `55868a6`.

## 7. Связанные заметки

- [[feat-031 customer-delivery-kit|FEAT-031]] — решения 8, 25, 27, 41–44; §3 «Версии».
- [[DEBT-059]] — единый источник номера прототипа (образец), приёмка в чистом окружении `vault/issues/debt-059/probes/clean_env_acceptance.py`.
- [[DEBT-048]] — номер прототипа повышается при выпуске.
- [[feat-035 workbook-to-config|FEAT-035]], [[feat-036 run-from-workbook|FEAT-036]] — правят `cli.py`, `test_cli.py`, README и вывод `run_case` (2.5).
- [[номер версии решателя — литерал __version__, журнал сводится при выпуске]] — заметка-решение по итогам.

## 8. Итог реализации (2026-10-18)

- Начало — после влития FEAT-035 (`86348ed`, «влит» `2f29235`); предварительный коммит `b9454a6` (план, `vault/issues/feat-037/`, черновик FEAT-031 с решениями 38–44 — по умолчанию п. 8 «Как начать»). Ветка от `b9454a6`, коммиты `c2538d5` (шаг 1), `54dbb2a` (2), `cad2c4c` (3), `d20dd4e` (4), `bf1b7fa` (5).
- Baseline 2395, быстрый 2118 passed / 1 skipped (138 с). После шагов: 2120 → 2123 → 2124 passed. Итог — 2401 тест; полный прогон 2400 passed, 1 skipped, 594 с. Предупреждение одно и прежнее (`PytestRemovedIn10Warning`, фикстура уровня класса в существующих тестах).
- Шаг 6: колесо из worktree `gpn_multiphase_solver-1.0.0.dev0-py3-none-any.whl`, METADATA `1.0.0.dev0` (`probes/implement_wheel.out.txt`).
- **Отклонение от плана:** шаг 7.3 (черновик FEAT-031) выполнен в worktree, а не в базовой ветке: причина, по которой план требовал базу (чужие незакоммиченные правки файла), отпала — файл закоммичен в `b9454a6`.
- Все блоки «После» перенесены без изменений; якоря «До» на базе после FEAT-035 совпали с эмуляцией аудита.
