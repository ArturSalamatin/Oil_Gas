"""Тесты ОФП Кори и подвижностей — FEAT-002."""

import json
import pytest
from pathlib import Path
from src.pvt.black_oil import BlackOilFluid

S_OR = 0.2
S_GC = 0.05
N_O = 2.0
N_G = 2.0
KRO_MAX = 1.0
KRG_MAX = 0.8

P = 15e6
T = 350.0
K_ABS = 1e-13


@pytest.fixture
def fluid():
    return BlackOilFluid(
        {"rho_o_st": 850.0, "rho_g_st": 0.85},
        p_b=18e6, T_0=350.0,
        relperm_config={"S_or": S_OR, "S_gc": S_GC, "n_o": N_O, "n_g": N_G,
                        "k_ro_max": KRO_MAX, "k_rg_max": KRG_MAX})


# ─── Шаг 4: тесты kro/krg ──────────────────────────────────────────


class TestKro:
    def test_kro_at_Sg_zero(self, fluid):
        assert fluid.kro(0.0) == pytest.approx(KRO_MAX)

    def test_kro_at_Sg_max(self, fluid):
        assert fluid.kro(1.0 - S_OR) == pytest.approx(0.0, abs=1e-15)

    def test_kro_at_Sgc(self, fluid):
        assert fluid.kro(S_GC) == pytest.approx(KRO_MAX)

    def test_kro_monotone_decreasing(self, fluid):
        sgs = [i / 20.0 * (1.0 - S_OR) for i in range(21)]
        kros = [fluid.kro(sg) for sg in sgs]
        for i in range(len(kros) - 1):
            assert kros[i] >= kros[i + 1]

    def test_kro_in_range(self, fluid):
        for sg in [i / 20.0 * (1.0 - S_OR) for i in range(21)]:
            kr = fluid.kro(sg)
            assert 0.0 <= kr <= KRO_MAX

    def test_kro_clamp_below_zero(self, fluid):
        assert fluid.kro(-0.01) == pytest.approx(KRO_MAX)

    def test_kro_known_value(self, fluid):
        sg = S_GC + 0.5 * (1.0 - S_OR - S_GC)  # S*=0.5
        assert fluid.kro(sg) == pytest.approx(KRO_MAX * 0.5**N_O)


class TestKrg:
    def test_krg_at_Sg_zero(self, fluid):
        assert fluid.krg(0.0) == pytest.approx(0.0, abs=1e-15)

    def test_krg_at_Sg_max(self, fluid):
        assert fluid.krg(1.0 - S_OR) == pytest.approx(KRG_MAX)

    def test_krg_at_Sgc(self, fluid):
        assert fluid.krg(S_GC) == pytest.approx(0.0, abs=1e-15)

    def test_krg_monotone_increasing(self, fluid):
        sgs = [i / 20.0 * (1.0 - S_OR) for i in range(21)]
        krgs = [fluid.krg(sg) for sg in sgs]
        for i in range(len(krgs) - 1):
            assert krgs[i] <= krgs[i + 1]

    def test_krg_in_range(self, fluid):
        for sg in [i / 20.0 * (1.0 - S_OR) for i in range(21)]:
            kr = fluid.krg(sg)
            assert 0.0 <= kr <= KRG_MAX

    def test_krg_clamp_above_max(self, fluid):
        assert fluid.krg(0.95) == pytest.approx(KRG_MAX)

    def test_krg_known_value(self, fluid):
        sg = S_GC + 0.5 * (1.0 - S_OR - S_GC)  # S*=0.5
        assert fluid.krg(sg) == pytest.approx(KRG_MAX * 0.5**N_G)


# ─── Шаг 5: тесты подвижностей и Λ ─────────────────────────────────


class TestMobility:
    def test_mobility_o_formula(self, fluid):
        Sg = 0.1
        expected = K_ABS * fluid.kro(Sg) / fluid.mu_o(P, T)
        assert fluid.mobility_o(P, T, Sg, K_ABS) == pytest.approx(expected)

    def test_mobility_g_formula(self, fluid):
        Sg = 0.1
        expected = K_ABS * fluid.krg(Sg) / fluid.mu_g(P, T)
        assert fluid.mobility_g(P, T, Sg, K_ABS) == pytest.approx(expected)

    def test_mobility_o_positive(self, fluid):
        assert fluid.mobility_o(P, T, 0.1, K_ABS) > 0

    def test_mobility_g_positive(self, fluid):
        assert fluid.mobility_g(P, T, 0.1, K_ABS) > 0

    def test_mobility_g_zero_below_Sgc(self, fluid):
        assert fluid.mobility_g(P, T, 0.0, K_ABS) == pytest.approx(0.0, abs=1e-30)

    def test_Lambda_formula(self, fluid):
        Sg = 0.1
        expected = (fluid.mobility_o(P, T, Sg, K_ABS)
                    + fluid.mobility_g(P, T, Sg, K_ABS)) / fluid.Bg(P, T)
        assert fluid.Lambda(P, T, Sg, K_ABS) == pytest.approx(expected)

    def test_Lambda_positive(self, fluid):
        assert fluid.Lambda(P, T, 0.1, K_ABS) > 0

    def test_Lambda_single_phase(self, fluid):
        expected = KRO_MAX * K_ABS / (fluid.Bg(P, T) * fluid.mu_o(P, T))
        assert fluid.Lambda(P, T, 0.0, K_ABS) == pytest.approx(expected)

    def test_mobility_o_over_Bo_formula(self, fluid):
        Sg = 0.1
        expected = fluid.mobility_o(P, T, Sg, K_ABS) / fluid.Bo(P, T)
        assert fluid.mobility_o_over_Bo(P, T, Sg, K_ABS) == pytest.approx(expected)

    def test_mobility_o_over_Bo_positive(self, fluid):
        assert fluid.mobility_o_over_Bo(P, T, 0.1, K_ABS) > 0


# ─── Шаг 6: интеграционный тест baseline.json ───────────────────────


def test_baseline_config_relperm():
    config_path = Path(__file__).parent.parent / "configs" / "baseline.json"
    with open(config_path) as f:
        config = json.load(f)
    fluid = BlackOilFluid(
        config["pvt"],
        config["initial_conditions"]["p_b"],
        config["initial_conditions"]["T_0"],
        relperm_config=config["relative_permeability"])
    k = config["rock"]["k"]
    p = config["initial_conditions"]["p_0"]
    T = config["initial_conditions"]["T_0"]
    assert fluid.kro(0.0) == pytest.approx(config["relative_permeability"]["k_ro_max"])
    assert fluid.krg(0.0) == 0.0
    assert fluid.Lambda(p, T, 0.0, k) > 0


# ─── Шаг 7: тест дефолтов ───────────────────────────────────────────


def test_default_relperm_config():
    fluid = BlackOilFluid({"rho_o_st": 850.0, "rho_g_st": 0.85}, 18e6, 350.0)
    assert fluid.kro(0.0) == pytest.approx(1.0)
    assert fluid.krg(0.0) == 0.0
    assert fluid._S_or == 0.2
    assert fluid._S_gc == 0.05
