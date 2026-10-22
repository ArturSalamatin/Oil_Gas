"""BUG-019: где нарушение B_g·dR_s/dp > dB_o/dp лежит относительно диапазона данных Стендинга
и спасает ли его Z-фактор газа.

Условие (A3) Peszyńska 2006 (TiPM 63:201, со ссылкой на Coats 1999, SPE 49774):
B'_so − B_g·R'_s ≤ 0 — необходимо и достаточно для c_t ≥ 0 в насыщенной зоне.

Диапазон данных Стендинга (1947, 105 точек, 22 нефти Калифорнии): R_s 20–1425 scf/STB,
p_b 130–7000 psia, T 100–258 °F, API 16.5–63.8, γ_g 0.59–0.95.

Z-фактор: Дранчук — Абу-Кассем (DAK), псевдокритические по Стендингу (1977) и Саттону (1985)
для природного газа. B_g с Z = Z·B_g(идеальный), как в модели (standing.py:104-106).

Запуск (из numerical_solver), после freeze.py:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\standing_range.py
"""

import numpy as np
from scipy.optimize import brentq

import common as c

model, cfg = c.make_model()
pvt = model.pvt
SCF = 5.6146                                   # scf/STB в 1 м³/м³ (units.py:23)
gamma_g = cfg.pvt.rho_g_std / 1.225
gamma_o = cfg.pvt.rho_o_std / 999.0
api = 141.5 / gamma_o - 131.5
T_K = cfg.initial_conditions.T0
T_F = (T_K - 273.15) * 1.8 + 32
T_R = T_F + 459.67
print(f"нефть примера 20: γ_g = {gamma_g:.3f}, API = {api:.1f}, T = {T_F:.1f} °F, "
      f"R_s0 = {cfg.initial_conditions.Rs0:.0f} м³/м³ = {cfg.initial_conditions.Rs0 * SCF:.0f} scf/STB")
print("диапазон Стендинга: R_s 20–1425 scf/STB, p_b 130–7000 psia (482.6 бар), T 100–258 °F, "
      "API 16.5–63.8, γ_g 0.59–0.95")

p = np.linspace(20.0, 469.0, 44901)            # бар, шаг 0.01
rs = pvt.rs_sat(p)
bo = pvt.bo(p, rs)
co = c.c_o_sat(pvt, p)


def at(mask_first, label):
    i = int(np.argmax(mask_first))
    print(f"  {label}: p = {p[i]:.1f} бар, R_s = {rs[i]:.1f} м³/м³ ({rs[i] * SCF:.0f} scf/STB), "
          f"B_o = {bo[i]:.3f}, c_o,sat = {co[i]:+.2e} 1/бар")


print("\nБез Z (как в модели):")
at(rs * SCF >= 1425.0, "граница данных Стендинга, R_s = 1425 scf/STB")
at(co < 0, "c_o,sat меняет знак")
at(p >= 463.8, "p_b примера 20")

# ── Z-фактор DAK ──
A = [0.3265, -1.0700, -0.5339, 0.01569, -0.05165, 0.5475, -0.7361, 0.1844, 0.1056, 0.6134, 0.7210]


def z_dak(tpr, ppr):
    def f(z):
        rr = 0.27 * ppr / (z * tpr)
        return (1 + (A[0] + A[1] / tpr + A[2] / tpr ** 3 + A[3] / tpr ** 4 + A[4] / tpr ** 5) * rr
                + (A[5] + A[6] / tpr + A[7] / tpr ** 2) * rr ** 2
                - A[8] * (A[6] / tpr + A[7] / tpr ** 2) * rr ** 5
                + A[9] * (1 + A[10] * rr ** 2) * (rr ** 2 / tpr ** 3) * np.exp(-A[10] * rr ** 2)) - z
    return brentq(f, 0.2, 3.0)


def z_hy(tpr, ppr):
    """Холл — Ярборо: независимая проверка DAK."""
    t = 1.0 / tpr
    a = 0.06125 * t * np.exp(-1.2 * (1 - t) ** 2)

    def f(y):
        return (-a * ppr + (y + y ** 2 + y ** 3 - y ** 4) / (1 - y) ** 3
                - (14.76 * t - 9.76 * t ** 2 + 4.58 * t ** 3) * y ** 2
                + (90.7 * t - 242.2 * t ** 2 + 42.4 * t ** 3) * y ** (2.18 + 2.82 * t))
    y = brentq(f, 1e-8, 0.7)
    return a * ppr / y


for tpr, ppr in ((1.5, 2.0), (1.6, 8.7), (1.6, 10.0)):
    print(f"проверка: Z(T_pr = {tpr}, p_pr = {ppr}): DAK {z_dak(tpr, ppr):.3f}, Холл — Ярборо {z_hy(tpr, ppr):.3f}")
PSC = {"Стендинг 1977": (168 + 325 * gamma_g - 12.5 * gamma_g ** 2, 677 + 15 * gamma_g - 37.5 * gamma_g ** 2),
       "Саттон 1985": (169.2 + 349.5 * gamma_g - 74.0 * gamma_g ** 2, 756.8 - 131.0 * gamma_g - 3.6 * gamma_g ** 2)}
h = 1e-3
for name, (tpc, ppc) in PSC.items():
    tpr = T_R / tpc
    zf = np.vectorize(lambda pb: z_dak(tpr, pb * 14.5038 / ppc))
    pc = p[::10]
    z, zp, zm = zf(pc), zf(pc + h), zf(pc - h)
    bg = pvt.bg(pc) * z
    drs = (pvt.rs_sat(pc + h) - pvt.rs_sat(pc - h)) / (2 * h)
    dbo = (pvt.bo(pc + h, pvt.rs_sat(pc + h)) - pvt.bo(pc - h, pvt.rs_sat(pc - h))) / (2 * h)
    co_z = (bg * drs - dbo) / pvt.bo(pc, pvt.rs_sat(pc))
    need = dbo / drs / pvt.bg(pc)              # Z, при котором c_o,sat = 0
    neg = np.where(co_z < 0)[0]
    print(f"\nС Z ({name}: T_pc = {tpc:.1f} °R, p_pc = {ppc:.1f} psia, T_pr = {tpr:.3f}):")
    for pp in (300.0, 345.5, 400.0, 463.8):
        k = int(np.argmin(np.abs(pc - pp)))
        print(f"  p = {pc[k]:6.1f} бар: Z = {z[k]:.3f}, нужно Z ≥ {need[k]:.3f}; c_o,sat = {co_z[k]:+.2e} 1/бар")
    if neg.size:
        k = neg[0]
        print(f"  c_o,sat < 0 с p = {pc[k]:.1f} бар (R_s = {pvt.rs_sat(pc[k:k+1])[0]:.1f} м³/м³, "
              f"{pvt.rs_sat(pc[k:k+1])[0] * SCF:.0f} scf/STB)")
    else:
        print("  c_o,sat > 0 на всём диапазоне до 469 бар")
