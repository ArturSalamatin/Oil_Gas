"""FEAT-039 (планирование): числа тестов VAL-004 на останове, если поле включает нарастание и на пуске.

tests/test_val004.py::_run_1h_shutin: 10 сут добычи из конфига tests/data/bug020_rs150
(шаг 1 сут), затем 1 ч останова одним интервалом, поле time.dt_after_control_change = h0.
После FEAT-039 то же поле начнёт и первые сутки добычи с подшага <= h0. Проба считает
конец часа останова и состояние на конце добычи при прежнем (пуск полным шагом) и
новом поведении.

Запуск из numerical_solver/ (P – путь к скрипту):
    .venv\\Scripts\\python P <h0> ...
"""

import copy
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from start_series import SOLVER_ROOT, patch_first, BAR  # noqa: E402  (вставляет Path.cwd())

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CFG = SOLVER_ROOT / "tests" / "data" / "bug020_rs150" / "config.json"
N_PROD, HOUR = 10, 3600.0


def run(h0, start):
    """Как _run_1h_shutin(h0); start – нарастание и на первом интервале (поведение FEAT-039)."""
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    hist = cfg.time.history
    assert len(hist) == N_PROD + 1, "сценарий bug020_rs150 изменился"
    shut = copy.deepcopy(hist[N_PROD])
    shut.dt = HOUR
    cfg.time.history = list(hist[:N_PROD]) + [shut]
    cfg.time.dt_after_control_change = h0
    sim, s0 = SimulatorFactory.from_config(cfg)
    if start and h0 is not None:
        patch_first(sim, h0)
    h = sim.run(s0)
    return h.states[N_PROD], h.states[-1]


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    for a in sys.argv[1:]:
        h0 = None if a == "none" else float(a)
        p_old, e_old = run(h0, False)
        p_new, e_new = run(h0, True)
        dprod = {f: float(np.max(np.abs(getattr(p_new, f) - getattr(p_old, f))))
                 for f in ("p", "Sg", "Rs", "T")}
        print(f"h0={a}: конец добычи max|Δ| p {dprod['p'] / BAR:.2e} бар, S_g {dprod['Sg']:.2e}, "
              f"R_s {dprod['Rs']:.2e}, T {dprod['T']:.2e} К", flush=True)
        for tag, e in (("прежнее", e_old), ("FEAT-039", e_new)):
            print(f"    1 ч останова, {tag}: T(r_w) {e.T[0]:.4f} К, p(r_w) {e.p[0] / BAR:.4f} бар, "
                  f"R_s(r_w) {e.Rs[0]:.4f}", flush=True)


if __name__ == "__main__":
    main()
