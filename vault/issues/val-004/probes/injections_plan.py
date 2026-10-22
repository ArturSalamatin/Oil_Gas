"""VAL-004 (планирование): ловит ли тест плана инъекции И1, И2 — подменой методов, без правки кода решателя.

И1 — адиабатический член с dt × 1.1 (TridiagEnergySolver.compute_adiabatic):
     схема согласована, но с другим уравнением — ждём прежний q и сдвиг предела T.
И2 — +1e-6 К к T после каждого решения энергии (TridiagEnergySolver.solve):
     ошибка на шаге, не исчезающая при Δt -> 0 — ждём q_T вне [0.9, 1.1].
В /implement (шаг 3) те же инъекции делаются правкой кода в worktree.

Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\val-004\\probes\\injections_plan.py
"""

import importlib.util
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("t", HERE / "test_plan_val004.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)   # копия кода плана: sys.path и CFG от numerical_solver/

from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402


def report(tag):
    s = {k: t._run(k) for k in t.K_SERIES}
    fails = {k: len(r["fails"]) for k, r in s.items()}
    for field, sc, ref, tol in (("p", t.BAR, t.P_LIM, t.P_LIM_TOL), ("T", 1.0, t.T_LIM, t.T_LIM_TOL)):
        u = [getattr(s[k]["end"], field)[0] / sc for k in t.K_SERIES]
        q = np.log2((u[1] - u[0]) / (u[2] - u[1]))
        a, b, c = (np.asarray(getattr(s[k]["end"], field)) for k in t.K_SERIES)
        qprof = np.log2(np.max(np.abs(b - a)) / np.max(np.abs(c - b)))
        lim = 2 * u[2] - u[1]
        print(f"{tag} {field}: значения {u[0]:.7f} {u[1]:.7f} {u[2]:.7f}; q(r_w) = {q:.4f} "
              f"[{'ok' if 0.9 <= q <= 1.1 else 'ПАДАЕТ'}]; q(профиль) = {qprof:.4f} "
              f"[{'ok' if 0.9 <= qprof <= 1.1 else 'ПАДАЕТ'}]; предел − эталон = {lim - ref:+.3e} "
              f"[{'ok' if abs(lim - ref) <= tol else 'ПАДАЕТ'}]; отказов {fails}", flush=True)


orig_ad = TridiagEnergySolver.compute_adiabatic
orig_solve = TridiagEnergySolver.solve


def inj1(self, *a):
    return orig_ad(self, *a[:-1], 1.1 * a[-1])


def inj2(self, *a, **kw):
    return orig_solve(self, *a, **kw) + 1e-6


TridiagEnergySolver.compute_adiabatic = inj1
report("И1")
TridiagEnergySolver.compute_adiabatic = orig_ad

TridiagEnergySolver.solve = inj2
report("И2")
TridiagEnergySolver.solve = orig_solve
