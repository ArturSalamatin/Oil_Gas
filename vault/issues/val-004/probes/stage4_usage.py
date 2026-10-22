"""VAL-004 (аудит): какие ступени advance прототипа решают шаги серии теста (k = 4, 5, 6).

Память ступени 4 (DEBT-048, m2s) включается после двух подряд принятых
шагов ступени 4; BUG-024 правит _newton_switching (ступень 4). Если в серии
теста ступень 4 не работает, обе задачи прогонов теста не меняют.

Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\val-004\\probes\\stage4_usage.py
"""

import importlib.util
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("t", HERE / "test_plan_val004.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)   # копия кода плана: sys.path и CFG от numerical_solver/

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def usage(k):
    cfg = load_config(t.CFG)
    cfg.time.history = t._shutin_history(cfg, k)
    sim, s0 = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    orig = model.advance
    c = Counter()

    def adv(state_old, dt_s, *a, **kw):
        new, rep = orig(state_old, dt_s, *a, **kw)
        stage = ("4" if getattr(rep, "phase_switching", False) else
                 "запасные 2-3" if getattr(rep, "fallback", False) or getattr(rep, "globalized", False)
                 else "1")
        c[(stage, bool(rep.converged))] += 1
        return new, rep

    model.advance = adv
    sim.run(s0)
    return c


for k in t.K_SERIES:
    c = usage(k)
    print(f"k={k}: " + ", ".join(f"ступень {s} {'принят' if ok else 'отказ'} ×{n}"
                                 for (s, ok), n in sorted(c.items())), flush=True)
