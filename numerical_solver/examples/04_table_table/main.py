"""Сценарий 04: разгазирование, табличные PVT + табличные ОФП (комбинация B).

Аналитику p, Sg и Rs ставит сам example_runner из общих модулей
closed_form.py и rs_analytics.py: замкнутое решение не зависит от того,
заданы PVT и ОФП таблицами или корреляциями. Для T аналитики в двухфазной
зоне нет (DEBT-022).

Здесь вызывается только ../two_phase_analytics.report — сводка проверок,
которых нет в графиках: постоянство GOR по граням, наклон профиля из
потока, совпадение двух оценок фронта.
"""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from example_runner import run_example  # noqa: E402

import two_phase_analytics as tpa  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent

    elapsed, history, grid, config = run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="04: Table PVT + Table ОФП",
    )

    # PVT берём из собранного симулятора — тот же объект, что считал задачу.
    from gpn_multiphase_solver.factory import SimulatorFactory
    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim._energy._pvt

    print()
    tpa.report(history, grid, config, pvt)
