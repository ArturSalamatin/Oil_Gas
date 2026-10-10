"""VAL-004 (аудит, раунд 2): инъекция И3 подменой — энергия на подшаге дробления получает длину шага, а не подшага.

В прогоне с принудительным отказом первой попытки (как
test_local_subdivision_equals_finer_series) каждый интервал останова
решается двумя подшагами H/2. Обёртка энергии на останове передаёт 2h = H —
то же, что правка `state, dt, bc` в Simulator._advance (план, шаг 3, И3).
В прогонах без дробления h = dt, правка там ничего не меняет.

Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\val-004\\probes\\injection_i3.py
"""

import importlib.util
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("t", HERE / "test_plan_val004.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)   # копия кода плана: sys.path и CFG от numerical_solver/

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

cfg = load_config(t.CFG)
cfg.time.history = t._shutin_history(cfg, 4)
t0 = t.N_PROD * t.DAY
starts = {}
for iv in cfg.time.history[t.N_PROD:]:
    starts[t0] = iv.dt
    t0 += iv.dt
sim, s0 = SimulatorFactory.from_config(cfg)
solve, esolve = sim._hydro.solve, sim._energy.solve


def failing_first(state, dt, bc):
    if starts.get(state.t) == dt:
        raise HydroConvergenceError("принудительный отказ первой попытки")
    return solve(state, dt, bc)


def energy_full_step(hydro_result, state, h, bc, collect=None):
    # на останове каждый подшаг — половина интервала: передать длину интервала
    if state.t >= t.N_PROD * t.DAY - 1e-6:
        h = 2.0 * h
    return esolve(hydro_result, state, h, bc, collect=collect)


sim._hydro.solve = failing_first
sim._energy.solve = energy_full_step
end = sim.run(s0).states[-1]
ref = t._run(5)["end"]
for f in ("p", "Sg", "Rs", "T", "regime"):
    a, b = np.asarray(getattr(end, f), float), np.asarray(getattr(ref, f), float)
    print(f"И3 {f}: {'побитово' if np.array_equal(a, b) else 'РАЗЛИЧИЕ'}, "
          f"max|Δ| = {np.max(np.abs(a - b)):.3e}", flush=True)
