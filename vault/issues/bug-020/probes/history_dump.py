"""BUG-020: история примера в npz для побитового сравнения деревьев кода.

Пример считается кодом дерева BUG020_SOLVER (по умолчанию — основной каталог);
сохраняются p, Sg, Rs, T, regime, t всех записей и дебиты. Сравнение двух
файлов — ключ --compare.

Запуск (из любого каталога):
    $env:BUG020_SOLVER = "<дерево>\\numerical_solver"
    <python> history_dump.py 16_well_shut_in out.npz
    <python> history_dump.py --compare a.npz b.npz
"""

import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

if sys.argv[1] == "--compare":
    a, b = np.load(sys.argv[2]), np.load(sys.argv[3])
    same = all(np.array_equal(a[k], b[k]) for k in a.files)
    diffs = {k: float(np.max(np.abs(a[k] - b[k]))) for k in a.files if a[k].shape == b[k].shape}
    print(f"побитово: {same}; " + ", ".join(f"max|Δ{k}| = {v:.3e}" for k, v in diffs.items()))
    sys.exit(0)

SOLVER = Path(os.environ.get("BUG020_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

name, out = sys.argv[1], sys.argv[2]
cfg = load_config(SOLVER / "examples" / name / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
t1 = time.perf_counter()
h = sim.run(init)
el = time.perf_counter() - t1
np.savez(out, **{f: np.array([getattr(s, f) for s in h.states]) for f in ("p", "Sg", "Rs", "T", "regime", "t")},
         q_o=np.array([w.q_o_std for w in h.well_data]), q_g=np.array([w.q_g_std for w in h.well_data]))
print(f"{name}: код {Path(gpn_multiphase_solver.__file__).parent}; {len(h.states)} записей, {el:.1f} с → {out}")
