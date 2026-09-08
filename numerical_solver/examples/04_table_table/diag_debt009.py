"""DEBT-009: измерить эффект асимметрии Rs_old[-1]/Rs[-1] на контурной грани.

В compute_degassing (tridiag.py:255-258) конвективный поток растворённого
газа на контуре при втекании берёт Rs_old[-1], а на всех остальных гранях
используется Rs (после гидро-шага). Скрипт проверяет по всем примерам:
  - как часто вообще происходит втекание через контур (G_o[N] < 0);
  - насколько Rs_old[-1] отличается от Rs[-1];
  - какой вклад в энергию дала бы замена Rs_old[-1] -> Rs[-1].

Если контурная ячейка остаётся насыщенной (p > p_b), Rs там не меняется и
обе ветви тождественны — тогда правка безопасна. Скрипт нужен, чтобы это
подтвердить фактом до и после правки, а не предполагать.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04_table_table\\diag_debt009.py
"""

import sys
from pathlib import Path
import numpy as np

_HERE = Path(__file__).resolve().parent
_EXAMPLES = _HERE.parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES), str(_EXAMPLES / "03_standing_corey")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_PROTO = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
if _PROTO.exists() and str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def check(cfg_path, label):
    cfg = load_config(cfg_path)
    sim, init = SimulatorFactory.from_config(cfg)
    history = sim.run(init)

    V = sim._grid.volumes
    pvt = sim._energy._pvt
    rho_g_std = pvt.rho_g_std
    t = np.array(history.times)

    max_diff = 0.0     # max |Rs_old[-1] - Rs[-1]| по шагам
    n_inflow = 0       # шагов с втеканием через контур
    cum_delta = 0.0    # суммарный вклад правки в энергию, Дж
    min_p_ext = np.inf  # минимальное давление в контурной ячейке

    for n in range(1, len(t)):
        st, st_prev = history.states[n], history.states[n - 1]
        dt = t[n] - t[n - 1]
        G_o = history.hydro_results[n].G_o
        min_p_ext = min(min_p_ext, float(st.p[-1]))

        # Ветвь Rs_old задействована только при втекании
        if G_o[-1] < 0:
            n_inflow += 1
            max_diff = max(max_diff, abs(float(st_prev.Rs[-1] - st.Rs[-1])))

            # Правка меняет R_conv[N] на G_o[N]*(Rs[-1] - Rs_old[-1]);
            # в mdot_conv последней ячейки это входит как -rho_g_std*Δ/V.
            L = pvt.L_degas(st.p, st_prev.T)
            diff = G_o[-1] * (st.Rs[-1] - st_prev.Rs[-1])
            d_mdot = -rho_g_std * diff / V[-1]
            cum_delta += float(V[-1] * (-L[-1] * d_mdot)) * dt

    print("%-28s втекание %3d/%3d  max|dRs|=%.3e  p_ext,min=%.3e Па  "
          "вклад правки=%+.3e Дж"
          % (label, n_inflow, len(t) - 1, max_diff, min_p_ext, cum_delta))


if __name__ == "__main__":
    for sub in sorted(p for p in _EXAMPLES.iterdir() if p.is_dir()):
        cfg = sub / "config.json"
        if cfg.exists():
            try:
                check(cfg, sub.name)
            except Exception as exc:  # пример может быть сломан — не ронять весь прогон
                print("%-28s ОШИБКА: %s: %s" % (sub.name, type(exc).__name__, exc))
