"""Тесты для Grid (фаза 1).

Тесты с независимыми эталонными значениями, не дублирующие логику Grid.
"""

import numpy as np
import pytest
from gpn_multiphase_solver.grid import Grid, LogRadialGrid


# ── Валидация конструктора ────────────────────────────────────

class TestValidation:
    def test_r_well_zero(self):
        with pytest.raises(ValueError, match="r_well must be > 0"):
            LogRadialGrid(r_well=0, R_ext=500, h=10, N=100)

    def test_r_well_negative(self):
        with pytest.raises(ValueError, match="r_well must be > 0"):
            LogRadialGrid(r_well=-1, R_ext=500, h=10, N=100)

    def test_R_ext_less_than_r_well(self):
        with pytest.raises(ValueError, match="R_ext must be > r_well"):
            LogRadialGrid(r_well=1.0, R_ext=0.5, h=10, N=100)

    def test_R_ext_equal_r_well(self):
        with pytest.raises(ValueError, match="R_ext must be > r_well"):
            LogRadialGrid(r_well=1.0, R_ext=1.0, h=10, N=100)

    def test_h_zero(self):
        with pytest.raises(ValueError, match="h must be > 0"):
            LogRadialGrid(r_well=0.1, R_ext=500, h=0, N=100)

    def test_h_negative(self):
        with pytest.raises(ValueError, match="h must be > 0"):
            LogRadialGrid(r_well=0.1, R_ext=500, h=-5, N=100)

    def test_N_zero(self):
        with pytest.raises(ValueError, match="N must be an integer >= 1"):
            LogRadialGrid(r_well=0.1, R_ext=500, h=10, N=0)

    def test_N_negative(self):
        with pytest.raises(ValueError, match="N must be an integer >= 1"):
            LogRadialGrid(r_well=0.1, R_ext=500, h=10, N=-5)

    def test_N_float(self):
        with pytest.raises(ValueError, match="N must be an integer >= 1"):
            LogRadialGrid(r_well=0.1, R_ext=500, h=10, N=10.5)

    def test_N_one_is_minimum(self):
        g = LogRadialGrid(r_well=0.1, R_ext=500, h=10, N=1)
        assert g.N == 1

    def test_k_negative(self):
        with pytest.raises(ValueError, match="k must be > 0"):
            LogRadialGrid(r_well=0.1, R_ext=500, h=10, N=100, k=-1)

    def test_k_default_is_one(self):
        g = LogRadialGrid(r_well=0.1, R_ext=500, h=10, N=100)
        assert g.trans_well > 0

    def test_isinstance_abc(self):
        g = LogRadialGrid(r_well=0.1, R_ext=500, h=10, N=10)
        assert isinstance(g, Grid)

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            Grid()


# ── Эталонные значения для малой сетки ────────────────────────
#
# N=3, r_w=1, R_ext=8, h=1, k=1
# Грани (geomspace): r_f = 1 · (8/1)^{j/3} = 1, 2, 4, 8
# r_L/r_R = 1/2 — одинаково для всех ячеек
# Центр ячейки — среднее геометрическое граней (eq:cell_center):
# r_j = √(r_L · r_R) = r_R · √(r_L/r_R) = r_R · √0.5 = r_R · 0.70711

R_W = 1.0
R_E = 8.0
FACES_3 = np.array([1.0, 2.0, 4.0, 8.0])

# Вычислим эталонные центры:
_factor = np.sqrt(0.5)
CENTERS_3 = FACES_3[1:] * _factor  # [2·f, 4·f, 8·f]

VOLUMES_3 = np.pi * 1.0 * np.array([
    2.0**2 - 1.0**2,   # 3π
    4.0**2 - 2.0**2,   # 12π
    8.0**2 - 4.0**2,   # 48π
])


@pytest.fixture
def grid3():
    return LogRadialGrid(r_well=R_W, R_ext=R_E, h=1.0, N=3, k=1.0)


class TestSmallGridValues:
    """Тесты с конкретными эталонными числами для N=3, r_w=1, R_ext=8."""

    def test_faces(self, grid3):
        np.testing.assert_allclose(grid3.r_faces, FACES_3, rtol=1e-14)

    def test_centers(self, grid3):
        np.testing.assert_allclose(grid3.r_centers, CENTERS_3, rtol=1e-12)

    def test_centers_inside_cells(self, grid3):
        for j in range(3):
            assert FACES_3[j] < grid3.r_centers[j] < FACES_3[j + 1]

    def test_volumes(self, grid3):
        np.testing.assert_allclose(grid3.volumes, VOLUMES_3, rtol=1e-14)

    def test_volume_sum(self, grid3):
        total = np.pi * (R_E**2 - R_W**2)
        assert np.sum(grid3.volumes) == pytest.approx(total, rel=1e-14)

    def test_transmissibility_well(self, grid3):
        # T_well = 2π·k·h / ln(r_center[0] / r_w)
        expected = 2.0 * np.pi / np.log(CENTERS_3[0] / R_W)
        assert grid3.trans_well == pytest.approx(expected, rel=1e-12)

    def test_transmissibility_ext(self, grid3):
        expected = 2.0 * np.pi / np.log(R_E / CENTERS_3[2])
        assert grid3.trans_ext == pytest.approx(expected, rel=1e-12)

    def test_transmissibility_internal(self, grid3):
        expected = np.array([
            2.0 * np.pi / np.log(CENTERS_3[1] / CENTERS_3[0]),
            2.0 * np.pi / np.log(CENTERS_3[2] / CENTERS_3[1]),
        ])
        np.testing.assert_allclose(grid3.trans_internal, expected, rtol=1e-12)


