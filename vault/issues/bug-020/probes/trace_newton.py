"""BUG-020: почему Ньютон на шагах останова после первого не укладывается в 15 итераций.

Добыча n_prod суток, затем режим B (q_oil = 0) и принятые шаги лестницы
trace_ladder_20B.out.txt (60, 60, 120, 60 с), после чего — отказывающий шаг
dt_fail (120 с, t = 0.083 ч). Ньютон исходной ступени (граница S_g = -0.05,
||F||_inf) повторяется вручную до max_iter итераций с журналом: невязка,
ячейка и уравнение максимума невязки, шаг линейного поиска, число граней со
сменой ячейки «выше по потоку» относительно предыдущей итерации, состояние
ячеек у максимума невязки.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\trace_newton.py 20 10 40
"""

import copy
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

DAY = 86400.0
BASES = {"20": "20_rs300_cooling"}
base_key, n_prod, max_iter = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ACCEPTED = [60.0, 60.0, 120.0, 60.0]
DT_FAIL = 120.0
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
n = model.grid.n
ps = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                   sg=s.Sg.copy(), gas_active=(s.regime == 1))
model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)
for dt in ACCEPTED:
    new, rep = model.advance(ps, dt)
    assert rep.converged, dt
    ps = new
mask = ps.gas_active.copy()
two = np.flatnonzero(mask)
print(f"=== состояние перед отказом: p0 = {ps.pressure_bar[0]:.2f} бар, 2ф = {two.size} "
      f"(ячейки {two.min()}…{two.max()}), dt = {DT_FAIL:.0f} с ===")

z = model.pack(ps, mask)
f0 = model.residual(z, ps, DT_FAIL, mask)
scale = max(np.linalg.norm(f0, np.inf), 1e-9)
tol = 1e-11 + 1e-8 * scale
print(f"допуск: {tol:.2e} (scale = {scale:.2e})")
prev_up = None
for it in range(1, max_iter + 1):
    J, f = model.finite_difference_jacobian(z, ps, DT_FAIL, mask)
    nrm = np.linalg.norm(f, np.inf)
    k = int(np.argmax(np.abs(f)))
    cell, eq = (k, "нефть") if k < n else (k - n, "газ")
    p = z[:n]
    up = (p[:-1] - p[1:]) >= 0
    flips = 0 if prev_up is None else int(np.count_nonzero(up != prev_up))
    flip_idx = [] if prev_up is None else list(np.flatnonzero(up != prev_up)[:6])
    prev_up = up
    st = model.unpack(z, mask)
    near = range(max(cell - 1, 0), min(cell + 2, n))
    desc = "; ".join(f"{j}:{'2ф' if mask[j] else '1ф'} p={st.pressure_bar[j]:.3f} "
                     f"{'Sg' if mask[j] else 'Rs'}={(st.sg[j] if mask[j] else st.rs_sm3_sm3[j]):.5f}"
                     for j in near)
    line = (f"it {it:2d}: |F| = {nrm:.2e} max: ячейка {cell} ({eq}); смен «выше по потоку»: {flips} {flip_idx}; {desc}")
    if nrm <= tol:
        print(line + "  → сошёлся")
        break
    dz = model._linear_solve(J, -f)
    mf = np.linalg.norm(f, np.inf)
    alpha = 1.0
    acc = False
    for _ in range(12):
        trial = z + alpha * dz
        if model._trial_is_reasonable(trial, mask):
            if np.linalg.norm(model.residual(trial, ps, DT_FAIL, mask), np.inf) < mf:
                z = trial
                acc = True
                break
        alpha *= 0.5
    print(line + f"  alpha = {alpha if acc else 0:.2e}  |dp|max = {np.abs(dz[:n]).max():.3e} "
                 f"(ячейка {int(np.argmax(np.abs(dz[:n])))})")
    if not acc:
        print("  → линейный поиск: нет шага")
        break
