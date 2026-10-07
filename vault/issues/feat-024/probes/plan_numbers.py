"""FEAT-024: числа плана для примера 14 (данные — probes/final/, make_14_config.py).

Что замеряется:
  - дробление шага (A-retry) — по вызовам EnergySolver.solve;
  - таблица по записям: q_o, q_g, GOR, T(r_w), S_g(r_w), R_s(r_w), p[0],
    число двухфазных ячеек, самая дальняя, контурная ячейка;
  - дальние ячейки (j >= 44) на каждой записи и после первого подшага —
    откуда двухфазная ячейка за стационарным фронтом;
  - тот же конфиг с разгоном шага (1, 1, 2, 4, 8, 8 ч, затем 1 сут до 30 сут,
    дальше 30 сут) — для сравнения положения фронта и T(r_w);
  - баланс энергии, время прогона.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-024\\probes\\plan_numbers.py
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

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

# argv[1] — папка с конфигом (по умолчанию final); argv[2] = "short" — без прогона с разгоном
CFG = HERE / (sys.argv[1] if len(sys.argv) > 1 else "final") / "config.json"
SHORT = len(sys.argv) > 2 and sys.argv[2] == "short"
DAY = 86400.0


class Recording:
    """Обёртка EnergySolver.solve: пишет каждый ПРИНЯТЫЙ подшаг, физику не трогает."""

    def __init__(self, inner):
        self._inner, self.rows = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        st = hr.state
        self.rows.append(dict(t=st.t, dt=dt, p=st.p.copy(), Sg=st.Sg.copy(),
                              Rs=st.Rs.copy(), regime=st.regime.copy()))
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def run(cfg):
    sim, init = SimulatorFactory.from_config(cfg)
    rec = Recording(sim._energy)
    sim._energy = rec
    t0 = time.perf_counter()
    h = sim.run(init)
    return sim, rec, h, time.perf_counter() - t0


def far_cells(label, r, p, Sg, Rs, regime, pb, j0=43):
    print(f"   {label}:")
    for j in range(j0, len(r)):
        print(f"      j={j:2d} r={r[j]:6.1f} м: p-p_b = {(p[j]-pb)/1e3:+8.1f} кПа, "
              f"S_g = {Sg[j]:.3e}, R_s = {Rs[j]:8.4f}, regime = {regime[j]}")


def report(name, cfg, sim, rec, h, el):
    grid, pvt = sim._grid, rec._inner._pvt
    Rs0, T0 = cfg.initial_conditions.Rs0, cfg.initial_conditions.T0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    r = grid.r_centers
    dts = Counter(round(x["dt"], 3) for x in rec.rows)
    print(f"\n=== {name} ===")
    print(f"p_b(R_s0) = {pb/1e6:.4f} МПа; sim.run {el:.1f} с; записей {len(h.states)}; "
          f"принятых подшагов {len(rec.rows)}; dt: {dict(dts)}")
    print(f"{'сут':>6} | {'q_o':>10} {'q_g':>8} {'GOR':>7} | {'T_w':>8} {'ΔT_w':>7} | "
          f"{'S_g(r_w)':>8} {'R_s(r_w)':>8} {'p[0]':>7} | {'n_2ф':>4} {'дальняя':>7} | "
          f"{'p_N-1-p_b':>9} {'S_g,N-1':>7}")
    for n, st in enumerate(h.states):
        w = h.well_data[n]
        tp = np.nonzero(st.Sg > 0)[0]
        g = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
        print(f"{h.times[n]/DAY:6.1f} | {w.q_o_std:10.4e} {w.q_g_std:8.5f} {g:7.2f} | "
              f"{st.T[0]:8.3f} {st.T[0]-T0:+7.3f} | {st.Sg[0]:8.4f} {st.Rs[0]:8.4f} "
              f"{st.p[0]/1e6:7.4f} | {tp.size:4d} {r[tp[-1]] if tp.size else 0:7.1f} | "
              f"{(st.p[-1]-pb)/1e3:+9.1f} {st.Sg[-1]:7.1e}")
    bal = compute_balance(h, grid, cfg)
    print(f"баланс: rel_residual = {float(bal['rel_residual'][-1]):.2e}; "
          f"max по записям {float(np.max(bal['rel_residual'])):.2e}")
    return pb, r


# ── 1. Штатный конфиг: 12 × 30 сут, суточный шаг ──
cfg = load_config(CFG)
cfg.output.log_level = "ERROR"
sim, rec, h, el = run(cfg)
pb, r = report("пример 14: 12 × 30 сут, dt_integration = 1 сут", cfg, sim, rec, h, el)

# Дальние ячейки: после первого подшага (1 сут), на 30 сут и на 360 сут
# hr.state в Recording — состояние В КОНЦЕ принятого подшага
x = rec.rows[0]
far_cells(f"после первого подшага (t = {x['t']/DAY:.3f} сут)", r, x["p"], x["Sg"], x["Rs"],
          x["regime"], pb)
for k in (1, 2, 4, 9, 29):
    x = rec.rows[k]
    tp = np.nonzero(x["Sg"] > 0)[0]
    print(f"   t = {x['t']/DAY:.0f} сут: двухфазных {tp.size}, дальняя r = {r[tp[-1]]:.1f} м, "
          f"p-p_b там {(x['p'][tp[-1]]-pb)/1e3:+.1f} кПа, S_g = {x['Sg'][tp[-1]]:.3e}")
for n in (1, len(h.states) - 1):
    st = h.states[n]
    far_cells(f"запись {h.times[n]/DAY:.0f} сут", r, st.p, st.Sg, st.Rs, st.regime, pb)

# Минимум p - p_b в каждой дальней ячейке по всем подшагам
print("   min по подшагам p - p_b (кПа) и max S_g в дальних ячейках:")
P = np.array([x["p"] for x in rec.rows])
S = np.array([x["Sg"] for x in rec.rows])
for j in range(43, len(r)):
    i = int(np.argmin(P[:, j]))
    print(f"      j={j:2d} r={r[j]:6.1f}: min(p-p_b) = {(P[i, j]-pb)/1e3:+8.1f} кПа "
          f"(t = {rec.rows[i]['t']/DAY:.0f} сут), max S_g = {S[:, j].max():.3e}")

# ── 2. Тот же конфиг с разгоном шага ──
if SHORT:
    sys.exit(0)
cfg2 = copy.deepcopy(cfg)
iv = cfg2.time.history[0]
dts = [h_ * 3600.0 for h_ in (1, 1, 2, 4, 8, 8)] + [DAY] * 29 + [30 * DAY] * 11
hist = []
for dt in dts:
    y = copy.deepcopy(iv)
    y.dt = dt
    hist.append(y)
cfg2.time.history = hist
sim2, rec2, h2, el2 = run(cfg2)
print(f"\n=== разгон шага: sim.run {el2:.1f} с, подшагов {len(rec2.rows)}, "
      f"min dt {min(x['dt'] for x in rec2.rows):.3g} с ===")
for n, t in enumerate(h2.times):
    d = t / DAY
    if n in (0, 1, 6) or abs(d - round(d)) < 1e-9 and round(d) in (1, 2, 3, 5, 10, 20, 30, 60, 180, 360):
        st = h2.states[n]
        tp = np.nonzero(st.Sg > 0)[0]
        w = h2.well_data[n]
        print(f"   {d:8.3f} сут: T_w = {st.T[0]:8.3f} (ΔT {st.T[0]-350:+.3f}), S_g(r_w) = {st.Sg[0]:.4f}, "
              f"q_o = {w.q_o_std:.4e}, двухфазных {tp.size}, дальняя {r[tp[-1]] if tp.size else 0:.1f} м")
far_cells("разгон шага, 360 сут", r, h2.states[-1].p, h2.states[-1].Sg, h2.states[-1].Rs,
          h2.states[-1].regime, pb)
