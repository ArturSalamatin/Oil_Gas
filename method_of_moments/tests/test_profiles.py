"""Тесты параметризации профилей p(r), Sg(r), T(r) — FEAT-003."""

import math

import pytest

from src.profiles.pressure import PressureProfile


# ─── Общие параметры (baseline.json) ─────────────────────────────────
R_W = 0.1
R_EXT = 500.0
P_WF = 15e6
P_0 = 20e6
PB_STAR = 18e6  # pb(T_0) при ΔTw=0
T_0 = 350.0
R_B = 10.0


# ═══ Тесты PressureProfile ═══════════════════════════════════════════

class TestPressureBoundary:

    @pytest.fixture
    def pp(self):
        return PressureProfile(R_W, R_EXT, P_WF, P_0)

    @pytest.fixture
    def gamma(self, pp):
        return pp.gamma(R_B, PB_STAR)

    def test_p_inner_at_rw(self, pp, gamma):
        assert pp(R_W, R_B, PB_STAR, gamma) == pytest.approx(P_WF)

    def test_p_inner_at_rb(self, pp, gamma):
        assert pp(R_B, R_B, PB_STAR, gamma) == pytest.approx(PB_STAR)

    def test_p_outer_at_rb(self, pp, gamma):
        p_outer = PB_STAR + (P_0 - PB_STAR) * math.log(R_B / R_B) / math.log(R_EXT / R_B)
        assert p_outer == pytest.approx(PB_STAR)

    def test_p_outer_at_Rext(self, pp, gamma):
        assert pp(R_EXT, R_B, PB_STAR, gamma) == pytest.approx(P_0)


class TestPressureGamma:

    @pytest.fixture
    def pp(self):
        return PressureProfile(R_W, R_EXT, P_WF, P_0)

    def test_gamma_flux_continuity(self, pp):
        gamma = pp.gamma(R_B, PB_STAR)
        dp_inner = pp.dp_dr(R_B, R_B, PB_STAR, gamma)
        dp_outer = pp.dp_dr(R_B + 1e-8, R_B, PB_STAR, gamma)
        assert dp_inner == pytest.approx(dp_outer, rel=1e-6)

    def test_gamma_positive(self, pp):
        gamma = pp.gamma(R_B, PB_STAR)
        assert gamma > 0


class TestPressureDerivative:

    @pytest.fixture
    def pp(self):
        return PressureProfile(R_W, R_EXT, P_WF, P_0)

    @pytest.fixture
    def gamma(self, pp):
        return pp.gamma(R_B, PB_STAR)

    def test_dp_dr_inner_vs_fd(self, pp, gamma):
        r = 1.0
        eps = 1e-6
        dp_fd = (pp(r + eps, R_B, PB_STAR, gamma) - pp(r - eps, R_B, PB_STAR, gamma)) / (2 * eps)
        dp_an = pp.dp_dr(r, R_B, PB_STAR, gamma)
        assert dp_an == pytest.approx(dp_fd, rel=1e-4)

    def test_dp_dr_outer_vs_fd(self, pp, gamma):
        r = 100.0
        eps = 1e-6
        dp_fd = (pp(r + eps, R_B, PB_STAR, gamma) - pp(r - eps, R_B, PB_STAR, gamma)) / (2 * eps)
        dp_an = pp.dp_dr(r, R_B, PB_STAR, gamma)
        assert dp_an == pytest.approx(dp_fd, rel=1e-4)

    def test_dp_dr_at_rw_gamma_lt_1(self, pp):
        gamma = pp.gamma(R_B, PB_STAR)
        assert gamma < 1.0
        dp = pp.dp_dr(R_W, R_B, PB_STAR, gamma)
        assert math.isinf(dp)
        assert dp > 0


class TestPressureMonotone:

    def test_p_monotone_increasing(self):
        pp = PressureProfile(R_W, R_EXT, P_WF, P_0)
        gamma = pp.gamma(R_B, PB_STAR)
        import numpy as np
        radii = np.geomspace(R_W, R_EXT, 50)
        pressures = [pp(r, R_B, PB_STAR, gamma) for r in radii]
        for i in range(len(pressures) - 1):
            assert pressures[i + 1] > pressures[i]


