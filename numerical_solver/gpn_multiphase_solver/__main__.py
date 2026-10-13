"""python -m gpn_multiphase_solver — команда расчёта по конфигу (FEAT-030)."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(prog="python -m gpn_multiphase_solver"))
