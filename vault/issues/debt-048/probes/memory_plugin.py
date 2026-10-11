"""DEBT-048: pytest-плагин — эмуляция памяти ступени 4 на моделях фабрики GPN (аудит плана).

Каждый адаптер, который создаёт фабрика (factory._create_prototype_hydro), получает память
варианта DEBT048_EMULATE (по умолчанию m2s) подменой advance на экземпляре модели —
stage_memory.install. Тесты, собирающие модель сами, не затрагиваются. Так настоящие
тесты примеров проверяют утверждение плана «тесты 16 и 17 проходят без правок» до
реализации.

Запуск (из numerical_solver, PowerShell):
    $env:PYTHONPATH = "..\\vault\\issues\\debt-048\\probes"
    .venv\\Scripts\\python -m pytest tests/test_examples.py -p memory_plugin -q -k "ShutInStrongCooling or WellShutIn"
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage_memory as sm  # noqa: E402  (ставит sys.path на numerical_solver и прототип)

from gpn_multiphase_solver import factory  # noqa: E402

VARIANT = os.environ.get("DEBT048_EMULATE", "m2s")
_orig = factory._create_prototype_hydro


def _create(*a, **k):
    hydro = _orig(*a, **k)
    sm.install(hydro._model, VARIANT)
    return hydro


factory._create_prototype_hydro = _create


def pytest_report_header(config):
    return f"DEBT-048 memory_plugin: память {VARIANT} на моделях фабрики; код {sm.SOLVER}"
