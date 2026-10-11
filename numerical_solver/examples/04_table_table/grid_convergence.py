"""Порядок сходимости примера 04 по сетке.

ЗАЧЕМ. Замкнутое решение (../closed_form.py) даёт дебит квадратурой и
профиль давления интегрированием ОДУ, не беря из расчёта ничего. На рабочей
сетке N = 50 расчёт расходится с ним на доли процента. Само по себе это
ничего не доказывает: расхождение может быть ошибкой аппроксимации (тогда
оно убывает с измельчением сетки) или систематическим смещением — ошибкой
вывода замыкания или схемы (тогда оно осталось бы при любом N).

Замкнутое решение считается на каждой сетке заново, в её центрах ячеек:
дебит от сетки не зависит, профиль сравнивается поузельно.

РЕЗУЛЬТАТ. Расхождение по дебиту убывает первым порядком, как и должно у
схемы против потока:

    N    2ф ячеек   q_o, м³ст/с    отн. ошибка   отношение   макс|dp|, кПа
    25      13     5.901165e-03     0.878 %                     46.3
    50      26     5.875953e-03     0.447 %        1.96         23.6
   100      53     5.863006e-03     0.226 %        1.98         12.0
   150      79     5.858591e-03     0.150 %        1.50          8.0

При удвоении N ошибка падает в 1.96-1.98 раза, при N x 1.5 — в 1.50;
теоретические значения 2.00 и 1.50. Ошибка профиля давления убывает так же.
Замкнутое решение q_o = 5.849791e-03, к нему расчёт и сходится:
систематического смещения нет, 0.45 % при N = 50 — цена дискретизации.

Так же, первым порядком, сходятся фронт r_b (2.666 -> 2.630 -> 2.612 ->
2.606 м при замкнутом 2.594) и T(r_w) (приращения 0.0051 и 0.0031 К при
удвоениях; замер 2026-10-11, DEBT-063).

ГДЕ СОСРЕДОТОЧЕНА ОШИБКА. На фронте разгазирования p = pb: подынтегральная
функция kro/(mu_o*Bo) там негладкая (ниже pb включается разгазирование,
Rs начинает падать), а схема размазывает излом по ячейке.

СЕТКИ. Серия заканчивается на N = 150. Первый шаг (скачок 20 -> 8 МПа)
сходится без дробления на всех сетках до N = 200 (замер 2026-10-01).

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04_table_table\\grid_convergence.py
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[0]))

import example_runner  # noqa: E402,F401  (консоль в UTF-8: скрипт печатает м³ст/с)

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

from closed_form import solve_closed  # noqa: E402
from rs_analytics import front_radius  # noqa: E402
from two_phase_analytics import SG_EPS  # noqa: E402

# Сетки для проверки; 50 — рабочая сетка примера.
GRIDS = (25, 50, 100, 150)

# Лимит дроблений первого шага. На результат не влияет — только страхует
# серию от отказа на стартовом скачке 20 -> 8 МПа.
MAX_RETRIES = 14


def run_case(N: int):
    """Полный прогон конфига примера на сетке N при штатном dt = 3600 с."""
    config = load_config(HERE / "config.json")
    config.grid.N = N
    config.numerics.max_retries = MAX_RETRIES
    simulator, initial_state = SimulatorFactory.from_config(config)
    t0 = time.time()
    history = simulator.run(initial_state)
    return config, simulator, history, time.time() - t0


def main():
    print("== Сходимость примера 04 по сетке ==")
    print()
    print("   N   2ф ячеек   q_o, м³ст/с    отн. ошибка   отношение"
          "   макс|dp|, кПа   r_b, м    T(r_w), К    время, с")

    prev_err = None
    for N in GRIDS:
        config, sim, history, elapsed = run_case(N)
        grid = sim._grid
        pvt = sim._energy._pvt
        # Замкнутое решение на ЭТОЙ сетке: из расчёта не берётся ничего.
        cl = solve_closed(config, pvt, _create_relperm(config), grid.r_centers)

        last = history.states[-1]
        q_num = history.well_data[-1].q_o_std
        err = abs(q_num - cl["q_o"]) / cl["q_o"]
        dp = np.abs(cl["p"] - last.p).max() / 1e3
        n_2ph = int(np.sum(last.Sg > SG_EPS))
        r_b = front_radius(config, history, grid, pvt)

        ratio = "" if prev_err is None else f"{prev_err / err:.2f}"
        print(f" {N:4d}   {n_2ph:6d}   {q_num:.6e}   {err * 100:8.4f} %   "
              f"{ratio:>6}      {dp:9.2f}     {r_b:.4f}   {last.T[0]:.4f}"
              f"   {elapsed:7.1f}")
        prev_err = err

    print()
    print(f"Замкнутое решение: q_o = {cl['q_o']:.6e} м³ст/с, "
          f"r_b = {cl['r_b']:.4f} м (от сетки не зависят)")


if __name__ == "__main__":
    main()
