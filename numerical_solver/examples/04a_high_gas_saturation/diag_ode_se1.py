"""Проверка второй причины: ОДУ на ПОЛНОЙ истории (save_every = 1, dt = 300 с).

Если при save_every = 1 ошибка ОДУ падает до уровня примера 04 (~0.02 К),
значит расхождение пунктирных кривых в штатном 04a вызвано именно
прореживанием истории, а не физикой или ошибкой вывода уравнения.

Прогон дорогой: 864 состояния => 864 последовательных solve_ivp.
Поэтому сравниваем только на ранних шагах (24 и 72 подшага = 2 и 6 ч),
этого достаточно, чтобы отделить причину.
"""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]          # numerical_solver/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "examples" / "04_table_table"))
sys.path.insert(0, str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
import temperature_ode as tode

HERE = Path(__file__).parent
config = load_config(HERE / "config.json")
config.output.save_every = 1                        # полная история
sim, st0 = SimulatorFactory.from_config(config)
hist = sim.run(st0)

print("сохранённых состояний:", len(hist.times))
print("шаг истории, с:", hist.times[1] - hist.times[0])

r_c = sim._grid.r_centers
mono = hist.states[-1].Sg <= 1e-12                  # однофазная зона

steps = [24, 72]                                    # 2 ч и 6 ч физического времени
sols = tode.solve_ode_at_steps(hist, config, sim._grid, sim._energy, steps=steps)
Sg = hist.states[-1].Sg
for s in steps:
    r_o, T_o = sols[s]
    d = hist.states[s].T - np.interp(r_c, r_o, T_o)
    i = int(np.argmax(np.abs(d)))
    print(f"  шаг {s:3d}  t = {hist.times[s]:7.0f} c   max|dT| = {np.max(np.abs(d)):.4f} K   "
          f"однофазная зона {np.max(np.abs(d[mono])):.4f} K")
    print(f"      максимум при r = {r_c[i]:.4f} м (ячейка {i}), Sg = {Sg[i]:.4f}; "
          f"dT(r_w) = {d[0]:+.4f} K")
    # Профиль ошибки по первым ячейкам — виден ли рост строго у забоя
    print("      dT по ячейкам 0..7: " + " ".join(f"{v:+.3f}" for v in d[:8]))
