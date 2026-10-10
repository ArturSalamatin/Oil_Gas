"""Адаптеры PVT и ОФП прототипа → наши ABC (бар/сП → Па/Па·с)."""

import numpy as np
from .base import HydroPVT, RelPermModel
from ..units import BAR_TO_PA, CP_TO_PA_S


class PrototypePVTAdapter(HydroPVT):
    """Обёртка BlackOilPVT прототипа → HydroPVT (SI).

    Конвертирует p: Па→бар на входе, μ: сП→Па·с на выходе.
    Bo, Bg, Rs — безразмерные, конвертация не нужна.
    """

    def __init__(self, proto_pvt, rho_o_std: float, rho_g_std: float):
        self._pvt = proto_pvt
        self._rho_o_std = float(rho_o_std)
        self._rho_g_std = float(rho_g_std)

    def _to_bar(self, p_pa):
        return np.asarray(p_pa, float) / BAR_TO_PA

    @property
    def rho_o_std(self) -> float:
        return self._rho_o_std

    @property
    def rho_g_std(self) -> float:
        return self._rho_g_std

    @property
    def proto_pvt(self):
        """BlackOilPVT прототипа под адаптером — тот же объект, что у модели (DEBT-006)."""
        # Публичный путь для фабрики и скриптов графиков вместо приватного
        # _pvt. Без сеттера: подмена объекта разорвала бы «один источник PVT»
        # (vault/knowledge/decisions/согласованность-pvt-hydro.md).
        return self._pvt

    def Rs_eq(self, p):
        return self._pvt.rs_sat(self._to_bar(p))

    def Bo(self, p, Rs):
        return self._pvt.bo(self._to_bar(p), np.asarray(Rs, float))

    def Bg(self, p):
        return self._pvt.bg(self._to_bar(p))

    def mu_o(self, p, Rs):
        return self._pvt.mu_o(self._to_bar(p), np.asarray(Rs, float)) * CP_TO_PA_S

    def mu_g(self, p):
        return self._pvt.mu_g(self._to_bar(p)) * CP_TO_PA_S

    def pb(self, Rs):
        return self._pvt.pb_of_rs(np.asarray(Rs, float)) * BAR_TO_PA


class PrototypeRPAdapter(RelPermModel):
    """Обёртка TabulatedRelPerm прототипа → RelPermModel."""

    def __init__(self, proto_rp):
        self._rp = proto_rp

    @property
    def proto_rp(self):
        """TabulatedRelPerm прототипа под адаптером — тот же объект, что у модели (DEBT-006)."""
        # Без сеттера — по той же причине, что proto_pvt
        return self._rp

    def kro(self, Sg):
        return self._rp.kro(np.asarray(Sg, float))

    def krg(self, Sg):
        return self._rp.krg(np.asarray(Sg, float))
