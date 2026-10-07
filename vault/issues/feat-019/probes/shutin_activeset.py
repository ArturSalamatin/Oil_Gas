"""FEAT-019: отказ шага останова — цикл набора активных фаз (лимит или зацикливание).

Добыча n_prod суток по конфигу примера, затем из конечного состояния — один
model.advance прототипа при p_wf = p_ext (полный останов) с разными dt и
лимитом max_active_iter (штатно 12). Обёртка _newton_fixed_active_set пишет
маску двухфазных ячеек на каждой итерации набора фаз: повтор маски —
зацикливание, монотонное убывание — медленное продвижение фронта растворения.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-019\\probes\\shutin_activeset.py 20 10
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
         "19": "19_rs150_cooling", "21": "21_rs100_cooling"}
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
h = sim.run(init)
st = h.states[-1]
model = sim._hydro._model
p_ext = cfg.initial_conditions.p0

masks = []
_orig = model._newton_fixed_active_set


def recording(z0, state_old, dt_s, gas_active, **kw):
    masks.append(gas_active.copy())
    z, rep = _orig(z0, state_old, dt_s, gas_active, **kw)
    masks[-1] = (masks[-1], rep.converged, rep.iterations)
    return z, rep


model._newton_fixed_active_set = recording


def proto(s):
    return BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                         sg=s.Sg.copy(), gas_active=(s.regime == 1))


print(f"=== {BASES[base_key]}: останов p_wf = p_ext = {p_ext/1e6:.2f} МПа после {n_prod} сут; "
      f"2ф = {int(np.count_nonzero(st.regime == 1))}, max S_g = {st.Sg.max():.4f} ===")
for dt in (60.0, 600.0, 3600.0, 86400.0):
    for mai in (12, 40, 150):
        masks.clear()
        model.set_bhp_control(p_ext / BAR_TO_PA)
        t1 = time.perf_counter()
        new, rep = model.advance(proto(st), dt, max_active_iter=mai)
        el = time.perf_counter() - t1
        # Разбор итераций набора фаз по всем вызовам _advance_phases этого шага
        n2 = [int(np.count_nonzero(m)) for m, _, _ in masks]
        keys = [m.tobytes() for m, _, _ in masks]
        repeats = sum(1 for k in range(len(keys)) if keys[k] in keys[:k])
        conv = sum(1 for _, c, _ in masks if c)
        tag = "✓" if rep.converged else "✗"
        print(f"dt = {dt:7.0f} с, max_active_iter = {mai:3d}: {tag} ({el:.1f} с); "
              f"решений с фикс. набором {len(masks)} (Ньютон сошёлся в {conv}); "
              f"повторов маски {repeats}; fallback={getattr(rep, 'fallback', False)}, "
              f"globalized={getattr(rep, 'globalized', False)}")
        print(f"    2ф по итерациям: {n2[:40]}{' …' if len(n2) > 40 else ''}")
        if rep.converged:
            print(f"    итог: p[0] = {new.pressure_bar[0]:.2f} бар, max S_g = {new.sg.max():.4f}, "
                  f"2ф = {int(np.count_nonzero(new.gas_active))}")
            break