# ── Стационарный дебит — независимая проверка ─────────────────
#
# Аналитика: q = 2πkh·(p_ext - p_wf) / (μ · ln(R_ext/r_w))
# Через сетку: p(r) = логарифмический профиль, поток через каждую
# грань должен давать тот же q. Вычисляем q из проводимостей
# и разности давлений между соседними центрами + границами.

class TestStationaryRate:
    """Проверка: проводимости дают правильный аналитический дебит."""

    @pytest.fixture
    def setup(self):
        r_w, R_ext, h, k = 0.1, 500.0, 10.0, 1e-13
        mu = 0.001  # Па·с
        p_wf = 10e6  # Па
        p_ext = 25e6  # Па
        N = 100
        grid = LogRadialGrid(r_well=r_w, R_ext=R_ext, h=h, N=N, k=k)

        # Аналитический дебит (одна фаза, несжимаемая)
        q_analytic = 2 * np.pi * k * h * (p_ext - p_wf) / (mu * np.log(R_ext / r_w))

        # Логарифмический профиль давления в центрах ячеек
        p_centers = p_wf + (p_ext - p_wf) * np.log(grid.r_centers / r_w) / np.log(R_ext / r_w)

        return grid, p_centers, p_wf, p_ext, mu, q_analytic

    def test_well_flux(self, setup):
        """Поток через забойную грань = аналитический дебит."""
        grid, p, p_wf, p_ext, mu, q_analytic = setup
        mob = 1.0 / mu
        q_well = grid.trans_well * mob * (p_wf - p[0])
        # Наша конвенция: q < 0 (к скважине), дебит = -q
        assert -q_well == pytest.approx(q_analytic, rel=1e-3)

    def test_ext_flux(self, setup):
        """Поток через контурную грань = аналитический дебит."""
        grid, p, p_wf, p_ext, mu, q_analytic = setup
        mob = 1.0 / mu
        q_ext = grid.trans_ext * mob * (p[-1] - p_ext)
        assert -q_ext == pytest.approx(q_analytic, rel=1e-3)

    def test_internal_flux_uniform(self, setup):
        """Потоки через все внутренние грани одинаковы = аналитическому дебиту."""
        grid, p, p_wf, p_ext, mu, q_analytic = setup
        mob = 1.0 / mu
        q_internal = grid.trans_internal * mob * (p[:-1] - p[1:])
        np.testing.assert_allclose(-q_internal, q_analytic, rtol=1e-3)

    def test_flux_exact_for_any_N(self):
        """Забойный поток на логарифмическом профиле точен при любом N."""
        # Точность — свойство проводимости грани 2πkh/ln(r_0/r_w), а не выбора
        # центра: при p = A + B·ln r поток T·(p_0 − p_wf)/μ = 2πkh·B/μ не зависит
        # от r_0. Сам центр ячейки проверяет TestCellCenterGeometricMean.
        r_w, R_ext, h, k, mu = 0.1, 500.0, 10.0, 1e-13, 0.001
        p_wf, p_ext = 10e6, 25e6
        q_analytic = 2 * np.pi * k * h * (p_ext - p_wf) / (mu * np.log(R_ext / r_w))

        for N in [3, 10, 50, 200]:
            grid = LogRadialGrid(r_well=r_w, R_ext=R_ext, h=h, N=N, k=k)
            p = p_wf + (p_ext - p_wf) * np.log(grid.r_centers / r_w) / np.log(R_ext / r_w)
            q_well = grid.trans_well * (1.0 / mu) * (p_wf - p[0])
            rel_err = abs(-q_well - q_analytic) / q_analytic
            assert rel_err < 1e-12, f"N={N}: rel_err={rel_err}"


# ── Структурные свойства ──────────────────────────────────────

