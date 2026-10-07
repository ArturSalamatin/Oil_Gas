---
tags:
  - план
  - инфраструктура
date: 2026-10-07
issue: DEBT-037
github: 66
branch: refactor/debt-037/shared-modules-copy-guard
status: в процессе
audit:
  date: 2026-10-07
  round: 2
  found: 7
  auto-fixed: 7
  manual-required: 0
---

# План DEBT-037: защита от копий общих модулей примеров строится по `examples/*.py`

**Задача:** DEBT-037 (`vault/roadmap/известные баги и технический долг.md`), issue [#66](https://github.com/ArturSalamatin/Oil_Gas/issues/66)
**Подтип:** инфраструктура (тестовая защита), код решателя и примеров не меняется
**Ветка:** `refactor/debt-037/shared-modules-copy-guard` от `numerical_scheme/implementation` (не раньше `6edc433`: там уже влиты DEBT-039 и BUG-021)
**Связанные заметки:** [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]], [[FEAT-016]], [[BUG-004]], [[DEBT-026]], [[DEBT-039]]

## Решения пользователя (2026-10-07)

1. Список для проверки копий строится по диску: **все** файлы `numerical_solver/examples/*.py`, включая 4 скрипта (`run_all.py` и др.), без исключений.
2. Проверка наличия `test_shared_modules_exist` **не меняется**: ручной `SHARED_CHECK_MODULES` (6 модулей после DEBT-039) + `convergence.py`.
3. Вариант 3 из issue (единый порядок `sys.path` в `main.py` 01, 02, 03, 05 и трёх скриптах сходимости) **в план не входит**.

## Контекст для читателя без истории

### Что защищается и почему

В `numerical_solver/examples/` лежат общие модули: проверки, графики, конвейер `example_runner.py`. Каждый пример (папка `examples/NN_имя/`) импортирует их по имени через `sys.path`. Если в папку примера положить файл с тем же именем, что и общий модуль, исход будет одним из двух, и оба молчаливые (проверено 2026-10-07):

| Порядок `sys.path` | Файлы | Что делает копия |
|---|---|---|
| сначала `examples/`, затем папка примера: папка оказывается **впереди** | `main.py` примеров 01, 02, 03, 05 (`examples/03_standing_corey/main.py:38, 40`); `examples/04_table_table/grid_convergence.py:50-51`; `examples/04a_high_gas_saturation/grid_convergence.py:46-48`; `examples/05_standing_table_rp/closed_form_convergence.py:36-37` | **перекрывает** общий модуль без ошибки импорта |
| вставляется только `examples/`, и он оказывается впереди каталога скрипта (`sys.path[0]` при запуске `python main.py`) | `main.py` остальных 16 примеров; `01_single_phase_no_jt/spatial_convergence.py`; `02_single_phase_jt/check_slopes.py`; `04a_high_gas_saturation/plot_profiles_50k.py` | **игнорируется**: правка копии ни на что не влияет |

Перекрытие транзитивно. Общие модули импортируют друг друга через тот же `sys.path`. Копия `figure_io.py` в папке 05 подменит модуль и внутри `example_runner.py`, `energy_balance.py`, `pvt_plot.py`, `relperm_plot.py`, `convergence.py`. Так четыре разошедшиеся копии `energy_balance.py` дали [[BUG-004]] (невязка баланса энергии 20 %).

### Что сейчас (HEAD `6edc433`)

`numerical_solver/tests/test_examples.py`:

- `:613` — заголовок раздела I («балансы энергии и массы…», правлен DEBT-039).
- `:616-629` — комментарий и ручной список `SHARED_CHECK_MODULES` из 6 модулей (5 из FEAT-016/017 и `mass_balance.py` из DEBT-039).
- `:756-769` — `TestSharedChecks.test_no_duplicate_helper_scripts` (декоратор на `:756`, `def` на `:757`), параметризован этим списком. Для каждого имени ищет `examples/*/<имя>` и падает, если нашёл.
- `:771-775` — `test_shared_modules_exist`: `SHARED_CHECK_MODULES + ["convergence.py"]` лежат в `examples/`.
- `:159-163` — `TestStructure.test_runner_and_run_all_exist`: наличие `example_runner.py`, `run_all.py`, `README.md`.

