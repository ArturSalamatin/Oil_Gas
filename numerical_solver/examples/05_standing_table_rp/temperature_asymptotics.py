"""Стационарная асимптотика температуры — пример 05 (Standing PVT + табличная ОФП).

Выкладки полностью повторяют пример 03: они опираются на структуру
уравнения энергии и не используют вид k_r(S_g) вообще. Отличие примера 05
только в конфиге — здесь λ = 0 (все три теплопроводности обнулены), и
телескопическая формула ниже становится ТОЧНОЙ, а не приближённой.

В примере 02 (однофазном) стационарный предел имел замкнутый вид
    T(r) = T_ext + mu_JT·[p(r) - p_ext],
потому что скорость сокращалась. В двухфазной зоне так не выходит: к JT
добавляется скрытая теплота дегазации, а конвективный коэффициент
Φ = Σ_α ρ_α cp_α Q_α меняется по r, потому что часть нефти переходит в газ.

ТОЧНАЯ ФОРМУЛА. Стационарное уравнение схемы при λ = 0 и dp/dt = 0
(см. tridiag.py, assemble_tridiag) для ячейки j:

    (Φ T)_{j+1} - (Φ T)_j = J_{j+1} - J_j + V_j·Q_deg,j,

где J = Σ_α mu_JT,α Φ_α p — поток Джоуля–Томсона, а Q_deg = -L·mdot.
В стационаре временная часть mdot равна нулю, остаётся конвективная:
mdot = -ρ_g,ст·(R_{j+1} - R_j)/V_j, R_f = <G^o·Rs>_f. Значит

    V_j·Q_deg,j = L·ρ_g,ст·(R_{j+1} - R_j),

и правая часть тоже дивергентна. Суммируя от грани f до контура N,
все внутренние слагаемые телескопируются:

    Φ_N T_ext - Φ_f T_f = (J_N - J_f) + L·ρ_g,ст·(R_N - R_f),

откуда ЯВНО

    T_f = [ Φ_N T_ext - J_N + J_f - L·ρ_g,ст·(R_N - R_f) ] / Φ_f.

Формула точна для схемы, но требует численных Φ, J, R — это не замкнутое
выражение через p(r). Её ценность в другом: она разлагает перепад
температуры на физические вклады, см. decompose_two_phase().

ОДНОФАЗНАЯ ЗОНА. Там S_g = 0, Φ_g = 0, R = G^o·Rs0 постоянно (Rs = Rs0),
поэтому член дегазации выпадает, Φ_o сокращается, и формула вырождается
ровно в асимптотику примера 02:

    T(r) = T_ext + mu_JT,o·[p(r) - p_ext].

ЧЕМ 05 ОТЛИЧАЕТСЯ ОТ 03 ЗДЕСЬ. В примере 03 конфиг задавал λ ≠ 0, и
телескопирование не учитывало кондуктивный поток — оставалась поправка
~0.003 К. В 05 теплопроводности обнулены, кондуктивная проводимость
Q_T = 2πh/(w_L/λ_L + w_R/λ_R) обращается в ноль тождественно, и формула
воспроизводит схему до машинной точности. Это делает пример 05 более
чистой проверкой: расхождение, если оно появится, указывает на ошибку
в сборке уравнения, а не на отброшенную физику.

ПОЧЕМУ ПРОФИЛЬ T В ДВУХФАЗНОЙ ЗОНЕ ПОЧТИ ПЛОСКИЙ. Разложение перепада
между забоем и фронтом даёт три вклада, два охлаждающих и один греющий:
Джоуль–Томсон и скрытая теплота тянут вниз, а изменение Φ — вверх.
По мере разгазирования часть массы переходит в газ, у которого cp вдвое
меньше, поэтому |Φ| падает, и та же энергия соответствует более высокой
температуре. Плоский профиль — не признак слабости эффектов, а результат
их взаимного погашения. Конкретные числа для 05 печатает report();
они близки к 03, потому что зависят от PVT и потоков, а не от ОФП.
"""

import numpy as np


