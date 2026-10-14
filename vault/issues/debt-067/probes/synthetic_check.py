"""DEBT-067, проба планирования: синтетика модульных тестов _cells_converged — на копии кода плана.

Модель Nabor_1b N = 12 с cell_tol = 1e-8, веса dt/V_p; якобиан — диагональная CSC-матрица,
z = 1 (ulp(1) = 2.22e-16). Строка 0 (нефть, забойная): мера 3e-8, предел строки 6e-8 —
проходит по своему пределу. Строка 1: мера 2e-8, предел 1e-8 — нет. Максимумы по сетке:
мера 3e-8 <= предел 6e-8 — сравнение максимумов пропустило бы.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-067\\probes\\synthetic_check.py
"""
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import csc_matrix

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
from tests.test_prototype_cell_tolerance import CELL_TOL, DT, _build  # noqa: E402

EPS = float(np.spacing(1.0))


def cells_converged(model, f, w, J=None, z=None, kappa=1.0):
    """Копия кода плана (шаг 3)."""
    m = model._cell_measure(f, w)
    if m is None or m <= model.cell_tol:
        return True
    if J is None or z is None or not kappa > 0.0:
        return False
    a = np.abs(f)
    bad = a * np.concatenate([w, w]) > model.cell_tol
    return bool(np.all(a[bad] <= kappa * (abs(J) @ np.spacing(np.abs(z)))[bad]))


model, state = _build(12, cell_tol=CELL_TOL)
n = model.grid.n
w = model._cell_weights(state, DT)
z = np.ones(2 * n)
f0 = 3e-8 / w[0]                     # строка 0: мера 3e-8
f1 = 2e-8 / w[1]                     # строка 1: мера 2e-8
d = np.ones(2 * n)
d[0] = 2.0 * f0 / EPS                # предел строки 0 — 6e-8 в единицах меры
d[1] = 0.5 * f1 / EPS                # предел строки 1 — 1e-8
J = csc_matrix(np.diag(d))

only0 = np.zeros(2 * n); only0[0] = f0
both = only0.copy(); both[1] = f1
small = np.zeros(2 * n); small[0] = 0.5e-8 / w[0]
print(f"w[0] = {w[0]:.3e}, w[1] = {w[1]:.3e}")
print("строгое прошло без якобиана:", cells_converged(model, small, w))
print("строка 0 на своём пределе:", cells_converged(model, only0, w, J, z))
print("строки 0 и 1:", cells_converged(model, both, w, J, z),
      f"| максимумы: мера {model._cell_measure(both, w):.3e}, предел {model._cell_floor(J, z, w):.3e}")
print("kappa = 0:", cells_converged(model, only0, w, J, z, kappa=0.0))
print("без якобиана:", cells_converged(model, only0, w))
