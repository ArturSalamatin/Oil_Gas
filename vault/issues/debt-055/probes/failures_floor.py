"""DEBT-055, проба планирования: отказы Ньютона «только по ячейке» — на полу округления?

Для каждого отказавшего Ньютона ступеней 1-3 (_newton_fixed_active_set) и ступени 4
(_newton_switching), у которого выполнен абсолютный критерий, а условие ячейки — нет,
в возвращённой точке z считается оценка пола по якобиану (гипотеза Q, floor_probe.py):
    m_J = max_i (|J| @ ulp(z))_i * dt / V_p,i,
и печатается мера отчёта рядом с m_J. Мера ~ m_J (в пределах порядка) — отказ на полу
округления: точку лучше на решётке представимых чисел не найти.

Сценарии — те же, что в переписи DEBT-054 (vault/issues/debt-054/probes/failure_census.py):
  bug018  — BUG-018, N = 350, Simulator.run (первые сутки дробятся);
  ex14    — пример 14 (N = 350, шаг 1 сут);
  shutin  — суточный останов bug020_rs300 (TestDailyShutin: 10 сут добычи + 3 сут q_oil = 0).

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-055\\probes\\failures_floor.py [bug018 ex14 shutin]
"""
import copy
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
HERE = Path(__file__).resolve().parent

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config      # noqa: E402
import radial_blackoil                                        # noqa: E402

NAMES = sys.argv[1:] or ["bug018", "ex14", "shutin"]
OUT = open(HERE / f"failures_floor_{'_'.join(NAMES)}.out.txt", "w", encoding="utf-8")


def out(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


out(f"SOLVER = {SOLVER}")
out(f"radial_blackoil: {Path(radial_blackoil.__file__).parent}")


def floor_at(model, z, state_old, dt, mask):
    """m_J и мера в z; ячейка (строка) максимума каждой."""
    n = model.grid.n
    w = dt / model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, state_old.pressure_bar)
    J, f = model.finite_difference_jacobian(z, state_old, dt, mask)
    noise = abs(J) @ np.spacing(np.abs(z))

    def mx(v):
        a, b = np.abs(v[:n]) * w, np.abs(v[n:]) * w
        return (float(a.max()), f"o{int(np.argmax(a))}") if a.max() >= b.max() \
            else (float(b.max()), f"g{int(np.argmax(b))}")
    # Поячеечно: какой множитель kappa пола |F_i| <= max(eps*V_i/dt, kappa*noise_i) нужен,
    # чтобы точка z прошла — max по строкам, где условие eps не выполнено, отношения |F|/noise
    bad = np.abs(f) * np.concatenate([w, w]) > model.cell_tol
    kappa = float(np.max(np.abs(f)[bad] / noise[bad])) if bad.any() else 0.0
    return mx(f), mx(noise), kappa


def instrument(model, recs):
    """Обёртки обоих Ньютонов: отказ при выполненном абсолютном критерии — в recs."""
    orig_fas = model._newton_fixed_active_set
    orig_sw = model._newton_switching

    def fas(z0, state_old, dt_s, gas_active, *a, **kw):
        z, rep = orig_fas(z0, state_old, dt_s, gas_active, *a, **kw)
        if (not rep.converged and rep.residual_tol is not None and rep.cell_measure is not None
                and rep.residual_inf <= rep.residual_tol and rep.cell_measure > model.cell_tol):
            (m, cm), (mj, cj), kap = floor_at(model, z, state_old, dt_s, gas_active)
            recs.append(("1-3", dt_s, rep.exit_reason, rep.cell_measure, m, cm, mj, cj, kap))
        return z, rep

    def sw(state_old, dt_s, *a, **kw):
        new, rep = orig_sw(state_old, dt_s, *a, **kw)
        if (not rep.converged and rep.residual_tol is not None and rep.cell_measure is not None
                and rep.residual_inf <= rep.residual_tol and rep.cell_measure > model.cell_tol):
            mask = new.gas_active.copy()
            (m, cm), (mj, cj), kap = floor_at(model, model.pack(new, mask), state_old, dt_s, mask)
            recs.append(("4", dt_s, rep.exit_reason, rep.cell_measure, m, cm, mj, cj, kap))
        return new, rep

    model._newton_fixed_active_set = fas
    model._newton_switching = sw


def run(title, cfg):
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    recs = []
    instrument(model, recs)
    t0 = time.perf_counter()
    try:
        sim.run(init)
        res = "расчёт прошёл"
    except RuntimeError as e:
        res = f"отказ расчёта: {str(e)[:120]}"
    out(f"\n=== {title}: {res}, {time.perf_counter() - t0:.0f} с; "
        f"отказов Ньютона «только ячейка» {len(recs)} ===")
    out("  ступени  dt, с      выход        мера отчёта  мера в z (ячейка)   m_J (ячейка)    "
        "мера/m_J  kappa поячеечно")
    for st, dt, why, mrep, m, cm, mj, cj, kap in recs[:40]:
        out(f"  {st:<8} {dt:<10.4g} {why:<12} {mrep:.3e}    {m:.3e} ({cm:<5})   "
            f"{mj:.3e} ({cj:<5})  {m / mj:.2f}      {kap:.2f}")
    if recs:
        r = np.array([x[4] / x[6] for x in recs])
        k = np.array([x[8] for x in recs])
        out(f"  мера/m_J: min {r.min():.2f}, медиана {np.median(r):.2f}, max {r.max():.2f}; "
            f"kappa поячеечно: min {k.min():.2f}, max {k.max():.2f}; "
            f"по dt: {dict(sorted(Counter(float(x[1]) for x in recs).items()))}")


for name in NAMES:
    if name == "bug018":
        cfg = load_config(SOLVER / "tests" / "data" / "bug018_rs500" / "config.json")
        cfg.grid.N = 350
        run("BUG-018, N = 350", cfg)
    elif name.startswith("ex"):
        # exNN — пример examples/NN_*
        d = next((SOLVER / "examples").glob(f"{name[2:]}_*/config.json"))
        run(f"пример {d.parent.name}", load_config(d))
    elif name == "shutin":
        cfg = load_config(SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
        hist = list(cfg.time.history)
        for _ in range(3):
            x = copy.deepcopy(hist[0])
            x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
            hist.append(x)
        cfg.time.history = hist
        run("суточный останов bug020_rs300", cfg)
