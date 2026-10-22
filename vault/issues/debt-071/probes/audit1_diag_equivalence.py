"""DEBT-071, аудит 1: правка шага 1 плана на копии diagnostics.py в памяти — вывод тот же?

Берёт текст radial_blackoil/diagnostics.py, применяет обе замены «До → После» шага 1
дословно (каждая «До» обязана найтись ровно один раз), исполняет результат как модуль и
сравнивает pvt_range_warnings исходного и нового модуля на 3000 случайных состояниях
модели фикстуры Nabor_1b (давление, R_s, S_g за краями таблиц и внутри, флаг газа),
с free_gas_sg = None и 1e-6. Плюс relperm_range_warnings = хвост RELPERM-записей.
Запуск из numerical_solver/HydroSolverPrototype/Prototype_1.0.3:
    ..\\..\\.venv\\Scripts\\python ..\\..\\..\\vault\\issues\\debt-071\\probes\\audit1_diag_equivalence.py
"""
import sys
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
import radial_blackoil.diagnostics as orig  # noqa: E402
from tests.helpers import model_and_state  # noqa: E402

SRC = Path(orig.__file__)
print(f"прототип: {SRC}")

OLD_1 = '''def pvt_range_warnings(model,state,free_gas_sg=None):
    """Return warnings for ACCEPTED states only. Evaluation itself always clamps."""
    p=np.asarray(state.pressure_bar,float); rs=np.asarray(state.rs_sm3_sm3,float)
    w=[]; pvt=model.pvt; rp=model.relperm
'''
NEW_1 = '''def relperm_range_warnings(model,state):
    """Relperm part of pvt_range_warnings: Sg outside the RELPERM table, ACCEPTED states only."""
    # DEBT-071 (GPN project): callable alone -- the GPN adapter on the Standing correlation
    # path has a RELPERM table but no PVT tables (its PVT object has no gp).
    sg=np.asarray(state.sg,float); rp=model.relperm; w=[]
    if np.min(sg) < rp.sg[0]-_range_tol(rp.sg[0]):
        w.append(f'RELPERM Sg below table: min Sg={np.min(sg):.8g}, table min={rp.sg[0]:.8g}. Endpoint value used; no extrapolation.')
    if np.max(sg) > rp.sg[-1]+_range_tol(rp.sg[-1]):
        w.append(f'RELPERM Sg above table: max Sg={np.max(sg):.8g}, table max={rp.sg[-1]:.8g}. Endpoint value used; no extrapolation.')
    return w


def pvt_range_warnings(model,state,free_gas_sg=None):
    """Return warnings for ACCEPTED states only. Evaluation itself always clamps."""
    p=np.asarray(state.pressure_bar,float); rs=np.asarray(state.rs_sm3_sm3,float)
    w=[]; pvt=model.pvt
'''
OLD_2 = '''    sg=np.asarray(state.sg,float)
    if np.min(sg) < rp.sg[0]-_range_tol(rp.sg[0]):
        w.append(f'RELPERM Sg below table: min Sg={np.min(sg):.8g}, table min={rp.sg[0]:.8g}. Endpoint value used; no extrapolation.')
    if np.max(sg) > rp.sg[-1]+_range_tol(rp.sg[-1]):
        w.append(f'RELPERM Sg above table: max Sg={np.max(sg):.8g}, table max={rp.sg[-1]:.8g}. Endpoint value used; no extrapolation.')
    return w
'''
NEW_2 = '''    # DEBT-071 (GPN project): the relperm part is a function of its own -- same texts, same order (last).
    w.extend(relperm_range_warnings(model,state))
    return w
'''

text = SRC.read_text(encoding="utf-8")
for old in (OLD_1, OLD_2):
    n = text.count(old)
    print(f"«До» найдено {n} раз(а)")
    assert n == 1
text = text.replace(OLD_1, NEW_1).replace(OLD_2, NEW_2)
new = types.ModuleType("diagnostics_plan")
exec(compile(text, "diagnostics_plan", "exec"), new.__dict__)

_, model, state = model_and_state(n=12)
rng = np.random.default_rng(71)
gp, rsv, pb, sgt = model.pvt.gp, model.pvt.rs_values, model.pvt.pb, model.relperm.sg
print(f"газовая таблица {gp[0]:.4g}…{gp[-1]:.4g} бар, R_s {rsv[0]:.4g}…{rsv[-1]:.4g}, "
      f"p_b {pb[0]:.4g}…{pb[-1]:.4g} бар, ОФП S_g {sgt[0]:.4g}…{sgt[-1]:.4g}")
n_cmp = n_rp = 0
cats = set()
for k in range(3000):
    s = state
    s.pressure_bar[:] = rng.uniform(0.5 * gp[0], 1.3 * gp[-1], s.pressure_bar.size)
    s.rs_sm3_sm3[:] = rng.uniform(-5.0, 1.2 * rsv[-1], s.rs_sm3_sm3.size)
    s.sg[:] = rng.uniform(-0.02, 1.02, s.sg.size) * (rng.random(s.sg.size) < 0.6)
    s.gas_active[:] = rng.random(s.sg.size) < 0.5
    for fg in (None, 1e-6):
        a = orig.pvt_range_warnings(model, s, free_gas_sg=fg)
        b = new.pvt_range_warnings(model, s, free_gas_sg=fg)
        assert a == b, (k, fg, a, b)
        n_cmp += 1
        cats.update(orig.warning_category(x) for x in a)
    r = new.relperm_range_warnings(model, s)
    tail = [x for x in a if x.startswith("RELPERM")]
    assert r == tail and a[len(a) - len(r):] == r, (k, r, a)
    n_rp += bool(r)
print(f"сравнений pvt_range_warnings: {n_cmp}, все совпали побитово; состояний с записью ОФП: {n_rp}")
print(f"встретились категории ({len(cats)} из {len(orig.WARNING_CATEGORIES)}): {sorted(cats)}")
