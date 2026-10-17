"""Разбор книги .xlsx стандартной библиотекой: ячейки с адресом, значением и типом (FEAT-034).

Разбор только сообщает, что лежит в ячейке: число, строка, логическое значение,
ошибка или пусто; число с форматом даты; формула и есть ли у неё сохранённое
значение. Что из этого допустимо в поле книги, решает перевод книги в конфиг
(FEAT-035). Защита листов, проверки данных и выпадающие списки Excel не читаются:
проверку данных обходит вставка из буфера обмена, поэтому все проверки — в переводе.
"""

from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

# ── Пространства имён (ECMA-376, переходный вариант — так сохраняет Excel) ──
_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
# Строгий вариант Open XML (Strict): тот же zip, другие пространства имён — без
# проверки разбор молча нашёл бы ноль листов
_STRICT_WORKBOOK = "{http://purl.oclc.org/ooxml/spreadsheetml/main}workbook"

# Составной файл OLE: так начинаются .xls и книга .xlsx с паролем на открытие
_OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")

_SAVE_AS = "Сохраните книгу в Excel как «Книга Excel (*.xlsx)»."

# ── Типы ячейки ──
NUMBER = "number"     # value — float: Excel хранит все числа вещественными
STRING = "string"     # value — str как в книге, пробелы не срезаются
BOOL = "bool"         # value — True / False
ERROR = "error"       # value — код ошибки Excel: "#DIV/0!", "#N/A", …
EMPTY = "empty"       # value — None: ячейки нет, она без значения или формула без значения

# Встроенные форматы даты и времени без кода в styles.xml (ECMA-376, часть 1,
# раздел numFmt): 14–22, 45–47; 27–36 и 50–58 — даты восточноазиатских языков.
# Excel с русскими настройками превращает ввод «1.5» в дату 1 мая — число 46143
# с форматом даты (встроенным или своим кодом с d, m)
_BUILTIN_DATE_FORMATS = frozenset([*range(14, 23), 45, 46, 47, *range(27, 37), *range(50, 59)])

# Части кода формата, которые не делают его датой: текст в кавычках, символ после
# «\» (литерал), «_» (отступ) и «*» (заполнение), скобки [Red], [$-419] — кроме
# прошедшего времени [h], [mm], [ss]
_FORMAT_LITERALS = re.compile(r'"[^"]*"|\\.|_.|\*.|\[(?!h+\]|m+\]|s+\])[^\]]*\]', re.I)
_DATE_LETTERS = re.compile(r"[dmyhs]", re.I)
_ESCAPED_CHAR = re.compile(r"_x([0-9A-Fa-f]{4})_")
_CELL_REF = re.compile(r"([A-Z]{1,3})([1-9][0-9]*)")


class WorkbookError(ValueError):
    """Файл не читается как книга .xlsx; сообщение — что не так и как пересохранить."""


@dataclass(frozen=True)
class Cell:
    """Ячейка листа: адрес, тип, значение, признаки даты и формулы."""
    sheet: str
    row: int                            # номер строки, с 1
    col: int                            # номер столбца, с 1: A = 1
    kind: str = EMPTY                   # NUMBER | STRING | BOOL | ERROR | EMPTY
    value: float | str | bool | None = None
    is_date: bool = False               # число с форматом даты или времени; t="d"
    # Текст формулы без «=»; "" — ячейка общей формулы (текст — у первой); None — не формула
    formula: str | None = None

    @property
    def address(self) -> str:
        """Адрес ячейки: C5."""
        return column_letters(self.col) + str(self.row)

    @property
    def ref(self) -> str:
        """Лист и адрес для сообщений: MODEL!C5."""
        return f"{self.sheet}!{self.address}"

    @property
    def formula_without_value(self) -> bool:
        """Формула без сохранённого значения: книгу не пересчитали в Excel."""
        return self.formula is not None and self.kind == EMPTY


