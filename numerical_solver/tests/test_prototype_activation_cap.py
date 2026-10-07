"""BUG-018: ограничение начального S_g при переходе ячейки в двухфазный режим.

При переходе в двухфазный режим прототип задаёт ячейке S_g «закрытого сосуда»:
весь газ, выделившийся при падении давления, остаётся в ячейке. Перетоки за шаг
это приближение не учитывает. При высоком R_s0 и глубокой депрессии оно у забоя
выше 1 - S_or (R_s0 = 500, p_wf = 5 МПа: 0.91 при решении 0.41), и из этой
области Ньютон до решения не доходит — шаг не сходится и при 4096 подшагах
(max_retries = 12, замер BUG-018).

Исправление: начальное S_g не выше наибольшего узла таблицы ОФП, где k_ro > 0
(RadialBlackOilModel.sg_activation_cap). Меняется только стартовая точка
Ньютона: уравнения и критерий сходимости прежние, решение то же.

План: vault/plans/bug-018 closed-flash-sg-activation.md.
"""

from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from radial_blackoil.blackoil import BlackOilNewtonReport, _sg_activation_cap
from radial_blackoil.relperm import TabulatedRelPerm
from radial_blackoil.state import BlackOilState

# Замороженный отказной сценарий (FEAT-025, пример 20 до обхода): R_s0 = 500,
# T0 = 380 К, PVT Стендинга, Кори S_gc = 0.1, S_or = 0.2, n_g = 3, N = 50,
# k = 100 мД, p0 = 46.9 МПа (p_b = 46.38), p_wf = 5 МПа, одни сутки. Пример 20
# в репозитории идёт с обходом S_or = 0.05 и может меняться — сценарий отдельно.
BUG018_CASE = Path(__file__).parent / "data" / "bug018_rs500" / "config.json"


def _sim(N=None, retries=None):
    cfg = load_config(BUG018_CASE)
    cfg.output.log_level = "ERROR"
    if N is not None:
        cfg.grid.N = N
    if retries is not None:
        cfg.numerics.max_retries = retries
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    return sim, init, dt


def _first_step(sim, init, dt):
    """Первый шаг истории через адаптер (с дроблением A-retry)."""
    return sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)


# ═══════════════════════════════════════════════════════════
# A. Граница по таблице ОФП
# ═══════════════════════════════════════════════════════════

class TestCapFromTable:
    def test_corey_table_101_nodes(self):
        """Кори на 101 узле (factory._get_or_create_proto_rp), S_or = 0.2: k_ro = 0
        с узла 0.80, наибольший узел с k_ro > 0 — 0.79."""
        sim, _, _ = _sim()
        assert sim._hydro._model.sg_activation_cap == pytest.approx(0.79, abs=1e-12)

    def test_coarse_table(self):
        """Таблица с узлами примера 04 (k_ro = 0 при S_g = 0.8): граница — узел 0.6."""
        rp = TabulatedRelPerm([0.0, 0.1, 0.2, 0.4, 0.6, 0.8],
                              [1.0, 0.8, 0.6, 0.3, 0.1, 0.0],
                              [0.0, 0.0, 0.1, 0.3, 0.6, 0.8])
        assert _sg_activation_cap(rp) == 0.6

    def test_no_immobile_oil_no_cap(self):
        """k_ro > 0 во всей таблице — ограничения нет (None)."""
        rp = TabulatedRelPerm([0.0, 0.5, 1.0], [1.0, 0.5, 0.1], [0.0, 0.3, 0.8])
        assert _sg_activation_cap(rp) is None

    def test_oil_immobile_from_first_node_no_cap(self):
        """k_ro = 0 уже в первом узле — нефть неподвижна всегда, ограничения нет."""
        rp = TabulatedRelPerm([0.0, 1.0], [0.0, 0.0], [0.0, 1.0])
        assert _sg_activation_cap(rp) is None


# ═══════════════════════════════════════════════════════════
# B. Отказной сценарий: первый шаг
# ═══════════════════════════════════════════════════════════

