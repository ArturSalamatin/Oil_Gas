"""Сценарий 03: разгазирование, PVT Стендинга + ОФП Кори (комбинация A).

Двухфазный сценарий. Все аналитики выведены из одного факта:
гидродинамика выходит на стационар за 1-2 часа, а в стационаре компонентные
потоки G^o и G^g постоянны по r. Отсюда следуют GOR = Rs0, алгебраическая
формула для S_g(p) и положение фронта p(r_b) = pb.

Что наносится на графики (overlays):

  p, Sg, Rs — ставит сам штатный набор run_case (gpn_multiphase_solver/report/:
       closed_form.py, rs.py): замкнутое решение (дебит квадратурой, профили p и
       Sg без единого числа из расчёта) и равновесие Rs: Rs = Rs_eq(p) в
       ячейках с газом, Rs <= Rs_eq(p) в остальных.
       Эти выводы не зависят ни от вида PVT, ни от вида ОФП, поэтому
       одинаковы для всех сценариев с газом и здесь не переопределяются.
  T  — JT-асимптотика в однофазной зоне и линия фронта разгазирования.
       В двухфазной зоне эталона нет. Единственная аналитика, специфичная
       для этого примера: температура в общий модуль не входит, потому что
       зависит от тепловых параметров.

       Пошаговой ОДУ-аналитики температуры нет: она требует дивергентной
       дискретизации конвекции, JT и дегазации, а постановка адвективная.

Вывод формул — в gpn_multiphase_solver/diagnostics/ (temperature.py, closed_form.py);
численные подтверждения — в README.md.

Баланс энергии, асимптотику температуры и аналитику двухфазного стационара
считает штатный набор run_case (gpn_multiphase_solver/report/, FEAT-030). Здесь
вызывается только ../two_phase_analytics.report — сводка проверок, которых
нет в графиках: постоянство GOR по граням, наклон Дюпюи из потока,
совпадение двух оценок фронта.
"""

import sys
from pathlib import Path

from gpn_multiphase_solver.cli import configure_batch_run
# Консоль UTF-8 и matplotlib без окна — как у команды (FEAT-030)
configure_batch_run()

# examples/ в sys.path — для two_phase_analytics (печать проверок стационара 03–05)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpn_multiphase_solver.report.pipeline import run_case  # noqa: E402

import two_phase_analytics as tpa  # noqa: E402


def overlay_temperature(ax, history, grid, simulator):
    """JT-асимптотика в однофазной зоне + линия фронта разгазирования.

    Сигнатура (ax, history, grid, simulator) задана run_case. Симулятор
    конфиг не хранит, поэтому перечитываем его из файла рядом.

    Обе кривые от формы дискретизации конвекции не зависят —
    JT-асимптотика выведена для однофазной зоны, где Phi постоянен, а
    фронт определяется давлением насыщения.
    """
    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.diagnostics.two_phase import SG_EPS, degassing_front
    from gpn_multiphase_solver.diagnostics.temperature import single_phase_asymptote

    config = load_config(Path(__file__).resolve().parent / "config.json")
    pvt = simulator.pvt

    # JT-асимптотика рисуется только там, где она выведена, — в однофазной
    # зоне. В двухфазной работает ещё скрытая теплота разгазирования, и
    # замкнутого выражения там нет.
    T_as = single_phase_asymptote(config, history)
    Sg = history.states[-1].Sg
    mask1 = Sg <= SG_EPS
    ax.semilogx(grid.r_centers[mask1], T_as[mask1], color='gray',
                linestyle=':', linewidth=1.8,
                label=r"JT-асимптотика: $T_{ext} + \mu_{JT,o}(p - p_{ext})$")

    fr = degassing_front(history, grid, config, pvt)
    ax.axvline(fr["r_b_interp"], color='gray', linestyle=':', linewidth=1.5,
               label=rf"фронт $r_b$ = {fr['r_b_interp']:.3f} м "
                     rf"(левее — двухфазная зона)")


if __name__ == "__main__":
    here = Path(__file__).parent

    # Заголовок, число профилей, стационарная аналитика — секция output
    # конфига (FEAT-030)
    r = run_case(
        here / "config.json",
        here / "output",
        # Rs здесь не передаём: проверка равновесия Rs не зависит
        # ни от ОФП, ни от источника PVT, поэтому её ставит сам
        # штатный набор (report/rs.py).
        # p, Sg, Rs не передаём: их аналитика общая для всех сценариев с
        # газом, и run_case ставит её сам. Переопределение здесь
        # только отключило бы более полное замкнутое решение.
        overlays={"T": overlay_temperature},
    )

    # PVT — у решателя, который считал задачу (CaseResult, FEAT-030)
    print()
    tpa.report(r.history, r.grid, r.config, r.simulator.pvt)

    # Асимптотику температуры и баланс энергии считает run_case —
    # общими проверками для всех расчётов (FEAT-016).
