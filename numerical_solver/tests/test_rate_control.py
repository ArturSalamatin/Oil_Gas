"""Управление скважиной по дебиту нефти (FEAT-020).

Проверяет:
  A. RateControl — данные управления и их проверка при создании.
  B. Фабрика: конфиг с control = "rate" → RateControl → расчёт.
  C. Согласованность двух управлений: прогон по дебиту, которому подали
     дебиты прогона по давлению, повторяет его траекторию.

Физика (problem_statement.tex, eq:bc_rate_well, eq:bc_rate_pwf): при заданном
дебите нефти q_o,ст забойное давление выражается из уравнения притока,
p_wf = p_0 − q_o,ст / (T_{1/2}·λ_o,0), с нижней границей min_bhp. Дебит
положителен при добыче (q = −G_o[0], конвенция: > 0 — от скважины).
"""

import pytest

from gpn_multiphase_solver.bc import PressureControl, RateControl, WellControl


DAY = 86400.0
ATM = 101325.0


# ═══════════════════════════════════════════════════════════
# A. RateControl
# ═══════════════════════════════════════════════════════════

class TestRateControlClass:
    def test_stores_si_values(self):
        """Дебит в м³ст/с и min_bhp в Па хранятся как заданы (СИ, без пересчёта)."""
        rc = RateControl(2.0 / DAY, ATM)
        assert rc.q_oil == 2.0 / DAY
        assert rc.min_bhp == ATM

    def test_zero_rate_allowed(self):
        """q_oil = 0 допустим: скважина стоит, p_wf = p[0]."""
        assert RateControl(0.0, ATM).q_oil == 0.0

    def test_negative_rate_rejected(self):
        """q_oil < 0 — нагнетание; прототип его не поддерживает (blackoil.py)."""
        with pytest.raises(ValueError, match="q_oil"):
            RateControl(-1e-3, ATM)

    @pytest.mark.parametrize("min_bhp", [0.0, -1.0])
    def test_nonpositive_min_bhp_rejected(self, min_bhp):
        """min_bhp ≤ 0 — без нижней границы p_wf при λ_o → 0 уходит в −∞."""
        with pytest.raises(ValueError, match="min_bhp"):
            RateControl(1e-3, min_bhp)

    def test_is_well_control(self):
        assert isinstance(RateControl(1e-3, ATM), WellControl)

    def test_has_no_boundary_pressure(self):
        """Управление — только данные: способа вычислить p_wf в обход
        HydroResult у него нет (решение 8 плана FEAT-020)."""
        assert not hasattr(PressureControl(1e7), "boundary_pressure")
        assert not hasattr(RateControl(1e-3, ATM), "boundary_pressure")
