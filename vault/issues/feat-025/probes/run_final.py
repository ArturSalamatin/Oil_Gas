"""FEAT-025: полный конвейер run_example на итоговых конфигах (печать для README).

Конфиги — make_configs.py <папка> names=1 (подпапки 19_rs150_cooling, ...).
Вызов run_example — как в main.py плана: steady_state=False, n_profiles по умолчанию.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\run_final.py <папка> [имя ...]
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
sys.path.insert(0, str(SOLVER / "examples"))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from example_runner import run_example  # noqa: E402

TITLES = {
    "19_rs150_cooling": "19: R_s0 = 150, горячий пласт — охлаждение забоя",
    "20_rs500_cooling": "20: R_s0 = 500, летучая нефть — охлаждение забоя",
    "21_rs100_cooling": "21: R_s0 = 100, горячий пласт — охлаждение забоя",
}

if __name__ == "__main__":
    root = Path(sys.argv[1])
    names = sys.argv[2:] or list(TITLES)
    for nm in names:
        d = root / nm
        print(f"\n{'═' * 70}\n{nm}\n{'═' * 70}")
        t0 = time.perf_counter()
        run_example(config_path=d / "config.json", output_dir=d / "output",
                    title=TITLES[nm], steady_state=False)
        print(f"── run_example: {time.perf_counter() - t0:.1f} с")
