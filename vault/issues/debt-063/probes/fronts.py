"""DEBT-063, проба: численный фронт r_b в README примеров — старые центры и √.

Фронт разгазирования в README — интерполяция ln r между центрами ячеек по
p = p_b (rs_analytics.front_radius; two_phase_analytics.degassing_front —
интерполяция и экстраполяция Дюпюи от дальней ячейки). Гидродинамика от
центров LogRadialGrid не зависит (examples_shift.out.txt), поэтому один
расчёт, а сетка подставляется дважды: центры exp<ln r> и √.

Для 03 — ещё ряд по сетке N = 25, 50, 100, 150, 200 (таблица «Сходимость
по сетке» README 03: r_b и отклонение от Дюпюи).

Запуск из numerical_solver/:  .venv\\Scripts\\python ..\\vault\\issues\\debt-063\\probes\\fronts.py
"""

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "examples"))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from rs_analytics import front_radius
from two_phase_analytics import degassing_front, dupuit_check

EXAMPLES = ["03_standing_corey", "04_table_table", "04a_high_gas_saturation",
            "05_standing_table_rp", "06_table_corey_rp", "07_degassing_adiabatic_only",
            "08_degassing_jt", "09_degassing_latent_heat", "10_deep_degassing",
            "18_prototype_input"]


def run(name, N=None):
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    if N is not None:
        cfg.grid.N = N
    sim, init = SimulatorFactory.from_config(cfg)
    logging.disable(logging.INFO)
    h = sim.run(init)
    logging.disable(logging.NOTSET)
    return cfg, sim, h


def grids(sim):
    """Сетка как есть (exp<ln r>) и с центрами √ — для функций, читающих r_centers."""
    g = sim._grid
    sq = SimpleNamespace(**{k: getattr(g, k) for k in
                            ("N", "r_well", "R_ext", "h", "r_faces", "volumes")},
                         r_centers=np.sqrt(g.r_faces[:-1] * g.r_faces[1:]))
    return g, sq


print(f"{'пример':28s} {'N':>4s} {'front_radius':>22s} {'C: интерп.':>22s} "
      f"{'C: формула':>22s}")
only = sys.argv[1:]                 # необязательно: имена примеров для повтора
for name in (only or EXAMPLES):
    cfg, sim, h = run(name)
    pvt = sim._energy._pvt
    g, sq = grids(sim)
    fr = [front_radius(cfg, h, x, pvt) for x in (g, sq)]
    dc = [degassing_front(h, x, cfg, pvt) for x in (g, sq)]
    print(f"{name:28s} {g.N:4d} {fr[0]:10.5f} → {fr[1]:9.5f} "
          f"{dc[0]['r_b_interp']:10.5f} → {dc[1]['r_b_interp']:9.5f} "
          f"{dc[0]['r_b_formula']:10.5f} → {dc[1]['r_b_formula']:9.5f}")
    if only:                        # повтор — с лишними знаками для округления
        print(f"    front_radius {fr[0]:.8f} → {fr[1]:.8f}; формула "
              f"{dc[0]['r_b_formula']:.8f} → {dc[1]['r_b_formula']:.8f}")
if only:
    sys.exit()

print("\n03_standing_corey, ряд по сетке: r_b (интерп.) и max|p − Дюпюи|, Па")
for N in (25, 50, 100, 150, 200):
    cfg, sim, h = run("03_standing_corey", N)
    pvt = sim._energy._pvt
    g, sq = grids(sim)
    rb = [degassing_front(h, x, cfg, pvt)["r_b_interp"] for x in (g, sq)]
    du = [dupuit_check(h, x, cfg, pvt)["max_dev"] for x in (g, sq)]
    print(f"  N = {N:3d}: r_b {rb[0]:.5f} → {rb[1]:.5f};  Дюпюи {du[0]:.1e} → {du[1]:.1e}")
