"""FEAT-025: генератор конфигов примеров 19–21 (PVT Стендинга, ОФП Кори).

Параметры — запись FEAT-025 в реестре фичей (оценка М.3 2026-10-01) и
решения пользователя при планировании: N = 350, S_or = 0.05, 30 сут по 1 сут,
L по Клапейрону, k = 10 / 30 / 10 мД. Без ключей — итоговые конфиги примеров
(подпапки 19/20/21; names=1 — полные имена папок).
Вызов: make_configs.py <папка назначения> [ключ=значение ...]
Ключи переопределения: N, R_ext, days, dt_int, n_g, n_o, S_or, krg_max,
L19, L20, L21, muo, mr, ramp=1, log, k — для проб вариантов. Первые пробы
(base, mr12, ramp, Lhigh, n50s, n350, n350s) сняты при прежних умолчаниях
N = 50, S_or = 0.2, k = 1e-13, log = WARNING — для их воспроизведения
передать эти ключи явно.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\make_configs.py ..\\vault\\issues\\feat-025\\probes\\base
"""

import json
import sys
from pathlib import Path

DAY = 86400.0

# ── Наборы параметров (запись FEAT-025) ──
# rho_g_std: γ_g = rho_g_std / 1.225 (RHO_AIR_STD решателя)
SETS = {
    # p0 = p_b решателя + 0.5 МПа; p_b решателя (RHO_WATER_STD = 999):
    # 19 — 24.1847, 20 — 46.3803, 21 — 17.2235 МПа
    # k — решение пользователя 2026-10-01: 10 мД в 19 и 21 (дебит ~250 и ~170
    # м³ст/сут); 30 мД в 20 — при 10 мД первый шаг не сходится (BUG-018)
    "19": dict(Rs0=150.0, T0=400.0, rho_o_std=800.0, rho_g_std=0.727,
               p0=24.7e6, p_wf=3.0e6, c_p_oil=2365.0, c_p_gas=2800.0,
               mu_JT_gas=2.05e-6, L=202000.0, k=1e-14),
    "20": dict(Rs0=500.0, T0=380.0, rho_o_std=800.0, rho_g_std=1.014,
               p0=46.9e6, p_wf=5.0e6, c_p_oil=2290.0, c_p_gas=3010.0,
               mu_JT_gas=2.0e-6, L=26000.0, k=3e-14),
    "21": dict(Rs0=100.0, T0=400.0, rho_o_std=800.0, rho_g_std=0.727,
               p0=17.7e6, p_wf=3.0e6, c_p_oil=2365.0, c_p_gas=2740.0,
               mu_JT_gas=2.3e-6, L=227000.0, k=1e-14),
}

# Разгон шага в начале истории: 1, 1, 2, 4, 8, 8 ч = 1 сут (как проба FEAT-024)
RAMP_H = [1, 1, 2, 4, 8, 8]


def history(s, o):
    """Интервалы истории: суточные; ramp=1 — первые сутки разбиты по RAMP_H."""
    days = int(o.get("days", 30))
    iv = [DAY] * days
    if o.get("ramp") == "1":
        iv = [h * 3600.0 for h in RAMP_H] + [DAY] * (days - 1)
    return [{"dt": d, "control": "pressure", "p_wf": s["p_wf"]} for d in iv]


def build(name, s, o):
    """Конфиг одного примера; o — переопределения из командной строки."""
    dt_int = float(o.get("dt_int", DAY))
    return {
        "geometry": {"r_well": 0.1, "R_ext": float(o.get("R_ext", 200.0)), "h": 10.0},
        "grid": {"N": int(o.get("N", 350)), "type": "log_radial"},
        "rock": {
            "porosity": 0.2,
            "permeability": float(o.get("k", s["k"])),
            "rho_cp_solid": 2.1e6,     # кварц 2650 кг/м³ × 800 Дж/(кг·К), на объём зёрен
            "lambda_solid": 2.5,
            "lambda_oil": 0.13,
            "lambda_gas": 0.05,
        },
        "pvt": {"model": "standing", "rho_o_std": s["rho_o_std"], "rho_g_std": s["rho_g_std"]},
        "relperm": {
            "model": "corey",
            # S_or = 0.05 — обход BUG-018: при 0.2 первый шаг не сходится в 20
            # (S_g «закрытого сосуда» 0.91 > 1 - S_or) и в 19 на N = 350 (0.85)
            "S_or": float(o.get("S_or", 0.05)),
            "S_gc": 0.1,               # решение пользователя: газ подвижен при S_g > 0.1
            "n_o": float(o.get("n_o", 2.0)),
            "n_g": float(o.get("n_g", 3.0)),
            "kro_max": 1.0,
            "krg_max": float(o.get("krg_max", 0.8)),
        },
        "thermal": {
            "c_p_oil": s["c_p_oil"],
            "c_p_gas": s["c_p_gas"],
            "mu_JT_oil": float(o.get("muo", -4e-7)),
            "mu_JT_gas": s["mu_JT_gas"],
            "L_degas": float(o.get("L" + name, s["L"])),
        },
        "initial_conditions": {"p0": s["p0"], "T0": s["T0"], "Rs0": s["Rs0"]},
        "time": {
            "start_day": 0.0,
            "dt_integration": dt_int,
            "history": history(s, o),
        },
        "numerics": {"dt_min": 1.0, "dt_max": 86400, "skin": 0.0,
                     "max_retries": int(o.get("mr", 9))},
        "output": {"log_level": o.get("log", "INFO")},
    }


# Папки примеров в numerical_solver/examples/ (ключ names=1)
FOLDERS = {"19": "19_rs150_cooling", "20": "20_rs500_cooling", "21": "21_rs100_cooling"}


if __name__ == "__main__":
    dst = Path(sys.argv[1])
    over = dict(a.split("=", 1) for a in sys.argv[2:])
    for name, s in SETS.items():
        d = dst / (FOLDERS[name] if over.get("names") == "1" else name)
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(
            json.dumps(build(name, s, over), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{d / 'config.json'}")
