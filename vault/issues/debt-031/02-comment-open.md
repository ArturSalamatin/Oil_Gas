### Контекст при открытии

- **Ветка:** `refactor/debt-031/convergence-dead-code`
- **Коммит:** `cecc250`
- **Мотивация:** четыре функции `examples/convergence.py` (~106 строк) не имеют вызывающих с BUG-007/DEBT-022, но правятся при каждом изменении оформления рисунков (FEAT-026); docstring модуля называет пользователями 01/04/05, которые модуль не импортируют.
- **Затронутые модули:** `examples/convergence.py`, `examples/energy_balance_convergence.py` (комментарий 58–59), `examples/README.md` (737); при вариантах 2/3 — `04a/grid_convergence.py` или `05/closed_form_convergence.py`
- **Рекомендуемый вариант:** 1 (удалить четыре функции, переписать docstring)
- **Оценка сложности:** простой
