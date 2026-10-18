"""Разбор книги .xlsx (FEAT-034): тип, значение и адрес каждой ячейки.

Книги-ловушки пишет XlsxWriter. Чего он не пишет (формула без <v>, ячейка без
адреса, дата t="d", Strict), — правкой XML книги. XlsxWriter помечает книгу
«пересчитать при открытии», Excel при сохранении пометку снимает: книга «после
Excel» — та же книга без пометки (_excel_saved). Корпус — 45 книг прототипа в
git, записанных прототипом и Excel: значения совпадают с radial_blackoil.xlsxio
там, где тот прав (в корпусе нет логических значений и формул без значения).
"""

import ast
import datetime as dt
import sys
import zipfile
from pathlib import Path

import pytest
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from gpn_multiphase_solver.io import xlsx_reader as xr
from gpn_multiphase_solver.io.xlsx_reader import (
    BOOL, EMPTY, ERROR, NUMBER, STRING, WorkbookError, column_letters, is_date_format,
    read_workbook)

from ._xlsx import read_book

SOLVER = Path(__file__).resolve().parents[1]                     # numerical_solver/
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
GENERATOR_BOOK = SOLVER / "configs" / "INPUT_TEMPLATE_v1.xlsx"
# Черновик руководителя — вне git (FEAT-033, решение 56): тест пропускается без него
DRAFT_BOOK = SOLVER / "configs" / "INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx"
IMEX_RATES = (PROTO / "regression" / "reference_imex_xlsx"
              / "T08c_IMEX8c_FI_EXTENDED_PVTO_rates.xlsx")
# Каталоги книг прототипа в git; OUTPUT/ (выходы регрессии) не берётся
CORPUS = sorted([*PROTO.glob("*.xlsx"), *(PROTO / "regression" / "evidence").glob("*.xlsx"),
                 *(PROTO / "regression" / "inputs").rglob("*.xlsx"),
                 *(PROTO / "regression" / "reference_imex_xlsx").glob("*.xlsx"),
                 *(PROTO / "tests" / "fixtures").glob("*.xlsx")])


# ── Средства ─────────────────────────────────────────────────

def _edit(path: Path, part: str, old: str, new: str) -> None:
    """Заменить текст в части книги — ровно одно вхождение (правка XML)."""
    with zipfile.ZipFile(path) as z:
        members = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    data = dict(members)
    text = data[part].decode("utf-8")
    assert text.count(old) == 1, f"{part}: {old!r} найдено {text.count(old)} раз"
    data[part] = text.replace(old, new).encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, _ in members:
            z.writestr(name, data[name])


def _excel_saved(path: Path) -> Path:
    """Книга, какой её сохраняет Excel: без пометки fullCalcOnLoad."""
    _edit(path, "xl/workbook.xml", ' fullCalcOnLoad="1"', "")
    return path


def _traps(path: Path) -> Path:
    """Книга-ловушка XlsxWriter: лист T — по ловушке в строке, скрытый лист H."""
    wb = xlsxwriter.Workbook(path)
    ws = wb.add_worksheet("T")
    ws.write_number("A1", 1.5)
    ws.write_string("A2", "1,5")                             # число строкой
    ws.write_string("A3", "  BHP ")                          # пробелы — как в книге
    ws.write_string("A4", "a\x01b")                          # XlsxWriter пишет a_x0001_b
    ws.write_rich_string("A5", "ab", wb.add_format({"bold": True}), "cd")
    ws.write_boolean("A6", True)
    ws.write_boolean("A7", False)
    ws.write_formula("A8", "=1/0", None, "#DIV/0!")          # ошибка: t="e"
    ws.write_formula("A9", "=1/3", None, 0.333)
    ws.write_formula("A10", '="x"', None, "abc")             # строка формулы: t="str"
    ws.write_formula("A11", "=1>0", None, True)
    ws.write_formula("A12", '=""', None, "")                 # <v></v> без типа
    ws.write_array_formula("A13:A13", "{=SUM(A1:A1)}", None, 1.5)
    ws.write_datetime("A14", dt.datetime(2026, 5, 1), wb.add_format({"num_format": 14}))
    ws.write_number("A15", 46143, wb.add_format({"num_format": 16}))      # d-mmm: дата без года
    ws.write_datetime("A16", dt.datetime(2026, 5, 1, 12),
                      wb.add_format({"num_format": "dd.mm.yyyy"}))
    ws.write_string("A17", "1.5", wb.add_format({"num_format": 14}))      # строка с форматом даты
    ws.write_blank("A18", None, wb.add_format({"num_format": 14}))        # стиль без значения
    ws.write_formula("A19", "=1/3")                          # значение не передано — 0
    ws.write_number("C21", 7)                                # пропуск строки и столбцов
    ws.write_blank("A30", None, wb.add_format({"bold": True}))            # пустой хвост
    hidden = wb.add_worksheet("H")
    hidden.write_number("B2", 2)
    hidden.hide()
    wb.add_worksheet("E")                                    # пустой лист
    wb.close()
    return path


