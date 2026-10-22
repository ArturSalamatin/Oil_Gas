## Описание

Вся диагностика решателя — замкнутое решение стационара, аналитика $R_s(r)$, однофазная асимптотика температуры, сборка невязок балансов энергии и массы, графики ОФП — лежит в `numerical_solver/examples/`. Этот каталог в дистрибутив не входит: `pyproject.toml` собирает только `gpn_multiphase_solver*`. Пользователь установленного пакета не может проверить свой расчёт теми средствами, которыми проверяются все примеры.

Запись в реестре заведена 2026-09-08 при аудите плана FEAT-017. С тех пор картина изменилась; ниже — состояние на `a26706a` (2026-10-10).

## Текущее состояние

### Что уже в ядре

Три задачи перенесли часть диагностики в пакет по схеме «вычисление в ядре, оформление в примерах»:

| задача | что в ядре | что осталось в `examples/` |
|---|---|---|
| FEAT-017 (#25) | `io/output.py::plot_pvt_properties` | `pvt_plot.py` — оформитель, узлы таблиц, отчёт |
| DEBT-013 | `energy/balance.py` — накопление 6 членов на каждом подшаге | `energy_balance.py::compute_balance` — невязка и её нормировка на $\sum|\text{членов}|$ |
| DEBT-039 (#65) | `mass_balance.py` — интегралы потоков компонентов | `mass_balance.py::compute_mass_balance` — невязка $\Delta M_\alpha + \int G_\alpha[N]\,dt - \int G_\alpha[0]\,dt$ |

Следствие: пользователь пакета получает `history.balance` — сырые накопленные суммы, — но не определение невязки. А нормировка как раз нетривиальна: нормировка на $\max(|\Delta E|, |\sum|)$ ломается при взаимно гасящих вкладах (комментарий в `examples/energy_balance.py:102-107`). Порог $10^{-12}$ (DEBT-043) тоже живёт в примерах.

### Что целиком вне пакета

| модуль | строк | вычислительное ядро | оформление |
|---|---|---|---|
| `closed_form.py` | 359 | `solve_closed`, `stationary_pwf`, `Closure` — замкнутое $p(r)$, $S_g(r)$ | наложения на графики, `report_closed` |
| `two_phase_analytics.py` | 415 | `compute_gor`, `predict_saturation`, `dupuit_check`, `degassing_front` | `report`, CLI |
| `rs_analytics.py` | 241 | `rs_expected`, `rs_error`, `rs_supersaturation`, `front_radius` | `_draw_rs`, `report_rs` |
| `temperature_asymptotics.py` | 125 | `single_phase_asymptote` | `report_asymptotics`, CLI |
| `relperm_plot.py` | 227 | — (кривые берутся у объекта ОФП) | график ОФП, рабочий диапазон $S_g$ |
| `convergence.py` | 68 | `run_series` — прогон серии по параметру | — |
| `energy_balance_convergence.py` | 215 | `run_convergence` — невязка на серии $\Delta t$ | график |

Итого по семи модулям — 1650 строк; с остатками балансов и `pvt_plot.py` — 2352. Восемь модулей исходной записи похудели с 2198 до 1881 строки: балансы частично ушли в ядро, BUG-012 убрал двухфазную асимптотику (`energy_balance.py` 409→231, `temperature_asymptotics.py` 335→125, `convergence.py` 188→68 по DEBT-031). Зато выросли `closed_form.py` (303→359) и `rs_analytics.py` (150→241), а в запись не вошли `mass_balance.py` (164, DEBT-039) и `pvt_plot.py` (307, FEAT-017).

### Приватный интерфейс

Диагностика получает объекты PVT и ОФП, которыми считалась задача, в обход публичного интерфейса — **24 обращения в 17 файлах**:

- `simulator._energy._pvt` — цепочка из двух приватных атрибутов (`temperature_asymptotics.py:41`, `closed_form.py:257` и др.);
- `factory._create_relperm(config)`, `factory._create_pvt(config)` — приватные функции фабрики.

У `Simulator` нет публичных `pvt` / `relperm`. Любой вариант решения упирается в это: переносить в пакет код, который ходит в приватные поля, бессмысленно, а включать его в дистрибутив как есть — значит отдать пользователю зависимость от внутренностей.

### Обнаружено при подготовке issue: ядро тоже не устанавливается

Исходная запись предполагает, что `pip install` даёт «только ядро». На деле не даёт и его. `factory.py` импортирует прототип `radial_blackoil` (`factory.py:132`, `:348-349`, `:374`, `:390-392`, `:478`; `hydro/prototype_adapter.py:60`, `:78`). Прототипа нет ни в `dependencies` (`pyproject.toml:10-14`), ни в дистрибутиве. Тесты и примеры работают, потому что вставляют `HydroSolverPrototype/Prototype_1.0.3` в `sys.path` (`tests/conftest.py:12-14`, `examples/example_runner.py`, заголовки общих модулей).

Воспроизведение (из корня репозитория, без вставок в `sys.path`):

```powershell
numerical_solver\.venv\Scripts\python -c "from gpn_multiphase_solver.io.config import load_config; from gpn_multiphase_solver.factory import SimulatorFactory; SimulatorFactory.from_config(load_config(r'numerical_solver\examples\03_standing_corey\config.json'))"
# ModuleNotFoundError: No module named 'radial_blackoil'   (factory.py:390)

numerical_solver\.venv\Scripts\python -c "import relperm_plot"
# ModuleNotFoundError: No module named 'relperm_plot'
```

Это отдельный дефект упаковки, к диагностике не относится, но он **предшествует** DEBT-011: пока ядро не запускается вне репозитория, вопрос «доступна ли пользователю пакета диагностика» не возникает. Предлагается зарегистрировать отдельной записью.

## Целевое состояние

- Вычислительное ядро проверок — функции от `(config, history, grid, pvt, relperm)`, без `matplotlib` и без записи файлов — в пакете, в `gpn_multiphase_solver/diagnostics/`.
- Невязки балансов энергии и массы (с нормировкой и порогом) вычисляются в ядре, рядом с накопителями.
- `Simulator` отдаёт PVT и ОФП публично; в `examples/` не остаётся ни одного обращения к `_energy._pvt` и `_create_*`.
- `examples/` содержит только оформление: графики, печать отчётов, CLI, `figure_io`, `example_runner`.
- Поведение примеров не меняется: отчёты и рисунки совпадают с базовым вариантом.

## Затронутые файлы

| файл | строки | роль |
|---|---|---|
| `numerical_solver/pyproject.toml` | 10-14, 24-26 | зависимости; `include = ["gpn_multiphase_solver*"]` (в записи реестра — 21-23, сдвинулись) |
| `numerical_solver/gpn_multiphase_solver/simulator.py` | — | нет публичного доступа к PVT / ОФП |
| `numerical_solver/gpn_multiphase_solver/factory.py` | 132, 348-349, 374, 390-392, 478 | импорт `radial_blackoil`; приватные `_create_relperm`, `_create_pvt` |
| `numerical_solver/gpn_multiphase_solver/energy/balance.py` | — | накопитель баланса энергии (DEBT-013) — сюда сборка невязки |
| `numerical_solver/gpn_multiphase_solver/mass_balance.py` | — | накопитель баланса массы (DEBT-039) — сюда сборка невязки |
| `numerical_solver/gpn_multiphase_solver/io/output.py` | — | `plot_pvt_properties` — образец для ядра графика ОФП |
| `numerical_solver/examples/closed_form.py` | 98-235, 253-259 | замкнутое решение; `_prepare` с приватным доступом |
| `numerical_solver/examples/two_phase_analytics.py` | 108-306 | аналитика стационара; импорт `closed_form._CACHE` (`:222`) |
| `numerical_solver/examples/rs_analytics.py` | 81-152 | аналитика $R_s$ |
| `numerical_solver/examples/temperature_asymptotics.py` | 35-64 | `_pvt_of` → `simulator._energy._pvt`; асимптотика |
| `numerical_solver/examples/energy_balance.py` | 71-113 | сборка невязки баланса энергии |
| `numerical_solver/examples/mass_balance.py` | 56-83 | сборка невязки баланса массы |
| `numerical_solver/examples/relperm_plot.py` | 79-227 | график ОФП, `_create_relperm` (`:90`, `:210`) |
| `numerical_solver/examples/pvt_plot.py` | 81-92 | `_create_pvt` (`:89`) |
| `numerical_solver/examples/convergence.py`, `energy_balance_convergence.py` | — | серии по параметру |
| `numerical_solver/examples/*/main.py`, `*/grid_convergence.py`, `05_*/closed_form_convergence.py` и др. | — | 10 скриптов примеров с приватным доступом |
| `numerical_solver/tests/test_energy_balance_examples.py`, `test_mass_balance.py`, `test_rs_analytics.py`, `test_examples.py` | — | импортируют модули `examples/` через `sys.path` |
| `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md` | — | каталога `examples/` и его статуса нет вовсе |

## Анализ вариантов решения

### Вариант 1. Расслоение по образцу FEAT-017 / DEBT-013 / DEBT-039

- **Суть.** Вычислительное ядро каждой проверки — в `gpn_multiphase_solver/diagnostics/`; оформление остаётся в `examples/` и вызывает ядро.
- **Изменения.** Новый подпакет (`closed_form`, `two_phase`, `rs`, `temperature`); сборка невязок — в `energy/balance.py` и `mass_balance.py`; ядро графика ОФП — в `io/output.py` рядом с `plot_pvt_properties`; публичные `Simulator.pvt`, `Simulator.relperm` (или публичная функция фабрики); перевод 17 файлов с приватного доступа; тесты — на ядро, а не на модули примеров.
- **Плюсы.** Три прецедента, схема проверена. Пользователь получает функции, а не скрипты. Пропадают плоские импорты и вставки в `sys.path` в общих модулях.
- **Минусы.** Самый большой объём. Затрагивает скрипты примеров, а их копии сверяются (DEBT-037, DEBT-046).

### Вариант 2. Включить `examples/` в дистрибутив

- **Суть.** `include` + `package-data`.
- **Плюсы.** Дёшево.
- **Минусы.** В пакет попадают `main.py`, конфиги, CSV, `output/`. Модули импортируются по плоскому имени (`from relperm_plot import ...`) и сами правят `sys.path`, вставляя туда путь к прототипу в репозитории — вне репозитория это не работает без переписывания. Приватный доступ к `_energy._pvt` уходит пользователю как интерфейс. По сути — перенос проблемы, а не решение.

### Вариант 3. Отдельный пакет `gpn-multiphase-diagnostics`

- **Суть.** Диагностика — отдельный дистрибутив, зависящий от ядра.
- **Плюсы.** Чистое разделение.
- **Минусы.** Две сущности, синхронизация версий. Без публичного доступа к PVT / ОФП не работает так же, как вариант 2, — то есть требует той же правки ядра, что и вариант 1, плюс инфраструктуру второго пакета.

### Вариант 4. Не делать до появления внешнего пользователя

- **Суть.** Зафиксировать `examples/` как часть репозитория, а не библиотеки, — в архитектурной заметке; задачу отложить.
- **Плюсы.** Ноль работы. Сейчас пакет никто не устанавливает: результаты для заказчика — рисунки примеров из репозитория.
- **Минусы.** Долг растёт: за месяц к диагностике добавился `mass_balance.py`, приватный доступ к PVT / ОФП расползся на 17 файлов.

### Рекомендация

Вариант 4 честен, если распространение пакета не планируется. Если планируется — комбинированный: сначала отдельная задача на упаковку прототипа (без неё любой вариант бесполезен), затем вариант 1 этапами от дешёвого к дорогому. Публичный доступ к PVT / ОФП полезен при любом варианте, кроме 4, и делается первым. Выбор варианта — за пользователем.

## План решения

Для варианта 1.

1. **Базовый вариант.** Полный прогон тестов; отчёты всех примеров (печать `run_example`) и истории — сохранить для сравнения.
2. **Публичный доступ к PVT и ОФП.** `Simulator.pvt`, `Simulator.relperm`; перевод всех 24 обращений; тест: в `examples/` нет `_energy._pvt` и `_create_` (разбором AST, как в DEBT-046).
3. **Невязки балансов в ядро.** Сборка невязки и нормировка — в `energy/balance.py` и `mass_balance.py`; `examples/energy_balance.py` и `examples/mass_balance.py` — только графики.
4. **Аналитика в `diagnostics/`.** `closed_form` → `two_phase` → `rs` → `temperature`, по одному модулю на шаг; после каждого — быстрый уровень тестов.
5. **Ядро графика ОФП** в `io/output.py` по образцу `plot_pvt_properties`.
6. **Верификация.** Все тесты зелёные; отчёты и истории примеров совпадают с п. 1; тест импорта `gpn_multiphase_solver.diagnostics` без `examples/` в `sys.path`; архитектурная заметка дополнена разделом о границе «пакет / примеры».

`convergence.py`, `energy_balance_convergence.py`, `figure_io.py`, `example_runner.py` остаются в `examples/`: это механика прогона примеров, а не проверка расчёта.

## Ветка

`refactor/debt-011/diagnostics-into-package`

## Связанные issues

Related: #25 (FEAT-017 — прецедент расслоения), #22 (FEAT-016 — свёл модули в `examples/`), #65 (DEBT-039 — накопитель баланса массы в ядре)

## Связанные заметки в vault

- `vault/roadmap/известные баги и технический долг.md` — запись DEBT-011
- `vault/plans/feat-017 pvt-plot-module.md` — §4.0 (расслоение), регистрация DEBT-011
- `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`
