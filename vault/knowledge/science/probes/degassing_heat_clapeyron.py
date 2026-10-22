"""Оценка удельной теплоты дегазации L по уравнению Клапейрона из корреляций p_b(R_s, T).

L = h_g - h̄_go (eq:L_def, problem_statement.tex). Равенство химических
потенциалов газового компонента в газе и в нефти вдоль кривой насыщения
при фиксированном R_s даёт точное (для чистой газовой фазы) соотношение

    L = T · (v_g - v̄_go) · (∂p_b/∂T)_{R_s},

где v_g — удельный объём свободного газа, v̄_go — парциальный удельный
объём растворённого газа. В переменных Black Oil на 1 м³ст газа:
v_g -> B_g, v̄_go -> (∂B_o/∂R_s)_{p,T}; деление на ρ_g,ст даёт Дж/кг газа.

Три уровня оценки:
  ideal — Вант-Гофф: идеальный газ (Z = 1), v̄_go = 0;
  Z     — реальный газ (Z по Папаю), v̄_go = 0;
  full  — реальный газ и v̄_go = dB_ob/dR_s по Стендингу.

Запуск: numerical_solver/.venv/Scripts/python vault/knowledge/science/probes/degassing_heat_clapeyron.py
"""

import numpy as np

# ── Константы (как в gpn_multiphase_solver/units.py) ──
PSI_TO_PA = 6894.757
SCF_PER_M3 = 5.6146
RHO_WATER_STD = 999.0   # кг/м³
RHO_AIR_STD = 1.225     # кг/м³
P_STD = 101325.0        # Па
T_STD = 288.71          # К (60°F)

# ── Нефть: 850 кг/м³ст ≈ 35 °API ──
RHO_O_STD = 850.0
GAMMA_O = RHO_O_STD / RHO_WATER_STD
API = 141.5 / GAMMA_O - 131.5


def K_to_F(T):
    return (T - 273.15) * 1.8 + 32.0


def K_to_R(T):
    return T * 1.8


# ── Корреляции давления насыщения, p_b в psia; Rs в scf/STB ──

def pb_standing(Rs, T, gg):
    a = 0.00091 * K_to_F(T) - 0.0125 * API
    return 18.2 * ((Rs / gg) ** 0.83 * 10.0 ** a - 1.4)


def pb_vasquez_beggs(Rs, T, gg):
    # Константы для API > 30 и API ≤ 30; поправка γ_g на давление сепаратора не вводится
    C1, C2, C3 = (0.0178, 1.187, 23.931) if API > 30 else (0.0362, 1.0937, 25.724)
    return (Rs / (C1 * gg * np.exp(C3 * API / K_to_R(T)))) ** (1.0 / C2)


def pb_al_marhoun(Rs, T, gg):
    # Al-Marhoun (1988), T в °R
    return 5.38088e-3 * Rs ** 0.715082 * gg ** -1.87784 * GAMMA_O ** 3.1437 * K_to_R(T) ** 1.32657


def pb_petrosky_farshad(Rs, T, gg):
    X = 4.561e-5 * K_to_F(T) ** 1.3911 - 7.916e-4 * API ** 1.541
    return 112.727 * (Rs ** 0.5774 / gg ** 0.8439 * 10.0 ** X - 12.340)


def pb_glaso(Rs, T, gg):
    ps = (Rs / gg) ** 0.816 * K_to_F(T) ** 0.172 / API ** 0.989
    lg = np.log10(ps)
    return 10.0 ** (1.7669 + 1.7447 * lg - 0.30218 * lg * lg)


CORRELATIONS = {
    "Стендинг": pb_standing,
    "Васкес–Беггс": pb_vasquez_beggs,
    "Аль-Мархун": pb_al_marhoun,
    "Петроски–Фаршад": pb_petrosky_farshad,
    "Гласо": pb_glaso,
}


# ── Свойства газа ──

