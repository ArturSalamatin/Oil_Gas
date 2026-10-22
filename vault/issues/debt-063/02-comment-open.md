### Контекст при открытии

- **Ветка:** `refactor/debt-063/unify-grid-prototype-centers`
- **Коммит:** `0c8f059`
- **Мотивация:** решение прототипа на центрах $\sqrt{r_{j-1/2}r_{j+1/2}}$ выводится, сравнивается с аналитикой и сопрягается с энергией на центрах $\exp\langle\ln r\rangle$ другой сетки — систематическое расхождение $\approx h^2/6$ по $\ln r$ и $\approx h/3$ в граничных проводимостях; решение пользователя — вариант A (GPN на центры прототипа), поглощает DEBT-060 (#96).
- **Затронутые модули:** `grid/log_radial.py`, `factory.py`, `energy/tridiag.py` (меняются вместе с центрами), `io/output.py`, `doc/problem_statement.tex`; тесты `test_grid.py`, `test_val001.py`, `test_factory_standing_hydro.py`, `test_prototype_adapter.py`, `test_examples.py`; аналитика `examples/`; 5 заметок `vault/knowledge/decisions/`. Прототип не меняется.
- **Оценка сложности:** средний (формула простая; основная работа — замер влияния на истории примеров и числа README).
