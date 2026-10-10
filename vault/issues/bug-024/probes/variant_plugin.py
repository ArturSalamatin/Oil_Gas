"""BUG-024: pytest-плагин — подмена RadialBlackOilModel._newton_switching вариантом до сбора тестов.

Вариант — BUG024_VARIANT (stage4_variants.py: base, satrel, half, rel), параметр — BUG024_DR.
Запуск из каталога numerical_solver (PYTHONPATH — только для подключения плагина):
    $env:PYTHONPATH = "..\\vault\\issues\\bug-024\\probes"; $env:BUG024_VARIANT = "satrel"
    .venv\\Scripts\\python -m pytest tests/ -q -m "not slow" -p variant_plugin
"""
import os
import sys
from pathlib import Path

# Прототип подключает tests/conftest.py, но плагин грузится раньше conftest
sys.path.insert(0, str(Path.cwd() / "HydroSolverPrototype" / "Prototype_1.0.3"))
from radial_blackoil.blackoil import RadialBlackOilModel  # noqa: E402
import stage4_variants  # noqa: E402

_fn = stage4_variants.make(os.environ.get("BUG024_VARIANT", "satrel"))
_fn.__defaults__ = RadialBlackOilModel._newton_switching.__defaults__
RadialBlackOilModel._newton_switching = _fn
