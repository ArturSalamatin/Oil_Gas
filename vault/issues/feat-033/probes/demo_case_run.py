"""Проба планирования FEAT-033: расчёт по демонстрационным значениям книги версии 1.

Конфиг собирается вручную — так, как его соберёт перевод книги (FEAT-035):
единицы книги → СИ, φ₀ = φ_ref·exp(c_r(p₀ − p_ref)), (ρc_p)_s = ρ_ma·c_ma,
SCHEDULE → time.history (интервал = разность моментов × 86400, до 1 мс).
Таблицы: OIL_PVT — T08c прототипа (черновик + ветвь R_s = 60), GAS_PVT и
RELPERM — INPUT_TEMPLATE.xlsx прототипа (равны черновику, compare_tables.out.txt).

Вопрос пробы: считается ли демонстрационный сценарий (30 сут, N = 100,
ступени BHP 150 → 120 → 100 бар) и чего стоит h0 = 0.11 с на смене режима
добычи — значение подобрано для останова (BUG-026), а не для ступеней BHP.

Варианты: h0 = 0.11 с (демо), h0 = 2 с, h0 выключено (none).

Запуск из корня проекта (пакет и прототип — из основного каталога):
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-033/probes/demo_case_run.py
Вывод: demo_case_run.out.txt; конфиги — demo_case/<вариант>/.
"""

import csv
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from compare_tables import T08C, TEMPLATE, cells, rows  # noqa: E402

import gpn_multiphase_solver                                    # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory      # noqa: E402
from gpn_multiphase_solver.io.config import load_config         # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA, CP_TO_PA_S, MD_TO_M2  # noqa: E402

DAY = 86400.0

# ── Демонстрационные значения книги (раздел 2.5 плана), единицы книги ──
MODEL = {"r_well": 0.1, "R_ext": 100.0, "h": 10.0, "k_mD": 1.0,
         "phi_ref": 0.2, "p_ref_bar": 200.0, "cr_1_bar": 4.5e-5,
         "rho_o_sc": 800.0, "rho_g_sc": 0.727, "p0_bar": 200.0, "Rs0": 50.0,
         "T0": 350.0, "skin": 0.0}
THERMAL = {"rho_ma": 2650.0, "c_ma": 820.0, "lam_ma": 2.5, "lam_o": 0.13,
           "lam_g": 0.05, "cp_o": 2365.0, "cp_g": 2800.0,
           "jt_o_K_MPa": -0.4, "jt_g_K_MPa": 2.05, "L_kJ_kg": 230.0}
# SCHEDULE черновика: (сут, режим, BHP бар); последняя строка — только конец
SCHEDULE = [(0.0, 150.0), (6.9444444444444447e-4, 150.0), (1.0, 150.0), (2.0, 150.0),
            (4.0, 150.0), (5.0, 120.0)] + \
           [(5.0 + k * 10.0 / DAY, 120.0) for k in range(1, 7)] + \
           [(6.0, 120.0), (14.0, 120.0), (15.0, 100.0)] + \
           [(15.0 + k * 10.0 / DAY, 100.0) for k in range(1, 7)] + \
           [(16.0, 100.0), (30.0, None)]


