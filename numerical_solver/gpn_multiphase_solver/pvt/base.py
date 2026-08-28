"""ABC для PVT-свойств и относительных фазовых проницаемостей.

Три уровня ABC для PVT:
  HydroPVT              — физические свойства фаз (Bo, Bg, mu, Rs_eq, pb, rho)
  FullPVT(HydroPVT)     — + тепловые свойства (c_p, mu_JT, L)
  DifferentiableHydroPVT(HydroPVT) — + производные по p, Rs (для якобиана Ньютона)

Физика и метод решения разделены:
  HydroPVT/FullPVT — что описывает вещество (нужно всем модулям)
  DifferentiableHydroPVT — как решается СЛАУ (нужно только Newton-солверу)
"""

from abc import ABC, abstractmethod
import numpy as np


# ── Уровень 1: физические свойства ────────────────────────────

class HydroPVT(ABC):
    """Физические свойства фаз. Единицы: SI (Па, Па·с).

    Характеризуют вещество, не метод решения.
    Все методы vectorized (np.ndarray → np.ndarray).
    """

    @property
    @abstractmethod
    def rho_o_std(self) -> float:
        """Плотность нефтяного компонента при ст. условиях, кг/м³."""
        ...

    @property
    @abstractmethod
    def rho_g_std(self) -> float:
        """Плотность газового компонента при ст. условиях, кг/м³."""
        ...

    @abstractmethod
    def Rs_eq(self, p: np.ndarray) -> np.ndarray:
        """Равновесное газосодержание Rs_eq(p), м³ст/м³ст."""
        ...

    @abstractmethod
    def Bo(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Объёмный коэффициент нефти Bo(p, Rs), м³пл/м³ст."""
        ...

    @abstractmethod
    def Bg(self, p: np.ndarray) -> np.ndarray:
        """Объёмный коэффициент газа Bg(p), м³пл/м³ст."""
        ...

    @abstractmethod
    def mu_o(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Вязкость нефти μ_o(p, Rs), Па·с."""
        ...

    @abstractmethod
    def mu_g(self, p: np.ndarray) -> np.ndarray:
        """Вязкость газа μ_g(p), Па·с."""
        ...

    @abstractmethod
    def pb(self, Rs: np.ndarray) -> np.ndarray:
        """Давление насыщения pb(Rs), Па. При T=const — функция только Rs."""
        ...

    def rho_o(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Плотность нефтяной фазы, кг/м³. Eq. 51 problem_statement.tex."""
        return (self.rho_o_std + Rs * self.rho_g_std) / self.Bo(p, Rs)

    def rho_g(self, p: np.ndarray) -> np.ndarray:
        """Плотность газовой фазы, кг/м³."""
        return self.rho_g_std / self.Bg(p)


# ── Уровень 2: + тепловые свойства ────────────────────────────

class FullPVT(HydroPVT):
    """Физические + тепловые свойства. Для EnergySolver.

    Тепловые методы принимают (p, T) для расширяемости.
    """

    @abstractmethod
    def c_p_oil(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплоёмкость нефти, Дж/(кг·К)."""
        ...

    @abstractmethod
    def c_p_gas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплоёмкость газа, Дж/(кг·К)."""
        ...

    @abstractmethod
    def mu_JT_oil(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Коэффициент Джоуля-Томсона нефти, К/Па."""
        ...

    @abstractmethod
    def mu_JT_gas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Коэффициент Джоуля-Томсона газа, К/Па."""
        ...

    @abstractmethod
    def L_degas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплота дегазации, Дж/кг газа."""
        ...


# ── Уровень 3: + производные (для Newton-солвера) ─────────────

class DifferentiableHydroPVT(HydroPVT):
    """Физические свойства + производные по p, Rs.

    Для Newton-солвера с аналитическим якобианом.
    Не нужен прототипу (конечно-разностный якобиан) и EnergySolver.
    """

    @abstractmethod
    def dRs_eq_dp(self, p: np.ndarray) -> np.ndarray:
        """∂Rs_eq/∂p, м³ст/(м³ст·Па)."""
        ...

    @abstractmethod
    def dBo_dp(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """∂Bo/∂p|_{Rs}, 1/Па."""
        ...

    @abstractmethod
    def dBo_dRs(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """∂Bo/∂Rs|_{p}."""
        ...

    @abstractmethod
    def dBg_dp(self, p: np.ndarray) -> np.ndarray:
        """∂Bg/∂p, 1/Па."""
        ...

    @abstractmethod
    def dmu_o_dp(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """∂μ_o/∂p|_{Rs}, с."""
        ...

    @abstractmethod
    def dmu_g_dp(self, p: np.ndarray) -> np.ndarray:
        """∂μ_g/∂p, с."""
        ...


# ── ОФП ───────────────────────────────────────────────────────

class RelPermModel(ABC):
    """Относительные фазовые проницаемости (физика). Аргумент: Sg."""

    @abstractmethod
    def kro(self, Sg: np.ndarray) -> np.ndarray:
        """k_ro(Sg)."""
        ...

    @abstractmethod
    def krg(self, Sg: np.ndarray) -> np.ndarray:
        """k_rg(Sg)."""
        ...


class DifferentiableRelPerm(RelPermModel):
    """ОФП + производные (для Newton-солвера)."""

    def dkro_dSg(self, Sg: np.ndarray) -> np.ndarray:
        """dk_ro/dSg. Default: конечные разности."""
        Sg = np.asarray(Sg, float)
        eps = 1e-8
        return (self.kro(Sg + eps) - self.kro(Sg - eps)) / (2.0 * eps)

    def dkrg_dSg(self, Sg: np.ndarray) -> np.ndarray:
        """dk_rg/dSg. Default: конечные разности."""
        Sg = np.asarray(Sg, float)
        eps = 1e-8
        return (self.krg(Sg + eps) - self.krg(Sg - eps)) / (2.0 * eps)
