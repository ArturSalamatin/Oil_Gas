"""BUG-015, аудит 1: снимает ли добавка полуячейки В СХЕМУ ошибку T[0] на примере 12?

План (замер 3) судил о варианте 3 по оценке поправки вывода ΔT_½ + ΔT_deg.
Здесь полуячейка [r_w, r_0] добавляется в уравнение ячейки 0 подменой методов
TridiagEnergySolver (код пакета не меняется):
  «+JT»      — J[0] += Σ_α μ_α[0]·Φ⁻_α,½·(p[0] − p_wf)   (форма правой грани eq:QJT_disc);
  «+JT+deg»  — то же и V_0·Q_deg[0] += L[0]·ρ_g,ст·G^o_½·(R_s[0] − R_s,w),
               R_s,w = min(R_s^eq(p_wf), R_s[0])            (форма правой грани eq:mdot_disc).
Сравнение T[0] с пределом T∞ = 2·T_200 − T_100 схемы как есть
(twf_grid_ex12.txt: сутки 1 — 349.65230, 5 — 349.91064, 15 — 350.32908 К).

Запуск из numerical_solver/ (~1 мин):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-015\\probes\\ex12_halfcell_scheme.py
"""

import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"Код: {SOLVER}")
sys.path.insert(0, str(SOLVER))

from gpn_multiphase_solver.cli import configure_batch_run  # noqa: E402
configure_batch_run()

from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CONFIG = SOLVER / "examples" / "12_large_drainage_radius" / "config.json"
T_INF = {1: 349.65230, 5: 349.91064, 15: 350.32908}
_jt, _deg = TridiagEnergySolver.compute_jt, TridiagEnergySolver.compute_degassing
_last = {}


def jt_plus(self, Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext, p_wf):
    J = _jt(self, Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext, p_wf).copy()
    J[0] += (mu_o[0] * min(Phi_o[0], 0.0)
             + mu_g[0] * min(Phi_g[0], 0.0)) * (p[0] - p_wf)
    _last["p_wf"] = p_wf          # compute_degassing вызывается после compute_jt
    return J


def deg_plus(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext, p=None):
    Q = _deg(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext, p=p).copy()
    pvt = self._pvt
    Rs_w = min(pvt.Rs_eq(np.array([_last["p_wf"]]))[0], Rs[0])
    G_minus = min(G_o[0], 0.0)
    Q[0] += L[0] * pvt.rho_g_std * G_minus * (Rs[0] - Rs_w) / self._grid.volumes[0]
    return Q


def run(N, variant):
    TridiagEnergySolver.compute_jt = jt_plus if variant != "как есть" else _jt
    TridiagEnergySolver.compute_degassing = deg_plus if variant == "+JT+deg" else _deg
    try:
        config = load_config(CONFIG)
        config.grid.N = N
        sim, init = SimulatorFactory.from_config(config)
        hist = sim.run(init)
    finally:
        TridiagEnergySolver.compute_jt, TridiagEnergySolver.compute_degassing = _jt, _deg
    times = np.array(hist.times)
    return {d: hist.states[int(np.argmin(np.abs(times - d * 86400.0)))].T[0]
            for d in T_INF}


def main():
    print("   N   вариант      " + "   ".join(f"T∞−T[0], сут {d}" for d in T_INF))
    for N in (50, 100):
        for variant in ("как есть", "+JT", "+JT+deg"):
            T0 = run(N, variant)
            print(f" {N:4d}   {variant:10s}  " + "   ".join(
                f"{T_INF[d] - T0[d]:+14.5f}" for d in T_INF))


if __name__ == "__main__":
    main()
