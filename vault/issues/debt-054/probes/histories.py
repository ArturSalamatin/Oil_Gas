"""DEBT-054: истории и тексты отказов до и после правки — побитовое сравнение.

Правка меняет только отчёт Ньютона и тексты отказа: принятые шаги, последовательность
вызовов гидродинамики и истории должны остаться побитово прежними, а каждый новый текст
отказа адаптера — начинаться с прежнего (прежний текст + хвост DEBT-054).

Сценарии — те, где работают затронутые ветви кода: отказы ступеней 1-3 «только по
ячейке» (BUG-018 при N = 350, пример 14), ступень 4 по памяти и её отказы (суточный
останов rs300 из TestDailyShutin), ступень 4 на останове (примеры 16, 17).

Запуск из numerical_solver/ (основного каталога или worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-054\\probes\\histories.py save before
    .venv\\Scripts\\python ..\\vault\\issues\\debt-054\\probes\\histories.py save after
    .venv\\Scripts\\python ..\\vault\\issues\\debt-054\\probes\\histories.py compare
Выход — hist_<сценарий>_<метка>.npz рядом со скриптом (в git не идут).
"""
import copy
import sys
import time
from pathlib import Path

import numpy as np

# Код — из каталога запуска (основной или worktree), а не из установки в общий venv
SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
OUT = Path(__file__).parent

from gpn_multiphase_solver import factory as _factory                  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory              # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError      # noqa: E402
from gpn_multiphase_solver.io.config import load_config                 # noqa: E402
import radial_blackoil                                                   # noqa: E402

print(f"Код: {_factory.__file__}")
print(f"Прототип: {radial_blackoil.__file__}")


def _bug018():
    cfg = load_config(SOLVER / "tests" / "data" / "bug018_rs500" / "config.json")
    cfg.grid.N = 350
    return cfg


def _example(name):
    return lambda: load_config(SOLVER / "examples" / name / "config.json")


def _daily_shutin():
    # TestDailyShutin (tests/test_prototype_phase_switching.py): 10 сут добычи + 3 сут q_oil = 0
    cfg = load_config(SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
    hist = list(cfg.time.history)
    for _ in range(3):
        x = copy.deepcopy(hist[0])
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    return cfg


SCENARIOS = {
    "bug018_n350": _bug018,
    "ex14": _example("14_high_gor_cooling"),
    "ex16": _example("16_well_shut_in"),
    "ex17": _example("17_shut_in_strong_cooling"),
    "daily_shutin": _daily_shutin,
}


def run(name):
    cfg = SCENARIOS[name]()
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    calls, msgs = [], []
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        try:
            r = orig(state, dt, bc)
        except HydroConvergenceError as exc:
            calls.append((state.t, dt, 0.0))
            msgs.append(str(exc))
            raise
        calls.append((state.t, dt, 1.0))
        return r

    sim._hydro.solve = solve
    t0 = time.perf_counter()
    h = sim.run(init)
    out = {f: np.array([getattr(s, f) for s in h.states]) for f in ("p", "Sg", "Rs", "T", "regime")}
    out["t"] = np.array([s.t for s in h.states])
    out["calls"] = np.array(calls, float).reshape(-1, 3)
    out["msgs"] = np.array(msgs, dtype=str)
    print(f"  {name}: {time.perf_counter() - t0:.1f} с, записей {len(h.states)}, "
          f"вызовов гидро {len(calls)}, отказов {len(msgs)}")
    return out


def save(tag):
    for name in SCENARIOS:
        np.savez(OUT / f"hist_{name}_{tag}.npz", **run(name))


def compare():
    ok = True
    for name in SCENARIOS:
        a = np.load(OUT / f"hist_{name}_before.npz")
        b = np.load(OUT / f"hist_{name}_after.npz")
        same = {f: np.array_equal(a[f], b[f]) for f in ("p", "Sg", "Rs", "T", "regime", "t", "calls")}
        ma, mb = list(a["msgs"]), list(b["msgs"])
        prefix = len(ma) == len(mb) and all(y.startswith(x) for x, y in zip(ma, mb))
        good = all(same.values()) and prefix
        ok &= good
        print(f"{name}: {'побитово' if all(same.values()) else 'РАЗЛИЧИЕ ' + str(same)}; "
              f"отказов {len(ma)} -> {len(mb)}, новый текст начинается с прежнего: {prefix}")
        for x, y in zip(ma, mb):
            print(f"    было:  {x}")
            print(f"    стало: {y}")
    print("ИТОГ:", "OK" if ok else "РАСХОЖДЕНИЕ")


if __name__ == "__main__":
    if sys.argv[1:2] == ["save"]:
        save(sys.argv[2])
    elif sys.argv[1:2] == ["compare"]:
        compare()
    else:
        sys.exit(__doc__)
