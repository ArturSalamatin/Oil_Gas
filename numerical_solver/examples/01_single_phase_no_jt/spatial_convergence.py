"""Сходимость по числу ячеек N для примера 01.

Прогоняет N=50 и N=200, для каждого решает рекуррентное ОДУ-аналитику
и считает max|T_num - T_ode| на финальном шаге.
При O(h^2) увеличение N в 4 раза должно уменьшить ошибку в ~16 раз.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\01_single_phase_no_jt\\spatial_convergence.py
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

from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory


def run_and_compute_errors(config, n_ode_points=500):
    """Прогон + рекуррентное ОДУ → ошибка T на каждом шаге."""
    sim, initial_state = SimulatorFactory.from_config(config)
    grid = sim._grid
    pvt = sim._energy._pvt
    rock = sim._energy._rock
    history = sim.run(initial_state)

    N = grid.N
    r_w = config.geometry.r_well
    R_e = config.geometry.R_ext
    h = config.geometry.h
    p0 = config.initial_conditions.p0
    p_wf = config.time.history[0].p_wf
    T0 = config.initial_conditions.T0
    phi = config.rock.porosity
    dt = config.time.dt_integration

    p_arr = np.array([p0])
    rho_o = pvt.rho_o(p_arr, np.array([0.0]))[0]
    c_p_o = pvt.c_p_oil(p_arr, np.array([T0]))[0]
    rho_cp_eff = (1 - phi) * rock.rho_cp_solid + phi * rho_o * c_p_o

    Q_o = history.hydro_results[1].Q_o[0]
    beta = rho_o * c_p_o * abs(Q_o) / (2 * np.pi * h)
    kappa = rho_cp_eff / dt

    C_dup = (p0 - p_wf) / np.log(R_e / r_w)

    def dp_dupuit(r):
        return -(p0 - p_wf) + C_dup * np.log(r / r_w)

    r_ode_grid = np.logspace(np.log10(r_w), np.log10(R_e), n_ode_points)
    r_eval_desc = r_ode_grid[::-1]

    def solve_step(T_prev_func, adiab):
        def rhs(r, T_vec):
            T_prev = T_prev_func(r)
            src = phi * dp_dupuit(r) / dt if adiab else 0.0
            return [(r / beta) * (kappa * (T_vec[0] - T_prev) - src)]
        sol = solve_ivp(rhs, [R_e, r_w], [T0], t_eval=r_eval_desc,
                        rtol=1e-12, atol=1e-14)
        r_out = sol.t[::-1]
        T_out = sol.y[0, ::-1]
        return r_out, T_out

    # Рекуррентное решение ОДУ для всех шагов
    n_steps = len(history.times)
    T_prev_func = lambda r: T0
    r_centers = grid.r_centers

    errors = []
    for n in range(1, n_steps):
        adiab = (n == 1)
        r_sol, T_sol = solve_step(T_prev_func, adiab)
        T_prev_func = interp1d(r_sol, T_sol, kind='linear',
                               fill_value='extrapolate')
        T_ode_centers = np.interp(r_centers, r_sol, T_sol)
        T_num = history.states[n].T
        errors.append(np.max(np.abs(T_num - T_ode_centers)))

    return history, grid, np.array(errors)


# ── Два прогона ──
config_base = load_config(HERE / "config.json")

Ns = [50, 200]
results = {}

for N_val in Ns:
    cfg = deepcopy(config_base)
    cfg.grid.N = N_val
    print(f"── N = {N_val} ──")
    history, grid, errors = run_and_compute_errors(cfg)
    results[N_val] = errors
    print(f"   max ошибка T (все шаги): {errors.max():.6f} К")
    print(f"   ошибка T (финал):        {errors[-1]:.6f} К")

# ── Отношение ──
ratio_max = results[Ns[0]].max() / results[Ns[1]].max()
ratio_fin = results[Ns[0]][-1] / results[Ns[1]][-1]
print(f"\nОтношение max ошибок (N={Ns[0]}/N={Ns[1]}): {ratio_max:.1f}x")
print(f"Отношение fin ошибок (N={Ns[0]}/N={Ns[1]}): {ratio_fin:.1f}x")
print(f"Ожидаем ~{(Ns[1]/Ns[0])**2:.0f}x при O(h^2)")

# ── График ──
fig, ax = plt.subplots(figsize=(9, 5))
t_hours_50 = np.arange(1, len(results[Ns[0]]) + 1) * config_base.time.dt_integration / 3600
t_hours_200 = np.arange(1, len(results[Ns[1]]) + 1) * config_base.time.dt_integration / 3600
ax.plot(t_hours_50, results[Ns[0]], 'b-', linewidth=1.5,
        label=f"N = {Ns[0]} (max {results[Ns[0]].max():.4f} К)")
ax.plot(t_hours_200, results[Ns[1]], 'r-', linewidth=1.5,
        label=f"N = {Ns[1]} (max {results[Ns[1]].max():.4f} К)")
ax.set_xlabel("Время, ч")
ax.set_ylabel("max|T_num − T_ode|, К")
ax.set_title("Сходимость температуры по числу ячеек N")
ax.legend()
ax.grid(True, alpha=0.3)

fig.tight_layout()
out_path = HERE / "output" / "spatial_convergence.png"
out_path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_path, dpi=130)
plt.close(fig)
print(f"\nСохранён: {out_path}")
