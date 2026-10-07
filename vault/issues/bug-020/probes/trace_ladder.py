"""BUG-020: лестница шагов останова с разбором каждого отказа по ступеням advance.

Добыча n_prod суток, затем останов (режим A: p_wf = p_ext; B: q_oil = 0)
лестницей шагов как в feat-019/probes/shutin_ladder.py (первый шаг dt0, рост
×2, отказ — ÷2) до t_end_h часов. Для каждого отказа печатаются все решения
Ньютона при фиксированном наборе фаз: ступень (граница S_g, ветка, норма),
число двухфазных на входе, исход, итерации, невязка, и смена набора фаз между
соседними решениями (+активаций/−деактиваций). Отличает исчерпание набора фаз
(12 итераций с переключениями) от несогласованной ветки скважины (кандидат К3).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\trace_ladder.py 20 10 A 0.5
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod, mode, t_end_h = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
dt0 = float(sys.argv[5]) if len(sys.argv) > 5 else 60.0
BASE = SOLVER / "examples" / BASES[base_key] / "config.json"

cfg = load_config(BASE)
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
hist = []
for _ in range(n_prod):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
cfg.time.history = hist
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
p_ext = cfg.initial_conditions.p0
ps = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                   sg=s.Sg.copy(), gas_active=(s.regime == 1))
if mode == "A":
    model.set_bhp_control(p_ext / BAR_TO_PA)
else:
    model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)

solves = []
_orig = model._newton_fixed_active_set


def recording(z0, state_old, dt_s, gas_active, **kw):
    z, rep = _orig(z0, state_old, dt_s, gas_active, **kw)
    solves.append({"stage": (model._sg_lower_bound, model._well_branch, model._line_search_l2),
                   "mask": gas_active.copy(), "ok": rep.converged, "it": rep.iterations,
                   "res": rep.residual_inf, "p0": float(z[0])})
    return z, rep


model._newton_fixed_active_set = recording


def stage_name(st):
    lo, br, l2 = st
    if lo == -0.05:
        return "исходный"
    return f"{'третья' if l2 else 'запасной'}/{br or '—'}"


t, dt, t_end = 0.0, dt0, t_end_h * 3600.0
n_acc = n_rej = 0
t1 = time.perf_counter()
print(f"=== {BASES[base_key]}: останов, режим {mode}, после {n_prod} сут; до {t_end_h} ч ===")
while t < t_end - 1e-6:
    step = min(dt, t_end - t)
    solves.clear()
    new, rep = model.advance(ps, step)
    if rep.converged:
        ps, t = new, t + step
        n_acc += 1
        print(f"✓ t = {t/3600:7.3f} ч  dt = {step:7.1f} с  p0 = {ps.pressure_bar[0]:7.2f} бар  "
              f"2ф = {int(np.count_nonzero(ps.gas_active))}  решений {len(solves)}  "
              f"ступень принятого: {stage_name(solves[-1]['stage'])}")
        dt = min(step * 2.0, DAY)
        continue
    n_rej += 1
    print(f"✗ t = {t/3600:7.3f} ч  dt = {step:7.1f} с  отчёт: it = {rep.iterations}, res = {rep.residual_inf:.1e}, "
          f"branch = '{rep.well_branch}'")
    prev = None
    for k, sv in enumerate(solves):
        m = sv["mask"]
        if prev is not None and sv["stage"] == prev["stage"]:
            act = int(np.count_nonzero(m & ~prev["mask"]))
            dea = int(np.count_nonzero(~m & prev["mask"]))
            sw = f" (+{act}/−{dea})"
        else:
            sw = ""
        print(f"    {k+1:2d}. {stage_name(sv['stage']):14s} 2ф = {int(np.count_nonzero(m)):3d}{sw:12s} "
              f"{'✓' if sv['ok'] else '✗'} it = {sv['it']:2d} res = {sv['res']:.1e} p0 = {sv['p0']:7.2f}")
        prev = sv
    dt = step / 2.0
    if dt < 1e-3:
        print("шаг < 1 мс — стоп")
        break
print(f"итог: {t/3600:.3f} ч за {n_acc} принятых шагов и {n_rej} отказов ({time.perf_counter() - t1:.1f} с)")
