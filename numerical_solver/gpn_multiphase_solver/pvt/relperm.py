"""Реализации RelPermModel: Corey, адаптер прототипа."""

import numpy as np
from .base import DifferentiableRelPerm


class CoreyRP(DifferentiableRelPerm):
    """Модель Кори для ОФП. Аналитические производные."""

    def __init__(self, S_or: float, S_gc: float,
                 n_o: float, n_g: float,
                 kro_max: float = 1.0, krg_max: float = 1.0):
        if not (0 <= S_or < 1):
            raise ValueError(f"S_or must be in [0, 1), got {S_or}")
        if not (0 <= S_gc < 1):
            raise ValueError(f"S_gc must be in [0, 1), got {S_gc}")
        if S_or + S_gc >= 1:
            raise ValueError(f"S_or + S_gc must be < 1, got {S_or + S_gc}")
        if n_o <= 0 or n_g <= 0:
            raise ValueError(f"Exponents must be > 0, got n_o={n_o}, n_g={n_g}")
        if not (0 < kro_max <= 1) or not (0 < krg_max <= 1):
            raise ValueError(f"kro_max, krg_max must be in (0, 1]")

        self._S_or = float(S_or)
        self._S_gc = float(S_gc)
        self._n_o = float(n_o)
        self._n_g = float(n_g)
        self._kro_max = float(kro_max)
        self._krg_max = float(krg_max)
        self._denom = 1.0 - S_or - S_gc

    def _S_star(self, Sg: np.ndarray) -> np.ndarray:
        """Нормированная газонасыщенность S* ∈ [0, 1]."""
        return np.clip((np.asarray(Sg, float) - self._S_gc) / self._denom, 0.0, 1.0)

    def kro(self, Sg: np.ndarray) -> np.ndarray:
        S = self._S_star(Sg)
        return self._kro_max * (1.0 - S) ** self._n_o

    def krg(self, Sg: np.ndarray) -> np.ndarray:
        S = self._S_star(Sg)
        return self._krg_max * S ** self._n_g

    def dkro_dSg(self, Sg: np.ndarray) -> np.ndarray:
        Sg = np.asarray(Sg, float)
        S = self._S_star(Sg)
        dS = 1.0 / self._denom
        deriv = -self._kro_max * self._n_o * (1.0 - S) ** (self._n_o - 1) * dS
        mobile = (S > 0) & (S < 1)
        return np.where(mobile, deriv, 0.0)

    def dkrg_dSg(self, Sg: np.ndarray) -> np.ndarray:
        Sg = np.asarray(Sg, float)
        S = self._S_star(Sg)
        dS = 1.0 / self._denom
        deriv = self._krg_max * self._n_g * S ** (self._n_g - 1) * dS
        mobile = (S > 0) & (S < 1)
        return np.where(mobile, deriv, 0.0)
