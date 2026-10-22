"""Перевод книги ввода Excel версии 1 в JSON-конфиг и CSV таблиц в СИ (FEAT-035).

Книга → config.json, oil_pvt.csv, gas_pvt.csv, relperm.csv в новом или пустом
каталоге; дальше — обычный load_config. Перевод проверяет только то, что есть
лишь в книге: листы, заголовки, ключи, единицы, типы и пределы ячеек, постоянные
строки, крайние строки RELPERM, моменты SCHEDULE. Конфиг (_validate) и таблицы
целиком (фабрика) проверяются при расчёте — перевод их не повторяет (решение 21
плана). Все ошибки ячеек — одним сообщением, с листом и адресом (решение 22).
Формат книги — таблица полей io/workbook_format.py.
"""

from __future__ import annotations

import csv
import json
from dataclasses import fields, replace
from pathlib import Path

import numpy as np

from . import workbook_format as wf
from .config import (GeometryConfig, GridConfig, InitialConfig, NumericsConfig,
                     OutputConfig, PVTConfig, RelPermConfig, RockConfig, ThermalConfig,
                     TimeConfig)
from .xlsx_reader import (BOOL, EMPTY, NUMBER, STRING, Cell, Sheet, Workbook, WorkbookError,
                          read_workbook)

CONFIG_NAME = "config.json"
# Лист таблицы → имя CSV рядом с config.json (pvt.oil_pvt_file, pvt.gas_pvt_file, relperm.file)
CSV_NAMES = {"OIL_PVT": "oil_pvt.csv", "GAS_PVT": "gas_pvt.csv", "RELPERM": "relperm.csv"}
# Сколько ошибок книги печатается; остальные — числом (решение 22)
MAX_ERRORS = 30
# Моменты SCHEDULE переводятся в целые миллисекунды (решение 19): интервал —
# разность целых, сумма интервалов равна последнему моменту без накопления ошибки
MS_PER_DAY = 86_400_000

# Секции конфига: ключ строки книги — поле конфига, если оно есть в секции;
# остальные ключи (format_version, пары для составных полей) — только книги
_SECTIONS = {"geometry": GeometryConfig, "grid": GridConfig, "rock": RockConfig,
             "pvt": PVTConfig, "relperm": RelPermConfig, "thermal": ThermalConfig,
             "initial_conditions": InitialConfig, "time": TimeConfig,
             "numerics": NumericsConfig, "output": OutputConfig}
CONFIG_FIELDS = frozenset(f"{s}.{f.name}" for s, cls in _SECTIONS.items() for f in fields(cls))

# Листы, которые перевод читает; COMMENTS не читается, лишние листы пропускаются (решение 10)
_SHEETS = (*wf.PARAM_SHEETS, *wf.TABLE_SHEETS)
_TEMPLATE_HINT = (f"книга версии {wf.FORMAT_VERSION} состоит из листов "
                  f"{', '.join(wf.SHEET_ORDER)}; шаблон пишет команда gpn-solver template")


class WorkbookContentError(WorkbookError):
    """Значения книги не годятся для перевода; errors — по строке на ошибку (FEAT-035)."""

    def __init__(self, path, errors: list[str]):
        self.errors = list(errors)
        shown = "\n".join(f"  {e}" for e in self.errors[:MAX_ERRORS])
        more = len(self.errors) - MAX_ERRORS
        tail = f"\n  … и ещё {more}" if more > 0 else ""
        super().__init__(f"{path}: книга не переведена, ошибок — {len(self.errors)}:\n"
                         f"{shown}{tail}")