@pytest.fixture(scope="module")
def traps_path(tmp_path_factory):
    return _traps(tmp_path_factory.mktemp("traps") / "traps.xlsx")


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    """Ловушки «после Excel»: сохранённые значения формул действительны."""
    p = _excel_saved(_traps(tmp_path_factory.mktemp("saved") / "saved.xlsx"))
    return read_workbook(p).sheets["T"]


def _cell(sheet, address):
    row = int("".join(ch for ch in address if ch.isdigit()))
    col = 0
    for ch in (ch for ch in address if ch.isalpha()):
        col = col * 26 + ord(ch) - 64
    return sheet.cell(row, col)


# ── Типы значений (книга «после Excel») ──────────────────────

@pytest.mark.parametrize("address, kind, value", [
    ("A1", NUMBER, 1.5),
    ("A2", STRING, "1,5"),               # строку разбор не толкует: «1,5» — отказ FEAT-035
    ("A3", STRING, "  BHP "),
    ("A4", STRING, "a\x01b"),             # _x0001_ раскодирован
    ("A5", STRING, "abcd"),               # форматированный текст: <r><t>…
    ("A6", BOOL, True),                   # не 1.0, как у xlsxio
    ("A7", BOOL, False),
    ("A8", ERROR, "#DIV/0!"),
    ("A9", NUMBER, 0.333),
    ("A10", STRING, "abc"),
    ("A11", BOOL, True),
    ("A13", NUMBER, 1.5),
])
def test_value_kinds(saved, address, kind, value):
    cell = _cell(saved, address)
    assert (cell.kind, cell.value) == (kind, value)
    assert type(cell.value) is type(value)         # True — bool, не int; 1.5 — float


@pytest.mark.parametrize("address, formula", [
    ("A8", "1/0"), ("A9", "1/3"), ("A10", '"x"'), ("A11", "1>0"),     # &gt; раскодирован
    ("A12", '""'), ("A13", "SUM(A1:A1)"), ("A1", None), ("A2", None)])
def test_formula_text(saved, address, formula):
    """Текст формулы без «=»; у значения — None."""
    assert _cell(saved, address).formula == formula


def test_formula_with_empty_v_has_no_value(saved):
    """<v></v> без типа (XlsxWriter, значение "") — формула без значения, а не число."""
    cell = _cell(saved, "A12")
    assert cell.kind == EMPTY and cell.formula_without_value


def test_formula_without_v(tmp_path):
    """Формула без <v> (книгу записала программа, Excel её не пересчитывал) — различима."""
    p = _excel_saved(_traps(tmp_path / "b.xlsx"))
    _edit(p, "xl/worksheets/sheet1.xml", "<f>1/3</f><v>0.333</v>", "<f>1/3</f>")
    cell = _cell(read_workbook(p).sheets["T"], "A9")
    assert cell.kind == EMPTY and cell.value is None and cell.formula_without_value


