"""DEBT-027, проба при /plan-improve: тесты шага 2 плана против эмуляции кода (emulate_debt027.install).

test_table_range_warnings.py здесь — копия кода тестов из плана (шаг 2, п. 9).
Запуск из numerical_solver/:
  .venv\\Scripts\\python -m pytest -c pyproject.toml ..\\vault\\issues\\debt-027\\probes\\emu_tests -q -p no:cacheprovider
Переменная окружения DEBT027_STEP1_ONLY=1 — подставлен только шаг 1 (прототип): какие тесты
шага 2 красные до его кода. FREE_GAS_SG адаптера тогда не существует — копия тестов его
импортирует, поэтому в этом режиме константа задаётся модулю адаптера здесь.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import emulate_debt027  # noqa: E402

if os.environ.get("DEBT027_STEP1_ONLY") == "1":
    emulate_debt027.install(prototype_only=True)
    import gpn_multiphase_solver.hydro.prototype_adapter as adapter_module
    adapter_module.FREE_GAS_SG = emulate_debt027.FREE_GAS_SG
else:
    emulate_debt027.install()
