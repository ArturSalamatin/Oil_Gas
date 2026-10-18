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
    """Свойства фаз модели Black Oil при пластовой температуре — базовый класс PVT-модели; единицы СИ.

    Характеризуют вещество, а не метод решения. Все методы работают с
    массивами: аргументы и результат — ``numpy.ndarray`` одной формы
    (скаляр допускается). Гидродинамика зависит от температуры только через
    пластовую температуру T0 — свойства берутся при ней. Новая PVT-модель —
    наследник :class:`FullPVT` (с тепловыми свойствами), ветка в
    :func:`create_pvt` и допустимое значение ``pvt.model`` в проверке
    конфигурации; гидродинамике прототипа модель передаётся через адаптер.
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
        """Равновесное газосодержание R_s^eq(p): наибольшее газосодержание нефти при давлении p.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.

        Возвращает
        ----------
        numpy.ndarray
            R_s^eq, м³ст/м³ст.
        """
        ...

    @abstractmethod
    def Bo(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Объёмный коэффициент нефти B_o(p, R_s).

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        Rs : numpy.ndarray
            Газосодержание нефти, м³ст/м³ст; той же формы, что ``p``.

        Возвращает
        ----------
        numpy.ndarray
            B_o, м³пл/м³ст.
        """
        ...

    @abstractmethod
    def Bg(self, p: np.ndarray) -> np.ndarray:
        """Объёмный коэффициент газа B_g(p).

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.

        Возвращает
        ----------
        numpy.ndarray
            B_g, м³пл/м³ст.
        """
        ...

    @abstractmethod
    def mu_o(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Вязкость нефти μ_o(p, R_s).

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        Rs : numpy.ndarray
            Газосодержание нефти, м³ст/м³ст.

        Возвращает
        ----------
        numpy.ndarray
            μ_o, Па·с.
        """
        ...

    @abstractmethod
    def mu_g(self, p: np.ndarray) -> np.ndarray:
        """Вязкость газа μ_g(p).

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.

        Возвращает
        ----------
        numpy.ndarray
            μ_g, Па·с.
        """
        ...

    @abstractmethod
    def pb(self, Rs: np.ndarray) -> np.ndarray:
        """Давление насыщения p_b(R_s) нефти с газосодержанием R_s — обратная к R_s^eq(p).

        Параметры
        ---------
        Rs : numpy.ndarray
            Газосодержание нефти, м³ст/м³ст.

        Возвращает
        ----------
        numpy.ndarray
            p_b, Па.
        """
        ...

    def rho_o(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Плотность нефтяной фазы с растворённым газом. Ур. (eq:rho_oil) problem_statement.tex.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        Rs : numpy.ndarray
            Газосодержание нефти, м³ст/м³ст.

        Возвращает
        ----------
        numpy.ndarray
            ρ_o, кг/м³.
        """
        return (self.rho_o_std + Rs * self.rho_g_std) / self.Bo(p, Rs)

    def rho_g(self, p: np.ndarray) -> np.ndarray:
        """Плотность газовой фазы: плотность газа в стандартных условиях, делённая на B_g.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.

        Возвращает
        ----------
        numpy.ndarray
            ρ_g, кг/м³.
        """
        return self.rho_g_std / self.Bg(p)


# ── Уровень 2: + тепловые свойства ────────────────────────────

class FullPVT(HydroPVT):
    """Свойства фаз и тепловые свойства — PVT-модель, которую получает решатель уравнения энергии.

    Тепловые методы принимают давление и температуру, хотя обе реализации
    пакета возвращают постоянные из раздела ``thermal`` конфигурации, —
    чтобы модель с зависимостью от p и T не меняла интерфейс.
    """

    @abstractmethod
    def c_p_oil(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплоёмкость нефти c_p,o.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        T : numpy.ndarray
            Температура, К.

        Возвращает
        ----------
        numpy.ndarray
            c_p,o, Дж/(кг·К).
        """
        ...

    @abstractmethod
    def c_p_gas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплоёмкость газа c_p,g.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        T : numpy.ndarray
            Температура, К.

        Возвращает
        ----------
        numpy.ndarray
            c_p,g, Дж/(кг·К).
        """
        ...

    @abstractmethod
    def mu_JT_oil(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Коэффициент Джоуля–Томсона нефти μ_JT,o (обычно < 0: нефть при дросселировании нагревается).

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        T : numpy.ndarray
            Температура, К.

        Возвращает
        ----------
        numpy.ndarray
            μ_JT,o, К/Па.
        """
        ...

    @abstractmethod
    def mu_JT_gas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Коэффициент Джоуля–Томсона газа μ_JT,g (обычно > 0: газ при дросселировании охлаждается).

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        T : numpy.ndarray
            Температура, К.

        Возвращает
        ----------
        numpy.ndarray
            μ_JT,g, К/Па.
        """
        ...

    @abstractmethod
    def L_degas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплота разгазирования L — теплота выделения газа из нефти.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        T : numpy.ndarray
            Температура, К.

        Возвращает
        ----------
        numpy.ndarray
            L, Дж/кг газа.
        """
        ...


# ── Уровень 3: + производные (для Newton-солвера) ─────────────

class DifferentiableHydroPVT(HydroPVT):
    """Свойства фаз и их производные по давлению и газосодержанию — для метода Ньютона с аналитическим якобианом.

    Прототипу (якобиан конечными разностями) и решателю энергии не нужен.
    """

    @abstractmethod
    def dRs_eq_dp(self, p: np.ndarray) -> np.ndarray:
        """Производная равновесного газосодержания по давлению ∂R_s^eq/∂p.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.

        Возвращает
        ----------
        numpy.ndarray
            ∂R_s^eq/∂p, м³ст/(м³ст·Па).
        """
        ...

    @abstractmethod
    def dBo_dp(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Производная объёмного коэффициента нефти по давлению при постоянном R_s.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        Rs : numpy.ndarray
            Газосодержание нефти, м³ст/м³ст.

        Возвращает
        ----------
        numpy.ndarray
            ∂B_o/∂p, м³пл/(м³ст·Па).
        """
        ...

    @abstractmethod
    def dBo_dRs(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Производная объёмного коэффициента нефти по газосодержанию при постоянном давлении.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        Rs : numpy.ndarray
            Газосодержание нефти, м³ст/м³ст.

        Возвращает
        ----------
        numpy.ndarray
            ∂B_o/∂R_s, м³пл/м³ст на единицу газосодержания.
        """
        ...

    @abstractmethod
    def dBg_dp(self, p: np.ndarray) -> np.ndarray:
        """Производная объёмного коэффициента газа по давлению.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.

        Возвращает
        ----------
        numpy.ndarray
            ∂B_g/∂p, м³пл/(м³ст·Па).
        """
        ...

    @abstractmethod
    def dmu_o_dp(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Производная вязкости нефти по давлению при постоянном R_s.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.
        Rs : numpy.ndarray
            Газосодержание нефти, м³ст/м³ст.

        Возвращает
        ----------
        numpy.ndarray
            ∂μ_o/∂p, с.
        """
        ...

    @abstractmethod
    def dmu_g_dp(self, p: np.ndarray) -> np.ndarray:
        """Производная вязкости газа по давлению.

        Параметры
        ---------
        p : numpy.ndarray
            Давление, Па.

        Возвращает
        ----------
        numpy.ndarray
            ∂μ_g/∂p, с.
        """
        ...


# ── ОФП ───────────────────────────────────────────────────────

class RelPermModel(ABC):
    """Относительные фазовые проницаемости как функции газонасыщенности — базовый класс модели ОФП.

    Новая модель — наследник с методами :meth:`kro` и :meth:`krg`, ветка в
    :func:`create_relperm` и допустимое значение ``relperm.model`` в
    проверке конфигурации.
    """

    @abstractmethod
    def kro(self, Sg: np.ndarray) -> np.ndarray:
        """ОФП нефти k_ro(S_g).

        Параметры
        ---------
        Sg : numpy.ndarray
            Газонасыщенность, доли.

        Возвращает
        ----------
        numpy.ndarray
            k_ro, доли.
        """
        ...

    @abstractmethod
    def krg(self, Sg: np.ndarray) -> np.ndarray:
        """ОФП газа k_rg(S_g).

        Параметры
        ---------
        Sg : numpy.ndarray
            Газонасыщенность, доли.

        Возвращает
        ----------
        numpy.ndarray
            k_rg, доли.
        """
        ...


class DifferentiableRelPerm(RelPermModel):
    """ОФП и их производные по газонасыщенности — для метода Ньютона; по умолчанию производные — центральными разностями."""

    def dkro_dSg(self, Sg: np.ndarray) -> np.ndarray:
        """Производная ОФП нефти по газонасыщенности; по умолчанию центральная разность с шагом 1e-8.

        Параметры
        ---------
        Sg : numpy.ndarray
            Газонасыщенность, доли.

        Возвращает
        ----------
        numpy.ndarray
            dk_ro/dS_g.
        """
        Sg = np.asarray(Sg, float)
        eps = 1e-8
        return (self.kro(Sg + eps) - self.kro(Sg - eps)) / (2.0 * eps)

    def dkrg_dSg(self, Sg: np.ndarray) -> np.ndarray:
        """Производная ОФП газа по газонасыщенности; по умолчанию центральная разность с шагом 1e-8.

        Параметры
        ---------
        Sg : numpy.ndarray
            Газонасыщенность, доли.

        Возвращает
        ----------
        numpy.ndarray
            dk_rg/dS_g.
        """
        Sg = np.asarray(Sg, float)
        eps = 1e-8
        return (self.krg(Sg + eps) - self.krg(Sg - eps)) / (2.0 * eps)
