"""Аудит FEAT-021: какое замыкание для S_g годится в нестационарном примере 12.

Тождество закона Дарси на грани (без капиллярного давления и гравитации):
    GOR(r) = G^g / G^o = R_s + (k_rg/k_ro)·(mu_o B_o)/(mu_g B_g),
откуда  k_rg/k_ro(S_g) = [GOR(r) - R_s(p)]·mu_g B_g/(mu_o B_o).

Варианты GOR в правой части:
  A — R_s^0 (стационарное замыкание closed_form.py);
  B — GOR скважины GOR_w(t), одно число на момент времени (квазистационар);
  C — локальный GOR(r) на грани, взятый из расчёта (тождество, проверка согласованности).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-021\\probes\\sg_closure_variants.py
"""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

cfg = load_config(SOLVER / "examples" / "11_degassing_at_boundary" / "config.json")
cfg.geometry.R_ext = 200.0
cfg.initial_conditions.p0 = 15.5e6
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
h = sim.run(init)
pvt, rp, grid = sim._energy._pvt, _create_relperm(cfg), sim._grid
Rs0 = cfg.initial_conditions.Rs0
S_hi = 0.999


def sg_closure(p, gor):
    """Корень k_rg/k_ro(S_g) = [gor - R_s(p)]·mu_g B_g/(mu_o B_o); 0, если дефицита нет."""
    pa = np.array([p])
    Rs = min(float(pvt.Rs_eq(pa)[0]), Rs0)
    Rsa = np.array([Rs])
    Bo, mo = float(pvt.Bo(pa, Rsa)[0]), float(pvt.mu_o(pa, Rsa)[0])
    Bg, mg = float(pvt.Bg(pa)[0]), float(pvt.mu_g(pa)[0])

    def res(S):
        s = np.array([S])
        return Rs + rp.krg(s)[0] / rp.kro(s)[0] * mo * Bo / (mg * Bg) - gor

    if res(0.0) >= 0.0:
        return 0.0
    return brentq(res, 0.0, S_hi, xtol=1e-14)


t_h = np.array(h.times) / 3600.0
for hh in (6, 24, 72):
    n = int(np.argmin(abs(t_h - hh)))
    st, hr = h.states[n], h.hydro_results[n]
    N = grid.N
    tp = np.nonzero(st.Sg > 0)[0]                  # двухфазные ячейки 0..j_f
    # GOR на гранях: грань j (между ячейками j-1 и j), поток к скважине — выше по
    # потоку ячейка j (правая). Для ячейки j берём её правую грань j+1: через неё
    # в ячейку втекает смесь состава ячейки j+1... поэтому для тождества с
    # составом ячейки j нужна ЛЕВАЯ грань j (upstream = j).
    gor_face = hr.G_g[:N] / hr.G_o[:N]             # грань j, upstream = ячейка j
    gor_w = gor_face[0]
    Sg_num = st.Sg[tp]
    Sg_A = np.array([sg_closure(st.p[j], Rs0) for j in tp])
    Sg_B = np.array([sg_closure(st.p[j], gor_w) for j in tp])
    Sg_C = np.array([sg_closure(st.p[j], gor_face[j]) for j in tp])

    def err(S):
        return np.max(np.abs(S - Sg_num)), np.max(np.abs(S - Sg_num)) / Sg_num.max()

    print(f"\n=== t = {t_h[n]:.0f} ч: двухфазных ячеек {tp.size}, фронт {grid.r_centers[tp[-1]]:.1f} м ===")
    print(f"  GOR на гранях двухфазной зоны: забой {gor_w:.2f}, "
          f"r=1 м {np.interp(1.0, grid.r_centers, gor_face):.2f}, "
          f"r=10 м {np.interp(10.0, grid.r_centers, gor_face):.2f}, "
          f"у фронта {gor_face[tp[-1]]:.2f}  (R_s0 = {Rs0})")
    for name, S in (("A  GOR = R_s0      ", Sg_A), ("B  GOR = GOR_w(t)  ", Sg_B),
                    ("C  GOR = GOR(r)    ", Sg_C)):
        a, rel = err(S)
        print(f"  {name}: S_g(r_w) = {S[0]:.4f} (расчёт {Sg_num[0]:.4f}); "
              f"max|ΔS_g| = {a:.2e} ({rel*100:.1f} % от max S_g)")
    # Где GOR(r) сходит с плато: радиус, на котором GOR упал на 10 % и на половину
    # перепада между GOR_w и R_s0
    rc = grid.r_centers[tp]
    g = gor_face[tp]
    for frac in (0.1, 0.5, 0.9):
        target = gor_w - frac * (gor_w - Rs0)
        k = np.nonzero(g < target)[0]
        print(f"    GOR упал на {int(frac*100)} % перепада к R_s0 при r ≈ "
              f"{rc[k[0]] if k.size else float('nan'):.1f} м")
    # Точность B во внутренней зоне
    for rmax in (1.0, 10.0, 30.0):
        m = rc <= rmax
        e = np.max(np.abs(Sg_B[m] - Sg_num[m])) / Sg_num[0]
        print(f"    B при r <= {rmax:4.0f} м: max|ΔS_g| / S_g(r_w) = {e*100:.2f} %")