def test_recalc_book_formulas_have_no_value(traps_path):
    """Пометка fullCalcOnLoad (XlsxWriter): значения формул не читаются (решение 9).

    XlsxWriter у формулы без значения пишет 0 (A19) — неотличимо от настоящего нуля.
    Значения без формул пометка не трогает.
    """
    book = read_workbook(traps_path)
    assert book.recalc_on_open
    t = book.sheets["T"]
    for address in ("A8", "A9", "A10", "A11", "A13", "A19"):
        assert _cell(t, address).formula_without_value, address
    assert (_cell(t, "A6").kind, _cell(t, "A1").value) == (BOOL, 1.5)


def test_excel_saved_book_keeps_formula_values(saved):
    assert not _cell(saved, "A19").formula_without_value
    assert _cell(saved, "A19").value == 0.0


# ── Даты ─────────────────────────────────────────────────────

@pytest.mark.parametrize("address, is_date", [
    ("A14", True),     # встроенный 14
    ("A15", True),     # встроенный 16 (d-mmm): день и месяц без года
    ("A16", True),     # пользовательский dd.mm.yyyy
    ("A1", False),
    ("A17", False),    # строка с форматом даты — не дата: признак только у чисел
])
def test_date_flag(saved, address, is_date):
    assert _cell(saved, address).is_date is is_date


def test_date_value_is_serial_number(saved):
    """Дата — число Excel (сутки от 1900 г.): 1 мая 2026 = 46143, полдень — .5."""
    assert (_cell(saved, "A14").value, _cell(saved, "A16").value) == (46143.0, 46143.5)


@pytest.mark.parametrize("code", [
    "yyyy-mm-dd", "dd.mm.yyyy", "d-mmm", "h:mm", "[h]:mm:ss", "[mm]:ss", "mm:ss.0",
    "hh:mm AM/PM", "[$-419]d mmmm yyyy;@", "[Red]dd/mm/yy", "DD.MM.YYYY"])
def test_date_formats(code):
    assert is_date_format(code)


@pytest.mark.parametrize("code", [
    "General", "0", "0.00", "0.00E+00", "#,##0.00", '0.0 "days"', "@", "0.0_)",
    "[Red]0.0", "0%", "# ?/?", '"date: "0', "0;[Red]-0", "* #,##0",
    # Формат 164 книг IMEX (сохранены Excel): все буквы экранированы — литералы
    r"\y\y\y\y\-\m\m\m\-\d\d\ \h\h\:\m\m\:\s\s"])
def test_not_date_formats(code):
    assert not is_date_format(code)


def test_builtin_time_format(tmp_path):
    """Встроенный формат 22 (m/d/yy h:mm) — дата без кода в styles.xml."""
    p = tmp_path / "b.xlsx"
    wb = xlsxwriter.Workbook(p)
    wb.add_worksheet().write_number("A1", 46143.25, wb.add_format({"num_format": 22}))
    wb.close()
    assert read_workbook(p).sheets["Sheet1"].cell(1, 1).is_date


def test_iso_date_cell(tmp_path):
    """t="d" (дата ISO 8601, так пишут не Excel) — строка с признаком даты."""
    p = _excel_saved(_traps(tmp_path / "b.xlsx"))
    _edit(p, "xl/worksheets/sheet1.xml", '<c r="A1"><v>1.5</v></c>',
          '<c r="A1" t="d"><v>2026-05-01T00:00:00</v></c>')
    cell = read_workbook(p).sheets["T"].cell(1, 1)
    assert (cell.kind, cell.value, cell.is_date) == (STRING, "2026-05-01T00:00:00", True)


# ── Строки, листы, адреса ────────────────────────────────────

def test_shared_string_phonetic_and_escapes(tmp_path):
    """Общая строка: фонетика <rPh> не читается; _x005F_ — «_», дальше текст как есть."""
    p = _excel_saved(_traps(tmp_path / "b.xlsx"))
    _edit(p, "xl/sharedStrings.xml", "<si><t>1,5</t></si>",
          '<si><t>_x005F_x0041_</t><rPh sb="0" eb="1"><t>ふ</t></rPh></si>')
    assert _cell(read_workbook(p).sheets["T"], "A2").value == "_x0041_"


