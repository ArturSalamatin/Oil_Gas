"""FEAT-021: числа плана для примера 12 с историей 15 × 86400 с.

Конфиг: заготовка 11 с R_ext = 200 м, p0 = 15.5 МПа; time.history — 15
интервалов по 1 сут; dt_integration = 3600 с (как в заготовке). Второй прогон —
dt_integration = 86400 с, только чтобы показать, во что обошёлся бы суточный
шаг интегрирования.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-021\\probes\\plan15d_numbers.py
"""

import copy
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402
from closed_form import report_closed  # noqa: E402
from rs_analytics import report_rs  # noqa: E402
from temperature_asymptotics import report_asymptotics  # noqa: E402


class Counting:
    """Считает вызовы EnergySolver.solve и их dt, физику не трогает."""

    def __init__(self, inner):
        self._inner, self.dt = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        self.dt.append(dt)
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def make_cfg(dt_int):
    cfg = load_config(SOLVER / "examples" / "11_degassing_at_boundary" / "config.json")
    cfg.geometry.R_ext = 200.0
    cfg.initial_conditions.p0 = 15.5e6
    cfg.output.log_level = "ERROR"
    iv = copy.deepcopy(cfg.time.history[0])
    iv.dt = 86400.0
    cfg.time.history = [copy.deepcopy(iv) for _ in range(15)]
    cfg.time.dt_integration = dt_int
    return cfg


def run(dt_int):
    cfg = make_cfg(dt_int)
    sim, init = SimulatorFactory.from_config(cfg)
    cnt = Counting(sim._energy)
    sim._energy = cnt
    t0 = time.perf_counter()
    h = sim.run(init)
    return cfg, sim, cnt, h, time.perf_counter() - t0


cfg, sim, cnt, h, el = run(3600.0)
grid, pvt = sim._grid, cnt._inner._pvt
Rs0 = cfg.initial_conditions.Rs0
pb = float(pvt.pb(np.array([Rs0]))[0])
r = grid.r_centers
j1 = int(np.argmin(abs(r - 1.0)))

print(f"=== 15 × 86400 с, dt_integration = 3600 с ===")
print(f"sim.run {el:.1f} с; сохранено {len(h.states)} состояний; вызовов solve {len(cnt.dt)}; "
      f"dt: {dict(Counter(round(d, 3) for d in cnt.dt))}; сумма dt {sum(cnt.dt):.0f} с")
print(f"{'сут':>4} | {'q_o':>10} {'GOR':>7} | {'T_w':>8} {'S_g(r_w)':>8} | {'n_2ф':>4} {'фронт':>6} | "
      f"{'p(1 м)':>8} {'p_N-1':>8} | {'Rs_N-1-Rs0':>10}")
for n, (st, w) in enumerate(zip(h.states, [None] + list(h.well_data[1:]))):
    tp = np.nonzero(st.Sg > 0)[0]
    q = w.q_o_std if w else float("nan")
    g = w.q_g_std / w.q_o_std if w else float("nan")
    print(f"{h.times[n]/86400:4.0f} | {q:10.4e} {g:7.2f} | {st.T[0]:8.3f} {st.Sg[0]:8.4f} | "
          f"{tp.size:4d} {r[tp[-1]] if tp.size else 0:6.1f} | {st.p[j1]/1e6:8.4f} "
          f"{st.p[-1]/1e6:8.4f} | {st.Rs[-1]-Rs0:10.1e}")

counts = [int(np.count_nonzero(s.Sg > 0)) for s in h.states]
gors = [w.q_g_std / w.q_o_std for w in h.well_data[1:]]
print(f"n_2ф не убывает: {all(b >= a for a, b in zip(counts, counts[1:]))}; "
      f"GOR строго убывает: {all(b < a for a, b in zip(gors, gors[1:]))}; "
      f"min GOR - Rs0 = {min(gors) - Rs0:.2f}")
print(f"контур: min p_N-1 - p_b = {(min(s.p[-1] for s in h.states) - pb)/1e3:+.1f} кПа; "
      f"max S_g,N-1 = {max(s.Sg[-1] for s in h.states):.1e}; "
      f"max|R_s,N-1 - R_s0| = {max(abs(s.Rs[-1] - Rs0) for s in h.states):.1e}")
bal = compute_balance(h, grid, cfg)
print(f"баланс: rel_residual = {float(bal['rel_residual'][-1]):.2e}; "
      f"E_конд = {float(np.ravel(bal['cum_cond'])[-1]):+.4e} Дж; "
      f"E_дегаз = {float(np.ravel(bal['cum_deg'])[-1]):+.4e} Дж")
s = h.states[-1]
print(f"забой 15 сут: p = {s.p[0]/1e6:.3f} МПа, R_s = {s.Rs[0]:.3f}, T = {s.T[0]:.3f} К "
      f"(ΔT = {s.T[0]-cfg.initial_conditions.T0:+.3f}), q_g = {h.well_data[-1].q_g_std:.4e}")
print()
report_rs(cfg, h, pvt)
print()
report_closed(cfg, h, grid, sim)
print()
report_asymptotics(cfg, h, grid, sim)

# ── Ячейка у фронта: почему на 13–15 сут p < p_b, а S_g = 0 ──
j = 46
print(f"\nячейка {j} (центр {r[j]:.1f} м; стационарный фронт 117.6 м):")
for n in (3, 6, 12, 13, 15):
    st = h.states[n]
    Rs_eq = float(pvt.Rs_eq(np.array([st.p[j]]))[0])
    print(f"  {n:2d} сут: p - p_b = {(st.p[j]-pb)/1e3:+7.2f} кПа, S_g = {st.Sg[j]:.2e}, "
          f"R_s = {st.Rs[j]:.4f}, R_s_eq(p) = {Rs_eq:.4f}, R_s - R_s_eq = {st.Rs[j]-Rs_eq:+.4f}")

# ── Во что обошёлся бы суточный шаг интегрирования ──
try:
    run(86400.0)
    print("\ndt_integration = 86400 с: сошлось")
except RuntimeError as e:
    print(f"\ndt_integration = 86400 с: ОТКАЗ — {str(e)[:90]}")
