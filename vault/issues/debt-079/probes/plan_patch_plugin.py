"""Плагин pytest (-p plan_patch_plugin): правка шага 1 плана DEBT-079 в памяти до сбора тестов.

Запуск из numerical_solver/ (PowerShell):
    $env:PYTHONPATH = "..\\vault\\issues\\debt-079\\probes"
    .venv\\Scripts\\python -m pytest tests/ -m "not slow" -q -p plan_patch_plugin
Ожидание без правки тестов: падают test_project_relperm_tables_accepted (старый вызов
с тремя аргументами) и test_initial_below_table_not_repeated (таблица с k_rg[0] = 0.005).
"""
import plan_emulate

plan_emulate.patch_in_memory()
