"""DEBT-083, аудит 1: эмуляция плана без правки рабочего дерева и git.

Собирает _emulate/: pipeline_patched.py — pipeline.py базы с правками шагов 1–2 (текстовые
замены, каждый old — ровно одно вхождение); emu_plugin.py — подменяет модуль
gpn_multiphase_solver.report.pipeline пропатченным; tests/ — копии test_output_dir.py,
test_cli.py, test_workbook_run.py и conftest.py со вставками тестов плана (SOLVER — основной
каталог) и test_emu_docs.py — правило докстрингов D1–D7 (tests/test_docs.py) на объектах
pipeline из перечня api.rst.

Запуск из корня проекта:
  numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-083\\probes\\plan_emulate.py
  cd vault\\issues\\debt-083\\probes\\_emulate
  $env:PYTHONPATH = (Get-Location).Path
  ..\\..\\..\\..\\..\\numerical_solver\\.venv\\Scripts\\python -m pytest tests -q -m "not slow" -p emu_plugin
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOLVER = ROOT / "numerical_solver"
EMU = Path(__file__).resolve().parent / "_emulate"


def patch(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    assert n == 1, f"{what}: вхождений {n}"
    return text.replace(old, new)


# ── pipeline.py: шаги 1–2 ──
src = (SOLVER / "gpn_multiphase_solver" / "report" / "pipeline.py").read_text(encoding="utf-8")

src = patch(src, "каталоге с датой и временем в имени.\n\"\"\"\n",
            "каталоге с датой и временем в имени.\n\n"
            "Путь вывода — файл, путь через файл или несуществующий диск (DEBT-083) —\n"
            "отказ до расчёта, у книги — до её чтения.\n\"\"\"\n", "докстринг модуля")

src = patch(src,
            "# книга — FEAT-036\nclass CaseConfigError(ValueError):\n"
            "    \"\"\"Ошибка входа расчёта: конфигурация, таблицы или книга не читаются или не "
            "проходят проверку, каталог результатов занят; расчёт не начат.\"\"\"",
            "# книга — FEAT-036; путь вывода — файл или нет диска — DEBT-083\n"
            "class CaseConfigError(ValueError):\n"
            "    \"\"\"Ошибка входа расчёта: конфигурация, таблицы или книга не читаются или не "
            "проходят проверку, каталог результатов занят, на его пути файл или нет диска; "
            "расчёт не начат.\"\"\"", "CaseConfigError")

src = patch(src, "# расчёта по конфигу — соседний каталог и предупреждение в журнал.\n",
            "# расчёта по конфигу — соседний каталог и предупреждение в журнал. Путь\n"
            "# вывода — файл, путь через файл или нет диска (DEBT-083): отказ до расчёта,\n"
            "# у книги — до её чтения.\n", "комментарий над run_case")

src = patch(src,
            "        каталога результатов; каталог результатов занят другой программой.\n"
            "        Расчёт не начат.\n",
            "        каталога результатов; каталог результатов занят другой программой;\n"
            "        путь каталога результатов — файл, проходит через файл или ведёт на\n"
            "        несуществующий диск. Расчёт не начат.\n", "Исключения run_case")

src = patch(src,
            "        _check_inputs_outside(config_path, config, output_dir)\n"
            "        # Занятый каталог вывода",
            "        _check_inputs_outside(config_path, config, output_dir)\n"
            "        # Путь вывода — файл или проходит через файл (опечатка в --output),\n"
            "        # диска нет — отказ до расчёта, а не FileExistsError после него\n"
            "        # (DEBT-083). У книги проверено в _translate_workbook\n"
            "        _check_output_path(output_dir)\n"
            "        # Занятый каталог вывода", "вызов у конфига")

FUNC = '''def _check_output_path(output_dir: Path) -> None:
    """Путь вывода годится под каталог: первый существующий среди него и его предков — каталог, иначе CaseConfigError. DEBT-083."""
    # Опечатка в --output (имя CSV или книги вместо каталога) обнаруживалась
    # только после расчёта: mkdir на файле падает FileExistsError даже с
    # exist_ok, на пути через файл (well_history.csv\\sub) — тоже, на
    # несуществующем диске — FileNotFoundError (пробы DEBT-083,
    # vault/issues/debt-083/probes/). Проверка ничего не создаёт. abspath, а
    # не resolve, — как в _sibling: диск subst и сетевой остаются собой
    path = Path(os.path.abspath(output_dir))
    existing = next((p for p in (path, *path.parents) if p.exists()), None)
    if existing is None:
        raise CaseConfigError(
            f"каталог вывода {path}: диск {path.anchor} не найден. Укажите "
            f"другой каталог вывода. Расчёт не начат.")
    if not existing.is_dir():
        head = (f"каталог вывода {path}" if existing == path
                else f"каталог вывода {path} не создать: {existing}")
        raise CaseConfigError(
            f"{head} — файл, а не каталог. Укажите другой каталог вывода. "
            f"Расчёт не начат.")


'''
src = patch(src, "def _check_output_free(output_dir: Path) -> None:\n",
            FUNC + "def _check_output_free(output_dir: Path) -> None:\n", "функция")

src = patch(src,
            "            f\"другой каталог вывода.\")\n    # Перевод в памяти — до очистки",
            "            f\"другой каталог вывода.\")\n"
            "    # Путь вывода — файл или проходит через файл, диска нет: отказ до чтения\n"
            "    # книги (DEBT-083); иначе write_files ниже падал FileExistsError с\n"
            "    # текстом, не называющим причину\n"
            "    _check_output_path(output_dir)\n"
            "    # Перевод в памяти — до очистки", "вызов у книги")

if EMU.exists():
    shutil.rmtree(EMU)
(EMU / "tests").mkdir(parents=True)
(EMU / "pipeline_patched.py").write_text(src, encoding="utf-8")

(EMU / "emu_plugin.py").write_text('''"""Подмена gpn_multiphase_solver.report.pipeline пропатченной копией (эмуляция DEBT-083)."""
import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import gpn_multiphase_solver.report as report  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "gpn_multiphase_solver.report.pipeline", Path(__file__).with_name("pipeline_patched.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)
report.pipeline = _mod
assert hasattr(_mod, "_check_output_path")
''', encoding="utf-8")

shutil.copy(SOLVER / "tests" / "conftest.py", EMU / "tests" / "conftest.py")

SOLVER_LINE = "SOLVER = Path(__file__).resolve().parents[1]"


def copy_test(name: str, edits) -> None:
    text = (SOLVER / "tests" / name).read_text(encoding="utf-8")
    text = patch(text, SOLVER_LINE, f"SOLVER = Path({str(SOLVER)!r})", f"{name}: SOLVER")
    for old, new, what in edits:
        text = patch(text, old, new, f"{name}: {what}")
    (EMU / "tests" / name).write_text(text, encoding="utf-8")


# ── test_output_dir.py: шаг 1 (4 теста) и шаг 2 (1 тест) ──
UNIT = '''# ── Путь вывода — файл (DEBT-083) ────────────────────────────

def test_output_path_file_refused(tmp_path):
    """Путь вывода — существующий файл: CaseConfigError «файл, а не каталог» с путём, файл не тронут."""
    f = tmp_path / "well_history.csv"
    f.write_text("1", encoding="utf-8")
    with pytest.raises(CaseConfigError, match="файл, а не каталог") as e:
        pipeline._check_output_path(f)
    assert str(f) in str(e.value) and "Расчёт не начат" in str(e.value)
    assert f.read_text(encoding="utf-8") == "1"


def test_output_path_under_file_refused(tmp_path):
    """Файл на месте каталога пути (well_history.csv\\\\sub, …\\\\a\\\\b): отказ называет этот файл; ничего не создано.

    mkdir(parents=True) на таком пути падает тем же FileExistsError, что и
    на самом файле (проба plan_path_checks.py DEBT-083), — после расчёта.
    """
    f = tmp_path / "well_history.csv"
    f.write_text("1", encoding="utf-8")
    for out in (f / "sub", f / "a" / "b"):
        with pytest.raises(CaseConfigError, match="файл, а не каталог") as e:
            pipeline._check_output_path(out)
        assert f"{out} не создать: {f}" in str(e.value)
    assert _names(tmp_path) == ["well_history.csv"]


def test_output_path_dir_or_missing_passes(tmp_path):
    """Существующий каталог и несуществующий путь внутри каталога проходят; проверка ничего не создаёт и не меняет."""
    out = _old_output(tmp_path)
    for p in (out, tmp_path / "new" / "out"):
        pipeline._check_output_path(p)
    assert _names(tmp_path) == ["out"] and _names(out) == OLD_FILES


@pytest.mark.skipif(sys.platform != "win32", reason="буквы дисков — только Windows")
def test_output_path_missing_drive_refused():
    """Диска нет (Q:\\\\out): ни одного существующего предка — отказ «диск … не найден»; mkdir после расчёта упал бы FileNotFoundError."""
    free = [d for d in "QRSTUVWXYZ" if not Path(f"{d}:\\\\").exists()]
    if not free:
        pytest.skip("все буквы дисков Q…Z заняты")
    with pytest.raises(CaseConfigError, match="не найден"):
        pipeline._check_output_path(Path(f"{free[0]}:\\\\out"))


'''
RUN_CASE = '''

def test_run_case_output_file_refused_before_run(tmp_path, monkeypatch, capsys):
    """Каталог вывода — файл или путь через файл: CaseConfigError до расчёта и до печати заголовка, файл цел (DEBT-083).

    Без проверки расчёт шёл целиком, а потом mkdir падал FileExistsError —
    трассировка, код 1, расчёт потерян. Simulator.run подменён на падение:
    отказ обязан прийти раньше расчёта.
    """
    # Своя подмена, а не _must_not_run модуля: её текст — о занятом каталоге
    def must_not_run(self, *args, **kwargs):
        raise AssertionError("расчёт начат при каталоге вывода — файле")
    monkeypatch.setattr(Simulator, "run", must_not_run)
    cfg = _small_case(tmp_path)
    f = tmp_path / "well_history.csv"
    f.write_text("1", encoding="utf-8")
    for out in (f, f / "sub"):
        with pytest.raises(CaseConfigError, match="файл, а не каталог"):
            run_case(cfg, out)
    assert capsys.readouterr().out == ""
    assert f.read_text(encoding="utf-8") == "1"
'''
od = (SOLVER / "tests" / "test_output_dir.py").read_text(encoding="utf-8")
assert od.endswith("\n")
copy_test("test_output_dir.py", [
    ("(DEBT-082).\n", "(DEBT-082, DEBT-083).\n", "заголовок"),
    ("    имя, неудача удаления переименованного каталога;\n",
     "    имя, неудача удаления переименованного каталога;\n"
     "  - _check_output_path (DEBT-083): путь вывода — файл, путь через файл,\n"
     "    нет диска — CaseConfigError; каталог и несуществующий путь внутри\n"
     "    каталога проходят, ничего не создаётся;\n", "докстринг"),
    ("@contextlib.contextmanager\ndef _hold_open_file", UNIT + "@contextlib.contextmanager\ndef _hold_open_file",
     "модульные тесты"),
    ("    assert _names(tmp_path) == [\"case\", \"out\"]\n",
     "    assert _names(tmp_path) == [\"case\", \"out\"]\n" + RUN_CASE, "тест run_case"),
])

# ── test_cli.py: шаг 2 ──
CLI = '''def test_output_file_returns_2(tmp_path, capsys, monkeypatch):
    """--output — существующий файл (имя CSV вместо каталога) → код 2 до расчёта, файл цел (DEBT-083).

    Раньше расчёт шёл целиком, затем mkdir падал FileExistsError:
    трассировка и код 1, расчёт потерян.
    """
    def must_not_run(self, *args, **kwargs):
        raise AssertionError("расчёт начат при --output, указывающем на файл")
    monkeypatch.setattr(Simulator, "run", must_not_run)

    cfg = _small_case(tmp_path)
    f = tmp_path / "well_history.csv"
    f.write_text("1", encoding="utf-8")
    assert cli.main(["run", str(cfg), "--output", str(f)]) == 2
    err = capsys.readouterr().err
    # cli.main передаёт run_case путь после resolve(); abspath его не меняет
    assert "файл, а не каталог" in err and str(f.resolve()) in err
    assert f.read_text(encoding="utf-8") == "1"


'''
copy_test("test_cli.py", [
    ("    занятый каталог вывода — тоже 2 до расчёта (DEBT-082),\n",
     "    занятый каталог вывода — тоже 2 до расчёта (DEBT-082),\n"
     "    путь --output — файл — тоже 2 до расчёта (DEBT-083),\n", "докстринг"),
    ("# ── Аргументы ─", CLI + "# ── Аргументы ─", "тест"),
])

# ── test_workbook_run.py: шаг 2 ──
BOOK = '''def test_output_file_refused_before_reading_book(tmp_path, monkeypatch):
    """Каталог вывода — файл или путь через файл: отказ «файл, а не каталог» до чтения книги, файл цел (DEBT-083).

    Без проверки книга читалась и переводилась, а write_files падал
    FileExistsError — «…\\\\input: Cannot create a file when that file
    already exists», о файле вместо каталога ни слова.
    """
    monkeypatch.setattr(Simulator, "run", _must_not_run)

    def must_not_read(*args, **kwargs):
        raise AssertionError("книга прочитана, хотя каталог вывода — файл")
    monkeypatch.setattr(pipeline, "read_workbook", must_not_read)
    book = _small_book(tmp_path / "b.xlsx")
    f = tmp_path / "прошлый.csv"
    f.write_text("1", encoding="utf-8")
    for out in (f, f / "sub"):
        with pytest.raises(CaseConfigError, match="файл, а не каталог"):
            run_case(book, out)
    assert f.read_text(encoding="utf-8") == "1"


'''
copy_test("test_workbook_run.py", [
    ("    не изменён (аудит 1, DEBT-082);\n",
     "    не изменён (аудит 1, DEBT-082);\n"
     "  - каталог вывода — файл или путь через файл — отказ до чтения книги,\n"
     "    файл цел (DEBT-083);\n", "докстринг"),
    ("def test_config_run_clears_output_after_run", BOOK + "def test_config_run_clears_output_after_run",
     "тест"),
])

# ── Правило докстрингов на объектах pipeline (tests/test_docs.py) ──
(EMU / "tests" / "test_emu_docs.py").write_text(f'''"""Правило D1–D7 test_docs.py на объектах pipeline пропатченного модуля."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("real_test_docs", Path({str(SOLVER / "tests" / "test_docs.py")!r}))
docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docs)
NAMES = [n for n in docs.API if ".report.pipeline." in n]


def test_patched_module_used():
    import gpn_multiphase_solver.report.pipeline as p
    assert hasattr(p, "_check_output_path")
    assert len(NAMES) == 4, NAMES


@pytest.mark.parametrize("name", NAMES)
def test_public_docstring_patched(name):
    assert not docs.docstring_problems(name), docs.docstring_problems(name)
''', encoding="utf-8")
print("собрано:", EMU)
