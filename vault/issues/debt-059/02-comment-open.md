### Контекст при открытии

- **Ветка:** `refactor/debt-059/installable-prototype-package`
- **Коммит:** `c0ec060`
- **Мотивация:** решатель с примерами и тестами передаётся заказчику (решение 2026-10-10), а без установки прототипа `radial_blackoil` пакет вне репозитория не работает — `factory.py:390` → `ModuleNotFoundError`.
- **Затронутые модули:** `numerical_solver/pyproject.toml`; `HydroSolverPrototype/Prototype_1.0.3/` (новый `pyproject.toml`, `requirements.txt`, версия в трёх местах, манифест); `tests/conftest.py`; `examples/example_runner.py`, 8 общих модулей `examples/`, 6 скриптов примеров; при варианте 2 — `factory.py`, `hydro/prototype_adapter.py`.
- **Базовый вариант:** тестов GPN 1677 (`--collect-only`), тесты прототипа 97 — OK.
- **Оценка сложности:** средний — кода расчёта задача не меняет, но требует решений о версии, манифесте и зависимостях прототипа и проверки в чистом окружении.
