"""DEBT-015, аудит: тесты раздела 7 плана (Т1–Т15) против кода плана (плагин plan_code).

FailingHydroStub — дословно из шага 3.4 плана. Т10 — на сценарии tests/data/bug018_rs500
(адаптер из фабрики), а не на фикстурах test_prototype_adapter.py: проверяется то же
утверждение «адаптер не дробит, отказ — HydroConvergenceError».

Запуск из numerical_solver:
    $env:PYTHONPATH = "..\\vault\\issues\\debt-015\\probes;."
    .venv\\Scripts\\python -m pytest -p plan_code ..\\vault\\issues\\debt-015\\probes\\test_plan_debt015.py -q
"""
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.hydro.base import HydroSolver, HydroConvergenceError
from gpn_multiphase_solver.simulator import Simulator
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.state import SimulationState, HydroResult, BoundaryConditions
from radial_blackoil.blackoil import BlackOilNewtonReport

from tests.test_simulator import (_make_simulator, _single_interval_schedule,
                                  _initial_state, _CountingEnergySolver)
from tests.test_mass_balance import _FluxIntegralStub

DATA = Path.cwd() / "tests" / "data"
DAY = 86400.0
BAR = 1e5


class FailingHydroStub(HydroSolver):
    """Двойник, отказывающий на заданных подшагах, — проверка локального дробления (DEBT-015)."""

    def __init__(self, inner: HydroSolver, fails):
        self._inner = inner
        self._fails = fails
        self.dt_calls: list[float] = []      # dt каждого вызова solve

    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        self.dt_calls.append(dt)
        if self._fails(state, dt):
            raise HydroConvergenceError(
                f"двойник: отказ при dt = {dt:g} с, t = {state.t:g} с")
        return self._inner.solve(state, dt, bc)

    def component_inventories(self, state: SimulationState):
        return self._inner.component_inventories(state)


def _run(fails, max_retries=None):
    grid, pvt, inner_hydro, inner_energy, _ = _make_simulator()
    hydro = FailingHydroStub(inner_hydro, fails)
    energy = _CountingEnergySolver(inner_energy)
    schedule = _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0)
    kw = {} if max_retries is None else {"max_retries": max_retries}
    sim = Simulator(grid, hydro, energy, pvt, schedule, **kw)
    return sim, hydro, energy


# ── 7.1 ──
def test_T1():
    sim, hydro, energy = _run(lambda s, dt: dt > 1800.0)
    sim.run(_initial_state())
    assert hydro.dt_calls == [3600.0, 1800.0, 1800.0]
    assert energy.dt_calls == [1800.0, 1800.0]
    assert sum(energy.dt_calls) == pytest.approx(3600.0)


def test_T2():
    sim, hydro, energy = _run(lambda s, dt: False)
    sim.run(_initial_state())
    assert hydro.dt_calls == [3600.0]
    assert energy.dt_calls == [3600.0]


def test_T3():
    sim, hydro, energy = _run(lambda s, dt: dt > 1800.0)
    history = sim.run(_initial_state())
    assert history.n_saved == 2
    assert history.times[-1] == pytest.approx(3600.0)


def test_T4():
    sim, hydro, energy = _run(lambda s, dt: dt > 1800.0 or (dt > 900.0 and s.t >= 1800.0))
    sim.run(_initial_state())
    assert hydro.dt_calls == [3600.0, 1800.0, 1800.0, 900.0, 900.0]
    assert energy.dt_calls == [1800.0, 900.0, 900.0]


def test_T5():
    sim, hydro, energy = _run(lambda s, dt: s.t < 900.0 and dt > 900.0)
    sim.run(_initial_state())
    assert hydro.dt_calls == [3600.0, 1800.0, 900.0, 900.0, 1800.0]
    assert energy.dt_calls == [900.0, 900.0, 1800.0]


def test_T6():
    sim, hydro, energy = _run(lambda s, dt: True, max_retries=2)
    with pytest.raises(RuntimeError,
                       match=r"^HydroSolver не сошёлся при дроблении шага до dt/4 = ") as exc:
        sim.run(_initial_state())
    msg = str(exc.value)
    assert "time.dt_integration" in msg and "numerics.max_retries" in msg
    assert hydro.dt_calls == [3600.0, 1800.0, 900.0]
    assert energy.dt_calls == []


