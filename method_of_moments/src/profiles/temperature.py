"""Профиль температуры T(r) — §4.4 moments_method.tex."""

import math

try:
    from ..integrals import J as _J_integral
except ImportError:
    from integrals import J as _J_integral


class TemperatureProfile:
    r"""Профиль T(r) с функцией формы Ψ(ζ), \eqref{eq:T_profile}, \eqref{eq:Psi}."""

    def __init__(self, r_w: float, R_ext: float, T_0: float, sigma: float = 1.0):
        self.r_w = r_w
        self.R_ext = R_ext
        self.T_0 = T_0
        self.sigma = sigma
        self.L_0 = math.log(R_ext / r_w)

    def zeta(self, r: float) -> float:
        r"""Безразмерная координата ζ = ln(R_ext/r) / L_0, \eqref{eq:T_profile}."""
        return math.log(self.R_ext / r) / self.L_0

    def zeta_b(self, r_b: float) -> float:
        """ζ_b = L_e / L_0 — координата фронта разгазирования."""
        return math.log(self.R_ext / r_b) / self.L_0

    def Psi(self, zeta: float) -> float:
        r"""Функция формы Ψ(ζ) = ζ^σ(2 − ζ^σ), \eqref{eq:Psi}."""
        zs = zeta ** self.sigma
        return zs * (2.0 - zs)

    def dPsi_dzeta(self, zeta: float) -> float:
        r"""Ψ'(ζ) = 2σζ^{σ−1}(1 − ζ^σ), из \eqref{eq:Psi}."""
        if zeta == 0.0:
            if self.sigma < 1.0:
                return math.inf
            elif self.sigma == 1.0:
                return 2.0 * self.sigma
            else:
                return 0.0
        return 2.0 * self.sigma * zeta ** (self.sigma - 1) * (1.0 - zeta ** self.sigma)

    def __call__(self, r: float, dT_w: float) -> float:
        r"""Температура T(r) = T_0 − ΔT_w·Ψ(ζ), \eqref{eq:T_profile}."""
        z = self.zeta(r)
        return self.T_0 - dT_w * self.Psi(z)

    def dT_dr(self, r: float, dT_w: float) -> float:
        r"""Производная dT/dr, \eqref{eq:dT_dr}."""
        z = self.zeta(r)
        return dT_w / (r * self.L_0) * self.dPsi_dzeta(z)

    def J(self, m: int) -> float:
        r"""Интеграл J^{(m)} = 2/(m+1) − 1/(m+σ+1), \eqref{eq:IPsi}."""
        return _J_integral(m, self.sigma)
