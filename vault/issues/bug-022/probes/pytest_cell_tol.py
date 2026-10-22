"""BUG-022: модуль pytest — прогон tests/ GPN на эмуляции плана (жёсткое условие по ячейке).

Подменяет Ньютоны прототипа копиями cell_tol.py (вариант pv<eps>, по умолчанию pv1e-8) и
включает условие только у моделей, созданных фабрикой GPN (_create_prototype_hydro):
модели, которые тесты строят напрямую, считают как прежде — как флаг cell_tol=None плана.
Запуск (из numerical_solver; PowerShell):
    $env:PYTHONPATH = "..\\vault\\issues\\bug-022\\probes"
    .venv\\Scripts\\python -m pytest tests/ -q -p pytest_cell_tol
Вариант — переменная окружения BUG022_VARIANT.
"""

import os


def pytest_configure(config):
    import cell_tol
    from gpn_multiphase_solver import factory

    cell_tol.install(os.environ.get("BUG022_VARIANT", "pv1e-8"))
    cell_tol.CELL["require_mark"] = True
    orig = factory._create_prototype_hydro

    def create(*a, **k):
        hydro = orig(*a, **k)
        hydro._model._probe_cell = True
        return hydro

    factory._create_prototype_hydro = create
    print(f"\nBUG-022 эмуляция: {cell_tol.CELL}")
