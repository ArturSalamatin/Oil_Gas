"""DEBT-027, проба при /plan-improve: 'saturated locus above table' в эталонных кейсах регрессии прототипа — ложное или настоящее?

Эталон (regression/golden/*/run_summary.json) у 16 кейсов из 17 записывает ровно это
предупреждение, а run_regression.py сравнивает текст предупреждений с эталоном. Проба
прогоняет прототип штатным run_workbook на входах кейсов; pvt_range_warnings в
simulation.py подменён обёрткой (в памяти): на каждом принятом шаге — max S_g газовых
ячеек с p выше наибольшего p_b таблицы. S_g ~ 0 — ячейка фронта, предупреждение ложное.
Выходы прототипа — в OUTPUT/DEBT027_<кейс> (игнорируется git), удаляются после кейса.
Запуск из numerical_solver/HydroSolverPrototype/Prototype_1.0.3:
  ..\\..\\.venv\\Scripts\\python ..\\..\\..\\vault\\issues\\debt-027\\probes\\golden_locus_cases.py [кейс ...]
"""
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import radial_blackoil
import radial_blackoil.simulation as simulation
from radial_blackoil.runner import run_workbook

print("прототип:", Path(radial_blackoil.__file__).parent, flush=True)
REG = ROOT / "regression"
MAIN = ['T00', 'T01', 'T02', 'T03', 'T04', 'T06', 'T07', 'T08c', 'T09', 'T10', 'T11']
T05 = ['T05S_N050_DT5m', 'T05S_N100_DT5m', 'T05S_N200_DT5m',
       'T05T_N100_DT60m', 'T05T_N100_DT10m', 'T05T_N100_DT3m']
cases = sys.argv[1:] or MAIN

orig = simulation.pvt_range_warnings
for case in cases:
    inp = REG / "inputs" / ("T05/" + case if case in T05 else case)
    inp = inp.with_suffix(".xlsx")
    stat = {"n": 0, "sg_max": 0.0, "p_max": 0.0, "steps": 0}

    def wrapped(model, state, _stat=stat):
        _stat["steps"] += 1
        ga = np.asarray(state.gas_active, bool)
        p = np.asarray(state.pressure_bar, float)
        j = ga & (p > model.pvt.pb[-1] + 1e-9 * max(1.0, abs(float(model.pvt.pb[-1]))))
        if np.any(j):
            _stat["n"] += 1
            _stat["sg_max"] = max(_stat["sg_max"], float(np.max(np.asarray(state.sg)[j])))
            _stat["p_max"] = max(_stat["p_max"], float(np.max(p[j])))
        return orig(model, state)

    simulation.pvt_range_warnings = wrapped
    out = ROOT / "OUTPUT" / f"DEBT027_{case}"
    t0 = time.perf_counter()
    s = run_workbook(inp, out)
    shutil.rmtree(out, ignore_errors=True)
    locus = [w for w in s["warnings"] if w.startswith("OIL_PVT saturated locus above")]
    other = [w.split(":", 1)[0] for w in s["warnings"] if not w.startswith("OIL_PVT saturated locus above")]
    print(f"{case:16s} {s['status']}, {time.perf_counter() - t0:5.0f} с: вызовов диагностики {stat['steps']}, "
          f"из них с газом выше max p_b {stat['n']}; max S_g там {stat['sg_max']:.3e}, max p {stat['p_max']:.5f} бар; "
          f"locus above в сводке: {'да' if locus else 'нет'}; прочие: {other or 'нет'}", flush=True)
simulation.pvt_range_warnings = orig
