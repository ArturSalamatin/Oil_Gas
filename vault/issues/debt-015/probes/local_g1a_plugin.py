"""DEBT-015: плагин pytest — локальное дробление G1a вместо равномерного A-retry (код плана подменой).

Адаптер делает одну попытку (max_retries = 0, отказ — RuntimeError), Simulator._advance —
make_aligned из local_subdiv.py с лимитом из конфига (запоминается при сборке адаптера;
у тестовых двойников — 9). Список упавших тестов = тесты, которые план обязан править.

Запуск из numerical_solver:
    $env:PYTHONPATH = "..\\vault\\issues\\debt-015\\probes"
    .venv\\Scripts\\python -m pytest -p local_g1a_plugin tests/ -m "not slow" -q
"""
import gpn_multiphase_solver.hydro.prototype_adapter as pa
from gpn_multiphase_solver.simulator import Simulator

import local_subdiv

local_subdiv.reset()                 # счётчики пробы: make_aligned пишет в них
_orig_init = pa.PrototypeHydroAdapter.__init__


def _init(self, model, grid, pvt, max_retries=9):
    _orig_init(self, model, grid, pvt, max_retries=0)
    self._mr_cfg = int(max_retries)


pa.PrototypeHydroAdapter.__init__ = _init

_cache = {}


def _advance(self, state, dt, bc, balance, mass, allow_subdivision=True):
    mr = getattr(self._hydro, "_mr_cfg", 9)
    if mr not in _cache:
        _cache[mr] = local_subdiv.make_aligned(mr)
    return _cache[mr](self, state, dt, bc, balance, mass)


Simulator._advance = _advance