В `examples/` 16 файлов `*.py`. Проверку копий проходят 6 из них. Не защищены 10: `example_runner.py` (его импортируют все 20 `main.py`), `figure_io.py` (импортируют 6 общих модулей и 7 файлов примеров), `rs_analytics.py`, `closed_form.py`, `relperm_plot.py`, `convergence.py` и 4 скрипта (`check_energy_balance_all.py`, `compare_script_copies.py`, `run_all.py`, `verify_balance_vs_solver.py`). Копий сейчас нет ни одной: глоб по всем 16 именам в `examples/*/` пуст. Подкаталог `examples/`, не являющийся примером, всего один, `__pycache__`, и `.py` в нём нет.

Причина долга — сам механизм ручного списка. `figure_io.py` появился в [[FEAT-026]], уже после [[FEAT-016]], и в список не попал.

### Что должно стать

- `test_no_duplicate_helper_scripts` параметризован списком, построенным по диску: `sorted(p.name for p in EXAMPLES_DIR.glob("*.py"))`. Сейчас это 16 имён, новый файл в `examples/` попадает под проверку сам.
- `SHARED_CHECK_MODULES` остаётся только для `test_shared_modules_exist`. Глоб для проверки наличия бесполезен: найденный им файл существует по построению.
- Комментарий над списками описывает оба исхода копии (перекрытие и игнорирование) и причину глоба. Нынешний комментарий утверждает, что `main.py` ставит папку примера впереди, а это верно только для 4 из 20 `main.py`.
- Заметка-решение [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]] (`:72-75`) исправлена так же.

### Зона неприкосновенности

- `numerical_solver/gpn_multiphase_solver/`, `numerical_solver/examples/**` (включая порядок `sys.path`, решение 3), `numerical_solver/HydroSolverPrototype/`: не меняются.
- `test_shared_modules_exist`, `test_runner_and_run_all_exist`, состав `SHARED_CHECK_MODULES`, заголовок раздела I (`:613`): не меняются.
- `examples/compare_script_copies.py`, список `GROUPS`: это диагностический инструмент, а не защита. Его комментарий (`:30-35`) ссылается на `test_no_duplicate_helper_scripts` по имени, и имя теста **сохраняется**.
- Имя теста `test_no_duplicate_helper_scripts` упоминают заметка-решение (`:87`), `compare_script_copies.py:34` и планы FEAT-016, FEAT-017, DEBT-026, DEBT-039 и др. Не переименовывать.

## Baseline (2026-10-07, HEAD `6edc433`)

| Что | Значение |
|---|---|
| `pytest tests/ --collect-only -q` | 1289 tests |
| `pytest tests/ -m "not slow" --collect-only -q` | 1053/1289 |
| `-k "duplicate_helper or shared_modules_exist" --collect-only` | 7 (6 параметров + 1) |
| `sorted(examples/*.py)` | `check_energy_balance_all.py`, `closed_form.py`, `compare_script_copies.py`, `convergence.py`, `energy_balance.py`, `energy_balance_convergence.py`, `example_runner.py`, `figure_io.py`, `mass_balance.py`, `pvt_plot.py`, `relperm_plot.py`, `rs_analytics.py`, `run_all.py`, `temperature_asymptotics.py`, `two_phase_analytics.py`, `verify_balance_vs_solver.py` (16) |

Ожидание после: **1299** тестов, быстрый уровень **1063** (+10 параметров: было 6, станет 16). Все новые параметры быстрые: фикстура `results` не нужна, метку `slow` хук `tests/conftest.py:35-40` не ставит.

Если до реализации влиты другие ветки, абсолютные числа сдвинутся. Тогда проверяется разница: параметров становится столько, сколько файлов в `examples/*.py`.

## Варианты (кратко; полный разбор — issue #66)

