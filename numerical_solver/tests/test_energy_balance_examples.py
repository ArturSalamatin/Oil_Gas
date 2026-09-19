"""Регрессия BUG-004: кумулятивный баланс энергии на конфигах примеров.

Существующие тесты (test_val002.py::check_energy_balance) проверяют невязку
СЛАУ — она и до фикса была ~1e-12, потому что решатель самосогласован.
Физический баланс по сохранённой истории не был покрыт ничем, поэтому
BUG-004 прожил незамеченным: скрипт energy_balance.py считал запас энергии
как разность от t=0, а схема дискретизует приращение с множителем cap_j,
стоящим и в матрице, и в правой части. Разность двух выражений — дрейф
(rho cp)_eff, умноженный на абсолютную температуру; на табличном PVT он
систематичен и давал 20 % невязки, не убывающей с шагом по времени.

Конфиги укорочены до 6 ч и N = 25, чтобы тесты шли доли секунды.
"""

import copy
import sys
from pathlib import Path

import pytest

# Прототип radial_blackoil подключает tests/conftest.py. Здесь нужен только
# путь до самого скрипта примеров — в conftest его не тащим, это код
# примеров, а не пакета.
_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
# Модуль общий для всех примеров (FEAT-016): до выноса он лежал в папке
# 03_standing_corey, и путь указывал туда.
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from energy_balance import compute_balance  # noqa: E402

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402


def _run_balance(example: str, p_wf: float | None = None) -> dict:
    """Укороченный прогон конфига примера + баланс энергии.

    6 ч вместо 72 ч и N = 25 вместо 50 — тест должен идти доли секунды.

    Конфиг примера содержит 72 интервала по 3600 с (DEBT-013), поэтому
    длительность задаётся усечением истории до одного интервала: правка
    history[0].dt без усечения укоротила бы только первый час из 72,
    и прогон остался бы 72-часовым — молча, без исключения.
    """
    config = load_config(_EXAMPLES / example / "config.json")
    config.grid.N = 25
    config.time.history = config.time.history[:1]
    config.time.history[0].dt = 21600.0        # 6 ч
    config.output.log_level = "WARNING"
    if p_wf is not None:
        config.time.history[0].p_wf = p_wf

    simulator, initial_state = SimulatorFactory.from_config(config)
    history = simulator.run(initial_state)
    # Длительность прогона — часть контракта теста: при неверном усечении
    # истории тест считал бы другой сценарий и всё равно был бы зелёным.
    assert history.times[-1] == pytest.approx(21600.0)
    return compute_balance(history, simulator._grid, config)


# Порог замыкания баланса. Дискретные уравнения схемы — тождество: если
# все члены выписаны на правильных слоях, баланс сходится точно, и остаются
# только округления прогонки. На укороченном сценарии тестов (6 ч, N = 25)
# измерено 4.0e-14 (пример 03) и 1.2e-13 (пример 04) — запас к порогу
# почти три порядка, а до дефектного значения 9.6e-3 остаётся восемь.
#
# До BUG-007 здесь стояли 1e-2 и 2e-2: невязку считали ошибкой расщепления
# O(dt) и подгоняли порог под наблюдаемые ~1e-3. Ошибки расщепления в
# балансе нет (см. шапку gpn_multiphase_solver/energy/balance.py).
TOL_RESIDUAL = 1e-10


def test_energy_balance_table_pvt():
    """Табличный PVT + табличная ОФП: именно эта конфигурация давала 20 %.

    До фикса BUG-004 невязка была 0.204 на этом же setup, до BUG-007 —
    ~3.6e-3. Теперь это округления прогонки.
    """
    bal = _run_balance("04_table_table")
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


def test_energy_balance_standing_pvt():
    """Standing + Corey: контрольная точка, что фикс не сломал рабочий путь.

    Прежде порог здесь был вдвое мягче остальных (2e-2 против 1e-2):
    невязка ~9.4e-3 считалась неустранимым остатком расщепления, и при
    пороге 1e-2 запас составлял 6 %. После BUG-007 выяснилось, что это был
    не остаток, а дефект: невязка упала до 4.0e-14, и отдельный порог
    больше не нужен.
    """
    bal = _run_balance("03_standing_corey")
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


def test_energy_balance_no_degassing():
    """Табличный PVT при p_wf > p_b: газ не выделяется, Sg == 0, Rs == const.

    Отдельный режим, потому что в нём отсутствует разгазирование, но дефект
    накопления присутствовал в полной мере (0.209 до фикса BUG-004) — дрейф
    (rho cp)_eff идёт через rho_o, а не только через Sg.

    ВНИМАНИЕ: cum_deg здесь НЕ равен нулю и не должен — при Rs == const
    конвективная часть телескопируется в -L*rho_g_std*R*(G_o[N] - G_o[0]),
    то есть в поток растворённого газа, втекающего с нефтью через контур и
    уносимого через забой. Дегазации нет, а поток есть; проверять cum_deg
    на ноль было бы ошибкой (см. DEBT-009 и запись BUG-004 в реестре).
    """
    bal = _run_balance("04_table_table", p_wf=16e6)
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


