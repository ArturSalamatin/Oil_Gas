"""Проба VAL-005: черновик main.py примера 18 (вывод — в draft_18/output). Запуск из numerical_solver/."""
import sys
from pathlib import Path

SOLVER = Path.cwd()  # запускать из numerical_solver/
sys.path.insert(0, str(SOLVER / "examples"))
print("SOLVER =", SOLVER)

from example_runner import run_example  # noqa: E402
from figure_io import export_emf  # noqa: E402
import prototype_input as pi  # noqa: E402  — модуль этой папки (sys.path[1] — папка скрипта)

if __name__ == "__main__":
    here = Path(__file__).parent
    output = here / "output"
    title = "18: вход прототипа (INPUT_TEMPLATE.xlsx)"
    _, history, grid, _ = run_example(
        config_path=here / "config.json", output_dir=output, title=title,
        n_profiles=6, steady_state=False)
    pi.report_and_plot(history, grid, output, title)
    export_emf(output)
