"""Сценарий 10: глубокое разгазирование при p_wf = 6 МПа, полная термика."""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from example_runner import run_example  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="10: глубокое разгазирование",
    )
