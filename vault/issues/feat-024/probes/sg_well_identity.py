"""FEAT-024: газонасыщенность у забоя в стационаре по тождеству Дарси.

На грани у забоя отношение потоков фаз — тождество закона Дарси
(README примера 12, раздел «Стационарное решение на графиках»):

    k_rg/k_ro (S_g) = (GOR - R_s(p)) · μ_g B_g / (μ_o B_o),

в стационаре GOR = R_s0. Правая часть зависит только от давления у забоя и
PVT, левая — только от ОФП. S_g у забоя — корень уравнения.

Таблицы — вариант B (p_b = 24 МПа): R_s(p) линейна от 0 при 5 МПа до 150
при 24 МПа, насыщенные B_o, μ_o линейны по R_s между ветками 0 и 150
(как в BlackOilPVT прототипа на насыщенной кривой).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-024\\probes\\sg_well_identity.py
"""

import numpy as np
from scipy.optimize import brentq

RS0 = 150.0
PB_ANCH = np.array([5.0e6, 24.0e6])       # p_b веток R_s = 0 и 150
RS_ANCH = np.array([0.0, 150.0])
BO_SAT = np.array([1.05, 1.45])
MU_O_SAT = np.array([0.003, 0.0009])
GP = np.array([5.0e6, 15.0e6, 30.0e6])      # gas_pvt.csv примера 12
BG = np.array([0.020, 0.008, 0.004])
MU_G = np.array([1.2e-5, 1.4e-5, 1.8e-5])

# ОФП: таблица примера 14 (k_rg = 0 до 0.1) — узлы
SG_T = np.array([0.0, 0.1, 0.2, 0.4, 0.6, 0.8])
KRO_T = np.array([1.0, 0.8, 0.6, 0.3, 0.1, 0.0])
KRG_T = np.array([0.0, 0.0, 0.05, 0.2, 0.5, 0.8])


def required_ratio(p, gor=RS0):
    """Правая часть тождества при давлении p (насыщенная нефть у забоя)."""
    rs = np.interp(p, PB_ANCH, RS_ANCH)
    w = rs / RS0
    bo = BO_SAT[0] + w * (BO_SAT[1] - BO_SAT[0])
    mu_o = MU_O_SAT[0] + w * (MU_O_SAT[1] - MU_O_SAT[0])
    return (gor - rs) * np.interp(p, GP, MU_G) * np.interp(p, GP, BG) / (mu_o * bo)


def krg_table(sg):
    return np.interp(sg, SG_T, KRG_T)


def krg_corey(n_g, S_gc=0.1, S_or=0.2, krg_max=0.8):
    # k_rg по Кори с тем же порогом S_gc; k_ro — табличная
    return lambda sg: krg_max * np.clip((sg - S_gc) / (1 - S_gc - S_or), 0, 1) ** n_g


def sg_root(krg, ratio):
    f = lambda sg: krg(sg) / np.interp(sg, SG_T, KRO_T) - ratio
    return brentq(f, 0.1 + 1e-9, 0.79)


if __name__ == "__main__":
    # Проверка на прогоне B730: 730 сут, p[0] = 6.2780 МПа, GOR = 149.00, S_g(r_w) = 0.1157
    r = required_ratio(6.2780e6, gor=149.00)
    print(f"проверка: p = 6.278 МПа, GOR = 149.0 -> k_rg/k_ro = {r:.4e}, "
          f"S_g = {sg_root(krg_table, r):.4f} (расчёт 0.1157)")
    print()
    krgs = {"таблица (линейно от 0.1)": krg_table}
    for n in (2, 3, 4):
        krgs[f"Кори n_g = {n}"] = krg_corey(n)
    print(f"{'p у забоя, МПа':>15} | {'k_rg/k_ro':>9} | " + " | ".join(f"{k:>24}" for k in krgs))
    for p in (6.28e6, 5.0e6):
        r = required_ratio(p)
        print(f"{p/1e6:15.2f} | {r:9.3e} | " + " | ".join(f"{sg_root(f, r):24.4f}" for f in krgs.values()))