# FEAT-035
def convert_workbook(workbook, out_dir) -> Path:
    """Перевести книгу ввода Excel в файл конфигурации и таблицы CSV в единицах СИ без расчёта.

    То же, что команда ``gpn-solver convert``. Проверяется только книга;
    файл конфигурации и таблицы целиком проверяются при расчёте
    (:func:`load_config`, :meth:`SimulatorFactory.from_config`). Книга с
    ошибкой файлов не оставляет.

    Параметры
    ---------
    workbook : str or pathlib.Path
        Книга ввода ``.xlsx``.
    out_dir : str or pathlib.Path
        Новый или пустой каталог для ``config.json`` и таблиц CSV.

    Возвращает
    ----------
    pathlib.Path
        Путь записанного ``config.json``.

    Исключения
    ----------
    FileExistsError
        ``out_dir`` существует и это не пустой каталог; файлы в нём не
        изменены.
    FileNotFoundError
        Книги нет.
    WorkbookError
        Файл не читается как книга ``.xlsx`` или значения книги не годятся
        для перевода (все ошибки ячеек сразу, с листом и ячейкой);
        наследник ``ValueError``.
    """
    workbook, out_dir = Path(workbook), Path(out_dir)
    # Непустой каталог — отказ (решение 10): файлы прежнего перевода или расчёта
    # не перемешиваются с новыми, чужие файлы не затираются
    if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())):
        raise FileExistsError(f"{out_dir} существует и это не пустой каталог: перевод книги "
                              f"пишется в новый или пустой каталог, файлы в нём не изменены")
    config, tables = workbook_to_config(read_workbook(workbook))
    # Запись — после всех проверок: книга с ошибкой файлов не оставляет
    return write_files(out_dir, config, tables)


