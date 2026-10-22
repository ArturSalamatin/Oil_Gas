"""Плагин pytest (-p audit1_plugin): шаг 1 плана DEBT-079 из текста плана — в память до сбора тестов.

Запуск из numerical_solver/ (PowerShell):
    $env:PYTHONPATH = "..\\vault\\issues\\debt-079\\probes"
    .venv\\Scripts\\python -m pytest -c pyproject.toml ..\\vault\\issues\\debt-079\\probes\\patched\\tests -q -p audit1_plugin
"""
import audit1_apply

audit1_apply.patch_in_memory()
