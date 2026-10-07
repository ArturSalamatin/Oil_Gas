"""DEBT-028: новые тесты плана (шаги 2-4) — проверка при планировании.

Ожидание: на текущем коде падают TestWellShutIn (кроме test_other_faces_unchanged,
test_producing_pwf_is_setpoint), TestPhaseFluxesFromComponents (нет функции) и
TestUpstreamWithZeroKro; с кодом плана (-p planned_plugin) — все проходят.

Запуск из каталога numerical_solver:
    $env:PYTHONPATH = "..\\vault\\issues\\debt-028\\probes"
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-028\\probes\\test_planned_debt028.py -q -p no:cacheprovider
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-028\\probes\\test_planned_debt028.py -q -p no:cacheprovider -p planned_plugin
"""
import sys
from pathlib import Path

import numpy as np
import pytest

_SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(_SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(_SOLVER_ROOT / "tests"))
sys.path.insert(0, str(_SOLVER_ROOT))

import gpn_multiphase_solver.fluxes as fl                                       # noqa: E402
from gpn_multiphase_solver.bc import PressureControl                            # noqa: E402
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions     # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA                               # noqa: E402
from radial_blackoil.state import BlackOilState                                 # noqa: E402

from test_fluxes import (pvt, relperm, grid_2ph, state_2ph,                     # noqa: E402,F401
                         P_EXT, T0, RS0, TestTwoPhaseAllFields)
import test_prototype_adapter as tpa                                            # noqa: E402
from test_prototype_adapter import (proto_pvt, proto_rp, proto_grid,            # noqa: E402,F401
                                    proto_rock, model, our_grid, our_pvt,
                                    adapter, bc)

P_WF_2PH = 6e6


@pytest.fixture
def bc_2ph():
    return BoundaryConditions(
        well=PressureControl(P_WF_2PH), p_ext=P_EXT,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)


@pytest.fixture
def result_2ph(state_2ph, grid_2ph, pvt, relperm, bc_2ph):
    return fl.compute_fluxes(state_2ph, grid_2ph, pvt, relperm, bc_2ph)


# ── шаг 2 ──

class TestWellShutIn:
    FIELDS = TestTwoPhaseAllFields.FIELDS

    @pytest.fixture
    def shut(self, state_2ph, grid_2ph, pvt, relperm):
        bc_shut = BoundaryConditions(
            well=PressureControl(10e6), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)
        return fl.compute_fluxes(state_2ph, grid_2ph, pvt, relperm, bc_shut)

    @pytest.mark.parametrize("field", TestTwoPhaseAllFields.FIELDS)
    def test_well_face_zero(self, shut, field):
        assert getattr(shut, field)[0] == 0.0

    def test_pwf_equals_p0(self, shut, state_2ph):
        assert shut.p_wf == state_2ph.p[0]

    def test_other_faces_unchanged(self, shut, result_2ph):
        for field in self.FIELDS:
            np.testing.assert_array_equal(getattr(shut, field)[1:],
                                          getattr(result_2ph, field)[1:])

    def test_producing_pwf_is_setpoint(self, result_2ph):
        assert result_2ph.p_wf == P_WF_2PH


# ── шаг 3 ──

class TestPhaseFluxesFromComponents:

    @staticmethod
    def _zeros(n):
        return np.zeros(n + 1), np.zeros(n + 1), np.zeros(n + 1)

    def test_upstream_by_pressure_when_G_o_zero(self, state_2ph, grid_2ph, pvt, bc_2ph):
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        G_free_gas[1] = -1.0
        G_g[1] = -1.0
        Bg = pvt.Bg(state_2ph.p)
        rho_g = pvt.rho_g(state_2ph.p)
        assert not np.isclose(Bg[0], Bg[1], rtol=1e-6)
        r = fl.phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                            grid_2ph, pvt, bc_2ph, P_WF_2PH)
        area = 2.0 * np.pi * grid_2ph.h * grid_2ph.r_faces[1]
        assert r.Q_g[1] == pytest.approx(-Bg[1], rel=1e-14)
        assert r.u_g[1] == pytest.approx(-Bg[1] / area, rel=1e-14)
        assert r.m_g[1] == pytest.approx(rho_g[1] * r.Q_g[1], rel=1e-14)

    def test_outer_inflow_gas_density_from_ext(self, state_2ph, grid_2ph, pvt, bc_2ph):
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        G_free_gas[N] = -1.0
        G_g[N] = -1.0
        p_ext_a = np.array([bc_2ph.p_ext])
        Bg_ext = pvt.Bg(p_ext_a)[0]
        rho_g_ext = pvt.rho_g(p_ext_a)[0]
        assert state_2ph.p[N - 1] < bc_2ph.p_ext
        assert not np.isclose(rho_g_ext, pvt.rho_g(state_2ph.p)[N - 1], rtol=1e-6)
        r = fl.phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                            grid_2ph, pvt, bc_2ph, P_WF_2PH)
        assert r.Q_g[N] == pytest.approx(-Bg_ext, rel=1e-14)
        assert r.m_g[N] == pytest.approx(rho_g_ext * r.Q_g[N], rel=1e-14)
        assert r.m_g[N] != 0.0

    def test_pwf_and_substeps_passed_through(self, state_2ph, grid_2ph, pvt, bc_2ph):
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        r = fl.phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                            grid_2ph, pvt, bc_2ph, 7.5e6,
                                            n_substeps=4)
        assert r.p_wf == 7.5e6
        assert r.n_substeps == 4
        assert r.state is state_2ph


# ── шаг 4 ──

class TestUpstreamWithZeroKro:

    def test_Q_g_uses_upstream_cell_by_pressure(self, adapter, our_pvt, our_grid, bc):
        N = tpa.N
        p = np.linspace(160e5, 200e5, N)
        Sg = np.zeros(N)
        Sg[:3] = 0.8
        Rs = np.where(Sg > 0, our_pvt.Rs_eq(p), tpa.RS0)
        state = SimulationState(p=p, Sg=Sg, Rs=Rs, T=np.full(N, tpa.T0),
                                regime=np.where(Sg > 0, 1, 2), t=0.0)
        proto = BlackOilState(pressure_bar=p / BAR_TO_PA, rs_sm3_sm3=Rs.copy(),
                              sg=Sg.copy(), gas_active=(Sg > 0))
        r = adapter._build_result(state, proto, bc)
        Bg = our_pvt.Bg(p)
        area = 2.0 * np.pi * our_grid.h * our_grid.r_faces
        for f in (1, 2):
            assert r.G_o[f] == 0.0
            assert r.G_free_gas[f] < 0.0
            assert not np.isclose(Bg[f], Bg[f - 1], rtol=1e-6)
            assert r.Q_g[f] == pytest.approx(r.G_free_gas[f] * Bg[f], rel=1e-14)
            assert r.u_g[f] == pytest.approx(r.Q_g[f] / area[f], rel=1e-14)
            assert r.m_g[f] == pytest.approx(our_pvt.rho_g_std * r.G_free_gas[f], rel=1e-12)
