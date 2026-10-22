"""Проба VAL-005: содержимое входных книг прототипа (INPUT_TEMPLATE, регрессия T00–T11)."""
import sys
from pathlib import Path

SOLVER = Path.cwd()  # запускать из numerical_solver/
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
sys.path.insert(0, str(PROTO))
print("PROTO =", PROTO)

from radial_blackoil.xlsxio import read_workbook_tables  # noqa: E402


def dump_full(path):
    """Все листы книги целиком."""
    print(f"\n==================== {path.relative_to(PROTO)} ====================")
    for name, rows in read_workbook_tables(path).items():
        print(f"\n--- {name} ({len(rows)} строк) ---")
        for r in rows:
            print(" | ".join("" if x is None else str(x) for x in r))


def model_params(path):
    """Лист MODEL → {параметр: значение}."""
    rows = read_workbook_tables(path)["MODEL"]
    h = [str(x).strip() if x is not None else "" for x in rows[0]]
    ip, iv = h.index("Parameter"), h.index("Value")
    return {str(r[ip]).strip(): r[iv] for r in rows[1:] if len(r) > iv and r[ip] not in (None, "")}


dump_full(PROTO / "INPUT_TEMPLATE.xlsx")

# ── Регрессионные кейсы: различия MODEL и размеры таблиц ──
cases = sorted((PROTO / "regression" / "inputs").glob("*.xlsx"))
base = model_params(PROTO / "INPUT_TEMPLATE.xlsx")
print("\n==================== Регрессия: отличия MODEL от INPUT_TEMPLATE ====================")
for c in cases:
    p = model_params(c)
    diff = {k: v for k, v in p.items() if base.get(k) != v}
    sh = read_workbook_tables(c)
    sizes = {s: len(sh[s]) - 1 for s in ("SCHEDULE", "OIL_PVT", "GAS_PVT", "RELPERM")}
    print(f"\n{c.name}: таблицы {sizes}")
    for k, v in diff.items():
        print(f"    {k}: {base.get(k)} -> {v}")
    print("    SCHEDULE:")
    for r in sh["SCHEDULE"]:
        print("     ", " | ".join("" if x is None else str(x) for x in r))

# ── Совпадают ли PVT-таблицы кейсов с шаблоном ──
print("\n==================== Совпадение таблиц с INPUT_TEMPLATE ====================")
tb = read_workbook_tables(PROTO / "INPUT_TEMPLATE.xlsx")
for c in cases:
    sh = read_workbook_tables(c)
    same = {s: sh[s] == tb[s] for s in ("OIL_PVT", "GAS_PVT", "RELPERM")}
    print(f"{c.name}: {same}")

# ── T08c — расширенная PVTO целиком ──
t08 = PROTO / "regression" / "inputs" / "T08c.xlsx"
print("\n==================== T08c OIL_PVT ====================")
for r in read_workbook_tables(t08)["OIL_PVT"]:
    print(" | ".join("" if x is None else str(x) for x in r))