@dataclass(frozen=True)
class Sheet:
    """Лист: ячейки со значением или формулой; остальные — пустые."""
    name: str
    cells: dict = field(default_factory=dict)       # (row, col) → Cell

    def cell(self, row: int, col: int) -> Cell:
        """Ячейка (row, col); не записанная в книге — пустая."""
        return self.cells.get((row, col)) or Cell(self.name, row, col)

    @property
    def max_row(self) -> int:
        """Последняя строка с непустой ячейкой; 0 — лист пуст."""
        return max((r for r, _ in self.cells), default=0)


@dataclass(frozen=True)
class Workbook:
    """Книга: листы в порядке книги."""
    path: Path
    sheets: dict                        # имя листа → Sheet
    # Пометка «пересчитать при открытии» (fullCalcOnLoad): её ставят XlsxWriter и
    # openpyxl, Excel при сохранении снимает. Значения формул такой книги не
    # читаются — formula_without_value (решение 9 плана)
    recalc_on_open: bool


def column_letters(col: int) -> str:
    """Номер столбца → буквы: 1 → A, 27 → AA, 16384 → XFD."""
    letters = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def is_date_format(code: str) -> bool:
    """Код формата числа — дата или время: d, m, y, h, s вне кавычек, [...] и экранирования."""
    # Только первый раздел: формат положительных чисел
    return _DATE_LETTERS.search(_FORMAT_LITERALS.sub("", code.split(";")[0])) is not None


def read_workbook(path) -> Workbook:
    """Прочитать книгу .xlsx: листы и ячейки с типами (FEAT-034)."""
    path = Path(path)
    with open(path, "rb") as f:                 # нет файла — FileNotFoundError, как у open
        head = f.read(len(_OLE_MAGIC))
    if head == _OLE_MAGIC:
        raise WorkbookError(
            f"{path}: не книга .xlsx — это файл .xls или книга с паролем на открытие. "
            f"{_SAVE_AS} Пароль на открытие не ставится.")
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise WorkbookError(f"{path}: не книга .xlsx — файл не zip-архив. {_SAVE_AS}") from None
    with z:
        return _read(path, z)


# ── Части книги ──

def _read(path: Path, z: zipfile.ZipFile) -> Workbook:
    """Книга из открытого архива: книга → связи → общие строки, стили → листы."""
    names = set(z.namelist())
    wb_part = _workbook_part(path, z, names)
    root = _xml(path, z, wb_part)
    if root.tag == _STRICT_WORKBOOK:
        raise WorkbookError(f"{path}: книга сохранена в строгом формате Open XML (Strict) — "
                            f"разбор его не читает. {_SAVE_AS}")
    if root.tag != f"{_M}workbook":
        raise WorkbookError(f"{path}: в архиве нет книги Excel ({wb_part}). {_SAVE_AS}")
    rels = _rels(path, z, wb_part, names)
    by_type = {rtype.rsplit("/", 1)[-1]: part for rtype, part in rels.values()}
    shared = _shared_strings(path, z, by_type.get("sharedStrings"))
    date_styles = _date_styles(path, z, by_type.get("styles"))
    calc = root.find(f"{_M}calcPr")
    recalc = calc is not None and calc.get("fullCalcOnLoad") in ("1", "true")
    sheets = {}
    sheets_el = root.find(f"{_M}sheets")
    for s in (sheets_el if sheets_el is not None else ()):
        name = s.get("name")
        rid = s.get(f"{_DOC_REL}id")
        if rid not in rels:
            raise WorkbookError(f"{path}: книга повреждена — у листа {name} нет части. {_SAVE_AS}")
        # Скрытые листы читаются как обычные (решение 6)
        sheets[name] = _sheet(path, z, name, rels[rid][1], shared, date_styles, recalc)
    return Workbook(path, sheets, recalc)


def _workbook_part(path: Path, z: zipfile.ZipFile, names: set) -> str:
    """Часть книги по связи officeDocument из _rels/.rels; .xlsb и не Excel — отказ."""
    if "_rels/.rels" in names:
        for r in _xml(path, z, "_rels/.rels").iter(f"{_PKG_REL}Relationship"):
            if r.get("Type", "").endswith("/officeDocument"):
                part = _part(names, "", r.get("Target", ""))
                if part.endswith(".bin"):
                    raise WorkbookError(f"{path}: двоичная книга Excel (.xlsb) — разбор её не "
                                        f"читает. {_SAVE_AS}")
                return part
    raise WorkbookError(f"{path}: в архиве нет книги Excel — возможно, это .ods, .docx или "
                        f"другой zip-архив. {_SAVE_AS}")


