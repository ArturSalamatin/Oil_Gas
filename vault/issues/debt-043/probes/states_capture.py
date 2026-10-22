"""DEBT-043, шаги 0 и 7 плана: решение до и после перехода к отклонениям θ.

  capture <метка> — прогнать 03, 16, 21 и сохранить финальные (и все записанные) T, p, Sg
                    в states_<метка>.npz рядом со скриптом;
  compare <a> <b> — сравнить два снимка: p, Sg — побитово (np.array_equal),
                    max|ΔT| по всем записям — должен быть < 1e-9 K.

Код решателя берётся из DEBT043_SOLVER (по умолчанию — numerical_solver основного каталога).
В worktree: $env:DEBT043_SOLVER = "<worktree>\\numerical_solver".

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\states_capture.py capture base
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\states_capture.py capture branch
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\states_capture.py compare base branch
"""

import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EXAMPLES = ["03_standing_corey", "16_well_shut_in", "21_rs100_cooling"]


def capture(tag):
    solver = Path(os.environ.get("DEBT043_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
    for p in (solver, solver / "HydroSolverPrototype" / "Prototype_1.0.3"):
        sys.path.insert(0, str(p))
    import gpn_multiphase_solver
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}")
    out = {}
    for name in EXAMPLES:
        cfg = load_config(solver / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        h = sim.run(init)
        for key in ("T", "p", "Sg"):
            out[f"{name}.{key}"] = np.array([getattr(s, key) for s in h.states])
        print(f"  {name}: записей {len(h.states)}")
    path = HERE / f"states_{tag}.npz"
    np.savez(path, **out)
    print(f"сохранено: {path}")


def compare(a, b):
    A = np.load(HERE / f"states_{a}.npz")
    B = np.load(HERE / f"states_{b}.npz")
    ok = True
    for name in EXAMPLES:
        p_eq = np.array_equal(A[f"{name}.p"], B[f"{name}.p"])
        s_eq = np.array_equal(A[f"{name}.Sg"], B[f"{name}.Sg"])
        dT = float(np.max(np.abs(A[f"{name}.T"] - B[f"{name}.T"])))
        good = p_eq and s_eq and dT < 1e-9
        ok &= good
        print(f"  {name}: p побитово {p_eq}, Sg побитово {s_eq}, max|ΔT| = {dT:.2e} K"
              f" → {'OK' if good else 'ПРОВАЛ'}")
    print("ИТОГ:", "OK" if ok else "ПРОВАЛ")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if sys.argv[1] == "capture":
        capture(sys.argv[2])
    else:
        compare(sys.argv[2], sys.argv[3])
