### Контекст при открытии

- **Ветка:** `refactor/debt-067/accept-at-cell-floor`
- **Коммит:** `3e8b797`
- **Мотивация:** решение, которое точнее не получить из-за округления (мера ячеек 0.23–0.40 предела $|J|\,\mathrm{ulp}(z)$), отвергается условием BUG-022, и шаг дробится, пока предел ($\propto \Delta t$) не опустится ниже порога: при $N$ = 350 и суточном шаге — 6 отказов у BUG-018, 3 у примера 14, 80 итераций ступени 4 впустую на суточном останове.
- **Затронутые модули:** `radial_blackoil/blackoil.py` (`_cells_converged`, `_newton_fixed_active_set`, `_newton_switching`), `CHANGELOG_1.0.3.md`, `doc/problem_statement.tex` (`eq:newton_cell_tol`), тесты `test_prototype_failure_diagnostics.py`, `test_prototype_phase_switching.py`, `test_prototype_cell_tolerance.py`; README примеров 14, 19–21 при сдвиге историй.
- **Рекомендуемый вариант:** (а) — поячеечный пол $\kappa\,(|J|\,\mathrm{ulp}(z))_i$, $\kappa \approx 1$; выбор между (а) и (в) — по замеру.
- **Оценка сложности:** средний (код — несколько строк; основная работа — перевод тестов отказа на другой сценарий и перемер историй).
