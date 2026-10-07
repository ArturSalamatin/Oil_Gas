"""Баланс массы компонентов (DEBT-039): контракты, накопитель, Simulator, укороченные примеры.

Схема гидродинамики консервативна: невязки eq:residual_oil, eq:residual_gas —
изменение запаса в ячейке плюс разность потоков через грани; их сумма по
ячейкам и шагам сворачивается к забою и контуру:
ΔM + ∫G[N] dt − ∫G[0] dt = 0. Накопленная невязка проверяет не физику, а то,
что стоит между невязкой Ньютона и историей: допуск Ньютона, учёт дробления
шага, знаки потоков адаптера.

Конфиги примеров укорочены (6 ч или 2 + 2 ч, N = 25) — тесты идут доли секунды.
"""

from dataclasses import replace

import numpy as np

from gpn_multiphase_solver.simulator import Simulator

from .test_simulator import _initial_state, _make_simulator, _single_interval_schedule

# Порог относительной невязки (нормировка — сумма модулей членов). Уровень —
# допуск Ньютона прототипа (rtol = 1e-8 к начальной невязке шага, atol =
# 1e-11 м³ст/с на ячейку), а не округления: замер при планировании — до
# 4.5e-10 на укороченных конфигах здесь, до 2.9e-8 на полных примерах.
# Дефекты, которые ловит проверка, дают 1e-3...1: поток последнего подшага
# вместо интеграла при дроблении — 9e-2 на шаге.
TOL = 1e-6


def _stub_result(**integrals):
    """HydroResult двойника за шаг 3600 с, с заданными интегралами потоков."""
    _, _, hydro, _, _ = _make_simulator()
    bc = _single_interval_schedule().intervals[0].bc
    return replace(hydro.solve(_initial_state(), 3600.0, bc), **integrals)


def _max_rel(bal):
    """Максимум относительной невязки по записям: нефть и газ вместе."""
    return max(float(np.max(bal["rel_residual_o"])),
               float(np.max(bal["rel_residual_g"])))


# ── Контракты ─────────────────────────────────────────────────

class TestContracts:
    def test_hydro_result_integrals_default_none(self):
        """Без интегралов HydroResult строится как прежде: поля — None.

        Шесть мест в тестах и fluxes.py строят HydroResult без новых полей;
        умолчание None — признак «решатель массу не сохраняет».
        """
        r = _stub_result()
        assert (r.int_G_o_well, r.int_G_o_ext,
                r.int_G_g_well, r.int_G_g_ext) == (None, None, None, None)

    def test_solver_inventories_default_none(self):
        """Метод ABC по умолчанию — None: двойник уравнений не решает."""
        _, _, hydro, _, _ = _make_simulator()
        assert hydro.component_inventories(_initial_state()) is None

    def test_stub_history_without_mass_balance(self):
        """На двойнике без запаса снимки баланса массы — None, расчёт идёт."""
        grid, pvt, hydro, energy, _ = _make_simulator()
        sim = Simulator(grid, hydro, energy, pvt,
                        _single_interval_schedule(dt_hist=7200.0, dt_int=3600.0))
        history = sim.run(_initial_state())
        # Один интервал — две записи: начальная и конец интервала
        assert history.mass_balance == [None, None]
