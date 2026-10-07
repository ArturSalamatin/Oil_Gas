"""Аудит DEBT-019, раунд 2: pytest-плагин, имитирующий запреты шагов 2 и 3 плана.

Код решателя не меняется. Плагин подменяет при загрузке:
  - gpn_multiphase_solver.fluxes.compute_fluxes — ValueError при
    dp_w = p_wf − p[0] > 0 (шаг 3 плана);
  - PrototypeHydroAdapter._build_result — ValueError при G_o[0] > 0
    (шаг 2 плана; проверка после сборки, исход для теста тот же).
Подмена делается ДО сбора тестов (-p грузит плагин раньше тестовых модулей),
поэтому `from gpn_multiphase_solver.fluxes import compute_fluxes` в тестах
и в tests/_doubles.py получает обёртку.

Каждое срабатывание пишется в round2_guard_hits.txt рядом с плагином
(PYTEST_CURRENT_TEST), чтобы увидеть и проглоченные исключения.

Запуск из каталога numerical_solver (PYTHONPATH — только для подключения
плагина, к сценарию пользователя отношения не имеет):
    $env:PYTHONPATH = "..\\vault\\issues\\debt-019\\probes"
    .venv\\Scripts\\python -m pytest tests/ -q -m "not slow" -p round2_guard_plugin
"""

import os
from pathlib import Path

import gpn_multiphase_solver.fluxes as _fl
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter

_HITS = Path(__file__).with_name("round2_guard_hits.txt")
_HITS.write_text("", encoding="utf-8")


def _hit(kind, value):
    with _HITS.open("a", encoding="utf-8") as fh:
        fh.write(f"{kind}\t{value:+.6e}\t{os.environ.get('PYTEST_CURRENT_TEST', '?')}\n")


_orig_compute_fluxes = _fl.compute_fluxes


def _guarded_compute_fluxes(state, grid, pvt, relperm, bc):
    if isinstance(bc.well, PressureControl):
        dp_w = bc.well.p_wf - state.p[0]
        if dp_w > 0.0:
            _hit("fluxes dp_w", dp_w)
            raise ValueError(f"DEBT-019 probe: dp_w = {dp_w:.6e} Па > 0")
    return _orig_compute_fluxes(state, grid, pvt, relperm, bc)


_fl.compute_fluxes = _guarded_compute_fluxes

_orig_build = PrototypeHydroAdapter._build_result


def _guarded_build(self, *args, **kwargs):
    res = _orig_build(self, *args, **kwargs)
    if res.G_o[0] > 0.0:
        _hit("adapter G_o[0]", res.G_o[0])
        raise ValueError(f"DEBT-019 probe: G_o[0] = {res.G_o[0]:.6e} > 0")
    return res


PrototypeHydroAdapter._build_result = _guarded_build
