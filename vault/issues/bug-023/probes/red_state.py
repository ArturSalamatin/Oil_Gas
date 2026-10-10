r"""BUG-023: красное состояние — эталон _ref_jt теряет вклад левой внутренней грани при Φ⁺ > 0.

Запуск из numerical_solver/ (основного каталога или worktree):
    .venv\Scripts\python ..\vault\issues\bug-023\probes\red_state.py
Файлы проекта не меняются. Разделы:
  1. синтетика N = 4 (данные — как в тесте плана): ручной расчёт по eq:QJT_disc,
     эталон теста _ref_jt и решатель TridiagEnergySolver.compute_jt;
  2. сообщение сверки d при нулевом допуске: какое значение и какую ячейку оно печатает.
"""
import sys
import warnings
from pathlib import Path

import numpy as np

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/, не из {SOLVER}")
print("SOLVER =", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER / "tests"))

import test_energy_matrix_examples as tme  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402

print("тест:", tme.__file__)

# ── 1. Синтетика ──
# Нефть течёт от скважины на всех гранях (Q_o > 0, Φ_o > 0), газ — к скважине
# (Q_g < 0, Φ_g < 0). Давление и μ_JT неоднородны, все числа целые:
# арифметика точная, сравнение — на равенство.
N = 4
p = np.array([10.0, 20.0, 40.0, 70.0])
p_wf = 5.0
ext = {"p": 110.0, "mu_JT_o": 9.0, "mu_JT_g": 10.0}
mu_o = np.array([1.0, 2.0, 3.0, 4.0])
mu_g = np.array([5.0, 6.0, 7.0, 8.0])
Q_o = np.full(N + 1, 1.0)
Q_g = np.full(N + 1, -1.0)
Phi_o = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
Phi_g = np.array([-1.0, -2.0, -3.0, -4.0, -6.0])

# Ручной расчёт eq:QJT_disc.
# Перепады на гранях: забой 10-5, внутренние 20-10, 40-20, 70-40, контур 110-70.
#   нефть, левая грань (Φ⁺), μ из ячейки слева (на забое — ячейка 0):
#     [1·1·5, 1·2·10, 2·3·20, 3·4·30] = [5, 20, 120, 360]
#   газ, правая грань (Φ⁻), μ из ячейки справа (на контуре при притоке — контурное):
#     [6·(-2)·10, 7·(-3)·20, 8·(-4)·30, 10·(-6)·40] = [-120, -420, -960, -2400]
J_hand = np.array([5.0 - 120.0, 20.0 - 420.0, 120.0 - 960.0, 360.0 - 2400.0])

J_ref = tme._ref_jt(Phi_o, Phi_g, mu_o, mu_g, Q_o, Q_g, p, N, ext, p_wf)
# compute_jt не читает сетку, PVT и породу — объект строится без них
J_solver = TridiagEnergySolver(None, None, None).compute_jt(
    Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext, p_wf)

print("== 1. Синтетика N = 4: нефть от скважины, газ к скважине")
print("   по формуле (вручную):", J_hand)
print("   эталон _ref_jt:      ", J_ref, "— совпадает" if np.array_equal(J_ref, J_hand)
      else f"— НЕ совпадает, разность {J_hand - J_ref}")
print("   решатель compute_jt: ", J_solver, "— совпадает" if np.array_equal(J_solver, J_hand)
      else f"— НЕ совпадает, разность {J_hand - J_solver}")

# ── 2. Сообщение сверки d при нулевом допуске ──
# Как в примере 18 из аудита VAL-005: ячейка 1 — решатель 1.18e-26 Вт при
# нулевом эталоне и нулевом масштабе, ячейка 2 — всё нули.
d = np.array([5.0, 1.18e-26, 0.0])
ref_d = np.array([5.0, 0.0, 0.0])
d_scale = np.array([5.0, 0.0, 0.0])
d_err = np.abs(d - ref_d)
d_lim = tme.RTOL * (np.abs(ref_d) + d_scale)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    ratio = d_err / d_lim
print("== 2. Сообщение сверки d при нулевом допуске")
print(f"   d_err / d_lim = {ratio}; предупреждений numpy: {len(caught)}")
print(f"   сообщение теста: max = {np.max(ratio):.2e} в ячейке {int(np.argmax(ratio))}")
print(f"   упавшие ячейки (d_err > d_lim): {np.flatnonzero(d_err > d_lim).tolist()}")
