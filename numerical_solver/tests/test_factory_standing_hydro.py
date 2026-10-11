"""Тесты Factory с pvt.model='standing' → PrototypeHydroAdapter (FEAT-014).

После FEAT-014 Factory всегда создаёт PrototypeHydroAdapter,
в том числе для аналитических корреляций (Standing).
Проверяем: адаптер создаётся, pipeline работает, ОФП согласованы.
"""

import logging
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import (
    SimulatorFactory, _get_or_create_proto_pvt, _get_or_create_proto_rp, _create_pvt,
)
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.pvt.hydro_to_blackoil_adapter import HydroPVTtoBlackOilAdapter
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.units import BAR_TO_PA
from radial_blackoil.relperm import TabulatedRelPerm


BASELINE = Path(__file__).parent.parent / "configs" / "baseline.json"
TABLE_PVT = Path(__file__).parent.parent / "configs" / "table_pvt" / "config.json"
EXAMPLE_03 = (Path(__file__).parent.parent / "examples"
              / "03_standing_corey" / "config.json")

# baseline.json параметры: p0=20e6, p_wf=15e6, Rs0=50
# pb(Rs0=50) ≈ 9.43 МПа < p_wf → нет разгазирования → однофазный
P0 = 20e6
P_WF = 15e6
R_WELL = 0.1
R_EXT = 50.0


# ═══════════════════════════════════════════════════════════
# A. Factory создаёт PrototypeHydroAdapter для Standing
# ═══════════════════════════════════════════════════════════

class TestFactoryStandingHydro:
    """Factory с pvt.model='standing' → PrototypeHydroAdapter."""

    def test_standing_creates_prototype_hydro(self):
        """HydroSolver = PrototypeHydroAdapter при pvt.model='standing'."""
        config = load_config(BASELINE)
        simulator, _ = SimulatorFactory.from_config(config)
        assert isinstance(simulator._hydro, PrototypeHydroAdapter)

    def test_standing_pvt_shared(self):
        """Стендинг: прототипу — адаптер над тем же StandingFullPVT, что у энергии (DEBT-006)."""
        simulator, _ = SimulatorFactory.from_config(load_config(BASELINE))
        model_pvt = simulator._hydro._model.pvt
        assert isinstance(model_pvt, HydroPVTtoBlackOilAdapter)
        # Поле адаптера читает тест, а не фабрика: это проверка тождества,
        # а не выбор ветки
        assert model_pvt._hydro is simulator._pvt
        assert simulator._hydro._pvt is simulator._pvt
        assert simulator._energy._pvt is simulator._pvt

    def test_standing_pipeline_runs(self):
        """baseline.json → Factory → run → history содержит данные."""
        config = load_config(BASELINE)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        assert history.n_saved > 1
        # Финальное давление < начального (добыча идёт)
        assert history.states[-1].p[0] < P0

    def test_standing_well_rate_positive(self):
        """Дебит нефти > 0 при добыче."""
        config = load_config(BASELINE)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)
        assert history.well_data[-1].q_o_std > 0

    def test_standing_dupuit_pressure(self):
        """Профиль давления = лог-профиль Дюпюи в центрах ячеек (однофазный).

        baseline.json, последний p_wf = 10e6. Центры LogRadialGrid — те же,
        что у прототипа (DEBT-063); в них отклонение от Дюпюи — до округления
        (замер DEBT-063: 6.7e-16). Прежние rtol=1e-2 и «нестационарное
        решение» объясняли расхождение 1.03e-4 — разницу точек сравнения.
        """
        config = load_config(BASELINE)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        r = simulator._grid.r_centers
        p_wf_last = config.time.history[-1].p_wf  # 10e6 Па
        p_exact = p_wf_last + (P0 - p_wf_last) * np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
        np.testing.assert_allclose(
            history.states[-1].p, p_exact, rtol=1e-12)

    def test_beal_reaches_pvt(self):
        """pvt.mu_o_undersaturated = "beal" доходит до StandingFullPVT (FEAT-027).

        PVT baseline.json: 850 / 0.85 / 350 К / Rs0 = 50, p_b = 9.43 МПа.
        При p = 20 МПа вязкость по Билу выше Беггса–Робинсона в 1.095309 раза
        (проба vault/issues/feat-027/probes/val001_beal.py, μ(p_e)/μ_ob).
        """
        config = load_config(BASELINE)
        config.pvt.mu_o_undersaturated = "beal"
        pvt = _create_pvt(config)
        p, Rs = np.array([20e6]), np.array([50.0])
        ratio = pvt.mu_o(p, Rs)[0] / pvt._mu_o_beggs(Rs)[0]
        assert ratio == pytest.approx(1.095309, rel=1e-6)

    def test_beal_with_table_raises(self):
        """Опция Била при табличном PVT — ValueError (FEAT-027).

        У таблицы вязкость выше p_b задают её недонасыщенные ветви; молча
        проигнорировать опцию нельзя — пользователь ждал бы эффекта.
        """
        config = load_config(TABLE_PVT)
        config.pvt.mu_o_undersaturated = "beal"
        with pytest.raises(ValueError, match="mu_o_undersaturated"):
            _create_pvt(config)


