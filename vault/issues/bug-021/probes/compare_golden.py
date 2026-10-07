"""BUG-021: разбор расхождения выхода регрессии прототипа с эталоном golden/ (как в DEBT-029).

По каждому расчёту: число принятых/отклонённых шагов, первая различающаяся строка step_log.csv,
на каждом моменте отчёта max|Δp| (бар), max|ΔS_g|, max|ΔR_s| по профилям и относительные Δq_o,
Δq_g, ΔGOR (%) по дебитам. Для T05 внешнего эталона IMEX нет — это исследование сходимости;
сдвиг метрик regression/evidence/T05_final_metrics_20260825a.json не больше max|Δ| здесь
(неравенство треугольника).

Запуск — из любого каталога:
    <python> <P>\\compare_golden.py <каталог OUTPUT\\REGRESSION_...> <каталог regression\\golden> <кейс> [кейс ...]
Кейс T05 — по пути T05\\<имя>, остальные — по имени.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sub(case):
    return Path("T05") / case if case.startswith("T05") else Path(case)


def compare(out_root, gold_root, case):
    o, g = out_root / sub(case), gold_root / sub(case)
    so = json.loads((o / "run_summary.json").read_text(encoding="utf-8"))
    sg = json.loads((g / "run_summary.json").read_text(encoding="utf-8"))
    print(f"=== {case}: шагов принято {sg['accepted_steps']} -> {so['accepted_steps']}, "
          f"отклонено {sg['rejected_steps']} -> {so['rejected_steps']}")
    lo, lg = rows(o / "step_log.csv"), rows(g / "step_log.csv")
    # Последовательность шагов — время, dt, принят. Итерации и невязку отклонённых строк
    # не сверяем: после BUG-014 их пишет последняя ветка скважины (DEBT-030)
    seq = ("time_s_or_start", "dt_s", "accepted")
    first = next((i for i, (a, b) in enumerate(zip(lg, lo)) if any(a[k] != b[k] for k in seq)), None)
    if first is None and len(lo) == len(lg):
        print("  step_log.csv: последовательность шагов совпадает")
    else:
        i = first if first is not None else min(len(lo), len(lg))
        print(f"  step_log.csv: последовательность шагов расходится со строки {i + 2} (с заголовком)")
        for name, src in (("эталон", lg), ("сейчас", lo)):
            for r in src[max(i - 2, 0):i + 3]:
                print(f"    {name}: " + ", ".join(f"{k}={r[k]}" for k in seq + ("newton_iterations", "residual_inf")))
    po, pg = defaultdict(list), defaultdict(list)
    for r in rows(o / "profiles.csv"):
        po[r["time_day"]].append(r)
    for r in rows(g / "profiles.csv"):
        pg[r["time_day"]].append(r)
    ro = {r["time_day"]: r for r in rows(o / "rates.csv")}
    rg = {r["time_day"]: r for r in rows(g / "rates.csv")}
    print(f"  {'сут':>10} {'max|Δp|, бар':>13} {'max|ΔSg|':>10} {'max|ΔRs|':>10} "
          f"{'Δq_o, %':>9} {'Δq_g, %':>9} {'ΔGOR, %':>9}")
    for t in pg:
        a, b = pg[t], po.get(t, [])
        if len(a) != len(b):
            print(f"  {float(t):10.6g}  число ячеек {len(a)} -> {len(b)}")
            continue
        dp = max(abs(float(x["pressure_bar"]) - float(y["pressure_bar"])) for x, y in zip(a, b))
        ds = max(abs(float(x["Sg"]) - float(y["Sg"])) for x, y in zip(a, b))
        dr = max(abs(float(x["Rs"]) - float(y["Rs"])) for x, y in zip(a, b))
        rel = []
        for k in ("oil_rate_sm3_day", "gas_rate_sm3_day", "GOR_sm3_sm3"):
            x, y = float(rg[t][k]), float(ro[t][k])
            rel.append(100.0 * (y - x) / x if x else float("nan"))
        print(f"  {float(t):10.6g} {dp:13.3e} {ds:10.3e} {dr:10.3e} {rel[0]:9.2e} {rel[1]:9.2e} {rel[2]:9.2e}")


if __name__ == "__main__":
    out_root, gold_root = Path(sys.argv[1]), Path(sys.argv[2])
    for c in sys.argv[3:]:
        compare(out_root, gold_root, c)