def test_shared_formula_child(tmp_path):
    """Ячейка общей формулы: <f t="shared" si="0"/> без текста — формула "", значение есть."""
    p = _excel_saved(_traps(tmp_path / "b.xlsx"))
    _edit(p, "xl/worksheets/sheet1.xml", "<f>1/3</f><v>0.333</v>",
          '<f t="shared" si="0"/><v>0.333</v>')
    cell = _cell(read_workbook(p).sheets["T"], "A9")
    assert (cell.formula, cell.kind, cell.value) == ("", NUMBER, 0.333)


def test_conditional_format_numfmt_ignored(tmp_path):
    """numFmt условного форматирования (<dxf>) с тем же номером не делает стиль ячейки датой."""
    p = tmp_path / "b.xlsx"
    wb = xlsxwriter.Workbook(p)
    wb.add_worksheet().write_number("A1", 2.5, wb.add_format({"num_format": "0.000"}))
    wb.close()
    _edit(p, "xl/styles.xml", "</styleSheet>",
          '<dxfs count="1"><dxf><numFmt numFmtId="164" formatCode="dd.mm.yyyy"/></dxf></dxfs>'
          "</styleSheet>")
    cell = read_workbook(p).sheets["Sheet1"].cell(1, 1)
    assert (cell.value, cell.is_date) == (2.5, False)


def test_relationship_target_from_root(tmp_path):
    """Цель связи «xl/worksheets/…» от корня архива, а не от xl/ — читается, как у xlsxio."""
    p = _excel_saved(_traps(tmp_path / "b.xlsx"))
    _edit(p, "xl/_rels/workbook.xml.rels", 'Target="worksheets/sheet1.xml"',
          'Target="xl/worksheets/sheet1.xml"')
    assert _cell(read_workbook(p).sheets["T"], "A1").value == 1.5


def test_inline_strings(tmp_path):
    """Встроенные строки (t="inlineStr"): XlsxWriter в режиме constant_memory."""
    p = tmp_path / "b.xlsx"
    wb = xlsxwriter.Workbook(p, {"constant_memory": True})
    wb.add_worksheet("S").write_string("B3", "Key")
    wb.close()
    with zipfile.ZipFile(p) as z:
        assert "xl/sharedStrings.xml" not in z.namelist()
    cell = read_workbook(p).sheets["S"].cell(3, 2)
    assert (cell.kind, cell.value, cell.ref) == (STRING, "Key", "S!B3")


def test_sheet_order_hidden_and_empty(saved, traps_path):
    """Порядок листов — как в книге; скрытый лист читается (решение 6); пустой — без ячеек."""
    book = read_workbook(traps_path)
    assert list(book.sheets) == ["T", "H", "E"]
    assert book.sheets["H"].cell(2, 2).value == 2.0
    assert book.sheets["E"].cells == {} and book.sheets["E"].max_row == 0


def test_gaps_and_styled_blanks(saved):
    """Неровные строки и пропуски — пусто; стилизованная пустая ячейка не хранится."""
    assert _cell(saved, "C21").value == 7.0
    assert _cell(saved, "A21").kind == EMPTY and _cell(saved, "C20").kind == EMPTY
    assert (18, 1) not in saved.cells and (30, 1) not in saved.cells
    assert saved.max_row == 21                     # пустой хвост A30 строку не продлевает


def test_cell_without_address(tmp_path):
    """Атрибут r у <c> и <row> необязателен: позиция — по порядку."""
    p = _excel_saved(_traps(tmp_path / "b.xlsx"))
    _edit(p, "xl/worksheets/sheet2.xml", '<row r="2" spans="2:2"><c r="B2"><v>2</v></c></row>',
          '<row r="2" spans="1:2"><c><v>1</v></c><c><v>2</v></c></row><row><c><v>3</v></c></row>')
    h = read_workbook(p).sheets["H"]
    assert [(k, c.value) for k, c in sorted(h.cells.items())] == [
        ((2, 1), 1.0), ((2, 2), 2.0), ((3, 1), 3.0)]


