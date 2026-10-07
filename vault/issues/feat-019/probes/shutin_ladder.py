"""FEAT-019: проходится ли останов из развитой газовой зоны лестницей шагов.

Добыча n_prod суток по конфигу примера, затем останов (p_wf = p_ext) одиночными
model.advance прототипа: первый шаг dt0, после успеха шаг ×grow (не больше
dt_max), после отказа ÷2 (как simulate_schedule прототипа, simulation.py).
Печатает последовательность принятых шагов и отказов, p[0], max S_g, число
двухфазных ячеек — до n_shut суток останова.

Вопрос: хватит ли ступенчатой записи истории (FEAT-018: мелкие интервалы сразу
после останова) или нужен исправленный решатель.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-019\\probes\\shutin_ladder.py 20 10 10 [dt0] [grow]
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

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling"}
base_key, n_prod, n_shut = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
dt0 = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
grow = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
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
h = sim.run(init)
model = sim._hydro._model
p_ext = cfg.initial_conditions.p0

from radial_blackoil.state import BlackOilState  # noqa: E402

s = h.states[-1]
ps = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                   sg=s.Sg.copy(), gas_active=(s.regime == 1))
model.set_bhp_control(p_ext / BAR_TO_PA)
pb_bar = None

t, dt, t_end = 0.0, dt0, n_shut * DAY
acc, rej = [], 0
t1 = time.perf_counter()
print(f"=== {BASES[base_key]}: останов после {n_prod} сут; dt0 = {dt0:.0f} с, рост ×{grow} ===")
print(f"старт: p[0] = {ps.pressure_bar[0]:.2f} бар, max S_g = {ps.sg.max():.4f}, "
      f"2ф = {int(np.count_nonzero(ps.gas_active))}")
while t < t_end - 1e-6:
    step = min(dt, t_end - t)
    new, rep = model.advance(ps, step)
    if rep.converged:
        ps, t = new, t + step
        acc.append(step)
        if len(acc) <= 12 or len(acc) % 10 == 0 or t >= t_end - 1e-6:
            print(f"  ✓ t = {t/3600:9.3f} ч  dt = {step:9.1f} с  it = {rep.iterations:2d}  "
                  f"p[0] = {ps.pressure_bar[0]:7.2f} бар  maxSg = {ps.sg.max():.4f}  "
                  f"2ф = {int(np.count_nonzero(ps.gas_active))}")
        dt = min(step * grow, DAY)
    else:
        rej += 1
        print(f"  ✗ t = {t/3600:9.3f} ч  dt = {step:9.1f} с  it = {rep.iterations:2d}  res = {rep.residual_inf:.1e}")
        dt = step / 2.0
        if dt < 1e-3:
            print("  шаг < 1 мс — стоп")
            break
print(f"итог: {t/DAY:.3f} сут за {len(acc)} принятых шагов и {rej} отказов "
      f"({time.perf_counter() - t1:.1f} с); последний шаг {acc[-1] if acc else 0:.0f} с")
