"""FEAT-022: хватает ли увеличенного numerics.max_retries для 13б и сколько это стоит.

upstep_diag.py: скачок 6 -> 10.75 МПа сходится только при подшаге ~1 с
(7 с — нет). A-retry дробит шаг 3600 с равномерно на 2**k подшагов, лимит
k = max_retries (по умолчанию 9 -> 7.03 с). Здесь: первые 2 сут 13б
(6, 6, 10.75, 10.75 МПа по 0.5 сут) при max_retries = 10, 11, 12; затем
первые 4 сут при наименьшем сходящемся лимите — время на пару скачков
вверх и вниз.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-022\\probes\\retries_cost.py
"""

import copy
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

BASE = SOLVER / "examples" / "12_large_drainage_radius" / "config.json"


class Counting:
    def __init__(self, inner):
        self._inner, self.dt = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        self.dt.append((sp.t, dt))
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def make_cfg(days, mr):
    cfg = load_config(BASE)
    cfg.output.log_level = "ERROR"
    cfg.numerics.max_retries = mr
    iv = cfg.time.history[0]
    hist = []
    for d in range(1, days + 1):
        for _ in range(2):
            x = copy.deepcopy(iv)
            x.dt, x.p_wf = 43200.0, (6.0e6 if d % 2 == 1 else 10.75e6)
            hist.append(x)
    cfg.time.history = hist
    return cfg


def run(days, mr):
    cfg = make_cfg(days, mr)
    sim, init = SimulatorFactory.from_config(cfg)
    cnt = Counting(sim._energy)
    sim._energy = cnt
    t0 = time.perf_counter()
    try:
        sim.run(init)
        ok = True
    except RuntimeError as e:
        ok = False
        msg = str(e)[:70]
    el = time.perf_counter() - t0
    # Мелкие подшаги по суткам: сутки -> {dt: число}
    by_day = {}
    for t, dt in cnt.dt:
        if dt < 3600.0 - 1e-9:
            d = int(t // 86400) + 1
            by_day.setdefault(d, Counter())[round(dt, 3)] += 1
    print(f"сут = {days}, max_retries = {mr:2d} ({2**mr:5d} подшагов, "
          f"{3600 / 2**mr:6.3f} с): {'OK   ' if ok else 'ОТКАЗ'} за {el:7.1f} с; "
          f"вызовов энергии {len(cnt.dt)}")
    for d, c in sorted(by_day.items()):
        print(f"     сутки {d}: {dict(c)}")
    if not ok:
        print(f"     {msg}")
    return ok


for mr in (10, 11, 12):
    if run(2, mr):
        run(4, mr)
        break
