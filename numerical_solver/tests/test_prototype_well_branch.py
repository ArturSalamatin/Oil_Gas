"""BUG-014: запасной путь RadialBlackOilModel.advance при скачке p_wf вверх.

Прототип (radial_blackoil), фикстура Nabor_1b (p_e = 200 бар, p_b = 180 бар),
12 ячеек. Скважина «только добыча»: q = WI·λ·max(p[0] − p_wf, 0).

Исходный алгоритм advance выбирает ветку скважины («открыта» / «закрыта») по
текущей итерации Ньютона и отвергает пробные точки с S_g < −0.05 в двухфазных
ячейках. Когда p_wf поднимают выше p[0] на длинном шаге, он не сходится: на
первой итерации ветка «закрыта», а на ней согласованного решения нет; газ у
забоя растворяется, и пробные точки уходят за границу S_g.

Правка (вариант F плана): advance сначала решает шаг исходным алгоритмом; только
при отказе — запасной путь: ветка фиксирована на всё решение и проверяется после
сходимости (старт — по состоянию на начало шага, при неудаче — другая ветка, не
более двух решений), нижняя граница S_g снята (метод отрицательных насыщенностей).

Модель Nabor_1b строится напрямую: пакет tests прототипа (helpers.py)
импортировать нельзя — у проекта свой пакет tests.

План: vault/plans/bug-014 well-shutin-active-set.md, шаг 1.
"""

from pathlib import Path

import numpy as np
import pytest

from radial_blackoil.blackoil import BlackOilNewtonReport, RadialBlackOilModel
from radial_blackoil.grid import RadialGrid
from radial_blackoil.input_reader import load_input
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.state import BlackOilState


# ── Параметры ────────────────────────────────────────────────

PROTO_ROOT = Path(__file__).parent.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
NABOR_1B = PROTO_ROOT / "tests" / "fixtures" / "Nabor_1b.xlsx"

N_CELLS = 12
P_INIT_BAR = 200.0         # начальное давление, выше p_b = 180 бар — газа нет
BHP_DRAWDOWN_BAR = 100.0   # p_wf отбора
DT_DRAWDOWN_S = 300.0
N_DRAWDOWN = 12            # 12 × 300 с = 1 ч отбора

SG_BOUND_DEFAULT = -0.05   # граница S_g исходного поиска по направлению
ORIGINAL = (None, SG_BOUND_DEFAULT)   # ключ исходного вызова: ветка не задана, граница −0.05


# ── Хелперы ──────────────────────────────────────────────────

def _build(bhp_bar):
    """Свежая модель Nabor_1b с p_wf = bhp_bar и начальное состояние без газа."""
    inp = load_input(NABOR_1B)
    p = inp.params
    grid = RadialGrid(float(p["Well radius rw"]), float(p["Outer radius re"]),
                      float(p["Formation thickness h"]), N_CELLS,
                      float(p["Absolute permeability"]))
    rock = CompressibleRock(float(p["Reference porosity"]), float(p["Reference pressure"]),
                            float(p["Rock compressibility cr"]))
    model = RadialBlackOilModel(grid, rock, inp.pvt, inp.relperm, bhp_bar,
                                float(p["Outer-boundary pressure"]),
                                float(p["Initial dissolved gas Rs"]),
                                skin=float(p["Well skin"]), linear_solver="sparse")
    state = BlackOilState.undersaturated(grid.n, P_INIT_BAR, float(p["Initial dissolved gas Rs"]))
    return model, state


def _model(bhp_bar):
    """Свежая модель Nabor_1b с p_wf = bhp_bar."""
    return _build(bhp_bar)[0]


def _fields(rep):
    """Поля отчёта BUG-014: (converged, well_branch, well_switches, fallback)."""
    return (rep.converged, rep.well_branch, rep.well_switches, rep.fallback)


def _assert_restored(model):
    """Вне advance атрибуты запасного пути — по умолчанию (прежнее поведение)."""
    assert model._well_branch is None
    assert model._sg_lower_bound == SG_BOUND_DEFAULT


