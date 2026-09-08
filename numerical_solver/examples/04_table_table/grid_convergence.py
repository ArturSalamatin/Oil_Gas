"""Порядок сходимости примера 04 по сетке.

ЗАЧЕМ. Аналитика GOR-замыкания даёт дебит q_o = 5.8498e-03 м³ст/с, расчёт
при N = 50 — 5.8760e-03, расхождение 0.45 %. Само по себе оно ничего не
доказывает: это может быть как ошибка аппроксимации (тогда она убывает
с измельчением сетки), так и систематическое смещение — ошибка в выводе
замыкания или в схеме (тогда она осталась бы при любом N).

РЕЗУЛЬТАТ. Ошибка убывает ровно вдвое при удвоении N — первый порядок,
чего и следует ожидать от схемы против потока:

    N     q_o, м³ст/с    отн. ошибка   отношение   макс|dp|, кПа
    25    5.901165e-03     0.8782 %                    63.9
    50    5.875953e-03     0.4472 %      1.96          27.9
   100    5.863006e-03     0.2259 %      1.98          13.1

Отношение 1.96 и 1.98 против теоретических 2.00. Ошибка профиля давления
убывает так же (63.9 -> 27.9 -> 13.1 кПа), то есть обе величины сходятся
согласованно. Систематического смещения нет: аналитика верна, а 0.45 %
при N = 50 — цена дискретизации, а не дефект.

ГДЕ СОСРЕДОТОЧЕНА ОШИБКА. На фронте разгазирования p = pb: подынтегральная
функция kro/(mu_o*Bo) там негладкая (ниже pb включается разгазирование,
Rs начинает падать), а схема размазывает излом по ячейке. Отсюда же
расхождение в оценке r_b на одну ячейку.

ОГРАНИЧЕНИЕ. При N >= 200 расчёт не сходится даже с dt_integration = 600 с
(RuntimeError: HydroSolver не сошёлся). Это BUG-003 / DEBT-007 — дефицит
лимита дробления шага, а не свойство задачи.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04_table_table\\grid_convergence.py
"""

import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[0]))
sys.path.insert(0, str(HERE))

from example_runner import _PROTO_ROOT  # noqa: E402,F401  (подключает прототип)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

from pressure_gor_closure import solve, K_PERM, H_THICK, P_EXT, R_EXT  # noqa: E402

# Сетки для проверки. 200 и выше не сходятся (BUG-003), поэтому не включены:
# скрипт должен проходить целиком, а не падать на последней строке.
GRIDS = (25, 50, 100)


def run_case(N: int, dt: float = 600.0):
    """Расчёт на сетке N. dt = 600 с, чтобы мелкие сетки тоже сходились."""
    config = load_config(HERE / "config.json")
    config.grid.N = N
    config.time.dt_integration = dt
    simulator, initial_state = SimulatorFactory.from_config(config)
    history = simulator.run(initial_state)
    return simulator._grid, history


def analytic_pressure(grid, clo, q_o):
    """Аналитический профиль p(r) на сетке grid — для сравнения по узлам."""
    lnr = np.log(grid.r_centers)
    C = q_o / (2.0 * np.pi * K_PERM * H_THICK)
    sol = solve_ivp(lambda x, y: [C / clo.mob_o(y[0])],
                    [np.log(R_EXT), lnr[0]], [P_EXT],
                    t_eval=lnr[::-1], rtol=1e-11, atol=1e-4, method="Radau")
    return sol.y[0][::-1]


def main():
    q_ana, _p_b, clo, _C, _rhs = solve()
    print("== Сходимость примера 04 по сетке ==")
    print(f"аналитика q_o = {q_ana:.6e} м³ст/с (от сетки не зависит)")
    print()
    print("   N     q_o, м³ст/с    отн. ошибка   отношение   макс|dp|, кПа")

    prev_err = None
    for N in GRIDS:
        grid, history = run_case(N)
        q_num = history.well_data[-1].q_o_std
        err = abs(q_num - q_ana) / q_ana

        p_ana = analytic_pressure(grid, clo, q_ana)
        dp = np.abs(p_ana - history.states[-1].p).max() / 1e3

        ratio = "" if prev_err is None else f"{prev_err / err:.2f}"
        print(f" {N:4d}   {q_num:.6e}   {err * 100:8.4f} %   {ratio:>6}"
              f"      {dp:7.1f}")
        prev_err = err

    print()
    print("Отношение ~2 при удвоении N — первый порядок, как у схемы против")
    print("потока. Систематического смещения нет: расхождение 0.45 % при")
    print("N = 50 — цена дискретизации, а не дефект аналитики.")


if __name__ == "__main__":
    main()
