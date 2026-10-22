"""DEBT-063, проба: запустить скрипт примера с текущими центрами или с √.

    python run_with_centers.py <скрипт.py> base|sqrt

sqrt — до импорта скрипта подменить функцию центров LogRadialGrid на
среднее геометрическое граней (как у прототипа). Скрипт исполняется через
runpy как __main__, со своим __file__ — пути внутри него работают как при
обычном запуске. Запускать из numerical_solver/.
"""

import runpy
import sys
from pathlib import Path

SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER))
script, mode = sys.argv[1], sys.argv[2]
if mode == "sqrt":
    import numpy as np
    import gpn_multiphase_solver.grid.log_radial as lr
    name = next(n for n in ("_cell_centers_mass", "_cell_centers_log_average")
                if hasattr(lr, n))
    setattr(lr, name, lambda a, b: np.sqrt(a * b))
import gpn_multiphase_solver as _g
import radial_blackoil as _r
# Какие пакеты взяты: в worktree оба должны быть из worktree (правило 3 /implement)
print(f"[{mode}] {Path(script).resolve()}\n[{mode}] пакеты: {_g.__file__} | {_r.__file__}",
      flush=True)
sys.argv = [script]
runpy.run_path(script, run_name="__main__")
