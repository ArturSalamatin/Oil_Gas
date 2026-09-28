"""Аудит FEAT-021: с какими характерными временами p, R_s, S_g подходят к стационару.

Конфиг примера 12, расписание продлено до 15 сут (только ради этого вопроса;
в самом примере остаётся 72 ч). Отклонения считаются от стационарного
замкнутого решения closed_form.solve_closed (GOR = R_s^0).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-021\\probes\\relaxation_times.py
"""

import copy
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from closed_form import solve_closed  # noqa: E402

DAYS = 15
cfg = load_config(SOLVER / "examples" / "11_degassing_at_boundary" / "config.json")
cfg.geometry.R_ext = 200.0
cfg.initial_conditions.p0 = 15.5e6
cfg.output.log_level = "ERROR"
cfg.time.history = [copy.deepcopy(cfg.time.history[0]) for _ in range(24 * DAYS)]
sim, init = SimulatorFactory.from_config(cfg)
h = sim.run(init)
pvt, grid = sim._energy._pvt, sim._grid
r = grid.r_centers
Rs0, p0 = cfg.initial_conditions.Rs0, cfg.initial_conditions.p0
dP = p0 - cfg.time.history[0].p_wf

cl = solve_closed(cfg, pvt, _create_relperm(cfg), r)
p_ss, Sg_ss = cl["p"], cl["Sg"]
Rs_ss = np.minimum(pvt.Rs_eq(p_ss), Rs0)
j1 = int(np.argmin(abs(r - 1.0)))

t_h = np.array(h.times) / 3600.0
print(f"стационар: p(1 м) = {p_ss[j1]/1e6:.4f} МПа, S_g(r_w) = {Sg_ss[0]:.4f}, "
      f"q_o = {cl['q_o']:.4e}")
print(f"{'t':>7} | {'max|p-p_ss|':>12} {'p-p_ss(1 м)':>12} | {'max|Rs-Rs_ss|':>13} | "
      f"{'Sg(r_w)':>8} {'Sg-Sg_ss':>9} | {'GOR-Rs0':>8} | {'q_o/q_ss-1':>10}")
rows = []
for hh in (1, 6, 12, 24, 48, 72, 120, 168, 240, 360):
    i = int(np.argmin(abs(t_h - hh)))
    s, w = h.states[i], h.well_data[i]
    dp_max = np.max(np.abs(s.p - p_ss))
    dp1 = s.p[j1] - p_ss[j1]
    dRs = np.max(np.abs(s.Rs - Rs_ss))
    dSg = s.Sg[0] - Sg_ss[0]
    gor = w.q_g_std / w.q_o_std - Rs0
    dq = w.q_o_std / cl["q_o"] - 1.0
    rows.append((hh, dp_max, dRs, dSg, gor))
    lab = f"{hh} ч" if hh < 48 else f"{hh/24:.0f} сут"
    print(f"{lab:>7} | {dp_max/dP*100:10.2f} % {dp1/1e3:+9.1f} кПа | {dRs:13.3f} | "
          f"{s.Sg[0]:8.4f} {dSg:+9.4f} | {gor:8.2f} | {dq*100:+9.2f} %")

# Темп затухания на последних сутках: e-кратное время по паре (10 сут, 15 сут)
(_, p10, R10, S10, g10), (_, p15, R15, S15, g15) = rows[-2], rows[-1]
dt = (360 - 240) / 24.0
for name, a, b in (("max|p-p_ss|", p10, p15), ("max|Rs-Rs_ss|", R10, R15),
                   ("Sg-Sg_ss (забой)", S10, S15), ("GOR-Rs0", g10, g15)):
    tau = dt / np.log(abs(a) / abs(b)) if abs(b) < abs(a) else float("inf")
    print(f"  e-кратное время {name:18s} на 10–15 сут: {tau:6.1f} сут")
