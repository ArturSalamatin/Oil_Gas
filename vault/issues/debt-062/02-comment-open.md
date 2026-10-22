### Контекст при открытии

- **Ветка:** `refactor/debt-062/label-number-guard`
- **Коммит:** `3e8b797`
- **Мотивация:** номер уравнения рядом с меткой уже уехал на 6 (74 → 80 по `problem_statement.aux` на `3e8b797`), а сторож DEBT-010 форму «метка (N)» пропускает — она появится снова.
- **Затронутые модули:** `numerical_solver/tests/test_energy_matrix_examples.py` (строки 254, 383, 799), `numerical_solver/tests/test_eq_references.py` (`FORBIDDEN`)
- **Оценка сложности:** простой
