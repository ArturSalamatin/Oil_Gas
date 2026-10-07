"""FEAT-024: сверка матрицы энергии с эталоном на данных примера 14 (до создания папки).

Та же логика, что tests/test_energy_matrix_examples.py::test_matrix_matches_reference,
но конфиг — probes/final/config.json. Замеряет время (стоимость теста) и число
вызовов solve.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-024\\probes\\matrix_check.py
"""

import sys
import time
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

cfg = load_config(HERE / "final" / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
n = [0]
worst = [0.0]


def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
    ra, rb, rc, rd = tm.build_reference(sim._grid, sim._pvt, cfg.rock,
                                        hydro_result, state_prev, dt, bc)
    for x, y in ((a, ra), (b, rb), (c, rc), (d, rd)):
        np.testing.assert_allclose(x, y, rtol=tm.RTOL, atol=0.0)
        m = np.abs(y) > 0
        if m.any():
            worst[0] = max(worst[0], float(np.max(np.abs(x[m] - y[m]) / np.abs(y[m]))))
    assert a[0] == 0.0 and c[-1] == 0.0
    n[0] += 1


sim._energy.matrix_probe = probe
t0 = time.perf_counter()
sim.run(init)
print(f"сверка матрицы: вызовов {n[0]}, max отн. расхождение {worst[0]:.2e} "
      f"(порог {tm.RTOL:.0e}), время {time.perf_counter() - t0:.1f} с")