# ═══ Тесты SaturationProfile ══════════════════════════════════════════

from src.profiles.saturation import SaturationProfile

SG_W = 0.15
BETA = 2.0


class TestSaturationBoundary:

    @pytest.fixture
    def sp(self):
        return SaturationProfile(R_W, beta=BETA)

    def test_Sg_at_rw(self, sp):
        assert sp(R_W, R_B, SG_W) == pytest.approx(SG_W)

    def test_Sg_at_rb(self, sp):
        assert sp(R_B, R_B, SG_W) == pytest.approx(0.0)

    def test_Sg_outside_zone(self, sp):
        assert sp(100.0, R_B, SG_W) == 0.0


class TestSaturationMonotone:

    def test_Sg_monotone_decreasing(self):
        import numpy as np
        sp = SaturationProfile(R_W, beta=BETA)
        radii = np.geomspace(R_W, R_B, 20)
        sats = [sp(r, R_B, SG_W) for r in radii]
        for i in range(len(sats) - 1):
            assert sats[i + 1] <= sats[i]

    def test_Sg_in_range(self):
        import numpy as np
        sp = SaturationProfile(R_W, beta=BETA)
        radii = np.geomspace(R_W, R_B, 20)
        for r in radii:
            sg = sp(r, R_B, SG_W)
            assert 0.0 <= sg <= SG_W


class TestSaturationDerivative:

    def test_dSg_dr_vs_fd(self):
        sp = SaturationProfile(R_W, beta=BETA)
        r = 1.0
        eps = 1e-6
        fd = (sp(r + eps, R_B, SG_W) - sp(r - eps, R_B, SG_W)) / (2 * eps)
        an = sp.dSg_dr(r, R_B, SG_W)
        assert an == pytest.approx(fd, rel=1e-4)


class TestSaturationDifferentBeta:

    @pytest.mark.parametrize("beta", [1.0, 2.0, 5.0])
    def test_boundary_preserved(self, beta):
        sp = SaturationProfile(R_W, beta=beta)
        assert sp(R_W, R_B, SG_W) == pytest.approx(SG_W)
        assert sp(R_B, R_B, SG_W) == pytest.approx(0.0)


# ═══ Тесты TemperatureProfile ═════════════════════════════════════════

from src.profiles.temperature import TemperatureProfile

SIGMA = 2.0
DT_W = 5.0


class TestPsiBoundary:

    @pytest.fixture
    def tp(self):
        return TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)

    def test_Psi_at_zero(self, tp):
        assert tp.Psi(0.0) == pytest.approx(0.0)

    def test_Psi_at_one(self, tp):
        assert tp.Psi(1.0) == pytest.approx(1.0)

    def test_dPsi_at_one(self, tp):
        assert tp.dPsi_dzeta(1.0) == pytest.approx(0.0)


class TestTemperatureBoundary:

    @pytest.fixture
    def tp(self):
        return TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)

    def test_T_at_Rext(self, tp):
        assert tp(R_EXT, DT_W) == pytest.approx(T_0)

    def test_T_at_rw(self, tp):
        assert tp(R_W, DT_W) == pytest.approx(T_0 - DT_W)

    def test_dT_dr_adiabatic_wall(self, tp):
        assert tp.dT_dr(R_W, DT_W) == pytest.approx(0.0)


class TestTemperatureDerivative:

    def test_dT_dr_vs_fd(self):
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)
        r = 10.0
        eps = 1e-6
        fd = (tp(r + eps, DT_W) - tp(r - eps, DT_W)) / (2 * eps)
        an = tp.dT_dr(r, DT_W)
        assert an == pytest.approx(fd, rel=1e-4)

    def test_T_isothermal(self):
        import numpy as np
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)
        radii = np.geomspace(R_W, R_EXT, 20)
        for r in radii:
            assert tp(r, 0.0) == pytest.approx(T_0)


