"""Отказ при N=500: цикл active set, а не Ньютон.

diag_n500_scale.py показал: _newton_fixed_active_set при фиксированной
маске сходится на всех dt. При этом advance() возвращает converged=False.
Разница между ними — внешний цикл active set (blackoil.py:202-214),
который переключает ячейки между режимами (газ активен / растворён) и
повторяет Ньютон.

Классический отказ такого цикла — зацикливание: одна и та же ячейка
включается и выключается от итерации к итерации, ns никогда не
обнуляется, цикл выходит по max_active_iter=12 с converged=False.

Воспроизводим цикл вручную и печатаем на каждой итерации: сколько
ячеек переключилось, какие именно, сошёлся ли внутренний Ньютон.
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
DT = 300.0


def main() -> None:
    config = load_config(HERE / "config.json")
    simulator, state = SimulatorFactory.from_config(config)
    grid = simulator._grid
    model = simulator._hydro._model
    model.set_bhp_control(config.time.history[0].p_wf / BAR)

    state_old = BlackOilState(
        pressure_bar=state.p / BAR,
        rs_sm3_sm3=state.Rs.copy(),
        sg=state.Sg.copy(),
        gas_active=(state.regime == 1),
    )

    print(f"N = {grid.N}, dt = {DT} с")
    print(f"стартовая маска: активных ячеек {int(np.count_nonzero(state_old.gas_active))}\n")

    mask = state_old.gas_active.copy()
    guess = state_old.copy()
    history_masks = []

    for aset in range(1, 13):
        z, rep = model._newton_fixed_active_set(
            model.pack(guess, mask), state_old, DT, mask)

        if not rep.converged:
            print(f"aset {aset:2d}: Ньютон НЕ сошёлся, res={rep.residual_inf:.3e}")
            break

        trial = model.unpack(z, mask)
        rs_sat = model.pvt.rs_sat(trial.pressure_bar)
        activate = (~mask) & (trial.rs_sm3_sm3 > rs_sat + model.rs_switch_tol)
        deactivate = mask & (trial.sg < -model.sg_switch_tol)
        n_act = int(np.count_nonzero(activate))
        n_deact = int(np.count_nonzero(deactivate))

        idx_a = np.where(activate)[0]
        idx_d = np.where(deactivate)[0]
        print(f"aset {aset:2d}: Ньютон ok ({rep.iterations} ит, res={rep.residual_inf:.2e}); "
              f"включить {n_act} {idx_a[:6]}, выключить {n_deact} {idx_d[:6]}")

        if n_act + n_deact == 0:
            print("\nСошлось: переключений нет.")
            return

        # Признак зацикливания: маска уже встречалась.
        key = mask.tobytes()
        if key in history_masks:
            print(f"\n!! Маска повторилась (была на итерации {history_masks.index(key) + 1}) "
                  f"— цикл active set зациклился.")
        history_masks.append(key)

        newmask = mask.copy()
        newmask[activate] = True
        newmask[deactivate] = False
        guess = trial.copy()
        guess.gas_active = newmask.copy()
        if np.any(activate):
            guess.sg[activate] = 0.0
            guess.rs_sm3_sm3[activate] = rs_sat[activate]
        mask = newmask

    print("\nВышли по лимиту max_active_iter — converged=False.")

    # Куда смотреть: где именно происходят переключения по радиусу.
    if idx_a.size:
        print(f"радиусы включаемых ячеек: {grid.r_centers[idx_a[:6]]}")
    if idx_d.size:
        print(f"радиусы выключаемых:      {grid.r_centers[idx_d[:6]]}")


if __name__ == "__main__":
    main()