| Вариант | Суть | Итог |
|---|---|---|
| 1 | дописать 6 модулей в ручной список | отклонён: причина долга (забытый список) остаётся |
| **2** | **параметр теста — глоб `examples/*.py`** | **выбран** (решение 1) |
| 3 | `examples/` впереди папки примера в 7 файлах | не входит (решение 3): копия всё равно молчит, только игнорируется |

## Подводные камни (чеклист 2.5)

- ✅ **Все места использования найдены.** `SHARED_CHECK_MODULES` в коде встречается только в `tests/test_examples.py` (`:622`, `:756`, `:773`). Остальные упоминания в vault — история.
- ✅ **Зависимости пакетов, импорты.** Новых нет: `Path` уже импортирован (`:18`), `EXAMPLES_DIR` определён на `:26`, раньше места использования.
- ✅ **Обратная совместимость.** Идентификаторы 6 существующих параметров (`[energy_balance.py]` … `[mass_balance.py]`) сохраняются, добавляются 10 новых. `pytest --lf` и кэш не ломаются.
- ✅ **Пустой глоб.** Сам по себе пустой список даёт SKIPPED («got empty parameter set»), а не FAIL (проверено пробой аудита). Но каталога `examples/` без файлов `*.py` не бывает без поломки всего модуля: на уровне модуля (`test_examples.py:886`, `load_config(EXAMPLES_DIR / name / "config.json")` для всех примеров) сборка падает с ERROR (проверено: каталог-заглушка → «1 error during collection»). Отдельная защита не нужна.
- ✅ **Порядок глоба.** `Path.glob` не гарантирует порядок, поэтому `sorted(...)`: идентификаторы параметров детерминированы.
- ✅ **Глоб при сборке.** Список вычисляется при импорте тестового модуля. Файл, созданный после сборки, не виден, но это ничему не мешает.
- ✅ **Windows.** Глоб на NTFS нечувствителен к регистру, все имена в нижнем регистре.
- ✅ **Глубина.** `*/{module}` ищет только в `examples/<папка>/`, как и раньше. `__pycache__` содержит только `.pyc` и не совпадает.
- ✅ **Длина строк.** Новые строки комментария ≤ 79 символов, как почти весь файл (длиннее 79 — 3 строки комментария из всех).
- ✅ **Связь с [[DEBT-039]]** — влит (`8df07ff`). Блок «До» 2a уже содержит его `"mass_balance.py",`, и строка остаётся в `SHARED_CHECK_MODULES`. Его тест `test_mass_balance_all_examples` и заголовок раздела I не затрагиваются.
- ✅ **Связь с [[BUG-021]]** — влит (`6edc433`), и **[[BUG-020]]** — план готов, ветки нет. Они правят прототип и тесты 13b/16, а не раздел I. Конфликта нет.
- ✅ **Configs, docstrings `\eqref{}`, циклические импорты, производительность.** Не затрагиваются. +10 тестов по ~1 мс (один глоб каждый).
- ✅ **Прототип.** Не меняется, тесты прототипа и регрессия не нужны.

## Обнаруженные проблемы

- Заметка-решение [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]] (`:72-75`) утверждает: «`main.py` каждого примера делает два `sys.path.insert(0, ...)`». Сейчас так делают только `main.py` 01, 02, 03, 05, у остальных 16 одна вставка. Так же неточен комментарий `test_examples.py:616-621`. Не блокирует. Исправляется в шагах 2 и 3 этого плана, отдельная запись в реестре не нужна.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]] (раздел «Три ловушки»).
3. **Код (шаги 1–2) — в отдельном worktree**, не в основном каталоге. Причина: в основном каталоге параллельные сессии коммитят vault в `numerical_scheme/implementation` (во время планирования так появились `59e9eab`, `546e6f8`, `1ea9697`, `acf0721`). `git checkout -b` в основном каталоге увёл бы их коммиты в ветку DEBT-037. Из корня проекта `d:\Lessons\Grants\2026\GPN\Oil_Gas`:
   `git worktree add .worktrees/debt-037 -b refactor/debt-037/shared-modules-copy-guard numerical_scheme/implementation`
   (если ветка уже есть: `git worktree add .worktrees/debt-037 refactor/debt-037/shared-modules-copy-guard`). `.worktrees/` исключён через `.git/info/exclude`.
