## Реализация завершена

**Ветка:** `feat/feat-040/workbook-example-no-install` (worktree `.worktrees/feat-040`, от `numerical_scheme/implementation` `1ac708d`)
**План:** `vault/plans/feat-040 workbook-example-without-install.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-040/workbook-example-no-install`

### Изменения
- `numerical_solver/examples/23_source_tree_run/`: книга `23_source_tree_run.xlsx` (шаблон), `main.py`, `README.md` – пример расчёта из папки с исходным кодом без установки пакетов. `main.py` вставляет в `sys.path` папку с исходным кодом и папку прототипа от своего расположения, считает пошаговыми вызовами функций (`convert_workbook` → `load_config` → `SimulatorFactory.from_config` → `simulator.run`) и по образцу `run_case` строит набор результатов, вызывая функции пакета по одной. Пример – иллюстрация: совпадение с `run_case` тестами не охраняется (решение пользователя); при создании все 17 файлов совпали с `run_case` побайтно.
- `gpn_multiphase_solver/report/` (`relperm.py`, `pvt.py`, `energy_balance.py`, `mass_balance.py`, `rs.py`): докстринги в стиле NumPy у `plot_relperm`, `plot_pvt`, `report_pvt`, `plot_energy_balance`, `plot_mass_balance`, `make_overlay_rs`, `report_rs`; код не менялся.
- `doc/source/api.rst`: раздел «Штатный набор: рисунки и проверки» – эти семь функций в публичном интерфейсе.
- `tests/test_examples.py`: пример 23 в списках примеров; класс `TestSourceTreeRun` – книга равна шаблону, состав папки, вставки путей, вызовы функций вместо команды, запуск копии дерева под `python -S` (пакеты решателя и прототипа не видны, `__file__` – из копии, 14 файлов вывода, числа README).
- `tests/test_energy_matrix_examples.py`: пример 23 в списках.
- `tests/test_packaging.py`: исключение `PROTO_PATH_ALLOWED` в стороже DEBT-059 и тест его актуальности.
- `README.md` пакета: ссылка на пример в «Начале работы» (новый шаг 2 случая «Папка с кодом без установки»), §2, §4; `examples/README.md` – обзор примера 23.
- `CHANGELOG.md`: пункт FEAT-040 в «Не выпущено», «Добавлено».
- `tools/release.py`: пример 23 вне архива примеров поставки для расчётов.

### Тесты
- Было: 2620 тестов (быстрый уровень 2335)
- Стало: 2650 тестов (+30: 7 докстрингов публичного интерфейса, 17 параметризаций примером 23, 5 тестов класса, 1 исключение сторожа); быстрый уровень 2356
- Полный прогон: 2649 passed, 1 skipped (11 мин 48 с) ✅
