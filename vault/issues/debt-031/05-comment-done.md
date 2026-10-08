## Реализация завершена

**Ветка:** `refactor/debt-031/convergence-dead-code` (worktree `.worktrees/debt-031`, от `numerical_scheme/implementation` `65a60ca`)
**План:** `vault/plans/debt-031 convergence-dead-code.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-031/convergence-dead-code` — `775712b` (тест), `2b851af` (удаление), `ba4d999` (комментарий и README)

### Изменения
- `numerical_solver/examples/convergence.py`: 198 → 68 строк. Удалены `fit_order`, `pairwise_orders`, `plot_convergence`, `report_series` и импорты `numpy`, `matplotlib`, `figure_io`. Тело `run_series` и настройка `sys.path` не менялись. Docstring: пользователи — `energy_balance_convergence` и `04a/grid_convergence`; 01/04/05 модуль не импортируют.
- `numerical_solver/examples/energy_balance_convergence.py`: комментарий над импортом `run_series` без ссылки на `fit_order`.
- `numerical_solver/examples/README.md`: строка таблицы общих модулей — «прогон серии по Δt или N с измерением метрики».
- `numerical_solver/tests/test_examples.py`: `TestSharedChecks::test_convergence_users_import` — импорт трёх файлов через `runpy` без блока `__main__` и проверка, что все глобальные имена тела `run_series` определены (`dis`, `LOAD_GLOBAL`). Краснеет при переименовании `run_series` (проверено порчей, откачено).

### Тесты
- Было: 1344 теста
- Стало: 1345 (+1 новый)
- Полный прогон: 1345 passed (387 с); быстрый уровень: 1109 passed
- Все зелёные: ✅

`git grep -E "fit_order|pairwise_orders|plot_convergence|report_series" -- numerical_solver` — пусто.
