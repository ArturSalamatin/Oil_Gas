"""Проба DEBT-065 (план): код isobar_radius из плана против трёх старых функций.

Запуск из numerical_solver/ основного каталога (база 015a297, функции ещё в examples/):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-065\\probes\\isobar_new.py

Проверяет:
  1. пример 11: новое значение замкнутого решения и численного профиля;
  2. внутри сетки новое значение побитово равно старому — на замкнутых
     профилях 03, 04, 04a, 10, 12 и на синтетике, включая немонотонный
     профиль с префиксом p < pb;
  3. время solve_closed на сетке примера 11 (для теста быстрого уровня).
"""

import sys
import time
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"SOLVER = {SOLVER}")
sys.path.insert(0, str(SOLVER / "examples"))

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

import closed_form  # noqa: E402
import rs_analytics  # noqa: E402


def isobar_radius(r, p, pb, R_ext, p_ext):
    """Код из плана DEBT-065, шаг 2 (копия для пробы)."""
    r_n = np.append(np.asarray(r, float), float(R_ext))
    p_n = np.append(np.asarray(p, float), float(p_ext))
    above = np.flatnonzero(p_n >= pb)
    if above.size == 0 or above[0] == 0:
        return np.nan
    j = int(above[0])
    w = (pb - p_n[j - 1]) / (p_n[j] - p_n[j - 1])
    return float(np.exp(np.log(r_n[j - 1]) + w * (np.log(r_n[j]) - np.log(r_n[j - 1]))))


def old_nan(r, p, pb):
    """Тело rs_analytics.front_radius (за краем — nan)."""
    j = int(np.searchsorted(p, pb))
    if not (0 < j < len(p)):
        return np.nan
    w = (pb - p[j - 1]) / (p[j] - p[j - 1])
    return float(np.exp(np.log(r[j - 1]) + w * (np.log(r[j]) - np.log(r[j - 1]))))


def case(name):
    c = load_config(SOLVER / "examples" / name / "config.json")
    sim, init = SimulatorFactory.from_config(c)
    return c, sim, init


# ── 1. Пример 11 ──
c11, sim, init = case("11_degassing_at_boundary")
r = sim._grid.r_centers
pvt, rp = sim._energy._pvt, _create_relperm(c11)
pb = float(pvt.pb(np.array([c11.initial_conditions.Rs0]))[0])
R_e, p_e = c11.geometry.R_ext, c11.initial_conditions.p0

closed_form._CACHE.clear()
t0 = time.perf_counter()
cl = closed_form.solve_closed(c11, pvt, rp, r)
print(f"solve_closed(11, N = {len(r)}): {time.perf_counter() - t0:.2f} с")
print(f"11, замкнутое: старое {cl['r_b']:.4f} м, новое "
      f"{isobar_radius(r, cl['p'], pb, R_e, p_e):.4f} м (опорное 47.7338 м)")

hist = sim.run(init)
p_num = hist.states[-1].p
print(f"11, численное: старое {rs_analytics.front_radius(c11, hist, sim._grid, pvt)}, "
      f"новое {isobar_radius(r, p_num, pb, R_e, p_e):.4f} м")
print(f"11, p_wf последней записи = {hist.well_data[-1].p_wf / 1e6:.4f} МПа")

# ── 2. Побитовое совпадение внутри сетки ──
print("\nЗамкнутые профили: старое _front_radius против нового (== побитово):")
for ex in ["03_standing_corey", "04_table_table", "04a_high_gas_saturation",
           "10_deep_degassing", "12_large_drainage_radius"]:
    c, s, _ = case(ex)
    rr = s._grid.r_centers
    pv = s._energy._pvt
    pbx = float(pv.pb(np.array([c.initial_conditions.Rs0]))[0])
    clx = closed_form.solve_closed(c, pv, _create_relperm(c), rr)
    new = isobar_radius(rr, clx["p"], pbx, c.geometry.R_ext, c.initial_conditions.p0)
    print(f"  {ex:26s} старое {clx['r_b']!r}  новое {new!r}  равны: {clx['r_b'] == new}")

print("\nСинтетика (pb = 15 МПа, R_ext = 50 м, p_ext = 20 МПа):")
rs = np.geomspace(0.1, 45.0, 6)
syn = {
    "внутри сетки": [10, 12, 14, 16, 18, 19.5],
    "немонотонный, префикс p < pb": [10, 12, 14, 17, 16, 19.5],
    "немонотонный, без префикса": [10, 16, 14, 17, 18, 19.5],
    "газа в ячейках нет": [15.5, 16, 17, 18, 19, 19.5],
    "в первой ячейке p = pb": [15, 16, 17, 18, 19, 19.5],
    "газ до контура": [10, 11, 12, 13, 14, 14.5],
}
for name, pm in syn.items():
    pp = np.array(pm, float) * 1e6
    a, b = old_nan(rs, pp, 15e6), isobar_radius(rs, pp, 15e6, 50.0, 20e6)
    same = (a == b) or (np.isnan(a) and np.isnan(b))
    print(f"  {name:30s} старое {a:10.6f}  новое {b:10.6f}  совпадают: {same}")
print(f"  контур ниже pb (p_ext = 14.8 МПа): "
      f"{isobar_radius(rs, np.array(syn['газ до контура']) * 1e6, 15e6, 50.0, 14.8e6)}")

# Точность на логарифмическом профиле: p = a + b ln r — интерполяция по ln r точна.
a_, b_ = 14e6, 0.5e6
p_log = a_ + b_ * np.log(rs)
for pbx in [14.5e6, a_ + b_ * np.log(48.0)]:
    exact = np.exp((pbx - a_) / b_)
    got = isobar_radius(rs, p_log, pbx, 50.0, a_ + b_ * np.log(50.0))
    print(f"  лог. профиль, pb = {pbx / 1e6:.4f} МПа: точный {exact:.12f}, "
          f"новое {got:.12f}, отн. {abs(got - exact) / exact:.1e}")
