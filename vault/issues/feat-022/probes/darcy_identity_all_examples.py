"""FEAT-022: тождество Дарси с местным G^g/G^o на последней записи всех двухфазных примеров.

Для каждой двухфазной ячейки j (грань j — её внутренняя сторона, поток к
скважине, ячейка j выше по потоку): решаем относительно Sg

    Rs_j + krg/kro(Sg) · (mu_o Bo)/(mu_g Bg)_j = G^g_j / G^o_j

и сравниваем с численной Sg_j. Отдельно — ячейки, где газ НЕПОДВИЖЕН
(krg(Sg_j) = 0, Кори с порогом S_gc): там тождество не обращается — любое
Sg <= S_gc даёт то же отношение потоков. Для сравнения — прежняя проверка
(стационарное замыкание GOR = Rs0 при численном p).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-022\\probes\\darcy_identity_all_examples.py
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from closed_form import Closure  # noqa: E402

NAMES = ["03_standing_corey", "04_table_table", "04a_high_gas_saturation",
         "05_standing_table_rp", "06_table_corey_rp", "07_degassing_adiabatic_only",
         "10_deep_degassing", "11_degassing_at_boundary", "12_large_drainage_radius",
         "13a_pwf_ramp_down"]

print(f"{'пример':<28} {'2ф':>4} {'непод.':>6} {'G_o<0':>6} {'|dSg| местн':>12} "
      f"{'|dSg| Rs0':>10} {'max GOR-Rs0':>12} {'t, с':>6}")
for name in NAMES:
    t0 = time.perf_counter()
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    h = sim.run(init)
    pvt, rp = sim._energy._pvt, _create_relperm(cfg)
    st, hr = h.states[-1], h.hydro_results[-1]
    N = len(st.p)
    Rs0 = cfg.initial_conditions.Rs0
    two = np.nonzero(st.Sg > 0)[0]
    mobile = np.array([j for j in two if rp.krg(np.array([st.Sg[j]]))[0] > 0.0], dtype=int)
    all_neg = bool(np.all(hr.G_o[:N] < 0.0))
    gor = hr.G_g[:N] / hr.G_o[:N]
    d_loc = max((abs(Closure(pvt, rp, gor[j]).Sg(st.p[j]) - st.Sg[j]) for j in mobile),
                default=0.0)
    d_st = max((abs(Closure(pvt, rp, Rs0).Sg(st.p[j]) - st.Sg[j]) for j in two), default=0.0)
    dgor = float(np.max(np.abs(gor[two] - Rs0))) if two.size else 0.0
    print(f"{name:<28} {two.size:4d} {two.size - mobile.size:6d} {str(all_neg):>6} "
          f"{d_loc:12.2e} {d_st:10.2e} {dgor:12.2e} {time.perf_counter() - t0:6.1f}")
    if two.size - mobile.size:
        imm = [j for j in two if j not in set(mobile)]
        print(f"{'':<28} неподвижный газ: ячейки {imm[:8]}, Sg = "
              f"{np.round(st.Sg[imm[:8]], 4).tolist()}")
