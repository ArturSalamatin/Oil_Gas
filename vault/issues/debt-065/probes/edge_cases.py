"""Проба DEBT-065: три реализации радиуса изобары p = pb на примере 11.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-065\\probes\\edge_cases.py

Пример 11 (p0 = 15.05 МПа, pb = 15 МПа) — кандидат на краевой случай
«давление ниже pb во всех ячейках». Проба считает на одном расчёте:
  - closed_form._front_radius на замкнутом профиле (сетка примера);
  - то же на мелкой сетке до R_ext — опорное значение r_b замкнутого решения;
  - two_phase_analytics.degassing_front["r_b_interp"] и
    rs_analytics.front_radius на численном профиле последней записи.
Плюс синтетические профили: газа нет, газ до контура, пересечение в первой
паре ячеек, изобара между r_w и первым центром.
"""

import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"SOLVER = {SOLVER}")
sys.path.insert(0, str(SOLVER / "examples"))

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

import closed_form  # noqa: E402
import rs_analytics  # noqa: E402
import two_phase_analytics as tpa  # noqa: E402

# ── Пример 11 ──
config = load_config(SOLVER / "examples" / "11_degassing_at_boundary" / "config.json")
simulator, initial_state = SimulatorFactory.from_config(config)
grid = simulator._grid
pvt = simulator._energy._pvt
relperm = _create_relperm(config)
history = simulator.run(initial_state)

r = grid.r_centers
p = history.states[-1].p
Rs0 = config.initial_conditions.Rs0
pb = float(pvt.pb(np.array([Rs0]))[0])
r_w, R_e = config.geometry.r_well, config.geometry.R_ext

print(f"N = {len(r)}, r_w = {r_w}, r[0] = {r[0]:.5f}, r[-1] = {r[-1]:.4f}, R_ext = {R_e}")
print(f"pb = {pb / 1e6:.4f} МПа, p0 = {config.initial_conditions.p0 / 1e6:.4f} МПа")
print(f"численный профиль, последняя запись: p[0] = {p[0] / 1e6:.4f}, "
      f"p[-1] = {p[-1] / 1e6:.4f} МПа; ячеек с p < pb: {int((p < pb).sum())} из {len(p)}")
print(f"  монотонность p по r: {bool(np.all(np.diff(p) > 0))}")

cl = closed_form.solve_closed(config, pvt, relperm, r)
print(f"замкнутое решение на сетке: p_ana[-1] = {cl['p'][-1] / 1e6:.4f} МПа; "
      f"ячеек с p_ana < pb: {int((cl['p'] < pb).sum())} из {len(r)}")
print(f"  closed_form._front_radius (сетка примера) = {cl['r_b']:.4f} м")

# Опорное r_b замкнутого решения: мелкая сетка до самого контура.
r_fine = np.geomspace(r[0], R_e * (1 - 1e-9), 20001)
cl_fine = closed_form.solve_closed(config, pvt, relperm, r_fine)
print(f"  closed_form._front_radius (мелкая сетка до R_ext) = {cl_fine['r_b']:.4f} м")

fr = tpa.degassing_front(history, grid, config, pvt)
print(f"two_phase_analytics.degassing_front['r_b_interp'] = {fr['r_b_interp']}")
print(f"rs_analytics.front_radius = {rs_analytics.front_radius(config, history, grid, pvt)}")

# ── Синтетика: одна и та же логика на краях ──
# rs_analytics.front_radius и degassing_front берут профиль из history,
# поэтому их тело воспроизведено функцией ниже (копия :141-145 rs_analytics.py).
def nan_variant(r, p, pb):
    j = int(np.searchsorted(p, pb))
    if not (0 < j < len(p)):
        return np.nan
    w = (pb - p[j - 1]) / (p[j] - p[j - 1])
    return float(np.exp(np.log(r[j - 1]) + w * (np.log(r[j]) - np.log(r[j - 1]))))


rs = np.geomspace(0.1, 50.0, 6)
cases = {
    "газа нет (все p > pb)": np.linspace(16e6, 17e6, 6),
    "газ до контура (все p < pb)": np.linspace(10e6, 14.9e6, 6),
    "пересечение в первой паре ячеек": np.linspace(14.5e6, 17e6, 6),
    "p[0] = pb ровно": np.linspace(15e6, 17e6, 6),
    "p[-1] = pb ровно": np.linspace(10e6, 15e6, 6),
}
print("\nСинтетика, pb = 15 МПа, r = geomspace(0.1, 50, 6):")
for name, pp in cases.items():
    a = closed_form._front_radius(rs, pp, 15e6)
    b = nan_variant(rs, pp, 15e6)
    print(f"  {name:34s} closed_form = {a:10.4f}   две другие = {b:10.4f}")

# ── Зависимость r_b замкнутого решения от сетки (пересечение внутри сетки) ──
# grid_convergence.py:110 печатает r_b замкнутого решения с пометкой
# «от сетки не зависят», а r_b — интерполяция по центрам ячеек сетки.
# Расчёт не запускается: нужны только PVT, ОФП и сетка из фабрики.
print("\nr_b замкнутого решения: сетка примера против мелкой сетки до R_ext:")
for ex in ["03_standing_corey", "04_table_table", "04a_high_gas_saturation"]:
    c = load_config(SOLVER / "examples" / ex / "config.json")
    sim, _ = SimulatorFactory.from_config(c)
    rr = sim._grid.r_centers
    pv, rp = sim._energy._pvt, _create_relperm(c)
    rb_grid = closed_form.solve_closed(c, pv, rp, rr)["r_b"]
    rf = np.geomspace(rr[0], c.geometry.R_ext * (1 - 1e-9), 20001)
    rb_fine = closed_form.solve_closed(c, pv, rp, rf)["r_b"]
    print(f"  {ex:26s} N = {len(rr):4d}: r_b = {rb_grid:.4f} м, мелкая = {rb_fine:.4f} м, "
          f"откл. {(rb_grid - rb_fine) / rb_fine * 100:+.2f} %")
