"""Баланс энергии во времени для примера 05_standing_table_rp.

Проверка интегральная: она не зависит ни от вида ОФП, ни от источника PVT,
поэтому код совпадает с примером 03. Смысл её здесь тот же — убедиться,
что схема не теряет и не создаёт энергию при табличной ОФП и при λ = 0.

Отличие от примера 02: расчёт двухфазный, поэтому добавлены два вклада —
скрытая теплота дегазации и газовая фаза во всех остальных членах.
Компоненты (кумулятивные, от t=0 до t_n):

  ΔE(t)     — изменение запаса тепловой энергии в области
  adiab(t)  — адиабатический источник, φ·Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt
  conv(t)   — чистая конвекция через забой и контур (обе фазы)
  jt(t)     — источник Джоуля–Томсона (обе фазы)
  deg(t)    — скрытая теплота дегазации, -L·mdot
  невязка   — ΔE - (adiab + conv + jt + deg)

Формулы повторяют то, что собирает TridiagEnergySolver.assemble_tridiag.
Суммирование по всем ячейкам телескопирует дивергентные члены (JT и
конвекцию) до разности потоков на забое и контуре; недивергентные
(адиабатика, дегазация) суммируются по объёму.

В отличие от 02 здесь (ρcp)_eff НЕ постоянна: она зависит от S_g и от PVT,
поэтому ΔE считается с поячеечными свойствами на каждом шаге.

Две функции:
  compute_balance()     — считает компоненты, возвращает dict
  plot_energy_balance() — строит график поверх compute_balance()

Запуск автономно:
    cd numerical_solver
    .venv\\Scripts\\python examples\\05_standing_table_rp\\energy_balance.py
"""

import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _cell_properties(pvt, rock, p, Sg, Rs, T):
    """(ρcp)_eff и покомпонентные PVT в ячейках — как в tridiag.py (eq. 5)."""
    phi = rock.porosity
    So = 1.0 - Sg
    rho_o = pvt.rho_o(p, Rs)
    rho_g = pvt.rho_g(p)
    cp_o = pvt.c_p_oil(p, T)
    cp_g = pvt.c_p_gas(p, T)
    rho_cp_eff = ((1 - phi) * rock.rho_cp_solid
                  + phi * (So * rho_o * cp_o + Sg * rho_g * cp_g))
    return rho_o, rho_g, cp_o, cp_g, rho_cp_eff


