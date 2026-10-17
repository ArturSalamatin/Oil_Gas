"""Шаблон книги ввода версии 1 (FEAT-033): листы, значения, защита, проверки данных.

Книгу пишет write_template, читает помощник tests/_xlsx.py (zip/XML стандартной
библиотекой). Проверяется, что книга — ровно таблица полей io/workbook_format.py:
подписи, единицы, демонстрационные значения, комментарии на двух языках; что
Key, Unit и постоянные значения заблокированы (решения 37, 65), RELPERM защищён
с обязательными строками S_g = 0 и S_g = 1 (решение 68), прочие таблицы — нет
(решение 59); что у каждой числовой ячейки
есть проверка данных Excel с пределом программы (решение 50); что существующий
файл не перезаписывается (решение 58).
"""

from pathlib import Path

import pytest
from xlsxwriter.utility import xl_rowcol_to_cell

from gpn_multiphase_solver.io import workbook_format as wf
from gpn_multiphase_solver.io.workbook_template import (
    COMMENTS, DEMO_TABLES, excel_rule, limit_text, write_template)

from ._xlsx import read_book

SOLVER = Path(__file__).resolve().parents[1]             # numerical_solver/
GENERATOR_BOOK = SOLVER / "configs" / "INPUT_TEMPLATE_v1.xlsx"


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    path = tmp_path_factory.mktemp("tpl") / "book.xlsx"
    write_template(path)
    return read_book(path)


def _col(c):
    return xl_rowcol_to_cell(0, c)[:-1]       # 0 → «A»


def _demo_numbers():
    """Все демонстрационные числа: значения строк трёх листов и ячейки таблиц."""
    nums = [p.demo for s in wf.PARAM_SHEETS.values() for p in s]
    nums += [x for rows in DEMO_TABLES.values() for row in rows for x in row]
    return [x for x in nums if isinstance(x, float)]


def test_demo_numbers_have_15_digits():
    """Демо-числа — с ≤ 15 значащими цифрами (решение 63), иначе книга не равна коду.

    XlsxWriter пишет число с 16 значащими цифрами ({:.16G}); у 17-значного
    литерала значение в книге сдвинулось бы (1.0451463166781947 → 1.045146316678195,
    аудит FEAT-033). Ловит литерал, вставленный из источника без округления.
    """
    long = [x for x in _demo_numbers() if float(f"{x:.15G}") != x]
    assert not long, long[:5]


# ── Листы и значения ─────────────────────────────────────────

def test_sheet_order(book):
    assert tuple(book.sheets) == wf.SHEET_ORDER


@pytest.mark.parametrize("name", list(wf.PARAM_SHEETS))
def test_param_sheet_rows(book, name):
    """Строка книги = строка таблицы полей; число — числом, слово — строкой."""
    v = book.sheets[name].values
    assert tuple(v[f"{_col(c)}1"] for c in range(6)) == wf.PARAM_HEADER
    for r, p in enumerate(wf.PARAM_SHEETS[name], start=2):
        assert tuple(v[f"{x}{r}"] for x in "ABCDEF") == \
               (p.key, p.label, p.demo, p.unit, p.comment, p.comment_ru)
        assert isinstance(v[f"C{r}"], str) == isinstance(p.demo, str), p.key
    assert f"A{len(wf.PARAM_SHEETS[name]) + 2}" not in v      # лишних строк нет


@pytest.mark.parametrize("name", list(wf.TABLE_SHEETS))
def test_table_sheets_rows(book, name):
    """Заголовки — Column.header; ячейки — демонстрационная таблица, None — пусто."""
    v = book.sheets[name].values
    cols = wf.TABLE_SHEETS[name]
    assert [v[f"{_col(c)}1"] for c in range(len(cols))] == [c.header for c in cols]
    for r, row in enumerate(DEMO_TABLES[name], start=2):
        assert [v.get(f"{_col(c)}{r}") for c in range(len(cols))] == list(row)


def test_schedule_last_row_time_only(book):
    """Последняя строка — только момент завершения: режим её не читается (решение 32)."""
    n = len(DEMO_TABLES["SCHEDULE"]) + 1
    v = book.sheets["SCHEDULE"].values
    assert v[f"A{n}"] == 30.0
    assert all(f"{c}{n}" not in v for c in "BCDE")


