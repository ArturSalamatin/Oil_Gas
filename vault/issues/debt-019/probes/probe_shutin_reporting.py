"""Аудит DEBT-019: что рапортует решатель, когда прототип глушит скважину.

Прототип реализует producer-only семантику (blackoil.py:78-88): при
p_bhp >= p[0] он НЕ разворачивает поток, а глушит скважину — qow = 0,
а эффективное забойное давление всплывает к p[0].

Вопросы аудита:
  1. Совпадает ли WellData.p_wf, который пишет Simulator, с эффективным
     давлением прототипа (_last_effective_bhp_bar)?
  2. Наблюдаем ли пользователь факт глушения хоть как-нибудь?

Скрипт ничего не меняет: только читает состояние прототипа после solve.
"""

import sys
from pathlib import Path

import numpy as np

_SOLVER_ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(_SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(_SOLVER_ROOT))

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from radial_blackoil.grid import RadialGrid                      # noqa: E402
from radial_blackoil.rock import CompressibleRock                # noqa: E402
from radial_blackoil.pvt import BlackOilPVT                      # noqa: E402
from radial_blackoil.relperm import TabulatedRelPerm             # noqa: E402
from radial_blackoil.blackoil import RadialBlackOilModel         # noqa: E402

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid   # noqa: E402
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypePVTAdapter  # noqa: E402
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions  # noqa: E402
from gpn_multiphase_solver.bc import PressureControl              # noqa: E402
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA, M2_TO_MD       # noqa: E402

R_WELL, R_EXT, H, N = 0.1, 50.0, 10.0, 20
K_PERM = 1e-13
K_MD = K_PERM * M2_TO_MD
PHI = 0.2
P0_PA = 200e5
P0_BAR = P0_PA / BAR_TO_PA
T0, RS0 = 350.0, 30.0
DT = 3600.0

OIL_ROWS = [(0.0, 50.0, 1.05, 3.0), (0.0, 300.0, 1.04, 3.2),
            (30.0, 150.0, 1.20, 1.5), (30.0, 300.0, 1.18, 1.6)]
GAS_ROWS = [(50.0, 0.020, 0.012), (150.0, 0.008, 0.014),
            (300.0, 0.004, 0.018)]


def run(p_wf_pa: float, label: str):
    proto_pvt = BlackOilPVT(OIL_ROWS, GAS_ROWS)
    model = RadialBlackOilModel(
        grid=RadialGrid(R_WELL, R_EXT, H, N, K_MD),
        rock=CompressibleRock(phi_ref=PHI, p_ref_bar=P0_BAR, cr_per_bar=0.0),
        pvt=proto_pvt,
        relperm=TabulatedRelPerm([0.0, 0.1, 0.2, 0.4, 0.6, 0.8],
                                 [1.0, 0.8, 0.6, 0.3, 0.1, 0.0],
                                 [0.0, 0.01, 0.05, 0.2, 0.5, 0.8]),
        p_bhp_bar=p_wf_pa / BAR_TO_PA, p_outer_bar=P0_BAR,
        outer_rs_sm3_sm3=RS0, skin=0.0)

    adapter = PrototypeHydroAdapter(
        model, LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=N, k=K_PERM),
        PrototypePVTAdapter(proto_pvt, rho_o_std=850.0, rho_g_std=0.85))

    state = SimulationState(
        p=np.full(N, P0_PA), Sg=np.zeros(N), Rs=np.full(N, RS0),
        T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
    bc = BoundaryConditions(well=PressureControl(p_wf_pa), p_ext=P0_PA,
                            T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)

    res = adapter.solve(state, dt=DT, bc=bc)

    # Что рапортует Simulator в WellData.p_wf (simulator.py:165-172):
    reported = bc.well.boundary_pressure(res.state, None, None, None)
    # Что фактически применил прототип:
    effective = model._last_effective_bhp_bar * BAR_TO_PA

    print(f"\n--- {label} ---")
    print(f"  задано p_wf (в WellData):  {reported/1e5:8.3f} бар")
    print(f"  эффективное BHP прототипа: {effective/1e5:8.3f} бар")
    print(f"  расхождение:               {(reported-effective)/1e5:+8.3f} бар")
    print(f"  дебит q_o = -G_o[0]:       {-res.G_o[0]:+.6e} м³ст/с")
    print(f"  скважина заглушена:        {bool(res.G_o[0] == 0.0)}")


if __name__ == "__main__":
    run(150e5, "добыча: p_wf = 150 бар < p0")
    run(200e5, "равновесие: p_wf = p0 = 200 бар")
    run(250e5, "закачка запрошена: p_wf = 250 бар > p0")
