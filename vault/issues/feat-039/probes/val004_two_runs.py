"""FEAT-039 (планирование): останов VAL-004 отдельным прогоном из конечного состояния добычи.

После FEAT-039 поле time.dt_after_control_change в tests/test_val004.py::_run_1h_shutin
включит нарастание и на первых сутках добычи: состояние перед остановом сдвинется
(val004_start.out.txt), а при h0 = 2 с последний шаг часа 1800 с начнёт отказывать
(val004_diag.out.txt). Вариант теста: добыча – прогон с полем null, останов – второй
прогон того же конфига с историей из одного интервала останова, начальное состояние –
конец добычи. Для второго прогона интервал останова – первый, и после FEAT-039 он
нарастает от h0 как смена управления. Проба проверяет, что на текущем коде (до FEAT-039,
первый интервал не нарастает) второй прогон при h0 = None побитово равен одному прогону,
а при FEAT-039 (подмена first_substep_depth) – прежнему одному прогону с h0.

Запуск из numerical_solver/ (P – путь к скрипту):
    .venv\\Scripts\\python P <h0|none> ...
"""

import copy
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from start_series import SOLVER_ROOT, patch_first, BAR  # noqa: E402

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CFG = SOLVER_ROOT / "tests" / "data" / "bug020_rs150" / "config.json"
N_PROD, HOUR = 10, 3600.0
FIELDS = ("p", "Sg", "Rs", "T", "regime")


def one_run(h0):
    """Как _run_1h_shutin(h0) сейчас: добыча и час останова одним прогоном."""
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    hist = cfg.time.history
    shut = copy.deepcopy(hist[N_PROD])
    shut.dt = HOUR
    cfg.time.history = list(hist[:N_PROD]) + [shut]
    cfg.time.dt_after_control_change = h0
    sim, s0 = SimulatorFactory.from_config(cfg)
    return sim.run(s0).states[-1]


def two_runs(h0, feat039):
    """Добыча при поле null; останов – второй прогон из конца добычи (интервал 0 – смена при FEAT-039)."""
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    hist = cfg.time.history
    shut = copy.deepcopy(hist[N_PROD])
    shut.dt = HOUR
    cfg.time.history = list(hist[:N_PROD])
    cfg.time.dt_after_control_change = None
    sim, s0 = SimulatorFactory.from_config(cfg)
    prod_end = sim.run(s0).states[-1]

    cfg2 = load_config(CFG)
    cfg2.output.log_level = "ERROR"
    cfg2.time.history = [shut]
    cfg2.time.dt_after_control_change = h0
    sim2, _ = SimulatorFactory.from_config(cfg2)
    if feat039 and h0 is not None:
        patch_first(sim2, h0)
    return sim2.run(prod_end).states[-1]


def same(a, b):
    return all(np.array_equal(np.asarray(getattr(a, f)), np.asarray(getattr(b, f))) for f in FIELDS)


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    for a in sys.argv[1:]:
        h0 = None if a == "none" else float(a)
        ref = one_run(h0)
        cur = two_runs(None, False) if h0 is None else two_runs(h0, True)
        print(f"h0={a}: один прогон T(r_w) {ref.T[0]:.4f} К, p(r_w) {ref.p[0] / BAR:.4f} бар, "
              f"R_s(r_w) {ref.Rs[0]:.4f}; два прогона{' + FEAT-039' if h0 is not None else ''}: "
              f"T(r_w) {cur.T[0]:.4f} К, p(r_w) {cur.p[0] / BAR:.4f} бар, R_s(r_w) {cur.Rs[0]:.4f}; "
              f"побитово {'да' if same(ref, cur) else 'НЕТ'}", flush=True)


if __name__ == "__main__":
    main()
