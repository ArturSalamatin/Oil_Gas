"""DEBT-055, проба планирования: из чего складывается предел округления меры ячейки.

m_J = max_i (|J| @ ulp(z))_i * dt / V_p,i (floor_probe.py) раскладывается на вклад столбцов
давления (ulp только у p) и столбцов второй переменной (S_g или R_s): какой из них задаёт
предел, и где (ячейка, строка). Плюс: предел у ступени 4 при недостижимом пороге (1e-30) —
доходит ли её Ньютон до него (мера/m_J), как у ступеней 1-3 (failures_floor.out.txt).

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-055\\probes\\floor_split.py
"""
import copy
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
HERE = Path(__file__).resolve().parent

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config      # noqa: E402
from radial_blackoil.state import BlackOilState               # noqa: E402

BAR = 1e5
OUT = open(HERE / "floor_split.out.txt", "w", encoding="utf-8")


def out(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


def mx(model, v, w):
    n = model.grid.n
    a, b = np.abs(v[:n]) * w, np.abs(v[n:]) * w
    return f"{a.max():.2e} (o{int(np.argmax(a))}) / {b.max():.2e} (g{int(np.argmax(b))})"


cfg = load_config(SOLVER / "examples" / "17_shut_in_strong_cooling" / "config.json")
cfg.output.log_level = "ERROR"
h0 = copy.deepcopy(cfg.time.history[0])
h0.duration = 2 * 86400.0
cfg.time.history = [h0]
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
st = BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(), sg=s.Sg.copy(),
                   gas_active=(s.regime == 1))
n = model.grid.n
out(f"SOLVER = {SOLVER}; пример 17, N = {n}, после 2 сут добычи")
for control in ("добыча", "останов"):
    if control == "добыча":
        model.set_bhp_control(cfg.time.history[0].p_wf / BAR)
    else:
        model.set_oil_rate_control(0.0, 101325.0 / BAR)
    dt = 3600.0
    new, rep = model.advance(st, dt)
    mask = new.gas_active.copy()
    z = model.pack(new, mask)
    w = dt / model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, st.pressure_bar)
    J, f = model.finite_difference_jacobian(z, st, dt, mask)
    ulp = np.spacing(np.abs(z))
    up, ux = ulp.copy(), ulp.copy()
    up[n:] = 0.0
    ux[:n] = 0.0
    out(f"\n{control}, dt = {dt:g} с (строки нефть / газ: max и ячейка)")
    out(f"  мера |F|              : {mx(model, f, w)}")
    out(f"  m_J полный            : {mx(model, abs(J) @ ulp, w)}")
    out(f"  m_J только давление   : {mx(model, abs(J) @ up, w)}")
    out(f"  m_J только S_g / R_s  : {mx(model, abs(J) @ ux, w)}")

# Ступень 4 на недостижимом пороге: где останавливается её Ньютон относительно m_J
model.set_oil_rate_control(0.0, 101325.0 / BAR)
for dt in (3600.0, 168.75):
    tol0 = model.cell_tol
    try:
        model.cell_tol = 1e-30
        new, rep = model._newton_switching(st, dt)
    finally:
        model.cell_tol = tol0
    mask = new.gas_active.copy()
    z = model.pack(new, mask)
    w = dt / model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, st.pressure_bar)
    J, f = model.finite_difference_jacobian(z, st, dt, mask)
    mj = model._cell_measure(abs(J) @ np.spacing(np.abs(z)), w)
    out(f"\nступень 4, порог 1e-30, dt = {dt:g} с: выход {rep.exit_reason}, итераций {rep.iterations}, "
        f"мера {rep.cell_measure:.3e}, m_J {mj:.3e}, мера/m_J {rep.cell_measure / mj:.2f}")
