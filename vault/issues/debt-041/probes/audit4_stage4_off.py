"""DEBT-041, аудит раунда 4: что снимает дробление в README 03, 04a, 05 — четвёртая ступень advance (BUG-020)?

Те же точки, что изменились после BUG-020, с выключенной четвёртой ступенью (phase_switching_stage = False
у модели прототипа; фабрика включает её всем примерам, factory.py). Если дробление возвращается к
прежним числам README (03 при 0.5 МПа — 16 подшагов, 04a N = 300 — 2, N = 500 — 8, 05 при 5 МПа — 2),
причина — четвёртая ступень. Только первый шаг: дробится только он.

Запуск — из каталога numerical_solver: .venv\\Scripts\\python <P>\\audit4_stage4_off.py
"""
import logging
import subprocess
import sys
from pathlib import Path

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
logging.disable(logging.INFO)

import gpn_multiphase_solver  # noqa: E402
import radial_blackoil  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EX = SOLVER_ROOT / "examples"
CASES = [("03_standing_corey", 150, 0.5), ("04a_high_gas_saturation", 300, None),
         ("04a_high_gas_saturation", 500, None), ("05_standing_table_rp", None, 5.0)]


def first_step(name, N, pwf_MPa, stage4):
    cfg = load_config(EX / name / "config.json")
    cfg.output.log_level = "ERROR"
    if N is not None:
        cfg.grid.N = N
    if pwf_MPa is not None:
        for iv in cfg.time.history:
            iv.p_wf = pwf_MPa * 1e6
    sim, init = SimulatorFactory.from_config(cfg)
    sim._hydro._model.phase_switching_stage = stage4
    _, dt = sim._schedule.substeps(0)
    return sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc).n_substeps


head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
print(f"HEAD {head}\nпакет: {gpn_multiphase_solver.__file__}\nпрототип: {radial_blackoil.__file__}", flush=True)
for name, N, pwf in CASES:
    on, off = first_step(name, N, pwf, True), first_step(name, N, pwf, False)
    print(f"{name} N={N} p_wf={pwf}: первый шаг — {on} подшагов со ступенью 4, {off} без неё", flush=True)
