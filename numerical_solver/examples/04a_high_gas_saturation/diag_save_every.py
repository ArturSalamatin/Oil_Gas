"""Диагностика: как save_every = 12 влияет на баланс энергии примера 04a.

ЗАЧЕМ. Тесты TestSharedChecks (FEAT-016) считают compute_balance для КАЖДОГО
имени из ALL_EXAMPLES с порогом невязки 1e-2. Но example_runner.py:180
пропускает баланс при save_every != 1, потому что он суммирует приращения
по шагам, а прореженная история их часть теряет. Значит включение 04a в
ALL_EXAMPLES может уронить общий тест — надо измерить, а не гадать.

РЕЗУЛЬТАТ (2026-09-09). Ответ оказался жёстче ожидаемого: compute_balance
не даёт большой невязки, а БРОСАЕТ ValueError — защита стоит явно
(energy_balance.py:124). То есть баланс для 04a не «неточен», а неприменим
по построению, и включение 04a в список тестов баланса уронило бы их не
числом, а исключением.

Отсюда решение (FEAT-015): списки BALANCE_EXAMPLES и TABLE_PVT в
tests/test_examples.py строятся ПО КОНФИГАМ, а не перечислением имён —
пример с прореживанием отсеивается автоматически. Тот же вывод отражён
в README примера, раздел «Временной шаг».

Скрипт печатает невязку баланса для 04a при save_every = 12 (штатный конфиг)
и при save_every = 1 (та же задача, полная история). Первая строка сейчас
завершается исключением — это и есть ожидаемое поведение.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04a_high_gas_saturation\\diag_save_every.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))   # numerical_solver/
sys.path.insert(0, str(HERE.parents[0]))   # examples/

from example_runner import _PROTO_ROOT  # noqa: E402,F401  (подключает прототип)
from energy_balance import compute_balance  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def run(save_every: int):
    """Прогон 04a с заданным save_every. Возвращает (невязка, число шагов).

    Невязка — None, если compute_balance отказался считать: отказ здесь
    ожидаемый исход, а не сбой, и скрипт обязан показать обе строки
    таблицы, а не падать на первой.
    """
    config = load_config(HERE / "config.json")
    config.output.save_every = save_every
    simulator, initial = SimulatorFactory.from_config(config)
    history = simulator.run(initial)
    try:
        bal = compute_balance(history, simulator._grid, config)
    except ValueError as exc:
        print(f"  compute_balance отказался: {exc}")
        return None, len(history.times)
    return abs(float(bal["rel_residual"][-1])), len(history.times)


def main():
    print("== Баланс энергии 04a: влияние save_every ==")
    print("порог теста test_energy_balance_all_examples: 1e-2")
    print()
    print("  save_every   шагов   отн. невязка")
    for se in (12, 1):
        rel, n = run(se)
        shown = "неприменим" if rel is None else f"{rel:.6e}"
        print(f"  {se:9d}   {n:5d}   {shown}")


if __name__ == "__main__":
    main()
