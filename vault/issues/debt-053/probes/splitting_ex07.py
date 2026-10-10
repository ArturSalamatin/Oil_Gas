"""DEBT-053, план: дробится ли шаг примера 07 на dt из test_dt_convergence.

test_dt_convergence.py:35 утверждает: при dt = 1200, 720, 450, 400 с
(n_sub = 3, 5, 8, 9) «срабатывает A-retry». Замер был до DEBT-015
(локальное дробление), BUG-016, BUG-020, BUG-021 (сняли дробление в
11, 12, 13b, 16). Проверяем на текущем коде: та же постановка, что
_run_first_interval теста (первый интервал истории, штатная сетка),
плюс обёртка-счётчик вызовов энергии — как _CountingEnergySolver
в tests/test_energy_matrix_examples.py.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-053\\probes\\splitting_ex07.py
"""
import copy
import sys
from pathlib import Path

# Пакет — из рабочего каталога (numerical_solver/ основного каталога или
# worktree), прототип — рядом с ним; путь печатается для контроля.
SOLVER = Path.cwd()
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
for p in (str(SOLVER), str(PROTO)):
    if p not in sys.path:
        sys.path.insert(0, p)

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

print(f"пакет: {Path(gpn_multiphase_solver.__file__).parent}")

CONFIG = SOLVER / "examples" / "07_degassing_adiabatic_only" / "config.json"
# Те же списки, что в tests/test_dt_convergence.py:32-37
DT_LIST = [1800.0, 1200.0, 900.0, 720.0, 600.0, 450.0, 400.0, 360.0]
DT_WITH_RETRY = [1200.0, 720.0, 450.0, 400.0]


class CountingEnergy:
    """Делегирует настоящему решателю энергии, запоминает dt каждого вызова."""

    def __init__(self, inner):
        self._inner = inner
        self.dt_calls: list[float] = []

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        self.dt_calls.append(dt)
        return self._inner.solve(hydro_result, state_prev, dt, bc, collect)


def run(dt_integration: float) -> tuple[int, int, float]:
    """Первый интервал при заданном dt -> (шагов по расписанию, вызовов энергии, наименьший dt)."""
    cfg = copy.deepcopy(load_config(CONFIG))
    cfg.output.log_level = "ERROR"
    cfg.time.dt_integration = float(dt_integration)
    cfg.time.history = cfg.time.history[:1]
    simulator, initial = SimulatorFactory.from_config(cfg)
    counter = CountingEnergy(simulator._energy)
    simulator._energy = counter
    simulator.run(initial)
    n_steps = round(cfg.time.history[0].dt / dt_integration)
    return n_steps, len(counter.dt_calls), min(counter.dt_calls)


print(f"интервал: {load_config(CONFIG).time.history[0].dt:g} с")
print(f"{'dt, с':>8} {'n_sub':>6} {'вызовов':>8} {'min dt, с':>10}  дробление  в DT_WITH_RETRY")
for dt in DT_LIST:
    n_steps, n_calls, dt_min = run(dt)
    split = n_calls > n_steps
    print(f"{dt:8g} {n_steps:6d} {n_calls:8d} {dt_min:10.4g}  "
          f"{'да' if split else 'нет':>9}  {'да' if dt in DT_WITH_RETRY else ''}")
