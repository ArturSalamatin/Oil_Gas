"""FEAT-025: диагностика сверки матрицы энергии (без assert) для примеров 19–21.

Для каждого массива a, b, c, d по всем вызовам: max отн. расхождение по
элементам (как в test_matrix_matches_reference, atol = 0) и max расхождение,
отнесённое к масштабу массива max|y| (вариант atol = RTOL·max|y|). Для худшего
элемента — значение, соседи и отношение |y_j| / max|y| (признак сокращения).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\matrix_diag.py [имя ...]
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "tests", SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
import test_energy_matrix_examples as tm  # noqa: E402

NAMES = ["19_rs150_cooling", "20_rs500_cooling", "21_rs100_cooling"]


def diag(cfg_path):
    cfg = load_config(cfg_path)
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    rel = {k: (0.0, None) for k in "abcd"}
    scaled = {k: 0.0 for k in "abcd"}
    n = [0]

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        ref = tm.build_reference(sim._grid, sim._pvt, cfg.rock, hydro_result, state_prev, dt, bc)
        for k, x, y in zip("abcd", (a, b, c, d), ref):
            m = np.abs(y) > 0
            if m.any():
                r = np.zeros_like(y)
                r[m] = np.abs(x[m] - y[m]) / np.abs(y[m])
                j = int(np.argmax(r))
                if r[j] > rel[k][0]:
                    lo, hi = max(j - 2, 0), min(j + 3, y.size)
                    rel[k] = (float(r[j]), (n[0], j, float(y[j]), y[lo:hi].copy(),
                                            float(np.abs(y[j]) / np.max(np.abs(y)))))
                scaled[k] = max(scaled[k], float(np.max(np.abs(x - y)) / np.max(np.abs(y))))
        n[0] += 1

    sim._energy.matrix_probe = probe
    sim.run(init)
    print(f"   вызовов {n[0]}")
    for k in "abcd":
        r, info = rel[k]
        line = f"   {k}: max отн. {r:.2e}; max |x-y|/max|y| = {scaled[k]:.2e}"
        if info:
            call, j, yj, nb, frac = info
            line += (f"; худший: вызов {call}, j = {j}, y = {yj:.6e}, |y_j|/max|y| = {frac:.1e}, "
                     f"соседи {np.array2string(nb, precision=4)}")
        print(line)


if __name__ == "__main__":
    for nm in sys.argv[1:] or NAMES:
        print(f"── {nm}")
        diag(HERE / "final" / nm / "config.json")
