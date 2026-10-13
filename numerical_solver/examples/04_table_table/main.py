"""Сценарий 04: разгазирование, табличные PVT + табличные ОФП (комбинация B).

Аналитику p, Sg и Rs ставит сам штатный набор run_case
(gpn_multiphase_solver/report/: closed_form.py, rs.py): замкнутое решение не
зависит от того, заданы PVT и ОФП таблицами или корреляциями. Для T
аналитики в двухфазной зоне нет (DEBT-022).

Здесь вызывается только ../two_phase_analytics.report — сводка проверок,
которых нет в графиках: постоянство GOR по граням, наклон профиля из
потока, совпадение двух оценок фронта.
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

if __name__ == "__main__":
    here = Path(__file__).parent

    # Заголовок, число профилей, стационарная аналитика — секция output
    # конфига (FEAT-030)
    r = run_case(here / "config.json", here / "output")

    # PVT — у решателя, который считал задачу (CaseResult, FEAT-030)
    print()
    tpa.report(r.history, r.grid, r.config, r.simulator.pvt)
