"""FEAT-025, аудит: вариант Д — допуск сверки d от суммы модулей слагаемых ячейки.

d_scale_j = |cap_j·T_j^n| + |J_j| + V_j·(|Q_ad,j| + |Q_deg,j|)
            (+ |Q_T_ext·T_ext| + |Φ⁻_N·T_ext| в ячейке N-1),
проверка: |d - d_ref| <= RTOL·(|d_ref| + d_scale) поэлементно.

d_scale считается обёрткой над test_energy_matrix_examples._ref_assemble (тот
же набор аргументов, что у эталона). Печатается:
  1) без дефекта — max |d-d_ref| / (RTOL·(|d_ref|+d_scale)) по всем вызовам
     (меньше 1 — проходит) для заданных конфигов;
  2) с дефектом Q_deg·(1+delta) в решателе — сколько вызовов ловится.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\audit_dscale.py noise [all|new]
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\audit_dscale.py inject
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "tests", SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402
import test_energy_matrix_examples as tm  # noqa: E402

ORIG_REF = tm._ref_assemble
ORIG_SOLVER = TridiagEnergySolver.assemble_tridiag
LAST = {}


def ref_with_scale(grid, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext,
                   Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
    """Эталон + масштаб слагаемых d (запоминается в LAST['scale'])."""
    out = ORIG_REF(grid, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext,
                   Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)
    V = grid.volumes
    cap = V * rho_cp_eff / dt
    scale = np.abs(cap * T_old) + np.abs(J_jt) + V * (np.abs(Q_ad) + np.abs(Q_deg))
    scale[N - 1] += abs(Q_T_ext * T_ext) + abs(Phi_minus[N] * T_ext)
    LAST["scale"] = scale
    return out


tm._ref_assemble = ref_with_scale


def check(cfg_path, delta=0.0, days=None):
    def patched(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext,
                Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
        return ORIG_SOLVER(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal,
                           Q_T_ext, Phi_plus, Phi_minus, J_jt, Q_ad,
                           Q_deg * (1.0 + delta))

    TridiagEnergySolver.assemble_tridiag = patched if delta else ORIG_SOLVER
    try:
        cfg = load_config(cfg_path)
        cfg.output.log_level = "ERROR"
        if days:
            cfg.time.history = cfg.time.history[:days]
        sim, init = SimulatorFactory.from_config(cfg)
        worst, caught, n = [0.0], [0], [0]

        def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
            rd = tm.build_reference(sim._grid, sim._pvt, cfg.rock, hydro_result,
                                    state_prev, dt, bc)[3]
            lim = tm.RTOL * (np.abs(rd) + LAST["scale"])
            ratio = float(np.max(np.abs(d - rd) / lim))
            worst[0] = max(worst[0], ratio)
            caught[0] += ratio > 1.0
            n[0] += 1

        sim._energy.matrix_probe = probe
        sim.run(init)
        return worst[0], caught[0], n[0]
    finally:
        TridiagEnergySolver.assemble_tridiag = ORIG_SOLVER


NEW = ["19_rs150_cooling", "20_rs500_cooling", "21_rs100_cooling"]

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "noise"
    if mode == "noise":
        which = sys.argv[2] if len(sys.argv) > 2 else "all"
        paths = []
        if which in ("all", "old"):
            paths += [SOLVER / "examples" / n / "config.json" for n in tm.ALL_EXAMPLES]
        if which in ("all", "new"):
            paths += [HERE / "final" / n / "config.json" for n in NEW]
        for pth in paths:
            w, c, n = check(pth)
            print(f"   {pth.parent.name:28s}: вызовов {n:5d}, max err/lim = {w:.2e}, "
                  f"{'ПАДАЕТ' if c else 'проходит'}")
    else:
        for nm in NEW[:2]:
            for delta in (1e-10, 1e-8):
                w, c, n = check(HERE / "final" / nm / "config.json", delta, days=3)
                print(f"   {nm}, дефект Q_deg·(1+{delta:g}): пойман на {c} из {n} вызовов, "
                      f"max err/lim = {w:.2e}")
