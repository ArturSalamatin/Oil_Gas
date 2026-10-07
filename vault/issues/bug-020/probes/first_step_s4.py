"""BUG-020: первый шаг останова — только опытная ступень (stage4_lib), разные dt и k_freeze.

Добыча n_prod суток, затем из конечного состояния — Ньютон опытной ступени
напрямую (без штатных ступеней). Для отказов — трассировка итераций.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\first_step_s4.py 20 10 B 4
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (HERE, SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402
import stage4_lib  # noqa: E402

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod, mode, k_freeze = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
LS = sys.argv[5] if len(sys.argv) > 5 else "none"
FLIP = int(sys.argv[6]) if len(sys.argv) > 6 else 2
TRACE_FAIL = len(sys.argv) > 7 and sys.argv[7] == "trace"
DTS = [60.0, 120.0, 168.75, 240.0, 337.5, 675.0, 1350.0, 2700.0, 5400.0, 21600.0, 86400.0]
BASE = SOLVER / "examples" / BASES[base_key] / "config.json"

cfg = load_config(BASE)
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
hist = []
for _ in range(n_prod):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
cfg.time.history = hist
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
p_ext = cfg.initial_conditions.p0
ps0 = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                    sg=s.Sg.copy(), gas_active=(s.regime == 1))
if mode == "A":
    model.set_bhp_control(p_ext / BAR_TO_PA)
else:
    model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)
stage4_lib.install(model, k_freeze=k_freeze, flip_freeze=FLIP, ls=LS)
print(f"=== {BASES[base_key]}: первый шаг останова ({mode}) только ступенью 4, k_freeze = {k_freeze}, "
      f"flip_freeze = {FLIP}, поиск: {LS} ===")
for dt in DTS:
    if mode == "A":
        model._well_branch = "shut"
    t1 = time.perf_counter()
    new, rep = model._stage4_newton(ps0, dt)
    el = time.perf_counter() - t1
    if rep.converged:
        print(f"  dt = {dt:8.2f} с: ✓ it = {rep.iterations:2d}  p0 = {new.pressure_bar[0]:7.2f} бар  "
              f"2ф = {int(new.gas_active.sum())}  ({el:.1f} с)")
    else:
        print(f"  dt = {dt:8.2f} с: ✗ res = {rep.residual_inf:.1e}  ({el:.1f} с)")
        if TRACE_FAIL:
            stage4_lib.TRACE = True
            model._stage4_newton(ps0, dt)
            stage4_lib.TRACE = False
    model._well_branch = None
