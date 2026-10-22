"""BUG-020: первое направление Ньютона на шаге останова — какие ячейки требуют огромного dSg.

Добыча n_prod суток, затем из конечного состояния: направление Ньютона
dz = -J^{-1} F на старом состоянии (ветка «закрыта», набор фаз старый) для
нескольких dt. Печать ячеек с наибольшим |dSg|: индекс, r, p, S_g, PV,
приращения, локальный c_t, вклад потоков в невязку.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\first_direction.py 20 10
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
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod = sys.argv[1], int(sys.argv[2])
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
st = sim.run(init).states[-1]
model = sim._hydro._model
p_ext = cfg.initial_conditions.p0
n = model.grid.n
old = BlackOilState(pressure_bar=st.p / BAR_TO_PA, rs_sm3_sm3=st.Rs.copy(),
                    sg=st.Sg.copy(), gas_active=(st.regime == 1))
mask = old.gas_active.copy()
r = np.asarray(getattr(model.grid, "centers_m", getattr(model.grid, "r_centers_m", np.full(n, np.nan))), float)
pv = model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, old.pressure_bar)
two = np.flatnonzero(mask)
print(f"=== {BASES[base_key]}: {n_prod} сут; 2ф ячейки {two.min()}…{two.max()}, "
      f"p_b(R_s0) ≈ {model.pvt.pb_of_rs(cfg.initial_conditions.Rs0):.1f} бар ===")
model.set_bhp_control(p_ext / BAR_TO_PA)
model._well_branch = "shut"
model._sg_lower_bound = None
z0 = model.pack(old, mask)
for dt in (60.0, 600.0, 3600.0):
    J, f = model.finite_difference_jacobian(z0, old, dt, mask)
    dz = model._linear_solve(J, -f)
    dp, dx = dz[:n], dz[n:]
    dsg = np.where(mask, dx, 0.0)
    top = np.argsort(-np.abs(dsg))[:5]
    print(f"\n── dt = {dt:.0f} с: max|dp| = {np.abs(dp).max():.1f} бар (ячейка {np.argmax(np.abs(dp))}), "
          f"max|dSg| = {np.abs(dsg).max():.2f} ──")
    for i in top:
        print(f"  i = {i:3d}  r = {r[i]:8.4f} м  p = {old.pressure_bar[i]:7.2f} бар  Sg = {old.sg[i]:.4f}  "
              f"PV = {pv[i]:.3e} м³  dp = {dp[i]:+8.2f}  dSg = {dsg[i]:+9.3f}  "
              f"F_o = {f[i]:+.2e}  F_g = {f[n+i]:+.2e}")
    print("  первые 5 ячеек:")
    for i in range(5):
        print(f"  i = {i:3d}  r = {r[i]:8.4f} м  p = {old.pressure_bar[i]:7.2f} бар  Sg = {old.sg[i]:.4f}  "
              f"PV = {pv[i]:.3e} м³  dp = {dp[i]:+8.2f}  dSg = {dsg[i]:+9.3f}  "
              f"F_o = {f[i]:+.2e}  F_g = {f[n+i]:+.2e}")
model._well_branch = None
model._sg_lower_bound = -0.05
print("\nатрибуты сетки:", [a for a in dir(model.grid) if not a.startswith("_")])
