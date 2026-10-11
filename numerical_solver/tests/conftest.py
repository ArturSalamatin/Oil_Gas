"""Общие fixtures для тестов gpn_multiphase_solver."""

import os

import pytest
import numpy as np

# radial_blackoil (прототип гидродинамики) pytest берёт из этого же дерева:
# pythonpath в [tool.pytest.ini_options] numerical_solver/pyproject.toml (DEBT-059).

# FEAT-026: SVG- и EMF-копии рисунков нужны только при запуске примеров,
# не в тестах (решение пользователя 2026-10-02): конвертация Inkscape
# добавила бы секунды к каждому run_example и plot_pvt. С "0" save_figure
# пишет только PNG, а export_emf не находит SVG и ничего не делает.
os.environ["GPN_EXAMPLES_EMF"] = "0"


# ── Уровни прогона (DEBT-032) ──────────────────────────────────
# Быстрый уровень: pytest -m "not slow" (~70 с); полный: pytest (~10 мин).
# Тесты на фикстуре results (tests/test_examples.py) получают метку slow
# автоматически: фикстура считает примеры на штатных конфигах (до минуты
# на пример, 17 — около 22 с после DEBT-048; все 23 — ~2.5 мин, замер
# 2026-10-11), и тест на ней ждёт этого расчёта.
# Автоматически — чтобы новый тест на results не попал в быстрый уровень
# по забывчивости. prototype_18 (tests/test_examples.py) — расчёт прототипа
# на книге примера 18, ~12 с (VAL-005).
# При переименовании фикстур поправить имена здесь.
_HEAVY_FIXTURES = ("results", "prototype_18")


def pytest_collection_modifyitems(config, items):
    """Метка slow для тестов на тяжёлых фикстурах (DEBT-032)."""
    for item in items:
        # fixturenames есть у тестовых функций; getattr — на случай других
        # элементов сбора (doctest), у которых этого атрибута нет.
        if any(name in getattr(item, "fixturenames", ()) for name in _HEAVY_FIXTURES):
            item.add_marker(pytest.mark.slow)
