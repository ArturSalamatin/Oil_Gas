"""BUG-027: проверка кода тестов плана до реализации (копии шагов 3 и 4).

Зелёная часть: тексты тестов из плана (шаг 3) на текущем коде проходят.
Негатив: те же проверки против записи документа до BUG-027
(ненормированное «среднее» 1/(w_L/λ_L + w_R/λ_R) под вторым ln) краснеют.

Запуск из numerical_solver/ (основного или worktree):
    .venv\\Scripts\\python -m pytest <путь>\\plan_tests_check.py -q -p no:cacheprovider
"""
import sys
from pathlib import Path

import numpy as np
import pytest

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    raise SystemExit(f"Запускать из numerical_solver/, cwd = {SOLVER}")
sys.path[:0] = [str(SOLVER), str(SOLVER / "tests")]

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402
from test_energy_matrix_examples import _ref_conductive  # noqa: E402

print(f"Код: {gpn_multiphase_solver.__file__}")


def _ref_conductive_old_doc(grid, lambda_eff):
    """Запись документа до BUG-027 буквально: среднее без множителя (w_L + w_R)."""
    w_L, w_R = grid.log_weights_left, grid.log_weights_right
    lam_face = 1.0 / (w_L / lambda_eff[:-1] + w_R / lambda_eff[1:])
    r_c = grid.r_centers
    Q_int = 2.0 * np.pi * grid.h * lam_face / np.log(r_c[1:] / r_c[:-1])
    Q_ext = (2.0 * np.pi * grid.h
             / np.log(grid.R_ext / grid.r_centers[-1]) * lambda_eff[-1])
    return Q_int, Q_ext


# ── Копия шага 3: новый тест test_energy_matrix_examples.py ──

def _annulus_check(ref):
    """Тело test_ref_conductive_matches_annulus_solution с подменяемым эталоном."""
    grid = LogRadialGrid(0.1, 200.0, 10.0, 20, 1e-13)
    N = grid.N
    r_c = grid.r_centers
    r_f = grid.r_faces[1:-1]
    two_pi_h = 2.0 * np.pi * grid.h

    lam = 1.228
    Q_int, Q_ext = ref(grid, np.full(N, lam))
    np.testing.assert_allclose(
        Q_int, two_pi_h * lam / np.log(r_c[1:] / r_c[:-1]), rtol=1e-12,
        err_msg="однородная λ: в знаменателе один ln (BUG-002, BUG-027)")
    np.testing.assert_allclose(
        Q_ext, two_pi_h * lam / np.log(grid.R_ext / r_c[-1]), rtol=1e-12,
        err_msg="контур: ssec:bc_disc")

    lam_cells = np.where(np.arange(N) % 2 == 0, 1.228, 0.3)
    R_layers = (np.log(r_f / r_c[:-1]) / lam_cells[:-1]
                + np.log(r_c[1:] / r_f) / lam_cells[1:])
    Q_int, _ = ref(grid, lam_cells)
    np.testing.assert_allclose(
        Q_int, two_pi_h / R_layers, rtol=1e-12,
        err_msg="эталон: сопротивления двух слоёв кольца складываются")
    Q_solver, _ = TridiagEnergySolver(grid, None, None) \
        .compute_conductive_transmissibility(lam_cells, N)
    np.testing.assert_allclose(
        Q_solver, two_pi_h / R_layers, rtol=1e-12,
        err_msg="решатель compute_conductive_transmissibility")


def test_annulus_green():
    _annulus_check(_ref_conductive)


def test_annulus_red_on_old_doc():
    with pytest.raises(AssertionError, match="один ln"):
        _annulus_check(_ref_conductive_old_doc)


# ── Копии шага 3: TestHarmonicInterpolation (test_grid.py) ──

@pytest.fixture
def grid():
    return LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=50, k=1e-13)


def _heat_flux(grid, Q_T_of):
    lam = 2.0
    T_centers = np.log(grid.r_centers)
    w_L = grid.log_weights_left
    w_R = grid.log_weights_right
    Q_T = Q_T_of(grid, w_L, w_R, lam)
    for f in range(grid.N - 1):
        dT = T_centers[f + 1] - T_centers[f]
        Q_face = Q_T[f] * dT
        assert Q_face == pytest.approx(
            2 * np.pi * grid.h * lam, rel=1e-10), f"face {f}"


def test_heat_flux_green(grid):
    _heat_flux(grid, lambda g, w_L, w_R, lam:
               2 * np.pi * g.h / (w_L / lam + w_R / lam))


def test_heat_flux_red_on_old_doc(grid):
    ln_c = np.log(grid.r_centers[1:] / grid.r_centers[:-1])
    with pytest.raises(AssertionError):
        _heat_flux(grid, lambda g, w_L, w_R, lam:
                   2 * np.pi * g.h / ln_c / (w_L / lam + w_R / lam))


def _mean_between(grid, mean_of):
    lam_cells = 1.0 + np.arange(grid.N, dtype=float)
    w_L = grid.log_weights_left
    w_R = grid.log_weights_right
    lam_face = mean_of(w_L, w_R, lam_cells[:-1], lam_cells[1:])
    assert np.all(np.isfinite(lam_face))
    assert np.all(lam_face >= lam_cells[:-1] * (1 - 1e-12))
    assert np.all(lam_face <= lam_cells[1:] * (1 + 1e-12))


def test_mean_between_green(grid):
    _mean_between(grid, lambda w_L, w_R, a, b: (w_L + w_R) / (w_L / a + w_R / b))


def test_mean_between_red_on_old_doc(grid):
    with pytest.raises(AssertionError):
        _mean_between(grid, lambda w_L, w_R, a, b: 1.0 / (w_L / a + w_R / b))


def _uniform_mean(grid, mean_of):
    lam_val = 2.5
    w_L = grid.log_weights_left
    w_R = grid.log_weights_right
    log_ratio_centers = np.log(grid.r_centers[1:] / grid.r_centers[:-1])
    lam_face = mean_of(log_ratio_centers, w_L, w_R, lam_val)
    np.testing.assert_allclose(lam_face, lam_val, rtol=1e-12)


def test_uniform_mean_green(grid):
    _uniform_mean(grid, lambda ln_c, w_L, w_R, lam: ln_c / (w_L / lam + w_R / lam))


def test_uniform_mean_red_on_old_doc(grid):
    with pytest.raises(AssertionError):
        _uniform_mean(grid, lambda ln_c, w_L, w_R, lam: 1.0 / (w_L / lam + w_R / lam))
