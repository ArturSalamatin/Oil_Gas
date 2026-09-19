"""Сходимость ОДУ-аналитики температуры по сетке — пример 05.

Расхождение ОДУ со схемой сосредоточено в узкой зоне разгазирования, где
свойства меняются быстрее всего. Этот скрипт показывает, что расхождение —
ошибка разрешения, а не дефект вывода: оно убывает при сгущении сетки.

ЗАЧЕМ ПОВТОРЯТЬ ЭТО ПОСЛЕ 03. В примере 03 у ошибки была ещё одна причина,
специфичная для ОФП Кори: k_rg = k_rg^max·(S_g - S_gc)^2 имеет порог
подвижности, из-за которого k_rg менялась в сотни раз между соседними
ячейками, и гладкий интерполянт этого не воспроизводил. Табличная ОФП
примера 05 растёт от нуля линейно, порога нет. Если после устранения этой
причины ошибка ведёт себя так же (убывает степенным образом с тем же
порядком), значит она определяется общей дискретизацией, а не конкретным
видом k_r — то есть вывод ОДУ корректен для обеих замыкающих зависимостей.

ПРО ШАГ ПО ВРЕМЕНИ. Весь ряд считается при штатном dt = 3600 с. Раньше
мелкие сетки требовали мелкого dt (Newton расходился при жёстко зашитом
лимите дробления), но после DEBT-007 лимит вынесен в конфиг —
numerics.max_retries задаётся для каждой сетки отдельно. Ошибка ОДУ
пространственная и от шага по времени практически не зависит.

ЧТО СЧИТАЕТСЯ. Все прогоны сравниваются на одном физическом времени —
24 часа, к этому моменту ошибка уже вышла на полку. Отдельно выводится
ошибка в однофазной зоне: там ОДУ совпадает со схемой почти как в примере
02, и её сходимость показывает, что порядок аппроксимации не зависит
от двухфазности.

Порядок определяется регрессией log(ошибка) по log(N), а не постулируется.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\05_standing_table_rp\\ode_grid_convergence.py
"""

import sys
import time
from copy import deepcopy
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
from convergence import fit_order  # noqa: E402

# (N, dt, max_retries) — весь ряд при штатном dt = 3600 с.
#
# До DEBT-007 лимит дробления шага был зашит (32 подшага), и мелкие сетки
# приходилось считать с уменьшенным dt: (75, 900), (100, 300), (140, 300),
# (200, 120). Теперь лимит задаётся через numerics.max_retries, и dt
# везде штатный.
#
# ⚠️ Порог по сетке НЕМОНОТОНЕН: N = 100 требует 11 удвоений, тогда как
# N = 140 и N = 200 обходятся девятью (измерено при DEBT-007). Это не
# опечатка — сходимость Newton зависит от того, как узлы сетки ложатся
# относительно фронта разгазирования, а не только от её мелкости.
# Переносить пороги из примера 03 сюда нельзя.
#
# Набор оборван на N = 200: ОДУ решается РЕКУРРЕНТНО, каждый шаг требует
# интерполяции предыдущего решения. Четырёхкратного диапазона по N
# хватает, чтобы определить порядок.
GRIDS = [
    (50, 3600, 9),
    (75, 3600, 9),
    (100, 3600, 11),
    (140, 3600, 9),
    (200, 3600, 9),
]

# Все прогоны сравниваются на этом физическом времени.
T_COMPARE = 24 * 3600.0


def run_one(N: int, dt: int, max_retries: int = 9) -> dict:
    """Прогон на сетке N с шагом dt + решение ОДУ + сравнение."""
    config = load_config(HERE / "config.json")
    config.grid.N = N
    config.time.dt_integration = dt
    # Глубина дробления шага в A-retry (DEBT-007); порог по сетке
    # немонотонен, значения подобраны перебором — см. GRIDS.
    config.numerics.max_retries = max_retries
    # ОДУ решается рекуррентно по сохранённым шагам, поэтому запись нужна
    # на каждом подшаге: интервал истории делаем равным dt_integration
    # (DEBT-013 — частоту вывода задаёт только структура истории).
    # Прогоны на разных dt дают разное число записей, как и раньше при
    # save_every = 1.
    n_records = int(round(T_COMPARE / dt))
    iv = deepcopy(config.time.history[0])
    config.time.history = [deepcopy(iv) for _ in range(n_records)]
    for h in config.time.history:
        h.dt = T_COMPARE / n_records
    config.output.log_level = "ERROR"

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
    print(f"{'N':>5} {'dt':>6} {'шагов':>6} {'max|dT|':>10} "
          f"{'однофаз.':>10} {'двухфаз.':>10} {'2ф.яч':>6} "
          f"{'T(rw)':>9} {'сек':>7}")

    results = []
    for N, dt, max_retries in GRIDS:
        res = run_one(N, dt, max_retries)
        results.append(res)
        print(f"{res['N']:5d} {res['dt']:6d} {res['n_steps']:6d} "
              f"{res['err_total']:10.5f} {res['err_single']:10.5f} "
              f"{res['err_two']:10.5f} {res['n_two']:6d} "
              f"{res['T_well']:9.4f} {res['elapsed']:7.1f}")

    N_arr = np.array([r["N"] for r in results], dtype=float)
    e_tot = np.array([r["err_total"] for r in results])
    e_one = np.array([r["err_single"] for r in results])

    # Регрессия — общая механика (examples/convergence.py). inverse=True:
    # параметр N обратен шагу сетки, знак наклона меняется, чтобы порядок
    # читался положительным.
    order_tot = fit_order(N_arr, e_tot, inverse=True)
    order_one = fit_order(N_arr, e_one, inverse=True)

    print(f"\nНаблюдаемый порядок по N: {order_tot:.3f} (полная область), "
          f"{order_one:.3f} (однофазная зона)")
    print(f"Отношение по краям: {e_tot[0] / e_tot[-1]:.1f}x "
          f"при N×{N_arr[-1] / N_arr[0]:.0f}")

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
