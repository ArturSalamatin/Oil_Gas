"""BUG-016: прогон всех примеров с правкой прототипа — сохранить историю для сравнения.

Запуск (из numerical_solver основного каталога):
    python <этот файл> <метка> <режим> [cap] [chop] [пример ...]
режим: orig (патч не ставится) | none | always | fallback — см. patch.py.
Результат: regress/<метка>/<пример>.npz и сводка в консоль.
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

label, mode = sys.argv[1], sys.argv[2]
cap = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
chop = float(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != "-" else None
only = sys.argv[5:]
if mode != "orig":
    patch.install(mode, cap=cap, chop=chop)
else:
    # Только счётчики, методы Ньютона — оригинальные
    patch.M.advance = patch.advance

EX = patch.NS / "examples"
out = HERE / "regress" / label
out.mkdir(parents=True, exist_ok=True)
names = only or sorted(d.name for d in EX.iterdir() if d.is_dir() and d.name[0].isdigit())
import gpn_multiphase_solver  # noqa: E402
print(f"{label}: режим {mode}, cap {cap}, chop {chop}")
print(f"  radial_blackoil: {Path(patch.bo.__file__).resolve()}")
print(f"  gpn_multiphase_solver: {Path(gpn_multiphase_solver.__file__).resolve()}")
print(f"  примеры: {EX}")
for name in names:
    for k in list(patch.COUNT):
        patch.COUNT[k] = 0
    cfg = load_config(EX / name / "config.json")
    t0 = time.perf_counter()
    try:
        sim, init = SimulatorFactory.from_config(cfg)
        h = sim.run(init)
    except RuntimeError as e:
        print(f"  {name:28s} ОТКАЗ: {str(e)[:70]}")
        continue
    dt = time.perf_counter() - t0
    S = h.states
    np.savez(out / f"{name}.npz",
             p=np.array([s.p for s in S]), Sg=np.array([s.Sg for s in S]),
             Rs=np.array([s.Rs for s in S]), T=np.array([s.T for s in S]),
             regime=np.array([s.regime for s in S]),
             q_o=np.array([w.q_o_std for w in h.well_data]),
             q_g=np.array([w.q_g_std for w in h.well_data]),
             p_wf=np.array([w.p_wf for w in h.well_data]),
             count=np.array([patch.COUNT["advance"], patch.COUNT["failed"],
                             patch.COUNT["fallback_ok"]]), time=dt)
    c = patch.COUNT
    print(f"  {name:28s} {dt:7.1f} с  advance {c['advance']:6d}  отказов {c['failed']:5d}  "
          f"запасной путь {c['fallback_ok']:4d}  третья ступень {c.get('tier3_ok', 0):4d}")
