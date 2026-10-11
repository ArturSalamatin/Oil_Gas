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
from gpn_multiphase_solver.energy.balance import (  # noqa: E402
    CUMULATIVE_KEYS, compute_energy_balance)
from gpn_multiphase_solver.factory import SimulatorFactory, create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.mass_balance import compute_mass_balance  # noqa: E402
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypeRPAdapter  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from gpn_multiphase_solver.simulator import Simulator  # noqa: E402
from gpn_multiphase_solver.state import SimulationHistory  # noqa: E402

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


# ── Ряды балансов ────────────────────────────────────────────

def _energy_history():
    """История из двух записей: нулевая и с членами, где ΔE ≠ Σ источников на 0.5 Дж."""
    zero = dict.fromkeys(CUMULATIVE_KEYS, 0.0)
    last = dict(delta_E=5.0, cum_adiab=1.0, cum_conv=2.0, cum_jt=-1.0,
                cum_deg=0.5, cum_cond=2.0)
    return SimulationHistory(times=[0.0, 10.0], balance=[zero, last])


def test_compute_energy_balance_residual_and_scale():
    """Невязка ΔE − Σ, нормировка на сумму модулей всех членов, t = 0 без деления на ноль.

    Σ источников = 1 + 2 − 1 + 0.5 + 2 = 4.5 → невязка 0.5 Дж;
    сумма модулей = 5 + 1 + 2 + 1 + 0.5 + 2 = 11.5.
    """
    bal = compute_energy_balance(_energy_history())
    assert set(bal) == set(CUMULATIVE_KEYS) | {"t", "total", "residual", "rel_residual"}
    assert bal["total"][1] == 4.5 and bal["residual"][1] == 0.5
    assert bal["rel_residual"][1] == pytest.approx(0.5 / 11.5, rel=1e-15)
    assert bal["rel_residual"][0] == 0.0


def test_compute_mass_balance_none_without_inventories():
    """Решатель без запаса компонентов (двойники): баланса массы нет — None, а не ошибка."""
    assert compute_mass_balance(SimulationHistory()) is None
    assert compute_mass_balance(SimulationHistory(mass_balance=[None])) is None


def test_compute_mass_balance_closes():
    """Запас нефти 100 → 90 м³ст, добыто 12, притекло 2: ΔM + ∫G[N] − ∫G[0] = −10 − 2 + 12 = 0.

    Знак G — от скважины (CLAUDE.md, конвенция знаков): добыча даёт
    cum_o_well < 0, приток с контура — cum_o_ext < 0. У газа все члены
    нулевые — нормировка 1, невязка 0.
    """
    snaps = [dict(M_o=100.0, M_g=0.0, cum_o_well=0.0, cum_o_ext=0.0,
                  cum_g_well=0.0, cum_g_ext=0.0),
             dict(M_o=90.0, M_g=0.0, cum_o_well=-12.0, cum_o_ext=-2.0,
                  cum_g_well=0.0, cum_g_ext=0.0)]
    bal = compute_mass_balance(SimulationHistory(times=[0.0, 1.0], mass_balance=snaps))
    assert bal["residual_o"][1] == 0.0 and bal["rel_residual_o"][1] == 0.0
    assert bal["prod_o"][1] == 12.0 and bal["inflow_o"][1] == 2.0
    assert bal["rel_residual_g"][1] == 0.0
