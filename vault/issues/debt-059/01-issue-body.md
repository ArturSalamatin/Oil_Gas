## Описание

Гидродинамику в `gpn_multiphase_solver` считает прототип `radial_blackoil` (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/`). У прототипа нет `pyproject.toml`, установить его нельзя, а в `dependencies` пакета GPN его нет. Ядро импортирует прототип лениво, и находится он только потому, что тесты и примеры вставляют путь к нему в `sys.path`. Вне репозитория не работает ничего: ни ядро, ни примеры, ни тесты.

Решение пользователя 2026-10-10: решатель гидродинамики и температуры вместе с примерами и тестами передаётся заказчику для внутреннего использования. Отдел разработки правит исходный код и продолжает разработку, инженеры и аналитики запускают расчёты. Код прототипа заказчик получает обязательно. Эта задача — первое звено поставки: DEBT-059 → DEBT-011 (#91) → FEAT-030 → FEAT-031.

## Текущее состояние

Воспроизведение (из корня репозитория, проверено на `c0ec060`):

```powershell
numerical_solver\.venv\Scripts\python -c "from gpn_multiphase_solver.io.config import load_config; from gpn_multiphase_solver.factory import SimulatorFactory; SimulatorFactory.from_config(load_config(r'numerical_solver\examples\03_standing_corey\config.json'))"
# File ".../gpn_multiphase_solver/factory.py", line 390, in _create_prototype_hydro
#     from radial_blackoil.grid import RadialGrid
# ModuleNotFoundError: No module named 'radial_blackoil'
```

Пакет GPN установлен в venv с правкой исходников (`direct_url.json`: `"editable": true`) — но только он: `include = ["gpn_multiphase_solver*"]`.

**Ленивые импорты прототипа в ядре** (8 мест): `factory.py:132` (PVT), `:348-349` (состояние, диагностика PVT), `:374` и `:488` (ОФП), `:390-392` (сетка, порода, модель); `hydro/prototype_adapter.py:60`, `:78` (состояние).

**Вставки пути к прототипу в `sys.path`** (14 мест + 2 импорта ради побочного действия):

| Где | Строки |
|---|---|
| `tests/conftest.py` | 10-14 |
| `examples/example_runner.py` (`_PROTO_ROOT`, проверка каталога, `RuntimeError`) | 30-46 |
| общие модули `examples/`: `convergence.py`, `energy_balance.py`, `energy_balance_convergence.py`, `mass_balance.py`, `two_phase_analytics.py`, `temperature_asymptotics.py`, `verify_balance_vs_solver.py`, `check_energy_balance_all.py` | 34-36, 55-57, 53-55, 45-47, 98-100, 105-108, 35-37, 32 |
| скрипты примеров: `01/spatial_convergence.py`, `02/check_slopes.py`, `05/closed_form_convergence.py`, `18/prototype_input.py` | 27, 40, 38, 19-23 |
| `04_table_table/grid_convergence.py`, `04a_high_gas_saturation/grid_convergence.py` — `from example_runner import _PROTO_ROOT  # (подключает прототип)` | 53, 50 |
| `examples/README.md` — описание механизма | 239 |

**Особенности прототипа, которые надо учесть:**

- **Самостоятельный продукт.** Свой вход через Excel (`run_prototype.py`, `run.bat`, `INPUT_TEMPLATE.xlsx`), свои тесты (`tests/`, unittest, 97 тестов — OK на `c0ec060`), регрессия по эталонам CMG IMEX (`regression/run_regression.py`, 17 случаев). Регрессия запускает `run_prototype.py` подпроцессом из корня прототипа (`run_regression.py:89-90`) — от установки не зависит.
- **Версия и манифест не описывают код.** `VERSION.txt` — «Prototype 1.0.3, Release status: final, 2026-08-25». Номер версии записан в трёх местах: `VERSION.txt`, `radial_blackoil/build_info.py` (`VERSION`, `BUILD_ID`), `radial_blackoil/__init__.py` (`__version__`). После 1.0.3 прототип менялся у нас (BUG-018, BUG-020, BUG-021, DEBT-030, DEBT-033, DEBT-036); контрольная сумма `radial_blackoil/blackoil.py` в `PACKAGE_MANIFEST_SHA256.txt:20` с файлом не совпадает. Каталог `Prototype_1.0.3/` назван по версии.
- **Зависимости не согласованы и фактически не соблюдаются.** `requirements.txt` прототипа фиксирует точные версии: `numpy==2.3.5`, `scipy==1.17.0`, `matplotlib==3.10.8`, `XlsxWriter==3.2.9`. В venv проекта стоят `numpy 2.5.2`, `scipy 1.18.1`, `matplotlib 3.11.1` — и на них зелёные и тесты, и регрессия. Пакет GPN задаёт нижние границы (`numpy>=1.24`, `scipy>=1.10`, `matplotlib>=3.7`), `XlsxWriter>=3.2` — в `dev` с комментарием «вывод results.xlsx в HydroSolverPrototype».
- **Что прототипу нужно на самом деле.** Сторонние импорты `radial_blackoil/*.py`: `numpy`, `scipy` — на уровне модулей; `xlsxwriter` и `matplotlib` — только внутри функций `output_artifacts.py:48`, `:138`, `:165` (вывод книги результатов и рисунков входа через Excel). Книги на входе читаются через `zipfile` без сторонних пакетов.
- **Импорты.** Внутри пакета — относительные (`from .state import ...`); тесты прототипа — по абсолютному имени (`tests/helpers.py`: `from radial_blackoil.grid import ...`).
- **Рядом с пакетом в корне прототипа** лежат `tests/` (с `__init__.py`), `regression/`, `docs/`, `INPUT/`, `OUTPUT/` — при сборке дистрибутива их надо явно исключить, иначе в `site-packages` попадёт пакет верхнего уровня `tests`.

## Целевое состояние

- Прототип и пакет GPN устанавливаются штатно; `SimulatorFactory.from_config` работает из любого каталога в окружении, где установлены оба пакета, без правки `sys.path`.
- В коде репозитория нет ни одной вставки пути к прототипу; тесты GPN и тесты прототипа проходят на установленных пакетах.
- У прототипа одна согласованная версия после наших правок, зависимости согласованы с пакетом GPN, судьба манифеста решена явно.
- Поведение расчётов не меняется: регрессия прототипа 17/17, истории примеров побитово совпадают с базовым вариантом.

## Затронутые файлы

| Файл | Строки | Роль |
|---|---|---|
| `numerical_solver/pyproject.toml` | 10-14, 16-22 | `dependencies` (+ `radial-blackoil`); `XlsxWriter` из `dev` — к прототипу |
| `HydroSolverPrototype/Prototype_1.0.3/pyproject.toml` | новый | дистрибутив `radial-blackoil` (вариант 1) |
| `HydroSolverPrototype/Prototype_1.0.3/requirements.txt` | 1-4 | точные версии → нижние границы или «проверенное окружение» |
| `HydroSolverPrototype/Prototype_1.0.3/VERSION.txt`, `radial_blackoil/build_info.py`, `radial_blackoil/__init__.py` | 1-5, 1-3, 1 | версия — три источника |
| `HydroSolverPrototype/Prototype_1.0.3/PACKAGE_MANIFEST_SHA256.txt` | весь | пересчитать / пометить исторической / удалить |
| `HydroSolverPrototype/Prototype_1.0.3/README.md`, `run.bat`, `run_tests.bat` | — | установка и запуск после изменений |
| `gpn_multiphase_solver/factory.py` | 132, 348-349, 374, 390-392, 488 | импорты прототипа — без изменений (вариант 1), переписываются (вариант 2) |
| `gpn_multiphase_solver/hydro/prototype_adapter.py` | 60, 78 | то же |
| `tests/conftest.py` | 10-14 | убрать вставку пути |
| `examples/example_runner.py` | 30-46 | убрать вставку и проверку каталога |
| 8 общих модулей `examples/`, 4 скрипта примеров, 2 скрипта сходимости 04/04a | см. таблицу выше | убрать вставки и импорт `_PROTO_ROOT` |
| `examples/README.md` | 239 | описание механизма подключения |

Путей к **данным** прототипа задача не касается — они остаются путями внутри репозитория: `tests/test_prototype_cell_tolerance.py:32-33`, `tests/test_prototype_well_branch.py:37-38` (`tests/fixtures/Nabor_1b.xlsx`), `examples/18_prototype_input/prototype_input.py:32`, `:37-38` (`INPUT_TEMPLATE.xlsx`, `regression/`). В `prototype_input.py` после удаления вставки `PROTO_ROOT` остаётся только для данных.

Вне задачи: вставки `numerical_solver/` и `examples/` в `sys.path` (плоские импорты модулей примеров) — DEBT-011 / FEAT-030; неотслеживаемый каталог `numerical_solver/deliverables/` (в git нет).

## Анализ вариантов решения

### Вариант 1. Два дистрибутива в одном репозитории — *рекомендован*

**Суть.** У прототипа свой `pyproject.toml` (дистрибутив `radial-blackoil`, пакет `radial_blackoil`), пакет GPN объявляет его в `dependencies`. Разработчики ставят оба с правкой исходников одной командой:

```powershell
pip install -e numerical_solver\HydroSolverPrototype\Prototype_1.0.3 -e "numerical_solver[dev]"
```

Инженерам — два файла `.whl`, установка без обращения к PyPI (`pip install --no-index --find-links <каталог> gpn-multiphase-solver`).

**Изменения.**
- `Prototype_1.0.3/pyproject.toml`: `[tool.setuptools.packages.find] include = ["radial_blackoil*"]`; версия — `dynamic = ["version"]` из `radial_blackoil.__version__` (один источник вместо трёх); зависимости `numpy`, `scipy` — обязательные; `XlsxWriter`, `matplotlib` — обязательные или необязательная группа для вывода через Excel (решить при планировании).
- `numerical_solver/pyproject.toml`: `"radial-blackoil>=<версия>"` в `dependencies`; `XlsxWriter` из `dev` уходит к прототипу.
- Удалить 14 вставок пути и 2 импорта `_PROTO_ROOT`; поправить `examples/README.md:239`, `README.md` прототипа, `run_tests.bat`.

**Плюсы.** Импорты ядра и тестов прототипа не меняются. Сохраняются граница авторства, своя версия, свои тесты и регрессия прототипа; прототип можно обновить отдельно от GPN. Вход через Excel остаётся самостоятельным.

**Минусы и риски.**
- Два дистрибутива — две версии, которые надо держать согласованными (нижняя граница в `dependencies` GPN).
- **Подмена зависимости.** Имя `radial-blackoil` в `dependencies` без ссылки на источник: если прототип не установлен, `pip` пойдёт за ним в PyPI и поставит чужой пакет с тем же именем, если такой там есть или появится. Защита — порядок установки (оба пути в одной команде) и `--no-index` для дистрибутивов; прямая ссылка `radial-blackoil @ file:///...` в `pyproject.toml` требует абсолютного пути и поэтому не годится.
- `run_prototype.py` лежит вне пакета: после установки из `.whl` без репозитория вход через Excel недоступен. Нужна ли команда в пакете (`[project.scripts]`) — решить при планировании или в FEAT-030/031.

### Вариант 2. Прототип — подпакет `gpn_multiphase_solver`

**Суть.** Один дистрибутив: `radial_blackoil` переносится в `gpn_multiphase_solver/` (например, `gpn_multiphase_solver/prototype/`).

**Изменения.** Внутренние импорты прототипа относительные и переносятся без правки. Переписываются 8 импортов ядра (`factory.py`, `prototype_adapter.py`), импорты тестов прототипа (`tests/helpers.py` и др.), `run_prototype.py`; регрессия и тесты прототипа переезжают или перенастраиваются.

**Плюсы.** Одна установка, одна версия, нет риска подмены зависимости.

**Минусы.** Версия, регрессия и граница авторства прототипа смешиваются с ядром; правки прототипа нельзя передать автору отдельным пакетом; больше изменений в коде, сравнение с исходным `Prototype_1.0.3.zip` затруднено.

### Вариант 3. Оставить вставку в `sys.path`

Задачу не решает: вне репозитория пакет не работает. Отклонён.

## План решения

**Этап 0 — базовый вариант** (`c0ec060`): тестов GPN 1677 (`--collect-only`); тесты прототипа 97 — OK; регрессия прототипа 17/17; истории примеров — сохранить для побитового сравнения; `pip list` venv.

**Этап 1 — решения при планировании** (с пользователем):
1. Вариант передачи прототипа (1 или 2).
2. Номер версии прототипа после наших правок (`1.0.4`, `1.0.3.post1` или локальная метка `1.0.3+gpn.1`) и единый источник номера.
3. Манифест `PACKAGE_MANIFEST_SHA256.txt`: пересчитать, пометить описанием поставки 2026-08-25 или удалить. Исходные `Prototype_1.0.3.zip` и `CONTEXT_HANDOFF_1.0.3.md` — оставить как историю.
4. Переименовывать ли каталог `Prototype_1.0.3/` (имя перестанет совпадать с версией; переименование трогает все пути к данным прототипа).
5. `requirements.txt`: нижние границы, файл «проверенное окружение» или удалить.
6. `XlsxWriter`/`matplotlib` — обязательные или необязательная группа; нужна ли команда входа через Excel в пакете.
7. Прогонять ли тесты прототипа (unittest) в составе `pytest` GPN.

**Этап 2 — реализация** (для варианта 1):
1. `pyproject.toml` прототипа; согласованная версия; правка `requirements.txt`, `VERSION.txt`, манифеста.
2. `dependencies` пакета GPN; переустановка обоих пакетов в venv проекта с правкой исходников.
3. Удаление вставок пути: `tests/conftest.py` → общие модули `examples/` и `example_runner.py` → скрипты примеров. Тест-сторож: в коде `numerical_solver/` (без `HydroSolverPrototype/`) нет вставок пути к прототипу.
4. Документация: `examples/README.md`, `README.md` прототипа, `run_tests.bat`.

**Этап 3 — верификация:**
- новое виртуальное окружение вне репозитория, установка обоих пакетов из `.whl` → `SimulatorFactory.from_config` на конфиге примера 03 из постороннего каталога;
- то же с правкой исходников (`pip install -e`);
- полный прогон тестов GPN (число тестов — по базовому варианту плюс новые) и тесты прототипа — без вставок в `sys.path`;
- регрессия прототипа 17/17;
- истории примеров побитово совпадают с базовым вариантом.

## Ветка

`refactor/debt-059/installable-prototype-package`

## Связанные issues

- Блокирует: #91 (DEBT-011 — диагностика примеров в пакете), FEAT-030 (команда расчёта по конфигу), FEAT-031 (комплект поставки) — issue для них пока нет.
- Related: #91 — задача обнаружена при подготовке его issue.

## Связанные заметки в vault

- `vault/roadmap/известные баги и технический долг.md` — запись DEBT-059
- `vault/roadmap/планируемые фичи.md` — FEAT-030, FEAT-031
- `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`
