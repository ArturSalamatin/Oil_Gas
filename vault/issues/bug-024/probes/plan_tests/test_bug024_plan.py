"""BUG-024: проверка тестов плана подменой ступени 4 — красные на коде базы, зелёные на варианте плана.

Копии тестов из шагов 1–2 плана (vault/plans/bug-024 stage4-rs-step-limit.md) с фикстурами,
повторёнными из tests/test_prototype_phase_switching.py и tests/test_prototype_cell_tolerance.py.
Запуск из numerical_solver (вариант — через плагин variant_plugin.py):
    $env:PYTHONPATH = "..\\vault\\issues\\bug-024\\probes"; $env:BUG024_VARIANT = "base"
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\bug-024\\probes\\plan_tests -q -p variant_plugin -p no:cacheprovider
    $env:BUG024_VARIANT = "satrel"; (то же)
"""

import copy
import sys
from pathlib import Path

import numpy as np
import pytest

SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.factory import SimulatorFactory              # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError      # noqa: E402
from gpn_multiphase_solver.io.config import load_config                 # noqa: E402
from radial_blackoil.state import BlackOilState                         # noqa: E402

DATA = SOLVER / "tests" / "data"
RS300 = DATA / "bug020_rs300" / "config.json"
BAR = 1e5
ATM_BAR = 101325.0 / BAR
DAY = 86400.0
DT_STAGE4 = 168.75
CELL_TOL = 1e-8


class _Stop(Exception):
    pass


def _proto(s):
    return BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(),
                         sg=s.Sg.copy(), gas_active=(s.regime == 1))


@pytest.fixture(scope="module")
def shutin_start():
    cfg = load_config(RS300)
    sim, init = SimulatorFactory.from_config(cfg)
    s = sim.run(init).states[-1]
    model = sim._hydro._model
    model.phase_switching_stage = True
    return model, _proto(s), cfg.initial_conditions.p0 / BAR


def _assert_restored(model):
    """Копия из tests/test_prototype_phase_switching.py: вне advance атрибуты ступеней — по умолчанию."""
    assert model._well_branch is None
    assert model._sg_lower_bound == -0.05
    assert model._line_search_l2 is False
    assert model._sg_step_max is None
    assert model._phase_switching is False
    assert model._upwind_frozen is None and model._upwind_left is None


def _measure(model, ps, new, dt):
    n = model.grid.n
    f = model.residual(model.pack(new), ps, dt, new.gas_active)
    w = dt / model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, ps.pressure_bar)
    return max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w)))


# ── шаг 1: ограничение шага R_s ──

def _first_update(model, ps, drs, monkeypatch):
    """z до и после одного обновления _newton_switching при направлении dp = 0, dS_g = 0, dR_s = drs."""
    n = model.grid.n
    mask = ps.gas_active.copy()
    zs = []
    orig_jac = model.finite_difference_jacobian

    def jac(z, *a, **kw):
        zs.append(z.copy())
        if len(zs) == 2:
            raise _Stop
        return orig_jac(z, *a, **kw)

    def lin(J, b):
        dz = np.zeros(2 * n)
        dz[n:][~mask] = drs
        return dz

    monkeypatch.setattr(model, "finite_difference_jacobian", jac)
    monkeypatch.setattr(model, "_linear_solve", lin)
    with pytest.raises(_Stop):
        model._newton_switching(ps, DT_STAGE4)
    return zs[0], zs[1], mask