def test_T7():
    class _Broken(FailingHydroStub):
        def solve(self, state, dt, bc):
            self.dt_calls.append(dt)
            raise RuntimeError("сбой двойника")

    grid, pvt, inner_hydro, inner_energy, _ = _make_simulator()
    hydro = _Broken(inner_hydro, lambda s, dt: False)
    sim = Simulator(grid, hydro, inner_energy, pvt,
                    _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
    with pytest.raises(RuntimeError, match="сбой двойника"):
        sim.run(_initial_state())
    assert hydro.dt_calls == [3600.0]


# ── 7.2 ──
def _mass_run(fails):
    grid, pvt, inner, energy, _ = _make_simulator()
    hydro = FailingHydroStub(_FluxIntegralStub(grid, pvt, inner._relperm), fails)
    sim = Simulator(grid, hydro, energy, pvt,
                    _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
    return hydro, sim.run(_initial_state())


def test_T8():
    hydro, history = _mass_run(lambda s, dt: dt > 1800.0)
    assert hydro.dt_calls == [3600.0, 1800.0, 1800.0]
    assert history.mass_balance[-1] is not None
    assert history.mass_balance[0]["cum_o_well"] == 0.0
    G0 = history.hydro_results[-1].G_o[0]
    assert history.mass_balance[-1]["cum_o_well"] == pytest.approx(3600.0 * G0, rel=1e-12)


def test_T9():
    hydro, history = _mass_run(lambda s, dt: dt > 1800.0 or (dt > 900.0 and s.t >= 1800.0))
    assert hydro.dt_calls == [3600.0, 1800.0, 1800.0, 900.0, 900.0]
    G0 = history.hydro_results[-1].G_o[0]
    assert history.mass_balance[-1]["cum_o_well"] == pytest.approx(3600.0 * G0, rel=1e-12)


# ── 7.3, 7.4 (сценарий bug018_rs500, как _sim в test_prototype_activation_cap.py) ──
def _sim018(retries=None):
    cfg = load_config(DATA / "bug018_rs500" / "config.json")
    cfg.output.log_level = "ERROR"
    if retries is not None:
        cfg.numerics.max_retries = retries
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    return sim, init, dt


def test_T10():
    sim, init, dt = _sim018()
    model = sim._hydro._model
    calls = []

    def always_fails(state_old, dt_s, *a, **kw):
        calls.append(dt_s)
        return state_old.copy(), BlackOilNewtonReport(False, 0, 1.0)

    model.advance = always_fails
    with pytest.raises(HydroConvergenceError, match="advance не сошёлся"):
        sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
    assert calls == [dt]


def test_T11():
    sim, init, dt = _sim018(retries=1)
    model = sim._hydro._model
    calls = []

    def always_fails(state_old, dt_s, *a, **kw):
        calls.append(dt_s)
        return state_old.copy(), BlackOilNewtonReport(False, 0, 1.0)

    model.advance = always_fails
    with pytest.raises(RuntimeError) as exc:
        sim.run(init)
    msg = str(exc.value)
    assert msg.startswith("HydroSolver не сошёлся при дроблении шага до dt/2 = ")
    assert "t = 0.0000 сут" in msg
    assert "двухфазных ячеек 0 из 50" in msg
    assert "time.dt_integration" in msg and "numerics.max_retries" in msg
    assert "малоподвижны" not in msg
    assert calls == [dt, dt / 2]


def test_without_cap_fails():
    sim, init, dt = _sim018()
    sim._hydro._model.sg_activation_cap = None
    with pytest.raises(HydroConvergenceError):
        sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)


# ── 7.6 ──
class _Stop(Exception):
    pass


def _run_rs150(flag, stop_after_first_ok=False):
    cfg = load_config(DATA / "bug020_rs150" / "config.json")
    sim, init = SimulatorFactory.from_config(cfg)
    sim._hydro._model.phase_switching_stage = flag
    calls = []
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        shut = state.t >= 10 * DAY - 1e-6
        try:
            r = orig(state, dt, bc)
        except HydroConvergenceError:
            if shut:
                calls.append((dt, False))
            raise
        if shut:
            calls.append((dt, True))
            if stop_after_first_ok:
                raise _Stop
        return r

    sim._hydro.solve = solve
    try:
        return sim.run(init), calls
    except _Stop:
        # Обрыв после первой удачи на останове: история не нужна, calls — да
        return None, calls


def test_T12():
    h, calls = _run_rs150(True)
    assert calls == [(3600.0, True)]
    st = h.states[-1]
    assert st.p[0] / BAR == pytest.approx(176.6086, abs=1e-3)
    assert int(np.count_nonzero(st.regime == 1)) == 263
    assert st.T[0] == pytest.approx(397.7928, abs=1e-3)


def test_T13a():
    h, calls = _run_rs150(False, stop_after_first_ok=True)
    assert h is None
    assert calls[0] == (3600.0, False)
    assert calls[-1][1] is True
    assert calls[-1][0] < 3600.0
    print(calls)


def test_T13b():
    h, calls = _run_rs150(False)
    ok = [dt for dt, c in calls if c]
    fail = [dt for dt, c in calls if not c]
    assert len(ok) == 60 and len(fail) == 34
    assert sum(ok) == pytest.approx(3600.0, rel=1e-12)
    st = h.states[-1]
    assert st.p[0] / BAR == pytest.approx(185.3065, abs=1e-3)
    assert int(np.count_nonzero(st.regime == 1)) == 255
    assert st.T[0] == pytest.approx(397.8867, abs=1e-3)


# ── Т14, Т15 (TABLE_CONFIG — как в test_factory_prototype.py) ──
def _table_config():
    from tests.test_factory_prototype import TABLE_CONFIG
    return load_config(TABLE_CONFIG)


def test_T14():
    config = _table_config()
    config.numerics.max_retries = 7
    simulator, _ = SimulatorFactory.from_config(config)
    assert simulator._max_retries == 7
    assert not hasattr(simulator._hydro, "_max_retries")


def test_T15():
    simulator, _ = SimulatorFactory.from_config(_table_config())
    assert simulator._max_retries == 9
