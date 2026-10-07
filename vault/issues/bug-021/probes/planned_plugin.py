"""BUG-021: pytest-плагин — подмена _newton_fixed_active_set вариантом плана до сбора тестов.

Запуск из каталога numerical_solver (PYTHONPATH — только для подключения плагина):
    $env:PYTHONPATH = "..\\vault\\issues\\bug-021\\probes"; $env:BUG021_VARIANT = "2"
    .venv\\Scripts\\python -m pytest tests/ -q -m "not slow" -p planned_plugin
"""
import os
import sys
from pathlib import Path

# Прототип подключает tests/conftest.py, но плагин грузится раньше conftest
sys.path.insert(0, str(Path.cwd() / "HydroSolverPrototype" / "Prototype_1.0.3"))
import planned_code  # noqa: E402

planned_code.apply(int(os.environ.get("BUG021_VARIANT", "2")))