4. **Vault (шаг 3) — в основном каталоге**, коммитом `vault:` в `numerical_scheme/implementation`, как у DEBT-039 (`546e6f8`, `1ea9697`): по конвенции проекта ветка задачи несёт только код. Stage — по имени файла: в основном каталоге лежат незакоммиченные правки vault других сессий.
5. Команды pytest и пробы шагов 1–2 выполняются из `d:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-037\numerical_solver`. venv общий, из основного каталога, в worktree его нет. Интерпретатор: `d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe`. Инструмент PowerShell **не сохраняет переменные между вызовами**, поэтому каждая команда начинается с `$PY = "d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe";`, затем `& $PY -m pytest ...`. Ниже `$PY` означает именно это. pytest из каталога worktree берёт код worktree (cwd первым в `sys.path`), а тест читает `examples/` относительно своего `__file__`, то есть каталог worktree.
6. Baseline: `& $PY -m pytest tests/ --collect-only -q` и `& $PY -m pytest tests/ -m "not slow" -q`. Запомни число тестов (всего и быстрых) и время быстрого уровня. Сверь с таблицей Baseline выше.
7. Шаги 1 → 2 → 3. После каждого — проверка из шага. Полный прогон — в конце, из worktree (`/implement` §3.1).

## Шаги

### Шаг 1: Baseline и проба нынешней защиты

**Цель:** зафиксировать исходные числа и показать, что сегодня копия `figure_io.py` проверкой не ловится.

**Файлы:** нет правок. Временный файл `.worktrees/debt-037/numerical_solver/examples/01_single_phase_no_jt/figure_io.py` удаляется в этом же шаге.

**Контекст:** отрицательная проба до правки нужна, чтобы шаг 2 проверялся по разнице «до/после», а не только по зелёному прогону: зелёный прогон защиты от копий ничего не доказывает, копий ведь нет.

**Что сделать** (из `.worktrees\debt-037\numerical_solver`, `$PY` — см. «Как начать», п. 5):
1. `& $PY -m pytest tests/ --collect-only -q` → записать число (ожидание 1289).
2. `& $PY -m pytest tests/ -m "not slow" -q` → записать число passed и время (ожидание 1053 passed, ~70 с).
3. `& $PY -m pytest tests/test_examples.py -k "duplicate_helper or shared_modules_exist" -q` → 7 passed.
4. Проба: `Copy-Item examples\figure_io.py examples\01_single_phase_no_jt\figure_io.py`, затем команда п. 3 → **7 passed** (копия не поймана, это и есть DEBT-037). Сразу после: `Remove-Item examples\01_single_phase_no_jt\figure_io.py`.
5. `git status --short` → пусто.

**Проверка после этого шага:**
- Регресс: быстрый (п. 2 и есть baseline).
- `git status` чистый: временная копия удалена.

**Подводные камни:** копию удалить обязательно. Иначе после шага 2 упадёт уже новый тест, а если её закоммитить, будут перекрыты рисунки 01 при запуске `main.py` 01 (папка 01 стоит в `sys.path` впереди).

**Зависимости:** блокирует шаг 2.

**Оценка:** 0 строк, ~3 мин.

### Шаг 2: Параметр проверки копий — глоб `examples/*.py`

**Цель:** `test_no_duplicate_helper_scripts` проверяет все 16 файлов `examples/*.py`, и новый файл попадает под проверку сам.

**Файлы:** `numerical_solver/tests/test_examples.py` (в worktree).

**Контекст:** см. «Контекст для читателя». `SHARED_CHECK_MODULES` остаётся и по-прежнему кормит `test_shared_modules_exist` (решение 2). Новая константа `SHARED_EXAMPLE_FILES` кормит проверку копий (решение 1). Комментарий переписывается, потому что нынешний неточен: копия перекрывает общий модуль только у 4 `main.py` и 3 скриптов, у остальных она игнорируется. Содержание старого комментария (механизм перекрытия, BUG-004) сохраняется.

