"""DEBT-030, проба при планировании: логический тест шага 2 (подмена _advance_phases).

Повторяет test_all_fail_reports_original_newton из плана на текущем advance и на
advance по плану (trace_stages.advance_planned). Ожидание: текущий — проверки не
проходят (iterations = 0), по плану — проходят.

Запуск из numerical_solver того дерева, чей код проверяется:
    .venv\\Scripts\\python <путь>\\planned_gpn_test_check.py
"""
import sys
from dataclasses import replace
from pathlib import Path

PROTO = Path.cwd() / "HydroSolverPrototype" / "Prototype_1.0.3"
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import radial_blackoil.blackoil as bo                        # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport     # noqa: E402
from tests.test_prototype_well_branch import _build, _model, BHP_DRAWDOWN_BAR, N_DRAWDOWN, DT_DRAWDOWN_S  # noqa: E402
from trace_stages import advance_planned                      # noqa: E402

print(f"код: {Path(bo.__file__).parent}")

ORIG3 = (None, -0.05, False)

# Состояние drawn_down — как фикстура test_prototype_well_branch.py:124-137
m0, state = _build(BHP_DRAWDOWN_BAR)
for _ in range(N_DRAWDOWN):
    state, r = m0.advance(state, DT_DRAWDOWN_S)
    assert r.converged
print(f"drawn_down: p[0] = {state.pressure_bar[0]:.3f} бар")


def run(planned):
    model = _model(150.0)
    reports = {
        ORIG3: (0.0, BlackOilNewtonReport(False, 15, 2.5e-7, 2, 21)),
        ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
        ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0)),
        ("shut", None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9)),
        ("open", None, True): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0)),
    }
    calls = []

    def fake(state_old, dt_s, max_active_iter, max_newton):
        key = (model._well_branch, model._sg_lower_bound, model._line_search_l2)
        calls.append(key)
        p0_bar, rep = reports[key]
        new = state_old.copy()
        new.pressure_bar[0] = p0_bar
        return new, replace(rep)

    model._advance_phases = fake
    adv = advance_planned.__get__(model) if planned else model.advance
    _, rep = adv(state, 3600.0)
    checks = {
        "calls": calls == [ORIG3, ("shut", None, False), ("open", None, False),
                           ("shut", None, True), ("open", None, True)],
        "not converged": not rep.converged,
        "newton fields": (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                          rep.phase_switches) == (15, 2.5e-7, 2, 21),
        "flags": rep.fallback and rep.globalized,
        "branch fields": (rep.well_branch, rep.well_switches) == ("open", 1),
        "restored": (model._well_branch is None and model._sg_lower_bound == -0.05
                     and model._line_search_l2 is False and model._sg_step_max is None),
    }
    print(f"{'по плану' if planned else 'сейчас  '}: {rep}")
    print(f"           {checks}")


run(planned=False)
run(planned=True)
