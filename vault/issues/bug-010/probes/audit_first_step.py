"""Аудит BUG-010: проверка варианта 3 (синхронное дробление гидро+энергии).

Установлено: ошибка рождается на ПЕРВОМ шаге (dt=450: -1.39 К против
эталона; dt=360: -0.10 К). Первый шаг -- резкое приложение депрессии,
там же срабатывает A-retry.

Гипотеза: дефект в том, что гидро дробит шаг, а энергия -- нет.
Энергия делает один большой шаг по полному dt.

Решающая проверка: пройти первый шаг dt=450 ДВУМЯ способами
  (а) как сейчас: hydro.solve(dt=450) [внутри дробит на 2] + energy.solve(dt=450)
  (б) вариант 3: два раза [hydro.solve(dt=225) + energy.solve(dt=225)]
и сравнить обе T с эталоном (мелкий шаг).

Если (б) резко ближе к эталону -- подтверждён вариант 3, а не осреднение.
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


def advance(sim, state, dt, n_energy=1):
    """Продвинуть на dt, разбив на n_energy шагов ГИДРО+ЭНЕРГИЯ вместе."""
    bc = sim._schedule.intervals[0].bc
    h, e = sim._hydro, sim._energy
    sub = dt / n_energy
    for _ in range(n_energy):
        hr = h.solve(state, sub, bc)
        T = e.solve(hr, state, sub, bc)
        state = SimulationState(p=hr.state.p, Sg=hr.state.Sg, Rs=hr.state.Rs,
                                T=T, regime=hr.state.regime, t=hr.state.t)
    return state


def main():
    dt = 450.0

    # Эталон: первый интервал времени 450 с, пройденный шагами по 50 с
    sim_ref, s_ref = build(50.0)
    st_ref = advance(sim_ref, s_ref, dt, n_energy=9)

    # (а) как сейчас: один шаг энергии на 450 с (гидро внутри дробит на 2)
    sim_a, s_a = build(dt)
    st_a = advance(sim_a, s_a, dt, n_energy=1)

    # (б) вариант 3: два шага гидро+энергия по 225 с
    sim_b, s_b = build(dt)
    st_b = advance(sim_b, s_b, dt, n_energy=2)

    print(f"Первый шаг, t: 0 -> {dt:g} с. Эталон -- 9 шагов по 50 с.\n")
    print(f"  эталон              T[0] = {st_ref.T[0]:.6f} К")
    print(f"  (а) энергия 1x450 с T[0] = {st_a.T[0]:.6f} К  "
          f"ошибка {st_a.T[0]-st_ref.T[0]:+.6f} К")
    print(f"  (б) энергия 2x225 с T[0] = {st_b.T[0]:.6f} К  "
          f"ошибка {st_b.T[0]-st_ref.T[0]:+.6f} К")
    print()
    ea = float(np.max(np.abs(st_a.T - st_ref.T)))
    eb = float(np.max(np.abs(st_b.T - st_ref.T)))
    print(f"  max|dT| (а) = {ea:.4e} К")
    print(f"  max|dT| (б) = {eb:.4e} К")
    print(f"  улучшение в {ea/eb:.1f} раз" if eb > 0 else "")

    # Состояния гидро у (а) и (б) -- одинаковы? (обе дробят на 2)
    print()
    print(f"  p совпадает между (а) и (б): "
          f"{np.allclose(st_a.p, st_b.p, rtol=1e-12)}")


if __name__ == "__main__":
    main()
