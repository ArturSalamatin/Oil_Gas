"""DEBT-082, аудит 1: план на копии дерева — правки шагов 1–5 дословно, затем тесты.

Копия — git archive <база> numerical_solver .gitignore в probes/emulate/ (удаляется
после разбора). Правки — строки «До:»/«После:» плана; каждая замена обязана найти
ровно одно вхождение. Тестовый файл tests/test_output_dir.py — сборка блоков
шагов 1–2. Запуск (из корня проекта):
  numerical_solver\\.venv\\Scripts\\python vault/issues/debt-082/probes/plan_emulate.py [база]
Потом из probes/emulate/numerical_solver — pytest интерпретатором основного venv.
"""

import io
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EMU = Path(__file__).resolve().parent / "emulate"
BASE = sys.argv[1] if len(sys.argv) > 1 else "49e75bd"

shutil.rmtree(EMU, ignore_errors=True)
EMU.mkdir()
tar = subprocess.run(["git", "archive", "--format=tar", BASE, "numerical_solver", ".gitignore"],
                     cwd=ROOT, capture_output=True, check=True).stdout
tarfile.open(fileobj=io.BytesIO(tar)).extractall(EMU)
S = EMU / "numerical_solver"


def edit(rel: str, old: str, new: str) -> None:
    p = EMU / rel
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    assert n == 1, f"{rel}: «{old[:60]}…» найдено {n} раз"
    p.write_text(text.replace(old, new), encoding="utf-8")


PIPE = "numerical_solver/gpn_multiphase_solver/report/pipeline.py"

# ── Шаг 1: импорты ──
edit(PIPE, "import platform\nimport shutil\nimport time\n",
     "import os\nimport platform\nimport shutil\nimport time\n")
edit(PIPE, "from ..io.xlsx_reader import WorkbookError, read_workbook\nfrom ..simulator import Simulator\n",
     "from ..io.xlsx_reader import WorkbookError, read_workbook\nfrom ..log import user_log\n"
     "from ..simulator import Simulator\n")

# ── Шаг 1: функции перед _translate_workbook ──
HELPERS = '''def _sibling(path: Path, suffix: str) -> Path:
    """Свободное имя <имя каталога><suffix>[-k] рядом с каталогом path; корень диска — CaseConfigError. DEBT-082."""
    # abspath, а не resolve: resolve на сетевом диске и диске subst заменил
    # бы букву диска реальным путём (проба аудита 1), и сообщения назвали бы
    # путь, которого инженер не вводил
    path = Path(os.path.abspath(path))
    # У корня диска (D:\\) нет имени: соседнего каталога нет, переименовать
    # корень нельзя, а rmtree стёр бы весь диск. Отказ до любого действия
    if not path.name:
        raise CaseConfigError(
            f"каталог вывода {path} — корень диска: перед записью результатов "
            f"каталог очищается целиком. Укажите подкаталог.")
    k = 0
    while True:
        cand = path.with_name(f"{path.name}{suffix}" + (f"-{k}" if k else ""))
        if not cand.exists():
            return cand
        k += 1


def _busy_message(output_dir: Path, exc: OSError) -> str:
    """Текст отказа очистки каталога вывода: причина ОС и подсказка. DEBT-082."""
    return (f"каталог вывода {output_dir} не удаётся очистить ({exc.strerror or exc}): "
            f"файл в нём открыт в другой программе (например, CSV в Excel) или "
            f"каталог — текущий в консоли. Закройте файл или перейдите в консоли "
            f"в другой каталог")


def _check_output_free(output_dir: Path) -> None:
    """Каталог вывода удаляется целиком: проба переименованием туда и обратно, иначе CaseConfigError. DEBT-082."""
    # Windows не переименовывает каталог, в котором открыт файл без права
    # удаления (так открывает Excel) или который служит текущим каталогом
    # процесса, — и ничего при этом не трогает. rmtree на том же каталоге
    # удалил бы часть файлов, а при консоли в каталоге — все, и только
    # потом упал бы (пробы DEBT-082, vault/issues/debt-082/probes/).
    # Файл, открытый с правом удаления, переименование тоже не пропускает,
    # хотя rmtree прошёл бы, — отказ с запасом. На POSIX переименование
    # проходит, как и rmtree
    if not output_dir.is_dir():
        return
    probe = _sibling(output_dir, f".check-{os.getpid()}")
    try:
        os.rename(output_dir, probe)
    except OSError as exc:
        raise CaseConfigError(
            f"{_busy_message(output_dir, exc)} и повторите расчёт. Расчёт не "
            f"начат, каталог не изменён.") from exc
    try:
        os.rename(probe, output_dir)
    except OSError as exc:
        raise CaseConfigError(
            f"каталог вывода {output_dir} при проверке переименован в {probe} и "
            f"не возвращён ({exc.strerror or exc}): верните ему прежнее имя и "
            f"повторите расчёт.") from exc


def _clear_output(output_dir: Path) -> None:
    """Очистка каталога вывода: переименование в соседний, затем его удаление; OSError переименования — каталог цел. DEBT-082."""
    # Переименование — точка невозврата. Прошло — каталог свободен (см.
    # _check_output_free), удаляется уже переименованный. Не прошло —
    # OSError вызывающему, ни один файл не тронут: прямой rmtree успевал
    # удалить часть файлов до отказа (проба аудита 1 FEAT-036)
    if not output_dir.is_dir():
        return
    trash = _sibling(output_dir, f".old-{os.getpid()}")
    os.rename(output_dir, trash)
    try:
        shutil.rmtree(trash)
    except OSError as exc:
        # Файл открыли в уже переименованном каталоге — почти невозможно, но
        # прежние результаты под чужим именем не должны остаться молча
        user_log.warning(f"прежние результаты перенесены в {trash} и не удалены "
                         f"({exc.strerror or exc}); удалите этот каталог вручную.")


def _translate_workbook('''
edit(PIPE, "def _translate_workbook(", HELPERS)

