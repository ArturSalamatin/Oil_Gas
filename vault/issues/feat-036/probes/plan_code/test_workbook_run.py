"""Расчёт по книге ввода Excel: run_case(книга.xlsx) и gpn-solver run книга.xlsx (FEAT-036).

Проверяется:
  - книга → output/input/ (config.json и CSV таблиц) → расчёт → штатный набор;
    заголовок — имя книги без расширения; печать «Книга: …»;
  - расчёт по output/input/config.json повторяет расчёт по книге побитово
    (решение 3 плана: вход сохраняется, расчёт воспроизводится без книги);
  - каталог вывода очищается до перевода (решение пользователя 2026-10-18):
    прежние файлы удалены; книга с ошибкой каталог не трогает; при ошибке
    конфига или отказе решателя в каталоге остаётся только input/;
  - книга внутри каталога вывода — отказ до чтения, книга цела (решение 4);
  - файл каталога вывода открыт в другой программе — отказ с подсказкой (аудит 1);
  - расчёт по JSON-конфигу прежний: очистка после расчёта (FEAT-030);
  - расширения Excel в любом регистре — путь книги, а не загрузчика JSON;
  - команда в отдельном процессе из постороннего каталога.
Книги — малые (N = 20, сутки при p_wf = 150 бар): XlsxWriter по таблице полей
и демо-значениям шаблона, как _write_book в test_workbook_convert.py.
"""

import contextlib
import io
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import xlsxwriter

import gpn_multiphase_solver.report.pipeline as pipeline
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io import workbook_format as wf
from gpn_multiphase_solver.io import workbook_template as wt
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.io.workbook_convert import convert_workbook
from gpn_multiphase_solver.report.pipeline import (
    EXCEL_SUFFIXES, INPUT_DIR, CaseConfigError, CaseRunError, run_case)
from gpn_multiphase_solver.simulator import Simulator

SOLVER = Path(__file__).resolve().parents[1]                 # numerical_solver/
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"  # дистрибутив radial-blackoil
INPUT_FILES = ["config.json", "gas_pvt.csv", "oil_pvt.csv", "relperm.csv"]
# Сутки при p_wf = 150 бар — ниже p_b = 180 бар ветви R_s0 = 50 демо-таблицы:
# газ выделяется, расчёт двухфазный. Запись — в конце суток. С N = 20 расчёт
# около 1 с, с рисунками — около 4 с
SMALL_SCHEDULE = ((0.0, "BHP", 150.0, None, None), (1.0, None, None, None, None))


def _small_book(path: Path, **values) -> Path:
    """Книга версии 1 XlsxWriter: демо-значения шаблона, N = 20, SCHEDULE — сутки; values — {ключ строки: значение}."""
    values = {"grid.N": 20, **values}
    tables = {**wt.DEMO_TABLES, "SCHEDULE": SMALL_SCHEDULE}
    wb = xlsxwriter.Workbook(path)
    for name, params in wf.PARAM_SHEETS.items():
        ws = wb.add_worksheet(name)
        ws.write_row(0, 0, wf.PARAM_HEADER)
        for r, p in enumerate(params, start=1):
            ws.write_row(r, 0, (p.key, p.label, values.get(p.key, p.demo), p.unit))
    for name, columns in wf.TABLE_SHEETS.items():
        ws = wb.add_worksheet(name)
        ws.write_row(0, 0, [c.header for c in columns])
        for r, row in enumerate(tables[name], start=1):
            for c, v in enumerate(row):
                if v is not None:
                    ws.write(r, c, v)
    wb.add_worksheet("COMMENTS")
    wb.close()
    return path


def _old_output(folder: Path) -> Path:
    """Каталог вывода прошлого расчёта: один файл прошлый.csv."""
    out = folder / "output"
    out.mkdir()
    (out / "прошлый.csv").write_text("1", encoding="utf-8")
    return out


def _must_not_run(self, *args, **kwargs):
    raise AssertionError("расчёт начат, хотя вход отвергнут")


# ── Расчёт по книге ──────────────────────────────────────────

@pytest.fixture(scope="module")
def case(tmp_path_factory):
    """run_case по малой книге с кириллицей и пробелом в имени; рядом — вывод прошлого расчёта: (книга, результат, печать)."""
    folder = tmp_path_factory.mktemp("book")
    book = _small_book(folder / "малая книга.xlsx")
    _old_output(folder)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = run_case(book)
    return book, r, buf.getvalue()


