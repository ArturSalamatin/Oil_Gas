"""BUG-020, реализация: невязка баланса энергии примера 16 и допуск Ньютона ступени 4.

С ступенью 4 относительная невязка баланса энергии примера 16 — 1.34e-10
(было 4.8e-11) при пороге TestSharedChecks::test_energy_balance_all_examples
1e-10. Проба: вариант без ступени 4, со ступенью и со ступенью при меньшем
rtol её Ньютона; для каждого — невязка баланса энергии и массы, отчёт шагов
ступени 4 (невязка Ньютона против допуска).

Запуск:
    $env:BUG020_SOLVER = "<дерево>\\numerical_solver"
    <python> energy16_stage4.py
"""

import functools
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path(os.environ.get("BUG020_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)


def run(label, flag, rtol=None):
    cfg = load_config(SOLVER / "examples" / "16_well_shut_in" / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    model.phase_switching_stage = flag
    if rtol is not None:
        model._newton_switching = functools.partial(
            type(model)._newton_switching, model, rtol=rtol)
    log = []
    orig = model.advance

    def advance(state_old, dt_s, *a, **kw):
        new, rep = orig(state_old, dt_s, *a, **kw)
        if rep.phase_switching or rep.globalized or rep.fallback:
            # допуск того же вида, что у Ньютона: atol + rtol * ||F(z0)||
            mask = state_old.gas_active
            f0 = model.residual(model.pack(state_old, mask), state_old, dt_s, mask)
            scale = max(np.linalg.norm(f0, np.inf), 1e-9)
            r = rtol if (rtol is not None and rep.phase_switching) else 1e-8
            f1 = model.residual(model.pack(new, new.gas_active), state_old, dt_s, new.gas_active)
            log.append((dt_s, rep.converged, rep.phase_switching, rep.globalized, rep.iterations,
                        rep.residual_inf, 1e-11 + r * scale, float(np.linalg.norm(f1, np.inf))))
        return new, rep

    model.advance = advance
    h = sim.run(init)
    bal = compute_balance(h, sim._grid, cfg)
    rel = np.asarray(bal["rel_residual"])
    print(f"\n=== {label} ===")
    print(f"  невязка баланса энергии: финал {rel[-1]:.3e}, max {np.max(np.abs(rel)):.3e}")
    for i in (15, 16, 17, 18, 19, 20, 53):
        print(f"    запись {i:2d}: rel {rel[i]:+.3e}")
    for row in log:
        dt, ok, ps, gl, it, res, tol, fin = row
        print(f"  шаг dt={dt:7.1f} с: сошёлся {ok}, ступень 4 {ps}, ступень 3 {gl}, итераций {it}, "
              f"|F|отчёт {res:.3e}, допуск {tol:.3e}, |F|принятого {fin:.3e}")
    st = h.states
    print(f"  p(r_w) записи 18, 22, 27: {st[18].p[0]/1e6:.6f} {st[22].p[0]/1e6:.6f} {st[27].p[0]/1e6:.6f} МПа")
    return h


if len(sys.argv) > 1 and sys.argv[1] == "--records":
    # по записям: относительная невязка и её числитель (Дж) в обоих вариантах
    out = {}
    for label, flag in (("без", False), ("с", True)):
        cfg = load_config(SOLVER / "examples" / "16_well_shut_in" / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        sim._hydro._model.phase_switching_stage = flag
        h = sim.run(init)
        out[label] = compute_balance(h, sim._grid, cfg)
    print("ключи compute_balance:", sorted(out["с"].keys()))
    rb, rs = np.asarray(out["без"]["rel_residual"]), np.asarray(out["с"]["rel_residual"])
    ab = np.asarray(out["без"].get("residual", rb)); as_ = np.asarray(out["с"].get("residual", rs))
    print(" запись | rel без ступени 4 | rel со ступенью 4 | невязка без, Дж | невязка с, Дж")
    for i in list(range(15, 54, 2)) + [53]:
        print(f"   {i:2d}   | {rb[i]:+.3e}        | {rs[i]:+.3e}        | {ab[i]:+.3e}      | {as_[i]:+.3e}")
    sys.exit(0)

run("без ступени 4 (как до BUG-020)", False)
run("ступень 4, rtol = 1e-8 (план)", True)
run("ступень 4, rtol = 1e-10", True, 1e-10)
run("ступень 4, rtol = 1e-12", True, 1e-12)
