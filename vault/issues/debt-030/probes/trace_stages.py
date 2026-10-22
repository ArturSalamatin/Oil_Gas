"""DEBT-030, проба при планировании: трассировка ступеней advance на отклонённых шагах.

Для кейсов регрессии прототипа (T03, T04, T05S_N200_DT5m) строит модель так же,
как runner.run_workbook, и повторяет первые шаги истории (dt0, dt0/2, ... до
первого принятого). На каждом шаге печатает все вызовы _advance_phases (ступень,
ветка, сошлась, согласована, итераций, ||F||_inf), отчёт, который возвращает
текущий advance, и отчёт, который вернёт advance по плану (вариант 1).

Запуск из numerical_solver/HydroSolverPrototype/Prototype_1.0.3 того дерева,
чей код проверяется:
    ..\\..\\.venv\\Scripts\\python <путь>\\trace_stages.py
"""
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import radial_blackoil.blackoil as bo                      # noqa: E402
from radial_blackoil.input_reader import load_input         # noqa: E402
from radial_blackoil.grid import RadialGrid                 # noqa: E402
from radial_blackoil.rock import CompressibleRock           # noqa: E402
from radial_blackoil.state import BlackOilState             # noqa: E402
from radial_blackoil.simulation import _apply_control       # noqa: E402

print(f"код: {Path(bo.__file__).parent}")

INPUTS = ROOT / "regression" / "inputs"
CASES = {"T03": INPUTS / "T03.xlsx", "T04": INPUTS / "T04.xlsx",
         "T05S_N200_DT5m": INPUTS / "T05" / "T05S_N200_DT5m.xlsx"}


def build(path):
    """Модель и начальное состояние — как runner.run_workbook (runner.py:106-114)."""
    inp = load_input(path); p = inp.params
    grid = RadialGrid(float(p['Well radius rw']), float(p['Outer radius re']),
                      float(p['Formation thickness h']), int(p['Grid cells N']),
                      float(p['Absolute permeability']))
    rock = CompressibleRock(float(p['Reference porosity']), float(p['Reference pressure']),
                            float(p['Rock compressibility cr']))
    first = inp.schedule.rows[0]
    initial_bhp = first.bhp_bar if first.mode == 'BHP' else (
        first.min_bhp_bar if first.min_bhp_bar is not None else float(p['Outer-boundary pressure']))
    model = bo.RadialBlackOilModel(grid, rock, inp.pvt, inp.relperm, initial_bhp,
                                   float(p['Outer-boundary pressure']), float(p['Initial dissolved gas Rs']),
                                   skin=float(p['Well skin']), jacobian_mode=str(p['Jacobian mode']),
                                   linear_solver=str(p['Linear solver']))
    state0 = BlackOilState.undersaturated(grid.n, float(p['Initial pressure']),
                                          float(p['Initial dissolved gas Rs']))
    _apply_control(model, inp.schedule.control_for_interval_starting_at(0.0))
    return model, state0, float(p['DT initial']) * 60.0


def advance_planned(self, state_old, dt_s, max_active_iter=12, max_newton=15):
    """advance по плану DEBT-030, вариант 1 (копия blackoil.py:294-321 + правка)."""
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
        if not rep.converged:
            rep = replace(rep, iterations=orig.iterations, residual_inf=orig.residual_inf,
                          active_set_iterations=orig.active_set_iterations,
                          phase_switches=orig.phase_switches)
        return new, rep
    finally:
        self._line_search_l2 = False; self._sg_step_max = None


def fmt(rep):
    return (f"conv={rep.converged!s:5} it={rep.iterations:2d} aset={rep.active_set_iterations:2d} "
            f"sw={rep.phase_switches:3d} |F|={rep.residual_inf:.6e}")


def trace(model, state0, dt):
    """Один вызов advance с записью всех вызовов _advance_phases."""
    calls = []
    inner = model._advance_phases

    def wrapped(state_old, dt_s, max_active_iter=12, max_newton=15):
        new, rep = inner(state_old, dt_s, max_active_iter, max_newton)
        stage = ("исходный" if model._well_branch is None and model._sg_lower_bound == -0.05
                 else ("третья" if model._line_search_l2 else "запасной"))
        branch = model._well_branch or "—"
        cons = ""
        if rep.converged and model._well_branch is not None:
            p0 = float(new.pressure_bar[0]); target = float(model.p_bhp_bar)
            cons = "согл." if ((p0 >= target) if branch == "open" else (p0 <= target)) else "НЕсогл."
        calls.append((stage, branch, cons, fmt(rep)))
        return new, rep

    model._advance_phases = wrapped
    try:
        _, rep_now = model.advance(state0, dt)
    finally:
        del model._advance_phases
    return calls, rep_now


def main():
    for name, path in CASES.items():
        model, state0, dt = build(path)
        print(f"\n=== {name}: N = {model.grid.n}, p0 = {state0.pressure_bar[0]:.1f} бар, "
              f"BHP = {float(model.p_bhp_bar):.1f} бар, dt0 = {dt:g} с ===")
        while True:
            calls, rep_now = trace(model, state0, dt)
            print(f"-- dt = {dt:g} с")
            for stage, branch, cons, r in calls:
                print(f"   {stage:9s} {branch:5s} {cons:7s} {r}")
            print(f"   advance сейчас : {fmt(rep_now)} fb={rep_now.fallback} gl={rep_now.globalized} "
                  f"branch={rep_now.well_branch!r} sw_well={rep_now.well_switches}")
            _, rep_plan = advance_planned.__get__(model)(state0, dt)
            print(f"   advance по плану: {fmt(rep_plan)} fb={rep_plan.fallback} gl={rep_plan.globalized} "
                  f"branch={rep_plan.well_branch!r} sw_well={rep_plan.well_switches}")
            if rep_now.converged:
                break
            dt *= 0.5


if __name__ == "__main__":
    main()
