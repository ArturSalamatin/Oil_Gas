"""DEBT-027, проба при /plan-improve: порог свободного газа для 'saturated locus above table' на настоящем случае (пример 04a).

На каждом принятом подшаге (solve адаптера обёрнут в памяти) — max S_g газовых ячеек
с p выше наибольшего p_b таблицы. Печать: первое время превышения порогов-кандидатов
и max за расчёт. Шум фронта по пробам — до 1.1e-9 (прототип, T01), 1.2e-11 (GPN).
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\free_gas_threshold_04a.py
"""
import logging
from pathlib import Path

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.units import BAR_TO_PA, DAY_TO_S
import gpn_multiphase_solver

SOLVER = Path.cwd()
print("пакет:", Path(gpn_multiphase_solver.__file__).parent, flush=True)
CONFIG = SOLVER / "examples" / "04a_high_gas_saturation" / "config.json"
THRESHOLDS = (1e-9, 1e-6, 1e-4, 1e-3, 1e-2)

config = load_config(CONFIG)
sim, state0 = SimulatorFactory.from_config(config)
logging.getLogger("gpn_multiphase_solver").setLevel(logging.WARNING)
hydro = sim._hydro
pb_max = hydro._model.pvt.pb[-1] * BAR_TO_PA
first = {}
track = {"sg_max": 0.0, "t_max": 0.0, "n": 0}
orig = hydro.solve


def solve(state, dt, bc):
    res = orig(state, dt, bc)
    s = res.state
    track["n"] += 1
    j = (s.regime == 1) & (s.p > pb_max)
    sg = float(np.max(s.Sg[j])) if np.any(j) else 0.0
    if sg > track["sg_max"]:
        track["sg_max"], track["t_max"] = sg, s.t
    for th in THRESHOLDS:
        if sg > th and th not in first:
            first[th] = (s.t, track["n"])
    return res


hydro.solve = solve
sim.run(state0)
print(f"подшагов {track['n']}, max p_b = {pb_max / 1e6:g} МПа")
for th in THRESHOLDS:
    if th in first:
        t, n = first[th]
        print(f"   S_g > {th:g}: впервые t = {t / DAY_TO_S:.5g} сут (подшаг {n})")
    else:
        print(f"   S_g > {th:g}: ни разу")
print(f"   max S_g = {track['sg_max']:.4g} при t = {track['t_max'] / DAY_TO_S:.5g} сут")