def _face_coefficients(history, config, pvt, grid):
    """Φ, J, R на всех гранях — ровно как их собирает tridiag.py.

    Возвращает (Phi, Phi_o, Phi_g, J, R_conv), все [N+1].
    Upstream: при потоке к скважине (Q < 0) upstream грани f — ячейка f.
    """
    N = grid.N
    st = history.states[-1]
    hr = history.hydro_results[-1]
    p, Sg, Rs, T = st.p, st.Sg, st.Rs, st.T
    Q_o, Q_g, G_o = hr.Q_o, hr.Q_g, hr.G_o

    rho_o = pvt.rho_o(p, Rs)
    rho_g = pvt.rho_g(p)
    cp_o = pvt.c_p_oil(p, T)
    cp_g = pvt.c_p_gas(p, T)
    mu_JT_o = pvt.mu_JT_oil(p, T)
    mu_JT_g = pvt.mu_JT_gas(p, T)

    Phi_o = np.zeros(N + 1)
    Phi_g = np.zeros(N + 1)
    J = np.zeros(N + 1)

    # ── Внутренние грани ──
    for f in range(1, N):
        up_o = f - 1 if Q_o[f] >= 0 else f
        Phi_o[f] = rho_o[up_o] * cp_o[up_o] * Q_o[f]
        up_g = f - 1 if Q_g[f] >= 0 else f
        Phi_g[f] = rho_g[up_g] * cp_g[up_g] * Q_g[f]

        # <Φ·p>_f: положительная часть берёт p слева, отрицательная — справа
        Po_p, Po_m = max(Phi_o[f], 0.0), min(Phi_o[f], 0.0)
        Pg_p, Pg_m = max(Phi_g[f], 0.0), min(Phi_g[f], 0.0)
        J[f] = (mu_JT_o[up_o] * (Po_p * p[f - 1] + Po_m * p[f])
                + mu_JT_g[up_g] * (Pg_p * p[f - 1] + Pg_m * p[f]))

    # ── Забой (f=0): upstream = ячейка 0 ──
    Phi_o[0] = rho_o[0] * cp_o[0] * Q_o[0]
    Phi_g[0] = rho_g[0] * cp_g[0] * Q_g[0]
    J[0] = (mu_JT_o[0] * Phi_o[0] + mu_JT_g[0] * Phi_g[0]) * p[0]

    # ── Контур (f=N): upstream = ячейка N-1 ──
    Phi_o[N] = rho_o[-1] * cp_o[-1] * Q_o[N]
    Phi_g[N] = rho_g[-1] * cp_g[-1] * Q_g[N]
    J[N] = (mu_JT_o[-1] * Phi_o[N] + mu_JT_g[-1] * Phi_g[N]) * p[-1]

    # ── R_f = <G^o·Rs>_f — поток растворённого газа ──
    R_conv = np.zeros(N + 1)
    for f in range(1, N):
        Go_p, Go_m = max(G_o[f], 0.0), min(G_o[f], 0.0)
        R_conv[f] = Go_p * Rs[f - 1] + Go_m * Rs[f]
    R_conv[0] = G_o[0] * Rs[0]
    R_conv[N] = G_o[N] * Rs[-1]

    return Phi_o + Phi_g, Phi_o, Phi_g, J, R_conv


def stationary_face_temperature(history, config, pvt, grid):
    """Точная стационарная T на гранях по телескопической формуле.

    Возвращает (T_pred, T_num) — оба [N+1].
    T_num — численная температура на грани по upwind: при потоке к скважине
    это T правой ячейки, на контуре — T_ext.

    ВАЖНО: формула верна только при λ = 0 и на стационаре. В конфиге 05
    теплопроводности обнулены, поэтому первое условие выполнено точно;
    остаточное расхождение отражает лишь незавершённость релаксации T.
    """
    N = grid.N
    T_ext = config.initial_conditions.T0
    L = config.thermal.L_degas
    rho_g_std = pvt.rho_g_std

    Phi, _, _, J, R = _face_coefficients(history, config, pvt, grid)

    T_pred = np.empty(N + 1)
    for f in range(N + 1):
        T_pred[f] = (Phi[N] * T_ext - J[N] + J[f]
                     - L * rho_g_std * (R[N] - R[f])) / Phi[f]

    T_num = np.empty(N + 1)
    T_num[:N] = history.states[-1].T[:N]   # upstream = правая ячейка
    T_num[N] = T_ext                       # контур: приток извне
    return T_pred, T_num


