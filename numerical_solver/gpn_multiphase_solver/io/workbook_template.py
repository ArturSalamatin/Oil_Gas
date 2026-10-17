"""Шаблон книги ввода версии 1 с демонстрационными значениями: gpn-solver template (FEAT-033)."""

from __future__ import annotations

import io
from pathlib import Path

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from . import workbook_format as wf

# Строк в листе Excel: проверки данных таблиц — на весь столбец (нестыковка 8)
EXCEL_ROWS = 1_048_576

# ── Демонстрационные таблицы, единицы книги ──
# SCHEDULE и GAS_PVT, RELPERM — книга прототипа INPUT_TEMPLATE.xlsx (равны
# черновику руководителя); OIL_PVT — T08c прототипа: черновик + ветвь R_s = 60.
# Последняя строка SCHEDULE — только момент завершения (решение 32).
# Числа — с 15 значащими цифрами (решение 63): у источников их 17, а XlsxWriter
# пишет 16 ({:.16G}) — 17-значное число в книге сдвинулось бы (до 5e-16).
# Число с ≤ 16 цифрами запись не меняет, 15 — точность набранного числа в
# Excel: книга равна литералам бит в бит. Отклонение от источников — до 5e-15.
# (t_day, mode, bhp_bar, rate_sm3_day, min_bhp_bar); None — пустая ячейка
DEMO_SCHEDULE = (
    (0.0, "BHP", 150.0, None, None),
    (0.000694444444444444, "BHP", 150.0, None, None),
    (1.0, "BHP", 150.0, None, None),
    (2.0, "BHP", 150.0, None, None),
    (4.0, "BHP", 150.0, None, None),
    (5.0, "BHP", 120.0, None, None),
    (5.00011574074074, "BHP", 120.0, None, None),
    (5.00023148148148, "BHP", 120.0, None, None),
    (5.00034722222222, "BHP", 120.0, None, None),
    (5.00046296296296, "BHP", 120.0, None, None),
    (5.0005787037037, "BHP", 120.0, None, None),
    (5.00069444444444, "BHP", 120.0, None, None),
    (6.0, "BHP", 120.0, None, None),
    (14.0, "BHP", 120.0, None, None),
    (15.0, "BHP", 100.0, None, None),
    (15.0001157407407, "BHP", 100.0, None, None),
    (15.0002314814815, "BHP", 100.0, None, None),
    (15.0003472222222, "BHP", 100.0, None, None),
    (15.000462962963, "BHP", 100.0, None, None),
    (15.0005787037037, "BHP", 100.0, None, None),
    (15.0006944444444, "BHP", 100.0, None, None),
    (16.0, "BHP", 100.0, None, None),
    (30.0, None, None, None, None),
)
# (Rs, p_bar, Bo, mu_o_cP)
DEMO_OIL_PVT = (
    (5.0, 24.507516328979, 1.04514631667819, 5.6450092402544),
    (5.0, 49.507516328979, 1.04201557618695, 5.75185168126232),
    (5.0, 74.507516328979, 1.03889421384293, 5.86071631686988),
    (5.0, 124.507516328979, 1.03267951131156, 6.08466599166751),
    (5.0, 300.0, 1.01115960248163, 6.94062062147152),
    (10.0, 45.4982821854944, 1.05496911285377, 4.65991245464173),
    (10.0, 70.4982821854944, 1.05180894813242, 4.74811008202324),
    (10.0, 95.4982821854944, 1.04865824969869, 4.83797701576006),
    (10.0, 145.498282185494, 1.04238513835386, 5.02284577936822),
    (10.0, 300.0, 1.02323715528014, 5.63993730754341),
    (20.0, 82.813259392784, 1.07513105012211, 3.4643521134975),
    (20.0, 107.813259392784, 1.07191049022701, 3.52992150772942),
    (20.0, 132.813259392784, 1.06869957753355, 3.59673192634889),
    (20.0, 182.813259392784, 1.0623065782452, 3.73417023622264),
    (20.0, 300.0, 1.04747253444172, 4.07722125070953),
    (30.0, 116.9397098221, 1.09590090359181, 2.76827699103872),
    (30.0, 141.9397098221, 1.09261812750725, 2.82067185144028),
    (30.0, 166.9397098221, 1.0893451849932, 2.87405838334198),
    (30.0, 216.9397098221, 1.0828286829389, 2.98388189389923),
    (30.0, 300.0, 1.0720894841505, 3.17567535321494),
    (40.0, 149.147548169977, 1.11720467055256, 2.31375526975003),
    (40.0, 174.147548169977, 1.11385807893827, 2.35754744977911),
    (40.0, 199.147548169977, 1.1105215120542, 2.40216847936577),
    (40.0, 249.147548169977, 1.10387833245021, 2.49396013428935),
    (40.0, 300.0, 1.09716265344739, 2.59091527510286),
    (50.0, 180.0, 1.13898576612303, 1.99384701056588),
    (50.0, 205.0, 1.13557392913902, 2.03158432374619),
    (50.0, 230.0, 1.13217231232803, 2.07003588671523),
    (50.0, 280.0, 1.12539961685854, 2.14913609197767),
    (50.0, 300.0, 1.12270189633761, 2.1816161246037),
    (60.0, 210.852451830023, 1.16076686169351, 1.67393875138173),
    (60.0, 235.852451830023, 1.15728977933977, 1.70562119771327),
    (60.0, 260.852451830023, 1.15382311260186, 1.73790329406469),
    (60.0, 300.0, 1.14824113922783, 1.77231697410453),
)
# (p_bar, Bg, mu_g_cP)
DEMO_GAS_PVT = (
    (10.0, 0.113716731005424, 0.0127198827764876),
    (20.0, 0.0560470307800101, 0.0128612191598994),
    (30.0, 0.0368541891865489, 0.013031582727123),
    (40.0, 0.027281962748336, 0.0132267897417917),
    (50.0, 0.0215590350342354, 0.0134449118486729),
    (75.0, 0.0139919318901466, 0.0140838755340569),
    (100.0, 0.0102802763524721, 0.0148476225818994),
    (125.0, 0.00811204058606345, 0.0157238560253021),
    (150.0, 0.00671379622979356, 0.0166968489784585),
    (175.0, 0.00575210667575148, 0.0177482733307558),
    (200.0, 0.00505920896438668, 0.0188593274804743),
    (225.0, 0.00454160275494752, 0.0200126756217303),
    (250.0, 0.00414334113369232, 0.0211935731021485),
)
# (Sg, kro, krg)
DEMO_RELPERM = (
    (0.0, 1.0, 0.0),
    (0.02, 1.0, 0.0),
    (0.04, 1.0, 0.0),
    (0.06, 0.951226947111721, 0.000487730528882792),
    (0.08, 0.903673220545649, 0.00195092211553117),
    (0.1, 0.857338820301783, 0.00438957475994513),
    (0.15, 0.746837372351776, 0.0147538484987045),
    (0.2, 0.643956713915562, 0.0312147538484987),
    (0.3, 0.461057765584514, 0.0824264593811919),
    (0.4, 0.308641975308642, 0.158024691358025),
    (0.5, 0.186709343087944, 0.258009449778997),
    (0.6, 0.0952598689224204, 0.382380734644109),
    (0.7, 0.0342935528120713, 0.531138545953361),
    (0.8, 0.00381039475689681, 0.704282883706752),
    (0.85, 0.0, 0.8),
    # Обязательная последняя строка S_g = 1 (решение 68). k_rg — как при 0.85:
    # выше последней строки таблицы фабрика и так брала её значения, расчёт тот же
    (1.0, 0.0, 0.8),
)
DEMO_TABLES = {"SCHEDULE": DEMO_SCHEDULE, "OIL_PVT": DEMO_OIL_PVT,
               "GAS_PVT": DEMO_GAS_PVT, "RELPERM": DEMO_RELPERM}

