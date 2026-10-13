"""Радиус изобары p = pb: одна функция diagnostics.rs.isobar_radius и три места вызова (DEBT-065).

Изобару считали три функции — rs.front_radius, two_phase.degassing_front и
closed_form._front_radius — одной формулой с разными краевыми случаями.
Теперь функция одна; края (решения пользователя 2026-10-11):
  * давление ниже pb во всех ячейках — изобара между последним центром и
    контуром, узел (R_ext, p_ext): на контуре задано p = p_ext (Дирихле);
  * pb не выше давления в первой ячейке — nan: ячейки изобару между r_w и
    первым центром не разрешают, а p_wf при скине — давление за скином;
  * профиль немонотонен — первое пересечение от забоя.
Расчёта нет, кроме замкнутого решения примера 11 (~2 с) — быстрый уровень.
"""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from gpn_multiphase_solver.diagnostics.rs import isobar_radius

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
MPA = 1e6
PB = 15.0 * MPA                     # pb синтетики, Па
R_EXT, P_EXT = 50.0, 20.0 * MPA     # контур синтетики — как у примера 04
R = np.geomspace(0.1, 45.0, 6)      # центры ячеек синтетики, м; R[-1] = 45 < R_EXT


def _r_log(r1, p1, r2, p2, pb):
    """Интерполяция ln r по p между узлами (r1, p1), (r2, p2) — ожидаемое значение."""
    w = (pb - p1) / (p2 - p1)
    return float(np.exp(np.log(r1) + w * (np.log(r2) - np.log(r1))))


# ── isobar_radius на синтетических профилях ──

@pytest.mark.parametrize("p_mpa, j", [
    ([14, 16, 17, 18, 19, 19.5], 1),       # первая пара ячеек 0–1 (тест краёв из реестра)
    ([10, 12, 14, 16, 18, 19.5], 3),       # середина, пара 2–3
    ([10, 11, 12, 13, 14, 16.0], 5),       # последняя пара 4–5, узел контура не нужен
])
def test_crossing_between_neighbour_cells(p_mpa, j):
    """Пересечение внутри сетки — между ячейками j-1 и j; значение побитово прежнее."""
    p = np.array(p_mpa, float) * MPA
    # Та же формула, те же числа: прежние три функции давали ровно это значение.
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == _r_log(R[j - 1], p[j - 1], R[j], p[j], PB)


def test_logarithmic_profile_is_exact():
    """На профиле p = a + b·ln r интерполяция по ln r точна — внутри сетки и до контура."""
    a, b = 14.0 * MPA, 0.5 * MPA
    p = a + b * np.log(R)
    p_ext = a + b * np.log(R_EXT)
    # 2.7 м — между центрами; 48 м — между последним центром (45 м) и контуром (50 м).
    for r_star in (2.7, 48.0):
        pb = a + b * np.log(r_star)
        assert isobar_radius(R, p, pb, R_EXT, p_ext) == pytest.approx(r_star, rel=1e-12)


def test_gas_to_contour_uses_contour_node():
    """Давление ниже pb во всех ячейках (как в примере 11): изобара между последним центром и контуром.

    Прежде: rs.front_radius и degassing_front — nan, closed_form._front_radius —
    центр последней ячейки R[-1]. Теперь — интерполяция до узла (R_EXT, P_EXT).
    """
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    r_b = isobar_radius(R, p, PB, R_EXT, P_EXT)
    assert R[-1] < r_b < R_EXT
    assert r_b == _r_log(R[-1], p[-1], R_EXT, P_EXT, PB)


def test_contour_below_pb_is_nan():
    """p_ext < pb: разгазирована вся область вместе с контуром — изобары в области нет."""
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    assert np.isnan(isobar_radius(R, p, PB, R_EXT, 14.8 * MPA))


@pytest.mark.parametrize("p0_mpa", [15.0, 15.5])
def test_no_cell_below_pb_is_nan(p0_mpa):
    """pb не выше давления в первой ячейке — nan.

    Изобара, если есть, лежит между r_w и первым центром: ячейки её не
    разрешают, а узел (r_w, p_wf) не используется — при скине p_wf —
    давление за скином. 15.0 — граница: p[0] = pb ровно, газа в ячейке нет
    (прежние три функции давали nan и здесь).
    """
    p = np.array([p0_mpa, 16, 17, 18, 19, 19.5]) * MPA
    assert np.isnan(isobar_radius(R, p, PB, R_EXT, P_EXT))


def test_nonmonotone_profile_takes_first_crossing_from_well():
    """Немонотонный профиль: граница зоны p < pb, примыкающей к скважине (ячейки 0–1).

    np.searchsorted прежнего кода дал бы здесь пару 3–4: двоичный поиск на
    неупорядоченном массиве попадает в произвольное пересечение.
    """
    p = np.array([10, 16, 14, 14.5, 18, 19.5]) * MPA
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == _r_log(R[0], p[0], R[1], p[1], PB)


def test_cell_at_pb_returns_its_center():
    """p = pb точно в ячейке 2: радиус — её центр (вес w = 1)."""
    p = np.array([10, 12, 15, 16, 18, 19.5]) * MPA
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == pytest.approx(R[2], rel=1e-15)


def test_contour_node_not_beyond_grid_raises():
    """R_ext не дальше последнего центра — сетка не от этого контура: ошибка, а не мусор."""
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    with pytest.raises(ValueError, match="узел контура"):
        isobar_radius(R, p, PB, 40.0, P_EXT)
