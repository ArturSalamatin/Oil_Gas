"""DEBT-027, проба при /issue: pvt_range_warnings на каждом принятом подшаге табличных примеров.

Это и есть «наивный» вариант задачи: диагностика прототипа после каждого
сошедшегося advance. solve адаптера обёрнут в памяти, код пакета не меняется.
Для каждой категории — сколько подшагов, первое время, крайнее значение, и для
'saturated locus above table' — max S_g в газовых ячейках выше наибольшего p_b
(≈ 0 — ячейка фронта, предупреждение ложное).
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\scan_examples.py [имя_примера ...]
"""
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.units import BAR_TO_PA
import gpn_multiphase_solver

from radial_blackoil.state import BlackOilState
from radial_blackoil.diagnostics import pvt_range_warnings

logging.getLogger("gpn_multiphase_solver").setLevel(logging.WARNING)

SOLVER = Path.cwd()
print("пакет:", Path(gpn_multiphase_solver.__file__).parent, flush=True)

names = sys.argv[1:]
cfgs = sorted((SOLVER / "examples").glob("*/config.json"))
for cfg in cfgs:
    if names and cfg.parent.name not in names:
        continue
    if json.loads(cfg.read_text(encoding="utf-8"))["pvt"].get("model") != "table":
        continue
    config = load_config(cfg)
    sim, state0 = SimulatorFactory.from_config(config)
    hydro = sim._hydro
    model = hydro._model
    pb_max = model.pvt.pb[-1] * BAR_TO_PA
    stats = {}          # категория → [число подшагов, первое t, пример текста]
    sg_front = [0.0]    # max S_g газовых ячеек выше max p_b
    n_steps = [0]
    orig = hydro.solve

    def solve(state, dt, bc, _orig=orig):
        res = _orig(state, dt, bc)
        s = res.state
        n_steps[0] += 1
        proto = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                              sg=s.Sg.copy(), gas_active=(s.regime == 1))
        for w in pvt_range_warnings(model, proto):
            key = w.split(":", 1)[0]
            st = stats.setdefault(key, [0, s.t, w])
            st[0] += 1
        j = (s.regime == 1) & (s.p > pb_max)
        if np.any(j):
            sg_front[0] = max(sg_front[0], float(np.max(s.Sg[j])))
        return res

    hydro.solve = solve
    t0 = time.perf_counter()
    try:
        sim.run(state0)
        status = "ok"
    except RuntimeError as e:
        status = f"отказ: {str(e)[:80]}"
    print(f"\n=== {cfg.parent.name}: {status}, принятых подшагов {n_steps[0]}, "
          f"{time.perf_counter() - t0:.0f} с ===", flush=True)
    if not stats:
        print("   предупреждений нет")
    for key, (n, t_first, w) in stats.items():
        print(f"   {n:6d} подшагов, впервые t = {t_first / 86400:.4g} сут: {w}")
    if "OIL_PVT saturated locus above table" in stats:
        print(f"   max S_g газовых ячеек выше max p_b = {pb_max / 1e6:g} МПа: {sg_front[0]:.3e}")