class TestFirstStep:
    @pytest.mark.parametrize("N, sg0, p0_MPa", [
        (50, 0.410017, 5.925090),
        (350, 0.417217, 5.140841),
    ])
    def test_first_step_converges(self, N, sg0, p0_MPa):
        """Первые сутки — одним шагом, без дробления.

        До исправления: RuntimeError после 512 подшагов при N = 50 и 350
        (S_g «закрытого сосуда» у забоя 0.905 / 0.912 > 1 - S_or = 0.8).
        Замер плана (vault/issues/bug-018/probes/freeze_case.py). N = 50 решает
        исходный алгоритм advance, N = 350 — третья ступень (BUG-016).
        """
        sim, init, dt = _sim(N=N)
        res = _first_step(sim, init, dt)
        assert res.n_substeps == 1
        assert res.state.Sg[0] == pytest.approx(sg0, abs=1e-5)
        assert res.state.p[0] == pytest.approx(p0_MPa * 1e6, abs=100.0)

    def test_without_cap_fails(self):
        """Без ограничения сценарий по-прежнему не сходится — он воспроизводит баг.

        Если когда-нибудь этот тест упадёт (шаг сойдётся и без ограничения),
        сценарий перестал проверять BUG-018 — его надо заменить, а не удалять
        проверку. max_retries = 0: без дробления, только три ступени advance.
        """
        sim, init, dt = _sim(retries=0)
        sim._hydro._model.sg_activation_cap = None
        with pytest.raises(RuntimeError):
            _first_step(sim, init, dt)

    def test_guess_capped(self):
        """Начальное S_g двухфазных ячеек в Ньютоне не выше границы и достигает её.

        Достижение границы означает, что «закрытый сосуд» её превышал (0.905) и
        ограничение сработало; превышение — что ограничение не применено.
        """
        sim, init, dt = _sim()
        model = sim._hydro._model
        cap = model.sg_activation_cap
        n = model.grid.n
        starts = []
        orig = model._newton_fixed_active_set

        def newton(z0, state_old, dt_s, gas_active, **kw):
            sg = np.asarray(z0)[n:][gas_active]
            if sg.size:
                starts.append(float(sg.max()))
            return orig(z0, state_old, dt_s, gas_active, **kw)

        model._newton_fixed_active_set = newton
        _first_step(sim, init, dt)
        assert starts, "двухфазных ячеек не было"
        assert max(starts) <= cap
        assert max(starts) == cap

    def test_solution_independent_of_cap(self):
        """Ограничение меняет только стартовую точку, не решение.

        Граница 0.79 (штатная) и 0.3 дают одно решение шага до точности Ньютона.
        Замер плана: max|Δp| = 6.0e-6 Па, max|ΔS_g| = 9.9e-13,
        max|ΔR_s| = 7.5e-11 м³ст/м³ст.
        """
        states = []
        for cap in (0.79, 0.3):
            sim, init, dt = _sim()
            sim._hydro._model.sg_activation_cap = cap
            states.append(_first_step(sim, init, dt).state)
        a, b = states
        assert np.max(np.abs(a.p - b.p)) < 1e-3           # Па, при p ~ 5e6..5e7
        assert np.max(np.abs(a.Sg - b.Sg)) < 1e-9
        assert np.max(np.abs(a.Rs - b.Rs)) < 1e-7


# ═══════════════════════════════════════════════════════════
# C. Сообщение адаптера при отказе
# ═══════════════════════════════════════════════════════════

def test_failure_message_reports_state_not_guess():
    """Текст ошибки сообщает факты (шаг, подшаги, t, двухфазные ячейки, max S_g)
    и не называет причину, которую адаптер не диагностировал.

    Прежний текст советовал увеличить max_retries и называл причину «обе фазы
    малоподвижны одновременно» — в BUG-018 это было неверно и то и другое.
    Начало текста «HydroSolver не сошёлся после N подшагов» сохранено: его
    цитируют README примеров 03, 06, 07, 10.
    """
    sim, init, dt = _sim(retries=1)
    model = sim._hydro._model

    def always_fails(state_old, dt_s, *a, **kw):
        return state_old.copy(), BlackOilNewtonReport(False, 0, 1.0)

    model.advance = always_fails
    with pytest.raises(RuntimeError) as exc:
        _first_step(sim, init, dt)
    msg = str(exc.value)
    assert msg.startswith("HydroSolver не сошёлся после 2 подшагов")
    assert "t = 0.0000 сут" in msg
    assert "двухфазных ячеек 0 из 50" in msg
    assert "малоподвижны" not in msg
    # BUG-020: подшаги A-retry равны — подсказка про dt_integration при смене режима скважины
    assert "time.dt_integration" in msg
