"""Сценарий 01: однофазная фильтрация несжимаемой нефти без эффекта Джоуля-Томсона.

После расчёта на график давления наносится аналитическое решение Дюпюи
(стационарный радиальный приток несжимаемой жидкости):
    p(r) = p_wf + (p_0 - p_wf) / ln(R_e/r_w) · ln(r/r_w)
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from example_runner import run_example  # noqa: E402
from gpn_multiphase_solver.io.figures import save_figure, export_emf  # noqa: E402
from gpn_multiphase_solver.io.output import plot_profiles  # noqa: E402

# Папка примера — в sys.path для импорта соседних модулей.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _add_dupuit_curve(history, grid, config, output_dir: Path, title: str):
    """Перестроить pressure_profiles.png, добавив аналитику Дюпюи пунктиром."""
    r_w = config.geometry.r_well
    R_e = config.geometry.R_ext
    p0 = config.initial_conditions.p0
    p_wf = config.time.history[0].p_wf

    # Формула Дюпюи: p(r) = p_wf + Δp / ln(R_e/r_w) · ln(r/r_w)
    r_an = np.logspace(np.log10(r_w), np.log10(R_e), 200)
    p_an = p_wf + (p0 - p_wf) / np.log(R_e / r_w) * np.log(r_an / r_w)

    # Перестроить график: численное решение + аналитика
    times = history.times
    idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
    times_to_plot = [times[i] for i in sorted(set(idx))]

    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, times_to_plot, field="p", ax=ax)

    ax.semilogx(r_an, p_an, 'k--', linewidth=1.5, label="Дюпюи (аналит.)")
    ax.legend()
    ax.set_title(f"{title}\nПрофили давления")
    fig.tight_layout()
    save_figure(fig, output_dir / "pressure_profiles.png", dpi=110)
    plt.close(fig)


def _add_temperature_analytics(history, grid, config, output_dir: Path,
                               title: str):
    """Перестроить temperature_profiles.png с аналитикой ОДУ (пунктиром).

    Для каждого рисуемого момента t_n решается ОДУ — непрерывный аналог
    неявной FVM-схемы (λ=0):

    Шаг 1 (адиабатика + конвекция):
        (ρcp)_eff · (T^1 - T_0)/Δt = β/r · dT^1/dr + φ · Δp(r)/Δt

    Шаги n ≥ 2 (только конвекция, dp/dt = 0):
        (ρcp)_eff · (T^n - T^{n-1})/Δt = β/r · dT^n/dr

    ГУ: T^n(R_e) = T_0.  β = ρ_o·cp_o·|Q_o|/(2πh).
    Каждое ОДУ решается от R_e к r_w через solve_ivp, T^{n-1}(r)
    берётся интерполяцией предыдущего решения.
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

    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim.pvt
    rock = config.rock
    p_arr = np.array([p0])
    Rs_arr = np.array([0.0])
    T_arr = np.array([T0])
    rho_o = pvt.rho_o(p_arr, Rs_arr)[0]
    c_p_o = pvt.c_p_oil(p_arr, T_arr)[0]
    rho_cp_eff = (1 - phi) * rock.rho_cp_solid + phi * rho_o * c_p_o

    Q_o = history.hydro_results[1].Q_o[0]
    beta = rho_o * c_p_o * abs(Q_o) / (2 * np.pi * h)
    kappa = rho_cp_eff / dt  # Вт/м³К — коэффициент накопления

    C_dup = (p0 - p_wf) / np.log(R_e / r_w)

    def dp_dupuit(r):
        return -(p0 - p_wf) + C_dup * np.log(r / r_w)

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
            src = phi * dp_dupuit(r) / dt if adiab_source else 0.0
            return [(r / beta) * (kappa * (T - T_prev) - src)]

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
    # T^0 = T_0
    T_prev_func = lambda r: T0

    # Хранилище решений для рисуемых моментов: {step_index: (r, T)}
    ode_solutions = {}
    ode_solutions[0] = (r_ode_grid, np.full_like(r_ode_grid, T0))

    print("Решение ОДУ для температуры...")
    for n in range(1, max_step + 1):
        adiab = (n == 1)
        r_sol, T_sol = solve_step(T_prev_func, adiab)
        if n in plot_indices:
            ode_solutions[n] = (r_sol, T_sol)
        # Интерполяция для следующего шага
        T_prev_func = interp1d(r_sol, T_sol, kind='linear',
                               fill_value='extrapolate')

    # ── График ──
    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, times_to_plot, field="T", ax=ax)

    # Пунктиры ОДУ поверх численных кривых
    for idx_n in plot_indices:
        if idx_n == 0:
            continue
        r_sol, T_sol = ode_solutions[idx_n]
        t_val = times[idx_n]
        ax.semilogx(r_sol, T_sol, 'k--', linewidth=1.2)

    # Одна запись в легенду для ОДУ
    ax.semilogx([], [], 'k--', linewidth=1.2, label="ОДУ-аналитика")
    ax.axhline(T0, color='gray', linestyle=':', linewidth=1,
               label=f"стационар T = {T0} К")
    ax.legend(fontsize=8)
    ax.set_title(f"{title}\nПрофили температуры")
    fig.tight_layout()
    save_figure(fig, output_dir / "temperature_profiles.png", dpi=110)
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


if __name__ == "__main__":
    here = Path(__file__).parent
    elapsed, history, grid, config = run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="01: однофазная несжимаемая фильтрация без JT",
    )

    _add_dupuit_curve(
        history, grid, config,
        output_dir=here / "output",
        title="01: однофазная несжимаемая фильтрация без JT",
    )
    print("График давления перестроен с аналитикой Дюпюи.")

    _add_temperature_analytics(
        history, grid, config,
        output_dir=here / "output",
        title="01: однофазная несжимаемая фильтрация без JT",
    )

    # Баланс энергии считает run_example — общей проверкой для всех
    # примеров (FEAT-016).

    # Перестроенные выше рисунки — вторым пакетом: первый конвертировал
    # run_example (FEAT-026).
    export_emf(here / "output")
