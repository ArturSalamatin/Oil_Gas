"""Сценарий 05: разгазирование, PVT Стендинга + табличные ОФП (комбинация C).

Физический режим совпадает с примером 03 (те же PVT, Rs0 = 50, p_wf = 8 МПа);
отличается ровно один модуль — ОФП читаются из relperm.csv вместо формул Кори.
Поэтому здесь проверяется не новая физика, а то, что все аналитические
соотношения двухфазного стационара держатся при смене замыкания k_r(S_g).

Что наносится на графики:

  p, Sg, Rs — ставит сам example_runner из общих модулей closed_form.py и
       rs_analytics.py: замкнутое решение (дебит квадратурой, профили без
       единого числа из расчёта) и равновесие Rs = min(Rs_eq(p), Rs0).
       Эти выводы не зависят ни от вида PVT, ни от вида ОФП, поэтому здесь
       не переопределяются.
  T  — ОДУ первого порядка на каждом моменте времени плюс однофазная
       JT-асимптотика. Единственная аналитика, специфичная для примера:
       температура зависит от тепловых параметров и в общий модуль не входит.

Теплопроводности в конфиге обнулены, как в примерах 03, 04, 06-09: ОДУ для
T выводится при lambda = 0, иначе задача становится краевой и аналитика —
приближённой. Цена проверена: при lambda != 0 порядок сходимости ОДУ по
сетке падает с 1.05 до 0.92 (ode_grid_convergence.py).

Дополнительные проверки запускаются отдельными скриптами — они делают свои
прогоны (до 1000 суток либо на мелких сетках) и потому небыстрые:
compare_with_corey, check_stationary_T, closed_form_convergence,
energy_balance_convergence, ode_grid_convergence.
"""

import sys
from pathlib import Path

import numpy as np

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Папка примера — для импорта соседних модулей аналитики.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from example_runner import run_example  # noqa: E402
from relperm_plot import report_relperm  # noqa: E402
from gpn_multiphase_solver.io.output import plot_profiles  # noqa: E402

import two_phase_analytics as tpa  # noqa: E402
import temperature_asymptotics as ta  # noqa: E402
import temperature_ode as tode  # noqa: E402


def _times_to_plot(history):
    """Те же 4 момента времени, что выбирает example_runner."""
    times = history.times
    idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
    return [times[i] for i in sorted(set(idx))]


def _add_temperature_analytics(history, grid, config, pvt, energy_solver,
                               output_dir: Path, title: str):
    """Перестроить temperature_profiles.png: ОДУ на каждом моменте + асимптотика."""
    T_as = ta.single_phase_asymptote(config, history)
    fr = tpa.degassing_front(history, grid, config, pvt)
    r = grid.r_centers
    Sg = history.states[-1].Sg
    mask1 = Sg <= tpa.SG_EPS

    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, _times_to_plot(history), field="T", ax=ax)

    # ОДУ-аналитика на тех же моментах. Рекуррентное решение до последнего
    # рисуемого шага — один проход, решения снимаются по дороге.
    times = history.times
    plot_idx = sorted(set([0, len(times) // 3,
                           2 * len(times) // 3, len(times) - 1]))
    print("Решение ОДУ для температуры...")
    ode_sol = tode.solve_ode_at_steps(history, config, grid, energy_solver,
                                      steps=plot_idx)
    for n in plot_idx:
        if n == 0:
            continue
        r_o, T_o = ode_sol[n]
        ax.semilogx(r_o, T_o, 'k--', linewidth=1.1)
    ax.semilogx([], [], 'k--', linewidth=1.1, label="ОДУ-аналитика")

    print("Аналитика T (ОДУ vs численное):")
    for n in plot_idx:
        if n == 0:
            continue
        r_o, T_o = ode_sol[n]
        err = np.max(np.abs(history.states[n].T - np.interp(r, r_o, T_o)))
        print(f"  t = {times[n]:8.0f} с (шаг {n:3d}): "
              f"max|T_num - T_ode| = {err:.4f} К")

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
    fig.savefig(output_dir / "temperature_profiles.png", dpi=110)
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
    pvt = sim._energy._pvt
    relperm = tpa._build_relperm(config)

    # ОФП — центральный сюжет этого примера: именно её вид отличает 05 от 03.
    # График строит example_runner (output/relperm.png), здесь печатаем числа
    # на рабочем диапазоне, включая отношение k_rg/k_ro из замыкания.
    print()
    report_relperm(config, history, relperm)

    # Проверки, которых нет в общей части: постоянство GOR по всем граням,
    # предсказание наклона Дюпюи из потока (проверка связки PVT ↔ гидродинамика),
    # совпадение двух независимых оценок фронта.
    print()
    tpa.report(history, grid, config, pvt)

    print()
    # report_asymptotics вызывает run_example (FEAT-016) — здесь не дублируем.

    _add_temperature_analytics(history, grid, config, pvt, sim._energy,
                               here / "output", TITLE)
    print("\nГрафик T перестроен с ОДУ-аналитикой.")

    # Баланс энергии считает run_example — общей проверкой для всех
    # примеров (FEAT-016).