def write_case(dst: Path, h0_hours) -> Path:
    """Конфиг и CSV демонстрационного сценария в dst; h0_hours — None или часы."""
    dst.mkdir(parents=True, exist_ok=True)
    oil = rows(cells(T08C)["OIL_PVT"], 4)
    gas = rows(cells(TEMPLATE)["GAS_PVT"], 3)
    rp = rows(cells(TEMPLATE)["RELPERM"], 3)
    for name, header, data in (
            ("oil_pvt.csv", ["Rs_sm3_sm3", "pressure_Pa", "Bo", "mu_o_Pa_s"],
             [(rs, p * BAR_TO_PA, bo, mu * CP_TO_PA_S) for rs, p, bo, mu in oil]),
            ("gas_pvt.csv", ["pressure_Pa", "Bg", "mu_g_Pa_s"],
             [(p * BAR_TO_PA, bg, mu * CP_TO_PA_S) for p, bg, mu in gas]),
            ("relperm.csv", ["Sg", "kro", "krg"], rp)):
        with open(dst / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            for r in data:
                w.writerow([repr(float(x)) for x in r])
    m, th = MODEL, THERMAL
    p0 = m["p0_bar"] * BAR_TO_PA
    cr = m["cr_1_bar"] / BAR_TO_PA
    history = [{"dt": round((b[0] - a[0]) * DAY, 3), "control": "pressure",
                "p_wf": a[1] * BAR_TO_PA} for a, b in zip(SCHEDULE[:-1], SCHEDULE[1:])]
    cfg = {
        "geometry": {"r_well": m["r_well"], "R_ext": m["R_ext"], "h": m["h"]},
        "grid": {"N": 100, "type": "log_radial"},
        "rock": {"porosity": m["phi_ref"] * float(np.exp(cr * (p0 - m["p_ref_bar"] * BAR_TO_PA))),
                 "permeability": m["k_mD"] * MD_TO_M2,
                 "rho_cp_solid": th["rho_ma"] * th["c_ma"],
                 "lambda_solid": th["lam_ma"], "lambda_oil": th["lam_o"],
                 "lambda_gas": th["lam_g"], "compressibility": cr},
        "pvt": {"model": "table", "rho_o_std": m["rho_o_sc"], "rho_g_std": m["rho_g_sc"],
                "oil_pvt_file": "oil_pvt.csv", "gas_pvt_file": "gas_pvt.csv"},
        "relperm": {"model": "table", "file": "relperm.csv"},
        "thermal": {"c_p_oil": th["cp_o"], "c_p_gas": th["cp_g"],
                    "mu_JT_oil": th["jt_o_K_MPa"] / 1e6, "mu_JT_gas": th["jt_g_K_MPa"] / 1e6,
                    "L_degas": th["L_kJ_kg"] * 1e3},
        "initial_conditions": {"p0": p0, "T0": m["T0"], "Rs0": m["Rs0"]},
        "time": {"dt_integration": 1.0 * 3600.0,
                 "dt_after_control_change": None if h0_hours is None else h0_hours * 3600.0,
                 "history": history},
        "numerics": {"skin": m["skin"], "max_retries": 9, "newton_max_iter": 15,
                     "max_active_set_iter": 12, "newton_cell_tol": 1e-8,
                     "rs_switch_tol": 1e-5, "sg_switch_tol": 1e-9,
                     "jacobian_mode": "grouped", "linear_solver": "sparse"},
    }
    path = dst / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return path


class Collect(logging.Handler):
    """Сообщения журнала пакета уровня WARNING и выше."""
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def run(variant: str, h0_hours, out):
    cfg_path = write_case(HERE / "demo_case" / variant, h0_hours)
    cfg = load_config(cfg_path)
    handler = Collect()
    logging.getLogger("gpn_multiphase_solver").addHandler(handler)
    t0 = time.perf_counter()
    sim, state0 = SimulatorFactory.from_config(cfg)
    hist = sim.run(state0)
    wall = time.perf_counter() - t0
    logging.getLogger("gpn_multiphase_solver").removeHandler(handler)
    print(f"\n== {variant}: h0 = {cfg.time.dt_after_control_change!r} с, "
          f"porosity = {cfg.rock.porosity!r}, rho_cp_solid = {cfg.rock.rho_cp_solid!r}", file=out)
    print(f"   время счёта {wall:.1f} с, записей {hist.n_saved}, предупреждений "
          f"{len(handler.messages)}", file=out)
    for msg in sorted(set(handler.messages))[:8]:
        print(f"   ! {msg[:300]}", file=out)
    t = np.array(hist.times) / DAY
    for day in (6.9444444444444447e-4, 1.0, 5.0, 5.0 + 10 / DAY, 5.0 + 60 / DAY, 6.0,
                15.0 + 10 / DAY, 15.0 + 60 / DAY, 16.0, 30.0):
        i = int(np.argmin(np.abs(t - day)))
        st, w = hist.states[i], hist.well_data[i]
        print(f"   t = {t[i]:10.6f} сут: T_wf = {w.T_wf:.5f} К, q_o = {w.q_o_std * DAY:8.4f} "
              f"м³ст/сут, GOR = {w.q_g_std / max(w.q_o_std, 1e-30):7.2f}, "
              f"S_g(0) = {st.Sg[0]:.4f}, R_s(0) = {st.Rs[0]:.3f}, max S_g = {np.max(st.Sg):.4f}",
              file=out)
    return hist


def main():
    out_path = HERE / "demo_case_run.out.txt"
    with open(out_path, "w", encoding="utf-8") as out:
        print(f"пакет: {Path(gpn_multiphase_solver.__file__).parent}", file=out)
        results = {}
        for variant, h0 in (("h0_0.11s", 0.11 / 3600), ("h0_2s", 2.0 / 3600), ("h0_none", None)):
            results[variant] = run(variant, h0, out)
            out.flush()
        a, b = results["h0_0.11s"], results["h0_none"]
        dT = [abs(x.T_wf - y.T_wf) for x, y in zip(a.well_data, b.well_data)]
        print(f"\nmax |T_wf(0.11 с) − T_wf(none)| по записям = {max(dT):.5f} К", file=out)
    print(out_path)


if __name__ == "__main__":
    main()
