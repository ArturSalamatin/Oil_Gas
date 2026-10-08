"""DEBT-015: плагин pytest — адаптер без внутреннего дробления (max_retries = 0).

Показывает тесты, которые зовут adapter.solve напрямую и молча опираются на
A-retry адаптера: после DEBT-015 адаптер делает один шаг и при отказе бросает
исключение. Тесты через Simulator.run с этим плагином теряют дробление вовсе —
их провалы к вопросу не относятся, поэтому запускать только тесты прототипа.

Запуск из numerical_solver:
    $env:PYTHONPATH = "..\\vault\\issues\\debt-015\\probes"
    .venv\\Scripts\\python -m pytest -p no_adapter_retry_plugin tests/test_prototype_adapter.py ... -q
"""
import gpn_multiphase_solver.hydro.prototype_adapter as pa

_orig = pa.PrototypeHydroAdapter.__init__


def _init(self, model, grid, pvt, max_retries=9):
    _orig(self, model, grid, pvt, max_retries=0)


pa.PrototypeHydroAdapter.__init__ = _init
