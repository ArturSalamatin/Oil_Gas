"""BUG-021: пример 13b целиком (как examples/13b_pwf_alternating/main.py) с выводом в probes/out_13b_<метка>.

Нужен для чисел README 13b, которых нет в истории: баланс энергии (члены за 30 сут, невязка).
Вывод примера в основном дереве не трогается.

Запуск — из каталога numerical_solver:
    .venv\\Scripts\\python <P>\\run_13b.py base
    .venv\\Scripts\\python <P>\\run_13b.py v2      # с подменой варианта 2
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT / "examples"))
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(HERE))
os.environ.setdefault("GPN_EXAMPLES_EMF", "0")   # без EMF (FEAT-026): Inkscape не нужен

tag = sys.argv[1]
if tag == "v2":
    import planned_code
    planned_code.apply(2)

from example_runner import run_example  # noqa: E402

ex = SOLVER_ROOT / "examples" / "13b_pwf_alternating"
run_example(config_path=ex / "config.json", output_dir=HERE / f"out_13b_{tag}",
            title="13b: чередование забойного давления 6 ↔ 10.75 МПа", n_profiles=7, steady_state=False)
