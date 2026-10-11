"""DEBT-063, проба: полный прогон тестов с центрами √(r_{j-1/2}·r_{j+1/2}) в LogRadialGrid.

Подключаемый модуль pytest: при старте подменяет функцию центров в модуле
gpn_multiphase_solver.grid.log_radial на среднее геометрическое граней (как
у прототипа, radial_blackoil/grid.py). Конструктор LogRadialGrid ищет функцию
по имени модуля при каждом вызове — подмена действует на все сетки прогона.
Код пакета не меняется.

Запуск из numerical_solver/:
    $env:PYTHONPATH = "..\\vault\\issues\\debt-063\\probes"
    .venv\\Scripts\\python -m pytest tests/ -q -p sqrt_centers_plugin
"""

import numpy as np


def _sqrt_centers(r_left, r_right):
    """Центры прототипа: среднее геометрическое граней."""
    return np.sqrt(r_left * r_right)


def pytest_configure(config):
    import gpn_multiphase_solver.grid.log_radial as lr
    name = next(n for n in ("_cell_centers_mass", "_cell_centers_log_average")
                if hasattr(lr, n))
    setattr(lr, name, _sqrt_centers)
    print(f"\n[DEBT-063] {lr.__file__}: {name} → √(r_left·r_right)")