**Что сделать:**
1. Заменить блок `:616-629` (комментарий + `SHARED_CHECK_MODULES`), см. «Изменения 2a».
2. Заменить декоратор и тело `test_no_duplicate_helper_scripts` (`:756-769`), см. «Изменения 2b».
3. `test_shared_modules_exist` (`:771-775`) не трогать.

**Изменения 2a (`:616-629`).**

До:
```python
# Модули проверок, вынесенные в examples/ (FEAT-016). Ни один из них не
# должен снова появиться в папке примера: копия в папке ПЕРЕКРЫВАЕТ общий
# модуль молча, без ошибки импорта (main.py делает sys.path.insert(0, ...)
# сначала для examples/, затем для папки примера, поэтому папка примера
# оказывается впереди). Именно так четыре копии energy_balance.py
# разошлись и породили BUG-004.
SHARED_CHECK_MODULES = [
    "energy_balance.py",
    "energy_balance_convergence.py",
    "temperature_asymptotics.py",
    "two_phase_analytics.py",
    "pvt_plot.py",
    "mass_balance.py",
]
```

После:
```python
# Модули проверок, вынесенные в examples/ (FEAT-016; mass_balance.py —
# DEBT-039). test_shared_modules_exist проверяет, что они на месте: без них
# примеры не считают проверки.
SHARED_CHECK_MODULES = [
    "energy_balance.py",
    "energy_balance_convergence.py",
    "temperature_asymptotics.py",
    "two_phase_analytics.py",
    "pvt_plot.py",
    "mass_balance.py",
]

# Все файлы верхнего уровня examples/ — общие модули и скрипты. Ни один из
# них не должен снова появиться в папке примера: исход у копии молчаливый
# при любом порядке sys.path.
#   - main.py 01, 02, 03, 05 и скрипты сходимости 04, 04a, 05 делают
#     sys.path.insert(0, ...) сначала для examples/, затем для папки
#     примера, и папка оказывается ВПЕРЕДИ. Копия ПЕРЕКРЫВАЕТ общий модуль
#     без ошибки импорта — и для всех, кто его импортирует: копия
#     figure_io.py подменит его и внутри example_runner.py.
#   - Остальные main.py вставляют только examples/, и он встаёт впереди
#     папки скрипта. Копия молча игнорируется: её правка ни на что не влияет.
# Именно так четыре копии energy_balance.py разошлись и породили BUG-004.
# Список строится по диску, а не вручную (DEBT-037): ручной список отстал —
# example_runner.py, figure_io.py и ещё четыре общих модуля в нём не
# значились. Новый файл в examples/ попадает под проверку сам.
SHARED_EXAMPLE_FILES = sorted(p.name for p in EXAMPLES_DIR.glob("*.py"))
```

**Изменения 2b (`:756-769`).**

До:
```python
    @pytest.mark.parametrize("module", SHARED_CHECK_MODULES)
    def test_no_duplicate_helper_scripts(self, module):
        """Вынесенный модуль не вернулся копией в папку примера.

        Защита от того самого механизма, которым возникла FEAT-016: скрипт
        пишется под один пример, копируется в другой, копии правятся
        независимо и расходятся. Копия в папке примера при этом молча
        перекрывает общий модуль.
        """
        copies = sorted(
            p.parent.name for p in EXAMPLES_DIR.glob(f"*/{module}"))
        assert not copies, (
            f"{module} снова скопирован в папки примеров: {copies}. "
            f"Общий модуль examples/{module} будет молча перекрыт.")
```

После:
```python
    @pytest.mark.parametrize("module", SHARED_EXAMPLE_FILES)
    def test_no_duplicate_helper_scripts(self, module):
        """Файл examples/ не вернулся копией в папку примера.

        Защита от того самого механизма, которым возникла FEAT-016: скрипт
        пишется под один пример, копируется в другой, копии правятся
        независимо и расходятся. Копия в папке примера при этом молча
        перекрывает общий модуль или молча игнорируется — в зависимости
        от порядка sys.path (комментарий у SHARED_EXAMPLE_FILES).
        """
        copies = sorted(
            p.parent.name for p in EXAMPLES_DIR.glob(f"*/{module}"))
        assert not copies, (
            f"{module} снова скопирован в папки примеров: {copies}. "
            f"Общий модуль examples/{module} будет молча перекрыт, "
            f"либо копия будет молча проигнорирована.")
```

