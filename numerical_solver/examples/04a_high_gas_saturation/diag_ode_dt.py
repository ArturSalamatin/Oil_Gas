"""Проверка гипотезы: ОДУ-аналитика 04a использует dt=300, а история прорежена (шаг 3600)."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(r"d:/Lessons/Grants/2026/GPN/Oil_Gas/numerical_solver")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "examples" / "04_table_table"))
sys.path.insert(0, str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
import temperature_ode as tode

HERE = ROOT / "examples" / "04a_high_gas_saturation"
config = load_config(HERE / "config.json")
sim, st0 = SimulatorFactory.from_config(config)
hist = sim.run(st0)

print("сохранённых состояний:", len(hist.times))
print("шаг сохранённой истории, с:", hist.times[1] - hist.times[0])
print("dt_integration в конфиге, с:", config.time.dt_integration)

r_c = sim._grid.r_centers
n = len(hist.times)
steps = sorted({n // 3, 2 * n // 3, n - 1})
print("steps:", steps)

# Однофазная зона: там разгазирования нет, ошибка должна быть заметно меньше,
# если причина расхождения — трактовка фронта, а не общий коэффициент.
mono = hist.states[-1].Sg <= 1e-12
print("ячеек в однофазной зоне:", int(mono.sum()), "из", len(r_c))

for dt_try in (300.0, 3600.0):
    config.time.dt_integration = dt_try
    sols = tode.solve_ode_at_steps(hist, config, sim._grid, sim._energy, steps=steps)
    print(f"\n dt в ОДУ = {dt_try} с")
    for s in steps:
        r_o, T_o = sols[s]
        T_i = np.interp(r_c, r_o, T_o)
        d = hist.states[s].T - T_i
        err = float(np.max(np.abs(d)))
        err1 = float(np.max(np.abs(d[mono])))
        r_max = float(r_c[int(np.argmax(np.abs(d)))])
        print(f"   шаг {s:3d}  t={hist.times[s]:9.0f} c   max|dT| = {err:.4f} K "
              f"при r = {r_max:.3f} м; однофазная зона {err1:.4f} K; "
              f"dT(r_w) = {d[0]:+.4f} K")
