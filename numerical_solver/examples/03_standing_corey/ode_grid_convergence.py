"""Сходимость ОДУ-аналитики температуры по сетке — пример 03.

Расхождение ОДУ с численным решением сосредоточено в узкой зоне
разгазирования (см. README, п. 5б): там k_rg меняется в сотни раз за
ячейку, а три тепловых эффекта по 0.6-1.3 К гасят друг друга до 0.011 К.
Этот скрипт показывает, что расхождение — именно ошибка разрешения, а не
дефект вывода: оно убывает при сгущении сетки.

ПРО ШАГ ПО ВРЕМЕНИ. Мелкие сетки требуют мелкого dt, иначе Newton
расходится (DEBT-007). Для каждой N берётся наибольший работающий шаг:

    N        50    75   100   140   200
    dt, с  3600   900   300   300   120

Разные dt сравнение не портят: ошибка ОДУ от шага по времени практически
не зависит (при N = 50 она равна 0.04895 К при dt = 3600 и 0.04887 К при
dt = 300, то есть меняется в четвёртом знаке). Это ожидаемо — ошибка
пространственная, а не временная.

ЧТО СЧИТАЕТСЯ. Все прогоны сравниваются на одном физическом времени —
24 часа, к этому моменту ошибка уже вышла на полку (на шагах 24/48/72
она одинакова). Отдельно выводится ошибка в однофазной зоне: там ОДУ
совпадает со схемой почти как в примере 02, и её сходимость показывает,
что порядок аппроксимации не зависит от двухфазности.

Порядок определяется регрессией log(ошибка) по log(N), а не постулируется.

ПОЧЕМУ В КОНФИГЕ lambda = 0. Теплопроводности в ОДУ нет — она сделала бы
уравнение энергии краевым (вторая производная), и решения первого порядка
не существовало бы. Пока в конфиге стояло lambda != 0, её вклад в
расхождение с сеткой НЕ убывал (≈0.0025 К при любом N), тогда как
собственная ошибка аппроксимации падала как 1/N. При N = 50 это давало 5 %
расхождения, при N = 400 — уже треть, и наблюдаемый порядок проседал
с 1.02 до 0.70. С нулевой теплопроводностью сходимость чистая: ОДУ и схема
решают ровно одно уравнение, и всё расхождение между ними — только
дискретизация. Примеры 04, 05, 07-09 обнулены по той же причине.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\03_standing_corey\\ode_grid_convergence.py
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT / "examples"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402

import temperature_ode as tode  # noqa: E402
from two_phase_analytics import SG_EPS  # noqa: E402
from convergence import fit_order, pairwise_orders  # noqa: E402

# (N, dt) — наибольший dt, при котором Newton сходится на этой сетке.
# Найдено перебором; при большем шаге падает с
# "HydroSolver не сошёлся после 32 подшагов".
#
# ЦЕНА МЕЛКИХ СЕТОК. ОДУ решается рекуррентно: шаг n даёт T_prev для шага
# n+1, пропустить нельзя. Число шагов = T_COMPARE/dt, и оно растёт вдвойне —
# и от измельчения сетки, и от вынужденного уменьшения dt:
#
#     N       50    75   100   140   200   280   400
#     шагов   24    96   288   288   720  1440  2880
#
# Суммарно ряд до N = 400 требует 5736 решений solve_ivp (около часа), причём
# половина приходится на одну последнюю точку. Ряд обрывается на N = 200:
# 1416 шагов, несколько минут, а пять точек с восьмикратным охватом
# (50 → 400 против 50 → 200) определяют порядок не хуже — по прежнему
# прогону попарные порядки на хвосте держались ровно.
#
# Сам dt на результат не влияет: ошибка ОДУ пространственная, при N = 50 она
# равна 0.04895 К при dt = 3600 и 0.04887 К при dt = 300. Мельчить шаг
# приходится только ради сходимости гидродинамики.
GRIDS = [
    (50, 3600),
    (75, 900),
    (100, 300),
    (140, 300),
    (200, 120),
]

# Все прогоны сравниваются на этом физическом времени.
T_COMPARE = 24 * 3600.0


def run_one(N: int, dt: int) -> dict:
    """Прогон на сетке N с шагом dt + решение ОДУ + сравнение."""
    config = load_config(HERE / "config.json")
    config.grid.N = N
    config.time.dt_integration = dt
    config.time.history[0].dt = T_COMPARE
    config.output.log_level = "ERROR"
    # save_every = 1: ОДУ решается рекуррентно по сохранённым шагам,
    # прореживание истории сломало бы соответствие шаг ↔ момент времени.
    config.output.save_every = 1

    t0 = time.perf_counter()
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)
    grid = sim._grid

    n_steps = len(history.times) - 1
    r_ode, T_ode = tode.solve_ode(history, config, grid, sim._energy,
                                  n_steps=n_steps)
    elapsed = time.perf_counter() - t0

    T_num = history.states[n_steps].T
    T_int = np.interp(grid.r_centers, r_ode, T_ode)
    diff = T_num - T_int

    Sg = history.states[-1].Sg
    mask1 = Sg <= SG_EPS

    return dict(
        N=N, dt=dt, n_steps=n_steps, elapsed=elapsed,
        err_total=float(np.max(np.abs(diff))),
        err_single=float(np.max(np.abs(diff[mask1]))),
        err_two=float(np.max(np.abs(diff[~mask1]))),
        n_two=int((~mask1).sum()),
        T_well=float(T_num[0]),
    )


if __name__ == "__main__":
    print(f"Сходимость ОДУ по сетке (сравнение на t = {T_COMPARE/3600:.0f} ч)\n")
    print(f"{'N':>5} {'dt':>6} {'шагов':>6} {'max|ΔT|':>10} "
          f"{'однофаз.':>10} {'двухфаз.':>10} {'2ф.яч':>6} "
          f"{'T(rw)':>9} {'сек':>7}")

    results = []
    for N, dt in GRIDS:
        res = run_one(N, dt)
        results.append(res)
        print(f"{res['N']:5d} {res['dt']:6d} {res['n_steps']:6d} "
              f"{res['err_total']:10.5f} {res['err_single']:10.5f} "
              f"{res['err_two']:10.5f} {res['n_two']:6d} "
              f"{res['T_well']:9.4f} {res['elapsed']:7.1f}")

    N_arr = np.array([r["N"] for r in results], dtype=float)
    e_tot = np.array([r["err_total"] for r in results])
    e_one = np.array([r["err_single"] for r in results])

    # Регрессия и попарные порядки — общая механика (examples/convergence.py).
    # inverse=True: параметр N обратен шагу сетки, знак наклона меняется,
    # чтобы порядок читался положительным.
    order_tot = fit_order(N_arr, e_tot, inverse=True)
    order_one = fit_order(N_arr, e_one, inverse=True)

    print(f"\nНаблюдаемый порядок по N: {order_tot:.3f} (полная область), "
          f"{order_one:.3f} (однофазная зона)")
    print(f"Отношение по краям: {e_tot[0] / e_tot[-1]:.1f}x "
          f"при N×{N_arr[-1] / N_arr[0]:.0f}")

    # Попарные порядки: регрессия усредняет и скрыла бы деградацию, если бы
    # она была. Здесь они должны держаться около единицы на всём ряду.
    print("\nПопарные порядки:")
    for n1, n2, k in zip(N_arr[:-1], N_arr[1:],
                         pairwise_orders(N_arr, e_tot, inverse=True)):
        print(f"  {n1:3.0f}→{n2:3.0f}: {k:.3f}")

    # ── График ──
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ax1.loglog(N_arr, e_tot, 'ko-', linewidth=1.5, markersize=7,
               label=f"вся область (порядок {order_tot:.2f})")
    ax1.loglog(N_arr, e_one, 'bs--', linewidth=1.2, markersize=6,
               markerfacecolor='none',
               label=f"однофазная зона (порядок {order_one:.2f})")
    # Эталон O(1/N), привязанный к самой мелкой сетке.
    ax1.loglog(N_arr, e_tot[0] * (N_arr[0] / N_arr), 'r:', linewidth=1.5,
               label=r"эталон $O(1/N)$")
    ax1.set_xlabel("N (число ячеек)")
    ax1.set_ylabel(r"max$|T_{num} - T_{ode}|$, К")
    ax1.set_title("Сходимость ОДУ-аналитики по сетке")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3, which="both")

    # Вторая панель: ошибка против числа ячеек В ЗОНЕ разгазирования —
    # именно оно определяет качество, а не полное N.
    n_two = np.array([r["n_two"] for r in results], dtype=float)
    ax2.loglog(n_two, e_tot, 'ko-', linewidth=1.5, markersize=7)
    for r in results:
        ax2.annotate(f"N={r['N']}", (r["n_two"], r["err_total"]),
                     textcoords="offset points", xytext=(6, 4), fontsize=7)
    ax2.set_xlabel("ячеек в зоне разгазирования")
    ax2.set_ylabel(r"max$|T_{num} - T_{ode}|$, К")
    ax2.set_title("Ошибка определяется разрешением двухфазной зоны")
    ax2.grid(True, alpha=0.3, which="both")

    fig.tight_layout()
    out_dir = HERE / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ode_grid_convergence.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"\nСохранён: {out_path}")