@pytest.mark.parametrize("col", [1, 2, 26, 27, 52, 53, 702, 703, 16384])
def test_column_letters(col):
    assert column_letters(col) == xl_col_to_name(col - 1)


def test_cell_ref(saved):
    assert _cell(saved, "C21").ref == "T!C21" and _cell(saved, "C21").address == "C21"


# ── Отказы ───────────────────────────────────────────────────

SAVE_AS = "«Книга Excel (*.xlsx)»"


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_workbook(tmp_path / "нет.xlsx")


def test_not_zip(tmp_path):
    p = tmp_path / "b.xlsx"
    p.write_text("Key;Value\n", encoding="utf-8")       # CSV под именем .xlsx
    with pytest.raises(WorkbookError, match="не zip-архив") as e:
        read_workbook(p)
    assert SAVE_AS in str(e.value) and str(p) in str(e.value)


def test_ole_file(tmp_path):
    """Составной файл OLE: .xls или книга с паролем на открытие (решение 4)."""
    p = tmp_path / "b.xlsx"
    p.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + bytes(504))
    with pytest.raises(WorkbookError, match=r"\.xls или книга с паролем") as e:
        read_workbook(p)
    assert SAVE_AS in str(e.value)


def test_xlsb(tmp_path):
    p = tmp_path / "b.xlsb"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
                   'openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                   'Target="xl/workbook.bin"/></Relationships>')
        z.writestr("xl/workbook.bin", b"\x00")
    with pytest.raises(WorkbookError, match=r"\.xlsb"):
        read_workbook(p)


def test_zip_without_workbook(tmp_path):
    p = tmp_path / "b.xlsx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
    with pytest.raises(WorkbookError, match="нет книги Excel"):
        read_workbook(p)


def test_strict_open_xml(tmp_path):
    """Strict: без проверки разбор молча нашёл бы ноль листов."""
    p = _traps(tmp_path / "b.xlsx")
    _edit(p, "xl/workbook.xml", 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"',
          'xmlns="http://purl.oclc.org/ooxml/spreadsheetml/main"')
    with pytest.raises(WorkbookError, match="Strict"):
        read_workbook(p)


def test_broken_sheet_xml(tmp_path):
    p = _traps(tmp_path / "b.xlsx")
    _edit(p, "xl/worksheets/sheet1.xml", "</sheetData>", "")
    with pytest.raises(WorkbookError, match="xl/worksheets/sheet1.xml"):
        read_workbook(p)


@pytest.mark.parametrize("old, new, where", [
    ('<c r="C21"><v>7</v></c>', '<c r="C21"><v>abc</v></c>', "T!C21"),          # не число
    ('<c r="A2" t="s"><v>0</v></c>', '<c r="A2" t="s"><v>99</v></c>', "T!A2"),  # нет общей строки
    ('<c r="A6" t="b"><v>1</v></c>', '<c r="A6" t="b"><v>2</v></c>', "T!A6"),
    ('<c r="C21"><v>7</v></c>', '<c r="C21" t="x"><v>7</v></c>', "T!C21"),     # неизвестный тип
])
def test_bad_cell_names_address(tmp_path, old, new, where):
    p = _traps(tmp_path / "b.xlsx")
    _edit(p, "xl/worksheets/sheet1.xml", old, new)
    with pytest.raises(WorkbookError, match=where):
        read_workbook(p)


@pytest.mark.parametrize("part, old, new, match", [
    # spans XlsxWriter считает по блокам из 16 строк — якорь без него
    ("xl/worksheets/sheet1.xml", '<row r="21" ', '<row r="x" ', "номер строки"),
    ("xl/worksheets/sheet1.xml", '<c r="C21"><v>7</v></c>', '<c r="C21" s="x"><v>7</v></c>',
     r"T!C21: стиль"),
    ("xl/styles.xml", '<numFmt numFmtId="164" formatCode="dd.mm.yyyy"/>',
     '<numFmt formatCode="dd.mm.yyyy"/>', "numFmtId"),      # без атрибута — не TypeError
])
def test_bad_attribute_is_workbook_error(tmp_path, part, old, new, match):
    """Испорченный служебный атрибут — WorkbookError, а не ValueError/TypeError из int().

    Вызывающий (FEAT-035, FEAT-036) ловит WorkbookError как ошибку книги; иное
    исключение командная строка печатает с трассировкой как ошибку кода (аудит 2).
    """
    p = _traps(tmp_path / "b.xlsx")
    _edit(p, part, old, new)
    with pytest.raises(WorkbookError, match=match):
        read_workbook(p)


