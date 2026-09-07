"""Сходимость невязки баланса энергии при уменьшении шага по времени.

Три прогона примера 01: dt = 3600, 900 и 360 с.
Ожидаемый порядок сходимости: O(Δt) — ошибка расщепления (splitting).
Гидро-шаг замораживает T, тепловой шаг замораживает p; рассогласование
между ними и есть невязка.

Порядок определяется по логарифмической регрессии, а не постулируется:
третья точка нужна, чтобы отличить первый порядок от случайного
совпадения двух чисел.

Строит 2 графика:
  (a) относительная невязка во времени для трёх Δt
  (b) финальная невязка vs Δt в log-log с эталонной прямой O(Δt)

Расчёт баланса берётся из energy_balance.compute_balance — те же формулы,
что и в основном скрипте, без копии.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\01_single_phase_no_jt\\energy_balance_convergence.py
"""

import sys
from pathlib import Path
from copy import deepcopy
import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT / "examples"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory

from energy_balance import compute_balance

# Шаги по времени, с. Отношения 4 и 2.5 — вместе дают 10,
# так что первый порядок читается и по краям, и по каждой паре.
DT_LIST = [3600, 900, 360]


def run_one(config_base, dt: int) -> dict:
    """Прогон примера с заданным dt + баланс энергии."""
    config = deepcopy(config_base)
    config.time.dt_integration = dt
    # save_every = 1: невязка нужна на каждом шаге, иначе кривая (a)
    # прореживается по-разному для разных dt и графики несопоставимы.
    config.output.save_every = 1

    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    bal = compute_balance(history, sim._grid, config)

    # Максимум берётся с 1-го шага: на нулевом ΔE = 0 и невязка не определена.
    bal["max_rel"] = float(np.max(bal["rel_residual"][1:])) if len(bal["t"]) > 1 else 0.0
    bal["final_rel"] = float(bal["rel_residual"][-1])
    bal["dt"] = dt
    return bal


if __name__ == "__main__":
    config_base = load_config(HERE / "config.json")

    results = []
    for dt in DT_LIST:
        print(f"── Прогон: dt = {dt} с ──")
        bal = run_one(config_base, dt)
        print(f"   max rel = {bal['max_rel']:.2e}, final rel = {bal['final_rel']:.2e}")
        results.append(bal)

    dt_arr = np.array([r["dt"] for r in results], dtype=float)
    fin_arr = np.array([r["final_rel"] for r in results])
    max_arr = np.array([r["max_rel"] for r in results])

    # Наблюдаемый порядок: наклон log(невязка) по log(dt).
    order_fin = np.polyfit(np.log(dt_arr), np.log(fin_arr), 1)[0]
    order_max = np.polyfit(np.log(dt_arr), np.log(max_arr), 1)[0]

    # ── Графики ──
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # (a) Невязка во времени
    colors = ['b', 'g', 'r']
    for bal, col in zip(results, colors):
        ax1.plot(bal["t"] / 3600.0, bal["rel_residual"], col, linewidth=1.3,
                 label=f"Δt = {bal['dt']} с (max {bal['max_rel']:.1e})")
    ax1.set_xlabel("Время, ч")
    ax1.set_ylabel(r"|невязка| / |$\Delta E$|")
    ax1.set_title("Невязка баланса энергии во времени")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # (b) Порядок сходимости в log-log
    ax2.loglog(dt_arr, fin_arr, 'ko-', linewidth=1.5, markersize=7,
               label=f"финальная (порядок {order_fin:.2f})")
    ax2.loglog(dt_arr, max_arr, 'ks--', linewidth=1.2, markersize=6,
               markerfacecolor='none', label=f"максимальная (порядок {order_max:.2f})")

    # Эталон O(Δt), привязанный к самой мелкой точке.
    ref = fin_arr[-1] * (dt_arr / dt_arr[-1])
    ax2.loglog(dt_arr, ref, 'r:', linewidth=1.5, label=r"эталон $O(\Delta t)$")

    ax2.set_xlabel("Δt, с")
    ax2.set_ylabel("относительная невязка")
    ax2.set_title("Порядок сходимости по Δt")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, which="both")

    fig.tight_layout()
    output_dir = HERE / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "energy_balance_convergence.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)

    print(f"\nСохранён: {out_path}")

    # ── Сводка ──
    print("\n  Δt, с   финальная    максимальная")
    for bal in results:
        print(f"  {bal['dt']:6d}   {bal['final_rel']:.3e}    {bal['max_rel']:.3e}")

    print(f"\nОтношение по краям: {fin_arr[0] / fin_arr[-1]:.1f}x "
          f"при Δt/{dt_arr[0] / dt_arr[-1]:.0f}  (ожидаем совпадения при O(Δt))")
    print(f"Наблюдаемый порядок: {order_fin:.3f} (финальная), "
          f"{order_max:.3f} (максимальная)")
