"""Печатает ли фабрика предупреждения на конфигах примеров с собственным main.py (FEAT-030).

main.py 01–05 после run_example собирают второй Simulator ради PVT
(SimulatorFactory.from_config). Если фабрика пишет в журнал (factory.py:
_warn_negative_compressibility, _warn_initial_table_range), второй вызов
повторяет предупреждения в stderr, и отказ от второго Simulator в FEAT-030
изменит печать этих примеров. Проба считает записи журнала WARNING и выше
на одном вызове from_config для каждого конфига.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-030\\probes\\factory_warnings.py
"""

import logging
from pathlib import Path

SOLVER = Path.cwd()
print(f"дерево: {SOLVER}")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


class _Count(logging.Handler):
    """Собирает записи журнала уровня WARNING и выше."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


for name in ("01_single_phase_no_jt", "02_single_phase_jt", "03_standing_corey",
             "04_table_table", "05_standing_table_rp", "18_prototype_input"):
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    h = _Count()
    logging.getLogger("gpn_multiphase_solver").addHandler(h)
    SimulatorFactory.from_config(cfg)
    logging.getLogger("gpn_multiphase_solver").removeHandler(h)
    print(f"{name}: предупреждений фабрики — {len(h.records)}")
    for m in h.records:
        print(f"    {m[:120]}")
