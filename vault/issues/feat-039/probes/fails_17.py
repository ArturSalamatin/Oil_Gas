"""FEAT-039 (планирование): где у примеров 16, 17, 22 отказывает гидродинамика до и после нарастания на пуске.

Печатает отказы (t, сут; dt, с) при конфиге как есть и при эмуляции FEAT-039 (интервал 0 –
смена управления с h0 из конфига). Нужна для комментариев тестов о дроблении 17.

Запуск из numerical_solver/ (P – путь к скрипту):
    .venv\\Scripts\\python P <имя> ...
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from start_series import config_path, patch_first  # noqa: E402

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

DAY = 86400.0


def fails(name, feat039):
    cfg = load_config(config_path(name))
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    if feat039:
        patch_first(sim, cfg.time.dt_after_control_change)
    out = []
    solve = sim._hydro.solve

    def counting(state, dt, bc):
        try:
            return solve(state, dt, bc)
        except HydroConvergenceError:
            out.append((round(state.t / DAY, 4), dt))
            raise

    sim._hydro.solve = counting
    sim.run(s0)
    return out


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    for name in sys.argv[1:]:
        for tag, f in (("как есть", False), ("FEAT-039", True)):
            fl = fails(name, f)
            print(f"{name} {tag}: отказов {len(fl)}: {fl}", flush=True)


if __name__ == "__main__":
    main()
