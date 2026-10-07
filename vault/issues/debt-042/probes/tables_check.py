r"""DEBT-042: 47 CSV-таблиц проекта — правила строгого разбора и снимок результата ридеров.

Запуск из numerical_solver/:
  .venv\Scripts\python ..\vault\issues\debt-042\probes\tables_check.py            # правила + снимок
  .venv\Scripts\python ..\vault\issues\debt-042\probes\tables_check.py --compare  # сверка ридеров со снимком

Снимок — tables_snapshot.json рядом со скриптом: выход текущих ридеров фабрики
(float в JSON записываются repr-ом, чтение обратно побитовое).
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree). Путь от расположения пробы указал бы на основной каталог:
# vault/issues/ в .gitignore, в worktree проб нет, и сверка шага 4 плана
# проверила бы неизменённый код основного каталога (аудит DEBT-042).
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver import factory                         # noqa: E402
from gpn_multiphase_solver.factory import (                      # noqa: E402
    _read_oil_pvt_csv, _read_gas_pvt_csv, _read_relperm_csv,
)

print(f"Код: {Path(factory.__file__).resolve()}")

SNAPSHOT = Path(__file__).resolve().parent / "tables_snapshot.json"
EXPECTED = {
    "oil_pvt.csv": ["Rs_sm3_sm3", "pressure_Pa", "Bo", "mu_o_Pa_s"],
    "gas_pvt.csv": ["pressure_Pa", "Bg", "mu_g_Pa_s"],
    "relperm.csv": ["Sg", "kro", "krg"],
}
READERS = {"oil_pvt.csv": _read_oil_pvt_csv, "gas_pvt.csv": _read_gas_pvt_csv,
           "relperm.csv": _read_relperm_csv}
SKIP_DIRS = {".venv", "HydroSolverPrototype", ".worktrees", ".pytest_cache"}


def tables():
    out = []
    for name in EXPECTED:
        for p in SOLVER.rglob(name):
            if not SKIP_DIRS & set(p.relative_to(SOLVER).parts):
                out.append(p)
    return sorted(out)


def strict_violations(path):
    """Нарушения правил плана DEBT-042 (имена заголовка, число полей, конечные числа)."""
    raw = path.read_bytes()
    issues = []
    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append("BOM")
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None or [h.strip() for h in header] != EXPECTED[path.name]:
            issues.append(f"заголовок {header}")
        for line in reader:
            if not any(s.strip() for s in line):
                continue
            if len(line) != len(EXPECTED[path.name]):
                issues.append(f"строка {reader.line_num}: {len(line)} полей")
                continue
            try:
                vals = [float(s) for s in line]
            except ValueError:
                issues.append(f"строка {reader.line_num}: не число {line}")
                continue
            if not np.all(np.isfinite(vals)):
                issues.append(f"строка {reader.line_num}: не конечное {line}")
    return issues


def read_all():
    return {str(p.relative_to(SOLVER)).replace("\\", "/"): READERS[p.name](p) for p in tables()}


def to_json(data):
    return {k: [list(r) for r in v] for k, v in data.items()}


if __name__ == "__main__":
    paths = tables()
    counts = {n: sum(p.name == n for p in paths) for n in EXPECTED}
    print(f"Таблиц: {len(paths)} {counts}")
    data = to_json(read_all())
    if "--compare" in sys.argv:
        ref = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        diff = sorted(set(ref) ^ set(data)) + [k for k in ref if k in data and ref[k] != data[k]]
        print("Сверка со снимком:", "побитово совпадает" if not diff else f"РАСХОЖДЕНИЯ: {diff}")
        sys.exit(1 if diff else 0)
    n_bad = 0
    for p in paths:
        v = strict_violations(p)
        if v:
            n_bad += 1
            print(f"  {p.relative_to(SOLVER)}: {v}")
    print(f"Нарушают правила строгого разбора: {n_bad} из {len(paths)}")
    SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    n_rows = sum(len(v) if not k.endswith("relperm.csv") else len(v[0]) for k, v in data.items())
    print(f"Снимок: {SNAPSHOT.name}, {len(data)} таблиц, {n_rows} строк данных")
