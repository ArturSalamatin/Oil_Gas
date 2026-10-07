"""BUG-016: run_example примера с правкой прототипа — консольный вывод для сверки с README.

Запуск (из numerical_solver основного каталога):
    python <этот файл> <метка> <режим> <cap|-> <chop|-> <пример> [kwargs-JSON]
kwargs-JSON — параметры run_example из main.py примера, например
    '{"n_profiles": 7, "steady_state": false}' (13b).
Вывод: readme_runs/<метка>/<пример>/ (графики, CSV) и консоль.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402

label, mode, cap, chop, name = sys.argv[1:6]
if mode != "orig":
    patch.install(mode, cap=None if cap == "-" else float(cap),
                  chop=None if chop == "-" else float(chop))
sys.path.insert(0, str(patch.NS / "examples"))
from example_runner import run_example  # noqa: E402

ex = patch.NS / "examples" / name
# overlays из main.py не нужны для сверки чисел консоли; steady_state и
# n_profiles — передаются, они меняют состав печати (13b)
kw = json.loads(sys.argv[6]) if len(sys.argv) > 6 else {}
run_example(config_path=ex / "config.json", output_dir=HERE / "readme_runs" / label / name,
            title=f"{name} [{label}]", **kw)
