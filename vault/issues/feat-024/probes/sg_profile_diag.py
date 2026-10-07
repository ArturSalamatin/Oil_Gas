"""FEAT-024: разбор profiles.csv примера 14 — S_g по ячейкам, узлы таблицы ОФП.

Запуск (из numerical_solver рабочего дерева .worktrees/feat-024):
    python <этот файл>
"""

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("HydroSolverPrototype/Prototype_1.0.3").resolve()))
sys.path.insert(0, str(Path("examples").resolve()))
from closed_form import Closure  # noqa: E402
from gpn_multiphase_solver.factory import _create_pvt, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

cfg = load_config(Path("examples/14_high_gor_cooling/config.json"))
pvt, rp = _create_pvt(cfg), _create_relperm(cfg)
clo = Closure(pvt, rp, cfg.initial_conditions.Rs0)


def local_gor(p, Sg):
    """Газовый фактор потока через грань, для которой ячейка выше по потоку."""
    out = []
    for pp, s in zip(p, Sg):
        Rs, Bo, mu_o, Bg, mu_g = clo.props(pp)
        S = np.array([s])
        out.append(Rs + rp.krg(S)[0] / rp.kro(S)[0] * mu_o * Bo / (mu_g * Bg))
    return np.array(out)

OUT = Path("examples/14_high_gor_cooling/output/profiles.csv")
rows = list(csv.DictReader(OUT.open(encoding="utf-8")))
steps = sorted({int(r["step"]) for r in rows})


def field(step, key):
    return np.array([float(r[key]) for r in rows if int(r["step"]) == step])


r = field(steps[-1], "r_m")
p360, sg360 = field(12, "p_Pa"), field(12, "Sg")
sg_clo = np.array([clo.Sg(pp) for pp in p360])
gor = local_gor(p360, sg360)
print(f"{'j':>3} {'r, м':>9} {'p, МПа':>8} {'Sg120':>8} {'Sg360':>8} {'Sg_замык':>8} "
      f"{'разн':>8} {'GOR_лок':>8}")
for j in range(len(r)):
    print(f"{j:3d} {r[j]:9.4f} {p360[j] / 1e6:8.4f} {field(4, 'Sg')[j]:8.5f} {sg360[j]:8.5f} "
          f"{sg_clo[j]:8.5f} {sg360[j] - sg_clo[j]:+8.5f} {gor[j]:8.3f}")
