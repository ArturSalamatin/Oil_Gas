"""Тесты Factory с pvt.model='standing' → PrototypeHydroAdapter (FEAT-014).

После FEAT-014 Factory всегда создаёт PrototypeHydroAdapter,
в том числе для аналитических корреляций (Standing).
Проверяем: адаптер создаётся, pipeline работает, ОФП согласованы.
"""

from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import (
    SimulatorFactory, _get_or_create_proto_rp,
)
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.units import BAR_TO_PA


BASELINE = Path(__file__).parent.parent / "configs" / "baseline.json"
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
        """Профиль давления ≈ лог-профиль Дюпюи (однофазный, Newton).

        baseline.json: 2 интервала, последний p_wf=10e6. Newton даёт
        нестационарное решение, rtol=1e-2.
        """
        config = load_config(BASELINE)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        r = simulator._grid.r_centers
        p_wf_last = config.time.history[-1].p_wf  # 10e6 Па
        p_exact = p_wf_last + (P0 - p_wf_last) * np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
        np.testing.assert_allclose(
            history.states[-1].p, p_exact, rtol=1e-2)


class TestStandingDeepDrawdownDenseGrid:
    """Сценарий DEBT-007: два отягчающих фактора сразу.

    У Стендинга B_g(p) — гипербола с d²B_g/dp² ≠ 0, поэтому линейная
    модель Newton неточна и поиск вдоль направления берёт очень малые
    шаги. Сгущение сетки и рост депрессии усиливают это независимо:
    по отдельности (N = 75 при p_wf = 8 МПа, либо p_wf = 6 МПа при
    N = 50) хватает 7 удвоений, вместе — нужно ровно 9.

    Именно этот сценарий обосновывает numerics.max_retries = 9 по
    умолчанию: он воспроизводим на конфиге, уже лежащем в репозитории,
    в отличие от сценария BUG-003 (пример 04a ещё не создан, FEAT-015).
    """

    def _config(self):
        """Пример 03 с обоими отягчающими факторами."""
        config = load_config(EXAMPLE_03)
        config.grid.N = 75                      # фактор 1: сгущение сетки
        config.time.history[0].p_wf = 6e6       # фактор 2: глубокая депрессия
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

    def test_fails_one_below_threshold(self):
        """При max_retries = 8 тот же расчёт падает — порог равен 9.

        Тест фиксирует, что значение по умолчанию не завышено произвольно:
        уменьшение лимита на единицу возвращает отказ. Без этой проверки
        default = 9 выглядел бы догадкой.
        """
        config = self._config()
        config.numerics.max_retries = 8
        simulator, initial = SimulatorFactory.from_config(config)

        with pytest.raises(RuntimeError, match="не сошёлся"):
            simulator.run(initial)


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
