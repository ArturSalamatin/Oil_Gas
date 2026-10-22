@echo off
rem Setup of gpn-multiphase-solver for development (Windows): finds Python 3.10+,
rem creates .venv next to this file if absent, installs both packages in
rem editable mode with test and documentation tools, checks the command.
rem Messages are in English: cmd prints UTF-8 Cyrillic as garbage (codepage 866).
rem Python is not installed by this script; PyPI (or a mirror) must be reachable.
rem After moving this directory run the script again: editable installs keep paths.
setlocal
pushd "%~dp0"
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1 && set "PY=python"
if not defined PY (
    echo Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and run setup.bat again.
    goto fail
)
if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv with %PY% ...
    %PY% -m venv .venv || goto fail
)
echo Installing radial-blackoil and gpn-multiphase-solver[dev] ...
".venv\Scripts\python.exe" -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]" || goto fail
".venv\Scripts\python.exe" -m gpn_multiphase_solver run --help >nul || goto fail
echo Done. Run: .venv\Scripts\python -m gpn_multiphase_solver run path\to\config.json
popd
exit /b 0
:fail
echo Setup failed.
popd
exit /b 1
