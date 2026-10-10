"""Проба VAL-005: черновик конвертера книги прототипа → CSV (СИ) + config.json.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\val-005\\probes\\convert_draft.py <xlsx> <каталог вывода> <dt_integration, с>
"""
import csv
import json
import sys
from pathlib import Path

SOLVER = Path.cwd()  # запускать из numerical_solver/
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
sys.path.insert(0, str(PROTO))
print("PROTO =", PROTO)

from radial_blackoil.xlsxio import read_workbook_tables  # noqa: E402

BAR = 1e5            # Па в баре
CP = 1e-3            # Па·с в сантипуазе
MD = 9.869233e-16    # м² в миллидарси
DAY = 86400.0        # с в сутках

# Тепловые свойства и плотности при ст. условиях — НЕ из книги прототипа
# (он изотермический): взяты из примера 14 (решение пользователя 2026-10-08).
THERMAL = {"c_p_oil": 2000.0, "c_p_gas": 2850.0, "mu_JT_oil": -4e-07,
           "mu_JT_gas": 4e-06, "L_degas": 230000.0}
ROCK_THERMAL = {"rho_cp_solid": 1250000.0, "lambda_solid": 1.5,
                "lambda_oil": 0.14, "lambda_gas": 0.04}
RHO_O_STD, RHO_G_STD, T0 = 850.0, 0.85, 350.0


def table(rows, headers):
    """Строки листа → список кортежей float по заголовкам; нечисловые строки пропускаются."""
    h = [str(x).strip() if x is not None else "" for x in rows[0]]
    idx = [h.index(k) for k in headers]
    out = []
    for r in rows[1:]:
        try:
            out.append(tuple(float(r[i]) for i in idx))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def convert(xlsx, out_dir, dt_integration):
    sh = read_workbook_tables(xlsx)
    m_rows = sh["MODEL"]
    h = [str(x).strip() if x is not None else "" for x in m_rows[0]]
    ip, iv = h.index("Parameter"), h.index("Value")
    m = {str(r[ip]).strip(): r[iv] for r in m_rows[1:] if len(r) > iv and r[ip] not in (None, "")}

    p0 = float(m["Initial pressure"]) * BAR
    # Наш решатель держит на контуре p0 и берёт опорное давление породы = p0
    # (factory.py:357-361) — расхождение книги с этим было бы молчаливой подменой.
    assert float(m["Outer-boundary pressure"]) * BAR == p0, "p_e != p0"
    assert float(m["Reference pressure"]) * BAR == p0, "p_ref != p0"

    out_dir.mkdir(parents=True, exist_ok=True)
    oil = table(sh["OIL_PVT"], ["Rs, Sm3/Sm3", "Pressure, bar(a)", "Bo, rm3/Sm3", "mu_o, cP"])
    with open(out_dir / "oil_pvt.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Rs_sm3_sm3", "pressure_Pa", "Bo", "mu_o_Pa_s"])
        for rs, p, bo, mu in oil:
            w.writerow([repr(rs), repr(p * BAR), repr(bo), repr(mu * CP)])
    gas = table(sh["GAS_PVT"], ["Pressure, bar(a)", "Bg, rm3/Sm3", "mu_g, cP"])
    with open(out_dir / "gas_pvt.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pressure_Pa", "Bg", "mu_g_Pa_s"])
        for p, bg, mu in gas:
            w.writerow([repr(p * BAR), repr(bg), repr(mu * CP)])
    rp = table(sh["RELPERM"], ["Sg", "kro", "krg"])
    with open(out_dir / "relperm.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Sg", "kro", "krg"])
        for row in rp:
            w.writerow([repr(x) for x in row])

    # SCHEDULE: строка k — граница и режим интервала [t_k, t_{k+1}]
    s_rows = sh["SCHEDULE"]
    hs = [str(x).strip() if x is not None else "" for x in s_rows[0]]
    sched = []
    for r in s_rows[1:]:
        if r[hs.index("Time, day")] in (None, ""):
            continue
        sched.append(dict(zip(hs, r)))
    history = []
    for a, b in zip(sched[:-1], sched[1:]):
        dt = round((float(b["Time, day"]) - float(a["Time, day"])) * DAY, 3)
        mode = str(a["Control mode"]).strip()
        if mode == "BHP":
            history.append({"dt": dt, "control": "pressure",
                            "p_wf": float(a["BHP target, bar(a)"]) * BAR})
        else:
            history.append({"dt": dt, "control": "rate",
                            "q_oil": float(a["Oil-rate target, Sm3/day"]) / DAY,
                            "min_bhp": float(a["Minimum BHP, bar(a)"]) * BAR})
    assert abs(float(sched[-1]["Time, day"]) - float(m["Simulation time"])) < 1e-9

    cfg = {
        "geometry": {"r_well": float(m["Well radius rw"]), "R_ext": float(m["Outer radius re"]),
                     "h": float(m["Formation thickness h"])},
        "grid": {"N": int(float(m["Grid cells N"])), "type": "log_radial"},
        "rock": {"porosity": float(m["Reference porosity"]),
                 "permeability": float(m["Absolute permeability"]) * MD,
                 **ROCK_THERMAL,
                 "compressibility": float(m["Rock compressibility cr"]) / BAR},
        "pvt": {"model": "table", "rho_o_std": RHO_O_STD, "rho_g_std": RHO_G_STD,
                "oil_pvt_file": "oil_pvt.csv", "gas_pvt_file": "gas_pvt.csv"},
        "relperm": {"model": "table", "file": "relperm.csv"},
        "thermal": THERMAL,
        "initial_conditions": {"p0": p0, "T0": T0, "Rs0": float(m["Initial dissolved gas Rs"])},
        "time": {"start_day": 0.0, "dt_integration": dt_integration, "history": history},
        "numerics": {"skin": float(m["Well skin"]),
                     "jacobian_mode": str(m["Jacobian mode"]).strip(),
                     "linear_solver": str(m["Linear solver"]).strip()},
        "output": {"log_level": "INFO"},
    }
    (out_dir / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{out_dir}: интервалов истории {len(history)}, строк PVTO {len(oil)}, "
          f"газ {len(gas)}, ОФП {len(rp)}, dt_integration {dt_integration} с")


if __name__ == "__main__":
    convert(Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3]))
