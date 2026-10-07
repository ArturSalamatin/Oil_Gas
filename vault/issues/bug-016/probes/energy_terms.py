"""BUG-016: члены баланса энергии примера с 8 знаками — для округления чисел README.

Консоль run_example печатает члены с 5 знаками, README 04a — с 4; на границе
округления (−1.1135e9) пяти знаков мало. Дерево — $env:BUG016_NS (patch.NS),
пакет — $env:PYTHONPATH. Запуск: python <этот файл> <пример>
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402

sys.path.insert(0, str(patch.NS / "examples"))
from energy_balance import compute_balance  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

name = sys.argv[1]
cfg = load_config(patch.NS / "examples" / name / "config.json")
sim, init = SimulatorFactory.from_config(cfg)
bal = compute_balance(sim.run(init), sim._grid, cfg)
for key in ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg"):
    print(f"{key:10s} {bal[key][-1]:+.8e}")
