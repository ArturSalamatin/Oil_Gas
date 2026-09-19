"""Почему при N=500 Ньютон не сходится, а дробление dt делает хуже.

Гипотеза: критерий в blackoil.py:190 относительный —
    nrm <= atol + rtol * scale,   scale = ||f(z0)||_inf,
где z0 — начальное приближение (состояние с прошлого шага). При малом
dt состояние почти не меняется, ||f(z0)|| мало, порог сжимается вместе
с ним, и Ньютон упирается в точность линейного решателя, а не в физику.

Печатаем для каждого dt: scale, порог, достигнутую невязку и их
отношение. Если nrm/порог растёт при уменьшении dt — гипотеза верна.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

BAR = 1e5
RTOL = 1e-8
ATOL = 1e-11


def main() -> None:
    config = load_config(HERE / "config.json")
    simulator, state = SimulatorFactory.from_config(config)
    model = simulator._hydro._model
    model.set_bhp_control(config.time.history[0].p_wf / BAR)

    proto = BlackOilState(
        pressure_bar=state.p / BAR,
        rs_sm3_sm3=state.Rs.copy(),
        sg=state.Sg.copy(),
        gas_active=(state.regime == 1),
    )
    mask = proto.gas_active.copy()
    z0 = model.pack(proto, mask)

    print(f"N = {simulator._grid.N}")
    print(f"{'dt, с':>10} {'scale=||f(z0)||':>16} {'порог':>12} "
          f"{'достигнуто':>12} {'nrm/порог':>11}")

    for dt in [300.0, 100.0, 30.0, 10.0, 3.0, 1.0, 0.3, 0.1, 0.03, 0.01]:
        f0 = model.residual(z0, proto, dt, mask)
        scale = max(np.linalg.norm(f0, np.inf), 1e-9)
        thresh = ATOL + RTOL * scale

        _, rep = model._newton_fixed_active_set(z0, proto, dt, mask)
        print(f"{dt:10.3g} {scale:16.4e} {thresh:12.4e} "
              f"{rep.residual_inf:12.4e} {rep.residual_inf / thresh:11.2e}")


if __name__ == "__main__":
    main()
