# Distribution version (pip): Prototype 1.0.3 + local changes of the GPN
# project, set N = the number after "+gpn." (CHANGELOG_1.0.3.md, DEBT-059);
# tools/release.py raises N at a solver release if this package changed
# (FEAT-038). numerical_solver/pyproject.toml requires radial-blackoil of
# exactly this version. Keep a plain literal: setuptools reads it without
# importing the package. build_info.VERSION ('1.0.3') is the version written
# to run_summary and compared by the regression with the golden outputs; it
# is unchanged.
__version__='1.0.3+gpn.1'
from .input_reader import load_input, InputValidationError
from .runner import run_workbook
