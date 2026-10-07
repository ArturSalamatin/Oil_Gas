"""DEBT-041, аудит раунда 4: числа дробления в README 04a и 05 после BUG-020 (включены в DEBT-041 решением пользователя).

README 04a:393 — «первый шаг при штатном max_retries = 9: N <= 200 — без дробления, 300 — 2 подшага, 500 — 8»;
README 05:179-180 — «до 6 МПа без дробления; ниже первый шаг дробится на 2 подшага только при 5 МПа,
при 4, 3 и 2 МПа сходится» (целиком). Четвёртая ступень advance (BUG-020) работает только после отказа
ступеней 1-3, поэтому устареть могли только ненулевые числа. 04a — только первый шаг (как в README),
05 — прогон целиком (k = max log2 n_substeps по всем вызовам hydro.solve, метод max_retries_probe.py).

Запуск — из каталога numerical_solver: .venv\\Scripts\\python <P>\\audit4_other_readmes.py
"""
import logging
import subprocess
import sys
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


def build(name, N=None, pwf_MPa=None):
    cfg = load_config(EX / name / "config.json")
    cfg.output.log_level = "ERROR"
    if N is not None:
        cfg.grid.N = N
    if pwf_MPa is not None:
        for iv in cfg.time.history:
            iv.p_wf = pwf_MPa * 1e6
    return SimulatorFactory.from_config(cfg)


head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
# Какой код считается: в worktree пакет и прототип обязаны быть из worktree (cwd), а не из основного каталога
print(f"HEAD {head}\nпакет: {gpn_multiphase_solver.__file__}\nпрототип: {radial_blackoil.__file__}", flush=True)

# 04a: первый шаг через адаптер с A-retry (лимит из конфига примера — 12)
for N in (80, 150, 200, 300, 500):
    sim, init = build("04a_high_gas_saturation", N=N)
    _, dt = sim._schedule.substeps(0)
    res = sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
    print(f"04a N={N}: первый шаг dt = {dt:.0f} с — {res.n_substeps} подшагов", flush=True)

# 05: прогон целиком, все вызовы гидро
for pwf in (8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0):  # диапазон замера README 05: 8…2 МПа через 1 МПа
    sim, init = build("05_standing_table_rp", pwf_MPa=pwf)
    calls = []
    orig = sim._hydro.solve

    def logged(state, dt, bc, orig=orig, calls=calls):
        res = orig(state, dt, bc)
        calls.append((state.t / 86400.0, res.n_substeps))
        return res

    sim._hydro.solve = logged
    sim.run(init)
    split = [(t, n) for t, n in calls if n > 1]
    k = int(np.log2(max(n for _, n in calls)))
    print(f"05 p_wf={pwf}: k = {k}; вызовов {len(calls)}; дробится "
          f"{', '.join(f't = {t:.4f} сут: {n}' for t, n in split) or 'нигде'}", flush=True)
