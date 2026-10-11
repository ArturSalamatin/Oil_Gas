"""DEBT-063, проба: откуда допуск 2 % в test_prototype_adapter::TestMassBalance.

Докстринг теста объясняет допуск «разными центрами ячеек». Но баланс в тесте
собран из объёмов ячеек (у обеих сеток одинаковы: грани общие) и потоков
G_o прототипа — центры в него не входят. Проба повторяет фикстуры теста
(N = 20, один шаг 3600 с) и печатает невязку баланса нефти по ячейкам в
двух вариантах накопления: B_o нашей обёртки PVT (как в тесте) и запасы
самого прототипа (component_inventories).

Запуск из numerical_solver/:  .venv\\Scripts\\python ..\\vault\\issues\\debt-063\\probes\\adapter_balance.py
"""

import sys
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import numpy as np

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

# Параметры — как в tests/test_prototype_adapter.py
R_WELL, R_EXT, H, N, K_PERM, PHI = 0.1, 50.0, 10.0, 20, 1e-13, 0.2
P0_PA, P_WF_PA, T0, RS0, DT = 200e5, 150e5, 350.0, 30.0, 3600.0
OIL_ROWS = [(0.0, 50.0, 1.05, 3.0), (0.0, 300.0, 1.04, 3.2),
            (30.0, 150.0, 1.20, 1.5), (30.0, 300.0, 1.18, 1.6)]
GAS_ROWS = [(50.0, 0.020, 0.012), (150.0, 0.008, 0.014), (300.0, 0.004, 0.018)]
SG_TAB = [0.0, 0.1, 0.2, 0.4, 0.6, 0.8]
KRO_TAB = [1.0, 0.8, 0.6, 0.3, 0.1, 0.0]
KRG_TAB = [0.0, 0.01, 0.05, 0.2, 0.5, 0.8]

proto_pvt = BlackOilPVT(OIL_ROWS, GAS_ROWS)
model = RadialBlackOilModel(
    grid=RadialGrid(R_WELL, R_EXT, H, N, K_PERM * M2_TO_MD),
    rock=CompressibleRock(phi_ref=PHI, p_ref_bar=P0_PA / BAR_TO_PA, cr_per_bar=0.0),
    pvt=proto_pvt, relperm=TabulatedRelPerm(SG_TAB, KRO_TAB, KRG_TAB),
    p_bhp_bar=P_WF_PA / BAR_TO_PA, p_outer_bar=P0_PA / BAR_TO_PA,
    outer_rs_sm3_sm3=RS0, skin=0.0)
grid = LogRadialGrid(r_well=R_WELL, R_ext=R_EXT, h=H, N=N, k=K_PERM)
pvt = PrototypePVTAdapter(proto_pvt, rho_o_std=850.0, rho_g_std=0.85)
adapter = PrototypeHydroAdapter(model, grid, pvt)

# Аудит DEBT-063: критерий Ньютона ||F||_inf <= 1e-11 + 1e-8·||F0||_inf
# (blackoil.py, _newton_fixed_active_set). Записать ||F0|| и итоговую
# невязку каждого решения — чтобы знать гарантию в долях дебита.
_calls = []
_orig_newton = model._newton_fixed_active_set


def _newton_logged(z0, state_old, dt_s, gas_active, *a, **kw):
    f0 = np.linalg.norm(model.residual(z0, state_old, dt_s, gas_active), np.inf)
    z, rep = _orig_newton(z0, state_old, dt_s, gas_active, *a, **kw)
    _calls.append((f0, rep.converged, rep.residual_inf if hasattr(rep, "residual_inf")
                   else rep[2]))
    return z, rep


model._newton_fixed_active_set = _newton_logged
s0 = SimulationState(p=np.full(N, P0_PA), Sg=np.zeros(N), Rs=np.full(N, RS0),
                     T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
bc = BoundaryConditions(well=PressureControl(P_WF_PA), p_ext=P0_PA,
                        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)
res = adapter.solve(s0, dt=DT, bc=bc)
s1 = res.state

# Как в тесте: накопление через B_o обёртки
acc = grid.volumes * PHI * ((1 - s1.Sg) / pvt.Bo(s1.p, s1.Rs)
                            - (1 - s0.Sg) / pvt.Bo(s0.p, s0.Rs)) / DT
net = res.G_o[1:] - res.G_o[:-1]
r_test = (acc + net) / abs(res.G_o[0])
j = int(np.argmax(np.abs(r_test)))
print(f"S_g max после шага: {s1.Sg.max():.3e}")
print(f"невязка как в тесте: max |r|/|G_o[0]| = {np.abs(r_test).max():.3e} (ячейка {j})")
print("  по ячейкам:", np.array2string(r_test, precision=2, max_line_width=120))
for k, (f0, ok, fin) in enumerate(_calls):
    print(f"Ньютон {k}: ||F0||_inf = {f0:.3e} ({f0 / abs(res.G_o[0]):.2f}·|G_o[0]|), "
          f"сошёлся {ok}, итоговая {fin:.3e}; гарантия критерия в долях дебита "
          f"{(1e-11 + 1e-8 * f0) / abs(res.G_o[0]):.1e}")
print(f"  объёмы двух сеток совпадают: "
      f"{np.max(np.abs(grid.volumes / model.grid.bulk_volumes_m3 - 1.0)):.1e}")
