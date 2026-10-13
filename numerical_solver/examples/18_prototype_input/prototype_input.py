"""Пример 18: книга Excel прототипа → конфиг решателя; сверка с прототипом и CMG IMEX (VAL-005).

Конвертация (из numerical_solver/):
    .venv\\Scripts\\python examples\\18_prototype_input\\prototype_input.py
Пишет config.json, oil_pvt.csv, gas_pvt.csv, relperm.csv в папку примера из книги BOOK.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
# Каталог прототипа в репозитории — ради данных: книга INPUT_TEMPLATE.xlsx и
# книги регрессии (BOOK, IMEX_BOOK, IMEX_DIR ниже). Пакет radial_blackoil —
# установленный дистрибутив radial-blackoil (DEBT-059).
# examples/18_prototype_input/ → numerical_solver/
PROTO_ROOT = HERE.parents[1] / "HydroSolverPrototype" / "Prototype_1.0.3"

from gpn_multiphase_solver.units import BAR_TO_PA, CP_TO_PA_S, MD_TO_M2  # noqa: E402

DAY = 86400.0   # с в сутках

# Книга примера — шаблон ввода прототипа (решение пользователя 2026-10-08).
# Другая книга: заменить путь здесь и перезапустить конвертацию — main.py
# считает прототип на той же BOOK.
BOOK = PROTO_ROOT / "INPUT_TEMPLATE.xlsx"

# Эталон CMG IMEX (полностью неявный) есть для регрессионного кейса T07: MODEL
# и таблицы те же, что в шаблоне; у шаблона лишь добавлены отчёты через 10 с
# после смен режима (CONTEXT_HANDOFF_1.0.3.md: шаблон основан на T07).
IMEX_BOOK = PROTO_ROOT / "regression" / "inputs" / "T07.xlsx"
IMEX_DIR = PROTO_ROOT / "regression" / "reference_imex_normalized"
IMEX_CELLS = 100   # ячеек пласта у IMEX; 101-я — буфер постоянного давления за контуром
# Приёмочные отметки авторов прототипа, сут. Отметки «+1 мин» после смен
# режима авторы из приёмки исключили (regression/evidence/P16_FINAL_REGRESSION_README.txt).
STABLE_DAYS = (1.0, 2.0, 4.0, 5.0, 6.0, 14.0, 15.0, 16.0, 30.0)

# ── Чего в книге нет ──
# Прототип изотермический: теплофизики и плотностей при ст. условиях в книге
# нет. Значения — как в примере 14 (решение пользователя 2026-10-08), это НЕ
# данные автора книги. На гидродинамику они не влияют: HydroSolver не видит
# секцию thermal, плотности нужны только уравнению энергии.
RHO_O_STD, RHO_G_STD = 850.0, 0.85   # кг/м³
T0 = 350.0                           # К
THERMAL = {"c_p_oil": 2000.0, "c_p_gas": 2850.0,
           "mu_JT_oil": -4e-07, "mu_JT_gas": 4e-06, "L_degas": 230000.0}
ROCK_THERMAL = {"rho_cp_solid": 1250000.0, "lambda_solid": 1.5,
                "lambda_oil": 0.14, "lambda_gas": 0.04}

# ── Допуски сверки (замер плана VAL-005, 2026-10-08) ──
# Против прототипа на той же книге различие — только последовательность шагов
# по времени: у нас dt_integration = DTMAX = 3600 с, у прототипа 1 мин с ростом
# до 60 мин. Замер: Δp 0.0054 бар, ΔS_g 3.1e-4, ΔR_s 1.7e-3, q_g 0.068 %;
# запас ~3 раза. Ошибку перевода книги допуск ловит: k на 1 % — q_o 0.94 %,
# c_r = 0 — Δp 1.38 бар, скин 0.1 — Δp 7.4 бар.
TOL_PROTOTYPE = {"dp": 0.02, "dsg": 1e-3, "drs": 5e-3,
                 "dqo": 0.2, "dqg": 0.2, "dgor": 0.2, "dbhp": 1e-9}
# Против IMEX T07 — уровень приёмки прототипа авторами (Δp 0.137 бар, ΔS_g
# 0.0046, RMSE 0.0023, ΔR_s 0.045, q_o 0.51 %, q_g 2.52 %, GOR 2.56 %) с запасом
# ~10 %. Замер: 0.1373 / 0.0046 / 0.00227 / 0.0445 / 0.51 / 2.59 / 2.62.
TOL_IMEX = {"dp": 0.15, "dsg": 0.005, "rmse_sg": 0.0025, "drs": 0.05,
            "dqo": 0.6, "dqg": 3.0, "dgor": 3.0}


# ═══════════════════════════════════════════════════════════
# Книга прототипа → конфиг
# ═══════════════════════════════════════════════════════════

def _read_book(book: Path) -> dict:
    """Листы книги → {имя: строки}; тем же ридером, что у прототипа."""
    from radial_blackoil.xlsxio import read_workbook_tables
    return read_workbook_tables(book)


def _header(rows) -> list:
    return [str(x).strip() if x is not None else "" for x in rows[0]]


def _table(rows, headers) -> list:
    """Строки листа → кортежи float по заголовкам; строки без чисел пропускаются, как в input_reader прототипа."""
    h = _header(rows)
    idx = [h.index(k) for k in headers]
    out = []
    for r in rows[1:]:
        try:
            out.append(tuple(float(r[i]) for i in idx))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def _model(sheets) -> dict:
    """Лист MODEL → {параметр: значение}."""
    rows = sheets["MODEL"]
    h = _header(rows)
    ip, iv = h.index("Parameter"), h.index("Value")
    return {str(r[ip]).strip(): r[iv] for r in rows[1:]
            if len(r) > iv and r[ip] not in (None, "")}


def _schedule(sheets) -> list:
    """Лист SCHEDULE → строки {заголовок: значение}, только строки со временем."""
    rows = sheets["SCHEDULE"]
    h = _header(rows)
    it = h.index("Time, day")
    return [dict(zip(h, r)) for r in rows[1:] if len(r) > it and r[it] not in (None, "")]


def _write_csv(path: Path, header, rows) -> None:
    # repr — кратчайшая запись double без потери точности; "\n" — окончания
    # строк не зависят от платформы.
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow([repr(float(x)) for x in row])


def convert(book: Path, out_dir: Path) -> None:
    """Книга прототипа → config.json, oil_pvt.csv, gas_pvt.csv, relperm.csv (СИ) в out_dir."""
    sheets = _read_book(book)
    m = _model(sheets)
    p0 = float(m["Initial pressure"]) * BAR_TO_PA
    # Решатель держит на контуре p0 и берёт опорное давление породы равным p0
    # (factory.py, CompressibleRock: p_ref_bar = p0). Книга с другими значениями
    # молча считалась бы не той задачей — отказ.
    for key in ("Outer-boundary pressure", "Reference pressure"):
        if float(m[key]) * BAR_TO_PA != p0:
            raise ValueError(f"{book.name}: «{key}» = {m[key]} бар, а Initial pressure = "
                             f"{m['Initial pressure']} бар — решатель такую задачу не ставит")

    out_dir.mkdir(parents=True, exist_ok=True)
    oil = _table(sheets["OIL_PVT"], ["Rs, Sm3/Sm3", "Pressure, bar(a)", "Bo, rm3/Sm3", "mu_o, cP"])
    _write_csv(out_dir / "oil_pvt.csv", ["Rs_sm3_sm3", "pressure_Pa", "Bo", "mu_o_Pa_s"],
               [(rs, p * BAR_TO_PA, bo, mu * CP_TO_PA_S) for rs, p, bo, mu in oil])
    gas = _table(sheets["GAS_PVT"], ["Pressure, bar(a)", "Bg, rm3/Sm3", "mu_g, cP"])
    _write_csv(out_dir / "gas_pvt.csv", ["pressure_Pa", "Bg", "mu_g_Pa_s"],
               [(p * BAR_TO_PA, bg, mu * CP_TO_PA_S) for p, bg, mu in gas])
    _write_csv(out_dir / "relperm.csv", ["Sg", "kro", "krg"],
               _table(sheets["RELPERM"], ["Sg", "kro", "krg"]))

    # ── SCHEDULE → time.history ──
    # Строка k — граница интервала [t_k, t_{k+1}] и режим на нём (семантика
    # прототипа, docs/INPUT_FORMAT.md). Разность в сутках → с округляется до мс:
    # 10-секундные интервалы в double дают 9.99999…
    sched = _schedule(sheets)
    if abs(float(sched[-1]["Time, day"]) - float(m["Simulation time"])) > 1e-9:
        raise ValueError(f"{book.name}: последняя строка SCHEDULE ≠ Simulation time")
    history = []
    for a, b in zip(sched[:-1], sched[1:]):
        dt = round((float(b["Time, day"]) - float(a["Time, day"])) * DAY, 3)
        if str(a["Control mode"]).strip() == "BHP":
            history.append({"dt": dt, "control": "pressure",
                            "p_wf": float(a["BHP target, bar(a)"]) * BAR_TO_PA})
        else:
            # OIL_RATE: м³ст/сут → м³ст/с; нижняя граница p_wf у решателя
            # обязательна (у прототипа — нет, он берёт давление контура)
            if a.get("Minimum BHP, bar(a)") in (None, ""):
                raise ValueError(f"{book.name}: OIL_RATE на {a['Time, day']} сут без Minimum BHP")
            history.append({"dt": dt, "control": "rate",
                            "q_oil": float(a["Oil-rate target, Sm3/day"]) / DAY,
                            "min_bhp": float(a["Minimum BHP, bar(a)"]) * BAR_TO_PA})

    cfg = {
        "geometry": {"r_well": float(m["Well radius rw"]), "R_ext": float(m["Outer radius re"]),
                     "h": float(m["Formation thickness h"])},
        "grid": {"N": int(float(m["Grid cells N"])), "type": "log_radial"},
        "rock": {"porosity": float(m["Reference porosity"]),
                 "permeability": float(m["Absolute permeability"]) * MD_TO_M2,
                 **ROCK_THERMAL,
                 "compressibility": float(m["Rock compressibility cr"]) / BAR_TO_PA},
        "pvt": {"model": "table", "rho_o_std": RHO_O_STD, "rho_g_std": RHO_G_STD,
                "oil_pvt_file": "oil_pvt.csv", "gas_pvt_file": "gas_pvt.csv"},
        "relperm": {"model": "table", "file": "relperm.csv"},
        "thermal": THERMAL,
        "initial_conditions": {"p0": p0, "T0": T0, "Rs0": float(m["Initial dissolved gas Rs"])},
        # Шаг интегрирования = наибольший шаг прототипа DTMAX (мин → с). Свой
        # выбор шага прототипа (DT initial, DT minimum) решатель не повторяет:
        # шаг постоянен на интервале истории (дробится только при отказе Ньютона).
        # start_day не пишется: поле удалено из схемы (DEBT-008), время истории — от 0
        "time": {"dt_integration": float(m["DTMAX"]) * 60.0,
                 "history": history},
        "numerics": {"skin": float(m["Well skin"]),
                     "jacobian_mode": str(m["Jacobian mode"]).strip(),
                     "linear_solver": str(m["Linear solver"]).strip()},
        "output": {"log_level": "INFO"},
    }
    (out_dir / "config.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _controls(sched) -> list:
    """Режимы скважины по SCHEDULE: (сут, режим, уставки) там, где режим меняется, и конец расписания."""
    keys = ("Control mode", "BHP target, bar(a)", "Oil-rate target, Sm3/day", "Minimum BHP, bar(a)")
    out, prev = [], None
    for r in sched:
        cur = tuple(r.get(k) for k in keys)
        if cur != prev:
            out.append((float(r["Time, day"]),) + cur)
            prev = cur
    return out + [float(sched[-1]["Time, day"])]


def imex_applicable(book: Path) -> bool:
    """Годится ли эталон IMEX T07 для книги: тот же MODEL, те же таблицы и режимы скважины."""
    a, b = _read_book(book), _read_book(IMEX_BOOK)
    return (_model(a) == _model(b)
            and all(a[s] == b[s] for s in ("OIL_PVT", "GAS_PVT", "RELPERM"))
            and _controls(_schedule(a)) == _controls(_schedule(b)))


# ═══════════════════════════════════════════════════════════
# Эталоны и сверка
# ═══════════════════════════════════════════════════════════

def run_prototype(book: Path, out_dir: Path) -> dict:
    """Расчёт прототипа на книге штатным путём (run_workbook, как run_prototype.py), ~12 с; сводка run_summary."""
    from radial_blackoil.runner import run_workbook
    return run_workbook(book, out_dir)


def load_prototype(out_dir: Path) -> dict:
    """profiles.csv, rates.csv прототипа → {сут: {"p" (бар), "Sg", "Rs" по ячейкам; "qo", "qg" (м³ст/сут), "GOR", "BHP" (бар)}}."""
    marks: dict = {}
    with open(out_dir / "profiles.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m = marks.setdefault(float(r["time_day"]), {"p": [], "Sg": [], "Rs": []})
            m["p"].append(float(r["pressure_bar"]))
            m["Sg"].append(float(r["Sg"]))
            m["Rs"].append(float(r["Rs"]))
    with open(out_dir / "rates.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            marks[float(r["time_day"])].update(
                qo=float(r["oil_rate_sm3_day"]), qg=float(r["gas_rate_sm3_day"]),
                GOR=float(r["GOR_sm3_sm3"]), BHP=float(r["BHP_bar"]))
    for m in marks.values():
        for k in ("p", "Sg", "Rs"):
            m[k] = np.asarray(m[k])
    return marks


def load_imex() -> dict:
    """Эталон IMEX T07 на отметках STABLE_DAYS — та же структура, что у load_prototype; ячейки 1…100."""
    prof: dict = {}
    with open(IMEX_DIR / "T07_profiles.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cell = int(r["cell"])
            if cell <= IMEX_CELLS:
                prof.setdefault(round(float(r["time_day"]), 6), {}).setdefault(
                    r["variable"], {})[cell] = float(r["value"])
    with open(IMEX_DIR / "T07_rates.csv", newline="", encoding="utf-8") as f:
        rates = {round(float(r["time_day"]), 6): r for r in csv.DictReader(f)}
    out = {}
    cells = range(1, IMEX_CELLS + 1)
    for d in STABLE_DAYS:
        pr, rr = prof[d], rates[d]
        p = np.array([pr["P_bar"][c] for c in cells])
        # В нормализованном файле на отметках «+1 мин» давление записано в кПа
        # (15133 вместо 151.3). Они в сверку не входят; на остальных — бары.
        if p.max() > 1000.0:
            raise ValueError(f"IMEX T07, {d:g} сут: давление {p.max():.0f} — не бары")
        out[d] = {"p": p, "Sg": np.array([pr["Sg"][c] for c in cells]),
                  "Rs": np.array([pr["Rs"][c] for c in cells]),
                  "qo": float(rr["qo"]), "qg": float(rr["qg"]),
                  "GOR": float(rr["GOR"]), "BHP": float(rr["BHP_bar"])}
    return out


def _ours(history, day: float) -> dict:
    """Запись истории на отметке day сут — в единицах эталонов (бар, м³ст/сут)."""
    t = np.asarray(history.times) / DAY
    i = int(np.argmin(np.abs(t - day)))
    # Отметки — границы интервалов истории; сумма dt, округлённых до мс,
    # отходит от времени строки книги на ~1e-6 с.
    if abs(t[i] - day) * DAY > 1e-2:
        raise ValueError(f"нет записи на {day:.9g} сут (ближайшая — {t[i]:.9g})")
    s, w = history.states[i], history.well_data[i]
    qo, qg = w.q_o_std * DAY, w.q_g_std * DAY
    return {"p": s.p / BAR_TO_PA, "Sg": s.Sg, "Rs": s.Rs,
            "qo": qo, "qg": qg, "GOR": qg / qo, "BHP": w.p_wf / BAR_TO_PA}


def compare(history, ref: dict, days) -> dict:
    """Наибольшие по отметкам days расхождения с эталоном: профили — абсолютные, дебиты — относительные, %."""
    # Метрики — как у авторов прототипа при сверке с IMEX (regression/evidence/
    # FINAL_REGRESSION_METRICS_20260825a.json; по golden/T07 воспроизводятся до
    # последнего знака): ячейка i ↔ ячейка i, RMSE S_g — по ячейкам отметки,
    # максимум по отметкам.
    worst = dict.fromkeys(("dp", "dsg", "rmse_sg", "drs", "dqo", "dqg", "dgor", "dbhp"), 0.0)
    for d in days:
        a, b = _ours(history, d), ref[d]
        dsg = a["Sg"] - b["Sg"]
        cur = {"dp": np.max(np.abs(a["p"] - b["p"])), "dsg": np.max(np.abs(dsg)),
               "rmse_sg": np.sqrt(np.mean(dsg ** 2)), "drs": np.max(np.abs(a["Rs"] - b["Rs"])),
               "dqo": 100.0 * abs(a["qo"] / b["qo"] - 1.0),
               "dqg": 100.0 * abs(a["qg"] / b["qg"] - 1.0),
               "dgor": 100.0 * abs(a["GOR"] / b["GOR"] - 1.0),
               "dbhp": abs(a["BHP"] - b["BHP"])}
        for k, v in cur.items():
            worst[k] = max(worst[k], float(v))
    return worst


_LABELS = {"dp": ("max|Δp|", "бар"), "dsg": ("max|ΔS_g|", ""), "rmse_sg": ("RMSE S_g", ""),
           "drs": ("max|ΔR_s|", "м³ст/м³ст"), "dqo": ("max|Δq_o|", "%"),
           "dqg": ("max|Δq_g|", "%"), "dgor": ("max|ΔGOR|", "%"), "dbhp": ("max|Δp_wf|", "бар")}


def _report(worst: dict, tol: dict) -> None:
    for k, lim in tol.items():
        name, unit = _LABELS[k]
        verdict = "в допуске" if worst[k] <= lim else "ВНЕ ДОПУСКА"
        print(f"  {name:11s} = {worst[k]:<10.4g} допуск {lim:<7g} {unit:10s} {verdict}")


def report_and_plot(history, grid, output_dir: Path, title: str) -> None:
    """Прототип на книге BOOK и эталон IMEX (если применим): сводка в консоль, рисунки сравнения."""
    print("\n── Сверка с прототипом: та же книга, штатный путь run_workbook ──")
    summary = run_prototype(BOOK, output_dir / "prototype")
    proto = load_prototype(output_dir / "prototype")
    days = sorted(t for t in proto if t > 0.0)   # t = 0 — начальное состояние, у обоих одно
    print(f"  отметок {len(days)} — все строки SCHEDULE; прототип: шагов "
          f"{summary['accepted_steps']}, отказов {summary['rejected_steps']}")
    _report(compare(history, proto, days), TOL_PROTOTYPE)
    for w in summary["warnings"]:
        print(f"  предупреждение прототипа: {w}")

    print("\n── Сверка с CMG IMEX, кейс T07: отметки 1–30 сут ──")
    imex = None
    if imex_applicable(BOOK):
        imex = load_imex()
        print("  приёмка прототипа авторами: Δp 0.137 бар, ΔS_g 0.0046, RMSE 0.0023, "
              "ΔR_s 0.045, q_o 0.51 %, q_g 2.52 %, GOR 2.56 %")
        _report(compare(history, imex, STABLE_DAYS), TOL_IMEX)
    else:
        print(f"  {BOOK.name}: MODEL, таблицы или режимы скважины не те, что в T07.xlsx, "
              "— эталона IMEX нет")
    plot_comparison(history, grid, proto, imex, output_dir, title)


# ═══════════════════════════════════════════════════════════
# Рисунки сравнения
# ═══════════════════════════════════════════════════════════

# По отметке на каждый режим и конец расчёта: 150 бар — 1 сут, 120 — 6 сут, 100 — 16 и 30 сут.
PLOT_DAYS = (1.0, 6.0, 16.0, 30.0)


def plot_comparison(history, grid, proto: dict, imex: dict | None, output_dir: Path, title: str) -> None:
    """prototype_profiles.png (p, S_g, R_s по r) и prototype_rates.png (q_o, q_g, GOR по t): расчёт, прототип, IMEX."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from gpn_multiphase_solver.io.figures import save_figure

    # Все источники — по номеру ячейки; абсцисса — центры ячеек: у нашей
    # сетки и у прототипа они одни (DEBT-063)
    r = grid.r_centers

    # ── Профили ──
    # Цвет — момент времени (как на штатных профилях), источник — стиль линии:
    # расчёт — сплошная, прототип — пунктир, IMEX — кружки через 4 ячейки.
    fields = (("p", "p, бар"), ("Sg", "$S_g$"), ("Rs", "$R_s$, м³ст/м³ст"))
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7, 10))
    for k, d in enumerate(PLOT_DAYS):
        a, c = _ours(history, d), f"C{k}"
        for ax, (key, _) in zip(axes, fields):
            ax.semilogx(r, a[key], color=c, lw=1.5, label=f"t = {d:g} сут")
            ax.semilogx(r, proto[d][key], color=c, lw=1.2, ls="--")
            if imex is not None:
                ax.semilogx(r, imex[d][key], color=c, ls="none", marker="o",
                            mfc="none", ms=4, markevery=4)
    sources = [Line2D([], [], color="k", lw=1.5, label="расчёт"),
               Line2D([], [], color="k", lw=1.2, ls="--", label="прототип")]
    if imex is not None:
        sources.append(Line2D([], [], color="k", ls="none", marker="o", mfc="none",
                              label="CMG IMEX T07"))
    for ax, (_, label) in zip(axes, fields):
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.3)
    handles, _ = axes[0].get_legend_handles_labels()
    axes[0].legend(handles=handles + sources, fontsize=8)
    axes[-1].set_xlabel("r, м")
    axes[0].set_title(f"{title}\nПрофили: расчёт, прототип, IMEX")
    fig.tight_layout()
    save_figure(fig, output_dir / "prototype_profiles.png", dpi=110)
    plt.close(fig)

    # ── Дебиты и газовый фактор ──
    t_ours = np.asarray(history.times[1:]) / DAY   # запись 0 — начальное состояние, дебита нет
    w_ours = history.well_data[1:]
    ours = {"qo": [w.q_o_std * DAY for w in w_ours], "qg": [w.q_g_std * DAY for w in w_ours]}
    ours["GOR"] = np.asarray(ours["qg"]) / np.asarray(ours["qo"])
    t_proto = sorted(t for t in proto if t > 0.0)
    rate_fields = (("qo", "$q_o$, м³ст/сут"), ("qg", "$q_g$, м³ст/сут"), ("GOR", "GOR, м³ст/м³ст"))
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7, 9))
    for ax, (key, label) in zip(axes, rate_fields):
        ax.plot(t_ours, ours[key], color="C0", lw=1.5, marker=".", label="расчёт")
        ax.plot(t_proto, [proto[t][key] for t in t_proto], color="C1", lw=1.2, ls="--",
                marker="x", ms=5, label="прототип")
        if imex is not None:
            t_imex, v_imex = _imex_rates(key)
            ax.plot(t_imex, v_imex, color="C2", ls="none", marker="o", mfc="none", ms=4,
                    label="CMG IMEX T07")
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.3)
    # Дебиты — в логарифмической шкале: всплески после смен режима (в 5–15 раз)
    # иначе прижимают к оси основной уровень, на котором и идёт сверка.
    axes[0].set_yscale("log")
    axes[1].set_yscale("log")
    axes[0].legend(fontsize=8)
    axes[-1].set_xlabel("t, сут")
    axes[0].set_title(f"{title}\nДебиты: расчёт, прототип, IMEX")
    fig.tight_layout()
    save_figure(fig, output_dir / "prototype_rates.png", dpi=110)
    plt.close(fig)


def _imex_rates(key: str):
    """Ряд IMEX T07 по времени ("qo", "qg", "GOR" — имена столбцов файла) с отметки 1 мин."""
    # Первая строка файла (1e-6 сут) — мгновенный дебит пуска, 87 м³ст/сут нефти:
    # у расчёта записи с дебитом в этот момент нет, а шкалу точка растягивает.
    with open(IMEX_DIR / "T07_rates.csv", newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if float(r["time_day"]) > 1e-4]
    return [float(r["time_day"]) for r in rows], [float(r[key]) for r in rows]


if __name__ == "__main__":
    convert(BOOK, HERE)
    print(f"{BOOK.name} → {HERE}: config.json, oil_pvt.csv, gas_pvt.csv, relperm.csv")
