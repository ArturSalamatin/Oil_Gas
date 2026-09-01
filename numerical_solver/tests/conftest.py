"""Общие fixtures для тестов gpn_multiphase_solver."""

import sys
from pathlib import Path

import pytest
import numpy as np

# radial_blackoil (прототип коллеги) — не установлен в venv,
# подключается через sys.path. Factory использует ленивые imports.
_PROTO_ROOT = Path(__file__).parent.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROTO_ROOT))
