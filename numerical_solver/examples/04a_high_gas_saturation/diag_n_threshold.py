"""Граница отказа по N: сколько ячеек разгазируется на первом шаге.

BUG-003 закрыт с проверкой до N = 120; при N = 500 первый же шаг
истории падает. Здесь измеряем, где проходит граница и как с ростом N
растёт число ячеек, которые цикл active set пытается перевести в
двухфазный режим за одну итерацию.

Считается ТОЛЬКО первый шаг (dt = 300 с) — именно на нём происходит
отказ, полный прогон не нужен.
"""

import json
import sys
import tempfile
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
N_LIST = [50, 100, 150, 200, 300, 400, 500]


def probe(n_cells: int) -> tuple:
    """Первый шаг при заданном N: сошёлся ли, сколько ячеек активируется."""
    raw = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    raw["grid"]["N"] = n_cells

    # load_config читает PVT-файлы относительно конфига, поэтому временный
    # конфиг кладём в ту же папку примера, а не в системный temp.
    tmp = HERE / f".probe_N{n_cells}.json"
    tmp.write_text(json.dumps(raw), encoding="utf-8")
    try:
        config = load_config(tmp)
        simulator, state = SimulatorFactory.from_config(config)
        model = simulator._hydro._model
        model.set_bhp_control(config.time.history[0].p_wf / BAR)

        old = BlackOilState(
            pressure_bar=state.p / BAR,
            rs_sm3_sm3=state.Rs.copy(),
            sg=state.Sg.copy(),
            gas_active=(state.regime == 1),
        )
        mask = old.gas_active.copy()

        # Первая итерация active set: сколько ячеек просится в двухфазный режим.
        z, rep1 = model._newton_fixed_active_set(
            model.pack(old, mask), old, DT, mask)
        n_activate = -1
        if rep1.converged:
            trial = model.unpack(z, mask)
            rs_sat = model.pvt.rs_sat(trial.pressure_bar)
            n_activate = int(np.count_nonzero(
                (~mask) & (trial.rs_sm3_sm3 > rs_sat + model.rs_switch_tol)))

        # Полный шаг через штатный advance (все итерации active set).
        _, rep = model.advance(old, DT)
        dr_well = simulator._grid.r_faces[1] - simulator._grid.r_faces[0]
        return rep.converged, n_activate, rep.residual_inf, dr_well
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    print(f"Первый шаг истории, dt = {DT} с, p_wf = 4 МПа, p0 = 20 МПа\n")
    print(f"{'N':>5} {'dr у забоя, м':>15} {'ячеек в газ':>12} "
          f"{'advance':>10} {'невязка':>12}")
    for n in N_LIST:
        ok, n_act, res, dr = probe(n)
        frac = f"{n_act} ({100 * n_act / n:.0f} %)" if n_act >= 0 else "—"
        print(f"{n:5d} {dr:15.3e} {frac:>12} "
              f"{('OK' if ok else 'ОТКАЗ'):>10} {res:12.3e}")


if __name__ == "__main__":
    main()
