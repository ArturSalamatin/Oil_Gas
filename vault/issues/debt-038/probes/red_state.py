r"""DEBT-038: поведение from_config на CSV-таблицах тестов плана до правки (красное состояние).

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-038\probes\red_state.py
"""
import shutil
import sys
import warnings
from pathlib import Path

SOLVER = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.io.config import load_config          # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory       # noqa: E402

TABLE_CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"
WORK = Path(__file__).resolve().parent / "red_state_tmp"

HEADER = "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
BRANCH_0 = "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
BRANCH_30 = "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"

CASES = {
    "one_row_middle": HEADER + BRANCH_0 + "15.0,10000000,1.12,0.0022\n" + BRANCH_30,
    "one_row_last": HEADER + BRANCH_0 + "30.0,15000000,1.20,0.0015\n",
    "repeated_pressure": HEADER + BRANCH_0 + ("30.0,15000000,1.20,0.0015\n"
                                              "30.0,20000000,1.19,0.00152\n"
                                              "30.0,20000000,1.185,0.00153\n"
                                              "30.0,30000000,1.18,0.0016\n"),
    "out_of_order": HEADER + BRANCH_0 + ("30.0,15000000,1.20,0.0015\n"
                                         "30.0,30000000,1.18,0.0016\n"
                                         "30.0,20000000,1.19,0.00152\n"),
    "rs_typo": HEADER + BRANCH_0 + ("30.0,15000000,1.20,0.0015\n"
                                    "30.01,22000000,1.19,0.00155\n"
                                    "30.0,30000000,1.18,0.0016\n"),
    "empty": HEADER,
    "interleaved": HEADER + ("0.0,5000000,1.05,0.003\n30.0,15000000,1.20,0.0015\n"
                             "0.0,30000000,1.04,0.0032\n30.0,30000000,1.18,0.0016\n"),
}

WORK.mkdir(exist_ok=True)
for name in ("gas_pvt.csv", "relperm.csv"):
    shutil.copy(TABLE_CONFIG.parent / name, WORK / name)
for case, text in CASES.items():
    (WORK / "oil_pvt.csv").write_text(text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = WORK
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            SimulatorFactory.from_config(config)
            outcome = "from_config прошёл"
        except Exception as e:                                    # noqa: BLE001
            outcome = f"{type(e).__name__}: {e}"
    runtime = [str(w.message) for w in caught if issubclass(w.category, RuntimeWarning)]
    print(f"{case:18s} {outcome}" + (f"  | RuntimeWarning: {runtime}" if runtime else ""))
shutil.rmtree(WORK)