def single_phase_asymptote(history, config):
    """Асимптотика примера 02: T = T_ext + mu_JT,o·(p - p_ext), [N].

    Опорная точка — центр последней ячейки, а не r = R_e: ГУ Дирихле держит
    T_ext за контуром, где p = p_0, тогда как численный профиль отсчитывается
    от центра ячейки. Та же оговорка, что в примере 02.
    """
    p = history.states[-1].p
    return config.initial_conditions.T0 + config.thermal.mu_JT_oil * (p - p[-1])


def decompose_two_phase(history, config, pvt, grid, f_well=0, f_front=None):
    """Разложить перепад T между забоем и фронтом на физические вклады.

    Возвращает dict с ключами jt, latent, phi_change, sum, actual (все К).

    Перепад dT = T(забой) - T(фронт) получается из телескопической формулы
    делением на Φ(забой):
        dT = -(J_фронт - J_забой)/Φ_забой          — Джоуля–Томсона
             -L·ρ_g,ст·(R_фронт - R_забой)/Φ_забой — скрытая теплота
             + T_фронт·(Φ_фронт - Φ_забой)/Φ_забой — изменение Φ
    """
    T = history.states[-1].T
    Sg = history.states[-1].Sg
    L = config.thermal.L_degas
    rho_g_std = pvt.rho_g_std

    if f_front is None:
        # Последняя грань, за которой ещё есть газ: индекс последней
        # двухфазной ячейки. Sg > 0 только в зоне разгазирования.
        gas_cells = np.where(Sg > 1e-12)[0]
        if len(gas_cells) == 0:
            return None
        f_front = int(gas_cells[-1])

    Phi, _, _, J, R = _face_coefficients(history, config, pvt, grid)

    dJ = J[f_front] - J[f_well]
    dDeg = L * rho_g_std * (R[f_front] - R[f_well])
    dPhi = Phi[f_front] - Phi[f_well]

    jt = -dJ / Phi[f_well]
    latent = -dDeg / Phi[f_well]
    phi_change = T[f_front] * dPhi / Phi[f_well]

    return dict(jt=jt, latent=latent, phi_change=phi_change,
                sum=jt + latent + phi_change,
                actual=T[f_well] - T[f_front],
                f_front=f_front)


def report(history, config, pvt, grid) -> dict:
    """Печать стационарных проверок. Возвращает сводку."""
    Sg = history.states[-1].Sg
    T = history.states[-1].T
    mask1 = Sg <= 1e-12

    print("── Стационарная асимптотика температуры ──")

    T_pred, T_num = stationary_face_temperature(history, config, pvt, grid)
    err_face = float(np.max(np.abs(T_pred[:grid.N] - T_num[:grid.N])))
    print(f"  телескопическая формула на гранях: max|T_форм - T_числ| = "
          f"{err_face:.3e} К")
    print(f"    (λ=0 задано в конфиге, поэтому формула точна для схемы; "
          f"остаток — незавершённая релаксация T за 3 сут)")

    T_as = single_phase_asymptote(history, config)
    err_1ph = float(np.max(np.abs(T[mask1] - T_as[mask1]))) if mask1.any() else np.nan
    print(f"  однофазная асимптотика T = T_ext + μ_JT(p - p_ext): "
          f"max|ΔT| = {err_1ph:.4f} К")
    print(f"    (за 3 суток релаксация не завершена — как в примере 02)")

    dec = decompose_two_phase(history, config, pvt, grid)
    if dec is not None:
        print(f"  разложение перепада T (забой ↔ фронт, грань {dec['f_front']}):")
        print(f"    Джоуль–Томсон    {dec['jt']:+8.4f} К")
        print(f"    скрытая теплота  {dec['latent']:+8.4f} К")
        print(f"    изменение Φ      {dec['phi_change']:+8.4f} К")
        print(f"    сумма            {dec['sum']:+8.4f} К   "
              f"фактически {dec['actual']:+8.4f} К")

    return dict(err_face=err_face, err_1ph=err_1ph, decomposition=dec,
                T_asymptote=T_as)


# ── Автономный запуск ──
if __name__ == "__main__":
    import sys
    from pathlib import Path

    HERE = Path(__file__).resolve().parent
    SOLVER_ROOT = HERE.parents[1]
    sys.path.insert(0, str(SOLVER_ROOT))
    sys.path.insert(0, str(SOLVER_ROOT / "examples"))
    sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory

    config = load_config(HERE / "config.json")
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    report(history, config, sim._energy._pvt, sim._grid)
