"""DEBT-027, проба при /issue: свободный газ выше наибольшего p_b таблицы в примере 04a.

Обход примеров (scan_examples.py) дал в 04a газовые ячейки с p > 15 МПа и S_g до 0.08:
не ячейка фронта. Таблица 04a: ветви R_s = 0 (p_b = 5 МПа) и 30 (p_b = 15 МПа), R_s0 = 30.
Выше 15 МПа R_s^sat обрезан на 30 = R_s0 — газ раствориться не может.
Печать: на записях истории — такие ячейки (j, r, p, S_g, R_s), и S_g этих ячеек во времени.
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\gas_above_pb_04a.py
"""
import logging
from pathlib import Path

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.units import BAR_TO_PA
import gpn_multiphase_solver

SOLVER = Path.cwd()
print("пакет:", Path(gpn_multiphase_solver.__file__).parent, flush=True)
CONFIG = SOLVER / "examples" / "04a_high_gas_saturation" / "config.json"

config = load_config(CONFIG)
logging.getLogger("gpn_multiphase_solver").setLevel(logging.WARNING)
sim, state0 = SimulatorFactory.from_config(config)
history = sim.run(state0)
pb_max = sim._hydro._model.pvt.pb[-1] * BAR_TO_PA
r = sim.grid.r_centers if hasattr(sim.grid, "r_centers") else None
print(f"max p_b = {pb_max / 1e6:g} МПа, S_gc = {config.relperm.S_gc}, записей {len(history.states)}")

for k in (1, 2, len(history.states) // 2, len(history.states) - 1):
    s = history.states[k]
    j = np.flatnonzero((s.regime == 1) & (s.p > pb_max))
    print(f"t = {history.times[k] / 86400:.4g} сут: газовых ячеек выше p_b max — {j.size}")
    if j.size:
        sel = j[np.argsort(-s.Sg[j])][:5]
        for i in sorted(sel):
            rr = f", r = {r[i]:.3f} м" if r is not None else ""
            print(f"   j = {i}{rr}: p = {s.p[i] / 1e6:.4f} МПа, S_g = {s.Sg[i]:.5f}, R_s = {s.Rs[i]:.4f}")
    # Газовая зона целиком: последняя газовая ячейка и её давление
    ga = np.flatnonzero(s.regime == 1)
    if ga.size:
        print(f"   газовая зона: j = {ga.min()}..{ga.max()}, p на её краю {s.p[ga.max()] / 1e6:.4f} МПа, "
              f"S_g на краю {s.Sg[ga.max()]:.5f}; разрывы зоны: {int(np.sum(np.diff(ga) > 1))}")
