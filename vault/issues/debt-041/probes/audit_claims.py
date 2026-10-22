"""DEBT-041, аудит: проверка утверждений нового комментария NumericsConfig.max_retries.

k = max log2(n_substeps) по всем вызовам hydro.solve прогона (метод — max_retries_probe.py). Проверяются:
  1) пример 03, N = 75, p_wf = 6 МПа (сценарий DEBT-007, test_factory_standing_hydro.py) — «не дробится»;
  2) пример 04a, N = 80 (отложенный критерий BUG-003, test_examples.py) — «не дробится»;
  3) пример 04, рабочая сетка, точки таблицы README 04 — «не больше 5 удвоений»; числа таблицы README 04
     (DEBT-041 правит её по этому выводу) и строка под ней: при 8 МПа N = 100, 150, 200 без дробления.
Лимит — из конфига примера (04a: 12, остальные — умолчание 9); k от лимита не зависит, пока лимит >= k.

Запуск — из каталога numerical_solver: .venv\\Scripts\\python <P>\\audit_claims.py
"""
import logging
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
logging.disable(logging.INFO)

import gpn_multiphase_solver  # noqa: E402
import radial_blackoil  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EX = SOLVER_ROOT / "examples"
DAY = 86400.0


def k_of_run(name, N=None, pwf_MPa=None):
    """Полный прогон; (k, число вызовов, места дробления, время)."""
    cfg = load_config(EX / name / "config.json")
    cfg.output.log_level = "ERROR"
    if N is not None:
        cfg.grid.N = N
    if pwf_MPa is not None:
        for iv in cfg.time.history:
            iv.p_wf = pwf_MPa * 1e6
    sim, init = SimulatorFactory.from_config(cfg)
    calls = []
    orig = sim._hydro.solve

    def logged(state, dt, bc):
        res = orig(state, dt, bc)
        calls.append((state.t / DAY, res.n_substeps))
        return res

    sim._hydro.solve = logged
    t0 = time.perf_counter()
    sim.run(init)
    split = [(t, n) for t, n in calls if n > 1]
    return int(np.log2(max(n for _, n in calls))), len(calls), split, time.perf_counter() - t0, cfg


head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
# Какой код считается: в worktree пакет и прототип обязаны быть из worktree (cwd), а не из основного каталога
print(f"HEAD {head}\nпакет: {gpn_multiphase_solver.__file__}\nпрототип: {radial_blackoil.__file__}", flush=True)
for name, N, pwf in [("03_standing_corey", 75, 6.0), ("04a_high_gas_saturation", 80, None)] + \
        [("04_table_table", None, p) for p in (14.0, 12.0, 10.0, 8.0, 6.0, 4.0, 3.0, 2.0, 1.0, 0.5)] + \
        [("04_table_table", N, 8.0) for N in (100, 150, 200)]:  # README 04: «при 8 МПа ... N = 100, 150, 200»
    k, n, split, wall, cfg = k_of_run(name, N, pwf)
    where = ", ".join(f"t = {t:.4f} сут: {m}" for t, m in split[:4]) or "нигде"
    print(f"{name} N={cfg.grid.N} p_wf={pwf} (лимит {cfg.numerics.max_retries}): k = {k}; "
          f"вызовов {n}; дробится {where}; {wall:.1f} с", flush=True)