# Лист COMMENTS: тема, текст по-английски, текст по-русски (решение 67).
# Строку «Run» добавит FEAT-036 (решение 62)
COMMENTS = (
    ("Template",
     "gpn-solver template my_case.xlsx writes this workbook with demonstration values. "
     "The command never overwrites an existing file.",
     "Команда gpn-solver template my_case.xlsx создаёт эту книгу с демонстрационными "
     "значениями. Существующий файл команда не перезаписывает."),
    ("Fill in",
     "On MODEL, THERMAL and NUMERICS change only the Value column. Every row needs a value, "
     "even if it equals the program default; rows are not added or removed.",
     "На листах MODEL, THERMAL и NUMERICS меняйте только столбец Value. Значение нужно в "
     "каждой строке, даже если оно совпадает с принятым в программе по умолчанию; строки "
     "не добавляются и не удаляются."),
    ("Protection",
     "MODEL, THERMAL, NUMERICS and RELPERM are protected without a password. Locked: Key, "
     "Unit, the format version, Jacobian mode, Linear solver and the fixed cells of RELPERM. "
     "Review > Unprotect Sheet removes the protection.",
     "Листы MODEL, THERMAL, NUMERICS и RELPERM защищены без пароля. Заблокированы Key, "
     "Unit, версия формата, Jacobian mode, Linear solver и постоянные ячейки RELPERM. "
     "Защиту снимает команда Рецензирование > Снять защиту листа."),
    ("Units",
     "Units are fixed for every row and table column and are checked when the workbook is "
     "read; convert your data to these units. bar(a): absolute pressure in bar. Sm3: cubic "
     "metre at standard conditions; rm3: cubic metre at reservoir conditions.",
     "Единицы измерения заданы для каждой строки и каждого столбца таблиц и проверяются при "
     "чтении книги; данные нужно перевести в эти единицы. bar(a): абсолютное давление в "
     "барах. Sm3: кубический метр при стандартных условиях; rm3: кубический метр в "
     "пластовых условиях."),
    ("Excel checks",
     "Numeric cells carry Excel data validation with the program limits. Pasted values and "
     "cleared cells bypass it; the program checks every value again.",
     "У числовых ячеек есть проверка данных Excel с пределами программы. Вставка из буфера "
     "обмена и очистка ячейки её обходят, поэтому программа проверяет все значения ещё раз."),
    ("SCHEDULE",
     "Row k sets the well control on [t_k, t_k+1]. The first row is t = 0; the last row only "
     "ends the run, its control cells are not used. Every row is a report time. Cells not "
     "used by the row's control mode are ignored.",
     "Строка k задаёт режим скважины на отрезке [t_k, t_k+1]. В первой строке t = 0; "
     "последняя строка только завершает расчёт, режим в ней не читается. В каждый момент из "
     "таблицы записываются результаты. Ячейки, которые режим строки не использует, не "
     "читаются."),
    ("Control modes",
     "BHP: BHP target. OIL_RATE: Oil-rate target (stock-tank oil) and Minimum BHP. "
     "Shut-in: OIL_RATE with rate 0 and Minimum BHP 1.01325 bar(a).",
     "BHP: задано забойное давление (BHP target). OIL_RATE: заданы дебит нефти при "
     "стандартных условиях (Oil-rate target) и наименьшее забойное давление (Minimum BHP). "
     "Остановка скважины: OIL_RATE с дебитом 0 и Minimum BHP 1.01325 bar(a)."),
    ("Time steps",
     "Δt and h0 on NUMERICS are in hours. Each SCHEDULE interval is split into equal "
     "substeps not longer than Δt; after a change of control (not at t = 0) the first "
     "substep shrinks to h0, rounded down to substep/2^m, then doubles. h0 not less than Δt "
     "switches this off.",
     "Δt и h0 на листе NUMERICS задаются в часах. Каждый интервал SCHEDULE делится на "
     "равные подшаги не длиннее Δt. После смены режима (кроме t = 0) первый подшаг "
     "уменьшается до h0, округлённого вниз до подшага/2^m, и дальше удваивается; при h0 не "
     "меньше Δt подшаг не уменьшается."),
    ("OIL_PVT",
     "PVTO-style table grouped by Rs: at least two Rs values, at least two rows each. The "
     "first row of each Rs is saturated (p = Pb(Rs)); higher pressures are undersaturated "
     "rows at fixed Rs, pressure increasing. Pb grows with Rs. Rsi on MODEL lies within the "
     "Rs range, pi not below Pb(Rsi).",
     "Таблица в форме PVTO, строки сгруппированы по Rs: не меньше двух значений Rs и не "
     "меньше двух строк на каждое. Первая строка группы описывает насыщенную нефть "
     "(p = Pb(Rs)), следующие, с ростом давления, недонасыщенную нефть при том же Rs. "
     "Давление насыщения Pb растёт с Rs. Rsi на листе MODEL лежит в диапазоне Rs таблицы, "
     "начальное давление pi не ниже Pb(Rsi)."),
    ("GAS_PVT",
     "At least two rows, pressure increasing.",
     "Не меньше двух строк, давление возрастает."),
    ("RELPERM",
     "Sg increases from the first row, Sg = 0 with krg = 0, to the last row, Sg = 1 with "
     "kro = 0; these cells are locked. Add or remove intermediate points by inserting or "
     "deleting worksheet rows between the first and the last row.",
     "Sg возрастает от первой строки, Sg = 0 и krg = 0, до последней, Sg = 1 и kro = 0; эти "
     "ячейки заблокированы. Промежуточные точки добавляйте и удаляйте вставкой и удалением "
     "строк листа между первой и последней строкой."),
)


