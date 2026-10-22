"""FEAT-029: откуда греется забой на останове — баланс энергии по ячейкам.

Накопитель EnergyBalanceAccumulator суммирует члены по всей области; здесь
те же выражения копятся по ячейкам (перехват add_substep/add_accumulation):
  adiab_j = V_j Q_ad,j dt,  deg_j = V_j Q_deg,j dt,  jt_j = J_jt,j dt,
  conv_j  = -F_j dt (адвективная форма, eq:energy_conv_face),
  dE_j    = (ρc_p)_eff,j V_j (T^{n+1} - T^n),
  cond_j  = dE_j - (adiab + deg + jt + conv)_j — теплопроводность (внутренние
            грани и контур), остаток уравнения ячейки.
Печать: вклады в ΔT забойной ячейки (К) и в энергию зон r < r_k (Дж) на
отрезках останова. Расписание — как у shutin_scenario.py.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-029\\probes\\local_budget.py 20 15 15
"""

import copy
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path(os.environ.get("FEAT029_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationHistory  # noqa: E402
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator as Acc  # noqa: E402

DAY, HOUR = 86400.0, 3600.0
BASES = {"19": "19_rs150_cooling", "20": "20_rs300_cooling", "21": "21_rs100_cooling"}
key, n_prod, n_shut = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
name = BASES[key]

cfg = load_config(SOLVER / "examples" / name / "config.json")
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
hist = []
for _ in range(n_prod):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
for k in range(24 + n_shut - 1):
    x = copy.deepcopy(iv)
    x.dt = HOUR if k < 24 else DAY
    x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
    hist.append(x)
cfg.time.history = hist
cfg.time.dt_integration = 3600.0
sim, init = SimulatorFactory.from_config(cfg)
grid = sim._grid
V = grid.volumes
N = grid.N
r = grid.r_centers

# ── Поячеечные накопления ──
KEYS = ("dE", "adiab", "deg", "jt", "conv")
cum = {k: np.zeros(N) for k in KEYS}
snaps = []
_add_sub, _add_acc = Acc.add_substep, Acc.add_accumulation


def add_substep(self, hydro_result, state_prev, dt, props, Phi_o, Phi_g,
                Q_T_ext, J_jt, Q_ad, Q_deg, T_ext):
    cum["jt"] += J_jt * dt
    cum["adiab"] += V * Q_ad * dt
    cum["deg"] += V * Q_deg * dt
    self._feat029_Phi = (np.maximum(Phi_o, 0.0) + np.maximum(Phi_g, 0.0),
                         np.minimum(Phi_o, 0.0) + np.minimum(Phi_g, 0.0), dt, T_ext)
    return _add_sub(self, hydro_result, state_prev, dt, props, Phi_o, Phi_g,
                    Q_T_ext, J_jt, Q_ad, Q_deg, T_ext)


def add_accumulation(self, T_new, T_prev, rho_cp_eff, dt):
    Pp, Pm, dts, T_ext = self._feat029_Phi
    T_left = np.concatenate(([T_new[0]], T_new[:-1]))
    T_right = np.concatenate((T_new[1:], [T_ext]))
    F = Pp[0:N] * (T_new - T_left) + Pm[1:N + 1] * (T_right - T_new)
    cum["conv"] += -F * dts
    cum["dE"] += rho_cp_eff * V * (T_new - T_prev)
    cap.append(rho_cp_eff * V)
    return _add_acc(self, T_new, T_prev, rho_cp_eff, dt)


cap = []
Acc.add_substep = add_substep
Acc.add_accumulation = add_accumulation
_orig_append = SimulationHistory.append


def _append(self, *a, **kw):
    s = {k: v.copy() for k, v in cum.items()}
    s["cap"] = cap[-1].copy() if cap else None
    snaps.append(s)
    return _orig_append(self, *a, **kw)


SimulationHistory.append = _append
t0 = time.perf_counter()
h = sim.run(init)
print(f"=== {name}: {n_prod} сут добычи + {n_shut} сут останова; счёт {time.perf_counter()-t0:.0f} с ===")

E = n_prod
T0 = cfg.initial_conditions.T0


def seg(a, b):
    d = {k: snaps[b][k] - snaps[a][k] for k in KEYS}
    d["cond"] = d["dE"] - d["adiab"] - d["deg"] - d["jt"] - d["conv"]
    return d


segs = [(E, E + 1, "1-й час"), (E + 1, E + 24, "2–24 ч"), (E + 24, len(snaps) - 1, "сутки 2–конец"),
        (E, len(snaps) - 1, "весь останов"), (0, E, "добыча")]
# Ёмкость забойной ячейки (ρc_p)_eff V меняется вместе с S_g; для перевода
# Дж → К берётся её значение на конце отрезка (пересчёт приближённый:
# столбец ΔT сверяется с фактическим приращением T(r_w)).
print(f"T(r_w): конец добычи {h.states[E].T[0]:.3f} К (ΔT {h.states[E].T[0]-T0:+.3f}); "
      f"+1 ч {h.states[E+1].T[0]:.3f}; +1 сут {h.states[E+24].T[0]:.3f}; конец {h.states[-1].T[0]:.3f}")
print("Забойная ячейка: вклады в ΔT, К (Дж / ((ρc_p)_eff V) на конце отрезка); факт — по записям:")
print(f"{'отрезок':>15} {'факт':>8} " + " ".join(f"{k:>8}" for k in ("ΔT", "adiab", "deg", "conv", "jt", "cond")))
for a, b, lab in segs:
    d = seg(a, b)
    cap0 = snaps[b]["cap"][0]
    fact = h.states[b].T[0] - h.states[a].T[0]
    print(f"{lab:>15} {fact:>8.3f} " + " ".join(f"{d[k][0]/cap0:>8.3f}" for k in ("dE", "adiab", "deg", "conv", "jt", "cond")))
for rk in (0.3, 1.0, 3.0, 10.0, 30.0, 200.0):
    m = r < rk
    print(f"Зона r < {rk:g} м ({int(m.sum())} ячеек), Дж:")
    for a, b, lab in segs:
        d = seg(a, b)
        print(f"{lab:>15} " + " ".join(f"{k} {float(np.sum(d[k][m])):+.2e}" for k in
                                         ("dE", "adiab", "deg", "conv", "jt", "cond")))
