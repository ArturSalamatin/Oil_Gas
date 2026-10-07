"""DEBT-033, аудит плана: код и тесты берутся из файла плана ДОСЛОВНО (блоки ```python),
блоки «До» сверяются с blackoil.py, затем код плана подменяется в памяти и прогоняются:
  prototype — тесты прототипа (кроме test_grouped_jacobian.py) + test_grouped_jacobian.py
              с правкой шага 3 (Jg.toarray()) + новые тесты плана; ожидается 76 + 4 + 3 = 83;
  solver    — быстрый уровень numerical_solver/tests (-m "not slow").
Файлы проекта не меняются.

Запуск — из каталога numerical_solver:
    .venv\\Scripts\\python d:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-033\\probes\\audit_plan_literal.py prototype|solver
"""
import os
import re
import sys
import textwrap
import unittest
from pathlib import Path

import numpy as np

PLAN = Path(__file__).resolve().parents[3] / "plans" / "debt-033 vectorize-grouped-jacobian.md"
SOLVER_ROOT = Path.cwd()
PROTO = SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
BLACKOIL = PROTO / "radial_blackoil" / "blackoil.py"
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(SOLVER_ROOT))

text = PLAN.read_text(encoding="utf-8")
blocks = re.findall(r"```python\n(.*?)```", text, flags=re.S)
src = BLACKOIL.read_text(encoding="utf-8").splitlines()


def block_with(marker):
    found = [b for b in blocks if marker in b]
    assert len(found) == 1, (marker, len(found))
    return found[0]


# ── Блоки «До» против файла ──
def check_before(marker, first, last):
    b = block_with(marker).rstrip("\n").splitlines()
    f = src[first - 1:last]
    ok = b == f
    print(f"«До» [{marker[:40]}] против blackoil.py:{first}-{last}: {'совпадает' if ok else 'РАСХОЖДЕНИЕ'}")
    if not ok:
        for i, (x, y) in enumerate(zip(b, f)):
            if x != y:
                print("  план:", x[:120]); print("  файл:", y[:120]); break
        print(f"  строк: план {len(b)}, файл {len(f)}")


check_before("J=np.zeros((2*n,2*n),float)", 204, 216)
check_before("return splu(csc_matrix(J)).solve(b)", 217, 221)
before2 = [b for b in blocks if "if room_plus <= 1.25*h and room_minus > h: return -h" in b and "_fd_steps" not in b]
assert len(before2) == 1
print("«До» шага 2 против blackoil.py:194-198:",
      "совпадает" if before2[0].rstrip("\n").splitlines() == src[193:198] else "РАСХОЖДЕНИЕ")

# ── Код шагов 2–3 из плана ──
after2 = block_with("def _fd_steps").splitlines()
i0 = next(i for i, l in enumerate(after2) if l.startswith("    def _fd_steps"))
i1 = next(i for i in range(i0 + 1, len(after2)) if after2[i].startswith("    def "))
fd_src = textwrap.dedent("\n".join(after2[i0:i1]).rstrip() + "\n")
after3 = textwrap.dedent(block_with("J.eliminate_zeros()"))

from scipy.linalg import solve as dense_solve  # noqa: E402
from scipy.sparse import coo_matrix, csc_matrix, issparse  # noqa: E402
from scipy.sparse.linalg import splu  # noqa: E402
import radial_blackoil.blackoil as B  # noqa: E402

ns = dict(np=np, coo_matrix=coo_matrix, csc_matrix=csc_matrix, issparse=issparse, splu=splu, dense_solve=dense_solve)
exec(fd_src, ns)
exec(after3, ns)
M = B.RadialBlackOilModel
M._fd_steps = ns["_fd_steps"]
M.finite_difference_jacobian_grouped = ns["finite_difference_jacobian_grouped"]
M.finite_difference_jacobian = ns["finite_difference_jacobian"]
M._linear_solve = ns["_linear_solve"]
print("код плана подменён:", ", ".join(k for k in ("_fd_steps", "finite_difference_jacobian_grouped",
                                                  "finite_difference_jacobian", "_linear_solve")))


class Patch:
    """Плагин pytest: методы уже подменены в этом процессе; печатает, откуда взят прототип."""
    def pytest_sessionstart(self, session):
        print("radial_blackoil:", Path(B.__file__).parent)


mode = sys.argv[1]
if mode == "prototype":
    import pytest
    os.chdir(PROTO)
    rc = pytest.main(["tests", "-q", "-p", "no:cacheprovider", "--ignore=tests/test_grouped_jacobian.py"], plugins=[Patch()])
    print("pytest (без test_grouped_jacobian.py): код", int(rc))
    sys.path.insert(0, str(PROTO))
    from tests.helpers import model_and_state  # noqa: E402
    old = (PROTO / "tests" / "test_grouped_jacobian.py").read_text(encoding="utf-8")
    n_rep = old.count("abs(Jg-Jr)")
    old = old.replace("abs(Jg-Jr)", "abs(Jg.toarray()-Jr)").replace("if __name__=='__main__': unittest.main()", "")
    tns = dict(np=np, unittest=unittest, csc_matrix=csc_matrix, issparse=issparse, model_and_state=model_and_state)
    exec(compile(old, "test_grouped_jacobian.py (шаг 3)", "exec"), tns)
    exec(compile(block_with("class GroupedJacobianSparseTests"), "тесты плана", "exec"), tns)
    suite = unittest.TestSuite()
    for cls in ("GroupedJacobianTests", "GroupedJacobianSparseTests"):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(tns[cls]))
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"test_grouped_jacobian.py по плану: замен abs(Jg-Jr) {n_rep}, тестов {res.testsRun}, "
          f"ошибок {len(res.errors)}, падений {len(res.failures)}")
elif mode == "solver":
    import pytest
    rc = pytest.main(["tests/", "-m", "not slow", "-q", "-p", "no:cacheprovider"], plugins=[Patch()])
    print("pytest быстрый уровень: код", int(rc))
