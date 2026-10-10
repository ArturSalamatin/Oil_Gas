"""BUG-024: первые сутки сценария BUG-018 (R_s0 = 500, N = 350, условие по ячейке) при вариантах ступени 4.

Повторяет tests/test_prototype_activation_cap.py::TestFirstStep::test_first_day_with_cell_tol:
на коде базы 86400 с — отказ, Simulator проходит сутки 2 × 43200 с; S_g(r_w) = 0.418464,
p(r_w) = 5.142747 МПа. Аргументы — варианты stage4_variants.py или code; BUG024_DR — параметр.
Из numerical_solver:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\bug018_day.py code satrel rel mix
"""

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = Path.cwd().resolve()   # запуск из numerical_solver проверяемого дерева
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", HERE):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory   # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError   # noqa: E402
from gpn_multiphase_solver.io.config import load_config      # noqa: E402
import stage4_variants                                        # noqa: E402


def main(variants):
    log = open(HERE / f"bug018_day_{'_'.join(variants)}{os.environ.get('BUG024_TAG', '')}.out.txt",
               "w", encoding="utf-8")
    for v in variants:
        cfg = load_config(SOLVER / "tests" / "data" / "bug018_rs500" / "config.json")
        cfg.output.log_level = "ERROR"
        cfg.grid.N = 350
        sim, init = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        if v != "code":
            stage4_variants.install(model, v)
        calls = []
        orig = sim._hydro.solve

        def solve(state, dt, bc):
            try:
                r = orig(state, dt, bc)
            except HydroConvergenceError:
                calls.append((dt, False))
                raise
            calls.append((dt, True))
            return r

        sim._hydro.solve = solve
        t0 = time.perf_counter()
        try:
            st = sim.run(init).states[-1]
            res = f"S_g(r_w) {st.Sg[0]:.6f}, p(r_w) {st.p[0] / 1e6:.6f} МПа"
        except RuntimeError as e:
            res = f"✗ {str(e)[:100]}"
        line = (f"[{v}{' DR=' + os.environ['BUG024_DR'] if os.environ.get('BUG024_DR') else ''}] "
                f"{time.perf_counter() - t0:.1f} с; вызовы {calls}; {res}")
        print(line, flush=True)
        log.write(line + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
