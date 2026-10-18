"""Каталог вывода: проверка и очистка переименованием (DEBT-082).

Windows не переименовывает каталог, в котором открыт файл без права удаления
(CSV в Excel) или который служит текущим каталогом консоли, — и ничего не
трогает; прямой rmtree успевал удалить часть файлов, а при консоли в каталоге
— все (пробы vault/issues/debt-082/probes/). Проверяется:
  - функции _check_output_free, _clear_output, _sibling: свободный и
    отсутствующий каталог, занятый (подмена os.rename — тест не зависит от
    ОС), неудача обратного переименования, корень диска, занятое соседнее
    имя, неудача удаления переименованного каталога;
  - настоящая блокировка на Windows: открытый файл и консоль в каталоге;
  - run_case по конфигу: занятый каталог — отказ до расчёта; заняли во время
    расчёта — результаты в соседнем каталоге с датой и временем, прежний цел
    (решение пользователя 2026-10-18); свободный — очищен, временных
    каталогов не осталось.
Отказ команды (код 2) — tests/test_cli.py, очистка у книги —
tests/test_workbook_run.py.
"""

import contextlib
import io
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

import gpn_multiphase_solver.report.pipeline as pipeline
from gpn_multiphase_solver.report.pipeline import CaseConfigError, run_case
from gpn_multiphase_solver.simulator import Simulator

SOLVER = Path(__file__).resolve().parents[1]                 # numerical_solver/
EXAMPLES_DIR = SOLVER / "examples"
OLD_FILES = ["a.png", "well_history.csv", "z.csv"]
windows_only = pytest.mark.skipif(sys.platform != "win32",
                                  reason="блокировка открытого файла — только Windows")


def _old_output(folder: Path) -> Path:
    """Каталог вывода прошлого расчёта folder/out с тремя файлами."""
    out = folder / "out"
    out.mkdir()
    for name in OLD_FILES:
        (out / name).write_text("1", encoding="utf-8")
    return out


def _names(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir())


def _lock_rename(monkeypatch, out: Path) -> None:
    """os.rename каталога out отказывает, как Windows при открытом в нём файле (WinError 5); остальные — настоящие."""
    real = os.rename
    target = out.resolve()

    def fake(src, dst):
        if Path(src).resolve() == target:
            raise PermissionError(13, "Access is denied", str(src))
        return real(src, dst)
    monkeypatch.setattr(pipeline.os, "rename", fake)


def _must_not_run(self, *args, **kwargs):
    raise AssertionError("расчёт начат при занятом каталоге вывода")


# ── Функции проверки и очистки ───────────────────────────────

def test_free_dir_passes_and_stays(tmp_path):
    """Свободный каталог: проверка проходит, файлы на месте, временных каталогов рядом не осталось."""
    out = _old_output(tmp_path)
    pipeline._check_output_free(out)
    assert _names(out) == OLD_FILES
    assert _names(tmp_path) == ["out"]


def test_missing_dir_noop(tmp_path):
    """Нет каталога: проверка и очистка ничего не делают и ничего не создают."""
    out = tmp_path / "out"
    pipeline._check_output_free(out)
    pipeline._clear_output(out)
    assert _names(tmp_path) == []


def test_busy_dir_refused(tmp_path, monkeypatch):
    """Занятый каталог: CaseConfigError с путём и подсказкой, файлы целы (подмена os.rename)."""
    out = _old_output(tmp_path)
    _lock_rename(monkeypatch, out)
    with pytest.raises(CaseConfigError, match="открыт в другой программе") as e:
        pipeline._check_output_free(out)
    assert str(out) in str(e.value) and "Расчёт не начат" in str(e.value)
    assert _names(out) == OLD_FILES


