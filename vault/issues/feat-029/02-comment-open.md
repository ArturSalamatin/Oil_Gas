### Контекст при открытии

- **Ветка:** `feat/feat-029/shutin-strong-cooling-example`
- **Коммит:** `59e9eab` (`numerical_scheme/implementation`)
- **Фаза roadmap:** примеры и демонстрация; FEAT-029 зависит от BUG-020 (#63), а тот — от BUG-021 (#64)
- **Формулы:** новых нет; ГУ останова — `eq:bc_rate_well`, `eq:bc_rate_pwf` (`numerical_solver/doc/problem_statement.tex`)
- **Модуль:** `numerical_solver/examples/<NN_имя>/`, `examples/README.md`, `tests/test_examples.py`, `tests/test_energy_matrix_examples.py`
- **Оценка сложности:** средний. Решатель не правится. Основная работа — выбор конфига и длительностей, замеры восстановления $T$ и время расчёта в уровне `slow`.
