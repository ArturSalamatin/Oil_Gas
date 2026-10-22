"""Сценарий 17: R_s0 = 300, 15 сут добычи при 5 МПа, затем 15 сут останова (q_oil = 0)."""

import sys
from pathlib import Path

from gpn_multiphase_solver.cli import main

if __name__ == "__main__":
    # То же, что python -m gpn_multiphase_solver run <папка примера>\config.json:
    # параметры примера — в секции output конфига (FEAT-030)
    sys.exit(main(["run", str(Path(__file__).parent / "config.json")]))
