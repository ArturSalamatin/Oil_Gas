"""Тесты для RelPermModel (фаза 2).

Воспроизведение формул Кори, проверка ветвлений, производных.
"""

import numpy as np
import pytest
from gpn_multiphase_solver.pvt import RelPermModel, CoreyRP
from gpn_multiphase_solver.pvt.base import DifferentiableRelPerm


# ── Параметры эталонного набора ────────────────────────────────
S_OR = 0.2
S_GC = 0.05
N_O = 2.0
N_G = 2.0
KRO_MAX = 1.0
KRG_MAX = 0.8
DENOM = 1.0 - S_OR - S_GC  # 0.75


def _S_star(Sg):
    return np.clip((np.asarray(Sg, float) - S_GC) / DENOM, 0.0, 1.0)


def _kro_formula(Sg):
    return KRO_MAX * (1.0 - _S_star(Sg)) ** N_O


def _krg_formula(Sg):
    return KRG_MAX * _S_star(Sg) ** N_G


def _dkro_dSg_formula(Sg):
    """Аналитическая производная kro по Sg."""
    S = _S_star(Sg)
    mobile = (S > 0) & (S < 1)
    deriv = -KRO_MAX * N_O * (1.0 - S) ** (N_O - 1) / DENOM
    return np.where(mobile, deriv, 0.0)


def _dkrg_dSg_formula(Sg):
    S = _S_star(Sg)
    mobile = (S > 0) & (S < 1)
    deriv = KRG_MAX * N_G * S ** (N_G - 1) / DENOM
    return np.where(mobile, deriv, 0.0)


@pytest.fixture
def corey():
    return CoreyRP(S_or=S_OR, S_gc=S_GC, n_o=N_O, n_g=N_G,
                   kro_max=KRO_MAX, krg_max=KRG_MAX)


# ── Валидация конструктора ────────────────────────────────────

class TestValidation:
    def test_S_or_negative(self):
        with pytest.raises(ValueError):
            CoreyRP(S_or=-0.1, S_gc=0.05, n_o=2, n_g=2)

    def test_S_gc_negative(self):
        with pytest.raises(ValueError):
            CoreyRP(S_or=0.2, S_gc=-0.1, n_o=2, n_g=2)

    def test_S_or_plus_S_gc_ge_one(self):
        with pytest.raises(ValueError):
            CoreyRP(S_or=0.6, S_gc=0.5, n_o=2, n_g=2)

    def test_n_o_zero(self):
        with pytest.raises(ValueError):
            CoreyRP(S_or=0.2, S_gc=0.05, n_o=0, n_g=2)

    def test_n_g_negative(self):
        with pytest.raises(ValueError):
            CoreyRP(S_or=0.2, S_gc=0.05, n_o=2, n_g=-1)

    def test_kro_max_gt_one(self):
        with pytest.raises(ValueError):
            CoreyRP(S_or=0.2, S_gc=0.05, n_o=2, n_g=2, kro_max=1.5)

    def test_isinstance_relperm(self, corey):
        assert isinstance(corey, RelPermModel)

    def test_isinstance_differentiable(self, corey):
        assert isinstance(corey, DifferentiableRelPerm)


# ── Формулы: сравнение код vs эталон ──────────────────────────

class TestCoreyFormula:
    """Параметризованный тест: код vs формула Кори."""

    @pytest.mark.parametrize("Sg", [0.0, 0.025, 0.05, 0.1, 0.2,
                                     0.3, 0.425, 0.5, 0.6, 0.7, 0.8])
    def test_kro_matches_formula(self, corey, Sg):
        expected = _kro_formula(Sg)
        actual = corey.kro(np.array([Sg]))[0]
        assert actual == pytest.approx(expected, abs=1e-14)

    @pytest.mark.parametrize("Sg", [0.0, 0.025, 0.05, 0.1, 0.2,
                                     0.3, 0.425, 0.5, 0.6, 0.7, 0.8])
    def test_krg_matches_formula(self, corey, Sg):
        expected = _krg_formula(Sg)
        actual = corey.krg(np.array([Sg]))[0]
        assert actual == pytest.approx(expected, abs=1e-14)


# ── Конкретные эталонные числа ────────────────────────────────

