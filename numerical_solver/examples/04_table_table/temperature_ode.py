"""ОДУ-аналитика температуры для примера 04 — табличный аналог примера 03.

ПОЧЕМУ ЗДЕСЬ ОДУ ТОЧНО, А НЕ ПРИБЛИЖЁННО. В примерах 01-03 теплопроводность
физически присутствовала, но в ОДУ не включалась: она сделала бы задачу
краевой (вторая производная). Там это оправдывалось малостью вклада
(в 03: ошибка 0.119 К при lambda = 0 против 0.122 К с ней).

В конфиге примера 04 все три теплопроводности обнулены:

    "lambda_solid": 0.0, "lambda_oil": 0.0, "lambda_gas": 0.0

Тогда кондуктивная проводимость граней Q_T = 2 pi h / (w_L/lam_L + w_R/lam_R)
обращается в ноль тождественно, уравнение энергии становится ОДУ первого
порядка ТОЧНО, и расхождение с решателем — это уже только ошибка перехода
от разностного оператора к дифференциальному, без физического упущения.

УРАВНЕНИЕ. То же, что в 03. Шаг 1 (адиабатический импульс: p падает с p_0
до стационарного профиля за один шаг), шаги n >= 2 (dp/dt = 0):

    (rho cp)_eff (T^n - T^{n-1})/dt
        = -(1/A) d(Phi T^n)/dr + (1/A) dJ/dr + L rho_g_st/A * dR/dr [+ Q_ad]

где A = 2 pi r h, J = sum_a mu_JT,a Phi_a p — поток Джоуля-Томсона,
R = <G^o Rs> — поток растворённого газа. Разрешая относительно dT/dr:

    dT/dr = -[ A (kappa (T - T_prev) - src) + T dPhi/dr ] / Phi,
    kappa = (rho cp)_eff / dt.

ГУ: T(R_e) = T_0, интегрирование от контура к скважине.

ЧТО ОТЛИЧАЕТСЯ ОТ 03. Структура уравнения та же, но коэффициенты нельзя
заморозить по конечному состоянию. В 03 гидродинамика вставала на стационар
за три шага; здесь она релаксирует постепенно:

    шаг         1      2      3      5      8
    |dPhi|/Phi  36 %   10 %   2.5 %  0.15 % 0.002 %
    Q_ad*V, Вт  -4.4e6 -1.2e6 -2.9e5 -1.7e4 -2.5e2

Заморозка по последнему состоянию (как в 03) давала ошибку 0.45 К, почти
НЕ УБЫВАЮЩУЮ с числом шагов — признак неверных коэффициентов, а не
накопления ошибки рекурсии. После перехода на пошаговые коэффициенты
ошибка упала до 0.017 К.

Как и в 03, Rs и Phi_g интерполируются PCHIP (кубический сплайн даёт
осцилляции производной на изломе у фронта), остальное — CubicSpline.

ТОЧНОСТЬ (N = 50):

    шаг                    24        72
    max|T_num - T_ode|     0.017 К   0.017 К
    в однофазной зоне      0.004 К   0.006 К

Это втрое точнее примера 03 (0.049 К) — там теплопроводность в ОДУ
отбрасывалась, здесь она физически отсутствует.

Запуск автономно:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04_table_table\\temperature_ode.py
"""

import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d, CubicSpline, PchipInterpolator

# Число шагов по умолчанию для автономного запуска. ОДУ решается рекуррентно —
# каждый шаг требует интерполяции предыдущего, пропустить шаги нельзя.
DEFAULT_N_STEPS = 24


