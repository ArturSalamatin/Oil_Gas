"""BUG-020: исход регрессии прототипа против эталона с опытной четвёртой ступенью.

Расчёт регрессии (run_workbook, как run_prototype.py) в этом же процессе; каждая
модель RadialBlackOilModel получает опытную ступень (stage4_lib.install) сразу
после __init__. Сравнение с golden/ — функциями run_regression.py. Ступень
включается только при отказе трёх штатных, поэтому разойтись могут лишь
расчёты, где эталон отвергает шаги: T03, T04 и пять T05 (step_log.csv,
accepted = False). Выходы — во временном каталоге в probes/, удаляются.

Запуск (из numerical_solver/HydroSolverPrototype/Prototype_1.0.3):
    ..\\..\\.venv\\Scripts\\python ..\\..\\..\\vault\\issues\\bug-020\\probes\\regression_effect.py T03 T04
"""

import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[3] / "numerical_solver" / "HydroSolverPrototype" / "Prototype_1.0.3"
for p in (HERE, PROTO, PROTO / "regression"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import run_regression as rr  # noqa: E402
from radial_blackoil import blackoil  # noqa: E402
from radial_blackoil.runner import run_workbook  # noqa: E402
import stage4_lib  # noqa: E402

_orig_init = blackoil.RadialBlackOilModel.__init__


def _init(self, *a, **kw):
    _orig_init(self, *a, **kw)
    stage4_lib.install(self)


blackoil.RadialBlackOilModel.__init__ = _init

OUT = HERE / "regression_out"
for case in sys.argv[1:]:
    if case in rr.T05_CASES:
        inp, gold = rr.INPUTS / "T05" / f"{case}.xlsx", rr.GOLDEN / "T05" / case
    else:
        inp, gold = rr.INPUTS / f"{case}.xlsx", rr.GOLDEN / case
    out = OUT / case
    if out.exists():
        shutil.rmtree(out)
    c0, k0 = stage4_lib.STATS["calls"], stage4_lib.STATS["ok"]
    t1 = time.perf_counter()
    try:
        run_workbook(inp, out)
        msgs = []
        for name in rr.CSV_FILES:
            ok, msg = rr.compare_csv(gold / name, out / name)
            if not ok:
                msgs.append(f"{name}: {msg}")
        ok, msg = rr.compare_summary(gold / "run_summary.json", out / "run_summary.json")
        if not ok:
            msgs.append(f"run_summary.json: {msg}")
        verdict = "PASS" if not msgs else "FAIL — " + "; ".join(m[:200] for m in msgs)
    except Exception as e:
        verdict = f"ОШИБКА расчёта: {e}"
    el = time.perf_counter() - t1
    print(f"[{case}] {verdict}; ступень 4: вызовов {stage4_lib.STATS['calls'] - c0}, "
          f"сошлась {stage4_lib.STATS['ok'] - k0}; {el:.0f} с", flush=True)
    shutil.rmtree(out, ignore_errors=True)
shutil.rmtree(OUT, ignore_errors=True)
