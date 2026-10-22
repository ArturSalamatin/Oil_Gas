"""BUG-022: числа для модульных тестов ступени 4 (_newton_switching) с условием по ячейке.

1. Nabor_1b, N = 50, dt = 3600 с, отбор: _newton_switching напрямую — база и eps = 1e-8.
2. Сценарий tests/data/bug020_rs300 (10 сут добычи, фабрика, код базы) -> шаг останова
   q_oil = 0, dt = 168.75 с (DT_STAGE4 тестов BUG-020): _newton_switching — база и eps = 1e-8.
Для каждого: сошлось, итераций, мера по ячейкам max_c |f_c,i|*dt/PV_i, |dp| между решениями.
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\unit_stage4.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cell_tol  # noqa: E402
import unit_nabor as un  # noqa: E402  (печатает свою таблицу при импорте)

from radial_blackoil.blackoil import RadialBlackOilModel  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

BAR = 1e5


def metric(m, s_old, s_new, dt):
    f = m.residual(m.pack(s_new), s_old, dt, s_new.gas_active)
    w = dt / m.rock.pore_volume_m3(m.grid.bulk_volumes_m3, s_old.pressure_bar)
    n = m.grid.n
    return max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w)))


def solve4(m, s, dt, variant):
    RadialBlackOilModel._newton_fixed_active_set, RadialBlackOilModel._newton_switching = un.ORIG
    if variant != "0":
        cell_tol.install(variant)
    new, rep = m._newton_switching(s, dt)
    return new, rep, metric(m, s, new, dt)


print("\n== ступень 4 напрямую")
m, s, _ = un.build(50)
a, ra, ma = solve4(m, s, 3600.0, "0")
b, rb, mb = solve4(m, s, 3600.0, "pv1e-8")
print(f"Nabor N=50 dt=3600: база сошлось {ra.converged} итераций {ra.iterations} мера {ma:.2e}; "
      f"eps=1e-8: сошлось {rb.converged} итераций {rb.iterations} мера {mb:.2e}; "
      f"|dp| {np.max(np.abs(a.pressure_bar - b.pressure_bar)):.1e} бар")

RadialBlackOilModel._newton_fixed_active_set, RadialBlackOilModel._newton_switching = un.ORIG
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
cfg = load_config(cell_tol.SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
sim, init = SimulatorFactory.from_config(cfg)
st = sim.run(init).states[-1]
model = sim._hydro._model
ps = BlackOilState(pressure_bar=st.p / BAR, rs_sm3_sm3=st.Rs.copy(), sg=st.Sg.copy(), gas_active=(st.regime == 1))
model.set_oil_rate_control(0.0, 101325.0 / BAR)
for dt in (168.75, 60.0):
    a, ra, ma = solve4(model, ps, dt, "0")
    b, rb, mb = solve4(model, ps, dt, "pv1e-8")
    print(f"rs300 останов dt={dt}: база сошлось {ra.converged} итераций {ra.iterations} мера {ma:.2e}; "
          f"eps=1e-8: сошлось {rb.converged} итераций {rb.iterations} мера {mb:.2e}; "
          f"|dp| {np.max(np.abs(a.pressure_bar - b.pressure_bar)):.1e} бар")
