"""Проба DEBT-078: c_o, введённое не в 1/Па (ошибка единиц), — что делают загрузка и расчёт.

Типичная сжимаемость недонасыщенной нефти — (5…20)·10⁻⁶ 1/psi ≈ (0.7…3)·10⁻⁹ 1/Па.
Значения ниже — то же число 10⁻⁹ 1/Па, записанное без перевода из других единиц:
1e-4 (1/бар), 1e-3 (1/МПа), 1e-5 (≈ 7·10⁻⁶ 1/psi, «из справочника в 1/psi»).

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-078\\probes\\co_magnitude.py
"""

import json
import logging
import time
import warnings
from pathlib import Path

import numpy as np

from gpn_multiphase_solver import factory
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = ROOT / "numerical_solver" / "examples"
print(f"пакет: {Path(factory.__file__).resolve()}")


class _Collect(logging.Handler):
    """Собирает записи журнала уровня WARNING и выше."""
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


src = json.loads((EXAMPLES / "03_standing_corey" / "config.json").read_text(encoding="utf-8"))
# 6 ч вместо 3 сут: достаточно, чтобы увидеть отказ или правдоподобный результат
src["time"]["history"] = [{"duration": 21600.0, "dt_out": 3600.0,
                           "control": "pressure", "p_wf": 8e6}]
src["output"]["log_level"] = "WARNING"
tmp = Path(__file__).with_name("co_magnitude_tmp.json")

print("пример 03 (Стендинг), p_wf = 8 МПа, 6 ч")
for co in (0.0, 1.45e-9, 1e-5, 1e-4, 1e-3):
    src["pvt"]["co_undersaturated"] = co
    tmp.write_text(json.dumps(src, ensure_ascii=False, indent=2), encoding="utf-8")
    h = _Collect()
    root = logging.getLogger()
    root.addHandler(h)
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            cfg = load_config(tmp)
            pvt = factory.create_pvt(cfg)
            ic = cfg.initial_conditions
            pb = float(pvt.pb(np.array([ic.Rs0]))[0])
            bo_pb = float(pvt.Bo(np.array([pb]), np.array([ic.Rs0]))[0])
            bo_p0 = float(pvt.Bo(np.array([ic.p0]), np.array([ic.Rs0]))[0])
            sim, state0 = SimulatorFactory.from_config(cfg)
            t0 = time.perf_counter()
            try:
                hist = sim.run(state0)
                s = hist.states[-1]
                outcome = (f"расчёт прошёл ({time.perf_counter() - t0:.1f} с): "
                           f"T(r_0) = {s.T[0]:.4f} К, max S_g = {s.Sg.max():.4f}")
            except Exception as exc:
                outcome = f"отказ расчёта: {type(exc).__name__}: {str(exc)[:160]}"
    except Exception as exc:
        outcome, bo_pb, bo_p0 = f"отказ до расчёта: {type(exc).__name__}: {exc}", np.nan, np.nan
    finally:
        root.removeHandler(h)
    msgs = [str(x.message) for x in w] + h.records
    print(f"\n  c_o = {co:g} 1/Па: B_o(p_b) = {bo_pb:.6g}, B_o(p0) = {bo_p0:.6g}")
    print(f"    {outcome}")
    print(f"    предупреждений: {len(msgs)}")
    for m in msgs[:3]:
        print(f"      {m[:200]}")
tmp.unlink(missing_ok=True)