class TestStandingDeepDrawdownDenseGrid:
    """Сценарий DEBT-007: пример 03, N = 75, p_wf = 6 МПа на всех интервалах.

    До BUG-014 первый шаг (20 → 6 МПа) требовал ровно 9 удвоений: исходный
    Newton прототипа отвергал пробные точки с S_g < −0.05, и шаг дробился.
    DEBT-007 объяснял это нелинейностью B_g(p) Стендинга — объяснение
    неполное. После BUG-014 первый шаг сходится без дробления: запасной
    путь advance (без нижней границы S_g) проходит шаг, на котором исходный
    Newton отказывал. Тест «при max_retries = 8 падает» поэтому удалён.

    Класс остаётся регрессионной привязкой результата. Умолчание
    numerics.max_retries = 9 — запас, а не порог: ни этот сценарий, ни
    пример 03 при глубокой депрессии (не больше 4 удвоений, замер DEBT-041)
    его не требуют. Обоснование значения — комментарий
    NumericsConfig.max_retries (gpn_multiphase_solver/io/config.py).
    """

    def _config(self):
        """Пример 03 с обоими отягчающими факторами."""
        config = load_config(EXAMPLE_03)
        config.grid.N = 75                      # фактор 1: сгущение сетки
        # Фактор 2: глубокая депрессия. Задаётся ВСЕМ интервалам истории:
        # после DEBT-013 их 72, и правка одного лишь history[0] применила
        # бы депрессию только к первому часу — молча, без исключения.
        for h in config.time.history:
            h.p_wf = 6e6
        return config

    def test_converges_at_default_limit(self):
        """При штатном max_retries = 9 расчёт проходит без правки dt."""
        simulator, initial = SimulatorFactory.from_config(self._config())
        history = simulator.run(initial)
        state = history.states[-1]

        # Результат бит-в-бит устойчив по лимиту (mr = 9, 10, 12 дают одно
        # и то же), поэтому фиксируем жёстко — это регрессионная привязка,
        # а не проверка «примерно сошлось».
        assert state.p[0] == pytest.approx(6.126106e6, rel=1e-4)

        # Сценарий обязан быть двухфазным: p_wf = 6 МПа ниже p_b = 9.43 МПа,
        # газ выделяется. Без этого тест проверял бы однофазный режим,
        # где лимит дробления ни при чём.
        assert state.Sg.max() == pytest.approx(0.0996, rel=1e-2)

        # Расчёт дошёл до конца истории, а не оборвался раньше
        assert history.n_saved == 73


# ═══════════════════════════════════════════════════════════
# B. CoreyRP → TabulatedRelPerm
# ═══════════════════════════════════════════════════════════

