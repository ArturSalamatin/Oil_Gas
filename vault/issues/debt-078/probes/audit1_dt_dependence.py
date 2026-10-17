"""Аудит 1 DEBT-078: c_o = −1e-9 при c_r = 0 — C_p < 0, но расчёт прошёл. Зависит ли результат от шага?

Постановка (абзац под eq:c_ot): при c_o < −c_r коэффициент C_p < 0, неявный шаг
вырождается на последовательности Δt. Сравниваются c_o = 0 и −1e-9 при
dt_integration = 3600, 1800, 900 с: разброс по шагу при c_o < 0 против c_o = 0.

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-078\\probes\\audit1_dt_dependence.py
"""

import json
import logging
from pathlib import Path

from gpn_multiphase_solver import factory
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = ROOT / "numerical_solver" / "examples"
print(f"пакет: {Path(factory.__file__).resolve()}")
logging.disable(logging.WARNING)   # предупреждение BUG-019 известно (co_negative_run.out.txt)

src = json.loads((EXAMPLES / "03_standing_corey" / "config.json").read_text(encoding="utf-8"))
src["time"]["history"] = [{"duration": 86400.0, "dt_out": 3600.0,
                           "control": "pressure", "p_wf": 8e6}]
src["output"]["log_level"] = "ERROR"
tmp = Path(__file__).with_name("audit1_dt_tmp.json")

print("пример 03 (Стендинг, c_r = 0), p_wf = 8 МПа, 1 сут; ячейка 0 и максимум |Δp| по области")
res = {}
try:
    for co in (0.0, -1e-9, -3.3e-9):
        for dt in (3600, 1800, 900):
            src["pvt"]["co_undersaturated"] = co
            src["time"]["dt_integration"] = dt
            tmp.write_text(json.dumps(src), encoding="utf-8")
            sim, s0 = SimulatorFactory.from_config(load_config(tmp))
            try:
                s = sim.run(s0).states[-1]
                res[co, dt] = s
                print(f"  c_o = {co:8.2g}, dt = {dt:4d} с: p(r_0) = {s.p[0] / 1e6:.6f} МПа, "
                      f"T(r_0) = {s.T[0]:.5f} К, двухфазных {int((s.Sg > 0).sum())}")
            except Exception as exc:
                print(f"  c_o = {co:8.2g}, dt = {dt:4d} с: отказ — {str(exc)[:110]}")
finally:
    tmp.unlink(missing_ok=True)

print("\nразброс по шагу (3600 против 900 с):")
for co in (0.0, -1e-9, -3.3e-9):
    if (co, 3600) in res and (co, 900) in res:
        a, b = res[co, 3600], res[co, 900]
        print(f"  c_o = {co:8.2g}: max|Δp| = {abs(a.p - b.p).max() / 1e3:.3f} кПа, "
              f"|ΔT(r_0)| = {abs(a.T[0] - b.T[0]):.5f} К")
