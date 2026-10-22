"""DEBT-030, аудит раунд 1: правки шага 3 и тест прототипа шага 2 — на копии прототипа.

Копирует numerical_solver/HydroSolverPrototype/Prototype_1.0.3 (без OUTPUT и
__pycache__) в probes/_work/Prototype_1.0.3, применяет правки E1–E5 плана точной
заменой (каждая строка-якорь должна встретиться ровно один раз — так её найдёт Edit),
пишет tests/test_failure_report.py. Затем в копии запускаются тесты прототипа и
регрессия (команды печатаются в конце). Копию удалить после разбора.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-030\\probes\\apply_plan.py
"""
import shutil
from pathlib import Path

HERE = Path(__file__).parent
SRC = Path.cwd() / "numerical_solver" / "HydroSolverPrototype" / "Prototype_1.0.3"
DST = HERE / "_work" / "Prototype_1.0.3"

EDITS = [
    ("E1 импорт replace",
     "from dataclasses import dataclass\n",
     "from dataclasses import dataclass, replace\n"),
    ("E2 docstring модуля",
     "(bitwise the former dense one); _linear_solve takes sparse or dense J.\n\"\"\"\n",
     "(bitwise the former dense one); _linear_solve takes sparse or dense J.\n"
     "DEBT-030: when all three stages of advance() fail, the report carries the Newton\n"
     "fields of the original algorithm, not those of the last fallback attempt.\n\"\"\"\n"),
    ("E3 docstring advance",
     "        if that fails too, the fallback again with a globalized Newton (BUG-016).\"\"\"\n",
     "        if that fails too, the fallback again with a globalized Newton (BUG-016).\n"
     "        If all three fail, the report carries the original algorithm's Newton (DEBT-030).\"\"\"\n"),
    ("E4 orig=rep",
     "            return new,rep\n"
     "        # Fallback only: where the original algorithm converges, results stay\n",
     "            return new,rep\n"
     "        orig=rep  # DEBT-030: reported if the fallback and the third stage fail too\n"
     "        # Fallback only: where the original algorithm converges, results stay\n"),
    ("E5 отчёт общего отказа",
     "            rep.globalized=True; return new,rep\n",
     "            rep.globalized=True\n"
     "            if not rep.converged:\n"
     "                # DEBT-030: the last attempt is often the BHP 'shut' branch, which\n"
     "                # \"converges\" in 0 iterations with ||F|| = 0 on an unchanged state and\n"
     "                # is dropped as inconsistent; its report made every rejected step in\n"
     "                # step_log.csv read \"0 iterations, residual 0\".  Report the original\n"
     "                # algorithm's Newton instead (as before BUG-014); the branch fields\n"
     "                # (well_branch, well_switches, fallback, globalized) stay the last\n"
     "                # attempt's.  Accepted steps are untouched (_grow_dt reads them).\n"
     "                rep=replace(rep,iterations=orig.iterations,residual_inf=orig.residual_inf,\n"
     "                            active_set_iterations=orig.active_set_iterations,\n"
     "                            phase_switches=orig.phase_switches)\n"
     "            return new,rep\n"),
]

TEST = '''import unittest
from tests.helpers import ROOT, model_and_state

# DEBT-030 (GPN project): first step of regression case T04 (Nabor_1b with other
# relperm tables, N = 100, p0 = 200 bar, BHP = 100 bar, dt = 60 s).  All three
# stages of advance() fail; the BHP 'shut' branch "converges" in 0 iterations with
# ||F|| = 0 on the unchanged initial state and is dropped as inconsistent.  Before
# DEBT-030 its report went to step_log.csv; now the Newton fields of the failure
# report are the original algorithm's.  The Nabor_1b fixture itself converges on
# this step.  An absolute case path: ROOT/'tests'/'fixtures'/<absolute> == <absolute>.
T04=ROOT/'regression'/'inputs'/'T04.xlsx'

class FailureReportTests(unittest.TestCase):
    def test_total_failure_reports_original_newton(self):
        _,ref,s=model_and_state(n=100,bhp=100.0,p0=200.0,case=T04)
        _,orig=ref._advance_phases(s,60.0)
        self.assertFalse(orig.converged,'precondition: the original algorithm fails on this step')
        _,m,_=model_and_state(n=100,bhp=100.0,p0=200.0,case=T04)
        _,rep=m.advance(s,60.0)
        self.assertFalse(rep.converged); self.assertTrue(rep.fallback and rep.globalized)
        self.assertGreater(rep.iterations,0)
        self.assertEqual((rep.iterations,rep.residual_inf,rep.active_set_iterations,rep.phase_switches),
                         (orig.iterations,orig.residual_inf,orig.active_set_iterations,orig.phase_switches))

if __name__=='__main__': unittest.main()
'''

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("OUTPUT", "__pycache__", "*.pyc"))
(DST / "OUTPUT").mkdir()

path = DST / "radial_blackoil" / "blackoil.py"
text = path.read_text(encoding="utf-8")
for name, old, new in EDITS:
    n = text.count(old)
    print(f"{name}: якорь найден {n} раз")
    assert n == 1, name
    text = text.replace(old, new)
path.write_text(text, encoding="utf-8")
(DST / "tests" / "test_failure_report.py").write_text(TEST, encoding="utf-8")
print(f"копия: {DST}")
print("дальше, из копии: ..\\..\\..\\..\\..\\..\\numerical_solver\\.venv\\Scripts\\python -m pytest tests -q")