def _assert_physical_sg(state):
    """Принятое состояние физично: 0 <= S_g < 1, у однофазных ячеек S_g = 0 ровно.

    В запасном пути нижней границы S_g в поиске по направлению нет — итерации
    Ньютона уходят в S_g < 0. Физичность ответа обеспечивает цикл набора фаз
    (_advance_phases): ячейка с S_g < −1e-9 переводится в однофазный режим и шаг
    решается заново; остаток из [−1e-9, 0) обнуляется.
    """
    assert state.sg.min() >= 0.0
    assert state.sg.max() < 1.0
    assert np.all(state.sg[~state.gas_active] == 0.0)


def _install_fake_phases(model, plan):
    """Подменить model._advance_phases: ответ по ключу (ветка, граница) в момент вызова.

    plan[key] — (converged, p0_bar): копия state_old с p[0] = p0_bar и отчёт
    BlackOilNewtonReport(converged, 3, 0.0); или "raise" — RuntimeError.
    Возвращает список ключей вызовов (заполняется по мере вызовов).
    """
    calls = []

    def fake(state_old, dt_s, max_active_iter, max_newton):
        key = (model._well_branch, model._sg_lower_bound)
        calls.append(key)
        answer = plan[key]
        if answer == "raise":
            raise RuntimeError("искусственный отказ")
        converged, p0_bar = answer
        new = state_old.copy()
        new.pressure_bar[0] = p0_bar
        return new, BlackOilNewtonReport(converged, 3, 0.0)

    model._advance_phases = fake
    return calls


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def drawn_down():
    """Состояние после 1 ч отбора при p_wf = 100 бар (12 × 300 с).

    Замер: p[0] = 111.672 бар, S_g[0] = 0.0672, у забоя 5 двухфазных ячеек —
    газ выделился. Исходный алгоритм на отборе сходится, запасной путь не нужен.
    """
    model, state = _build(BHP_DRAWDOWN_BAR)
    for _ in range(N_DRAWDOWN):
        state, rep = model.advance(state, DT_DRAWDOWN_S)
        assert rep.converged
    assert state.pressure_bar[0] == pytest.approx(111.672, abs=1e-3)
    assert int(np.count_nonzero(state.gas_active)) == 5
    return state


# ═══════════════════════════════════════════════════════════
# A. Скачок p_wf на реальном Ньютоне (тесты 1–4, 7)
# ═══════════════════════════════════════════════════════════

