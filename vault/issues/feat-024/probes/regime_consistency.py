"""FEAT-024: согласованность режима ячеек с давлением на записях примера 14.

На каждой записи сравниваются множества ячеек:
  A = {regime == 1} (газ активен), B = {S_g > 0}, C = {p < p_b(R_s0)}.
Без ветки PVT выше R_s0 ячейка на 137.3 м остаётся в A и B (S_g ~ 1e-16)
при p > p_b; с веткой R_s = 180 множества совпадают (гипотеза для теста).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-024\\probes\\regime_consistency.py <папка>
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

cfg = load_config(HERE / sys.argv[1] / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
h = sim.run(init)
pb = float(sim._pvt.pb(np.array([cfg.initial_conditions.Rs0]))[0])
print(f"=== {sys.argv[1]}: p_b = {pb/1e6:.4f} МПа ===")
for n, st in enumerate(h.states):
    A = st.regime == 1
    B = st.Sg > 0
    C = st.p < pb
    print(f"  {h.times[n]/86400:5.0f} сут: |A| = {A.sum():2d}, |B| = {B.sum():2d}, |C| = {C.sum():2d}; "
          f"A==C {np.array_equal(A, C)}, B==C {np.array_equal(B, C)}; "
          f"min S_g по B = {st.Sg[B].min() if B.any() else 0:.3e}")
