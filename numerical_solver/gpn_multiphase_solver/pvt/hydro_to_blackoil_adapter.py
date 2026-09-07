"""Адаптер HydroPVT (SI) → BlackOilPVT (бар/сП) для RadialBlackOilModel.

Зеркало PrototypePVTAdapter (BlackOilPVT → HydroPVT).
Тот конвертирует бар→Па на входе; этот — Па→бар.
Тот конвертирует сП→Па·с на выходе; этот — Па·с→сП.

RadialBlackOilModel работает в барах/сП, наш HydroPVT — в Па/Па·с.
"""

import numpy as np
from ..units import BAR_TO_PA, PA_S_TO_CP


class HydroPVTtoBlackOilAdapter:
    """Обёртка HydroPVT → BlackOilPVT (бар/сП).

    Конвертирует p: бар→Па на входе в HydroPVT, μ: Па·с→сП на выходе.
    Bo, Bg, Rs — безразмерные, конвертация не нужна.
    """

    def __init__(self, hydro_pvt, p_max_pa: float, n_knots: int = 20):
        """
        hydro_pvt  — наш HydroPVT (StandingFullPVT, PrototypePVTAdapter и т.д.)
        p_max_pa   — верхнее давление (Па), определяет max_rs и диапазон rs_values
        n_knots    — число узлов для rs_values/pb (для FD-якобиана и диагностики)
        """
        self._hydro = hydro_pvt

        # Протабулировать кривую насыщения для атрибутов BlackOilPVT.
        # _pressure_fd_step в blackoil.py использует searchsorted по self.pb
        # для выбора направления FD-шага; diagnostics.py — rs_values и pb
        # для предупреждений о выходе за таблицу.
        self.max_rs = float(hydro_pvt.Rs_eq(np.array([p_max_pa]))[0])
        rs_grid = np.linspace(0.0, self.max_rs, n_knots)
        self.rs_values = rs_grid
        # pb[i] = давление насыщения для Rs=rs_grid[i], в барах
        pb_pa = hydro_pvt.pb(rs_grid)
        self.pb = pb_pa / BAR_TO_PA
        # bo_sat[i], mu_sat[i] — значения на кривой насыщения (не используются
        # в blackoil.py, заполняются для полноты интерфейса BlackOilPVT)
        self.bo_sat = hydro_pvt.Bo(pb_pa, rs_grid)
        self.mu_sat = hydro_pvt.mu_o(pb_pa, rs_grid) * PA_S_TO_CP

    def _to_pa(self, p_bar):
        return np.asarray(p_bar, float) * BAR_TO_PA

    def rs_sat(self, p_bar):
        return self._hydro.Rs_eq(self._to_pa(p_bar))

    def pb_of_rs(self, rs):
        return self._hydro.pb(np.asarray(rs, float)) / BAR_TO_PA

    def bo(self, p_bar, rs):
        return self._hydro.Bo(self._to_pa(p_bar), np.asarray(rs, float))

    def mu_o(self, p_bar, rs):
        return self._hydro.mu_o(self._to_pa(p_bar), np.asarray(rs, float)) * PA_S_TO_CP

    def bg(self, p_bar):
        return self._hydro.Bg(self._to_pa(p_bar))

    def mu_g(self, p_bar):
        return self._hydro.mu_g(self._to_pa(p_bar)) * PA_S_TO_CP
