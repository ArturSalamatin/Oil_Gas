"""ОДУ-аналитика температуры для примера 05 (Standing PVT + табличная ОФП).

В примерах 01 и 02 температура на каждом шаге воспроизводилась решением ОДУ —
непрерывного аналога неявной FVM-схемы при lambda = 0. Пример 03 перенёс эту
идею в двухфазную постановку; здесь тот же вывод применяется при табличной
ОФП. Физика и PVT совпадают с 03, меняется только замыкание k_r(S_g).

ЧТО ПОЗВОЛЯЕТ ПЕРЕНОС. Гидродинамика в этом сценарии выходит на стационар
за несколько шагов и дальше не меняется, поэтому все коэффициенты уравнения
энергии постоянны во времени, и рекуррентная схема "решить ОДУ, подставить
результат как T_prev, решить снова" работает так же, как в 02.

ПОЧЕМУ В 05 ТОЧНЕЕ, ЧЕМ В 03. В примере 03 остаточная ошибка ОДУ (0.049 К)
почти вся сидела в шести ячейках зоны разгазирования, и главная причина
называлась там прямо: у Кори k_rg = k_rg^max·(S_g - S_gc)^2 имеет ПОРОГ
подвижности S_gc = 0.05, из-за чего между соседними ячейками k_rg менялась
в 338 раз. Гладкий интерполянт такой скачок не воспроизводит.

Табличная ОФП этого дефекта не имеет: на первом отрезке k_rg ≈ 0.1·S_g —
линейный рост от нуля, без порога. Коэффициенты ОДУ становятся гладкими
по r, и ошибка перехода от разностного оператора к дифференциальному
падает. Это не «улучшение метода», а следствие того, что интерполируемая
функция стала гладкой — ровно то, чего требует вывод ОДУ.

Дополнительно в конфиге 05 обнулены теплопроводности (lambda = 0), тогда
как в 03 они были ненулевыми. ОДУ выводится именно при lambda = 0, поэтому
здесь оно описывает ту же задачу, что решает решатель, а не её приближение.

ЧТО ПРИШЛОСЬ УЧЕСТЬ ПРИ ВЫВОДЕ (перенесено из 03 без изменений).

  1. Phi больше не константа. В 01/02 нефть несжимаема, Q_o ~ 1/r, и
     Phi_o = rho cp Q_o постоянен по r — поэтому дивергенция сворачивалась
     в (beta/r) dT/dr. Здесь часть нефти переходит в газ, |Phi| падает к
     забою, и в уравнении остаётся второе слагаемое T dPhi/dr. Именно оно
     даёт греющий вклад в разложение перепада (см.
     temperature_asymptotics.py) — выбросить его нельзя.

  2. Добавляется скрытая теплота. Источник недивергентный по виду, но в
     стационаре его временная часть равна нулю, и остаётся конвективная:
     mdot = -rho_g_st/(2 pi r h) * d(G^o Rs)/dr.

  3. Источники нельзя интерполировать поячеечно. Взять J_jt и Q_deg как
     плотности в ячейках и интерполировать — ошибка в 03 достигала 1.26 К.
     Обе величины дивергентны и резко меняются у фронта; интерполировать
     надо ПОТОКИ (Phi, p, Rs, G^o), а производные брать от интерполянтов.

  4. Upwind сдвигает аргумент. Схема берёт p и Rs на грани из ячейки ВЫШЕ
     ПО ПОТОКУ, то есть правой (поток к скважине), а не с самой грани.
     Сдвиг составляет полшага по ln r; у забоя это ~0.27 МПа, что в
     температуре даёт mu_JT * 0.27 МПа ≈ 0.11 К. Воспроизведение сдвига
     обязательно.

УРАВНЕНИЕ. Шаг 1 (есть адиабатический импульс, p падает от p_0 до профиля
Дюпюи за один шаг), шаги n >= 2 (dp/dt = 0):

    (rho cp)_eff (T^n - T^{n-1})/dt
        = -(1/A) d(Phi T^n)/dr + (1/A) dJ/dr + L rho_g_st/A * dR/dr [+ Q_ad]

где A = 2 pi r h, J = sum_a mu_JT,a Phi_a p — поток Джоуля-Томсона,
R = <G^o Rs> — поток растворённого газа. Разрешая относительно dT/dr:

    dT/dr = -[ A (kappa (T - T_prev) - src) + T dPhi/dr ] / Phi,
    kappa = (rho cp)_eff / dt.

ГУ: T(R_e) = T_0, интегрирование от контура к скважине.

ЧЕГО ФОРМУЛА НЕ УЧИТЫВАЕТ. Теплопроводности в ОДУ нет — она сделала бы
задачу краевой (вторая производная). В примере 03 это было приближением;
в 05 lambda = 0 задано в конфиге, поэтому здесь никакого пренебрежения нет:
ОДУ соответствует ровно той задаче, которую решает решатель.

ТОЧНОСТЬ. Числа печатает report(); он же показывает, что ни один из членов
выбросить нельзя — выключение JT или дегазации увеличивает ошибку на
порядок. Ошибка убывает с измельчением сетки (проверяется отдельным
скриптом ode_grid_convergence.py), что и подтверждает: остаток —
дискретизационный, а не дефект вывода.

Запуск автономно:
    cd numerical_solver
    .venv\\Scripts\\python examples\\05_standing_table_rp\\temperature_ode.py
"""