def write_template(path) -> None:
    """Записать шаблон книги версии 1 в новый файл path (.xlsx); существующий — FileExistsError."""
    path = Path(path)
    if path.suffix.lower() != ".xlsx":
        raise ValueError(f"шаблон книги пишется в файл .xlsx, получено {path.name!r}")
    buf = io.BytesIO()
    book = xlsxwriter.Workbook(buf, {"in_memory": True})
    fmt = _formats(book)
    for name, params in wf.PARAM_SHEETS.items():
        _param_sheet(book, name, params, fmt)
    for name, columns in wf.TABLE_SHEETS.items():
        _table_sheet(book, name, columns, DEMO_TABLES[name], fmt)
    _comments_sheet(book, fmt)
    book.close()
    # «x» — только новый файл: заполненную книгу команда не перезаписывает
    # (решение 58). Книга собрана в памяти — при ошибке построения файла нет
    with open(path, "xb") as f:
        f.write(buf.getvalue())


def excel_rule(limit: wf.Limit, cell: str, above_cell: str | None = None) -> str:
    """Формула проверки данных Excel для ячейки cell по пределу limit (решение 50)."""
    parts = [f"ISNUMBER({cell})"]
    if limit.integer:
        parts.append(f"{cell}=INT({cell})")
    if limit.lo is not None:
        parts.append(f"{cell}{'>' if limit.lo_strict else '>='}{limit.lo:g}")
    if limit.hi is not None:
        parts.append(f"{cell}<={limit.hi:g}")
    if limit.above_key is not None:
        parts.append(f"{cell}>{above_cell}")
    return f"=AND({','.join(parts)})"