class TestCoreyConcreteValues:
    """Вручную вычисленные значения (не через код)."""

    # S_or=0.2, S_gc=0.05, denom=0.75

    def test_kro_Sg_zero(self, corey):
        # S*=0 → kro = 1.0·(1-0)^2 = 1.0
        assert corey.kro(np.array([0.0]))[0] == pytest.approx(1.0)

    def test_kro_Sg_0_05(self, corey):
        # S*=0 → kro = 1.0
        assert corey.kro(np.array([0.05]))[0] == pytest.approx(1.0)

    def test_kro_Sg_0_425(self, corey):
        # S* = (0.425-0.05)/0.75 = 0.5 → kro = (1-0.5)^2 = 0.25
        assert corey.kro(np.array([0.425]))[0] == pytest.approx(0.25)

    def test_kro_Sg_0_8(self, corey):
        # S* = (0.8-0.05)/0.75 = 1.0 → kro = 0.0
        assert corey.kro(np.array([0.8]))[0] == pytest.approx(0.0, abs=1e-14)

    def test_krg_Sg_0_05(self, corey):
        # S*=0 → krg = 0.8·0^2 = 0.0
        assert corey.krg(np.array([0.05]))[0] == pytest.approx(0.0)

    def test_krg_Sg_0_425(self, corey):
        # S*=0.5 → krg = 0.8·0.25 = 0.2
        assert corey.krg(np.array([0.425]))[0] == pytest.approx(0.2)

    def test_krg_Sg_0_8(self, corey):
        # S*=1 → krg = 0.8·1.0 = 0.8
        assert corey.krg(np.array([0.8]))[0] == pytest.approx(0.8)

    def test_kro_Sg_0_2(self, corey):
        # S* = (0.2-0.05)/0.75 = 0.2 → kro = (0.8)^2 = 0.64
        assert corey.kro(np.array([0.2]))[0] == pytest.approx(0.64)

    def test_krg_Sg_0_2(self, corey):
        # S* = 0.2 → krg = 0.8·0.04 = 0.032
        assert corey.krg(np.array([0.2]))[0] == pytest.approx(0.032)


# ── Clamping (за пределами [S_gc, 1-S_or]) ────────────────────

class TestClamping:
    def test_kro_negative_Sg(self, corey):
        assert corey.kro(np.array([-0.1]))[0] == pytest.approx(1.0)

    def test_krg_negative_Sg(self, corey):
        assert corey.krg(np.array([-0.1]))[0] == pytest.approx(0.0)

    def test_kro_above_max_Sg(self, corey):
        assert corey.kro(np.array([0.95]))[0] == pytest.approx(0.0, abs=1e-14)

    def test_krg_above_max_Sg(self, corey):
        assert corey.krg(np.array([0.95]))[0] == pytest.approx(0.8)


# ── Производные: аналитика vs формула ─────────────────────────

class TestDerivatives:
    @pytest.mark.parametrize("Sg", [0.1, 0.2, 0.3, 0.425, 0.5, 0.6, 0.7])
    def test_dkro_dSg_formula(self, corey, Sg):
        """Аналитическая производная kro совпадает с формулой."""
        expected = _dkro_dSg_formula(Sg)
        actual = corey.dkro_dSg(np.array([Sg]))[0]
        assert actual == pytest.approx(expected, rel=1e-12)

    @pytest.mark.parametrize("Sg", [0.1, 0.2, 0.3, 0.425, 0.5, 0.6, 0.7])
    def test_dkrg_dSg_formula(self, corey, Sg):
        expected = _dkrg_dSg_formula(Sg)
        actual = corey.dkrg_dSg(np.array([Sg]))[0]
        assert actual == pytest.approx(expected, rel=1e-12)

    def test_dkro_dSg_negative_interior(self, corey):
        Sg = np.linspace(0.1, 0.7, 20)
        assert np.all(corey.dkro_dSg(Sg) < 0)

    def test_dkrg_dSg_positive_interior(self, corey):
        Sg = np.linspace(0.1, 0.7, 20)
        assert np.all(corey.dkrg_dSg(Sg) > 0)

    def test_dkro_zero_at_endpoints(self, corey):
        deriv = corey.dkro_dSg(np.array([0.0, 0.05, 0.8, 0.9]))
        np.testing.assert_allclose(deriv, 0.0, atol=1e-10)

    def test_dkrg_zero_at_endpoints(self, corey):
        deriv = corey.dkrg_dSg(np.array([0.0, 0.05, 0.8, 0.9]))
        np.testing.assert_allclose(deriv, 0.0, atol=1e-10)

    def test_dkro_vs_finite_diff(self, corey):
        Sg = np.array([0.15, 0.3, 0.5, 0.65])
        eps = 1e-7
        fd = (corey.kro(Sg + eps) - corey.kro(Sg - eps)) / (2 * eps)
        np.testing.assert_allclose(corey.dkro_dSg(Sg), fd, rtol=1e-5)

    def test_dkrg_vs_finite_diff(self, corey):
        Sg = np.array([0.15, 0.3, 0.5, 0.65])
        eps = 1e-7
        fd = (corey.krg(Sg + eps) - corey.krg(Sg - eps)) / (2 * eps)
        np.testing.assert_allclose(corey.dkrg_dSg(Sg), fd, rtol=1e-5)

    def test_dkro_concrete_value(self, corey):
        # Sg=0.425, S*=0.5: dkro/dSg = -1.0·2·(1-0.5)^1 / 0.75 = -1.3333...
        assert corey.dkro_dSg(np.array([0.425]))[0] == pytest.approx(
            -1.0 * 2.0 * 0.5 / 0.75, rel=1e-12)

    def test_dkrg_concrete_value(self, corey):
        # Sg=0.425, S*=0.5: dkrg/dSg = 0.8·2·0.5^1 / 0.75 = 1.06666...
        assert corey.dkrg_dSg(np.array([0.425]))[0] == pytest.approx(
            0.8 * 2.0 * 0.5 / 0.75, rel=1e-12)


