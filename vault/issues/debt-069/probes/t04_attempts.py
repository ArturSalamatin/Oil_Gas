"""DEBT-069 (/plan-improve): попытки ступеней advance на первом шаге T04 (сценарий теста прототипа DEBT-030).

Перехват _advance_phases на экземпляре, как в attempts_probe.py; ступень — по флагам модели.
Запуск из numerical_solver/HydroSolverPrototype/Prototype_1.0.3 (P — путь к скрипту):
    ..\\..\\.venv\\Scripts\\python P
"""

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import radial_blackoil  # noqa: E402
from tests.helpers import ROOT, model_and_state  # noqa: E402

T04 = ROOT / 'regression' / 'inputs' / 'T04.xlsx'


def stage_of(m):
    if m._phase_switching:
        return 4
    if m._line_search_l2:
        return 3
    if m._sg_lower_bound is None:
        return 2
    return 1


print(f"прототип: {Path(radial_blackoil.__file__).parent}")
_, m, s = model_and_state(n=100, bhp=100.0, p0=200.0, case=T04)
print(f"T04: p_wf = {m.p_bhp_bar} бар, p_ext = {m.p_outer_bar} бар, phase_switching_stage = {m.phase_switching_stage}")
log = []
states = []
orig = m._advance_phases


def wrapped(state_old, dt_s, *a, **kw):
    new, rep = orig(state_old, dt_s, *a, **kw)
    log.append((stage_of(m), m._well_branch or "", replace(rep), float(new.pressure_bar[0])))
    states.append(new.copy())
    return new, rep


m._advance_phases = wrapped
_, rep = m.advance(s, 60.0)
for stage, branch, r, p0 in log:
    print(f"  ступень {stage} {branch or '-':5s} сошлась={r.converged!s:5s} выход={r.exit_reason:12s} итераций {r.iterations:3d} "
          f"проходов {r.active_set_iterations:3d} переключений {r.phase_switches:4d} невязка {r.residual_inf:.2e} p[0] = {p0:.3f}")
print(f"  итог: сошлась={rep.converged} выход={rep.exit_reason} итераций {rep.iterations} невязка {rep.residual_inf:.2e} "
      f"проходов {rep.active_set_iterations} переключений {rep.phase_switches} ветка={rep.well_branch!r} смен={rep.well_switches}")
# Ступень 2 «открыта» против ступени 1 (аудит 1 DEBT-069): побитово ли состояние и числа отчёта
import numpy as np  # noqa: E402
for k, (stage, branch, r, _) in enumerate(log):
    if stage == 2 and branch == "open":
        r1 = log[0][2]
        same_state = all(np.array_equal(getattr(states[0], f), getattr(states[k], f))
                         for f in ("pressure_bar", "sg", "rs_sm3_sm3", "gas_active"))
        keys = ("iterations", "active_set_iterations", "phase_switches", "residual_inf", "exit_reason", "cell_measure")
        same_rep = all(getattr(r1, f) == getattr(r, f) for f in keys)
        print(f"  ступень 2 «открыта» против ступени 1: состояние побитово {same_state}, числа отчёта побитово {same_rep}")