class TestAdvanceUpstep:
    def test_long_upstep_reopens_well(self, drawn_down):
        # p_wf 100 → 150 бар при p[0] = 111.7 бар, шаг 1 ч. За час приток с контура
        # (200 бар) поднимает p[0] выше 150 бар — согласованный ответ: скважина
        # открыта, добыча идёт при p[0] >= p_wf.
        # Исходный алгоритм: на первой итерации p[0] < p_wf → ветка «закрыта», на ней
        # решения нет — отказ. Запасной путь стартует с «закрыта» (по старому
        # состоянию), она не согласуется → «открыта»: одна смена ветки.
        model = _model(150.0)
        new, rep = model.advance(drawn_down, 3600.0)
        assert _fields(rep) == (True, "open", 1, True)
        assert new.pressure_bar[0] >= 150.0               # замер 152.605 бар
        assert model.well_rates(new)["oil_sm3_s"] > 0.0   # добыча, замер 2.14e-5 ст.м³/с
        _assert_physical_sg(new)
        _assert_restored(model)

    def test_long_upstep_near_reservoir_stays_shut(self, drawn_down):
        # p_wf 100 → 195 бар — почти пластовое. За час p[0] растёт (111.7 → 170.7 бар),
        # но до 195 не доходит: скважина закрыта всё время, q = 0.
        # Исходный алгоритм не сходится (газ у забоя растворяется, пробные точки
        # с S_g < −0.05 отвергаются); запасной путь сходится на стартовой ветке «закрыта».
        model = _model(195.0)
        new, rep = model.advance(drawn_down, 3600.0)
        assert _fields(rep) == (True, "shut", 0, True)
        p0 = new.pressure_bar[0]
        assert 111.672 < p0 <= 195.0                      # замер 170.743 бар
        assert model.well_rates(new)["oil_sm3_s"] == 0.0
        _assert_physical_sg(new)
        _assert_restored(model)

    def test_short_upstep_original_path(self, drawn_down):
        # Тот же скачок до 195 бар, но шаг 60 с: исходный алгоритм справляется сам,
        # запасной путь не запускается (fallback = False) — ответ побитово прежний.
        # Ветка в отчёте — по принятому состоянию: p[0] <= p_wf → «закрыта».
        model = _model(195.0)
        new, rep = model.advance(drawn_down, 60.0)
        assert _fields(rep) == (True, "shut", 0, False)
        assert new.pressure_bar[0] <= 195.0               # замер 122.297 бар
        assert model.well_rates(new)["oil_sm3_s"] == 0.0
        _assert_restored(model)

    def test_downstep_original_path(self, drawn_down):
        # p_wf 100 → 105 бар — ниже p[0] = 111.7 бар: скважина продолжает добывать.
        # Обычный шаг: исходный алгоритм сходится, запасной путь не нужен.
        model = _model(105.0)
        new, rep = model.advance(drawn_down, 3600.0)
        assert _fields(rep) == (True, "open", 0, False)
        assert model.well_rates(new)["oil_sm3_s"] > 0.0   # замер 6.43e-5 ст.м³/с
        _assert_restored(model)

    def test_rate_control_original_path(self):
        # Управление по дебиту нефти 2 ст.м³/сут (нижняя граница p_wf = 100 бар),
        # шаг 60 с из начального состояния — как test_rate_control.py прототипа.
        # Ветки «открыта / закрыта» по давлению здесь нет: well_branch = "".
        # Ловит: правка не задевает режим управления по дебиту.
        model, state = _build(150.0)
        model.set_oil_rate_control(2.0, 100.0)
        new, rep = model.advance(state, 60.0)
        assert _fields(rep) == (True, "", 0, False)
        assert model.well_rates(new)["oil_sm3_s"] * 86400.0 == pytest.approx(2.0, rel=1e-10)
        _assert_restored(model)


# ═══════════════════════════════════════════════════════════
# B. Инварианты запасного пути (тесты 5, 6a, 6b)
# ═══════════════════════════════════════════════════════════

