"""DEBT-040: числа для тестов плана — перебор веток на реальном шаге останова и модель Nabor_1b.

1. Сценарий rs300 (tests/data/bug020_rs300, как фикстура shutin_start), шаг 168.75 с
   при p_wf = p_ext: последовательность (ступень, ветка) решений _advance_phases и итог
   шага — на коде базы и с вариантом 2 (stage_profile.install_v2).
2. Модель Nabor_1b тестов логики (test_prototype_well_branch._build): p_ext и
   max p состояния drawn_down — выполняется ли условие варианта 2 при p_wf = 200 бар.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-040\\probes\\plan_tests_check.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (HERE, SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402
import stage_profile  # noqa: E402

BAR = 1e5
RS300 = SOLVER / "tests" / "data" / "bug020_rs300" / "config.json"


def shutin_start():
    cfg = load_config(RS300)
    sim, init = SimulatorFactory.from_config(cfg)
    s = sim.run(init).states[-1]
    model = sim._hydro._model
    ps = BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(), sg=s.Sg.copy(),
                       gas_active=(s.regime == 1))
    return model, ps, cfg.initial_conditions.p0 / BAR


def spy(model):
    calls = []
    base = model._advance_phases

    def phases(state_old, dt_s, max_active_iter=12, max_newton=15):
        new, rep = base(state_old, dt_s, max_active_iter, max_newton)
        calls.append((stage_profile.stage_of(model), model._well_branch, bool(rep.converged),
                      round(float(new.pressure_bar[0]), 4), rep.iterations))
        return new, rep
    model._advance_phases = phases
    return calls


for variant in ("0", "v2"):
    model, ps, p_ext = shutin_start()
    if variant == "v2":
        stage_profile.install_v2(model)
    calls = spy(model)
    model.set_bhp_control(p_ext)
    print(f"--- вариант {variant}: p_ext = {p_ext:.4f} бар, max p old = {ps.pressure_bar.max():.4f} бар, "
          f"p_outer модели = {model.p_outer_bar:.4f}")
    new, rep = model.advance(ps, 168.75)
    for c in calls:
        print(f"    ступень {c[0]} ветка {c[1]}: сошлось {c[2]}, p0 {c[3]}, итераций {c[4]}")
    print(f"  итог: converged {rep.converged}, ветка {rep.well_branch}, смен {rep.well_switches}, "
          f"ступень 4 {rep.phase_switching}, p0 = {new.pressure_bar[0]:.6f}, "
          f"2ф = {int(new.gas_active.sum())}, max Sg = {new.sg.max():.6f}")
    np.save(HERE / f"plan_step_{variant}.npy", np.concatenate([new.pressure_bar, new.rs_sm3_sm3, new.sg]))

a, b = np.load(HERE / "plan_step_0.npy"), np.load(HERE / "plan_step_v2.npy")
print(f"шаг 168.75 с, вариант 2 против базы: побитово {np.array_equal(a, b)}")
for f in ("plan_step_0.npy", "plan_step_v2.npy"):
    (HERE / f).unlink()

sys.path.insert(0, str(SOLVER / "tests"))
from test_prototype_well_branch import _build, BHP_DRAWDOWN_BAR  # noqa: E402

model, state = _build(BHP_DRAWDOWN_BAR)
for _ in range(12):
    state, rep = model.advance(state, 300.0)
    assert rep.converged
print(f"Nabor_1b: p_outer = {model.p_outer_bar} бар; drawn_down: p[0] = {state.pressure_bar[0]:.3f}, "
      f"max p = {state.pressure_bar.max():.6f} бар, ячеек {state.pressure_bar.size}")
