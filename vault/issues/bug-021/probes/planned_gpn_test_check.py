"""BUG-021: тело изменённого test_sg_step_limited_in_third_stage (tests/test_prototype_globalization.py).

Тест собирает приближения Ньютона третьей ступени по вызовам finite_difference_jacobian. С
вариантом 2 якобиан в сошедшемся приближении не строится, и последнее обновление каждого
вызова выпадает из проверки |dS_g| <= 0.2. План добавляет в перехват _newton_fixed_active_set
возвращённое приближение. Проба: число пар и max|dS_g| — без добавки и с ней, на текущем коде
и на варианте 2.

Запуск — из каталога numerical_solver: .venv\\Scripts\\python <P>\\planned_gpn_test_check.py
"""
import logging
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path.cwd() / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(HERE))
logging.disable(logging.INFO)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402
from tests.test_prototype_globalization import BUG016_CASE, SG_STEP_MAX, _assert_restored  # noqa: E402


def run(with_final):
    cfg = load_config(BUG016_CASE)
    cfg.grid.N = 100
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    _, dt = sim._schedule.substeps(0)
    model.set_bhp_control(cfg.time.history[0].p_wf / 1e5)
    calls = []
    orig_newton = model._newton_fixed_active_set
    orig_jac = model.finite_difference_jacobian

    # ── тело «После» плана ──
    def newton(z0, state_old, dt_s, gas_active, **kw):
        calls.append([])
        z, rep = orig_newton(z0, state_old, dt_s, gas_active, **kw)
        if with_final and model._sg_step_max is not None:
            calls[-1].append((z.copy(), gas_active.copy()))
        return z, rep

    def jac(z, state_old, dt_s, gas_active, **kw):
        if model._sg_step_max is not None:
            calls[-1].append((z.copy(), gas_active.copy()))
        return orig_jac(z, state_old, dt_s, gas_active, **kw)

    model._newton_fixed_active_set = newton
    model.finite_difference_jacobian = jac
    s0 = BlackOilState(pressure_bar=init.p / 1e5, rs_sm3_sm3=init.Rs.copy(),
                       sg=init.Sg.copy(), gas_active=(init.regime == 1))
    _, rep = model.advance(s0, dt)
    assert rep.converged and rep.globalized
    n = model.grid.n
    steps = [np.abs(b[0][n:][b[1]] - a[0][n:][a[1]]).max()
             for seq in calls for a, b in zip(seq, seq[1:]) if b[1].any()]
    assert steps and max(steps) <= SG_STEP_MAX + 1e-12
    _assert_restored(model)
    return len(steps), max(steps)


for label in ("текущий код", "вариант 2"):
    if label == "вариант 2":
        import planned_code
        planned_code.apply(2)
    for wf in (False, True):
        k, m = run(wf)
        print(f"{label}, {'с последним приближением' if wf else 'только точки якобиана'}: пар {k}, max|dS_g| = {m:.6f}")