def _part(names: set, source: str, target: str) -> str:
    """Имя части по ссылке Target: абсолютной (/xl/…) или от каталога части source."""
    if target.startswith("/"):
        return target.lstrip("/")
    part = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
    # Цель «xl/…» от корня вместо пути от каталога части — так пишут не все
    # программы, но radial_blackoil.xlsxio такие книги читает; читаем и мы
    return target if part not in names and target in names else part


def _rels(path: Path, z: zipfile.ZipFile, part: str, names: set) -> dict:
    """Связи части: Id → (Type, имя части)."""
    rels_part = posixpath.join(posixpath.dirname(part), "_rels",
                               posixpath.basename(part) + ".rels")
    return {r.get("Id"): (r.get("Type", ""), _part(names, part, r.get("Target", "")))
            for r in _xml(path, z, rels_part).iter(f"{_PKG_REL}Relationship")
            if r.get("TargetMode") != "External"}


def _xml(path: Path, z: zipfile.ZipFile, part: str) -> ET.Element:
    """Корень XML части; нет части, испорчен XML или архив — WorkbookError."""
    try:
        return ET.fromstring(z.read(part))
    except KeyError:
        raise WorkbookError(f"{path}: книга повреждена — нет части {part}. {_SAVE_AS}") from None
    except ET.ParseError as exc:
        raise WorkbookError(f"{path}: книга повреждена — {part}: {exc}. {_SAVE_AS}") from None
    except (zipfile.BadZipFile, zlib.error, EOFError) as exc:
        raise WorkbookError(f"{path}: книга повреждена — {part} не распаковывается ({exc}). "
                            f"{_SAVE_AS}") from None


def _text(el: ET.Element) -> str:
    """Текст <si> или <is>: <t> и <t> в <r>; фонетика <rPh> не читается."""
    parts = []
    for child in el:
        if child.tag == f"{_M}t":
            parts.append(child.text or "")
        elif child.tag == f"{_M}r":
            parts.extend(t.text or "" for t in child.findall(f"{_M}t"))
    return _unescape("".join(parts))


def _unescape(s: str) -> str:
    """Символы, записанные как _xHHHH_ (управляющие; «_» перед x — как _x005F_)."""
    return _ESCAPED_CHAR.sub(lambda m: chr(int(m.group(1), 16)), s)


def _int(path: Path, text: str | None, what: str) -> int:
    """Целое из атрибута XML (номер строки, стиля, формата); иное — WorkbookError."""
    # Отказ разбора — всегда WorkbookError: голый ValueError (или TypeError на
    # отсутствующем атрибуте) вызывающий принял бы за ошибку кода (аудит 2)
    if text is None or not text.isdigit():
        raise WorkbookError(f"{path}: книга повреждена — {what}: {text!r} не целое. {_SAVE_AS}")
    return int(text)


def _shared_strings(path: Path, z: zipfile.ZipFile, part: str | None) -> list:
    """Таблица общих строк; книга без неё (книги прототипа) — пустая."""
    if part is None:
        return []
    return [_text(si) for si in _xml(path, z, part).findall(f"{_M}si")]


def _date_styles(path: Path, z: zipfile.ZipFile, part: str | None) -> list:
    """Для каждого стиля ячейки cellXfs — дата ли его формат числа."""
    if part is None:
        return []
    root = _xml(path, z, part)
    # Только <numFmts>: у <dxf> условного форматирования свои numFmt с теми же номерами
    numfmts = root.find(f"{_M}numFmts")
    codes = {_int(path, n.get("numFmtId"), f"{part}: numFmtId"): n.get("formatCode", "")
             for n in (numfmts if numfmts is not None else ())}
    xfs = root.find(f"{_M}cellXfs")
    out = []
    for xf in (xfs if xfs is not None else ()):
        fid = _int(path, xf.get("numFmtId", "0"), f"{part}: numFmtId стиля")
        # Код в книге важнее встроенного номера: книга может переопределить 14…
        out.append(is_date_format(codes[fid]) if fid in codes else fid in _BUILTIN_DATE_FORMATS)
    return out


