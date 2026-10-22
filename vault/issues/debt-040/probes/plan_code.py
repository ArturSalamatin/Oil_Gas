"""DEBT-040, аудит: блоки кода плана — сверка «было» с файлом, тесты шага 1, подмена _fallback кодом шага 2.

Блоки берутся из текста плана (vault/plans/debt-040 shutin-skip-failing-stages.md),
а не переписываются вручную: проверяется ровно то, что вставит /implement.

    python plan_code.py check             — блоки «было» шага 2 есть в blackoil.py дословно
    python plan_code.py write-tests <путь> — записать файл тестов шага 1
    pytest -p plan_code ...               — прогон с _fallback из блока «стало» шага 2
                                            (каталог проб — в PYTHONPATH)
"""

import re
import sys
import textwrap
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PLAN = HERE.parents[2] / "plans" / "debt-040 shutin-skip-failing-stages.md"
SOLVER = HERE.parents[3] / "numerical_solver"
BLACKOIL = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3" / "radial_blackoil" / "blackoil.py"


def blocks():
    return re.findall(r"```python\n(.*?)```", PLAN.read_text(encoding="utf-8"), flags=re.S)


def find(pred, what):
    found = [b for b in blocks() if pred(b)]
    if len(found) < 1:
        raise RuntimeError(f"в плане не найден блок: {what}")
    return found


def fallback_after():
    return find(lambda b: b.lstrip().startswith("def _fallback") and "open_hopeless=" in b,
                "«стало» _fallback")[0]


def install():
    from radial_blackoil.blackoil import RadialBlackOilModel
    ns = {"np": np}
    exec(textwrap.dedent(fallback_after()), ns)
    RadialBlackOilModel._fallback = ns["_fallback"]


def pytest_sessionstart(session):
    install()
    print("\n[plan_code] RadialBlackOilModel._fallback подменён блоком «стало» шага 2")


def check():
    src = BLACKOIL.read_text(encoding="utf-8")
    before_fb = find(lambda b: b.lstrip().startswith("def _fallback") and "open_hopeless=" not in b,
                     "«было» _fallback")[0]
    header = find(lambda b: b.startswith("BUG-020: a fourth stage") and "DEBT-040" not in b,
                  "«было» шапки")[0]
    print(f"«было» _fallback дословно в файле: {before_fb in src}")
    print(f"«было» шапки дословно в файле: {header in src}")
    after = fallback_after()
    compile(textwrap.dedent(after), "<стало _fallback>", "exec")
    long = [ln for ln in after.splitlines() if len(ln) > 100]
    print(f"«стало» компилируется; строк длиннее 100: {len(long)}")
    for ln in long:
        print(f"    {len(ln)}: {ln.strip()[:80]}…")


def write_tests(path):
    body = find(lambda b: b.startswith('"""DEBT-040: запасной путь advance'), "тесты шага 1")[0]
    Path(path).write_text(body, encoding="utf-8")
    print(f"записано {len(body.splitlines())} строк в {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "check":
        check()
    else:
        write_tests(sys.argv[2])
