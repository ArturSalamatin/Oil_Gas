"""Класс BlackOilFluid — единый интерфейс PVT Black Oil."""

from . import correlations as cor


class BlackOilFluid:
    """PVT-свойства флюида Black Oil. Ур. §2 moments_method.tex."""

    def __init__(self, pvt_config: dict, p_b: float, T_0: float,
                 relperm_config: dict | None = None):
        self.rho_o_st = pvt_config["rho_o_st"]
        self.rho_g_st = pvt_config["rho_g_st"]
        self.p_b = p_b
        self.T_0 = T_0
        self.Rs_total = cor.Rs(p_b, T_0, self.rho_o_st, self.rho_g_st)
        self._cp_o = pvt_config.get("cp_o", 2000.0)
        self._cp_g = pvt_config.get("cp_g", 1000.0)
        self._L_degas = pvt_config.get("L_degas", 300e3)

        relperm_config = relperm_config or {}
        self._S_or = relperm_config.get("S_or", 0.2)
        self._S_gc = relperm_config.get("S_gc", 0.05)
        self._n_o = relperm_config.get("n_o", 2.0)
        self._n_g = relperm_config.get("n_g", 2.0)
        self._kro_max = relperm_config.get("k_ro_max", 1.0)
        self._krg_max = relperm_config.get("k_rg_max", 0.8)
        self._S_norm = 1.0 - self._S_or - self._S_gc

    # ─── Относительные фазовые проницаемости (Кори) ───────────────
    def _S_star(self, Sg: float) -> float:
        """Нормализованная газонасыщенность."""
        return max(0.0, min(1.0, (Sg - self._S_gc) / self._S_norm))

    def kro(self, Sg: float) -> float:
        """Относительная проницаемость нефти (Кори)."""
        return self._kro_max * (1.0 - self._S_star(Sg)) ** self._n_o

    def krg(self, Sg: float) -> float:
        """Относительная проницаемость газа (Кори)."""
        return self._krg_max * self._S_star(Sg) ** self._n_g

    # ─── Подвижности и суммарная подвижность ───────────────────────
    def mobility_o(self, p: float, T: float, Sg: float, k: float) -> float:
        """λ_o = k·kro/μo. Ур. (eq:mobility) moments_method.tex."""
        return k * self.kro(Sg) / self.mu_o(p, T)

    def mobility_g(self, p: float, T: float, Sg: float, k: float) -> float:
        """λ_g = k·krg/μg. Ур. (eq:mobility) moments_method.tex."""
        return k * self.krg(Sg) / self.mu_g(p, T)

    def Lambda(self, p: float, T: float, Sg: float, k: float) -> float:
        """Λ = (λ_o + λ_g)/Bg. Ур. (eq:Lambda) moments_method.tex."""
        return (self.mobility_o(p, T, Sg, k)
                + self.mobility_g(p, T, Sg, k)) / self.Bg(p, T)

    def mobility_o_over_Bo(self, p: float, T: float, Sg: float,
                           k: float) -> float:
        """λ_o/B_o — вспомогательная, §5 moments_method.tex."""
        return self.mobility_o(p, T, Sg, k) / self.Bo(p, T)

    # ─── Базовые PVT ───────────────────────────────────────────────
    def _effective_Rs(self, p, T):
        """Rs с учётом насыщения: min(Rs(p,T), Rs_total)."""
        return min(cor.Rs(p, T, self.rho_o_st, self.rho_g_st), self.Rs_total)

    def _is_saturated(self, p, T):
        pb_val = self.pb(T)
        return p < pb_val

    def Rs(self, p, T):
        """Газосодержание [м³ст/м³ст]."""
        return self._effective_Rs(p, T)

    def Bo(self, p, T):
        """Объёмный коэффициент нефти."""
        return cor.Bo(p, T, self._effective_Rs(p, T),
                      self.rho_o_st, self.rho_g_st)

    def Bg(self, p, T):
        """Объёмный коэффициент газа."""
        return cor.Bg(p, T)

    def mu_o(self, p, T):
        """Вязкость нефти [Па·с]."""
        return cor.mu_o(T, self._effective_Rs(p, T), self.rho_o_st)

    def mu_g(self, p, T):
        """Вязкость газа [Па·с]."""
        return cor.mu_g(p, T, self.rho_g_st)

    def pb(self, T):
        """Давление насыщения [Па]."""
        return cor.pb(self.Rs_total, T, self.rho_o_st, self.rho_g_st)

    # ─── Производные Rs ─────────────────────────────────────────────
    def dRs_dp(self, p, T):
        """∂Rs/∂p [м³ст/(м³ст·Па)]."""
        if not self._is_saturated(p, T):
            return 0.0
        return cor.dRs_dp(p, T, self.rho_o_st, self.rho_g_st)

    def dRs_dT(self, p, T):
        """∂Rs/∂T [м³ст/(м³ст·К)]."""
        if not self._is_saturated(p, T):
            return 0.0
        return cor.dRs_dT(p, T, self.rho_o_st, self.rho_g_st)

    # ─── Плотности ──────────────────────────────────────────────────
    def rho_o(self, p, T):
        """Плотность нефти [кг/м³]. Ур. (eq:rho_o) moments_method.tex."""
        Rs_val = self._effective_Rs(p, T)
        Bo_val = cor.Bo(p, T, Rs_val, self.rho_o_st, self.rho_g_st)
        return (self.rho_o_st + Rs_val * self.rho_g_st) / Bo_val

    def rho_g(self, p, T):
        """Плотность газа [кг/м³]."""
        return self.rho_g_st / cor.Bg(p, T)

    # ─── Сжимаемости при фикс. составе (eq:co_cg) ──────────────────
    def co(self, p, T):
        """co = −(1/Bo)·∂Bo/∂p|_{T,Rs}. Ур. (eq:co_cg) two_phase_energy.tex."""
        return 0.0  # Standing: Bo не зависит от p при фикс. Rs

    def cg(self, p, T):
        """cg = −(1/Bg)·∂Bg/∂p|_T = 1/p. Ур. (eq:co_cg) two_phase_energy.tex."""
        return 1.0 / p

    # ─── Температурные коэфф. расширения (eq:beta_o_g) ──────────────
    def beta_o(self, p, T):
        """βo = (1/Bo)·∂Bo/∂T|_{p,Rs}. Ур. (eq:beta_o_g) two_phase_energy.tex."""
        Rs_val = self._effective_Rs(p, T)
        Bo_val = cor.Bo(p, T, Rs_val, self.rho_o_st, self.rho_g_st)
        dBo_dT = cor.dBo_dT_fixed_Rs(p, T, Rs_val,
                                      self.rho_o_st, self.rho_g_st)
        return dBo_dT / Bo_val

    def beta_g(self, p, T):
        """βg = (1/Bg)·∂Bg/∂T|_p = 1/T. Ур. (eq:beta_o_g) two_phase_energy.tex."""
        return 1.0 / T

    # ─── Полные коэфф. вдоль кривой насыщения ───────────────────────
    def co_sat(self, p, T):
        """co_sat = co − (1/Bo)·∂Bo/∂Rs·∂Rs/∂p. Ур. (eq:co_sat) two_phase_energy.tex."""
        Rs_val = self._effective_Rs(p, T)
        Bo_val = cor.Bo(p, T, Rs_val, self.rho_o_st, self.rho_g_st)
        dBo_dRs = cor.dBo_dRs(p, T, Rs_val, self.rho_o_st, self.rho_g_st)
        dRs_dp = self.dRs_dp(p, T)
        return self.co(p, T) - dBo_dRs / Bo_val * dRs_dp

    def beta_o_sat(self, p, T):
        """βo_sat = βo + (1/Bo)·∂Bo/∂Rs·∂Rs/∂T. Ур. (eq:beta_o_sat) two_phase_energy.tex."""
        Rs_val = self._effective_Rs(p, T)
        Bo_val = cor.Bo(p, T, Rs_val, self.rho_o_st, self.rho_g_st)
        dBo_dRs = cor.dBo_dRs(p, T, Rs_val, self.rho_o_st, self.rho_g_st)
        dRs_dT = self.dRs_dT(p, T)
        return self.beta_o(p, T) + dBo_dRs / Bo_val * dRs_dT

    # ─── Коэфф. теплового расширения (eq:thermal_expansion) ─────────
    def alpha_o(self, p, T):
        """αo = −(1/ρo)·∂ρo/∂T|_{p,Rs} = βo. Ур. (eq:thermal_expansion) two_phase_energy.tex."""
        return self.beta_o(p, T)

    def alpha_g(self, p, T):
        """αg = −(1/ρg)·∂ρg/∂T|_p = 1/T. Ур. (eq:thermal_expansion) two_phase_energy.tex."""
        return 1.0 / T

    # ─── Коэффициенты ёмкости (eq:Cp, eq:CT) ────────────────────────
    def Cp(self, p, T, Sg, phi, cr):
        """Коэффициент ёмкости C_p. Ур. (eq:Cp) moments_method.tex."""
        So = 1.0 - Sg
        Bo_val = self.Bo(p, T)
        Bg_val = self.Bg(p, T)
        Rs_val = self.Rs(p, T)
        co_sat_val = self.co_sat(p, T)
        cg_val = self.cg(p, T)
        dRs_dp_val = self.dRs_dp(p, T)
        xi_o_val = So / Bo_val
        inv_Bg_minus_Rs_over_Bo = 1.0 / Bg_val - Rs_val / Bo_val
        return phi * (
            So * (cr + co_sat_val) * inv_Bg_minus_Rs_over_Bo
            + xi_o_val * (dRs_dp_val + Rs_val * (cr + co_sat_val))
            + Sg / Bg_val * (cg_val + cr)
        )

    def CT(self, p, T, Sg, phi):
        """Температурный коэффициент C_T. Ур. (eq:CT) moments_method.tex."""
        So = 1.0 - Sg
        Bo_val = self.Bo(p, T)
        Bg_val = self.Bg(p, T)
        Rs_val = self.Rs(p, T)
        beta_o_sat_val = self.beta_o_sat(p, T)
        beta_g_val = self.beta_g(p, T)
        dRs_dT_val = self.dRs_dT(p, T)
        xi_o_val = So / Bo_val
        inv_Bg_minus_Rs_over_Bo = 1.0 / Bg_val - Rs_val / Bo_val
        return phi * (
            -So * beta_o_sat_val * inv_Bg_minus_Rs_over_Bo
            + xi_o_val * (dRs_dT_val - Rs_val * beta_o_sat_val)
            - Sg / Bg_val * beta_g_val
        )

    # ─── Вспомогательные ────────────────────────────────────────────
    def xi_o(self, p, T, Sg):
        """ξo = (1−Sg)/Bo. Ур. (eq:xi_o) two_phase_energy.tex."""
        return (1.0 - Sg) / self.Bo(p, T)

    def cp_o(self, p, T):
        """Удельная теплоёмкость нефти [Дж/(кг·К)]."""
        return self._cp_o

    def cp_g(self, p, T):
        """Удельная теплоёмкость газа [Дж/(кг·К)]."""
        return self._cp_g

    def L(self, p, T):
        """Теплота дегазации [Дж/кг]. Ур. (eq:L_def) two_phase_energy.tex."""
        return self._L_degas
