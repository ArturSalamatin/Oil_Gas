"""Тесты коэффициентов ODE — §5 moments_method.tex."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from src.pvt.black_oil import BlackOilFluid
from src.coefficients import (
    frozen_pvt_zone1, frozen_pvt_zone2,
    dp_drb_numerical, dp_dpwf_numerical,
    oil_A11, oil_A13, oil_F1,
    gas_A21, gas_A22, gas_A23, gas_F2,
    gas_A2beta, gas_A41, gas_A42, gas_A43, gas_A44, gas_F4,
    energy_A31, energy_A33, energy_F3,
    assemble_ode_system,
    OdeState,
)
from src.profiles.pressure import PressureProfile
from src.profiles.temperature import TemperatureProfile
from src.profiles.saturation import SaturationProfile


# ─── Фикстуры ─────────────────────────────────────────────────────

CONFIGS = Path(__file__).resolve().parent.parent / "configs"


@pytest.fixture
def baseline_config():
    with open(CONFIGS / "baseline.json") as f:
        return json.load(f)


@pytest.fixture
def fluid(baseline_config):
    cfg = baseline_config
    return BlackOilFluid(
        pvt_config=cfg["pvt"],
        p_b=cfg["initial_conditions"]["p_b"],
        T_0=cfg["initial_conditions"]["T_0"],
        relperm_config=cfg["relative_permeability"],
    )


@pytest.fixture
def rock(baseline_config):
    return baseline_config["rock"]


# ─── Параметры baseline ───────────────────────────────────────────

P_WF = 15e6
P_0 = 20e6
P_B = 18e6
T_0 = 350.0
SG_BASELINE = 0.1
PHI = 0.2
CR = 5e-10


# ─── Тесты Cp ─────────────────────────────────────────────────────

class TestCp:
    def test_Cp_positive(self, fluid):
        val = fluid.Cp(P_WF, T_0, SG_BASELINE, PHI, CR)
        assert val > 0, f"Cp должен быть > 0, получено {val}"

    def test_Cp_single_phase(self, fluid):
        val = fluid.Cp(P_0, T_0, 0.0, PHI, CR)
        assert val > 0, f"Cp (однофазный) должен быть > 0, получено {val}"

    def test_Cp_dimension(self, fluid):
        val = fluid.Cp(P_WF, T_0, SG_BASELINE, PHI, CR)
        assert 1e-12 < abs(val) < 1e-6, (
            f"Cp ~ 1e-10..1e-8 [1/Па], получено {val:.3e}"
        )


# ─── Тесты CT ─────────────────────────────────────────────────────

class TestCT:
    def test_CT_negative(self, fluid):
        val = fluid.CT(P_WF, T_0, SG_BASELINE, PHI)
        assert val < 0, f"CT должен быть < 0, получено {val}"

    def test_CT_single_phase(self, fluid):
        p_above_pb = P_0
        val = fluid.CT(p_above_pb, T_0, 0.0, PHI)
        Bo_val = fluid.Bo(p_above_pb, T_0)
        Bg_val = fluid.Bg(p_above_pb, T_0)
        beta_o_val = fluid.beta_o(p_above_pb, T_0)
        expected = -PHI * beta_o_val / Bg_val
        # При Sg=0, p>pb: CT = phi*(-beta_o*(1/Bg - Rs/Bo) + xi_o*(0 - Rs*beta_o) - 0)
        # = phi*(-beta_o/Bg + beta_o*Rs/Bo - Rs*beta_o/Bo) = -phi*beta_o/Bg
        assert val == pytest.approx(expected, rel=1e-10), (
            f"CT однофазный: {val:.6e} != -phi*beta_o/Bg = {expected:.6e}"
        )


# ─── Тесты замораживания PVT ──────────────────────────────────────

class TestFrozenPVT:
    def test_frozen_zone1_averages(self):
        pb_star = P_B
        p_bar, T_bar, Sg_bar = frozen_pvt_zone1(P_WF, pb_star, T_0, 5.0, SG_BASELINE)
        assert p_bar == pytest.approx(0.5 * (P_WF + pb_star))
        assert T_bar == pytest.approx(T_0 - 5.0)
        assert Sg_bar == pytest.approx(0.5 * SG_BASELINE)

    def test_frozen_zone2_Sg_zero(self):
        pb_star = P_B
        p_bar, T_bar, Sg_bar = frozen_pvt_zone2(pb_star, P_0, T_0)
        assert Sg_bar == 0.0
        assert p_bar == pytest.approx(0.5 * (pb_star + P_0))
        assert T_bar == pytest.approx(T_0)

    def test_frozen_zone1_isothermal(self):
        p_bar, T_bar, Sg_bar = frozen_pvt_zone1(P_WF, P_B, T_0, 0.0, SG_BASELINE)
        assert T_bar == pytest.approx(T_0)


# ─── Фикстуры профилей ────────────────────────────────────────────

R_W = 0.1
R_EXT = 500.0
SIGMA = 2.0


@pytest.fixture
def p_profile():
    return PressureProfile(R_W, R_EXT, P_WF, P_0)


@pytest.fixture
def t_profile():
    return TemperatureProfile(R_W, R_EXT, T_0, SIGMA)


# ─── Тесты dp/dr_b ────────────────────────────────────────────────

class TestDpDrb:
    def test_dp_drb_sign_inner(self, fluid, p_profile, t_profile):
        """∂p/∂r_b < 0 в зоне разгазирования."""
        r_b = 5.0
        dT_w = 2.0
        r_test = math.sqrt(R_W * r_b)
        val = dp_drb_numerical(p_profile, r_test, r_b, fluid, t_profile, dT_w)
        assert val < 0, f"∂p/∂r_b должен быть < 0 в зоне 1, получено {val:.6e}"

    def test_dp_drb_sign_outer(self, fluid, p_profile, t_profile):
        """∂p/∂r_b < 0 в однофазной зоне (или ≈0 вблизи контура)."""
        r_b = 5.0
        dT_w = 2.0
        r_test = math.sqrt(r_b * R_EXT)
        val = dp_drb_numerical(p_profile, r_test, r_b, fluid, t_profile, dT_w)
        assert val <= 0, f"∂p/∂r_b должен быть ≤ 0 в зоне 2, получено {val:.6e}"

    def test_dp_drb_zero_at_Rext(self, fluid, p_profile, t_profile):
        """∂p/∂r_b = 0 на контуре (p(R_ext) = p_0 = const)."""
        r_b = 5.0
        dT_w = 2.0
        val = dp_drb_numerical(p_profile, R_EXT, r_b, fluid, t_profile, dT_w)
        assert abs(val) < 1.0, f"∂p/∂r_b на контуре ≈ 0, получено {val:.6e}"

    def test_dp_drb_continuity_at_rb(self, fluid, p_profile, t_profile):
        """∂p/∂r_b непрерывна в r = r_b (конечная разность)."""
        r_b = 5.0
        dT_w = 2.0
        eps = 1e-4
        val_left = dp_drb_numerical(
            p_profile, r_b * (1 - eps), r_b, fluid, t_profile, dT_w)
        val_right = dp_drb_numerical(
            p_profile, r_b * (1 + eps), r_b, fluid, t_profile, dT_w)
        assert val_left == pytest.approx(val_right, rel=0.05), (
            f"Разрыв dp/dr_b на r_b: left={val_left:.6e}, right={val_right:.6e}"
        )


class TestDpDpwf:
    def test_dp_dpwf_at_rw(self, fluid, p_profile, t_profile):
        """∂p/∂p_wf(r_w) ≈ 1."""
        r_b = 5.0
        dT_w = 2.0
        val = dp_dpwf_numerical(p_profile, R_W, r_b, fluid, t_profile, dT_w)
        assert val == pytest.approx(1.0, abs=0.05), (
            f"∂p/∂p_wf(r_w) ≈ 1, получено {val:.6f}"
        )

    def test_dp_dpwf_at_Rext(self, fluid, p_profile, t_profile):
        """∂p/∂p_wf(R_ext) = 0 (p₀ = const)."""
        r_b = 5.0
        dT_w = 2.0
        val = dp_dpwf_numerical(p_profile, R_EXT, r_b, fluid, t_profile, dT_w)
        assert abs(val) < 1e-4, f"∂p/∂p_wf(R_ext) ≈ 0, получено {val:.6e}"

    def test_dp_dpwf_zero_in_zone2(self, fluid, p_profile, t_profile):
        """∂p/∂p_wf = 0 в однофазной зоне."""
        r_b = 5.0
        dT_w = 2.0
        r_test = math.sqrt(r_b * R_EXT)
        val = dp_dpwf_numerical(p_profile, r_test, r_b, fluid, t_profile, dT_w)
        assert abs(val) < 0.01, f"∂p/∂p_wf в зоне 2 ≈ 0, получено {val:.6e}"


# ─── Фикстуры для A11/A13/F1 ──────────────────────────────────────

BETA = 2.0


@pytest.fixture
def s_profile():
    return SaturationProfile(R_W, BETA)


def _make_state(r_b=5.0, Sg_w=0.1, dT_w=2.0, p_wf=P_WF, dp_wf_dt=0.0):
    return OdeState(r_b=r_b, Sg_w=Sg_w, dT_w=dT_w, p_wf=p_wf,
                    dp_wf_dt=dp_wf_dt)


# ─── Тесты A₁₂ = 0 ────────────────────────────────────────────────

class TestA12Zero:
    def test_no_oil_A12_in_api(self):
        """A₁₂ = 0: давление не зависит от Sg_w, функция не реализуется."""
        import src.coefficients as coeff
        assert not hasattr(coeff, "oil_A12"), (
            "oil_A12 не должна существовать: A₁₂ = 0 по конструкции"
        )


# ─── Тесты A₁₁ ────────────────────────────────────────────────────

class TestA11:
    def test_A11_sign(self, fluid, rock, p_profile, t_profile):
        """A₁₁ < 0: Cp > 0 и ∂p/∂r_b < 0."""
        state = _make_state()
        val = oil_A11(fluid, rock, p_profile, t_profile, state)
        assert val < 0, f"A₁₁ должен быть < 0, получено {val:.6e}"

    def test_A11_dimension(self, fluid, rock, p_profile, t_profile):
        """A₁₁ [м] — конечное отрицательное число."""
        state = _make_state()
        val = oil_A11(fluid, rock, p_profile, t_profile, state)
        assert val < 0
        assert abs(val) > 1e-20, f"A₁₁ слишком мал: {val:.6e}"
        assert abs(val) < 1e10, f"A₁₁ слишком велик: {val:.6e}"


# ─── Тесты A₁₃ ────────────────────────────────────────────────────

class TestA13:
    def test_A13_sign(self, fluid, rock, p_profile, t_profile):
        """A₁₃ > 0: CT < 0 и Ψ > 0 ⟹ −CT·Ψ > 0."""
        state = _make_state()
        val = oil_A13(fluid, rock, p_profile, t_profile, state)
        assert val > 0, f"A₁₃ должен быть > 0, получено {val:.6e}"

    def test_A13_isothermal(self, fluid, rock, p_profile, t_profile):
        """A₁₃ > 0 даже при ΔTw = 0 (Ψ не зависит от ΔTw)."""
        state = _make_state(dT_w=0.0)
        val = oil_A13(fluid, rock, p_profile, t_profile, state)
        assert val > 0, f"A₁₃(ΔTw=0) должен быть > 0, получено {val:.6e}"


# ─── Тесты F₁ ─────────────────────────────────────────────────────

class TestF1:
    def test_F1_sign(self, fluid, rock, p_profile, t_profile, s_profile):
        """F₁ < 0: отток на забое доминирует над притоком на контуре."""
        state = _make_state()
        val = oil_F1(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val < 0, f"F₁ должен быть < 0, получено {val:.6e}"

    def test_F1_isothermal(self, fluid, rock, p_profile, t_profile, s_profile):
        """F₁ при ΔTw = 0: dT/dr = 0 ⟹ температурные члены Q_quad обнуляются."""
        state = _make_state(dT_w=0.0)
        val = oil_F1(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val < 0, f"F₁(ΔTw=0) должен быть < 0, получено {val:.6e}"

    def test_single_phase_limit(self, fluid, rock, p_profile, t_profile, s_profile):
        """При r_b → r_w зона 1 вырождается; A₁₁ и F₁ определяются зоной 2."""
        r_b_small = R_W * 1.01
        state = _make_state(r_b=r_b_small, Sg_w=0.0, dT_w=0.0)
        a11 = oil_A11(fluid, rock, p_profile, t_profile, state)
        a13 = oil_A13(fluid, rock, p_profile, t_profile, state)
        f1 = oil_F1(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(a11), f"A₁₁ не конечен при r_b→r_w: {a11}"
        assert math.isfinite(a13), f"A₁₃ не конечен при r_b→r_w: {a13}"
        assert math.isfinite(f1), f"F₁ не конечен при r_b→r_w: {f1}"


# ─── Тесты A₂₂ (eq:A22) ─────────────────────────────────────────

class TestA22:
    def test_A22_positive(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₂₂ > 0: подынтегральная r·(1−η^β) ≥ 0."""
        state = _make_state()
        val = gas_A22(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val > 0, f"A₂₂ должен быть > 0, получено {val:.6e}"

    def test_A22_grows_with_rb(self, fluid, rock, p_profile, t_profile,
                               s_profile):
        """A₂₂ растёт с r_b (больше домен интегрирования)."""
        state1 = _make_state(r_b=5.0)
        state2 = _make_state(r_b=10.0)
        val1 = gas_A22(fluid, rock, p_profile, t_profile, s_profile, state1)
        val2 = gas_A22(fluid, rock, p_profile, t_profile, s_profile, state2)
        assert val2 > val1, f"A₂₂(rb=10) должен быть > A₂₂(rb=5)"

    def test_A22_zero_at_rw(self, fluid, rock, p_profile, t_profile,
                            s_profile):
        """A₂₂ → 0 при rb → rw (домен вырождается)."""
        state = _make_state(r_b=R_W * 1.0001)
        val = gas_A22(fluid, rock, p_profile, t_profile, s_profile, state)
        assert abs(val) < 1e-6, f"A₂₂ → 0 при rb→rw, получено {val:.6e}"


# ─── Тесты A₂₁ (eq:A21) ─────────────────────────────────────────

class TestA21:
    def test_A21_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₂₁ конечен при baseline параметрах."""
        state = _make_state()
        val = gas_A21(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"A₂₁ не конечен: {val}"

    def test_A21_positive(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₂₁ > 0: оба слагаемых положительны (∂p/∂rb < 0)."""
        state = _make_state()
        val = gas_A21(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val > 0, f"A₂₁ должен быть > 0, получено {val:.6e}"

    def test_A21_single_phase(self, fluid, rock, p_profile, t_profile,
                              s_profile):
        """A₂₁ конечен при вырожденном домене (rb ≈ rw, Sg_w = 0)."""
        state = _make_state(r_b=R_W * 1.01, Sg_w=0.0)
        val = gas_A21(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"A₂₁ не конечен при r_b→r_w: {val}"


# ─── Тесты A₂₃ (eq:A23) ─────────────────────────────────────────

class TestA23:
    def test_A23_sign_consistent(self, fluid, rock, p_profile, t_profile,
                                 s_profile):
        """sign(A₂₃) = −sign(β_o_sat): при baseline β_o_sat < 0 → A₂₃ > 0."""
        state = _make_state()
        pbs = p_profile.pb_star(state.r_b, state.dT_w, fluid, t_profile)
        p1, T1, _ = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0,
                                     state.dT_w, state.Sg_w)
        beta_o_sat_val = fluid.beta_o_sat(p1, T1)
        val = gas_A23(fluid, rock, p_profile, t_profile, s_profile, state)
        if beta_o_sat_val < 0:
            assert val > 0, (
                f"β_o_sat={beta_o_sat_val:.3e} < 0, но A₂₃={val:.6e} не > 0"
            )
        else:
            assert val < 0, (
                f"β_o_sat={beta_o_sat_val:.3e} > 0, но A₂₃={val:.6e} не < 0"
            )

    def test_A23_isothermal(self, fluid, rock, p_profile, t_profile,
                            s_profile):
        """A₂₃ конечен при ΔTw = 0 (Ψ не зависит от ΔTw)."""
        state = _make_state(dT_w=0.0)
        val = gas_A23(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"A₂₃(ΔTw=0) не конечен: {val}"


# ─── Тесты F₂ (eq:F2) ───────────────────────────────────────────

class TestF2:
    def test_F2_sign(self, fluid, rock, p_profile, t_profile, s_profile):
        """F₂ > 0: нефть притекает в зону разгазирования, Sg растёт."""
        state = _make_state()
        val = gas_F2(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val > 0, f"F₂ должен быть > 0, получено {val:.6e}"

    def test_F2_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        """F₂ конечен при baseline параметрах."""
        state = _make_state()
        val = gas_F2(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"F₂ не конечен: {val}"

    def test_F2_single_phase(self, fluid, rock, p_profile, t_profile,
                             s_profile):
        """F₂ конечен при вырожденном домене."""
        state = _make_state(r_b=R_W * 1.01, Sg_w=0.0)
        val = gas_F2(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"F₂ не конечен при r_b→r_w: {val}"

    def test_F2_nonstationary_pwf(self, fluid, rock, p_profile, t_profile,
                                  s_profile):
        """F₂ при ṗ_wf ≠ 0 отличается от стационарного значения."""
        state_stat = _make_state()
        state_nstat = _make_state(dp_wf_dt=1e5)
        val_stat = gas_F2(fluid, rock, p_profile, t_profile, s_profile,
                          state_stat)
        val_nstat = gas_F2(fluid, rock, p_profile, t_profile, s_profile,
                           state_nstat)
        assert math.isfinite(val_nstat), f"F₂(ṗ_wf≠0) не конечен: {val_nstat}"
        assert val_stat != pytest.approx(val_nstat, rel=1e-6), (
            f"F₂ не изменился при ṗ_wf=1e5: {val_stat:.6e} ≈ {val_nstat:.6e}"
        )


# ─── Тест согласованности строк 1 и 2 ───────────────────────────

# ─── Тесты (ρcp)_eff (FEAT-005c, шаг 1) ─────────────────────────

class TestRhocpEff:
    def test_rhocp_eff_positive(self, fluid):
        val = fluid.rhocp_eff(P_WF, T_0, SG_BASELINE, PHI, 2e6)
        assert val > 0, f"(ρcp)_eff должен быть > 0, получено {val}"

    def test_rhocp_eff_star_ge_eff(self, fluid):
        rhocp = fluid.rhocp_eff(P_WF, T_0, SG_BASELINE, PHI, 2e6)
        rhocp_star = fluid.rhocp_eff_star(P_WF, T_0, SG_BASELINE, PHI, 2e6)
        assert rhocp_star >= rhocp, (
            f"(ρcp)_eff*={rhocp_star:.3e} < (ρcp)_eff={rhocp:.3e}"
        )

    def test_rhocp_eff_single_phase(self, fluid):
        val = fluid.rhocp_eff(P_0, T_0, 0.0, PHI, 2e6)
        assert val > 0

    def test_rhocp_eff_star_dimension(self, fluid):
        val = fluid.rhocp_eff_star(P_WF, T_0, SG_BASELINE, PHI, 2e6)
        assert 1e4 < val < 1e8, f"(ρcp)_eff* порядка 10⁶, получено {val:.3e}"

    def test_rhocp_eff_star_equals_eff_above_pb(self, fluid):
        """Выше pb: dRs/dT = 0 ⟹ модификация = 0."""
        rhocp = fluid.rhocp_eff(P_0, T_0, 0.0, PHI, 2e6)
        rhocp_star = fluid.rhocp_eff_star(P_0, T_0, 0.0, PHI, 2e6)
        assert rhocp_star == pytest.approx(rhocp, rel=1e-12)


# ─── Тесты Q̄_ad* (FEAT-005c, шаг 2) ─────────────────────────────

# ─── Тесты A₃₁ (FEAT-005c, шаг 3) ───────────────────────────────

class TestA31:
    def test_A31_sign(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₃₁ > 0: −(Q̄_ad* > 0)·(∂p/∂rb < 0) → положительный."""
        state = _make_state()
        val = energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val > 0, f"A₃₁ должен быть > 0, получено {val:.6e}"

    def test_A31_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        state = _make_state()
        val = energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"A₃₁ не конечен: {val}"

    def test_A31_single_phase(self, fluid, rock, p_profile, t_profile,
                              s_profile):
        """A₃₁ конечен при вырождении зоны 1."""
        state = _make_state(r_b=R_W * 1.01, Sg_w=0.0, dT_w=0.0)
        val = energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"A₃₁ не конечен при r_b→r_w: {val}"


# ─── Тесты A₃₃ (FEAT-005c, шаг 4) ───────────────────────────────

class TestA33:
    def test_A33_sign(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₃₃ < 0: (ρcp)_eff* > 0, Ψ > 0, знак минус."""
        state = _make_state()
        val = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val < 0, f"A₃₃ должен быть < 0, получено {val:.6e}"

    def test_A33_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        state = _make_state()
        val = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"A₃₃ не конечен: {val}"

    def test_A33_isothermal(self, fluid, rock, p_profile, t_profile,
                            s_profile):
        """A₃₃ конечен и < 0 при ΔTw = 0."""
        state = _make_state(dT_w=0.0)
        val = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"A₃₃(ΔTw=0) не конечен: {val}"
        assert val < 0, f"A₃₃(ΔTw=0) должен быть < 0, получено {val:.6e}"


# ─── Тесты C̄_conv*, Q̄_JT* (FEAT-005c, шаг 5 PVT) ────────────────

class TestCConvStar:
    def test_C_conv_star_positive(self, fluid, rock):
        k = rock["k"]
        val = fluid.C_conv_star(P_WF, T_0, SG_BASELINE, k)
        assert val > 0, f"C̄_conv* должен быть > 0, получено {val:.6e}"


class TestQJTStarCoeff:
    def test_QJT_star_coeff_finite(self, fluid, rock):
        k = rock["k"]
        val = fluid.QJT_star_coeff(P_WF, T_0, SG_BASELINE, k)
        assert math.isfinite(val), f"Q̄_JT* не конечен: {val}"

    def test_QJT_star_coeff_single_phase_positive(self, fluid, rock):
        """Выше pb: dRs/dp = 0 ⟹ нет дегазационной добавки, JT > 0."""
        k = rock["k"]
        val = fluid.QJT_star_coeff(P_0, T_0, 0.0, k)
        assert val > 0, f"Q̄_JT* (однофазный) должен быть > 0, получено {val:.6e}"


# ─── Тесты F₃ (FEAT-005c, шаг 5) ────────────────────────────────

class TestF3:
    def test_F3_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        state = _make_state()
        val = energy_F3(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val), f"F₃ не конечен: {val}"

    def test_F3_nonzero(self, fluid, rock, p_profile, t_profile, s_profile):
        """F₃ ≠ 0 при dT_w > 0."""
        state = _make_state(dT_w=2.0)
        val = energy_F3(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val != 0.0, f"F₃ не должен быть 0, получено {val:.6e}"

    def test_F3_isothermal_nonzero(self, fluid, rock, p_profile, t_profile,
                                   s_profile):
        """При dT_w = 0: F₃ ≠ 0 (JT действует при любом ΔP)."""
        state = _make_state(dT_w=0.0)
        val = energy_F3(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val != 0.0, f"F₃(ΔTw=0) не должен быть 0"

    def test_F3_dot_dTw_positive(self, fluid, rock, p_profile, t_profile,
                                 s_profile):
        """ΔṪ_w = F₃/A₃₃ > 0: охлаждение нарастает (A₃₃ < 0)."""
        state = _make_state(dT_w=0.0)
        a33 = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)
        f3 = energy_F3(fluid, rock, p_profile, t_profile, s_profile, state)
        dot_dTw = f3 / a33
        assert dot_dTw > 0, (
            f"ΔṪ_w = F₃/A₃₃ = {f3:.3e}/{a33:.3e} = {dot_dTw:.3e} должен быть > 0"
        )

    def test_F3_no_pwf(self, fluid, rock, p_profile, t_profile, s_profile):
        """dp_wf_dt = 0 → I_pwf = 0."""
        state = _make_state(dp_wf_dt=0.0)
        val = energy_F3(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(val)

    def test_F3_nonstationary_pwf(self, fluid, rock, p_profile, t_profile,
                                  s_profile):
        """F₃ меняется при ṗ_wf ≠ 0."""
        state_stat = _make_state()
        state_nstat = _make_state(dp_wf_dt=1e5)
        val_stat = energy_F3(fluid, rock, p_profile, t_profile, s_profile,
                             state_stat)
        val_nstat = energy_F3(fluid, rock, p_profile, t_profile, s_profile,
                              state_nstat)
        assert math.isfinite(val_nstat)
        assert val_stat != pytest.approx(val_nstat, rel=1e-6), (
            f"F₃ не изменился при ṗ_wf=1e5"
        )


# ─── Тест A₃₂ = 0 (FEAT-005c, шаг 6) ────────────────────────────

class TestA32Zero:
    def test_no_energy_A32_in_api(self):
        """A₃₂ = 0 по расщеплению (eq:matrix_structure)."""
        import src.coefficients as coeff
        assert not hasattr(coeff, "energy_A32"), (
            "energy_A32 не должна существовать: A₃₂ = 0 по расщеплению"
        )


# ─── Тест согласованности строки 3 (FEAT-005c, шаг 6) ───────────

class TestEnergyConsistency:
    def test_energy_coefficients_finite(self, fluid, rock, p_profile,
                                       t_profile, s_profile):
        state = _make_state()
        a31 = energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)
        a33 = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)
        f3 = energy_F3(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(a31)
        assert math.isfinite(a33)
        assert math.isfinite(f3)
        assert a33 != 0.0

    def test_single_phase_limit_energy(self, fluid, rock, p_profile,
                                       t_profile, s_profile):
        """При r_b → r_w + ε все коэффициенты конечны."""
        state = _make_state(r_b=R_W * 1.01, Sg_w=0.001, dT_w=0.0)
        a31 = energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)
        a33 = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)
        f3 = energy_F3(fluid, rock, p_profile, t_profile, s_profile, state)
        assert math.isfinite(a31), f"A₃₁ не конечен при r_b→r_w: {a31}"
        assert math.isfinite(a33), f"A₃₃ не конечен при r_b→r_w: {a33}"
        assert math.isfinite(f3), f"F₃ не конечен при r_b→r_w: {f3}"


class TestQadStarCoeff:
    def test_Qad_star_coeff_positive(self, fluid):
        val = fluid.Qad_star_coeff(P_WF, T_0, SG_BASELINE, PHI, 2e6, CR)
        assert val > 0, f"Q̄_ad* должен быть > 0, получено {val}"

    def test_Qad_star_coeff_single_phase(self, fluid):
        val = fluid.Qad_star_coeff(P_0, T_0, 0.0, PHI, 2e6, CR)
        assert val > 0, f"Q̄_ad* (однофазный) должен быть > 0, получено {val}"

    def test_Qad_star_coeff_dimension(self, fluid):
        val = fluid.Qad_star_coeff(P_WF, T_0, SG_BASELINE, PHI, 2e6, CR)
        assert 1e-3 < val < 1e2, f"Q̄_ad* ~ 0.1–1.0 (безразм.), получено {val:.3e}"


class TestConsistency:
    def test_dot_rb_positive(self, fluid, rock, p_profile, t_profile,
                             s_profile):
        """ṙ_b = F₁/A₁₁ > 0 (из первого уравнения при расщеплении)."""
        state = _make_state()
        a11 = oil_A11(fluid, rock, p_profile, t_profile, state)
        f1 = oil_F1(fluid, rock, p_profile, t_profile, s_profile, state)
        dot_rb = f1 / a11
        assert dot_rb > 0, (
            f"ṙ_b = F₁/A₁₁ = {f1:.6e}/{a11:.6e} = {dot_rb:.6e} должен быть > 0"
        )


class TestAssembly:
    """Тесты сборки матрицы A и вектора F — FEAT-005d."""

    def test_A12_zero(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₁₂ = 0 — расщепление (eq:matrix_structure)."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        assert A[0, 1] == 0.0, f"A₁₂ должен быть 0, получено {A[0, 1]:.6e}"

    def test_A32_zero(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₃₂ = 0 — расщепление (eq:matrix_structure)."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        assert A[2, 1] == 0.0, f"A₃₂ должен быть 0, получено {A[2, 1]:.6e}"

    def test_det_nonzero(self, fluid, rock, p_profile, t_profile, s_profile):
        """det(A) ≠ 0 при baseline параметрах."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        det = np.linalg.det(A)
        assert det != 0.0, "det(A) = 0 — матрица вырождена"
        assert np.isfinite(det), f"det(A) не конечен: {det}"

    def test_2x2_subsystem_nonsingular(self, fluid, rock, p_profile,
                                        t_profile, s_profile):
        """Определитель подсистемы 2×2 (уравнения 1 и 3) ненулевой."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        det_13 = A[0, 0] * A[2, 2] - A[0, 2] * A[2, 0]
        assert det_13 != 0.0, (
            f"A₁₁·A₃₃ − A₁₃·A₃₁ = {det_13:.6e} — подсистема 2×2 вырождена"
        )

    def test_all_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        """Все элементы A и F конечны."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.all(np.isfinite(A)), f"A содержит NaN/Inf:\n{A}"
        assert np.all(np.isfinite(F)), f"F содержит NaN/Inf: {F}"

    def test_solve_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        """ẋ = A⁻¹·F — все компоненты конечны."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        x_dot = np.linalg.solve(A, F)
        assert np.all(np.isfinite(x_dot)), f"ẋ содержит NaN/Inf: {x_dot}"

    def test_solve_dot_rb_positive(self, fluid, rock, p_profile, t_profile,
                                    s_profile):
        """ṙ_b > 0 из полной матричной системы."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        x_dot = np.linalg.solve(A, F)
        assert x_dot[0] > 0, (
            f"ṙ_b = {x_dot[0]:.6e} должен быть > 0 (зона разгазирования растёт)"
        )

    def test_assembly_matches_components(self, fluid, rock, p_profile,
                                         t_profile, s_profile):
        """Элементы A и F из сборки совпадают с прямыми вызовами."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)

        assert A[0, 0] == pytest.approx(oil_A11(fluid, rock, p_profile, t_profile, state))
        assert A[0, 2] == pytest.approx(oil_A13(fluid, rock, p_profile, t_profile, state))
        assert A[1, 0] == pytest.approx(gas_A21(fluid, rock, p_profile, t_profile, s_profile, state))
        assert A[1, 1] == pytest.approx(gas_A22(fluid, rock, p_profile, t_profile, s_profile, state))
        assert A[1, 2] == pytest.approx(gas_A23(fluid, rock, p_profile, t_profile, s_profile, state))
        assert A[2, 0] == pytest.approx(energy_A31(fluid, rock, p_profile, t_profile, s_profile, state))
        assert A[2, 2] == pytest.approx(energy_A33(fluid, rock, p_profile, t_profile, s_profile, state))

        assert F[0] == pytest.approx(oil_F1(fluid, rock, p_profile, t_profile, s_profile, state))
        assert F[1] == pytest.approx(gas_F2(fluid, rock, p_profile, t_profile, s_profile, state))
        assert F[2] == pytest.approx(energy_F3(fluid, rock, p_profile, t_profile, s_profile, state))

    def test_small_Sg(self, fluid, rock, p_profile, t_profile, s_profile):
        """Сборка работает при малом Sg_w ≈ 0.01 и rb ≈ rw."""
        state = _make_state(r_b=0.2, Sg_w=0.01, dT_w=0.1)
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.all(np.isfinite(A)), f"A при Sg≈0:\n{A}"
        assert np.all(np.isfinite(F)), f"F при Sg≈0: {F}"
        det = np.linalg.det(A)
        assert det != 0.0, f"det(A) = 0 при Sg≈0"


# ─── Тесты A_{2,β} ──────────────────────────────────────────────


class TestA2beta:
    def test_A2beta_positive(self, fluid, rock, p_profile, t_profile, s_profile):
        """A_{2,β} > 0 при Sg_w > 0 (ln η < 0, минус перед интегралом)."""
        state = _make_state(Sg_w=0.1)
        val = gas_A2beta(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val > 0, f"A_2beta должен быть > 0, получено {val:.6e}"

    def test_A2beta_zero_at_Sg0(self, fluid, rock, p_profile, t_profile, s_profile):
        """A_{2,β} = 0 при Sg_w = 0."""
        state = _make_state(Sg_w=0.0)
        val = gas_A2beta(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val == pytest.approx(0.0, abs=1e-15)

    def test_A2beta_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        state = _make_state()
        val = gas_A2beta(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.isfinite(val)


# ─── Тесты A₄₁ ──────────────────────────────────────────────────


class TestA41:
    def test_A41_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        state = _make_state()
        val = gas_A41(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.isfinite(val), f"A₄₁ не конечен: {val}"

    def test_A41_structure_like_A21(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₄₁ имеет ту же структуру, что A₂₁, но с дополнительным весом η^β."""
        state = _make_state()
        a21 = gas_A21(fluid, rock, p_profile, t_profile, s_profile, state)
        a41 = gas_A41(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.isfinite(a21)
        assert np.isfinite(a41)


# ─── Тесты A₄₂ ──────────────────────────────────────────────────


class TestA42:
    def test_A42_positive(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₄₂ > 0 — геометрический интеграл."""
        state = _make_state()
        val = gas_A42(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val > 0, f"A₄₂ должен быть > 0, получено {val:.6e}"

    def test_A42_less_than_A22(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₄₂ < A₂₂: дополнительный множитель η^β < 1 уменьшает интеграл."""
        state = _make_state()
        a22 = gas_A22(fluid, rock, p_profile, t_profile, s_profile, state)
        a42 = gas_A42(fluid, rock, p_profile, t_profile, s_profile, state)
        assert a42 < a22, f"A₄₂={a42:.6e} должен быть < A₂₂={a22:.6e}"


# ─── Тесты A₄₃ ──────────────────────────────────────────────────


class TestA43:
    def test_A43_positive(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₄₃ > 0 при Sg_w > 0 (Галёркин, однозначный знак)."""
        state = _make_state(Sg_w=0.1)
        val = gas_A43(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val > 0, f"A₄₃ должен быть > 0, получено {val:.6e}"

    def test_A43_zero_at_Sg0(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₄₃ = 0 при Sg_w = 0."""
        state = _make_state(Sg_w=0.0)
        val = gas_A43(fluid, rock, p_profile, t_profile, s_profile, state)
        assert val == pytest.approx(0.0, abs=1e-15)


# ─── Тесты A₄₄ ──────────────────────────────────────────────────


class TestA44:
    def test_A44_sign_like_A23(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₄₄ и A₂₃ имеют одинаковый знак (оба строятся из −∫r·So·βo_sat·Ψ·dr)."""
        state = _make_state()
        a23 = gas_A23(fluid, rock, p_profile, t_profile, s_profile, state)
        a44 = gas_A44(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.sign(a44) == np.sign(a23), (
            f"A₄₄={a44:.6e} и A₂₃={a23:.6e} должны иметь одинаковый знак"
        )

    def test_A44_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        state = _make_state()
        val = gas_A44(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.isfinite(val)


# ─── Тесты F₄ ────────────────────────────────────────────────────


class TestF4:
    def test_F4_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        state = _make_state()
        val = gas_F4(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.isfinite(val), f"F₄ не конечен: {val}"

    def test_F4_no_rw_singularity(self, fluid, rock, p_profile, t_profile, s_profile):
        """F₄ конечен даже при малом γ — сингулярность на r_w подавлена весом η^β."""
        state = _make_state(r_b=0.2, Sg_w=0.05, dT_w=0.5)
        val = gas_F4(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.isfinite(val), f"F₄ при малом rb: {val}"
