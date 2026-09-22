"""Аудит DEBT-019: проверка реализуемости тестов 3 и 4 из плана.

Запускается pytest-ом ИЗ КАТАЛОГА numerical_solver, чтобы подхватился
tests/conftest.py с путём к прототипу:

    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-019\\probes\\test_probe_guard_feasibility.py -v

Проверяется механика, а не сам запрет (проверки в коде ещё нет):
  1. monkeypatch подменяет face_component_fluxes_sm3s на экземпляре model,
     и подменённое значение действительно доходит до G_o[0] > 0.
  2. Прототип при p_wf > p0 глушит скважину (G_o[0] == 0), а не
     разворачивает поток.

Если обе проверки зелёные — тесты плана реализуемы в предложенном виде.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

_SOLVER_ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(_SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(_SOLVER_ROOT))

from radial_blackoil.grid import RadialGrid
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.pvt import BlackOilPVT
from radial_blackoil.relperm import TabulatedRelPerm
from radial_blackoil.blackoil import RadialBlackOilModel

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypePVTAdapter
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.units import BAR_TO_PA, M2_TO_MD

R_WELL, R_EXT, H, N = 0.1, 50.0, 10.0, 20
K_PERM = 1e-13
K_MD = K_PERM * M2_TO_MD
PHI = 0.2
P0_PA = 200e5
P0_BAR = P0_PA / BAR_TO_PA
P_WF_PA = 150e5
T0, RS0 = 350.0, 30.0
DT = 3600.0

OIL_ROWS = [(0.0, 50.0, 1.05, 3.0), (0.0, 300.0, 1.04, 3.2),
            (30.0, 150.0, 1.20, 1.5), (30.0, 300.0, 1.18, 1.6)]
GAS_ROWS = [(50.0, 0.020, 0.012), (150.0, 0.008, 0.014),
            (300.0, 0.004, 0.018)]


@pytest.fixture
def proto_pvt():
    return BlackOilPVT(OIL_ROWS, GAS_ROWS)


@pytest.fixture
def model(proto_pvt):
    return RadialBlackOilModel(
        grid=RadialGrid(R_WELL, R_EXT, H, N, K_MD),
        rock=CompressibleRock(phi_ref=PHI, p_ref_bar=P0_BAR, cr_per_bar=0.0),
        pvt=proto_pvt,
        relperm=TabulatedRelPerm([0.0, 0.1, 0.2, 0.4, 0.6, 0.8],
                                 [1.0, 0.8, 0.6, 0.3, 0.1, 0.0],
                                 [0.0, 0.01, 0.05, 0.2, 0.5, 0.8]),
        p_bhp_bar=P_WF_PA / BAR_TO_PA, p_outer_bar=P0_BAR,
        outer_rs_sm3_sm3=RS0, skin=0.0)


@pytest.fixture
def our_grid():
    return LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=N, k=K_PERM)


@pytest.fixture
def our_pvt(proto_pvt):
    return PrototypePVTAdapter(proto_pvt, rho_o_std=850.0, rho_g_std=0.85)


@pytest.fixture
def adapter(model, our_grid, our_pvt):
    return PrototypeHydroAdapter(model, our_grid, our_pvt)


@pytest.fixture
def initial_state():
    return SimulationState(
        p=np.full(N, P0_PA), Sg=np.zeros(N), Rs=np.full(N, RS0),
        T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)


@pytest.fixture
def bc():
    return BoundaryConditions(well=PressureControl(P_WF_PA), p_ext=P0_PA,
                              T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)


def test_monkeypatch_reaches_G_o(adapter, model, initial_state, bc,
                                 monkeypatch):
    """Подмена face_component_fluxes_sm3s доходит до G_o[0].

    Механика теста 3 плана. Инверсия well-потока означает, что
    oil_well = -1e-3 должно дать G_o[0] = +1e-3.
    """
    orig = model.face_component_fluxes_sm3s

    def fake_fluxes(proto_state):
        f = dict(orig(proto_state))
        f['oil_well'] = -1.0e-3
        return f

    monkeypatch.setattr(model, "face_component_fluxes_sm3s", fake_fluxes)

    res = adapter.solve(initial_state, dt=DT, bc=bc)
    assert res.G_o[0] == pytest.approx(1.0e-3), \
        "подмена не дошла до G_o[0] — тест 3 плана нереализуем в этом виде"


def test_prototype_shuts_in(model, our_grid, our_pvt, initial_state):
    """p_wf выше пластового → заглушено, поток не развёрнут (тест 4)."""
    p_wf_above = P0_PA + 50e5
    model.set_bhp_control(p_wf_above / BAR_TO_PA)
    adapter = PrototypeHydroAdapter(model, our_grid, our_pvt)
    bc_inj = BoundaryConditions(well=PressureControl(p_wf_above),
                                p_ext=P0_PA, T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)

    res = adapter.solve(initial_state, dt=DT, bc=bc_inj)

    assert res.G_o[0] == pytest.approx(0.0, abs=1e-15)
    assert res.G_o[0] <= 0.0