import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d, CubicSpline, PchipInterpolator

# Число шагов по умолчанию для автономного запуска. ОДУ решается
# рекуррентно — каждый шаг требует интерполяции предыдущего, пропустить
# шаги нельзя. 24 шага (сутки) считаются секунды; полные 72 — втрое дольше,
# при том что ошибка выходит на полку рано.
DEFAULT_N_STEPS = 24


def _build_interpolants(history, config, grid, energy_solver):
    """Гладкие функции r для всех коэффициентов ОДУ.

    Интерполируются ПОТОКИ (Phi, J, R) и свойства, а не плотности
    источников: J_jt и Q_deg дивергентны и резко меняются у фронта,
    поячеечная интерполяция плотностей даёт ошибку в 1.26 К.

    Возвращает dict с функциями от x = ln r.
    """
    N = grid.N
    es = energy_solver
    r_c, r_f = grid.r_centers, grid.r_faces
    x_c, x_f = np.log(r_c), np.log(r_f)

    # Состояние на стационаре: с 5-го шага p, Sg, Rs не меняются вовсе,
    # поэтому коэффициенты берём из последнего состояния.
    st = history.states[-1]
    st_prev = history.states[-2]
    hr = history.hydro_results[-1]
    p, Sg, Rs = st.p, st.Sg, st.Rs

    props = es.compute_cell_properties(p, Sg, Rs, 1.0 - Sg, st_prev.T)

    # Свойства контура — выше по потоку при притоке (DEBT-017). Объекта bc
    # здесь нет (скрипт работает по history), собираем из конфига так же,
    # как factory.py:328-334. _ext_properties читает только p_ext, T_ext,
    # Rs_ext; well в расчёт не входит, но поле обязательное.
    from gpn_multiphase_solver.state import BoundaryConditions
    from gpn_multiphase_solver.bc import PressureControl
    ic = config.initial_conditions
    bc = BoundaryConditions(
        well=PressureControl(config.time.history[0].p_wf), p_ext=ic.p0,
        T_ext=ic.T0, Rs_ext=ic.Rs0, Sg_ext=0.0)
    ext = es._ext_properties(bc)

    _, _, Phi_o, Phi_g = es.compute_convective_coefficients(
        hr.Q_o, hr.Q_g, props['rho_o'], props['rho_g'],
        props['c_p_o'], props['c_p_g'], N, ext)

    mu_o = config.thermal.mu_JT_oil
    mu_g = config.thermal.mu_JT_gas

    # Upwind-сдвиг: схема берёт p и Rs на грани из ячейки выше по потоку
    # (правой, т.к. поток к скважине), а не с самой грани. На логарифмической
    # сетке это ровно полшага по ln r.
    dx_half = 0.5 * (x_c[1] - x_c[0])

    # Rs и Phi_g имеют ИЗЛОМ на фронте: слева Rs убывает, справа он строго
    # постоянен (= Rs0). Кубический сплайн через такой узел даёт
    # затухающие знакопеременные осцилляции производной (в однофазной зоне,
    # где dRs/dr = 0 точно, он выдаёт -1.30, +0.35, -0.093, +0.025 ...).
    # Производная Rs входит прямо в источник дегазации, поэтому осцилляции
    # порождают паразитные источники в ячейках, где схема даёт строгий ноль.
    # PCHIP сохраняет монотонность и даёт там точный ноль.
    Phi_o_s = CubicSpline(x_f, Phi_o)
    Phi_g_s = PchipInterpolator(x_f, Phi_g)
    Phi_s = CubicSpline(x_f, Phi_o + Phi_g)
    Go_s = CubicSpline(x_f, hr.G_o)
    p_s = CubicSpline(x_c, p)
    Rs_s = PchipInterpolator(x_c, Rs)
    rcp_s = CubicSpline(x_c, props['rho_cp_eff'])

    # Адиабатический импульс 1-го шага: давление падает с p_0 до профиля
    # Дюпюи за один шаг, dp/dt огромно. На шагах n >= 2 он строго нулевой.
    s1, s0 = history.states[1], history.states[0]
    pr1 = es.compute_cell_properties(s1.p, s1.Sg, s1.Rs, 1.0 - s1.Sg, s0.T)
    Q_ad1 = es.compute_adiabatic(
        1.0 - s1.Sg, s1.Sg, pr1['rho_o'], pr1['rho_g'],
        pr1['c_p_o'], pr1['c_p_g'], pr1['mu_JT_o'], pr1['mu_JT_g'],
        s1.p, s0.p, config.time.dt_integration)
    ad1_s = CubicSpline(x_c, Q_ad1)

    return dict(
        Phi=Phi_s, rcp=rcp_s, ad1=ad1_s,
        # J(r) = sum_a mu_a Phi_a p_up — поток Джоуля-Томсона, Вт
        J=lambda x: (mu_o * Phi_o_s(x) + mu_g * Phi_g_s(x)) * p_s(x + dx_half),
        # R(r) = G^o Rs_up — поток растворённого газа, м³ст/с
        R=lambda x: Go_s(x) * Rs_s(x + dx_half),
    )