**Проверка после этого шага** (из `.worktrees\debt-037\numerical_solver`):
1. `& $PY -m pytest tests/test_examples.py -k "duplicate_helper or shared_modules_exist" --collect-only -q` → **17** (16 параметров + 1). Среди параметров есть `[example_runner.py]`, `[figure_io.py]`, `[mass_balance.py]`, `[run_all.py]`.
2. Тот же `-k` без `--collect-only` → 17 passed.
3. **Отрицательная проба А** (та же копия, что в шаге 1, п. 4, где она не ловилась):
   `Copy-Item examples\figure_io.py examples\01_single_phase_no_jt\figure_io.py`;
   `& $PY -m pytest "tests/test_examples.py::TestSharedChecks::test_no_duplicate_helper_scripts[figure_io.py]" -q` → **1 failed**, в сообщении `figure_io.py снова скопирован в папки примеров: ['01_single_phase_no_jt']`;
   `Remove-Item examples\01_single_phase_no_jt\figure_io.py`.
4. **Отрицательная проба Б** (новый общий модуль защищён без правки списка):
   `Set-Content -Encoding utf8 examples\zz_debt037_probe.py "# проба DEBT-037"`;
   `Copy-Item examples\zz_debt037_probe.py examples\03_standing_corey\zz_debt037_probe.py`;
   `& $PY -m pytest tests/test_examples.py -k "duplicate_helper" -q` → **1 failed, 16 passed**, упал параметр `[zz_debt037_probe.py]`, папка `['03_standing_corey']`;
   `Remove-Item examples\zz_debt037_probe.py, examples\03_standing_corey\zz_debt037_probe.py`.
5. `git status --short` → только `numerical_solver/tests/test_examples.py`.
6. Регресс: быстрый. `& $PY -m pytest tests/ -m "not slow" -q` → **1063 passed** (baseline + 10). `--collect-only -q` → **1299**.

Проба аудита `vault/issues/debt-037/probes/apply_plan.py` (раунд 2, HEAD `6edc433`) проверила шаг 2 без правки проекта. Блоки «До» 2a и 2b найдены в нынешнем файле по одному разу. Пропатченный тест на настоящем `examples/` — 17 collected, 17 passed. Пробы А и Б на фиктивном каталоге — `1 failed, 15 passed` (`[figure_io.py]`, `['01_single_phase_no_jt']`) и `1 failed, 16 passed` (`[zz_debt037_probe.py]`). Новые строки ≤ 79 символов. Проба читает файлы основного каталога (`vault/issues/` в `.gitignore`, в worktree его нет), поэтому ручные пробы А и Б в worktree обязательны.

**Подводные камни:** пустой глоб, порядок и имя теста описаны в чеклисте. Пробные файлы удаляются в той же команде, где созданы. Если проба упала не так, как ожидалось, сначала удалить файлы, потом разбираться.

**Зависимости:** требует шаг 1. Блокирует шаг 3.

**Оценка:** ~20 строк (+17 комментарий и константа, ~3 в тесте), ~15 мин.

### Шаг 3: Vault — заметка-решение

**Цель:** исправить в заметке-решении неточное описание порядка `sys.path` и указать, что защита строится по диску.

**Файлы:** `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md` (`:72-75`, `:87`). Правка **в основном каталоге** (`d:\Lessons\Grants\2026\GPN\Oil_Gas\vault\...`), не в worktree (см. «Как начать», п. 4).

**Контекст:** заметка — первоисточник правила «копии удаляются в том же шаге, где создаётся общий модуль». Её текст о двух вставках `sys.path` у каждого `main.py` неверен для 16 из 20 примеров. Команда проверки `:84` остаётся верной: она моделирует порядок 03 явно.

