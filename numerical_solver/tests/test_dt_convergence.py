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

# Пример 07: mu_JT = 0, L_degas = 0 — источник в энергии один, адиабатический
# член; тепло переносят конвекция и теплопроводность (lambda = 1.5 / 0.14 /
# 0.04 с DEBT-023; её вклад в ошибки этого теста — ниже четвёртого знака,
# замер DEBT-023). Табличный PVT: на нём проявлялся
# BUG-010 — при dt = 1200, 720, 450, 400 с гидродинамика дробила шаг,
# а энергия шла одним шагом, и ошибка выбивалась из тренда в 6–24 раза.
# Замер DEBT-053 (2026-10-10, vault/issues/debt-053/probes/): сейчас шаг
# примера 07 не дробится ни при одном dt из DT_LIST, поэтому здесь
# проверяется только сходимость T по dt. Сам механизм (энергия идёт по
# подшагам гидродинамики) проверяют test_simulator.py
# (test_energy_steps_match_hydro_substeps, двойник) и
# test_energy_matrix_examples.py (test_energy_substeps_preserve_total_time,
# пример 10).
CONFIG = (Path(__file__).parent.parent / "examples"
          / "07_degassing_adiabatic_only" / "config.json")

DT_REF = 50.0          # эталон: 72 подшага на интервал 3600 с
DT_LIST = [1800.0, 1200.0, 900.0, 720.0, 600.0, 450.0, 400.0, 360.0]


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


# ── FEAT-039: нарастающий шаг на пуске скважины ──
# Пример 20: пуск из равновесия 33 МПа на p_wf = 5 МПа (PVT Стендинга, N = 350),
# первая запись – через 3600 с. Предел равномерного сгущения T(r_w) первой
# записи – 367.4061 К: первый шаг 3600/2**15 = 0.11 с, каждая ступень удвоения
# поделена на 2**j равных шагов, j = 0…5; разности соседних j убывают вдвое
# (0.055, 0.028, 0.014, 0.0073, 0.0037 К), предел – Ричардсон при q = 1 по
# j = 4, 5 (vault/issues/feat-039/probes/octave.out.txt). У примера 04a ошибка
# больше (0.54 К), но давление на пуске уходит ниже таблицы PVT – свойства по
# крайней точке, для проверки схемы по времени такая постановка хуже.
CONFIG_20 = (Path(__file__).parent.parent / "examples"
             / "20_rs300_cooling" / "config.json")
T_LIM_START_20 = 367.4061


def _first_record_20(h0) -> float:
    """T(r_w) первой записи примера 20 (первый интервал, 3600 с) при time.dt_after_control_change = h0."""
    cfg = load_config(CONFIG_20)
    cfg.time.history = cfg.time.history[:1]
    cfg.time.dt_after_control_change = h0
    simulator, initial_state = SimulatorFactory.from_config(cfg)
    return float(simulator.run(initial_state).states[-1].T[0])


@pytest.fixture(scope="module")
def start_20() -> dict:
    """Первая запись пуска полным шагом и с нарастанием от 0.11 с (~3 с)."""
    return {h0: _first_record_20(h0) for h0 in (None, 0.11)}


class TestRampOnProductionStart:
    """FEAT-039: нарастающий шаг на пуске уменьшает ошибку T(r_w) первой записи втрое с лишним.

    Пуск из равновесия – резкая смена режима, как останов, а схема первого
    порядка по времени. Одним шагом 3600 с T(r_w) через час на 0.392 К выше
    предела (охлаждение от выделения газа за час занижено), с подшагов от
    0.11 с с удвоением – на 0.112 К. Остаток – крупные подшаги конца часа
    (900, 1800 с): одна ступень удвоения на октаву, как у останова (BUG-026).
    """

    def test_one_step_error_at_start(self, start_20):
        """Без нарастания T(r_w) через 1 ч выше предела на 0.392 К – исходная ошибка FEAT-039."""
        assert start_20[None] - T_LIM_START_20 == pytest.approx(0.3924, abs=2e-3)

    def test_ramp_reduces_start_error(self, start_20):
        """С h0 = 0.11 с: T(r_w) = 367.5186 К (+0.112 от предела); ошибка < 0.35 прежней.

        Ловит: нарастание не доходит до первого интервала (T как без поля,
        ошибка 0.392 К), неверную последовательность подшагов (числа другие).
        """
        T = start_20[0.11]
        assert T == pytest.approx(367.5186, abs=2e-3)
        assert T - T_LIM_START_20 < 0.35 * (start_20[None] - T_LIM_START_20)
