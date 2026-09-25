"""Проба аудита BUG-013: числа плана на свежем прогоне примера 02 (3 суток).

Не меняет код проекта. Считает обе формулы асимптоты — текущую (от p[-1])
и исправленную (от p0) — и проверяет утверждения тестов шага 1 плана.

Запуск (из numerical_solver/, как в плане):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-013\\probes\\probe_reference.py
"""

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(EXAMPLES))

import example_runner  # noqa: E402,F401  (подключает прототип radial_blackoil)
import temperature_asymptotics as ta  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

cfg = load_config(EXAMPLES / "02_single_phase_jt" / "config.json")
sim, st0 = SimulatorFactory.from_config(cfg)
t0 = time.time()
history = sim.run(st0)
print(f"02: N = {cfg.grid.N}, расчёт {time.time() - t0:.1f} с")

T0 = cfg.initial_conditions.T0
p0 = cfg.initial_conditions.p0
mu = cfg.thermal.mu_JT_oil
p = history.states[-1].p
T = history.states[-1].T

T_old = ta.single_phase_asymptote(cfg, history)      # текущий код: от p[-1]
T_new = T0 + mu * (p - p0)                            # план: от p0

print(f"mu*(p0 - p[-1])           = {mu * (p0 - p[-1]):.6f} К")
print(f"T[-1] - T0                = {T[-1] - T0:+.6f} К")
print(f"старая: min(T-T_as) все   = {(T - T_old).min():+.6f}   без [-1] = {(T - T_old)[:-1].min():+.6f}")
print(f"новая:  min(T-T_as) все   = {(T - T_new).min():+.6f}")

# Тест 1 плана: подход сверху во всех ячейках + прежняя проверка у забоя.
gap_well = T[0] - T_new[0]
full_swing = T0 - T_new[0]
print(f"gap_well = {gap_well:.4f}, full_swing = {full_swing:.4f}, "
      f"0 < gap < 0.5*swing: {0.0 < gap_well < 0.5 * full_swing}")
print(f"старый тест проходит сейчас: {bool(np.all(T[:-1] >= T_old[:-1] - 1e-9))}")
print(f"новый тест 1 на старом коде падает: {not bool(np.all(T >= T_old - 1e-9))}")

# Тест 2 плана: допуск на сравнение T0 - T_as[-1] с mu*(p0 - p[-1]).
lhs = T0 - T_new[-1]
rhs = mu * (p0 - p[-1])
print(f"|lhs - rhs| = {abs(lhs - rhs):.2e} К, отн. = {abs(lhs - rhs) / rhs:.2e}")
print(f"  pytest.approx(rel=1e-12) прошёл бы: {abs(lhs - rhs) <= 1e-12 * rhs}")
print(f"  pytest.approx(abs=1e-12) прошёл бы: {abs(lhs - rhs) <= 1e-12}")
