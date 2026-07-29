"""PVT-корреляции Black Oil (Standing, Beggs-Robinson, Lee-Gonzalez-Eakin)."""

import math

# ─── Константы ──────────────────────────────────────────────────────────
PSI_PER_PA = 1.0 / 6894.757
PA_PER_PSI = 6894.757
SCF_PER_M3 = 5.6146  # 1 м³/м³ → scf/STB
RHO_WATER_ST = 999.0  # кг/м³
RHO_AIR_ST = 1.225    # кг/м³
P_ST = 101325.0        # Па, стандартное давление
T_ST = 288.71          # К, стандартная температура


# ─── Пересчёт единиц ───────────────────────────────────────────────────
def _pa_to_psia(p):
    return p * PSI_PER_PA


def _psia_to_pa(p_psia):
    return p_psia * PA_PER_PSI


def _K_to_F(T):
    return (T - 273.15) * 9.0 / 5.0 + 32.0


def _K_to_R(T):
    return T * 9.0 / 5.0


def _api_gravity(rho_o_st):
    """γ_API из плотности нефти [кг/м³]."""
    gamma_o = rho_o_st / RHO_WATER_ST
    return 141.5 / gamma_o - 131.5


def _gas_specific_gravity(rho_g_st):
    """γ_g из плотности газа [кг/м³]."""
    return rho_g_st / RHO_AIR_ST


# ─── Газосодержание Rs и давление насыщения pb ──────────────────────────
def Rs(p, T, rho_o_st, rho_g_st):
    """Газосодержание [м³ст/м³ст]. Standing (1947)."""
    gamma_api = _api_gravity(rho_o_st)
    gamma_g = _gas_specific_gravity(rho_g_st)
    T_F = _K_to_F(T)
    a = 0.00091 * T_F - 0.0125 * gamma_api

    p_psia = _pa_to_psia(p)
    Y = p_psia / 18.2 + 1.4
    Rs_scf = gamma_g * Y ** (1.0 / 0.83) * 10.0 ** (-a / 0.83)
    return Rs_scf / SCF_PER_M3


def pb(Rs_total, T, rho_o_st, rho_g_st):
    """Давление насыщения [Па]. Standing (1947)."""
    gamma_api = _api_gravity(rho_o_st)
    gamma_g = _gas_specific_gravity(rho_g_st)
    T_F = _K_to_F(T)
    a = 0.00091 * T_F - 0.0125 * gamma_api

    Rs_scf = Rs_total * SCF_PER_M3
    pb_psia = 18.2 * ((Rs_scf / gamma_g) ** 0.83 * 10.0 ** a - 1.4)
    return _psia_to_pa(pb_psia)


def dRs_dp(p, T, rho_o_st, rho_g_st):
    """∂Rs/∂p [м³ст/(м³ст·Па)]. Аналитическая производная Standing."""
    p_psia = _pa_to_psia(p)
    Y = p_psia / 18.2 + 1.4
    Rs_val = Rs(p, T, rho_o_st, rho_g_st)
    return Rs_val / (0.83 * Y * 18.2 * PA_PER_PSI)


def dRs_dT(p, T, rho_o_st, rho_g_st):
    """∂Rs/∂T [м³ст/(м³ст·К)]. Аналитическая производная Standing."""
    Rs_val = Rs(p, T, rho_o_st, rho_g_st)
    return -Rs_val / 0.83 * math.log(10) * 0.00091 * 9.0 / 5.0


# ─── Объёмные коэффициенты Bo, Bg ──────────────────────────────────────
def _F_standing(Rs_m3, T, rho_o_st, rho_g_st):
    """Параметр F корреляции Standing для Bo."""
    gamma_o = rho_o_st / RHO_WATER_ST
    gamma_g = _gas_specific_gravity(rho_g_st)
    T_F = _K_to_F(T)
    Rs_scf = Rs_m3 * SCF_PER_M3
    return Rs_scf * (gamma_g / gamma_o) ** 0.5 + 1.25 * T_F