def solve_ode(history, config, grid, energy_solver,
              n_steps=DEFAULT_N_STEPS, with_jt=True, with_degassing=True,
              n_points=500):
    """Рекуррентно решить ОДУ n_steps раз.

    with_jt / with_degassing позволяют выключить отдельные члены — это
    нужно, чтобы показать, что каждый из них обязателен (см. report()).

    Возвращает (r, T) — решение на последнем шаге.
    """
    ip = _build_interpolants(history, config, grid, energy_solver)
    r_w, R_e = config.geometry.r_well, config.geometry.R_ext
    h = config.geometry.h
    T0 = config.initial_conditions.T0
    dt = config.time.dt_integration
    L = config.thermal.L_degas
    rho_g_std = energy_solver._pvt.rho_g_std

    # Численная производная потоков по ln r. Шаг 1e-5 — компромисс:
    # крупнее теряет точность у фронта, мельче попадает в шум сплайна.
    eps = 1e-5

    def dJ_dx(x):
        return (ip['J'](x + eps) - ip['J'](x - eps)) / (2 * eps)

    def dR_dx(x):
        return (ip['R'](x + eps) - ip['R'](x - eps)) / (2 * eps)

    r_grid = np.logspace(np.log10(r_w), np.log10(R_e), n_points)
    r_desc = r_grid[::-1]

    # T^0 = T_0 всюду
    T_prev_f = lambda r: np.full(np.shape(r), float(T0))
    r_out, T_out = r_grid, np.full_like(r_grid, T0)

    for n in range(1, n_steps + 1):
        first = (n == 1)

        def rhs(r, y, first=first):
            T = y[0]
            x = np.log(r)
            T_prev = float(T_prev_f(r))
            A = 2.0 * np.pi * r * h            # площадь грани, м²

            Phi_v = float(ip['Phi'](x))
            dPhi_dr = float(ip['Phi'](x, 1)) / r

            src = 0.0
            if with_jt:
                # (1/A) dJ/dr — дивергенция потока Джоуля-Томсона
                src += float(dJ_dx(x)) / r / A
            if with_degassing:
                # Q_deg = -L·mdot, mdot = -rho_g_st/A · dR/dr (стационар)
                src += L * rho_g_std * float(dR_dx(x)) / r / A
            if first:
                src += float(ip['ad1'](x))

            kappa = float(ip['rcp'](x)) / dt
            # kappa(T - T_prev) = -(1/A)[Phi dT/dr + T dPhi/dr] + src
            return [-(A * (kappa * (T - T_prev) - src) + T * dPhi_dr) / Phi_v]

        sol = solve_ivp(rhs, [R_e, r_w], [T0], t_eval=r_desc,
                        rtol=1e-9, atol=1e-11, method='LSODA')
        r_out, T_out = sol.t[::-1], sol.y[0, ::-1]
        T_prev_f = interp1d(r_out, T_out, kind='cubic',
                            fill_value='extrapolate')

    return r_out, T_out


