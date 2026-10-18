"""Перевод книги ввода Excel в конфиг (FEAT-035): книга → config.json и CSV таблиц в СИ.

Проверяется:
  - книга генератора и она же после Excel переводятся; load_config и сборка
    решателя принимают результат; ячейка → файл → то же число побитово;
  - составные поля (пористость при p0, (ρc_p)_s), SCHEDULE → time.history с
    моментами в целых мс (решение 19), заголовок — имя книги;
  - каждое правило книги — отказ с листом и адресом ячейки, все ошибки сразу
    (решение 22); пробелы по краям строк срезаются (решение 20);
  - convert_workbook: новый или пустой каталог; книга с ошибкой файлов не оставляет.
Книги с ошибками собираются в памяти правкой ячеек книги генератора (Cell
разбора): здесь проверяется перевод, разбор — в test_xlsx_reader.py. Сквозь
разбор — книги XlsxWriter (формула, дата, пометка пересчёта) и фикстура Excel.
"""

import csv
import json
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import xlsxwriter

from gpn_multiphase_solver.factory import SimulatorFactory, create_pvt, create_relperm
from gpn_multiphase_solver.io import workbook_convert as wc
from gpn_multiphase_solver.io import workbook_format as wf
from gpn_multiphase_solver.io import workbook_template as wt
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.io.workbook_convert import (
    CONFIG_FIELDS, MAX_ERRORS, WorkbookContentError, convert_workbook, workbook_to_config,
    write_files)
from gpn_multiphase_solver.io.xlsx_reader import (
    BOOL, EMPTY, ERROR, NUMBER, STRING, Cell, Sheet, Workbook, WorkbookError, read_workbook)
from gpn_multiphase_solver.units import DAY_TO_S

SOLVER = Path(__file__).resolve().parents[1]                     # numerical_solver/
TEMPLATE = SOLVER / "configs" / "INPUT_TEMPLATE_v1.xlsx"           # книга генератора (FEAT-033)
# Книга генератора, сохранённая Excel (FEAT-034, шаг 3): r_w — формула =0.2/2
TEMPLATE_SAVED = SOLVER / "tests" / "data" / "feat034_excel" / "template_saved.xlsx"
PARAMS = {p.key: (sheet, p) for sheet, ps in wf.PARAM_SHEETS.items() for p in ps}
# Интервалы SCHEDULE книги генератора, с: 1 мин, сутки ступенями, по 10 с после смены p_wf
TEMPLATE_DT = [60.0, 86340.0, 86400.0, 172800.0, 86400.0, *[10.0] * 6, 86340.0, 691200.0,
               86400.0, *[10.0] * 6, 86340.0, 1209600.0]


# ── Средства ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def book():
    """Книга генератора, прочитанная разбором; тесты правят её ячейки в памяти."""
    return read_workbook(TEMPLATE)


def _value_cell(sheet: str, row: int, col: int, value) -> Cell:
    """Ячейка по значению: число, строка, логическое, None — пусто; ("date", v), ("error", код), ("formula", текст)."""
    if isinstance(value, tuple):
        what, v = value
        if what == "date":
            return Cell(sheet, row, col, NUMBER, float(v), is_date=True)
        if what == "error":
            return Cell(sheet, row, col, ERROR, v)
        assert what == "formula", what
        return Cell(sheet, row, col, EMPTY, None, formula=v)   # формула без значения
    if value is None:
        return Cell(sheet, row, col)
    if isinstance(value, bool):
        return Cell(sheet, row, col, BOOL, value)
    if isinstance(value, (int, float)):
        return Cell(sheet, row, col, NUMBER, float(value))
    return Cell(sheet, row, col, STRING, value)


def _edit(book: Workbook, sheet: str, changes: dict, recalc: bool = False) -> Workbook:
    """Книга с изменёнными ячейками листа: {(строка, столбец): значение}; None — ячейку убрать."""
    cells = dict(book.sheets[sheet].cells)
    for (r, c), v in changes.items():
        cell = _value_cell(sheet, r, c, v)
        if cell.kind == EMPTY and cell.formula is None:
            cells.pop((r, c), None)
        else:
            cells[(r, c)] = cell
    return Workbook(book.path, {**book.sheets, sheet: Sheet(sheet, cells)}, recalc)


def _row(book: Workbook, key: str) -> int:
    """Строка ключа key на его листе «параметр–значение»."""
    sheet = book.sheets[PARAMS[key][0]]
    return next(r for (r, c), cell in sheet.cells.items() if c == 1 and cell.value == key)


def _set(book: Workbook, key: str, value, col: int = 3, recalc: bool = False) -> Workbook:
    """Книга с новым значением столбца col строки key (C — Value, D — Unit, A — Key)."""
    return _edit(book, PARAMS[key][0], {(_row(book, key), col): value}, recalc)


