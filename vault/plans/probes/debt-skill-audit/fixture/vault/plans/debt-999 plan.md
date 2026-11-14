---
issue: DEBT-999
status: готов к аудиту
---

# План DEBT-999

В `src/config.py` выделить функцию `normalize_limit(data)`, возвращающую `data.get("limit", 5)`. Вызвать её из `read_limit` и `read_other_limit` вместо повторённого выражения.

Создать `tests/test_limits.py`, проверить обе функции для отсутствующего ключа, `0` и `None`. Ожидания: соответственно `5`, `0`, `None`. В корне `skill-work/fixture` выполнить `..\..\numerical_solver\.venv\Scripts\python.exe -m pytest tests/test_limits.py`.
