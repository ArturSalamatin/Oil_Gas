"""Аудит DEBT-019: проверка реализуемости теста 3 (шаг 5б плана).

Вопрос: если задать p_wf ВЫШЕ пластового давления и прогнать
PrototypeHydroAdapter.solve, действительно ли получится G_o[0] > 0,
то есть сработает ли проверка, которую предлагает план?

Риски, которые проверяются:
  1. Прототип может не сойтись при закачке → RuntimeError A-retry
     вместо ValueError. Тогда тест плана нереализуем в таком виде.
  2. Знак может оказаться иным из-за инверсии well-потока
     (P2-знаки-потоков-прототип.md: G_o[0] = -fluxes['oil_well']).

Скрипт НИЧЕГО не меняет в коде: только вызывает существующий адаптер.
"""

import sys
from pathlib import Path

import numpy as np

_SOLVER_ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
_PROTO_ROOT = _SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
sys.path.insert(0, str(_PROTO_ROOT))
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

# Параметры — копия из tests/test_prototype_adapter.py
R_WELL, R_EXT, H, N = 0.1, 50.0, 10.0, 20
K_PERM = 1e-13
K_MD = K_PERM * M2_TO_MD
PHI = 0.2
P0_PA = 200e5
P0_BAR = P0_PA / BAR_TO_PA
T0, RS0 = 350.0, 30.0
RHO_O_STD, RHO_G_STD = 850.0, 0.85
DT = 3600.0

OIL_ROWS = [(0.0, 50.0, 1.05, 3.0), (0.0, 300.0, 1.04, 3.2),
            (30.0, 150.0, 1.20, 1.5), (30.0, 300.0, 1.18, 1.6)]
GAS_ROWS = [(50.0, 0.020, 0.012), (150.0, 0.008, 0.014),
            (300.0, 0.004, 0.018)]
SG_TAB = [0.0, 0.1, 0.2, 0.4, 0.6, 0.8]
KRO_TAB = [1.0, 0.8, 0.6, 0.3, 0.1, 0.0]
KRG_TAB = [0.0, 0.01, 0.05, 0.2, 0.5, 0.8]


def run(p_wf_pa: float, label: str) -> None:
    """Прогнать adapter.solve при заданном p_wf и напечатать знак G_o[0]."""
    proto_pvt = BlackOilPVT(OIL_ROWS, GAS_ROWS)
    model = RadialBlackOilModel(
        grid=RadialGrid(R_WELL, R_EXT, H, N, K_MD),
        rock=CompressibleRock(phi_ref=PHI, p_ref_bar=P0_BAR, cr_per_bar=0.0),
        pvt=proto_pvt,
        relperm=TabulatedRelPerm(SG_TAB, KRO_TAB, KRG_TAB),
        p_bhp_bar=p_wf_pa / BAR_TO_PA, p_outer_bar=P0_BAR,
        outer_rs_sm3_sm3=RS0, skin=0.0)

    our_pvt = PrototypePVTAdapter(proto_pvt, rho_o_std=RHO_O_STD,
                                  rho_g_std=RHO_G_STD)
    adapter = PrototypeHydroAdapter(
        model, LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=N, k=K_PERM),
        our_pvt)

    state = SimulationState(
        p=np.full(N, P0_PA), Sg=np.zeros(N), Rs=np.full(N, RS0),
        T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
    bc = BoundaryConditions(well=PressureControl(p_wf_pa), p_ext=P0_PA,
                            T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)

    print(f"\n--- {label}: p_wf = {p_wf_pa/1e5:.0f} бар, p0 = {P0_PA/1e5:.0f} бар ---")
    try:
        res = adapter.solve(state, dt=DT, bc=bc)
    except Exception as exc:
        print(f"  ИСКЛЮЧЕНИЕ {type(exc).__name__}: {str(exc)[:200]}")
        return

    print(f"  G_o[0]      = {res.G_o[0]:+.6e} м³ст/с")
    print(f"  G_o[N]      = {res.G_o[N]:+.6e} м³ст/с")
    print(f"  Q_o[0]      = {res.Q_o[0]:+.6e} м³пл/с")
    print(f"  p[0]        = {res.state.p[0]/1e5:.3f} бар")
    print(f"  p[0] - p_wf = {(res.state.p[0] - p_wf_pa)/1e5:+.3f} бар")
    print(f"  ВТЕКАНИЕ (G_o[0] > 0): {bool(res.G_o[0] > 0)}")


if __name__ == "__main__":
    run(150e5, "добыча (штатный режим)")
    run(250e5, "закачка: p_wf на 50 бар ВЫШЕ пластового")
    run(200e5, "равновесие: p_wf = p0")
