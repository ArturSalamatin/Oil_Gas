"""DEBT-071, аудит 1: тесты GPN шага 2 плана на ИСХОДНОМ коде (без install) — какие красные.

Ожидание: 4 красных (проверка ОФП на пути Стендинга выключена / relperm_range_warnings
нет), зелёный — test_standing_corey_silent (страж от шума на Кори). Тест-тела берутся из
plan_tests_emulate.py, подмена install() отключена. Запуск из numerical_solver/:
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-071\\probes\\audit1_plan_tests_base.py -q -p no:cacheprovider
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import standing_relperm_scan  # noqa: E402

standing_relperm_scan.install = lambda: None   # исходный код: без подмены

from plan_tests_emulate import TestStandingRelperm  # noqa: E402,F401