class TestRsStepLimit:
    def test_large_rs_step_is_limited(self, shutin_start, monkeypatch):
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)
        z0, z1, mask = _first_update(model, ps, -1e4, monkeypatch)
        n = model.grid.n
        und = ~mask
        assert np.count_nonzero(und) > 0
        rs0, rs1 = z0[n:][und], z1[n:][und]
        lim = 0.2 * np.maximum(model.pvt.rs_sat(z0[:n][und]), 1.0)
        assert np.array_equal(rs1, np.maximum(rs0 - lim, 0.0))
        assert np.all(rs1 > 0.0)
        _assert_restored(model)

    def test_small_rs_step_unchanged(self, shutin_start, monkeypatch):
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)
        z0, z1, mask = _first_update(model, ps, 1e-3, monkeypatch)
        n = model.grid.n
        p = z0[:n]
        keep = ~mask & (z0[n:] + 1.0 < model.pvt.rs_sat(p))
        assert np.count_nonzero(keep) > 0
        assert np.array_equal(z1[n:][keep], z0[n:][keep] + 1e-3)


# ── шаг 1: условие по ячейке стоит в _newton_switching (переделка TestSwitching) ──

def test_switching_meets_cell_tol(shutin_start):
    model, ps, _ = shutin_start
    model.set_oil_rate_control(0.0, ATM_BAR)
    ct = model.cell_tol
    assert ct == CELL_TOL
    try:
        model.cell_tol = None
        a, ra = model._newton_switching(ps, DT_STAGE4)
        model.cell_tol = 1e-30
        c, rc = model._newton_switching(ps, DT_STAGE4)
        model.cell_tol = CELL_TOL
        b, rb = model._newton_switching(ps, DT_STAGE4)
    finally:
        model.cell_tol = ct
    print(f"без условия: {ra.converged} {ra.iterations}; 1e-30: {rc.converged} {rc.iterations}; "
          f"1e-8: {rb.converged} {rb.iterations}, мера {_measure(model, ps, b, DT_STAGE4):.2e}")
    assert ra.converged and not rc.converged
    assert rb.converged and _measure(model, ps, b, DT_STAGE4) <= CELL_TOL
    assert np.max(np.abs(b.pressure_bar - a.pressure_bar)) < 1e-7


# ── шаг 1: первые сутки сценария BUG-018 (перезамер test_first_day_with_cell_tol) ──

def test_first_day_with_cell_tol():
    cfg = load_config(DATA / "bug018_rs500" / "config.json")
    cfg.output.log_level = "ERROR"
    cfg.grid.N = 350
    sim, init = SimulatorFactory.from_config(cfg)
    calls = []
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        try:
            r = orig(state, dt, bc)
        except HydroConvergenceError:
            calls.append((dt, False))
            raise
        calls.append((dt, True))
        return r

    sim._hydro.solve = solve
    h = sim.run(init)
    assert calls == [(86400.0, False), (43200.0, False), (21600.0, True),
                     (21600.0, True), (43200.0, True)]
    st = h.states[-1]
    assert st.Sg[0] == pytest.approx(0.419040, abs=1e-5)
    assert st.p[0] == pytest.approx(5.141098e6, abs=100.0)


# ── шаг 2: суточный останов при штатном max_retries ──

def test_daily_shutin_passes_default_retries():
    cfg = load_config(RS300)
    cfg.output.log_level = "ERROR"
    hist = list(cfg.time.history)
    for _ in range(3):
        x = copy.deepcopy(hist[0])
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    assert cfg.time.dt_integration == DAY and cfg.numerics.max_retries == 9
    sim, init = SimulatorFactory.from_config(cfg)
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
        return r

    sim._hydro.solve = solve
    st = sim.run(init).states[-1]
    ok = [d for d, c in calls if c]
    failed = [d for d, c in calls if not c]
    print(f"принято {len(ok)}, отказов {len(failed)}, наименьший {min(ok)}, p {st.p[0] / BAR:.4f}, "
          f"T {st.T[0]:.4f}")
    assert len(ok) == 10 and len(failed) == 7
    assert sum(ok) == pytest.approx(3 * DAY, rel=1e-12)
    assert min(ok) == 5400.0
    assert st.p[0] / BAR == pytest.approx(327.2428, abs=1e-3)
    assert st.T[0] == pytest.approx(375.3667, abs=1e-3)
