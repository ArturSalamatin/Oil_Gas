"""Свойства флюидов (PVT) и относительные фазовые проницаемости (ОФП).

Модули
------
- ``base`` — базовые классы: ``HydroPVT`` (свойства фаз), ``FullPVT``
  (с тепловыми свойствами), ``DifferentiableHydroPVT``, ``RelPermModel``,
  ``DifferentiableRelPerm``;
- ``standing`` — ``StandingFullPVT``: корреляции Стендинга и др.;
- ``table_full`` — ``TableFullPVT``: таблицы CSV через прототип;
- ``relperm`` — ``CoreyRP``: модель Кори;
- ``prototype_adapter`` — таблицы PVT и ОФП прототипа в интерфейсах пакета;
- ``hydro_to_blackoil_adapter`` — PVT пакета в интерфейсе прототипа (для
  корреляций);
- ``consistency`` — проверка согласованности PVT: сжимаемости нефти и газа
  неотрицательны (иначе — предупреждение).
"""

from .base import (
    HydroPVT, FullPVT, DifferentiableHydroPVT,
    RelPermModel, DifferentiableRelPerm,
)
from .standing import StandingFullPVT
from .relperm import CoreyRP
from .prototype_adapter import PrototypePVTAdapter, PrototypeRPAdapter
from .hydro_to_blackoil_adapter import HydroPVTtoBlackOilAdapter
from .table_full import TableFullPVT
