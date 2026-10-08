---
tags:
  - план
  - удаление
date: 2026-10-07
issue: DEBT-031
github: 75
branch: refactor/debt-031/convergence-dead-code
status: реализован
merged: 002a96e (2026-10-08)
worktree: .worktrees/debt-031; удалён после влития
audit:
  date: 2026-10-07
  found: 5
  auto-fixed: 5
  manual-required: 0
---

# DEBT-031: мёртвый код в `examples/convergence.py`

**Реестр:** `vault/roadmap/известные баги и технический долг.md`, секция DEBT-031.
**GitHub:** [#75](https://github.com/ArturSalamatin/Oil_Gas/issues/75) (тело — `vault/issues/debt-031/01-issue-body.md`).
**Ветка:** `refactor/debt-031/convergence-dead-code` (не существует; создаётся `/implement` в worktree `.worktrees/debt-031`).
**База:** `numerical_scheme/implementation`, HEAD `9d4321d` на аудите (после `d73624c` — влит DEBT-041 — только vault-коммит). Файлы плана с `6d14a5c` не менялись: `git diff --stat 6d14a5c d73624c` по `convergence.py`, `energy_balance_convergence.py`, `examples/README.md`, `tests/test_examples.py`, `04a/grid_convergence.py` пуст.
**Подтип:** удаление мёртвого кода.

## Решения пользователя (2026-10-07)

1. **Вариант 1** — удалить четыре функции без вызывающих, оставить `run_series`, переписать docstring модуля. Варианты 2 (подключить `report_series` к 04a), 3 (подключить `fit_order` к 05) и 4 (оставить с пометкой) отклонены.
2. **Тест импорта** — добавить в `tests/test_examples.py` тест, который импортирует `convergence.py` и оба скрипта на `run_series` без запуска расчёта. Сейчас ни один тест их не импортирует.

## Суть задачи

`numerical_solver/examples/convergence.py` — общий модуль примеров с пятью функциями. Вызывается только `run_series`, остальные четыре (`fit_order`, `pairwise_orders`, `plot_convergence`, `report_series`, строки 92–197, ~106 строк) не вызываются ни скриптами, ни тестами. Последние вызывающие ушли с BUG-007 (`a4484bb`, 2026-09-19: `energy_balance_convergence` проверяет уровень невязки, а не порядок по Δt) и DEBT-022 (`dc8c38b`, 2026-09-23: удалена ОДУ-аналитика температуры).

Вред: (1) мёртвые функции правятся при каждом изменении оформления рисунков — FEAT-026 переводил `plot_convergence` на `save_figure` + `export_emf` только ради единообразия; (2) docstring модуля описывает механику (регрессия порядка, «двухпанельный график»), которой никто не пользуется, и называет пользователями скрипты 01/04/05, которые модуль **не импортируют**.

Поведение решателя и примеров задача не меняет: тело `run_series` не трогается.

## Исходное состояние

Замер на HEAD `6d14a5c`, повторно на `d73624c` и на аудите (`9d4321d`, без чужого незакоммиченного файла — см. ниже), 2026-10-07, из `numerical_solver/`:

| Что | Значение |
|---|---|
| Число тестов | 1344 (`--collect-only -q`) |
| Быстрый уровень | 1108 из 1344 (`-m "not slow" --collect-only -q`) |

⚠️ В основном каталоге на момент планирования лежит чужой незакоммиченный `numerical_solver/tests/test_prototype_open_branch_skip.py` (+7 тестов, параллельная сессия DEBT-040) — там `--collect-only` даёт 1351. В worktree этого файла нет; ориентир — 1344.

Кто вызывает функции модуля (`grep` по `numerical_solver/`, `*.py` и `*.md`):

| Функция | Строки `convergence.py` | Вызывающие |
|---|---|---|
| `run_series` | 60–89 | `examples/energy_balance_convergence.py:60` (импорт), `:98`, `:203`; `examples/04a_high_gas_saturation/grid_convergence.py:53` (импорт), `:98` |
| `fit_order` | 92–106 | только `plot_convergence` (`:138`) и `report_series` (`:190`) |
| `pairwise_orders` | 109–122 | только `report_series` (`:195`) |
| `plot_convergence` | 125–173 | нет |
| `report_series` | 176–197 | нет |

Импорты модуля и кому они нужны:

| Строка | Импорт | Нужен |
|---|---|---|
| 39–40 | `sys`, `Path` | настройка `sys.path` (50–55) — остаётся |
| 41–42 | `deepcopy`, `Callable` | `run_series` — остаётся |
| 44 | `numpy as np` | только `fit_order`, `pairwise_orders`, `plot_convergence` — удаляется |
| 46–48 | `matplotlib`, `matplotlib.use("Agg")`, `pyplot as plt` | только `plot_convergence` — удаляется |
| 57 | `from figure_io import save_figure, export_emf` | только `plot_convergence` — удаляется |

`run_series` сама импортирует `SimulatorFactory` внутри тела (строка 73) — от модульных импортов `numpy`/`matplotlib`/`figure_io` не зависит.

Тесты: функций модуля не вызывает ни один тест. `tests/test_examples.py:791–795` (`test_shared_modules_exist`) проверяет только наличие файла `convergence.py`; `SHARED_EXAMPLE_FILES` (`:642`) — что файл не скопирован в папку примера. Оба выполняются и после удаления.

Ссылки на удаляемые имена вне `convergence.py` (`grep -E "fit_order|pairwise_orders|plot_convergence|report_series"` по `numerical_solver/`):

| Файл | Строка | Что |
|---|---|---|
| `numerical_solver/examples/energy_balance_convergence.py` | 58–59 | комментарий «fit_order не импортируется…» |

Описание модуля в README: `numerical_solver/examples/README.md:739` — «механика серий и регрессии порядка (эталон — у примера)». ⚠️ До влития DEBT-045 (`279d710`) это была строка 737 — искать по тексту, а не по номеру.

Упоминания в `vault/` (планы FEAT-016, FEAT-022, FEAT-026, BUG-006, BUG-007, реестры) — история, **не правятся**.

## Целевое состояние

- `convergence.py` содержит только `run_series` и настройку `sys.path`; импорты `numpy`, `matplotlib`, `figure_io` удалены.
- Docstring модуля: назначение — прогон серии с измерением метрики; фактические пользователи — `energy_balance_convergence` и `04a/grid_convergence`; эталон и обработка серии — у вызывающего; скрипты 01/04/05 модуль не импортируют.
- Комментарий `energy_balance_convergence.py:58–59` не ссылается на удалённую функцию.
- Строка README описывает модуль по факту.
- Новый тест `test_convergence_users_import` — импорт трёх файлов через `runpy`, без прогона серии, и проверка, что все глобальные имена тела `run_series` определены.
- Число тестов 1344 → 1345 (быстрый уровень 1108 → 1109).

Граф импортов: `energy_balance_convergence` → `convergence`; `04a/grid_convergence` → `convergence`. Не меняется. Циклов нет (`convergence` не импортирует никого из `examples/`, кроме `gpn_multiphase_solver.factory` внутри `run_series`).

## Зона неприкосновенности

- Тело `run_series` (строки 60–89) — ни символа.
- Цикл настройки `sys.path` (строки 50–55) — без изменений. После удаления импорта `figure_io` каталог `examples/` модулю уже не нужен, но вставка безвредна; правка не входит в задачу.
- `05_standing_table_rp/closed_form_convergence.py`, `01_single_phase_no_jt/spatial_convergence.py`, `04_table_table/grid_convergence.py` — свои встроенные расчёты порядка не трогаются (решение пользователя: вариант 3 отклонён).
- Шапки `04a/grid_convergence.py` и `energy_balance_convergence.py` — не трогаются (кроме комментария 58–59).
- `vault/` вне записи DEBT-031 и материалов задачи.

## Варианты (сводка, выбран 1)

| | Суть | Плюсы | Минусы |
|---|---|---|---|
| **1 ✅** | удалить четыре функции, переписать docstring | −~110 строк; вывод примеров не меняется по построению | при нужде — восстанавливать из git (`6d14a5c`) |
| 2 | `report_series` в `04a/grid_convergence` | две функции получают вызывающего | меняет вывод 04a → правка docstring и README 04a, прогон ~3 мин; новой информации почти нет (отношения ошибок уже печатаются); `plot_convergence` остаётся мёртвой |
| 3 | `fit_order` в `05/closed_form_convergence:124–125` | убирает одну копию, порядок побитно тот же | зависимость 05 от общего модуля ради двух строк; график 05 перевести нельзя без изменения рисунка |
| 4 | оставить, пометить | минимум правок | код по-прежнему сопровождается впустую |

Подробный разбор — в теле issue.

## Подводные камни (чеклист)

| Пункт | Статус | Комментарий |
|---|---|---|
| Все места вызова найдены | ✅ | `grep` по `numerical_solver/` (`*.py`, `*.md`), включая `HydroSolverPrototype/` и `tests/`: вызовов нет; единственная внешняя ссылка — комментарий `energy_balance_convergence.py:58–59` (шаг 4). Повторная проверка — шаг 1 |
| Зависимости пакетов | ✅ | `pyproject.toml` не меняется; `numpy`/`matplotlib` остаются зависимостями пакета (их используют другие модули) |
| Обратная совместимость | ✅ | `run_series` и её сигнатура не меняются; оба вызывающих импортируют только `run_series` |
| Состояние при ошибке | ✅ | не применимо: нет исполняемых изменений |
| Тесты | ⚠️ | функций модуля не вызывает ни один тест, поэтому сломанный импорт `run_series` pytest сейчас не ловит → новый тест импорта (шаг 2) пишется **до** удаления и должен быть зелёным на исходном коде. Импорт сам по себе не ловит имя, нужное только при вызове (`deepcopy`), — поэтому в тесте проверка `LOAD_GLOBAL` через `dis` (аудит) |
| Циклические импорты | ✅ | новых импортов нет |
| Docstrings / `\eqref{}` | ✅ | ссылок на уравнения в модуле нет; docstring переписывается (шаг 3) |
| Конфиги | ✅ | не затрагиваются |
| Связь с другими задачами | ⚠️ | DEBT-045 влит (`279d710`) — сдвинул строку README 737 → 739, искать по тексту. DEBT-041 влит (`d73624c`) — файлы плана не трогал. Планы DEBT-040, DEBT-044, FEAT-029 эти файлы не упоминают (`grep` по `vault/plans/`). Если до реализации в базу вольётся задача с правкой `tests/test_examples.py`, сдвинутся только номера строк — тест вставлять по якорю `test_shared_modules_exist`, а не по номеру |
| Производительность | ✅ | на холодном интерпретаторе три импорта — 2.07 с (замер при планировании), проба аудита с четырьмя тестами — 2.00 с; почти всё — первая загрузка `matplotlib`/`scipy`/пакета, которые в сеансе pytest уже загружены другими тестами |
| Прототип | ✅ | `HydroSolverPrototype/` не меняется — тесты и регрессия прототипа не нужны |
| `sys.path` после теста | ⚠️ | `04a/grid_convergence.py` при импорте вставляет в `sys.path[0]` папку примера, где лежит свой `main.py`. Тест подменяет `sys.path` копией через `monkeypatch` — после теста список восстанавливается |
| Worktree и экземпляр пакета | ✅ | память проекта: в worktree скрипты примеров могут брать `gpn_multiphase_solver` из основного каталога. Задача пакет не меняет, поэтому какой экземпляр подхватится — не важно; pytest в worktree берёт пакет worktree корректно |

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-031 в `vault/roadmap/известные баги и технический долг.md` и тело issue `vault/issues/debt-031/01-issue-body.md`.
3. Worktree и ветка (делает `/implement`, шаг 1.5): `<W>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-031`, ветка `refactor/debt-031/convergence-dead-code` от `numerical_scheme/implementation`. Все правки — только в `<W>`. Основной каталог занят параллельными сессиями (в `vault/` чужие незакоммиченные правки) — его не трогать, `git checkout -b` там не делать.
4. Интерпретатор общий, по абсолютному пути (в worktree нет `.venv`):
   ```powershell
   $py = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-031\numerical_solver
   ```
   Команды pytest и `Select-String` плана — из `<W>\numerical_solver`; команды `git grep` / `git checkout` — из `<W>`. pytest из `<W>\numerical_solver` импортирует код worktree (память проекта, `reference_worktree_pythonpath`).
5. Исходное состояние из `<W>\numerical_solver`:
   ```powershell
   & $py -m pytest tests/ --collect-only -q            # ожидается 1344
   & $py -m pytest tests/ -m "not slow" -q             # ожидается 1108 passed, ~70 с
   ```
   Если числа другие — база ушла вперёд (например, влит DEBT-040: +7 тестов); записать фактические и продолжать от них (+1 тест после шага 2). Все «1345 / 1109» ниже читать как «исходное + 1».
6. Запомни число тестов (всего и в быстром уровне) и время быстрого уровня.
7. Шаги 1–5 по порядку. После каждого — проверка из поля «Регресс». Полный прогон — в конце (`/implement` §3.1).

---

## Шаг 1: Подготовка — подтвердить, что код мёртвый

**Цель:** убедиться на ветке задачи, что четыре функции не вызываются нигде и с момента планирования вызывающие не появились.

**Файлы:** только чтение — `numerical_solver/` целиком.

**Контекст:** план составлен на `6d14a5c`. Между планированием и реализацией в базу могли влиться задачи, добавившие вызов. Удалять функцию, у которой появился вызывающий, нельзя — тогда план надо пересмотреть.

**Что сделать:**
1. Из корня worktree:
   ```powershell
   git grep -n -E "fit_order|pairwise_orders|plot_convergence|report_series" -- numerical_solver
   ```
   Ожидание — совпадения **только** в:
   - `numerical_solver/examples/convergence.py` (определения 92–197 и docstring, строка 28);
   - `numerical_solver/examples/energy_balance_convergence.py:58` (комментарий).
2. Импорты модуля:
   ```powershell
   git grep -n -E "from convergence import|import convergence" -- numerical_solver
   ```
   Ожидание — ровно две строки: `examples/energy_balance_convergence.py:60` и `examples/04a_high_gas_saturation/grid_convergence.py:53`, обе `from convergence import run_series`.
3. Если найдено что-то ещё — остановиться и сообщить пользователю (новый вызывающий меняет выбор варианта).

**Проверка после этого шага:**
- Регресс: не нужен (только чтение). Исходное состояние — из «Как начать работу», п. 5.

**Подводные камни:** чеклист — «Все места вызова найдены».

**Зависимости:** требует — ничего; блокирует — шаги 2–5.

**Оценка:** 0 строк, ~3 минуты.

---

## Шаг 2: Тест импорта `convergence.py` и скриптов на `run_series`

**Цель:** добавить тест, который ловит сломанный импорт `run_series`, — до удаления кода, на исходном состоянии он зелёный.

**Файлы:** `numerical_solver/tests/test_examples.py`.

**Контекст:**
Скрипты сходимости (`energy_balance_convergence.py`, `04a_high_gas_saturation/grid_convergence.py`) запускаются только вручную, ни один тест их не импортирует (`grep` по `tests/` на `run_path|import_module|spec_from_file_location` — пусто). Если при удалении задеть `run_series` или импорт, нужный модулю, pytest этого не заметит — ошибка всплывёт при следующем ручном запуске.

`runpy.run_path(путь, run_name=...)` выполняет файл как модуль с указанным `__name__`. При `run_name ≠ "__main__"` выполняются импорты верхнего уровня, а блок `if __name__ == "__main__":` — нет, то есть серия прогонов не запускается. Функция возвращает словарь пространства имён модуля — в нём должна быть `run_series`: в `convergence.py` она определена, в двух скриптах — импортирована `from convergence import run_series`.

Проверено при планировании на `6d14a5c` (холодный интерпретатор, из `numerical_solver/`): все три файла дают `callable(ns["run_series"]) == True`, 2.07 с на все три.

**Что сделать:**
1. В классе `TestSharedChecks` файла `numerical_solver/tests/test_examples.py` сразу после метода `test_shared_modules_exist` (сейчас строки 791–795; искать по имени) вставить новый метод (код ниже).
2. `import builtins`, `import dis`, `import runpy` и `import sys` — внутри метода: в этом файле `sys` импортируется локально в тестах (см. `test_energy_balance_reported_for_all_examples`, строки 809–812), на уровне модуля его нет.

**Изменения (старый → новый код):**

До (`tests/test_examples.py:791–797`):
```python
    def test_shared_modules_exist(self):
        """Общие модули на месте — иначе примеры не считают проверки."""
        for module in SHARED_CHECK_MODULES + ["convergence.py"]:
            path = EXAMPLES_DIR / module
            assert path.is_file(), f"нет общего модуля examples/{module}"

    def test_energy_balance_reported_for_all_examples(self, tmp_path):
```

После:
```python
    def test_shared_modules_exist(self):
        """Общие модули на месте — иначе примеры не считают проверки."""
        for module in SHARED_CHECK_MODULES + ["convergence.py"]:
            path = EXAMPLES_DIR / module
            assert path.is_file(), f"нет общего модуля examples/{module}"

    def test_convergence_users_import(self, monkeypatch):
        """convergence.py и скрипты на run_series импортируются (DEBT-031).

        Скрипты сходимости запускаются только вручную, и других тестов,
        которые бы их импортировали, нет: удалённое из convergence.py имя
        или потерянный импорт обнаружились бы лишь при ручном запуске.
        runpy.run_path с run_name ≠ "__main__" выполняет импорты верхнего
        уровня, но не блок __main__ — серия прогонов не запускается.
        """
        import builtins
        import dis
        import runpy
        import sys

        # Скрипты сами вставляют свои каталоги в sys.path (04a — папку
        # примера со своим main.py). Подменяем список копией: monkeypatch
        # вернёт исходный после теста, и папка 04a не перекроет модули
        # в других тестах.
        monkeypatch.setattr(sys, "path", list(sys.path))
        for script in ("convergence.py",
                       "energy_balance_convergence.py",
                       "04a_high_gas_saturation/grid_convergence.py"):
            namespace = runpy.run_path(str(EXAMPLES_DIR / script),
                                       run_name="__import_check__")
            # run_series определена в convergence.py и импортирована обоими
            # скриптами — её наличие в пространстве имён и есть проверка.
            run_series = namespace.get("run_series")
            assert callable(run_series), (
                f"examples/{script}: нет run_series после импорта")
            # Импорт видит только имена, нужные при загрузке модуля. Имя,
            # нужное лишь при вызове (deepcopy в теле run_series), пропало
            # бы молча — проверяем, что каждое глобальное имя тела
            # определено в модуле или среди встроенных.
            missing = sorted(
                ins.argval for ins in dis.get_instructions(run_series)
                if ins.opname == "LOAD_GLOBAL"
                and ins.argval not in run_series.__globals__
                and not hasattr(builtins, ins.argval))
            assert not missing, (
                f"examples/{script}: run_series ссылается на "
                f"неопределённые имена {missing}")

    def test_energy_balance_reported_for_all_examples(self, tmp_path):
```

Почему проверка `dis`, а не только импорт (аудит 2026-10-07). Самая вероятная ошибка шага 3 — удалить вместе с блоком `numpy`/`matplotlib` и соседний `from copy import deepcopy`. Импорт модуля при этом проходит: `deepcopy` нужен только при вызове `run_series`, а вызвать её в тесте нельзя — она запускает расчёт. `dis.get_instructions` перечисляет инструкции байт-кода тела функции; `LOAD_GLOBAL` — обращение к глобальному имени. На текущем коде это `deepcopy`, `dict`, `float`, `isinstance` (Python 3.13.3 venv); первое определено в модуле, остальные — встроенные. `SimulatorFactory` импортируется внутри тела и в список не попадает. Проба `vault/issues/debt-031/probes/probe_import_check.py` (4 passed): тело теста зелёное на текущем коде; файл «После» шага 3 проходит; без `from copy import deepcopy` импорт проходит, а `missing == ["deepcopy"]`; переименованная `run_series` ловится.

**Проверка после этого шага:**
- Тест шага: `& $py -m pytest tests/test_examples.py -k test_convergence_users_import -q` → `1 passed`.
- Метка: тест без фикстуры `results` → в быстром уровне. `--collect-only -q` → 1345; `-m "not slow" --collect-only -q` → 1109 из 1345.
- Регресс: быстрый — `& $py -m pytest tests/ -m "not slow" -q` → 1109 passed.
- Проверка, что тест ловит то, ради чего написан (временная порча, **не коммитить**): в рабочей копии `examples/convergence.py` переименовать `def run_series` → `def run_series_x`, запустить тест шага — ожидается FAIL (`ImportError: cannot import name 'run_series'` из `energy_balance_convergence.py` либо падение `assert` на `convergence.py`). Вернуть (из `<W>`): `git checkout -- numerical_solver/examples/convergence.py`. Убедиться, что `git status` не показывает `convergence.py` изменённым. Порча и откат — до шага 3, поэтому `git checkout` возвращает исходный файл, а не теряет правки.

**Подводные камни:** чеклист — «Тесты», «`sys.path` после теста», «Связь с другими задачами» (якорь вставки — имя метода).

**Зависимости:** требует — шаг 1; блокирует — шаг 3 (тест должен существовать до удаления).

**Оценка:** +42 строки, ~10 минут.

---

## Шаг 3: Удалить четыре функции и лишние импорты, переписать docstring `convergence.py`

**Цель:** в модуле остаются только настройка `sys.path` и `run_series`; docstring описывает модуль по факту.

**Файлы:** `numerical_solver/examples/convergence.py`.

**Контекст:**
Удаляются `fit_order` (92–106), `pairwise_orders` (109–122), `plot_convergence` (125–173), `report_series` (176–197) и импорты, нужные только им: `numpy` (44), `matplotlib` (46–48), `figure_io` (57). Тело `run_series` (60–89) не меняется.

Docstring (1–37) сейчас неверен в трёх местах:
- строки 3–6: «оценить порядок регрессией… нарисовать двухпанельный график» — регрессию никто не вызывает, `plot_convergence` строит одну панель;
- строки 9–12: пользователи — 01/spatial_convergence, 04/grid_convergence, 05/closed_form_convergence. Ни один из трёх модуль не импортирует; фактические пользователи — `energy_balance_convergence` и `04a/grid_convergence`;
- строки 18–32 («ПОЧЕМУ ПОРЯДОК ИЗМЕРЯЕТСЯ», «ГДЕ ЭТОТ ПРИЁМ НЕПРИМЕНИМ», «ТРИ ТОЧКИ МИНИМУМ») обосновывают удаляемые функции.

Разделы 18–32 удаляются целиком (решение пользователя): их доводы уже записаны у вызывающих —
- «полка ⇔ ошибка в выводе, степенное убывание ⇔ дискретизация»: шапки `04a_high_gas_saturation/grid_convergence.py:3–7, 24–27` и `05_standing_table_rp/closed_form_convergence.py:9–13`;
- «невязка баланса — тождество схемы, проверяется уровень, а не порядок»: шапка `energy_balance_convergence.py:3–7, 25–27`;
- «три точки»: `energy_balance_convergence.py:33–34`.

Абзацы «Эталон — это физика конкретного примера…» (14–16) и «Модуль библиотечный…» (34–36) остаются по смыслу.

**Что сделать:**
1. Заменить строки 1–37 (docstring) новым текстом (ниже).
2. Удалить строку 44 (`import numpy as np`), строки 46–48 (блок `matplotlib`) и пустые строки вокруг них так, чтобы после `from typing import Callable` шла одна пустая строка и `_EXAMPLES = ...`.
3. Удалить строку 57 (`from figure_io import save_figure, export_emf  # noqa: E402`) вместе с пустой строкой перед ней; после цикла `for _p in ...` — две пустые строки и `def run_series`.
4. Удалить всё после `return results` (строки 90–197). Файл заканчивается строкой `    return results` и переводом строки.

**Изменения (старый → новый код):**

До — строки 1–58 (docstring, импорты, `sys.path`) и 90–197 (четыре функции); полный текст — `git show 6d14a5c:numerical_solver/examples/convergence.py`.

После — **весь файл**:
```python
"""Прогон серии по параметру — общая механика проверок по Δt и по сетке.

ЧТО ЗДЕСЬ ОБЩЕЕ, А ЧТО НЕТ. Проверки на серии устроены одинаково:
прогнать задачу на ряде значений параметра (Δt или N) и на каждом
измерить метрику. Отличаются они ЭТАЛОНОМ, с которым сравнивается
расчёт, и тем, что делается с серией:

  energy_balance_convergence  — уровень невязки баланса энергии по Δt
  04a/grid_convergence        — дебит против GOR-замыкания по N,
                                отношения ошибок соседних сеток

Эталон — это физика конкретного примера, и выносить его нельзя: он и есть
предмет проверки. Поэтому здесь только прогон серии: настройка конфига и
метрика приходят аргументами-функциями, а обработка серии (порядок,
уровень, отношения ошибок) остаётся у вызывающего скрипта.

Скрипты сходимости 01/spatial_convergence, 04/grid_convergence и
05/closed_form_convergence прогоняют серию сами и этот модуль не
импортируют.

Модуль библиотечный: своего __main__ у него нет, потому что запускать
«сходимость вообще» бессмысленно — нужен пример и его эталон. Запускаются
скрипты примеров, которые этот модуль используют.
"""

import sys
from pathlib import Path
from copy import deepcopy
from typing import Callable

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES),
           str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def run_series(config_base, values, apply: Callable, measure: Callable,
               log_level: str = "WARNING") -> list[dict]:
    """Прогнать задачу на серии значений параметра и измерить ошибку.

    apply(config, value)          — выставить параметр в копии конфига
    measure(sim, history, config) — вернуть метрику (float) или dict с ней

    Возвращает список dict по одному на значение; в каждом есть ключ
    "value", плюс всё, что вернул measure (если dict) либо ключ "error".

    Конфиг копируется deepcopy: серия прогонов не должна портить базовый
    объект, иначе второй вызов run_series получит уже изменённые параметры.
    """
    from gpn_multiphase_solver.factory import SimulatorFactory

    results = []
    for value in values:
        config = deepcopy(config_base)
        apply(config, value)
        config.output.log_level = log_level

        sim, initial_state = SimulatorFactory.from_config(config)
        history = sim.run(initial_state)

        measured = measure(sim, history, config)
        row = dict(measured) if isinstance(measured, dict) else {
            "error": float(measured)}
        row["value"] = value
        results.append(row)
    return results
```

Тело `run_series` и цикл `sys.path` выше скопированы из `6d14a5c` без изменений — сверить `git diff`: в этих строках не должно быть ни одного `+`/`-`.

**Проверка после этого шага:**
- Статическая: в модуле не осталось имён удалённых импортов и функций —
  ```powershell
  Select-String -Path examples\convergence.py -Pattern '\bnp\.|plt\.|matplotlib|save_figure|export_emf|fit_order|pairwise_orders|plot_convergence|report_series'
  ```
  Ожидание — пусто.
- `git diff -- examples/convergence.py`: изменены только docstring, строки импортов `numpy`/`matplotlib`/`figure_io` и хвост после `return results`; строки 50–55 и 60–89 исходного файла — без изменений.
- Тест шага 2: `& $py -m pytest tests/test_examples.py -k "test_convergence_users_import or test_shared_modules_exist or test_no_duplicate_helper_scripts" -q` → все passed. Тест ловит и потерю `from copy import deepcopy` (проверка `dis`), и удалённую `run_series`; но не ловит изменение логики тела — его сторожит сверка `git diff` ниже.
- Проба (по желанию): `& $py -m pytest ..\vault\issues\debt-031\probes\probe_import_check.py -q -p no:cacheprovider` из `<W>\numerical_solver` (проба попадает в worktree с коммитом материалов задачи, который `/implement` делает в базу до создания worktree) — после шага 3 первый тест пробы проверяет уже новый `convergence.py` (код берётся из текущего каталога, проба печатает путь).
- Регресс: быстрый — `& $py -m pytest tests/ -m "not slow" -q` → 1109 passed (число не меняется относительно шага 2).

**Подводные камни:** чеклист — «Обратная совместимость», «Тесты», «Зона неприкосновенности» (тело `run_series`).

**Зависимости:** требует — шаг 2; блокирует — шаг 4 (комментарий ссылается на шапку, которая меняется здесь).

**Оценка:** файл 198 → 68 строк (замер блока «После» пробой), ~10 минут.

---

## Шаг 4: Комментарий в `energy_balance_convergence.py` и строка README

**Цель:** убрать ссылку на удалённую `fit_order` и описать модуль в README по факту.

**Файлы:**
- `numerical_solver/examples/energy_balance_convergence.py` (строки 58–59);
- `numerical_solver/examples/README.md` (строка 739; искать по тексту `[convergence.py](convergence.py)`).

**Контекст:**
Комментарий над `from convergence import run_series` объясняет, почему из `convergence` не берётся `fit_order`. После шага 3 такой функции нет, и комментарий ссылается на несуществующее имя. Суть («у невязки нет порядка по Δt, проверяется уровень») верна и полезна читателю импорта — комментарий переформулируется, а не удаляется (правило CLAUDE.md «не удаляй комментарии без причины»). Ссылку «(см. шапку модуля)» уточнить: имеется в виду шапка **этого** файла — раздел «СМЫСЛ ПРОВЕРКИ» (строки 3–7); раньше её можно было прочитать и как шапку `convergence.py`, где был раздел «ГДЕ ЭТОТ ПРИЁМ НЕПРИМЕНИМ» (удалён в шаге 3).

Строка README в таблице общих модулей называет `convergence.py` «механикой серий и регрессии порядка» — регрессии в модуле больше нет.

**Что сделать:**
1. `energy_balance_convergence.py`: заменить две строки комментария (код ниже).
2. `examples/README.md`: заменить описание в строке таблицы (код ниже). Столбцы таблицы: «модуль | что проверяет | автономный запуск».

**Изменения (старый → новый код):**

`energy_balance_convergence.py`, до (57–60):
```python
from energy_balance import compute_balance  # noqa: E402
# fit_order не импортируется: невязка — округления, порядка по Δt у неё
# нет, проверяется уровень (см. шапку модуля).
from convergence import run_series  # noqa: E402
```
После:
```python
from energy_balance import compute_balance  # noqa: E402
# Из convergence — только прогон серии: невязка — округления, порядка
# по Δt у неё нет, проверяется уровень (см. шапку этого модуля, раздел
# «СМЫСЛ ПРОВЕРКИ»).
from convergence import run_series  # noqa: E402
```

Комментарий становится трёхстрочным: строки файла ниже сдвигаются на 1.

`examples/README.md`, до (739):
```markdown
| [convergence.py](convergence.py) | механика серий и регрессии порядка (эталон — у примера) | — |
```
После:
```markdown
| [convergence.py](convergence.py) | прогон серии по $\Delta t$ или $N$ с измерением метрики (эталон и обработка серии — у вызывающего скрипта) | — |
```

**Проверка после этого шага:**
- `git grep -n -E "fit_order|pairwise_orders|plot_convergence|report_series" -- numerical_solver` из корня worktree → **пусто**.
- Тест шага 2: `& $py -m pytest tests/test_examples.py -k test_convergence_users_import -q` → 1 passed (комментарий — в импортируемом файле, синтаксис должен остаться целым).
- Регресс: `--collect-only -q` → 1345 (шаг меняет комментарий и документ; исполняемый код не меняется).

**Подводные камни:** чеклист — «Связь с другими задачами» (строка README сдвинута DEBT-045 — искать по тексту).

**Зависимости:** требует — шаг 3; блокирует — шаг 5.

**Оценка:** 3 строки, ~5 минут.

---

## Шаг 5: Итоговая проверка и vault

**Цель:** подтвердить, что поведение не изменилось, и закрыть задачу в vault.

**Файлы:** `vault/roadmap/известные баги и технический долг.md` (секция DEBT-031), `vault/issues/debt-031/05-comment-done.md`.

**Что сделать:**
1. Полный прогон (`/implement` §3.1): `& $py -m pytest tests/ -q` → 1345 passed (исходные 1344 + 1).
2. Ручной запуск `energy_balance_convergence.py` и `04a/grid_convergence.py` **не нужен**: тело `run_series` не менялось (шаг 3, сверка `git diff`), импорт обоих скриптов проверяет тест шага 2. Прогоны примеров по памяти проекта не гонять без надобности.
3. В записи DEBT-031 реестра: статус — по правилам `/implement` (у DEBT-записей реестра — «✅ ГОТОВО (дата) — ветка `refactor/debt-031/convergence-dead-code`», как у DEBT-045), число тестов, коммиты; варианты — пометить выбранный (1, решение пользователя 2026-10-07).
4. Комментарий в issue #75 — результат (`05-comment-done.md`): что удалено, число строк, тест, 1345 passed.

**Проверка после этого шага:** полный прогон зелёный; `git grep` из шага 4 пуст.

**Зависимости:** требует — шаги 1–4.

**Оценка:** ~10 минут + полный прогон ~10 мин.

---

## Тестовая стратегия

**Тест:** `test_convergence_users_import`
**Файл:** `numerical_solver/tests/test_examples.py` (существующий файл, класс `TestSharedChecks`, новый метод)
**Сценарий:** импорт `examples/convergence.py`, `examples/energy_balance_convergence.py`, `examples/04a_high_gas_saturation/grid_convergence.py` через `runpy.run_path(..., run_name="__import_check__")` — блок `__main__` не выполняется, расчёта нет.
**Setup:** `sys.path` подменён копией через `monkeypatch` — скрипты дописывают в него свои каталоги.
**Ожидание:** все три импорта без исключения; в пространстве имён каждого — вызываемая `run_series`; у её тела нет глобальных имён (`LOAD_GLOBAL`), не определённых ни в модуле, ни среди встроенных.
**Исходное состояние:** зелёный на `6d14a5c` до удаления (проверено при планировании вне pytest: три `True`, 2.07 с; на аудите — проба `vault/issues/debt-031/probes/probe_import_check.py`, 4 passed, в том числе с проверкой `dis`); проверка, что тест краснеет при порче `run_series`, — шаг 2.
**Предотвращает:** молчаливую поломку скриптов сходимости при правке `convergence.py`: удалённое или переименованное `run_series`, потерянный импорт — и нужный при загрузке модуля, и нужный только при вызове (`deepcopy`). Изменение логики тела `run_series` тест не ловит — его сторожит сверка `git diff` в шаге 3.

Существующие тесты, покрывающие затронутые файлы:
- `TestSharedChecks::test_shared_modules_exist` (`test_examples.py:791`) — `convergence.py` и `energy_balance_convergence.py` на месте;
- `TestSharedChecks::test_no_duplicate_helper_scripts` (параметризован по `SHARED_EXAMPLE_FILES`, `test_examples.py:774`) — файлы не скопированы в папки примеров.

Инвариант вычислений: исполняемый код, который вызывается, не меняется (тело `run_series`), поэтому сверка чисел не нужна.

## Критерии завершения

- [ ] Шаги 1–5 выполнены.
- [ ] Полный прогон: 1345 passed (или исходное + 1, если база ушла вперёд).
- [ ] Новый тест зелёный и краснеет при порче `run_series` (проверено в шаге 2, порча откачена).
- [ ] В `convergence.py` только `run_series` и настройка `sys.path`; импортов `numpy`, `matplotlib`, `figure_io` нет.
- [ ] `git grep -E "fit_order|pairwise_orders|plot_convergence|report_series" -- numerical_solver` пуст.
- [ ] Тело `run_series` и цикл `sys.path` — без изменений (`git diff`).
- [ ] Docstring `convergence.py` называет пользователями `energy_balance_convergence` и `04a/grid_convergence`.
- [ ] Комментарий `energy_balance_convergence.py` и строка `examples/README.md` обновлены.
- [ ] Vault: статус DEBT-031, комментарий в issue #75; issue закрывается при `/merge`.
- [ ] Прототип не менялся — его тесты и регрессия не нужны.

## Обнаруженные проблемы

1. **Автономные скрипты `examples/` не импортирует ни один тест.** `grep` по `tests/` на `run_path|import_module|spec_from_file_location|py_compile` — пусто. Скрипты сходимости (`01/spatial_convergence`, `04/grid_convergence`, `05/closed_form_convergence`, `04a/grid_convergence`), `02/check_slopes`, `04a/rewrite_history`, `04a/plot_profiles_50k`, общие `check_energy_balance_all`, `verify_balance_vs_solver`, `compare_script_copies` запускаются только вручную: удаление или переименование имени в общем модуле ломает их молча. Тест шага 2 закрывает только три файла DEBT-031. Обобщение осложняет то, что `01_single_phase_no_jt/spatial_convergence.py` не защищён `if __name__ == "__main__"` — импорт запускает расчёт. **Не блокирует** DEBT-031. Зарегистрировано как **DEBT-046**.

## Связь формула → код

Не применимо: формулы не затрагиваются.

## Оценка

| Файл | Изменение |
|---|---|
| `numerical_solver/examples/convergence.py` | 198 → 68 строк |
| `numerical_solver/tests/test_examples.py` | +42 строки |
| `numerical_solver/examples/energy_balance_convergence.py` | комментарий 2 → 3 строки |
| `numerical_solver/examples/README.md` | 1 строка |

Время: ~40 минут + полный прогон ~10 минут.
