r"""DEBT-042: что делают CSV-ридеры фабрики с ошибочными строками до правки (красное состояние).

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-042\probes\red_state.py
Рабочий каталог red_state_tmp/ создаётся рядом и удаляется в конце.
"""
import shutil
import sys
import traceback
from pathlib import Path

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree), а не от расположения пробы: см. tables_check.py
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver import factory                         # noqa: E402
from gpn_multiphase_solver.io.config import load_config          # noqa: E402
from gpn_multiphase_solver.factory import (                      # noqa: E402
    SimulatorFactory, _read_oil_pvt_csv, _read_gas_pvt_csv, _read_relperm_csv,
)

print(f"Код: {Path(factory.__file__).resolve()}")

TABLE_CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"
WORK = Path(__file__).resolve().parent / "red_state_tmp"

OIL_H = "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
OIL_0 = "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
GAS_H = "pressure_Pa,Bg,mu_g_Pa_s\n"
RP_H = "Sg,kro,krg\n"

# (ридер, текст файла); у каждого случая одна ошибочная строка (кроме служебных)
READER_CASES = {
    "oil_typo":          ("oil", OIL_H + OIL_0 + "30.0,15OOOOOO,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_decimal_comma": ("oil", OIL_H + OIL_0 + "30.0,15000000,1,20,0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_short":         ("oil", OIL_H + OIL_0 + "30.0,15000000,1.20\n30.0,30000000,1.18,0.0016\n"),
    "oil_trailing":      ("oil", OIL_H + OIL_0 + "30.0,15000000,1.20,0.0015,\n30.0,30000000,1.18,0.0016\n"),
    "oil_nan":           ("oil", OIL_H + OIL_0 + "30.0,nan,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_inf":           ("oil", OIL_H + OIL_0 + "30.0,15000000,inf,0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_spaces_line":   ("oil", OIL_H + OIL_0 + "   \n30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_no_header":     ("oil", OIL_0 + "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_swapped_cols":  ("oil", "Rs_sm3_sm3,pressure_Pa,mu_o_Pa_s,Bo\n" + OIL_0),
    "oil_empty_file":    ("oil", ""),
    "oil_bom":           ("oil", "﻿" + OIL_H + OIL_0),
    "oil_semicolon":     ("oil", "Rs_sm3_sm3;pressure_Pa;Bo;mu_o_Pa_s\n0,0;5000000;1,05;0,003\n0,0;30000000;1,04;0,0032\n"),
    "gas_typo":          ("gas", GAS_H + "5000000,0.020,0.000012\n15000000,0.0O8,0.000014\n30000000,0.004,0.000018\n"),
    "rp_col2_error":     ("rp",  RP_H + "0.0,1.0,0.0\n0.4,0.3x,0.2\n0.8,0.0,0.8\n"),
    "rp_col3_error":     ("rp",  RP_H + "0.0,1.0,0.0\n0.4,0.3,0.2x\n0.8,0.0,0.8\n"),
}

READERS = {"oil": _read_oil_pvt_csv, "gas": _read_gas_pvt_csv, "rp": _read_relperm_csv}


def run_reader_cases():
    print("== Прямой вызов ридеров")
    for name, (kind, text) in READER_CASES.items():
        path = WORK / f"{name}.csv"
        path.write_text(text, encoding="utf-8")
        try:
            out = READERS[kind](path)
            if kind == "rp":
                print(f"{name:18s} OK: len(Sg, kro, krg) = {tuple(len(c) for c in out)}")
            else:
                print(f"{name:18s} OK: {len(out)} строк; {out}")
        except Exception as e:
            print(f"{name:18s} {type(e).__name__}: {e}")


def _config_with(tmp, oil=None, gas=None, rp=None):
    """TABLE_CONFIG с подменёнными CSV в каталоге tmp."""
    tmp.mkdir()
    for fname in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        shutil.copy(TABLE_CONFIG.parent / fname, tmp / fname)
    for fname, text in (("oil_pvt.csv", oil), ("gas_pvt.csv", gas), ("relperm.csv", rp)):
        if text is not None:
            (tmp / fname).write_text(text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = tmp
    return config


def run_factory_cases():
    print("\n== from_config и run (configs/table_pvt)")
    rp_bad = (RP_H + "0.0,1.0,0.0\n0.1,0.8,0.01\n0.2,0.6x,0.05\n"
              "0.4,0.3,0.2\n0.6,0.1,0.5\n0.8,0.0,0.8\n")
    gas_semicolon = "pressure_Pa;Bg;mu_g_Pa_s\n5000000;0,020;0,000012\n15000000;0,008;0,000014\n"
    rp_semicolon = "Sg;kro;krg\n0,0;1,0;0,0\n0,4;0,3;0,2\n0,8;0,0;0,8\n"
    cases = {
        "rp_col2_error": dict(rp=rp_bad),
        "gas_semicolon": dict(gas=gas_semicolon),
        "rp_semicolon": dict(rp=rp_semicolon),
    }
    for name, kw in cases.items():
        config = _config_with(WORK / f"cfg_{name}", **kw)
        stage = "from_config"
        try:
            sim, state = SimulatorFactory.from_config(config)
            stage = "run"
            sim.run(state)
            print(f"{name:18s} from_config и run прошли")
        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)[-1]
            print(f"{name:18s} {stage}: {type(e).__name__}: {e}  [{Path(tb.filename).name}:{tb.lineno}]")


if __name__ == "__main__":
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    try:
        run_reader_cases()
        run_factory_cases()
    finally:
        shutil.rmtree(WORK)
