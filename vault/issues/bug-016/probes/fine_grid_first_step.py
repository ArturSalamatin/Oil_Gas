"""FEAT-024: почему пример 14 не делает первый шаг на сетке N = 100 / 150.

Первый шаг (скачок p_wf 24.5 -> 6 МПа из недонасыщенного состояния) на
модели прототипа напрямую, с журналом каждого вызова Ньютона на
фиксированном наборе фаз и причин отказа пробных векторов в линейном поиске.

Запуск (из numerical_solver рабочего дерева .worktrees/feat-024):
    python <этот файл> N dt_s [dt_s ...]
"""

import collections
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("HydroSolverPrototype/Prototype_1.0.3").resolve()))
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.blackoil import BlackOilState  # noqa: E402

BAR = 1e5
N = int(sys.argv[1])
dts = [float(a) for a in sys.argv[2:]] or [86400.0]

cfg = load_config(Path("examples/14_high_gor_cooling/config.json"))
cfg.grid.N = N
sim, init = SimulatorFactory.from_config(cfg)
model = sim._hydro._model
g = sim._grid
print(f"N = {N}: первая ячейка {g.r_centers[0]:.4f} м, "
      f"ширина {g.r_faces[1] - g.r_faces[0]:.4f} м" if hasattr(g, "r_faces") else f"N = {N}")
model.set_bhp_control(6.0e6 / BAR)

# ── Журнал: вызовы Ньютона и причины отказа пробных векторов ──
calls = []
reject = collections.Counter()
orig_newton = model._newton_fixed_active_set
orig_reasonable = model._trial_is_reasonable


def reasonable(z, gas_active):
    n = model.grid.n
    p, x = z[:n], z[n:]
    ok = orig_reasonable(z, gas_active)
    if not ok:
        if not np.all(np.isfinite(z)):
            reject["не конечен"] += 1
        elif np.any(p <= 1.0):
            reject["p <= 1 бар"] += 1
        elif np.any(x[gas_active] > 0.98):
            reject["S_g > 0.98"] += 1
        elif model._sg_lower_bound is not None and np.any(x[gas_active] < model._sg_lower_bound):
            reject["S_g < -0.05"] += 1
        else:
            reject["R_s вне границ"] += 1
    return ok


def newton(z0, state_old, dt_s, gas_active, **kw):
    before = dict(reject)
    z, rep = orig_newton(z0, state_old, dt_s, gas_active, **kw)
    n = model.grid.n
    sg = z[n:][gas_active]
    calls.append(dict(active=int(gas_active.sum()), ok=rep.converged, it=rep.iterations,
                      res=rep.residual_inf, p_min=z[:n].min() * BAR / 1e6,
                      sg_max=float(sg.max()) if sg.size else 0.0,
                      new_rej={k: reject[k] - before.get(k, 0) for k in reject
                               if reject[k] - before.get(k, 0)}))
    return z, rep


model._newton_fixed_active_set = newton
model._trial_is_reasonable = reasonable

s0 = BlackOilState(pressure_bar=init.p / BAR, rs_sm3_sm3=init.Rs.copy(),
                   sg=init.Sg.copy(), gas_active=(init.regime == 1))
for dt in dts:
    calls.clear()
    reject.clear()
    new, rep = model.advance(s0, dt)
    print(f"\n── dt = {dt:g} с: сошёлся = {rep.converged}, "
          f"fallback = {getattr(rep, 'fallback', False)}, "
          f"итераций набора = {getattr(rep, 'active_set_iterations', '?')}")
    for k, c in enumerate(calls):
        print(f"  {k:2d}: активных {c['active']:3d}  сошёлся {str(c['ok']):5s} "
              f"итер {c['it']:2d}  невязка {c['res']:.2e}  p_min {c['p_min']:6.3f} МПа  "
              f"S_g max {c['sg_max']:.3f}  отказы {c['new_rej']}")
    if rep.converged:
        print(f"  итог: двухфазных {int(new.gas_active.sum())}, S_g[0] = {new.sg[0]:.4f}, "
              f"p[0] = {new.pressure_bar[0] / 10:.3f} МПа")