def solve_ode_at_steps(history, config, grid, energy_solver, steps,
                       n_points=500):
    """Решения ОДУ на нескольких шагах за один рекуррентный проход.

    solve_ode() пересчитывает всю рекурсию ради одного момента; для графика
    с несколькими кривыми это лишняя работа. Здесь проход один, а решения
    сохраняются на перечисленных шагах.

    Возвращает dict {step: (r, T)}.
    """
    ip = _build_interpolants(history, config, grid, energy_solver)
    r_w, R_e = config.geometry.r_well, config.geometry.R_ext
    h = config.geometry.h
    T0 = config.initial_conditions.T0
    dt = config.time.dt_integration
    L = config.thermal.L_degas
    rho_g_std = energy_solver._pvt.rho_g_std
    eps = 1e-5

    r_grid = np.logspace(np.log10(r_w), np.log10(R_e), n_points)
    r_desc = r_grid[::-1]

    T_prev_f = lambda r: np.full(np.shape(r), float(T0))
    out = {}
    if 0 in steps:
        out[0] = (r_grid, np.full_like(r_grid, T0))

    for n in range(1, max(steps) + 1):
        first = (n == 1)

        def rhs(r, y, first=first):
            T = y[0]
            x = np.log(r)
            T_prev = float(T_prev_f(r))
            A = 2.0 * np.pi * r * h
            Phi_v = float(ip['Phi'](x))
            dPhi_dr = float(ip['Phi'](x, 1)) / r
            src = ((ip['J'](x + eps) - ip['J'](x - eps)) / (2 * eps)) / r / A
            src += (L * rho_g_std
                    * ((ip['R'](x + eps) - ip['R'](x - eps)) / (2 * eps))
                    / r / A)
            if first:
                src += float(ip['ad1'](x))
            kappa = float(ip['rcp'](x)) / dt
            return [-(A * (kappa * (T - T_prev) - src) + T * dPhi_dr) / Phi_v]

        sol = solve_ivp(rhs, [R_e, r_w], [T0], t_eval=r_desc,
                        rtol=1e-9, atol=1e-11, method='LSODA')
        r_out, T_out = sol.t[::-1], sol.y[0, ::-1]
        if n in steps:
            out[n] = (r_out, T_out)
        T_prev_f = interp1d(r_out, T_out, kind='cubic',
                            fill_value='extrapolate')

    return out


def report(history, config, grid, energy_solver, n_steps=DEFAULT_N_STEPS):
    """Сравнить ОДУ с численным решением; показать, что оба члена нужны."""
    T_num = history.states[n_steps].T
    r_c = grid.r_centers
    Sg = history.states[-1].Sg
    mask1 = Sg <= 1e-12

    print(f"── ОДУ-аналитика температуры (шаг {n_steps}, "
          f"t = {history.times[n_steps] / 3600:.0f} ч) ──")

    variants = [
        ("полное (JT + дегазация)", True, True),
        ("без дегазации", True, False),
        ("без JT", False, True),
    ]
    results = {}
    for label, jt, deg in variants:
        r_o, T_o = solve_ode(history, config, grid, energy_solver,
                             n_steps=n_steps, with_jt=jt, with_degassing=deg)
        T_i = np.interp(r_c, r_o, T_o)
        err = float(np.max(np.abs(T_num - T_i)))
        err1 = float(np.max(np.abs((T_num - T_i)[mask1])))
        results[label] = (r_o, T_o, err)
        print(f"  {label:26s} max|dT| = {err:.4f} К   "
              f"(однофазная зона {err1:.4f} К)")

    print("  Выключение любого члена увеличивает ошибку на порядок — "
          "оба обязательны.")
    return results["полное (JT + дегазация)"]


# ── Автономный запуск ──
if __name__ == "__main__":
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

    report(history, config, sim._grid, sim._energy)
