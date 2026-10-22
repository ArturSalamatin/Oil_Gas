"""Проба планирования FEAT-033: все ячейки книг .xlsx с адресом, типом и значением.

Читает zip/XML стандартной библиотекой: листы, общие строки, проверки
данных, защиту листа. Книги: черновик руководителя (вне git), книга
прототипа INPUT_TEMPLATE.xlsx и T08c.xlsx (ветвь R_s = 60).

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-033/probes/dump_workbooks.py
Вывод: dump_workbooks.out.txt рядом со скриптом.
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOLVER = ROOT / "numerical_solver"
BOOKS = [
    SOLVER / "configs" / "INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx",
    SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3" / "INPUT_TEMPLATE.xlsx",
    SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3" / "regression" / "inputs" / "T08c.xlsx",
]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def shared_strings(z):
    """Список общих строк (sharedStrings.xml), текст всех <t> элемента <si>."""
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t"))
            for si in root.findall("m:si", NS)]


def sheet_paths(z):
    """[(имя листа, путь XML)] в порядке книги."""
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels.findall(f"{REL_NS}Relationship")}
    out = []
    for s in wb.find("m:sheets", NS).findall("m:sheet", NS):
        rid = s.get(f"{{{NS['r']}}}id")
        t = target[rid].lstrip("/")
        out.append((s.get("name"), t if t.startswith("xl/") else "xl/" + t))
    return out


def dump(path, out):
    print(f"\n######## {path.relative_to(ROOT)}", file=out)
    with zipfile.ZipFile(path) as z:
        ss = shared_strings(z)
        for name, xml_path in sheet_paths(z):
            root = ET.fromstring(z.read(xml_path))
            print(f"\n=== Лист {name} ({xml_path})", file=out)
            prot = root.find("m:sheetProtection", NS)
            if prot is not None:
                print(f"  защита: {prot.attrib}", file=out)
            for row in root.iter(f"{{{NS['m']}}}row"):
                cells = []
                for c in row.findall("m:c", NS):
                    t = c.get("t", "n")
                    v = c.find("m:v", NS)
                    f = c.find("m:f", NS)
                    if t == "s" and v is not None:
                        val = repr(ss[int(v.text)])
                    elif t == "inlineStr":
                        val = repr("".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t")))
                    else:
                        val = v.text if v is not None else "<пусто>"
                    extra = f" f={f.text!r}" if f is not None else ""
                    if v is None and f is None and t != "inlineStr":
                        continue          # ячейка только со стилем
                    cells.append(f"{c.get('r')}[{t},s{c.get('s', '0')}]={val}{extra}")
                if cells:
                    print("  " + " | ".join(cells), file=out)
            dvs = root.find("m:dataValidations", NS)
            if dvs is not None:
                for dv in dvs.findall("m:dataValidation", NS):
                    f1 = dv.find("m:formula1", NS)
                    print(f"  проверка данных: {dv.attrib} formula1="
                          f"{f1.text if f1 is not None else None!r}", file=out)
            merged = root.find("m:mergeCells", NS)
            if merged is not None:
                print("  объединения: " + ", ".join(m.get("ref") for m in merged), file=out)
        comments = [n for n in z.namelist() if "comments" in n]
        if comments:
            print(f"\n  примечания ячеек: {comments}", file=out)


def main():
    out_path = Path(__file__).with_suffix(".out.txt")
    with open(out_path, "w", encoding="utf-8") as out:
        print(f"python {sys.version.split()[0]}", file=out)
        for b in BOOKS:
            dump(b, out)
    print(out_path)


if __name__ == "__main__":
    main()
