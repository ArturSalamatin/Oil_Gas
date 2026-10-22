"""ЧЕРНОВИК функции numerical_solver/gpn_multiphase_solver/factory.py для плана BUG-019 (шаг 4).

В реальном коде импорты — относительные: from .pvt.consistency import (...);
user_log уже импортирован в factory.py (строка 27). Проверяется плагином
plan_impl_plugin.py до реализации.
"""

import numpy as np

from gpn_multiphase_solver.log import user_log
from gpn_multiphase_solver.pvt.consistency import (
    gas_compressibility, negative_intervals,
    saturated_oil_compressibility, undersaturated_oil_compressibility,
)


def _warn_negative_compressibility(config, pvt) -> None:
    """Предупредить о c < 0 нефти или газа (BUG-019). Ур. (eq:c_ot) problem_statement.tex."""
    # Условия (A2)-(A3) Peszyńska 2006 (Coats 1999, SPE 49774): при
    # отрицательной сжимаемости коэффициент C_p уравнения давления
    # (eq:Cp, eq:c_ot problem_statement.tex) в части ячеек меньше нуля, и
    # задача некорректна: якобиан шага вырождается на последовательности Δt,
    # шаг не сходится или результат зависит от шага. Как в ECLIPSE («Negative
    # Compressibility Found») — предупреждение, расчёт продолжается.
    # Конфиг BUG-019 (прежний пример 20: Стендинг, R_s0 = 500): c_ot < 0 при
    # p > 34.55 МПа.
    ic = config.initial_conditions
    # Нижняя граница — наименьшее забойное давление истории: при добыче
    # давление в пласте ниже него не опускается. При управлении дебитом
    # p_wf не задано — берём min_bhp (обязателен при control='rate', FEAT-020).
    p_lo = min(h.p_wf if h.control == "pressure" else h.min_bhp
               for h in config.time.history)
    p_b = float(pvt.pb(np.array([ic.Rs0]))[0])
    checks = []
    # Насыщенные состояния (нефть + свободный газ) — только при p <= p_b(Rs0):
    # растворённого газа больше Rs0 в задаче нет (закачки нет). Rs0 = 0 —
    # дегазированная нефть, свободного газа не бывает.
    if ic.Rs0 > 0.0 and p_b > p_lo:
        checks.append((
            "насыщенной нефти с выделяющимся газом c_ot = (B_g·dR_s/dp − dB_o/dp)/B_o",
            lambda p: saturated_oil_compressibility(pvt, p), p_lo, p_b))
        checks.append((
            "газа c_g = −(1/B_g)·dB_g/dp",
            lambda p: gas_compressibility(pvt, p), p_lo, p_b))
    # Недонасыщенная нефть с R_s = Rs0 — от p_b(Rs0) (или p_lo, если оно выше)
    # до p0: при добыче давление выше начального не поднимается.
    p_u = max(p_b, p_lo)
    if ic.p0 > p_u:
        checks.append((
            f"недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p при R_s = {ic.Rs0:g}",
            lambda p: undersaturated_oil_compressibility(pvt, p, ic.Rs0), p_u, ic.p0))
    for name, c_of_p, lo, hi in checks:
        for p1, p2, c_min in negative_intervals(c_of_p, lo, hi):
            user_log.warning(
                f"PVT несогласована: отрицательная сжимаемость {name} при p от "
                f"{p1 / 1e6:.4g} до {p2 / 1e6:.4g} МПа (min {c_min:.3g} 1/Па). "
                f"Коэффициент уравнения давления C_p может стать отрицательным "
                f"(problem_statement.tex, eq:c_ot): возможны отказы шага и "
                f"зависимость результата от шага по времени. Расчёт продолжается.")
