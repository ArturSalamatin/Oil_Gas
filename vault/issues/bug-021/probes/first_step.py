"""BUG-021: первый шаг конфигураций с замером дробления в README — текущий код против варианта 2.

Конфигурации — те, где README приводит число подшагов первого шага:
03 (N = 150; p_wf = 4, 2, 0.5 МПа: max_retries 1, 4, 9 → 2, 16, 512 подшагов), 04a (N = 300, 500:
2 и 8 подшагов), 05 (p_wf = 5, 4, 2 МПа: 2 подшага). Первый шаг — через адаптер с дроблением
A-retry, как _first_step в tests/test_prototype_globalization.py. Сначала все — на текущем коде,
затем метод подменяется вариантом 2 и всё повторяется.

Запуск — из каталога numerical_solver: .venv\\Scripts\\python <P>\\first_step.py
"""
import logging
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(HERE))
logging.disable(logging.INFO)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EX = SOLVER_ROOT / "examples"
CASES = [("03_standing_corey", 150, 4.0), ("03_standing_corey", 150, 2.0), ("03_standing_corey", 150, 0.5),
         ("04a_high_gas_saturation", 300, None), ("04a_high_gas_saturation", 500, None),
         ("05_standing_table_rp", None, 5.0), ("05_standing_table_rp", None, 4.0), ("05_standing_table_rp", None, 2.0)]


def first_step(name, N, pwf_MPa):
    cfg = load_config(EX / name / "config.json")
    cfg.output.log_level = "ERROR"
    if N is not None:
        cfg.grid.N = N
    if pwf_MPa is not None:
        for iv in cfg.time.history:
            iv.p_wf = pwf_MPa * 1e6
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    t = time.perf_counter()
    try:
        res = sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
        return res.n_substeps, res.state.p.copy(), time.perf_counter() - t
    except RuntimeError as e:
        return f"отказ: {e}", None, time.perf_counter() - t


base = [first_step(*c) for c in CASES]
import planned_code  # noqa: E402
planned_code.apply(2)
new = [first_step(*c) for c in CASES]
for c, (nb, pb, tb), (nn, pn, tn) in zip(CASES, base, new):
    dp = float(np.max(np.abs(pb - pn))) if pb is not None and pn is not None else float("nan")
    print(f"{c[0]} N={c[1]} p_wf={c[2]}: подшагов {nb} -> {nn}; max|Δp| {dp:.3g} Па; {tb:.1f} -> {tn:.1f} с", flush=True)