# ── Другие параметры Кори ─────────────────────────────────────

class TestCoreyAlternativeParams:
    def test_cubic_exponents(self):
        """n_o=3, n_g=1.5, другие пределы."""
        rp = CoreyRP(S_or=0.15, S_gc=0.1, n_o=3.0, n_g=1.5,
                     kro_max=0.9, krg_max=0.7)
        denom = 1.0 - 0.15 - 0.1  # 0.75

        Sg = 0.4
        S_star = (Sg - 0.1) / denom
        kro_expected = 0.9 * (1.0 - S_star) ** 3.0
        krg_expected = 0.7 * S_star ** 1.5

        assert rp.kro(np.array([Sg]))[0] == pytest.approx(kro_expected, rel=1e-12)
        assert rp.krg(np.array([Sg]))[0] == pytest.approx(krg_expected, rel=1e-12)

    def test_no_residual_oil(self):
        """S_or=0: газонасыщенность может достичь 1.0."""
        rp = CoreyRP(S_or=0.0, S_gc=0.0, n_o=2, n_g=2)
        assert rp.kro(np.array([1.0]))[0] == pytest.approx(0.0, abs=1e-14)
        assert rp.krg(np.array([1.0]))[0] == pytest.approx(1.0)
        assert rp.kro(np.array([0.0]))[0] == pytest.approx(1.0)
        assert rp.krg(np.array([0.0]))[0] == pytest.approx(0.0)

    def test_no_critical_gas(self):
        """S_gc=0: krg > 0 при любом Sg > 0."""
        rp = CoreyRP(S_or=0.2, S_gc=0.0, n_o=2, n_g=2, krg_max=0.5)
        assert rp.krg(np.array([0.01]))[0] > 0
        assert rp.krg(np.array([0.0]))[0] == pytest.approx(0.0)

    def test_linear_exponents(self):
        """n_o=1, n_g=1: линейные ОФП."""
        rp = CoreyRP(S_or=0.0, S_gc=0.0, n_o=1, n_g=1)
        Sg = np.array([0.3])
        assert rp.kro(Sg)[0] == pytest.approx(0.7, rel=1e-12)
        assert rp.krg(Sg)[0] == pytest.approx(0.3, rel=1e-12)


# ── Векторизация ──────────────────────────────────────────────

class TestVectorized:
    def test_array_shape(self, corey):
        Sg = np.linspace(0.0, 0.8, 50)
        assert corey.kro(Sg).shape == (50,)
        assert corey.krg(Sg).shape == (50,)
        assert corey.dkro_dSg(Sg).shape == (50,)
        assert corey.dkrg_dSg(Sg).shape == (50,)

    def test_full_array_vs_formula(self, corey):
        Sg = np.linspace(0.0, 0.8, 100)
        np.testing.assert_allclose(corey.kro(Sg), _kro_formula(Sg), atol=1e-14)
        np.testing.assert_allclose(corey.krg(Sg), _krg_formula(Sg), atol=1e-14)
