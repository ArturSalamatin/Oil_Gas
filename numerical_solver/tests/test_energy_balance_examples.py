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

import sys
from pathlib import Path

import pytest

# Прототип radial_blackoil подключает tests/conftest.py. Здесь нужен только
# путь до самого скрипта примеров — в conftest его не тащим, это код
# примеров, а не пакета.
_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
_BALANCE_SRC = _EXAMPLES / "03_standing_corey"
if str(_BALANCE_SRC) not in sys.path:
    sys.path.insert(0, str(_BALANCE_SRC))

from energy_balance import compute_balance  # noqa: E402

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402


def _run_balance(example: str, p_wf: float | None = None) -> dict:
    """Укороченный прогон конфига примера + баланс энергии.

    6 ч вместо 72 ч и N = 25 вместо 50 — тест должен идти доли секунды.
    save_every = 1 обязателен: баланс суммирует приращения по шагам.
    """
    config = load_config(_EXAMPLES / example / "config.json")
    config.grid.N = 25
    config.time.history[0].dt = 21600.0        # 6 ч
    config.output.save_every = 1
    config.output.log_level = "WARNING"
    if p_wf is not None:
        config.time.history[0].p_wf = p_wf

    simulator, initial_state = SimulatorFactory.from_config(config)
    history = simulator.run(initial_state)
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
def test_compute_balance_rejects_sparse_history(example):
    """save_every > 1 должен отвергаться, а не давать молча неверную сумму.

    Баланс суммирует приращения (T^n - T^{n-1}) по сохранённым шагам:
    при прореженной истории часть приращений выпадает и сумма занижается.
    """
    config = load_config(_EXAMPLES / example / "config.json")
    config.grid.N = 25
    config.time.history[0].dt = 21600.0
    config.output.save_every = 1
    config.output.log_level = "WARNING"

    simulator, initial_state = SimulatorFactory.from_config(config)
    history = simulator.run(initial_state)

    config.output.save_every = 5
    with pytest.raises(ValueError, match="save_every"):
        compute_balance(history, simulator._grid, config)
