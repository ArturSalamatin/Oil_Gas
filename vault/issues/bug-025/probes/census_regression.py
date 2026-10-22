"""BUG-025 (планирование): меняет ли предел округления в допуске KAPPA*eps*M_max/dt решения регрессии прототипа.

Предел округления меняет допуск решения, только если KAPPA > kappa* = atol*dt/(eps*M_max). Для каждого кейса
регрессии (T00–T11, T05): M_max — наибольший запас ячейки (нефть; газ / s_g) на начальном
состоянии и при давлении внешней границы (у неё самая крупная ячейка, а давление близко к
p_outer), dt — наименьший шаг эталонного журнала regression/golden/<кейс>/step_log.csv
(все попытки, и отвергнутые). Оценка: M_max по ходу расчёта меняется мало (внешняя ячейка —
у границы с заданным давлением), проверка — регрессия при реализации.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-025\\probes\\census_regression.py
"""
import csv
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
assert PROTO.is_dir(), "запускать из numerical_solver/"
sys.path.insert(0, str(PROTO))

from radial_blackoil.input_reader import load_input              # noqa: E402
from radial_blackoil.grid import RadialGrid                      # noqa: E402
from radial_blackoil.rock import CompressibleRock                # noqa: E402
from radial_blackoil.blackoil import RadialBlackOilModel         # noqa: E402
from radial_blackoil.state import BlackOilState                  # noqa: E402

EPS = float(np.finfo(float).eps)
ATOL = 1e-11
REG = PROTO / "regression"


def m_max(path):
    """M_max (м³ст) кейса: начальное состояние и то же при давлении внешней границы — большее."""
    inp = load_input(path)
    p = inp.params
    g = RadialGrid(float(p['Well radius rw']), float(p['Outer radius re']), float(p['Formation thickness h']),
                   int(p['Grid cells N']), float(p['Absolute permeability']))
    r = CompressibleRock(float(p['Reference porosity']), float(p['Reference pressure']),
                         float(p['Rock compressibility cr']))
    m = RadialBlackOilModel(g, r, inp.pvt, inp.relperm, float(p['Outer-boundary pressure']),
                            float(p['Outer-boundary pressure']), float(p['Initial dissolved gas Rs']))
    out = []
    for p0 in (float(p['Initial pressure']), float(p['Outer-boundary pressure'])):
        s = BlackOilState.undersaturated(g.n, p0, float(p['Initial dissolved gas Rs']))
        oi, gi = m.component_inventories(s)
        out.append(max(float(np.max(oi)), float(np.max(gi)) / m.gas_residual_scale))
    return max(out), g.n, float(p['Outer radius re'])


for log in sorted((REG / "golden").glob("**/step_log.csv")):
    case = log.parent.name
    xlsx = REG / "inputs" / ("T05/" if case.startswith("T05") else "") / f"{case}.xlsx"
    with open(log, newline="") as fh:
        dt = min(float(row["dt_s"]) for row in csv.DictReader(fh))
    M, n, re = m_max(xlsx)
    k = ATOL * dt / (EPS * M)
    print(f"{case:18s} N = {n:4d}, r_e = {re:7.1f} м, M_max = {M:.3e} м³ст, min dt = {dt:8.4g} с, "
          f"kappa* = {k:9.3g}  (предел округления при KAPPA = 4 {'МЕНЯЕТ' if k < 4 else 'не меняет'} допуск)")