def _shift_down(book: Workbook, sheet: str, at: int) -> Workbook:
    """Книга с пустой строкой листа перед строкой at: строки ниже сдвинуты на одну."""
    cells = {}
    for (r, c), cell in book.sheets[sheet].cells.items():
        r2 = r + 1 if r >= at else r
        cells[(r2, c)] = replace(cell, row=r2)
    return Workbook(book.path, {**book.sheets, sheet: Sheet(sheet, cells)}, False)


def _with_schedule(book: Workbook, rows) -> Workbook:
    """Книга с SCHEDULE из строк (t_сут, режим, BHP бар, дебит м³ст/сут, min BHP бар); None — пусто."""
    cells = {k: v for k, v in book.sheets["SCHEDULE"].cells.items() if k[0] == 1}
    for r, row in enumerate(rows, start=2):
        for c, v in enumerate(row, start=1):
            if v is not None:
                cells[(r, c)] = _value_cell("SCHEDULE", r, c, v)
    return Workbook(book.path, {**book.sheets, "SCHEDULE": Sheet("SCHEDULE", cells)}, False)


def _errors(book: Workbook) -> list[str]:
    """Ошибки перевода книги (ждём отказ)."""
    with pytest.raises(WorkbookContentError) as e:
        workbook_to_config(book)
    return e.value.errors


def _one_error(book: Workbook) -> str:
    """Единственная ошибка перевода книги."""
    errors = _errors(book)
    assert len(errors) == 1, errors
    return errors[0]


