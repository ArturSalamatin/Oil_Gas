"""BUG-015, замер при планировании: что даёт перепад полуячейки у забоя в J[0].

Утверждение записи реестра: «добавлять забойный перепад в ячейку 0 нельзя —
двойной учёт (~1.5 ячейки)». Проверка на кейсе B VAL-002 (чистый JT,
стационар): к J_jt[0] добавляется μ_JT[0]·Φ⁻_{1/2}·(p[0] − p_wf) — ровно
формула, которую постановка (абзац о забое в ssec:bc_disc) приписывает схеме.
Печатает T[0] − T(r_w), отклонение остальных ячеек от T(r_j) и сумму
JT-вкладов против точного интеграла μ·Φ·(p_ext − p_wf).

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-015\\probes\\jt_well_halfcell_added.py
"""

import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"Код: {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "tests"))

import test_val002 as v  # noqa: E402
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402

MU = v.TestCaseB_PureJT.MU_JT
_orig = TridiagEnergySolver.compute_jt
CAPTURE = {}


def with_well_halfcell(self, Q_o, Q_g, Phi_o, Phi_g, mu_JT_o, mu_JT_g, p, N,
                       ext, p_wf):
    """compute_jt + μ·Φ⁻_{1/2}·(p[0] − p_wf) в ячейку 0."""
    J = _orig(self, Q_o, Q_g, Phi_o, Phi_g, mu_JT_o, mu_JT_g, p, N, ext, p_wf)
    J = J.copy()
    J[0] += (mu_JT_o[0] * min(Phi_o[0], 0.0)
             + mu_JT_g[0] * min(Phi_g[0], 0.0)) * (p[0] - p_wf)
    CAPTURE["J"] = J
    CAPTURE["Phi"] = Phi_o[0] + Phi_g[0]
    return J


def run(N, patched):
    TridiagEnergySolver.compute_jt = with_well_halfcell if patched else _orig
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
    TridiagEnergySolver.compute_jt = _orig
    p = hydro.state.p
    T_c = v.T_EXT + MU * (p - v.P_EXT)
    T_w = v.T_EXT + MU * (v.P_WF - v.P_EXT)
    return T, T_c, T_w, p


def main():
    print("   N   вариант          T[0]−T(r_w), К   max_{j≥1}|T_j−T(r_j)|, К"
          "   T[0]−T(r_0), К")
    for N in (25, 50, 100):
        for patched in (False, True):
            T, T_c, T_w, p = run(N, patched)
            name = "+ полуячейка" if patched else "схема как есть"
            print(f" {N:4d}   {name:15s}  {T[0] - T_w:+.6f}"
                  f"          {np.max(np.abs(T[1:] - T_c[1:])):.3e}"
                  f"               {T[0] - T_c[0]:+.6f}")
    print("\nСумма JT-вкладов (вариант «+ полуячейка», N = 100) против "
          "точного μ·Φ·(p_ext − p_wf):")
    run(100, True)
    J, Phi = CAPTURE["J"], CAPTURE["Phi"]
    exact = MU * Phi * (v.P_EXT - v.P_WF)
    print(f"  ΣJ = {J.sum():.6e} Вт, точно = {exact:.6e} Вт,"
          f" отношение {J.sum() / exact:.12f}")


if __name__ == "__main__":
    main()
