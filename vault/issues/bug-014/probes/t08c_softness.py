"""BUG-014: проходит ли T08c (скачок BHP 100 → 175 бар на 5 сут) только из-за мягкости постановки?

В регрессии прототипа T08c идёт без единого отклонённого шага, но там k = 1 мД
и первый шаг после скачка обрезан строкой расписания «5 сут + 1 мин» до 60 с.
Здесь тот же T08c.xlsx (PVT, ОФП, сетка, p0 = pe = 200 бар) прогоняется
матрицей 2×2: k = 1 / 100 мД × со строкой «+1 мин» / без неё. Горизонт 7 сут
(скачок на 5 сут + 2 сут после), драйвер — штатный simulate_schedule прототипа
(деление шага пополам при отказе, DT minimum = 1e-5 с).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-014\\probes\\t08c_softness.py
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[3] / "numerical_solver" / "HydroSolverPrototype" / "Prototype_1.0.3"
sys.path.insert(0, str(PROTO))

from radial_blackoil.input_reader import load_input  # noqa: E402
from radial_blackoil.grid import RadialGrid  # noqa: E402
from radial_blackoil.rock import CompressibleRock  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402
from radial_blackoil.blackoil import RadialBlackOilModel  # noqa: E402
from radial_blackoil.schedule import Schedule  # noqa: E402
from radial_blackoil.simulation import simulate_schedule, SimulationFailure  # noqa: E402
from radial_blackoil.units import DAY_TO_S  # noqa: E402

T_END_DAY = 7.0
T_JUMP_S = 5.0 * DAY_TO_S          # момент скачка BHP 100 → 175 бар
ONE_MIN_ROW_DAY = 5.0 + 1.0 / 1440.0  # строка отчёта «+1 мин», обрезающая первый шаг до 60 с


def build(perm_md, keep_one_min_row):
    """Модель и расписание как в runner.run_workbook, с подменой k и строк расписания."""
    inp = load_input(PROTO / "regression" / "inputs" / "T08c.xlsx")
    p = inp.params
    grid = RadialGrid(float(p["Well radius rw"]), float(p["Outer radius re"]),
                      float(p["Formation thickness h"]), int(p["Grid cells N"]), float(perm_md))
    rock = CompressibleRock(float(p["Reference porosity"]), float(p["Reference pressure"]),
                            float(p["Rock compressibility cr"]))
    rows = [r for r in inp.schedule.rows if r.time_day <= T_END_DAY + 1e-12]
    if not keep_one_min_row:
        rows = [r for r in rows if abs(r.time_day - ONE_MIN_ROW_DAY) > 1e-9]
    sched = Schedule(rows, T_END_DAY)
    model = RadialBlackOilModel(grid, rock, inp.pvt, inp.relperm, rows[0].bhp_bar,
                                float(p["Outer-boundary pressure"]), float(p["Initial dissolved gas Rs"]),
                                skin=float(p["Well skin"]), jacobian_mode=str(p["Jacobian mode"]),
                                linear_solver=str(p["Linear solver"]))
    state0 = BlackOilState.undersaturated(grid.n, float(p["Initial pressure"]), float(p["Initial dissolved gas Rs"]))
    dt0 = float(p["DT initial"]) * 60.0
    dtmin = float(p["DT minimum"])
    dtmax = float(p["DTMAX"]) * 60.0
    return model, state0, sched, dt0, dtmin, dtmax


def run(perm_md, keep_one_min_row):
    model, state0, sched, dt0, dtmin, dtmax = build(perm_md, keep_one_min_row)
    tic = time.perf_counter()
    try:
        hist = simulate_schedule(model, state0, sched, dt0, dtmin, dtmax)
        status, err = "SUCCESS", ""
    except SimulationFailure as e:
        hist, status, err = e.history, "FAILED", str(e)
    wall = time.perf_counter() - tic

    # step_log: (t, dt, accepted, newton_it, active_set_it, phase_switches, res_inf);
    # для принятого шага t — КОНЕЦ шага, для отклонённого — НАЧАЛО.
    log = hist.step_log
    t_start = [(x[0] - x[1]) if x[2] else x[0] for x in log]
    before = [x for x, t0 in zip(log, t_start) if t0 < T_JUMP_S - 1e-6]
    after = [x for x, t0 in zip(log, t_start) if T_JUMP_S - 1e-6 <= t0 < T_JUMP_S + DAY_TO_S]
    first_try = after[0] if after else None
    first_acc = next((x for x in after if x[2]), None)
    # Отказы подряд от момента скачка до первого принятого шага
    rej_chain = 0
    for x in after:
        if x[2]:
            break
        rej_chain += 1
    acc_after = [x for x in after if x[2]]
    # Сколько секунд модельного времени и сколько шагов ушло на первый час после скачка
    first_hour = [x for x in acc_after if x[0] <= T_JUMP_S + 3600.0 + 1e-6]
    return {
        "k_mD": perm_md,
        "row_+1min": keep_one_min_row,
        "status": status,
        "wall_s": wall,
        "acc_before_jump": sum(1 for x in before if x[2]),
        "rej_before_jump": sum(1 for x in before if not x[2]),
        "first_try_dt_s": first_try[1] if first_try else None,
        "rej_chain_at_jump": rej_chain,
        "first_acc_dt_s": first_acc[1] if first_acc else None,
        "first_acc_newton": first_acc[3] if first_acc else None,
        "rej_day5_6": sum(1 for x in after if not x[2]),
        "acc_first_hour": len(first_hour),
        "min_acc_dt_day5_6": min((x[1] for x in acc_after), default=None),
        "err": err,
    }


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


if __name__ == "__main__":
    cols = ["k_mD", "row_+1min", "status", "wall_s", "acc_before_jump", "rej_before_jump",
            "first_try_dt_s", "rej_chain_at_jump", "first_acc_dt_s", "first_acc_newton",
            "rej_day5_6", "acc_first_hour", "min_acc_dt_day5_6"]
    results = []
    for perm in (1.0, 100.0):
        for keep in (True, False):
            r = run(perm, keep)
            results.append(r)
            print(" | ".join(f"{c}={fmt(r[c])}" for c in cols), flush=True)
            if r["err"]:
                print("   ошибка:", r["err"], flush=True)
