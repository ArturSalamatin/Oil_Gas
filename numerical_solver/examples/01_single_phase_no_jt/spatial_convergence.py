"""Сходимость по числу ячеек N для примера 01.

Прогоняет серию сеток, для каждой решает рекуррентное ОДУ-аналитику
и считает max|T_num - T_ode| на финальном шаге.
Конвективный член дискретизирован против потока (схема 1-го порядка),
поэтому при O(h) увеличение N в 4 раза уменьшает ошибку в ~4 раза.

Сетки здесь НЕ совпадают с рабочей сеткой примера: config.json фиксирует
N = 150, на ней ошибка 0.0013 К и кривые на temperature_profiles.png
сливаются с эталоном. Ряд 50/200/800 кратен четырём: так отношения ошибок
читаются напрямую как проверка порядка схемы.

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
from gpn_multiphase_solver.units import S_TO_DAY


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


# ── Прогоны на последовательности сеток ──
config_base = load_config(HERE / "config.json")

# Каждая следующая сетка в 4 раза подробнее предыдущей
Ns = [50, 200, 800]
results = {}

for N_val in Ns:
    cfg = deepcopy(config_base)
    cfg.grid.N = N_val
    print(f"── N = {N_val} ──")
    history, grid, errors = run_and_compute_errors(cfg)
    results[N_val] = errors
    print(f"   max ошибка T (все шаги): {errors.max():.6f} К")
    print(f"   ошибка T (финал):        {errors[-1]:.6f} К")

# ── Отношения ошибок на соседних сетках ──
# Схема против потока → 1-й порядок: ошибка падает линейно по h, то есть в N раз.
# Наблюдаемый порядок p = log(E_coarse/E_fine) / log(N_fine/N_coarse).
print()
for N_coarse, N_fine in zip(Ns[:-1], Ns[1:]):
    ratio_max = results[N_coarse].max() / results[N_fine].max()
    ratio_fin = results[N_coarse][-1] / results[N_fine][-1]
    order_max = np.log(ratio_max) / np.log(N_fine / N_coarse)
    print(f"N={N_coarse} → N={N_fine} (ожидаем ~{N_fine / N_coarse:.0f}x при O(h)):")
    print(f"   отношение max ошибок: {ratio_max:.1f}x   (порядок p = {order_max:.2f})")
    print(f"   отношение fin ошибок: {ratio_fin:.1f}x")

# ── График ──
fig, ax = plt.subplots(figsize=(9, 5))
colors = ['b', 'r', 'g', 'm']
for N_val, color in zip(Ns, colors):
    errors = results[N_val]
    # Время по оси — в сутках (FEAT-022)
    t_days = np.arange(1, len(errors) + 1) * config_base.time.dt_integration * S_TO_DAY
    ax.plot(t_days, errors, color=color, linestyle='-', linewidth=1.5,
            label=f"N = {N_val} (max {errors.max():.4f} К)")
ax.set_xlabel("Время, сут")
ax.set_ylabel("max|T_num − T_ode|, К")
# Ошибки на разных сетках отличаются на порядки — лог-шкала делает все кривые читаемыми
ax.set_yscale('log')
ax.set_title("Сходимость температуры по числу ячеек N")
ax.legend()
ax.grid(True, alpha=0.3)

fig.tight_layout()
out_path = HERE / "output" / "spatial_convergence.png"
out_path.parent.mkdir(parents=True, exist_ok=True)
# Стираем результат прошлого прогона. Остальные файлы в output/ пишет
# main.py примера, и трогать их нельзя: этот скрипт их не восстановит.
out_path.unlink(missing_ok=True)
fig.savefig(out_path, dpi=130)
plt.close(fig)
print(f"\nСохранён: {out_path}")
