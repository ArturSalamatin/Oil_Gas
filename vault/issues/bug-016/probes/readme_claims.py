"""BUG-016: утверждения README 11 и 12 о режимах, которые «не сходятся», — с правкой.

  12: dt_integration = 86400 с (README 12: «не сходится и после 512 подшагов»);
  11: p0 = 15.2 МПа (README 11: «не сходится после 512 подшагов», max_retries = 9).

Запуск (из numerical_solver основного каталога): python <этот файл> <режим> [cap] [chop]
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

mode = sys.argv[1]
cap = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "-" else None
chop = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
patch.install(mode, cap=cap, chop=chop)
EX = patch.NS / "examples"


def attempt(label, cfg):
    for k in list(patch.COUNT):
        patch.COUNT[k] = 0
    t0 = time.perf_counter()
    try:
        sim, init = SimulatorFactory.from_config(cfg)
        h = sim.run(init)
        w = h.well_data[-1]
        out = (f"сошёлся: advance {patch.COUNT['advance']}, отказов {patch.COUNT['failed']}, "
               f"третья ступень {patch.COUNT.get('tier3_ok', 0)}; T(r_w) = {h.states[-1].T[0]:.3f} К, "
               f"q_o = {w.q_o_std:.4e}")
    except RuntimeError as e:
        out = f"ОТКАЗ: {str(e)[:60]}"
    print(f"{label:40s} {out}  ({time.perf_counter() - t0:.1f} с)", flush=True)


c12 = load_config(EX / "12_large_drainage_radius" / "config.json")
c12.time.dt_integration = 86400.0
attempt("12, dt_integration = 86400 с", c12)

c11 = load_config(EX / "11_degassing_at_boundary" / "config.json")
c11.initial_conditions.p0 = 15.2e6
c11.numerics.max_retries = 9
attempt("11, p0 = 15.2 МПа, max_retries = 9", c11)
