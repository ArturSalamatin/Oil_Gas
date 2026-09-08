"""Сходимость ОДУ-аналитики температуры по сетке — пример 03.

Расхождение ОДУ с численным решением сосредоточено в узкой зоне
разгазирования (см. README, п. 5б): там k_rg меняется в сотни раз за
ячейку, а три тепловых эффекта по 0.6-1.3 К гасят друг друга до 0.011 К.
Этот скрипт показывает, что расхождение — именно ошибка разрешения, а не
дефект вывода: оно убывает при сгущении сетки.

ПРО ШАГ ПО ВРЕМЕНИ. Весь ряд считается при штатном dt = 3600 с. Раньше
мелкие сетки требовали мелкого dt (Newton расходился при жёстко зашитом
лимите дробления 32 подшага), но после DEBT-007 лимит вынесен в конфиг:
при numerics.max_retries = 9 сетки до N = 140 сходятся при dt = 3600,
N = 200 требует 10.

Единый шаг ошибку ОДУ не меняет — она пространственная, а не временная
(проверено: N = 100 даёт 0.02204 К при dt = 300 против 0.02205 К при
dt = 3600; N = 200 — 0.01078 против 0.01079 К), зато ряд считается за
~60 с вместо ~15 минут: число шагов ОДУ равно T_COMPARE/dt, и при
dt = 3600 их 24 вместо 288-720.

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

# (N, dt, max_retries) — весь ряд при штатном dt = 3600 с.
#
# До DEBT-007 лимит дробления шага был зашит (32 подшага), и мелкие сетки
# приходилось считать с уменьшенным dt: (75, 900), (100, 300), (140, 300),
# (200, 120). Теперь лимит задаётся через numerics.max_retries: девяти
# удвоений хватает до N = 140, для N = 200 нужно десять.
#
# ЦЕНА ШАГА. ОДУ решается рекуррентно: шаг n даёт T_prev для шага n+1,
# пропустить нельзя, число шагов = T_COMPARE/dt. При едином dt = 3600 это
# 24 шага на каждую точку ряда вместо прежних 288-720, и весь ряд считается
# за ~60 с вместо ~15 минут.
#
# На результат dt не влияет — ошибка ОДУ пространственная: N = 100 даёт
# 0.02204 К при dt = 300 против 0.02205 К при dt = 3600, N = 200 — 0.01078
# против 0.01079 К (совпадение в четвёртом знаке при том, что между
# соседними сетками ошибка убывает в полтора-два раза).
GRIDS = [
    (50, 3600, 9),
    (75, 3600, 9),
    (100, 3600, 9),
    (140, 3600, 9),
    (200, 3600, 10),
]

# Все прогоны сравниваются на этом физическом времени.
T_COMPARE = 24 * 3600.0


def run_one(N: int, dt: int, max_retries: int = 9) -> dict:
    """Прогон на сетке N с шагом dt + решение ОДУ + сравнение."""
    config = load_config(HERE / "config.json")
    config.grid.N = N
    config.time.dt_integration = dt
    # Глубина дробления шага в A-retry (DEBT-007): мелкие сетки требуют
    # больше удвоений, чтобы Newton сошёлся при штатном dt.
    config.numerics.max_retries = max_retries
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
