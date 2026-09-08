"""Проверка: оба JT-члена в ОДУ-аналитике необходимы.

ОДУ в main.py::_add_temperature_analytics содержит два вклада Джоуля-Томсона:
  1. поток      -mu_JT * (beta/r) * dp/dr       — действует на каждом шаге
  2. множитель  (1 + rho*cp*mu_JT) при адиабатике — только на 1-м шаге

Скрипт решает ОДУ в четырёх вариантах (оба члена / без каждого / без обоих)
и сравнивает с численным решением. Если член нужен — без него ошибка растёт.

Диагностический скрипт, из main.py не вызывается.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\02_single_phase_jt\\check_jt_terms.py
"""

import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

warnings.filterwarnings("ignore")

from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory

# Сравниваем на 24-м шаге, а не на 72-м: ошибка уже вышла на полку
# (0.0042 К против 0.0037 К в финале), а считается втрое быстрее.
N_STEPS = 24


def main():
    config = load_config(HERE / "config.json")
    sim, initial = SimulatorFactory.from_config(config)
    history = sim.run(initial)
    grid = sim._grid

    pvt = sim._energy._pvt
    rock = sim._energy._rock

    r_w = config.geometry.r_well
    R_e = config.geometry.R_ext
    h = config.geometry.h
    p0 = config.initial_conditions.p0
    T0 = config.initial_conditions.T0
    p_wf = config.time.history[0].p_wf
    phi = config.rock.porosity
    dt = config.time.dt_integration
    mu_JT = config.thermal.mu_JT_oil

    rho_o = pvt.rho_o(np.array([p0]), np.array([0.0]))[0]
    c_p_o = pvt.c_p_oil(np.array([p0]), np.array([T0]))[0]
    rho_cp_eff = (1 - phi) * rock.rho_cp_solid + phi * rho_o * c_p_o

    Q_o = history.hydro_results[1].Q_o[0]
    beta = rho_o * c_p_o * abs(Q_o) / (2 * np.pi * h)
    kappa = rho_cp_eff / dt

    C_dup = (p0 - p_wf) / np.log(R_e / r_w)
    r_grid = np.logspace(np.log10(r_w), np.log10(R_e), 300)
    r_desc = r_grid[::-1]

    T_num = history.states[N_STEPS].T

    def solve(use_flux: bool, use_factor: bool) -> float:
        """Решить N_STEPS шагов ОДУ, вернуть max|T_num - T_ode| в центрах ячеек."""
        adiab_factor = 1.0 + rho_o * c_p_o * mu_JT if use_factor else 1.0
        T_prev = lambda r: T0

        for n in range(1, N_STEPS + 1):
            def rhs(r, T_vec, T_prev=T_prev, n=n):
                # JT-поток: dp/dr = C/r для профиля Дюпюи
                jt = -mu_JT * (beta / r) * (C_dup / r) if use_flux else 0.0
                src = (phi * adiab_factor * (-(p0 - p_wf) + C_dup * np.log(r / r_w)) / dt
                       if n == 1 else 0.0)
                return [(r / beta) * (kappa * (T_vec[0] - T_prev(r)) - src - jt)]

            sol = solve_ivp(rhs, [R_e, r_w], [T0], t_eval=r_desc,
                            rtol=1e-10, atol=1e-12)
            r_sol, T_sol = sol.t[::-1], sol.y[0, ::-1]
            T_prev = interp1d(r_sol, T_sol, kind="linear",
                              fill_value="extrapolate")

        return float(np.max(np.abs(T_num - np.interp(grid.r_centers, r_sol, T_sol))))

    print(f"Сравнение на шаге {N_STEPS} (t = {history.times[N_STEPS]:.0f} с)\n")
    variants = [
        ("оба члена (как в main.py)", True, True),
        ("без JT-потока", False, True),
        ("без множителя адиабатики", True, False),
        ("без обоих (формула из 01)", False, False),
    ]
    for label, use_flux, use_factor in variants:
        err = solve(use_flux, use_factor)
        print(f"  {label:30s}  max|T_num - T_ode| = {err:.4f} К")


if __name__ == "__main__":
    main()