**Что сделать:**
1. Заметка, `:72-75`. Абзац от «`main.py` каждого примера делает два `sys.path.insert(0, ...)`» до «общий модуль просто не используется.» включительно заменить на:
   ```markdown
   `main.py` примеров 01, 02, 03, 05 и скрипты сходимости 04, 04a, 05 делают
   два `sys.path.insert(0, ...)`: сначала для `examples/`, затем для папки
   примера. Поскольку `insert(0, ...)` кладёт в начало, папка примера
   оказывается **впереди**. При одноимённых модулях загружается копия, и
   ошибки не возникает — общий модуль просто не используется, причём и внутри
   других общих модулей, которые его импортируют. Остальные `main.py` (16 из 20
   на 2026-10-07) вставляют только `examples/` — там копия, наоборот, молча
   игнорируется. Оба исхода молчаливые (уточнено в DEBT-037).
   ```
2. Заметка, `:87`.
   До: ``Структурная защита: `tests/test_examples.py::TestSharedChecks::test_no_duplicate_helper_scripts`.``
   После: ``Структурная защита: `tests/test_examples.py::TestSharedChecks::test_no_duplicate_helper_scripts` — по всем файлам `examples/*.py`, список строится по диску (DEBT-037; до него — ручной список модулей).``
3. Коммит в основном каталоге: `git add "vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md"`, затем `git commit -m "vault: DEBT-037 — заметка-решение: порядок sys.path, защита по всем examples/*.py"`.

**Проверка после этого шага:**
- Регресс: шаг меняет только документы, поэтому `--collect-only -q` в worktree → 1299, как после шага 2.
- `Grep "каждого примера делает два"` по заметке → нет совпадений.

**Подводные камни:** не делать `git add` по каталогу: в основном каталоге незакоммиченные правки vault других сессий.

**Зависимости:** требует шаг 2 (текст заметки описывает результат шага 2).

**Оценка:** ~10 строк vault, ~10 мин.

## Тестовая стратегия

**Тест:** `TestSharedChecks::test_no_duplicate_helper_scripts` (изменён: параметр)
**Файл:** `numerical_solver/tests/test_examples.py` (существующий)
**Сценарий:** для каждого файла `examples/*.py` в папках `examples/*/` нет файла с тем же именем.
**Setup:** нет. Читается текущее дерево `examples/`.
**Ожидание:** 16 passed на текущем дереве. Пробы А и Б (шаг 2) — ровно один failed с именем модуля и папки.
**Baseline:** 6 параметров, проба А на baseline — passed (не ловится).
**Предотвращает:** возврат копии любого общего модуля (`example_runner.py`, `figure_io.py`, …) в папку примера и тихое перекрытие (BUG-004) или тихое игнорирование. Новые общие модули — без правки списка.

**Регресс без изменений:** `test_shared_modules_exist`, `test_runner_and_run_all_exist`, весь быстрый уровень (1063), полный прогон в конце (1299).

Тест на сам тест (подмена `EXAMPLES_DIR` на `tmp_path`) не пишется: проверка — одна строка глоба, и ручные пробы А и Б в шаге 2 её исчерпывают. Отдельная функция ради подмены каталога — абстракция сверх задачи.

## Критерии завершения

- [ ] Шаги 1–3 выполнены.
- [ ] `--collect-only`: 1299 тестов, быстрый уровень 1063 (или baseline + 10 при сдвинутом baseline).
- [ ] `test_no_duplicate_helper_scripts` параметризован `SHARED_EXAMPLE_FILES`, 16 параметров, все зелёные.
- [ ] Пробы А и Б дали по одному failed с именем модуля и папки. Пробные файлы удалены (`git status` в worktree — только намеренные правки).
- [ ] `test_shared_modules_exist`, состав `SHARED_CHECK_MODULES` (6 модулей) и `examples/**` не изменены.
- [ ] Быстрый уровень после каждого шага зелёный. Полный прогон в конце (из worktree) зелёный.
- [ ] Заметка-решение исправлена (`:72-75`, `:87`) и закоммичена в базовую ветку из основного каталога.
- [ ] Vault: статус DEBT-037, issue #66 прокомментирован результатом и закрывается при слиянии.

## Оценка

1 файл кода (`tests/test_examples.py`, ~20 строк), 1 файл vault (~10 строк), 3 шага, ~30 мин.
