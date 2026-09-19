"""Сходимость решения T по шагу интегрирования dt (BUG-010).

Зачем отдельный файл. В наборе проверок была сходимость по СЕТКЕ и
замыкание баланса энергии, но не было сходимости самого решения T по dt.
Баланс к ошибке расщепления нечувствителен принципиально: он проверяет
тождественность дискретных уравнений, а не точность (см. заметку
«невязка баланса энергии не есть ошибка расщепления»). Поэтому BUG-010 —
скачок T на 0.48 К при отдельных dt — жил незамеченным: невязка
замыкалась в обоих режимах, и ни один тест не смотрел на саму T.

Проверяемое свойство: ошибка T против мелкого эталона обязана убывать
МОНОТОННО по dt. Любой механизм, тихо меняющий режим расчёта при
отдельных значениях dt, ломает монотонность — независимо от того,
какова его природа.
"""

import copy
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

# Пример 07: mu_JT = 0, L_degas = 0, lambda = 0 — в энергии работают
# только конвекция и адиабатический член. Табличный PVT: именно на нём
# A-retry срабатывает и проявлялся BUG-010.
CONFIG = (Path(__file__).parent.parent / "examples"
          / "07_degassing_adiabatic_only" / "config.json")

DT_REF = 50.0          # эталон: 72 подшага на интервал 3600 с
DT_LIST = [1800.0, 1200.0, 900.0, 720.0, 600.0, 450.0, 400.0, 360.0]

# Аномальные до фикса dt (n_sub = 3, 5, 8, 9 — там срабатывает A-retry).
# Именно они выбивались из тренда в 6–24 раза.
DT_WITH_RETRY = [1200.0, 720.0, 450.0, 400.0]


def _run_first_interval(dt_integration: float) -> np.ndarray:
    """Первый интервал истории при заданном dt_integration -> T [N].

    Только первый интервал: ошибка вносится на нём (резкое приложение
    депрессии 20 -> 8 МПа), дальше монотонно релаксирует.
    """
    cfg = copy.deepcopy(load_config(CONFIG))
    cfg.time.dt_integration = float(dt_integration)
    cfg.time.history = cfg.time.history[:1]
    simulator, initial_state = SimulatorFactory.from_config(cfg)
    history = simulator.run(initial_state)
    return np.asarray(history.states[-1].T, float)


@pytest.fixture(scope="module")
def errors() -> dict[float, float]:
    """max|T(dt) - T(dt_ref)| для каждого dt из DT_LIST."""
    T_ref = _run_first_interval(DT_REF)
    return {dt: float(np.max(np.abs(_run_first_interval(dt) - T_ref)))
            for dt in DT_LIST}


class TestTemperatureConvergenceInDt:
    def test_temperature_converges_monotonically_in_dt(self, errors):
        """Ошибка T убывает монотонно при измельчении dt.

        До BUG-010 при dt = 1200, 720, 450, 400 с ошибка подскакивала до
        ~0.48 К — в 6–24 раза выше тренда O(dt), — тогда как соседние шаги
        давали 2–6e-02 К. Немонотонность и есть подпись дефекта: результат
        не должен зависеть от dt скачком.

        Сравниваем соседние по убыванию dt с запасом 1.5: небольшие
        локальные всплески допустимы (метод первого порядка, эталон не
        точное решение), кратные — нет.
        """
        ordered = sorted(errors, reverse=True)        # 1800 -> 360
        for dt_coarse, dt_fine in zip(ordered, ordered[1:]):
            assert errors[dt_fine] <= 1.5 * errors[dt_coarse], (
                f"Ошибка выросла при измельчении шага: "
                f"dt={dt_coarse:g} с -> {errors[dt_coarse]:.4e} К, "
                f"dt={dt_fine:g} с -> {errors[dt_fine]:.4e} К")

    def test_no_dt_deviates_from_linear_trend(self, errors):
        """Ни один dt не выбивается из линейного тренда O(dt).

        Схема первого порядка по времени: ошибка ~ C*dt. Нормируем тренд
        по самому крупному шагу и требуем, чтобы отношение не превышало 2.
        До фикса аномальные шаги давали 5.7, 9.4, 15.0 и 16.6.
        """
        dt_max = max(errors)
        err_max = errors[dt_max]
        for dt, err in sorted(errors.items(), reverse=True):
            expected = err_max * dt / dt_max
            ratio = err / expected
            assert ratio <= 2.0, (
                f"dt={dt:g} с выбивается из тренда O(dt): "
                f"ошибка {err:.4e} К при ожидаемой ~{expected:.4e} К "
                f"(отношение {ratio:.1f})")

    def test_retry_steps_match_their_neighbours(self, errors):
        """Шаги с A-retry не хуже соседних без него.

        Прямая проверка механизма BUG-010: при dt из DT_WITH_RETRY
        гидродинамика дробит шаг, и раньше энергия этого не делала.
        Теперь дробление синхронно, поэтому такие шаги обязаны давать
        ошибку того же порядка, что соседи, а не на порядок большую.
        """
        ordered = sorted(errors, reverse=True)
        for dt in DT_WITH_RETRY:
            i = ordered.index(dt)
            neighbours = [errors[ordered[j]]
                          for j in (i - 1, i + 1) if 0 <= j < len(ordered)]
            assert errors[dt] <= 2.0 * max(neighbours), (
                f"Шаг с A-retry dt={dt:g} с даёт {errors[dt]:.4e} К "
                f"против соседних {neighbours} — дробление энергии "
                f"не сработало")
