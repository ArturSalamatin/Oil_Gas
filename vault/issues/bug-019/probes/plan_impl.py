"""BUG-019, план (вариант В): проверка кода шагов до реализации.

1. Черновик pvt/consistency.py (consistency_draft.py) и функции фабрики
   _warn_negative_compressibility (здесь — warn_draft) на всех штатных примерах,
   конфигах тестов и замороженном сценарии BUG-019: кто получает предупреждение.
2. Синтетические таблицы: насыщенная нефть с завышенным ростом B_o (граница
   нарушения известна аналитически — 11.944 МПа) и газ с ростом B_g на 10–15 МПа.
3. Стендинг (PVT примера 20): c_ot по разностям против аналитических производных
   формул standing.py; корень c_ot.
4. Время проверки.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\plan_impl.py
"""

import json
import shutil
import time

import numpy as np
from scipy.optimize import brentq

import common as c
import consistency_draft as cons
from gpn_multiphase_solver.factory import _create_pvt
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.units import (PSI_TO_PA, SCF_PER_M3, RHO_AIR_STD,
                                         RHO_WATER_STD, P_STD, T_STD)


def warn_draft(config, pvt):
    """Черновик factory._warn_negative_compressibility: список сообщений вместо user_log.warning."""
    ic = config.initial_conditions
    p_lo = min(h.p_wf if h.control == "pressure" else h.min_bhp for h in config.time.history)
    p_b = float(pvt.pb(np.array([ic.Rs0]))[0])
    checks = []
    if ic.Rs0 > 0.0 and p_b > p_lo:
        checks.append(("насыщенной нефти с выделяющимся газом c_ot = (B_g·dR_s/dp − dB_o/dp)/B_o",
                       lambda p: cons.saturated_oil_compressibility(pvt, p), p_lo, p_b))
        checks.append(("газа c_g = −(1/B_g)·dB_g/dp",
                       lambda p: cons.gas_compressibility(pvt, p), p_lo, p_b))
    p_u = max(p_b, p_lo)
    if ic.p0 > p_u:
        checks.append((f"недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p при R_s = {ic.Rs0:g}",
                       lambda p: cons.undersaturated_oil_compressibility(pvt, p, ic.Rs0), p_u, ic.p0))
    msgs = []
    for name, func, lo, hi in checks:
        for p1, p2, cmin in cons.negative_intervals(func, lo, hi):
            msgs.append(f"PVT несогласована: отрицательная сжимаемость {name} при p от "
                        f"{p1 / 1e6:.4g} до {p2 / 1e6:.4g} МПа (min {cmin:.3g} 1/Па)")
    return msgs, (p_lo, p_b, p_u)


# ═════════════ 1. Конфиги ═════════════
paths = sorted((c.SOLVER / "examples").glob("*/config.json")) + [
    c.SOLVER / "configs" / "baseline.json",
    c.SOLVER / "configs" / "table_pvt" / "config.json",
    c.SOLVER / "tests" / "data" / "bug018_rs500" / "config.json",
    c.SOLVER / "tests" / "data" / "bug016_example14" / "config.json",
    c.FROZEN / "config.json",
]
print("═══ 1. Предупреждения на конфигах ═══")
for path in paths:
    if not path.exists():
        print(f"  нет файла: {path}")
        continue
    cfg = load_config(path)
    pvt = _create_pvt(cfg)
    t0 = time.perf_counter()
    msgs, (p_lo, p_b, p_u) = warn_draft(cfg, pvt)
    ms = (time.perf_counter() - t0) * 1e3
    rel = path.relative_to(c.SOLVER.parent)
    print(f"  {str(rel):<70} p_lo {p_lo / 1e6:6.3f}, p_b {p_b / 1e6:7.3f}, p0 {cfg.initial_conditions.p0 / 1e6:6.2f} МПа; "
          f"{ms:6.1f} мс; предупреждений {len(msgs)}")
    for m in msgs:
        print(f"      {m}")

