"""BUG-020: влияние опытной четвёртой ступени на штатные примеры.

Пример считается дважды: штатный прототип и прототип с опытной ступенью
(stage4_lib.install). Ступень включается только при отказе трёх штатных, поэтому
расхождение возможно лишь в примерах с дроблением A-retry. Печать: число
вызовов ступени и её успехов, время счёта, max|Δ| по записанным состояниям
(p, S_g, R_s, T) и по дебитам, побитовое совпадение историй.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\examples_effect.py 10_deep_degassing
"""

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
import os  # noqa: E402
import stage4_lib  # noqa: E402
import plan_code  # noqa: E402

# BUG020_IMPL=plan — код правки из плана (plan_code.apply), иначе опытная ступень stage4_lib
PLAN = os.environ.get("BUG020_IMPL") == "plan"
INSTALL, STATS = (plan_code.apply, plan_code.STATS) if PLAN else (stage4_lib.install, stage4_lib.STATS)

name = sys.argv[1]
BASE = SOLVER / "examples" / name / "config.json"


def run(use4):
    cfg = load_config(BASE)
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    if use4:
        INSTALL(sim._hydro._model)
    t1 = time.perf_counter()
    h = sim.run(init)
    return h, time.perf_counter() - t1


h0, e0 = run(False)
h1, e1 = run(True)
S = STATS
same = all(np.array_equal(getattr(a, f), getattr(b, f))
           for a, b in zip(h0.states, h1.states) for f in ("p", "Sg", "Rs", "T"))


def dmax(f):
    return max(float(np.max(np.abs(getattr(a, f) - getattr(b, f)))) for a, b in zip(h0.states, h1.states))


dq = max(abs(a.q_o_std - b.q_o_std) for a, b in zip(h0.well_data, h1.well_data)) \
    if hasattr(h0, "well_data") else float("nan")
print(f"{name} ({'код плана' if PLAN else 'stage4_lib'}): ступень 4 — вызовов {S['calls']}, "
      f"сошлась {S['ok']}, итераций {S.get('iters', '—')}; "
      f"счёт {e0:.1f} → {e1:.1f} с; записей {len(h0.states)}/{len(h1.states)}; побитово: {same}; "
      f"max|Δp| = {dmax('p'):.3e} Па, max|ΔSg| = {dmax('Sg'):.2e}, max|ΔRs| = {dmax('Rs'):.2e}, "
      f"max|ΔT| = {dmax('T'):.2e} К, max|Δq_o| = {dq:.2e} м³ст/с")
