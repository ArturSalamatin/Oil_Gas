"""Чтение книги .xlsx в тестах стандартной библиотекой (FEAT-033).

Значения ячеек, стили, проверки данных и защита листа — то, что пишет генератор
шаблона (io/workbook_template.py). Не разборщик книги для пользователя (FEAT-034).
"""

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass
class Sheet:
    """Лист: значения (адрес → float | str), стили ячеек, проверки данных, защита."""
    values: dict = field(default_factory=dict)
    styles: dict = field(default_factory=dict)       # адрес → индекс стиля cellXfs
    row_styles: dict = field(default_factory=dict)   # номер строки → стиль строки (customFormat)
    validations: list = field(default_factory=list)  # атрибуты <dataValidation> + formula1
    protection: dict | None = None                   # атрибуты <sheetProtection>; None — нет


@dataclass
class Book:
    """Книга: листы в порядке книги и стили без блокировки."""
    sheets: dict
    unlocked: set

    def locked(self, sheet: str, addr: str) -> bool:
        """Заблокирована ли ячейка; ячейка без стиля — стиль 0, заблокирована (как в Excel)."""
        return self.sheets[sheet].styles.get(addr, 0) not in self.unlocked

    def row_unlocked(self, sheet: str, row: int) -> bool:
        """Разблокирована ли строка целиком — формат строки без блокировки."""
        style = self.sheets[sheet].row_styles.get(row)
        return style is not None and style in self.unlocked


def read_book(path: Path) -> Book:
    """Прочитать книгу path: листы, значения, стили, проверки данных, защиту."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{_M}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_M}t")))
        xfs = ET.fromstring(z.read("xl/styles.xml")).find(f"{_M}cellXfs")
        unlocked = set()
        for i, xf in enumerate(xfs):
            prot = xf.find(f"{_M}protection")
            if prot is not None and prot.get("locked") == "0":
                unlocked.add(i)
        rels = {r.get("Id"): r.get("Target") for r in
                ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(f"{_PR}Relationship")}
        sheets = {}
        for s in ET.fromstring(z.read("xl/workbook.xml")).iter(f"{_M}sheet"):
            target = rels[s.get(f"{_R}id")].lstrip("/")
            root = ET.fromstring(z.read(target if target.startswith("xl/") else "xl/" + target))
            sh = Sheet()
            for row in root.iter(f"{_M}row"):
                # Формат всей строки: им Excel оформляет и пустые ячейки строки
                if row.get("customFormat") == "1":
                    sh.row_styles[int(row.get("r"))] = int(row.get("s", "0"))
            for c in root.iter(f"{_M}c"):
                sh.styles[c.get("r")] = int(c.get("s", "0"))
                v = c.find(f"{_M}v")
                if v is not None:
                    sh.values[c.get("r")] = (shared[int(v.text)] if c.get("t") == "s"
                                             else float(v.text))
            for dv in root.iter(f"{_M}dataValidation"):
                f1 = dv.find(f"{_M}formula1")
                sh.validations.append({**dv.attrib, "formula1": None if f1 is None else f1.text})
            prot = root.find(f"{_M}sheetProtection")
            sh.protection = None if prot is None else dict(prot.attrib)
            sheets[s.get("name")] = sh
    return Book(sheets, unlocked)
