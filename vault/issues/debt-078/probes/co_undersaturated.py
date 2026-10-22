"""Проба DEBT-078: pvt.co_undersaturated при табличном PVT и знак c_o у Стендинга.

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-078\\probes\\co_undersaturated.py
"""

import copy
import json
import logging
import warnings
from pathlib import Path

import numpy as np

from gpn_multiphase_solver import factory
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = ROOT / "numerical_solver" / "examples"
print(f"пакет: {Path(factory.__file__).resolve()}")


def bo_above_pb(pvt, p0, Rs0, n=6):
    """B_o на недонасыщенной ветви R_s = R_s0 от p_b(R_s0) до p0."""
    pb = float(pvt.pb(np.array([Rs0]))[0])
    p = np.linspace(max(pb, 1e5), p0, n)
    return p, pvt.Bo(p, np.full_like(p, Rs0))


class _Collect(logging.Handler):
    """Собирает записи журнала уровня WARNING и выше."""
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def build(cfg):
    """create_pvt и from_config с перехватом warnings и журнала; возвращает PVT и список предупреждений."""
    # Проверка согласованности PVT фабрики (BUG-019) пишет в журнал logging,
    # а не через warnings — перехватываются оба канала.
    h = _Collect()
    root = logging.getLogger()
    root.addHandler(h)
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            pvt = factory.create_pvt(cfg)
            SimulatorFactory.from_config(cfg)
    finally:
        root.removeHandler(h)
    return pvt, [str(x.message) for x in w] + h.records


# ── 1. Табличный PVT (пример 04): c_o = 0 и c_o = 3.3e-9 ──
cfg = load_config(EXAMPLES / "04_table_table" / "config.json")
ic = cfg.initial_conditions
print(f"\n1. пример 04, pvt.model = {cfg.pvt.model!r}, p0 = {ic.p0:.4g} Па, Rs0 = {ic.Rs0}")
res = {}
for co in (0.0, 3.3e-9):
    c = copy.deepcopy(cfg)
    c.pvt.co_undersaturated = co
    pvt, w = build(c)
    p, bo = bo_above_pb(pvt, ic.p0, ic.Rs0)
    res[co] = bo
    print(f"   c_o = {co:g}: отказа нет, предупреждений {len(w)}; B_o(p) = {np.array2string(bo, precision=6)}")
print(f"   max |ΔB_o| = {np.max(np.abs(res[3.3e-9] - res[0.0])):.3e}")

# ── 2. Стендинг (пример 03): c_o < 0 через load_config ──
src = json.loads((EXAMPLES / "03_standing_corey" / "config.json").read_text(encoding="utf-8"))
src["pvt"]["co_undersaturated"] = -1e-9
tmp = Path(__file__).with_name("standing_co_negative.json")
tmp.write_text(json.dumps(src, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n2. пример 03, pvt.co_undersaturated = -1e-9")
try:
    cfg = load_config(tmp)
    print("   load_config: принят")
    pvt, w = build(cfg)
    print(f"   create_pvt/from_config: отказа нет, предупреждений {len(w)}")
    for m in w:
        print(f"     {m}")
    ic = cfg.initial_conditions
    p, bo = bo_above_pb(pvt, ic.p0, ic.Rs0)
    print(f"   p, МПа = {np.array2string(p / 1e6, precision=3)}")
    print(f"   B_o    = {np.array2string(bo, precision=6)}  (растёт с p: {bool(np.all(np.diff(bo) > 0))})")
except Exception as exc:
    print(f"   отказ: {type(exc).__name__}: {exc}")
finally:
    tmp.unlink(missing_ok=True)
