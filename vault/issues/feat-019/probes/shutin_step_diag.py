"""FEAT-019: одиночный шаг останова из развитой газовой зоны — какие dt сходятся.

Добыча n_prod суток по конфигу примера (как в примере), затем из конечного
состояния — одиночные model.advance прототипа (без A-retry адаптера) при
разных управлениях и dt:
  - продолжение добычи (контроль: шаг сходится);
  - p_wf = p_wf_target для нескольких значений между p_wf примера и p_ext
    (частичный и полный останов, eq:bc_pwf_shutin);
  - q_oil = 0 (eq:bc_rate_well).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-019\\probes\\shutin_step_diag.py 20 10
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod = sys.argv[1], int(sys.argv[2])
BASE = SOLVER / "examples" / BASES[base_key] / "config.json"

cfg = load_config(BASE)
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
hist = []
for _ in range(n_prod):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
cfg.time.history = hist
sim, init = SimulatorFactory.from_config(cfg)
t0 = time.perf_counter()
h = sim.run(init)
st = h.states[-1]
model = sim._hydro._model
p_wf0, p_ext = iv.p_wf, cfg.initial_conditions.p0
print(f"=== {BASES[base_key]}: {n_prod} сут добычи при {p_wf0/1e6:.2f} МПа "
      f"({time.perf_counter() - t0:.1f} с) ===")
print(f"состояние: p[0] = {st.p[0]/1e6:.4f} МПа, S_g(r_w) = {st.Sg[0]:.4f}, max S_g = {st.Sg.max():.4f}, "
      f"двухфазных {int(np.count_nonzero(st.regime == 1))} из {st.p.size}; p_ext = {p_ext/1e6:.2f} МПа")


def proto(s):
    return BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                         sg=s.Sg.copy(), gas_active=(s.regime == 1))


def try_step(label, set_control, dts):
    cells = []
    for dt in dts:
        set_control()
        t1 = time.perf_counter()
        new, rep = model.advance(proto(st), dt)
        el = time.perf_counter() - t1
        if rep.converged:
            sg = new.sg
            cells.append(f"{dt:>7.0f} с: ✓ it={rep.iterations:<3d} p0={new.pressure_bar[0]:7.2f} бар "
                         f"maxSg={sg.max():.3f} 2ф={int(np.count_nonzero(new.gas_active))} ({el:.1f} с)")
        else:
            cells.append(f"{dt:>7.0f} с: ✗ it={rep.iterations:<3d} res={rep.residual_inf:.1e} ({el:.1f} с)")
    print(f"\n── {label} ──")
    for c in cells:
        print("   " + c)


DTS = [1.0, 10.0, 60.0, 169.0, 600.0, 3600.0, 86400.0]
try_step(f"продолжение добычи p_wf = {p_wf0/1e6:.2f} МПа",
         lambda: model.set_bhp_control(p_wf0 / BAR_TO_PA), DTS)
for frac in (0.1, 0.25, 0.5, 1.0):
    target = p_wf0 + frac * (p_ext - p_wf0)
    try_step(f"p_wf = {target/1e6:.2f} МПа (доля {frac} от p_wf → p_ext)",
             lambda tg=target: model.set_bhp_control(tg / BAR_TO_PA), DTS)
try_step("q_oil = 0, min_bhp = 1 атм",
         lambda: model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA), DTS)
