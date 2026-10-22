"""DEBT-043, план: ловит ли страж (порог 1e-14, укороченные 03 и 04) ошибку реализации.

Ошибка: СЛАУ решается в θ, но накопителю передаётся записанная T^{n+1} = θ + T_ref
и абсолютные T_old, T_ext (то есть ΔE по записанным полям). Ожидание плана:
невязка возвращается к ~1e-13, страж падает.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\plan2_guard_check.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan2_theta_emulation as em  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from energy_balance import compute_balance  # noqa: E402


def run_recorded(cfg):
    """θ-сборка и решение, но накопитель — по записанной T (ошибка)."""
    sim, init = SimulatorFactory.from_config(cfg)
    en = sim._energy
    held = {}
    asm0, solve0 = en.assemble_tridiag, en.solve_banded_system

    def asm(N, dt, T_old, T_ext, *rest):
        held["T_ref"] = T_ext
        return asm0(N, dt, T_old - T_ext, T_ext - T_ext, *rest)

    def solve(a, b, c, d, N):
        return solve0(a, b, c, d, N) + held["T_ref"]

    en.assemble_tridiag = asm
    en.solve_banded_system = solve
    h = sim.run(init)
    return compute_balance(h, sim._grid, cfg)


import os  # noqa: E402
os.environ["DEBT043_SHORT"] = "1"
for name in ("03_standing_corey", "04_table_table"):
    bal = run_recorded(em.config(name))
    rel = float(bal["rel_residual"][-1])
    print(f"{name}: накопитель по записанной T — отн. невязка {rel:.2e}; "
          f"страж 1e-14 {'ПАДАЕТ' if not rel < 1e-14 else 'проходит (не ловит!)'}")
