"""Аудит BUG-010: где в траектории рождается 0.48 К?

Установлено: ни cum_ad, ни cum_conv не объясняют скачок -- оба
меняются гладко и у аномальных шагов даже ЛУЧШЕ, чем у чистого dt=600.

Значит дело в траектории T. Отследим T[0] шаг за шагом для
аномального dt=450 (8 шагов) и чистого dt=360 (10 шагов),
сравнивая с эталоном dt=50 в те же моменты времени.

Ищем: ошибка накапливается плавно или рождается на ОДНОМ шаге?
"""

import copy
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
_PROTO = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
for _p in (str(_PROTO), str(_ROOT / "examples")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402

CFG = _ROOT / "examples" / "07_degassing_adiabatic_only" / "config.json"


def build(dt):
    cfg = copy.deepcopy(load_config(CFG))
    cfg.time.dt_integration = float(dt)
    cfg.time.history = cfg.time.history[:1]
    return SimulatorFactory.from_config(cfg)


def trajectory(dt, total=3600.0):
    """Список (t, T[0], max T, признак что гидро дробил) по шагам."""
    sim, state = build(dt)
    bc = sim._schedule.intervals[0].bc
    hydro, energy = sim._hydro, sim._energy

    out = [(0.0, float(state.T[0]))]
    n = int(round(total / dt))
    for _ in range(n):
        hr = hydro.solve(state, dt, bc)
        T_new = energy.solve(hr, state, dt, bc)
        state = SimulationState(p=hr.state.p, Sg=hr.state.Sg, Rs=hr.state.Rs,
                                T=T_new, regime=hr.state.regime, t=hr.state.t)
        out.append((float(state.t), float(state.T[0])))
    return out


def interp_ref(ref, t):
    ts = np.array([r[0] for r in ref])
    vs = np.array([r[1] for r in ref])
    return float(np.interp(t, ts, vs))


def main():
    ref = trajectory(50.0)

    for dt in (450.0, 360.0):
        tr = trajectory(dt)
        n_sub = int(np.ceil(3600.0 / dt))
        tag = "АНОМАЛЬНЫЙ" if n_sub in (3, 5, 8, 9) else "чистый"
        print(f"\ndt = {dt:g} с ({tag}), {len(tr)-1} шагов энергии")
        print(f"{'t, с':>8} {'T[0], К':>12} {'эталон':>12} {'ошибка, К':>12} "
              f"{'прирост ош.':>12}")
        prev = 0.0
        for t, T in tr:
            r = interp_ref(ref, t)
            err = T - r
            print(f"{t:8.0f} {T:12.6f} {r:12.6f} {err:12.6f} {err - prev:12.6f}")
            prev = err


if __name__ == "__main__":
    main()
