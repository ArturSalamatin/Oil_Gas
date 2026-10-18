"""TableFullPVT — табличные гидро (через PrototypePVTAdapter) + скалярные тепловые."""

import numpy as np
from .base import FullPVT
from .prototype_adapter import PrototypePVTAdapter


class TableFullPVT(FullPVT):
    """PVT по таблицам CSV (нефть — формат PVTO, газ) с постоянными тепловыми свойствами.

    Модель ``pvt.model = "table"``: свойства фаз — интерполяция таблиц
    прототипа (тот же объект, что считает гидродинамику), тепловые —
    постоянные из раздела ``thermal``. Корреляции не используются.

    Параметры
    ---------
    hydro : PrototypePVTAdapter
        Таблицы PVT прототипа в интерфейсе :class:`HydroPVT`.
    c_p_oil : float
        Удельная теплоёмкость нефти, Дж/(кг·К).
    c_p_gas : float
        Удельная теплоёмкость газа, Дж/(кг·К).
    mu_JT_oil : float
        Коэффициент Джоуля–Томсона нефти, К/Па.
    mu_JT_gas : float
        Коэффициент Джоуля–Томсона газа, К/Па.
    L_degas : float
        Удельная теплота разгазирования, Дж/кг газа.
    """

    # Гидро-методы делегируются PrototypePVTAdapter, тепловые — постоянные скаляры
    def __init__(self, hydro: PrototypePVTAdapter,
                 c_p_oil: float, c_p_gas: float,
                 mu_JT_oil: float, mu_JT_gas: float,
                 L_degas: float):
        self._hydro = hydro
        self._cp_o = float(c_p_oil)
        self._cp_g = float(c_p_gas)
        self._mu_JT_o = float(mu_JT_oil)
        self._mu_JT_g = float(mu_JT_gas)
        self._L = float(L_degas)

    # Гидро-часть для фабрики и скриптов графиков (DEBT-006): BlackOilPVT
    # прототипа — table_pvt.hydro.proto_pvt, без приватных полей. Без сеттера.
    @property
    def hydro(self) -> PrototypePVTAdapter: return self._hydro

    @property
    def rho_o_std(self): return self._hydro.rho_o_std
    @property
    def rho_g_std(self): return self._hydro.rho_g_std

    def Rs_eq(self, p): return self._hydro.Rs_eq(p)
    def Bo(self, p, Rs): return self._hydro.Bo(p, Rs)
    def Bg(self, p): return self._hydro.Bg(p)
    def mu_o(self, p, Rs): return self._hydro.mu_o(p, Rs)
    def mu_g(self, p): return self._hydro.mu_g(p)
    def pb(self, Rs): return self._hydro.pb(Rs)

    def c_p_oil(self, p, T): return np.full_like(np.asarray(p, float), self._cp_o)
    def c_p_gas(self, p, T): return np.full_like(np.asarray(p, float), self._cp_g)
    def mu_JT_oil(self, p, T): return np.full_like(np.asarray(p, float), self._mu_JT_o)
    def mu_JT_gas(self, p, T): return np.full_like(np.asarray(p, float), self._mu_JT_g)
    def L_degas(self, p, T): return np.full_like(np.asarray(p, float), self._L)
