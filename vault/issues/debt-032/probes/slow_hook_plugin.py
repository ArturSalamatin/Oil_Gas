"""Хук шага 2 плана DEBT-032 в виде плагина: проверка, что -m видит его метки.

Запуск из numerical_solver/ (плагин подключается через -p, conftest не трогаем):
    $env:PYTHONPATH = "..\\vault\\issues\\debt-032\\probes"
    .venv\\Scripts\\python -m pytest tests/ -p slow_hook_plugin -m "not slow" --collect-only -q
Ожидание на HEAD 132c9c8 (без явной метки на test_matrix_matches_reference):
1121 - 206 (фикстура results) - 1 (KNOWN_SLOW) = 914 в быстром уровне.
Если вышло 1120 — фильтр -m отработал раньше хука, и метки из хука не действуют.
"""

import pytest

_HEAVY_FIXTURES = ("results",)


def pytest_collection_modifyitems(config, items):
    """Метка slow для тестов на тяжёлых фикстурах (DEBT-032)."""
    for item in items:
        if any(name in getattr(item, "fixturenames", ()) for name in _HEAVY_FIXTURES):
            item.add_marker(pytest.mark.slow)
