r"""DEBT-042, аудит 2: блок тестов шага 2 плана под настоящим pytest — до и после подмены ридеров.

Запуск из numerical_solver/ (основного каталога или worktree):
  & $py -m pytest "$pr\test_plan_block.py" -q -p no:cacheprovider --basetemp "$pr\pytest_tmp" -rfE
  $env:DEBT042_PATCHED = "1"; (то же); Remove-Item Env:DEBT042_PATCHED   # с кодом шага 3 в памяти
Код тестов и реализации берётся из блоков ```python плана; файлы проекта не меняются.
"""
import os
import re
import shutil  # noqa: F401 — нужен блоку тестов
import sys
from pathlib import Path

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/, не из {SOLVER}")
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]

import pytest  # noqa: E402,F401 — нужен блоку тестов
from gpn_multiphase_solver import factory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402,F401

PLAN = Path(__file__).resolve().parents[3] / "plans" / "debt-042 strict-csv-readers.md"
_blocks = re.findall(r"```python\n(.*?)```", PLAN.read_text(encoding="utf-8"), re.S)
if os.environ.get("DEBT042_PATCHED") == "1":
    exec(next(b for b in _blocks if "def _read_numeric_csv" in b), factory.__dict__)

from gpn_multiphase_solver.factory import (  # noqa: E402,F401
    SimulatorFactory, _read_oil_pvt_csv, _read_gas_pvt_csv, _read_relperm_csv,
)

TABLE_CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"
OIL_HEADER = "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
OIL_BRANCH_0 = "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
OIL_BRANCH_30 = "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"

exec(next(b for b in _blocks if "class TestCSVStrictParsing" in b))
print(f"\nКод: {Path(factory.__file__).resolve()}; подмена: {os.environ.get('DEBT042_PATCHED') == '1'}")