class TestFallbackInvariants:
    @pytest.mark.parametrize("bhp_bar", [150.0, 195.0])
    def test_mass_balance_after_fallback(self, drawn_down, bhp_bar):
        # Шаг, решённый запасным путём (тесты 1 и 2), сохраняет массу каждого
        # компонента: изменение запаса + dt·(поток через скважину и контур) = 0.
        # Отрицательная S_g допускается только на промежуточных итерациях; принятое
        # состояние решает те же уравнения баланса. Замер: ~1e-16 от запаса.
        dt = 3600.0
        model = _model(bhp_bar)
        new, rep = model.advance(drawn_down, dt)
        assert rep.converged and rep.fallback
        err_oil, err_gas = model.step_global_balance(drawn_down, new, dt)
        inv_oil, inv_gas = model.component_inventories(drawn_down)
        assert abs(err_oil) / inv_oil.sum() <= 1e-12
        assert abs(err_gas) / inv_gas.sum() <= 1e-12

    @pytest.mark.parametrize("bhp_bar", [150.0, 195.0])
    def test_negative_iterates_not_accepted(self, drawn_down, bhp_bar):
        # Где живёт отрицательная S_g. В запасном пути итерации Ньютона уходят за
        # снятую границу −0.05 (замер: до −0.447 в обоих случаях) — это гладкое
        # продолжение уравнений ячейки. В принятое состояние S_g < 0 не попадает:
        # ячейки, где газ растворился, цикл набора фаз переводит в однофазный
        # режим и решает шаг заново (двухфазных 5 → 4 при 150 бар, 5 → 3 при 195).
        # Итерации перехватываются на экземпляре: finite_difference_jacobian
        # вызывается на каждой итерации Ньютона с текущей точкой z.
        model = _model(bhp_bar)
        n = model.grid.n
        iter_min = []
        jacobian = model.finite_difference_jacobian

        def recording(z, state_old, dt_s, gas_active, *args, **kwargs):
            x = np.asarray(z)[n:][np.asarray(gas_active, bool)]   # S_g двухфазных ячеек
            if x.size:
                iter_min.append(float(x.min()))
            return jacobian(z, state_old, dt_s, gas_active, *args, **kwargs)

        model.finite_difference_jacobian = recording
        new, rep = model.advance(drawn_down, 3600.0)
        assert rep.converged and rep.fallback
        # Граница действительно пересекалась — иначе тест ничего не проверяет
        assert min(iter_min) < SG_BOUND_DEFAULT
        # Газ растворился хотя бы в одной ячейке: она стала однофазной
        assert rep.phase_switches >= 1
        assert np.count_nonzero(new.gas_active) < np.count_nonzero(drawn_down.gas_active)
        _assert_physical_sg(new)

    def test_exception_in_original_call(self, drawn_down):
        # Исключение в исходном вызове пробрасывается наружу; атрибуты запасного
        # пути к этому моменту не менялись. После — прежний выбор ветки вне advance:
        # p[0] = 111.7 < p_wf = 195 бар → скважина закрыта, bhp = p[0], дебит 0.
        model = _model(195.0)
        _install_fake_phases(model, {ORIGINAL: "raise"})
        with pytest.raises(RuntimeError):
            model.advance(drawn_down, 60.0)
        _assert_restored(model)
        rates = model.well_rates(drawn_down)
        assert rates["oil_sm3_s"] == 0.0
        assert rates["bhp_bar"] == pytest.approx(drawn_down.pressure_bar[0], abs=1e-12)

    def test_exception_in_fallback(self, drawn_down):
        # Исходный вызов — отказ; в запасном пути (ветка «закрыта», граница снята) —
        # исключение. try/finally должен вернуть атрибуты по умолчанию, иначе
        # следующие вызовы well_rates и advance работали бы с зафиксированной
        # веткой и без границы S_g.
        model = _model(195.0)
        _install_fake_phases(model, {ORIGINAL: (False, 0.0), ("shut", None): "raise"})
        with pytest.raises(RuntimeError):
            model.advance(drawn_down, 60.0)
        _assert_restored(model)
        rates = model.well_rates(drawn_down)
        assert rates["oil_sm3_s"] == 0.0
        assert rates["bhp_bar"] == pytest.approx(drawn_down.pressure_bar[0], abs=1e-12)


# ═══════════════════════════════════════════════════════════
# C. Проверка пробной точки поиска по направлению (тесты 8, 9)
# ═══════════════════════════════════════════════════════════

class TestTrialBounds:
    def test_sg_lower_bound_attribute(self, drawn_down):
        # Нижняя граница S_g двухфазной ячейки — атрибут _sg_lower_bound.
        # По умолчанию −0.05: S_g = −0.3 отвергается (исходный алгоритм).
        # None (запасной путь): S_g = −0.3 допустима — гладкое продолжение уравнений
        # ячейки. Верхняя граница 0.98 остаётся в силе.
        model = _model(BHP_DRAWDOWN_BAR)
        mask = drawn_down.gas_active.copy()
        n = model.grid.n
        j = int(np.nonzero(mask)[0][0])        # первая двухфазная ячейка
        z = model.pack(drawn_down, mask)
        trial = z.copy()
        trial[n + j] = -0.3
        assert model._trial_is_reasonable(trial, mask) is False
        model._sg_lower_bound = None
        assert model._trial_is_reasonable(trial, mask) is True
        trial_high = z.copy()
        trial_high[n + j] = 0.99
        assert model._trial_is_reasonable(trial_high, mask) is False

    def test_other_bounds_kept(self, drawn_down):
        # Прочие проверки пробной точки правка не трогает: давление <= 1 бар,
        # нечисловое значение, отрицательное R_s однофазной ячейки — отвергаются.
        # Охранный тест: зелёный и до, и после правки.
        model = _model(BHP_DRAWDOWN_BAR)
        mask = drawn_down.gas_active.copy()
        n = model.grid.n
        k = int(np.nonzero(~mask)[0][0])       # первая однофазная ячейка
        z = model.pack(drawn_down, mask)
        low_p = z.copy()
        low_p[0] = 0.5
        not_finite = z.copy()
        not_finite[1] = np.nan
        negative_rs = z.copy()
        negative_rs[n + k] = -1e-6
        assert model._trial_is_reasonable(low_p, mask) is False
        assert model._trial_is_reasonable(not_finite, mask) is False
        assert model._trial_is_reasonable(negative_rs, mask) is False


