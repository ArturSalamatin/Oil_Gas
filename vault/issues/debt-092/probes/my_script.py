"""Вызов из собственного скрипта по примеру README на копии поставки."""

from pathlib import Path
import sys

here = Path(__file__).resolve().parent
solver = here / "acceptance" / "gpn-multiphase-solver-1.0.7"
sys.path.insert(0, str(solver))
sys.path.insert(0, str(solver / "HydroSolverPrototype/Prototype_1.0.3"))

import gpn_multiphase_solver
import radial_blackoil
from gpn_multiphase_solver.cli import configure_batch_run
from gpn_multiphase_solver.report.pipeline import run_case

configure_batch_run()
print(gpn_multiphase_solver.__file__)
print(radial_blackoil.__file__)
result = run_case("my_case/config.json", "my_case/output", title="Скважина 1")
well = result.history.well_data[-1]
print("Забойная температура, К:", well.T_wf)
print("Дебит нефти, м³ст/сут:", well.q_o_std * 86400)