# ── Реальные книги ───────────────────────────────────────────

def _rows(sheet) -> list:
    """Непустые строки листа: значения столбцов 1…последний непустой."""
    rows = {}
    for (r, c) in sheet.cells:
        rows[r] = max(rows.get(r, 0), c)
    return [[sheet.cell(r, c).value for c in range(1, rows[r] + 1)] for r in sorted(rows)]


def _xlsxio_rows(rows) -> list:
    """Строки xlsxio без пустых и без хвостовых None (xlsxio хранит стилизованные пустые)."""
    out = []
    for row in rows:
        while row and row[-1] is None:
            row = row[:-1]
        if row:
            out.append(row)
    return out


def test_corpus_present():
    """Корпус на месте: пустой список молча пропустил бы сверку."""
    assert len(CORPUS) >= 45


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_corpus_matches_xlsxio(path):
    """Книги прототипа и Excel: листы и значения — как у radial_blackoil.xlsxio."""
    from radial_blackoil.xlsxio import read_workbook_tables
    theirs = read_workbook_tables(path)
    book = read_workbook(path)
    assert list(book.sheets) == list(theirs)
    for name, sheet in book.sheets.items():
        assert _rows(sheet) == _xlsxio_rows(theirs[name]), name
        assert all(c.kind in (NUMBER, STRING) for c in sheet.cells.values()), name


def test_imex_formulas_and_escaped_format():
    """Книга IMEX, сохранённая Excel: формулы DATE+TIME с значениями, формат 164 — не дата.

    В формате 164 все буквы экранированы (\\y\\y\\y\\y\\-…): по правилам кода формата
    это литералы, Excel выводит их как текст. Правило признака даты — решение 12 плана.
    """
    book = read_workbook(IMEX_RATES)
    assert not book.recalc_on_open
    cell = next(iter(book.sheets.values())).cell(5, 2)          # B5
    assert cell.formula == "DATE(2026,1,1) + TIME(0,1,0)"
    assert (cell.kind, cell.value, cell.is_date) == (NUMBER, 46023.000694444447, False)


def test_generator_book_matches_test_reader():
    """Книга генератора FEAT-033: значения — как у помощника тестов tests/_xlsx.py."""
    book = read_workbook(GENERATOR_BOOK)
    theirs = read_book(GENERATOR_BOOK)
    assert list(book.sheets) == list(theirs.sheets)
    for name, sheet in book.sheets.items():
        ours = {c.address: c.value for c in sheet.cells.values()}
        assert ours == theirs.sheets[name].values, name


@pytest.mark.skipif(not DRAFT_BOOK.exists(), reason="черновик руководителя вне git (решение 11)")
def test_draft_book_matches_xlsxio():
    """Черновик руководителя: листы, неровные строки SCHEDULE, пустые строки THERMAL."""
    from radial_blackoil.xlsxio import read_workbook_tables
    theirs = read_workbook_tables(DRAFT_BOOK)
    book = read_workbook(DRAFT_BOOK)
    assert list(book.sheets) == ["MODEL", "THERMAL", "SCHEDULE", "OIL_PVT", "GAS_PVT",
                                 "RELPERM", "COMMENTS"]
    for name, sheet in book.sheets.items():
        assert _rows(sheet) == _xlsxio_rows(theirs[name]), name


# ── Книги, сохранённые Excel (шаг 3 плана) ───────────────────

