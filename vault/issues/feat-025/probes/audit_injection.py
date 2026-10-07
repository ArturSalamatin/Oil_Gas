"""FEAT-025, аудит: ловит ли сверка d с вариантом Б (atol = RTOL·max|d|) малый дефект сборки.

Дефект: в TridiagEnergySolver.assemble_tridiag член дегазации Q_deg умножается
на (1 + delta) — эталон test_energy_matrix_examples.build_reference его не
видит. Для delta = 1e-8 и 1e-10 и для «шума» (delta = 0) на примере 19
(probes/final, 3 суток) печатается: падает ли сверка d при atol = 0 и при
варианте Б.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\audit_injection.py
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

ORIG = TridiagEnergySolver.assemble_tridiag


def run(name, delta, days=3):
    def patched(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext,
                Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
        return ORIG(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext,
                    Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg * (1.0 + delta))

    TridiagEnergySolver.assemble_tridiag = patched
    try:
        cfg = load_config(HERE / "final" / name / "config.json")
        cfg.output.log_level = "ERROR"
        cfg.time.history = cfg.time.history[:days]
        sim, init = SimulatorFactory.from_config(cfg)
        strict = scaled = 0
        worst_scaled = [0.0]

        def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
            nonlocal strict, scaled
            rd = tm.build_reference(sim._grid, sim._pvt, cfg.rock, hydro_result,
                                    state_prev, dt, bc)[3]
            if not np.allclose(d, rd, rtol=tm.RTOL, atol=0.0):
                strict += 1
            atol = tm.RTOL * float(np.max(np.abs(rd)))
            if not np.allclose(d, rd, rtol=tm.RTOL, atol=atol):
                scaled += 1
            worst_scaled[0] = max(worst_scaled[0],
                                  float(np.max(np.abs(d - rd)) / np.max(np.abs(rd))))

        sim._energy.matrix_probe = probe
        sim.run(init)
        print(f"   {name}, delta = {delta:g}: вызовов с отказом — atol=0: {strict}, "
              f"вариант Б: {scaled} (из {days}); max|d-ref|/max|ref| = {worst_scaled[0]:.2e}")
    finally:
        TridiagEnergySolver.assemble_tridiag = ORIG


if __name__ == "__main__":
    for nm in ("19_rs150_cooling", "20_rs500_cooling"):
        for delta in (0.0, 1e-10, 1e-8):
            run(nm, delta)
