"""Проба BUG-017: какие вызовы SimulatorFactory.from_config нарушили бы проверки начального состояния.

Плагин pytest, исходники не меняет. Запуск из numerical_solver:
    .venv/Scripts/python -m pytest tests/ -q -p check_ic_plugin
с PYTHONPATH, содержащим папку этого файла. Нарушения дописываются в
check_ic_violations.txt рядом с файлом.

Проверки (кандидаты плана):
  1. табличная PVT: rs_values[0] <= Rs0 <= rs_values[-1];
  2. обе модели: Rs0 <= Rs_eq(p0) (нет пересыщения на старте).
"""

from pathlib import Path

import numpy as np

from gpn_multiphase_solver import factory as _factory

_OUT = Path(__file__).with_name("check_ic_violations.txt")
_orig = _factory.SimulatorFactory.from_config


def _wrapped(config):
    sim, st = _orig(config)
    ic = config.initial_conditions
    pvt = sim._pvt
    msgs = []
    proto = getattr(getattr(pvt, "_hydro", None), "_pvt", None)
    if proto is not None and hasattr(proto, "rs_values"):
        lo, hi = float(proto.rs_values[0]), float(proto.rs_values[-1])
        if not (lo <= ic.Rs0 <= hi):
            msgs.append(f"range: Rs0={ic.Rs0} вне [{lo}, {hi}]")
    rs_eq = float(pvt.Rs_eq(np.array([ic.p0]))[0])
    if ic.Rs0 > rs_eq * (1 + 1e-6):
        pb = float(pvt.pb(np.array([ic.Rs0]))[0])
        msgs.append(f"supersat: Rs0={ic.Rs0} > Rs_eq(p0={ic.p0})={rs_eq:.6g}, pb(Rs0)={pb:.6g}")
    if msgs:
        import os
        test = os.environ.get("PYTEST_CURRENT_TEST", "?")
        with open(_OUT, "a", encoding="utf-8") as f:
            f.write(f"{test} | {config.pvt.model} | " + "; ".join(msgs) + "\n")
    return sim, st


_factory.SimulatorFactory.from_config = staticmethod(_wrapped)
