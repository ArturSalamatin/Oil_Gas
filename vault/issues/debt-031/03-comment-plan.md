### План готов

План: `vault/plans/debt-031 convergence-dead-code.md`. Ветка: `refactor/debt-031/convergence-dead-code`. Шагов: 5.

- **Решения пользователя:** вариант 1 — удалить `fit_order`, `pairwise_orders`, `plot_convergence`, `report_series` и импорты `numpy`, `matplotlib`, `figure_io`; docstring модуля переписать по факту (пользователи — `energy_balance_convergence` и `04a/grid_convergence`). Добавить тест импорта.
- **Тест:** `test_convergence_users_import` в `tests/test_examples.py` — `runpy.run_path` трёх файлов без блока `__main__`; пишется до удаления, зелёный на исходном коде, краснеет при порче `run_series` (проверка в шаге 2). 1344 → 1345 тестов.
- **Не меняется:** тело `run_series`, вывод примеров, прототип.
- **Обнаружено:** DEBT-046 — автономные скрипты `examples/` не импортирует ни один тест.
