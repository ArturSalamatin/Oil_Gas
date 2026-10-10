r"""Аудит BUG-023: есть ли на 22 штатных примерах течение от скважины (Q_α > 0) на внутренних гранях.

План вписывает в docstring теста «на текущих конфигах Φ⁺ ≡ 0 на внутренних гранях» — проверка
по каждому вызову energy.solve (тот же крючок matrix_probe, что у test_matrix_matches_reference).
Запуск из numerical_solver/:
    .venv\Scripts\python ..\vault\issues\bug-023\probes\audit_phi_plus.py
"""
import sys
from pathlib import Path

import numpy as np

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/, не из {SOLVER}")
print("SOLVER =", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER / "tests"))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from test_energy_matrix_examples import ALL_EXAMPLES, EXAMPLES_DIR  # noqa: E402

print(f"{'пример':28s} {'вызовов':>7s} {'граней Q>0':>10s} {'max Q_o>0':>10s} {'max Q_g>0':>10s} "
      f"{'max |Q·Δp| при Q>0':>18s}")
for example in ALL_EXAMPLES:
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)
    stat = {"calls": 0, "faces": 0, "Qo": 0.0, "Qg": 0.0, "QdP": 0.0}

    def probe(a, b, c, d, dt, T_old, T_ref, hydro_result, state_prev, bc, s=stat):
        s["calls"] += 1
        p = hydro_result.state.p
        dp = p[1:] - p[:-1]                       # перепад на внутренних гранях 1..N-1
        for Q, key in ((hydro_result.Q_o, "Qo"), (hydro_result.Q_g, "Qg")):
            Qi = Q[1:-1]
            pos = Qi > 0.0
            if pos.any():
                s["faces"] += int(pos.sum())
                s[key] = max(s[key], float(Qi[pos].max()))
                s["QdP"] = max(s["QdP"], float(np.max(np.abs(Qi[pos] * dp[pos]))))

    simulator._energy.matrix_probe = probe
    simulator.run(initial)
    print(f"{example:28s} {stat['calls']:7d} {stat['faces']:10d} {stat['Qo']:10.2e} {stat['Qg']:10.2e} "
          f"{stat['QdP']:18.2e}", flush=True)
