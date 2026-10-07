"""BUG-019: pytest-плагин — код шагов 2 и 4 плана до реализации.

Регистрирует consistency_draft как модуль gpn_multiphase_solver.pvt.consistency
и подменяет factory._create_pvt: после создания PVT вызывается черновик
_warn_negative_compressibility (factory_draft.py). В реальном коде вызов стоит в
from_config после _check_undersaturated_start; для тестов порядок не важен
(ни один тест шага 5 не ждёт ValueError).

Запуск (из numerical_solver), путь к пробам — через PYTHONPATH:
    $env:PYTHONPATH = "..\\vault\\issues\\bug-019\\probes"
    .venv\\Scripts\\python -m pytest <тесты> -p plan_impl_plugin -q
"""

import sys

import common  # noqa: F401  — пути к пакету решателя и прототипу
import consistency_draft

sys.modules["gpn_multiphase_solver.pvt.consistency"] = consistency_draft
import gpn_multiphase_solver.pvt as _pvt_pkg  # noqa: E402
_pvt_pkg.consistency = consistency_draft

from gpn_multiphase_solver import factory  # noqa: E402
from factory_draft import _warn_negative_compressibility  # noqa: E402

_orig_create_pvt = factory._create_pvt


def _create_pvt(config):
    pvt = _orig_create_pvt(config)
    _warn_negative_compressibility(config, pvt)
    return pvt


factory._create_pvt = _create_pvt
