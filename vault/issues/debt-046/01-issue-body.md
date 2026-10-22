## Описание

Скрипты в `numerical_solver/examples/`, которые запускаются только вручную, не исполняет ни один тест. Если имя удалить или переименовать в общем модуле `examples/` (`two_phase_analytics.py`, `figure_io.py`, `example_runner.py`, …) или в пакете `gpn_multiphase_solver`, скрипт ломается без сигнала. Поломка обнаружится при следующем ручном запуске — возможно, через недели и другим человеком.

Механизм уже встречался: DEBT-031 (#75) удалял мёртвый код из `convergence.py`. Для трёх пользователей `convergence.py` защиту добавил тест `test_convergence_users_import`, для остальных скриптов её нет.

Приоритет низкий, задача ничего не блокирует.

## Текущее состояние

Проверено на `c7b0ce6` (после влития DEBT-031).

1. **Тесты, исполняющие скрипты.** `grep` по `numerical_solver/tests/` на `run_path|import_module|spec_from_file_location|py_compile` находит только `test_examples.py:797`, `test_convergence_users_import` (DEBT-031). Он выполняет `runpy.run_path` для `convergence.py`, `energy_balance_convergence.py`, `04a_high_gas_saturation/grid_convergence.py` и проверяет `LOAD_GLOBAL` в теле `run_series`.
2. **`main.py` примеров тоже не исполняются.** Фикстура `results` (`test_examples.py:82-83`, `:131`) считает примеры через `load_config` и `SimulatorFactory.from_config` напрямую, а не через `main.py`. Сами `main.py` тесты читают только как текст и ищут в нём строки (`test_examples.py:1777`, `:1998`, `:2142`, `:2265`, `:2424`, `:2609`). Значит, не исполняется **ни один из 21 `main.py`**. В записи реестра `main.py` не упомянуты, то есть фактический охват задачи шире.

### Непокрытые скрипты

| Скрипт | `__main__` | Имена из общих модулей `examples/` и пакета |
|---|---|---|
| `01_single_phase_no_jt/main.py` | `:186` | `run_example`, `save_figure`, `export_emf`, `plot_profiles`; внутри функции (`:71-73`) `SimulatorFactory`; `sim._energy._pvt`, `sim._energy._rock` |
| `02_single_phase_jt/main.py` | `:290` | `run_example`, `figure_io`, `plot_profiles`, `ta.single_phase_asymptote`; внутри функции (`:115-117`) `SimulatorFactory`; `sim._energy._pvt`, `._rock` |
| `03_standing_corey/main.py` | `:79` | `run_example`, `tpa.SG_EPS`, `tpa.degassing_front`, `tpa.report`; внутри функций (`:57-58`, `:97`) `load_config`, `temperature_asymptotics as ta`, `SimulatorFactory` |
| `04_table_table/main.py` | `:23` | `run_example`, `tpa.report`; внутри функции (`:33`) `SimulatorFactory` |
| `05_standing_table_rp/main.py` | `:83` | `run_example`, `report_relperm`, `figure_io`, `plot_profiles`, `tpa.degassing_front`, `tpa.SG_EPS`, `tpa._build_relperm`, `tpa.report`, `ta.single_phase_asymptote`; внутри функции (`:94`) `SimulatorFactory` |
| `main.py` примеров 04a, 06–16, 19–21 (16 файлов) | есть | только `from example_runner import run_example` и вызов с именованными аргументами |
| `01_single_phase_no_jt/spatial_convergence.py` | **нет** | `figure_io`, `load_config`, `SimulatorFactory`, `S_TO_DAY`; `sim._grid`, `sim._energy._pvt`, `._rock`. На верхнем уровне (`:106-161`) — три прогона N = 50/200/800 и запись PNG/EMF в `output/` |
| `02_single_phase_jt/check_slopes.py` | `:228` | `load_config`, `SimulatorFactory`, `figure_io`; на верхнем уровне `warnings.filterwarnings("ignore")` (`:44`) |
| `04_table_table/grid_convergence.py` | `:113` | `example_runner._PROTO_ROOT`, `SimulatorFactory`, `_create_relperm`, `load_config`, `closed_form.solve_closed`, `rs_analytics.front_radius`, `two_phase_analytics.SG_EPS` |
| `05_standing_table_rp/closed_form_convergence.py` | `:157` | `SimulatorFactory`, `_create_relperm`, `load_config`, `figure_io`, `tpa.solve_closed` |
| `04a_high_gas_saturation/plot_profiles_50k.py` | `:86` | `figure_io` |
| `check_energy_balance_all.py` | `:85` | `load_config`, `SimulatorFactory`, `energy_balance.compute_balance` |
| `verify_balance_vs_solver.py` | `:185` | `SimulatorFactory`, `load_config`, `TridiagEnergySolver`, `eb.compute_balance` |
| `04a_high_gas_saturation/rewrite_history.py` | `:53` | только стандартная библиотека |
| `compare_script_copies.py` | **нет** | только стандартная библиотека; верхний уровень безвреден (копий нет — вывод пуст) |
| `run_all.py` | `:94` | только стандартная библиотека; `main.py` запускает подпроцессом |

### Классы поломок

От класса зависит, какой механизм проверки её поймает.

| Класс | Пример в коде | Импорт файла (`runpy`) | `dis`, `LOAD_GLOBAL` | Разбор AST |
|---|---|---|---|---|
| (а) `from M import name` на верхнем уровне | `from closed_form import solve_closed` | ✅ | — | ✅ |
| (б) `from M import name` внутри функции | `main.py` 01–05 | ❌ | ❌ | ✅ |
| (в) атрибут модуля `alias.name` | `tpa.report`, `ta.single_phase_asymptote` — 12 мест в `main.py` 02–05 и `closed_form_convergence.py` | ❌ | ❌ (видит `tpa`, не `.report`) | ✅ |
| (г) имя, нужное только в теле функции | `deepcopy` в `run_series` (DEBT-031) | ❌ | ✅ | ✅ |
| (д) атрибут объекта, именованный аргумент | `sim._energy._rock`, `run_example(title=…)` | ❌ | ❌ | ❌ (кроме сверки аргументов с `inspect.signature`) |

`sim._energy._rock` берут только непокрытые скрипты: `main.py` 01, 02, `spatial_convergence.py` и `check_slopes.py`. `_grid` и `_pvt` берёт и `example_runner.py`, который тесты покрывают.

## Целевое состояние

- Если удалить или переименовать имя в общем модуле `examples/` или в пакете, а скрипт `examples/` от этого имени зависит, быстрый уровень тестов падает. Сообщение называет скрипт и имя.
- Список скриптов строится по диску, как в DEBT-037 (`SHARED_EXAMPLE_FILES`, `test_examples.py:642`): новый скрипт попадает под проверку сам.
- Тест не запускает расчёты, не пишет в `output/` и не получает метку `slow`.

## Затронутые файлы

| Файл | Строки | Роль |
|---|---|---|
| `numerical_solver/tests/test_examples.py` | 797–837 | `test_convergence_users_import` (DEBT-031): обобщить или заменить |
| `numerical_solver/tests/test_examples.py` | 628–642 | `SHARED_EXAMPLE_FILES`: приём «список по диску» (DEBT-037) |
| `numerical_solver/examples/01_single_phase_no_jt/spatial_convergence.py` | 106–161 | расчёт на верхнем уровне без `__main__`; для варианта 1 нужна защита |
| `numerical_solver/examples/compare_script_copies.py` | 69–94 | нет `__main__`, верхний уровень безвреден |
| `numerical_solver/examples/*/main.py` | — | 21 файл; тестами не исполняются |
| остальные скрипты из таблицы выше | — | тестами не исполняются |

## Анализ вариантов решения

### Вариант 1. `runpy` по списку с диска и `LOAD_GLOBAL` по всем функциям (обобщение DEBT-031)

- **Суть.** Для каждого `.py` в `examples/` и `examples/*/` вызвать `runpy.run_path(..., run_name="__import_check__")`. Затем проверить `LOAD_GLOBAL` во всех функциях, определённых в этом файле (`__code__.co_filename`). Проверка должна обходить и вложенные code-объекты (лямбды, вложенные `def`): сам `dis.get_instructions` в них не заходит.
- **Ловит:** (а), (г). **Не ловит:** (б), (в), (д).
- **Требует.** `spatial_convergence.py` нужно защитить `if __name__ == "__main__"` (иначе импорт запустит три прогона и запишет файлы в `output/`) или исключить из списка. Код верхнего уровня даёт побочные эффекты: `sys.path.insert` (снимается через `monkeypatch`, как в DEBT-031), `matplotlib.use("Agg")`, `warnings.filterwarnings("ignore")` в `check_slopes.py`. Pytest восстанавливает фильтры предупреждений после каждого теста — при планировании это проверить.
- **Плюсы.** Мало кода, приём уже есть в проекте. Импорты исполняются по-настоящему, пути `sys.path` разрешаются так же, как при ручном запуске.
- **Минусы.** Пропускает (б) и (в), а именно они встречаются в `main.py` 01–05. Нужна правка скрипта примера.

### Вариант 2. Разбор AST без исполнения

- **Суть.** Разобрать каждый файл через `ast.parse`. Для каждого `ImportFrom` на любом уровне вложенности, если модуль из `examples/` или `gpn_multiphase_solver`, проверить `importlib` + `hasattr(module, name)`. Для `import M as alias`, где `M` из `examples/`, проверить каждое `Attribute(value=Name(alias))` через `hasattr(M, attr)`.
- **Ловит:** (а), (б), (в). **Не ловит:** (г), (д). Класс (г) — ошибка самого скрипта, а не общего модуля.
- **Плюсы.** Ничего не исполняет, `spatial_convergence.py` трогать не нужно. Ловит импорты внутри функций и атрибуты модулей.
- **Минусы.** Нужен свой разрешитель модулей: какой модуль из `examples/`, какой из пакета, какой сторонний (сторонние пропускать). Если локальная переменная затеняет алиас, будет ложное срабатывание (на текущем коде не проверено). В тесте прибавится примерно 40–60 строк.

### Вариант 3. Варианты 1 и 2 вместе

- **Ловит:** (а)–(г). (д) не ловит.
- **Минусы.** Два механизма в одном тесте. Для `spatial_convergence.py` то же условие, что в варианте 1, либо `runpy` только для скриптов с `__main__`, а остальные проверяются только через AST.

### Вариант 4. Линтер (ruff/pyflakes) по `examples/`

F821 и F401 работают в пределах одного файла и не разрешают имена в чужих модулях. Удалённое из общего модуля имя линтер не поймает, задачу этот вариант не решает.

### Вариант 5. Пробный прогон каждого скрипта на малой сетке

Ловит всё, включая (д). Но скрипты зашивают серии сеток и пути вывода, поэтому каждый пришлось бы параметризовать. Это секунды–минуты на скрипт и запись файлов — несоразмерно низкому приоритету.

### Вариант 6. Оставить ручной запуск

Так сейчас.

### Предварительная рекомендация

Вариант 3 или вариант 2: только они ловят классы (б) и (в), которые реально встречаются в `main.py` 01–05. Окончательный выбор — в `/plan-improve`.

### Открытые вопросы к плану

1. Включать ли 21 `main.py`. Реестр их не упоминает, но их не исполняет ни один тест. При списке по диску они попадут автоматически; чтобы исключить, нужен отдельный фильтр.
2. Заменить `test_convergence_users_import` обобщённым тестом или оставить оба.
3. `spatial_convergence.py`: добавить `if __name__ == "__main__"` (правка примера) или исключить его из части с `runpy`.
4. Сверять ли именованные аргументы вызовов `run_example(...)` с `inspect.signature(run_example)`. Это частично закрывает (д) для 16 тонких `main.py`.

## План решения

1. **Подготовка.** Записать число тестов (`--collect-only -q`) и убедиться, что быстрый уровень зелёный. Замерить время проверки всех скриптов (пока не замерено).
2. **Проба красного состояния.** Подменой (`monkeypatch.delattr` или временная копия модуля) убрать имя каждого класса (а)–(в) и убедиться, что тест падает и называет скрипт и имя.
3. **Реализация.** Тест в `test_examples.py` рядом с `test_no_duplicate_helper_scripts`, список по диску; при выбранном варианте — защита `__main__` в `spatial_convergence.py`.
4. **Проверка.** Быстрый уровень зелёный, новый тест без метки `slow`; полный прогон в конце. Выход примеров не меняется: код примеров не трогается, кроме возможной защиты `__main__`.

## Ветка

`refactor/debt-046/examples-scripts-import-check`

## Связанные issues

Related: #75 (DEBT-031 — тест импорта пользователей `convergence.py`), #66 (DEBT-037 — список файлов `examples/` по диску)

## Связанные заметки в vault

- `vault/roadmap/известные баги и технический долг.md` — DEBT-046
- `vault/plans/debt-031 convergence-dead-code.md` — шаг 2, `test_convergence_users_import`
- `vault/plans/debt-037 shared-modules-copy-guard.md` — список по диску
