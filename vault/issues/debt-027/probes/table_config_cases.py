"""DEBT-027, проба при /plan-improve: сценарии будущих тестов на configs/table_pvt (N = 20, таблицы примера 04).

p_wf = 15 (штатный конфиг), 8 и 2 МПа, начальное p0 = 32 МПа при штатном p_wf; 1 сут по 1 ч.
На каждом принятом подшаге — pvt_range_warnings прототипа как есть (без фильтра):
категории, число подшагов, первое время; max S_g газовых ячеек выше max p_b; время расчёта.
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\table_config_cases.py
"""
import logging
import time
from pathlib import Path

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.units import BAR_TO_PA, DAY_TO_S
import gpn_multiphase_solver

from radial_blackoil.state import BlackOilState
from radial_blackoil.diagnostics import pvt_range_warnings, unique_warnings

SOLVER = Path.cwd()
print("пакет:", Path(gpn_multiphase_solver.__file__).parent, flush=True)
CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"

for label, p_wf, p0 in (("штатный", None, None), ("8 МПа", 8e6, None),
                        ("2 МПа", 2e6, None), ("p0 = 32 МПа", None, 32e6)):
    config = load_config(CONFIG)
    if p_wf is not None:
        for h in config.time.history:
            h.p_wf = p_wf
    if p0 is not None:
        config.initial_conditions.p0 = p0
    sim, state0 = SimulatorFactory.from_config(config)
    logging.getLogger("gpn_multiphase_solver").setLevel(logging.WARNING)
    hydro = sim._hydro
    model = hydro._model
    pb_max = model.pvt.pb[-1] * BAR_TO_PA
    stats, sg_front, n = {}, [0.0], [0]
    orig = hydro.solve

    def solve(state, dt, bc, _orig=orig, _stats=stats, _sg=sg_front, _n=n):
        res = _orig(state, dt, bc)
        s = res.state
        _n[0] += 1
        proto = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                              sg=s.Sg.copy(), gas_active=(s.regime == 1))
        for w in unique_warnings(pvt_range_warnings(model, proto)):
            st = _stats.setdefault(w.split(":", 1)[0][:40], [0, s.t])
            st[0] += 1
        j = (s.regime == 1) & (s.p > pb_max)
        if np.any(j):
            _sg[0] = max(_sg[0], float(np.max(s.Sg[j])))
        return res

    hydro.solve = solve
    t0 = time.perf_counter()
    sim.run(state0)
    print(f"\n=== {label}: подшагов {n[0]}, {time.perf_counter() - t0:.2f} с, "
          f"max S_g газа выше max p_b {sg_front[0]:.3e} ===")
    for key, (k, t_first) in stats.items():
        print(f"   {k:3d} подшагов, впервые t = {t_first / DAY_TO_S:.4g} сут: {key}")
    if not stats:
        print("   предупреждений нет")
