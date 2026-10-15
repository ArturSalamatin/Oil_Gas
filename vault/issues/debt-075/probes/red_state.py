"""DEBT-075: что делает Simulator сейчас, если гидродинамика вернула нефизичное состояние.

Двойники тестов (tests/_doubles.py: LogProfileHydroStub) + настоящий TridiagEnergySolver,
как в разделе G tests/test_simulator.py (DEBT-047). Обёртка гидродинамики на втором
вызове ставит в ячейку 3 значение S_g, p или R_s; 24 шага по 1 ч, N = 10.
Исход до DEBT-075: расчёт дошёл до конца / какое исключение и с каким текстом.

Запуск из numerical_solver/ (в worktree — с PYTHONPATH на worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-075\\probes\\red_state.py
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER))       # пакет tests — двойники и помощники test_simulator

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.simulator import Simulator  # noqa: E402
from tests.test_simulator import (  # noqa: E402
    _make_simulator, _initial_state, _single_interval_schedule)

print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)


class Corrupting:
    """На вызове on_call ставит state.<field>[cell] = value в результате внутреннего двойника."""

    def __init__(self, inner, field, value, cell=3, on_call=2):
        self.inner, self.field, self.value, self.cell, self.on_call = (
            inner, field, value, cell, on_call)
        self.n_calls = 0

    def solve(self, state, dt, bc):
        r = self.inner.solve(state, dt, bc)
        self.n_calls += 1
        if self.n_calls == self.on_call:
            x = getattr(r.state, self.field).copy()
            x[self.cell] = self.value
            r = replace(r, state=replace(r.state, **{self.field: x}))
        return r

    def component_inventories(self, state):
        return self.inner.component_inventories(state)


CASES = [("Sg", 1.5), ("Sg", 6.585), ("Sg", -0.01), ("Sg", np.nan), ("Sg", np.inf),
         ("Sg", np.nextafter(1.0, 2.0)), ("Sg", np.nextafter(0.0, -1.0)),
         ("Sg", 0.0), ("Sg", 1.0),
         ("p", 0.0), ("p", -1e5), ("p", np.nan), ("p", np.inf), ("p", 1.0),
         ("Rs", -1.0), ("Rs", np.nan), ("Rs", 0.0)]

for field, value in CASES:
    grid, pvt, inner_hydro, energy, _ = _make_simulator()
    hydro = Corrupting(inner_hydro, field, value)
    sim = Simulator(grid, hydro, energy, pvt, _single_interval_schedule())
    try:
        hist = sim.run(_initial_state())
        T = hist.states[-1].T
        out = (f"дошёл до конца: вызовов гидро {hydro.n_calls}, записей {len(hist.states)}, "
               f"T в [{np.min(T):.4f}, {np.max(T):.4f}] К")
    except Exception as exc:  # noqa: BLE001 — проба: печать причины
        out = f"{type(exc).__name__} после {hydro.n_calls} вызовов гидро: {str(exc)[:160]}"
    print(f"{field:3s} = {value!s:8s} → {out}", flush=True)
