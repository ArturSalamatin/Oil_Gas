"""FEAT-039 (планирование): почему p(r_w) через 1 ч останова (h0 = 2 с) сдвигается на 0.84 бар при нарастании на пуске.

Сценарий – как val004_start.py (tests/test_val004.py::_run_1h_shutin). Печатает подшаги
и отказы гидродинамики на часе останова, первые подшаги останова, состояние забойных
ячеек на конце часа.

Запуск из numerical_solver/ (P – путь к скрипту):
    .venv\\Scripts\\python P <h0> ...
"""

import copy
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from start_series import SOLVER_ROOT, patch_first, BAR  # noqa: E402

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CFG = SOLVER_ROOT / "tests" / "data" / "bug020_rs150" / "config.json"
N_PROD, HOUR, DAY = 10, 3600.0, 86400.0


def run(h0, start):
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    hist = cfg.time.history
    shut = copy.deepcopy(hist[N_PROD])
    shut.dt = HOUR
    cfg.time.history = list(hist[:N_PROD]) + [shut]
    cfg.time.dt_after_control_change = h0
    sim, s0 = SimulatorFactory.from_config(cfg)
    if start:
        patch_first(sim, h0)
    t_shut = N_PROD * DAY
    log = []
    solve = sim._hydro.solve

    # Подшаги часа останова: (t от начала останова, dt, исход)
    def counting(state, dt, bc):
        on = state.t >= t_shut - 1e-6
        try:
            res = solve(state, dt, bc)
        except HydroConvergenceError:
            if on:
                log.append((state.t - t_shut, dt, "отказ"))
            raise
        if on:
            log.append((state.t - t_shut, dt, "ок"))
        return res

    sim._hydro.solve = counting
    h = sim.run(s0)
    end = h.states[-1]
    fails = [x for x in log if x[2] == "отказ"]
    tag = "FEAT-039" if start else "прежнее"
    print(f"h0={h0:g} {tag}: подшагов останова {len(log) - len(fails)}, отказов {len(fails)}"
          + (f" (t, dt: {[(round(t, 3), round(d, 3)) for t, d, _ in fails[:6]]})" if fails else ""),
          flush=True)
    print(f"    первые подшаги: {[(round(t, 3), round(d, 4), r) for t, d, r in log[:6]]}", flush=True)
    print(f"    конец часа: p[0:4] {np.round(end.p[:4] / BAR, 4)} бар, S_g[0:4] {np.round(end.Sg[:4], 5)}, "
          f"R_s[0:4] {np.round(end.Rs[:4], 3)}, ячеек с газом {int(np.count_nonzero(end.Sg > 0))}",
          flush=True)


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    for a in sys.argv[1:]:
        h0 = float(a)
        run(h0, False)
        run(h0, True)


if __name__ == "__main__":
    main()
