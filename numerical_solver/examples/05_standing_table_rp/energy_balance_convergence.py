"""Сходимость невязки баланса энергии по Δt — пример 05.

Баланс пятикомпонентный (со скрытой теплотой дегазации, см. energy_balance.py).
Проверка не зависит от вида ОФП, поэтому код тот же, что в примере 03; здесь
она нужна, чтобы обосновать невязку ~1 %, которую печатает main.py.

Смысл проверки: невязка баланса должна быть ошибкой РАСЩЕПЛЕНИЯ, а не
ошибкой формул. Расщепление даёт O(Δt): гидро-шаг замораживает T, тепловой
шаг замораживает p и S_g, рассогласование между ними линейно по шагу.
Если бы какой-то член баланса был выписан неверно, невязка вышла бы на
полку и порядок оказался бы близок к нулю.

Три точки, а не две: по двум числам первый порядок не отличить от
случайного совпадения. Порядок определяется регрессией log(невязка)
по log(Δt), а не постулируется.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\05_standing_table_rp\\energy_balance_convergence.py
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
import matplotlib.pyplot as plt  # noqa: E402

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402

from energy_balance import compute_balance  # noqa: E402

# Шаги по времени, с. Отношения 4 и 2.5 дают в произведении 10,
# так что первый порядок читается и по краям, и по каждой паре.
DT_LIST = [3600, 900, 360]


def run_one(config_base, dt: int) -> dict:
    """Прогон примера с заданным dt + баланс энергии."""
    config = deepcopy(config_base)
    config.time.dt_integration = dt
    # save_every = 1: невязка нужна на каждом шаге, иначе кривые для разных
    # dt прореживаются по-разному и панель (a) несопоставима.
    config.output.save_every = 1
    config.output.log_level = "WARNING"

    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    bal = compute_balance(history, sim._grid, config)
    # Максимум берём с 1-го шага: на нулевом ΔE = 0, невязка не определена.
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
        print(f"   max rel = {bal['max_rel']:.2e}, "
              f"final rel = {bal['final_rel']:.2e}")
        results.append(bal)

    dt_arr = np.array([r["dt"] for r in results], dtype=float)
    fin_arr = np.array([r["final_rel"] for r in results])
    max_arr = np.array([r["max_rel"] for r in results])

    order_fin = np.polyfit(np.log(dt_arr), np.log(fin_arr), 1)[0]
    order_max = np.polyfit(np.log(dt_arr), np.log(max_arr), 1)[0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    colors = ['b', 'g', 'r']
    for bal, col in zip(results, colors):
        ax1.plot(bal["t"] / 3600.0, bal["rel_residual"], col, linewidth=1.3,
                 label=f"Δt = {bal['dt']} с (max {bal['max_rel']:.1e})")
    ax1.set_xlabel("Время, ч")
    ax1.set_ylabel(r"|невязка| / |$\Delta E$|")
    ax1.set_title("Невязка баланса энергии во времени")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    ax2.loglog(dt_arr, fin_arr, 'ko-', linewidth=1.5, markersize=7,
               label=f"финальная (порядок {order_fin:.2f})")
    ax2.loglog(dt_arr, max_arr, 'ks--', linewidth=1.2, markersize=6,
               markerfacecolor='none',
               label=f"максимальная (порядок {order_max:.2f})")
    # Эталон O(Δt), привязанный к самой мелкой точке.
    ax2.loglog(dt_arr, fin_arr[-1] * (dt_arr / dt_arr[-1]), 'r:', linewidth=1.5,
               label=r"эталон $O(\Delta t)$")
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

    print("\n  Δt, с   финальная    максимальная")
    for bal in results:
        print(f"  {bal['dt']:6d}   {bal['final_rel']:.3e}    {bal['max_rel']:.3e}")

    print(f"\nОтношение по краям: {fin_arr[0] / fin_arr[-1]:.1f}x "
          f"при Δt/{dt_arr[0] / dt_arr[-1]:.0f}  (совпадение = O(Δt))")
    print(f"Наблюдаемый порядок: {order_fin:.3f} (финальная), "
          f"{order_max:.3f} (максимальная)")
