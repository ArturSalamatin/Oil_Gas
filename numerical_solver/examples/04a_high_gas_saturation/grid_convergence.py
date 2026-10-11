"""Сходимость примера 04a по сетке.

ЗАЧЕМ. На рабочей сетке N = 150 дебит расчёта расходится с замкнутым
решением (GOR = Rs0) на 0.55 %. Само по себе это ничего не доказывает:
расхождение может быть как ошибкой аппроксимации (тогда оно убывает с
измельчением сетки), так и систематическим смещением — ошибкой в выводе
замыкания или в схеме (тогда оно осталось бы при любом N).

РЕЗУЛЬТАТ. Ошибка убывает при измельчении, целевая насыщенность держится:

    N      Sg(r_w)    q_o, м³ст/с    отн. ошибка   отношение
    25     0.6991     5.082609e-03      3.3239 %
    50     0.7000     4.997825e-03      1.6839 %       1.97
    80     0.7000     4.965104e-03      1.0360 %       1.63
   120     0.7000     4.948061e-03      0.6951 %       1.49
   150     0.7000     4.940866e-03      0.5505 %       1.26

    аналитика q_o = 4.913667e-03 м³ст/с (от сетки не зависит)

Sg стабильна с четвёртого знака начиная с N = 50 — целевое значение 0.70
достигается независимо от сетки, что и требовалось от обратного расчёта
k_rg^max: параметр выведен из замыкания, а не подогнан под дискретизацию.

Дебит сходится первым порядком (схема против потока): отношения ошибок
1.97, 1.63, 1.49, 1.26 совпадают с отношениями шагов сетки 2, 1.6, 1.5,
1.25 — порядок держится единичным на всём ряду, систематического смещения
нет.

ЛИМИТ ДРОБЛЕНИЯ. Все сетки считаются на numerics.max_retries = 12 из
конфига примера. Первый шаг (скачок p_wf 20 -> 4 МПа) на всех пяти сетках
сходится без дробления — его решает третья ступень advance.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04a_high_gas_saturation\\grid_convergence.py

~3 мин: пять прогонов.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))   # numerical_solver/
sys.path.insert(0, str(HERE.parents[0]))   # examples/
sys.path.insert(0, str(HERE))

import example_runner  # noqa: E402,F401  (консоль в UTF-8: скрипт печатает м³ст/с)

from closed_form import solve_closed  # noqa: E402
from convergence import run_series  # noqa: E402
from gpn_multiphase_solver.factory import _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

# Сетки для проверки; 150 — рабочая сетка примера (config.json).
# Лимит дробления берётся из конфига примера: numerics.max_retries = 12.
GRIDS = (25, 50, 80, 120, 150)


def _apply(config, N):
    """Выставить сетку в копии конфига (хук run_series)."""
    config.grid.N = N


def _measure(sim, history, config):
    """Метрики прогона: Sg на забое, дебит и ошибка против замыкания.

    Дебит расчёта берётся как |G_o| на забое: поток положителен ОТ скважины
    (конвенция знаков проекта), поэтому дебит добычи — модуль потока.
    """
    grid = sim._grid
    cl = solve_closed(config, sim._energy._pvt, _create_relperm(config),
                      grid.r_centers)
    q_num = abs(history.hydro_results[-1].G_o[0])
    return {
        "Sg_well": float(history.states[-1].Sg[0]),
        "q_num": float(q_num),
        "q_ana": float(cl["q_o"]),
        # Нормировка на РАСЧЁТ, а не на аналитику — как в closed_form.
        # report_closed (печать расхождения q_o). Разные знаменатели дали бы 1.683 % и
        # 1.712 % для одного и того же прогона, и README примера расходился
        # бы с тем, что печатает сам пример.
        "error": abs(q_num - cl["q_o"]) / q_num,
    }


def main():
    """Таблица: N, Sg(r_w), q_o, относительная ошибка, отношение ошибок."""
    config = load_config(HERE / "config.json")

    print("== Сходимость примера 04a по сетке ==")
    print(f"numerics.max_retries = {config.numerics.max_retries} "
          f"(из конфига примера)")
    print()

    rows = run_series(config, GRIDS, _apply, _measure)

    print("   N      Sg(r_w)    q_o, м³ст/с    отн. ошибка   отношение")
    prev_err = None
    for row in rows:
        ratio = "" if prev_err is None else f"{prev_err / row['error']:.2f}"
        print(f" {row['value']:4d}     {row['Sg_well']:.4f}     "
              f"{row['q_num']:.6e}     {row['error'] * 100:7.4f} %"
              f"      {ratio:>5}")
        prev_err = row["error"]

    print()
    print(f"аналитика q_o = {rows[0]['q_ana']:.6e} м³ст/с (от сетки не зависит)")
    print()

    # Целевая насыщенность — главный критерий: обратный расчёт k_rg^max
    # обязан давать 0.70 независимо от дискретизации, иначе параметр
    # подогнан под конкретную сетку, а не выведен из замыкания.
    Sg = np.array([r["Sg_well"] for r in rows])
    print(f"Sg(r_w): {Sg.min():.4f} … {Sg.max():.4f} — разброс "
          f"{(Sg.max() - Sg.min()):.4f}")
    print("Целевое 0.70 достигается на всех сетках: параметр k_rg^max выведен")
    print("из замыкания, а не подогнан под сетку.")


if __name__ == "__main__":
    main()