class TestCoreyToTabulated:
    """CoreyRP → TabulatedRelPerm через _get_or_create_proto_rp."""

    def test_kro_matches(self):
        """Табулированная kro ≈ CoreyRP.kro на тестовых точках."""
        corey = CoreyRP(S_or=0.2, S_gc=0.05, n_o=2.0, n_g=2.0)
        proto_rp = _get_or_create_proto_rp(corey)

        Sg_test = np.array([0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
        # np.interp на 101 точке — ошибка интерполяции < 1e-4
        np.testing.assert_allclose(
            proto_rp.kro(Sg_test), corey.kro(Sg_test), atol=1e-4)

    def test_krg_matches(self):
        """Табулированная krg ≈ CoreyRP.krg на тестовых точках."""
        corey = CoreyRP(S_or=0.2, S_gc=0.05, n_o=2.0, n_g=2.0)
        proto_rp = _get_or_create_proto_rp(corey)

        Sg_test = np.array([0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
        np.testing.assert_allclose(
            proto_rp.krg(Sg_test), corey.krg(Sg_test), atol=1e-4)


class TestBranchByClass:
    """Ветку фабрики выбирает класс объекта, а не имена его приватных полей (DEBT-006).

    До DEBT-006 фабрика проверяла hasattr(pvt, '_hydro') и hasattr(relperm,
    '_rp'): любой объект с полями таких имён уходил в ветку «извлечь объект
    прототипа», а переименование поля в обёртке — в ветку «обернуть или
    протабулировать». Обе ошибки молчаливые. Здесь объектам Стендинга и Кори
    подставлены посторонние поля с «нужными» именами — ветка не должна
    измениться.
    """

    def test_pvt_branch_ignores_private_field_names(self):
        """StandingFullPVT с посторонним _hydro._pvt по-прежнему оборачивается адаптером."""
        pvt = _create_pvt(load_config(BASELINE))
        pvt._hydro = SimpleNamespace(_pvt="посторонний объект")
        proto = _get_or_create_proto_pvt(pvt, P0)
        assert isinstance(proto, HydroPVTtoBlackOilAdapter)

    def test_rp_branch_ignores_private_field_names(self):
        """CoreyRP с посторонним _rp по-прежнему табулируется на 101 узле."""
        corey = CoreyRP(S_or=0.2, S_gc=0.05, n_o=2.0, n_g=2.0)
        corey._rp = "посторонний объект"
        proto = _get_or_create_proto_rp(corey)
        assert isinstance(proto, TabulatedRelPerm)
        assert proto.sg.size == 101


# ═══════════════════════════════════════════════════════════
# Начальное состояние против корреляции (BUG-017)
# ═══════════════════════════════════════════════════════════

class TestStandingInitialState:
    """Пересыщенный старт отвергается и для Стендинга; без таблиц — без предупреждений."""

    def test_supersaturated_start_raises(self):
        """Rs0 = 80, p0 = 10 МПа < p_b(80) = 14.0 МПа — ошибка.

        Без проверки первый шаг молча поднимал давление до 13.78 МПа за час
        (замер плана BUG-017, §1.2).
        """
        config = load_config(BASELINE)
        config.initial_conditions.Rs0 = 80.0
        config.initial_conditions.p0 = 10e6
        with pytest.raises(ValueError, match="пересыщено"):
            SimulatorFactory.from_config(config)

    def test_p0_1pa_below_pb_passes(self):
        """p0 = p_b(50) − 1 Па: избыток ~6e-6 < 1e-5 — допустимо (округление ввода)."""
        config = load_config(BASELINE)
        simulator, _ = SimulatorFactory.from_config(config)
        pb = float(simulator._pvt.pb(np.array([50.0]))[0])
        config.initial_conditions.p0 = pb - 1.0
        SimulatorFactory.from_config(config)

    def test_dead_oil_passes(self):
        """Rs0 = 0: p_b(0) = −0.176 МПа < 0 — допустимо при любом p0 (примеры 01, 02)."""
        config = load_config(BASELINE)
        config.initial_conditions.Rs0 = 0.0
        SimulatorFactory.from_config(config)

    def test_no_range_warnings(self, caplog):
        """Путь Стендинга не зовёт pvt_range_warnings (у адаптера нет газовой таблицы gp)."""
        config = load_config(BASELINE)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            SimulatorFactory.from_config(config)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
