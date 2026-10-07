"""BUG-016: первый шаг истории через адаптер (с дроблением A-retry) — сетка × вариант правки.

Запуск (из numerical_solver основного каталога):
    python <этот файл> <пример> <N,N,...> <вариант,вариант,...> [max_retries]
варианты: orig | fb_l2 | fb_l2_cap03 | fb_chop02 | fb_l2_chop02 | al_l2_cap03 | al_l2
  fb_* — правки только в запасном пути, al_* — всегда; l2 — поиск по ||F||_2,
  capXX — S_g активации <= 0.XX, chopXX — |dS_g| <= 0.XX за итерацию.
Печать: подшагов до успеха (1 — без дробления) или отказ, время.
"""

import copy
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

name = sys.argv[1]
Ns = [int(x) for x in sys.argv[2].split(",")]
variants = sys.argv[3].split(",")
retries = int(sys.argv[4]) if len(sys.argv) > 4 else 9

VAR = {
    "orig": ("none", None, None),
    "fb_l2": ("fallback", None, None),
    "fb_l2_cap03": ("fallback", 0.3, None),
    "fb_chop02": ("fallback", None, 0.2),
    "fb_l2_chop02": ("fallback", None, 0.2),
    "al_l2_cap03": ("always", 0.3, None),
    "al_l2": ("always", None, None),
    "t3_l2_cap03": ("tier3", 0.3, None),
    "t3_l2_chop02": ("tier3", None, 0.2),
}
patch.install("none")
base = load_config(patch.NS / "examples" / name / "config.json")
for N in Ns:
    for v in variants:
        mode, cap, chop = VAR[v]
        patch.CFG.update(mode=mode, cap=cap, chop=chop)
        # fb_chop02 — ограничитель без смены нормы: норма зависит от режима,
        # поэтому отдельный флаг (см. ниже)
        patch.CFG["inf_norm"] = (v == "fb_chop02")
        cfg = copy.deepcopy(base)
        cfg.grid.N = N
        cfg.numerics.max_retries = retries
        sim, init = SimulatorFactory.from_config(cfg)
        _, dt = sim._schedule.substeps(0)
        bc = sim._schedule.intervals[0].bc
        t0 = time.perf_counter()
        try:
            res = sim._hydro.solve(init, dt, bc)
            out = f"подшагов {getattr(res, 'n_substeps', '?')}"
        except RuntimeError:
            out = f"ОТКАЗ (> {2 ** retries} подшагов)"
        print(f"{name} N={N:4d} dt={dt:8.0f} с  {v:13s} {out:28s} {time.perf_counter() - t0:7.1f} с",
              flush=True)
