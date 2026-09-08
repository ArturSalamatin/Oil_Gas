"""Сценарий 02: однофазная фильтрация несжимаемой нефти с эффектом Джоуля-Томсона.

После расчёта на графики наносятся три аналитики:

1. Давление — решение Дюпюи (как в примере 01):
       p(r) = p_wf + (p_0 - p_wf) / ln(R_e/r_w) · ln(r/r_w)

2. Температура на каждом шаге — решение ОДУ, непрерывного аналога
   неявной FVM-схемы. Отличие от 01: правая часть содержит два вклада
   JT — постоянно действующий поток -μ_JT·(β/r)·dp/dr и множитель
   (1 + ρ·cp·μ_JT) при адиабатике. Подробности в docstring
   _add_temperature_analytics.

3. Температура в пределе t → ∞ — стационарная JT-асимптотика. Без теплопроводности
   (в этом конфиге λ = 0) стационарный энергобаланс сводится к
       ρ c_p u dT/dr = ρ c_p μ_JT u dp/dr,
   скорость u сокращается, остаётся dT/dr = μ_JT dp/dr, откуда
       T(r) = T_ext + μ_JT · (p(r) - p_ext).
   Профиль не зависит ни от дебита, ни от проницаемости.

   Привязка к КОНТУРУ, а не к p_0: граничное условие Дирихле держит
   T = T_ext за контуром, где давление равно p_0. Опорной точкой служит
   центр последней ячейки, где p чуть ниже p_0 — разница даёт постоянное
   смещение μ_JT·(p_0 - p[-1]) ≈ 0.02 К, которое иначе выглядело бы как
   ошибка схемы.

За 3 суток решение проходит лишь часть пути к этой асимптотике,
поэтому на графике аналитика идёт ниже численных профилей — расхождение
не ошибка, а незавершённая релаксация.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from example_runner import run_example  # noqa: E402
from gpn_multiphase_solver.io.output import plot_profiles  # noqa: E402

# energy_balance.py лежит рядом с main.py — добавляем папку примера в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from energy_balance import plot_energy_balance  # noqa: E402


def _times_to_plot(history):
    """Те же 4 момента времени, что выбирает example_runner."""
    times = history.times
    idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
    return [times[i] for i in sorted(set(idx))]


def _add_dupuit_curve(history, grid, config, output_dir: Path, title: str):
    """Перестроить pressure_profiles.png, добавив аналитику Дюпюи пунктиром."""
    r_w = config.geometry.r_well
    R_e = config.geometry.R_ext
    p0 = config.initial_conditions.p0
    p_wf = config.time.history[0].p_wf

    # Формула Дюпюи: p(r) = p_wf + Δp / ln(R_e/r_w) · ln(r/r_w)
    r_an = np.logspace(np.log10(r_w), np.log10(R_e), 200)
    p_an = p_wf + (p0 - p_wf) / np.log(R_e / r_w) * np.log(r_an / r_w)

    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, _times_to_plot(history), field="p", ax=ax)

    ax.semilogx(r_an, p_an, 'k--', linewidth=1.5, label="Дюпюи (аналит.)")
    ax.legend()
    ax.set_title(f"{title}\nПрофили давления")
    fig.tight_layout()
    fig.savefig(output_dir / "pressure_profiles.png", dpi=110)
    plt.close(fig)


def _add_temperature_analytics(history, grid, config, output_dir: Path,
                               title: str):
    """Перестроить temperature_profiles.png с ОДУ-аналитикой и JT-асимптотикой.

    Аналог одноимённой функции примера 01, но правая часть содержит
    два дополнительных вклада Джоуля-Томсона.

    Для каждого рисуемого момента t_n решается ОДУ — непрерывный аналог
    неявной FVM-схемы (λ=0):

    Шаг 1 (адиабатика + конвекция + JT):
        (ρcp)_eff·(T^1 - T_0)/Δt = β/r·dT^1/dr - μ_JT·β/r·dp/dr
                                   + φ·(1 + ρ·cp·μ_JT)·Δp(r)/Δt

    Шаги n ≥ 2 (конвекция + JT, dp/dt = 0):
        (ρcp)_eff·(T^n - T^{n-1})/Δt = β/r·dT^n/dr - μ_JT·β/r·dp/dr

    ГУ: T^n(R_e) = T_0.  β = ρ_o·cp_o·|Q_o|/(2πh).

    Откуда берутся два JT-члена (см. tridiag.py):

    1. Поток J_face = μ_JT·Φ_o·p (compute_jt) в дивергентной форме даёт
       (1/2πrh)·d(μ_JT·Φ_o·p)/dr. Для несжимаемой нефти Φ_o = const
       и равен -2πh·β (проверено численно), поэтому член сводится
       к -μ_JT·(β/r)·dp/dr. Он действует на КАЖДОМ шаге, пока есть
       градиент давления — отсюда стационарная асимптотика.

    2. Адиабатика (compute_adiabatic) получает множитель (1 + ρ·cp·μ_JT)
       вместо единицы. При данных параметрах это 1.647 — поправка
       в 65%, опускать её нельзя.

    Возвращает отставание численного решения от JT-асимптотики на
    последнем шаге (К) — мера незавершённости релаксации.
    """
    from scipy.integrate import solve_ivp
    from scipy.interpolate import interp1d
    from gpn_multiphase_solver.factory import SimulatorFactory

    r_w = config.geometry.r_well
    R_e = config.geometry.R_ext
    h = config.geometry.h
    p0 = config.initial_conditions.p0
    p_wf = config.time.history[0].p_wf
    T0 = config.initial_conditions.T0
    phi = config.rock.porosity
    dt = config.time.dt_integration
    mu_JT = config.thermal.mu_JT_oil

    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim._energy._pvt
    rock = sim._energy._rock
    p_arr = np.array([p0])
    Rs_arr = np.array([0.0])
    T_arr = np.array([T0])
    rho_o = pvt.rho_o(p_arr, Rs_arr)[0]
    c_p_o = pvt.c_p_oil(p_arr, T_arr)[0]
    rho_cp_eff = (1 - phi) * rock.rho_cp_solid + phi * rho_o * c_p_o

    Q_o = history.hydro_results[1].Q_o[0]
    beta = rho_o * c_p_o * abs(Q_o) / (2 * np.pi * h)
    kappa = rho_cp_eff / dt  # Вт/(м³·К) — коэффициент накопления

    # Множитель адиабатики с учётом JT: (1 + ρ·cp·μ_JT), см. tridiag.py:223
    adiab_factor = 1.0 + rho_o * c_p_o * mu_JT

    C_dup = (p0 - p_wf) / np.log(R_e / r_w)

    def dp_dupuit(r):
        """Δp(r) = p_Dupuit(r) - p_0 — падение давления от начального."""
        return -(p0 - p_wf) + C_dup * np.log(r / r_w)

    def dpdr_dupuit(r):
        """dp/dr для профиля Дюпюи: p ∝ ln r ⇒ dp/dr = C/r."""
        return C_dup / r

    # Сетка r для ОДУ (от R_e к r_w)
    r_ode_grid = np.logspace(np.log10(r_w), np.log10(R_e), 300)
    r_eval_desc = r_ode_grid[::-1]

    def solve_step(T_prev_func, adiab_source):
        """Решить одно ОДУ.

        T_prev_func(r) — температура предыдущего шага.
        adiab_source — True для 1-го шага (есть φ·dp/dt).
        """
        def rhs(r, T_vec):
            T = T_vec[0]
            T_prev = T_prev_func(r)
            # JT-поток: действует на каждом шаге, знак — охлаждение.
            jt = -mu_JT * (beta / r) * dpdr_dupuit(r)
            src = (phi * adiab_factor * dp_dupuit(r) / dt
                   if adiab_source else 0.0)
            return [(r / beta) * (kappa * (T - T_prev) - src - jt)]

        sol = solve_ivp(rhs, [R_e, r_w], [T0], t_eval=r_eval_desc,
                        rtol=1e-10, atol=1e-12)
        r_out = sol.t[::-1]
        T_out = sol.y[0, ::-1]
        return r_out, T_out

    # Моменты для графика
    times = history.times
    idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
    plot_indices = sorted(set(idx))
    times_to_plot = [times[i] for i in plot_indices]

    # Рекуррентное решение ОДУ: шаг за шагом от 0 до последнего plot_index
    max_step = max(plot_indices)
    T_prev_func = lambda r: T0   # T^0 = T_0

    ode_solutions = {0: (r_ode_grid, np.full_like(r_ode_grid, T0))}

    print("Решение ОДУ для температуры...")
    for n in range(1, max_step + 1):
        adiab = (n == 1)
        r_sol, T_sol = solve_step(T_prev_func, adiab)
        if n in plot_indices:
            ode_solutions[n] = (r_sol, T_sol)
        # Интерполяция для следующего шага
        T_prev_func = interp1d(r_sol, T_sol, kind='linear',
                               fill_value='extrapolate')

    # JT-асимптотика (стационарный предел ОДУ при t → ∞).
    # Давление стационарно с 1-го шага, поэтому берём финальный профиль p.
    # Опорная точка — центр последней ячейки: там ГУ Дирихле держит T_ext.
    p_final = history.states[-1].p
    T_asymp = T0 + mu_JT * (p_final - p_final[-1])

    # ── Наклоны двух линейных участков ──
    # В логарифмической шкале профиль состоит из двух линейных участков
    # с плавным переходом. Оба наклона следуют из того, что давление
    # Дюпюи линейно по ln r с постоянным C = dp/dlnr.
    C_slope = C_dup   # (p0 - p_wf)/ln(R_e/r_w), Па на единицу ln r

    # Ближняя зона: конвекция уже вывела приствольную область на
    # JT-стационар dT/dr = mu_JT·dp/dr.
    slope_near = mu_JT * C_slope

    # Дальняя зона: конвекция ещё не дошла, держится профиль от
    # адиабатического импульса 1-го шага (с тем же множителем adiab_factor).
    slope_far = phi * adiab_factor * C_slope / rho_cp_eff

    # ── График ──
    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, times_to_plot, field="T", ax=ax)

    # Пунктиры ОДУ поверх численных кривых
    for idx_n in plot_indices:
        if idx_n == 0:
            continue
        r_sol, T_sol = ode_solutions[idx_n]
        ax.semilogx(r_sol, T_sol, 'k--', linewidth=1.2)

    # Одна запись в легенду для ОДУ
    ax.semilogx([], [], 'k--', linewidth=1.2, label="ОДУ-аналитика")
    ax.semilogx(grid.r_centers, T_asymp, color='gray', linestyle=':',
                linewidth=1.5,
                label=r"JT-асимптотика: $T_{ext} + \mu_{JT}(p - p_{ext})$")

    # Опорные прямые с наклонами двух участков — короткие отрезки,
    # смещённые вниз от профилей, чтобы наклон читался, а не сливался
    # с кривыми. Ближний участок берём у забоя, дальний — у контура.
    r_c = grid.r_centers
    T_fin = history.states[-1].T
    span = T_fin.max() - T_fin.min()

    # Ближний: отрезок r ∈ [r_w, 1] м, смещён на 12% размаха вниз
    r_left = np.array([r_c[0], 1.0])
    T_left = T_fin[0] - 0.12 * span + slope_near * np.log(r_left / r_c[0])
    ax.semilogx(r_left, T_left, color='tab:green', linestyle='-',
                linewidth=2.2, alpha=0.85,
                label=fr"наклон $\mu_{{JT}} C$ = {slope_near:.3f} К (JT-стационар)")

    # Дальний: отрезок r ∈ [8, R_e], смещён на 25% размаха вниз —
    # иначе упирается в верхний край области рисования
    r_right = np.array([8.0, r_c[-1]])
    T_right = (T_fin[-1] - 0.25 * span
               + slope_far * np.log(r_right / r_c[-1]))
    ax.semilogx(r_right, T_right, color='tab:purple', linestyle='-',
                linewidth=2.2, alpha=0.85,
                label=fr"наклон $\varphi(1{{+}}\rho c_p\mu_{{JT}})C/(\rho c_p)_{{eff}}$"
                      fr" = {slope_far:.3f} К (адиабат. след)")

    ax.legend(fontsize=7, loc="lower right")
    ax.set_title(f"{title}\nПрофили температуры")
    fig.tight_layout()
    fig.savefig(output_dir / "temperature_profiles.png", dpi=110)
    plt.close(fig)

    # Ошибки для каждого рисуемого момента
    r_centers = grid.r_centers
    print("Аналитика T (ОДУ vs численное):")
    for idx_n in plot_indices:
        if idx_n == 0:
            continue
        r_sol, T_sol = ode_solutions[idx_n]
        T_ode_centers = np.interp(r_centers, r_sol, T_sol)
        T_num = history.states[idx_n].T
        err = np.max(np.abs(T_num - T_ode_centers))
        print(f"  t = {times[idx_n]:8.0f} с (шаг {idx_n:3d}): "
              f"max|T_num - T_ode| = {err:.4f} К")

    print(f"Наклоны dT/dlnr: ближний {slope_near:.4f} К (JT-стационар), "
          f"дальний {slope_far:.4f} К (адиабатический след)")

    return float(np.max(np.abs(history.states[-1].T - T_asymp)))


if __name__ == "__main__":
    here = Path(__file__).parent
    TITLE = "02: однофазная фильтрация с JT"

    elapsed, history, grid, config = run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title=TITLE,
    )

    _add_dupuit_curve(history, grid, config, here / "output", TITLE)
    print("График давления перестроен с аналитикой Дюпюи.")

    gap = _add_temperature_analytics(history, grid, config, here / "output", TITLE)
    print(f"  Отставание от JT-асимптотики: {gap:.3f} К "
          f"(релаксация не завершена за {history.times[-1] / 86400:.0f} сут)")

    # Баланс энергии: ΔE = адиабатика + конвекция + JT
    plot_energy_balance(history, grid, config, here / "output")
