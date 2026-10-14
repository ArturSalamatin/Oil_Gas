"""DEBT-027, проба при /issue: 'saturated locus above table' — ячейка фронта или настоящий выход за таблицу?

Конфиг VAL-005 (vault/issues/val-005/probes/draft_18, R_s0 = 50 = последняя ветвь,
p_b = 180 бар), первые 24 интервала истории. На каждой записи — газовые ячейки
с p выше наибольшего p_b таблицы: их p, S_g, R_s. Если у всех S_g ≈ 0 и R_s = R_s0 —
предупреждение прототипа ложное: ячейка на фронте, обрезка R_s^sat на R_s0 ничего не меняет.
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\front_cell_locus.py [config.json]
Аргумент — другой конфиг (аудит: examples/18_prototype_input/config.json).
"""
import sys
from pathlib import Path

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.units import BAR_TO_PA
import gpn_multiphase_solver

SOLVER = Path.cwd()
print("пакет:", Path(gpn_multiphase_solver.__file__).parent)
CONFIG = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else
          SOLVER.parent / "vault" / "issues" / "val-005" / "probes" / "draft_18" / "config.json")
print("конфиг:", CONFIG)

config = load_config(CONFIG)
config.time.history = config.time.history[:24]
sim, state0 = SimulatorFactory.from_config(config)
history = sim.run(state0)

pb_max = sim._hydro._model.pvt.pb[-1] * BAR_TO_PA
print(f"t_end = {history.times[-1] / 86400:g} сут, max p_b таблицы = {pb_max / 1e6:g} МПа")
n_hit = 0
sg_max = 0.0
for t, s in zip(history.times, history.states):
    j = np.flatnonzero((s.regime == 1) & (s.p > pb_max))
    if j.size:
        n_hit += 1
        sg_max = max(sg_max, float(np.max(s.Sg[j])))
        if n_hit <= 3:
            print(f"t = {t / 3600:g} ч: j = {j.tolist()}, p = {(s.p[j] / 1e6).round(4).tolist()} МПа, "
                  f"S_g = {s.Sg[j].tolist()}, R_s = {s.Rs[j].round(6).tolist()}")
print(f"записей с такими ячейками: {n_hit} из {len(history.states)}, max S_g в них: {sg_max:.3e}")
