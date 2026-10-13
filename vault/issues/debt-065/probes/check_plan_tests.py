"""Проба DEBT-065 (план): тесты шага 1 на копии isobar_radius из плана.

Запуск из numerical_solver/:
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-065\\probes\\check_plan_tests.py -q -p no:cacheprovider
"""

import numpy as np
import pytest


def isobar_radius(r, p, pb, R_ext, p_ext):
    """Копия кода шага 1 плана."""
    r_n = np.append(np.asarray(r, float), float(R_ext))
    p_n = np.append(np.asarray(p, float), float(p_ext))
    above = np.flatnonzero(p_n >= pb)
    if above.size == 0:
        return np.nan
    j = int(above[0])
    if j == 0:
        return np.nan
    if j == r_n.size - 1 and not r_n[-2] < r_n[-1]:
        raise ValueError(
            f"узел контура R_ext = {R_ext} м не дальше последнего центра "
            f"r[-1] = {r_n[-2]} м: сетка задана не для этого контура")
    w = (pb - p_n[j - 1]) / (p_n[j] - p_n[j - 1])
    return float(np.exp(np.log(r_n[j - 1]) + w * (np.log(r_n[j]) - np.log(r_n[j - 1]))))


MPA = 1e6
PB = 15.0 * MPA
R_EXT, P_EXT = 50.0, 20.0 * MPA
R = np.geomspace(0.1, 45.0, 6)


def _r_log(r1, p1, r2, p2, pb):
    w = (pb - p1) / (p2 - p1)
    return float(np.exp(np.log(r1) + w * (np.log(r2) - np.log(r1))))


@pytest.mark.parametrize("p_mpa, j", [
    ([14, 16, 17, 18, 19, 19.5], 1),
    ([10, 12, 14, 16, 18, 19.5], 3),
    ([10, 11, 12, 13, 14, 16.0], 5),
])
def test_crossing_between_neighbour_cells(p_mpa, j):
    p = np.array(p_mpa, float) * MPA
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == _r_log(R[j - 1], p[j - 1], R[j], p[j], PB)


def test_logarithmic_profile_is_exact():
    a, b = 14.0 * MPA, 0.5 * MPA
    p = a + b * np.log(R)
    p_ext = a + b * np.log(R_EXT)
    for r_star in (2.7, 48.0):
        pb = a + b * np.log(r_star)
        assert isobar_radius(R, p, pb, R_EXT, p_ext) == pytest.approx(r_star, rel=1e-12)


def test_gas_to_contour_uses_contour_node():
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    r_b = isobar_radius(R, p, PB, R_EXT, P_EXT)
    assert R[-1] < r_b < R_EXT
    assert r_b == _r_log(R[-1], p[-1], R_EXT, P_EXT, PB)


def test_contour_below_pb_is_nan():
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    assert np.isnan(isobar_radius(R, p, PB, R_EXT, 14.8 * MPA))


@pytest.mark.parametrize("p0_mpa", [15.0, 15.5])
def test_no_cell_below_pb_is_nan(p0_mpa):
    p = np.array([p0_mpa, 16, 17, 18, 19, 19.5]) * MPA
    assert np.isnan(isobar_radius(R, p, PB, R_EXT, P_EXT))


def test_nonmonotone_profile_takes_first_crossing_from_well():
    p = np.array([10, 16, 14, 14.5, 18, 19.5]) * MPA
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == _r_log(R[0], p[0], R[1], p[1], PB)
    # Утверждение докстринга: searchsorted дал бы пару 3–4.
    assert int(np.searchsorted(p, PB)) == 4


def test_cell_at_pb_returns_its_center():
    p = np.array([10, 12, 15, 16, 18, 19.5]) * MPA
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == pytest.approx(R[2], rel=1e-15)


def test_contour_node_not_beyond_grid_raises():
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    with pytest.raises(ValueError, match="узел контура"):
        isobar_radius(R, p, PB, 40.0, P_EXT)
