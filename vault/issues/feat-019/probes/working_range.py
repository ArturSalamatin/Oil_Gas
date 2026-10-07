"""FEAT-019: рабочий диапазон рисунков PVT и ОФП — по конечному состоянию и по всей истории.

relperm_plot.py (plot_relperm, report_relperm) и pvt_plot.py (plot_pvt,
report_pvt) берут диапазон из history.states[-1]. Решение пользователя
2026-10-03: брать по всей истории. Проба считает все примеры (и пробный
конфиг 16) и печатает оба диапазона, число узлов таблицы PVT в диапазоне и
признак two_phase у relperm — чтобы знать, какие README и тесты меняются.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-019\\probes\\working_range.py
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
import pvt_plot  # noqa: E402

EX = SOLVER / "examples"
names = sorted(d.name for d in EX.iterdir() if d.is_dir() and d.name[0].isdigit())
configs = [(n, EX / n / "config.json") for n in names] + [("16 (проба)", HERE / "cfg_16" / "config.json")]

print(f"{'пример':26s} | {'p конец, МПа':>19s} | {'p история, МПа':>19s} | узлы к/и | "
      f"{'S_g max конец':>13s} {'S_g max ист.':>12s} {'S_g min к/и':>15s} | 2ф к/и")
for name, path in configs:
    cfg = load_config(path)
    cfg.output.log_level = "ERROR"
    t0 = time.perf_counter()
    sim, init = SimulatorFactory.from_config(cfg)
    h = sim.run(init)
    el = time.perf_counter() - t0
    fin = h.states[-1]
    p_all = np.concatenate([s.p for s in h.states])
    sg_all = np.concatenate([s.Sg for s in h.states])
    pk = (float(fin.p.min()), float(fin.p.max()))
    pi = (float(p_all.min()), float(p_all.max()))
    pvt = sim._energy._pvt
    nodes = pvt_plot._pvt_table_nodes(pvt, float(cfg.initial_conditions.Rs0))
    nk = pvt_plot._nodes_in_range(nodes, *pk)
    ni = pvt_plot._nodes_in_range(nodes, *pi)
    sk, si = float(fin.Sg.max()), float(sg_all.max())
    smk, smi = float(fin.Sg.min()), float(sg_all.min())
    flag = "" if (abs(sk - si) < 1e-12 and abs(pk[0] - pi[0]) < 1.0 and abs(pk[1] - pi[1]) < 1.0) else "  ←"
    print(f"{name:26s} | {pk[0]/1e6:8.4f} … {pk[1]/1e6:8.4f} | {pi[0]/1e6:8.4f} … {pi[1]/1e6:8.4f} | "
          f"{nk:3d}/{ni:<3d} | {sk:13.6f} {si:12.6f} {smk:7.4f}/{smi:<7.4f} | "
          f"{int(sk > 1e-12)}/{int(si > 1e-12)}  ({el:.0f} с){flag}")
