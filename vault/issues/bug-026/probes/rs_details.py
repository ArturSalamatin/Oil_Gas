"""BUG-026 (планирование): числа R_s из докстрингов тестов 16, 17 при заданном h0.

16 — test_gas_redissolves_and_rs_freezes: max(R_s - R_s^eq(p)) на финале,
     max|R_s(запись 43, 20 сут) - R_s(финал)|.
17 — test_wellbore_rs_never_decreases: R_s ячеек 0 и 1 на финале, наименьшее
     изменение R_s(r_w) между записями 16..53.

Запуск из numerical_solver/ (P — путь к скрипту): .venv\\Scripts\\python P <h0> [<h0> ...]
"""

import sys
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory, create_pvt  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

E = 15


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    for a in sys.argv[1:]:
        h0 = float(a)
        for name in ("16_well_shut_in", "17_shut_in_strong_cooling"):
            cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
            cfg.output.log_level = "ERROR"
            cfg.time.dt_after_control_change = h0
            sim, s0 = SimulatorFactory.from_config(cfg)
            st = sim.run(s0).states
            f = st[-1]
            rs_eq = create_pvt(cfg).Rs_eq(f.p)
            rs_w = np.array([s.Rs[0] for s in st])
            print(f"{name} h0={h0:g}: финал R_s[0] {f.Rs[0]:.4f}, R_s[1] {f.Rs[1]:.4f}; "
                  f"max(R_s - R_s^eq) {np.max(f.Rs - rs_eq):.2e}; "
                  f"max|R_s(43) - R_s(финал)| {np.max(np.abs(st[43].Rs - f.Rs)):.2e}; "
                  f"min ΔR_s(r_w) записи {E + 1}..{len(st) - 1}: {np.min(np.diff(rs_w[E + 1:])):+.2e}",
                  flush=True)


if __name__ == "__main__":
    main()
