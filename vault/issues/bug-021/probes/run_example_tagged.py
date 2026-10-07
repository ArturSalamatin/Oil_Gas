"""BUG-021, после влития: пример целиком (как его main.py) на коде текущего каталога, вывод в probes/out_<пример>_<метка>.

Нужен, чтобы сравнить числа README (баланс энергии, баланс массы DEBT-039, проверка R_s) на базе до
влития и на слитом дереве: код берётся из каталога запуска (worktree базы или основной каталог),
а не из установленного пакета.

Запуск — из каталога numerical_solver проверяемого дерева:
    <python> <P>\\run_example_tagged.py 13b_pwf_alternating base
"""
import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT / "examples"))
sys.path.insert(0, str(SOLVER_ROOT))
os.environ.setdefault("GPN_EXAMPLES_EMF", "0")   # без EMF (FEAT-026)

ex, tag = sys.argv[1], sys.argv[2]
import example_runner  # noqa: E402

orig = example_runner.run_example


def run_example(config_path, output_dir, **kw):
    # main.py примера передаёт свой output_dir — подменяем на каталог проб
    return orig(config_path, HERE / f"out_{ex}_{tag}", **kw)


example_runner.run_example = run_example
print("код:", Path(example_runner.__file__).parent, flush=True)
runpy.run_path(str(SOLVER_ROOT / "examples" / ex / "main.py"), run_name="__main__")
