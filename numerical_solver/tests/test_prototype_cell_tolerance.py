"""BUG-022: условие сходимости Ньютона прототипа по ячейке (аргумент cell_tol).

Абсолютный критерий прототипа ||F||_inf <= atol + rtol*||F_0||_inf (м³ст/с) один на
все ячейки. На логарифмической сетке поровый объём забойной ячейки в ~(R_ext/r_w)^2 раз
меньше, чем у внешней, и та же невязка там — относительная ошибка в ~10^6 раз больше:
у примера 17 R_s(r_w) на останове блуждал на ±0.015 и убывал, хотя может только расти.
С cell_tol решение Ньютона принимается, только если ещё в каждой ячейке
max_c |F_c,i|*dt/PV_i <= cell_tol (PV — поровый объём на начало шага; газовые строки,
как и в абсолютном критерии, поделены на gas_residual_scale). Иначе — отказ решения,
шаг идёт на следующие ступени advance. По умолчанию выключено (собственные расчёты
прототипа и его эталон регрессии побитово прежние), фабрика GPN включает:
numerics.newton_cell_tol = 1e-8.

Модель Nabor_1b строится напрямую: пакет tests прототипа импортировать нельзя.
План: vault/plans/bug-022 newton-cell-relative-tolerance.md; числа —
vault/issues/bug-022/probes/unit_check.out.txt, unit_newton_direct.out.txt.
"""

from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from radial_blackoil.blackoil import RadialBlackOilModel
from radial_blackoil.grid import RadialGrid
from radial_blackoil.input_reader import load_input
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.state import BlackOilState

PROTO_ROOT = Path(__file__).parent.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
NABOR_1B = PROTO_ROOT / "tests" / "fixtures" / "Nabor_1b.xlsx"
RS300 = Path(__file__).parent / "data" / "bug020_rs300" / "config.json"
BAR = 1e5
ATM_BAR = 101325.0 / BAR
CELL_TOL = 1e-8          # numerics.newton_cell_tol по умолчанию
DT = 3600.0              # шаг отбора Nabor_1b, с
DT_STAGE4 = 168.75       # шаг останова rs300, который решает только ступень 4 (BUG-020)


def _build(n, cell_tol=None):
    """Модель Nabor_1b на n ячейках (p_wf = 100 бар) и начальное состояние без газа (200 бар)."""
    inp = load_input(NABOR_1B)
    p = inp.params
    grid = RadialGrid(float(p["Well radius rw"]), float(p["Outer radius re"]),
                      float(p["Formation thickness h"]), n, float(p["Absolute permeability"]))
    rock = CompressibleRock(float(p["Reference porosity"]), float(p["Reference pressure"]),
                            float(p["Rock compressibility cr"]))
    model = RadialBlackOilModel(grid, rock, inp.pvt, inp.relperm, 100.0,
                                float(p["Outer-boundary pressure"]),
                                float(p["Initial dissolved gas Rs"]),
                                skin=float(p["Well skin"]), linear_solver="sparse",
                                cell_tol=cell_tol)
    state = BlackOilState.undersaturated(grid.n, 200.0, float(p["Initial dissolved gas Rs"]))
    return model, state


def _measure(model, s_old, s_new, dt):
    """Мера условия на решении: max_c |F_c,i|*dt/PV_i (газ — /gas_residual_scale, как в residual)."""
    f = model.residual(model.pack(s_new), s_old, dt, s_new.gas_active)
    w = dt / model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, s_old.pressure_bar)
    n = model.grid.n
    return max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w)))


def _newton(model, state):
    """Одно решение Ньютона ступени 1 на наборе фаз начального состояния: (z, отчёт)."""
    return model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active)


# ═══════════════════════════════════════════════════════════
# A. Аргумент: по умолчанию выключено, неверное значение — ошибка
# ═══════════════════════════════════════════════════════════

class TestArgument:
    def test_default_off(self):
        """Без аргумента условия нет: cell_tol = None, весов нет — прототип считает как прежде."""
        model, state = _build(8)
        assert model.cell_tol is None
        assert model._cell_weights(state, DT) is None

    @pytest.mark.parametrize("value", [0.0, -1e-8, np.nan, np.inf])
    def test_invalid_rejected(self, value):
        """Порог — положительное конечное число: 0 и отрицательный невыполнимы, NaN и inf бессмысленны."""
        with pytest.raises(ValueError, match="cell_tol"):
            _build(8, cell_tol=value)


# ═══════════════════════════════════════════════════════════
# B. Ступени 1–3: _newton_fixed_active_set и advance (Nabor_1b, отбор 200 -> 100 бар, 1 ч)
# ═══════════════════════════════════════════════════════════

