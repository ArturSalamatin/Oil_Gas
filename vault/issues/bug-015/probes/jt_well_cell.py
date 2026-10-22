"""BUG-015, замер при открытии issue: что такое T[0] — T(r_w) или T(r_0)?

Кейс B VAL-002 (tests/test_val002.py): чистый JT, однофазная нефть,
стационарные потоки Дюпюи, λ ≈ 0. Эталон T(r) = T_ext + μ_JT·(p(r) − p_ext).
Если схема точна в центрах ячеек (BUG-013, README 02), то
T[0] − T(r_w) = μ_JT·(p[0] − p_wf) — перепад полуячейки у забоя, первый
порядок по Δln r. Печатает это для N = 25…200 и допуск
test_wellbore_temperature (rtol = 0.01 от абсолютной T).

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-015\\probes\\jt_well_cell.py
"""

import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"пакет и тесты из: {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "tests"))

import test_val002 as v  # noqa: E402
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402

MU = v.TestCaseB_PureJT.MU_JT if hasattr(v, "TestCaseB_PureJT") else -3e-7


def run(N):
    """Стационар кейса B на сетке N; те же параметры, что в фикстуре теста."""
    grid = LogRadialGrid(v.R_WELL, v.R_EXT, v.H, N, v.K_PERM)
    pvt = v._make_pvt(mu_JT_oil=MU)
    relperm = CoreyRP(S_or=0.0, S_gc=0.0, n_o=2.0, n_g=2.0)
    rock = v._rock(lambda_solid=0.001, lambda_oil=0.001, lambda_gas=0.001)
    solver = TridiagEnergySolver(grid, pvt, rock)
    hydro = v._stationary_hydro_result(grid, pvt, relperm, v.P_WF, v.P_EXT,
                                       v.T_EXT, v.RS0)
    state = SimulationState(p=hydro.state.p, Sg=hydro.state.Sg,
                            Rs=hydro.state.Rs, T=np.full(N, v.T_EXT),
                            regime=hydro.state.regime, t=0.0)
    T, _ = v._run_energy_steps(solver, hydro, state, 1e7, v.T_EXT, 400,
                               rtol_converge=1e-12)
    p = hydro.state.p
    T_centers = v.T_EXT + MU * (p - v.P_EXT)          # эталон в центрах
    T_w = v.T_EXT + MU * (v.P_WF - v.P_EXT)           # эталон на r_w
    return dict(N=N, r0=grid.r_centers[0],
                err_centers=np.max(np.abs(T - T_centers)),
                d_w=T[0] - T_w, pred=MU * (p[0] - v.P_WF),
                p0_pwf=p[0] - v.P_WF, T_w=T_w)


def main():
    dTw = abs(MU * (v.P_WF - v.P_EXT))
    print(f"μ_JT = {MU:g} К/Па, |ΔT_w| = {dTw:.4f} К")
    print("   N    r_0, м   max|T−T(r_j)|, К   T[0]−T(r_w), К"
          "   μ(p[0]−p_wf), К   p[0]−p_wf, кПа   отношение")
    prev = None
    for N in (25, 50, 100, 200):
        r = run(N)
        ratio = "" if prev is None else f"{prev / r['d_w']:.3f}"
        print(f" {N:4d}   {r['r0']:.5f}   {r['err_centers']:.3e}"
              f"          {r['d_w']:+.6f}       {r['pred']:+.6f}"
              f"        {r['p0_pwf'] / 1e3:8.2f}      {ratio}")
        prev = r["d_w"]
    tol = 0.01 * r["T_w"]
    print(f"\ntest_wellbore_temperature: допуск rtol=0.01 → {tol:.2f} К"
          f" при |ΔT_w| = {dTw:.2f} К; T[0] = T_ext прошёл бы: "
          f"{abs(v.T_EXT - r['T_w']) <= tol}")


if __name__ == "__main__":
    main()