def test_demo_tables_satisfy_limits():
    """Демонстрационные таблицы проходят пределы столбцов; время — с 0 и растёт."""
    for name, rows in DEMO_TABLES.items():
        cols = wf.TABLE_SHEETS[name]
        for row in rows:
            for col, v in zip(cols, row):
                if v is None:
                    continue
                assert (v in col.choices) if col.choices else col.limit.accepts(v), (name, row)
    times = [row[0] for row in DEMO_TABLES["SCHEDULE"]]
    assert times[0] == 0.0 and all(b > a for a, b in zip(times, times[1:]))
    for row in DEMO_TABLES["SCHEDULE"][:-1]:
        _, used = wf.CONTROL_MODES[row[1]]
        idx = {c.target: i for i, c in enumerate(wf.SCHEDULE)}
        assert all(row[idx[t]] is not None for t in used), row
    # Обязательные строки RELPERM (решение 68): число образца — в демо то же
    rel = DEMO_TABLES["RELPERM"]
    for row, pattern in ((rel[0], wf.RELPERM_FIRST_ROW), (rel[-1], wf.RELPERM_LAST_ROW)):
        assert all(p is None or v == p for v, p in zip(row, pattern)), row


def test_comments_sheet(book):
    """COMMENTS — под gpn-solver, по-английски и по-русски (решение 67), без run_prototype."""
    v = book.sheets["COMMENTS"].values
    assert "format version 1" in v["A1"] and "версия формата 1" in v["C1"]
    rows = range(3, 3 + len(COMMENTS))
    assert [(v[f"A{r}"], v[f"B{r}"], v[f"C{r}"]) for r in rows] == list(COMMENTS)
    for _, text, text_ru in COMMENTS:
        assert any("а" <= ch.lower() <= "я" for ch in text_ru), text_ru
        assert not {"−", "–", "—"} & set(text + text_ru), text
    assert any("gpn-solver template" in text for _, text, _ in COMMENTS)
    assert not any("run_prototype" in str(x) for x in v.values())


# ── Защита ───────────────────────────────────────────────────

@pytest.mark.parametrize("name", list(wf.PARAM_SHEETS))
def test_param_sheets_protected_without_password(book, name):
    prot = book.sheets[name].protection
    assert prot is not None
    assert not {"password", "hashValue", "algorithmName"} & set(prot)


@pytest.mark.parametrize("name", list(wf.PARAM_SHEETS))
def test_locked_cells(book, name):
    """Key, Unit, заголовки, постоянные значения — заблокированы; подписи и комментарии — нет."""
    for c in "ABCDEF":
        assert book.locked(name, f"{c}1")
    for r, p in enumerate(wf.PARAM_SHEETS[name], start=2):
        assert book.locked(name, f"A{r}") and book.locked(name, f"D{r}")
        assert not any(book.locked(name, f"{c}{r}") for c in "BEF"), p.key
        assert book.locked(name, f"C{r}") == p.fixed, p.key


@pytest.mark.parametrize("name", ["SCHEDULE", "OIL_PVT", "GAS_PVT", "COMMENTS"])
def test_table_sheets_unprotected(book, name):
    assert book.sheets[name].protection is None


def test_relperm_protection(book):
    """RELPERM (решение 68): без пароля, вставка и удаление строк разрешены.

    В sheetProtection «0» означает «действие не защищено». Постоянные ячейки
    первой (S_g = 0, k_rg = 0) и последней (S_g = 1, k_ro = 0) строк
    заблокированы, остальные — нет; промежуточные строки разблокированы
    целиком — иначе Excel не удалит их на защищённом листе.
    """
    prot = book.sheets["RELPERM"].protection
    assert prot is not None and not {"password", "hashValue"} & set(prot)
    assert prot.get("insertRows") == "0" and prot.get("deleteRows") == "0"
    n = len(DEMO_TABLES["RELPERM"]) + 1                       # строка листа S_g = 1
    for r, pattern in ((2, wf.RELPERM_FIRST_ROW), (n, wf.RELPERM_LAST_ROW)):
        for x, p in zip("ABC", pattern):
            assert book.locked("RELPERM", f"{x}{r}") == (p is not None), f"{x}{r}"
    for r in range(3, n):
        assert book.row_unlocked("RELPERM", r), r
        assert not any(book.locked("RELPERM", f"{x}{r}") for x in "ABC"), r


# ── Проверки данных ──────────────────────────────────────────

@pytest.mark.parametrize("name", list(wf.PARAM_SHEETS))
def test_param_value_validation(book, name):
    """Одна проверка на ячейку Value, у постоянной — ни одной; пустая ячейка не проходит."""
    params = wf.PARAM_SHEETS[name]
    row_of = {p.key: r for r, p in enumerate(params, start=2)}
    by_cell = {}
    for dv in book.sheets[name].validations:
        by_cell.setdefault(dv["sqref"], []).append(dv)
    for p in params:
        cell = f"C{row_of[p.key]}"
        if p.fixed:
            assert cell not in by_cell, p.key
            continue
        (dv,) = by_cell.pop(cell)
        above = f"C{row_of[p.limit.above_key]}" if p.limit.above_key else None
        assert dv["type"] == "custom"
        assert dv["formula1"] == excel_rule(p.limit, cell, above)[1:]
        assert "allowBlank" not in dv, p.key
    assert not by_cell                                       # лишних проверок нет


