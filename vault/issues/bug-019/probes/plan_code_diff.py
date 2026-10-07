"""BUG-019, аудит: код в плане совпадает с проверенными черновиками.

Сравнивает блоки ```python плана (тесты §7, consistency.py шага 2, функция шага 4.3)
с test_pvt_consistency.py, consistency_draft.py, factory_draft.py. Печатает различия.

Запуск: python vault/issues/bug-019/probes/plan_code_diff.py
"""

import difflib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE.parents[2] / "plans" / "bug-019 pvt-negative-compressibility-check.md"
blocks = re.findall(r"```python\n(.*?)```", PLAN.read_text(encoding="utf-8"), flags=re.S)


def find(prefix):
    return next(b for b in blocks if b.startswith(prefix))


def show(name, a, b):
    d = list(difflib.unified_diff(a.splitlines(), b.splitlines(), "план", name, lineterm="", n=0))
    print(f"── {name}: {'совпадает' if not d else f'{len(d)} строк различий'}")
    for line in d[:40]:
        print("   " + line)


show("test_pvt_consistency.py", find('"""Согласованность PVT: сжимаемости нефти и газа неотрицательны (BUG-019).\n\nA.'),
     (HERE / "test_pvt_consistency.py").read_text(encoding="utf-8"))

cons_plan = find('"""Согласованность PVT: сжимаемости нефти и газа неотрицательны (BUG-019).\n\nУсловия')
cons_draft = (HERE / "consistency_draft.py").read_text(encoding="utf-8")
# Ожидаемые отличия — только докстринг модуля и комментарий у _REL_STEP
strip = lambda t: t[t.index("def _d_dp"):]
show("consistency_draft.py (от def _d_dp)", strip(cons_plan), strip(cons_draft))

func_plan = find("def _warn_negative_compressibility")
fd = (HERE / "factory_draft.py").read_text(encoding="utf-8")
show("factory_draft.py (функция)", func_plan, fd[fd.index("def _warn_negative_compressibility"):])
