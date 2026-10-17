"""Проба FEAT-034: какой XML пишет XlsxWriter на ловушки разбора и как устроены книги в git.

Запуск из корня проекта:
    numerical_solver/.venv/Scripts/python "vault/issues/feat-034/probes/xlsxwriter_xml.py"
Вывод — xlsxwriter_xml.out.txt рядом (печать в консоль).
"""

import datetime as dt
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import xlsxwriter

HERE = Path(__file__).resolve().parent


def cells(xml: str) -> list[str]:
    return re.findall(r"<c [^>]*?(?:/>|>.*?</c>)", xml, re.S)


def show(path: Path, member: str = "xl/worksheets/sheet1.xml") -> None:
    with zipfile.ZipFile(path) as z:
        for c in cells(z.read(member).decode()):
            print("   ", c)


# Книги пробы — в папке пробы (не во временном каталоге системы), удаляются в конце
tmp = HERE / "_xlsxwriter_xml"
tmp.mkdir(exist_ok=True)

# ── 1. Ловушки одного листа ──
p = tmp / "traps.xlsx"
wb = xlsxwriter.Workbook(p)
ws = wb.add_worksheet("T")
d14 = wb.add_format({"num_format": 14})                # встроенный формат даты
d16 = wb.add_format({"num_format": 16})                # встроенный d-mmm
dcust = wb.add_format({"num_format": "dd.mm.yyyy"})    # пользовательский
ws.write_formula("A1", "=1/3")                         # значение не передано
ws.write_formula("A2", "=1/0", None, "#DIV/0!")
ws.write_formula("A3", '=""', None, "")
ws.write_formula("A4", '="x"', None, "abc")
ws.write_formula("A5", "=1>0", None, True)
ws.write_boolean("A6", True)
ws.write_boolean("A7", False)
ws.write_datetime("A8", dt.datetime(2026, 5, 1), d14)
ws.write_number("A9", 46143, d16)
ws.write_datetime("A10", dt.datetime(2026, 5, 1, 12), dcust)
ws.write_string("A11", "1,5")
ws.write_string("A12", "  BHP ")
ws.write_string("A13", "a\x01b")                       # управляющий символ
ws.write_number("A14", 1.0451463166781947)
ws.write_rich_string("A15", "ab", wb.add_format({"bold": True}), "cd")
ws.write_blank("A16", None, d14)                       # стиль без значения
ws.write_number("C20", 7)                              # неровная строка, пропуск строк
ws.write_formula("A17", "=1/3", None, 0.333)
ws.write_array_formula("A18:A18", "{=SUM(A9:A9)}", None, 46143)
hid = wb.add_worksheet("H")
hid.hide()
wb.close()
print("1. Ловушки XlsxWriter", xlsxwriter.__version__)
show(p)
with zipfile.ZipFile(p) as z:
    wbx = z.read("xl/workbook.xml").decode()
    print("   workbook:", re.findall(r"<sheet [^>]*/>|<calcPr[^>]*/>", wbx))
    st = z.read("xl/styles.xml").decode()
    print("   numFmts:", re.findall(r"<numFmt [^>]*/>", st))
    print("   cellXfs:", re.findall(r'<xf numFmtId="(\d+)"', re.search(r"<cellXfs.*?</cellXfs>", st, re.S).group(0)))
    print("   sharedStrings:", z.read("xl/sharedStrings.xml").decode()[-400:])

# ── 2. constant_memory: общие или встроенные строки ──
p2 = tmp / "cm.xlsx"
wb = xlsxwriter.Workbook(p2, {"constant_memory": True})
ws = wb.add_worksheet("T")
ws.write_string("A1", "inline?")
wb.close()
print("2. constant_memory")
show(p2)
with zipfile.ZipFile(p2) as z:
    print("    sharedStrings.xml в книге:", "xl/sharedStrings.xml" in z.namelist())

# ── 3. Пути частей книг в git: _rels/.rels и workbook.xml.rels ──
print("3. Пути частей")
files = subprocess.run(["git", "ls-files", "*.xlsx"], capture_output=True, text=True).stdout.split()
seen = {}
for f in files:
    with zipfile.ZipFile(f) as z:
        rels = z.read("_rels/.rels").decode()
        office = re.findall(r'Target="([^"]+)"[^>]*Type="[^"]*officeDocument"|Type="[^"]*officeDocument"[^>]*Target="([^"]+)"', rels)
        wrels = z.read("xl/_rels/workbook.xml.rels").decode()
        sheets = re.findall(r'Target="([^"]*worksheets[^"]*)"', wrels)[:1]
        styles = re.findall(r'Target="([^"]*styles[^"]*)"', wrels)
        key = (str(office), str(sheets[:1]).replace(re.sub(r"\D", "", str(sheets[:1])) or "#", "#"), str(styles))
        seen.setdefault(key, []).append(Path(f).name)
for k, v in seen.items():
    print("   ", k, len(v), v[:2])

shutil.rmtree(tmp)
