---
tags:
  - план
  - инфраструктура
date: 2026-10-10
issue: DEBT-059
github: 94
branch: refactor/debt-059/installable-prototype-package
status: реализован
worktree: .worktrees/debt-059
audit:
  date: 2026-10-10
  found: 8
  auto-fixed: 8
  manual-required: 0
---

# DEBT-059: прототип `radial_blackoil` — устанавливаемый дистрибутив `radial-blackoil`

Подтип: **инфраструктура** (упаковка). Кода расчёта задача не меняет: числа всех расчётов побитово прежние — это проверяет отпечаток истории (шаги 0, 5) и регрессия прототипа (шаги 0, 6).

## Как начать работу по этому плану

Обозначения — как в `/implement` («Схема работы»): `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas`, `<W>` = `<КОРЕНЬ>\.worktrees\debt-059`, `<PY>` = `<КОРЕНЬ>\numerical_solver\.venv\Scripts\python.exe`. Переменные PowerShell (`$env:PYTHONPATH`) задавать в той же команде, что и запуск.

1. Прочитай этот файл целиком: особенно «Решения пользователя», «Чеклист подводных камней» и раздел «После влития».
2. Прочитай запись DEBT-059 в `vault/roadmap/известные баги и технический долг.md` и тело issue `vault/issues/debt-059/01-issue-body.md`.
3. Пробы планирования лежат в `vault/issues/debt-059/probes/` и попадут в worktree с предварительным коммитом `/implement` (1.4). Это `history_fingerprint.py`, `clean_env_acceptance.py`, вспомогательные пробы и их выводы `*.out.txt`. Понадобятся в шагах 0 и 5.
4. Worktree `<W>` на ветке `refactor/debt-059/installable-prototype-package` от `numerical_scheme/implementation`. Это делает `/implement` (1.5).
5. ⚠️ **В общий venv (`<PY>`) во время реализации ничего не устанавливать** (`pip install` только во временные окружения пробы приёмки). Почему — подводный камень П1.
6. Базовый вариант — шаг 0.
7. Дальше шаги 1–6 по порядку. После каждого — тест шага и регресс по полю «Регресс». Полный прогон — в шаге 6.

## Решения пользователя (2026-10-10, при планировании)

| Вопрос | Решение | Следствие для плана |
|---|---|---|
| В каком виде передать прототип | **Два дистрибутива в одном репозитории**: у прототипа свой `pyproject.toml` (`radial-blackoil`), GPN объявляет его в `dependencies` | импорты ядра (8 мест) и тестов прототипа не меняются |
| Как тесты GPN находят прототип | **`pythonpath` в `[tool.pytest.ini_options]`** вместо вставки в `tests/conftest.py` | тесты берут прототип из своего дерева (в worktree — из worktree); правила `/implement` и `/merge` для pytest не меняются |
| Номер версии | **`1.0.3+gpn.1` только у дистрибутива** (`radial_blackoil.__version__`); `build_info.VERSION`, `BUILD_ID`, поля `prototype_version`/`build_id` в `run_summary.json` остаются `1.0.3` | эталоны регрессии и `test_output_contract.py:14` не трогаются; GPN требует `radial-blackoil==1.0.3+gpn.1` |
| `PACKAGE_MANIFEST_SHA256.txt` | **Оставить как запись поставки 2026-08-25**: файл не меняется; в CHANGELOG и README прототипа — что он описывает поставку и с кодом не совпадает | исходный `Prototype_1.0.3.zip` в git не хранится (`*.zip` в `.gitignore`), манифест — единственная запись исходных сумм в репозитории |

Решения по умолчанию (не обсуждались отдельно, приняты планом; при несогласии — до `/implement`):
- каталог `Prototype_1.0.3/` **не переименовывается** — переименование трогает все пути к данным прототипа (тесты, пример 18, README), а имя — это исходный выпуск;
- `XlsxWriter` и `matplotlib` — **обязательные** зависимости прототипа: `run_workbook` входит в API пакета (`radial_blackoil/__init__.py:3`), его вызывают пример 18 (`prototype_input.py:223`) и фикстура `prototype_18` (`tests/test_examples.py:2882`); без `XlsxWriter` пример 18 падает;
- `requirements.txt` прототипа **не меняется** — это проверенное окружение выпуска 1.0.3 для входа через Excel из корня прототипа (`docs/QUICK_START.md:13`); нижние границы — в `pyproject.toml`;
- команды входа через Excel в пакете нет (`run_prototype.py` остаётся скриптом в репозитории) — FEAT-030/031;
- тесты прототипа (unittest, 97) в прогон `pytest` GPN не включаются — у них свои команды.

## Контекст

### Что сейчас

