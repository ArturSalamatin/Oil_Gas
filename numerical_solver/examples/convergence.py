"""Механика проверок сходимости — общая для прогонов по Δt и по сетке.

ЧТО ЗДЕСЬ ОБЩЕЕ, А ЧТО НЕТ. Все проверки сходимости в примерах устроены
одинаково: прогнать задачу на серии значений параметра (Δt или N),
измерить ошибку, оценить порядок регрессией log(ошибка) по log(шаг),
нарисовать двухпанельный график. Отличаются они ЭТАЛОНОМ, с которым
сравнивается расчёт:

  01/spatial_convergence      — ОДУ-аналитика по температуре
  03/ode_grid_convergence     — ОДУ-аналитика в двухфазной зоне
  04/grid_convergence         — дебит против GOR-замыкания
  05/closed_form_convergence  — two_phase_analytics.solve_closed
  */energy_balance_convergence — невязка баланса энергии по Δt

Эталон — это физика конкретного примера, и выносить его нельзя: он и есть
предмет проверки. Поэтому здесь только механика, а эталон приходит
аргументом-функцией.

ПОЧЕМУ ПОРЯДОК ИЗМЕРЯЕТСЯ, А НЕ ПОСТУЛИРУЕТСЯ. Ожидаемый порядок известен
теоретически (O(Δt) для расщепления, O(1/N) для аппроксимации), но именно
его измерение отличает «член выписан неверно» от «член выписан верно, но
дискретизация грубая». Пропущенный член даёт полку — порядок около нуля
при любой ошибке — и это единственный надёжный признак. Так был найден
BUG-004 (порядок -0.006 вместо 1) и пропуск кондукции у примера 10
(0.751 вместо 0.980).

ТРИ ТОЧКИ МИНИМУМ. По двум числам первый порядок не отличить от случайного
совпадения.

Модуль библиотечный: своего __main__ у него нет, потому что запускать
«сходимость вообще» бессмысленно — нужен пример и его эталон. Запускаются
скрипты примеров, которые этот модуль используют.
"""

import sys
from pathlib import Path
from copy import deepcopy
from typing import Callable

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


def run_series(config_base, values, apply: Callable, measure: Callable,
               log_level: str = "WARNING") -> list[dict]:
    """Прогнать задачу на серии значений параметра и измерить ошибку.

    apply(config, value)          — выставить параметр в копии конфига
    measure(sim, history, config) — вернуть метрику (float) или dict с ней

    Возвращает список dict по одному на значение; в каждом есть ключ
    "value", плюс всё, что вернул measure (если dict) либо ключ "error".

    Конфиг копируется deepcopy: серия прогонов не должна портить базовый
    объект, иначе второй вызов run_series получит уже изменённые параметры.
    """
    from gpn_multiphase_solver.factory import SimulatorFactory

    results = []
    for value in values:
        config = deepcopy(config_base)
        apply(config, value)
        config.output.log_level = log_level

        sim, initial_state = SimulatorFactory.from_config(config)
        history = sim.run(initial_state)

        measured = measure(sim, history, config)
        row = dict(measured) if isinstance(measured, dict) else {
            "error": float(measured)}
        row["value"] = value
        results.append(row)
    return results


def fit_order(values, errors, inverse: bool = False) -> float:
    """Порядок сходимости регрессией log(ошибка) по log(шаг).

    inverse=False — параметр ЕСТЬ шаг (Δt): порядок = наклон, ожидается > 0.
    inverse=True  — параметр обратен шагу (N ~ 1/h): знак наклона меняется,
                    чтобы порядок снова читался положительным.

    Регрессия, а не отношение двух крайних точек: усреднение по всем точкам
    устойчивее к шуму одной из них. Попарные порядки при этом стоит смотреть
    отдельно — регрессия усреднила бы деградацию на хвосте.
    """
    x = np.log(np.asarray(values, dtype=float))
    y = np.log(np.abs(np.asarray(errors, dtype=float)))
    slope = float(np.polyfit(x, y, 1)[0])
    return -slope if inverse else slope


def pairwise_orders(values, errors, inverse: bool = False) -> list[float]:
    """Порядки по каждой соседней паре — контроль на деградацию.

    Регрессия усредняет: если порядок падает к мелким шагам (признак
    систематического члена, который начинает доминировать), в наклоне это
    смазывается, а здесь видно.
    """
    v = np.asarray(values, dtype=float)
    e = np.abs(np.asarray(errors, dtype=float))
    out = []
    for i in range(len(v) - 1):
        k = np.log(e[i + 1] / e[i]) / np.log(v[i + 1] / v[i])
        out.append(float(-k if inverse else k))
    return out


def plot_convergence(values, errors, x_label: str, title: str,
                     out_path: Path, inverse: bool = False,
                     extra_series: dict | None = None,
                     reference_label: str | None = None) -> float:
    """График сходимости в логарифмических осях. Возвращает порядок.

    extra_series — дополнительные кривые {подпись: массив ошибок}, например
    ошибка отдельно в однофазной зоне.
    reference_label — подпись эталонной прямой; по умолчанию строится
    O(шаг) для inverse=False и O(1/N) для inverse=True.
    """
    v = np.asarray(values, dtype=float)
    e = np.abs(np.asarray(errors, dtype=float))
    order = fit_order(v, e, inverse=inverse)

    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.loglog(v, e, 'ko-', linewidth=1.5, markersize=7,
              label=f"ошибка (порядок {order:.2f})")

    for label, series in (extra_series or {}).items():
        ax.loglog(v, np.abs(np.asarray(series, dtype=float)), 's--',
                  linewidth=1.2, markersize=6, markerfacecolor='none',
                  label=label)

    # Эталонная прямая первого порядка, привязанная к последней точке:
    # совпадение наклонов и означает первый порядок.
    power = -1.0 if inverse else 1.0
    if reference_label is None:
        reference_label = r"эталон $O(1/N)$" if inverse else \
            r"эталон $O(\Delta t)$"
    ax.loglog(v, e[-1] * (v / v[-1]) ** power, 'r:', linewidth=1.5,
              label=reference_label)

    ax.set_xlabel(x_label)
    ax.set_ylabel("ошибка")
    ax.set_title(title)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, which="both")

    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"Сохранён: {out_path}")
    return order


def report_series(results, value_label: str, error_key: str = "error",
                  inverse: bool = False) -> float:
    """Печать таблицы серии и порядка. Возвращает порядок.

    Печатает и попарные порядки: регрессия усредняет и скрыла бы
    деградацию на хвосте, если бы она была.
    """
    values = [r["value"] for r in results]
    errors = [r[error_key] for r in results]

    print(f"\n  {value_label:>8}   ошибка")
    for v, e in zip(values, errors):
        print(f"  {v:>8}   {e:.4e}")

    order = fit_order(values, errors, inverse=inverse)
    print(f"\nНаблюдаемый порядок (регрессия): {order:.3f}")
    print("Попарные порядки:", ", ".join(
        f"{v1}→{v2}: {k:.3f}"
        for v1, v2, k in zip(values[:-1], values[1:],
                             pairwise_orders(values, errors,
                                             inverse=inverse))))
    return order
