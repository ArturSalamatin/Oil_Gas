r"""DEBT-038, аудит: p_b(R_s) не растёт от ветви к ветви (опечатка в давлении насыщенной строки).

Таблица: ветви 0 (5, 30 МПа), 15 (20 МПа вместо 10 — опечатка, и 30 МПа), 30 (15, 30 МПа).
Внутри каждой ветви давление растёт — проверка плана её пропускает.
Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-038\probes\pb_order.py
"""
import logging
import shutil
import sys
from pathlib import Path

import numpy as np

SOLVER = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.factory import SimulatorFactory, _read_oil_pvt_csv, _read_gas_pvt_csv  # noqa: E402
from gpn_multiphase_solver.io.config import load_config          # noqa: E402
from radial_blackoil.pvt import BlackOilPVT                       # noqa: E402

TABLE_CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"
WORK = Path(__file__).resolve().parent / "pb_order_tmp"
TEXT = ("Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
        "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
        "15.0,20000000,1.12,0.0022\n15.0,30000000,1.11,0.0023\n"
        "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n")

WORK.mkdir(exist_ok=True)
for name in ("gas_pvt.csv", "relperm.csv"):
    shutil.copy(TABLE_CONFIG.parent / name, WORK / name)
(WORK / "oil_pvt.csv").write_text(TEXT, encoding="utf-8")

pvt = BlackOilPVT(_read_oil_pvt_csv(WORK / "oil_pvt.csv"), _read_gas_pvt_csv(WORK / "gas_pvt.csv"))
print("R_s ветвей:", pvt.rs_values, " p_b, бар:", pvt.pb)
p = np.array([60.0, 100.0, 140.0, 160.0, 199.0, 210.0])
print("p, бар:      ", p)
print("R_s^sat(p):  ", pvt.rs_sat(p))
print("p_b(R_s=10, 20, 25):", pvt.pb_of_rs(np.array([10.0, 20.0, 25.0])))

logging.basicConfig(level=logging.WARNING, format="  журнал: %(message)s")
config = load_config(TABLE_CONFIG)
config.config_dir = WORK
try:
    SimulatorFactory.from_config(config)
    print("from_config прошёл")
except Exception as e:                                            # noqa: BLE001
    print(f"{type(e).__name__}: {e}")
shutil.rmtree(WORK)