class TestFixedActiveSet:
    def test_refines_under_resolved_well_cell(self):
        """N = 12: абсолютный критерий выполнен за 2 итерации, но забойная ячейка недорешена.

        Замер плана: без условия — 2 итерации, мера 2.33e-8 > 1e-8; с условием —
        3 итерации, мера 3.44e-12, |dp| 1.13e-6 бар (тот же корень, точнее).
        Ловит: условие не проверяется (сходимость после 2 итераций).
        """
        base, state = _build(12)
        z_base, r_base = _newton(base, state)
        assert r_base.converged and r_base.iterations == 2
        assert _measure(base, state, base.unpack(z_base, state.gas_active), DT) > CELL_TOL
        model, state = _build(12, cell_tol=CELL_TOL)
        z, rep = _newton(model, state)
        assert rep.converged and rep.iterations == r_base.iterations + 1
        assert _measure(model, state, model.unpack(z, state.gas_active), DT) <= CELL_TOL
        assert np.max(np.abs(z[:12] - z_base[:12])) < 1e-5

    def test_bitwise_where_cells_already_converged(self):
        """N = 50: на месте остановки условие уже выполнено — решение побитово прежнее.

        Замер плана: 4 итерации, мера 4.72e-10 <= 1e-8 в обоих случаях.
        Ловит: условие меняет решения там, где оно не нужно (лишняя итерация, другой корень).
        """
        base, state = _build(50)
        z_base, r_base = _newton(base, state)
        assert _measure(base, state, base.unpack(z_base, state.gas_active), DT) <= CELL_TOL
        model, state = _build(50, cell_tol=CELL_TOL)
        z, rep = _newton(model, state)
        assert rep.converged and rep.iterations == r_base.iterations
        assert np.array_equal(z, z_base)

    def test_start_meets_absolute_but_not_cell_test(self):
        """Старт, где абсолютный критерий уже выполнен, а условие ячейки — нет: Ньютон итерирует.

        Начальное приближение — решение базы при N = 12 (мера 2.33e-8 > 1e-8); atol_sm3s = 1e-6
        делает абсолютный критерий выполненным сразу. Замер плана (unit_start.out.txt): без
        условия — 0 итераций, решение не меняется; с условием — 1 итерация, мера 3.44e-12.
        Ловит: условие не проверяется при выходе до цикла итераций (0 итераций).
        """
        base, state = _build(12)
        z_base, _ = _newton(base, state)
        z0, r0 = base._newton_fixed_active_set(z_base.copy(), state, DT, state.gas_active, atol_sm3s=1e-6)
        assert r0.converged and r0.iterations == 0 and np.array_equal(z0, z_base)
        model, state = _build(12, cell_tol=CELL_TOL)
        z, rep = model._newton_fixed_active_set(z_base.copy(), state, DT, state.gas_active,
                                                atol_sm3s=1e-6)
        assert rep.converged and rep.iterations >= 1
        assert _measure(model, state, model.unpack(z, state.gas_active), DT) <= CELL_TOL

    def test_advance_meets_cell_tol(self):
        """N = 50, шаг advance целиком: принятое решение удовлетворяет условию.

        Замер плана: без условия — 9 итераций (по всем решениям набора фаз), мера
        2.21e-7; с условием — 10 итераций, мера 1.38e-14, |dp| 4.41e-10 бар.
        Ловит: условие стоит не во всех решениях Ньютона шага (газ появляется на шаге:
        набор фаз меняется, решений несколько).
        """
        base, state = _build(50)
        new_base, r_base = base.advance(state, DT)
        assert r_base.converged and _measure(base, state, new_base, DT) > CELL_TOL
        model, state = _build(50, cell_tol=CELL_TOL)
        new, rep = model.advance(state, DT)
        assert rep.converged
        assert _measure(model, state, new, DT) <= CELL_TOL
        assert np.max(np.abs(new.pressure_bar - new_base.pressure_bar)) < 1e-8


# ═══════════════════════════════════════════════════════════
# C. Ступень 4: _newton_switching (останов rs300 после 10 сут добычи)
# ═══════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def shutin():
    """Модель фабрики и состояние после 10 сут добычи сценария rs300 (~2 с), управление q_oil = 0.

    Замер плана: p(r_w) = 50.8965 бар, двухфазных 289, max S_g = 0.4483.
    """
    cfg = load_config(RS300)
    sim, init = SimulatorFactory.from_config(cfg)
    s = sim.run(init).states[-1]
    model = sim._hydro._model
    model.set_oil_rate_control(0.0, ATM_BAR)
    ps = BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(),
                       sg=s.Sg.copy(), gas_active=(s.regime == 1))
    return model, ps


class TestSwitching:
    def test_switching_meets_cell_tol(self, shutin):
        """Шаг останова 168.75 с ступенью 4: условие по ячейке стоит в _newton_switching.

        Недостижимый порог 1e-30 — отказ (40 итераций), без условия — сходится; с порогом
        1e-8 мера решения <= 1e-8. До BUG-024 тест сравнивал решения без условия и с ним
        (без условия мера 2.24e-8 > 1e-8, 20 итераций против 21). С ограничением шага R_s
        (BUG-024) Ньютон и без условия сходится за 16 итераций с мерой 1.2e-11 —
        сравнение перестало различать, недостижимый порог различает всегда. Замер плана
        BUG-024: без условия и с 1e-8 — 16 итераций, мера 1.21e-11, |dp| = 0.
        Модель фабрики: cell_tol меняется на экземпляре и возвращается в finally.
        Ловит: условие не стоит в _newton_switching.
        """
        model, ps = shutin
        assert model.cell_tol == CELL_TOL               # фабрика включила (шаг 3)
        try:
            model.cell_tol = None
            a, ra = model._newton_switching(ps, DT_STAGE4)
            model.cell_tol = 1e-30
            _, rc = model._newton_switching(ps, DT_STAGE4)
            model.cell_tol = CELL_TOL
            b, rb = model._newton_switching(ps, DT_STAGE4)
        finally:
            model.cell_tol = CELL_TOL
        assert ra.converged and not rc.converged
        assert rb.converged and _measure(model, ps, b, DT_STAGE4) <= CELL_TOL
        assert np.max(np.abs(b.pressure_bar - a.pressure_bar)) < 1e-7


# ═══════════════════════════════════════════════════════════
# D. Фабрика передаёт numerics.newton_cell_tol
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("value", [1e-8, 1e-6, None])
def test_factory_passes_cell_tol(value):
    """Порог конфига доходит до модели прототипа; null — условие выключено."""
    cfg = load_config(RS300)
    cfg.numerics.newton_cell_tol = value
    sim, _ = SimulatorFactory.from_config(cfg)
    assert sim._hydro._model.cell_tol == value
