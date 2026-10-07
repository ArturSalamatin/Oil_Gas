"""BUG-016: минимально достаточный max_retries первого шага — таблицы README 03 и 04.

Первый шаг истории через адаптер при max_retries = 14; подшагов 2^k -> нужно k
удвоений. Код — дерево $env:BUG016_NS / $env:PYTHONPATH (без патча: реализация).
Запуск: python <этот файл> <пример> <N> <p_wf МПа,...>
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402  (только patch.NS и путь к прототипу; install не вызывается)
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

name, N = sys.argv[1], int(sys.argv[2])
pwfs = [float(x) for x in sys.argv[3].split(",")]
print(f"{name}, N = {N}; radial_blackoil: {Path(patch.bo.__file__).resolve()}")
for pwf in pwfs:
    cfg = load_config(patch.NS / "examples" / name / "config.json")
    cfg.grid.N = N
    cfg.numerics.max_retries = 14
    for iv in cfg.time.history:
        iv.p_wf = pwf * 1e6
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    t0 = time.perf_counter()
    try:
        res = sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
        n = res.n_substeps
        out = f"подшагов {n:5d} -> max_retries {int(round(np.log2(n)))}"
    except RuntimeError as e:
        out = f"ОТКАЗ: {str(e)[:50]}"
    print(f"  p_wf = {pwf:5.2f} МПа: {out}  ({time.perf_counter() - t0:.1f} с)", flush=True)
