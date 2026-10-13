"""Печать однофазной проверки температуры для run_example.

Асимптотика T = T_ext + mu_JT,o·(p − p_0) и почему двухфазной нет —
gpn_multiphase_solver.diagnostics.temperature (DEBT-011).

Запуск:
    .venv\\Scripts\\python examples\\temperature_asymptotics.py 02
"""

import sys
from pathlib import Path

import numpy as np

from gpn_multiphase_solver.diagnostics.temperature import single_phase_asymptote

# Порог, ниже которого ячейка считается однофазной
SG_EPS = 1e-12


def report_asymptotics(config, history, grid, simulator) -> dict:
    """Печать однофазной проверки. Возвращает сводку.

    Двухфазной части нет — см. шапку diagnostics/temperature.py. Вызывается
    example_runner.run_example для всех примеров.
    """
    Sg = history.states[-1].Sg
    T = history.states[-1].T
    mask1 = Sg <= SG_EPS

    print("── Асимптотика температуры (однофазная зона) ──")

    if not mask1.any():
        print("  не проверяется: однофазных ячеек нет "
              "(газ во всей области)")
        return dict(applicable=False, err_1ph=np.nan, n_cells=0,
                    T_asymptote=None)

    T_as = single_phase_asymptote(config, history)
    err_1ph = float(np.max(np.abs(T[mask1] - T_as[mask1])))

    print(f"  T = T_ext + mu_JT·(p − p_ext) на {int(mask1.sum())} ячейках "
          f"из {len(Sg)}: max|ΔT| = {err_1ph:.4f} К")
    print("    (расхождение — незавершённая релаксация T к асимптотике)")

    if not mask1.all():
        print("  двухфазная зона: аналитической проверки нет.")
        print("    Схема верифицируется сверкой матрицы с постановкой")
        print("    (test_energy_matrix_examples.py) и балансом энергии.")

    return dict(applicable=True, err_1ph=err_1ph,
                n_cells=int(mask1.sum()), T_asymptote=T_as)


if __name__ == "__main__":
    _HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(_HERE))
    sys.path.insert(0, str(_HERE.parent))
    # radial_blackoil (прототип гидродинамики) — установленный дистрибутив (DEBT-059)

    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config

    if len(sys.argv) < 2:
        raise SystemExit(
            "укажите пример: python examples\\temperature_asymptotics.py 02")

    name = sys.argv[1]
    root = Path(__file__).parent
    folder = next(d for d in root.iterdir()
                  if d.is_dir() and d.name.startswith(name))

    cfg = load_config(folder / "config.json")
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    report_asymptotics(cfg, hist, sim.grid, sim)
