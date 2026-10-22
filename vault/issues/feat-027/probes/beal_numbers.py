"""FEAT-027, проба: эталонные числа Била–Стендинга для unit-тестов плана.

Параметры фикстуры tests/test_pvt.py (rho_o 800, rho_g 0.78, T0 300 К)
и примера 20 (rho_o 800, rho_g 1.014, T0 380 К, Rs0 300). Для сравнения —
Васкес–Беггс (отвергнут: расходится при p_b -> 0).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-027\\probes\\beal_numbers.py
"""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(ROOT))

from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402
from gpn_multiphase_solver.units import PA_TO_PSI  # noqa: E402


def beal_ratio(s, p, Rs):
    """mu_o(p, Rs)/mu_ob(Rs) по Билу–Стендингу (p > p_b)."""
    pb = s.pb(np.array([Rs]))[0]
    mub = s._mu_o_beggs(np.array([Rs]))[0] * 1e3
    dpsi = max(p - pb, 0.0) * PA_TO_PSI
    return (mub + 1e-3 * dpsi * (0.024 * mub ** 1.6 + 0.038 * mub ** 0.56)) / mub


def vb_ratio(s, p, Rs):
    pb = s.pb(np.array([Rs]))[0]
    pp = p * PA_TO_PSI
    m = 2.6 * pp ** 1.187 * np.exp(-11.513 - 8.98e-5 * pp)
    return (p / pb) ** m if pb > 0 else float("nan")


for title, args in (("фикстура test_pvt.py", (800.0, 0.78, 300.0, 50.0, 5e-10)),
                    ("пример 20", (800.0, 1.014, 380.0, 300.0, 3.3e-9))):
    s = StandingFullPVT(*args)
    Rs_star = brentq(lambda R: s.pb(np.array([R]))[0], 1e-6, 300.0)
    print(f"\n== {title}: Rs*(p_b = 0) = {Rs_star:.4f} м3ст/м3ст")
    print("   Rs   p_b,МПа   mu_ob,сП    dmu/dp,сП/МПа   p,МПа   Бил      ВБ")
    for Rs, p in ((0.0, 2e6), (0.0, 33e6), (10.0, 20e6), (30.0, 20e6),
                  (50.0, 20e6), (300.0, 33e6)):
        pb = s.pb(np.array([Rs]))[0]
        mub = s._mu_o_beggs(np.array([Rs]))[0] * 1e3
        # сП/psi · (psi в 1 МПа) = сП/МПа
        slope = 1e-3 * (0.024 * mub ** 1.6 + 0.038 * mub ** 0.56) * (1e6 * PA_TO_PSI)
        print(f"{Rs:6.1f} {pb/1e6:9.4f} {mub:10.6f} {slope:14.6e} {p/1e6:7.2f} "
              f"{beal_ratio(s, p, Rs):.6f} {vb_ratio(s, p, Rs):.6f}")
