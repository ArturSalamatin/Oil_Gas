"""DEBT-033, планирование: совпадает ли grouped-якобиан с поколонным побитово
и даёт ли сборка coo → csc → eliminate_zeros() те же массивы, что csc_matrix(dense).

Запуск — из каталога numerical_solver:
    .venv\\Scripts\\python d:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-033\\probes\\grouped_vs_reference.py [пример ...]
Результат на a342a85 — grouped_vs_reference.txt. Только для кода ДО DEBT-033: проба ждёт
плотную матрицу от finite_difference_jacobian_grouped.

Состояния Ньютона перехватываются подменой finite_difference_jacobian на экземпляре
модели прототипа (как в tests/test_prototype_globalization.py); код не меняется.
"""
import sys
import time
from pathlib import Path

import numpy as np
import scipy
from scipy.sparse import coo_matrix, csc_matrix

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

MAX_SAMPLES = 10   # состояний на пример для поколонного якобиана (он стоит 2N невязок)


def band_csc(J, n):
    """Разреженная сборка из трёх диагоналей четырёх блоков плотной J — как в целевом коде."""
    rows, cols = [], []
    for bi in (0, 1):
        for bj in (0, 1):
            for d in (-1, 0, 1):
                i = np.arange(max(0, -d), min(n, n - d))   # строка i, столбец i + d
                rows.append(bi * n + i)
                cols.append(bj * n + i + d)
    rows = np.concatenate(rows)
    cols = np.concatenate(cols)
    A = coo_matrix((J[rows, cols], (rows, cols)), shape=J.shape).tocsc()
    A.eliminate_zeros()
    return A


def check_example(ex):
    cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
    sim, s0 = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    orig = model.finite_difference_jacobian
    states = []

    def recording(z, state_old, dt_s, gas_active, *a, **k):
        # Копии: z и state_old дальше меняются Ньютоном
        states.append((np.array(z, float), state_old.copy(), float(dt_s), np.array(gas_active, bool),
                       model._well_branch, model._sg_step_max, model.control_mode))
        return orig(z, state_old, dt_s, gas_active, *a, **k)

    model.finite_difference_jacobian = recording
    t = time.perf_counter()
    sim.run(s0)
    wall = time.perf_counter() - t
    model.finite_difference_jacobian = orig
    n = model.grid.n

    # Равномерная выборка + все состояния с особой ветвью (shut, третья ступень)
    idx = set(np.linspace(0, len(states) - 1, min(MAX_SAMPLES, len(states))).astype(int))
    idx |= {k for k, s in enumerate(states) if s[4] == 'shut' or s[5] is not None}
    bitwise = csc_same = 0
    worst = 0.0
    t_g = []
    for k in sorted(idx):
        z, so, dt, ga, *_ = states[k]
        t1 = time.perf_counter()
        Jg, f = model.finite_difference_jacobian_grouped(z, so, dt, ga)
        t_g.append(time.perf_counter() - t1)
        Jr, _ = model.finite_difference_jacobian_reference(z, so, dt, ga)
        same = np.array_equal(Jg, Jr)
        bitwise += same
        if not same:
            worst = max(worst, float(np.max(np.abs(Jg - Jr)) / np.max(np.abs(Jr))))
        A, B = csc_matrix(Jg), band_csc(Jg, n)
        csc_same += (np.array_equal(A.indptr, B.indptr) and np.array_equal(A.indices, B.indices)
                     and np.array_equal(A.data, B.data))
        # Вне полосы плотная J — нули (иначе раскраска пропустила бы связь)
        assert np.count_nonzero(Jg) == A.nnz
    branches = sorted({str(s[4]) for s in states})
    stage3 = sum(s[5] is not None for s in states)
    print(f"{ex}: N={n}, расчёт {wall:.1f} с, якобианов {len(states)} (ветви {branches}, "
          f"третья ступень {stage3}, режим {states[0][6]}); проверено {len(idx)}: "
          f"grouped == reference побитово {bitwise}/{len(idx)}"
          + (f", max отн. расхождение {worst:.2e}" if bitwise < len(idx) else "")
          + f"; csc из полосы == csc_matrix(dense) {csc_same}/{len(idx)}; "
          f"grouped {1e3 * np.median(t_g):.1f} мс/якобиан")


print("scipy", scipy.__version__, "numpy", np.__version__)
for ex in sys.argv[1:] or ["04_table_table", "20_rs300_cooling", "15_oil_rate_ramp_up",
                           "13b_pwf_alternating", "14_high_gor_cooling"]:
    check_example(ex)
