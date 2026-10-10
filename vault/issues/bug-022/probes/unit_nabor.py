"""BUG-022: числа для модульных тестов условия по ячейке — фикстура прототипа Nabor_1b.

Шаг отбора (p_wf = 100 бар, p0 = 200 бар, без газа) на N ячейках: решение одним
абсолютным критерием (код базы), мера по ячейкам m0 = max_c |f_c,i|*dt/PV_i на нём;
затем тот же шаг на эмуляции плана (cell_tol.py, жёсткий вариант) с eps = m0/10 и m0/100:
сходится ли, сколько итераций, мера на решении. Эмуляция включает условие на всех
моделях (без отметки фабрики).
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\unit_nabor.py
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
NABOR = cell_tol.SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3" / "tests" / "fixtures" / "Nabor_1b.xlsx"
ORIG = (RadialBlackOilModel._newton_fixed_active_set, RadialBlackOilModel._newton_switching)


def build(n, bhp=100.0, p0=200.0):
    inp = load_input(NABOR)
    p = inp.params
    g = RadialGrid(float(p["Well radius rw"]), float(p["Outer radius re"]), float(p["Formation thickness h"]),
                   n, float(p["Absolute permeability"]))
    r = CompressibleRock(float(p["Reference porosity"]), float(p["Reference pressure"]), float(p["Rock compressibility cr"]))
    m = RadialBlackOilModel(g, r, inp.pvt, inp.relperm, bhp, float(p["Outer-boundary pressure"]),
                            float(p["Initial dissolved gas Rs"]), skin=float(p["Well skin"]), linear_solver="sparse")
    s = BlackOilState.undersaturated(g.n, p0, float(p["Initial dissolved gas Rs"]))
    return m, s, p


def metric(m, s_old, s_new, dt):
    f = m.residual(m.pack(s_new), s_old, dt, s_new.gas_active)
    w = dt / m.rock.pore_volume_m3(m.grid.bulk_volumes_m3, s_old.pressure_bar)
    n = m.grid.n
    return max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w))), float(np.linalg.norm(f, np.inf))


for n in (8, 12, 50):
    for dt in (300.0, 3600.0):
        RadialBlackOilModel._newton_fixed_active_set, RadialBlackOilModel._newton_switching = ORIG
        m, s, p = build(n)
        new, rep = m.advance(s, dt)
        m0, r0 = metric(m, s, new, dt)
        pv = m.rock.pore_volume_m3(m.grid.bulk_volumes_m3, s.pressure_bar)
        line = (f"N={n:<3} dt={dt:<6} r_w={float(p['Well radius rw'])} r_e={float(p['Outer radius re'])} "
                f"PV {pv.min():.3e}..{pv.max():.3e}; база: сошлось {rep.converged}, итераций {rep.iterations}, "
                f"||f|| {r0:.2e}, мера {m0:.2e}")
        for k in (10.0, 100.0, 1e4):
            cell_tol.install(f"pv{m0 / k:.3e}")
            m2, s2, _ = build(n)
            new2, rep2 = m2.advance(s2, dt)
            m2v, r2 = metric(m2, s2, new2, dt)
            line += (f" | eps=m0/{k:g}: сошлось {rep2.converged}, итераций {rep2.iterations}, "
                     f"мера {m2v:.2e}, |dp| {np.max(np.abs(new2.pressure_bar - new.pressure_bar)):.1e} бар")
        print(line)