def limit_text(limit: wf.Limit, above_label: str | None = None) -> str:
    """Сообщение Excel о недопустимом значении: какое значение ждёт ячейка."""
    what = "an integer" if limit.integer else "a number"
    lo, hi = limit.lo, limit.hi
    if lo is not None and hi is not None:
        rng = (f" equal to {lo:g}" if lo == hi else
               f" in ({lo:g}, {hi:g}]" if limit.lo_strict else f" from {lo:g} to {hi:g}")
    elif lo is not None:
        rng = f" {'>' if limit.lo_strict else '>='} {lo:g}"
    elif limit.above_key is not None:
        rng = f" > {above_label}"
    else:
        rng = ""
    return f"Enter {what}{rng}."


def _formats(book) -> dict:
    """Форматы ячеек: заголовок, заблокированные Key/Unit, ввод Value, текст (П11)."""
    return {
        "header": book.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1}),
        "locked": book.add_format({"bg_color": "#F2F2F2"}),
        "text": book.add_format({"locked": False}),
        "value": book.add_format({"locked": False, "bg_color": "#FFF2CC"}),
        "comment": book.add_format({"locked": False, "text_wrap": True, "valign": "top"}),
        "title": book.add_format({"bold": True, "font_size": 12}),
        "topic": book.add_format({"bold": True, "valign": "top"}),
        "wrap": book.add_format({"text_wrap": True, "valign": "top"}),
    }


def _param_sheet(book, name: str, params, fmt: dict) -> None:
    """Лист «параметр–значение»: Key | Parameter | Value | Unit | Comment | Комментарии."""
    ws = book.add_worksheet(name)
    ws.write_row(0, 0, wf.PARAM_HEADER, fmt["header"])
    row_of = {p.key: r for r, p in enumerate(params, start=1)}
    for r, p in enumerate(params, start=1):
        ws.write_string(r, 0, p.key, fmt["locked"])
        ws.write_string(r, 1, p.label, fmt["text"])
        value_fmt = fmt["locked"] if p.fixed else fmt["value"]
        if isinstance(p.demo, str):
            ws.write_string(r, 2, p.demo, value_fmt)
        else:
            ws.write_number(r, 2, p.demo, value_fmt)
        ws.write_string(r, 3, p.unit, fmt["locked"])
        ws.write_string(r, 4, p.comment, fmt["comment"])
        ws.write_string(r, 5, p.comment_ru, fmt["comment"])
        if p.fixed:
            continue          # постоянное значение заблокировано — проверка данных не нужна
        above_key = p.limit.above_key
        above_cell = xl_rowcol_to_cell(row_of[above_key], 2) if above_key else None
        above_label = params[row_of[above_key] - 1].label if above_key else None
        ws.data_validation(r, 2, r, 2, {
            "validate": "custom",
            "value": excel_rule(p.limit, xl_rowcol_to_cell(r, 2), above_cell),
            "ignore_blank": False, "error_title": "Invalid value",
            "error_message": limit_text(p.limit, above_label)})
    for col, width in enumerate((34, 46, 16, 10, 70, 70)):
        ws.set_column(col, col, width)
    ws.freeze_panes(1, 0)
    ws.protect("", {"format_columns": True, "format_rows": True})


