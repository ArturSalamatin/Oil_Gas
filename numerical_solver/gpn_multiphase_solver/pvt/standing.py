"""StandingFullPVT — корреляции Standing, Beggs-Robinson, Lee-Gonzalez-Eakin."""

import numpy as np
from .base import FullPVT
from ..units import (
    PA_TO_PSI, PSI_TO_PA, SCF_PER_M3,
    RHO_WATER_STD, RHO_AIR_STD, P_STD, T_STD,
)


def _pa_to_psia(p):
    return np.asarray(p, float) * PA_TO_PSI

def _K_to_F(T):
    return (np.asarray(T, float) - 273.15) * 9.0 / 5.0 + 32.0

def _K_to_R(T):
    return np.asarray(T, float) * 9.0 / 5.0

def _api_gravity(rho_o_st):
    return 141.5 / (rho_o_st / RHO_WATER_STD) - 131.5

def _gas_specific_gravity(rho_g_st):
    return rho_g_st / RHO_AIR_STD


# Модели вязкости недонасыщенной нефти (p > pb(Rs)), FEAT-027.
MU_O_UNDERSATURATED_MODELS = ("none", "beal")


class StandingFullPVT(FullPVT):
    """Корреляции Standing (Rs, Bo), Beggs-Robinson и Бил (μ_o), LGE (μ_g) + скалярные тепловые."""

    def __init__(self, rho_o_std: float, rho_g_std: float, T0: float,
                 Rs0: float,
                 co_undersaturated: float = 0.0,
                 c_p_oil: float = 2000.0, c_p_gas: float = 1000.0,
                 mu_JT_oil_val: float = 0.0, mu_JT_gas_val: float = 0.0,
                 L_degas_val: float = 0.0,
                 mu_o_undersaturated: str = "none"):
        """
        Rs0 — начальное газосодержание, м³ст/м³ст. Определяет pb.
        co_undersaturated — сжимаемость нефти при p > pb, 1/Па.
        mu_o_undersaturated — μ_o при p > pb(Rs): "none" — только через Rs,
            "beal" — линейный рост с p по Билу–Стендингу (FEAT-027).
        """
        # Проверка до присваиваний: при ошибке объект не создаётся частично.
        if mu_o_undersaturated not in MU_O_UNDERSATURATED_MODELS:
            raise ValueError(
                f"mu_o_undersaturated = {mu_o_undersaturated!r} не поддерживается. "
                f"Доступные: {MU_O_UNDERSATURATED_MODELS}.")
        self._mu_under = mu_o_undersaturated
        self._rho_o_std = float(rho_o_std)
        self._rho_g_std = float(rho_g_std)
        self._T0 = float(T0)
        self._co_under = float(co_undersaturated)

        self._gamma_api = _api_gravity(rho_o_std)
        self._gamma_g = _gas_specific_gravity(rho_g_std)
        self._gamma_o = rho_o_std / RHO_WATER_STD
        self._T_F = _K_to_F(T0)
        self._a = 0.00091 * self._T_F - 0.0125 * self._gamma_api

        self._cp_o = float(c_p_oil)
        self._cp_g = float(c_p_gas)
        self._mu_JT_o = float(mu_JT_oil_val)
        self._mu_JT_g = float(mu_JT_gas_val)
        self._L = float(L_degas_val)

        self._Rs0 = float(Rs0)
        self._pb_val = float(self.pb(np.array([Rs0]))[0])
        self._Bo_at_pb = self._Bo_standing(
            np.array([self._pb_val]), np.array([Rs0]))[0]

    @property
    def rho_o_std(self) -> float:
        return self._rho_o_std

    @property
    def rho_g_std(self) -> float:
        return self._rho_g_std

    # ── Rs ──

    def Rs_eq(self, p):
        p = np.asarray(p, float)
        p_psia = _pa_to_psia(p)
        Y = p_psia / 18.2 + 1.4
        Rs_scf = self._gamma_g * Y ** (1.0 / 0.83) * 10.0 ** (-self._a / 0.83)
        return Rs_scf / SCF_PER_M3

    # ── Bo ──

    def _F_standing(self, Rs):
        Rs_scf = np.asarray(Rs, float) * SCF_PER_M3
        return Rs_scf * (self._gamma_g / self._gamma_o) ** 0.5 + 1.25 * self._T_F

    def _Bo_standing(self, p, Rs):
        F = self._F_standing(Rs)
        return 0.9759 + 1.2e-4 * F ** 1.2

    def Bo(self, p, Rs):
        p = np.asarray(p, float)
        Rs = np.asarray(Rs, float)
        Bo_sat = self._Bo_standing(p, Rs)
        if self._co_under == 0:
            return Bo_sat
        pb_local = self.pb(Rs)
        above = p >= pb_local
        Bo_at_pb_local = self._Bo_standing(pb_local, Rs)
        Bo_under = Bo_at_pb_local * np.exp(-self._co_under * (p - pb_local))
        return np.where(above, Bo_under, Bo_sat)

    # ── Bg ──

    def Bg(self, p):
        p = np.asarray(p, float)
        return P_STD * self._T0 / (T_STD * p)

    # ── μ_o ──

    def _mu_dead_oil(self):
        Y = 3.0324 - 0.02023 * self._gamma_api
        A = 10.0 ** Y
        mu_od_cP = 10.0 ** (A * self._T_F ** (-1.163)) - 1.0
        return mu_od_cP * 1e-3

    def _mu_o_beggs(self, Rs):
        Rs_scf = np.asarray(Rs, float) * SCF_PER_M3
        A = 10.715 / (Rs_scf + 100.0) ** 0.515
        B = 5.44 / (Rs_scf + 150.0) ** 0.338
        mu_od = self._mu_dead_oil()
        mu_od_cP = mu_od * 1e3
        mu_o_cP = A * mu_od_cP ** B
        return mu_o_cP * 1e-3

    def _beal_slope(self, mu_ob):
        """∂μ_o/∂p|_Rs выше pb по Билу–Стендингу, Па·с/Па (vault: pvt-корреляции-стендинг.md)."""
        mu_ob_cP = np.asarray(mu_ob, float) * 1e3
        # Корреляция записана в сП и psi: наклон в сП/psi → Па·с/Па.
        slope_cP_per_psi = 1e-3 * (0.024 * mu_ob_cP ** 1.6 + 0.038 * mu_ob_cP ** 0.56)
        return slope_cP_per_psi * 1e-3 * PA_TO_PSI

    def mu_o(self, p, Rs):
        p = np.asarray(p, float)
        Rs = np.asarray(Rs, float)
        # Беггс–Робинсон: вязкость насыщенной нефти, зависит только от Rs.
        mu_ob = self._mu_o_beggs(Rs)
        if self._mu_under == "none":
            return mu_ob
        # Выше pb(Rs) нефть недонасыщена: при том же Rs вязкость растёт с p
        # линейно (Бил–Стендинг). Ниже pb прибавка 0 — насыщенная ветвь;
        # при pb < 0 (Rs < Rs*, Стендинг) p - pb > 0 и прибавка конечна.
        dp_above = np.maximum(p - self.pb(Rs), 0.0)
        return mu_ob + self._beal_slope(mu_ob) * dp_above

    # ── μ_g ──

    def mu_g(self, p):
        p = np.asarray(p, float)
        M_g = 28.97 * self._gamma_g
        T_R = _K_to_R(self._T0)
        K = (9.4 + 0.02 * M_g) * T_R ** 1.5 / (209.0 + 19.0 * M_g + T_R)
        X = 3.5 + 986.0 / T_R + 0.01 * M_g
        Y_exp = 2.4 - 0.2 * X
        rho_g_SI = self._rho_g_std / self.Bg(p)
        rho_g_gcc = rho_g_SI / 1000.0
        mu_g_cP = 1e-4 * K * np.exp(X * rho_g_gcc ** Y_exp)
        return mu_g_cP * 1e-3

    # ── pb ──

    def pb(self, Rs):
        Rs = np.asarray(Rs, float)
        Rs_scf = Rs * SCF_PER_M3
        pb_psia = 18.2 * ((Rs_scf / self._gamma_g) ** 0.83 * 10.0 ** self._a - 1.4)
        return pb_psia * PSI_TO_PA

    # ── Тепловые (скалярные) ──

    def c_p_oil(self, p, T):
        return np.full_like(np.asarray(p, float), self._cp_o)

    def c_p_gas(self, p, T):
        return np.full_like(np.asarray(p, float), self._cp_g)

    def mu_JT_oil(self, p, T):
        return np.full_like(np.asarray(p, float), self._mu_JT_o)

    def mu_JT_gas(self, p, T):
        return np.full_like(np.asarray(p, float), self._mu_JT_g)

    def L_degas(self, p, T):
        return np.full_like(np.asarray(p, float), self._L)
