"""Проверить, что целевые тесты обнаруживают подмены DEBT-067 и BUG-024."""

import inspect
import sys
from pathlib import Path

import pytest

solver = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(solver / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(solver))

from radial_blackoil import blackoil


class Mutation:
    def __init__(self, mode):
        self.mode = mode
        self.original_kappa = blackoil.CELL_FLOOR_KAPPA
        self.original_newton = blackoil.RadialBlackOilModel._newton_switching
        self.calls = 0

    def pytest_runtest_setup(self, item):
        if self.mode == "floor":
            blackoil.CELL_FLOOR_KAPPA = 0.0
        else:
            original = self.original_newton
            signature = inspect.signature(original)

            def unlimited(*args, **kwargs):
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                bound.arguments["dr_rel"] = 1e30
                self.calls += 1
                return original(*bound.args, **bound.kwargs)

            blackoil.RadialBlackOilModel._newton_switching = unlimited

    def pytest_runtest_teardown(self, item, nextitem):
        blackoil.CELL_FLOOR_KAPPA = self.original_kappa
        blackoil.RadialBlackOilModel._newton_switching = self.original_newton


if __name__ == "__main__":
    mode = sys.argv[1]
    tests = {
        "floor": "tests/test_prototype_cell_floor.py::TestBug018Day::test_newton_accepted_at_limit",
        "shutin": "tests/test_prototype_phase_switching.py::TestDailyShutin::test_daily_shutin_passes_default_retries",
    }
    plugin = Mutation(mode)
    code = pytest.main([tests[mode], "-q", "-p", "no:cacheprovider", "--tb=short"], plugins=[plugin])
    print(f"Подмена: {mode}; код pytest: {code}; вызовы ступени 4: {plugin.calls}")
    if code != pytest.ExitCode.TESTS_FAILED or (mode == "shutin" and plugin.calls == 0):
        raise SystemExit(1)
