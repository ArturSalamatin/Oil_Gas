"""Проба планирования FEAT-033: таблицы черновика руководителя против книг прототипа в git.

Черновик (configs/INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx) в git не
коммитится (решение 56 плана). Демонстрационные таблицы книги берутся из
файлов в git: проверяем, что листы MODEL, SCHEDULE, OIL_PVT, GAS_PVT, RELPERM
черновика побитово равны INPUT_TEMPLATE.xlsx прототипа, а OIL_PVT T08c —
таблице черновика плюс ветвь R_s = 60. Печатает таблицы как литералы Python
(repr) — источник для демонстрационных данных пакета.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-033/probes/compare_tables.py
Вывод: compare_tables.out.txt рядом со скриптом.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dump_workbooks import NS, ROOT, SOLVER, shared_strings, sheet_paths  # noqa: E402

import zipfile                                 # noqa: E402
import xml.etree.ElementTree as ET             # noqa: E402

DRAFT = SOLVER / "configs" / "INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx"
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
TEMPLATE = PROTO / "INPUT_TEMPLATE.xlsx"
T08C = PROTO / "regression" / "inputs" / "T08c.xlsx"


def cells(path):
    """{лист: {адрес: значение}}; число — float, строка — str."""
    out = {}
    with zipfile.ZipFile(path) as z:
        ss = shared_strings(z)
        for name, xml_path in sheet_paths(z):
            root = ET.fromstring(z.read(xml_path))
            d = {}
            for c in root.iter(f"{{{NS['m']}}}c"):
                t = c.get("t", "n")
                v = c.find("m:v", NS)
                if t == "inlineStr":
                    d[c.get("r")] = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                elif v is None:
                    continue
                elif t == "s":
                    d[c.get("r")] = ss[int(v.text)]
                elif t in ("str", "e"):
                    d[c.get("r")] = v.text
                else:
                    d[c.get("r")] = float(v.text)
            out[name] = d
    return out


def rows(sheet, ncol):
    """Строки данных листа-таблицы (со 2-й) как кортежи значений столбцов A.."""
    cols = "ABCDE"[:ncol]
    n = max(int("".join(ch for ch in a if ch.isdigit())) for a in sheet)
    return [tuple(sheet.get(f"{c}{i}") for c in cols) for i in range(2, n + 1)]


def main():
    out_path = Path(__file__).with_suffix(".out.txt")
    draft, tmpl, t08c = cells(DRAFT), cells(TEMPLATE), cells(T08C)
    with open(out_path, "w", encoding="utf-8") as out:
        for sheet in ("MODEL", "SCHEDULE", "OIL_PVT", "GAS_PVT", "RELPERM"):
            a, b = draft[sheet], tmpl[sheet]
            diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            print(f"{sheet}: черновик vs INPUT_TEMPLATE — различий {len(diff)}"
                  + (f": {[(k, a.get(k), b.get(k)) for k in diff]}" if diff else ""), file=out)
        oil_d, oil_t = rows(draft["OIL_PVT"], 4), rows(t08c["OIL_PVT"], 4)
        same = oil_t[:len(oil_d)] == oil_d
        print(f"OIL_PVT: T08c[:{len(oil_d)}] == черновик — {same}; строк T08c {len(oil_t)}, "
              f"ветвь 60: {oil_t[len(oil_d):]}", file=out)
        for sheet in ("GAS_PVT", "RELPERM"):
            print(f"{sheet}: T08c == INPUT_TEMPLATE — {t08c[sheet] == tmpl[sheet]}", file=out)
        print("\n# Литералы (repr) — OIL_PVT T08c: (Rs, p_bar, Bo, mu_cP)", file=out)
        for r in oil_t:
            print(f"    ({', '.join(repr(x) for x in r)}),", file=out)
        print("\n# GAS_PVT INPUT_TEMPLATE: (p_bar, Bg, mu_cP)", file=out)
        for r in rows(tmpl["GAS_PVT"], 3):
            print(f"    ({', '.join(repr(x) for x in r)}),", file=out)
        print("\n# RELPERM INPUT_TEMPLATE: (Sg, kro, krg)", file=out)
        for r in rows(tmpl["RELPERM"], 3):
            print(f"    ({', '.join(repr(x) for x in r)}),", file=out)
        print("\n# SCHEDULE черновика: (t_day, mode, BHP, q_oil, min_BHP)", file=out)
        for r in rows(draft["SCHEDULE"], 5):
            print(f"    ({', '.join(repr(x) for x in r)}),", file=out)
    print(out_path)


if __name__ == "__main__":
    main()