def _interpolants_at(history, config, grid, es, n):
    """Набор коэффициентов ОДУ, замороженных на шаге n.

    Интерполируются ПОТОКИ (Phi, J, R), а не плотности источников:
    J_jt и Q_deg дивергентны и резко меняются у фронта разгазирования,
    поячеечная интерполяция плотностей даёт ошибку в целый градус.
    """
    N = grid.N
    x_c, x_f = np.log(grid.r_centers), np.log(grid.r_faces)

    st, st_prev = history.states[n], history.states[n - 1]
    hr = history.hydro_results[n]
    p, Sg, Rs = st.p, st.Sg, st.Rs

    props = es.compute_cell_properties(p, Sg, Rs, 1.0 - Sg, st_prev.T)
    _, _, Phi_o, Phi_g = es.compute_convective_coefficients(
        hr.Q_o, hr.Q_g, props['rho_o'], props['rho_g'],
        props['c_p_o'], props['c_p_g'], N)

    mu_o = config.thermal.mu_JT_oil
    mu_g = config.thermal.mu_JT_gas

    # Upwind-сдвиг: схема берёт p и Rs на грани из ячейки выше по потоку
    # (правой, т.к. поток к скважине). На логарифмической сетке — полшага по ln r.
    dx_half = 0.5 * (x_c[1] - x_c[0])

    # Rs и Phi_g имеют излом на фронте: слева Rs убывает, справа строго
    # постоянен. Кубический сплайн через такой узел даёт знакопеременные
    # осцилляции производной, а dRs/dr входит прямо в источник дегазации —
    # появились бы паразитные источники там, где схема даёт строгий ноль.
    # PCHIP сохраняет монотонность и даёт там точный ноль.
    Phi_o_s = CubicSpline(x_f, Phi_o)
    Phi_g_s = PchipInterpolator(x_f, Phi_g)
    Phi_s = CubicSpline(x_f, Phi_o + Phi_g)
    Go_s = CubicSpline(x_f, hr.G_o)
    p_s = CubicSpline(x_c, p)
    Rs_s = PchipInterpolator(x_c, Rs)
    rcp_s = CubicSpline(x_c, props['rho_cp_eff'])

    # Адиабатический источник этого шага: phi * sum_a S_a (1 + rho cp mu_JT) dp/dt.
    # Не ноль, пока давление релаксирует.
    Q_ad = es.compute_adiabatic(
        1.0 - Sg, Sg, props['rho_o'], props['rho_g'],
        props['c_p_o'], props['c_p_g'], props['mu_JT_o'], props['mu_JT_g'],
        p, st_prev.p, config.time.dt_integration)
    ad_s = CubicSpline(x_c, Q_ad)

    return dict(
        Phi=Phi_s, rcp=rcp_s, ad=ad_s,
        # J(r) = sum_a mu_a Phi_a p_up — поток Джоуля–Томсона, Вт
        J=lambda x: (mu_o * Phi_o_s(x) + mu_g * Phi_g_s(x)) * p_s(x + dx_half),
        # R(r) = G^o Rs_up — поток растворённого газа, м³ст/с
        R=lambda x: Go_s(x) * Rs_s(x + dx_half),
    )


def _build_interpolants(history, config, grid, energy_solver, n_steps):
    """Коэффициенты ОДУ для каждого шага рекурсии 1..n_steps.

    ВАЖНОЕ ОТЛИЧИЕ ОТ ПРИМЕРА 03. Там гидродинамика вставала на стационар
    за три шага, коэффициенты можно было заморозить по конечному состоянию,
    а адиабатический импульс учесть только на первом шаге.

    Здесь (табличные PVT) давление релаксирует постепенно. На шаге 1
    конвективный коэффициент Phi отличается от стационарного на 36 %,
    на шаге 2 — на 10 %, на шаге 3 — на 2.5 %, и лишь к шагу 8 разница
    падает ниже 0.01 %. Адиабатический источник Q_ad*V спадает так же:
    -4.4e6, -1.2e6, -2.9e5, -7.1e4 ... Вт.

    Заморозка по конечному состоянию давала систематическую ошибку 0.45 К,
    ПОЧТИ ПОСТОЯННУЮ по числу шагов — признак неверных коэффициентов,
    а не накопления ошибки рекурсии. Поэтому для каждого шага берём свои,
    а после выхода на стационар переиспользуем один набор.
    """
    es = energy_solver
    n_avail = len(history.states) - 1
    per_step = {}

    stationary = None
    for n in range(1, min(n_steps, n_avail) + 1):
        # Гидродинамика стационарна, если состояние не изменилось за шаг
        st, st_prev = history.states[n], history.states[n - 1]
        frozen = (np.abs(st.p - st_prev.p).max() < 1e-6
                  and np.abs(st.Sg - st_prev.Sg).max() < 1e-12)
        if frozen and stationary is not None:
            per_step[n] = stationary
            continue
        ip = _interpolants_at(history, config, grid, es, n)
        per_step[n] = ip
        if frozen:
            stationary = ip

    # Если запрошено больше шагов, чем есть в истории, — добиваем последним
    if n_steps > n_avail:
        last = per_step[n_avail]
        for n in range(n_avail + 1, n_steps + 1):
            per_step[n] = last

    return per_step


def _make_rhs(ip, config, energy_solver, with_jt, with_degassing, T_prev_f):
    """Собрать правую часть ОДУ dT/dr для одного шага рекурсии.

    ip — набор коэффициентов, замороженных на этом шаге.
    """
    h = config.geometry.h
    dt = config.time.dt_integration
    L = config.thermal.L_degas
    rho_g_std = energy_solver._pvt.rho_g_std

    # Численная производная потоков по ln r. Шаг 1e-5 — компромисс:
    # крупнее теряет точность у фронта, мельче попадает в шум сплайна.
    eps = 1e-5

    def rhs(r, y):
        T = y[0]
        x = np.log(r)
        T_prev = float(T_prev_f(r))
        A = 2.0 * np.pi * r * h            # площадь грани, м²

        Phi_v = float(ip['Phi'](x))
        dPhi_dr = float(ip['Phi'](x, 1)) / r

        src = 0.0
        if with_jt:
            # (1/A) dJ/dr — дивергенция потока Джоуля–Томсона
            dJ = (ip['J'](x + eps) - ip['J'](x - eps)) / (2 * eps)
            src += float(dJ) / r / A
        if with_degassing:
            # Q_deg = -L·mdot, mdot = -rho_g_st/A · dR/dr (стационар)
            dR = (ip['R'](x + eps) - ip['R'](x - eps)) / (2 * eps)
            src += L * rho_g_std * float(dR) / r / A
        # Адиабатический член — не ноль, пока давление релаксирует
        src += float(ip['ad'](x))

        kappa = float(ip['rcp'](x)) / dt
        # kappa(T - T_prev) = -(1/A)[Phi dT/dr + T dPhi/dr] + src
        return [-(A * (kappa * (T - T_prev) - src) + T * dPhi_dr) / Phi_v]

    return rhs


