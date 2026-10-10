"""BUG-022: числа модульных тестов плана при eps = 1e-8 ровно (эмуляция плана, жёсткий вариант).

1. Nabor_1b, отбор p_wf = 100 бар, dt = 3600 с: N = 50 (база недорешает забой) и N = 8
   (база уже в пределах eps) — advance: сошлось, итераций, мера, побитовость при N = 8.
2. Сценарий bug020_rs300: 10 сут добычи на эмуляции плана (условие у модели фабрики, как
   будет в коде) -> шаг останова q_oil = 0, dt = 168.75 с: _newton_switching при
   cell_tol выключенном и 1e-8.
3. B_o в забойной ячейке примера 17 на конце (для границы ошибки R_s в docstring теста).
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\unit_check.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cell_tol  # noqa: E402

from radial_blackoil.blackoil import RadialBlackOilModel  # noqa: E402
from radial_blackoil.grid import RadialGrid  # noqa: E402
from radial_blackoil.input_reader import load_input  # noqa: E402
from radial_blackoil.rock import CompressibleRock  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BAR = 1e5
NABOR = cell_tol.SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3" / "tests" / "fixtures" / "Nabor_1b.xlsx"
ORIG = (RadialBlackOilModel._newton_fixed_active_set, RadialBlackOilModel._newton_switching)
out_lines = []


def out(s):
    print(s, flush=True)
    out_lines.append(s)


def build(n):
    inp = load_input(NABOR)
    p = inp.params
    g = RadialGrid(float(p["Well radius rw"]), float(p["Outer radius re"]), float(p["Formation thickness h"]),
                   n, float(p["Absolute permeability"]))
    r = CompressibleRock(float(p["Reference porosity"]), float(p["Reference pressure"]), float(p["Rock compressibility cr"]))
    m = RadialBlackOilModel(g, r, inp.pvt, inp.relperm, 100.0, float(p["Outer-boundary pressure"]),
                            float(p["Initial dissolved gas Rs"]), skin=float(p["Well skin"]), linear_solver="sparse")
    return m, BlackOilState.undersaturated(g.n, 200.0, float(p["Initial dissolved gas Rs"]))


def measure(m, s_old, s_new, dt):
    f = m.residual(m.pack(s_new), s_old, dt, s_new.gas_active)
    w = dt / m.rock.pore_volume_m3(m.grid.bulk_volumes_m3, s_old.pressure_bar)
    n = m.grid.n
    return max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w)))


def use(variant):
    RadialBlackOilModel._newton_fixed_active_set, RadialBlackOilModel._newton_switching = ORIG
    if variant != "0":
        cell_tol.install(variant)
    cell_tol.CELL["require_mark"] = False


out("== 1. Nabor_1b, dt = 3600 с, advance")
for n in (50, 8):
    use("0")
    m, s = build(n)
    a, ra = m.advance(s, 3600.0)
    use("pv1e-8")
    m2, s2 = build(n)
    b, rb = m2.advance(s2, 3600.0)
    same = all(np.array_equal(getattr(a, k), getattr(b, k)) for k in ("pressure_bar", "rs_sm3_sm3", "sg", "gas_active"))
    out(f"N={n}: база сошлось {ra.converged} итераций {ra.iterations} мера {measure(m, s, a, 3600.0):.3e}; "
        f"eps=1e-8 сошлось {rb.converged} итераций {rb.iterations} мера {measure(m2, s2, b, 3600.0):.3e}; "
        f"max|dp| {np.max(np.abs(a.pressure_bar - b.pressure_bar)):.2e} бар; побитово {same}")

out("== 2. rs300: добыча на эмуляции плана, шаг останова ступенью 4")
from gpn_multiphase_solver import factory  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
use("pv1e-8")
cell_tol.CELL["require_mark"] = True
orig_create = factory._create_prototype_hydro


def create(*a, **k):
    h = orig_create(*a, **k)
    h._model._probe_cell = True
    return h


factory._create_prototype_hydro = create
cfg = load_config(cell_tol.SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
sim, init = SimulatorFactory.from_config(cfg)
st = sim.run(init).states[-1]
model = sim._hydro._model
ps = BlackOilState(pressure_bar=st.p / BAR, rs_sm3_sm3=st.Rs.copy(), sg=st.Sg.copy(), gas_active=(st.regime == 1))
out(f"после добычи: p(r_w) = {ps.pressure_bar[0]:.4f} бар, двухфазных {int(ps.gas_active.sum())}, max S_g = {ps.sg.max():.4f}")
model.set_oil_rate_control(0.0, 101325.0 / BAR)
for dt in (168.75,):
    model._probe_cell = False          # условие выключено (cell_tol = None)
    a, ra = model._newton_switching(ps, dt)
    ma = measure(model, ps, a, dt)
    model._probe_cell = True           # cell_tol = 1e-8
    b, rb = model._newton_switching(ps, dt)
    mb = measure(model, ps, b, dt)
    out(f"dt={dt}: выкл. сошлось {ra.converged} итераций {ra.iterations} мера {ma:.3e}; "
        f"1e-8 сошлось {rb.converged} итераций {rb.iterations} мера {mb:.3e}; "
        f"max|dp| {np.max(np.abs(a.pressure_bar - b.pressure_bar)):.2e} бар")

out("== 3. B_o забоя примера 17 на конце")
h = np.load(HERE / "hist_17_shut_in_strong_cooling_pv1e-8.npz")
cfg17 = load_config(cell_tol.SOLVER / "examples" / "17_shut_in_strong_cooling" / "config.json")
sim17, _ = SimulatorFactory.from_config(cfg17)
m17 = sim17._hydro._model
p0, rs0 = h["p"][-1, 0] / BAR, h["Rs"][-1, 0]
bo = float(m17.pvt.bo(np.array([p0]), np.array([rs0]))[0])
out(f"p = {p0:.4f} бар, R_s = {rs0:.5f}, B_o = {bo:.4f}, gas_residual_scale = {m17.gas_residual_scale}; "
    f"граница за шаг eps*B_o*(s+R_s) = {1e-8 * bo * (m17.gas_residual_scale + rs0):.3e}")
(HERE / "unit_check.out.txt").write_text("\n".join(out_lines) + "\n", encoding="utf-8")
