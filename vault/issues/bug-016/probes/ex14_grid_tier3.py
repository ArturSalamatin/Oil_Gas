"""BUG-016: пример 14 на N = 50/100/150 с правкой (третья ступень) — первый шаг и год.

Запуск (из numerical_solver основного каталога): python <этот файл> <режим> <cap|-> <chop|->
Печать: первый шаг через адаптер (подшаги, S_g[0], p[0]), итог года, сходимость по сетке.
"""

import copy
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

mode, cap, chop = sys.argv[1], sys.argv[2], sys.argv[3]
patch.install(mode, cap=None if cap == "-" else float(cap), chop=None if chop == "-" else float(chop))
base = load_config(patch.NS / "examples" / "14_high_gor_cooling" / "config.json")
for N in (50, 100, 150):
    cfg = copy.deepcopy(base)
    cfg.grid.N = N
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    res = sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
    st1 = res.state
    print(f"N={N:3d} первый шаг: подшагов {res.n_substeps}, S_g[0] = {st1.Sg[0]:.6f}, "
          f"p[0] = {st1.p[0] / 1e6:.6f} МПа, двухфазных {int((st1.regime == 1).sum())}", flush=True)
    for k in list(patch.COUNT):
        patch.COUNT[k] = 0
    sim, init = SimulatorFactory.from_config(cfg)
    t0 = time.perf_counter()
    h = sim.run(init)
    st, w = h.states[-1], h.well_data[-1]
    print(f"N={N:3d} год: {time.perf_counter() - t0:.1f} с, advance {patch.COUNT['advance']}, "
          f"отказов {patch.COUNT['failed']}, третья ступень {patch.COUNT.get('tier3_ok', 0)}; "
          f"T(r_w) = {st.T[0]:.3f} К, S_g(r_w) = {st.Sg[0]:.4f}, q_o = {w.q_o_std:.4e}, "
          f"GOR = {w.q_g_std / w.q_o_std:.2f}", flush=True)
