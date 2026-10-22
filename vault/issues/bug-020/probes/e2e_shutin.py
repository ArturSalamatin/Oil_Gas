"""BUG-020: сквозной расчёт через Simulator — добыча n_prod сут, затем останов n_shut сут.

История: n_prod суточных интервалов при p_wf примера, затем n_shut суточных
интервалов останова (A: p_wf = p_ext; B: q_oil = 0, min_bhp = 1 атм).
Гидродинамика — адаптер прототипа с A-retry, как в примерах; stage4 = 1 —
прототип с опытной четвёртой ступенью (stage4_lib.install), 0 — штатный.
Печать: время счёта, дробление по суткам, итог, баланс масс по шагам прототипа.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\e2e_shutin.py 20 10 3 B 1 900
"""

import copy
import sys
import time
from collections import Counter
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
PLAN = os.environ.get("BUG020_IMPL") == "plan"

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod, n_shut, mode = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
use4 = sys.argv[5] == "1"
wall = float(sys.argv[6]) if len(sys.argv) > 6 else 1e9
dt_int_arg = float(sys.argv[7]) if len(sys.argv) > 7 else None
BASE = SOLVER / "examples" / BASES[base_key] / "config.json"

cfg = load_config(BASE)
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
p_ext = cfg.initial_conditions.p0
hist = []
for _ in range(n_prod):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
for _ in range(n_shut):
    x = copy.deepcopy(iv)
    x.dt = DAY
    if mode == "A":
        x.control, x.p_wf = "pressure", p_ext
    else:
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
    hist.append(x)
cfg.time.history = hist
if dt_int_arg is not None:
    cfg.time.dt_integration = dt_int_arg
sim, init = SimulatorFactory.from_config(cfg)
model = sim._hydro._model
if use4:
    (plan_code.apply if PLAN else stage4_lib.install)(model)

# Журнал принятых подшагов: время, dt; баланс масс компонентов прототипа на шаге
rows = []
orig_adv = model.advance
t_wall0 = time.perf_counter()


def rec_advance(state_old, dt_s, *a, **kw):
    if time.perf_counter() - t_wall0 > wall:
        raise TimeoutError("предел времени счёта")
    new, rep = orig_adv(state_old, dt_s, *a, **kw)
    if rep.converged:
        bo, bg = model.step_global_balance(state_old, new, dt_s)
        oi, gi = model.component_inventories(new)
        rows.append({"dt": dt_s, "bo": bo / max(float(np.sum(oi)), 1e-30),
                     "bg": bg / max(float(np.sum(gi)), 1e-30), "p0": float(new.pressure_bar[0]),
                     "n2": int(new.gas_active.sum())})
    return new, rep


model.advance = rec_advance
dt_int = cfg.time.dt_integration
import gpn_multiphase_solver  # noqa: E402
import radial_blackoil  # noqa: E402
print(f"    код: {Path(gpn_multiphase_solver.__file__).parent}, {Path(radial_blackoil.__file__).parent}")
print(f"=== {BASES[base_key]}: {n_prod} сут добычи + {n_shut} сут останова ({mode}); "
      f"ступень 4: {'да' if use4 else 'нет'}; dt_integration = {dt_int:.0f} с, max_retries = {cfg.numerics.max_retries} ===")
try:
    h = sim.run(init)
    status = "✓"
except (RuntimeError, TimeoutError) as e:
    status = f"✗ {str(e)[:160]}"
el = time.perf_counter() - t_wall0
t_cum = np.cumsum([r["dt"] for r in rows]) if rows else np.zeros(1)
t_shut = n_prod * DAY
print(f"итог: {status}; счёт {el:.0f} с; принятых шагов прототипа {len(rows)}; "
      f"достигнуто t = {t_cum[-1]/DAY:.3f} сут")
sh = [(t, r) for t, r in zip(t_cum, rows) if t > t_shut + 1e-6]
if sh:
    dts = Counter(round(r["dt"], 3) for _, r in sh)
    print(f"останов: шагов {len(sh)}; dt подшагов: {dict(sorted(dts.items()))}")
    by_day = Counter(int((t - t_shut - 1e-6) // DAY) + 1 for t, _ in sh)
    print(f"шагов по суткам останова: {dict(sorted(by_day.items()))}")
    r_last = sh[-1][1]
    print(f"в конце: p0 = {r_last['p0']:.2f} бар, 2ф = {r_last['n2']}")
    print(f"баланс масс на шаге (отн. к запасу): нефть max {max(abs(r['bo']) for _, r in sh):.1e}, "
          f"газ max {max(abs(r['bg']) for _, r in sh):.1e}")
if use4 and PLAN:
    print(f"ступень 4 (код плана): вызовов {plan_code.STATS['calls']}, сошлась {plan_code.STATS['ok']}")
elif use4:
    it = stage4_lib.STATS["iters"]
    print(f"ступень 4: вызовов {stage4_lib.STATS['calls']}, сошлась {stage4_lib.STATS['ok']}, "
          f"с доводкой {stage4_lib.STATS['polish']}, итераций медиана {np.median(it) if it else 0:.0f}, "
          f"максимум {max(it) if it else 0}")
