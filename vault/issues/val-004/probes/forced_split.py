"""VAL-004 (аудит): локальное дробление на реальном решателе — серия k с отказом первой попытки каждого интервала = серия k+1.

Обёртка sim._hydro.solve бросает HydroConvergenceError на первой попытке
каждого интервала останова (state.t — начало интервала, dt — его длина).
Simulator._advance (DEBT-015) делит шаг пополам: два подшага H/2 с энергией
на каждом. Серия k+1 — те же подшаги отдельными интервалами истории. Если
локальное дробление и энергия по подшагам согласованы, состояния на 1 ч
останова равны побитово (h/2 — точная двоичная операция).

Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\val-004\\probes\\forced_split.py [k]
"""

import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("t", HERE / "test_plan_val004.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)   # копия кода плана: sys.path и CFG от numerical_solver/

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def run_forced(k):
    cfg = load_config(t.CFG)
    cfg.time.history = t._shutin_history(cfg, k)
    # Начала и длины интервалов останова — по ним узнаётся первая попытка
    t0 = t.N_PROD * t.DAY
    starts = {}
    for iv in cfg.time.history[t.N_PROD:]:
        starts[t0] = iv.dt
        t0 += iv.dt
    sim, s0 = SimulatorFactory.from_config(cfg)
    solve = sim._hydro.solve
    n = {"forced": 0, "solved": 0}

    def forced(state, dt, bc):
        if starts.get(state.t) == dt:
            n["forced"] += 1
            raise HydroConvergenceError("принудительный отказ первой попытки (аудит VAL-004)")
        n["solved"] += 1
        return solve(state, dt, bc)

    sim._hydro.solve = forced
    hist = sim.run(s0)
    return hist.states[-1], hist.times[-1], n


def main():
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    t1 = time.perf_counter()
    end_f, t_f, n = run_forced(k)
    el_f = time.perf_counter() - t1
    t1 = time.perf_counter()
    ref = t._run(k + 1)
    el_r = time.perf_counter() - t1
    print(f"серия k={k} с отказом первой попытки: принудительных отказов {n['forced']}, "
          f"решений {n['solved']} (ожидается {10 * 2 ** k} и {10 * 2 ** (k + 1)}, без добычи — "
          f"добыча идёт до первого отказа); t_end = {t_f:.6f}; счёт {el_f:.1f} с")
    print(f"серия k={k + 1}: отказов {len(ref['fails'])}, t_end = {ref['t_end']:.6f}; счёт {el_r:.1f} с")
    for f in ("p", "Sg", "Rs", "T", "regime"):
        a, b = np.asarray(getattr(end_f, f)), np.asarray(getattr(ref["end"], f))
        same = np.array_equal(a, b)
        d = float(np.max(np.abs(a.astype(float) - b.astype(float))))
        print(f"  {f}: {'побитово' if same else 'РАЗЛИЧИЕ'} (max|Δ| = {d:.3e})")


if __name__ == "__main__":
    main()
