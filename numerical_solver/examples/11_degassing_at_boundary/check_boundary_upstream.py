"""DEBT-009: измерить вклад контурного upstream на сценарии, где он виден.

Во всех примерах 01–10 контурная ячейка остаётся насыщенной ($p_{N-1}$
почти на 5 МПа выше $p_b$), поэтому $R_{s,N-1} = R_s^0$ и обе ветви
контурной грани дают одно значение — дефект DEBT-009 численно не проявлялся
($\\le 3.3\\cdot10^{-8}$ Дж при дегазационном члене $\\sim10^{9}$ Дж).

Здесь $p_0 = 15.05$ МПа вплотную к $p_b = 15$ МПа: депрессия дотягивается
до центра последней ячейки, там начинается разгазирование, но приток через
контур сохраняется. В этих условиях состав притока ($R_s^0$) и состав
ячейки $N-1$ расходятся, и выбор upstream начинает влиять на результат.

Скрипт считает по истории прогона два варианта конвективного потока
растворённого газа через контурную грань:
  - исправленный (текущая схема): R_conv[N] = G_o[N]·Rs_ext, Rs_ext = Rs^0;
  - дефектный (до DEBT-009):      R_conv[N] = G_o[N]·Rs_old[N-1].
Разность пересчитывается в энергию через -L·mdot и сравнивается с полным
дегазационным членом.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\11_degassing_at_boundary\\check_boundary_upstream.py
"""

import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_EXAMPLES = _HERE.parent
_ROOT = _EXAMPLES.parent
# Прототип radial_blackoil подключается conftest-ом только под pytest,
# автономному скрипту приходится делать это самому
for _p in (str(_ROOT), str(_EXAMPLES)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_PROTO = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
if _PROTO.exists() and str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def check(config_path, label):
    cfg = load_config(Path(config_path))
    sim, init = SimulatorFactory.from_config(cfg)
    history = sim.run(init)

    grid = sim._grid
    pvt = sim._energy._pvt
    N = grid.N
    V = grid.volumes
    rho_g_std = pvt.rho_g_std
    Rs_ext = cfg.initial_conditions.Rs0
    p_b = float(pvt.pb(np.array([Rs_ext]))[0])

    t_arr = np.array(history.times)

    cum_deg = 0.0        # полный дегазационный член, Дж
    cum_delta = 0.0      # вклад дефекта (дефектный - исправленный), Дж
    n_inflow = 0
    min_p_last = np.inf
    max_dRs = 0.0

    for n in range(1, len(t_arr)):
        st, st_prev = history.states[n], history.states[n - 1]
        dt = t_arr[n] - t_arr[n - 1]
        hydro = history.hydro_results[n]

        p, Sg, Rs = st.p, st.Sg, st.Rs
        So = 1.0 - Sg
        G_o = hydro.G_o
        # Теплота дегазации на T предыдущего шага — как в решателе
        L = pvt.L_degas(p, st_prev.T)

        min_p_last = min(min_p_last, float(p[-1]))
        max_dRs = max(max_dRs, abs(float(Rs[-1]) - Rs_ext))

        # Полный Q_deg текущей (исправленной) схемой
        Q_deg = sim._energy.compute_degassing(
            So, Sg, Rs, st_prev.Rs, pvt.Bo(p, Rs), G_o, L, dt, N, Rs_ext)
        cum_deg += float(np.sum(V * Q_deg)) * dt

        # Вклад дефекта: он менял только R_conv[N] и только при втекании
        if G_o[N] < 0:
            n_inflow += 1
            diff = G_o[N] * (st_prev.Rs[-1] - Rs_ext)
            # R_conv[N] входит в mdot_conv последней ячейки как -rho_g_std/V
            d_mdot = -rho_g_std * diff / V[-1]
            cum_delta += float(V[-1] * (-L[-1] * d_mdot)) * dt

    print(f"\n=== {label} ===")
    print(f"  p_b = {p_b:.4e} Па,  min p[N-1] = {min_p_last:.4e} Па"
          f"  -> {'НИЖЕ p_b' if min_p_last < p_b else 'выше p_b'}")
    print(f"  шагов с втеканием (G_o[N] < 0): {n_inflow} из {len(t_arr) - 1}")
    print(f"  max |Rs[N-1] - Rs^0|        = {max_dRs:.4e} м³ст/м³ст")
    print(f"  полный дегазационный член   = {cum_deg:+.4e} Дж")
    print(f"  вклад дефекта DEBT-009      = {cum_delta:+.4e} Дж")
    if abs(cum_deg) > 0:
        print(f"  доля дефекта                = {abs(cum_delta)/abs(cum_deg)*100:.4f} %")
    return cum_deg, cum_delta


if __name__ == "__main__":
    # Сценарий, где дефект виден: разгазирование доходит до контура
    check(_HERE / "config.json",
          "Пример 11 (разгазирование у контура, p0 = 15.05 МПа)")
    # Контроль: штатный пример 10, где контур насыщен и дефект не проявляется
    check(_EXAMPLES / "10_deep_degassing" / "config.json",
          "Пример 10 (контур насыщен, p0 = 20 МПа)")
