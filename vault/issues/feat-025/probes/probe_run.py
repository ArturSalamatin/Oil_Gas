"""FEAT-025: прогон конфигов примеров 19–21 и таблица по записям.

Замеряется: число принятых подшагов (дробление шага — больше записей истории),
q_o, GOR, T(r_w), ΔT(r_w), S_g(r_w), R_s(r_w), p у забоя, двухфазные ячейки,
контурная ячейка (p_{N-1} - p_b), баланс энергии, время sim.run.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\probe_run.py <папка с 19/20/21> [19 20 21]
"""

import sys
import time
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

DAY = 86400.0


class Counting:
    """Обёртка EnergySolver.solve: считает принятые подшаги и их длины."""

    def __init__(self, inner):
        self._inner, self.dts = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        self.dts.append(dt)
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def run_one(cfg_path, every):
    cfg = load_config(cfg_path)
    sim, init = SimulatorFactory.from_config(cfg)
    cnt = Counting(sim._energy)
    sim._energy = cnt
    t0 = time.perf_counter()
    try:
        h = sim.run(init)
    except Exception as e:  # noqa: BLE001 — проба: печатаем отказ и идём дальше
        print(f"   ОТКАЗ: {type(e).__name__}: {e}")
        return
    el = time.perf_counter() - t0
    grid, pvt = sim._grid, cnt._inner._pvt
    r = grid.r_centers
    T0, Rs0 = cfg.initial_conditions.T0, cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    n_int = len(cfg.time.history)
    print(f"   p_b = {pb/1e6:.3f} МПа; sim.run {el:.1f} с; подшагов {len(cnt.dts)} "
          f"(интервалов {n_int}); min dt = {min(cnt.dts):.0f} с")
    print(f"   {'сут':>6} | {'q_o':>10} {'GOR':>7} | {'T_w':>8} {'ΔT_w':>7} | {'Sg_w':>6} "
          f"{'Rs_w':>7} {'p_w,МПа':>8} | {'2ф':>3} {'дальн,м':>8} | {'pN-pb,кПа':>9}")
    for n, st in enumerate(h.states):
        if n % every and n != len(h.states) - 1:
            continue
        w = h.well_data[n]
        g = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
        tp = np.flatnonzero(st.Sg > 0)
        far = r[tp[-1]] if tp.size else 0.0
        print(f"   {h.times[n]/DAY:6.2f} | {w.q_o_std:10.4e} {g:7.2f} | {st.T[0]:8.3f} "
              f"{st.T[0]-T0:+7.3f} | {st.Sg[0]:6.4f} {st.Rs[0]:7.3f} {st.p[0]/1e6:8.4f} | "
              f"{tp.size:3d} {far:8.1f} | {(st.p[-1]-pb)/1e3:9.1f}")
    bal = compute_balance(h, grid, cfg)
    print(f"   баланс энергии: rel_residual = {bal['rel_residual'][-1]:.2e}")


if __name__ == "__main__":
    root = Path(sys.argv[1])
    names = sys.argv[2:] or ["19", "20", "21"]
    every = 5
    for nm in names:
        print(f"\n── {nm}: {root / nm / 'config.json'}")
        run_one(root / nm / "config.json", every)
