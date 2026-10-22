"""DEBT-030, аудит раунд 1: логические тесты шага 2 на трёх версиях advance.

Версии: текущая (код на диске), по плану (trace_stages.advance_planned) и «мутант» —
replace применён после третьей ступени без условия, то есть и к сошедшемуся шагу.
Сценарии (подмена _advance_phases, модель Nabor_1b):
  A. BHP, отказ всех ступеней — поля Ньютона исходного алгоритма;
  B. управление по дебиту, отказ всех ступеней — то же, ветка '' и 0 смен;
  C. BHP, третья ступень сошлась — отчёт сошедшейся ступени, не исходного.
Ожидание: текущая — A, B не проходят, C проходит; по плану — всё проходит;
мутант — C не проходит (а регрессия его не видит: _grow_dt различает только
iterations >= 10 / >= 6, у T03, T04 сошедшаяся третья ступень — 17, исходный — 15).

Запуск из numerical_solver:
    .venv\\Scripts\\python <путь>\\audit_gpn_tests_check.py
"""
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import radial_blackoil.blackoil as bo                        # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport as R  # noqa: E402
from tests.test_prototype_well_branch import (_build, _model, BHP_DRAWDOWN_BAR,  # noqa: E402
                                              N_DRAWDOWN, DT_DRAWDOWN_S)
from trace_stages import advance_planned                      # noqa: E402

print(f"код: {Path(bo.__file__).parent}")


def advance_mutant(self, state_old, dt_s, max_active_iter=12, max_newton=15):
    """Ошибочное размещение: replace без условия после третьей ступени."""
    new, rep = self._advance_phases(state_old, dt_s, max_active_iter, max_newton)
    if rep.converged:
        if self.control_mode == 'BHP':
            p0 = float(new.pressure_bar[0])
            rep.well_branch = 'shut' if p0 <= float(self.p_bhp_bar) else 'open'
        return new, rep
    orig = rep
    new, rep = self._fallback(state_old, dt_s, max_active_iter, max_newton)
    if rep.converged: return new, rep
    self._line_search_l2 = True; self._sg_step_max = 0.2
    try:
        new, rep = self._fallback(state_old, dt_s, max_active_iter, max_newton)
        rep.globalized = True
        rep = replace(rep, iterations=orig.iterations, residual_inf=orig.residual_inf,
                      active_set_iterations=orig.active_set_iterations,
                      phase_switches=orig.phase_switches)
        return new, rep
    finally:
        self._line_search_l2 = False; self._sg_step_max = None


m0, drawn = _build(BHP_DRAWDOWN_BAR)
for _ in range(N_DRAWDOWN):
    drawn, r = m0.advance(drawn, DT_DRAWDOWN_S)
    assert r.converged

ORIG3 = (None, -0.05, False)
ORIG_REP = R(False, 15, 2.5e-7, 2, 21)
SCENARIOS = {
    "A": dict(rate=False, state="drawn", dt=3600.0, reports={
        ORIG3: (0.0, ORIG_REP),
        ("shut", None, False): (0.0, R(False, 14, 3.0e-6, 3, 7)),
        ("open", None, False): (140.0, R(True, 0, 0.0, 1, 0)),
        ("shut", None, True): (0.0, R(False, 13, 4.0e-5, 4, 9)),
        ("open", None, True): (140.0, R(True, 0, 0.0, 1, 0))},
        expect=(False, 15, 2.5e-7, 2, 21, "open", 1, True, True)),
    "B": dict(rate=True, state="init", dt=60.0, reports={
        ORIG3: (0.0, ORIG_REP),
        (None, None, False): (0.0, R(False, 14, 3.0e-6, 3, 7)),
        (None, None, True): (0.0, R(False, 13, 4.0e-5, 4, 9))},
        expect=(False, 15, 2.5e-7, 2, 21, "", 0, True, True)),
    "C": dict(rate=False, state="drawn", dt=3600.0, reports={
        ORIG3: (0.0, ORIG_REP),
        ("shut", None, False): (0.0, R(False, 14, 3.0e-6, 3, 7)),
        ("open", None, False): (140.0, R(True, 0, 0.0, 1, 0)),
        ("shut", None, True): (149.0, R(True, 17, 2.0e-16, 2, 15))},
        expect=(True, 17, 2.0e-16, 2, 15, "shut", 0, True, True)),
}


def run(version, sc):
    model, init = _build(150.0)
    if sc["rate"]:
        model.set_oil_rate_control(2.0, 100.0)
    state = drawn if sc["state"] == "drawn" else init

    def fake(state_old, dt_s, max_active_iter, max_newton):
        key = (model._well_branch, model._sg_lower_bound, model._line_search_l2)
        p0_bar, rep = sc["reports"][key]
        new = state_old.copy()
        new.pressure_bar[0] = p0_bar
        return new, replace(rep)

    model._advance_phases = fake
    adv = {"сейчас": model.advance, "по плану": advance_planned.__get__(model),
           "мутант": advance_mutant.__get__(model)}[version]
    _, rep = adv(state, sc["dt"])
    got = (rep.converged, rep.iterations, rep.residual_inf, rep.active_set_iterations,
           rep.phase_switches, rep.well_branch, rep.well_switches, rep.fallback, rep.globalized)
    return got == sc["expect"], got


for version in ("сейчас", "по плану", "мутант"):
    for name, sc in SCENARIOS.items():
        ok, got = run(version, sc)
        print(f"{version:9s} {name}: {'проходит' if ok else 'НЕ проходит'}  {got}")
