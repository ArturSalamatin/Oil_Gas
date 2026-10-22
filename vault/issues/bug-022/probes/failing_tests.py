"""BUG-022: разбор двух тестов GPN, падающих на эмуляции плана (раздел 1.7 плана).

A. test_prototype_activation_cap.py::TestFirstStep::test_first_step_converges[350]:
   сценарий tests/data/bug018_rs500 при N = 350, первые сутки одним вызовом адаптера.
   База — третья ступень решает шаг 86400 с; план — ? Печатаем: исход одного вызова,
   отказы Ньютона (stall/maxit при выполненном абсолютном критерии) по ступеням; затем
   первые сутки через Simulator (локальное дробление): подшаги, S_g(r_w), p(r_w) на конце суток.
B. test_prototype_phase_switching.py::TestShutinFirstHour::test_first_hour_passes_with_local_subdivision:
   сценарий tests/data/bug020_rs150, без ступени 4: принятые/отказавшие подшаги часа
   останова, p(r_w), двухфазных, T(r_w) — база и план.
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\failing_tests.py
"""

import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cell_tol  # noqa: E402

from radial_blackoil.blackoil import RadialBlackOilModel  # noqa: E402
from gpn_multiphase_solver import factory  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BAR, DAY = 1e5, 86400.0
DATA = cell_tol.SOLVER / "tests" / "data"
ORIG = (RadialBlackOilModel._newton_fixed_active_set, RadialBlackOilModel._newton_switching)
ORIG_CREATE = factory._create_prototype_hydro
lines = []


def out(s):
    print(s, flush=True)
    lines.append(s)


def use(variant):
    """0 — код базы; иначе — эмуляция плана (условие у модели фабрики)."""
    RadialBlackOilModel._newton_fixed_active_set, RadialBlackOilModel._newton_switching = ORIG
    factory._create_prototype_hydro = ORIG_CREATE
    if variant == "0":
        return
    cell_tol.install(variant)
    cell_tol.CELL["require_mark"] = True

    def create(*a, **k):
        h = ORIG_CREATE(*a, **k)
        h._model._probe_cell = True
        return h

    factory._create_prototype_hydro = create


def stage_of(m):
    return 4 if m._phase_switching else 3 if m._line_search_l2 else 2 if m._sg_lower_bound is None else 1


def wrap_fails(model):
    """Отказы Ньютона по ступеням: (ступень, причина) — из счётчика пробы FAILS."""
    by = Counter()
    for name in ("_newton_fixed_active_set", "_newton_switching"):
        f = getattr(model, name)

        def w(*a, _f=f, **k):
            before = Counter(cell_tol.FAILS)
            r = _f(*a, **k)
            for key, v in (cell_tol.FAILS - before).items():
                by[(stage_of(model), key)] += v
            return r

        setattr(model, name, w)
    return by


out("== A. bug018_rs500, N = 350, первые сутки")
for v in ("0", "pv1e-8"):
    use(v)
    cfg = load_config(DATA / "bug018_rs500" / "config.json")
    cfg.output.log_level = "ERROR"
    cfg.grid.N = 350
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    model = sim._hydro._model
    cell_tol.FAILS.clear()
    by = wrap_fails(model)
    try:
        res = sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
        one = f"сошёлся: S_g(r_w) = {res.state.Sg[0]:.6f}, p(r_w) = {res.state.p[0] / 1e6:.6f} МПа"
    except HydroConvergenceError as e:
        one = f"отказ: {e}"
    out(f"[{v}] один вызов адаптера, dt = {dt:.0f} с: {one}; отказы Ньютона {dict(sorted(by.items()))}")
    # те же первые сутки через Simulator (локальное дробление): обрыв после первых суток
    cfg2 = load_config(DATA / "bug018_rs500" / "config.json")
    cfg2.output.log_level = "ERROR"
    cfg2.grid.N = 350
    sim2, init2 = SimulatorFactory.from_config(cfg2)
    calls = []
    orig_solve = sim2._hydro.solve

    def solve(state, dt_s, bc, _o=orig_solve, _c=calls):
        try:
            r = _o(state, dt_s, bc)
        except HydroConvergenceError:
            _c.append((dt_s, False))
            raise
        _c.append((dt_s, True))
        return r

    sim2._hydro.solve = solve
    h = sim2.run(init2)
    day1 = [s for s, t in zip(h.states, h.times) if abs(t - DAY) < 1.0]
    ok = [d for d, c in calls if c]
    out(f"[{v}] Simulator: записей {len(h.states)}, вызовов {len(calls)}, принято {len(ok)}, отказов "
        f"{len(calls) - len(ok)}; принятые dt {Counter(ok)}; на 1 сут S_g(r_w) = {day1[0].Sg[0]:.6f}, "
        f"p(r_w) = {day1[0].p[0] / 1e6:.6f} МПа")

out("== B. bug020_rs150, час останова без ступени 4")
for v in ("0", "pv1e-8"):
    use(v)
    cfg = load_config(DATA / "bug020_rs150" / "config.json")
    sim, init = SimulatorFactory.from_config(cfg)
    sim._hydro._model.phase_switching_stage = False
    calls = []
    orig_solve = sim._hydro.solve

    def solve(state, dt_s, bc, _o=orig_solve, _c=calls):
        shut = state.t >= 10 * DAY - 1e-6
        try:
            r = _o(state, dt_s, bc)
        except HydroConvergenceError:
            if shut:
                _c.append((dt_s, False))
            raise
        if shut:
            _c.append((dt_s, True))
        return r

    sim._hydro.solve = solve
    cell_tol.FAILS.clear()
    by = wrap_fails(sim._hydro._model)
    h = sim.run(init)
    ok = [d for d, c in calls if c]
    st = h.states[-1]
    out(f"[{v}] принято {len(ok)} {dict(sorted(Counter(ok).items()))}, отказов {len(calls) - len(ok)}, "
        f"сумма {sum(ok):.6f} с; p(r_w) = {st.p[0] / BAR:.4f} бар, двухфазных "
        f"{int(np.count_nonzero(st.regime == 1))}, T(r_w) = {st.T[0]:.4f} К; "
        f"отказы Ньютона {dict(sorted(by.items()))}")
(HERE / "failing_tests.out.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