# ═════════════ 2. Синтетические таблицы ═════════════
print("\n═══ 2. Синтетические таблицы (configs/table_pvt, p_wf = 5 МПа) ═══")
SRC = c.SOLVER / "configs" / "table_pvt"
SYN = c.HERE / "synthetic"
SYN.mkdir(exist_ok=True)
OIL_BAD = ("Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
           "30.0,15000000,1.40,0.0015\n30.0,30000000,1.38,0.0016\n")
GAS_BAD = ("pressure_Pa,Bg,mu_g_Pa_s\n5000000,0.020,0.000012\n10000000,0.012,0.000013\n"
           "15000000,0.013,0.000014\n30000000,0.004,0.000018\n")
for name, oil, gas in (("oil_bad", OIL_BAD, None), ("gas_bad", None, GAS_BAD), ("ok", None, None)):
    d = SYN / name
    d.mkdir(exist_ok=True)
    for f in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        shutil.copy(SRC / f, d / f)
    if oil:
        (d / "oil_pvt.csv").write_text(oil, encoding="utf-8")
    if gas:
        (d / "gas_pvt.csv").write_text(gas, encoding="utf-8")
    cfg = load_config(SRC / "config.json")
    cfg.config_dir = d
    for h in cfg.time.history:
        h.p_wf = 5e6
    pvt = _create_pvt(cfg)
    msgs, _ = warn_draft(cfg, pvt)
    print(f"  {name}: предупреждений {len(msgs)}")
    for m in msgs:
        print(f"      {m}")
# Аналитика для oil_bad: dR_s/dp = 30/1e7, dB_o/dp = 0.35/1e7, B_g = 0.020 − 1.2e-9·(p − 5e6)
p_star = 5e6 + (0.020 - (0.35 / 1e7) / (30 / 1e7)) / 1.2e-9
print(f"  аналитическая граница oil_bad: {p_star / 1e6:.6f} МПа")

# ═════════════ 3. Стендинг: разности против аналитики ═════════════
print("\n═══ 3. Стендинг, PVT примера 20 ═══")
pvt20 = StandingFullPVT(rho_o_std=800.0, rho_g_std=1.014, T0=380.0, Rs0=500.0)
g_g = 1.014 / RHO_AIR_STD
g_o = 800.0 / RHO_WATER_STD
api = 141.5 / g_o - 131.5
T_F = (380.0 - 273.15) * 9 / 5 + 32
a = 0.00091 * T_F - 0.0125 * api


def c_ot_exact(p):
    """Аналитические производные формул standing.py (co_undersaturated = 0)."""
    Y = p / PSI_TO_PA / 18.2 + 1.4
    rs = g_g * Y ** (1 / 0.83) * 10.0 ** (-a / 0.83) / SCF_PER_M3
    drs = rs / 0.83 / (18.2 * Y) / PSI_TO_PA
    F = rs * SCF_PER_M3 * (g_g / g_o) ** 0.5 + 1.25 * T_F
    bo = 0.9759 + 1.2e-4 * F ** 1.2
    dbo = 1.2e-4 * 1.2 * F ** 0.2 * SCF_PER_M3 * (g_g / g_o) ** 0.5 * drs
    bg = P_STD * 380.0 / (T_STD * p)
    return (bg * drs - dbo) / bo


p_t = np.array([5e6, 10e6, 20e6, 30e6, 34e6, 40e6, 46e6])
fd, ex = cons.saturated_oil_compressibility(pvt20, p_t), c_ot_exact(p_t)
for pp, a1, a2 in zip(p_t, fd, ex):
    print(f"  p = {pp / 1e6:5.1f} МПа: разности {a1:+.6e}, аналитика {a2:+.6e}, отн. разница {abs(a1 - a2) / abs(a2):.1e}")
root_fd = brentq(lambda q: cons.saturated_oil_compressibility(pvt20, np.array([q]))[0], 30e6, 40e6)
root_ex = brentq(lambda q: c_ot_exact(q), 30e6, 40e6)
print(f"  корень c_ot: по разностям {root_fd / 1e6:.6f} МПа, аналитически {root_ex / 1e6:.6f} МПа")
print(f"  c_g при 40 МПа: {cons.gas_compressibility(pvt20, np.array([40e6]))[0]:.6e}, 1/p = {1 / 40e6:.6e}")
