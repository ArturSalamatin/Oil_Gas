"""Невязка баланса энергии на серии Δt — общая проверка для всех примеров.

СМЫСЛ ПРОВЕРКИ. Баланс должен замыкаться на уровне машинной точности при
ЛЮБОМ Δt. Дискретные уравнения схемы — тождество: если все члены выписаны
на правильных слоях и с правильными коэффициентами, сумма источников
равна изменению запаса точно, а не приближённо. Остаётся лишь арифметика
с плавающей точкой. Любое превышение TOL означает дефект в члене.

Серия по Δt, а не один прогон: дефектный член обычно ЗАВИСИТ от шага, и
эта зависимость — сильнейший диагностический признак. Она же показывает,
что порог выдерживается не случайно.

ПОРЯДОК ПО Δt ЗДЕСЬ ОТРИЦАТЕЛЕН: невязка медленно РАСТЁТ при измельчении
шага. Это подпись округлений, а не аппроксимации. Зависимость от числа
подшагов немонотонна, поэтому дело не в «больше подшагов — больше
сложений», а в катастрофическом сокращении: невязка есть разность
кумулятивных сумм порядка 1e9–1e10 Дж. Само представление 6e9 в double
несёт неопределённость 6e9·eps ≈ 1.3e-6 Дж, и накопленная за сотни
подшагов она даёт наблюдаемые доли джоуля. Невязка меряется на уровне
шума представления самих кумулятивных сумм, поэтому её значение —
случайная величина, а не сигнал.

Практическое следствие: при мелком шаге невязка выходит на плато ~1e-10
и дальше отражает только точность double. Порог ниже этого уровня
выставлять нельзя, измельчать шаг ради чистого баланса — тоже
бессмысленно. Строже лечится суммированием Кэхэна в аккумуляторах
energy/balance.py, а не ужесточением порога.
Разбор: vault/knowledge/numerics/
невязка баланса энергии упирается в сокращение больших чисел.md

Расщепление при этом O(Δt) — но оно влияет на САМО РЕШЕНИЕ T, а не на
замыкание дискретного баланса. Проверять его порядок надо сходимостью T
по Δt, а не невязкой баланса.

ПРИЗНАК ДЕФЕКТА — невязка выше уровня округлений. Член, выписанный
неверно или взятый не на том временном слое, даёт невязку порядка 1e-3 и
выше — на много порядков над порогом.

ТРИ ТОЧКИ НУЖНЫ: они показывают, что уровень держится во всём рабочем
диапазоне Δt, а не подобран под один шаг.

Уровень невязки: при штатном Δt = 3600 с — до ~1e-11, при самом мелком
Δt = 360 с — до ~1.5e-10. Порог 1e-9 берётся по худшему шагу серии и даёт
запас примерно порядок.

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
# fit_order не импортируется: порядок невязки по Δt отрицателен и смысла
# не несёт, проверяется уровень (см. шапку модуля).
from convergence import run_series  # noqa: E402
from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402
from figure_io import save_figure, export_emf  # noqa: E402

# Шаги по времени, с. Диапазон в 10 раз: проверяем, что уровень невязки
# держится и при штатном шаге, и при десятикратно меньшем.
DT_LIST = [3600, 900, 360]

# Порог замыкания баланса. Невязка растёт при измельчении шага (сокращение
# больших чисел, см. шапку модуля): до ~1e-11 при штатном Δt = 3600 с и до
# ~1.5e-10 при самом мелком Δt = 360 с. Поэтому порог привязан к худшему
# шагу серии, а не к штатному: запас примерно порядок над 1.5e-10.
TOL_RESIDUAL = 1e-9


def _apply_dt(config, dt):
    """Выставить шаг интегрирования.

    Частоту вывода задаёт структура time.history, общая для всех
    прогонов, поэтому моменты записи совпадают у всех dt по построению,
    а внутри интервала укладывается dt_hist/dt подшагов — тем больше, чем
    мельче шаг.
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
    """Двухпанельный график: невязка во времени + уровень против Δt.

    Возвращает (максимальная финальная невязка по серии, максимальная
    мгновенная невязка по серии) — обе должны быть ниже TOL_RESIDUAL.
    Порядок сходимости не возвращается: для невязки баланса он смысла не
    несёт (см. шапку модуля).
    """
    dt_arr = np.array([r["value"] for r in results], dtype=float)
    fin_arr = np.array([r["final_rel"] for r in results])
    max_arr = np.array([r["max_rel"] for r in results])

    worst_fin = float(np.max(fin_arr))
    worst_max = float(np.max(max_arr))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    colors = ['b', 'g', 'r', 'c', 'm']
    for bal, col in zip(results, colors):
        # Время по оси — в сутках (FEAT-022); Δt в легенде — шаг
        # интегрирования, численный параметр, а не время: остаётся в секундах.
        ax1.plot(bal["t"] * S_TO_DAY, bal["rel_residual"], col, linewidth=1.3,
                 label=f"Δt = {bal['value']} с (max {bal['max_rel']:.1e})")
    ax1.set_xlabel("Время, сут")
    ax1.set_ylabel(r"|невязка| / |$\Delta E$|")
    ax1.set_title("Невязка баланса энергии во времени")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    ax2.loglog(dt_arr, fin_arr, 'ko-', linewidth=1.5, markersize=7,
               label="финальная")
    ax2.loglog(dt_arr, max_arr, 'ks--', linewidth=1.2, markersize=6,
               markerfacecolor='none', label="максимальная")
    # Горизонталь порога: проверяется УРОВЕНЬ, а не наклон. Наклон здесь
    # отрицателен (округления копятся с числом подшагов) и смысла не несёт.
    ax2.axhline(TOL_RESIDUAL, color='r', linestyle=':', linewidth=1.5,
                label=f"порог {TOL_RESIDUAL:.0e}")
    ax2.set_xlabel("Δt, с")
    ax2.set_ylabel("относительная невязка")
    ax2.set_title(f"Замыкание баланса против Δt{title_suffix}")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, which="both")

    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "energy_balance_convergence.png"
    # Стираем результат прошлого прогона. Остальные файлы в output/ пишет
    # main.py примера, и трогать их нельзя: этот скрипт их не восстановит.
    out_path.unlink(missing_ok=True)
    save_figure(fig, out_path, dpi=130)
    plt.close(fig)
    print(f"\nСохранён: {out_path}")

    print("\n  dt, с   финальная    максимальная")
    for bal in results:
        print(f"  {bal['value']:6d}   {bal['final_rel']:.3e}    "
              f"{bal['max_rel']:.3e}")

    verdict = "OK" if worst_fin < TOL_RESIDUAL else "ПРОВАЛ"
    print(f"\nХудшая финальная невязка по серии: {worst_fin:.3e} "
          f"(порог {TOL_RESIDUAL:.0e}) — {verdict}")
    if worst_fin >= TOL_RESIDUAL:
        print("  Баланс не замыкается: какой-то член выписан неверно либо "
              "взят не на том временном слое.")
    return worst_fin, worst_max


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

    worst_fin, _ = plot_balance_convergence(results, folder / "output",
                                            f" — {folder.name}")
    # SVG рисунка — в EMF до выхода по коду возврата (FEAT-026).
    export_emf(folder / "output")
    # Ненулевой код возврата, чтобы запуск из скрипта или CI отличал
    # незамкнувшийся баланс от успешного прогона.
    raise SystemExit(0 if worst_fin < TOL_RESIDUAL else 1)
