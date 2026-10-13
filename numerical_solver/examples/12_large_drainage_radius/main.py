"""Сценарий 12: большая область дренирования (R_ext = 200 м, p0 = 15.5 МПа, 15 сут)."""

import sys
from pathlib import Path

from gpn_multiphase_solver.cli import main

if __name__ == "__main__":
    # То же, что python -m gpn_multiphase_solver run <папка примера>\config.json:
    # параметры примера — в секции output конфига (FEAT-030)
    sys.exit(main(["run", str(Path(__file__).parent / "config.json")]))
