"""DEBT-030: сверка step_log.csv выхода регрессии прототипа с эталоном golden/.

Для каждого расчёта, найденного в каталоге выхода, печатает:
  - совпадает ли файл с эталоном побайтно;
  - число строк, где различаются время, шаг, флаг принятия или целые колонки
    (newton_iterations, active_set_iterations, phase_switches);
  - число строк, где различается только residual_inf (округление: эталон 11 расчётов
    снят авторами в другой среде, невязки сошедшихся шагов ~1e-16 расходятся везде);
  - отклонённые строки выхода и эталона, если они различаются.

Запуск из numerical_solver/HydroSolverPrototype/Prototype_1.0.3:
    ..\\..\\.venv\\Scripts\\python <путь>\\compare_step_logs.py OUTPUT\\REGRESSION_<время>
"""
import csv
import sys
from pathlib import Path

GOLDEN = Path.cwd() / "regression" / "golden"
INT_COLS = ("time_s_or_start", "dt_s", "accepted", "newton_iterations",
            "active_set_iterations", "phase_switches")


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(out_dir):
    out_dir = Path(out_dir)
    for new_path in sorted(out_dir.rglob("step_log.csv")):
        rel = new_path.parent.relative_to(out_dir)
        gold_path = GOLDEN / rel / "step_log.csv"
        same_bytes = new_path.read_bytes() == gold_path.read_bytes()
        a, b = rows(new_path), rows(gold_path)
        print(f"{str(rel):22s} байт-в-байт: {same_bytes!s:5s} строк: {len(a)}/{len(b)}", end="")
        if len(a) != len(b):
            print("  ЧИСЛО СТРОК РАЗНОЕ")
            continue
        int_diff = [i for i, (x, y) in enumerate(zip(a, b)) if any(x[c] != y[c] for c in INT_COLS)]
        res_only = sum(1 for i, (x, y) in enumerate(zip(a, b))
                       if i not in int_diff and x["residual_inf"] != y["residual_inf"])
        print(f"  целые колонки различаются: {len(int_diff)}, только residual_inf: {res_only}")
        rej = [i for i, x in enumerate(a) if x["accepted"] == "False"]
        changed = [i for i in rej if a[i] != b[i]]
        for i in changed:
            fa = [a[i][c] for c in INT_COLS[1:]] + [a[i]["residual_inf"]]
            fb = [b[i][c] for c in INT_COLS[1:]] + [b[i]["residual_inf"]]
            print(f"   строка {i + 2}: выход  {','.join(fa)}")
            print(f"   {'':{len(str(i + 2)) + 7}} эталон {','.join(fb)}")


if __name__ == "__main__":
    main(sys.argv[1])
