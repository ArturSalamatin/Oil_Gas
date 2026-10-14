"""BUG-026, аудит 1: ход S_g и R_s забойных ячеек в первый час останова (сценарий VAL-004).

Каждый шаг — интервал истории (как режим octave пробы h0_series.py), поэтому
история хранит состояние после каждого шага. Первый шаг 3600/2**F, 2**j шагов на
ступень удвоения. Проверяет объяснение плана: когда газ уходит из ячейки 0 и
меняется ли R_s(r_w) после этого (приток нефти из ячейки 1).

Запуск из numerical_solver/: .venv\\Scripts\\python P <F> <j>
"""

import copy
import sys
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

HOUR, DAY = 3600.0, 86400.0
F, j = int(sys.argv[1]), int(sys.argv[2])
EX = sys.argv[3] if len(sys.argv) > 3 else None     # пример вместо сценария VAL-004
M = F - j
cfg = load_config(SOLVER_ROOT / "examples" / EX / "config.json" if EX else
                  SOLVER_ROOT / "tests" / "data" / "bug020_rs150" / "config.json")
cfg.output.log_level = "ERROR"
hist = cfg.time.history
K = 15 if EX else 10          # индекс первого интервала останова (добыча: 15 или 10 сут)
if EX:
    assert hist[K].dt == HOUR and hist[K].control == "rate", (hist[K].dt, hist[K].control)
    hist = list(hist[:K + 1])  # добыча + первый час останова
base = [HOUR / 2 ** M] + [HOUR / 2 ** i for i in range(M, 0, -1)]
tail = []
for H in base:
    for _ in range(2 ** j):
        x = copy.deepcopy(hist[K])
        x.dt = H / 2 ** j
        tail.append(x)
cfg.time.history = list(hist[:K]) + tail
cfg.time.dt_after_control_change = None
sim, s0 = SimulatorFactory.from_config(cfg)
h = sim.run(s0)
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}; первый шаг {HOUR / 2 ** F:.4g} с, j = {j}")
t0 = K * DAY
print("t после останова, с | S_g[0] | S_g[1] | R_s[0] | R_s[1] | p[0], бар")
prev_t = -1.0
for t, st in zip(h.times, h.states):
    dt = t - t0
    if dt < -1e-6:
        continue
    # печать — на границах ступеней (каждый 2**j-й шаг) и в начале
    if dt == 0 or abs(np.log2(max(dt, 1e-9) / (HOUR / 2 ** M)) % 1) < 1e-9 or dt >= HOUR - 1e-6:
        if dt - prev_t > 1e-9:
            print(f"{dt:10.4f} | {st.Sg[0]:.4f} | {st.Sg[1]:.4f} | {st.Rs[0]:.4f} | {st.Rs[1]:.4f} | "
                  f"{st.p[0] / 1e5:.3f}")
            prev_t = dt
