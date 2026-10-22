"""DEBT-028: pytest-плагин — подмена кода плана (planned_code.apply) до сбора тестов.

Запуск из каталога numerical_solver (PYTHONPATH — только для подключения плагина):
    $env:PYTHONPATH = "..\\vault\\issues\\debt-028\\probes"
    .venv\\Scripts\\python -m pytest tests/ -q -m "not slow" -p planned_plugin
"""
import planned_code

planned_code.apply()
