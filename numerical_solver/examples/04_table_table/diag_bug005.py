"""BUG-005: почему cum_deg != 0 при Sg = 0 и Rs = const.

Наблюдение (BUG-004): cum_deg = +2.05e7 Дж в примере 04, где Sg ≡ 0 и
Rs ≡ 30 — дегазации нет вовсе, а член скрытой теплоты ненулевой.

Проверяем три версии причины:
  (1) временная часть mdot_time ∝ (Rs - Rs_old) — должна быть строго 0;
  (2) телескопический остаток конвективной части: при Rs ≡ R сумма по
      объёму даёт -rho_g_std*R*(G_o[N] - G_o[0]) — это НЕ ноль, а чистый
      поток стандартного газа, втекающий с нефтью и уносимый через забой;
  (3) неверный upstream на контурной грани: при втекании схема брала
      состав ячейки N-1 (Rs_old[-1]) вместо состава притока Rs_ext = Rs^0
      (DEBT-009, исправлено).

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04_table_table\\diag_bug005.py
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


def check(config_path, label):
    cfg = load_config(Path(config_path))
    sim, init = SimulatorFactory.from_config(cfg)
    history = sim.run(init)

    grid = sim._grid
    V = grid.volumes
    pvt = sim._energy._pvt
    rock = sim._energy._rock
    phi = rock.porosity
    rho_g_std = pvt.rho_g_std
    # Состав притока с контура (eq. bc_Sg_ext): Rs|_ext = Rs^0
    Rs_ext = cfg.initial_conditions.Rs0
    N = len(V)

    t_arr = np.array(history.times)

    cum_time = 0.0        # вклад временной части
    cum_conv = 0.0        # вклад конвективной части
    cum_tele = 0.0        # предсказание телескопирования при Rs = const
    cum_line258 = 0.0     # вклад дефекта DEBT-009 (Rs_old[-1] vs Rs_ext)
    max_dRs = 0.0
    max_Sg = 0.0
    n_inflow = 0          # шагов с втеканием через контур

    for n in range(1, len(t_arr)):
        st, st_prev = history.states[n], history.states[n - 1]
        dt = t_arr[n] - t_arr[n - 1]
        hydro = history.hydro_results[n]

        p, Sg, Rs = st.p, st.Sg, st.Rs
        So = 1.0 - Sg
        G_o = hydro.G_o
        # Теплота дегазации — как в решателе (tridiag.py:98): на T предыдущего шага
        L = pvt.L_degas(p, st_prev.T)

        max_dRs = max(max_dRs, float(np.max(np.abs(Rs - st_prev.Rs))))
        max_Sg = max(max_Sg, float(np.max(np.abs(Sg))))

        # ── (1) временная часть ──
        mdot_time = (-rho_g_std * phi * So / pvt.Bo(p, Rs)
                     * (Rs - st_prev.Rs) / dt)
        cum_time += float(np.sum(V * (-L * mdot_time))) * dt

        # ── (2) конвективная часть, точно как в tridiag.py:246-260 ──
        R_conv = np.zeros(N + 1)
        for f in range(1, N):
            Go_p, Go_m = max(G_o[f], 0.0), min(G_o[f], 0.0)
            R_conv[f] = Go_p * Rs[f - 1] + Go_m * Rs[f]
        R_conv[0] = G_o[0] * Rs[0]
        if G_o[N] >= 0:
            R_conv[N] = G_o[N] * Rs[N - 1]
        else:
            # Приток: upstream = контур, состав задан ГУ (DEBT-009)
            R_conv[N] = G_o[N] * Rs_ext
            n_inflow += 1
        mdot_conv = -rho_g_std * (R_conv[1:] - R_conv[:-1]) / V
        cum_conv += float(np.sum(V * (-L * mdot_conv))) * dt

        # ── (2') предсказание: при Rs ≡ R остаётся только поток через границы ──
        # Σ_j V_j mdot_conv,j = -rho_g_std (R_conv[N] - R_conv[0])
        tele = -rho_g_std * (R_conv[N] - R_conv[0])
        # L поячеечное, для оценки берём среднее — члены на границах
        cum_tele += float(-np.mean(L) * tele) * dt

        # ── (3) вклад дефекта DEBT-009: контур брал состав ячейки N-1
        # (Rs_old[-1]) вместо состава притока Rs_ext ──
        if G_o[N] < 0:
            diff = G_o[N] * (st_prev.Rs[-1] - Rs_ext)
            # входит в mdot_conv последней ячейки со знаком -rho_g_std/V
            d_mdot = -rho_g_std * diff / V[-1]
            cum_line258 += float(V[-1] * (-L[-1] * d_mdot)) * dt

    print(f"\n=== {label} ===")
    print(f"  max|Sg|                     = {max_Sg:.3e}")
    print(f"  max|Rs - Rs_old| за шаг     = {max_dRs:.3e}")
    print(f"  cum_deg: временная часть    = {cum_time:+.4e} Дж")
    print(f"  cum_deg: конвективная часть = {cum_conv:+.4e} Дж")
    print(f"  сумма                       = {cum_time + cum_conv:+.4e} Дж")
    print(f"  предсказание телескопа      = {cum_tele:+.4e} Дж")
    print(f"  вклад дефекта DEBT-009      = {cum_line258:+.4e} Дж")
    print(f"  шагов с втеканием (G_o[N]<0): {n_inflow} из {len(t_arr) - 1}")


if __name__ == "__main__":
    check(_HERE / "config.json", "Пример 04 (табличный PVT, Sg=0, Rs=30)")
