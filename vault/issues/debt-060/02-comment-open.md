### Контекст при открытии

- **Ветка:** `refactor/debt-060/cell-center-name`
- **Коммит:** `b3ffaac`
- **Мотивация:** центр ячейки назван «центром масс кольца», а формула `eq:cell_center` даёт $\exp\langle\ln r\rangle$ (кольцо 1–2 м: 1.528 против 1.556) — проверяющий решит, что ошибочна формула, хотя ошибочно только название.
- **Затронутые модули:** `doc/problem_statement.tex`, `grid/log_radial.py` (докстринги, имя `_cell_centers_mass`), `tests/test_grid.py`, `tests/test_prototype_adapter.py`, `tests/test_val001.py` (комментарии, докстринги, имя класса), 5 заметок `vault/knowledge/decisions/`.
- **Оценка сложности:** простой (только тексты и два приватных имени; поведение не меняется).
