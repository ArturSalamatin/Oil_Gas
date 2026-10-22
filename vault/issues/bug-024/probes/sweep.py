"""BUG-024: серия прогонов stage4_failure.py — проходит ли суточный останов при малых возмущениях траектории.

Каждый прогон — отдельный процесс (окружение задаёт опыт); итоговые строки собираются
в sweep_<набор>.out.txt рядом со скриптом.
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\sweep.py perturb
"""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
SETS = {
    # возмущения траектории на сценарии 20B, 1 сут, max_retries = 9
    "perturb": [
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "none", "BUG024_ATOL": "2e-11"}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "none", "BUG024_ATOL": "5e-12"}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "1e-7"}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "1e-9"}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "1e-5"}),
    ],
    # сценарии DEBT-015 при 1 сут на коде после BUG-022 (newton_cell_tol = 1e-8)
    "debt015": [
        ("19 10 3 B 86400", {}),
        ("21 10 3 B 86400", {}),
        ("20 10 3 A 86400", {}),
    ],
    # вариант satrel (|dR_s| <= 0.2 R_s^sat): те же возмущения и сценарии DEBT-015 — устойчиво ли
    "satrel": [
        ("20 10 3 B 86400", {"BUG024_VARIANT": "satrel", "BUG024_CELL_TOL": "1e-6"}),
        ("20 10 3 B 86400", {"BUG024_VARIANT": "satrel", "BUG024_CELL_TOL": "1e-7"}),
        ("20 10 3 B 86400", {"BUG024_VARIANT": "satrel", "BUG024_CELL_TOL": "1e-9"}),
        ("20 10 3 B 86400", {"BUG024_VARIANT": "satrel", "BUG024_CELL_TOL": "none"}),
        ("20 10 3 B 86400", {"BUG024_VARIANT": "satrel", "BUG024_CELL_TOL": "none", "BUG024_ATOL": "5e-12"}),
        ("19 10 3 B 86400", {"BUG024_VARIANT": "satrel"}),
        ("21 10 3 B 86400", {"BUG024_VARIANT": "satrel"}),
        ("20 10 3 A 86400", {"BUG024_VARIANT": "satrel"}),
        ("20 10 3 B 3600", {"BUG024_VARIANT": "satrel"}),
        ("20 10 3 B 3600", {}),
    ],
    # код ветки BUG-024 (ограничение уже в коде, подмены нет): те же сценарии, что "satrel"
    "branch": [
        ("20 10 3 B 86400", {}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "1e-6"}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "1e-7"}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "1e-9"}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "none"}),
        ("20 10 3 B 86400", {"BUG024_CELL_TOL": "none", "BUG024_ATOL": "5e-12"}),
        ("19 10 3 B 86400", {}),
        ("21 10 3 B 86400", {}),
        ("20 10 3 A 86400", {}),
        ("20 10 3 B 3600", {}),
    ],
    # лимит итераций ступени 4 (гипотеза «не хватает 40 итераций»)
    "maxiter": [
        ("20 10 3 B 86400", {"BUG024_MAX_ITER4": "80"}),
        ("20 10 3 B 86400", {"BUG024_MAX_ITER4": "200"}),
    ],
}


def main(name):
    out = open(HERE / f"sweep_{name}.out.txt", "w", encoding="utf-8")
    for args, env in SETS[name]:
        tag = "_" + "_".join(f"{k[7:].lower()}{v}" for k, v in env.items()) if env else "_base"
        tag = f"_{name}{tag}"
        e = dict(os.environ, BUG024_DETAIL="0", BUG024_TAG=tag, **env)
        # опыт задаёт только env набора: переменные, оставшиеся в окружении оболочки, убираются
        for k in ("BUG024_T_STOP", "BUG024_DETAIL_ALL", "BUG024_VARIANT", "BUG024_CELL_TOL", "BUG024_ATOL",
                  "BUG024_MAX_ITER4", "BUG024_MAX_RETRIES", "BUG024_DR"):
            if k not in env:
                e.pop(k, None)
        r = subprocess.run([PY, str(HERE / "stage4_failure.py"), *args.split()], env=e,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("итог", "решений", "==="))]
        if r.returncode:
            lines.append("ОШИБКА: " + r.stderr[-400:])
        out.write(f"## {args} {env}\n" + "\n".join(lines) + "\n\n")
        out.flush()
        print(f"## {args} {env}", *lines, sep="\n", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
