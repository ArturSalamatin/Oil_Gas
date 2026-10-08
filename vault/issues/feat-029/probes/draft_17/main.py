"""Черновик main.py примера 17 (FEAT-029): штатный run_example, вывод в draft_17/output."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parents[4] / "numerical_solver" / "examples"
sys.path.insert(0, str(EXAMPLES))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from example_runner import run_example  # noqa: E402

if __name__ == "__main__":
    elapsed, *_ = run_example(
        config_path=HERE / "config.json",
        output_dir=HERE / "output",
        title="17: останов после сильного охлаждения забоя",
        n_profiles=7,
        steady_state=False,
    )
    print(f"run_example: расчёт {elapsed:.0f} с")
