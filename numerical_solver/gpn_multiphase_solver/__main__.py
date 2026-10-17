"""python -m gpn_multiphase_solver — расчёт по конфигу и шаблон книги ввода (FEAT-030, FEAT-033)."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(prog="python -m gpn_multiphase_solver"))
