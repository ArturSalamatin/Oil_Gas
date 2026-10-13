"""Печать однофазной проверки температуры для run_case (FEAT-030: из examples/temperature_asymptotics.py).

Асимптотика T = T_ext + mu_JT,o·(p − p_0) и почему двухфазной нет —
gpn_multiphase_solver.diagnostics.temperature (DEBT-011). Входит в штатный
набор run_case (report/pipeline.py) при стационарной аналитике
(output.steady_state).
"""

import numpy as np

from ..diagnostics.temperature import single_phase_asymptote

# Порог, ниже которого ячейка считается однофазной
SG_EPS = 1e-12


def report_asymptotics(config, history, grid, simulator) -> dict:
    """Печать однофазной проверки. Возвращает сводку.

    Двухфазной части нет — см. шапку diagnostics/temperature.py. Вызывается
    run_case (report/pipeline.py) при стационарной аналитике.
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