def Bo(p, T, Rs_val, rho_o_st, rho_g_st):
    """Объёмный коэффициент нефти [м³пл/м³ст]. Standing (1947)."""
    F = _F_standing(Rs_val, T, rho_o_st, rho_g_st)
    return 0.9759 + 1.2e-4 * F ** 1.2


def dBo_dRs(p, T, Rs_val, rho_o_st, rho_g_st):
    """∂Bo/∂Rs|_{p,T} [м³пл/м³ст / (м³ст/м³ст)]. Standing."""
    F = _F_standing(Rs_val, T, rho_o_st, rho_g_st)
    gamma_o = rho_o_st / RHO_WATER_ST
    gamma_g = _gas_specific_gravity(rho_g_st)
    dF_dRs = (gamma_g / gamma_o) ** 0.5 * SCF_PER_M3
    return 1.44e-4 * F ** 0.2 * dF_dRs


def dBo_dT_fixed_Rs(p, T, Rs_val, rho_o_st, rho_g_st):
    """∂Bo/∂T|_{p,Rs} [м³пл/(м³ст·К)]. Standing."""
    F = _F_standing(Rs_val, T, rho_o_st, rho_g_st)
    dF_dT = 1.25 * 9.0 / 5.0  # dF/dT_K = 1.25 * dT_F/dT_K = 1.25 * 9/5
    return 1.44e-4 * F ** 0.2 * dF_dT


def Bg(p, T):
    """Объёмный коэффициент газа [м³пл/м³ст]. Идеальный газ (z=1)."""
    return P_ST * T / (T_ST * p)


def dBg_dp(p, T):
    """∂Bg/∂p [м³пл/(м³ст·Па)]."""
    return -Bg(p, T) / p


def dBg_dT(p, T):
    """∂Bg/∂T [м³пл/(м³ст·К)]."""
    return Bg(p, T) / T


# ─── Вязкости ───────────────────────────────────────────────────────────
def mu_dead_oil(T, rho_o_st):
    """Вязкость мёртвой нефти [Па·с]. Beggs-Robinson (1975), McCain (1990)."""
    gamma_api = _api_gravity(rho_o_st)
    T_F = _K_to_F(T)
    Y = 3.0324 - 0.02023 * gamma_api
    A = 10.0 ** Y
    mu_od_cP = 10.0 ** (A * T_F ** (-1.163)) - 1.0
    return mu_od_cP * 1e-3


def mu_o(T, Rs_val, rho_o_st):
    """Вязкость живой нефти [Па·с]. Beggs et al. (1975)."""
    Rs_scf = Rs_val * SCF_PER_M3
    A = 10.715 / (Rs_scf + 100.0) ** 0.515
    B = 5.44 / (Rs_scf + 150.0) ** 0.338
    mu_od = mu_dead_oil(T, rho_o_st)
    mu_od_cP = mu_od * 1e3
    mu_o_cP = A * mu_od_cP ** B
    return mu_o_cP * 1e-3


def mu_g(p, T, rho_g_st):
    """Вязкость газа [Па·с]. Lee-Gonzalez-Eakin (1966)."""
    gamma_g = _gas_specific_gravity(rho_g_st)
    M_g = 28.97 * gamma_g
    T_R = _K_to_R(T)

    K = (9.4 + 0.02 * M_g) * T_R ** 1.5 / (209.0 + 19.0 * M_g + T_R)
    X = 3.5 + 986.0 / T_R + 0.01 * M_g
    Y_exp = 2.4 - 0.2 * X

    rho_g_SI = rho_g_st / Bg(p, T)  # кг/м³
    rho_g_gcc = rho_g_SI / 1000.0    # г/см³

    mu_g_cP = 1e-4 * K * math.exp(X * rho_g_gcc ** Y_exp)
    return mu_g_cP * 1e-3
