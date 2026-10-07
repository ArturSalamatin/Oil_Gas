"""Проверка согласованности PVT: сжимаемости нефти и газа неотрицательны (BUG-019).

ЧЕРНОВИК модуля numerical_solver/gpn_multiphase_solver/pvt/consistency.py для плана
BUG-019 (вариант В). Проверяется пробой plan_impl.py до реализации.

Условия (A2)–(A3) Peszyńska 2006 (TiPM 63:201) со ссылкой на Coats 1999 (SPE 49774):
при них коэффициент C_p уравнения давления (eq:Cp problem_statement.tex) неотрицателен.
ECLIPSE проверяет то же при загрузке PVT и выдаёт предупреждение «Negative
Compressibility Found»; расчёт продолжается.
"""

import numpy as np

# Число равноотстоящих точек проверки на диапазоне — как в ECLIPSE (30 точек от
# наименьшего до наибольшего давления таблицы; руководство whitson+, «PVT Table»).
N_CHECK = 30

# Относительный шаг центральной разности по давлению. Для формул Стендинга
# погрешность ~h² и округление ~1e-16/h — обе на порядки ниже нарушений
# (−5.6e-9 1/Па у примера 20). На таблицах (кусочно-линейная интерполяция)
# разность точна внутри отрезка; у узла даёт среднее наклонов соседних отрезков.
_REL_STEP = 1e-6

# Делений пополам при уточнении границы интервала: ширина ячейки сетки
# (до ~15 бар) / 2^40 — доли паскаля.
_N_BISECT = 40


def _d_dp(f, p):
    """Центральная разность df/dp с шагом _REL_STEP·p."""
    h = _REL_STEP * p
    return (f(p + h) - f(p - h)) / (2.0 * h)


def saturated_oil_compressibility(pvt, p):
    """c_ot = (B_g·dR_s/dp − dB_o/dp)/B_o, 1/Па. Ур. (eq:c_ot) problem_statement.tex."""
    p = np.asarray(p, float)

    def bo_sat(q):
        return pvt.Bo(q, pvt.Rs_eq(q))

    return (pvt.Bg(p) * _d_dp(pvt.Rs_eq, p) - _d_dp(bo_sat, p)) / bo_sat(p)


def undersaturated_oil_compressibility(pvt, p, Rs):
    """c_o = −(1/B_o)·∂B_o/∂p при R_s = const, 1/Па. Ур. (eq:co_cg) problem_statement.tex."""
    p = np.asarray(p, float)

    def bo(q):
        return pvt.Bo(q, np.full_like(q, Rs))

    return -_d_dp(bo, p) / bo(p)


def gas_compressibility(pvt, p):
    """c_g = −(1/B_g)·dB_g/dp, 1/Па. Ур. (eq:co_cg) problem_statement.tex."""
    p = np.asarray(p, float)
    return -_d_dp(pvt.Bg, p) / pvt.Bg(p)


def negative_intervals(c_of_p, p_lo, p_hi, n=N_CHECK):
    """Интервалы [p1, p2], где c_of_p(p) < 0, с минимумом c: n точек, границы — делением пополам."""
    p = np.linspace(p_lo, p_hi, n)
    neg = c_of_p(p) < 0.0
    out = []
    i = 0
    while i < n:
        if not neg[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and neg[j + 1]:
            j += 1
        p1 = p_lo if i == 0 else _boundary(c_of_p, p[i - 1], p[i])
        p2 = p_hi if j == n - 1 else _boundary(c_of_p, p[j + 1], p[j])
        c_min = float(np.min(c_of_p(np.linspace(p1, p2, n))))
        out.append((float(p1), float(p2), c_min))
        i = j + 1
    return out


def _boundary(c_of_p, p_ok, p_neg):
    """Граница между точкой с c >= 0 (p_ok) и точкой с c < 0 (p_neg) — деление пополам."""
    for _ in range(_N_BISECT):
        mid = 0.5 * (p_ok + p_neg)
        if c_of_p(np.array([mid]))[0] < 0.0:
            p_neg = mid
        else:
            p_ok = mid
    return 0.5 * (p_ok + p_neg)
