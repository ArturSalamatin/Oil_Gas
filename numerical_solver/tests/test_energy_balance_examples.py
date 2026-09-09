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


def test_energy_balance_table_pvt():
    """Табличный PVT + табличная ОФП: именно эта конфигурация давала 20 %.

    До фикса BUG-004 невязка была 0.204 на этом же setup. Порог 1e-2 —
    уровень ошибки расщепления O(dt); измеренное значение ~3.6e-3, запас
    примерно втрое.
    """
    bal = _run_balance("04_table_table")
    assert abs(bal["rel_residual"][-1]) < 1e-2


def test_energy_balance_standing_pvt():
    """Standing + Corey: контрольная точка, что фикс не сломал рабочий путь.

    Порог здесь 2e-2, а не 1e-2: у этого примера невязка ~9.4e-3 —
    остаток чисто от расщепления по времени (дрейфом свойств он не был
    поражён, фикс его не уменьшает). При пороге 1e-2 запас был бы 6 %,
    и тест стал бы хрупким к любому изменению сетки или шага.
    """
    bal = _run_balance("03_standing_corey")
    assert abs(bal["rel_residual"][-1]) < 2e-2


def test_energy_balance_no_degassing():
    """Табличный PVT при p_wf > p_b: газ не выделяется, Sg == 0, Rs == const.

    Отдельный режим, потому что в нём отсутствует разгазирование, но дефект
    накопления присутствовал в полной мере (0.209 до фикса) — дрейф
    (rho cp)_eff идёт через rho_o, а не только через Sg.

    ВНИМАНИЕ: cum_deg здесь НЕ равен нулю и не должен — при Rs == const
    конвективная часть телескопируется в -L*rho_g_std*R*(G_o[N] - G_o[0]),
    то есть в поток растворённого газа, втекающего с нефтью через контур и
    уносимого через забой. Дегазации нет, а поток есть; проверять cum_deg
    на ноль было бы ошибкой (см. DEBT-009 и запись BUG-004 в реестре).
    """
    bal = _run_balance("04_table_table", p_wf=16e6)
    assert abs(bal["rel_residual"][-1]) < 1e-2


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
    assert abs(sparse["rel_residual"][-1]) < 2e-2
    assert abs(dense["rel_residual"][-1]) < 2e-2
