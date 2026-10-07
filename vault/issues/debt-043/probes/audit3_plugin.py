"""Плагин pytest для аудита DEBT-043: подменяет TridiagEnergySolver.solve кодом шага 1 плана.

Запуск (из numerical_solver/):
    $env:PYTHONPATH = "D:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-043\\probes"
    .venv\\Scripts\\python -m pytest tests/ -m "not slow" -q -p audit3_plugin
"""


def pytest_configure(config):
    import audit3_planned_solve
    audit3_planned_solve.install()
    print("\n[audit3] TridiagEnergySolver.solve подменён кодом шага 1 плана DEBT-043")
