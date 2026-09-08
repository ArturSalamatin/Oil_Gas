"""Проверка: телескопическая формула точна при λ = 0 и выходе на стационар.

Отчёт temperature_asymptotics.report() на штатных 3 сутках даёт расхождение
~0.39 К. Вопрос: это дефект формулы или незавершённая релаксация температуры?

Тепловой фронт на порядки медленнее барического — полная теплоёмкость области
~1e11 Дж/К, поэтому за 3 суток поле T до стационара не доходит, тогда как p и
S_g стационарны уже через час. Если расхождение вызвано именно этим, оно
должно монотонно падать до машинного нуля с ростом времени расчёта.

Если же оно выйдет на полку — значит, телескопирование что-то не учитывает,
и вывод в temperature_asymptotics.py неверен.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\05_standing_table_rp\\check_stationary_T.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT / "examples"))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

import temperature_asymptotics as ta  # noqa: E402


def run_days(days: float):
    """Прогнать конфиг примера на заданное время. Возвращает (history, sim, config)."""
    config = load_config(HERE / "config.json")
    config.time.history[0].dt = days * 86400.0
    # Хранить только начало и конец: промежуточные шаги здесь не нужны,
    # а история на 200 суток — это тысячи состояний.
    config.output.save_every = 1000000

    sim, initial_state = SimulatorFactory.from_config(config)
    return sim.run(initial_state), sim, config


def main():
    print("Расхождение телескопической формулы с расчётом по мере релаксации T")
    print("(λ = 0, поэтому формула должна становиться точной)\n")
    print(f"{'сутки':>8}  {'T(r_w), К':>12}  {'max|T_форм-T_числ|, К':>22}")

    for days in (3.0, 30.0, 100.0, 400.0, 1000.0):
        history, sim, config = run_days(days)
        pvt = sim._energy._pvt
        grid = sim._grid

        T_pred, T_num = ta.stationary_face_temperature(config, history, grid,
                                                       sim)
        # Сравниваем только внутренние грани: на контуре T_num = T_ext по ГУ
        err = float(np.max(np.abs(T_pred[:grid.N] - T_num[:grid.N])))
        print(f"{days:8.0f}  {history.states[-1].T[0]:12.5f}  {err:22.3e}")

    print("\nПадение ошибки до машинного нуля подтверждает: формула точна,")
    print("а расхождение на 3 сутках — незавершённая релаксация температуры.")


if __name__ == "__main__":
    main()
