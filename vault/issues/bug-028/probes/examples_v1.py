"""BUG-028 (/plan-fix): примеры GPN без подмены и с вариантом 1 — истории побитово?

Для каждого примера: прогон штатный (отпечаток истории, время) и с вариантом 1
(отпечаток, время, события — вызовы _advance_phases, где проходов стало больше
max_active_iter, то есть где вариант расходится со штатным). Пакет не правится.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P [имя примера ...]     — без имён: все examples/*/config.json
"""

import hashlib
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(HERE))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
import variant1  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

DAY = 86400.0


def fingerprint(hist):
    """Отпечаток истории: sha256 всех полей всех записей (как ramp_probe.py FEAT-032)."""
    hsh = hashlib.sha256()
    for st in hist.states:
        for f in ("p", "Sg", "Rs", "T"):
            hsh.update(np.ascontiguousarray(getattr(st, f), dtype=float).tobytes())
    return hsh.hexdigest()[:16]


def run(name, v1):
    cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    (variant1.install if v1 else variant1.uninstall)()
    variant1.EVENTS.clear()
    sim, s0 = SimulatorFactory.from_config(cfg)
    base_solve = sim._hydro.solve

    def solve(state, dt, bc):
        # t начала подшага — в события варианта 1
        variant1.CONTEXT["t_day"] = round(state.t / DAY, 6)
        return base_solve(state, dt, bc)

    sim._hydro.solve = solve
    t0 = time.perf_counter()
    try:
        hist = sim.run(s0)
        fp = fingerprint(hist)
    except RuntimeError as exc:
        fp = f"ОТКАЗ: {str(exc)[:120]}"
    finally:
        variant1.uninstall()
    return fp, time.perf_counter() - t0, list(variant1.EVENTS)


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    names = sys.argv[1:] or sorted(p.parent.name for p in (SOLVER_ROOT / "examples").glob("*/config.json"))
    for name in names:
        fp0, t_0, _ = run(name, False)
        fp1, t_1, ev = run(name, True)
        same = "побитово" if fp0 == fp1 else "РАЗЛИЧАЮТСЯ"
        print(f"{name}: {same}; штатный {fp0} {t_0:.1f} с, вариант 1 {fp1} {t_1:.1f} с, "
              f"событий {len(ev)}", flush=True)
        for e in ev[:5]:
            print(f"    {e}", flush=True)
        if len(ev) > 5:
            print(f"    … ещё {len(ev) - 5}; последнее {ev[-1]}", flush=True)


if __name__ == "__main__":
    main()