def test_input_saved_and_output_cleared(case):
    """Вывод — output рядом с книгой: input/ с четырьмя файлами перевода, штатный набор, файла прошлого расчёта нет."""
    book, r, _ = case
    out = book.parent / "output"
    assert r.output_dir == out
    # Имя подкаталога — в README, на листе COMMENTS книги и в справке команды
    assert INPUT_DIR == "input"
    assert sorted(p.name for p in (out / INPUT_DIR).iterdir()) == INPUT_FILES
    assert not (out / "прошлый.csv").exists()
    for name in ("well_history.csv", "profiles.csv", "pvt.png", "mass_balance.png"):
        assert (out / name).is_file(), name


def test_title_and_print(case):
    """Заголовок — имя книги без расширения (перевод пишет output.title, FEAT-035); вторая строка печати — «Книга: путь»."""
    book, r, text = case
    assert r.title == "малая книга"
    lines = text.splitlines()
    assert lines[0] == "=== малая книга ==="
    assert lines[1] == f"Книга: {book}"


def test_saved_input_reproduces_run(case):
    """Расчёт по output/input/config.json повторяет расчёт по книге побитово: p, T, S_g, R_s, дебиты всех записей.

    Ловит: перевод в output/input/ отличается от того, по которому шёл
    расчёт (запись другого словаря, округление чисел при записи).
    """
    book, r, _ = case
    cfg = load_config(book.parent / "output" / INPUT_DIR / "config.json")
    simulator, initial = SimulatorFactory.from_config(cfg)
    history = simulator.run(initial)
    assert np.array_equal(history.times, r.history.times)
    for a, b in zip(history.states, r.history.states, strict=True):
        for field in ("p", "T", "Sg", "Rs"):
            assert np.array_equal(getattr(a, field), getattr(b, field)), field
    assert [w.q_o_std for w in history.well_data] == [w.q_o_std for w in r.history.well_data]
    assert [w.T_wf for w in history.well_data] == [w.T_wf for w in r.history.well_data]


# ── Каталог вывода: очистка до перевода (решение 2026-10-18) ──

def test_book_inside_output_refused(tmp_path, monkeypatch):
    """Каталог вывода — папка книги или её предок: отказ до чтения книги, книга цела (решение 4 черновика)."""
    monkeypatch.setattr(Simulator, "run", _must_not_run)
    (tmp_path / "a").mkdir()
    book = _small_book(tmp_path / "a" / "b.xlsx")
    # Предок — tmp_path, а не общий каталог pytest: если проверка пропадёт,
    # очистка удалит только каталог этого теста
    for out in (book.parent, tmp_path):
        with pytest.raises(CaseConfigError, match="содержит книгу"):
            run_case(book, out)
    assert book.is_file()


def test_book_error_leaves_output(tmp_path, monkeypatch):
    """Ошибка ячейки (N = 20.5) — отказ перевода с адресом; каталог вывода прошлого расчёта не тронут."""
    monkeypatch.setattr(Simulator, "run", _must_not_run)
    book = _small_book(tmp_path / "b.xlsx", **{"grid.N": 20.5})
    out = _old_output(tmp_path)
    with pytest.raises(CaseConfigError, match="книга не переведена") as e:
        run_case(book)
    assert "NUMERICS!C2" in str(e.value)
    assert [p.name for p in out.iterdir()] == ["прошлый.csv"]


def test_not_workbook_and_missing(tmp_path):
    """Не книга .xlsx — отказ разбора с подсказкой; нет файла — «книга не найдена»; каталог вывода не создан."""
    fake = tmp_path / "fake.xlsx"
    fake.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(CaseConfigError, match="не zip"):
        run_case(fake)
    with pytest.raises(CaseConfigError, match="книга не найдена"):
        run_case(tmp_path / "нет.xlsx")
    assert not (tmp_path / "output").exists()


def test_config_error_after_cleanup_keeps_input(tmp_path):
    """R_s0 = 70 вне ветвей таблицы (5…60): отказ фабрики с путём книги; в каталоге вывода только input/.

    Перевод R_s0 не сверяет с таблицей — это делает фабрика (BUG-017),
    уже после очистки каталога: прежних результатов нет, перевод — для разбора.
    """
    book = _small_book(tmp_path / "b.xlsx", **{"initial_conditions.Rs0": 70.0})
    out = _old_output(tmp_path)
    with pytest.raises(CaseConfigError, match="Rs0 = 70") as e:
        run_case(book)
    assert str(e.value).startswith(f"{book}: ")
    assert [p.name for p in out.iterdir()] == [INPUT_DIR]
    assert sorted(p.name for p in (out / INPUT_DIR).iterdir()) == INPUT_FILES


