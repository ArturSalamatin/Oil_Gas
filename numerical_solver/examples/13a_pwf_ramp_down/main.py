"""Сценарий 13a: ступенчатое снижение p_wf 14.4 -> 6 МПа за 15 сут (R_ext = 200 м)."""

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
        title="13a: ступенчатое снижение забойного давления",
        # Профили на каждую запись истории — 31 кривая (решение
        # пользователя 2026-09-28): видна каждая ступень p_wf.
        all_profiles=True,
    )
