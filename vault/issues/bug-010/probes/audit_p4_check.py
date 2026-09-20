"""Аудит BUG-010: разрешение конфликта плана с проектным решением P4.

P4 постулирует: потоки наружу — мгновенные при итоговом state^{n+1},
"это то, что нужно EnergySolver для конвекции (неявная схема)".

План BUG-010 объявляет это дефектом и предлагает осреднение по подшагам.

Кто прав? Ключевой вопрос: при n_sub = 1 (retry не сработал) мгновенный
поток при state^{n+1} — это ровно то, что даёт неявная схема. Осреднение
при n_sub = 1 тождественно тому же. Расхождение возникает ТОЛЬКО при
n_sub > 1.

Решающий тест: сравнить три величины при аномальном dt = 450 с
  (а) мгновенный поток при финальном состоянии всего шага dt=450
      -- то, что дало бы БЕЗ дробления, если бы Ньютон сошёлся;
  (б) мгновенный поток последнего подшага (текущее поведение);
  (в) среднее по подшагам (предложение плана).
Эталон: мелкий прогон dt = 50 с, где дробления нет вовсе.

Если (а) ближе к эталону, чем (б) -- дефект в том, что поток берётся
при состоянии ПОДШАГА, а не всего шага, и осреднение -- не единственный
и, возможно, не лучший фикс.
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


def build(dt, max_retries=None):
    cfg = copy.deepcopy(load_config(CFG))
    cfg.time.dt_integration = float(dt)
    cfg.time.history = cfg.time.history[:1]
    if max_retries is not None:
        cfg.numerics.max_retries = int(max_retries)
    return SimulatorFactory.from_config(cfg)


def main():
    dt = 450.0
    sim, state0 = build(dt)
    bc = sim._schedule.intervals[0].bc
    hydro = sim._hydro

    # (б) текущее поведение: retry дробит на 2, отдаёт поток последнего подшага
    res_retry = hydro.solve(state0, dt, bc)

    # Разложим вручную на два подшага по 225 с
    half = dt / 2.0
    r1 = hydro.solve(state0, half, bc)
    mid = SimulationState(p=r1.state.p, Sg=r1.state.Sg, Rs=r1.state.Rs,
                          T=state0.T.copy(), regime=r1.state.regime, t=r1.state.t)
    r2 = hydro.solve(mid, half, bc)

    g_last = r2.G_o[0]
    g_mean = 0.5 * (r1.G_o[0] + r2.G_o[0])

    print(f"Состояние после шага dt={dt:g} с (оба пути дают одно и то же состояние):")
    print(f"  p[0] retry  = {res_retry.state.p[0]:.6f} Па")
    print(f"  p[0] вручную= {r2.state.p[0]:.6f} Па")
    print(f"  совпадают: {np.allclose(res_retry.state.p, r2.state.p)}")
    print()

    # (а) Мгновенный поток ПРИ ФИНАЛЬНОМ СОСТОЯНИИ всего шага.
    # Это то, что вернула бы схема без дробления. Состояние то же самое,
    # значит и мгновенный поток тот же -- проверим это утверждение.
    print(f"Забойный поток G_o[0], ст.куб.м/с:")
    print(f"  (б) поток последнего подшага / retry: {g_last:.6e}")
    print(f"  (в) среднее по подшагам:              {g_mean:.6e}")
    print()

    # Эталон: как ведёт себя мгновенный поток при мелком шаге в тот же
    # момент времени t = 450 с.
    sim_f, s0f = build(50.0)
    bcf = sim_f._schedule.intervals[0].bc
    hf = sim_f._hydro
    st = s0f
    for _ in range(9):           # 9 x 50 c = 450 c
        rf = hf.solve(st, 50.0, bcf)
        st = SimulationState(p=rf.state.p, Sg=rf.state.Sg, Rs=rf.state.Rs,
                             T=st.T.copy(), regime=rf.state.regime, t=rf.state.t)
    print(f"  эталон dt=50 с, мгновенный поток при t=450 с: {rf.G_o[0]:.6e}")
    print(f"  состояние p[0] эталона: {rf.state.p[0]:.6f} Па")
    print()
    print("ВЫВОД по потоку:")
    print(f"  |последний подшаг - эталон| = {abs(g_last - rf.G_o[0]):.3e}")
    print(f"  |среднее         - эталон| = {abs(g_mean - rf.G_o[0]):.3e}")


if __name__ == "__main__":
    main()
