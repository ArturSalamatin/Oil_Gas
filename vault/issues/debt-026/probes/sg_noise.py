"""Аудит DEBT-026: двухфазные по режиму ячейки без свободного газа.

На последней записи для каждого примера: сколько ячеек regime == 1 имеют
S_g выше порогов 0, 1e-12, 1e-8; у ячеек regime == 1 с S_g <= 1e-8 —
диапазон S_g, p - p_b и Rs - Rs_eq(p). Нужна для выбора критерия
«двухфазная ячейка» в rs_analytics: режим решателя или наличие газа.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-026\\probes\\sg_noise.py 04_table_table 04a_high_gas_saturation
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EXAMPLES = SOLVER / "examples"

for name in sys.argv[1:]:
    cfg = load_config(EXAMPLES / name / "config.json")
    Rs0 = cfg.initial_conditions.Rs0
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    pvt = sim._energy._pvt
    pb = float(pvt.pb(np.array([Rs0]))[0])
    r = sim._grid.r_centers
    print(f"\n=== {name}: записей {len(hist.states)} ===")
    for n in sorted({len(hist.states) - 1}):
        st = hist.states[n]
        two = st.regime == 1
        print(f"  запись {n} (t = {st.t / 86400:.3f} сут): regime 1: {int(two.sum())}; "
              f"Sg>0: {int((st.Sg > 0).sum())}, Sg>1e-12: {int((st.Sg > 1e-12).sum())}, "
              f"Sg>1e-8: {int((st.Sg > 1e-8).sum())}; p<pb: {int((st.p < pb).sum())}")
        noise = two & (st.Sg <= 1e-8)
        for j in np.where(noise)[0]:
            print(f"    ячейка {j:3d}  r = {r[j]:8.3f} м  Sg = {st.Sg[j]:.2e}  "
                  f"p - pb = {(st.p[j] - pb) / 1e3:+9.2f} кПа  "
                  f"Rs - Rs_eq = {st.Rs[j] - float(pvt.Rs_eq(st.p[j:j + 1])[0]):+.2e}")
        gas_above = (st.Sg > 1e-8) & (st.p >= pb)
        if gas_above.any():
            print(f"  газ (Sg > 1e-8) при p >= pb: {int(gas_above.sum())} ячеек, "
                  f"Sg от {st.Sg[gas_above].min():.2e} до {st.Sg[gas_above].max():.2e}")
