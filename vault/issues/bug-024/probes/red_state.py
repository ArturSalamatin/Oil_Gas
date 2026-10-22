"""BUG-024: красное состояние регрессионного теста плана — суточный останов на замороженном конфиге.

Сценарий теста: tests/data/bug020_rs300/config.json (копия конфига 20 на 2026-10-06: 10 сут
добычи при 5 МПа, dt_integration = 1 сут, max_retries = 9) + 3 интервала по 1 сут с q_oil = 0,
min_bhp = 1 атм. Код базы — отказ на dt/512; с ограничением шага R_s — проходит.
Аргумент — вариант stage4_variants.py или code. Из numerical_solver:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\red_state.py code satrel
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path.cwd().resolve()   # запуск из numerical_solver проверяемого дерева
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", HERE):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory   # noqa: E402
from gpn_multiphase_solver.io.config import load_config      # noqa: E402
import stage4_variants                                        # noqa: E402

DAY = 86400.0
BAR = 1e5


def scenario():
    cfg = load_config(SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
    cfg.output.log_level = "ERROR"
    hist = list(cfg.time.history)
    for _ in range(3):
        x = copy.deepcopy(hist[0])
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    return cfg


def main(variants):
    log = open(HERE / f"red_state_{'_'.join(variants)}.out.txt", "w", encoding="utf-8")

    def out(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    for v in variants:
        cfg = scenario()
        out(f"[{v}] интервалов {len(cfg.time.history)} ({[h.dt for h in cfg.time.history][:2]}…), "
            f"dt_integration {cfg.time.dt_integration}, max_retries {cfg.numerics.max_retries}, "
            f"newton_cell_tol {cfg.numerics.newton_cell_tol}")
        sim, init = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        if v != "code":
            stage4_variants.install(model, v)
        calls = []
        orig = sim._hydro.solve

        def solve(state, dt, bc):
            shut = state.t >= 10 * DAY - 1e-6
            try:
                r = orig(state, dt, bc)
            except Exception:
                if shut:
                    calls.append((dt, False))
                raise
            if shut:
                calls.append((dt, True))
            return r

        sim._hydro.solve = solve
        t0 = time.perf_counter()
        try:
            h = sim.run(init)
            st = h.states[-1]
            ok = [d for d, c in calls if c]
            out(f"[{v}] ✓ {time.perf_counter() - t0:.1f} с; на останове вызовов {len(calls)}, отказов "
                f"{len(calls) - len(ok)}, принято {len(ok)}, сумма {sum(ok) / DAY:.6f} сут, наименьший "
                f"{min(ok):.2f} с; p(r_w) {st.p[0] / BAR:.4f} бар, T(r_w) {st.T[0]:.4f} К, двухфазных "
                f"{int(np.count_nonzero(st.regime == 1))}, max S_g {st.Sg.max():.4f}")
            out(f"[{v}] принятые подшаги останова, с: {[round(d, 2) for d in ok]}")
        except RuntimeError as e:
            out(f"[{v}] ✗ {time.perf_counter() - t0:.1f} с: {str(e)[:160]}")


if __name__ == "__main__":
    main(sys.argv[1:])