def test_run_failure_keeps_input(tmp_path, monkeypatch):
    """Отказ решателя — CaseRunError; в каталоге вывода только input/ (у конфига прежний вывод цел — test_run_case_run_failure)."""
    def fail(self, *args, **kwargs):
        raise RuntimeError("шаг не сошёлся")
    monkeypatch.setattr(Simulator, "run", fail)
    book = _small_book(tmp_path / "b.xlsx")
    out = _old_output(tmp_path)
    with pytest.raises(CaseRunError, match="шаг не сошёлся"):
        run_case(book)
    assert [p.name for p in out.iterdir()] == [INPUT_DIR]


def test_locked_output_file_refused(tmp_path, monkeypatch):
    """Файл каталога вывода открыт в другой программе: отказ с путём и подсказкой, а не трассировка.

    На Windows rmtree падает PermissionError (WinError 32) на открытом файле,
    успев удалить часть файлов (проба аудита 1, audit_locked_output.py). Здесь
    rmtree подменён: тест не зависит от ОС. Расчёт не начат.
    """
    monkeypatch.setattr(Simulator, "run", _must_not_run)
    book = _small_book(tmp_path / "b.xlsx")
    out = _old_output(tmp_path)

    def locked(path, *args, **kwargs):
        raise PermissionError(13, "файл занят", str(Path(path) / "well_history.csv"))
    monkeypatch.setattr(pipeline.shutil, "rmtree", locked)
    with pytest.raises(CaseConfigError, match="открыт в другой программе") as e:
        run_case(book)
    assert str(out) in str(e.value) and "well_history.csv" in str(e.value)


def test_config_run_clears_output_after_run(tmp_path):
    """Расчёт по JSON-конфигу прежний: каталог вывода очищается после расчёта, input/ не появляется (FEAT-030).

    Ловит: правка ветки очистки ради книги (workbook is None and …) отключила
    очистку у конфига — файлы прошлого расчёта остались бы рядом с новыми.
    Конфиг — перевод малой книги (convert_workbook), заголовок — имя книги.
    """
    config = convert_workbook(_small_book(tmp_path / "b.xlsx"), tmp_path / "case")
    out = _old_output(tmp_path)
    with contextlib.redirect_stdout(io.StringIO()):
        r = run_case(config, out)
    names = {p.name for p in out.iterdir()}
    assert "прошлый.csv" not in names and INPUT_DIR not in names
    assert "well_history.csv" in names
    assert r.title == "b"


def test_invalid_profiles_argument_leaves_output(tmp_path, monkeypatch):
    """Явный n_profiles = 1 — ValueError до перевода: каталог вывода не тронут."""
    monkeypatch.setattr(Simulator, "run", _must_not_run)
    book = _small_book(tmp_path / "b.xlsx")
    out = _old_output(tmp_path)
    with pytest.raises(ValueError, match="n_profiles"):
        run_case(book, n_profiles=1)
    assert [p.name for p in out.iterdir()] == ["прошлый.csv"]


@pytest.mark.parametrize("name", ["B.XLSX", "b.xlsm", "b.xls", "b.xlsb"])
def test_excel_suffixes_take_workbook_path(tmp_path, name):
    """Расширение Excel в любом регистре — путь книги: отказ разбора «не zip», а не загрузчика JSON."""
    path = tmp_path / name
    path.write_text("{}", encoding="utf-8")            # JSON под именем книги
    with pytest.raises(CaseConfigError, match="не zip"):
        run_case(path)


def test_excel_suffixes():
    assert EXCEL_SUFFIXES == (".xlsx", ".xlsm", ".xls", ".xlsb")


# ── Команда в отдельном процессе ─────────────────────────────

def test_command_runs_workbook(tmp_path):
    """python -m gpn_multiphase_solver run книга.xlsx из постороннего каталога: код 0, input/ и штатный набор, «Книга: …».

    Подпроцесс получает PYTHONPATH на пакет и прототип этого дерева (как
    test_cli.py): в worktree иначе взялся бы пакет основного каталога.
    """
    (tmp_path / "case").mkdir()
    book = _small_book(tmp_path / "case" / "скважина 1.xlsx")
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               PYTHONPATH=os.pathsep.join([str(SOLVER), str(PROTO)]))
    r = subprocess.run([sys.executable, "-m", "gpn_multiphase_solver", "run",
                        "case/скважина 1.xlsx"], cwd=tmp_path, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-2000:]
    out = book.parent / "output"
    assert sorted(p.name for p in (out / INPUT_DIR).iterdir()) == INPUT_FILES
    assert (out / "well_history.csv").is_file()
    lines = r.stdout.splitlines()
    assert lines[0] == "=== скважина 1 ==="
    assert lines[1] == f"Книга: {book.resolve()}"