# ── Шаг 2: проверка до расчёта ──
edit(PIPE, """        _check_inputs_outside(config_path, config, output_dir)
""", """        _check_inputs_outside(config_path, config, output_dir)
        # Занятый каталог вывода (файл открыт в Excel, консоль в каталоге) —
        # отказ до расчёта, а не трассировка после него (DEBT-082). У книги
        # каталог уже очищен в _translate_workbook
        _check_output_free(output_dir)
""")

# ── Шаг 2: очистка после расчёта ──
edit(PIPE, """    # перевода (_translate_workbook), в нём только input/ этого расчёта.
    if workbook is None and output_dir.is_dir():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
""", """    # перевода (_translate_workbook), в нём только input/ этого расчёта.
    # Очистка переименованием (_clear_output, DEBT-082): каталог заняли во
    # время расчёта (проверка до расчёта прошла) — ни один файл не удалён,
    # а расчёт не теряется: результаты пишутся в соседний каталог с датой и
    # временем в имени, прежний не тронут (решение пользователя
    # 2026-10-18). Расчёт выполнен — код команды 0, CaseResult.output_dir —
    # новый каталог
    if workbook is None and output_dir.is_dir():
        try:
            _clear_output(output_dir)
        except OSError as exc:
            busy = output_dir
            output_dir = _sibling(busy, time.strftime("_%Y-%m-%d_%H-%M-%S"))
            user_log.warning(f"{_busy_message(busy, exc)}. Результаты записаны в "
                             f"{output_dir}; прежние результаты в {busy} не тронуты.")
    output_dir.mkdir(parents=True, exist_ok=True)
""")

# ── Шаг 3: очистка у книги ──
edit(PIPE, """    # остаётся input/ — вход, на котором расчёт остановился
    if output_dir.is_dir():
        try:
            shutil.rmtree(output_dir)
        except OSError as exc:
            # Windows: файл каталога открыт в другой программе (CSV в Excel) —
            # WinError 32, rmtree успевает удалить часть файлов (аудит 1). Расчёт
            # ещё не начат: отказ с подсказкой, а не трассировка (у конфига — DEBT-082)
            raise CaseConfigError(
                f"каталог вывода {output_dir} очищен не полностью — {exc.filename}: "
                f"{exc.strerror}. Файл открыт в другой программе? Закройте его и "
                f"повторите расчёт.") from exc
""", """    # остаётся input/ — вход, на котором расчёт остановился.
    # Очистка переименованием (_clear_output, DEBT-082): каталог занят (файл
    # открыт в Excel, консоль в каталоге) — отказ с подсказкой, ни один файл
    # не удалён; прямой rmtree успевал удалить часть (аудит 1 FEAT-036).
    # Корень диска _clear_output отвергает сам (CaseConfigError)
    try:
        _clear_output(output_dir)
    except OSError as exc:
        raise CaseConfigError(
            f"{_busy_message(output_dir, exc)} и повторите расчёт. Расчёт не "
            f"начат, каталог не изменён.") from exc
""")

# ── Шаг 3: тест книги ──
WR = "numerical_solver/tests/test_workbook_run.py"
edit(WR, '''    def locked(path, *args, **kwargs):
        raise PermissionError(13, "файл занят", str(Path(path) / "well_history.csv"))
    monkeypatch.setattr(pipeline.shutil, "rmtree", locked)
    with pytest.raises(CaseConfigError, match="открыт в другой программе") as e:
        run_case(book)
    assert str(out) in str(e.value) and "well_history.csv" in str(e.value)
''', '''    real = os.rename

    def locked(src, dst):
        if Path(src).resolve() == out.resolve():
            raise PermissionError(13, "Access is denied", str(src))
        return real(src, dst)
    monkeypatch.setattr(pipeline.os, "rename", locked)
    with pytest.raises(CaseConfigError, match="открыт в другой программе") as e:
        run_case(book)
    assert str(out) in str(e.value) and "Расчёт не начат" in str(e.value)
    # Очистка переименованием: прежний каталог не изменён
    assert [p.name for p in out.iterdir()] == ["прошлый.csv"]
''')