def compute_balance(history, grid, config):
    """Покомпонентный баланс энергии по сохранённой истории.

    Возвращает dict с массивами длины n_steps:
      t, delta_E, cum_adiab, cum_conv, cum_jt, cum_deg,
      total, residual, rel_residual
    """
    from gpn_multiphase_solver.factory import SimulatorFactory

    # pvt и rock нужны для (ρcp)_eff, Φ, μ_JT и L. Пересобираем фабрикой —
    # это дёшево, прогон не повторяется.
    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim._energy._pvt
    rock = sim._energy._rock

    N = grid.N
    V = grid.volumes
    phi = rock.porosity
    T_ext = config.initial_conditions.T0
    rho_g_std = pvt.rho_g_std

    st0 = history.states[0]
    _, _, _, _, rho_cp_0 = _cell_properties(
        pvt, rock, st0.p, st0.Sg, st0.Rs, st0.T)
    E_init = np.sum(rho_cp_0 * V * st0.T)

    n_steps = len(history.times)
    t_arr = np.array(history.times)

    delta_E = np.zeros(n_steps)
    cum_conv = np.zeros(n_steps)
    cum_adiab = np.zeros(n_steps)
    cum_jt = np.zeros(n_steps)
    cum_deg = np.zeros(n_steps)

    for n in range(n_steps):
        st = history.states[n]
        _, _, _, _, rho_cp_n = _cell_properties(
            pvt, rock, st.p, st.Sg, st.Rs, st.T)
        # Запас энергии считается с текущими свойствами: (ρcp)_eff зависит
        # от S_g, и в двухфазной зоне заметно отличается от начального.
        delta_E[n] = np.sum(rho_cp_n * V * st.T) - E_init

        if n == 0:
            continue

        dt_step = t_arr[n] - t_arr[n - 1]
        st_prev = history.states[n - 1]
        hydro = history.hydro_results[n]

        p, Sg, Rs, T_prev = st.p, st.Sg, st.Rs, st_prev.T
        So = 1.0 - Sg
        Q_o, Q_g, G_o = hydro.Q_o, hydro.Q_g, hydro.G_o

        rho_o, rho_g, cp_o, cp_g, _ = _cell_properties(
            pvt, rock, p, Sg, Rs, T_prev)
        mu_JT_o = pvt.mu_JT_oil(p, T_prev)
        mu_JT_g = pvt.mu_JT_gas(p, T_prev)
        L = pvt.L_degas(p, T_prev)

        # ── Конвекция (обе фазы) ──
        # Φ_α = ρ_α cp_α Q_α (eq. 23). Знак: Q < 0 (поток к скважине) ⇒ Φ < 0.
        # Upstream забоя — ячейка 0, upstream контура — ячейка N-1
        # (для Φ; вносимая температура на контуре — T_ext, см. ниже).
        Phi_o_well = rho_o[0] * cp_o[0] * Q_o[0]
        Phi_g_well = rho_g[0] * cp_g[0] * Q_g[0]
        Phi_o_ext = rho_o[-1] * cp_o[-1] * Q_o[N]
        Phi_g_ext = rho_g[-1] * cp_g[-1] * Q_g[N]

        # На забое выносится T ближней ячейки, на контуре вносится T_ext.
        conv_well = (Phi_o_well + Phi_g_well) * T_prev[0] * dt_step
        conv_ext = (Phi_o_ext + Phi_g_ext) * T_ext * dt_step
        # Чистая конвекция в FVM: -(поток_out - поток_in)
        net_conv = -(conv_ext - conv_well)

        # ── Джоуль–Томсон (обе фазы) ──
        # J_face = Σ_α μ_JT,α Φ_α p_up; сумма по ячейкам телескопируется
        # до J_face[N] - J_face[0].
        J_well = (mu_JT_o[0] * Phi_o_well + mu_JT_g[0] * Phi_g_well) * p[0]
        J_ext = (mu_JT_o[-1] * Phi_o_ext + mu_JT_g[-1] * Phi_g_ext) * p[-1]
        jt_step = (J_ext - J_well) * dt_step

        # ── Адиабатика (обе фазы) ──
        # Q_ad = φ Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt, Вт/м³ (eq. 29).
        dp = st.p - st_prev.p
        adiab_step = phi * np.sum(
            V * (So * (1.0 + rho_o * cp_o * mu_JT_o)
                 + Sg * (1.0 + rho_g * cp_g * mu_JT_g)) * dp)

        # ── Скрытая теплота дегазации ──
        # Q_deg = -L·mdot, mdot = временная + конвективная части (eq. 31).
        # Временная: газ, вышедший из раствора в самой ячейке за шаг.
        mdot_time = (-rho_g_std * phi * So / pvt.Bo(p, Rs)
                     * (Rs - st_prev.Rs) / dt_step)
        # Конвективная: дивергенция потока растворённого газа <G^o·Rs>.
        R_conv = np.zeros(N + 1)
        for f in range(1, N):
            Go_p, Go_m = max(G_o[f], 0.0), min(G_o[f], 0.0)
            R_conv[f] = Go_p * Rs[f - 1] + Go_m * Rs[f]
        R_conv[0] = G_o[0] * Rs[0]
        R_conv[N] = (G_o[N] * Rs[N - 1] if G_o[N] >= 0
                     else G_o[N] * st_prev.Rs[-1])
        mdot_conv = -rho_g_std * (R_conv[1:] - R_conv[:-1]) / V
        mdot = mdot_time + mdot_conv
        deg_step = np.sum(-L * mdot * V) * dt_step

        cum_conv[n] = cum_conv[n - 1] + net_conv
        cum_adiab[n] = cum_adiab[n - 1] + adiab_step
        cum_jt[n] = cum_jt[n - 1] + jt_step
        cum_deg[n] = cum_deg[n - 1] + deg_step

    total = cum_conv + cum_adiab + cum_jt + cum_deg
    residual = delta_E - total

    # Нормируем на больший из масштабов: на первых шагах ΔE ещё мало,
    # и деление на него дало бы ложный всплеск невязки.
    scale = np.maximum(np.abs(delta_E), np.abs(total))
    scale = np.where(scale < 1e-10, 1.0, scale)

    return dict(
        t=t_arr, delta_E=delta_E,
        cum_adiab=cum_adiab, cum_conv=cum_conv,
        cum_jt=cum_jt, cum_deg=cum_deg,
        total=total, residual=residual,
        rel_residual=np.abs(residual) / scale,
    )


def plot_energy_balance(history, grid, config, output_dir: Path):
    """Построить график баланса энергии и вернуть финальную отн. невязку."""
    bal = compute_balance(history, grid, config)
    t_hours = bal["t"] / 3600.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(t_hours, bal["delta_E"], 'k-', linewidth=2,
             label=r"$\Delta E$ (накопление)")
    ax1.plot(t_hours, bal["cum_adiab"], 'b--', linewidth=1.5,
             label="адиабатика (кумул.)")
    ax1.plot(t_hours, bal["cum_conv"], 'r--', linewidth=1.5,
             label="чистая конвекция (кумул.)")
    ax1.plot(t_hours, bal["cum_jt"], 'm--', linewidth=1.5,
             label="Джоуль–Томсон (кумул.)")
    ax1.plot(t_hours, bal["cum_deg"], 'c--', linewidth=1.5,
             label="скрытая теплота (кумул.)")
    ax1.plot(t_hours, bal["total"], 'g:', linewidth=1.5, label="сумма источников")
    ax1.set_ylabel("Энергия, Дж")
    ax1.legend(fontsize=9)
    ax1.set_title(r"Баланс энергии — пример 05 (табличная ОФП, $\lambda = 0$)")
    ax1.grid(True, alpha=0.3)
    ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    ax2.plot(t_hours, bal["rel_residual"], 'k-', linewidth=1)
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

    final_rel = abs(bal["residual"][-1] / (abs(bal["delta_E"][-1]) + 1e-30))
    print(f"  ΔE финал          = {bal['delta_E'][-1]:+.4e} Дж")
    print(f"  Адиабатика финал  = {bal['cum_adiab'][-1]:+.4e} Дж")
    print(f"  Конвекция финал   = {bal['cum_conv'][-1]:+.4e} Дж")
    print(f"  Джоуль-Томсон     = {bal['cum_jt'][-1]:+.4e} Дж")
    print(f"  Скрытая теплота   = {bal['cum_deg'][-1]:+.4e} Дж")
    print(f"  Невязка финал     = {bal['residual'][-1]:+.4e} Дж  ({final_rel:.2e})")
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
    history = sim.run(initial_state)

    plot_energy_balance(history, sim._grid, config, HERE / "output")
