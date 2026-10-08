"""Накопление интегралов потоков компонентов для баланса массы (DEBT-039).

Схема гидродинамики консервативна: невязки eq:residual_oil, eq:residual_gas
(problem_statement.tex) — изменение запаса компонента в ячейке плюс разность
потоков через её грани. Сумма по ячейкам и шагам сворачивается к забою и
контуру:

    ΔM_α(t) + ∫G_α[N] dt − ∫G_α[0] dt = 0,   α = нефть, газ (м³ст).

Потоки через забой и контур надо интегрировать по ВСЕМ принятым шагам: по
записям истории их не восстановить (довод DEBT-013 для баланса энергии). Здесь
— только сумматор; интегралы шага по внутренним подшагам решателя приходят в
HydroResult.int_G_* (у адаптера прототипа подшаг один — DEBT-015; дробит шаг
Simulator, и интегралы копятся здесь по принятым подшагам). Запас M_α —
функция состояния, его не копят: на каждой записи его отдаёт решатель
(HydroSolver.component_inventories), с теми же φ, B_o, B_g, что в невязке.

Невязка — уровень допуска Ньютона, а не округлений, как у баланса энергии:
проверяется не физика, а всё между невязкой Ньютона и историей (допуск,
накопленный по шагам; знаки потоков адаптера; учёт дробления шага). Сборка
невязки, график и печать — examples/mass_balance.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import HydroResult


# Ключи снимка: запас компонентов на момент записи и интегралы потоков
# через забой и контур от t = 0, м³ст.
MASS_KEYS = ("M_o", "M_g", "cum_o_well", "cum_o_ext", "cum_g_well", "cum_g_ext")


class MassBalanceAccumulator:
    """Интегралы потоков компонентов по принятым шагам. Ур. (eq:residual_oil), (eq:residual_gas)."""

    def __init__(self) -> None:
        # ∫G[0] dt и ∫G[N] dt от t = 0, м³ст. Знак — как у G (> 0 от
        # скважины): при добыче cum_*_well < 0, при притоке с контура
        # cum_*_ext < 0.
        self.cum_o_well = 0.0
        self.cum_o_ext = 0.0
        self.cum_g_well = 0.0
        self.cum_g_ext = 0.0

    def add_step(self, hydro_result: HydroResult) -> None:
        """Добавить интегралы потоков принятого шага. Ур. (eq:residual_oil), (eq:residual_gas)."""
        hr = hydro_result
        ints = (hr.int_G_o_well, hr.int_G_o_ext, hr.int_G_g_well, hr.int_G_g_ext)
        # Проверка до накопления: прерванный вызов не оставляет сумматор
        # частично обновлённым. Сюда приходят только решатели, отдавшие
        # запас (Simulator.run): запас без интегралов — несогласованный
        # решатель, баланс по dt·G последнего подшага был бы ложным.
        if None in ints:
            raise RuntimeError(
                "HydroResult без интегралов потоков int_G_*: решатель отдаёт "
                "запас компонентов, но не интегралы — баланс массы не замкнуть "
                "(DEBT-039)")
        self.cum_o_well += hr.int_G_o_well
        self.cum_o_ext += hr.int_G_o_ext
        self.cum_g_well += hr.int_G_g_well
        self.cum_g_ext += hr.int_G_g_ext

    def snapshot(self, inventories: tuple[float, float]) -> dict:
        """Снимок для SimulationHistory: запас на записи и накопленные интегралы, м³ст."""
        M_o, M_g = inventories
        return {"M_o": M_o, "M_g": M_g,
                "cum_o_well": self.cum_o_well, "cum_o_ext": self.cum_o_ext,
                "cum_g_well": self.cum_g_well, "cum_g_ext": self.cum_g_ext}
