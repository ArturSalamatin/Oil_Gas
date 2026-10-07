"""BUG-021: давление у забоя 13b к концу первого часа после первого скачка p_wf вверх (README: 10.78–10.79 МПа).

История конфига 13b заменена двумя интервалами: сутки при 6 МПа (24 подшага по 3600 с — те же шаги,
что у штатных двух интервалов по 12), затем час при 10.75 МПа. Запись 2 — конец этого часа.
Сначала текущий код, затем вариант 2.

Запуск — из каталога numerical_solver: .venv\\Scripts\\python <P>\\hour1_13b.py
"""
import copy
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(HERE))
logging.disable(logging.INFO)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def run():
    cfg = load_config(SOLVER_ROOT / "examples" / "13b_pwf_alternating" / "config.json")
    cfg.output.log_level = "ERROR"
    day, up = copy.deepcopy(cfg.time.history[0]), copy.deepcopy(cfg.time.history[2])
    day.dt, up.dt = 86400.0, 3600.0
    cfg.time.history = [day, up]
    sim, init = SimulatorFactory.from_config(cfg)
    h = sim.run(init)
    return h.states[1].p[0], h.states[2].p[0]


a = run()
import planned_code  # noqa: E402
planned_code.apply(2)
b = run()
print(f"p у забоя, МПа: 1 сут {a[0] / 1e6:.4f} -> {b[0] / 1e6:.4f}; 1 сут + 1 ч {a[1] / 1e6:.4f} -> {b[1] / 1e6:.4f} "
      f"(Δ = {b[1] - a[1]:.0f} Па)")