@pytest.mark.parametrize("example", ["03_standing_corey", "04_table_table"])
def test_balance_independent_of_history_structure(example):
    """Накопленные члены не зависят от того, как часто пишется история.

    Ключевой тест части B (DEBT-013). Раньше на этом месте стоял тест
    обратного смысла: compute_balance ОТВЕРГАЛ разреженную историю, потому
    что суммировал приращения (T^n - T^{n-1}) по сохранённым шагам, и при
    пропуске шагов сумма занижалась. Теперь члены копятся на подшагах
    внутри решателя, поэтому структура истории на них не влияет вовсе.

    Один и тот же сценарий (6 ч, dt_integration из конфига) считается
    двумя способами: одной записью на весь прогон и шестью почасовыми.
    Суммируются одни и те же вклады подшагов, поэтому финальные значения
    обязаны совпасть с точностью до накопления ошибок сложения.
    """
    def run(n_intervals: int):
        config = load_config(_EXAMPLES / example / "config.json")
        config.grid.N = 25
        iv = copy.deepcopy(config.time.history[0])
        config.time.history = [copy.deepcopy(iv) for _ in range(n_intervals)]
        for h in config.time.history:
            h.dt = 21600.0 / n_intervals
        config.output.log_level = "WARNING"

        simulator, initial_state = SimulatorFactory.from_config(config)
        history = simulator.run(initial_state)
        assert history.n_saved == n_intervals + 1
        return compute_balance(history, simulator._grid, config)

    sparse = run(1)     # одна запись на весь прогон
    dense = run(6)      # почасовые записи

    for key in ("delta_E", "cum_adiab", "cum_conv",
                "cum_jt", "cum_deg", "cum_cond"):
        assert sparse[key][-1] == pytest.approx(dense[key][-1], rel=1e-10), key

    # Невязка проходит порог при обеих структурах — раньше разреженная
    # история давала на два-три порядка хуже.
    assert abs(sparse["rel_residual"][-1]) < TOL_RESIDUAL
    assert abs(dense["rel_residual"][-1]) < TOL_RESIDUAL


# ──────────────────────────────────────────────────────────────
# Регрессия BUG-007: конвективный член на слое T^{n+1}
# ──────────────────────────────────────────────────────────────


def test_convection_uses_implicit_temperature():
    """Баланс замыкается с машинной точностью на Standing-PVT.

    Прямой регрессор BUG-007. Схема НЕЯВНАЯ: Phi+/Phi- стоят в матрице
    СЛАУ при неизвестных T^{n+1}, а накопитель баланса умножал их на T^n.
    Ошибка ~Phi*(T^{n+1}-T^n)*dt за подшаг систематична, пока идёт
    охлаждение, поэтому копилась: 9.6e-3 против самосогласованности
    схемы 5.5e-13.

    На дефектном коде даёт ~9.6e-3 — мимо порога на восемь порядков
    (проверено откатом правки).
    """
    bal = _run_balance("03_standing_corey")
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


def test_convection_implicit_table_pvt():
    """То же на табличном PVT — вторая ветвь по источнику свойств.

    Источник PVT был разделительной линией в BUG-004 (20 % на таблице
    против 1 % на Стендинге), поэтому обе ветви проверяются раздельно:
    дефект, проявляющийся только на одной из них, иначе прошёл бы мимо.
    """
    bal = _run_balance("04_table_table")
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


def test_accumulation_without_substep_raises():
    """add_accumulation без парного add_substep обязана бросить RuntimeError.

    Контракт двухфазного накопления (DEBT-013): коэффициенты подшага
    приходят в первой фазе, применяются во второй. При рассогласовании фаз
    Phi остались бы от ПРЕДЫДУЩЕГО подшага, и конвективный вклад
    посчитался бы по чужим коэффициентам — молча, без признаков.

    Без явной проверки падение всё равно произошло бы, но с невнятным
    "TypeError: unsupported operand type(s) for *: 'NoneType' and 'float'"
    на гашеном _dt_substep. Явное сообщение называет причину.
    """
    import numpy as np

    from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator
    from gpn_multiphase_solver.grid.log_radial import LogRadialGrid

    # Сетка-минимум: значения роли не играют, нужны лишь N и volumes.
    grid = LogRadialGrid(0.1, 100.0, 10.0, 5, 1e-14)
    acc = EnergyBalanceAccumulator(grid)

    T_new = np.full(5, 350.0)
    T_prev = np.full(5, 351.0)
    rho_cp_eff = np.full(5, 2.0e6)

    with pytest.raises(RuntimeError, match="add_substep"):
        acc.add_accumulation(T_new, T_prev, rho_cp_eff, dt=3600.0)

    # Состояние не тронуто: проверка стоит до любых накоплений, поэтому
    # прерванный вызов не оставляет накопитель частично обновлённым.
    assert acc.delta_E == 0.0
    assert acc.cum_cond == 0.0
