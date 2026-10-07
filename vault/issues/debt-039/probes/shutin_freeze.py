"""DEBT-039: почему невязка баланса массы примера 16 растёт линейно после 20 сут.

Гипотеза: у Ньютона прототипа допуск atol_sm3s = 1e-11 м3ст/с на ячейку
(blackoil.py, _newton_fixed_active_set). Когда невязка начального
приближения (старого состояния) ниже допуска, шаг принимается без
итераций — состояние не меняется, а потоки через контур (на этом же
состоянии) не нулевые и копятся. Невязка баланса растёт на dt*(G[N]-G[0]) за шаг.

Печатает по записям после конца добычи: max|dp| к прошлой записи, число
итераций Ньютона на подшагах интервала, приращение интеграла потока через
контур, приращение запаса нефти.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-039\\probes\\shutin_freeze.py
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import planned_code_check as pc  # noqa: E402

cfg = pc.load_config(pc.EX / "16_well_shut_in" / "config.json")
cfg.output.log_level = "WARNING"
sim, init = pc.build(cfg, True)
model = sim._hydro._model
iters = []
real = model.advance


def counting(ps, dt, *a, **k):
    new, rep = real(ps, dt, *a, **k)
    iters.append((dt, rep.iterations))
    return new, rep


model.advance = counting
marks = []
real_run_step = sim._advance


h = sim.run(init)
bal = pc.compute_mass_balance(h)
t = np.array(h.times) / 86400.0
k15 = int(np.argmin(np.abs(t - 15.0)))
# Подшаги по времени: восстанавливаем, к какой записи относится каждый вызов advance
cum_t = np.cumsum([d for d, _ in iters])
print(f"вызовов advance {len(iters)}; итераций 0 у {sum(1 for _, n in iters if n == 0)}")
print(f"{'запись':>6} {'t, сут':>7} {'max|dp|, Па':>12} {'итер. (0/всего)':>15} "
      f"{'d приток_o':>11} {'d dM_o':>11} {'d невязка_o':>12}")
for k in range(k15, len(h.times)):
    dp = np.max(np.abs(h.states[k].p - h.states[k - 1].p))
    sel = (cum_t > h.times[k - 1] + 1e-6) & (cum_t <= h.times[k] + 1e-6)
    its = [n for (_, n), s in zip(iters, sel) if s]
    print(f"{k:6d} {t[k]:7.3f} {dp:12.4e} {sum(1 for n in its if n == 0):6d}/{len(its):<8d} "
          f"{bal['inflow_o'][k] - bal['inflow_o'][k - 1]:+11.3e} "
          f"{bal['dM_o'][k] - bal['dM_o'][k - 1]:+11.3e} "
          f"{bal['residual_o'][k] - bal['residual_o'][k - 1]:+12.3e}")
