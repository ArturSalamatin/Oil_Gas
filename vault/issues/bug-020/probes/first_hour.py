"""BUG-020: первый час останова через адаптер прототипа (A-retry) — заготовка теста.

История: n_prod суточных интервалов добычи (dt_integration конфига), затем один
интервал останова 3600 с (q_oil = 0, min_bhp = 1 атм). Гидро-адаптер дробит
интервал при отказе (2^k подшагов, max_retries конфига). Печать: дробление
первого часа останова, время счёта, состояние в конце часа; со ступенью 4 и без.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\first_hour.py 20 10
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

import os  # noqa: E402

HERE = Path(__file__).resolve().parent
# BUG020_SOLVER — numerical_solver проверяемого дерева (рабочей копии реализации);
# по умолчанию — основной каталог, где лежит проба
SOLVER = Path(os.environ.get("BUG020_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (HERE, SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
import os  # noqa: E402
import stage4_lib  # noqa: E402
import plan_code  # noqa: E402

# BUG020_IMPL=plan — код правки из плана (plan_code.apply), иначе опытная ступень stage4_lib
INSTALL = plan_code.apply if os.environ.get("BUG020_IMPL") == "plan" else stage4_lib.install

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod = sys.argv[1], int(sys.argv[2])
BASE = SOLVER / "examples" / BASES[base_key] / "config.json"


def run(use4):
    cfg = load_config(BASE)
    cfg.output.log_level = "ERROR"
    iv = cfg.time.history[0]
    hist = []
    for _ in range(n_prod):
        x = copy.deepcopy(iv)
        x.dt = DAY
        hist.append(x)
    x = copy.deepcopy(iv)
    x.dt = 3600.0
    x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
    hist.append(x)
    cfg.time.history = hist
    sim, init = SimulatorFactory.from_config(cfg)
    if use4:
        INSTALL(sim._hydro._model)
    calls = []
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        t1 = time.perf_counter()
        r = orig(state, dt, bc)
        calls.append((state.t, dt, r.n_substeps, time.perf_counter() - t1))
        return r

    sim._hydro.solve = solve
    try:
        h = sim.run(init)
        st = h.states[-1]
        tail = f"p0 = {st.p[0]/1e5:.2f} бар, 2ф = {int(np.count_nonzero(st.regime == 1))}"
    except RuntimeError as e:
        tail = f"отказ: {str(e)[:90]}"
    shut = [c for c in calls if c[0] >= n_prod * DAY - 1e-6]
    first = shut[0] if shut else None
    print(f"  ступень 4: {'да' if use4 else 'нет'}; первый час: "
          f"{'подшагов %d, %.1f с' % (first[2], first[3]) if first else '—'}; {tail}")


import gpn_multiphase_solver  # noqa: E402
import radial_blackoil  # noqa: E402

print(f"=== {BASES[base_key]}: {n_prod} сут добычи, затем час останова (q_oil = 0) ===")
print(f"    код: {Path(gpn_multiphase_solver.__file__).parent}, {Path(radial_blackoil.__file__).parent}")
run(False)
run(True)