def write_files(out_dir: Path, config: dict, tables: dict) -> Path:
    """config.json и CSV таблиц в каталог out_dir (создаётся); путь config.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (header, rows) in tables.items():
        _write_csv(out_dir / name, header, rows)
    path = out_dir / CONFIG_NAME
    # json пишет float через repr — обратное чтение точное; newline="\n": без него
    # write_text на Windows пишет «\r\n» (проба плана), а CSV рядом — «\n»
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")
    return path


def workbook_to_config(book: Workbook) -> tuple[dict, dict]:
    """Книга → (конфиг в СИ, {имя CSV: (заголовок, строки в СИ)}); ошибки — WorkbookContentError (FEAT-035)."""
    missing = [s for s in _SHEETS if s not in book.sheets]
    if missing:
        raise WorkbookContentError(book.path,
                                   [f"нет листа {s} — {_TEMPLATE_HINT}" for s in missing])
    _check_version(book)
    recalc = book.recalc_on_open
    errors: list[str] = []
    # Порядок проверки — порядок листов книги: ошибки в сообщении идут так же
    values: dict = {}
    refs: dict = {}                        # ключ → «MODEL!C7 (подпись)» для сообщений
    for name, params in wf.PARAM_SHEETS.items():
        values.update(_param_sheet(book.sheets[name], params, recalc, errors, refs))
        if name == "MODEL":
            _check_porosity(values, refs, errors)     # источники φ0 — все на MODEL
    history = _schedule(book.sheets["SCHEDULE"], recalc, errors)
    tables = {}
    for name in ("OIL_PVT", "GAS_PVT", "RELPERM"):
        columns = wf.TABLE_SHEETS[name]
        n_before = len(errors)
        rows = _table(book.sheets[name], columns, recalc, errors)
        if name == "RELPERM" and len(errors) == n_before:
            # Крайние строки — только у листа без ошибок: строка с ошибкой в rows
            # не попадает, и «первой» оказалась бы следующая
            _relperm_ends(book.sheets[name], rows, errors)
        si = [tuple(wf.UNIT_TO_SI[c.unit](v) for v, c in zip(vals, columns)) for _, vals in rows]
        tables[CSV_NAMES[name]] = ([c.target for c in columns], si)
    if errors:
        raise WorkbookContentError(book.path, errors)
    return _config(values, history, book.path.stem), tables


# ── Версия формата ──

def _check_version(book: Workbook) -> None:
    """format_version = 1 — до остальных проверок: книга другой версии получает одну ошибку (решение 15)."""
    sheet = book.sheets["MODEL"]
    p = next(p for p in wf.MODEL if p.key == "format_version")
    row = next((r for r in range(2, sheet.max_row + 1)
                if _text(sheet.cell(r, 1)) == p.key), None)
    if row is None:
        raise WorkbookContentError(book.path, [
            f"MODEL: нет строки {p.key} — это не книга ввода версии {wf.FORMAT_VERSION}; "
            f"{_TEMPLATE_HINT}"])
    cell = sheet.cell(row, 3)
    if not (cell.kind == NUMBER and cell.value == wf.FORMAT_VERSION):
        raise WorkbookContentError(book.path, [
            f"{cell.ref} ({p.label}): версия формата {_show(cell)}, программа читает версию "
            f"{wf.FORMAT_VERSION} — {_TEMPLATE_HINT}"])


# ── Листы «параметр–значение» ──

def _param_sheet(sheet: Sheet, params, recalc: bool, errors: list, refs: dict) -> dict:
    """Лист MODEL, THERMAL или NUMERICS → {ключ: значение в СИ}; ошибки — в errors, адреса — в refs (решения 15, 17, 20)."""
    # Читаются столбцы Key (A), Value (C), Unit (D); заголовок сверяется по D
    # включительно — вставленный левее столбец сдвинул бы чтение
    if not _header_ok(sheet, wf.PARAM_HEADER[:4], errors):
        return {}
    by_key = {p.key: p for p in params}
    rows: dict = {}                        # ключ → строка листа
    for r in range(2, sheet.max_row + 1):
        key_cell = sheet.cell(r, 1)
        if not _filled(key_cell):
            # Строка без ключа: пустая пропускается, с данными — ошибка (решение 25)
            if any(_filled(sheet.cell(r, c)) for c in (2, 3, 4)):
                errors.append(f"{key_cell.ref}: строка без ключа (Key) — значение не к чему "
                              f"отнести")
            continue
        key = _text(key_cell)
        if key not in by_key:
            home = next((n for n, ps in wf.PARAM_SHEETS.items()
                         if any(p.key == key for p in ps)), None)
            where = f" — эта строка листа {home}" if home else ""
            errors.append(f"{key_cell.ref}: неизвестный ключ {_show(key_cell)}{where}")
        elif key in rows:
            errors.append(f"{key_cell.ref}: ключ {key} повторяется — он уже в строке {rows[key]}")
        else:
            rows[key] = r

    # Значения в единицах книги: сначала тип и единица каждой строки, потом пределы —
    # предел r_e > r_w ссылается на значение другой строки
    raw: dict = {}
    for p in params:
        r = rows.get(p.key)
        if r is None:
            errors.append(f"{sheet.name}: нет строки {p.key} ({p.label}) — все строки "
                          f"листа обязательны")
            continue
        unit, cell = sheet.cell(r, 4), sheet.cell(r, 3)
        refs[p.key] = f"{cell.ref} ({p.label})"
        if _text(unit) != p.unit:
            errors.append(f"{unit.ref} ({p.label}): единица {_show(unit)}, нужна {p.unit!r} — "
                          f"единицы книги фиксированы")
            continue
        if isinstance(p.demo, str):
            # Постоянная строка-слово (jacobian_mode, linear_solver): только своё значение
            if _text(cell) != p.demo:
                errors.append(f"{refs[p.key]}: значение постоянное — {p.demo!r}, в книге "
                              f"{_show(cell)}")
            else:
                raw[p.key] = p.demo
            continue
        v, why = _number(cell, recalc)
        if why:
            errors.append(f"{refs[p.key]}: {why}")
        else:
            raw[p.key] = v

    out: dict = {}
    for p in params:
        if p.key not in raw:
            continue                       # ошибка строки уже записана
        v = raw[p.key]
        if p.fixed:
            if v != p.demo:
                errors.append(f"{refs[p.key]}: значение постоянное — {p.demo!r}, в книге {v!r}")
            else:
                out[p.key] = p.demo
            continue
        limit, above, above_label = p.limit, None, None
        if limit.above_key is not None:
            above = raw.get(limit.above_key)
            above_label = by_key[limit.above_key].label
            if above is None:
                # Опорная строка с ошибкой (она уже в списке) — сравнения нет
                limit = replace(limit, above_key=None)
        if not limit.accepts(v, above):
            errors.append(f"{refs[p.key]}: {v!r} — нужно {_limit_text(limit, above_label)}")
            continue
        # Целое поле — int: Excel хранит 100 как 100.0, а load_config ждёт целое
        # (max_retries, newton_max_iter, max_active_set_iter, grid.N)
        out[p.key] = int(v) if limit.integer else wf.UNIT_TO_SI[p.unit](v)
    return out


def _porosity(values: dict) -> float | None:
    """φ0 = φ_ref·exp(c_r·(p0 − p_ref)) в СИ; None — у источника ошибка."""
    keys = wf.DERIVED["rock.porosity"]     # φ_ref, p_ref, c_r, p0
    if any(k not in values for k in keys):
        return None
    phi_ref, p_ref, c_r, p0 = (values[k] for k in keys)
    # Порода решателя — φ(p) = φ0·exp(c_r·(p − p0)) (CompressibleRock прототипа),
    # поэтому перенос опорной точки точный; c_r — 1/Па, давления — Па
    return float(phi_ref * np.exp(c_r * (p0 - p_ref)))


def _check_porosity(values: dict, refs: dict, errors: list) -> None:
    """φ0 ≤ 1 проверяет перевод: строки rock.porosity в книге нет (умолчание 35)."""
    # _validate отверг бы φ0 > 1 сообщением о rock.porosity — поле, которого
    # инженер в книге не найдёт; ошибка — у ячейки φ_ref, с источниками φ0
    phi0 = _porosity(values)
    if phi0 is not None and phi0 > 1.0:
        errors.append(f"{refs['rock.porosity_ref']}: пористость при начальном давлении "
                      f"φref·exp(cr·(pi - pref)) = {phi0!r} больше 1 — проверьте φref, cr, "
                      f"pref и pi на листе MODEL")


# ── Таблицы ──

def _table(sheet: Sheet, columns, recalc: bool, errors: list) -> list[tuple[int, tuple]]:
    """Табличный лист → [(строка листа, значения в единицах книги)]; пустые строки пропускаются (решение 23)."""
    if not _header_ok(sheet, [c.header for c in columns], errors):
        return []
    rows = []
    for r in _data_rows(sheet, len(columns)):
        values = tuple(_table_number(sheet.cell(r, c), col, recalc, errors)
                       for c, col in enumerate(columns, start=1))
        if None not in values:
            rows.append((r, values))
    return rows


def _relperm_ends(sheet: Sheet, rows: list, errors: list) -> None:
    """Первая строка RELPERM — S_g = 0, k_rg = 0; последняя — S_g = 1, k_ro = 0 (решение 17)."""
    # Защита листа снимается без пароля, поэтому крайние строки проверяет перевод;
    # k_rg = 0 при S_g = 0 и k_ro = 0 в последней строке требует и фабрика
    # (_check_relperm_table), а S_g = 0 и S_g = 1 по краям — только книга
    if not rows:
        errors.append(f"{sheet.name}: нет строк — нужны хотя бы строки Sg = 0 и Sg = 1")
        return
    for (r, values), pattern, which in ((rows[0], wf.RELPERM_FIRST_ROW, "первая"),
                                         (rows[-1], wf.RELPERM_LAST_ROW, "последняя")):
        for c, (v, need) in enumerate(zip(values, pattern), start=1):
            if need is not None and v != need:
                col = wf.RELPERM[c - 1]
                errors.append(f"{sheet.cell(r, c).ref} ({col.header}): {which} строка таблицы — "
                              f"{col.header} = {need:g}, в книге {v!r}")


def _schedule(sheet: Sheet, recalc: bool, errors: list) -> list[dict]:
    """SCHEDULE → time.history: интервал k — [t_k, t_{k+1}] с режимом строки k, моменты в целых мс (решения 8, 16, 19)."""
    cols = wf.SCHEDULE
    if not _header_ok(sheet, [c.header for c in cols], errors):
        return []
    rows = _data_rows(sheet, len(cols))
    if len(rows) < 2:
        errors.append(f"{sheet.name}: нужны хотя бы две строки — t = 0 и момент завершения "
                      f"расчёта")
        return []
    n_before = len(errors)
    col_of = {c.target: i for i, c in enumerate(cols, start=1)}
    ms: list = []                  # момент строки, целые мс; None — ячейка с ошибкой
    controls: list = []            # управление интервала без dt
    prev = None                    # (ячейка, сут, мс) последнего верного момента
    for k, r in enumerate(rows):
        t_cell = sheet.cell(r, 1)
        t = _table_number(t_cell, cols[0], recalc, errors)
        m = None
        if t is not None:
            m = round(t * MS_PER_DAY)          # round(float) — int
            # Первая строка — ровно 0, как проверка Excel A2 = 0 (раскладка FEAT-033)
            if k == 0 and t != 0.0:
                errors.append(f"{t_cell.ref} ({cols[0].header}): первая строка — t = 0, в книге "
                              f"{t!r}")
            elif prev is not None and m <= prev[2]:
                errors.append(f"{t_cell.ref} ({cols[0].header}): момент {t!r} сут не позже "
                              f"предыдущего ({prev[0].ref} = {prev[1]!r} сут) с точностью 1 мс — "
                              f"интервал нулевой или отрицательный")
            prev = (t_cell, t, m)
        ms.append(m)
        if k == len(rows) - 1:
            break                  # последняя строка — только момент завершения (решение 8)
        # Режим строки и только его ячейки (решение 16): ячейку чужого режима
        # _validate_interval отверг бы (control='pressure' без q_oil, min_bhp)
        mode_cell = sheet.cell(r, 2)
        mode = _text(mode_cell)
        if mode not in wf.CONTROL_MODES:
            errors.append(f"{mode_cell.ref} ({cols[1].header}): {_show(mode_cell)} — нужен "
                          f"{' или '.join(wf.CONTROL_MODES)}")
            controls.append(None)
            continue
        control, used = wf.CONTROL_MODES[mode]
        entry = {"control": control}
        for target in used:
            c = col_of[target]
            v = _table_number(sheet.cell(r, c), cols[c - 1], recalc, errors)
            if v is not None:
                entry[target] = wf.UNIT_TO_SI[cols[c - 1].unit](v)
        controls.append(entry)
    if len(errors) > n_before:
        return []
    # Деление целых мс на 1000 — ближайший к точному значению double
    return [{"dt": (ms[k + 1] - ms[k]) / 1000, **controls[k]} for k in range(len(controls))]


def _data_rows(sheet: Sheet, ncols: int) -> list[int]:
    """Строки данных таблицы: со второй, хотя бы одна непустая ячейка в столбцах 1…ncols."""
    # Разбор хранит только ячейки со значением или формулой (стилизованные
    # пустые — нет): полностью пустая строка в таблицу не попадает. Столбцы
    # правее таблицы не читаются (решение 24)
    return sorted({r for r, c in sheet.cells if r > 1 and c <= ncols})


# ── Ячейки ──

def _table_number(cell: Cell, col: wf.Column, recalc: bool, errors: list) -> float | None:
    """Число ячейки таблицы в пределах столбца; иначе ошибка в errors и None."""
    v, why = _number(cell, recalc)
    if why is None and not col.limit.accepts(v):
        why = f"{v!r} — нужно {_limit_text(col.limit)}"
    if why is not None:
        errors.append(f"{cell.ref} ({col.header}): {why}")
        return None
    return v


def _number(cell: Cell, recalc: bool) -> tuple[float | None, str | None]:
    """Число ячейки или текст ошибки: пусто, текст, дата, логическое, ошибка, формула без значения (решение 6)."""
    if cell.formula_without_value:
        if recalc:
            # Ячейка общей формулы хранит текст только у первой ячейки: formula = ""
            what = f"формула ={cell.formula}" if cell.formula else "общая формула"
            return None, (f"{what} без сохранённого значения: книга помечена "
                          f"«пересчитать при открытии» — так пишут её программы, а не Excel; "
                          f"откройте книгу в Excel и сохраните её или введите число вместо "
                          f"формулы")
        return None, (f"формула без сохранённого значения — откройте книгу в Excel и "
                      f"сохраните её или введите число вместо формулы")
    if cell.kind == EMPTY:
        return None, "пусто — нужно число: все значения книги обязательны"
    if cell.kind == NUMBER:
        if cell.is_date:
            # Excel с русскими настройками превращает «1.5» в 1 мая (число 46143)
            return None, (f"{cell.value!r} с форматом даты или времени — Excel мог принять "
                          f"ввод за дату; задайте ячейке формат «Общий» и введите число заново")
        return cell.value, None
    if cell.kind == STRING:
        return None, (f"текст {cell.value!r} — нужно число; десятичный разделитель — точка, "
                      f"число вводится без кавычек и апострофа")
    if cell.kind == BOOL:
        return None, f"логическое значение {_show(cell)} — нужно число"
    return None, f"ошибка Excel {cell.value} — нужно число"


def _header_ok(sheet: Sheet, headers, errors: list) -> bool:
    """Строка 1 листа — заголовки headers по порядку (пробелы по краям срезаются, решение 20)."""
    ok = True
    for c, h in enumerate(headers, start=1):
        cell = sheet.cell(1, c)
        if _text(cell) != h:
            errors.append(f"{cell.ref}: заголовок {_show(cell)}, нужен {h!r} — столбцы "
                          f"читаются по порядку")
            ok = False
    return ok


def _text(cell: Cell) -> str | None:
    """Строка ячейки без пробелов по краям (решение 20); не строка — None."""
    return cell.value.strip() if cell.kind == STRING else None


def _filled(cell: Cell) -> bool:
    """В ячейке есть значение или формула."""
    return cell.kind != EMPTY or cell.formula is not None


def _show(cell: Cell) -> str:
    """Содержимое ячейки для сообщения: строка — в кавычках, чтобы были видны пробелы."""
    if cell.kind == EMPTY:
        return "пусто"
    if cell.kind == BOOL:
        return "TRUE" if cell.value else "FALSE"
    return repr(cell.value) if cell.kind in (STRING, NUMBER) else str(cell.value)


def _limit_text(limit: wf.Limit, above_label: str | None = None) -> str:
    """Допустимые значения ячейки словами — для сообщения об ошибке."""
    what = "целое число" if limit.integer else "число"
    lo, hi = limit.lo, limit.hi
    if lo is not None and hi is not None:
        return (f"{what} в ({lo:g}, {hi:g}]" if limit.lo_strict
                else f"{what} от {lo:g} до {hi:g}")
    if lo is not None:
        return f"{what} {'>' if limit.lo_strict else '≥'} {lo:g}"
    if limit.above_key is not None:
        return f"{what} больше, чем {above_label}"
    return f"конечное {what}"


# ── Конфиг и файлы ──

def _config(values: dict, history: list, title: str) -> dict:
    """Конфиг: каждое поле книги явно, составные поля, таблицы, заголовок (решения 11, 15)."""
    cfg: dict = {s: {} for s in _SECTIONS}
    cfg["pvt"]["model"] = "table"          # книга только табличная (решение 28 FEAT-033)
    cfg["relperm"]["model"] = "table"
    for key, v in values.items():
        if key in CONFIG_FIELDS:
            section, name = key.split(".")
            cfg[section][name] = v
    # Составные поля — wf.DERIVED
    cfg["rock"]["porosity"] = _porosity(values)
    # (ρc_p)_s = ρ_ma·c_ma — определение под eq:main_rhocpeff
    cfg["rock"]["rho_cp_solid"] = values["rock.rho_solid"] * values["rock.c_solid"]
    cfg["pvt"]["oil_pvt_file"] = CSV_NAMES["OIL_PVT"]
    cfg["pvt"]["gas_pvt_file"] = CSV_NAMES["GAS_PVT"]
    cfg["relperm"]["file"] = CSV_NAMES["RELPERM"]
    cfg["time"]["history"] = history
    # Листа OUTPUT нет (решение 44 FEAT-033): параметры вывода — умолчания,
    # заголовок рисунков — имя книги без расширения (FEAT-036)
    cfg["output"]["title"] = title
    return cfg


def _write_csv(path: Path, header, rows) -> None:
    """CSV таблицы в СИ: числа через repr — обратное чтение точное; окончания строк «\\n»."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows([repr(float(x)) for x in row] for row in rows)
