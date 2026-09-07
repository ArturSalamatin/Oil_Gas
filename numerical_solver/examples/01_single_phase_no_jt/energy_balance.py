"""Баланс энергии во времени для примера 01_single_phase_no_jt.

На каждом шаге n считаем кумулятивные (от t=0 до t_n):
  ΔE(t)       — изменение запаса тепловой энергии в области
  adiab(t)    — кумулятивный адиабатический источник
  conv(t)     — кумулятивная чистая конвекция (контур - забой)
  невязка(t)  — ΔE − (adiab + conv)

Строит 2 графика: (a) все компоненты, (b) относительная невязка.

Запуск автономно:
    cd numerical_solver
    .venv\\Scripts\\python examples\\01_single_phase_no_jt\\energy_balance.py

Или из main.py::

    from energy_balance import plot_energy_balance
    plot_energy_balance(history, grid, config, output_dir)
"""

import sys
from pathlib import Path
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_energy_balance(history, grid, config, output_dir: Path):
    """Построить график баланса энергии и вернуть финальную относительную невязку."""
    from gpn_multiphase_solver.factory import SimulatorFactory

    # Нужны pvt и rock для вычисления (ρcp)_eff и конвективных коэффициентов.
    # Получаем через повторную сборку (дёшево — без прогона).
    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim._energy._pvt
    rock = sim._energy._rock

    N = grid.N
    V = grid.volumes
    phi = rock.porosity
    T_ext = config.initial_conditions.T0

    # (ρcp)_eff — в однофазном случае постоянна
    p0_arr = np.array([config.initial_conditions.p0])
    T0_arr = np.array([T_ext])
    Rs0_arr = np.array([0.0])
    c_p_o = pvt.c_p_oil(p0_arr, T0_arr)[0]
    rho_o = pvt.rho_o(p0_arr, Rs0_arr)[0]
    rho_cp_eff = (1 - phi) * rock.rho_cp_solid + phi * rho_o * c_p_o

    T_init = history.states[0].T.copy()

    n_steps = len(history.times)
    t_arr = np.array(history.times)

    delta_E = np.zeros(n_steps)
    cum_conv = np.zeros(n_steps)
    cum_adiab = np.zeros(n_steps)

    for n in range(n_steps):
        T_n = history.states[n].T
        delta_E[n] = np.sum(rho_cp_eff * V * (T_n - T_init))

        if n == 0:
            continue

        dt_step = t_arr[n] - t_arr[n - 1]
        state_prev = history.states[n - 1]
        state_curr = history.states[n]
        hydro = history.hydro_results[n]

        Q_o = hydro.Q_o
        p = state_curr.p
        Rs = state_curr.Rs
        rho_o_cells = pvt.rho_o(p, Rs)
        c_p_o_cells = pvt.c_p_oil(p, state_prev.T)

        # Конвективные коэффициенты Φ на забое и контуре
        Phi_well = rho_o_cells[0] * c_p_o_cells[0] * Q_o[0]
        Phi_ext = rho_o_cells[-1] * c_p_o_cells[-1] * Q_o[N]

        # Потоки энтальпии (Дж за шаг)
        conv_well_step = Phi_well * state_prev.T[0] * dt_step
        conv_ext_step = Phi_ext * T_ext * dt_step

        # Чистая конвекция: -(Φ_ext·T_ext - Φ_well·T_well)
        net_conv_step = -(conv_ext_step - conv_well_step)

        # Адиабатика: φ · Σ_j V_j · (p^n - p^{n-1})
        dp = state_curr.p - state_prev.p
        adiab_step = phi * np.sum(V * dp)

        cum_conv[n] = cum_conv[n - 1] + net_conv_step
        cum_adiab[n] = cum_adiab[n - 1] + adiab_step

    residual = delta_E - (cum_conv + cum_adiab)

    # ── Перевод в часы ──
    t_hours = t_arr / 3600.0

    # ── Графики ──
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 1]})

    # (a) Компоненты баланса
    ax1.plot(t_hours, delta_E, 'k-', linewidth=2, label=r"$\Delta E$ (накопление)")
    ax1.plot(t_hours, cum_adiab, 'b--', linewidth=1.5, label="адиабатика (кумул.)")
    ax1.plot(t_hours, cum_conv, 'r--', linewidth=1.5, label="чистая конвекция (кумул.)")
    ax1.plot(t_hours, cum_conv + cum_adiab, 'g:', linewidth=1.5,
             label="адиабатика + конвекция")
    ax1.set_ylabel("Энергия, Дж")
    ax1.legend(fontsize=9)
    ax1.set_title("Баланс энергии — пример 01 (λ=0, μ_JT=0, L=0)")
    ax1.grid(True, alpha=0.3)
    ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    # (b) Относительная невязка
    scale = np.maximum(np.abs(delta_E), np.abs(cum_conv + cum_adiab))
    scale = np.where(scale < 1e-10, 1.0, scale)
    rel_residual = np.abs(residual) / scale

    ax2.plot(t_hours, rel_residual, 'k-', linewidth=1)
    ax2.set_xlabel("Время, ч")
    ax2.set_ylabel(r"|невязка| / |$\Delta E$|")
    ax2.set_title("Относительная невязка баланса")
    ax2.grid(True, alpha=0.3)
    ax2.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "energy_balance.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"Сохранён: {out_path}")

    # ── Сводка ──
    final_rel = abs(residual[-1] / (abs(delta_E[-1]) + 1e-30))
    print(f"  ΔE финал         = {delta_E[-1]:+.4e} Дж")
    print(f"  Адиабатика финал = {cum_adiab[-1]:+.4e} Дж")
    print(f"  Конвекция финал  = {cum_conv[-1]:+.4e} Дж")
    print(f"  Невязка финал    = {residual[-1]:+.4e} Дж  ({final_rel:.2e})")
    return final_rel


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
    grid = sim._grid
    history = sim.run(initial_state)

    plot_energy_balance(history, grid, config, HERE / "output")
