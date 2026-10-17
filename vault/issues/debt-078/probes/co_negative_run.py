"""Проба DEBT-078: расчёт примера 03 (Стендинг) при c_o < 0 — до проверки знака в _validate.

c_r = 0 у примера 03, поэтому при c_o < 0 коэффициент C_p в недонасыщенной зоне
отрицателен (eq:Cp, механизм BUG-019). Что делает расчёт: идёт молча, отказывает?

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-078\\probes\\co_negative_run.py
"""

import json
import logging
import time
from pathlib import Path

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
# 1 сут вместо 3: первые сутки — самые резкие (запуск скважины)
src["time"]["history"] = [{"duration": 86400.0, "dt_out": 3600.0,
                           "control": "pressure", "p_wf": 8e6}]
src["output"]["log_level"] = "WARNING"
tmp = Path(__file__).with_name("co_negative_run_tmp.json")

print("пример 03 (Стендинг, c_r = 0), p_wf = 8 МПа, 1 сут")
for co in (0.0, -1e-9, -3.3e-9):
    src["pvt"]["co_undersaturated"] = co
    tmp.write_text(json.dumps(src, ensure_ascii=False, indent=2), encoding="utf-8")
    h = _Collect()
    root = logging.getLogger()
    root.addHandler(h)
    try:
        cfg = load_config(tmp)
        sim, state0 = SimulatorFactory.from_config(cfg)
        t0 = time.perf_counter()
        try:
            hist = sim.run(state0)
            s = hist.states[-1]
            outcome = (f"расчёт прошёл ({time.perf_counter() - t0:.1f} с): "
                       f"p(r_0) = {s.p[0] / 1e6:.4f} МПа, T(r_0) = {s.T[0]:.4f} К, "
                       f"max S_g = {s.Sg.max():.4f}, двухфазных ячеек {int((s.Sg > 0).sum())}")
        except Exception as exc:
            outcome = f"отказ расчёта: {type(exc).__name__}: {str(exc)[:220]}"
    except Exception as exc:
        outcome = f"отказ до расчёта: {type(exc).__name__}: {exc}"
    finally:
        root.removeHandler(h)
    print(f"\n  c_o = {co:g} 1/Па")
    print(f"    {outcome}")
    print(f"    записей журнала WARNING+: {len(h.records)}")
    for m in h.records[:2]:
        print(f"      {m[:160]}")
tmp.unlink(missing_ok=True)
