"""Сценарий 13b: p_wf по суткам 6 <-> 10.75 МПа, 30 сут (R_ext = 200 м)."""

import sys
from pathlib import Path

from gpn_multiphase_solver.cli import main

if __name__ == "__main__":
    # То же, что python -m gpn_multiphase_solver run <папка примера>\config.json:
    # параметры примера — в секции output конфига (FEAT-030)
    sys.exit(main(["run", str(Path(__file__).parent / "config.json")]))