@pytest.mark.parametrize("name", list(wf.TABLE_SHEETS))
def test_table_validation(book, name):
    """Проверка на весь столбец (нестыковка 8); у времени SCHEDULE — 0 и рост."""
    dvs = {dv["sqref"]: dv for dv in book.sheets[name].validations}
    for c, col in enumerate(wf.TABLE_SHEETS[name]):
        x = _col(c)
        if name == "SCHEDULE" and c == 0:
            assert dvs["A2"]["formula1"] == "AND(ISNUMBER(A2),A2=0)"
            assert "allowBlank" not in dvs["A2"]
            assert dvs["A3:A1048576"]["formula1"] == "AND(ISNUMBER(A3),A3>A2)"
            continue
        dv = dvs[f"{x}2:{x}1048576"]
        assert dv.get("allowBlank") == "1"
        if col.choices:
            assert dv["formula1"] == '"' + ",".join(col.choices) + '"'
        else:
            assert dv["formula1"] == excel_rule(col.limit, f"{x}2")[1:]


@pytest.mark.parametrize("limit, cell, above, rule", [
    (wf.POSITIVE, "C2", None, "=AND(ISNUMBER(C2),C2>0)"),
    (wf.COUNT, "C2", None, "=AND(ISNUMBER(C2),C2=INT(C2),C2>=1)"),
    (wf.POROSITY, "C2", None, "=AND(ISNUMBER(C2),C2>0,C2<=1)"),
    (wf.Limit(above_key="k"), "C4", "C3", "=AND(ISNUMBER(C4),C4>C3)"),
    (wf.ANY, "C2", None, "=AND(ISNUMBER(C2))"),
])
def test_excel_rule(limit, cell, above, rule):
    assert excel_rule(limit, cell, above) == rule


@pytest.mark.parametrize("limit, above, text", [
    (wf.POSITIVE, None, "Enter a number > 0."),
    (wf.Limit(lo=0.0, hi=20.0, integer=True), None, "Enter an integer from 0 to 20."),
    (wf.POROSITY, None, "Enter a number in (0, 1]."),
    (wf.Limit(above_key="k"), "Wellbore radius (rw)", "Enter a number > Wellbore radius (rw)."),
    (wf.ANY, None, "Enter a number."),
])
def test_limit_text(limit, above, text):
    assert limit_text(limit, above) == text


# ── Запись файла ─────────────────────────────────────────────

def test_existing_file_not_overwritten(tmp_path):
    """Существующий файл — FileExistsError, байты не тронуты (решение 58)."""
    path = tmp_path / "filled.xlsx"
    path.write_bytes(b"filled")
    with pytest.raises(FileExistsError):
        write_template(path)
    assert path.read_bytes() == b"filled"


@pytest.mark.parametrize("name", ["book.xls", "book"])
def test_not_xlsx_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        write_template(tmp_path / name)
    assert not (tmp_path / name).exists()


# ── Книга генератора в git (П5) ──────────────────────────────

class TestGeneratorBook:
    """configs/INPUT_TEMPLATE_v1.xlsx — по таблице полей: листы, ключи, единицы, заголовки.

    Значения не сравниваются: книгу генератора пишет gpn-solver template, а при
    смене таблицы полей её пересоздают вручную (удалить файл — решение 58). Тест
    ловит устаревшую книгу у нас, а не у заказчика (часть «шаблон читается» FEAT-035).
    """

    def test_matches_format(self):
        book = read_book(GENERATOR_BOOK)
        assert tuple(book.sheets) == wf.SHEET_ORDER
        for name, params in wf.PARAM_SHEETS.items():
            v = book.sheets[name].values
            assert tuple(v.get(f"{_col(c)}1") for c in range(len(wf.PARAM_HEADER))) == \
                   wf.PARAM_HEADER, name
            assert [(v.get(f"A{r}"), v.get(f"D{r}")) for r in range(2, len(params) + 2)] == \
                   [(p.key, p.unit) for p in params], name
        for name, cols in wf.TABLE_SHEETS.items():
            v = book.sheets[name].values
            assert [v.get(f"{_col(c)}1") for c in range(len(cols))] == \
                   [c.header for c in cols], name
