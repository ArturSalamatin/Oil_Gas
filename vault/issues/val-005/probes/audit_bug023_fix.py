"""Аудит VAL-005: проба исправления BUG-023 в копии tests/test_energy_matrix_examples.py (probes/impl).

_ref_jt_face возвращает давления по обе стороны грани, _ref_jt берёт перепад справа минус слева.
Запуск (из корня проекта, после apply_plan.py):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\val-005\\probes\\audit_bug023_fix.py
"""
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

path = Path(__file__).resolve().parent / "impl" / "numerical_solver" / "tests" / "test_energy_matrix_examples.py"
text = path.read_text(encoding="utf-8")

edits = [
    ("    if f == 0:\n        return p_wf, mu_JT_o[0], mu_JT_g[0]\n",
     "    if f == 0:\n        return p_wf, p[0], mu_JT_o[0], mu_JT_g[0]\n"),
    ("        return (ext['p'],\n",
     "        return (p[N - 1], ext['p'],\n"),
    ("    return p[f], mu_JT_o[_upstream(Q_o[f], f)], mu_JT_g[_upstream(Q_g[f], f)]\n",
     "    return p[f - 1], p[f], mu_JT_o[_upstream(Q_o[f], f)], mu_JT_g[_upstream(Q_g[f], f)]\n"),
    ("        p_left, mu_o_l, mu_g_l = _ref_jt_face(\n",
     "        p_ll, p_lr, mu_o_l, mu_g_l = _ref_jt_face(\n"),
    ("        p_right, mu_o_r, mu_g_r = _ref_jt_face(\n",
     "        p_rl, p_rr, mu_o_r, mu_g_r = _ref_jt_face(\n"),
    ("        dp_left = p[j] - p_left          # на левой грани j-1/2\n"
     "        dp_right = p_right - p[j]        # на правой грани j+1/2\n",
     "        dp_left = p_lr - p_ll            # на левой грани j-1/2: p_j - p_{j-1}\n"
     "        dp_right = p_rr - p_rl           # на правой грани j+1/2: p_{j+1} - p_j\n"),
]
for old, new in edits:
    n = text.count(old)
    print(f"  {'✓' if n == 1 else '✗'} найдено {n}: {old.strip()[:70]}")
    text = text.replace(old, new)
path.write_text(text, encoding="utf-8")

# Синтетика: поток от скважины на внутренних гранях — эталон обязан дать mu*Phi+*(p_j - p_{j-1})
import importlib.util  # noqa: E402
import numpy as np  # noqa: E402
spec = importlib.util.spec_from_file_location("tme_fixed", path)
tme = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(path.parent))
spec.loader.exec_module(tme)
N = 4
p = np.array([10.0, 20.0, 30.0, 40.0])
Q = np.full(N + 1, 1.0)
Q[0] = 0.0
Phi = np.full(N + 1, 2.0)
Phi[0] = 0.0
mu = np.full(N, 0.5)
ext = {"p": 50.0, "mu_JT_o": 0.5, "mu_JT_g": 0.5}
J = tme._ref_jt(Phi, np.zeros(N + 1), mu, mu, Q, np.zeros(N + 1), p, N, ext, 5.0)
print("эталон после правки J =", J, "(ожидание [0, 10, 10, 10])")
