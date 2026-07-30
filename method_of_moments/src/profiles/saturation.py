"""Профиль газонасыщенности Sg(r) — §4.3 moments_method.tex."""

import math


class SaturationProfile:
    r"""Профиль Sg(r) с компактным носителем [r_w, r_b], \eqref{eq:Sg_profile}."""

    def __init__(self, r_w: float, beta: float = 2.0):
        self.r_w = r_w
        self.beta = beta

    def eta(self, r: float, r_b: float) -> float:
        r"""Безразмерная координата η = ln(r/r_w) / ln(r_b/r_w), \eqref{eq:Phi}."""
        return math.log(r / self.r_w) / math.log(r_b / self.r_w)

    def __call__(self, r: float, r_b: float, Sg_w: float) -> float:
        r"""Газонасыщенность Sg(r), \eqref{eq:Sg_profile}."""
        if r > r_b or r < self.r_w:
            return 0.0
        eta = self.eta(r, r_b)
        return Sg_w * (1.0 - eta ** self.beta)

    def dSg_dr(self, r: float, r_b: float, Sg_w: float) -> float:
        r"""Производная dSg/dr, из \eqref{eq:Sg_profile}."""
        if r > r_b or r < self.r_w:
            return 0.0
        L_b = math.log(r_b / self.r_w)
        if r <= self.r_w:
            if self.beta < 1.0:
                return -math.inf
            elif self.beta == 1.0:
                return -Sg_w * self.beta / (r * L_b)
        eta = self.eta(r, r_b)
        return -Sg_w * self.beta / (r * L_b) * eta ** (self.beta - 1)
