"""BUG-015, замер при планировании: точность фикстуры кейса B VAL-002.

Фикстура TestCaseB_PureJT.result (N = 50, Δt = 1e7 с, rtol_converge = 1e-6)
как есть. Печатает отклонение от T(r_j) в центрах и T[0] − T(r_w) против
μ·(p[0] − p_wf) — для выбора допусков нового теста шага 3.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-015\\probes\\val002b_fixture.py
"""

import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"Код: {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "tests"))

import test_val002 as v  # noqa: E402

c = v.TestCaseB_PureJT()
r = v.TestCaseB_PureJT.result.__wrapped__(c)
T, T_c, hy = r["T_final"], r["T_exact"], r["hydro"]
p0 = hy.state.p[0]
T_w = v.T_EXT + c.MU_JT * (v.P_WF - v.P_EXT)
half = c.MU_JT * (p0 - v.P_WF)
print(f"шагов энергии: {len(r['history']) - 1}")
print(f"max|T − T(r_j)| = {np.max(np.abs(T - T_c)):.3e} К"
      f" ({np.max(np.abs(T - T_c)) / 1.5:.2e} от ΔT_w)")
print(f"max_(j≥1)|T − T(r_j)| = {np.max(np.abs(T[1:] - T_c[1:])):.3e} К")
print(f"T[0] − T(r_w) = {T[0] - T_w:+.6e} К, μ(p[0] − p_wf) = {half:+.6e} К,"
      f" разность {T[0] - T_w - half:+.3e} К")
