"""Baseline для векторизации циклов в energy/tridiag.py (DEBT-017).

Не тест в обычном смысле: одноразовая утилита сравнения «до/после».
Запуск через pytest, потому что conftest настраивает путь к внешнему
прототипу radial_blackoil (нужен табличному PVT примеров 07-11).

Порядок применения (переменная окружения, чтобы не править общий conftest):
  1. до правки:  BASELINE_WRITE=1 pytest tests/baseline_vectorization_check.py
  2. после:      pytest tests/baseline_vectorization_check.py
Второй прогон требует ПОБИТОВОГО совпадения: векторизация меняет только
порядок обхода граней, но не арифметику в каждой грани, поэтому любое
отличие в последнем бите означает изменение смысла, а не шум суммирования.
"""

import os
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
BASELINE_FILE = Path(__file__).parent / "baseline_vectorization_T.npz"

# Примеры, где работают все три векторизуемых цикла: дегазация (Q_deg,
# конвективный перенос Rs), JT и свободный газ на гранях. Однофазные 01-02
# не нагружают газовую ветку, поэтому здесь не нужны.
CASES = [
    "07_degassing_adiabatic_only",
    "08_degassing_jt",
    "09_degassing_latent_heat",
    "10_deep_degassing",
    "11_degassing_at_boundary",
]


def _run(example: str) -> np.ndarray:
    """Прогнать пример, вернуть поле T последнего состояния."""
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)
    result = simulator.run(initial)
    return np.asarray(result.states[-1].T, dtype=float)


def test_temperature_bitwise_identical():
    """Поле T побитово совпадает с записанным baseline.

    При BASELINE_WRITE=1 вместо сверки записывает эталон.
    """
    write = os.environ.get("BASELINE_WRITE") == "1"

    # Проверка ДО прогона примеров: он занимает ~12 с, тратить их, чтобы
    # затем сообщить об отсутствии эталона, незачем.
    if not write and not BASELINE_FILE.exists():
        # Пропуск, а не падение: файл эталона локальный (в .gitignore),
        # привязан к конкретному дереву и в свежем клоне его нет. Красный
        # тест на чистом клоне означал бы поломку набора, а не дефект кода.
        pytest.skip(f"нет baseline ({BASELINE_FILE.name}); "
                    f"снять эталон: BASELINE_WRITE=1 pytest {Path(__file__).name}")

    fields = {name: _run(name) for name in CASES}

    if write:
        np.savez(BASELINE_FILE, **fields)
        pytest.skip(f"baseline записан: {BASELINE_FILE}")

    ref = np.load(BASELINE_FILE)

    for name in CASES:
        got, want = fields[name], ref[name]
        # Побитово: array_equal, не allclose. Обоснование в шапке модуля.
        assert np.array_equal(got, want), (
            f"{name}: поле T изменилось; "
            f"макс. |Δ| = {np.max(np.abs(got - want)):.3e}")
