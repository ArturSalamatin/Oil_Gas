"""DEBT-067: условие сходимости по ячейке принимает решение на пределе округления.

Условие BUG-022 (Ур. (eq:newton_cell_tol) problem_statement.tex) недостижимо ниже предела
округления — меры вектора |J|·ulp(z) (eq:newton_cell_floor, DEBT-055): Ньютон встаёт на
0.28–0.46 предела строки, решение отвергалось, шаг дробился. Теперь строка, не прошедшая
порог, проходит, если её невязка не выше её предела: |F_r| <= CELL_FLOOR_KAPPA·(|J|·ulp(z))_r
(eq:newton_cell_tol_floor), CELL_FLOOR_KAPPA = 1. Сравнение построчное.

План: vault/plans/debt-067 accept-at-cell-floor.md; числа — vault/issues/debt-067/probes/
(unit_numbers.out.txt, synthetic_check.out.txt).
"""

import numpy as np
import pytest
from scipy.sparse import csc_matrix

from radial_blackoil import blackoil

from .test_prototype_cell_tolerance import CELL_TOL, DT, _build as _nabor, _newton
from .test_prototype_failure_diagnostics import _bug018_model

EPS = float(np.spacing(1.0))      # ulp(1.0): при z = 1 предел строки r — d_r·EPS


def test_kappa_default_is_one():
    """Множитель предела по умолчанию — 1: «невязка строки не выше её предела» (решение пользователя 2026-10-14).

    Замер плана: Ньютон встаёт на 0.28–0.46 предела строки — запас вдвое; при 0.5 запас
    к BUG-018 (0.46) был бы ×1.09. Ловит: случайную смену множителя.
    """
    assert blackoil.CELL_FLOOR_KAPPA == 1.0


# ═══════════════════════════════════════════════════════════
# A. Построчное сравнение на синтетике
# ═══════════════════════════════════════════════════════════

def _synthetic():
    """Nabor_1b N = 12 с cell_tol = 1e-8, диагональный якобиан, z = 1.

    Строка 0 (нефть, забойная ячейка): мера 3e-8, предел строки 6e-8 — проходит по своему.
    Строка 1 (нефть, ячейка 1): мера 2e-8, предел строки 1e-8 — нет.
    Возвращает модель, веса dt/V_p, невязки строк 0 и 1, якобиан, z.
    """
    model, state = _nabor(12, cell_tol=CELL_TOL)
    n = model.grid.n
    w = model._cell_weights(state, DT)
    f0, f1 = 3e-8 / w[0], 2e-8 / w[1]
    d = np.ones(2 * n)
    d[0], d[1] = 2.0 * f0 / EPS, 0.5 * f1 / EPS
    return model, w, f0, f1, csc_matrix(np.diag(d)), np.ones(2 * n)


class TestRowLimit:
    """_cells_converged(f, w, J, z): строгое условие BUG-022, затем — предел каждой строки выше порога."""

    def test_strict_pass_needs_no_jacobian(self):
        """Мера 5e-9 <= 1e-8: строгое условие выполнено, якобиан не нужен — побитово как до DEBT-067."""
        model, w, _, _, _, _ = _synthetic()
        f = np.zeros(2 * model.grid.n)
        f[0] = 0.5e-8 / w[0]
        assert model._cells_converged(f, w)

    def test_row_at_its_limit_passes(self):
        """Строка 0: мера 3e-8 > 1e-8, но |F_0| — половина её предела: проходит. Ловит: предел не действует."""
        model, w, f0, _, J, z = _synthetic()
        f = np.zeros(2 * model.grid.n)
        f[0] = f0
        assert model._cells_converged(f, w, J, z)

    def test_row_above_its_limit_fails(self):
        """Строки 0 и 1: строка 1 выше своего предела — отказ, хотя максимум меры (3e-8) не выше максимума предела (6e-8).

        Ловит: сравнение максимумов по сетке (вариант (б) плана) — строка прошла бы по
        пределу другой ячейки (у BUG-018 максимумы меры и предела — в o16 и g13).
        """
        model, w, f0, f1, J, z = _synthetic()
        f = np.zeros(2 * model.grid.n)
        f[0], f[1] = f0, f1
        assert model._cell_measure(f, w) <= model._cell_floor(J, z, w)
        assert not model._cells_converged(f, w, J, z)

    def test_strict_without_jacobian_or_kappa(self, monkeypatch):
        """Без якобиана (проверка до первой итерации) и при CELL_FLOOR_KAPPA = 0 — строгое условие BUG-022."""
        model, w, f0, _, J, z = _synthetic()
        f = np.zeros(2 * model.grid.n)
        f[0] = f0
        assert not model._cells_converged(f, w)
        monkeypatch.setattr(blackoil, "CELL_FLOOR_KAPPA", 0.0)
        assert not model._cells_converged(f, w, J, z)

    def test_nonfinite_row_fails(self):
        """NaN в невязке строки — отказ, хотя других строк выше порога нет.

        np.all по пустой выборке — True: выборка «a·w > порог» NaN-строку не содержит, и
        метод принял бы нечисловую невязку; выборка ~(a·w <= порог) её включает. Из
        Ньютона так не попасть (раньше стоит ||F||_inf <= tol, с NaN ложно), но контракт —
        метода (аудит 1 плана). Ловит: приём NaN-невязки по пределу.
        """
        model, w, _, _, J, z = _synthetic()
        f = np.zeros(2 * model.grid.n)
        f[2] = np.nan
        assert not model._cells_converged(f, w, J, z)


