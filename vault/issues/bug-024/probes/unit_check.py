"""BUG-024: числа тестов ступени 4 при варианте обновления R_s (stage4_variants.py).

Повторяет сценарии тестов, которые закрепляют результат ступени 4:
  tests/test_prototype_phase_switching.py — TestFourthStage (rs300, шаг 168.75 с; 60 с — тот же
      корень), TestShutinFirstHour::test_first_hour_converges (rs150, час одним шагом);
  tests/test_prototype_cell_tolerance.py — TestSwitching (168.75 с без условия по ячейке и с ним).
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\unit_check.py code satrel
"""

import sys
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
from radial_blackoil.state import BlackOilState              # noqa: E402
import stage4_variants                                        # noqa: E402

DATA = SOLVER / "tests" / "data"
BAR = 1e5
ATM_BAR = 101325.0 / BAR
DT4 = 168.75


def measure(model, ps, new, dt):
    """max_c |F_c,i| dt / PV_i решения — как _measure в test_prototype_cell_tolerance.py."""
    n = model.grid.n
    f = model.residual(model.pack(new), ps, dt, new.gas_active)
    w = dt / model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, ps.pressure_bar)
    return max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w)))


def proto(s):
    return BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(), sg=s.Sg.copy(),
                         gas_active=(s.regime == 1))


def check(variant, out):
    cfg = load_config(DATA / "bug020_rs300" / "config.json")
    sim, init = SimulatorFactory.from_config(cfg)
    ps = proto(sim.run(init).states[-1])
    model = sim._hydro._model
    if variant != "code":
        stage4_variants.install(model, variant)
    model.phase_switching_stage = True
    model.set_oil_rate_control(0.0, ATM_BAR)
    new, rep = model.advance(ps, DT4)
    out(f"[{variant}] rs300 168.75 с: сошлось {rep.converged}, ступень 4 {rep.phase_switching}, "
        f"p(r_w) {new.pressure_bar[0]:.4f} (тест 174.4349), двухфазных {int(new.gas_active.sum())} (250), "
        f"max S_g {new.sg.max():.4f} (0.3084), итераций {rep.iterations}, переключений фаз "
        f"{rep.phase_switches} (docstring: 20 итераций, 127 переключений)")
    ct = model.cell_tol
    try:
        model.cell_tol = None
        a, ra = model._newton_switching(ps, DT4)
        model.cell_tol = ct
        b, rb = model._newton_switching(ps, DT4)
    finally:
        model.cell_tol = ct
    out(f"[{variant}] без условия: сошлось {ra.converged}, итераций {ra.iterations}, мера "
        f"{measure(model, ps, a, DT4):.2e} (тест: > 1e-8); с условием: {rb.converged}, итераций "
        f"{rb.iterations} (тест: больше), мера {measure(model, ps, b, DT4):.2e}, |dp| "
        f"{np.max(np.abs(b.pressure_bar - a.pressure_bar)):.2e} (тест < 1e-7)")
    ref, r1 = model.advance(ps, 60.0)
    alt, r2 = model._newton_switching(ps, 60.0)
    out(f"[{variant}] 60 с: штатные {r1.converged} (ступень 4 {r1.phase_switching}), ступень 4 {r2.converged}; "
        f"маски равны {np.array_equal(ref.gas_active, alt.gas_active)}, |dp| "
        f"{np.max(np.abs(ref.pressure_bar - alt.pressure_bar)):.1e}, |dS_g| {np.max(np.abs(ref.sg - alt.sg)):.1e}, "
        f"|dR_s| {np.max(np.abs(ref.rs_sm3_sm3 - alt.rs_sm3_sm3)):.1e}")
    # rs150: 10 сут добычи + час останова; час одним шагом (test_first_hour_converges)
    cfg = load_config(DATA / "bug020_rs150" / "config.json")
    sim, init = SimulatorFactory.from_config(cfg)
    m2 = sim._hydro._model
    if variant != "code":
        stage4_variants.install(m2, variant)
    calls = []
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        shut = state.t >= 10 * 86400.0 - 1e-6
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
    st = sim.run(init).states[-1]
    out(f"[{variant}] rs150 час: вызовы {calls[:4]}{'…' if len(calls) > 4 else ''} (тест [(3600, True)]), "
        f"p(r_w) {st.p[0] / BAR:.4f} (176.6086), двухфазных {int(np.count_nonzero(st.regime == 1))} (263), "
        f"T(r_w) {st.T[0]:.4f} (397.7928)")


if __name__ == "__main__":
    log = open(HERE / f"unit_check_{'_'.join(sys.argv[1:])}.out.txt", "w", encoding="utf-8")

    def out(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    for v in sys.argv[1:]:
        check(v, out)
