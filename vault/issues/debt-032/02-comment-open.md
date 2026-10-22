### Контекст при открытии

- **Ветка:** `refactor/debt-032/test-tiers-fast-regression`
- **Коммит:** `132c9c8`
- **Мотивация:** полный прогон (10 мин) запускается ~11 раз на задачу — около 2 ч тестов; 93 % его времени — повторные расчёты 20 примеров в двух файлах.
- **Затронутые модули:** `numerical_solver/tests/conftest.py`, `tests/test_examples.py`, `tests/test_energy_matrix_examples.py`, `pyproject.toml`; `.claude/commands/` (`implement`, `audit-plan`, `plan-*`); `CLAUDE.md`
- **Оценка сложности:** простой (варианты 1–3); средний с вариантом 5.
