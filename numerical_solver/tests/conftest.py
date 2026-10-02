"""Общие fixtures для тестов gpn_multiphase_solver."""

import os
import sys
from pathlib import Path

import pytest
import numpy as np

# radial_blackoil (прототип коллеги) — не установлен в venv,
# подключается через sys.path. Factory использует ленивые imports.
_PROTO_ROOT = Path(__file__).parent.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROTO_ROOT))

# FEAT-026: SVG- и EMF-копии рисунков нужны только при запуске примеров,
# не в тестах (решение пользователя 2026-10-02): конвертация Inkscape
# добавила бы секунды к каждому run_example и plot_pvt. С "0" save_figure
# пишет только PNG, а export_emf не находит SVG и ничего не делает.
os.environ["GPN_EXAMPLES_EMF"] = "0"
