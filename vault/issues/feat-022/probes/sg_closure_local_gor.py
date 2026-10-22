"""FEAT-022: почему на saturation_profiles.png 13a численная S_g выше «аналитики».

Обе наложенные кривые — СТАЦИОНАРНОЕ замыкание closed_form (GOR = Rs0 = 30):
кружки — при численном давлении, пунктир — при давлении автономного решения.

Тождество закона Дарси на грани (upstream — ячейка j, поток к скважине):

    G^g/G^o = Rs_j + krg(Sg_j)/kro(Sg_j) · (mu_o Bo)/(mu_g Bg)_j

выполняется в ЛЮБОЙ момент, если слева стоит МЕСТНОЕ отношение потоков
компонентов, а не Rs0. Проверка: подставить G^g/G^o из hydro_result на
каждой грани, решить относительно Sg_j и сравнить с численной Sg_j.
Если совпадает — расхождение с «аналитикой» целиком объясняется тем, что
режим нестационарен (G^g/G^o != Rs0), а не ошибкой схемы или наложения.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-022\\probes\\sg_closure_local_gor.py
"""

import sys
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
from closed_form import Closure, solve_closed  # noqa: E402

cfg = load_config(SOLVER / "examples" / "13a_pwf_ramp_down" / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
h = sim.run(init)
pvt = sim._energy._pvt
rp = _create_relperm(cfg)
r = sim._grid.r_centers
Rs0 = cfg.initial_conditions.Rs0

for n_rec in (6, 18, 30):          # 3, 9, 15 сут
    st, hr = h.states[n_rec], h.hydro_results[n_rec]
    two = np.nonzero(st.Sg > 0)[0]
    # Грань j — внутренняя сторона ячейки j (j = 0 — забой); поток к скважине,
    # поэтому ячейка выше по потоку для грани j — ячейка j.
    gor_loc = hr.G_g[:len(r)] / hr.G_o[:len(r)]
    sg_loc = np.array([Closure(pvt, rp, gor_loc[j]).Sg(st.p[j]) if j in two else 0.0
                       for j in range(len(r))])
    sg_st = np.array([Closure(pvt, rp, Rs0).Sg(pp) for pp in st.p])
    d_loc = np.abs(sg_loc - st.Sg)[two].max()
    d_st = np.abs(sg_st - st.Sg)[two].max()
    print(f"\n=== {h.times[n_rec] / 86400:.0f} сут: двухфазных ячеек {two.size} ===")
    print(f"  замыкание с МЕСТНЫМ G^g/G^o:   max|Sg - Sg_числ| = {d_loc:.2e}")
    print(f"  замыкание с GOR = Rs0 = {Rs0:.0f}:   max|Sg - Sg_числ| = {d_st:.2e}")
    print(f"  {'r, м':>8} {'G^g/G^o':>9} {'Sg числ':>9} {'Sg местн':>9} {'Sg Rs0':>9}")
    for j in [0, 10, 20, 30, 40] + ([two[-1]] if two.size else []):
        if j < len(r):
            print(f"  {r[j]:8.3f} {gor_loc[j]:9.3f} {st.Sg[j]:9.5f} {sg_loc[j]:9.5f} "
                  f"{sg_st[j]:9.5f}")

# Кружки и пунктир на графике: одно замыкание при двух давлениях
cl = solve_closed(cfg, pvt, rp, r)
st = h.states[-1]
print(f"\nкружки vs пунктир (15 сут): max|p_числ - p_ана| = "
      f"{np.abs(st.p - cl['p']).max() / 1e3:.1f} кПа; "
      f"max|Sg(p_числ) - Sg(p_ана)| = "
      f"{np.abs(np.array([Closure(pvt, rp, Rs0).Sg(pp) for pp in st.p]) - cl['Sg']).max():.2e}")
