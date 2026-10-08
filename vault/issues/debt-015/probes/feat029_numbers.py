"""DEBT-015, аудит раунда 2: числа примера 17 (проба FEAT-029 plan_numbers.py) на коде плана и без него.

Запуск из <дерево с примером 17>\\numerical_solver:
    $env:FEAT029_SOLVER = (Get-Location).Path
    $env:FEAT029_CONFIG = "examples\\17_shut_in_strong_cooling\\config.json"
    <python> <P>\\feat029_numbers.py plan     # код шага 3 DEBT-015 подменой (plan_code)
    <python> <P>\\feat029_numbers.py base     # код дерева как есть
"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if sys.argv[1] == "plan":
    import plan_code  # noqa: F401  — подмена до импорта пробы FEAT-029

runpy.run_path(str(HERE.parents[1] / "feat-029" / "probes" / "plan_numbers.py"), run_name="__main__")