class TestJIntegral:

    @pytest.fixture
    def tp(self):
        return TemperatureProfile(R_W, R_EXT, T_0, sigma=1.0)

    @pytest.fixture
    def tp2(self):
        return TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)

    @pytest.mark.parametrize("m", [0, 1, 2, 3])
    def test_J_vs_quad_sigma1(self, tp, m):
        from scipy.integrate import quad
        expected, _ = quad(lambda z: z**m * (2 - z**tp.sigma), 0, 1)
        assert tp.J(m) == pytest.approx(expected, abs=1e-12)

    @pytest.mark.parametrize("m", [0, 1, 2])
    def test_J_vs_quad_sigma2(self, tp2, m):
        from scipy.integrate import quad
        expected, _ = quad(lambda z: z**m * (2 - z**tp2.sigma), 0, 1)
        assert tp2.J(m) == pytest.approx(expected, abs=1e-12)


class TestPsiDifferentSigma:

    @pytest.mark.parametrize("sigma", [0.5, 1.0, 2.0, 5.0])
    def test_boundary_preserved(self, sigma):
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=sigma)
        assert tp.Psi(0.0) == pytest.approx(0.0)
        assert tp.Psi(1.0) == pytest.approx(1.0)
        assert tp.dPsi_dzeta(1.0) == pytest.approx(0.0)


class TestTemperatureSingularity:

    def test_dT_dr_at_Rext_sigma_lt_1(self):
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=0.5)
        dt = tp.dT_dr(R_EXT, DT_W)
        assert math.isinf(dt)


class TestPbStar:

    def test_pb_star_isothermal(self):
        from src.pvt.black_oil import BlackOilFluid
        pvt_cfg = {"rho_o_st": 850.0, "rho_g_st": 0.85}
        fluid = BlackOilFluid(pvt_cfg, p_b=PB_STAR, T_0=T_0)

        pp = PressureProfile(R_W, R_EXT, P_WF, P_0)

        class MockTemp:
            T_0 = 350.0
            sigma = 2.0
            def Psi(self, zeta):
                zs = zeta ** self.sigma
                return zs * (2.0 - zs)

        tp = MockTemp()
        pb_star = pp.pb_star(R_B, 0.0, fluid, tp)
        assert pb_star == pytest.approx(fluid.pb(T_0))


# ═══ Интеграционные тесты ════════════════════════════════════════════

class TestIntegrationPbStarWithTemperature:

    def test_pb_star_decreases_with_cooling(self):
        from src.pvt.black_oil import BlackOilFluid
        pvt_cfg = {"rho_o_st": 850.0, "rho_g_st": 0.85}
        fluid = BlackOilFluid(pvt_cfg, p_b=PB_STAR, T_0=T_0)

        pp = PressureProfile(R_W, R_EXT, P_WF, P_0)
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)

        pb_iso = pp.pb_star(R_B, 0.0, fluid, tp)
        pb_cool = pp.pb_star(R_B, 5.0, fluid, tp)
        assert pb_cool < pb_iso


class TestIntegrationProfilesConsistency:

    def test_profiles_at_rb(self):
        from src.pvt.black_oil import BlackOilFluid
        pvt_cfg = {"rho_o_st": 850.0, "rho_g_st": 0.85}
        fluid = BlackOilFluid(pvt_cfg, p_b=PB_STAR, T_0=T_0)

        pp = PressureProfile(R_W, R_EXT, P_WF, P_0)
        sp = SaturationProfile(R_W, beta=BETA)
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)

        pb_star = pp.pb_star(R_B, 0.0, fluid, tp)
        gamma = pp.gamma(R_B, pb_star)

        p_inner = pp(R_B, R_B, pb_star, gamma)
        p_outer = pp(R_B + 1e-10, R_B, pb_star, gamma)
        assert p_inner == pytest.approx(pb_star)
        assert p_outer == pytest.approx(pb_star, rel=1e-6)
        assert sp(R_B, R_B, SG_W) == pytest.approx(0.0)

    def test_gamma_positive(self):
        pp = PressureProfile(R_W, R_EXT, P_WF, P_0)
        gamma = pp.gamma(R_B, PB_STAR)
        assert gamma > 0
