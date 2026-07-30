"""Профиль давления p(r) — §4.2 moments_method.tex."""

import math


class PressureProfile:
    r"""Двухзонный профиль давления \eqref{eq:p_inner}, \eqref{eq:p_outer}."""

    def __init__(self, r_w: float, R_ext: float, p_wf: float, p_0: float):
        self.r_w = r_w
        self.R_ext = R_ext
        self.p_wf = p_wf
        self.p_0 = p_0
        self.L_0 = math.log(R_ext / r_w)

    def L_b(self, r_b: float) -> float:
        """ln(r_b / r_w)."""
        return math.log(r_b / self.r_w)

    def L_e(self, r_b: float) -> float:
        """ln(R_ext / r_b)."""
        return math.log(self.R_ext / r_b)

    def eta(self, r: float, r_b: float) -> float:
        r"""Безразмерная координата η = ln(r/r_w) / ln(r_b/r_w), \eqref{eq:Phi}."""
        return math.log(r / self.r_w) / self.L_b(r_b)

    def gamma(self, r_b: float, pb_star: float) -> float:
        r"""Показатель γ из непрерывности потока, \eqref{eq:gamma_constraint}."""
        dp1 = pb_star - self.p_wf
        dp2 = self.p_0 - pb_star
        return dp2 * self.L_b(r_b) / (dp1 * self.L_e(r_b))

    def pb_star(self, r_b: float, dT_w: float, fluid, temp_profile) -> float:
        r"""Давление насыщения на фронте p_b^*, \eqref{eq:pb_star}."""
        zeta_b = self.L_e(r_b) / self.L_0
        T_rb = temp_profile.T_0 - dT_w * temp_profile.Psi(zeta_b)
        return fluid.pb(T_rb)

    def __call__(self, r: float, r_b: float, pb_star: float, gamma: float) -> float:
        r"""Давление p(r), \eqref{eq:p_inner}, \eqref{eq:p_outer}."""
        if r <= r_b:
            dp1 = pb_star - self.p_wf
            eta = self.eta(r, r_b)
            return self.p_wf + dp1 * eta ** gamma
        else:
            dp2 = self.p_0 - pb_star
            L_e = self.L_e(r_b)
            return pb_star + dp2 * math.log(r / r_b) / L_e

    def dp_dr(self, r: float, r_b: float, pb_star: float, gamma: float) -> float:
        r"""Производная dp/dr, \eqref{eq:dp_inner}, \eqref{eq:dp_outer}."""
        if r <= r_b:
            dp1 = pb_star - self.p_wf
            L_b = self.L_b(r_b)
            if r <= self.r_w:
                if gamma < 1.0:
                    return math.inf
                elif gamma == 1.0:
                    return dp1 * gamma / (r * L_b)
            eta = self.eta(r, r_b)
            return dp1 * gamma / (r * L_b) * eta ** (gamma - 1)
        else:
            dp2 = self.p_0 - pb_star
            L_e = self.L_e(r_b)
            return dp2 / (r * L_e)
