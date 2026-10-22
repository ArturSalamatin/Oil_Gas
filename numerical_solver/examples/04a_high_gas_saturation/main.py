"""Сценарий 04a: высокая газонасыщенность (S_g = 0.7 на забое).

Табличный PVT и ОФП Кори с k_rg^max = 0.0014, вычисленной ОБРАТНЫМ
РАСЧЁТОМ из условия GOR = Rs0 (вывод — в README).
Показывает, что насыщенность управляется подвижностью газа, а не депрессией.
"""

import sys
from pathlib import Path

from gpn_multiphase_solver.cli import main

if __name__ == "__main__":
    # То же, что python -m gpn_multiphase_solver run <папка примера>\config.json:
    # параметры примера — в секции output конфига (FEAT-030)
    sys.exit(main(["run", str(Path(__file__).parent / "config.json")]))