# ── Листы и ячейки ──

def _sheet(path: Path, z: zipfile.ZipFile, name: str, part: str, shared: list,
           date_styles: list, recalc: bool) -> Sheet:
    """Лист: ячейки со значением или формулой; стилизованные пустые не хранятся."""
    data = _xml(path, z, part).find(f"{_M}sheetData")
    cells = {}
    row_no = 0
    for row in (data if data is not None else ()):          # лист диаграммы — без sheetData
        # Атрибут r необязателен (ECMA-376): без него — следующая строка, следующий столбец
        row_no = (_int(path, row.get("r"), f"лист {name}: номер строки") if row.get("r")
                  else row_no + 1)
        col_no = 0
        for c in row.findall(f"{_M}c"):
            ref = c.get("r")
            if ref:
                m = _CELL_REF.fullmatch(ref)
                if m is None:
                    raise WorkbookError(f"{path}: лист {name}: адрес ячейки {ref!r} не по "
                                        f"стандарту. {_SAVE_AS}")
                col_no = 0
                for ch in m.group(1):
                    col_no = col_no * 26 + ord(ch) - ord("A") + 1
                r = int(m.group(2))
            else:
                col_no, r = col_no + 1, row_no
            cell = _cell(path, name, r, col_no, c, shared, date_styles, recalc)
            if cell.kind != EMPTY or cell.formula is not None:
                cells[(r, col_no)] = cell
    return Sheet(name, cells)


def _cell(path: Path, sheet: str, row: int, col: int, c: ET.Element, shared: list,
          date_styles: list, recalc: bool) -> Cell:
    """Ячейка <c>: тип по атрибуту t, значение <v>, формула <f>, дата — по стилю s."""
    t = c.get("t", "n")
    f = c.find(f"{_M}f")
    formula = None if f is None else (f.text or "")
    v = c.find(f"{_M}v")
    text = None if v is None else (v.text or "")
    if formula is not None and recalc:
        # Значение формулы записала не Excel: XlsxWriter пишет 0, если значение
        # не передали, — сохранённого значения нет (решение 9)
        text = None

    def bad(what: str) -> WorkbookError:
        return WorkbookError(f"{path}: ячейка {sheet}!{column_letters(col)}{row}: {what}. "
                             f"{_SAVE_AS}")

    if t == "inlineStr":
        el = c.find(f"{_M}is")
        return Cell(sheet, row, col, *((STRING, _text(el)) if el is not None else (EMPTY, None)),
                    formula=formula)
    if text is None:                                # нет <v>: пусто или формула без значения
        return Cell(sheet, row, col, formula=formula)
    if t == "s":
        if not text.isdigit() or int(text) >= len(shared):
            raise bad(f"нет общей строки с номером {text!r}")
        return Cell(sheet, row, col, STRING, shared[int(text)], formula=formula)
    if t == "str":                      # строка формулы; у книг прототипа — любая строка
        return Cell(sheet, row, col, STRING, _unescape(text), formula=formula)
    if t == "b":
        if text not in ("0", "1", "true", "false"):
            raise bad(f"логическое значение {text!r}")
        return Cell(sheet, row, col, BOOL, text in ("1", "true"), formula=formula)
    if t == "e":
        return Cell(sheet, row, col, ERROR, text, formula=formula)
    if t == "d":                                    # дата ISO 8601 — так пишет не Excel
        return Cell(sheet, row, col, STRING, text, True, formula)
    if t != "n":
        raise bad(f"неизвестный тип ячейки t={t!r}")
    if not text.strip():
        # <v></v>: XlsxWriter у формулы со значением "" — значения нет
        return Cell(sheet, row, col, formula=formula)
    try:
        value = float(text)
    except ValueError:
        raise bad(f"значение {text!r} не число") from None
    style = _int(path, c.get("s", "0"), f"ячейка {sheet}!{column_letters(col)}{row}: стиль")
    is_date = style < len(date_styles) and date_styles[style]
    return Cell(sheet, row, col, NUMBER, value, is_date, formula)
