"""FEAT-024: данные примера 14 из конфига примера 12.

Меняется (решения пользователя 2026-09-30):
  - initial_conditions.Rs0 = 150, p0 = 24.5 МПа (p_b = 23.72 МПа — Стендинг);
  - oil_pvt.csv: 19 веток R_s = 0, 10, ..., 180 (решение пользователя
    2026-10-01; было три ветки 0/150/180 с прямой R_s(p) от 5 до 24 МПа).
    Точка насыщения ветки — Стендинг (p_b, B_o) и Бегс–Робинсон (mu_o) при
    rho_o,ст = 850, rho_g,ст = 0.85, T0 = 350 К — та же реализация, что
    StandingFullPVT пакета. Ветка R_s = 0 — мёртвая нефть при атмосферном
    давлении. Недонасыщенная часть — Васкес–Беггс, узлы через 1 МПа до
    30 МПа. Ветки выше R_s0 нужны (см. ниже);
  - relperm.csv: k_rg — Кори n_g = 3 с порогом S_gc = 0.1, узлы через 0.01
    (было 0.05: линейная интерполяция между узлами давала изломы S_g(r)
    при S_g = 0.15, 0.20, решение пользователя 2026-10-01);
    k_ro — линейная интерполяция узлов примера 12;
  - time: 12 интервалов по 30 сут, dt_integration = 1 сут;
  - gas_pvt.csv: три узла примера 12 (5, 15, 30 МПа) сохранены, между ними
    узлы через 0.5 МПа — PCHIP по 1/B_g и по mu_g (было: копия примера 12,
    излом S_g(r) при p = 15 МПа, решение пользователя 2026-10-01).

Запуск (из numerical_solver), DST — папка назначения:
    .venv\\Scripts\\python ..\\vault\\issues\\feat-024\\probes\\make_14_config.py <DST>
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

HERE = Path(__file__).resolve().parent
EX = HERE.parents[3] / "numerical_solver" / "examples"
SRC = EX / "12_large_drainage_radius"
DST = Path(sys.argv[1]).resolve()

DAY = 86400.0

# ── PVTO нефти ──
# Ветки выше R_s0 = 150 (160, 170, 180) обязательны: без них R_s_sat(p) при
# p > p_b упирается в край таблицы (R_s0), и ячейка, ошибочно помеченная
# двухфазной на первом суточном шаге, остаётся «насыщенной» с S_g ~ 1e-16
# (замер plan_numbers.py на прежней таблице).
RS_BRANCHES = np.arange(0.0, 180.0 + 1e-9, 10.0)
P_TOP = 30.0e6          # верх всех веток, Па — как у прежней таблицы
P_STEP = 1.0e6          # шаг узлов недонасыщенной части, Па


def oil_pvt_rows():
    """Ветки PVTO: (R_s, p, B_o, mu_o) в СИ; первая строка ветки — точка насыщения."""
    from gpn_multiphase_solver.pvt.standing import (
        StandingFullPVT, _api_gravity, _gas_specific_gravity, _K_to_F)
    from gpn_multiphase_solver.units import P_STD, PA_TO_PSI, SCF_PER_M3

    cfg = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
    rho_o, rho_g = cfg["pvt"]["rho_o_std"], cfg["pvt"]["rho_g_std"]
    T0 = cfg["initial_conditions"]["T0"]
    # Rs0 конструктора на ветки не влияет: p_b(R_s), B_o, mu_o считаются по R_s
    st = StandingFullPVT(rho_o, rho_g, T0, Rs0=150.0)
    api, gam_g, T_F = _api_gravity(rho_o), _gas_specific_gravity(rho_g), float(_K_to_F(T0))

    def A_vb(rs):
        # Васкес–Беггс: c_o = A/p (A безразмерна, p в psia) → интеграл от p_b:
        # B_o = B_ob·(p/p_b)^(-A). gamma_g без поправки на сепаратор 100 psig.
        return 1e-5 * (-1433.0 + 5.0 * rs * SCF_PER_M3 + 17.2 * T_F
                       - 1180.0 * gam_g + 12.61 * api)

    def m_vb(p):
        # Васкес–Беггс: mu_o = mu_ob·(p/p_b)^m, m = 2.6 p^1.187 exp(-11.513 - 8.98e-5 p),
        # p в psia. Вне области корреляции при больших p/p_b (ветки R_s = 0, 10:
        # mu_o x8 и x2.5 к 30 МПа) — в расчёте примера 14 эти участки не
        # используются: недонасыщенной бывает только нефть с R_s = R_s0.
        pp = p * PA_TO_PSI
        return 2.6 * pp ** 1.187 * np.exp(-11.513 - 8.98e-5 * pp)

    rows = []
    for rs in RS_BRANCHES:
        # Мёртвая нефть: R_s = 0 по определению при стандартных условиях.
        # У Стендинга p_b(0) < 0 — корреляция туда не продолжается.
        pb = P_STD if rs == 0.0 else float(st.pb(np.array([rs]))[0])
        Bob = float(st.Bo(np.array([pb]), np.array([rs]))[0])
        mub = float(st.mu_o(np.array([pb]), np.array([rs]))[0])
        # Точка насыщения + целые МПа строго выше p_b до P_TOP включительно
        p_nodes = [pb] + list(np.arange(np.floor(pb / P_STEP) + 1.0,
                                        P_TOP / P_STEP + 1e-9) * P_STEP)
        for p in p_nodes:
            Bo = Bob * (p / pb) ** (-A_vb(rs))
            mu = mub * (p / pb) ** m_vb(p)
            # 6 значащих цифр, как у gas_pvt.csv и k_rg
            rows.append((float(rs), float(round(p)), float(f"{Bo:.6g}"),
                         float(f"{mu:.6g}")))
    return rows

# Узлы k_ro примера 12 — k_ro между ними линейна, как у TabulatedRelPerm
SG_12 = np.array([0.0, 0.1, 0.2, 0.4, 0.6, 0.8])
KRO_12 = np.array([1.0, 0.8, 0.6, 0.3, 0.1, 0.0])
S_GC, S_OR, KRG_MAX, N_G = 0.1, 0.2, 0.8, 3.0


def relperm_rows():
    rows = []
    for sg in np.round(np.arange(0.0, 0.8 + 1e-9, 0.01), 2):
        kro = round(float(np.interp(sg, SG_12, KRO_12)), 6)
        s_star = min(max((sg - S_GC) / (1.0 - S_GC - S_OR), 0.0), 1.0)
        # 6 значащих цифр: табличная ОФП, как из лабораторного отчёта
        krg = float(f"{KRG_MAX * s_star ** N_G:.6g}")
        rows.append((float(sg), kro, krg))
    return rows


def gas_pvt_rows():
    p12, bg12, mu12 = np.loadtxt(SRC / "gas_pvt.csv", delimiter=",",
                                 skiprows=1, unpack=True)
    # Интерполяция по 1/B_g, а не по B_g: плотность газа rho_g = rho_g,ст/B_g
    # почти линейна по p, а B_g ~ 1/p — гипербола. Линейная интерполяция B_g
    # по трём узлам завышает её между узлами (+23 % при 10 МПа) и даёт излом
    # dB_g/dp в 4.5 раза в узле 15 МПа. PCHIP монотонна и проходит через узлы.
    inv_bg = PchipInterpolator(p12, 1.0 / bg12)
    mu_g = PchipInterpolator(p12, mu12)
    rows = []
    for p in np.arange(p12[0], p12[-1] + 1.0, 0.5e6):
        # 6 значащих цифр, как у k_rg; узлы примера 12 воспроизводятся точно
        rows.append((float(p), float(f"{1.0 / inv_bg(p):.6g}"),
                     float(f"{mu_g(p):.6g}")))
    return rows


DST.mkdir(parents=True, exist_ok=True)
with open(DST / "gas_pvt.csv", "w", encoding="utf-8", newline="\n") as f:
    f.write("pressure_Pa,Bg,mu_g_Pa_s\n")
    for p, bg, mu in gas_pvt_rows():
        f.write(f"{p:.0f},{bg!r},{mu!r}\n")
with open(DST / "oil_pvt.csv", "w", encoding="utf-8", newline="\n") as f:
    f.write("Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n")
    for rs, p, bo, mu in oil_pvt_rows():
        f.write(f"{rs!r},{p:.0f},{bo!r},{mu!r}\n")
with open(DST / "relperm.csv", "w", encoding="utf-8", newline="\n") as f:
    f.write("Sg,kro,krg\n")
    for sg, kro, krg in relperm_rows():
        f.write(f"{sg!r},{kro!r},{krg!r}\n")

cfg = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
cfg["initial_conditions"]["p0"] = 24.5e6
cfg["initial_conditions"]["Rs0"] = 150.0
cfg["time"]["dt_integration"] = DAY
cfg["time"]["history"] = [
    {"dt": 30 * DAY, "control": "pressure", "p_wf": 6.0e6} for _ in range(12)
]
(DST / "config.json").write_text(
    json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("записаны", DST, [p.name for p in sorted(DST.iterdir())])
