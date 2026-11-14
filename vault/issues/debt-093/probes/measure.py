"""Измерить два сценария DEBT-093 без изменения тестов и решателя."""

import copy
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[4]
SOLVER = ROOT / "numerical_solver"
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER))

from radial_blackoil import blackoil
from tests.test_prototype_failure_diagnostics import _bug018_model
from tests.test_prototype_phase_switching import BAR, DAY, RS300
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from gpn_multiphase_solver.io.config import load_config


def cell_case(with_floor, capture):
    model, state, dt = _bug018_model()
    cls = type(model)
    original_check = cls._cells_converged
    original_kappa = blackoil.CELL_FLOOR_KAPPA
    calls = []

    def check(self, f, w, J=None, z=None):
        result = original_check(self, f, w, J, z)
        row = {"result": result, "jacobian": J is not None, "weights": w is not None}
        if w is not None and J is not None and z is not None:
            weights = np.concatenate((w, w))
            residual = np.abs(f.copy())
            limit = abs(J.copy()) @ np.spacing(np.abs(z.copy()))
            above = ~(residual * weights <= self.cell_tol)
            row.update(above=int(np.count_nonzero(above)),
                       failed=np.flatnonzero(above & ~(residual <= blackoil.CELL_FLOOR_KAPPA * limit)).tolist(),
                       max_measure=float(np.max(residual * weights)),
                       max_limit=float(np.max(limit * weights)))
        calls.append(row)
        return result

    try:
        blackoil.CELL_FLOOR_KAPPA = original_kappa if with_floor else 0.0
        if capture:
            cls._cells_converged = check
        z = model.pack(state, state.gas_active)
        _, report = model._newton_fixed_active_set(z, state, dt, state.gas_active)
        fields = {name: getattr(report, name) for name in
                  ("converged", "iterations", "exit_reason", "cell_measure", "cell_floor")}
        return {"report": fields, "calls": calls}
    finally:
        cls._cells_converged = original_check
        blackoil.CELL_FLOOR_KAPPA = original_kappa


def shutin_case(unlimited):
    cfg = load_config(RS300)
    cfg.output.log_level = "ERROR"
    hist = list(cfg.time.history)
    for _ in range(3):
        entry = copy.deepcopy(hist[0])
        entry.control, entry.p_wf, entry.q_oil, entry.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(entry)
    cfg.time.history = hist
    sim, initial = SimulatorFactory.from_config(cfg)
    cls = type(sim._hydro._model)
    original_newton = cls._newton_switching
    signature = inspect.signature(original_newton)
    stages = []
    calls = []
    original_solve = sim._hydro.solve

    def newton(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        bound.arguments["dr_rel"] = 1e30
        stages.append({"dt": bound.arguments["dt_s"], "dr_rel": bound.arguments["dr_rel"]})
        return original_newton(*bound.args, **bound.kwargs)

    def solve(state, dt, bc):
        shut = state.t >= 10 * DAY - 1e-6
        try:
            result = original_solve(state, dt, bc)
        except HydroConvergenceError:
            if shut:
                calls.append([float(dt), False])
            raise
        if shut:
            calls.append([float(dt), True])
        return result

    try:
        if unlimited:
            cls._newton_switching = newton
        sim._hydro.solve = solve
        try:
            state = sim.run(initial).states[-1]
            result = {"p_bar": float(state.p[0] / BAR), "T_K": float(state.T[0]),
                      "finite": bool(np.all(np.isfinite(state.p)) and np.all(np.isfinite(state.T)))}
        except (HydroConvergenceError, RuntimeError) as exc:
            result = {"error": str(exc)}
        accepted = [dt for dt, ok in calls if ok]
        result.update(calls=calls, accepted_sum=sum(accepted),
                      accepted_min=min(accepted) if accepted else None, stages=stages)
        return result
    finally:
        cls._newton_switching = original_newton


if __name__ == "__main__":
    print("Python", sys.version)
    print("NumPy", np.__version__, "SciPy", scipy.__version__)
    print("NumPy configuration:")
    np.show_config()
    print("SciPy configuration:")
    scipy.show_config()
    print("RESULTS")
    for floor in (True, False):
        plain = cell_case(floor, False)
        observed = cell_case(floor, True)
        print("cell", floor, json.dumps({"plain": plain, "observed": observed}, ensure_ascii=False))
    for unlimited in (False, True):
        print("shutin", unlimited, json.dumps(shutin_case(unlimited), ensure_ascii=False))
