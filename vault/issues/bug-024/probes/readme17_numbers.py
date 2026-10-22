"""BUG-024: числа README примера 17 и закреплённые тестами значения — код базы против варианта ступени 4.

Расчёт примера 17 через фабрику (как фикстура results в tests/test_examples.py), вариант —
stage4_variants.py или code. Печатает: таблицу записей README (p, T, S_g у забоя, ячеек с газом),
числа текста (прогрев, выход выше p_b, недогрев, профиль T на финале, кольцо газа), члены баланса
энергии за первые сутки останова и за весь останов (energy_balance.compute_balance, как
test_shut_in_heating_sources), дробление часов останова (подшаги Simulator).
Из numerical_solver:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\readme17_numbers.py code satrel
"""

import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path.cwd().resolve()   # запуск из numerical_solver проверяемого дерева
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", HERE, SOLVER / "examples"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory   # noqa: E402
from gpn_multiphase_solver.io.config import load_config      # noqa: E402
from energy_balance import compute_balance                   # noqa: E402
import stage4_variants                                        # noqa: E402

NAME = "17_shut_in_strong_cooling"
E = 15            # запись конца добычи
DAY = 86400.0
PB = 30.2921e6    # p_b примера 17, Па


def run(variant, out):
    cfg = load_config(SOLVER / "examples" / NAME / "config.json")
    cfg.output.log_level = "ERROR"
    if os.environ.get("BUG024_DT17"):
        # опыт: суточный dt_integration (утверждение docstring test_config_follows_decisions)
        cfg.time.dt_integration = float(os.environ["BUG024_DT17"])
    out(f"[{variant}] dt_integration = {cfg.time.dt_integration:.0f} с")
    sim, init = SimulatorFactory.from_config(cfg)
    if variant != "code":
        stage4_variants.install(sim._hydro._model, variant)
    subs = []     # (t начала подшага, h, сошёлся)
    orig = sim._hydro.solve

    tsolve = defaultdict(float)   # время гидро по суткам от начала расчёта

    def solve(state, h, bc):
        t1 = time.perf_counter()
        try:
            r = orig(state, h, bc)
        except Exception:
            subs.append((state.t, h, False))
            tsolve[int(state.t // DAY)] += time.perf_counter() - t1
            raise
        subs.append((state.t, h, True))
        tsolve[int(state.t // DAY)] += time.perf_counter() - t1
        return r

    sim._hydro.solve = solve
    t0 = time.perf_counter()
    try:
        hist = sim.run(init)
    except RuntimeError as e:
        out(f"[{variant}] ✗ {time.perf_counter() - t0:.1f} с: {str(e)[:160]}")
        return
    wall = time.perf_counter() - t0
    grid = sim._grid
    st = hist.states
    p_w = np.array([s.p[0] for s in st]); T_w = np.array([s.T[0] for s in st])
    out(f"[{variant}] счёт {wall:.1f} с; записей {len(st)}")
    out("  запись | t, сут  | p(r_w), МПа | T(r_w), К | S_g(r_w) | ячеек с газом")
    for k in (0, 1, 15, 16, 17, 27, 39, 43, 53):
        s = st[k]
        out(f"  {k:>6} | {hist.times[k] / DAY:7.4f} | {s.p[0] / 1e6:11.4f} | {s.T[0]:9.4f} | "
            f"{s.Sg[0]:.4f} | {int(np.count_nonzero(s.Sg > 0))}")
    above = np.flatnonzero(p_w[E:] > PB)
    out(f"  прогрев за 1 ч {T_w[E + 1] - T_w[E]:+.4f} К; p(r_w) выше p_b с записи {E + above[0]}; "
        f"конец первых суток p {p_w[39] / 1e6:.4f} МПа, T {T_w[39]:.4f} К; финал T {T_w[-1]:.4f} К; "
        f"min приращение T на останове {np.min(np.diff(T_w[E:])):.4f} К")
    T0 = cfg.initial_conditions.T0
    fin = st[-1]
    rr = grid.r_centers
    dT = fin.T - T0
    k = int(np.argmax(dT))
    gas = fin.Sg > 0
    i1, i10 = int(np.argmin(np.abs(rr - 1.0))), int(np.argmin(np.abs(rr - 10.0)))
    out(f"  финал: ΔT забой {dT[0]:+.4f}, на 1 м {dT[i1]:+.4f}, на 10 м {dT[i10]:+.4f}, max {dT[k]:+.4f} К "
        f"на {rr[k]:.2f} м; max|p - p0| {np.max(np.abs(fin.p - cfg.initial_conditions.p0)):.3e} Па; "
        f"газ {int(gas.sum())} ячеек на {rr[gas].min():.2f}–{rr[gas].max():.2f} м, max S_g "
        f"{fin.Sg.max():.4f}; R_s(r_w) {fin.Rs[0]:.4f}")
    rs = np.array([s.Rs[0] for s in st])
    out(f"  R_s(r_w): наименьшее изменение между записями останова {np.min(np.diff(rs[E + 1:])):+.2e}")
    i03 = int(np.argmin(np.abs(rr - 0.3)))
    ks = int(np.argmax(fin.Sg))
    gas16 = np.flatnonzero(st[E + 1].Sg > 0)    # через 1 ч останова
    out(f"  финал: R_s на 0.3 м {fin.Rs[i03]:.2f}, на 1 м {fin.Rs[i1]:.2f}; max S_g {fin.Sg.max():.5f} на "
        f"{rr[ks]:.2f} м; через 1 ч газа нет на r < {rr[gas16.min()]:.3f} м; T(r_w) на 39 и 53 "
        f"{T_w[39]:.4f} / {T_w[-1]:.4f}; недогрев {T0 - T_w[-1]:.4f} К")
    bal = compute_balance(hist, grid, cfg)
    keys = ("delta_E", "cum_adiab", "cum_deg", "cum_jt", "cum_conv", "cum_cond")
    d1 = {kk: float(bal[kk][39] - bal[kk][E]) for kk in keys}
    dall = {kk: float(bal[kk][-1] - bal[kk][E]) for kk in keys}
    out("  баланс энергии останова, Дж: " + "; ".join(
        f"{kk} {d1[kk]:+.4e} / {dall[kk]:+.4e}" for kk in keys))
    out(f"  относительная невязка баланса энергии на конце (сводный README): {float(bal['rel_residual'][-1]):.4e}")
    out(f"  доли за весь останов: сжатие {dall['cum_adiab'] / dall['delta_E']:.1%}, растворение "
        f"{dall['cum_deg'] / dall['delta_E']:.1%}; дегазация за добычу {float(bal['cum_deg'][E]):+.3e}")
    # дробление часов останова: часы, где был отказ, и подшаги в них
    per_hour = defaultdict(list)
    for t, h, ok in subs:
        if t >= E * DAY - 1e-6:
            per_hour[int((t - E * DAY) // 3600.0)].append((h, ok))
    tot = sum(tsolve.values())
    out(f"  время гидро {tot:.1f} с из {wall:.1f}: добыча {sum(v for d, v in tsolve.items() if d < E):.1f} с, "
        f"первые трое суток останова {sum(v for d, v in tsolve.items() if E <= d < E + 3):.1f} с "
        f"({sum(v for d, v in tsolve.items() if E <= d < E + 3) / wall:.0%} счёта), остальное "
        f"{sum(v for d, v in tsolve.items() if d >= E + 3):.1f} с")
    split = {hr: v for hr, v in per_hour.items() if any(not ok for _, ok in v) or len(v) > 1}
    hs = [h for v in split.values() for h, ok in v if ok]
    out(f"  дробление останова: отказов {sum(not ok for _, _, ok in subs)}, часов с дроблением {len(split)}"
        + (f" (с {min(split)}-го по {max(split)}-й час от закрытия; принятых подшагов в часе "
           f"{min(sum(ok for _, ok in v) for v in split.values())}–{max(sum(ok for _, ok in v) for v in split.values())}, "
           f"от {min(hs) / 60:.1f} до {max(hs) / 60:.1f} мин)" if split else ""))


if __name__ == "__main__":
    tag = f"_dt{os.environ['BUG024_DT17']}" if os.environ.get("BUG024_DT17") else ""
    log = open(HERE / f"readme17_{'_'.join(sys.argv[1:])}{tag}.out.txt", "w", encoding="utf-8")

    def out(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    for v in sys.argv[1:]:
        run(v, out)
