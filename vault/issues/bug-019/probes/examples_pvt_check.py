"""BUG-019, вариант В: какие штатные примеры получат предупреждение о несогласованной PVT.

Условие (A3) Peszyńska 2006 / Coats 1999: c_o,sat = (B_g·dR_s/dp − dB_o/dp)/B_o ≥ 0 на
насыщенной кривой — то, что ECLIPSE проверяет при загрузке («Negative Compressibility
Found», предупреждение, расчёт продолжается) в 30 равноотстоящих точках диапазона таблицы.

Для каждого examples/*/config.json: PVT собирается той же функцией фабрики, что в
расчёте (_create_pvt); диапазон давлений — от наименьшего забойного давления
истории (p_wf, при управлении дебитом — min_bhp) до p_b(R_s0): выше насыщенных
состояний в задаче нет. Проверка — в 30 точках (как ECLIPSE) и на мелкой сетке
(2000 точек), чтобы видеть, не пропускают ли 30 точек узкую зону.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\examples_pvt_check.py
"""

import numpy as np

import common as c
from gpn_multiphase_solver.factory import _create_pvt
from gpn_multiphase_solver.io.config import load_config


def c_o_sat_si(pvt, p, rel=1e-6):
    """(B_g·dR_s/dp − dB_o/dp)/B_o на насыщенной кривой, 1/Па; центральная разность, h = rel·p."""
    h = rel * p
    rs_p, rs_m = pvt.Rs_eq(p + h), pvt.Rs_eq(p - h)
    drs = (rs_p - rs_m) / (2 * h)
    dbo = (pvt.Bo(p + h, rs_p) - pvt.Bo(p - h, rs_m)) / (2 * h)
    return (pvt.Bg(p) * drs - dbo) / pvt.Bo(p, pvt.Rs_eq(p))


def c_g_si(pvt, p, rel=1e-6):
    h = rel * p
    return -(pvt.Bg(p + h) - pvt.Bg(p - h)) / (2 * h) / pvt.Bg(p)


print(f"{'пример':<28} {'PVT':<9} {'R_s0':>6} {'p_low, бар':>10} {'p_b(R_s0)':>10} "
      f"{'min c_o,sat (30 т.)':>20} {'min (2000 т.)':>14} {'c_o,sat<0 при p, бар':>24} {'c_g<0':>6}")
for cfg_path in sorted((c.SOLVER / "examples").glob("*/config.json")):
    cfg = load_config(cfg_path)
    pvt = _create_pvt(cfg)
    ic = cfg.initial_conditions
    lows = [h.p_wf if h.control == "pressure" else h.min_bhp for h in cfg.time.history]
    p_low = float(min(lows))
    p_high = float(pvt.pb(np.array([ic.Rs0]))[0])
    name = cfg_path.parent.name
    if p_high <= p_low:
        print(f"{name:<28} {cfg.pvt.model:<9} {ic.Rs0:6.1f} {p_low / 1e5:10.2f} {p_high / 1e5:10.2f} "
              f"{'насыщенных состояний нет':>20}")
        continue
    p30 = np.linspace(p_low, p_high, 30)
    pf = np.linspace(p_low, p_high, 2000)
    co30, cof = c_o_sat_si(pvt, p30), c_o_sat_si(pvt, pf)
    cg = c_g_si(pvt, pf)
    neg = pf[cof < 0]
    rng = f"{neg.min() / 1e5:.1f}…{neg.max() / 1e5:.1f}" if neg.size else "—"
    print(f"{name:<28} {cfg.pvt.model:<9} {ic.Rs0:6.1f} {p_low / 1e5:10.2f} {p_high / 1e5:10.2f} "
          f"{co30.min() * 1e5:+20.3e} {cof.min() * 1e5:+14.3e} {rng:>24} {int(np.sum(cg < 0)):6d}")
print("\nc_o,sat — в 1/бар; c_g<0 — число точек мелкой сетки, где B_g растёт с давлением")
