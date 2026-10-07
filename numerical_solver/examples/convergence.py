"""Прогон серии по параметру — общая механика проверок по Δt и по сетке.

ЧТО ЗДЕСЬ ОБЩЕЕ, А ЧТО НЕТ. Проверки на серии устроены одинаково:
прогнать задачу на ряде значений параметра (Δt или N) и на каждом
измерить метрику. Отличаются они ЭТАЛОНОМ, с которым сравнивается
расчёт, и тем, что делается с серией:

  energy_balance_convergence  — уровень невязки баланса энергии по Δt
  04a/grid_convergence        — дебит против GOR-замыкания по N,
                                отношения ошибок соседних сеток

Эталон — это физика конкретного примера, и выносить его нельзя: он и есть
предмет проверки. Поэтому здесь только прогон серии: настройка конфига и
метрика приходят аргументами-функциями, а обработка серии (порядок,
уровень, отношения ошибок) остаётся у вызывающего скрипта.

Скрипты сходимости 01/spatial_convergence, 04/grid_convergence и
05/closed_form_convergence прогоняют серию сами и этот модуль не
импортируют.

Модуль библиотечный: своего __main__ у него нет, потому что запускать
«сходимость вообще» бессмысленно — нужен пример и его эталон. Запускаются
скрипты примеров, которые этот модуль используют.
"""

import sys
from pathlib import Path
from copy import deepcopy
from typing import Callable

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES),
           str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def run_series(config_base, values, apply: Callable, measure: Callable,
               log_level: str = "WARNING") -> list[dict]:
    """Прогнать задачу на серии значений параметра и измерить ошибку.

    apply(config, value)          — выставить параметр в копии конфига
    measure(sim, history, config) — вернуть метрику (float) или dict с ней

    Возвращает список dict по одному на значение; в каждом есть ключ
    "value", плюс всё, что вернул measure (если dict) либо ключ "error".

    Конфиг копируется deepcopy: серия прогонов не должна портить базовый
    объект, иначе второй вызов run_series получит уже изменённые параметры.
    """
    from gpn_multiphase_solver.factory import SimulatorFactory

    results = []
    for value in values:
        config = deepcopy(config_base)
        apply(config, value)
        config.output.log_level = log_level

        sim, initial_state = SimulatorFactory.from_config(config)
        history = sim.run(initial_state)

        measured = measure(sim, history, config)
        row = dict(measured) if isinstance(measured, dict) else {
            "error": float(measured)}
        row["value"] = value
        results.append(row)
    return results
