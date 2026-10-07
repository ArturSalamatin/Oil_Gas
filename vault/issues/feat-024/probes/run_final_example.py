"""FEAT-024: полный конвейер run_example на данных probes/<папка>/ — печать для README.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-024\\probes\\run_final_example.py [папка]
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from example_runner import run_example  # noqa: E402

d = HERE / (sys.argv[1] if len(sys.argv) > 1 else "final")
# Без стационара на профиле S_g — решение пользователя 2026-09-30 (как у 13a)
run_example(config_path=d / "config.json", output_dir=d / "output",
            title="14: высокий газовый фактор — охлаждение забоя",
            overlays={"Sg": None})
