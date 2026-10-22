"""DEBT-020, план: отрицательный контроль bits_capture.py — проба видит сдвиг в 1 ULP.

Подменяет assemble_tridiag обёрткой, сдвигающей b[N-1] на одну единицу
последнего разряда (np.nextafter), и снимает снимок с меткой neg. Сравнение
compare base neg обязано дать ПРОВАЛ — иначе совпадение «до/после» в /implement
ничего не доказывает.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-020\\probes\\bits_capture.py capture base
    .venv\\Scripts\\python ..\\vault\\issues\\debt-020\\probes\\plan_negative_control.py
    .venv\\Scripts\\python ..\\vault\\issues\\debt-020\\probes\\bits_capture.py compare base neg
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bits_capture  # noqa: E402

bits_capture._setup_path()
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402

orig = TridiagEnergySolver.assemble_tridiag


def perturbed(self, N, *args, **kw):
    a, b, c, d = orig(self, N, *args, **kw)
    b[N - 1] = np.nextafter(b[N - 1], np.inf)
    return a, b, c, d


TridiagEnergySolver.assemble_tridiag = perturbed
bits_capture.capture("neg")