- Гидродинамику считает прототип `radial_blackoil` (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/`). Ядро импортирует его лениво, внутри функций: `numerical_solver/gpn_multiphase_solver/factory.py:132`, `:348-349`, `:374`, `:390-392`, `:488`; `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py:60`, `:78`. Эти импорты задача **не меняет**.
- У прототипа нет `pyproject.toml`, в `dependencies` пакета GPN (`numerical_solver/pyproject.toml:10-14`) его нет. Воспроизведение на `c0ec060`:
  ```powershell
  numerical_solver\.venv\Scripts\python -c "from gpn_multiphase_solver.io.config import load_config; from gpn_multiphase_solver.factory import SimulatorFactory; SimulatorFactory.from_config(load_config(r'numerical_solver\examples\03_standing_corey\config.json'))"
  # ModuleNotFoundError: No module named 'radial_blackoil'   (factory.py:390)
  ```
- Находится прототип только через вставки пути в `sys.path`. Мест 14, проба `plan_tests_check.out.txt` находит ровно их:

  | Файл (`numerical_solver/...`) | Строки | Вид |
  |---|---|---|
  | `tests/conftest.py` | 10-14 | `_PROTO_ROOT`, `sys.path.insert` |
  | `examples/example_runner.py` | 30-46 | `_SOLVER_ROOT`, `_PROTO_ROOT`, проверка каталога, `RuntimeError`, вставка |
  | `examples/convergence.py` | 33-36 | цикл `for _p in (_ROOT, _EXAMPLES, <прототип>)` |
  | `examples/energy_balance.py` | 54-57 | то же |
  | `examples/energy_balance_convergence.py` | 52-55 | то же |
  | `examples/mass_balance.py` | 44-47 | то же |
  | `examples/two_phase_analytics.py` | 97-100 | то же |
  | `examples/temperature_asymptotics.py` | 104-108 | `_PROTO` в блоке `__main__` |
  | `examples/verify_balance_vs_solver.py` | 30-37 | `_PROTO` после цикла |
  | `examples/check_energy_balance_all.py` | 32 | одна строка |
  | `examples/01_single_phase_no_jt/spatial_convergence.py` | 27 | одна строка |
  | `examples/02_single_phase_jt/check_slopes.py` | 40 | одна строка |
  | `examples/05_standing_table_rp/closed_form_convergence.py` | 38 | одна строка |
  | `examples/18_prototype_input/prototype_input.py` | 12, 18-23 | `PROTO_ROOT` + вставка; `import sys` только ради неё |

  Ещё два скрипта импортируют `_PROTO_ROOT` ради побочного действия: `examples/04_table_table/grid_convergence.py:53`, `examples/04a_high_gas_saturation/grid_convergence.py:50`. Механизм описан в `examples/README.md:238-239`.
- Окружение: общий venv `numerical_solver/.venv` (Python 3.13.3), `gpn-multiphase-solver 0.1.0` установлен с правкой исходников из основного каталога (finder в `sys.meta_path`). Стоят `numpy 2.5.2`, `scipy 1.18.1`, `matplotlib 3.11.1`, `xlsxwriter 3.2.9`. `setuptools` в venv **нет**: сборка идёт в изолированном окружении `pip`, `setuptools>=68` скачивается из PyPI. Worktree своего venv не имеют. pytest в worktree берёт `gpn_multiphase_solver` из worktree, потому что каталог запуска стоит первым в `sys.path`; прототип — по вставке в `conftest.py` относительно файла, тоже из worktree.
- Прототип — самостоятельный продукт. Вход через Excel — `run_prototype.py`. Тесты — `tests/`: unittest, импорты `from tests.helpers import ...` требуют корня прототипа в `sys.path`, запуск из корня. Регрессия — `regression/run_regression.py`: запускает `run_prototype.py` подпроцессом с `cwd=ROOT` (`:89-90`) и от установки не зависит. Сверяет CSV и поля `run_summary.json`, в том числе `prototype_version` и `build_id` (`:72`). `tests/test_output_contract.py:14` проверяет `prototype_version == '1.0.3'`.
- Сторонние импорты (проба `plan_tests_check.out.txt`). `gpn_multiphase_solver`: `matplotlib`, `numpy`, `radial_blackoil`, `scipy`. `radial_blackoil`: `matplotlib`, `numpy`, `scipy`, `xlsxwriter` — последние два только внутри функций `output_artifacts.py:48`, `:138`, `:165`.

### Что хотим

- `pip install -e HydroSolverPrototype/Prototype_1.0.3 -e ".[dev]"` ставит оба пакета. Установка из колёс (`.whl`) без PyPI тоже работает. `SimulatorFactory.from_config` работает из любого каталога.
- В коде `numerical_solver/` (пакет, примеры, тесты) нет ни одной вставки пути к прототипу. Это сторожит тест. pytest берёт прототип из своего дерева через `pythonpath`.
- У дистрибутива прототипа один источник версии (`radial_blackoil.__version__ = '1.0.3+gpn.1'`). GPN требует ровно её, согласованность проверяет тест.
- Расчёты побитово прежние: отпечаток примеров 03, 04, 05; регрессия прототипа 11/11 PASS.

### Почему именно так (что проверено пробами при планировании)

Пробы — в `vault/issues/debt-059/probes/`, выводы — в `*.out.txt` рядом.

| Проба | Что показала |
|---|---|
| `packaging_feasibility.py` (на копиях в `numerical_solver/build/`, удалены) | `setuptools` читает `1.0.3+gpn.1` из литерала `__version__` статически, без импорта пакета (в изолированной сборке numpy нет); в колесе прототипа только `radial_blackoil`; `pip install --no-index --find-links` находит `radial-blackoil==1.0.3+gpn.1` как зависимость GPN; `pip check` чистый; установка с правкой исходников — через finder в `sys.meta_path`, пакет `tests` прототипа наружу не виден (`find_spec('tests')` → `None`); отпечаток 03 в чистом окружении равен текущему |
| `history_fingerprint.py` → `fingerprint_plan_c0ec060.out.txt` | отпечатки примеров 03, 04, 05 на `c0ec060` (по 73 записи, ~0.5 с каждый) |
| `acceptance_dry_run.py` → `acceptance_dry_run.out.txt` | `clean_env_acceptance.py` на макете будущего дерева: все 9 проверок «ОК», «ПРИЁМКА: ПРОЙДЕНА» |
| `plan_tests_check.py` → `plan_tests_check.out.txt` | разбор AST будущего `test_packaging.py` на текущем дереве: 81 вставка в `sys.path`, из них 14 — пути к прототипу (ровно таблица выше); `__version__` читается статически |
| `audit_plan_dry_run.py` (+ `plan_blocks.py`) → `audit_plan_dry_run.out.txt` (аудит, `b3ffaac`) | шаги 1–3 применены к копии дерева блоками «До/После» **из текста этого плана**: все блоки «До» найдены ровно столько раз, сколько нужно; `test_packaging.py` 8 passed, с `-o pythonpath=` — 1 failed (ожидаемый); 1687 тестов, быстрый уровень 1425 passed; примеры 03, 18 с `PYTHONPATH` на копию — считаются, пример 03 без него — `ModuleNotFoundError: radial_blackoil`. `plan_blocks.py` берёт блоки по номерам: после правки плана, добавляющей блоки кода в шаги 0–3, номера в `audit_plan_dry_run.py` сверить |
| `audit_regression_quick.out.txt` (аудит, `b3ffaac`) | регрессия прототипа `--quick` до правки — 11/11 PASS |

## Варианты

| Вариант | Суть | Итог |
|---|---|---|
| 1. Два дистрибутива | `pyproject.toml` у прототипа, GPN — `radial-blackoil==1.0.3+gpn.1` в `dependencies` | **выбран пользователем** |
| 2. Подпакет GPN | `radial_blackoil` → `gpn_multiphase_solver/prototype/`; переписать 8 импортов ядра, импорты тестов прототипа (17 файлов с `from tests...`), `run_prototype.py` | отклонён: смешивает версию, регрессию и авторство прототипа с ядром, больше правок |
| 3. Оставить `sys.path` | — | задачу не решает |

Как тесты находят прототип:

| Вариант | Итог |
|---|---|
| A. `pythonpath = ["HydroSolverPrototype/Prototype_1.0.3"]` в `[tool.pytest.ini_options]` | **выбран**: тесты проверяют код своего дерева при общем venv; правила `/implement`, `/merge` для pytest не меняются. Цена — тесты не замечают забытую установку прототипа; её ловит приёмка (шаг 5) |
| B. Только установленный пакет + сторож происхождения в `conftest.py` + `PYTHONPATH` в worktree | отклонён: в worktree общий venv дал бы прототип основного каталога; нужен `PYTHONPATH` на каждый прогон pytest и правка `/implement`, `/merge` |

**Промежуточные состояния:** каждый шаг оставляет тесты зелёными. Шаг 1 только добавляет `pyproject.toml` прототипа: GPN от него ещё не зависит. Шаг 2 меняет путь прототипа в pytest с `conftest.py` на `pythonpath`; путь тот же, `sys.path` тот же. Шаг 3 убирает вставки из примеров: тесты их уже не используют, а запуск примеров в worktree по правилу 3 `/implement` и так задаёт `PYTHONPATH` на оба пакета. Шаг 4 — только документы.

## Чеклист подводных камней

- ✅ **Все места найдены.** 14 вставок пути и 2 импорта `_PROTO_ROOT`. Grep по `HydroSolverPrototype`, `Prototype_1.0.3`, `_PROTO`, `sys.path` в `numerical_solver/` и проба AST дали одно и то же. Ленивые импорты ядра не меняются. Вне задачи и вне сторожа — неотслеживаемый `numerical_solver/deliverables/` (в git нет) и пробы прежних задач в `vault/issues/*/probes/`: они вставляют путь сами, это продолжит работать — вставка в `sys.path` важнее finder-а установки.
- ⚠️ **П1. Общий venv не трогать.** Если во время реализации поставить прототип в `<PY>` с правкой исходников из `<W>`, то основной каталог и параллельные сессии начнут импортировать прототип из worktree. После `/merge` worktree удаляется, finder указывает в пустоту, и после влития (вставки в `conftest.py` уже нет) всё ломается. Поэтому в шагах 1–6 `pip install` — только во временные окружения `clean_env_acceptance.py` в `<W>\numerical_solver\build\`. Установка в общий venv — из `<КОРЕНЬ>`, после влития (раздел «После влития»). Контроль: `pip freeze` общего venv в шаге 0 и в шаге 6 совпадают.
- ⚠️ **П2. Пример и тесты после влития до установки.** В основном каталоге после влития примеры (`example_runner` больше не вставляет путь) и `run.md` падают с `ModuleNotFoundError: radial_blackoil`, пока прототип не поставлен в общий venv. Тесты не падают: у них `pythonpath`. Установка — раздел «После влития», сразу после `/merge`. Это написано в `05-comment-done.md` и в записи реестра.
- ⚠️ **П3. Побочное действие импорта `example_runner`.** Скрипты `04_table_table/grid_convergence.py:53` и `04a_high_gas_saturation/grid_convergence.py:50` импортируют `_PROTO_ROOT` «ради подключения прототипа». Но этот импорт заодно переключает консоль на UTF-8 (`example_runner.py:26-28`), а скрипты печатают `м³ст/с`: символа `³` в cp1251 нет. Если просто удалить строку, на консоли Windows будет `UnicodeEncodeError`. Поэтому строка заменяется на `import example_runner` с комментарием, а не удаляется (шаг 3).
- ⚠️ **П4. Версия должна оставаться литералом.** `setuptools` читает `radial_blackoil.__version__` статически (разбором AST). Если заменить литерал выражением или импортом (`from .build_info import ...`), `setuptools` начнёт импортировать пакет. В изолированной сборке numpy нет — сборка упадёт. Комментарий в `__init__.py` и тест `test_prototype_version_is_dynamic_from_literal` (+ `_static_version` в `test_gpn_pins_prototype_version` падает, если `__version__` не литерал).
- ✅ **Подмена зависимости из PyPI закрыта самой версией.** Требование `==1.0.3+gpn.1` содержит локальную метку. Кандидат подходит только с той же меткой, а PyPI не принимает загрузки с локальными метками версий. Значит, чужой `radial-blackoil` из PyPI зависимость не удовлетворит. `pip install -e .` без прототипа заканчивается ошибкой «No matching distribution found for radial-blackoil==1.0.3+gpn.1», а не установкой чужого пакета. Сейчас имя в PyPI свободно (`pip index versions radial-blackoil` → «No matching distribution found», 2026-10-10). Приёмка всё равно ставит с `--no-index`.
- ✅ **Обратная совместимость API.** Импорты и сигнатуры не меняются. Удаляются `example_runner._PROTO_ROOT` и `_SOLVER_ROOT`: используют их только 04/04a (`grep`), они правятся в том же шаге. Если пропустить, это поймает `tests/test_example_scripts.py` (DEBT-046 проверяет, что импортированные имена существуют).
- ✅ **Состояние при ошибке.** Неприменимо: логики расчёта нет.
- ⚠️ **Тесты.** Шаг 2 меняет `tests/conftest.py` — по DEBT-032 это повод для полного прогона. Полный прогон делается один, в шаге 6. Он покрывает и `conftest.py` (шаг 2), и `example_runner.py` (шаг 3), который тесты на фикстуре `results` импортируют в том же процессе. Ошибка здесь не тонкая, а грубая (`ModuleNotFoundError` на первом же расчёте) и находится сразу, поэтому отдельный полный прогон после шага 2 не нужен. Быстрый уровень после шагов 2 и 3 включает `test_examples.py` без `results`, `test_example_scripts.py`, `test_mass_balance.py`, `test_energy_balance_examples.py`, `test_rs_analytics.py`: они импортируют общие модули `examples/`.
- ✅ **Циклы импортов.** Новых импортов в пакетах нет.
- ✅ **Docstrings / метки уравнений.** Ссылок на уравнения новый код не содержит. Сторож DEBT-010 `tests/test_eq_references.py` (влит в `b3ffaac`) просматривает все `.py` в `gpn_multiphase_solver/`, `tests/`, `examples/` и README примеров на запрещённые формы («eq. N», «ур. N», «.tex:N»). Новые тексты плана их не содержат: быстрый уровень на копии дерева после шагов 1–3 зелёный (аудит).
- ✅ **Тесты прототипа и конфигурация pytest.** pytest, запущенный из корня прототипа (`pytest tests`), берёт `rootdir` = `numerical_solver/` и `configfile` = `numerical_solver/pyproject.toml`. Раздел `[tool.pytest.ini_options]` есть только там, а новый `pyproject.toml` прототипа без него конфигурацией не становится. Значит, `pythonpath` GPN действует и на тесты прототипа и указывает на то же дерево. Аудит: на копии после шагов 1–3 — 97 passed, `rootdir`/`configfile` как сказано.
- ✅ **Установка по инструкции пользователя (с PyPI).** Аудит на копии дерева, в новом окружении. `pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"` ставит `radial-blackoil 1.0.3+gpn.1` из каталога, `pip check` чистый. Пример 03 без `PYTHONPATH` считается, `test_packaging.py` — 8 passed. `pip install -e ".[dev]"` без прототипа — `ERROR: No matching distribution found for radial-blackoil==1.0.3+gpn.1`, как обещает README.
- ✅ **Данные пакета.** В `gpn_multiphase_solver/` нет файлов, кроме `.py`: колесо без `package-data` полное.
- ✅ **Конфиги.** `configs/*.json`, `examples/*/config.json` не меняются.
- ⚠️ **Связь с другими задачами.**
  - DEBT-048 (план готов, аудит ✅) дописывает раздел в конец `CHANGELOG_1.0.3.md` и правит комментарий `tests/conftest.py:27`. Второй влитый из двух получит конфликт в CHANGELOG: обе стороны дописывают в конец файла. `/merge` остановится, так как конфликт вне `vault/`. Разрешение — оставить оба раздела. В `conftest.py` правки не пересекаются (строки 3-14 против 27).
  - BUG-024 (план `vault/plans/bug-024 stage4-rs-step-limit.md` появился во время аудита) правит `radial_blackoil/blackoil.py` и тоже дописывает раздел в конец `CHANGELOG_1.0.3.md`: тот же конфликт при влитии, то же разрешение — оба раздела. Других общих файлов нет.
  - VAL-004 может добавить метку в `[tool.pytest.ini_options]` (`pyproject.toml:35-37`). Строка `pythonpath` встаёт после `testpaths` (`:29`) — возможен соседний конфликт; разрешение — обе строки.
  - DEBT-011 (#91), FEAT-030, FEAT-031 зависят от этой задачи. Вставки `numerical_solver/` и `examples/` в `sys.path` (плоские импорты общих модулей) — их предмет, здесь они остаются.
- ✅ **Производительность.** Не меняется (тот же код).
- ⚠️ **Прототип.** Правка `HydroSolverPrototype/`: новый `pyproject.toml`, литерал `__version__` в `radial_blackoil/__init__.py` (кроме него и `pyproject.toml` никто не читает: `grep __version__`), документы. Тесты прототипа — после шага 1 и в шаге 6. Регрессия `--quick` — в шаге 0 (базовый вариант) и в шаге 6. Ожидание: **11/11 PASS побитово**, потому что `build_info.VERSION`, `BUILD_ID`, `INPUT_FORMAT_VERSION`, которые сверяет `run_regression.py:72`, не меняются, а кода расчёта задача не касается. Полная регрессия с T05 (~45 мин) не нужна: T05 гоняет тот же код на других сетках, а затронут только литерал, который ни одна функция не читает.
- ⚠️ **Сеть.** Изолированная сборка (`pip wheel`, `pip install -e`) скачивает `setuptools>=68`; приёмка скачивает колёса numpy, scipy, matplotlib, XlsxWriter, setuptools (`pip download`, может взять из кэша `pip`). Без доступа к PyPI — сначала `<PY> -m pip download -d <каталог> setuptools>=68 wheel` на машине с сетью, затем `--no-index --find-links <каталог>`. При планировании сеть была.
- ⚠️ **`requires-python = ">=3.10"`** у обоих пакетов не проверен на 3.10–3.12: на машине есть только 3.13 и 3.9. Это прежняя декларация GPN, задача её не меняет; `test_packaging.py` использует `tomllib` (3.11+) через `pytest.importorskip` — на 3.10 эти тесты пропускаются, а не падают.
- ⚠️ **BOM в выводе PowerShell.** Перенаправление `>` в Windows PowerShell 5.1 пишет UTF-8 с BOM. Побайтовая сверка с файлом без BOM ложно расходится (поймано на пробе при планировании). Отпечаток пишет файл сам (`--out`), приёмка сравнивает построчно через `utf-8-sig`.

## Шаги

### Шаг 0: Базовый вариант

**Цель:** зафиксировать числа тестов, отпечаток расчётов и состояние общего venv до правки.

**Файлы:** — (только выводы в `<W>\vault\issues\debt-059\probes\` и `<W>\numerical_solver\build\`).

**Что сделать:**
1. Тесты GPN:
   ```powershell
   cd <W>\numerical_solver; <PY> -m pytest tests/ --collect-only -q
   cd <W>\numerical_solver; <PY> -m pytest tests/ -m "not slow" -q
   ```
   На `b3ffaac` (аудит 2026-10-10) — 1679 тестов; на `c0ec060`, при планировании, было 1677 — DEBT-010 добавил `tests/test_eq_references.py`. Быстрый уровень на `b3ffaac`: 1417 passed, 262 deselected, ~92 с, одно предупреждение (`PytestRemovedIn10Warning` из `_pytest/fixtures.py` — давнее, к задаче не относится). Если база ушла дальше, записать фактические числа. Ориентир после шагов 1–3 (аудит на копии дерева): 1687 тестов, быстрый уровень — 1425 passed (= 1417 + 8), 262 deselected, то же одно предупреждение.
2. Тесты и регрессия прототипа (регрессию — в фоне, ~8 мин):
   ```powershell
   cd <W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3; <PY> -m pytest tests -q
   cd <W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3; <PY> regression\run_regression.py --quick
   ```
   Ожидание: 97 passed, 11/11 PASS — оба подтверждены аудитом на `b3ffaac`. Шапка команд пишет 80 — устарело, см. «Обнаруженные проблемы». Красная база — СТОП.
3. Отпечаток расчётов до правки — код worktree через `PYTHONPATH` (как правило 3 `/implement`):
   ```powershell
   cd <W>\numerical_solver; $env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"; <PY> -X utf8 <W>\vault\issues\debt-059\probes\history_fingerprint.py --examples examples --out <W>\vault\issues\debt-059\probes\fingerprint_before.out.txt
   ```
   В stderr — пути импортов: оба должны быть в `<W>`. Сравнить с отпечатком планирования:
   ```powershell
   Compare-Object (Get-Content <W>\vault\issues\debt-059\probes\fingerprint_plan_c0ec060.out.txt) (Get-Content <W>\vault\issues\debt-059\probes\fingerprint_before.out.txt)
   ```
   Пусто — база для этих примеров не менялась (на `b3ffaac` пусто, проверено аудитом). Если не пусто — не ошибка, если база ушла вперёд по коду расчёта. Тогда эталон сверки — `fingerprint_before.out.txt`; записать в отчёт.
4. Состояние общего venv:
   ```powershell
   <PY> -m pip freeze > <W>\numerical_solver\build\debt059_venv_before.txt
   ```
   (`build/` игнорируется git.)

**Проверка после шага:** всё зелёное, файлы `fingerprint_before.out.txt` и `debt059_venv_before.txt` созданы.

**Оценка:** 0 строк кода, ~12 мин (из них регрессия ~8 мин в фоне).

---

### Шаг 1: `pyproject.toml` прототипа и версия `1.0.3+gpn.1`

**Цель:** прототип собирается в дистрибутив `radial-blackoil 1.0.3+gpn.1`, в который входит только пакет `radial_blackoil`.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/pyproject.toml` (новый)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/__init__.py`

**Контекст:** документы прототипа англоязычные; наши правки в нём (CHANGELOG «Local changes — GPN project») — тоже на английском. Новый `pyproject.toml` и комментарии в коде прототипа — на английском, в том же стиле. Нижние границы зависимостей — как у GPN (`numerical_solver/pyproject.toml:11-13`), чтобы оба пакета жили в одном окружении без противоречий. Проверены только версии venv (numpy 2.5.2, scipy 1.18.1) и `requirements.txt` прототипа.

**Что сделать:**
1. Создать `pyproject.toml`:
   ```toml
   # Installable distribution of Prototype 1.0.3 with the local changes of the
   # GPN project (DEBT-059, CHANGELOG_1.0.3.md). Only the package
   # radial_blackoil is installed; run_prototype.py, run.bat, tests/,
   # regression/ and docs/ stay in this directory and are run from it as before.
   [build-system]
   requires = ["setuptools>=68.0"]
   build-backend = "setuptools.build_meta"

   [project]
   name = "radial-blackoil"
   dynamic = ["version"]
   description = "1D radial black-oil simulator: Prototype 1.0.3 with local changes of the GPN project"
   requires-python = ">=3.10"
   # Lower bounds as in numerical_solver/pyproject.toml. Validated: the versions
   # of requirements.txt (1.0.3 release) and numpy 2.5.2, scipy 1.18.1 (GPN venv).
   dependencies = [
       "numpy>=1.24",
       "scipy>=1.10",
       # results.xlsx and PNG plots of run_workbook (output_artifacts.py,
       # imported lazily); run_workbook is part of the package API.
       "matplotlib>=3.7",
       "XlsxWriter>=3.2",
   ]

   [tool.setuptools.dynamic]
   # Read statically from the literal in radial_blackoil/__init__.py, without
   # importing the package: the isolated build environment has no numpy.
   version = {attr = "radial_blackoil.__version__"}

   [tool.setuptools.packages.find]
   where = ["."]
   # Explicit: tests/ (a package, it has __init__.py), regression/, docs/,
   # INPUT/ and OUTPUT/ lie next to radial_blackoil and must not be installed.
   include = ["radial_blackoil*"]
   ```
2. `radial_blackoil/__init__.py`.
   До:
   ```python
   __version__='1.0.3'
   from .input_reader import load_input, InputValidationError
   from .runner import run_workbook
   ```
   После:
   ```python
   # Distribution version (pip): Prototype 1.0.3 + local changes of the GPN
   # project, set 1 (CHANGELOG_1.0.3.md, DEBT-059). numerical_solver/pyproject.toml
   # requires radial-blackoil of exactly this version. Keep a plain literal:
   # setuptools reads it without importing the package. build_info.VERSION
   # ('1.0.3') is the version written to run_summary and compared by the
   # regression with the golden outputs; it is unchanged.
   __version__='1.0.3+gpn.1'
   from .input_reader import load_input, InputValidationError
   from .runner import run_workbook
   ```

**Проверка после этого шага:**
- Тесты прототипа: `cd <W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3; <PY> -m pytest tests -q` — 97 passed.
- Сборка колеса (в общий venv ничего не ставится):
  ```powershell
  cd <W>\numerical_solver; <PY> -m pip wheel --no-deps -q -w build\debt059_step1 HydroSolverPrototype\Prototype_1.0.3
  cd <W>\numerical_solver; <PY> -c "import glob, zipfile; w = glob.glob(r'build\debt059_step1\radial_blackoil-*.whl'); print(w); print(sorted({n.split('/')[0] for n in zipfile.ZipFile(w[0]).namelist()}))"
  ```
  Ожидание: `['build\\debt059_step1\\radial_blackoil-1.0.3+gpn.1-py3-none-any.whl']` и `['radial_blackoil', 'radial_blackoil-1.0.3+gpn.1.dist-info']`.
- `git -C <W> status --porcelain` — только два файла шага. Сборка оставляет `HydroSolverPrototype/Prototype_1.0.3/build/` и `radial_blackoil.egg-info/`; их игнорирует git (`build/`, `*.egg-info/`).
- Регресс: быстрый. GPN от прототипа ещё не зависит, ожидается то же, что в шаге 0.
- Регресс прототипа: только тесты (выше); регрессия — в шаге 6. Изменён литерал, который ни одна функция не читает: `grep __version__` по прототипу — только `__init__.py`.

**Подводные камни:** П4 (литерал версии), «Прототип».

**Зависимости:** требует шаг 0; блокирует шаги 2, 5.

**Оценка:** ~40 строк, ~10 мин.

---

### Шаг 2: зависимость GPN от прототипа, `pythonpath` для pytest, тесты установки

**Цель:** GPN объявляет `radial-blackoil==1.0.3+gpn.1`; pytest берёт прототип из своего дерева по `pythonpath`, вставка из `conftest.py` уходит; тесты сторожат согласованность версии и зависимостей.

**Файлы:**
- `numerical_solver/pyproject.toml`
- `numerical_solver/tests/conftest.py`
- `numerical_solver/tests/test_packaging.py` (новый)
- комментарии: `numerical_solver/tests/test_energy_balance_examples.py`, `numerical_solver/tests/test_examples.py`, `numerical_solver/tests/baseline_vectorization_check.py`

**Контекст:** общий venv один на основной каталог и все worktree. Установленный прототип будет указывать на основной каталог, а тесты worktree обязаны проверять код worktree. `pythonpath` в `[tool.pytest.ini_options]` вставляет путь относительно каталога `pyproject.toml` (rootdir), в начало `sys.path`, до загрузки `conftest.py`. Так прототип берётся из того же дерева, откуда запущен pytest, — ровно то, что сейчас делает `conftest.py`, только декларативно. `XlsxWriter` переезжает из `dev` GPN в обязательные зависимости прототипа: он нужен `run_workbook`, а ставить его теперь будет зависимость `radial-blackoil`.

**Что сделать:**
1. `numerical_solver/pyproject.toml`, строки 10-22.
   До:
   ```toml
   dependencies = [
       "numpy>=1.24",
       "scipy>=1.10",
       "matplotlib>=3.7",
   ]

   [project.optional-dependencies]
   dev = [
       "pytest>=7.0",
       # Вывод results.xlsx в HydroSolverPrototype (run_prototype.py и его тесты);
       # пакет gpn_multiphase_solver его не импортирует.
       "XlsxWriter>=3.2",
   ]
   ```
   После:
   ```toml
   dependencies = [
       "numpy>=1.24",
       "scipy>=1.10",
       "matplotlib>=3.7",
       # Прототип гидродинамики (HydroSolverPrototype/Prototype_1.0.3) — отдельный
       # дистрибутив в этом же репозитории (DEBT-059). Ровно эта версия: с нашими
       # правками прототипа совместима только она (тест test_packaging.py). Метка
       # «+gpn.1» — локальная; PyPI таких версий не принимает, поэтому чужой
       # пакет с тем же именем зависимость не удовлетворит. Ставить вместе:
       #   pip install -e HydroSolverPrototype/Prototype_1.0.3 -e ".[dev]"
       "radial-blackoil==1.0.3+gpn.1",
   ]

   [project.optional-dependencies]
   dev = [
       "pytest>=7.0",
   ]
   ```
2. Там же, строки 28-29.
   До:
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   ```
   После:
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   # Прототип — из этого же дерева, а не установленный: venv общий для основного
   # каталога и worktree, установленный radial_blackoil указывает на основной
   # каталог, а тесты worktree обязаны проверять свой код (DEBT-059). Путь — от
   # каталога этого файла. Установку проверяет приёмка в чистом окружении
   # (vault/issues/debt-059/probes/clean_env_acceptance.py).
   pythonpath = ["HydroSolverPrototype/Prototype_1.0.3"]
   ```
3. `numerical_solver/tests/conftest.py`, строки 1-15.
   До:
   ```python
   """Общие fixtures для тестов gpn_multiphase_solver."""

   import os
   import sys
   from pathlib import Path

   import pytest
   import numpy as np

   # radial_blackoil (прототип коллеги) — не установлен в venv,
   # подключается через sys.path. Factory использует ленивые imports.
   _PROTO_ROOT = Path(__file__).parent.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
   if str(_PROTO_ROOT) not in sys.path:
       sys.path.insert(0, str(_PROTO_ROOT))

   ```
   После:
   ```python
   """Общие fixtures для тестов gpn_multiphase_solver."""

   import os

   import pytest
   import numpy as np

   # radial_blackoil (прототип гидродинамики) pytest берёт из этого же дерева:
   # pythonpath в [tool.pytest.ini_options] numerical_solver/pyproject.toml (DEBT-059).

   ```
   `sys` и `Path` в `conftest.py` больше нигде не используются (проверено grep). Неиспользуемый `import numpy as np` был и раньше — не трогать.
4. Создать `numerical_solver/tests/test_packaging.py`:
   ```python
   """Установка пакетов: зависимости, версия прототипа, код своего дерева в тестах (DEBT-059)."""

   import ast
   import importlib
   import re
   import sys
   from pathlib import Path

   import pytest

   SOLVER = Path(__file__).resolve().parents[1]                 # numerical_solver/
   PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"  # дистрибутив radial-blackoil

   # Модуль импорта → дистрибутив (имя по PEP 503). Новый сторонний импорт
   # в пакете — добавить сюда и в dependencies его pyproject.toml.
   DIST_OF_MODULE = {
       "numpy": "numpy",
       "scipy": "scipy",
       "matplotlib": "matplotlib",
       "xlsxwriter": "xlsxwriter",
       "radial_blackoil": "radial-blackoil",
   }


   def _pyproject(path: Path) -> dict:
       """pyproject.toml как словарь; tomllib — с Python 3.11, на 3.10 тест пропускается."""
       tomllib = pytest.importorskip("tomllib")
       with open(path, "rb") as f:
           return tomllib.load(f)


   def _req_name(req: str) -> str:
       """Имя дистрибутива из строки требования по PEP 503: строчные, разделители — «-»."""
       name = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", req).group(1)
       return re.sub(r"[-_.]+", "-", name).lower()


   def _imported_top_modules(package_dir: Path) -> set:
       """Верхние имена абсолютных импортов во всех модулях пакета, включая импорты внутри функций."""
       names = set()
       for path in package_dir.rglob("*.py"):
           for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
               if isinstance(node, ast.Import):
                   names.update(a.name.split(".")[0] for a in node.names)
               elif isinstance(node, ast.ImportFrom) and node.level == 0:
                   names.add(node.module.split(".")[0])
       return names


   def _static_version(init_py: Path) -> str:
       """__version__ из литерала в __init__.py — так, как его читает setuptools (без импорта)."""
       for node in ast.parse(init_py.read_text(encoding="utf-8")).body:
           if (isinstance(node, ast.Assign) and len(node.targets) == 1
                   and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == "__version__"):
               # Не литерал — setuptools стал бы импортировать пакет, а в
               # изолированной сборке numpy нет (DEBT-059, П4 плана)
               assert isinstance(node.value, ast.Constant), "__version__ — не литерал"
               return node.value.value
       raise AssertionError(f"нет __version__ в {init_py}")


   class TestDistributions:
       """pyproject.toml обоих дистрибутивов согласованы с кодом."""

       def test_gpn_pins_prototype_version(self):
           """GPN требует ровно ту версию radial-blackoil, что в radial_blackoil.__version__."""
           # Сменили версию прототипа в одном месте и забыли во втором — pip
           # откажется ставить пару (или поставит не ту, если границу ослабить).
           version = _static_version(PROTO / "radial_blackoil" / "__init__.py")
           deps = _pyproject(SOLVER / "pyproject.toml")["project"]["dependencies"]
           pins = [d for d in deps if _req_name(d) == "radial-blackoil"]
           assert pins == [f"radial-blackoil=={version}"]

       def test_prototype_version_is_dynamic_from_literal(self):
           """Версия дистрибутива прототипа — из radial_blackoil.__version__: один источник номера."""
           proj = _pyproject(PROTO / "pyproject.toml")
           assert proj["project"]["dynamic"] == ["version"]
           assert proj["tool"]["setuptools"]["dynamic"]["version"] == {
               "attr": "radial_blackoil.__version__"}

       def test_prototype_installs_only_its_package(self):
           """В дистрибутив прототипа попадает только radial_blackoil (рядом tests/ — тоже пакет)."""
           # Без include в site-packages лёг бы пакет верхнего уровня tests
           proj = _pyproject(PROTO / "pyproject.toml")
           assert proj["tool"]["setuptools"]["packages"]["find"]["include"] == ["radial_blackoil*"]

       @pytest.mark.parametrize("package_dir, pyproject", [
           (SOLVER / "gpn_multiphase_solver", SOLVER / "pyproject.toml"),
           (PROTO / "radial_blackoil", PROTO / "pyproject.toml"),
       ], ids=["gpn-multiphase-solver", "radial-blackoil"])
       def test_declared_dependencies_cover_imports(self, package_dir, pyproject):
           """Каждый сторонний импорт пакета (и внутри функций) объявлен в его dependencies."""
           # Необъявленный импорт в репозитории незаметен (в общем venv всё
           # стоит), а в чистом окружении после установки — ModuleNotFoundError
           third_party = (_imported_top_modules(package_dir)
                          - set(sys.stdlib_module_names) - {package_dir.name})
           unknown = third_party - DIST_OF_MODULE.keys()
           assert not unknown, (f"новый сторонний импорт {sorted(unknown)}: "
                                "добавить в DIST_OF_MODULE и в dependencies")
           declared = {_req_name(d) for d in _pyproject(pyproject)["project"]["dependencies"]}
           missing = {DIST_OF_MODULE[m] for m in third_party} - declared
           assert not missing, f"не объявлены в {pyproject}: {sorted(missing)}"


   class TestTestsUseThisTree:
       """pytest проверяет код своего дерева, а не установленный в общий venv."""

       @pytest.mark.parametrize("module, home", [
           ("gpn_multiphase_solver", SOLVER / "gpn_multiphase_solver"),
           ("radial_blackoil", PROTO / "radial_blackoil"),
       ])
       def test_package_imported_from_this_tree(self, module, home):
           """Пакет импортирован из того же дерева, что и тесты (в worktree — из worktree)."""
           # gpn_multiphase_solver — из каталога запуска (python -m pytest из
           # numerical_solver), radial_blackoil — по pythonpath в pyproject.toml.
           # Падение в worktree значит: тесты проверяют код основного каталога.
           mod = importlib.import_module(module)
           assert Path(mod.__file__).resolve().parent == home.resolve()
   ```
5. Комментарии тестов, которые ссылаются на подключение прототипа в `conftest.py` (grep `conftest` по `numerical_solver/tests/*.py`):
   - `tests/test_energy_balance_examples.py:23-25`.
     До:
     ```python
     # Прототип radial_blackoil подключает tests/conftest.py. Здесь нужен только
     # путь до самого скрипта примеров — в conftest его не тащим, это код
     # примеров, а не пакета.
     ```
     После:
     ```python
     # Прототип radial_blackoil pytest берёт по pythonpath в pyproject.toml (DEBT-059).
     # Здесь нужен только путь до самого скрипта примеров — в pyproject.toml его
     # не тащим, это код примеров, а не пакета.
     ```
   - `tests/test_examples.py:2867-2868`: «Модуль импортирует пакет, прототип (путь — conftest), numpy» → «Модуль импортирует пакет, прототип (путь — pythonpath в pyproject.toml), numpy».
   - `tests/baseline_vectorization_check.py:4-5`: «Запуск через pytest, потому что conftest настраивает путь к внешнему прототипу radial_blackoil (нужен табличному PVT примеров 07-11).» → «Запуск через pytest, потому что pytest подключает прототип radial_blackoil (pythonpath в pyproject.toml, DEBT-059; нужен табличному PVT примеров 07-11).» Строку 7 («чтобы не править общий conftest») не трогать — она о другом.

**Проверка после этого шага:**
- `cd <W>\numerical_solver; <PY> -m pytest tests/test_packaging.py -q` — 7 passed.
- Контрольная проверка, что прототип теперь даёт именно `pythonpath`: `cd <W>\numerical_solver; <PY> -m pytest tests/test_packaging.py -q -o pythonpath=` → ровно 1 failed (`test_package_imported_from_this_tree[radial_blackoil-...]`, `ModuleNotFoundError`: в общем venv прототипа нет), остальные passed.
- `--collect-only -q`: базовое число + 7.
- Регресс: быстрый — все зелёные. Полный — в шаге 6 (см. чеклист, «Тесты»).

**Подводные камни:** П1 (не ставить в общий venv), П4, «Тесты», «Связь с другими задачами» (VAL-004 — соседние строки `[tool.pytest.ini_options]`).

**Зависимости:** требует шаг 1 (`pyproject.toml` прототипа читают тесты); блокирует шаг 3.

**Оценка:** ~150 строк (из них ~130 — новый тест), ~25 мин.

---

### Шаг 3: примеры без вставки пути к прототипу, сторож вставок

**Цель:** ни один файл `examples/` не вставляет путь к прототипу; тест сторожит это для пакета, примеров и тестов.

**Файлы** (все — `numerical_solver/examples/...`):
`example_runner.py`, `convergence.py`, `energy_balance.py`, `energy_balance_convergence.py`, `mass_balance.py`, `two_phase_analytics.py`, `temperature_asymptotics.py`, `verify_balance_vs_solver.py`, `check_energy_balance_all.py`, `01_single_phase_no_jt/spatial_convergence.py`, `02_single_phase_jt/check_slopes.py`, `05_standing_table_rp/closed_form_convergence.py`, `18_prototype_input/prototype_input.py`, `04_table_table/grid_convergence.py`, `04a_high_gas_saturation/grid_convergence.py`; и `numerical_solver/tests/test_packaging.py`.

**Контекст:** после шага 2 тесты берут прототип по `pythonpath`. Вставки в примерах нужны только для запуска скриптов. В основном каталоге их заменит установка (раздел «После влития»), в worktree — `PYTHONPATH` по правилу 3 `/implement`, который уже задаёт оба пути. Вставки `numerical_solver/` и `examples/` (`_ROOT`, `_EXAMPLES`, `SOLVER_ROOT`, `HERE`) остаются: это плоские импорты общих модулей, предмет DEBT-011 и FEAT-030.

**Что сделать:**
1. `example_runner.py`, строки 30-47. Блок от `# ── Подключение прототипа radial_blackoil ──` по `sys.path.insert(0, str(_PROTO_ROOT))` включительно заменить на:
   ```python
   # ── Прототип radial_blackoil ─────────────────────────────────
   # Установленный дистрибутив radial-blackoil, зависимость пакета (DEBT-059):
   # pip install -e HydroSolverPrototype/Prototype_1.0.3 -e ".[dev]" из
   # numerical_solver (examples/README.md, «Запуск»). Путь сюда не добавляется.

   ```
   Уходят `_SOLVER_ROOT`, `_PROTO_ROOT`, проверка каталога с `RuntimeError`. `import sys` остаётся: он нужен в строках 26-28.
2. Пять общих модулей с циклом — `convergence.py:33-36`, `energy_balance.py:54-57`, `energy_balance_convergence.py:52-55`, `mass_balance.py:44-47`, `two_phase_analytics.py:97-100`.
   До (во всех пяти одинаково):
   ```python
   for _p in (str(_ROOT), str(_EXAMPLES),
              str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
       if _p not in sys.path:
           sys.path.insert(0, _p)
   ```
   После:
   ```python
   # Прототип radial_blackoil — установленный дистрибутив (DEBT-059), путь к нему не добавляется
   for _p in (str(_ROOT), str(_EXAMPLES)):
       if _p not in sys.path:
           sys.path.insert(0, _p)
   ```
   Порядок оставшихся путей прежний: `_EXAMPLES` перед `_ROOT`.
3. `temperature_asymptotics.py:104-108` (внутри `if __name__ == "__main__":`).
   До:
   ```python
       # radial_blackoil (прототип гидродинамики) не установлен в venv —
       # подключается через sys.path, как в tests/conftest.py
       _PROTO = _HERE.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
       if str(_PROTO) not in sys.path:
           sys.path.insert(0, str(_PROTO))
   ```
   После:
   ```python
       # radial_blackoil (прототип гидродинамики) — установленный дистрибутив (DEBT-059)
   ```
4. `verify_balance_vs_solver.py:30-37`.
   До:
   ```python
   # Прототип radial_blackoil подключается conftest-ом только под pytest,
   # автономному скрипту приходится делать это самому.
   for _p in (str(_ROOT), str(_EXAMPLES), str(_EXAMPLES / "03_standing_corey")):
       if _p not in sys.path:
           sys.path.insert(0, _p)
   _PROTO = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
   if _PROTO.exists() and str(_PROTO) not in sys.path:
       sys.path.insert(0, str(_PROTO))
   ```
   После:
   ```python
   # Прототип radial_blackoil — установленный дистрибутив (DEBT-059), путь к нему не добавляется
   for _p in (str(_ROOT), str(_EXAMPLES), str(_EXAMPLES / "03_standing_corey")):
       if _p not in sys.path:
           sys.path.insert(0, _p)
   ```
5. Четыре скрипта — удалить одну строку `sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))`: `check_energy_balance_all.py:32`, `01_single_phase_no_jt/spatial_convergence.py:27`, `02_single_phase_jt/check_slopes.py:40`, `05_standing_table_rp/closed_form_convergence.py:38`. Остальные вставки в этих файлах не трогать.
6. `18_prototype_input/prototype_input.py`: удалить `import sys` (строка 12 — других обращений к `sys` в файле нет, grep). Строки 17-23.
   До:
   ```python
   HERE = Path(__file__).resolve().parent
   # examples/18_prototype_input/ → numerical_solver/
   PROTO_ROOT = HERE.parents[1] / "HydroSolverPrototype" / "Prototype_1.0.3"
   # radial_blackoil не установлен в venv. main.py получает путь от example_runner,
   # тесты — от tests/conftest.py; при запуске конвертации напрямую добавляем сами.
   if str(PROTO_ROOT) not in sys.path:
       sys.path.insert(0, str(PROTO_ROOT))
   ```
   После:
   ```python
   HERE = Path(__file__).resolve().parent
   # Каталог прототипа в репозитории — ради данных: книга INPUT_TEMPLATE.xlsx и
   # книги регрессии (BOOK, IMEX_BOOK, IMEX_DIR ниже). Пакет radial_blackoil —
   # установленный дистрибутив radial-blackoil (DEBT-059).
   # examples/18_prototype_input/ → numerical_solver/
   PROTO_ROOT = HERE.parents[1] / "HydroSolverPrototype" / "Prototype_1.0.3"
   ```
7. `04_table_table/grid_convergence.py:53` и `04a_high_gas_saturation/grid_convergence.py:50` (П3).
   До:
   ```python
   from example_runner import _PROTO_ROOT  # noqa: E402,F401  (подключает прототип)
   ```
   После:
   ```python
   import example_runner  # noqa: E402,F401  (консоль в UTF-8: скрипт печатает м³ст/с)
   ```
8. В `tests/test_packaging.py` дописать в конец:
   ```python
   def _is_path_insert(call: ast.Call) -> bool:
       """Вызов sys.path.insert / sys.path.append или monkeypatch.syspath_prepend."""
       f = call.func
       if not isinstance(f, ast.Attribute):
           return False
       if f.attr == "syspath_prepend":
           return True
       return (f.attr in ("insert", "append") and isinstance(f.value, ast.Attribute)
               and f.value.attr == "path" and isinstance(f.value.value, ast.Name)
               and f.value.value.id == "sys")


   def _path_insertions(tree: ast.AST) -> list:
       """Текст каждой вставки в sys.path; для вставки в цикле — вместе с тем, по чему идёт цикл."""
       # Вставка в цикле — sys.path.insert(0, _p): путь виден только в for ... in (...)
       loop_iter = {}
       for loop in ast.walk(tree):
           if isinstance(loop, ast.For):
               for node in ast.walk(loop):
                   loop_iter[id(node)] = loop_iter.get(id(node), "") + " | " + ast.unparse(loop.iter)
       return [ast.unparse(n) + loop_iter.get(id(n), "")
               for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_path_insert(n)]


   class TestNoPrototypePathInsertion:
       def test_code_does_not_insert_prototype_path(self):
           """Ни пакет, ни примеры, ни тесты не вставляют путь к прототипу в sys.path (DEBT-059)."""
           # Вставка маскирует забытую установку: в репозитории работает, у
           # пользователя установленного пакета — ModuleNotFoundError
           found, hits = 0, []
           for base in ("gpn_multiphase_solver", "examples", "tests"):
               for path in sorted((SOLVER / base).rglob("*.py")):
                   for text in _path_insertions(ast.parse(path.read_text(encoding="utf-8"))):
                       found += 1
                       # «proto» ловит и литерал HydroSolverPrototype, и имена _PROTO, PROTO_ROOT
                       if "proto" in text.lower():
                           hits.append(f"{path.relative_to(SOLVER)}: {text}")
           # На c0ec060 вставок 81, после шага 3 — 72 (5 циклов остаются вставками
           # без пути к прототипу, 9 прямых уходят); ноль значит: разбор сломан
           assert found > 10, "сторож не нашёл ни одной вставки в sys.path"
           assert hits == []
   ```

**Проверка после этого шага:**
- `cd <W>\numerical_solver; <PY> -m pytest tests/test_packaging.py tests/test_example_scripts.py -q` — всё passed (`test_packaging.py` — 8). `test_example_scripts.py` (DEBT-046) проверяет, что имена, которые импортируют скрипты `examples/`, существуют: забытый `from example_runner import _PROTO_ROOT` упадёт здесь.
- Регресс: быстрый — все зелёные; `--collect-only` — базовое + 8.
- Примеры в worktree по правилу 3 `/implement` (оба пути в `<W>`):
  ```powershell
  cd <W>\numerical_solver; $env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"; <PY> -c "import gpn_multiphase_solver as g, radial_blackoil as r; print(g.__file__, r.__file__)"; <PY> examples\03_standing_corey\main.py; <PY> examples\18_prototype_input\main.py
  ```
  Ожидание: оба пути в `<W>`. Пример 03 завершается без ошибок. Пример 18 печатает сверку с прототипом и IMEX в допусках, как раньше: он использует `PROTO_ROOT` для книг и `run_workbook` прототипа.
- Отрицательная проверка — примеры теперь опираются на установку:
  ```powershell
  cd <W>\numerical_solver; $env:PYTHONPATH = $null; <PY> examples\03_standing_corey\main.py
  ```
  Ожидание: `ModuleNotFoundError: No module named 'radial_blackoil'` — в общем venv прототипа нет (П1). Так и должно быть до установки после влития.

**Подводные камни:** П3 (не удалять импорт `example_runner` в 04/04a), «Обратная совместимость API».

**Зависимости:** требует шаг 2; блокирует шаги 4, 5.

**Оценка:** ~60 строк правок + ~45 строк теста, ~30 мин.

---

### Шаг 4: документы, команды `.claude/`, vault

**Цель:** описание установки и механизма подключения прототипа соответствует коду.

**Файлы:**
- `numerical_solver/examples/README.md`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/README.md`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`
- `.claude/commands/implement.md`, `audit-plan.md`, `plan-feature.md`, `plan-fix.md`, `plan-improve.md`, `plan-validate.md`, `run.md`
- `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md`

**Что сделать:**
1. `examples/README.md`, раздел «Запуск» (строки 225-239).
   - Строку `.venv\Scripts\pip install -e .        # один раз` заменить на:
     ```powershell
     # один раз: прототип гидродинамики и решатель, оба с правкой исходников
     .venv\Scripts\python -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"
     ```
   - Абзац «`PYTHONPATH` задавать не нужно: `example_runner.py` сам подключает прототип `radial_blackoil` через `sys.path`.» заменить на:
     ```markdown
     Прототип гидродинамики `radial_blackoil` — отдельный дистрибутив `radial-blackoil`
     (каталог `HydroSolverPrototype/Prototype_1.0.3`), зависимость решателя (DEBT-059).
     Ставить оба одной командой, как выше: решатель требует ровно версию `1.0.3+gpn.1`,
     и `pip install -e .` без прототипа завершится ошибкой «No matching distribution
     found for radial-blackoil». `PYTHONPATH` задавать не нужно.
     ```
2. `README.md` прототипа — новый раздел перед `## Documentation` (строка 81). Внешняя ограда — четыре обратные кавычки: внутри раздела свой блок `powershell`.
   ````markdown
   ## Installation as a package (GPN project)

   Since DEBT-059 of the GPN project the package `radial_blackoil` is an installable distribution `radial-blackoil` (`pyproject.toml` in this directory), version `1.0.3+gpn.1`: Prototype 1.0.3 with the local changes listed in `CHANGELOG_1.0.3.md`. The GPN solver (`numerical_solver/pyproject.toml`) requires exactly this version. Install both from `numerical_solver`:

   ```powershell
   python -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"
   ```

   Only the package is installed. The Excel workflow above (`run_prototype.py`, `run.bat`), `tests/` and `regression/` are run from this directory as before and do not need the installation. `VERSION.txt`, `BUILD.txt`, `radial_blackoil/build_info.py` and the `prototype_version` / `build_id` fields of `run_summary` still name the 1.0.3 release: the regression compares them with the golden outputs. `PACKAGE_MANIFEST_SHA256.txt` lists the files of the 2026-08-25 delivery and does not match the current code.
   ````
3. `CHANGELOG_1.0.3.md` — раздел в конец (числа — фактические из шагов 5, 6):
   ```markdown
   ## Local changes — GPN project (DEBT-059): installable distribution radial-blackoil 1.0.3+gpn.1
   - Problem: the package `radial_blackoil` could not be installed (no `pyproject.toml`); the GPN solver found it only through `sys.path` insertions in its tests and examples and did not work outside the repository.
   - New `pyproject.toml`: distribution `radial-blackoil` with the package `radial_blackoil` only (explicit `include`; `tests/`, `regression/`, `docs/` stay in the repository), dependencies numpy, scipy, matplotlib, XlsxWriter with the lower bounds of the GPN solver. `requirements.txt` (the validated 1.0.3 environment) is unchanged.
   - Distribution version `1.0.3+gpn.1` = `radial_blackoil.__version__`, a literal that setuptools reads without importing the package. `build_info.VERSION`, `BUILD_ID` and the `run_summary` fields are unchanged: the regression compares them with the golden outputs. The GPN solver requires `radial-blackoil==1.0.3+gpn.1`.
   - No numerical code changed: prototype tests <N> passed, quick regression 11/11 PASS; the GPN examples 03, 04, 05 reproduce their histories bitwise in a clean environment installed from wheels without PyPI.
   - `PACKAGE_MANIFEST_SHA256.txt` is kept as the record of the 2026-08-25 delivery and is not updated.
   - Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/94; plan: `vault/plans/debt-059 installable-prototype-package.md` of the GPN project.
   ```
4. Команды `.claude/commands/`:
   - Строка «⚠️ Для `numerical_solver` тестам нужен прототип `radial_blackoil` — его подключает `tests/conftest.py` через `sys.path`. Скрипты вне pytest должны делать это сами.» — `audit-plan.md:30`, `plan-feature.md:26`, `plan-fix.md:26`, `plan-improve.md:26`, `plan-validate.md:26` — заменить на:
     «⚠️ Для `numerical_solver` тестам нужен прототип `radial_blackoil` — pytest берёт его из того же дерева (`pythonpath` в `[tool.pytest.ini_options]` `numerical_solver/pyproject.toml`, DEBT-059). Скрипты вне pytest берут установленный дистрибутив `radial-blackoil` (`pip install -e HydroSolverPrototype/Prototype_1.0.3 -e ".[dev]"`); в worktree — `PYTHONPATH` на worktree (правило 3 `/implement`).»
   - `implement.md:49` — та же замена, хвост «(правило 3 ниже)» сохранить.
   - `implement.md:63`, правило 3: «без подготовки берут пакет `gpn_multiphase_solver` **основного** каталога: он установлен в venv в редактируемом режиме» → «без подготовки берут пакеты `gpn_multiphase_solver` и `radial_blackoil` **основного** каталога: оба установлены в общий venv в редактируемом режиме (прототип — с DEBT-059)». Команду не менять: она уже задаёт оба пути.
   - Попутно — устаревшее число тестов прототипа (см. «Обнаруженные проблемы»): «тесты прототипа, 80 шт., ~45 с» → «тесты прототипа, 97 шт. на 2026-10-10, ~45 с» (`implement.md:53`, `audit-plan.md:34`, `plan-feature.md:30`, `plan-fix.md:30`, `plan-improve.md:30`); «80 passed» → «все passed (97 на 2026-10-10)» (`implement.md:170`, `audit-plan.md:306`, `plan-feature.md:298`, `plan-fix.md:225`, `plan-improve.md:284`).
   - `run.md`: удалить строку 22 `$env:PYTHONPATH = "$PWD\HydroSolverPrototype\Prototype_1.0.3"`; строку 34 заменить на «`radial_blackoil` — установленный дистрибутив `radial-blackoil` (DEBT-059). `ModuleNotFoundError: radial_blackoil` — не выполнена установка: `.venv\Scripts\python -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"` из `numerical_solver`.»
   - Перед правкой — grep по каждому файлу: номера строк могли сдвинуться; искать по тексту.
5. Заметка `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md`, строки 155-160. Абзац «⚠️ Модуль с `__main__` **обязан сам добавить прототип в `sys.path`** …» заменить на:
   ```markdown
   ⚠️ До DEBT-059 (2026-10) модуль с `__main__` обязан был сам добавить прототип
   в `sys.path`: `radial_blackoil` не устанавливался. Теперь прототип — установленный
   дистрибутив `radial-blackoil`, путь к нему не добавляет никто (это сторожит
   `tests/test_packaging.py`); автономно запускаемые модули добавляют только
   `examples/` и `numerical_solver/` — для плоских импортов общих модулей.
   ```

**Проверка после шага:** `--collect-only -q` — число как после шага 3 (документы). `git -C <W> diff --stat` — только перечисленные файлы. Регресс прототипа: не нужен — в прототипе меняются только `README.md` и `CHANGELOG_1.0.3.md`.

**Зависимости:** требует шаг 3.

**Оценка:** ~60 строк, ~25 мин.

---

### Шаг 5: приёмка в чистом окружении

**Цель:** доказать, что оба дистрибутива ставятся без репозитория в `sys.path` и без PyPI и что расчёт побитово прежний.

**Файлы:** — (пробы `vault/issues/debt-059/probes/clean_env_acceptance.py`, `history_fingerprint.py` уже в `<W>`).

**Контекст:** проба собирает колёса из дерева `<W>` и скачивает зависимости в каталог колёс в версиях общего venv: `pip freeze` идёт в ограничения, иначе другая numpy могла бы сдвинуть отпечаток. Дальше проба создаёт два временных окружения в `<W>\numerical_solver\build\debt059_acceptance\`: «колёса» (`--no-index --find-links`) и «правка исходников» (`-e`). Проверки запускаются через `python -I`: каталог запуска и `PYTHONPATH` в `sys.path` не попадают, поэтому видно только установленное. Проба проверена при планировании на макете дерева (`acceptance_dry_run.out.txt`, 9 × «ОК»).

**Что сделать:**
1. Приёмка:
   ```powershell
   cd <W>\numerical_solver; <PY> -X utf8 <W>\vault\issues\debt-059\probes\clean_env_acceptance.py --baseline <W>\vault\issues\debt-059\probes\fingerprint_before.out.txt *> <W>\vault\issues\debt-059\probes\clean_env_acceptance.out.txt; Get-Content <W>\vault\issues\debt-059\probes\clean_env_acceptance.out.txt -Encoding UTF8
   ```
   Ожидание: 9 строк «ОК», последняя — «ПРИЁМКА: ПРОЙДЕНА». Первая строка — `Проверяемое дерево: <W>\numerical_solver`.
2. Отпечаток после правки в worktree (тот же способ, что в шаге 0):
   ```powershell
   cd <W>\numerical_solver; $env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"; <PY> -X utf8 <W>\vault\issues\debt-059\probes\history_fingerprint.py --examples examples --out <W>\vault\issues\debt-059\probes\fingerprint_after.out.txt
   Compare-Object (Get-Content <W>\vault\issues\debt-059\probes\fingerprint_before.out.txt) (Get-Content <W>\vault\issues\debt-059\probes\fingerprint_after.out.txt)
   ```
   Ожидание: пустой вывод.
3. Общий venv не изменился (П1):
   ```powershell
   <PY> -m pip freeze > <W>\numerical_solver\build\debt059_venv_after.txt
   Compare-Object (Get-Content <W>\numerical_solver\build\debt059_venv_before.txt) (Get-Content <W>\numerical_solver\build\debt059_venv_after.txt)
   ```
   Ожидание: пустой вывод.
4. Выходы `clean_env_acceptance.out.txt`, `fingerprint_before.out.txt`, `fingerprint_after.out.txt` — текстовые, закоммитить на ветке (`vault:`), иначе `git worktree remove` откажет (правило 4 `/implement`).

**При «ОШИБКА»:**
- «колесо прототипа содержит только пакет» — проверить `include` в `pyproject.toml` прототипа.
- «pip check» / установка — прочитать вывод `pip`: чаще всего зависимость не скачалась в каталог колёс.
- «отпечаток» — сначала сверить в stderr пробы версии numpy в обоих окружениях. Совпадают — СТОП: кода расчёта задача не меняет, расхождения быть не может, разобрать.
- «run_workbook» — `XlsxWriter`/`matplotlib` не в зависимостях прототипа.

**Зависимости:** требует шаги 1-3.

**Оценка:** 0 строк, ~10 мин (сборка, скачивание, два окружения).

---

### Шаг 6: итоговая проверка и vault

**Цель:** всё зелёное, регрессия прототипа побитово, основной каталог и общий venv не тронуты; vault отражает итог и шаг «После влития».

**Что сделать:**
1. Полный прогон GPN: `cd <W>\numerical_solver; <PY> -m pytest tests/ -q` — все passed; число = базовое + 8.
2. Прототип: `cd <W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3; <PY> -m pytest tests -q` — 97 passed; `<PY> regression\run_regression.py --quick` — 11/11 PASS. Перед регрессией зафиксировать HEAD worktree (`git -C <W> rev-parse --short HEAD`). Выходы `OUTPUT/REGRESSION_<время>/` удалить после разбора.
3. Основной каталог: `git -C <КОРЕНЬ> status --porcelain -- numerical_solver/` — как в начале (`/implement`, правило 2).
4. Числа в CHANGELOG (шаг 4, п. 3) — фактические.
5. Vault (на ветке задачи):
   - запись DEBT-059 в реестре — статус, итог, строка «После влития: …» (раздел ниже);
   - `vault/issues/debt-059/05-comment-done.md` — итог и **раздел «После влития» дословно**;
   - статус плана — «реализован».
6. Отчёт пользователю: отдельной строкой — нужна однократная установка в общий venv после влития.

**Проверка:** пункты 1-3 зелёные.

**Оценка:** ~15 мин + ~10 мин полного прогона + ~8 мин регрессии.

## После влития (основной каталог, однократно)

Сразу после `/merge` — сессией, выполнившей мерж, или пользователем. Без этого в основном каталоге не запускаются примеры и `run.md` (П2). Тесты работают и без установки.

```powershell
cd <КОРЕНЬ>\numerical_solver
<PY> -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"
<PY> -m pip check                                                   # No broken requirements found.
<PY> -c "import radial_blackoil as r; print(r.__file__, r.__version__)"   # <КОРЕНЬ>\...\Prototype_1.0.3\radial_blackoil\__init__.py 1.0.3+gpn.1
<PY> examples\03_standing_corey\main.py                             # без PYTHONPATH — работает
<PY> -X utf8 <КОРЕНЬ>\vault\issues\debt-059\probes\history_fingerprint.py --examples examples --out <КОРЕНЬ>\numerical_solver\build\debt059_main.out.txt
Compare-Object (Get-Content <КОРЕНЬ>\vault\issues\debt-059\probes\fingerprint_after.out.txt) (Get-Content <КОРЕНЬ>\numerical_solver\build\debt059_main.out.txt)   # пусто
```

Установка именно из `<КОРЕНЬ>`, не из worktree: worktree удаляется при `/merge` (П1). Параллельные worktree других задач продолжают работать. Их pytest берёт прототип своего дерева: до влития базы — через `conftest.py`, после — через `pythonpath`. Их скрипты с `PYTHONPATH` по правилу 3 тоже берут своё дерево: `PYTHONPATH` стоит в `sys.path` раньше finder-а установки.

Заметку памяти `reference_worktree_pythonpath` после установки обновить: прототип теперь тоже установлен в общий venv из основного каталога.

## Тестовая стратегия

**Неизменность поведения:**
- Все существующие тесты GPN зелёные после каждого шага (быстрый уровень) и в шаге 6 (полный). Затронутый код покрывают: `tests/test_examples.py` (фикстура `results` импортирует `example_runner` в том же процессе, `prototype_18` вызывает `run_workbook`), `tests/test_example_scripts.py` (имена импортов 45 скриптов `examples/`, DEBT-046), `tests/test_mass_balance.py`, `tests/test_energy_balance_examples.py`, `tests/test_rs_analytics.py` (импортируют общие модули `examples/`), `tests/test_prototype_cell_tolerance.py`, `tests/test_prototype_well_branch.py` (импортируют `radial_blackoil` на уровне модуля — проверяют `pythonpath`).
- Тесты прототипа 97 passed (шаги 0, 1, 6), регрессия `--quick` 11/11 PASS (шаги 0, 6).
- Отпечаток истории примеров 03, 04, 05 (SHA-256 по всем массивам истории): до = после в worktree (шаг 5, п. 2) = в чистом окружении из колёс (шаг 5, п. 1).

**Новые тесты** — `numerical_solver/tests/test_packaging.py`:

| Тест | Шаг | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `TestDistributions::test_gpn_pins_prototype_version` | 2 | требование `radial-blackoil` в `numerical_solver/pyproject.toml` против литерала `__version__` прототипа | ровно одно требование, `radial-blackoil==1.0.3+gpn.1` | смена версии прототипа в одном месте из двух |
| `TestDistributions::test_prototype_version_is_dynamic_from_literal` | 2 | `[project].dynamic` и `[tool.setuptools.dynamic]` прототипа | `["version"]`, `{"attr": "radial_blackoil.__version__"}` | второй источник номера версии |
| `TestDistributions::test_prototype_installs_only_its_package` | 2 | `packages.find.include` прототипа | `["radial_blackoil*"]` | пакет `tests` прототипа в `site-packages` |
| `TestDistributions::test_declared_dependencies_cover_imports[gpn-multiphase-solver]`, `[radial-blackoil]` | 2 | все абсолютные импорты пакета (AST, включая импорты в функциях) минус стандартная библиотека | каждый сторонний модуль объявлен в `dependencies` своего `pyproject.toml` | необъявленная зависимость: в общем venv незаметна, в чистом окружении — `ModuleNotFoundError` |
| `TestTestsUseThisTree::test_package_imported_from_this_tree[gpn_multiphase_solver-…]`, `[radial_blackoil-…]` | 2 | `__file__` импортированного пакета | каталог пакета в том же дереве, что тесты | тесты worktree проверяют код основного каталога (общий venv) |
| `TestNoPrototypePathInsertion::test_code_does_not_insert_prototype_path` | 3 | все вызовы `sys.path.insert/append`, `syspath_prepend` в `gpn_multiphase_solver/`, `examples/`, `tests/` (с итерируемым циклом) | ни одного с «proto»; всего вставок > 10 | возврат вставки, маскирующей забытую установку |

Итого +8 тестов. Время — доли секунды: разбор AST ~150 файлов.

**Приёмка установки** (вне pytest — нужна сеть и временные окружения): `clean_env_acceptance.py`, шаг 5.

## Критерии завершения

- [ ] Шаги 0-6 выполнены.
- [ ] Тесты GPN: полный прогон зелёный, число = базовое + 8.
- [ ] Тесты прототипа 97 passed; регрессия `--quick` 11/11 PASS.
  Полная регрессия с T05 (без `--quick`, ~45 мин) не выполняется, хотя запись реестра называла «17/17». Кода расчёта задача не меняет: изменён литерал `__version__`, который ни одна функция не читает, а сверяемые регрессией `build_info.VERSION`, `BUILD_ID` прежние (чеклист, «Прототип»). Если пользователь потребует — запустить в шаге 6 вместо `--quick`.
- [ ] `clean_env_acceptance.py`: «ПРИЁМКА: ПРОЙДЕНА» (9 × «ОК»).
- [ ] Отпечатки 03, 04, 05: до = после (worktree) = чистое окружение.
- [ ] Общий venv не изменился (`pip freeze` до = после); основной каталог не тронут.
- [ ] В `numerical_solver/` нет вставок пути к прототипу (тест-сторож).
- [ ] Документы: `examples/README.md`, README и CHANGELOG прототипа, 7 команд `.claude/`, заметка vault.
- [ ] Vault: реестр, `05-comment-done.md` с разделом «После влития», статус плана; issue #94 прокомментирован.
- [ ] После `/merge`: выполнен раздел «После влития».

## Затронутые файлы

| Файл | Шаг | Что |
|---|---|---|
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/pyproject.toml` | 1 | новый |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/__init__.py` | 1 | `__version__='1.0.3+gpn.1'` + комментарий |
| `numerical_solver/pyproject.toml` | 2 | `radial-blackoil==1.0.3+gpn.1`; `XlsxWriter` из `dev`; `pythonpath` |
| `numerical_solver/tests/conftest.py` | 2 | без вставки, без `sys`, `Path` |
| `numerical_solver/tests/test_packaging.py` | 2, 3 | новый, 8 тестов |
| `numerical_solver/tests/test_energy_balance_examples.py`, `test_examples.py`, `baseline_vectorization_check.py` | 2 | комментарии: прототип — по `pythonpath`, не `conftest` |
| `numerical_solver/examples/example_runner.py` | 3 | без блока подключения прототипа |
| `numerical_solver/examples/{convergence,energy_balance,energy_balance_convergence,mass_balance,two_phase_analytics}.py` | 3 | цикл без пути к прототипу |
| `numerical_solver/examples/temperature_asymptotics.py`, `verify_balance_vs_solver.py`, `check_energy_balance_all.py` | 3 | без вставки |
| `numerical_solver/examples/01_single_phase_no_jt/spatial_convergence.py`, `02_single_phase_jt/check_slopes.py`, `05_standing_table_rp/closed_form_convergence.py` | 3 | без вставки |
| `numerical_solver/examples/18_prototype_input/prototype_input.py` | 3 | без вставки и `import sys`; `PROTO_ROOT` — для данных |
| `numerical_solver/examples/04_table_table/grid_convergence.py`, `04a_high_gas_saturation/grid_convergence.py` | 3 | `import example_runner` вместо `_PROTO_ROOT` |
| `numerical_solver/examples/README.md` | 4 | «Запуск» |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/README.md`, `CHANGELOG_1.0.3.md` | 4 | раздел установки; запись DEBT-059 |
| `.claude/commands/{implement,audit-plan,plan-feature,plan-fix,plan-improve,plan-validate,run}.md` | 4 | механизм подключения; 80 → 97 |
| `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md` | 4 | абзац о `sys.path` |
| `vault/roadmap/известные баги и технический долг.md`, `vault/issues/debt-059/05-comment-done.md`, этот план | 6 | итог |

**Не меняются** (зона неприкосновенности): код расчёта пакета и прототипа, ленивые импорты `factory.py`, `prototype_adapter.py`; `build_info.py`, `VERSION.txt`, `BUILD.txt`, `requirements.txt`, `PACKAGE_MANIFEST_SHA256.txt`, `regression/golden/`, `run_prototype.py`, тесты прототипа; вставки `numerical_solver/` и `examples/` в `sys.path` (DEBT-011/FEAT-030); пути к данным прототипа в `tests/test_prototype_cell_tolerance.py:32-33`, `tests/test_prototype_well_branch.py:37-38`, `prototype_input.py:32-38`.

## Обнаруженные проблемы

1. **Число тестов прототипа в шапках команд `.claude/` устарело**: «80 шт.», «ожидается 80 passed», а на `c0ec060` их 97 (`pytest --collect-only` и `unittest discover`). Аудиторы и `/implement` сверяют базу с неверным ожиданием. Не блокирует; исправляется попутно в шаге 4, отдельной записи в реестре не нужно.
2. **Регрессия сверяет версию сборки в выходных файлах** (`run_regression.py:72`: `prototype_version`, `build_id`). Значит, любая будущая смена `build_info.VERSION` требует пересъёма 17 эталонных `run_summary.json`. Решением пользователя (версия только у дистрибутива) обойдено. Не задача — особенность, записанная в README прототипа (шаг 4).
3. **Когда менять `+gpn.N`.** Правила нет: метка описывает набор локальных правок, а прототип продолжат править (DEBT-048, BUG-024). Предложение — менять при каждой поставке заказчику, если код прототипа изменился с прошлой поставки. Решить в FEAT-031, не здесь.

## Связь с другими задачами

- **Блокирует:** DEBT-011 (#91), FEAT-030, FEAT-031 — поставку заказчику.
- **Пересекается по файлам:** DEBT-048 и BUG-024 (`CHANGELOG_1.0.3.md` — конфликт дописывания в конец при влитии после любой из них; у DEBT-048 ещё `tests/conftest.py` — разные строки), VAL-004 (возможна метка в `[tool.pytest.ini_options]`).
- **Обходы других задач не затрагиваются:** код расчёта и флаги прототипа (`phase_switching_stage`, `cell_tol`) не меняются.
