"""Сценарий 03: разгазирование, PVT Стендинга + ОФП Кори (комбинация A).

Первый двухфазный пример. Все аналитики выведены из одного факта:
гидродинамика выходит на стационар за 1-2 часа, а в стационаре компонентные
потоки G^o и G^g постоянны по r. Отсюда следуют GOR = Rs0, алгебраическая
формула для S_g(p) и положение фронта p(r_b) = pb.

Что наносится на графики (overlays):

  p, Sg, Rs — ставит сам example_runner из общих модулей closed_form.py и
       rs_analytics.py: замкнутое решение (дебит квадратурой, профили p и
       Sg без единого числа из расчёта) и равновесие Rs = min(Rs_eq(p), Rs0).
       Эти выводы не зависят ни от вида PVT, ни от вида ОФП, поэтому
       одинаковы для всех сценариев с газом и здесь не переопределяются.
  T  — ОДУ первого порядка (двухфазный аналог примера 02) на каждом моменте
       плюс JT-асимптотика, нарисованная только там, где она выведена.
       Единственная аналитика, специфичная для этого примера: температура в
       общий модуль не входит, потому что зависит от тепловых параметров.

Вывод формул — в docstring temperature_ode.py и temperature_asymptotics.py,
а также ../closed_form.py; численные подтверждения — в README.md.
Модуль two_phase_analytics.py остаётся: он проверяет то, чего нет в общей
части — постоянство GOR по граням, наклон Дюпюи из потока, совпадение
двух оценок фронта.
"""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Папка примера — для импорта соседних модулей аналитики.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from example_runner import run_example  # noqa: E402

import two_phase_analytics as tpa  # noqa: E402
import temperature_asymptotics as ta  # noqa: E402
from temperature_ode import overlay_temperature  # noqa: E402
from energy_balance import plot_energy_balance  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    TITLE = "03: Standing + Corey"

    elapsed, history, grid, config = run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title=TITLE,
        # Rs здесь не передаём: проверка min(Rs_eq(p), Rs0) не зависит
        # ни от ОФП, ни от источника PVT, поэтому её ставит сам
        # example_runner из общего модуля rs_analytics.py.
        # p, Sg, Rs не передаём: их аналитика общая для всех сценариев с
        # газом, и example_runner ставит её сам. Переопределение здесь
        # только отключило бы более полное замкнутое решение.
        overlays={"T": overlay_temperature},
    )

    # PVT берём из собранного симулятора — тот же объект, что считал задачу.
    from gpn_multiphase_solver.factory import SimulatorFactory
    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim._energy._pvt

    print()
    tpa.report(history, grid, config, pvt)

    print()
    ta.report(history, config, pvt, grid)

    print()
    plot_energy_balance(history, grid, config, here / "output")
