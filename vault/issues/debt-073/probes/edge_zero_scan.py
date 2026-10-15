"""DEBT-073: допустимые таблицы ОФП (последний узел k_ro = 0) с узким краем — выход S_g за таблицу в расчёте.

После DEBT-073 фабрика отвергает таблицу с k_ro > 0 в последнем узле, и тест DEBT-071
test_relperm_above_table_before_failure (таблица до 0.01, k_ro = 0.98 на краю) теряет
сценарий. Здесь — есть ли допустимая таблица, на которой настоящий расчёт примера 05
выходит за край таблицы ОФП (запись «вне таблиц» на пути Стендинга, DEBT-071).

Запуск из numerical_solver/ (код базы, DEBT-071 влита):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-073\\probes\\edge_zero_scan.py
"""
import logging
import time
from pathlib import Path

import numpy as np

import gpn_multiphase_solver
import radial_blackoil
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.io.config import load_config

SOLVER = Path.cwd()
HERE = Path(__file__).resolve().parent
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
print(f"прототип: {Path(radial_blackoil.__file__).parent}", flush=True)

# Таблицы: последний узел k_ro = 0 (DEBT-073 их принимает), край по S_g — узкий
TABLES = {
    "до 0.02, k_ro 0.98 → 0": ["0.0,1.0,0.0", "0.01,0.98,0.001", "0.02,0.0,0.002"],
    "до 0.01, k_ro → 0": ["0.0,1.0,0.0", "0.01,0.0,0.001"],
    "до 0.05, k_ro 0.98 → 0": ["0.0,1.0,0.0", "0.01,0.98,0.001", "0.05,0.0,0.05"],
    "до 0.1, k_ro 0.8 → 0": ["0.0,1.0,0.0", "0.1,0.0,0.01"],
}

MAX_SG = {}
_orig_solve = PrototypeHydroAdapter.solve


def solve(self, state, dt, bc):
    res = _orig_solve(self, state, dt, bc)
    MAX_SG["max"] = max(MAX_SG.get("max", 0.0), float(np.max(res.state.Sg)))
    MAX_SG["n"] = MAX_SG.get("n", 0) + 1
    return res


PrototypeHydroAdapter.solve = solve


class Collect(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def main():
    for hours in (1, 6):
        for k, (label, rows) in enumerate(TABLES.items()):
            # таблицы — рядом с пробой (CLAUDE.md: без временных каталогов)
            csv = HERE / f"relperm_edge_zero_{k}.csv"
            csv.write_text("Sg,kro,krg\n" + "\n".join(rows) + "\n", encoding="utf-8")
            cfg = load_config(SOLVER / "examples" / "05_standing_table_rp" / "config.json")
            # load_config разворачивает историю примера 05 в 72 интервала по 1 ч
            cfg.time.history = cfg.time.history[:hours]
            cfg.relperm.file = str(csv)
            logger = logging.getLogger("gpn_multiphase_solver")
            h = Collect()
            logger.addHandler(h)
            MAX_SG.clear()
            t0 = time.perf_counter()
            try:
                sim, s0 = SimulatorFactory.from_config(cfg)
                logger.setLevel(logging.WARNING)
                sim.run(s0)
                status = "сошёлся"
            except Exception as exc:  # noqa: BLE001 — проба: печать причины
                status = f"отказ ({type(exc).__name__}): {str(exc)[:120]}"
            finally:
                logger.removeHandler(h)
            rng = [m for m in h.records if "вне таблиц" in m]
            print(f"\n05, {hours} ч, {label}: {status}; {time.perf_counter() - t0:.2f} с; "
                  f"принятых подшагов {MAX_SG.get('n', 0)}, max S_g {MAX_SG.get('max', 0):.6g}")
            for m in rng:
                print(f"    {m}")


if __name__ == "__main__":
    main()