# ═══════════════════════════════════════════════════════════
# D. Управляющая логика advance без Ньютона (тесты 12a–f)
# ═══════════════════════════════════════════════════════════

class TestAdvanceBranchLogic:
    """_advance_phases подменён: ответ задаётся по ключу (ветка, граница) вызова.

    Модель p_wf = 150 бар, state_old = drawn_down: p[0] = 111.7 < 150 → запасной
    путь стартует с «закрыта». Проверяются порядок вызовов и поля отчёта.
    """

    def test_fallback_second_branch(self, drawn_down):
        # Исходный — отказ; «закрыта» — отказ Ньютона; «открыта» — сошлась,
        # p[0] = 151 >= 150 — согласована. Одна смена ветки.
        model = _model(150.0)
        calls = _install_fake_phases(model, {
            ORIGINAL: (False, 0.0), ("shut", None): (False, 0.0), ("open", None): (True, 151.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIGINAL, ("shut", None), ("open", None)]
        assert _fields(rep) == (True, "open", 1, True)
        _assert_restored(model)

    def test_all_fail(self, drawn_down):
        # Отказ везде: после двух веток запасной путь сдаётся; третья ступень
        # (BUG-016) повторяет его с ||F||_2 и ограничителем dS_g — тоже отказ.
        # converged = False — адаптер раздробит шаг, как раньше.
        model = _model(150.0)
        calls = _install_fake_phases(model, {
            ORIGINAL: (False, 0.0), ("shut", None): (False, 0.0), ("open", None): (False, 0.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIGINAL, ("shut", None), ("open", None), ("shut", None), ("open", None)]
        assert _fields(rep) == (False, "open", 1, True)
        _assert_restored(model)

    def test_both_branches_inconsistent(self, drawn_down):
        # Обе ветки сходятся, но несогласованы: «закрыта» с p[0] = 160 > p_wf
        # (должна была добывать), «открыта» с p[0] = 140 < p_wf (закачка).
        # Не более двух решений — без зацикливания; converged = False.
        # Третья ступень (BUG-016) повторяет обе ветки — снова несогласованы.
        model = _model(150.0)
        calls = _install_fake_phases(model, {
            ORIGINAL: (False, 0.0), ("shut", None): (True, 160.0), ("open", None): (True, 140.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIGINAL, ("shut", None), ("open", None), ("shut", None), ("open", None)]
        assert _fields(rep) == (False, "open", 1, True)
        _assert_restored(model)

    def test_fallback_start_from_old_state(self, drawn_down):
        # p_wf = 105 < p[0] = 111.7 бар: запасной путь стартует с «открыта»
        # (по состоянию на начало шага) и на ней же сходится — без смены ветки.
        model = _model(105.0)
        calls = _install_fake_phases(model, {ORIGINAL: (False, 0.0), ("open", None): (True, 110.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIGINAL, ("open", None)]
        assert _fields(rep) == (True, "open", 0, True)
        _assert_restored(model)

    def test_original_converged_no_fallback(self, drawn_down):
        # Исходный алгоритм сошёлся — запасного пути нет, один вызов.
        # Ветка в отчёте — по принятому состоянию: p[0] = 151 > 150 → «открыта».
        model = _model(150.0)
        calls = _install_fake_phases(model, {ORIGINAL: (True, 151.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIGINAL]
        assert _fields(rep) == (True, "open", 0, False)
        _assert_restored(model)

    def test_rate_control_fallback_without_branch(self):
        # Управление по дебиту: запасной путь — повтор без границы S_g, ветка по
        # давлению не фиксируется (ключ (None, None)), well_branch = "".
        model, state = _build(150.0)
        model.set_oil_rate_control(2.0, 100.0)
        calls = _install_fake_phases(model, {ORIGINAL: (False, 0.0), (None, None): (True, 190.0)})
        _, rep = model.advance(state, 60.0)
        assert calls == [ORIGINAL, (None, None)]
        assert _fields(rep) == (True, "", 0, True)
        _assert_restored(model)
