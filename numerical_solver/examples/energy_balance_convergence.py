"""Сходимость невязки баланса энергии по Δt — общая проверка для всех примеров.

СМЫСЛ ПРОВЕРКИ. Невязка баланса энергии должна быть ошибкой РАСЩЕПЛЕНИЯ, а
не ошибкой формул. Расщепление даёт O(Δt): гидро-шаг замораживает T,
тепловой шаг замораживает p и S_g, рассогласование между ними линейно по
шагу. Если бы какой-то член баланса был выписан неверно, невязка вышла бы
на полку и порядок оказался бы близок к нулю.

Именно так были найдены два дефекта:
  BUG-004  — накопление считалось как разность запасов вместо суммы
             приращений: порядок -0.006 (полка 0.2001/0.2017/0.2025) на
             примере 04 вместо ожидаемой единицы;
  FEAT-016 — пропущенный кондуктивный член на примере 10: порядок 0.751
             вместо 0.980. При штатном шаге член давал всего 8.6 % невязки
             и по одному прогону был неотличим от шума.

Мораль: проверка невязки при одном Δt слабее проверки её ПОРЯДКА.
Систематический член почти не зависит от шага, поэтому при измельчении он
начинает доминировать над убывающей ошибкой расщепления — и полка
проявляется, тогда как абсолютная величина невязки выглядит приемлемой.

Три точки, а не две: по двум числам первый порядок не отличить от
случайного совпадения. Порядок определяется регрессией log(невязка) по
log(Δt), а не постулируется.

ОЖИДАЕМЫЕ ПОРЯДКИ (измерено):
    пример 01  1.000     пример 04  0.967
    пример 02  0.999     пример 05  0.996
    пример 03  0.995     пример 10  0.980

Запуск для конкретного примера:
    cd numerical_solver
    .venv\\Scripts\\python examples\\energy_balance_convergence.py 03
"""

import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES),
           str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from energy_balance import compute_balance  # noqa: E402
from convergence import run_series, fit_order  # noqa: E402

# Шаги по времени, с. Отношения 4 и 2.5 дают в произведении 10,
# так что первый порядок читается и по краям, и по каждой паре.
DT_LIST = [3600, 900, 360]


def _apply_dt(config, dt):
    """Выставить шаг интегрирования.

    Прежде здесь дополнительно ставился save_every = 1: без него кривые
    для разных dt прореживались бы по-разному, делая панель (a)
    несопоставимой. После DEBT-013 частоту вывода задаёт только структура
    time.history, общая для всех прогонов, поэтому моменты записи
    совпадают у всех dt по построению, а внутри интервала укладывается
    dt_hist/dt подшагов — тем больше, чем мельче шаг.
    """
    config.time.dt_integration = dt


def _measure_balance(sim, history, config) -> dict:
    """Невязка баланса: финальная и максимальная по шагам."""
    bal = compute_balance(history, sim._grid, config)
    # Максимум берём с 1-го шага: на нулевом ΔE = 0, невязка не определена.
    max_rel = (float(np.max(bal["rel_residual"][1:]))
               if len(bal["t"]) > 1 else 0.0)
    return dict(bal, error=float(bal["rel_residual"][-1]),
                final_rel=float(bal["rel_residual"][-1]), max_rel=max_rel)


def run_convergence(config_base, dt_list=None) -> list[dict]:
    """Серия прогонов по Δt с балансом энергии на каждом."""
    return run_series(config_base, dt_list or DT_LIST,
                      _apply_dt, _measure_balance)


def plot_balance_convergence(results, output_dir: Path,
                             title_suffix: str = "") -> tuple[float, float]:
    """Двухпанельный график: невязка во времени + порядок по Δt.

    Возвращает (порядок по финальной невязке, порядок по максимальной).
    """
    dt_arr = np.array([r["value"] for r in results], dtype=float)
    fin_arr = np.array([r["final_rel"] for r in results])
    max_arr = np.array([r["max_rel"] for r in results])

    order_fin = fit_order(dt_arr, fin_arr)
    order_max = fit_order(dt_arr, max_arr)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    colors = ['b', 'g', 'r', 'c', 'm']
    for bal, col in zip(results, colors):
        ax1.plot(bal["t"] / 3600.0, bal["rel_residual"], col, linewidth=1.3,
                 label=f"Δt = {bal['value']} с (max {bal['max_rel']:.1e})")
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
    ax2.loglog(dt_arr, fin_arr[-1] * (dt_arr / dt_arr[-1]), 'r:',
               linewidth=1.5, label=r"эталон $O(\Delta t)$")
    ax2.set_xlabel("Δt, с")
    ax2.set_ylabel("относительная невязка")
    ax2.set_title(f"Порядок сходимости по Δt{title_suffix}")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, which="both")

    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "energy_balance_convergence.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"\nСохранён: {out_path}")

    print("\n  dt, с   финальная    максимальная")
    for bal in results:
        print(f"  {bal['value']:6d}   {bal['final_rel']:.3e}    "
              f"{bal['max_rel']:.3e}")

    print(f"\nОтношение по краям: {fin_arr[0] / fin_arr[-1]:.1f}x "
          f"при Δt/{dt_arr[0] / dt_arr[-1]:.0f}  (совпадение = O(Δt))")
    print(f"Наблюдаемый порядок: {order_fin:.3f} (финальная), "
          f"{order_max:.3f} (максимальная)")
    return order_fin, order_max


def _resolve_example(name_or_prefix: str) -> Path:
    """examples/<имя>/ по полному имени или числовому префиксу ('03').

    Пользователю не нужно печатать '03_standing_corey' целиком.
    Ошибка при отсутствии или неоднозначности префикса.
    """
    exact = _EXAMPLES / name_or_prefix
    if exact.is_dir():
        return exact
    matches = sorted(d for d in _EXAMPLES.iterdir()
                     if d.is_dir() and d.name.startswith(name_or_prefix))
    if not matches:
        raise SystemExit(f"нет примера '{name_or_prefix}'")
    if len(matches) > 1:
        raise SystemExit(f"неоднозначно: {[m.name for m in matches]}")
    return matches[0]


# ── Автономный запуск ──
if __name__ == "__main__":
    from gpn_multiphase_solver.io.config import load_config

    if len(sys.argv) < 2:
        raise SystemExit("укажите пример: python "
                         "examples\\energy_balance_convergence.py 03")

    folder = _resolve_example(sys.argv[1])
    config_base = load_config(folder / "config.json")

    results = []
    for dt in DT_LIST:
        print(f"── Прогон: dt = {dt} с ──")
        row = run_series(config_base, [dt], _apply_dt, _measure_balance)[0]
        print(f"   max rel = {row['max_rel']:.2e}, "
              f"final rel = {row['final_rel']:.2e}")
        results.append(row)

    plot_balance_convergence(results, folder / "output",
                             f" — {folder.name}")