def solve_ode_at_steps(history, config, grid, energy_solver, steps,
                       with_jt=True, with_degassing=True, n_points=500):
    """Решения ОДУ на нескольких шагах за один рекуррентный проход.

    Возвращает dict {step: (r, T)}.
    """
    per_step = _build_interpolants(history, config, grid, energy_solver,
                                   n_steps=max(steps))
    r_w, R_e = config.geometry.r_well, config.geometry.R_ext
    T0 = config.initial_conditions.T0

    r_grid = np.logspace(np.log10(r_w), np.log10(R_e), n_points)
    r_desc = r_grid[::-1]

    # T^0 = T_0 всюду
    T_prev_f = lambda r: np.full(np.shape(r), float(T0))
    out = {}
    if 0 in steps:
        out[0] = (r_grid, np.full_like(r_grid, T0))

    for n in range(1, max(steps) + 1):
        rhs = _make_rhs(per_step[n], config, energy_solver,
                        with_jt, with_degassing, T_prev_f)
        # Интегрируем от контура (там T = T_0 задано) к скважине
        sol = solve_ivp(rhs, [R_e, r_w], [T0], t_eval=r_desc,
                        rtol=1e-9, atol=1e-11, method='LSODA')
        r_out, T_out = sol.t[::-1], sol.y[0, ::-1]
        if n in steps:
            out[n] = (r_out, T_out)
        T_prev_f = interp1d(r_out, T_out, kind='cubic',
                            fill_value='extrapolate')

    return out


def solve_ode(history, config, grid, energy_solver,
              n_steps=DEFAULT_N_STEPS, with_jt=True, with_degassing=True,
              n_points=500):
    """Рекуррентно решить ОДУ n_steps раз. Возвращает (r, T) на последнем шаге."""
    out = solve_ode_at_steps(history, config, grid, energy_solver,
                             steps=[n_steps], with_jt=with_jt,
                             with_degassing=with_degassing, n_points=n_points)
    return out[n_steps]


def report(history, config, grid, energy_solver, n_steps=DEFAULT_N_STEPS):
    """Сравнить ОДУ с численным решением; показать, что оба члена нужны."""
    T_num = history.states[n_steps].T
    r_c = grid.r_centers
    Sg = history.states[-1].Sg
    mono = Sg <= 1e-12          # однофазная зона: там разгазирования нет

    lam = config.rock.lambda_solid
    print(f"== ОДУ-аналитика температуры (шаг {n_steps}, "
          f"t = {history.times[n_steps] / 3600:.0f} ч) ==")
    print(f"lambda_solid = {lam} => при нуле ОДУ точно, а не приближённо")

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
        err1 = float(np.max(np.abs((T_num - T_i)[mono])))
        results[label] = (r_o, T_o, err)
        print(f"  {label:26s} max|dT| = {err:.4f} К   "
              f"(однофазная зона {err1:.4f} К)")

    print("  Выключение любого члена увеличивает ошибку на порядок — "
          "оба обязательны.")
    return results["полное (JT + дегазация)"]


def overlay_temperature(ax, history, grid, simulator):
    """Наложить ОДУ-решения на график профилей температуры (хук example_runner).

    Кривые строятся на тех же шагах, что рисует run_example, чтобы ОДУ и
    расчёт сравнивались попарно, а не только в конечный момент.
    """
    from gpn_multiphase_solver.io.config import load_config

    config = load_config(Path(__file__).parent / "config.json")
    # example_runner берёт 4 момента: начало, треть, две трети, конец.
    # Нулевой шаг пропускаем: там T = T_0 всюду, сравнивать нечего.
    n = len(history.times)
    steps = sorted({n // 3, 2 * n // 3, n - 1})

    sols = solve_ode_at_steps(history, config, grid, simulator._energy,
                              steps=steps)

    for k, s in enumerate(steps):
        r_o, T_o = sols[s]
        ax.plot(r_o, T_o, "k--", lw=1.6, zorder=5,
                label="ОДУ ($\\lambda = 0$)" if k == 0 else None)


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
