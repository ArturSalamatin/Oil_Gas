"""BUG-015, реализация: тесты кейса B VAL-002 на коде и на двух мутантах compute_jt.

Тот же разбор, что часть «мутанты» plan_apply_check.py, но на рабочем
tests/test_val002.py (после шага 3), а не на копии с применённым планом.
Ожидание: код как есть — оба теста passed; «+ полуячейка» и «JT выключен» —
оба FAILED.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-015\\probes\\mutants_case_b.py
"""

import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"Код: {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "tests"))

import test_val002 as v  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402

print(f"тесты из: {v.__file__}")
ORIG = TridiagEnergySolver.compute_jt


def plus_half(self, Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext, p_wf):
    """К J[0] добавлен перепад полуячейки μ·Φ⁻_{1/2}·(p[0] − p_wf)."""
    J = ORIG(self, Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext, p_wf).copy()
    J[0] += (mu_o[0] * min(Phi_o[0], 0.0)
             + mu_g[0] * min(Phi_g[0], 0.0)) * (p[0] - p_wf)
    return J


def jt_off(self, Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext, p_wf):
    return np.zeros(N)


NAMES = ("test_T_profile_matches_analytical", "test_cell0_is_center_not_wellbore")
cls = v.TestCaseB_PureJT
for label, fn in (("код как есть", ORIG), ("+ полуячейка", plus_half),
                  ("JT выключен", jt_off)):
    TridiagEnergySolver.compute_jt = fn
    try:
        inst = cls()
        res = cls.result.__wrapped__(inst)
        print(f"[{label}]")
        for name in NAMES:
            try:
                getattr(inst, name)(res)
                print(f"  {name}: passed")
            except AssertionError as e:
                msg = (str(e).splitlines() or ["без сообщения"])[0][:60]
                print(f"  {name}: FAILED ({msg})")
    finally:
        TridiagEnergySolver.compute_jt = ORIG