def test_rename_back_failure_names_probe(tmp_path, monkeypatch):
    """Обратное переименование не прошло: CaseConfigError называет временное имя, каталог под ним цел."""
    out = _old_output(tmp_path)
    real = os.rename

    def back_fails(src, dst):
        if Path(dst) == out:                 # второе переименование — обратно в out
            raise PermissionError(13, "Access is denied", str(src))
        return real(src, dst)
    monkeypatch.setattr(pipeline.os, "rename", back_fails)
    with pytest.raises(CaseConfigError, match="не возвращён") as e:
        pipeline._check_output_free(out)
    probe = out.with_name(f"out.check-{os.getpid()}")
    assert str(probe) in str(e.value)
    assert _names(probe) == OLD_FILES


def test_drive_root_refused():
    """Корень диска: CaseConfigError «корень диска» до любого переименования — и у проверки, и у очистки."""
    root = Path(Path.cwd().anchor)
    for fn in (pipeline._check_output_free, pipeline._clear_output):
        with pytest.raises(CaseConfigError, match="корень диска"):
            fn(root)


def test_sibling_skips_taken_name(tmp_path):
    """Занятое соседнее имя: берётся следующее с суффиксом -1."""
    out = _old_output(tmp_path)
    (tmp_path / f"out.check-{os.getpid()}").mkdir()
    assert pipeline._sibling(out, f".check-{os.getpid()}").name == f"out.check-{os.getpid()}-1"


def test_clear_removes_whole_dir(tmp_path):
    """Очистка свободного каталога: каталога нет, временного рядом тоже."""
    out = _old_output(tmp_path)
    pipeline._clear_output(out)
    assert _names(tmp_path) == []


def test_clear_busy_keeps_files(tmp_path, monkeypatch):
    """Очистка занятого каталога: OSError вызывающему, rmtree не вызван, файлы целы."""
    out = _old_output(tmp_path)
    _lock_rename(monkeypatch, out)
    called = []
    monkeypatch.setattr(pipeline.shutil, "rmtree", lambda p, *a, **k: called.append(p))
    with pytest.raises(PermissionError):
        pipeline._clear_output(out)
    assert called == [] and _names(out) == OLD_FILES


def test_clear_trash_left_warns(tmp_path, monkeypatch, caplog):
    """Переименованный каталог не удалился: предупреждение с его путём, каталог под временным именем цел."""
    out = _old_output(tmp_path)

    def rmtree_fails(path, *args, **kwargs):
        raise PermissionError(13, "Access is denied", str(path))
    monkeypatch.setattr(pipeline.shutil, "rmtree", rmtree_fails)
    with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
        pipeline._clear_output(out)
    trash = out.with_name(f"out.old-{os.getpid()}")
    assert _names(trash) == OLD_FILES
    assert str(trash) in caplog.text and "удалите этот каталог вручную" in caplog.text


@contextlib.contextmanager
def _hold_open_file(out: Path):
    """Файл каталога открыт на запись — как CSV в Excel (без права удаления)."""
    f = open(out / "well_history.csv", "a", encoding="utf-8")
    try:
        yield
    finally:
        f.close()


@contextlib.contextmanager
def _hold_cwd(out: Path):
    """Каталог — текущий у другого процесса, как у консоли после cd."""
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=out)
    time.sleep(0.5)                          # как в пробе edge_cases.py
    try:
        yield
    finally:
        p.kill()
        p.wait()


@windows_only
@pytest.mark.parametrize("hold", [_hold_open_file, _hold_cwd], ids=["open_file", "cwd"])
def test_real_lock_keeps_files(tmp_path, hold):
    """Windows, настоящая блокировка: проверка — CaseConfigError, очистка — OSError; ни один файл не удалён.

    Прямой rmtree при открытом файле удалял часть файлов, при консоли в
    каталоге — все (проба edge_cases.py, случаи 1 и 4; настоящий Excel —
    excel_lock.ps1).
    """
    out = _old_output(tmp_path)
    with hold(out):
        with pytest.raises(CaseConfigError, match="не удаётся очистить"):
            pipeline._check_output_free(out)
        with pytest.raises(OSError):
            pipeline._clear_output(out)
        assert _names(out) == OLD_FILES
    assert _names(tmp_path) == ["out"]
