"""Диагностика отказа сходимости при N = 500 на первом шаге истории.

Вопрос: расходимость — это нехватка подшагов (тогда при уменьшении dt
невязка падает) или структурный дефект, не лечащийся дроблением
(невязка стоит на месте при любом dt)?

Печатаем отчёт Ньютона (iterations, residual_inf, converged) для ряда
dt от 300 с вниз до долей секунды, начиная с начального состояния.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))          # numerical_solver/examples
sys.path.insert(0, str(HERE.parents[1] / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

BAR = 1e5


def main() -> None:
    config = load_config(HERE / "config.json")
    simulator, state = SimulatorFactory.from_config(config)
    grid = simulator._grid
    adapter = simulator._hydro
    model = adapter._model

    print(f"N = {grid.N}, r_w = {grid.r_centers[0]:.4e} м, "
          f"первая грань dr = {grid.r_faces[1] - grid.r_faces[0]:.4e} м")
    print(f"p0 = {state.p[0] / 1e6:.2f} МПа, Sg0 = {state.Sg[0]:.4f}, "
          f"Rs0 = {state.Rs[0]:.2f}")

    # Граничное условие первого интервала истории.
    bc = simulator._schedule.intervals[0].bc if hasattr(simulator, "_schedule") else None
    p_wf = config.time.history[0].p_wf
    model.set_bhp_control(p_wf / BAR)
    print(f"p_wf = {p_wf / 1e6:.2f} МПа\n")

    proto = BlackOilState(
        pressure_bar=state.p / BAR,
        rs_sm3_sm3=state.Rs.copy(),
        sg=state.Sg.copy(),
        gas_active=(state.regime == 1),
    )

    print(f"{'dt, с':>12} {'iters':>6} {'residual_inf':>14} {'converged':>10}")
    for dt in [300.0, 100.0, 30.0, 10.0, 3.0, 1.0, 0.3, 0.1, 0.01]:
        new_proto, report = model.advance(proto, dt)
        print(f"{dt:12.3g} {report.iterations:6d} "
              f"{report.residual_inf:14.4e} {str(report.converged):>10}")


if __name__ == "__main__":
    main()