def _read_csv(path: Path) -> tuple[list, list]:
    """Заголовок и строки CSV перевода (числа — float)."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], [tuple(float(x) for x in r) for r in rows[1:]]


def _write_book(path: Path, cell=None) -> Path:
    """Книга версии 1 XlsxWriter из таблицы полей и демо-значений; cell(лист, ключ, ws, строка, формат даты) → True — Value записана им."""
    wb = xlsxwriter.Workbook(path)
    date_fmt = wb.add_format({"num_format": 14})
    for name, params in wf.PARAM_SHEETS.items():
        ws = wb.add_worksheet(name)
        ws.write_row(0, 0, wf.PARAM_HEADER)
        for r, p in enumerate(params, start=1):
            ws.write_row(r, 0, (p.key, p.label))
            ws.write_string(r, 3, p.unit)
            if not (cell and cell(name, p.key, ws, r, date_fmt)):
                ws.write(r, 2, p.demo)
    for name, columns in wf.TABLE_SHEETS.items():
        ws = wb.add_worksheet(name)
        ws.write_row(0, 0, [c.header for c in columns])
        for r, row in enumerate(wt.DEMO_TABLES[name], start=1):
            for c, v in enumerate(row):
                if v is not None:
                    ws.write(r, c, v)
    wb.add_worksheet("COMMENTS")
    wb.close()
    return path


def _excel_saved(path: Path) -> Path:
    """Книга, какой её сохраняет Excel: без пометки fullCalcOnLoad (FEAT-034, решение 9)."""
    with zipfile.ZipFile(path) as z:
        members = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    data = dict(members)
    text = data["xl/workbook.xml"].decode("utf-8")
    assert text.count(' fullCalcOnLoad="1"') == 1
    data["xl/workbook.xml"] = text.replace(' fullCalcOnLoad="1"', "").encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, _ in members:
            z.writestr(name, data[name])
    return path


# ── Книга генератора ─────────────────────────────────────────

def test_template_converts_and_builds(tmp_path):
    """Книга генератора → 4 файла; load_config, create_pvt, create_relperm и сборка решателя проходят.

    Решение 9 черновика: снимок генератора отстаёт от таблицы полей — новое
    поле, ключ или единица дают отказ перевода здесь, а не у заказчика.
    """
    path = convert_workbook(TEMPLATE, tmp_path / "case")
    assert path == tmp_path / "case" / "config.json"
    assert sorted(p.name for p in path.parent.iterdir()) == [
        "config.json", "gas_pvt.csv", "oil_pvt.csv", "relperm.csv"]
    cfg = load_config(path)
    create_pvt(cfg)
    create_relperm(cfg)
    sim, state = SimulatorFactory.from_config(cfg)
    assert state.p.shape == (100,)


def test_excel_saved_template_converts(tmp_path):
    """Книга после Excel (FEAT-034, шаг 3): формула =0.2/2 с сохранённым значением — r_w = 0.1 м."""
    cfg = load_config(convert_workbook(TEMPLATE_SAVED, tmp_path / "case"))
    assert cfg.geometry.r_well == 0.1
    assert cfg.output.title == "template_saved"


def test_param_cells_to_json_bitwise(tmp_path, book):
    """Ячейка Value → поле JSON: UNIT_TO_SI ячейки побитово; целые — int, постоянные слова — как есть."""
    raw = json.loads(convert_workbook(TEMPLATE, tmp_path / "c").read_text(encoding="utf-8"))
    for key, (sheet, p) in PARAMS.items():
        if key not in CONFIG_FIELDS:
            continue                                   # поля книги для составных полей
        cell = book.sheets[sheet].cell(_row(book, key), 3)
        section, name = key.split(".")
        if isinstance(p.demo, str):
            expected = p.demo
        elif p.limit.integer:
            expected = int(cell.value)
        else:
            expected = wf.UNIT_TO_SI[p.unit](cell.value)
        assert raw[section][name] == expected, key
        assert type(raw[section][name]) is type(expected), key


def test_table_cells_to_csv_bitwise(tmp_path, book):
    """Ячейка таблицы → CSV: заголовок — столбцы фабрики, числа — UNIT_TO_SI ячейки побитово."""
    out = convert_workbook(TEMPLATE, tmp_path / "c").parent
    for name, columns in (("OIL_PVT", wf.OIL_PVT), ("GAS_PVT", wf.GAS_PVT),
                          ("RELPERM", wf.RELPERM)):
        header, rows = _read_csv(out / wc.CSV_NAMES[name])
        assert header == [c.target for c in columns]
        sheet = book.sheets[name]
        expected = [tuple(wf.UNIT_TO_SI[c.unit](sheet.cell(r, i).value)
                          for i, c in enumerate(columns, start=1))
                    for r in range(2, sheet.max_row + 1)]
        assert rows == expected, name


def test_every_book_field_explicit(book):
    """В конфиге — каждое поле книги явно, составные поля, таблицы, заголовок; умолчаний не подставлено (решение 15)."""
    cfg, _ = workbook_to_config(book)
    written = {f"{s}.{n}" for s, sec in cfg.items() for n in sec}
    expected = ({k for k in PARAMS if k in CONFIG_FIELDS} | set(wf.DERIVED)
                | {"pvt.model", "pvt.oil_pvt_file", "pvt.gas_pvt_file", "relperm.model",
                   "relperm.file", "output.title"})
    assert written == expected
    # Ключи только книги — format_version и источники составных полей
    assert set(PARAMS) - CONFIG_FIELDS == {"format_version", "rock.porosity_ref", "rock.p_ref",
                                           "rock.rho_solid", "rock.c_solid"}


def test_integer_fields_written_as_int(tmp_path):
    """grid.N и лимиты Ньютона — целые в тексте JSON: Excel хранит 100 как 100.0."""
    path = convert_workbook(TEMPLATE, tmp_path / "c")
    text, raw = path.read_text(encoding="utf-8"), json.loads(path.read_text(encoding="utf-8"))
    for section, name, value in (("grid", "N", 100), ("numerics", "max_retries", 9),
                                 ("numerics", "newton_max_iter", 15),
                                 ("numerics", "max_active_set_iter", 12)):
        assert type(raw[section][name]) is int and raw[section][name] == value, name
        assert f'"{name}": {value}.0' not in text, name


def test_derived_porosity_and_rho_cp(book):
    """φ0 = φ_ref·exp(c_r·(p0 − p_ref)); (ρc_p)_s = ρ_ma·c_ma — 2650·820 Дж/(м³·К).

    При p_ref = 150 бар, p0 = 200 бар, c_r = 4.5e-5 1/бар: φ0 = 0.2·exp(2.25e-3).
    Обратно по закону породы решателя φ(p_ref) = φ0·exp(c_r·(p_ref − p0)) = φ_ref
    до округления — перенос опорной точки точный.
    """
    cfg, _ = workbook_to_config(book)
    assert cfg["rock"]["porosity"] == 0.2                    # p_ref = p0: exp(0) = 1
    assert cfg["rock"]["rho_cp_solid"] == 2173000.0
    cfg, _ = workbook_to_config(_set(book, "rock.p_ref", 150.0))
    c_r = wf.UNIT_TO_SI["1/bar"](4.5e-5)
    phi0 = cfg["rock"]["porosity"]
    assert phi0 == float(0.2 * np.exp(c_r * (2e7 - 1.5e7)))
    assert phi0 == pytest.approx(0.2 * np.exp(2.25e-3), rel=1e-14)
    assert phi0 * np.exp(c_r * (1.5e7 - 2e7)) == pytest.approx(0.2, rel=1e-14)


def test_porosity_above_one_refused(book):
    """φ0 > 1 — ошибка у ячейки φ_ref (умолчание 35): строки rock.porosity в книге нет.

    c_r = 0.05 1/бар, p0 − p_ref = 50 бар: φ0 = 0.2·exp(2.5) ≈ 2.44. Без этой
    проверки отказ дал бы _validate при расчёте: «porosity должна быть в (0, 1]».
    """
    b = _set(_set(book, "rock.compressibility", 0.05), "rock.p_ref", 150.0)
    error = _one_error(b)
    r = _row(book, "rock.porosity_ref")
    assert error.startswith(f"MODEL!C{r} (Reference porosity (φref))"), error
    assert "больше 1" in error and repr(float(0.2 * np.exp(0.05 / 1e5 * 5e6))) in error


def test_history_from_template(book):
    """22 интервала: строка k SCHEDULE (Excel k) — history[k − 2]; сумма — 30 сут ровно."""
    cfg, _ = workbook_to_config(book)
    history = cfg["time"]["history"]
    assert [h["dt"] for h in history] == TEMPLATE_DT
    assert sum(h["dt"] for h in history) == 30 * DAY_TO_S
    sheet = book.sheets["SCHEDULE"]
    for i, h in enumerate(history):
        # BHP: только p_wf — ячейки других режимов в интервал не попадают
        assert h == {"dt": TEMPLATE_DT[i], "control": "pressure",
                     "p_wf": sheet.cell(i + 2, 3).value * 1e5}


def test_title_and_output_section(book, tmp_path):
    """Секция output — только заголовок, имя книги без расширения (решение 11)."""
    cfg, _ = workbook_to_config(book)
    assert cfg["output"] == {"title": "INPUT_TEMPLATE_v1"}
    named = tmp_path / "скважина 7.xlsx"
    named.write_bytes(TEMPLATE.read_bytes())
    text = convert_workbook(named, tmp_path / "c").read_text(encoding="utf-8")
    assert '"title": "скважина 7"' in text                   # ensure_ascii=False — читаемо


def test_files_text_format(tmp_path):
    """config.json и CSV — UTF-8, окончания строк «\\n»; config.json кончается переводом строки."""
    out = convert_workbook(TEMPLATE, tmp_path / "c").parent
    for name in ("config.json", "oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        data = (out / name).read_bytes()
        assert b"\r" not in data and data.endswith(b"\n"), name


# ── SCHEDULE ─────────────────────────────────────────────────

def test_rate_rows_shut_in_and_foreign_cells(book, tmp_path):
    """OIL_RATE: дебит м³ст/сут → м³ст/с, min BHP бар → Па; останов — дебит 0; ячейки чужого режима не читаются.

    Строка BHP с заполненными дебитом и min BHP и строка OIL_RATE с заполненным
    BHP target: прочитанная ячейка чужого режима дала бы отказ load_config
    (_validate_interval: control='pressure' не использует q_oil).
    """
    b = _with_schedule(book, [
        (0.0, "OIL_RATE", 150.0, 50.0, 50.0),
        (1.0, "OIL_RATE", None, 0.0, 1.01325),
        (2.0, "BHP", 120.0, 30.0, 40.0),
        (3.0, None, None, None, None),
    ])
    cfg, tables = workbook_to_config(b)
    assert cfg["time"]["history"] == [
        {"dt": 86400.0, "control": "rate", "q_oil": 50.0 / 86400.0, "min_bhp": 5e6},
        {"dt": 86400.0, "control": "rate", "q_oil": 0.0,
         "min_bhp": wf.UNIT_TO_SI["bar(a)"](1.01325)},
        {"dt": 86400.0, "control": "pressure", "p_wf": 1.2e7},
    ]
    load_config(write_files(tmp_path / "c", cfg, tables))


def test_last_row_mode_not_read(book):
    """Режим последней строки не читается, даже неверный (решения 8, 40)."""
    base, _ = workbook_to_config(book)
    cfg, _ = workbook_to_config(_edit(book, "SCHEDULE", {(24, 2): "RATE", (24, 3): -5.0}))
    assert cfg["time"]["history"] == base["time"]["history"]


def test_moments_in_whole_ms_do_not_drift(book):
    """Моменты вне сетки 1 мс (k/7 сут, 15 цифр, как в ячейке Excel): моменты записи — в 0.5 мс от t_k (решение 19).

    Округление каждой разности (как в конвертере примера 18) сдвигало бы
    моменты на сумму ошибок: 12342.857142857… с → 12342.857 с, за 700
    интервалов — на 0.1 с.
    """
    t = [float(f"{k / 7:.15g}") for k in range(701)]
    rows = [(x, "BHP", 150.0, None, None) for x in t[:-1]] + [(t[-1], None, None, None, None)]
    cfg, _ = workbook_to_config(_with_schedule(book, rows))
    dts = [h["dt"] for h in cfg["time"]["history"]]
    acc, worst = 0.0, 0.0
    for k, dt in enumerate(dts, start=1):
        acc += dt
        worst = max(worst, abs(acc - t[k] * DAY_TO_S))
    # 0.5 мс — округление момента; 1e-5 с — запас на сложение 700 чисел в double
    assert worst <= 0.5e-3 + 1e-5, worst
    assert set(dts) <= {12342.857, 12342.858}


@pytest.mark.parametrize("rows, ref, text", [
    ([(0.5, "BHP", 150.0), (1.0,)], "SCHEDULE!A2", "первая строка — t = 0"),
    ([(0.0, "BHP", 150.0), (2.0, "BHP", 150.0), (1.0,)], "SCHEDULE!A4", "не позже предыдущего"),
    # 1e-9 сут = 86 мкс: после перевода в целые мс интервал нулевой
    ([(0.0, "BHP", 150.0), (1.0, "BHP", 150.0), (1.0 + 1e-9,)], "SCHEDULE!A4", "нулевой"),
    ([(0.0, "BHP", 150.0)], "SCHEDULE", "хотя бы две строки"),
    ([(0.0, "RATE", 150.0), (1.0,)], "SCHEDULE!B2", "нужен BHP или OIL_RATE"),
    ([(0.0, "bhp", 150.0), (1.0,)], "SCHEDULE!B2", "нужен BHP или OIL_RATE"),   # регистр — точно
    ([(0.0, None, 150.0), (1.0,)], "SCHEDULE!B2", "пусто"),
    ([(0.0, "BHP", None), (1.0,)], "SCHEDULE!C2", "пусто"),
    ([(0.0, "BHP", 0.0), (1.0,)], "SCHEDULE!C2", "> 0"),
    ([(0.0, "OIL_RATE", None, 50.0, None), (1.0,)], "SCHEDULE!E2", "пусто"),
    ([(0.0, "OIL_RATE", None, -1.0, 50.0), (1.0,)], "SCHEDULE!D2", "≥ 0"),
    ([(0.0, "BHP", 150.0), (("date", 46143),)], "SCHEDULE!A3", "дат"),
])
def test_schedule_errors(book, rows, ref, text):
    """Ошибка SCHEDULE — с адресом ячейки и причиной."""
    error = _one_error(_with_schedule(book, rows))
    assert error.startswith(ref) and text in error, error


def test_mode_with_spaces_accepted(book):
    """« BHP » из буфера обмена — BHP (решение 20)."""
    cfg, _ = workbook_to_config(_with_schedule(book, [(0.0, " BHP ", 150.0), (1.0,)]))
    assert cfg["time"]["history"] == [{"dt": 86400.0, "control": "pressure", "p_wf": 1.5e7}]


def test_empty_row_in_schedule_skipped(book):
    """Полностью пустая строка в SCHEDULE пропускается: история та же (решение 23)."""
    base, _ = workbook_to_config(book)
    cfg, _ = workbook_to_config(_shift_down(book, "SCHEDULE", 10))
    assert cfg["time"]["history"] == base["time"]["history"]


# ── Таблицы ──────────────────────────────────────────────────

@pytest.mark.parametrize("sheet, at", [("OIL_PVT", 10), ("GAS_PVT", 5), ("RELPERM", 8)])
def test_empty_row_in_table_skipped(book, sheet, at):
    """Пустая строка внутри таблицы пропускается, строки ниже читаются (решение 23)."""
    _, base = workbook_to_config(book)
    _, tables = workbook_to_config(_shift_down(book, sheet, at))
    assert tables == base


def test_cells_right_of_tables_not_read(book):
    """Ячейки правее последнего столбца таблицы не читаются (решение 24)."""
    _, base = workbook_to_config(book)
    b = _edit(book, "OIL_PVT", {(5, 5): "заметка", (1, 5): "Note"})
    b = _edit(b, "SCHEDULE", {(3, 6): 1.0})
    _, tables = workbook_to_config(b)
    assert tables == base


def test_table_header_with_spaces_accepted(book):
    """Заголовок с пробелами по краям — тот же заголовок (решение 20)."""
    workbook_to_config(_edit(book, "OIL_PVT", {(1, 2): "  Pressure, bar(a) "}))


@pytest.mark.parametrize("sheet, cell, value, text", [
    ("OIL_PVT", (1, 2), "Pressure, bar", "заголовок"),
    ("OIL_PVT", (5, 1), "1,5", "текст"),
    ("OIL_PVT", (5, 3), ("date", 46143), "дат"),
    ("OIL_PVT", (5, 4), None, "пусто"),                     # строка заполнена частично
    ("GAS_PVT", (3, 2), -1.0, "> 0"),
    ("GAS_PVT", (3, 3), ("error", "#DIV/0!"), "ошибка Excel #DIV/0!"),
    ("RELPERM", (5, 2), 1.5, "от 0 до 1"),
    ("RELPERM", (5, 3), True, "логическое"),
])
def test_table_cell_errors(book, sheet, cell, value, text):
    """Ошибка ячейки таблицы — с адресом и причиной."""
    error = _one_error(_edit(book, sheet, {cell: value}))
    r, c = cell
    assert error.startswith(Cell(sheet, r, c).ref) and text in error, error


@pytest.mark.parametrize("cell, value, ref", [
    ((2, 1), 0.02, "RELPERM!A2"),                 # первая строка — Sg = 0
    ((2, 3), 0.1, "RELPERM!C2"),                  # и krg = 0
    ((17, 1), 0.9, "RELPERM!A17"),                # последняя — Sg = 1
    ((17, 2), 0.1, "RELPERM!B17"),                # и kro = 0
])
def test_relperm_end_rows(book, cell, value, ref):
    """Крайние строки RELPERM проверяет перевод: защита листа без пароля (решение 17)."""
    error = _one_error(_edit(book, "RELPERM", {cell: value}))
    assert error.startswith(ref) and "строка таблицы" in error, error


def test_relperm_without_rows(book):
    cells = {(1, c): book.sheets["RELPERM"].cell(1, c).value for c in (1, 2, 3)}
    b = Workbook(book.path, {**book.sheets, "RELPERM": Sheet("RELPERM", {
        k: _value_cell("RELPERM", *k, v) for k, v in cells.items()})}, False)
    assert "нет строк" in _one_error(b)


def test_relperm_ends_not_checked_after_cell_error(book):
    """Строка с ошибкой ячейки — одна ошибка: «первой» не становится следующая строка."""
    error = _one_error(_edit(book, "RELPERM", {(2, 1): "x"}))
    assert error.startswith("RELPERM!A2") and "текст" in error


# ── Листы «параметр–значение» ────────────────────────────────

@pytest.mark.parametrize("sheet", ["MODEL", "THERMAL", "NUMERICS", "SCHEDULE", "OIL_PVT",
                                   "GAS_PVT", "RELPERM"])
def test_missing_sheet(book, sheet):
    sheets = {n: s for n, s in book.sheets.items() if n != sheet}
    error = _one_error(Workbook(book.path, sheets, False))
    assert error.startswith(f"нет листа {sheet}") and "gpn-solver template" in error


def test_comments_and_extra_sheets_not_read(book):
    """COMMENTS не нужен, лишний лист пропускается (решение 10)."""
    sheets = {n: s for n, s in book.sheets.items() if n != "COMMENTS"}
    sheets["NOTES"] = Sheet("NOTES", {(1, 1): Cell("NOTES", 1, 1, STRING, "x")})
    workbook_to_config(Workbook(book.path, sheets, False))


@pytest.mark.parametrize("value, text", [
    (2.0, "версия формата 2.0"),
    ("1", "версия формата '1'"),
    (None, "версия формата пусто"),
])
def test_format_version(book, value, text):
    """Книга другой версии — одна ошибка, прочие проверки не делаются (решение 15)."""
    b = _set(_set(book, "format_version", value), "rock.permeability", -1.0)
    error = _one_error(b)
    assert error.startswith("MODEL!C2") and text in error, error


def test_format_version_row_missing(book):
    b = _edit(book, "MODEL", {(_row(book, "format_version"), c): None for c in range(1, 7)})
    assert "нет строки format_version" in _one_error(b)


def test_param_header_mismatch(book):
    """Неверный заголовок листа — ошибка заголовка; строки листа не читаются."""
    b = _set(_edit(book, "MODEL", {(1, 3): "Значение"}), "rock.permeability", -1.0)
    assert _one_error(b).startswith("MODEL!C1")


def test_unknown_and_foreign_keys(book):
    """Неизвестный ключ и ключ другого листа — ошибки с адресом; строка ключа другого листа названа."""
    r = _row(book, "rock.permeability")
    errors = _errors(_edit(book, "MODEL", {(r, 1): "rock.perm"}))
    assert errors[0].startswith(f"MODEL!A{r}") and "неизвестный ключ 'rock.perm'" in errors[0]
    assert "нет строки rock.permeability" in errors[1]
    errors = _errors(_edit(book, "MODEL", {(r, 1): "grid.N"}))
    assert "листа NUMERICS" in errors[0]


def test_duplicate_key(book):
    r = _row(book, "geometry.h")
    b = _edit(book, "MODEL", {(30, 1): "geometry.h", (30, 3): 5.0, (30, 4): "m"})
    error = _one_error(b)
    assert error.startswith("MODEL!A30") and f"уже в строке {r}" in error


def test_missing_key_row(book):
    """Нет строки ключа — отказ, умолчание конфига не подставляется (решение 15)."""
    r = _row(book, "numerics.newton_cell_tol")
    b = _edit(book, "NUMERICS", {(r, c): None for c in range(1, 7)})
    assert "нет строки numerics.newton_cell_tol" in _one_error(b)


def test_row_without_key(book):
    """Строка без ключа, но со значением — ошибка; пустая строка — пропускается (решение 25)."""
    error = _one_error(_edit(book, "THERMAL", {(20, 3): 5.0}))
    assert error.startswith("THERMAL!A20") and "без ключа" in error
    workbook_to_config(_edit(book, "THERMAL", {(20, 5): "comment"}))    # Comment — не данные
    workbook_to_config(_shift_down(book, "THERMAL", 5))


def test_key_and_unit_with_spaces_accepted(book):
    """Пробелы по краям ключа и единицы срезаются (решение 20)."""
    r = _row(book, "rock.permeability")
    workbook_to_config(_edit(book, "MODEL", {(r, 1): " rock.permeability ", (r, 4): "mD "}))


def test_unit_mismatch(book):
    r = _row(book, "rock.permeability")
    error = _one_error(_set(book, "rock.permeability", "md", col=4))
    assert error.startswith(f"MODEL!D{r}") and "нужна 'mD'" in error


@pytest.mark.parametrize("value, recalc, text", [
    (None, False, "пусто"),
    ("1,5", False, "текст '1,5'"),
    ("1.5", False, "текст '1.5'"),                           # число строкой — тоже отказ
    (True, False, "логическое значение TRUE"),
    (("error", "#DIV/0!"), False, "ошибка Excel #DIV/0!"),
    (("date", 46143), False, "с форматом даты"),
    (("formula", "0.2/2"), False, "введите число вместо формулы"),
    (("formula", "0.2/2"), True, "пересчитать при открытии"),
    (("formula", ""), True, "общая формула без сохранённого значения"),   # ячейка общей формулы
])
def test_value_kinds(book, value, recalc, text):
    """Тип ячейки Value — отказ с адресом и подсказкой (решение 6; FEAT-034 решение 9)."""
    r = _row(book, "geometry.r_well")
    error = _one_error(_set(book, "geometry.r_well", value, recalc=recalc))
    assert error.startswith(f"MODEL!C{r} (Wellbore radius (rw))") and text in error, error


@pytest.mark.parametrize("key, value, text", [
    ("rock.permeability", 0.0, "нужно число > 0"),
    ("rock.porosity_ref", 1.5, "нужно число в (0, 1]"),
    ("rock.compressibility", -1e-5, "нужно число ≥ 0"),
    ("numerics.max_retries", 21.0, "нужно целое число от 0 до 20"),
    ("grid.N", 100.5, "нужно целое число ≥ 1"),
    ("geometry.R_ext", 0.05, "нужно число больше, чем Wellbore radius (rw)"),
    ("thermal.mu_JT_oil", float("inf"), "нужно конечное число"),
])
def test_limits(book, key, value, text):
    """Предел строки — как у программы (решение 50 FEAT-033); проверяется заново: вставка обходит Excel."""
    assert text in _one_error(_set(book, key, value))


def test_above_skipped_when_reference_invalid(book):
    """r_w с ошибкой — одна ошибка: сравнение r_e > r_w не делается."""
    b = _set(_set(book, "geometry.r_well", "x"), "geometry.R_ext", 0.05)
    assert "Wellbore radius" in _one_error(b)


def test_integer_from_float(book):
    """Целое поле из вещественной ячейки: 200.0 → 200, 0 → 0 (max_retries от 0)."""
    cfg, _ = workbook_to_config(_set(_set(book, "grid.N", 200.0), "numerics.max_retries", 0.0))
    assert (cfg["grid"]["N"], cfg["numerics"]["max_retries"]) == (200, 0)
    assert type(cfg["grid"]["N"]) is int


@pytest.mark.parametrize("key, value, ok", [
    ("numerics.jacobian_mode", "reference", False),
    ("numerics.jacobian_mode", " grouped ", True),
    ("numerics.linear_solver", "dense", False),
    ("numerics.linear_solver", 1.0, False),
])
def test_fixed_values(book, key, value, ok):
    """Постоянные строки — только своё значение (решение 65 FEAT-033): книга строже JSON."""
    b = _set(book, key, value)
    if ok:
        workbook_to_config(b)
    else:
        assert "значение постоянное" in _one_error(b)


# ── Сообщение ────────────────────────────────────────────────

def test_all_errors_at_once_in_sheet_order(book):
    """Все ошибки одним сообщением, в порядке листов книги (решение 22)."""
    b = _set(book, "grid.N", 0.0)
    b = _set(b, "rock.permeability", -1.0)
    b = _edit(b, "GAS_PVT", {(3, 2): "x"})
    b = _edit(b, "SCHEDULE", {(5, 2): "RATE"})
    with pytest.raises(WorkbookContentError) as e:
        workbook_to_config(b)
    refs = [err.split(" ")[0] for err in e.value.errors]
    assert [r.split("!")[0] for r in refs] == ["MODEL", "NUMERICS", "SCHEDULE", "GAS_PVT"]
    text = str(e.value)
    assert text.startswith(f"{book.path}: книга не переведена, ошибок — 4:")
    assert all(r in text for r in refs)


def test_error_list_capped(book):
    """Ошибок больше MAX_ERRORS — первые MAX_ERRORS и число остальных."""
    sheet = book.sheets["OIL_PVT"]
    b = _edit(book, "OIL_PVT", {(r, 3): "x" for r in range(2, sheet.max_row + 1)})
    with pytest.raises(WorkbookContentError) as e:
        workbook_to_config(b)
    n = len(e.value.errors)
    assert n == sheet.max_row - 1 > MAX_ERRORS
    lines = str(e.value).splitlines()
    assert len(lines) == 1 + MAX_ERRORS + 1 and lines[-1] == f"  … и ещё {n - MAX_ERRORS}"


def test_content_error_is_workbook_error():
    """Один тип для вызывающих (FEAT-036): ошибки перевода — подкласс WorkbookError и ValueError."""
    assert issubclass(WorkbookContentError, WorkbookError)
    assert issubclass(WorkbookContentError, ValueError)


# ── convert_workbook: файлы и каталог ────────────────────────

def test_convert_into_empty_existing_dir(tmp_path):
    (tmp_path / "c").mkdir()
    assert convert_workbook(TEMPLATE, tmp_path / "c").is_file()


@pytest.mark.parametrize("make", [
    lambda d: (d.mkdir(), (d / "old.txt").write_text("old", encoding="utf-8")),
    lambda d: d.write_text("file", encoding="utf-8"),
])
def test_convert_refuses_non_empty_dir_or_file(tmp_path, make):
    """Непустой каталог или файл на месте каталога — FileExistsError, ничего не изменено (решение 10)."""
    out = tmp_path / "c"
    make(out)
    before = sorted(p.name for p in out.iterdir()) if out.is_dir() else out.read_bytes()
    with pytest.raises(FileExistsError, match="не пустой каталог"):
        convert_workbook(TEMPLATE, out)
    after = sorted(p.name for p in out.iterdir()) if out.is_dir() else out.read_bytes()
    assert after == before


def test_book_error_leaves_no_files(tmp_path):
    """Книга с ошибкой — отказ до записи: каталог не создан."""
    def negative_h(sheet, key, ws, r, fmt):
        if key != "geometry.h":
            return False
        ws.write_number(r, 2, -1.0)
        return True
    book = _write_book(tmp_path / "b.xlsx", negative_h)
    with pytest.raises(WorkbookContentError, match="Formation thickness"):
        convert_workbook(_excel_saved(book), tmp_path / "c")
    assert not (tmp_path / "c").exists()


def test_reader_errors_pass_through(tmp_path):
    """Нет файла — FileNotFoundError; не книга .xlsx — WorkbookError разбора, не ошибка перевода."""
    with pytest.raises(FileNotFoundError):
        convert_workbook(tmp_path / "нет.xlsx", tmp_path / "c")
    fake = tmp_path / "fake.xlsx"
    fake.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(WorkbookError, match="не zip") as e:
        convert_workbook(fake, tmp_path / "c")
    assert not isinstance(e.value, WorkbookContentError)


# ── Сквозь разбор: книги XlsxWriter ──────────────────────────

def test_xlsxwriter_book_equals_template(tmp_path, book):
    """Книга из таблицы полей и демо-значений (XlsxWriter, без оформления) — тот же конфиг, что у генератора."""
    path = _excel_saved(_write_book(tmp_path / "plain.xlsx"))
    cfg, tables = workbook_to_config(read_workbook(path))
    base_cfg, base_tables = workbook_to_config(book)
    cfg["output"] = base_cfg["output"]                       # имена книг разные
    assert (cfg, tables) == (base_cfg, base_tables)


def _formula_book(tmp_path: Path, saved: bool) -> Workbook:
    """Книга с h0 формулой =0.11/3600 (часы); saved — сохранена Excel (без пометки пересчёта)."""
    def h0(sheet, key, ws, r, fmt):
        if key != "time.dt_after_control_change":
            return False
        ws.write_formula(r, 2, "=0.11/3600", None, 0.11 / 3600)
        return True
    path = _write_book(tmp_path / f"f{int(saved)}.xlsx", h0)
    return read_workbook(_excel_saved(path) if saved else path)


def test_formula_with_saved_value_accepted(tmp_path):
    """Формула с сохранённым значением допустима (решение 26 FEAT-033): h0 = значение ячейки × 3600 с."""
    b = _formula_book(tmp_path, saved=True)
    cell = b.sheets["NUMERICS"].cell(_row(b, "time.dt_after_control_change"), 3)
    assert cell.formula == "0.11/3600"
    cfg, _ = workbook_to_config(b)
    assert cfg["time"]["dt_after_control_change"] == cell.value * 3600.0


def test_formula_in_recalc_book_refused(tmp_path):
    """Книга XlsxWriter с пометкой пересчёта: значения формулы нет — отказ с подсказкой (FEAT-034 решение 9)."""
    error = _one_error(_formula_book(tmp_path, saved=False))
    assert "NUMERICS!C" in error and "пересчитать при открытии" in error


def test_date_cell_through_reader(tmp_path):
    """Ячейка с форматом даты (Excel с русскими настройками: «1.5» → 1 мая) — отказ."""
    def date(sheet, key, ws, r, fmt):
        if key != "rock.permeability":
            return False
        ws.write_number(r, 2, 46143, fmt)
        return True
    b = read_workbook(_excel_saved(_write_book(tmp_path / "d.xlsx", date)))
    assert "с форматом даты" in _one_error(b)
