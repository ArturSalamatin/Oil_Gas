"""Почему ошибка T у примера 10 немонотонна по dt?

Гипотеза: дело не в тепловом шаге, а в ГИДРО-части — при разных dt
цикл active set переводит в двухфазный режим разное число ячеек, и
профиль Sg/p слегка "дёргается". Тогда немонотонность видна уже в p и Sg,
а не только в T.
"""
import sys
from pathlib import Path

ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
for p in (str(ROOT), str(ROOT / "examples"),
          str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def run(example, dt):
    cfg = load_config(ROOT / "examples" / example / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    s = hist.states[-1]
    return (np.array(s.T, float), np.array(s.p, float),
            np.array(s.Sg, float), np.array(s.Rs, float))


EXAMPLE = sys.argv[1] if len(sys.argv) > 1 else "10_deep_degassing"
DTS = [3600.0, 1800.0, 900.0, 450.0]
REF_DT = 225.0

Tr, pr, Sgr, Rsr = run(EXAMPLE, REF_DT)
print(f"=== {EXAMPLE}: расхождение с эталоном dt={REF_DT} по всем полям ===")
print(f"{'dt':>8s} {'max|dT|,K':>13s} {'max|dp|,Па':>13s} "
      f"{'max|dSg|':>13s} {'max|dRs|':>13s} {'яч. с газом':>12s}")
for dt in DTS:
    T, p, Sg, Rs = run(EXAMPLE, dt)
    ncell = int(np.count_nonzero(Sg > 1e-12))
    print(f"{dt:8.1f} {np.max(np.abs(T-Tr)):13.4e} {np.max(np.abs(p-pr)):13.4e} "
          f"{np.max(np.abs(Sg-Sgr)):13.4e} {np.max(np.abs(Rs-Rsr)):13.4e} "
          f"{ncell:12d}")
print(f"{'эталон':>8s} {'—':>13s} {'—':>13s} {'—':>13s} {'—':>13s} "
      f"{int(np.count_nonzero(Sgr > 1e-12)):12d}")