# ═══════════════════════════════════════════════════════════
# B. Сутки BUG-018 при N = 350 (шаг 86400 с)
# ═══════════════════════════════════════════════════════════

class TestBug018Day:
    def test_newton_accepted_at_limit(self, monkeypatch):
        """Первый Ньютон суток: 3 итерации, мера 2.596e-8 > 1e-8, но не выше предела 6.420e-8 — принят.

        Замер плана (unit_numbers.out.txt, п. 5): без предела — отказ линейного поиска
        после 4 итераций в той же точке (четвёртая итерация её не сдвинула); с пределом —
        приём на 3-й, множитель поячеечно 0.46. Предел — с якобианом 3-й итерации
        (предыдущего приближения), с якобианом в точке совпадает до 12 знаков. Отчёт
        решения, принятого на пределе, несёт предел (cell_floor).
        Ловит: предел не стоит в проверке после обновления; отчёт без предела.
        """
        model, ps, dt = _bug018_model()
        z0 = model.pack(ps, ps.gas_active)
        _, rep = model._newton_fixed_active_set(z0, ps, dt, ps.gas_active)
        assert rep.converged and rep.iterations == 3 and rep.exit_reason == "converged"
        # Приём выше строгого порога зависит от предела, а не от точного значения невязки.
        assert CELL_TOL < rep.cell_measure <= rep.cell_floor
        # Без предела — прежний отказ на пределе (DEBT-055)
        monkeypatch.setattr(blackoil, "CELL_FLOOR_KAPPA", 0.0)
        _, rep0 = model._newton_fixed_active_set(z0, ps, dt, ps.gas_active)
        assert not rep0.converged and rep0.iterations == 4 and rep0.exit_reason == "line_search"

    def test_day_step_solved_by_advance(self):
        """Шаг 86400 с целиком: advance сходится (до DEBT-067 отказывали все ступени, сутки дробились).

        Замер плана (unit_numbers.out.txt, п. 1): ступень 1 принимает первого Ньютона на
        пределе, набор фаз меняется, второй Ньютон отказывает по лимиту итераций (мера 4.5e4 —
        не предел); шаг решает третья ступень, её последний Ньютон — по строгому условию:
        мера 8.16e-9 <= 1e-8. Ловит: возврат отказа суток на пределе округления.
        """
        model, ps, dt = _bug018_model()
        _, rep = model.advance(ps, dt)
        assert rep.converged and rep.globalized
        assert rep.cell_measure <= CELL_TOL and rep.cell_floor is None


# ═══════════════════════════════════════════════════════════
# C. Предел ниже порога — условие BUG-022 не ослаблено
# ═══════════════════════════════════════════════════════════

def test_limit_below_threshold_changes_nothing():
    """Nabor_1b N = 12 после 2 итераций без условия: мера 2.33e-8, предел 7.9e-15 — предел не принимает.

    Строка выше порога проходит по пределу, только если сам предел строки выше порога
    (|F_r|·Δt/V > ε и |F_r| <= κ·предел ⇒ κ·предел·Δt/V > ε). Здесь он ниже на шесть
    порядков: недорешённую забойную ячейку BUG-022 предел не пропускает, Ньютон делает
    третью итерацию (test_refines_under_resolved_well_cell). Замер плана (п. 6): max
    |F_r|/(|J|·ulp)_r по строкам выше порога — 3.6e6.
    Ловит: предел, ослабляющий условие BUG-022 там, где он ниже порога.
    """
    base, state = _nabor(12)
    z2, r2 = _newton(base, state)
    assert r2.iterations == 2
    model, state = _nabor(12, cell_tol=CELL_TOL)
    w = model._cell_weights(state, DT)
    J, f = model.finite_difference_jacobian(z2, state, DT, state.gas_active)
    assert model._cell_measure(f, w) > CELL_TOL
    assert model._cell_floor(J, z2, w) < 1e-12
    assert not model._cells_converged(f, w, J, z2)
