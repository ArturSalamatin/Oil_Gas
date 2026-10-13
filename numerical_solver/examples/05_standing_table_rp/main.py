"""Сценарий 05: разгазирование, PVT Стендинга + табличные ОФП (комбинация C).

PVT — корреляции Стендинга (Rs0 = 50, p_wf = 8 МПа), ОФП читаются из
relperm.csv. Пример проверяет, что аналитические соотношения двухфазного
стационара держатся при табличном замыкании k_r(S_g).

Что наносится на графики:

  p, Sg, Rs — ставит сам example_runner из общих модулей closed_form.py и
       rs_analytics.py: замкнутое решение (дебит квадратурой, профили без
       единого числа из расчёта) и равновесие Rs: Rs = Rs_eq(p) в ячейках
       с газом, Rs <= Rs_eq(p) в остальных.
       Эти выводы не зависят ни от вида PVT, ни от вида ОФП, поэтому здесь
       не переопределяются.
  T  — однофазная JT-асимптотика и линия фронта разгазирования. В
       двухфазной зоне эталона нет. Аналитика специфична для примера:
       температура зависит от тепловых параметров и в общий модуль не входит.

Теплопроводности в конфиге обнулены. Цена обнуления мала: конвекция
подавляет кондукцию.

Дополнительные проверки запускаются отдельными скриптами — они делают свои
прогоны (серии сеток или шагов по времени) и потому небыстрые:
closed_form_convergence, energy_balance_convergence.
"""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Папка примера — для импорта соседних модулей аналитики.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from example_runner import run_example  # noqa: E402
from relperm_plot import report_relperm  # noqa: E402
from gpn_multiphase_solver.io.figures import save_figure, export_emf  # noqa: E402
from gpn_multiphase_solver.io.output import plot_profiles  # noqa: E402
from gpn_multiphase_solver.diagnostics.two_phase import (  # noqa: E402
    SG_EPS, degassing_front)

import two_phase_analytics as tpa  # noqa: E402
from gpn_multiphase_solver.diagnostics.temperature import single_phase_asymptote  # noqa: E402


def _times_to_plot(history):
    """Те же 4 момента времени, что выбирает example_runner."""
    times = history.times
    idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
    return [times[i] for i in sorted(set(idx))]


def _add_temperature_analytics(history, grid, config, pvt,
                               output_dir: Path, title: str):
    """Перестроить temperature_profiles.png: JT-асимптотика и линия фронта."""
    T_as = single_phase_asymptote(config, history)
    fr = degassing_front(history, grid, config, pvt)
    r = grid.r_centers
    Sg = history.states[-1].Sg
    mask1 = Sg <= SG_EPS

    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, _times_to_plot(history), field="T", ax=ax)

    # Асимптотику рисуем только там, где она выведена — в однофазной зоне.
    ax.semilogx(r[mask1], T_as[mask1], color='gray', linestyle=':',
                linewidth=1.8,
                label=r"JT-асимптотика: $T_{ext} + \mu_{JT,o}(p - p_{ext})$")
    # Линия фронта: слева от неё асимптотика не выведена (двухфазная зона),
    # поэтому пунктир там и не рисуется.
    ax.axvline(fr["r_b_interp"], color='gray', linestyle=':', linewidth=1.5,
               label=rf"фронт $r_b$ = {fr['r_b_interp']:.3f} м "
                     rf"(левее — двухфазная зона)")
    ax.legend(fontsize=8, loc="lower right")
    ax.set_title(f"{title}\nПрофили температуры")
    fig.tight_layout()
    save_figure(fig, output_dir / "temperature_profiles.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    here = Path(__file__).parent
    TITLE = "05: Standing PVT + Table ОФП"

    elapsed, history, grid, config = run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title=TITLE,
    )

    # PVT и ОФП берём из собранного симулятора — те же объекты, что считали задачу.
    from gpn_multiphase_solver.factory import SimulatorFactory
    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim.pvt
    relperm = sim.relperm

    # ОФП — центральный сюжет этого примера.
    # График строит example_runner (output/relperm.png), здесь печатаем числа
    # на рабочем диапазоне, включая отношение k_rg/k_ro из замыкания.
    print()
    report_relperm(config, history, relperm)

    # Проверки, которых нет в общей части: постоянство GOR по всем граням,
    # предсказание наклона Дюпюи из потока (проверка связки PVT ↔ гидродинамика),
    # совпадение двух независимых оценок фронта.
    print()
    tpa.report(history, grid, config, pvt)

    # report_asymptotics вызывает run_example (FEAT-016) — здесь не дублируем.
    print()
    _add_temperature_analytics(history, grid, config, pvt,
                               here / "output", TITLE)
    print("\nГрафик T перестроен с JT-асимптотикой и линией фронта.")

    # Баланс энергии считает run_example — общей проверкой для всех
    # примеров (FEAT-016).

    # Перестроенный выше рисунок — вторым пакетом: первый конвертировал
    # run_example (FEAT-026).
    export_emf(here / "output")