# ── Шаг 2: тест команды ──
CLI_T = "numerical_solver/tests/test_cli.py"
edit(CLI_T, '''    assert "содержит входной файл" in capsys.readouterr().err

''', '''    assert "содержит входной файл" in capsys.readouterr().err


def test_busy_output_returns_2(tmp_path, capsys, monkeypatch):
    """Каталог вывода занят (файл открыт в другой программе) → код 2 до расчёта, без трассировки, файлы целы (DEBT-082).

    os.rename каталога вывода подменён на отказ, как Windows при открытом
    CSV (WinError 5): тест не зависит от ОС.
    """
    def must_not_run(self, *args, **kwargs):
        raise AssertionError("расчёт начат при занятом каталоге вывода")
    monkeypatch.setattr(Simulator, "run", must_not_run)

    cfg = _small_case(tmp_path)
    out = cfg.parent / "output"
    out.mkdir()
    (out / "well_history.csv").write_text("1", encoding="utf-8")
    real = os.rename

    def locked(src, dst):
        if Path(src).resolve() == out.resolve():
            raise PermissionError(13, "Access is denied", str(src))
        return real(src, dst)
    monkeypatch.setattr(os, "rename", locked)

    assert cli.main(["run", str(cfg)]) == 2
    err = capsys.readouterr().err
    assert "не удаётся очистить" in err and str(out.resolve()) in err
    assert "Traceback" not in err
    assert [p.name for p in out.iterdir()] == ["well_history.csv"]

''')

# ── Шаг 4: примеры и .gitignore ──
EX = "numerical_solver/examples"
e01 = f"{EX}/01_single_phase_no_jt/main.py"
t = (EMU / e01).read_text(encoding="utf-8")
assert t.count('output_dir=here / "output",') == 2 and t.count('export_emf(here / "output")') == 1
t = t.replace('output_dir=here / "output",', "output_dir=r.output_dir,").replace(
    'export_emf(here / "output")', "export_emf(r.output_dir)")
(EMU / e01).write_text(t, encoding="utf-8")
e02 = f"{EX}/02_single_phase_jt/main.py"
t = (EMU / e02).read_text(encoding="utf-8")
assert t.count('here / "output"') == 4
t = t.replace('run_case(here / "config.json", here / "output")', "RUN_CASE_KEEP")
t = t.replace('here / "output"', "r.output_dir").replace(
    "RUN_CASE_KEEP", 'run_case(here / "config.json", here / "output")')
(EMU / e02).write_text(t, encoding="utf-8")
e05 = f"{EX}/05_standing_table_rp/main.py"
t = (EMU / e05).read_text(encoding="utf-8")
assert t.count('here / "output"') == 3
t = t.replace('run_case(here / "config.json", here / "output")', "RUN_CASE_KEEP")
t = t.replace('here / "output"', "r.output_dir").replace(
    "RUN_CASE_KEEP", 'run_case(here / "config.json", here / "output")')
(EMU / e05).write_text(t, encoding="utf-8")
edit(f"{EX}/18_prototype_input/main.py", '''    output = here / "output"
''', "")
edit(f"{EX}/18_prototype_input/main.py", '''    r = run_case(here / "config.json", output)
''', '''    r = run_case(here / "config.json", here / "output")
    # Каталог, куда run_case записал результаты: при занятом here/output —
    # соседний с датой и временем в имени (DEBT-082)
    output = r.output_dir
''')
edit(".gitignore", "numerical_solver/examples/**/output/\n",
     "numerical_solver/examples/**/output/\n"
     "# Соседний каталог вывода при занятом output/ (output_<дата>_<время>) и\n"
     "# временные имена очистки (output.check-<pid>, output.old-<pid>) — DEBT-082\n"
     "numerical_solver/examples/**/output[._]*/\n")

# ── Шаг 5: эпилог справки ──
edit("numerical_solver/gpn_multiphase_solver/cli.py", '''        epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; "
               "2 — ошибка аргументов, конфига или книги. Каталог вывода "
               "очищается целиком: при расчёте по конфигу — после расчёта, "
               "по книге — до него.")''', '''        epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; "
               "2 — ошибка аргументов, конфига или книги, занятый каталог "
               "вывода. Каталог вывода очищается целиком: при расчёте по "
               "конфигу — после расчёта, по книге — до него. Если файл "
               "каталога открыт в другой программе — отказ до расчёта; если "
               "его открыли во время расчёта — результаты в соседнем каталоге "
               "с датой и временем в имени.")''')

# ── Шаги 1–2: новый тестовый файл (блоки плана) ──
src = (Path(__file__).resolve().parent / "plan_code" / "test_output_dir.py").read_text(encoding="utf-8")
(S / "tests" / "test_output_dir.py").write_text(src, encoding="utf-8")
print("правки применены:", EMU)
