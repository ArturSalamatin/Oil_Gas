### Контекст при открытии

- **Ветка:** `refactor/debt-053/simulator-output-config-retry-terms`
- **Коммит:** `d0a8c05`
- **Мотивация:** docstring `Simulator` обещает действие параметра `output_config`, которого нет, а тесты называют дробление шага механизмом A-retry, удалённым в DEBT-015.
- **Затронутые модули:** `simulator.py`, `factory.py`; комментарии и сообщения `assert` в `test_energy_matrix_examples.py`, `test_rate_control.py`, `test_dt_convergence.py`; `examples/05_standing_table_rp/closed_form_convergence.py`; vault — `модули-simulator-оркестратор.md`
- **Оценка сложности:** простой. Открытый вопрос — замер: дробится ли шаг примера 07 на dt = 1200, 720, 450, 400 с после DEBT-015, BUG-016, BUG-020, BUG-021 (от него зависит текст `test_dt_convergence.py`)
