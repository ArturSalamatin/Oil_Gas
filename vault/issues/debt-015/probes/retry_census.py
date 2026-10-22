"""DEBT-015: перепись срабатываний A-retry на всех примерах и цена повторного прохода.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-015\\probes\\retry_census.py [имя_примера ...]

Для каждого примера печатает:
  - число вызовов PrototypeHydroAdapter.solve и сколько из них вернули n_substeps > 1;
  - значения n_substeps (по числу случаев);
  - время пробных шагов с дроблением (включая отказавшие попытки) — t_trial;
  - время гидро в повторном проходе Simulator._advance(allow_subdivision=False) — t_replay;
  - полное время sim.run.
t_replay — то, что убирает вынос A-retry на уровень Simulator: отказавшие
попытки грубого шага платятся при любой схеме, повтор успешной — только при нынешней.
"""

import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np  # noqa: F401  (нужен примерам через пакет)

ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(ROOT / "tests"))
# Прототип подключается через sys.path — как в tests/conftest.py
sys.path.insert(0, str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.simulator import Simulator  # noqa: E402
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter  # noqa: E402
from test_examples import ALL_EXAMPLES, EXAMPLES_DIR  # noqa: E402

# ── Счётчики: сбрасываются перед каждым примером ──
stats = {}
_in_replay = [False]

_orig_solve = PrototypeHydroAdapter.solve
_orig_advance = Simulator._advance


def _solve(self, state, dt, bc):
    t0 = time.perf_counter()
    res = _orig_solve(self, state, dt, bc)
    el = time.perf_counter() - t0
    stats["calls"] += 1
    if _in_replay[0]:
        stats["t_replay"] += el
    elif res.n_substeps > 1:
        stats["t_trial"] += el
        stats["n_sub"][res.n_substeps] += 1
    return res


def _advance(self, state, dt, bc, balance, allow_subdivision=True):
    # Вложенный вызов с allow_subdivision=False — повторный проход интервала
    # после пробного шага с дроблением (simulator.py, механизм BUG-010).
    prev = _in_replay[0]
    _in_replay[0] = not allow_subdivision
    try:
        return _orig_advance(self, state, dt, bc, balance, allow_subdivision)
    finally:
        _in_replay[0] = prev


PrototypeHydroAdapter.solve = _solve
Simulator._advance = _advance


def census(name):
    stats.clear()
    stats.update(calls=0, t_trial=0.0, t_replay=0.0, n_sub=Counter())
    cfg = load_config(EXAMPLES_DIR / name / "config.json")
    sim, initial = SimulatorFactory.from_config(cfg)
    t0 = time.perf_counter()
    sim.run(initial)
    t_run = time.perf_counter() - t0
    n_retry = sum(stats["n_sub"].values())
    subs = ", ".join(f"{k}×{v}" for k, v in sorted(stats["n_sub"].items())) or "—"
    print(f"{name:32s} solve={stats['calls']:6d} retry={n_retry:4d} n_sub: {subs:24s} "
          f"t_trial={stats['t_trial']:7.2f} t_replay={stats['t_replay']:7.2f} "
          f"t_run={t_run:7.2f} c", flush=True)
    return t_run, stats["t_replay"]


if __name__ == "__main__":
    names = sys.argv[1:] or ALL_EXAMPLES
    tot_run = tot_replay = 0.0
    for n in names:
        r, rp = census(n)
        tot_run += r
        tot_replay += rp
    print(f"ИТОГО: t_run={tot_run:.1f} c, t_replay={tot_replay:.1f} c "
          f"({100 * tot_replay / tot_run:.1f} %)")