def z_papay(p, T, gg):
    """Z-фактор: Папай + псевдокритические параметры Саттона (1985)."""
    Tpc = (169.2 + 349.5 * gg - 74.0 * gg ** 2) / 1.8          # К
    ppc = (756.8 - 131.07 * gg - 3.6 * gg ** 2) * PSI_TO_PA    # Па
    Tpr, ppr = T / Tpc, p / ppc
    return 1.0 - 3.52 * ppr / 10.0 ** (0.9813 * Tpr) + 0.274 * ppr ** 2 / 10.0 ** (0.8157 * Tpr)


def Bg(p, T, Z):
    """Объёмный коэффициент газа, м³/м³ст."""
    return Z * P_STD * T / (T_STD * p)


def dBo_dRs_standing(Rs_scf, T, gg):
    """Парциальный объём растворённого газа (∂B_o/∂R_s) по Стендингу, м³ пласт./м³ст газа."""
    F = Rs_scf * (gg / GAMMA_O) ** 0.5 + 1.25 * K_to_F(T)
    return 1.44e-4 * F ** 0.2 * (gg / GAMMA_O) ** 0.5 * SCF_PER_M3


def L_estimates(pb_func, Rs_m3, T, gg):
    """Три оценки L, Дж/кг газа, и p_b, Па."""
    Rs = Rs_m3 * SCF_PER_M3
    rho_g_std = gg * RHO_AIR_STD
    dT = 0.01
    pb = pb_func(Rs, T, gg) * PSI_TO_PA
    dpb_dT = (pb_func(Rs, T + dT, gg) - pb_func(Rs, T - dT, gg)) * PSI_TO_PA / (2 * dT)
    Z = z_papay(pb, T, gg)
    vbar = dBo_dRs_standing(Rs, T, gg)
    # T·(объём на м³ст газа)·dp/dT -> Дж на м³ст газа; / ρ_g,ст -> Дж/кг
    L_ideal = T * Bg(pb, T, 1.0) * dpb_dT / rho_g_std
    L_Z = T * Bg(pb, T, Z) * dpb_dT / rho_g_std
    L_full = T * (Bg(pb, T, Z) - vbar) * dpb_dT / rho_g_std
    return pb, Z, vbar / Bg(pb, T, Z), L_ideal, L_Z, L_full


def main():
    print(f"Нефть: ρ_o,ст = {RHO_O_STD} кг/м³ ({API:.1f} °API)\n")

    # ── Таблица 1: все корреляции, R_s = 100 м³/м³, T = 350 К ──
    T, Rs = 350.0, 100.0
    for gg in (0.65, 0.80):
        print(f"γ_g = {gg} (ρ_g,ст = {gg * RHO_AIR_STD:.3f} кг/м³), R_s = {Rs:.0f} м³/м³, T = {T:.0f} К")
        print(f"  {'корреляция':16s} {'p_b, МПа':>8s} {'Z':>5s} {'v̄/v_g':>6s}"
              f" {'L_ideal':>8s} {'L_Z':>6s} {'L_full':>7s}   кДж/кг")
        for name, f in CORRELATIONS.items():
            pb, Z, ratio, Li, LZ, Lf = L_estimates(f, Rs, T, gg)
            print(f"  {name:16s} {pb / 1e6:8.1f} {Z:5.2f} {ratio:6.2f}"
                  f" {Li / 1e3:8.0f} {LZ / 1e3:6.0f} {Lf / 1e3:7.0f}")
        print()

    # ── Таблица 2: Стендинг, зависимость от R_s (т.е. от p_b) и T ──
    gg = 0.70
    print(f"Стендинг, γ_g = {gg}: L_full (L_ideal), кДж/кг")
    Ts = (330.0, 350.0, 370.0)
    print(f"  {'R_s, м³/м³':>10s} " + " ".join(f"{'T=' + str(int(t)) + ' К':>22s}" for t in Ts))
    for Rs in (20.0, 40.0, 60.0, 100.0, 150.0):
        cells = []
        for t in Ts:
            pb, Z, ratio, Li, LZ, Lf = L_estimates(pb_standing, Rs, t, gg)
            cells.append(f"p_b={pb / 1e6:4.1f} МПа: {Lf / 1e3:3.0f} ({Li / 1e3:3.0f})")
        print(f"  {Rs:10.0f} " + " ".join(f"{c:>22s}" for c in cells))


if __name__ == "__main__":
    main()