def _table_sheet(book, name: str, columns, rows, fmt: dict) -> None:
    """Табличный лист: заголовки, строки, проверки на весь столбец; RELPERM защищён (решение 68)."""
    ws = book.add_worksheet(name)
    ws.write_row(0, 0, [c.header for c in columns], fmt["header"])
    relperm = name == "RELPERM"
    for r, row in enumerate(rows, start=1):
        # Обязательные строки RELPERM: число в образце — постоянная ячейка
        pattern = ()
        if relperm and r == 1:
            pattern = wf.RELPERM_FIRST_ROW
        elif relperm and r == len(rows):
            pattern = wf.RELPERM_LAST_ROW
        elif relperm:
            # Промежуточная строка разблокирована целиком, а не только в A…C:
            # строку с заблокированной ячейкой Excel на защищённом листе не удалит
            ws.set_row(r, None, fmt["text"])
        for c, v in enumerate(row):
            if v is None:
                continue                      # пустая ячейка
            cell_fmt = None                   # листы без защиты — формат не нужен
            if relperm:
                cell_fmt = fmt["locked"] if pattern and pattern[c] is not None else fmt["text"]
            if isinstance(v, str):
                ws.write_string(r, c, v, cell_fmt)
            else:
                ws.write_number(r, c, v, cell_fmt)
    for c, col in enumerate(columns):
        if name == "SCHEDULE" and c == 0:
            # Время: первая строка — 0, дальше строго возрастает (раздел 2.6)
            ws.data_validation(1, 0, 1, 0, {
                "validate": "custom", "value": "=AND(ISNUMBER(A2),A2=0)",
                "ignore_blank": False, "error_title": "Invalid value",
                "error_message": "The first row is t = 0."})
            ws.data_validation(2, 0, EXCEL_ROWS - 1, 0, {
                "validate": "custom", "value": "=AND(ISNUMBER(A3),A3>A2)",
                "error_title": "Invalid value",
                "error_message": "Enter a time greater than the row above."})
            continue
        if col.choices:
            opts = {"validate": "list", "source": list(col.choices),
                    "error_message": "Choose " + " or ".join(col.choices) + "."}
        else:
            opts = {"validate": "custom",
                    "value": excel_rule(col.limit, xl_rowcol_to_cell(1, c)),
                    "error_message": limit_text(col.limit)}
        opts["error_title"] = "Invalid value"
        ws.data_validation(1, c, EXCEL_ROWS - 1, c, opts)
    ws.set_column(0, len(columns) - 1, 24)
    ws.freeze_panes(1, 0)
    if relperm:
        # Без пароля (решение 53); вставка и удаление строк разрешены — так
        # инженер меняет промежуточные точки. Первая и последняя строки с
        # заблокированными ячейками не удаляются
        ws.protect("", {"insert_rows": True, "delete_rows": True,
                        "format_columns": True, "format_rows": True})


def _comments_sheet(book, fmt: dict) -> None:
    """Лист COMMENTS: как получить шаблон и заполнить его, по-английски и по-русски (решение 67)."""
    ws = book.add_worksheet("COMMENTS")
    ws.write_string(0, 0, f"gpn-solver input workbook, format version {wf.FORMAT_VERSION}",
                    fmt["title"])
    ws.write_string(0, 2, f"Книга исходных данных gpn-solver, версия формата "
                          f"{wf.FORMAT_VERSION}", fmt["title"])
    for r, (topic, text, text_ru) in enumerate(COMMENTS, start=2):
        ws.write_string(r, 0, topic, fmt["topic"])
        ws.write_string(r, 1, text, fmt["wrap"])
        ws.write_string(r, 2, text_ru, fmt["wrap"])
    ws.set_column(0, 0, 22)
    ws.set_column(1, 2, 80)
