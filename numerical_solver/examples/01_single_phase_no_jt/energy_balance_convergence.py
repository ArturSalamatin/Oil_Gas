"""Сходимость невязки баланса энергии при уменьшении шага по времени.

Два прогона примера 01: dt=3600 с и dt=360 с.
График: относительная невязка для обоих на одних осях.
Ожидаемый порядок сходимости: O(Δt) — ошибка расщепления (splitting).

Запуск:
    cd numerical_solver
    .venv\Scripts\python examples\01_single_phase_no_jt\energy_balance_convergence.py
"""

import sys
from pathlib import Path
from copy import deepcopy
import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT / "examples"))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory


def compute_balance(config):
    """Прогон + баланс энергии. Возвращает (t_hours, rel_residual, max_rel, final_rel)."""
    sim, initial_state = SimulatorFactory.from_config(config)
    grid = sim._grid
    pvt = sim._energy._pvt
    rock = sim._energy._rock

    history = sim.run(initial_state)

    N = grid.N
    V = grid.volumes
    phi = rock.porosity
    T_ext = config.initial_conditions.T0

    p0_arr = np.array([config.initial_conditions.p0])
    T0_arr = np.array([T_ext])
    Rs0_arr = np.array([0.0])
    c_p_o = pvt.c_p_oil(p0_arr, T0_arr)[0]
    rho_o_val = pvt.rho_o(p0_arr, Rs0_arr)[0]
    rho_cp_eff = (1 - phi) * rock.rho_cp_solid + phi * rho_o_val * c_p_o

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

        Phi_well = rho_o_cells[0] * c_p_o_cells[0] * Q_o[0]
        Phi_ext = rho_o_cells[-1] * c_p_o_cells[-1] * Q_o[N]

        conv_well_step = Phi_well * state_prev.T[0] * dt_step
        conv_ext_step = Phi_ext * T_ext * dt_step
        net_conv_step = -(conv_ext_step - conv_well_step)

        dp = state_curr.p - state_prev.p
        adiab_step = phi * np.sum(V * dp)

        cum_conv[n] = cum_conv[n - 1] + net_conv_step
        cum_adiab[n] = cum_adiab[n - 1] + adiab_step

    residual = delta_E - (cum_conv + cum_adiab)
    scale = np.maximum(np.abs(delta_E), np.abs(cum_conv + cum_adiab))
    scale = np.where(scale < 1e-10, 1.0, scale)
    rel_residual = np.abs(residual) / scale

    t_hours = t_arr / 3600.0
    max_rel = np.max(rel_residual[1:]) if n_steps > 1 else 0.0
    final_rel = rel_residual[-1]

    return t_hours, rel_residual, max_rel, final_rel


# ── Два прогона ──
config_base = load_config(HERE / "config.json")

config_1 = deepcopy(config_base)
config_1.time.dt_integration = 3600
config_1.output.save_every = 1
print("── Прогон 1: dt = 3600 с ──")
t1, r1, max1, fin1 = compute_balance(config_1)
print(f"   max rel = {max1:.2e}, final rel = {fin1:.2e}")

config_2 = deepcopy(config_base)
config_2.time.dt_integration = 360
config_2.output.save_every = 1
print("── Прогон 2: dt = 360 с ──")
t2, r2, max2, fin2 = compute_balance(config_2)
print(f"   max rel = {max2:.2e}, final rel = {fin2:.2e}")

# ── График ──
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(t1, r1, 'b-', linewidth=1.5, label=f"Δt = 3600 с (max {max1:.1e})")
ax.plot(t2, r2, 'r-', linewidth=1.5, label=f"Δt = 360 с  (max {max2:.1e})")
ax.set_xlabel("Время, ч")
ax.set_ylabel(r"|невязка| / |$\Delta E$|")
ax.set_title("Сходимость невязки баланса энергии по Δt")
ax.legend()
ax.grid(True, alpha=0.3)

fig.tight_layout()
output_dir = HERE / "output"
output_dir.mkdir(parents=True, exist_ok=True)
out_path = output_dir / "energy_balance_convergence.png"
fig.savefig(out_path, dpi=130)
plt.close(fig)

print(f"\nСохранён: {out_path}")
print(f"\nОтношение max невязок: {max1 / max2:.1f}x  (ожидаем ~10 при O(Δt))")
print(f"Отношение fin невязок: {fin1 / fin2:.1f}x")
