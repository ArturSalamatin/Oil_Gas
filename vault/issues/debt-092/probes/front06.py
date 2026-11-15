"""Сравнение трёх определений фронта примера 06 на копии поставки."""

from pathlib import Path
import platform
import sys

root = Path(__file__).resolve().parent / "acceptance" / "gpn-multiphase-solver-1.0.7"
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "HydroSolverPrototype" / "Prototype_1.0.3"))

import numpy as np
import scipy
import gpn_multiphase_solver as solver
import radial_blackoil as prototype
from gpn_multiphase_solver.diagnostics.closed_form import solve_closed
from gpn_multiphase_solver.diagnostics.rs import front_radius
from gpn_multiphase_solver.diagnostics.two_phase import degassing_front
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

print("Python", platform.python_version(), "numpy", np.__version__, "scipy", scipy.__version__)
print("solver", solver.__file__)
print("prototype", prototype.__file__)
config = load_config(root / "examples/06_table_corey_rp/config.json")
simulator, initial = SimulatorFactory.from_config(config)
history = simulator.run(initial)
closed = solve_closed(config, simulator.pvt, simulator.relperm, simulator.grid.r_centers)
numeric = front_radius(config, history, simulator.grid, simulator.pvt)
fronts = degassing_front(history, simulator.grid, config, simulator.pvt)
print("closed", closed["r_b"], "numeric", numeric, "dupuit", fronts["r_b_formula"])