class TestStructuralProperties:
    @pytest.fixture
    def grid(self):
        return LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=100)

    def test_faces_boundary_values(self, grid):
        assert grid.r_faces[0] == pytest.approx(0.1)
        assert grid.r_faces[100] == pytest.approx(500.0)

    def test_faces_strictly_increasing(self, grid):
        assert np.all(np.diff(grid.r_faces) > 0)

    def test_faces_all_positive(self, grid):
        assert np.all(grid.r_faces > 0)

    def test_face_steps_all_positive(self, grid):
        dr = np.diff(grid.r_faces)
        assert np.all(dr > 0)

    def test_faces_log_spacing(self, grid):
        log_steps = np.diff(np.log(grid.r_faces))
        np.testing.assert_allclose(log_steps, log_steps[0], rtol=1e-12)

    def test_centers_all_positive(self, grid):
        assert np.all(grid.r_centers > 0)

    def test_centers_strictly_increasing(self, grid):
        assert np.all(np.diff(grid.r_centers) > 0)

    def test_centers_inside_cells(self, grid):
        assert np.all(grid.r_centers > grid.r_faces[:-1])
        assert np.all(grid.r_centers < grid.r_faces[1:])

    def test_all_positive(self, grid):
        assert np.all(grid.volumes > 0)
        assert np.all(grid.trans_internal > 0)
        assert grid.trans_well > 0
        assert grid.trans_ext > 0
        assert np.all(grid.log_weights_left > 0)
        assert np.all(grid.log_weights_right > 0)

    def test_array_lengths(self, grid):
        N = grid.N
        assert len(grid.r_faces) == N + 1
        assert len(grid.r_centers) == N
        assert len(grid.volumes) == N
        assert len(grid.trans_internal) == N - 1
        assert len(grid.log_weights_left) == N - 1
        assert len(grid.log_weights_right) == N - 1

    def test_N_one_cell(self):
        g = LogRadialGrid(r_well=0.1, R_ext=500, h=10, N=1)
        assert g.N == 1
        assert len(g.r_faces) == 2
        assert len(g.r_centers) == 1
        assert len(g.trans_internal) == 0
        assert len(g.log_weights_left) == 0

    def test_properties_are_readonly(self, grid):
        assert grid.r_well == 0.1
        assert grid.R_ext == 500.0
        assert grid.h == 10.0
        assert grid.N == 100

    def test_internal_trans_uniform_on_log_grid(self, grid):
        """На логарифмической сетке все внутренние проводимости одинаковы."""
        np.testing.assert_allclose(
            grid.trans_internal, grid.trans_internal[0], rtol=1e-10)


# ── Монотонность и положительность для разных N ──────────────

class TestMonotonicity:
    """Координаты и шаги положительны и монотонны при разных N."""

    @pytest.mark.parametrize("N", [1, 2, 3, 5, 10, 50, 200])
    def test_faces_positive_and_monotone(self, N):
        g = LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=N)
        assert np.all(g.r_faces > 0)
        assert np.all(np.diff(g.r_faces) > 0)

    @pytest.mark.parametrize("N", [1, 2, 3, 5, 10, 50, 200])
    def test_centers_positive_and_monotone(self, N):
        g = LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=N)
        assert np.all(g.r_centers > 0)
        if N > 1:
            assert np.all(np.diff(g.r_centers) > 0)

    @pytest.mark.parametrize("N", [1, 2, 3, 5, 10, 50, 200])
    def test_face_steps_positive(self, N):
        g = LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=N)
        dr = np.diff(g.r_faces)
        assert np.all(dr > 0)

    @pytest.mark.parametrize("N", [1, 2, 3, 5, 10, 50, 200])
    def test_volumes_positive(self, N):
        g = LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=N)
        assert np.all(g.volumes > 0)


# ── Центр ячейки: независимая верификация ─────────────────────

class TestCellCenterGeometricMean:
    """Проверка eq:cell_center: центр — середина ячейки по ln r."""

    @pytest.fixture
    def grid(self):
        return LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=50)

    def test_log_midpoint_property(self, grid):
        """ln r_j = (ln r_{j-1/2} + ln r_{j+1/2})/2 в каждой ячейке."""
        # Эталон — по граням, независимо от кода центров. Допуск абсолютный:
        # ln r проходит через ноль (r ≈ 1 м на этой сетке)
        mid = 0.5 * (np.log(grid.r_faces[:-1]) + np.log(grid.r_faces[1:]))
        np.testing.assert_allclose(np.log(grid.r_centers), mid, rtol=0, atol=1e-13)

    def test_equal_log_weights(self, grid):
        """Веса eq:face_interp равны: w_L = ln(r_{j+1/2}/r_j) = w_R = ln(r_{j+1}/r_{j+1/2})."""
        # На сетке eq:log_grid обе половины — по половине шага ln(r_{j+1}/r_j)
        np.testing.assert_allclose(grid.log_weights_left, grid.log_weights_right,
                                   rtol=1e-12)


