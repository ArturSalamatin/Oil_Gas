"""Баланс энергии во времени для примера 02_single_phase_jt.

Отличие от одноимённого скрипта примера 01: добавлен четвёртый компонент —
источник Джоуля-Томсона. В 01 он тождественно нулевой (mu_JT = 0), здесь
это главный член, определяющий стационарную асимптотику температуры.

На каждом шаге n считаем кумулятивные (от t=0 до t_n):
  ΔE(t)       — изменение запаса тепловой энергии в области
  adiab(t)    — кумулятивный адиабатический источник
  conv(t)     — кумулятивная чистая конвекция (контур - забой)
  jt(t)       — кумулятивный источник Джоуля-Томсона
  невязка(t)  — ΔE - (adiab + conv + jt)

Все компоненты воспроизводят ровно те формулы, которые собирает
TridiagEnergySolver.assemble_tridiag: JT входит в правую часть d[j]
как J_jt[j] (уже в Вт, не на м³), адиабатика — как V[j]·Q_ad[j].

Строит 2 графика: (a) все компоненты, (b) относительная невязка.

Две функции:
  compute_balance()      — считает компоненты, возвращает dict с массивами
  plot_energy_balance()  — строит график поверх compute_balance()

Расчётная часть вынесена отдельно, чтобы energy_balance_convergence.py
использовал те же формулы, а не свою копию.

Запуск автономно:
    cd numerical_solver
    .venv\\Scripts\\python examples\\02_single_phase_jt\\energy_balance.py

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


def compute_balance(history, grid, config):
    """Покомпонентный баланс энергии по сохранённой истории.

    Возвращает dict с массивами длины n_steps:
      t, delta_E, cum_adiab, cum_conv, cum_jt, total, residual, rel_residual

    Формулы повторяют то, что собирает TridiagEnergySolver.assemble_tridiag.
    Вынесено отдельной функцией, чтобы plot_energy_balance и
    energy_balance_convergence.py считали баланс одним и тем же кодом.
    """
    from gpn_multiphase_solver.factory import SimulatorFactory

    # Нужны pvt и rock для (ρcp)_eff, конвективных коэффициентов и μ_JT.
    # Получаем через повторную сборку (дёшево — без прогона).
    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim._energy._pvt
    rock = sim._energy._rock

    N = grid.N
    V = grid.volumes
    phi = rock.porosity
    T_ext = config.initial_conditions.T0

    # (ρcp)_eff — в однофазном случае постоянна (Sg ≡ 0, Bo = const),
    # поэтому считается один раз скаляром. Дефект накопления BUG-004 в этом
    # упрощении НЕ возникает — измерено: расхождение со схемой ~2e-6 Дж при
    # невязке ~2e+7 Дж, доля 0.0000. В двухфазных примерах (03, 05) так
    # делать НЕЛЬЗЯ: там (ρcp)_eff дрейфует, и накопление надо считать по
    # приращениям.
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
    cum_jt = np.zeros(n_steps)

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
        mu_JT_cells = pvt.mu_JT_oil(p, state_prev.T)

        # ── Конвекция ──
        # Конвективные коэффициенты Φ на забое и контуре.
        # Знак: Q_o < 0 (поток к скважине) ⇒ Φ < 0 на обеих гранях.
        Phi_well = rho_o_cells[0] * c_p_o_cells[0] * Q_o[0]
        Phi_ext = rho_o_cells[-1] * c_p_o_cells[-1] * Q_o[N]

        # Потоки энтальпии через границы (Дж за шаг).
        # На забое выносится T ближней ячейки, на контуре вносится T_ext.
        conv_well_step = Phi_well * state_prev.T[0] * dt_step
        conv_ext_step = Phi_ext * T_ext * dt_step

        # Чистая конвекция в схеме FVM: -(поток_out - поток_in) = -(Φ_ext·T_ext - Φ_well·T_well)
        net_conv_step = -(conv_ext_step - conv_well_step)

        # ── Джоуль-Томсон ──
        # J_face[f] = μ_JT_up · Φ_o[f] · p_up, вклад в ячейку = J_face[j+1] - J_face[j].
        # Сумма по всем ячейкам телескопируется: Σ_j J_jt[j] = J_face[N] - J_face[0].
        # Поток однонаправленный (Q_o < 0 всюду), upstream каждой грани — правая ячейка,
        # кроме забоя (f=0, upstream = ячейка 0) и контура (f=N, upstream = ячейка N-1).
        J_face_0 = mu_JT_cells[0] * Phi_well * p[0]
        J_face_N = mu_JT_cells[-1] * Phi_ext * p[-1]
        jt_step = (J_face_N - J_face_0) * dt_step

        # ── Адиабатика ──
        # Q_ad = φ·(1 + ρ·cp·μ_JT)·dp/dt (Sg = 0, So = 1), Вт/м³.
        # Интегрируя по объёму и по шагу: φ·Σ_j V_j·(1 + ρcp·μ_JT)_j·Δp_j.
        dp = state_curr.p - state_prev.p
        adiab_step = phi * np.sum(
            V * (1.0 + rho_o_cells * c_p_o_cells * mu_JT_cells) * dp)

        cum_conv[n] = cum_conv[n - 1] + net_conv_step
        cum_adiab[n] = cum_adiab[n - 1] + adiab_step
        cum_jt[n] = cum_jt[n - 1] + jt_step

    total = cum_conv + cum_adiab + cum_jt
    residual = delta_E - total

    # Относительная невязка: нормируем на больший из масштабов, чтобы
    # не делить на ноль на первых шагах, когда ΔE ещё мало.
    scale = np.maximum(np.abs(delta_E), np.abs(total))
    scale = np.where(scale < 1e-10, 1.0, scale)

    return dict(
        t=t_arr,
        delta_E=delta_E,
        cum_adiab=cum_adiab,
        cum_conv=cum_conv,
        cum_jt=cum_jt,
        total=total,
        residual=residual,
        rel_residual=np.abs(residual) / scale,
    )


def plot_energy_balance(history, grid, config, output_dir: Path):
    """Построить график баланса энергии и вернуть финальную относительную невязку."""
    bal = compute_balance(history, grid, config)
    delta_E = bal["delta_E"]
    cum_adiab = bal["cum_adiab"]
    cum_conv = bal["cum_conv"]
    cum_jt = bal["cum_jt"]
    total = bal["total"]
    residual = bal["residual"]
    rel_residual = bal["rel_residual"]

    # ── Перевод в часы ──
    t_hours = bal["t"] / 3600.0

    # ── Графики ──
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 1]})

    # (a) Компоненты баланса
    ax1.plot(t_hours, delta_E, 'k-', linewidth=2, label=r"$\Delta E$ (накопление)")
    ax1.plot(t_hours, cum_adiab, 'b--', linewidth=1.5, label="адиабатика (кумул.)")
    ax1.plot(t_hours, cum_conv, 'r--', linewidth=1.5, label="чистая конвекция (кумул.)")
    ax1.plot(t_hours, cum_jt, 'm--', linewidth=1.5, label="Джоуль–Томсон (кумул.)")
    ax1.plot(t_hours, total, 'g:', linewidth=1.5, label="сумма источников")
    ax1.set_ylabel("Энергия, Дж")
    ax1.legend(fontsize=9)
    ax1.set_title(r"Баланс энергии — пример 02 ($\lambda=0$, $\mu_{JT}\neq 0$, $L=0$)")
    ax1.grid(True, alpha=0.3)
    ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    # (b) Относительная невязка
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
    print(f"  Джоуль-Томсон    = {cum_jt[-1]:+.4e} Дж")
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
