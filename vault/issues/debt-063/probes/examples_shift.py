"""DEBT-063, проба: на сколько меняются примеры при центрах √(r_{j-1/2}·r_{j+1/2}).

Каждый пример ALL_EXAMPLES (tests/test_examples.py) считается дважды: с
текущими центрами LogRadialGrid (exp<ln r>, eq:cell_center) и с центрами
прототипа — подменой функции центров в модуле log_radial (как
sqrt_centers_plugin.py). Ожидание: гидродинамика (p, S_g, R_s, дебиты)
побитово та же — прототип наших центров не видит, температура обратно на
гидродинамику не влияет; меняется только T (веса λ и контурная
кондуктивная проводимость энергии).

Печатает по примеру: N; совпадение p, S_g, q_o (побитово / max отличие);
max_t |ΔT(r_w)|; |ΔT(r_w)| в конце; max_{t,j} |ΔT|; подъём/падение T у
забоя за расчёт (масштаб, к которому относить ΔT).

Запуск из numerical_solver/:  .venv\\Scripts\\python -u ..\\vault\\issues\\debt-063\\probes\\examples_shift.py
"""

import sys
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import numpy as np

import gpn_multiphase_solver.grid.log_radial as lr
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory

sys.path.insert(0, str(SOLVER / "tests"))
from test_examples import ALL_EXAMPLES, EXAMPLES_DIR  # noqa: E402

ORIG = lr._cell_centers_mass


def run(name, sqrt):
    """История примера с текущими центрами или с √."""
    lr._cell_centers_mass = (lambda a, b: np.sqrt(a * b)) if sqrt else ORIG
    try:
        cfg = load_config(EXAMPLES_DIR / name / "config.json")
        sim, init = SimulatorFactory.from_config(cfg)
        h = sim.run(init)
    finally:
        lr._cell_centers_mass = ORIG
    P = np.array([s.p for s in h.states])
    S = np.array([s.Sg for s in h.states])
    T = np.array([s.T for s in h.states])
    q = np.array([w.q_o_std for w in h.well_data])
    return sim._grid.N, P, S, T, q


print(f"{'пример':28s} {'N':>4s} {'p,S_g,q_o':>10s} {'max|ΔT_w|':>10s} "
      f"{'|ΔT_w| кон.':>11s} {'max|ΔT|':>9s} {'ΔT_w за расчёт':>15s}")
for name in ALL_EXAMPLES:
    N, P0, S0, T0, q0 = run(name, sqrt=False)
    _, P1, S1, T1, q1 = run(name, sqrt=True)
    if P0.shape != P1.shape or q0.shape != q1.shape:
        print(f"{name:28s} {N:4d}  разное число записей: {P0.shape} / {P1.shape}")
        continue
    same = (np.array_equal(P0, P1) and np.array_equal(S0, S1)
            and np.array_equal(q0, q1))
    hyd = "побитово" if same else (
        f"{max(np.max(np.abs(P1 - P0)), np.max(np.abs(S1 - S0))):.1e}")
    dTw = np.abs(T1[:, 0] - T0[:, 0])
    span = T0[:, 0].max() - T0[:, 0].min()
    print(f"{name:28s} {N:4d} {hyd:>10s} {dTw.max():10.2e} {dTw[-1]:11.2e} "
          f"{np.max(np.abs(T1 - T0)):9.2e} {span:15.3f}")