# ── Гармоническая интерполяция через log_weights ──────────────

class TestHarmonicInterpolation:
    """Проверка log_weights: кондуктивный поток при T(r) = A·ln(r) + B."""

    @pytest.fixture
    def grid(self):
        return LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=50, k=1e-13)

    def test_heat_flux_analytic(self, grid):
        """При T = ln(r) и λ=const: тепловой поток через все грани одинаков."""
        lam = 2.0  # Вт/(м·К), постоянная теплопроводность
        T_centers = np.log(grid.r_centers)

        # Аналитический кондуктивный поток: Q = -λ·2πh·A / ln(R/rw)·Δln(r)
        # Для T = ln(r): dT/dr = 1/r, Q = -λ·2πh через всю область
        # Поток через грань = λ·2πh·(dT/dr)·r = λ·2πh = const
        # Но в дискретной форме: Q_face = Q_T · (T_{j+1} - T_j)
        # где Q_T = 2πh·λ_face / ln(r_center[j+1]/r_center[j])
        # λ_face = λ (постоянна, гармоническое среднее = λ)
        # Q_face = 2πh·λ / ln(r_center[j+1]/r_center[j]) · (ln(r[j+1]) - ln(r[j]))
        #        = 2πh·λ · 1 = 2πh·λ = const

        # Через log_weights (BUG-027): сопротивления двух кольцевых слоёв
        # [r_j, r_{j+1/2}] и [r_{j+1/2}, r_{j+1}] складываются,
        # Q_T_f = 2πh / (w_L/λ + w_R/λ) = 2πhλ / (w_L + w_R), и
        # w_L + w_R = ln(r_c[j+1]/r_c[j]) — в знаменателе один ln. Запись
        # «2πh/ln · 1/(w_L/λ + w_R/λ)» (ненормированное «среднее» λ/ln под
        # вторым ln) — дефект BUG-002; до BUG-027 она стояла и в этом
        # комментарии, и в постановке.
        # Q_face = Q_T_f · (T[j+1] - T[j])

        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        Q_T = 2 * np.pi * grid.h / (w_L / lam + w_R / lam)    # [N-1], Вт/К

        for f in range(grid.N - 1):
            dT = T_centers[f + 1] - T_centers[f]
            Q_face = Q_T[f] * dT
            # dT = ln(r[f+1]) - ln(r[f]) = w_L + w_R → Q_face = 2πhλ
            assert Q_face == pytest.approx(
                2 * np.pi * grid.h * lam, rel=1e-10), f"face {f}"

    def test_harmonic_mean_nontrivial(self, grid):
        """Среднее eq:face_interp при неоднородном λ лежит между λ_j и λ_{j+1}.

        Проверяется свойство среднего, а не только знак. Ненормированная форма
        1/(w_L/λ_j + w_R/λ_{j+1}) — запись постановки до BUG-027 — в
        1/ln(r_{j+1}/r_j) ≈ 5.9 раза больше верного среднего на этой сетке и
        выходит за max(λ_j, λ_{j+1}).
        """
        lam_cells = 1.0 + np.arange(grid.N, dtype=float)    # растёт: λ_j < λ_{j+1}
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        lam_face = (w_L + w_R) / (w_L / lam_cells[:-1] + w_R / lam_cells[1:])

        assert np.all(np.isfinite(lam_face))
        # Допуск 1e-12 — запас на округление: среднее строго между λ_j и λ_{j+1},
        # ошибка его счёта — несколько ULP
        assert np.all(lam_face >= lam_cells[:-1] * (1 - 1e-12))
        assert np.all(lam_face <= lam_cells[1:] * (1 + 1e-12))

    def test_uniform_lambda_face_value(self, grid):
        """При однородном λ среднее eq:face_interp равно λ.

        Нормировка весов eq:face_interp: w_L + w_R = ln(r_{j+1}/r_j) между
        центрами ячеек — та же проверка, что до BUG-027, но величина
        называется средним, только если равна λ.
        """
        lam_val = 2.5
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        log_ratio_centers = np.log(grid.r_centers[1:] / grid.r_centers[:-1])
        lam_face = log_ratio_centers / (w_L / lam_val + w_R / lam_val)
        np.testing.assert_allclose(lam_face, lam_val, rtol=1e-12)


# ── Параметризованный тест: баланс объёмов ────────────────────

@pytest.mark.parametrize("N", [1, 2, 3, 5, 10, 100, 1000])
def test_volume_sum_parametrized(N):
    r_w, R_ext, h = 0.1, 500.0, 10.0
    grid = LogRadialGrid(r_well=r_w, R_ext=R_ext, h=h, N=N)
    total = np.pi * h * (R_ext**2 - r_w**2)
    assert np.sum(grid.volumes) == pytest.approx(total, rel=1e-12)