EXCEL_DIR = SOLVER / "tests" / "data" / "feat034_excel"
# traps.xlsx — Excel 16 с английскими настройками (десятичная точка), лист Sheet1.
# Ловушка русского Excel «1.5 → 1 мая» здесь не воспроизводится: при точке ввод
# 1.5 — число, а «01.05.2026» — не дата, текст. Признак даты книги настоящего
# Excel проверяет время 10:30 (встроенный формат 20)
EXCEL_TRAPS = EXCEL_DIR / "traps.xlsx"
# template_saved.xlsx — книга генератора FEAT-033 (версия 1), открытая и сохранённая
# в Excel; в Value строки geometry.r_well введено =0.2/2
TEMPLATE_SAVED = EXCEL_DIR / "template_saved.xlsx"


@pytest.mark.parametrize("address, kind, value, is_date, formula", [
    ("A1", NUMBER, 1.5, False, "1.5"),              # введено формулой =1.5
    ("A2", STRING, "1,5", False, None),             # запятая при десятичной точке — текст
    ("A3", STRING, "1,5", False, None),             # '1,5 — текст с апострофом
    ("A4", BOOL, True, False, None),
    ("A5", NUMBER, 0.11 / 3600, False, "0.11/3600"),  # в XML — 3.0555555555555554E-5
    ("A6", ERROR, "#DIV/0!", False, "1/0"),
    ("A7", STRING, "01.05.2026", False, None),      # не дата при английских настройках
    ("A8", NUMBER, 0.4375, True, None),             # 10:30 = 10.5/24, встроенный формат 20
    ("A9", NUMBER, 0.05, False, None),              # 5 %, формат 9 — не дата
    ("A10", NUMBER, 10.0, False, "ROW()"),
])
def test_excel_saved_traps(address, kind, value, is_date, formula):
    """Книга настоящего Excel: тип, значение, признак даты и формула ячейки — как в её XML."""
    cell = _cell(read_workbook(EXCEL_TRAPS).sheets["Sheet1"], address)
    assert (cell.kind, cell.value, cell.is_date, cell.formula) == (kind, value, is_date, formula)
    assert type(cell.value) is type(value)          # True — bool, не float, как у xlsxio


def test_excel_saved_traps_book():
    """Excel пометку пересчёта не ставит; в книге ровно ячейки A1:A10."""
    book = read_workbook(EXCEL_TRAPS)
    assert not book.recalc_on_open
    assert list(book.sheets) == ["Sheet1"]
    assert sorted(book.sheets["Sheet1"].cells) == [(r, 1) for r in range(1, 11)]


def test_template_saved_by_excel():
    """Книга генератора после Excel: пометки пересчёта нет, у формулы есть значение (решение 9).

    Допущение решения 9: Excel при сохранении снимает fullCalcOnLoad, который
    ставит XlsxWriter, — иначе формулы всех книг инженеров получили бы отказ.
    С текущей книгой генератора фикстура не сравнивается: она — снимок версии 1,
    генератор меняется вместе с форматом FEAT-033 (аудит 2).
    """
    book = read_workbook(TEMPLATE_SAVED)
    assert not book.recalc_on_open
    assert list(book.sheets) == ["MODEL", "THERMAL", "NUMERICS", "SCHEDULE", "OIL_PVT",
                                 "GAS_PVT", "RELPERM", "COMMENTS"]
    model = book.sheets["MODEL"]
    row = next(r for (r, c), cell in model.cells.items()
               if c == 1 and cell.value == "geometry.r_well")
    value = model.cell(row, 3)                      # столбец C — Value
    assert (value.formula, value.kind, value.value) == ("0.2/2", NUMBER, 0.1)
    cells = [c for s in book.sheets.values() for c in s.cells.values()]
    assert not [c.ref for c in cells if c.formula_without_value]
    assert [c.ref for c in cells if c.formula is not None] == [value.ref]   # формула одна


# ── Без зависимостей ─────────────────────────────────────────

def test_reader_imports_only_stdlib():
    """Разбор — только стандартная библиотека (решение 1): ни numpy, ни XlsxWriter."""
    tree = ast.parse(Path(xr.__file__).read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
            for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree)
             if isinstance(n, ast.ImportFrom) and n.level == 0}
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}, mods
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level > 0]
