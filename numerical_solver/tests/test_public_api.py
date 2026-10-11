"""Публичный интерфейс пакета для диагностики расчёта (DEBT-011).

Решатель с примерами передаётся заказчику: примеры — образец работы с
библиотекой, и всё, что они вызывают, становится интерфейсом. Здесь —
объекты задачи у Simulator, функции сборки фабрики, ряды балансов,
рисунки проверок и страж независимости пакета от examples/.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402,F401
import numpy as np  # noqa: E402
import pytest  # noqa: E402,F401

import gpn_multiphase_solver.factory as factory  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory, create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypeRPAdapter  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from gpn_multiphase_solver.simulator import Simulator  # noqa: E402

SOLVER_ROOT = Path(__file__).resolve().parent.parent
BASELINE = SOLVER_ROOT / "configs" / "baseline.json"                 # Стендинг + Кори
TABLE_CONFIG = SOLVER_ROOT / "configs" / "table_pvt" / "config.json"  # таблицы PVT и ОФП


# ── Фабрика ──────────────────────────────────────────────────

def test_factory_builders_public_without_aliases():
    """Сборка PVT и ОФП по конфигу — публичные create_pvt, create_relperm.

    Приватных имён не осталось (решение пользователя: без псевдонимов —
    два имени одной функции расходятся при следующей правке).
    """
    assert callable(factory.create_pvt) and callable(factory.create_relperm)
    assert not hasattr(factory, "_create_pvt")
    assert not hasattr(factory, "_create_relperm")


# ── Объекты задачи у Simulator ───────────────────────────────

def test_simulator_objects_table():
    """Табличный случай: сетка и PVT — объекты решателя энергии, ОФП — обёртка таблицы модели.

    Тождество (is), а не равенство: диагностика обязана видеть ровно то,
    что считало задачу. Приватные поля здесь — белый ящик, ради проверки
    связки фабрики.
    """
    sim, _ = SimulatorFactory.from_config(load_config(TABLE_CONFIG))
    assert sim.grid is sim._energy._grid
    assert sim.pvt is sim._energy._pvt
    assert isinstance(sim.relperm, PrototypeRPAdapter)
    # Модель прототипа получила ту же TabulatedRelPerm (DEBT-006, BUG-018)
    assert sim._hydro._model.relperm is sim.relperm.proto_rp


def test_simulator_objects_corey():
    """Кори: ОФП — CoreyRP с параметрами конфига; кривые совпадают с create_relperm побитово."""
    cfg = load_config(BASELINE)
    sim, _ = SimulatorFactory.from_config(cfg)
    assert sim.pvt is sim._energy._pvt
    assert isinstance(sim.relperm, CoreyRP)
    S = np.linspace(0.0, 1.0, 11)
    ref = create_relperm(cfg)
    np.testing.assert_array_equal(sim.relperm.kro(S), ref.kro(S))
    np.testing.assert_array_equal(sim.relperm.krg(S), ref.krg(S))


def test_simulator_relperm_none_without_argument():
    """Simulator без ОФП (так его строят тестовые двойники) отдаёт relperm = None."""
    sim = Simulator(grid=None, hydro=None, energy=None, pvt=None, schedule=None)
    assert sim.relperm is None
