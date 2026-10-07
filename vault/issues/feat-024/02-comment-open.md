### Контекст при открытии

- **Ветка:** `feat/feat-024/high-gor-cooling-example` (от `numerical_scheme/implementation`)
- **Коммит:** `4d2886d`
- **Фаза roadmap:** FEAT-024 — примеры и демонстрация; зависимость BUG-014 (#42) влита (`d18f734`)
- **Формулы:** новых нет — `problem_statement.tex`: `eq:energy_final`, `eq:muJT_def`, `eq:bc_p_ext`, `eq:bc_Sg_ext`, `eq:bc_flux_well`; тождество Дарси на забойной грани (README примера 12)
- **Модуль:** `numerical_solver/examples/14_high_gor_cooling/` (конфиг, CSV, `main.py`, README); списки в `tests/test_examples.py`, `tests/test_energy_matrix_examples.py`; `examples/README.md`. Библиотека не меняется
- **Ключевой замер:** 12 × 30 сут, суточный шаг без дробления, `sim.run` 11.9 с; $\Delta T(r_w) = -5.77$ К, $S_g(r_w) = 0.229$ на 360 сут
- **Оценка сложности:** простой (данные и README; открытый вопрос — дальняя двухфазная ячейка на 137.3 м)
