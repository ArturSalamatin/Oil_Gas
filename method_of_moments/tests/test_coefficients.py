"""Тесты коэффициентов ODE — §5 moments_method.tex."""

import json
import math
from pathlib import Path

import pytest

from src.pvt.black_oil import BlackOilFluid
from src.coefficients import (
    frozen_pvt_zone1, frozen_pvt_zone2,
    dp_drb_numerical, dp_dpwf_numerical,
    oil_A11, oil_A13, oil_F1,
    gas_A21, gas_A22, gas_A23, gas_F2,
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
    def test_A22_positive(self, s_profile):
        """A₂₂ > 0: подынтегральная r·(1−η^β) ≥ 0."""
        state = _make_state()
        val = gas_A22(s_profile, state)
        assert val > 0, f"A₂₂ должен быть > 0, получено {val:.6e}"

    def test_A22_grows_with_rb(self, s_profile):
        """A₂₂ растёт с r_b (больше домен интегрирования)."""
        state1 = _make_state(r_b=5.0)
        state2 = _make_state(r_b=10.0)
        val1 = gas_A22(s_profile, state1)
        val2 = gas_A22(s_profile, state2)
        assert val2 > val1, f"A₂₂(rb=10) должен быть > A₂₂(rb=5)"

    def test_A22_zero_at_rw(self, s_profile):
        """A₂₂ → 0 при rb → rw (домен вырождается)."""
        state = _make_state(r_b=R_W * 1.0001)
        val = gas_A22(s_profile, state)
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
